"""
Visitor Management Celery Tasks
BioTime 9.5 compatible background tasks with POB extensions
Auto-checkout, overstay alerts, and notification tasks
"""

from celery import Celery
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.models.visitor import VisitorVisitLog, VisitorType, Visitor, VisitorPreRegistration
from app.models.emergency import MusteringEvent, MusteringExpected, MusteringLog
from app.services.visitor_service import VisitorService
from app.core.email import send_email
from app.core.sms import send_sms

# Initialize Celery
celery_app = Celery('visitor_tasks')

@celery_app.task
def auto_checkout_visitors():
    """
    Auto-checkout visitors at end of day
    Runs daily at 23:59
    """
    try:
        db = next(get_db())
        visitor_service = VisitorService(db)
        
        # Get all visitor types with auto_checkout enabled
        auto_checkout_types = db.query(VisitorType).filter(
            VisitorType.auto_checkout == True
        ).all()
        
        type_ids = [t.id for t in auto_checkout_types]
        
        if not type_ids:
            print("No visitor types with auto-checkout enabled")
            return
        
        # Get visitors still checked in with auto-checkout types
        cutoff_time = datetime.utcnow() - timedelta(hours=24)  # 24 hour limit
        active_visits = db.query(VisitorVisitLog).join(Visitor).join(VisitorType).filter(
            and_(
                VisitorVisitLog.status == 0,  # still checked in
                VisitorVisitLog.check_in_time < cutoff_time,  # older than 24 hours
                VisitorType.id.in_(type_ids),  # auto-checkout enabled
                VisitorType.auto_checkout == True
            )
        ).all()
        
        auto_checkout_count = 0
        for visit in active_visits:
            try:
                # Auto check-out
                visit.check_out_time = datetime.utcnow()
                visit.status = 1  # checked out
                
                # Remove from devices
                visitor_service._remove_visitor_from_device(visit.visitor_id)
                
                # Update mustering if active event
                active_event = db.query(MusteringEvent).filter(
                    MusteringEvent.status == 0
                ).first()
                
                if active_event and visit.mustering_zone_id:
                    mustering_log = MusteringLog(
                        event_id=active_event.id,
                        visitor_id=visit.visitor_id,
                        mustering_zone_id=visit.mustering_zone_id,
                        status=1,  # marked as safe on auto-checkout
                        log_time=datetime.utcnow()
                    )
                    db.add(mustering_log)
                
                auto_checkout_count += 1
                
                # Send notification to host
                if visit.host_employee and visit.host_employee.email:
                    send_email(
                        to_email=visit.host_employee.email,
                        subject='Visitor Auto-Checked Out',
                        template='visitor_auto_checkout',
                        data={
                            'visitor_name': visit.visitor.full_name,
                            'check_in_time': visit.check_in_time,
                            'auto_checkout_time': visit.check_out_time
                        }
                    )
                
            except Exception as e:
                print(f"Failed to auto-checkout visitor {visit.id}: {e}")
                continue
        
        db.commit()
        print(f"Auto-checked out {auto_checkout_count} visitors")
        
    except Exception as e:
        print(f"Auto-checkout task failed: {e}")
    finally:
        db.close()


@celery_app.task
def check_overstay_visitors():
    """
    Check for overstayed visitors and send alerts
    Runs every hour
    """
    try:
        db = next(get_db())
        
        # Get all visitor types with their default visit hours
        visitor_types = db.query(VisitorType).all()
        type_hours = {t.id: t.default_visit_hours for t in visitor_types}
        
        overstays = []
        
        # Check each active visit
        active_visits = db.query(VisitorVisitLog).join(Visitor).join(VisitorType).filter(
            VisitorVisitLog.status == 0  # still checked in
        ).all()
        
        for visit in active_visits:
            # Get allowed hours for this visitor type
            allowed_hours = type_hours.get(visit.visitor.visitor_type_id, 8)
            
            # Calculate time since check-in
            # check_in_time is timezone-aware; naive utcnow() raised TypeError for every
            # visitor on site, so this task crashed and no overstay alert was ever sent.
            ci = visit.check_in_time
            if ci.tzinfo is None:
                ci = ci.replace(tzinfo=timezone.utc)
            time_since_checkin = datetime.now(timezone.utc) - ci
            hours_overdue = (time_since_checkin.total_seconds() / 3600) - allowed_hours
            
            if hours_overdue > 0 and not visit.overstay_alert_sent:
                overstays.append({
                    'visit': visit,
                    'hours_overdue': hours_overdue
                })
        
        # Send alerts for overstays
        for overstay in overstays:
            visit = overstay['visit']
            hours_overdue = overstay['hours_overdue']
            
            try:
                # Mark alert as sent
                visit.overstay_alert_sent = True
                visit.status = 2  # overstay status
                
                # Send email to host
                if visit.host_employee and visit.host_employee.email:
                    send_email(
                        to_email=visit.host_employee.email,
                        subject='Visitor Overstay Alert',
                        template='visitor_overstay',
                        data={
                            'visitor_name': visit.visitor.full_name,
                            'company': visit.visitor.company,
                            'check_in_time': visit.check_in_time,
                            'hours_overdue': round(hours_overdue, 1),
                            'host_name': visit.host_employee.full_name
                        }
                    )
                
                # Send SMS to host
                if visit.host_employee and visit.host_employee.phone:
                    send_sms(
                        to_phone=visit.host_employee.phone,
                        message=f"ALERT: Visitor {visit.visitor.full_name} from {visit.visitor.company or 'Unknown'} has overstayed by {round(hours_overdue, 1)} hours. Please arrange check-out."
                    )
                
                # Send SMS to visitor
                if visit.visitor.phone:
                    send_sms(
                        to_phone=visit.visitor.phone,
                        message=f"REMINDER: Your visit has exceeded the allowed time. Please check out at reception."
                    )
                
            except Exception as e:
                print(f"Failed to send overstay alert for visitor {visit.id}: {e}")
                continue
        
        db.commit()
        print(f"Processed {len(overstays)} overstay alerts")
        
    except Exception as e:
        print(f"Overstay check task failed: {e}")
    finally:
        db.close()


@celery_app.task
def cleanup_expired_pre_registrations():
    """
    Clean up expired pre-registrations
    Runs daily at midnight
    """
    try:
        db = next(get_db())
        
        # Mark pre-registrations as expired if visit date is past
        expiry_date = datetime.utcnow().date() - timedelta(days=1)
        
        expired_count = db.query(VisitorPreRegistration).filter(
            and_(
                VisitorPreRegistration.visit_date < expiry_date,
                VisitorPreRegistration.status.in_([0, 1])  # pending or approved
            )
        ).update({'status': 5})  # expired
        
        db.commit()
        print(f"Marked {expired_count} pre-registrations as expired")
        
    except Exception as e:
        print(f"Pre-registration cleanup task failed: {e}")
    finally:
        db.close()


@celery_app.task
def sync_visitor_mustering_status():
    """
    Sync visitor mustering status during active events
    Runs every 5 minutes during active mustering events
    """
    try:
        db = next(get_db())
        
        # Check for active mustering events
        active_event = db.query(MusteringEvent).filter(
            MusteringEvent.status == 0
        ).first()
        
        if not active_event:
            return  # No active event
        
        # Get all visitors checked in during the event
        active_visits = db.query(VisitorVisitLog).filter(
            and_(
                VisitorVisitLog.check_in_time >= active_event.start_time,
                VisitorVisitLog.status == 0  # still checked in
            )
        ).all()
        
        for visit in active_visits:
            # Check if visitor is in mustering expected
            expected = db.query(MusteringExpected).filter(
                and_(
                    MusteringExpected.event_id == active_event.id,
                    MusteringExpected.visitor_id == visit.visitor_id
                )
            ).first()
            
            if not expected:
                # Add to mustering expected if not already there
                expected = MusteringExpected(
                    event_id=active_event.id,
                    visitor_id=visit.visitor_id,
                    mustering_zone_id=visit.mustering_zone_id,
                    expected_time=datetime.utcnow()
                )
                db.add(expected)
                
                # Update visit log with mustering zone
                if not visit.mustering_zone_id:
                    visit.mustering_zone_id = expected.mustering_zone_id
        
        db.commit()
        print(f"Synced mustering status for {len(active_visits)} visitors")
        
    except Exception as e:
        print(f"Visitor mustering sync task failed: {e}")
    finally:
        db.close()


@celery_app.task
def send_visitor_reminders():
    """
    Send reminders for upcoming pre-registrations
    Runs daily at 08:00
    """
    try:
        db = next(get_db())
        
        # Get pre-registrations for today
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        
        upcoming_visits = db.query(VisitorPreRegistration).join(Visitor).filter(
            and_(
                VisitorPreRegistration.visit_date.in_([today, tomorrow]),
                VisitorPreRegistration.status == 1  # approved
            )
        ).all()
        
        for pre_reg in upcoming_visits:
            try:
                # Send reminder to visitor
                if pre_reg.visitor.email:
                    send_email(
                        to_email=pre_reg.visitor.email,
                        subject='Reminder: Your Visit Tomorrow',
                        template='visitor_reminder',
                        data={
                            'visitor_name': pre_reg.visitor.full_name,
                            'visit_date': pre_reg.visit_date,
                            'visit_time': pre_reg.visit_time_start,
                            'host_name': pre_reg.host_employee.full_name,
                            'purpose': pre_reg.purpose,
                            'qr_code': pre_reg.qr_code
                        }
                    )
                
                # Send reminder to host
                if pre_reg.host_employee.email:
                    send_email(
                        to_email=pre_reg.host_employee.email,
                        subject='Reminder: Visitor Tomorrow',
                        template='host_visitor_reminder',
                        data={
                            'visitor_name': pre_reg.visitor.full_name,
                            'company': pre_reg.visitor.company,
                            'visit_date': pre_reg.visit_date,
                            'visit_time': pre_reg.visit_time_start,
                            'purpose': pre_reg.purpose
                        }
                    )
                
            except Exception as e:
                print(f"Failed to send reminder for pre-registration {pre_reg.id}: {e}")
                continue
        
        print(f"Sent reminders for {len(upcoming_visits)} upcoming visits")
        
    except Exception as e:
        print(f"Visitor reminder task failed: {e}")
    finally:
        db.close()


# Schedule tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'auto-checkout-visitors': {
        'task': 'app.tasks.visitor_tasks.auto_checkout_visitors',
        'schedule': crontab(hour=23, minute=59),  # Daily at 23:59
    },
    'check-overstay-visitors': {
        'task': 'app.tasks.visitor_tasks.check_overstay_visitors',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-expired-pre-registrations': {
        'task': 'app.tasks.visitor_tasks.cleanup_expired_pre_registrations',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'sync-visitor-mustering-status': {
        'task': 'app.tasks.visitor_tasks.sync_visitor_mustering_status',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'send-visitor-reminders': {
        'task': 'app.tasks.visitor_tasks.send_visitor_reminders',
        'schedule': crontab(hour=8, minute=0),  # Daily at 08:00
    },
}
