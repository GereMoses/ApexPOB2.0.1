"""
Mobile API Endpoints
API endpoints for mobile application access
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timedelta
from pydantic import BaseModel

from ..core.database import get_db
from ..core.dependencies import get_current_user
from sqlalchemy import text

router = APIRouter(prefix="/mobile", tags=["mobile"])


class LocationData(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    timestamp: datetime


class EmergencyAlert(BaseModel):
    alert_type: str
    location: LocationData
    message: Optional[str] = None
    severity: Optional[str] = "medium"


@router.post("/check-in")
async def mobile_check_in(
    location: LocationData,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mobile check-in with geolocation
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        # Record check-in with location
        result = db.execute(text("""
            INSERT INTO checkinout (
                emp_code, check_time, check_type, sensor_id, 
                processed, created_at
            )
            VALUES (
                :emp_code, :check_time, 0, :sensor_id,
                FALSE, :created_at
            )
            RETURNING id
        """), {
            'emp_code': emp_code,
            'check_time': datetime.utcnow(),
            'sensor_id': f"{location.latitude},{location.longitude}",
            'created_at': datetime.utcnow()
        })
        
        checkin_id = result.fetchone()[0]
        db.commit()
        
        return {
            'success': True,
            'message': 'Check-in recorded successfully',
            'checkin_id': checkin_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record check-in: {str(e)}"
        )


@router.post("/check-out")
async def mobile_check_out(
    location: LocationData,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mobile check-out with geolocation
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        # Record check-out with location
        result = db.execute(text("""
            INSERT INTO checkinout (
                emp_code, check_time, check_type, sensor_id,
                processed, created_at
            )
            VALUES (
                :emp_code, :check_time, 1, :sensor_id,
                FALSE, :created_at
            )
            RETURNING id
        """), {
            'emp_code': emp_code,
            'check_time': datetime.utcnow(),
            'sensor_id': f"{location.latitude},{location.longitude}",
            'created_at': datetime.utcnow()
        })
        
        checkout_id = result.fetchone()[0]
        db.commit()
        
        return {
            'success': True,
            'message': 'Check-out recorded successfully',
            'checkout_id': checkout_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record check-out: {str(e)}"
        )


@router.get("/my-qr")
async def get_my_qr_code(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's QR code for mobile access
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        # Get employee details
        result = db.execute(text("""
            SELECT id, emp_code, first_name, last_name, photo
            FROM personnel_employee
            WHERE emp_code = :emp_code
        """), {'emp_code': emp_code})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Generate QR code data (simplified - in production use proper QR library)
        qr_data = f"POB:{emp_code}:{row[0]}:{datetime.utcnow().timestamp()}"
        
        return {
            'success': True,
            'data': {
                'qr_data': qr_data,
                'emp_code': emp_code,
                'name': f"{row[2]} {row[3]}",
                'photo': row[4]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate QR code: {str(e)}"
        )


@router.post("/emergency-alert")
async def emergency_alert(
    alert: EmergencyAlert,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit emergency alert from mobile
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        # Create emergency event
        result = db.execute(text("""
            INSERT INTO emergency_event (
                emp_code, event_type, location, message, severity,
                status, created_at, updated_at
            )
            VALUES (
                :emp_code, :event_type, :location, :message, :severity,
                0, :created_at, :updated_at
            )
            RETURNING id
        """), {
            'emp_code': emp_code,
            'event_type': alert.alert_type,
            'location': f"{alert.location.latitude},{alert.location.longitude}",
            'message': alert.message,
            'severity': alert.severity,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })
        
        event_id = result.fetchone()[0]
        db.commit()
        
        # TODO: Trigger notification to emergency responders
        # TODO: Send push notifications to relevant personnel
        
        return {
            'success': True,
            'message': 'Emergency alert submitted',
            'event_id': event_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit emergency alert: {str(e)}"
        )


@router.get("/my-location")
async def get_my_location(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's current location/zone
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        result = db.execute(text("""
            SELECT current_zone_id, is_onboard
            FROM personnel
            WHERE emp_code = :emp_code
        """), {'emp_code': emp_code})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        return {
            'success': True,
            'data': {
                'zone_id': row[0],
                'is_onboard': row[1]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get location: {str(e)}"
        )


@router.get("/notifications")
async def get_notifications(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get mobile notifications for user
    """
    try:
        # In-app notifications live in sys_notifications, keyed by login user.
        result = db.execute(text("""
            SELECT id, notification_type, message, is_read, created_at
            FROM sys_notifications
            WHERE user_id = :uid
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
            LIMIT :limit
        """), {'uid': current_user.id, 'limit': limit})
        
        notifications = []
        for row in result:
            notifications.append({
                'id': row[0],
                'type': row[1],
                'message': row[2],
                'is_read': row[3],
                'created_at': row[4].isoformat() if row[4] else None
            })
        
        return {
            'success': True,
            'data': notifications
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notifications: {str(e)}"
        )


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark notification as read
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        db.execute(text("""
            UPDATE notifications
            SET is_read = TRUE, read_at = :read_at
            WHERE id = :notification_id AND emp_code = :emp_code
        """), {
            'notification_id': notification_id,
            'emp_code': emp_code,
            'read_at': datetime.utcnow()
        })
        
        db.commit()
        
        return {
            'success': True,
            'message': 'Notification marked as read'
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notification as read: {str(e)}"
        )


@router.get("/mustering-status")
async def get_mustering_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current mustering status for user
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        # Check if there's an active mustering event
        result = db.execute(text("""
            SELECT 
                me.id, me.event_type, me.start_time, me.status,
                ml.status as muster_status, ml.check_time
            FROM mustering_event me
            LEFT JOIN mustering_log ml ON me.id = ml.event_id AND ml.emp_code = :emp_code
            WHERE me.status = 0
            ORDER BY me.start_time DESC
            LIMIT 1
        """), {'emp_code': emp_code})
        
        row = result.fetchone()
        
        if row:
            return {
                'success': True,
                'data': {
                    'event_id': row[0],
                    'event_type': row[1],
                    'start_time': row[2].isoformat() if row[2] else None,
                    'event_status': row[3],
                    'muster_status': row[4],
                    'check_time': row[5].isoformat() if row[5] else None,
                    'has_active_event': True
                }
            }
        else:
            return {
                'success': True,
                'data': {
                    'has_active_event': False
                }
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mustering status: {str(e)}"
        )


@router.post("/mustering-checkin")
async def mustering_checkin(
    location: LocationData,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check-in to mustering point from mobile
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        # Get active mustering event
        result = db.execute(text("""
            SELECT id, zone_id
            FROM mustering_event
            WHERE status = 0
            ORDER BY start_time DESC
            LIMIT 1
        """))
        
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active mustering event"
            )
        
        event_id = row[0]
        zone_id = row[1]
        
        # Record mustering check-in
        db.execute(text("""
            INSERT INTO mustering_log (
                event_id, emp_code, check_time, device_sn, 
                status, location, created_at
            )
            VALUES (
                :event_id, :emp_code, :check_time, 'MOBILE',
                1, :location, :created_at
            )
            ON CONFLICT (event_id, emp_code)
            DO UPDATE SET 
                check_time = :check_time,
                status = 1,
                location = :location,
                created_at = :created_at
        """), {
            'event_id': event_id,
            'emp_code': emp_code,
            'check_time': datetime.utcnow(),
            'location': f"{location.latitude},{location.longitude}",
            'created_at': datetime.utcnow()
        })
        
        db.commit()
        
        return {
            'success': True,
            'message': 'Mustering check-in recorded',
            'event_id': event_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record mustering check-in: {str(e)}"
        )
