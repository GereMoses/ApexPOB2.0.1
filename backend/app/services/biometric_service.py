"""
Biometric Service for Oil & Gas Personnel Management
Handles biometric enrollment, device management, and access control
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import logging

# Import models with proper error handling
try:
    from ..models.personnel import Personnel
except ImportError:
    Personnel = None

try:
    from ..models.device import Device
except ImportError:
    Device = None

try:
    from ..models.device import AccessLog
except ImportError:
    AccessLog = None

from ..core.database import get_db

logger = logging.getLogger(__name__)

class BiometricService:
    """Service for managing biometric enrollment and access control"""
    
    def __init__(self, db: Session = None):
        """
        Args:
            db: the CALLER's request-scoped session. Always pass one.

        The old default — `self.db = next(get_db())` evaluated once, at module
        import — handed every request in the process a single shared session that
        was never closed. Two consequences, both seen in practice:

          * A method that raised without rolling back left that session in an
            aborted transaction, so the NEXT, unrelated request failed with
            "current transaction is aborted, commands ignored…" — an error about
            somebody else's request.
          * The session sat open permanently, showing up as `idle in transaction`
            and able to block DDL (that is what stalled the whole API earlier).

        The fallback below is kept only so any legacy caller that constructs the
        service with no argument still works; it is not the intended path.
        """
        self.db = db if db is not None else next(get_db())
    
    async def enroll_personnel_biometric(
        self, 
        personnel_id: int, 
        biometric_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enroll personnel in biometric system
        
        Args:
            personnel_id: Personnel ID
            biometric_data: Biometric enrollment data
            
        Returns:
            Enrollment result
        """
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == personnel_id).first()
            if not personnel:
                return {
                    "success": False,
                    "message": "Personnel not found",
                    "error": "PERSONNEL_NOT_FOUND"
                }
            
            # Update biometric enrollment status
            personnel.biometric_enrolled = True
            personnel.biometric_data = biometric_data
            
            # Calculate compliance score based on biometric enrollment
            if personnel.compliance_score < 70:
                personnel.compliance_score = min(100, personnel.compliance_score + 20)
            
            # Add to access log if model exists.
            #
            # access_logs.device_id is a FK to devices(device_id). The caller sends
            # whatever the enrolling station reports, which is not necessarily a
            # device registered here — and an unknown value aborts the whole
            # enrolment with a foreign-key violation, losing the template for a
            # bookkeeping row. Record the id only when it genuinely exists.
            if AccessLog is not None:
                raw_device = biometric_data.get('device_id')
                device_id = None
                if raw_device is not None:
                    known = self.db.execute(text(
                        "SELECT 1 FROM devices WHERE device_id = :d"
                    ), {"d": str(raw_device)}).fetchone()
                    if known:
                        device_id = raw_device
                    else:
                        logger.warning(
                            "Biometric enrolment for personnel %s reported unknown device %r "
                            "— logging without a device reference", personnel_id, raw_device
                        )
                access_log = AccessLog(
                    personnel_id=personnel_id,
                    device_id=device_id,
                    event_type='BIOMETRIC_ENROLLMENT',
                    timestamp=datetime.utcnow(),
                    access_granted=True,
                    biometric_data=biometric_data
                )
                self.db.add(access_log)
            
            self.db.commit()
            
            logger.info(f"Personnel {personnel.full_name} enrolled in biometric system")
            
            return {
                "success": True,
                "message": "Biometric enrollment successful",
                "personnel_id": personnel_id,
                "enrolled_at": datetime.utcnow().isoformat(),
                "device_id": biometric_data.get('device_id')
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error enrolling biometric for personnel {personnel_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to enroll biometric: {str(e)}",
                "error": "ENROLLMENT_ERROR"
            }
    
    async def revoke_biometric_access(
        self, 
        personnel_id: int,
        reason: str
    ) -> Dict[str, Any]:
        """
        Revoke biometric access for personnel
        
        Args:
            personnel_id: Personnel ID
            reason: Reason for revocation
            
        Returns:
            Revocation result
        """
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == personnel_id).first()
            if not personnel:
                return {
                    "success": False,
                    "message": "Personnel not found",
                    "error": "PERSONNEL_NOT_FOUND"
                }
            
            # Revoke biometric enrollment
            personnel.biometric_enrolled = False
            personnel.biometric_data = None
            
            # Update compliance score
            if personnel.compliance_score > 80:
                personnel.compliance_score = max(0, personnel.compliance_score - 20)
            
            # Add to access log if model exists
            if AccessLog is not None:
                access_log = AccessLog(
                    personnel_id=personnel_id,
                    event_type='BIOMETRIC_REVOCATION',
                    timestamp=datetime.utcnow(),
                    access_granted=False,
                    # The column is denial_reason — `reason` is not a mapped
                    # attribute, so this raised on every revocation attempt.
                    denial_reason=reason
                )
                self.db.add(access_log)
            
            self.db.commit()
            
            logger.info(f"Biometric access revoked for personnel {personnel.full_name}")
            
            return {
                "success": True,
                "message": "Biometric access revoked successfully",
                "personnel_id": personnel_id,
                "revoked_at": datetime.utcnow().isoformat(),
                "reason": reason
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error revoking biometric access for personnel {personnel_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to revoke biometric access: {str(e)}",
                "error": "REVOCATION_ERROR"
            }
    
    async def get_biometric_status(
        self, 
        personnel_id: int
    ) -> Dict[str, Any]:
        """
        Get comprehensive biometric status for personnel
        
        Args:
            personnel_id: Personnel ID
            
        Returns:
            Biometric status information
        """
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == personnel_id).first()
            if not personnel:
                return {
                    "success": False,
                    "message": "Personnel not found",
                    "error": "PERSONNEL_NOT_FOUND"
                }
            
            # Get recent access logs if model exists
            if AccessLog is not None:
                recent_logs = self.db.query(AccessLog).filter(
                    AccessLog.personnel_id == personnel_id
                ).order_by(AccessLog.timestamp.desc()).limit(10).all()
            
            # Get device access count.
            #
            # authorized_personnel is a JSONB array of personnel ids. SQLAlchemy's
            # generic JSON `.contains(int)` compiles to a LIKE, which Postgres
            # rejects outright: "operator does not exist: jsonb ~~ text". That made
            # this endpoint fail every single time — and because the failure left
            # the shared session in an aborted transaction, it also broke whichever
            # request came next. Use the JSONB containment operator instead.
            device_access_count = self.db.execute(text(
                "SELECT count(*) FROM devices "
                "WHERE authorized_personnel @> CAST(:pid AS jsonb)"
            ), {"pid": json.dumps([personnel_id])}).scalar() or 0
            
            # Analyze biometric data
            biometric_data = personnel.biometric_data or {}
            fingerprint_count = len(biometric_data.get('fingerprint_templates', []))
            has_face_template = bool(biometric_data.get('face_template'))
            has_card = bool(biometric_data.get('card_number'))
            
            return {
                "success": True,
                "personnel_id": personnel_id,
                "biometric_enrolled": personnel.biometric_enrolled,
                "biometric_data": {
                    "fingerprint_count": fingerprint_count,
                    "has_face_template": has_face_template,
                    "has_card": has_card,
                    "last_enrollment": biometric_data.get('enrolled_at'),
                    "device_id": biometric_data.get('device_id')
                },
                "device_access_count": device_access_count,
                "recent_access": [
                    {
                        "timestamp": log.timestamp.isoformat(),
                        "event_type": log.event_type,
                        "device_id": log.device_id,
                        "access_granted": log.access_granted,
                        "reason": log.denial_reason
                    }
                    for log in recent_logs
                ],
                "compliance_impact": {
                    "score_impact": "+20%" if not personnel.biometric_enrolled else "0%",
                    "current_score": personnel.compliance_score
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting biometric status for personnel {personnel_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to get biometric status: {str(e)}",
                "error": "STATUS_ERROR"
            }
    
    async def get_biometric_analytics(
        self
    ) -> Dict[str, Any]:
        """
        Get biometric analytics for the entire system
        
        Returns:
            Biometric analytics data
        """
        try:
            total_personnel = self.db.query(Personnel).filter(Personnel.is_active == True).count()  # noqa: E712
            enrolled_personnel = self.db.query(Personnel).filter(Personnel.biometric_enrolled == True).count()
            not_enrolled_personnel = total_personnel - enrolled_personnel
            
            # Get enrollment trends (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_enrollments = self.db.query(AccessLog).filter(
                AccessLog.event_type == 'BIOMETRIC_ENROLLMENT',
                AccessLog.timestamp >= thirty_days_ago
            ).count()
            
            # Get device distribution
            device_usage = {}
            access_logs = self.db.query(AccessLog).filter(
                AccessLog.access_granted == True
            ).all()
            
            for log in access_logs:
                device_id = log.device_id
                if device_id not in device_usage:
                    device_usage[device_id] = 0
                device_usage[device_id] += 1
            
            # Get compliance impact
            avg_compliance_enrolled = self.db.query(Personnel).filter(
                Personnel.biometric_enrolled == True
            ).with_entities(Personnel.compliance_score).all()
            
            avg_compliance_not_enrolled = self.db.query(Personnel).filter(
                Personnel.biometric_enrolled == False
            ).with_entities(Personnel.compliance_score).all()
            
            avg_compliance_score_enrolled = sum(p.compliance_score for p in avg_compliance_enrolled) / len(avg_compliance_enrolled) if avg_compliance_enrolled else 0
            avg_compliance_score_not_enrolled = sum(p.compliance_score for p in avg_compliance_not_enrolled) / len(avg_compliance_not_enrolled) if avg_compliance_not_enrolled else 0
            
            return {
                "success": True,
                "total_personnel": total_personnel,
                "enrolled_personnel": enrolled_personnel,
                "not_enrolled_personnel": not_enrolled_personnel,
                "enrollment_rate": round((enrolled_personnel / total_personnel * 100) if total_personnel > 0 else 0, 1),
                "recent_enrollments": recent_enrollments,
                "device_usage": device_usage,
                "most_used_device": max(device_usage.items(), key=device_usage.get) if device_usage else None,
                "overview": {
                    "total_personnel": total_personnel,
                    "enrolled_personnel": enrolled_personnel,
                    "not_enrolled_personnel": not_enrolled_personnel,
                    "enrollment_rate": round((enrolled_personnel / total_personnel * 100) if total_personnel > 0 else 0, 1),
                },
                "compliance_impact": {
                    "enrolled_avg_compliance": round(avg_compliance_score_enrolled, 1),
                    "not_enrolled_avg_compliance": round(avg_compliance_score_not_enrolled, 1),
                    "overall_improvement": round(avg_compliance_score_enrolled - avg_compliance_score_not_enrolled, 1)
                },
                "trends": {
                    "enrollment_trend": "increasing" if recent_enrollments > 5 else "stable",
                    "device_usage_trend": "stable"
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting biometric analytics: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to get biometric analytics: {str(e)}",
                "error": "ANALYTICS_ERROR"
            }
    
    async def sync_with_zkteco_device(
        self,
        device_id: str,
        personnel_id: int
    ) -> Dict[str, Any]:
        """
        Push a single personnel record to a ZKTeco device via direct TCP (ZKLib).
        device_id can be an IP address, serial number, or Device.device_id string.
        """
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == personnel_id).first()
            if not personnel:
                return {"success": False, "message": "Personnel not found", "error": "PERSONNEL_NOT_FOUND"}

            # Resolve device IP from device_id (try as IP directly, then look up in tables)
            device_ip = None
            device_port = 4370

            # 1. Check if device_id is already an IP address
            import re
            if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', device_id):
                device_ip = device_id
            else:
                # 2. Look up in Device table
                try:
                    device_obj = self.db.query(Device).filter(
                        (Device.device_id == device_id) | (Device.serial_number == device_id)
                    ).first() if Device else None
                    if device_obj and device_obj.ip_address:
                        device_ip = device_obj.ip_address
                        device_port = device_obj.port or 4370
                except Exception:
                    pass

                # 3. Look up in IClockTerminal
                if not device_ip:
                    try:
                        from ..models.biotime_models import IClockTerminal
                        term = self.db.query(IClockTerminal).filter(
                            (IClockTerminal.sn == device_id) | (IClockTerminal.alias == device_id)
                        ).first()
                        if term and term.ip_address:
                            device_ip = term.ip_address
                    except Exception:
                        pass

            if not device_ip:
                return {"success": False, "message": f"Cannot resolve device IP for '{device_id}'", "error": "DEVICE_NOT_FOUND"}

            from .zkteco.direct_connection import zkteco_direct
            result = await zkteco_direct.sync_personnel_from_db(
                ip=device_ip,
                port=device_port,
                personnel_ids=[personnel_id],
                db=self.db,
            )

            if result.get("success"):
                personnel.last_sync_timestamp = datetime.utcnow()
                self.db.commit()
                logger.info(f"Synced personnel {personnel.full_name} to device {device_ip}")

            return {
                "success": result.get("success", False),
                "message": "Personnel synced to device" if result.get("success") else result.get("error", "Sync failed"),
                "sync_result": {
                    "device_id": device_id,
                    "device_ip": device_ip,
                    "synced": result.get("synced", 0),
                    "errors": result.get("errors", []),
                    "sync_timestamp": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"sync_with_zkteco_device error for device {device_id}: {e}")
            return {"success": False, "message": f"Sync failed: {str(e)}", "error": "SYNC_ERROR"}
    
    async def get_device_biometric_status(
        self,
        device_id: str
    ) -> Dict[str, Any]:
        """
        Get biometric status for a specific device
        
        Args:
            device_id: ZKTeco device ID
            
        Returns:
            Device biometric status
        """
        try:
            device = self.db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                return {
                    "success": False,
                    "message": "Device not found",
                    "error": "DEVICE_NOT_FOUND"
                }
            
            # Get personnel authorized for this device
            authorized_personnel = device.authorized_personnel or []
            
            # Get recent access attempts
            recent_access = self.db.query(AccessLog).filter(
                AccessLog.device_id == device_id
            ).order_by(AccessLog.timestamp.desc()).limit(50).all()
            
            return {
                "success": True,
                "device_id": device_id,
                "device_name": device.name,
                "device_status": device.status,
                "authorized_personnel_count": len(authorized_personnel),
                "recent_access_count": len(recent_access),
                "last_access": recent_access[0].timestamp.isoformat() if recent_access else None,
                "access_success_rate": self._calculate_success_rate(recent_access)
            }
            
        except Exception as e:
            logger.error(f"Error getting device biometric status for device {device_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to get device biometric status: {str(e)}",
                "error": "DEVICE_STATUS_ERROR"
            }
    
    def _calculate_success_rate(self, access_logs: List) -> float:
        """Calculate success rate from access logs"""
        if not access_logs:
            return 0.0
        
        successful_access = sum(1 for log in access_logs if log.access_granted)
        total_access = len(access_logs)
        
        return (successful_access / total_access * 100) if total_access > 0 else 0.0
