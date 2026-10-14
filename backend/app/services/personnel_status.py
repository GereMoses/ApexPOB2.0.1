"""
Personnel Status Tracking Service

This service handles personnel status tracking including ONBOARD/OFFBOARD status,
location tracking, and status history.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..models.personnel import Personnel, PersonnelStatus, AttendanceLog
from ..core.database import get_db


class PersonnelStatusService:
    """Service for managing personnel status tracking"""
    
    async def update_personnel_status(
        self,
        personnel_id: int,
        new_status: PersonnelStatus,
        location: Optional[str] = None,
        zone: Optional[str] = None,
        notes: Optional[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Update personnel status with tracking
        
        Args:
            personnel_id: Personnel ID
            new_status: New status to set
            location: Current location (optional)
            zone: Current zone (optional)
            notes: Status change notes (optional)
            db: Database session
            
        Returns:
            Updated personnel information
        """
        if db is None:
            db = next(get_db())
        
        # Get personnel record
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise ValueError(f"Personnel with ID {personnel_id} not found")
        
        # Track status change
        old_status = personnel.status
        old_onboard = personnel.is_onboard
        
        # Update personnel status
        personnel.status = new_status
        personnel.updated_at = datetime.now(timezone.utc)
        
        # Update location if provided
        if location:
            personnel.current_location = location
        
        if zone:
            personnel.current_zone = zone
        
        # Update onboard status based on new status
        if new_status in [PersonnelStatus.OFFSHORE, PersonnelStatus.ONSHORE]:
            personnel.is_onboard = True
        elif new_status == PersonnelStatus.TRANSIT:
            # Keep current onboard status during transit
            pass
        else:  # ACTIVE, INACTIVE, ON_LEAVE
            personnel.is_onboard = False
        
        # Update last seen timestamp
        personnel.last_seen = datetime.now(timezone.utc)
        
        # Create attendance log entry for status change
        attendance_log = AttendanceLog(
            personnel_id=personnel_id,
            badge_id=personnel.badge_id,
            location=location or personnel.current_location,
            zone=zone or personnel.current_zone,
            action=f"STATUS_CHANGE_{old_status.value}_TO_{new_status.value}",
            timestamp=datetime.now(timezone.utc),
            notes=notes
        )
        
        db.add(attendance_log)
        db.commit()
        db.refresh(personnel)
        
        return {
            "success": True,
            "personnel_id": personnel_id,
            "old_status": old_status.value,
            "new_status": new_status.value,
            "old_onboard": old_onboard,
            "new_onboard": personnel.is_onboard,
            "location": personnel.current_location,
            "zone": personnel.current_zone,
            "timestamp": personnel.updated_at,
            "notes": notes
        }
    
    async def check_in_personnel(
        self,
        personnel_id: int,
        location: str,
        zone: Optional[str] = None,
        notes: Optional[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Check in personnel (mark as ONBOARD)
        
        Args:
            personnel_id: Personnel ID
            location: Check-in location
            zone: Check-in zone (optional)
            notes: Check-in notes (optional)
            db: Database session
            
        Returns:
            Check-in result
        """
        if db is None:
            db = next(get_db())
        
        # Get personnel record
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise ValueError(f"Personnel with ID {personnel_id} not found")
        
        # Determine status based on location
        if zone and "offshore" in zone.lower():
            new_status = PersonnelStatus.OFFSHORE
        elif zone and "onshore" in zone.lower():
            new_status = PersonnelStatus.ONSHORE
        else:
            new_status = PersonnelStatus.ACTIVE
        
        # Update personnel
        old_status = personnel.status
        personnel.status = new_status
        personnel.current_location = location
        personnel.current_zone = zone
        personnel.is_onboard = True
        personnel.last_seen = datetime.now(timezone.utc)
        personnel.updated_at = datetime.now(timezone.utc)
        
        # Create attendance log
        attendance_log = AttendanceLog(
            personnel_id=personnel_id,
            badge_id=personnel.badge_id,
            location=location,
            zone=zone,
            action="CHECK_IN",
            timestamp=datetime.now(timezone.utc),
            notes=notes
        )
        
        db.add(attendance_log)
        db.commit()
        db.refresh(personnel)
        
        return {
            "success": True,
            "personnel_id": personnel_id,
            "badge_id": personnel.badge_id,
            "full_name": personnel.full_name,
            "action": "CHECK_IN",
            "status": new_status.value,
            "location": location,
            "zone": zone,
            "timestamp": personnel.last_seen,
            "notes": notes
        }
    
    async def check_out_personnel(
        self,
        personnel_id: int,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Check out personnel (mark as OFFBOARD)
        
        Args:
            personnel_id: Personnel ID
            location: Check-out location (optional)
            notes: Check-out notes (optional)
            db: Database session
            
        Returns:
            Check-out result
        """
        if db is None:
            db = next(get_db())
        
        # Get personnel record
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise ValueError(f"Personnel with ID {personnel_id} not found")
        
        # Update personnel
        old_status = personnel.status
        personnel.status = PersonnelStatus.ACTIVE
        personnel.is_onboard = False
        personnel.last_seen = datetime.now(timezone.utc)
        personnel.updated_at = datetime.now(timezone.utc)
        
        # Clear location if not provided
        if not location:
            personnel.current_location = None
            personnel.current_zone = None
        else:
            personnel.current_location = location
        
        # Create attendance log
        attendance_log = AttendanceLog(
            personnel_id=personnel_id,
            badge_id=personnel.badge_id,
            location=location or personnel.current_location,
            zone=personnel.current_zone,
            action="CHECK_OUT",
            timestamp=datetime.now(timezone.utc),
            notes=notes
        )
        
        db.add(attendance_log)
        db.commit()
        db.refresh(personnel)
        
        return {
            "success": True,
            "personnel_id": personnel_id,
            "badge_id": personnel.badge_id,
            "full_name": personnel.full_name,
            "action": "CHECK_OUT",
            "status": PersonnelStatus.ACTIVE.value,
            "location": location,
            "timestamp": personnel.last_seen,
            "notes": notes
        }
    
    async def get_personnel_status_history(
        self,
        personnel_id: int,
        limit: int = 50,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        Get personnel status history
        
        Args:
            personnel_id: Personnel ID
            limit: Maximum number of records to return
            db: Database session
            
        Returns:
            List of status history records
        """
        if db is None:
            db = next(get_db())
        
        # Get attendance logs for this personnel
        logs = db.query(AttendanceLog).filter(
            AttendanceLog.personnel_id == personnel_id
        ).order_by(AttendanceLog.timestamp.desc()).limit(limit).all()
        
        history = []
        for log in logs:
            history.append({
                "id": log.id,
                "action": log.action,
                "location": log.location,
                "zone": log.zone,
                "timestamp": log.timestamp,
                "notes": log.notes
            })
        
        return history
    
    async def get_onboard_personnel(
        self,
        location: Optional[str] = None,
        zone: Optional[str] = None,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        Get all currently onboard personnel
        
        Args:
            location: Filter by location (optional)
            zone: Filter by zone (optional)
            db: Database session
            
        Returns:
            List of onboard personnel
        """
        if db is None:
            db = next(get_db())
        
        query = db.query(Personnel).filter(Personnel.is_onboard == True)
        
        if location:
            query = query.filter(Personnel.current_location.ilike(f"%{location}%"))
        
        if zone:
            from ..models.zone import Zone
            query = query.join(Zone, Personnel.current_zone_id == Zone.id).filter(
                Zone.name.ilike(f"%{zone}%"))
        
        personnel_list = query.order_by(Personnel.last_seen.desc()).all()
        
        result = []
        for person in personnel_list:
            result.append({
                "id": person.id,
                "badge_id": person.badge_id,
                "full_name": person.full_name,
                "company": person.company,
                "role": person.role,
                "status": person.status.value if person.status is not None else None,
                "current_location": person.current_location,
                # current_zone is a relationship to Zone, not a string
                "current_zone": person.current_zone.name if person.current_zone else None,
                "last_seen": person.last_seen
            })
        
        return result
    
    async def get_status_summary(
        self,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get personnel status summary
        
        Args:
            db: Database session
            
        Returns:
            Status summary statistics
        """
        if db is None:
            db = next(get_db())
        
        # Count personnel by status
        status_counts = {}
        for status in PersonnelStatus:
            count = db.query(Personnel).filter(Personnel.status == status).count()
            status_counts[status.value] = count
        
        # Count onboard/offboard
        onboard_count = db.query(Personnel).filter(Personnel.is_onboard == True).count()
        total_count = db.query(Personnel).count()
        offboard_count = total_count - onboard_count
        
        # Count by location
        location_counts = {}
        personnel_by_location = db.query(
            Personnel.current_location,
            func.count(Personnel.id)
        ).filter(Personnel.current_location.isnot(None)).group_by(Personnel.current_location).all()
        
        for location, count in personnel_by_location:
            location_counts[location] = count
        
        return {
            "total_personnel": total_count,
            "onboard_personnel": onboard_count,
            "offboard_personnel": offboard_count,
            "onboard_percentage": round((onboard_count / total_count * 100) if total_count > 0 else 0, 2),
            "status_distribution": status_counts,
            "location_distribution": location_counts
        }


# Create singleton instance
personnel_status_service = PersonnelStatusService()
