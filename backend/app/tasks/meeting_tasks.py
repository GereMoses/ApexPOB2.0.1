import asyncio
"""
Meeting Management Celery Tasks
BioTime 9.5 Meeting Room Booking + POB Extensions
"""

from celery import Celery
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import SessionLocal
from app.models.meeting import MeetingBooking, MeetingRoom, MeetingAttendance
from app.models.access_control import AccessDoor
from app.services.device_service import DeviceService
from app.services.adms_protocol import ADMSProtocolService

celery = Celery('meeting_tasks')

@celery.task
def auto_unlock_meeting_rooms():
    """
    Auto-unlock meeting rooms when meetings start
    Runs every minute
    """
    db = SessionLocal()
    try:
        now = datetime.now()
        
        # Find meetings that should start now (within 1 minute window)
        upcoming_meetings = db.query(MeetingBooking).filter(
            and_(
                MeetingBooking.status == 1,  # approved
                MeetingBooking.auto_unlock == True,
                MeetingBooking.start_time <= now,
                MeetingBooking.start_time >= now - timedelta(minutes=1),
                ~MeetingBooking.id.in_(
                    db.query(MeetingAttendance.attendee_id).filter(
                        MeetingAttendance.check_in_time.isnot(None)
                    )
                )
            )
        ).all()
        
        for booking in upcoming_meetings:
            room = db.query(MeetingRoom).filter(
                MeetingRoom.id == booking.room_id
            ).first()
            
            if room and room.door_id:
                door = db.query(AccessDoor).filter(
                    AccessDoor.id == room.door_id
                ).first()
                
                if door:
                    # Send RELAY_ON command to unlock door
                    device_service = DeviceService(db)
                    adms_service = ADMSProtocolService()
                    
                    # Get device SN for the door
                    device = device_service.get_device_by_door_id(room.door_id)
                    if device:
                        result = asyncio.run(adms_service.send_relay_command(
                            device_sn=device.sn,
                            command="RELAY_ON",
                            duration=30  # Unlock for 30 seconds
                        ))
                        
                        # Log the event
                        from app.models.access_control import AccessEvent
                        event = AccessEvent(
                            door_id=room.door_id,
                            event_type=7,  # meeting unlock
                            event_time=now,
                            description=f"Auto-unlock for meeting: {booking.title}"
                        )
                        db.add(event)
                        db.commit()
                        
                        print(f"✅ Unlocked door {door.door_name} for meeting {booking.title}")
        
        return {"unlocked_rooms": len(upcoming_meetings)}
        
    except Exception as e:
        print(f"❌ Error in auto_unlock_meeting_rooms: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task
def auto_lock_meeting_rooms():
    """
    Auto-lock meeting rooms when meetings end
    Runs every minute
    """
    db = SessionLocal()
    try:
        now = datetime.now()
        
        # Find meetings that just ended (within 1 minute window)
        ended_meetings = db.query(MeetingBooking).filter(
            and_(
                MeetingBooking.status == 1,  # approved
                MeetingBooking.auto_unlock == True,
                MeetingBooking.end_time <= now,
                MeetingBooking.end_time >= now - timedelta(minutes=1)
            )
        ).all()
        
        for booking in ended_meetings:
            room = db.query(MeetingRoom).filter(
                MeetingRoom.id == booking.room_id
            ).first()
            
            if room and room.door_id:
                door = db.query(AccessDoor).filter(
                    AccessDoor.id == room.door_id
                ).first()
                
                if door:
                    # Send RELAY_OFF command to lock door
                    device_service = DeviceService(db)
                    adms_service = ADMSProtocolService()
                    
                    # Get device SN for the door
                    device = device_service.get_device_by_door_id(room.door_id)
                    if device:
                        result = asyncio.run(adms_service.send_relay_command(
                            device_sn=device.sn,
                            command="RELAY_OFF"
                        ))
                        
                        # Log the event
                        from app.models.access_control import AccessEvent
                        event = AccessEvent(
                            door_id=room.door_id,
                            event_type=8,  # meeting lock
                            event_time=now,
                            description=f"Auto-lock after meeting: {booking.title}"
                        )
                        db.add(event)
                        db.commit()
                        
                        print(f"✅ Locked door {door.door_name} after meeting {booking.title}")
        
        return {"locked_rooms": len(ended_meetings)}
        
    except Exception as e:
        print(f"❌ Error in auto_lock_meeting_rooms: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task
def process_recurring_meetings():
    """
    Create recurring meeting instances
    Runs daily at midnight
    """
    db = SessionLocal()
    try:
        today = datetime.now().date()
        
        # Find bookings with recurrence
        recurring_bookings = db.query(MeetingBooking).filter(
            and_(
                MeetingBooking.repeat_type.in_([1, 2, 3]),  # daily, weekly, monthly
                MeetingBooking.repeat_until >= today,
                MeetingBooking.status == 1  # approved
            )
        ).all()
        
        created_instances = 0
        
        for booking in recurring_bookings:
            # Calculate next occurrence
            next_start = None
            next_end = None
            
            if booking.repeat_type == 1:  # daily
                next_start = booking.start_time + timedelta(days=1)
                next_end = booking.end_time + timedelta(days=1)
            elif booking.repeat_type == 2:  # weekly
                next_start = booking.start_time + timedelta(weeks=1)
                next_end = booking.end_time + timedelta(weeks=1)
            elif booking.repeat_type == 3:  # monthly
                next_start = booking.start_time + timedelta(days=30)
                next_end = booking.end_time + timedelta(days=30)
            
            if next_start and next_end and next_start.date() <= booking.repeat_until:
                # Check if instance already exists
                existing = db.query(MeetingBooking).filter(
                    and_(
                        MeetingBooking.room_id == booking.room_id,
                        MeetingBooking.start_time == next_start,
                        MeetingBooking.end_time == next_end,
                        MeetingBooking.title == booking.title
                    )
                ).first()
                
                if not existing:
                    # Create new instance
                    new_booking = MeetingBooking(
                        room_id=booking.room_id,
                        title=booking.title,
                        start_time=next_start,
                        end_time=next_end,
                        organizer_emp_id=booking.organizer_emp_id,
                        agenda=booking.agenda,
                        attachments=booking.attachments,
                        repeat_type=0,  # No repeat for instances
                        status=1,  # Auto-approve instances
                        auto_unlock=booking.auto_unlock
                    )
                    
                    db.add(new_booking)
                    created_instances += 1
        
        db.commit()
        return {"created_instances": created_instances}
        
    except Exception as e:
        print(f"❌ Error in process_recurring_meetings: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task
def cleanup_old_meeting_data():
    """
    Clean up old meeting data (attendance records, etc.)
    Runs weekly
    """
    db = SessionLocal()
    try:
        # Delete attendance records older than 1 year
        cutoff_date = datetime.now() - timedelta(days=365)
        
        from app.models.meeting import MeetingAttendance
        deleted_count = db.query(MeetingAttendance).filter(
            MeetingAttendance.check_in_time < cutoff_date
        ).delete()
        
        db.commit()
        return {"deleted_records": deleted_count}
        
    except Exception as e:
        print(f"❌ Error in cleanup_old_meeting_data: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task
def send_meeting_reminders():
    """
    Send meeting reminders to attendees
    Runs every 15 minutes
    """
    db = SessionLocal()
    try:
        now = datetime.now()
        reminder_time = now + timedelta(minutes=15)
        
        # Find meetings starting in 15 minutes
        upcoming_meetings = db.query(MeetingBooking).filter(
            and_(
                MeetingBooking.status == 1,  # approved
                MeetingBooking.start_time <= reminder_time,
                MeetingBooking.start_time > now
            )
        ).all()
        
        reminders_sent = 0
        
        for booking in upcoming_meetings:
            # Get attendees
            from app.models.meeting import MeetingAttendee
            attendees = db.query(MeetingAttendee).filter(
                MeetingAttendee.booking_id == booking.id
            ).all()
            
            for attendee in attendees:
                # Send reminder based on attendee type
                if attendee.attendee_type == 0 and attendee.emp_id:
                    # Employee reminder
                    from app.models.personnel import PersonnelEmployee
                    employee = db.query(PersonnelEmployee).filter(
                        PersonnelEmployee.id == attendee.emp_id
                    ).first()
                    if employee and employee.email:
                        # Send email reminder
                        print(f"📧 Sending reminder to {employee.email} for meeting {booking.title}")
                        reminders_sent += 1
                
                elif attendee.attendee_type == 1 and attendee.visitor_id:
                    # Visitor reminder
                    from app.models.visitor import Visitor
                    visitor = db.query(Visitor).filter(
                        Visitor.id == attendee.visitor_id
                    ).first()
                    if visitor and visitor.email:
                        # Send email reminder
                        print(f"📧 Sending reminder to {visitor.email} for meeting {booking.title}")
                        reminders_sent += 1
        
        return {"reminders_sent": reminders_sent}
        
    except Exception as e:
        print(f"❌ Error in send_meeting_reminders: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task
def emergency_mustering_unlock():
    """
    Unlock emergency assembly rooms during mustering events
    Runs when mustering event is activated
    """
    db = SessionLocal()
    try:
        # Find emergency assembly rooms
        emergency_rooms = db.query(MeetingRoom).filter(
            MeetingRoom.is_emergency_assembly == True
        ).all()
        
        unlocked_rooms = 0
        
        for room in emergency_rooms:
            if room.door_id:
                door = db.query(AccessDoor).filter(
                    AccessDoor.id == room.door_id
                ).first()
                
                if door:
                    # Send RELAY_ON command to unlock door
                    device_service = DeviceService(db)
                    adms_service = ADMSProtocolService()
                    
                    # Get device SN for the door
                    device = device_service.get_device_by_door_id(room.door_id)
                    if device:
                        result = asyncio.run(adms_service.send_relay_command(
                            device_sn=device.sn,
                            command="RELAY_ON",
                            duration=0  # Keep unlocked until manually locked
                        ))
                        
                        # Log the event
                        from app.models.access_control import AccessEvent
                        event = AccessEvent(
                            door_id=room.door_id,
                            event_type=9,  # emergency unlock
                            event_time=datetime.now(),
                            description="Emergency assembly room unlocked for mustering"
                        )
                        db.add(event)
                        db.commit()
                        
                        unlocked_rooms += 1
                        print(f"🚨 Emergency unlocked door {door.door_name} (Assembly Room)")
        
        return {"unlocked_rooms": unlocked_rooms}
        
    except Exception as e:
        print(f"❌ Error in emergency_mustering_unlock: {e}")
        return {"error": str(e)}
    finally:
        db.close()

# Schedule the tasks
from celery.schedules import crontab

celery.conf.beat_schedule = {
    'auto-unlock-meeting-rooms': {
        'task': 'app.tasks.meeting_tasks.auto_unlock_meeting_rooms',
        'schedule': crontab(minute='*'),  # Every minute
    },
    'auto-lock-meeting-rooms': {
        'task': 'app.tasks.meeting_tasks.auto_lock_meeting_rooms',
        'schedule': crontab(minute='*'),  # Every minute
    },
    'process-recurring-meetings': {
        'task': 'app.tasks.meeting_tasks.process_recurring_meetings',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'cleanup-old-meeting-data': {
        'task': 'app.tasks.meeting_tasks.cleanup_old_meeting_data',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Weekly on Sunday at 2 AM
    },
    'send-meeting-reminders': {
        'task': 'app.tasks.meeting_tasks.send_meeting_reminders',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}
