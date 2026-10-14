"""
Device Sync Rules Service
Handles automatic device synchronization rules and command queue management
"""

from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from ..models.biotime_models import IClockTerminal, IClockTransaction, PersonnelEmployee
from ..core.database import get_db
from .device_pin import rewrite_command

logger = logging.getLogger(__name__)


class DeviceSyncRulesService:
    """Service for device synchronization rules and command management"""
    
    def __init__(self):
        self.sync_rules = {
            'personnel_create': True,
            'personnel_update': True,
            'fingerprint_enroll': True,
            'face_enroll': True,
            'device_online': True,
            'area_change': True
        }
    
    async def queue_command_for_device(
        self,
        device_sn: str,
        command: str,
        db: Session,
        priority: int = 0
    ) -> Optional[int]:
        """Queue a command for a device"""
        try:
            command = rewrite_command(db, command)   # PIN=<emp_code> -> reader PIN
            result = db.execute(text("""
                INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, status)
                VALUES (:sn, :cmd_content, :commit_time, 0)
                RETURNING id
            """), {
                'sn': device_sn,
                'cmd_content': command,
                'commit_time': datetime.utcnow()
            })
            
            command_id = result.scalar()
            db.commit()
            
            logger.info(f"✅ Queued command '{command}' for device {device_sn} (ID: {command_id})")
            return command_id
            
        except Exception as e:
            logger.error(f"❌ Error queuing command: {e}")
            db.rollback()
            return None
    
    async def on_personnel_created_or_updated(
        self,
        personnel_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """Handle personnel creation or update - queue sync commands to devices"""
        try:
            if not self.sync_rules.get('personnel_create', True):
                return {"success": False, "message": "Personnel sync rule disabled"}
            
            # Get personnel details
            personnel = db.query(PersonnelEmployee).filter(
                PersonnelEmployee.id == personnel_id
            ).first()
            
            if not personnel:
                return {"success": False, "error": "Personnel not found"}
            
            # Get devices in same area
            area_filter = ""
            params = {'emp_code': personnel.emp_code}
            
            if personnel.area_id:
                area_filter = "AND area_id = :area_id"
                params['area_id'] = personnel.area_id
            
            # Get devices in personnel's area
            devices_result = db.execute(text(f"""
                SELECT sn FROM iclock_terminal 
                WHERE state = 1 AND device_type IN (0, 1)
                {area_filter}
            """), params)
            
            devices = devices_result.fetchall()
            
            if not devices:
                return {
                    "success": True,
                    "message": "No devices found in personnel's area",
                    "devices_queued": 0
                }
            
            # Queue sync commands for each device
            command_ids = []
            for device_row in devices:
                device_sn = device_row.sn
                
                # Queue user info update
                cmd_id = await self.queue_command_for_device(
                    device_sn, 
                    f"DATA UPDATE USERINFO PIN={personnel.emp_code}",
                    db
                )
                if cmd_id:
                    command_ids.append(cmd_id)
            
            return {
                "success": True,
                "message": f"Personnel sync queued for {len(devices)} devices",
                "devices_queued": len(devices),
                "command_ids": command_ids
            }
            
        except Exception as e:
            logger.error(f"Error in personnel sync: {e}")
            return {"success": False, "error": str(e)}
    
    async def on_fingerprint_enrolled(
        self,
        personnel_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """Handle fingerprint enrollment - queue fingerprint sync to all devices"""
        try:
            if not self.sync_rules.get('fingerprint_enroll', True):
                return {"success": False, "message": "Fingerprint sync rule disabled"}
            
            # Get personnel details
            personnel = db.query(PersonnelEmployee).filter(
                PersonnelEmployee.id == personnel_id
            ).first()
            
            if not personnel:
                return {"success": False, "error": "Personnel not found"}
            
            # Get all active devices
            devices_result = db.execute(text("""
                SELECT sn FROM iclock_terminal 
                WHERE state = 1 AND device_type IN (0, 1)
            """))
            
            devices = devices_result.fetchall()
            
            if not devices:
                return {
                    "success": True,
                    "message": "No active devices found",
                    "devices_queued": 0
                }
            
            # Queue fingerprint sync commands
            command_ids = []
            for device_row in devices:
                device_sn = device_row.sn
                
                # Queue fingerprint update
                cmd_id = await self.queue_command_for_device(
                    device_sn,
                    f"DATA UPDATE FINGER PIN={personnel.emp_code}",
                    db
                )
                if cmd_id:
                    command_ids.append(cmd_id)
            
            return {
                "success": True,
                "message": f"Fingerprint sync queued for {len(devices)} devices",
                "devices_queued": len(devices),
                "command_ids": command_ids
            }
            
        except Exception as e:
            logger.error(f"Error in fingerprint sync: {e}")
            return {"success": False, "error": str(e)}
    
    async def on_face_enrolled(
        self,
        personnel_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """Handle face enrollment - queue face sync to all devices"""
        try:
            if not self.sync_rules.get('face_enroll', True):
                return {"success": False, "message": "Face sync rule disabled"}
            
            # Get personnel details
            personnel = db.query(PersonnelEmployee).filter(
                PersonnelEmployee.id == personnel_id
            ).first()
            
            if not personnel:
                return {"success": False, "error": "Personnel not found"}
            
            # Get all active devices
            devices_result = db.execute(text("""
                SELECT sn FROM iclock_terminal 
                WHERE state = 1 AND device_type IN (0, 1)
            """))
            
            devices = devices_result.fetchall()
            
            if not devices:
                return {
                    "success": True,
                    "message": "No active devices found",
                    "devices_queued": 0
                }
            
            # Queue face sync commands
            command_ids = []
            for device_row in devices:
                device_sn = device_row.sn
                
                # Queue face update
                cmd_id = await self.queue_command_for_device(
                    device_sn,
                    f"DATA UPDATE FACE PIN={personnel.emp_code}",
                    db
                )
                if cmd_id:
                    command_ids.append(cmd_id)
            
            return {
                "success": True,
                "message": f"Face sync queued for {len(devices)} devices",
                "devices_queued": len(devices),
                "command_ids": command_ids
            }
            
        except Exception as e:
            logger.error(f"Error in face sync: {e}")
            return {"success": False, "error": str(e)}
    
    async def on_device_came_online(
        self,
        device_sn: str,
        db: Session
    ) -> Dict[str, Any]:
        """Handle device coming online - queue INFO command and sync users"""
        try:
            if not self.sync_rules.get('device_online', True):
                return {"success": False, "message": "Device online sync rule disabled"}
            
            # Get device details
            device = db.query(IClockTerminal).filter(
                IClockTerminal.sn == device_sn
            ).first()
            
            if not device:
                return {"success": False, "error": "Device not found"}
            
            command_ids = []
            
            # Queue INFO command to get device details
            info_cmd_id = await self.queue_command_for_device(
                device_sn,
                "INFO",
                db,
                priority=1  # High priority
            )
            if info_cmd_id:
                command_ids.append(info_cmd_id)
            
            # Queue user sync for device's area
            if device.area_id:
                users_result = db.execute(text("""
                    SELECT emp_code FROM personnel_employee 
                    WHERE area_id = :area_id AND deleted = 0
                """), {'area_id': device.area_id})
                
                users = users_result.fetchall()
                
                for user_row in users:
                    emp_code = user_row.emp_code
                    
                    # Queue user info update
                    cmd_id = await self.queue_command_for_device(
                        device_sn,
                        f"DATA UPDATE USERINFO PIN={emp_code}",
                        db
                    )
                    if cmd_id:
                        command_ids.append(cmd_id)
            
            return {
                "success": True,
                "message": f"Device online sync queued for {device_sn}",
                "commands_queued": len(command_ids),
                "command_ids": command_ids
            }
            
        except Exception as e:
            logger.error(f"Error in device online sync: {e}")
            return {"success": False, "error": str(e)}
    
    async def cleanup_expired_commands(
        self,
        db: Session,
        timeout_minutes: int = 10
    ) -> Dict[str, Any]:
        """Clean up expired commands in the queue"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            
            # Update expired pending commands to failed
            result = db.execute(text("""
                UPDATE iclock_devcmd 
                SET status = 3, cmd_return_time = :now, cmd_return = 'TIMEOUT'
                WHERE status = 0 AND cmd_commit_time < :cutoff_time
            """), {
                'now': datetime.utcnow(),
                'cutoff_time': cutoff_time
            })
            
            expired_count = result.rowcount
            db.commit()
            
            logger.info(f"Cleaned up {expired_count} expired commands")
            
            return {
                "success": True,
                "expired_commands": expired_count,
                "timeout_minutes": timeout_minutes
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up expired commands: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_command_queue_stats(
        self,
        db: Session
    ) -> Dict[str, Any]:
        """Get command queue statistics"""
        try:
            # Get command counts by status
            stats_result = db.execute(text("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    MIN(cmd_commit_time) as oldest_time
                FROM iclock_devcmd 
                GROUP BY status
                ORDER BY status
            """))
            
            stats = {}
            for row in stats_result:
                stats[row.status] = {
                    'count': row.count,
                    'oldest_time': row.oldest_time
                }
            
            # Get devices with most pending commands
            devices_result = db.execute(text("""
                SELECT 
                    sn,
                    COUNT(*) as pending_count
                FROM iclock_devcmd 
                WHERE status = 0
                GROUP BY sn
                ORDER BY pending_count DESC
                LIMIT 10
            """))
            
            devices_with_pending = []
            for row in devices_result:
                devices_with_pending.append({
                    'sn': row.sn,
                    'pending_count': row.pending_count
                })
            
            return {
                "success": True,
                "queue_stats": stats,
                "devices_with_pending": devices_with_pending,
                "total_pending": stats.get(0, {}).get('count', 0),
                "total_sent": stats.get(1, {}).get('count', 0),
                "total_success": stats.get(2, {}).get('count', 0),
                "total_failed": stats.get(3, {}).get('count', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting command queue stats: {e}")
            return {"success": False, "error": str(e)}
    
    def enable_sync_rule(self, rule_name: str) -> bool:
        """Enable a specific sync rule"""
        if rule_name in self.sync_rules:
            self.sync_rules[rule_name] = True
            logger.info(f"Enabled sync rule: {rule_name}")
            return True
        return False
    
    def disable_sync_rule(self, rule_name: str) -> bool:
        """Disable a specific sync rule"""
        if rule_name in self.sync_rules:
            self.sync_rules[rule_name] = False
            logger.info(f"Disabled sync rule: {rule_name}")
            return True
        return False
    
    def get_sync_rules_status(self) -> Dict[str, bool]:
        """Get current status of all sync rules"""
        return self.sync_rules.copy()


# Create service instance
device_sync_rules_service = DeviceSyncRulesService()
