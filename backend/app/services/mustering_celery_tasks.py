"""
Mustering Celery Tasks
Automated drill scheduling, notifications, and background tasks for mustering system
"""

from celery import Celery
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import logging
import json
import requests

import os

from app.core.database import engine
from app.services.mustering_service import MusteringService
from app.models.biotime_models import (
    MusteringDrillSchedule, MusteringEvent, MusteringEventTemplate,
    MusteringLog, MusteringEscalationRecord, EmergencyDevice, IClockDevcmd,
)
from app.models.zone import Zone
from sqlalchemy import and_, text

# Configure logging
logger = logging.getLogger(__name__)

_redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Initialize Celery
celery_app = Celery(
    'mustering_tasks',
    broker=_redis_url,
    backend=_redis_url,
    include=[
        'app.services.mustering_celery_tasks',
        'app.tasks.compliance_email_celery',
    ]
)

# ── Celery Beat schedules (single definition — do not add another below) ─────
from celery.schedules import crontab

# Database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@celery_app.task(bind=True, max_retries=3)
def check_scheduled_drills(self):
    """
    Check for scheduled drills and start them automatically
    Runs every minute
    """
    db = SessionLocal()
    
    try:
        logger.info("Checking for scheduled drills...")
        
        # Get current time
        now = datetime.utcnow()
        
        # Only pick up unprocessed drills — prevents double-trigger on Celery retry
        scheduled_drills = db.query(MusteringDrillSchedule).filter(
            MusteringDrillSchedule.scheduled_time <= now,
            MusteringDrillSchedule.auto_start == True,
            MusteringDrillSchedule.processed == False,
        ).all()
        
        started_drills = []
        
        for drill in scheduled_drills:
            try:
                # Check if there's already an active event for this zone
                active_event = db.query(MusteringEvent).filter(
                    MusteringEvent.zone_id == drill.zone_id,
                    MusteringEvent.status == 0  # Active
                ).first()
                
                if active_event:
                    logger.warning(f"Zone {drill.zone_id} already has active event, skipping scheduled drill")
                    continue
                
                # Load template for notification flags and display name (#12)
                template = None
                if drill.template_id:
                    template = db.query(MusteringEventTemplate).filter(
                        MusteringEventTemplate.id == drill.template_id
                    ).first()
                drill_name = template.template_name if template else "Scheduled drill"

                # Fix #3: zone_ids expects List[int]; no initiated_type param
                mustering_service = MusteringService(db)
                event_result = mustering_service.start_mustering_event(
                    zone_ids=[drill.zone_id],
                    event_type=drill.event_type,
                    initiated_by=drill.created_by or 0,
                    notify_sms=False,   # notifications handled by send_drill_notifications task
                    notify_email=False,
                    notify_whatsapp=False,
                    notify_siren=False,
                    notes=f"Automated drill: {drill_name}",
                )

                # Fix #12: populate notify flags from template so send_drill_notifications
                # actually dispatches SMS/email instead of silently skipping them
                started_drills.append({
                    'drill_id': drill.id,
                    'event_id': event_result['event_id'],
                    'zone_id': drill.zone_id,
                    'scheduled_time': drill.scheduled_time,
                    'started_time': now,
                    'notify_sms': template.notify_sms if template else False,
                    'notify_email': template.notify_email if template else False,
                    'notify_whatsapp': False,
                    'notify_siren': False,
                })
                
                # Update drill schedule to mark as processed
                drill.processed = True
                drill.processed_time = now
                db.commit()
                
                logger.info(f"✅ Started scheduled drill {drill.id} -> Event {event_result['event_id']}")
                
            except Exception as e:
                logger.error(f"❌ Error starting scheduled drill {drill.id}: {e}")
                db.rollback()
        
        # Send notification for started drills
        if started_drills:
            send_drill_notifications.delay(started_drills)
        
        # Clean up old processed drills (older than 7 days)
        cleanup_old_schedules()
        
    except Exception as e:
        logger.error(f"❌ Error in check_scheduled_drills task: {e}")
        db.rollback()
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def send_drill_notifications(self, drill_data):
    """
    Send notifications for started drills
    drill_data: List of dictionaries with drill information
    """
    try:
        logger.info(f"Sending drill notifications for {len(drill_data)} drills")
        
        for drill in drill_data:
            # Send SMS notifications
            if drill.get('notify_sms'):
                send_sms_notification.delay(
                    message=f"DRILL STARTED: Emergency drill initiated in Zone {drill['zone_id']}",
                    recipients=get_drill_recipients(drill['zone_id'], 'sms')
                )
            
            # Send Email notifications
            if drill.get('notify_email'):
                send_email_notification.delay(
                    subject=f"Emergency Drill Started - Zone {drill['zone_id']}",
                    message=f"An emergency drill has been initiated in Zone {drill['zone_id']} at {drill['started_time']}.",
                    recipients=get_drill_recipients(drill['zone_id'], 'email')
                )
            
            # Send WhatsApp notifications
            if drill.get('notify_whatsapp'):
                send_whatsapp_notification.delay(
                    message=f"🚨 DRILL: Emergency drill in Zone {drill['zone_id']}",
                    recipients=get_drill_recipients(drill['zone_id'], 'whatsapp')
                )
            
            # Trigger sirens
            if drill.get('notify_siren'):
                trigger_sirens.delay(drill['zone_id'])
        
        logger.info(f"✅ Drill notifications sent for {len(drill_data)} drills")
        
    except Exception as e:
        logger.error(f"❌ Error sending drill notifications: {e}")

@celery_app.task(bind=True, max_retries=3)
def send_emergency_notifications(self, event_data):
    """
    Send emergency notifications for real events
    event_data: Dictionary with event information
    """
    try:
        logger.info(f"Sending emergency notifications for event {event_data.get('event_id')}")
        
        event_id = event_data.get('event_id')
        zone_id = event_data.get('zone_id')
        event_type = event_data.get('event_type')
        
        # Get notification preferences from zone
        db = SessionLocal()
        try:
            zone = db.query(Zone).filter(Zone.id == zone_id).first()
            if not zone:
                logger.error(f"Zone {zone_id} not found for notifications")
                return
            
            # Determine event type name
            event_names = {
                0: "Real Emergency",
                1: "Drill", 
                2: "Fire Emergency",
                3: "Gas Emergency",
                4: "Man Down Emergency"
            }
            event_name = event_names.get(event_type, "Emergency")
            
            # Send notifications based on event type and preferences
            if event_data.get('notify_sms'):
                send_sms_notification.delay(
                    message=f"🚨 {event_name}: Emergency initiated in Zone {zone.name}",
                    recipients=get_emergency_recipients(zone_id, 'sms')
                )
            
            if event_data.get('notify_email'):
                send_email_notification.delay(
                    subject=f"🚨 {event_name} - Zone {zone.name}",
                    message=f"A {event_name.lower()} has been initiated in Zone {zone.name} at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}. Please proceed to your designated muster point immediately.",
                    recipients=get_emergency_recipients(zone_id, 'email')
                )
            
            if event_data.get('notify_whatsapp'):
                send_whatsapp_notification.delay(
                    message=f"🚨 {event_name} in Zone {zone.name} - Proceed to muster point immediately!",
                    recipients=get_emergency_recipients(zone_id, 'whatsapp')
                )
            
            if event_data.get('notify_siren'):
                trigger_sirens.delay(zone_id)
            
            logger.info(f"✅ Emergency notifications sent for event {event_id}")
            
        except Exception as e:
            logger.error(f"❌ Error sending emergency notifications: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Critical error in send_emergency_notifications: {e}")

@celery_app.task(bind=True, max_retries=3)
def send_muster_completion_notifications(self, event_data):
    """
    Send notifications when mustering event is completed
    event_data: Dictionary with event completion information
    """
    try:
        logger.info(f"Sending muster completion notifications for event {event_data.get('event_id')}")
        
        event_id = event_data.get('event_id')
        zone_id = event_data.get('zone_id')
        headcount = event_data.get('final_headcount', {})
        
        db = SessionLocal()
        try:
            zone = db.query(Zone).filter(Zone.id == zone_id).first()
            if not zone:
                logger.error(f"Zone {zone_id} not found for completion notifications")
                return
            
            total_expected = headcount.get('total_expected', 0)
            total_safe = headcount.get('total_safe', 0)
            total_missing = headcount.get('total_missing', 0)
            completion_percent = headcount.get('completion_percentage', 0)
            
            # Prepare message
            if total_missing == 0:
                status_msg = f"✅ All personnel accounted for ({total_safe}/{total_expected})"
                status_emoji = "✅"
            else:
                status_msg = f"⚠️ {total_missing} personnel still missing ({total_safe}/{total_expected})"
                status_emoji = "⚠️"
            
            # Send completion notifications
            send_sms_notification.delay(
                message=f"{status_emoji} Muster Complete: {status_msg} - {completion_percent:.1f}% accounted",
                recipients=get_emergency_recipients(zone_id, 'sms')
            )
            
            send_email_notification.delay(
                subject=f"Muster Complete - Zone {zone.name} - {completion_percent:.1f}%",
                message=f"""
Mustering event completed for Zone {zone.name}.

Summary:
- Total Expected: {total_expected}
- Safe: {total_safe}
- Missing: {total_missing}
- Completion: {completion_percent:.1f}%

{status_msg}

Event Duration: {event_data.get('duration', 'N/A')} minutes
                """,
                recipients=get_emergency_recipients(zone_id, 'email')
            )
            
            logger.info(f"✅ Muster completion notifications sent for event {event_id}")
            
        except Exception as e:
            logger.error(f"❌ Error sending completion notifications: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Critical error in send_muster_completion_notifications: {e}")

@celery_app.task(bind=True, max_retries=3)
def send_sms_notification(self, message, recipients):
    """Send SMS via generic HTTP provider (SMS_API_KEY + SMS_API_URL env vars)."""
    try:
        sms_api_key = os.getenv('SMS_API_KEY')
        sms_api_url = os.getenv('SMS_API_URL')
        if not sms_api_key or not sms_api_url:
            logger.warning("SMS not configured — set SMS_API_KEY and SMS_API_URL to enable")
            return
        logger.info(f"Sending SMS to {len(recipients)} recipients")
        for recipient in recipients:
            try:
                resp = requests.post(
                    sms_api_url,
                    json={'api_key': sms_api_key, 'to': recipient, 'message': message},
                    timeout=10,
                )
                resp.raise_for_status()
                logger.info(f"SMS sent to {recipient}")
            except Exception as exc:
                logger.error(f"SMS to {recipient} failed: {exc}")
    except Exception as e:
        logger.error(f"❌ send_sms_notification error: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_email_notification(self, subject, message, recipients):
    """Send email via SMTP (SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD env vars)."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASSWORD')
        email_from = os.getenv('EMAIL_FROM', smtp_user)
        if not smtp_host or not smtp_user:
            logger.warning("Email not configured — set SMTP_HOST, SMTP_USER, SMTP_PASSWORD to enable")
            return
        logger.info(f"Sending email '{subject}' to {len(recipients)} recipients")
        for recipient in recipients:
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = email_from
                msg['To'] = recipient
                msg.attach(MIMEText(message, 'plain'))
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(email_from, [recipient], msg.as_string())
                logger.info(f"Email sent to {recipient}")
            except Exception as exc:
                logger.error(f"Email to {recipient} failed: {exc}")
    except Exception as e:
        logger.error(f"❌ send_email_notification error: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_whatsapp_notification(self, message, recipients):
    """Send WhatsApp via generic HTTP provider (WHATSAPP_API_KEY + WHATSAPP_API_URL env vars)."""
    try:
        whatsapp_api_key = os.getenv('WHATSAPP_API_KEY')
        whatsapp_api_url = os.getenv('WHATSAPP_API_URL')
        if not whatsapp_api_key or not whatsapp_api_url:
            logger.warning("WhatsApp not configured — set WHATSAPP_API_KEY and WHATSAPP_API_URL to enable")
            return
        logger.info(f"Sending WhatsApp to {len(recipients)} recipients")
        for recipient in recipients:
            try:
                resp = requests.post(
                    whatsapp_api_url,
                    json={'api_key': whatsapp_api_key, 'to': recipient, 'message': message},
                    timeout=10,
                )
                resp.raise_for_status()
                logger.info(f"WhatsApp sent to {recipient}")
            except Exception as exc:
                logger.error(f"WhatsApp to {recipient} failed: {exc}")
    except Exception as e:
        logger.error(f"❌ send_whatsapp_notification error: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def trigger_sirens(self, zone_id):
    """
    Trigger emergency sirens and strobes in a zone by writing EMERGENCY_ON commands
    directly to the iclock_devcmd queue table, which ZKTeco devices poll via ADMS.
    zone_id: ID of the mustering zone (None = all zones)
    """
    try:
        logger.info(f"Triggering sirens for zone {zone_id}")
        db = SessionLocal()
        try:
            zone = db.query(Zone).filter(Zone.id == zone_id).first()
            if not zone:
                logger.error(f"Zone {zone_id} not found for siren activation")
                return

            # Query real siren/strobe devices (device_type 1=siren, 2=strobe), skip faulted
            query = db.query(EmergencyDevice).filter(
                EmergencyDevice.device_type.in_([1, 2]),
                EmergencyDevice.status != 2,  # not fault
            )
            if zone_id:
                query = query.filter(EmergencyDevice.zone_id == zone_id)
            devices = query.all()

            if not devices:
                logger.warning(f"No active siren/strobe devices found for zone {zone_id}")
                return

            activated = 0
            for device in devices:
                if not device.terminal_sn:
                    continue
                try:
                    cmd = IClockDevcmd(
                        sn=device.terminal_sn,
                        cmd_content="EMERGENCY_ON",
                        status=0,  # pending — ADMS polling loop will deliver it
                    )
                    db.add(cmd)
                    device.status = 1  # mark active
                    activated += 1
                except Exception as dev_err:
                    logger.error(f"Failed to queue EMERGENCY_ON for device {device.id}: {dev_err}")

            db.commit()
            logger.info(f"Sirens activated for zone {zone.name}: {activated} device commands queued")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error triggering sirens: {e}")
            raise self.retry(exc=e, countdown=30)
        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Critical error in trigger_sirens: {e}")


@celery_app.task(max_retries=3)
def cleanup_old_schedules():
    """
    Clean up old processed drill schedules (runs nightly via Celery beat).
    """
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        old_schedules = db.query(MusteringDrillSchedule).filter(
            MusteringDrillSchedule.processed == True,
            MusteringDrillSchedule.processed_time < cutoff_date
        ).all()

        for schedule in old_schedules:
            db.delete(schedule)

        if old_schedules:
            db.commit()
            logger.info(f"✅ Cleaned up {len(old_schedules)} old drill schedules")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error cleaning up old schedules: {e}")
    finally:
        db.close()
        db.rollback()

def get_drill_recipients(zone_id, notification_type):
    """
    Query personnel with emergency_contact or safety role for the given zone.
    Falls back to an empty list so drills are never blocked by a missing contact.
    """
    db = SessionLocal()
    try:
        if notification_type == 'email':
            rows = db.execute(text("""
                SELECT DISTINCT au.email
                FROM auth_user au
                JOIN auth_user_role ur ON ur.user_id = au.id
                JOIN auth_role r ON r.id = ur.role_id
                WHERE au.is_active = TRUE
                  AND au.email IS NOT NULL AND au.email != ''
                  AND (r.name ILIKE '%safety%' OR r.name ILIKE '%hse%'
                       OR r.name ILIKE '%emergency%' OR r.name ILIKE '%muster%')
            """)).fetchall()
            return [r[0] for r in rows]
        elif notification_type in ('sms', 'whatsapp'):
            rows = db.execute(text("""
                SELECT DISTINCT p.phone
                FROM personnel p
                JOIN auth_user au ON au.id = p.user_id
                JOIN auth_user_role ur ON ur.user_id = au.id
                JOIN auth_role r ON r.id = ur.role_id
                WHERE au.is_active = TRUE
                  AND p.phone IS NOT NULL AND p.phone != ''
                  AND (r.name ILIKE '%safety%' OR r.name ILIKE '%hse%'
                       OR r.name ILIKE '%emergency%')
            """)).fetchall()
            return [r[0] for r in rows]
    except Exception as exc:
        logger.error("get_drill_recipients(%s, %s) error: %s", zone_id, notification_type, exc)
    finally:
        db.close()
    return []


def get_emergency_recipients(zone_id, notification_type):
    """
    Like get_drill_recipients but also includes on-call / emergency-team roles.
    """
    db = SessionLocal()
    try:
        if notification_type == 'email':
            rows = db.execute(text("""
                SELECT DISTINCT au.email
                FROM auth_user au
                JOIN auth_user_role ur ON ur.user_id = au.id
                JOIN auth_role r ON r.id = ur.role_id
                WHERE au.is_active = TRUE
                  AND au.email IS NOT NULL AND au.email != ''
                  AND (r.name ILIKE '%safety%' OR r.name ILIKE '%hse%'
                       OR r.name ILIKE '%emergency%' OR r.name ILIKE '%oncall%'
                       OR au.is_superuser = TRUE)
            """)).fetchall()
            return [r[0] for r in rows]
        elif notification_type in ('sms', 'whatsapp'):
            rows = db.execute(text("""
                SELECT DISTINCT p.phone
                FROM personnel p
                JOIN auth_user au ON au.id = p.user_id
                JOIN auth_user_role ur ON ur.user_id = au.id
                JOIN auth_role r ON r.id = ur.role_id
                WHERE au.is_active = TRUE
                  AND p.phone IS NOT NULL AND p.phone != ''
                  AND (r.name ILIKE '%safety%' OR r.name ILIKE '%hse%'
                       OR r.name ILIKE '%emergency%' OR r.name ILIKE '%oncall%')
            """)).fetchall()
            return [r[0] for r in rows]
    except Exception as exc:
        logger.error("get_emergency_recipients(%s, %s) error: %s", zone_id, notification_type, exc)
    finally:
        db.close()
    return []

@celery_app.task(bind=True, max_retries=3)
def check_missing_escalations(self):
    """
    Scan all active mustering events for persons missing beyond the 10 / 20 / 30-minute
    escalation thresholds and fire a notification for each new threshold crossed.

    Runs every 5 minutes via beat schedule.
    De-duplicated via the mustering_escalation_record table so each level is only
    notified once per person per event.
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        active_events = db.query(MusteringEvent).filter(MusteringEvent.status == 0).all()

        total_notified = 0
        new_by_level = {}
        for event in active_events:
            start = event.start_time
            if hasattr(start, 'tzinfo') and start.tzinfo is not None:
                start = start.replace(tzinfo=None)
            minutes_elapsed = (now - start).total_seconds() / 60

            missing_logs = db.query(MusteringLog).filter(
                and_(MusteringLog.event_id == event.id, MusteringLog.status == 0)
            ).all()

            zone_name = event.zone.name if event.zone else f"Event {event.id}"

            for log in missing_logs:
                thresholds = [
                    (10, 1, 'ALERT',
                        f"⚠️  {log.emp_name or log.emp_code} has been MISSING for 10 minutes in {zone_name}."),
                    (20, 2, 'SEARCH_ORDERED',
                        f"🔴  {log.emp_name or log.emp_code} MISSING 20 minutes — search team should be deployed in {zone_name}."),
                    (30, 3, 'CRITICAL',
                        f"🚨  CRITICAL: {log.emp_name or log.emp_code} MISSING 30+ minutes in {zone_name}. Escalate immediately."),
                    (60, 4, 'MAYDAY',
                        f"🆘  MAYDAY: {log.emp_name or log.emp_code} MISSING 60+ minutes in {zone_name}. "
                        f"Initiate Search and Rescue / notify coast guard per facility emergency plan."),
                ]

                for threshold_min, level, notif_type, msg in thresholds:
                    if minutes_elapsed < threshold_min:
                        continue

                    already_sent = db.query(MusteringEscalationRecord).filter(
                        and_(
                            MusteringEscalationRecord.event_id == event.id,
                            MusteringEscalationRecord.emp_code == log.emp_code,
                            MusteringEscalationRecord.level == level,
                        )
                    ).first()

                    if already_sent:
                        continue

                    logger.warning(f"MUSTER ESCALATION [{notif_type}] event={event.id}: {msg}")

                    # Persist to sys_notifications and push via SSE
                    dedup_key = f"muster_esc_{event.id}_{log.emp_code}_{level}"
                    db.execute(text("""
                        INSERT INTO sys_notifications
                            (dedup_key, notification_type, title, message, priority, expires_at)
                        VALUES (:dk, :nt, :title, :msg, :pri, NOW() + INTERVAL '48 hours')
                        ON CONFLICT (dedup_key) DO NOTHING
                    """), {
                        "dk": dedup_key,
                        "nt": "muster_escalation",
                        "title": f"Muster Escalation [{notif_type}]",
                        "msg": msg,
                        "pri": "critical" if level >= 2 else "high",
                    })
                    from app.api.notifications import notify_sync
                    notify_sync({
                        "type": "muster_escalation",
                        "priority": "critical" if level >= 2 else "high",
                        "title": f"Muster Escalation [{notif_type}]",
                        "message": msg,
                        "dedup_key": dedup_key,
                        "event_id": event.id,
                        "emp_code": log.emp_code,
                        "level": level,
                    })
                    # External alert: ONE message per event per level to the response
                    # team (not one per missing person), sent after the loop.
                    new_by_level.setdefault((event, level, notif_type, threshold_min), []).append(
                        log.emp_name or log.emp_code)

                    record = MusteringEscalationRecord(
                        event_id=event.id,
                        emp_code=log.emp_code,
                        level=level,
                        notification_type=notif_type,
                    )
                    db.add(record)
                    total_notified += 1

        db.commit()

        from app.services.notify_dispatch import dispatch_background
        for (event, level, notif_type, mins), names in new_by_level.items():
            label = {1: "STILL MISSING", 2: "SEARCH NEEDED", 3: "CRITICAL", 4: "MAYDAY"}.get(level, notif_type)
            head = (f"{'DRILL — ' if event.event_type == 1 else ''}MUSTER {label} — "
                    f"{len(names)} unaccounted after {mins} min")
            body = (f"{head}: " + ", ".join(names[:20]) + ("…" if len(names) > 20 else "") + ". "
                    + {1: "Wardens: check your areas and radios.",
                       2: "Deploy the search team to last known locations (ApexPOB → Missing persons).",
                       3: "Escalate to the OIM / site manager now.",
                       4: "Start search and rescue per the emergency response plan."}.get(level, ""))
            dispatch_background("muster_escalation", event.id, [], head, body,
                                channels=event.notify_channels or None, include_responders=True)
        logger.info(f"check_missing_escalations: {len(active_events)} active events, {total_notified} new escalations fired")

    except Exception as exc:
        logger.error(f"check_missing_escalations error: {exc}")
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def check_overdue_journeys(self):
    """Autonomously detect land journeys (JMP) that have missed their check-in call
    or overshot their ETA, and escalate to the control room — without anyone having
    to be watching the board. Runs every 3 minutes; each distinct missed window is
    escalated once (dedup via sys_notifications)."""
    from app.models.journey import JourneyPlan
    GRACE = 10  # minutes past due before we escalate
    db = SessionLocal()
    try:
        now = datetime.utcnow()

        def _naive(dt):
            if dt is None:
                return None
            return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt

        in_progress = db.query(JourneyPlan).filter(JourneyPlan.status == "IN_PROGRESS").all()
        fired = 0
        for j in in_progress:
            due = _naive(j.next_checkin_due)
            eta = _naive(j.planned_arrival)
            trigger = None
            if due and now > due + timedelta(minutes=GRACE):
                trigger = due
            if eta and now > eta + timedelta(minutes=GRACE):
                trigger = min(trigger, eta) if trigger else eta
            if not trigger:
                continue

            dedup_key = f"journey_overdue_{j.id}_{trigger.isoformat()}"
            # Escalate ONCE per missed window — when the driver checks in, next_checkin_due
            # advances and a later miss produces a new key.
            exists = db.execute(
                text("SELECT 1 FROM sys_notifications WHERE dedup_key = :dk"), {"dk": dedup_key}
            ).first()
            if exists:
                continue

            mins = int((now - trigger).total_seconds() // 60)
            ref = j.reference or f"JMP-{j.id}"
            msg = (f"🚗 OVERDUE JOURNEY {ref}: {j.driver_name or 'driver'} "
                   f"({j.vehicle_reg or 'vehicle'}) {j.origin} → {j.destination} — no check-in for "
                   f"{mins} min. Contact the driver and follow the journey-management escalation plan.")

            db.execute(text("""
                INSERT INTO sys_notifications
                    (dedup_key, notification_type, title, message, priority, expires_at)
                VALUES (:dk, 'journey_overdue', :title, :msg, 'critical', NOW() + INTERVAL '48 hours')
                ON CONFLICT (dedup_key) DO NOTHING
            """), {"dk": dedup_key, "title": f"Overdue Journey {ref}", "msg": msg})

            from app.api.notifications import notify_sync
            notify_sync({
                "type": "journey_overdue", "priority": "critical",
                "title": f"Overdue Journey {ref}", "message": msg,
                "dedup_key": dedup_key, "journey_id": j.id,
            })

            # External escalation to the control room / on-call
            recips_sms = get_emergency_recipients(None, "sms")
            # Include the driver's own number when we can resolve it
            if j.driver_personnel_id:
                drow = db.execute(
                    text("SELECT phone FROM personnel WHERE id = :pid"),
                    {"pid": j.driver_personnel_id},
                ).first()
                if drow and drow[0]:
                    recips_sms = list({*(recips_sms or []), drow[0]})
            if recips_sms:
                send_sms_notification.delay(message=msg, recipients=recips_sms)
            recips_email = get_emergency_recipients(None, "email")
            if recips_email:
                send_email_notification.delay(
                    subject=f"Overdue Journey {ref}", message=msg, recipients=recips_email,
                )
            fired += 1

        db.commit()
        logger.info("check_overdue_journeys: %d in progress, %d escalations", len(in_progress), fired)
    except Exception as exc:
        logger.error("check_overdue_journeys error: %s", exc)
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def pob_reconciliation(self):
    """Cross-check the headline POB across subsystems every 15 min and alert on a
    material discrepancy — so POB drift between musters is caught proactively rather
    than discovered during an emergency. Compares operational-zone occupancy against
    the on-board personnel count."""
    db = SessionLocal()
    try:
        zone_total = db.execute(text(
            "SELECT COALESCE(SUM(current_occupancy),0) FROM zones "
            "WHERE zone_type IS DISTINCT FROM 'MUSTER_POINT'"
        )).scalar() or 0
        onboard = db.execute(text(
            "SELECT COUNT(*) FROM personnel WHERE is_onboard = TRUE"
        )).scalar() or 0
        zone_total, onboard = int(zone_total), int(onboard)
        diff = abs(zone_total - onboard)
        # Tolerate small noise; alert on >5 people or >10% of the on-board population.
        threshold = max(5, int(0.10 * max(onboard, 1)))

        if diff > threshold:
            msg = (f"⚠️ POB reconciliation discrepancy: operational-zone occupancy = {zone_total} "
                   f"vs on-board personnel = {onboard} (Δ{diff}). Likely offline readers, missed "
                   f"punches or manual overrides — verify before relying on the headline POB.")
            dedup_key = f"pob_recon_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
            db.execute(text("""
                INSERT INTO sys_notifications
                    (dedup_key, notification_type, title, message, priority, expires_at)
                VALUES (:dk, 'pob_reconciliation', 'POB Discrepancy', :msg, 'high', NOW() + INTERVAL '24 hours')
                ON CONFLICT (dedup_key) DO NOTHING
            """), {"dk": dedup_key, "msg": msg})
            from app.api.notifications import notify_sync
            notify_sync({"type": "pob_reconciliation", "priority": "high",
                         "title": "POB Discrepancy", "message": msg, "dedup_key": dedup_key})
            logger.warning(msg)

        db.commit()
        logger.info("pob_reconciliation: zone=%d onboard=%d diff=%d (threshold=%d)",
                    zone_total, onboard, diff, threshold)
    except Exception as exc:
        logger.error("pob_reconciliation error: %s", exc)
        db.rollback()
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2)
def seamlesshr_reconcile(self):
    """Nightly reconciliation with SeamlessHR — full employee-master pull + leave
    refresh — so any webhook events missed during the day are caught, and muster
    rosters stay leave-accurate. No-op when SeamlessHR isn't configured."""
    import asyncio
    from app.services.seamlesshr_service import get_config, pull_employees, pull_leave
    db = SessionLocal()
    try:
        if not get_config(db):
            logger.info("seamlesshr_reconcile: SeamlessHR not configured — skipping")
            return
        emp = asyncio.run(pull_employees(db, triggered_by="scheduled"))
        lv = asyncio.run(pull_leave(db, triggered_by="scheduled"))
        logger.info("seamlesshr_reconcile: employees=%s leave=%s", emp, lv)
    except Exception as e:
        logger.error("seamlesshr_reconcile error: %s", e)
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(max_retries=3)
def daily_auto_checkout():
    """Daily: if enabled in Settings → Database, check out anyone whose last punch
    was an entry more than N days ago (a forgotten check-in). No-op when disabled.
    Shares the exact logic used by the manual button in the Database tab."""
    from app.services import database_admin_service as dbadmin
    db = SessionLocal()
    try:
        cfg = dbadmin.get_settings(db)
        if not cfg.get("auto_checkout_enabled"):
            logger.info("daily_auto_checkout: disabled — skipping")
            return {"skipped": True}
        res = dbadmin.auto_checkout_stale(db, cfg.get("auto_checkout_days", 1))
        logger.info("daily_auto_checkout: %s", res)
        return res
    except Exception as e:
        logger.error("daily_auto_checkout error: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task
def run_due_report_schedules():
    """Scheduled reports: build + email whatever is due (report_scheduler)."""
    from app.services.report_scheduler import run_due
    db = SessionLocal()
    try:
        n = run_due(db)
        if n:
            logger.info("run_due_report_schedules: ran %d schedule(s)", n)
        return {"ran": n}
    except Exception as e:
        logger.error("run_due_report_schedules error: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task
def snapshot_pob():
    """Record today's POB (latest, peak, low, by company) for the POB trend report.
    There was no history of POB at all — only "now"."""
    from sqlalchemy import text as _t
    from app.services.attendance_calculation_service import SITE_TZ
    db = SessionLocal()
    try:
        today = datetime.now(SITE_TZ).date()
        rows = db.execute(_t("""
            SELECT COALESCE(NULLIF(company, ''), 'Unknown') AS company, COUNT(*) AS n
            FROM personnel WHERE is_onboard = TRUE AND is_active = TRUE GROUP BY 1
        """)).fetchall()
        by_company = {r.company: int(r.n) for r in rows}
        total = sum(by_company.values())
        db.execute(_t("""
            INSERT INTO pob_daily_snapshot (snap_date, pob_last, pob_peak, pob_low, by_company, updated_at)
            VALUES (:d, :n, :n, :n, CAST(:bc AS jsonb), now())
            ON CONFLICT (snap_date) DO UPDATE SET
                pob_last = EXCLUDED.pob_last,
                pob_peak = GREATEST(pob_daily_snapshot.pob_peak, EXCLUDED.pob_last),
                pob_low  = LEAST(COALESCE(pob_daily_snapshot.pob_low, EXCLUDED.pob_last), EXCLUDED.pob_last),
                by_company = EXCLUDED.by_company, updated_at = now()
        """), {"d": today, "n": total, "bc": __import__("json").dumps(by_company)})
        db.commit()
        return {"date": str(today), "pob": total}
    except Exception as e:
        logger.error("snapshot_pob error: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


celery_app.conf.beat_schedule = {
    'run-due-report-schedules': {
        'task': 'app.services.mustering_celery_tasks.run_due_report_schedules',
        'schedule': crontab(minute='*/5'),
    },
    'snapshot-pob': {
        'task': 'app.services.mustering_celery_tasks.snapshot_pob',
        'schedule': crontab(minute='*/15'),
    },
    'check-scheduled-drills': {
        'task': 'app.services.mustering_celery_tasks.check_scheduled_drills',
        'schedule': crontab(minute='*'),
    },
    'seamlesshr-nightly-reconcile': {
        'task': 'app.services.mustering_celery_tasks.seamlesshr_reconcile',
        'schedule': crontab(hour=2, minute=30),  # 02:30 UTC daily
    },
    'check-missing-escalations': {
        'task': 'app.services.mustering_celery_tasks.check_missing_escalations',
        'schedule': crontab(minute='*'),   # every minute — a 10-min threshold must not fire at 14
    },
    'check-overdue-journeys': {
        'task': 'app.services.mustering_celery_tasks.check_overdue_journeys',
        'schedule': crontab(minute='*/3'),
    },
    'pob-reconciliation': {
        'task': 'app.services.mustering_celery_tasks.pob_reconciliation',
        'schedule': crontab(minute='*/15'),
    },
    'compliance-digest-daily': {
        'task': 'app.tasks.compliance_email_celery.send_compliance_digest_task',
        'schedule': crontab(hour=6, minute=0),  # 06:00 UTC daily
        'args': (),
    },
    'daily-auto-checkout': {
        'task': 'app.services.mustering_celery_tasks.daily_auto_checkout',
        'schedule': crontab(hour=3, minute=0),  # 03:00 UTC daily
    },
}

import os


@celery_app.task(name="app.services.mustering_celery_tasks.dispatch_alert")
def dispatch_alert(source_type, source_id, people, subject, message, channels=None, include_responders=True):
    """Send one alert on every configured channel (see notify_dispatch)."""
    from app.services.notify_dispatch import dispatch
    return dispatch(source_type, source_id, people, subject, message, channels, include_responders)


@celery_app.task(name="app.services.mustering_celery_tasks.email_muster_list")
def email_muster_list():
    """Shift change: email the printable muster list to the response team."""
    from app.services.muster_list import email_to_responders
    db = SessionLocal()
    try:
        return email_to_responders(db)
    finally:
        db.close()


celery_app.conf.beat_schedule["email-muster-list-shift-change"] = {
    "task": "app.services.mustering_celery_tasks.email_muster_list",
    "schedule": crontab(minute=0, hour="5,17"),   # 06:00 and 18:00 Lagos (beat runs in UTC)
}


@celery_app.task(name="app.services.mustering_celery_tasks.sync_access_panels")
def sync_access_panels():
    """Nightly: load active staff onto every C3/inBio door panel AND every T&A
    terminal, and remove leavers from both."""
    from app.services.panel_sync import sync_all
    from app.services.ta_sync import sync_all_terminals
    db = SessionLocal()
    try:
        return {"panels": sync_all(db), "ta_terminals": sync_all_terminals(db)}
    finally:
        db.close()


celery_app.conf.beat_schedule["sync-access-panels-nightly"] = {
    "task": "app.services.mustering_celery_tasks.sync_access_panels",
    "schedule": crontab(minute=30, hour=1),   # 02:30 Lagos — after the SeamlessHR staff pull
}
