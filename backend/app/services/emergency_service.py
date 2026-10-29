"""
Emergency Management Service - POB v2.0
Comprehensive emergency system with lockdown, fire mode, notifications, and audit trails
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
from sqlalchemy.exc import SQLAlchemyError
import json
import logging
import asyncio
from enum import Enum

from ..models.emergency import (
    EmergencyEvent, EmergencyTemplate, EmergencyNotification,
    EmergencyPlan, EmergencyPanicLog, Transport, TransportMaintenance,
    FlightLog, TransportCrew, TransportSchedule, TransportInventory,
    EmergencyEventType, EmergencyStatus, EmergencyScope, EmergencyInitiatedType,
    NotificationChannel, NotificationStatus, RecipientType, PanicType,
    TransportType, TransportStatus
)
from ..models.biotime_models import EmergencyDevice
from ..models.biotime_models import (
    IClockTerminal, AccDoor, MusteringEvent,
    AuthUser, PersonnelEmployee, BaseOperationLog
)
from ..models.zone import Zone
from ..models.personnel import Personnel
from ..models.access_controller import AccessController, AccessReader
from ..core.database import get_db
from ..services.zkteco.biometric_service import ZKTecoBiometricService
from ..services.emergency_websocket import emergency_websocket_manager
from ..services.zkteco_adms_service import zkteco_adms_service
from ..services.mustering_service import MusteringService

# Configure logging
logger = logging.getLogger(__name__)

TELEGRAM_CHANNEL = 6   # not in the legacy NotificationChannel enum


class EmergencyService:
    """Comprehensive emergency management service"""
    
    def __init__(self):
        self.zkteco_service = ZKTecoBiometricService()
        
        # Emergency type mappings
        self.emergency_type_names = {
            0: "LOCKDOWN",
            1: "FIRE", 
            2: "GAS",
            3: "INTRUDER",
            4: "MEDICAL",
            5: "ALL_CLEAR"
        }
        
        self.emergency_status_names = {
            0: "ACTIVE",
            1: "RESOLVED", 
            2: "CANCELLED"
        }
        
        self.notification_channel_names = {
            0: "SMS",
            1: "EMAIL",
            2: "WHATSAPP", 
            3: "PUSH",
            4: "PA",
            5: "SIREN"
        }

    async def get_emergency_dashboard(self, db: Session) -> Dict[str, Any]:
        """Get comprehensive emergency dashboard data"""
        try:
            # Get active emergencies
            active_emergencies = db.query(EmergencyEvent).filter(
                EmergencyEvent.status == EmergencyStatus.ACTIVE.value
            ).all()
            
            # Count doors by emergency action
            # Doors as last commanded from ApexPOB (not their emergency configuration).
            locked_doors = db.query(AccDoor).filter(AccDoor.lock_state == "locked").count()
            unlocked_doors = db.query(AccDoor).filter(AccDoor.lock_state == "unlocked").count()
            
            # Count active emergency devices
            sirens_on = db.query(EmergencyDevice).filter(
                EmergencyDevice.device_type.in_([1, 2]),  # Siren, Strobe
                EmergencyDevice.status == 1  # ON
            ).count()
            
            # Get recent emergency events
            recent_events = db.query(EmergencyEvent).order_by(
                EmergencyEvent.start_time.desc()
            ).limit(10).all()
            
            # Get zone status
            zones = db.query(Zone).all()
            zone_status = []
            for zone in zones:
                active_count = len([e for e in active_emergencies if zone.id in (e.zone_ids or [])])
                zone_status.append({
                    "id": zone.id,
                    "name": zone.name,
                    "status": "ACTIVE" if active_count > 0 else "SAFE",
                    "active_emergencies": active_count,
                    "capacity": zone.max_capacity,
                    "evac_point": zone.evac_point,
                    # Muster/assembly points are safe destinations, not operational
                    # zones — flag them so the UI can separate them from lockdown targets.
                    "is_muster_point": zone.zone_type == "MUSTER_POINT",
                    "zone_type": zone.zone_type,
                })
            
            return {
                "total_emergencies": len(active_emergencies),
                "active_emergencies": [
                    {
                        "id": e.id,
                        "event_type": e.event_type,
                        "event_type_name": self.emergency_type_names.get(e.event_type, "UNKNOWN"),
                        "status": e.status,
                        "status_name": self.emergency_status_names.get(e.status, "UNKNOWN"),
                        "start_time": e.start_time.isoformat(),
                        "trigger_source": e.trigger_source,
                        "reason": e.reason,
                        "scope": e.scope,
                        "zone_ids": e.zone_ids or [],
                        "door_ids": e.door_ids or []
                    }
                    for e in active_emergencies
                ],
                "doors_locked": locked_doors,
                "doors_unlocked": unlocked_doors,
                "doors_total": db.query(AccDoor).count(),
                "sirens_on": sirens_on,
                "recent_events": [
                    {
                        "id": e.id,
                        "event_type": e.event_type,
                        "event_type_name": self.emergency_type_names.get(e.event_type, "UNKNOWN"),
                        "start_time": e.start_time.isoformat(),
                        "end_time": e.end_time.isoformat() if e.end_time else None,
                        "status": e.status,
                        "trigger_source": e.trigger_source
                    }
                    for e in recent_events
                ],
                "zone_status": zone_status,
                "last_trigger": active_emergencies[0].start_time.isoformat() if active_emergencies else None,
                "system_status": "EMERGENCY" if active_emergencies else "NORMAL"
            }
            
        except Exception as e:
            logger.error(f"Error getting emergency dashboard: {str(e)}")
            raise

    @staticmethod
    def _muster_zone_ids(db: Session) -> set:
        """IDs of zones that are muster/assembly points (zone_type == MUSTER_POINT).

        A muster point is the *safe destination* people evacuate TO — its headcount
        comes from Horus H1 ADMS readers via the mustering module. It is never an
        operational zone to lock down or evacuate, so emergency actions exclude it.
        """
        rows = db.query(Zone.id).filter(Zone.zone_type == "MUSTER_POINT").all()
        return {r[0] for r in rows}

    @staticmethod
    def _dedupe_doors(doors: List[AccDoor]) -> List[AccDoor]:
        """Preserve order, drop duplicate AccDoor rows by id."""
        seen, out = set(), []
        for d in doors:
            if d.id not in seen:
                seen.add(d.id)
                out.append(d)
        return out

    def _controller_doors_for_zones(self, db: Session, zone_ids: List[int]) -> List[AccDoor]:
        """Access-control doors whose controller port maps to a reader in `zone_ids`.

        A door is a (controller_id, port) unit; a zone owns controller ports via
        AccessReader (controller_id, door_no, zone_id). Match port == door_no.
        """
        if not zone_ids:
            return []
        reader_ports = db.query(
            AccessReader.controller_id, AccessReader.door_no
        ).filter(AccessReader.zone_id.in_(zone_ids)).distinct().all()
        pairs = {(c, d) for c, d in reader_ports}
        if not pairs:
            return []
        candidates = db.query(AccDoor).filter(
            AccDoor.controller_id.in_({c for c, _ in pairs}),
            AccDoor.port.isnot(None),
        ).all()
        return [d for d in candidates if (d.controller_id, d.port) in pairs]

    async def _command_controller_door(
        self, db: Session, door: AccDoor, action: str
    ) -> Tuple[bool, Optional[str]]:
        """Emergency-command an access-control door via its C3 controller.

        Run off the event loop so a blocking panel connect can never starve the
        request workers. Uses the proven ControlDeviceOutput verb: duration 255
        holds the door open for egress (unlock); duration 0 returns it to the
        fail-secure locked state (lock). An unreachable panel is reported as a
        failed door — it is never silently treated as done.
        """
        from ..services.zkteco import c3_zkaccess
        ctrl = db.query(AccessController).filter(
            AccessController.id == door.controller_id
        ).first()
        if not ctrl:
            return False, "Controller not found"

        duration = 255 if action == "unlock" else 0

        def _send():
            with c3_zkaccess.ZKAccessC3Client(
                ctrl.ip_address, ctrl.port or 4370, ctrl.comm_password or ""
            ) as c:
                return c.open_door(int(door.port), duration)

        try:
            await asyncio.to_thread(_send)
            return True, None
        except Exception as e:  # noqa: BLE001 — panel error must not abort the lockdown
            logger.error(
                f"Controller door {door.id} (ctrl {door.controller_id} port {door.port}) "
                f"{action} failed: {e}"
            )
            return False, str(e)

    async def _switch_controller_aux(self, db: Session, device, on: bool) -> Tuple[bool, Optional[str]]:
        """Siren / strobe wired to a C3 panel's AUX output: hold on, or switch off."""
        from ..services.zkteco import c3_zkaccess
        ctrl = db.query(AccessController).filter(AccessController.id == device.controller_id).first()
        if not ctrl:
            return False, "Controller not found"

        def _send():
            with c3_zkaccess.ZKAccessC3Client(ctrl.ip_address, ctrl.port or 4370, ctrl.comm_password or "") as c:
                return c.aux_output(int(device.aux_no or 1), 255 if on else 0)
        try:
            await asyncio.to_thread(_send)
            return True, None
        except Exception as e:  # noqa: BLE001
            logger.error(f"Siren {device.id} (ctrl {device.controller_id} aux {device.aux_no}) {'on' if on else 'off'} failed: {e}")
            return False, str(e)

    async def _command_door(self, db: Session, door: AccDoor, action: str, by: str) -> Tuple[bool, Optional[str]]:
        """Lock / unlock one door (C3 controller port or standalone terminal relay) and
        record the outcome on the door, so the operator sees its real state."""
        try:
            if getattr(door, "controller_id", None) and door.port is not None:
                ok, err = await self._command_controller_door(db, door, action)
            elif door.terminal:
                res = await self.zkteco_queue_command(door.terminal.sn, "RELAY_OFF" if action == "lock" else "RELAY_ON")
                ok, err = bool(res.get("success")), (None if res.get("success") else res.get("error") or "Command failed")
            else:
                ok, err = False, "Door is not wired to a controller or terminal"
        except Exception as e:  # noqa: BLE001
            ok, err = False, str(e)
        now = datetime.now(timezone.utc)
        if ok:
            door.lock_state = "locked" if action == "lock" else "unlocked"
            door.lock_state_error = None
        else:
            door.lock_state_error = f"{action} failed: {err}"
        door.lock_state_at, door.lock_state_by = now, by
        return ok, err

    @staticmethod
    def _add_action(event, action: Dict[str, Any]) -> None:
        """Append to the event's JSON action log. Reassign (not .append) so SQLAlchemy
        sees the change — an in-place append on a JSON column is silently not saved."""
        event.actions = [*(event.actions or []), action]

    @staticmethod
    def _user_label(db: Session, user_id: Optional[int]) -> str:
        if not user_id:
            return "System"
        u = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        return (f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username) if u else f"user #{user_id}"

    def door_states(self, db: Session) -> Dict[str, Any]:
        """Every door with its last commanded state and its controller's health."""
        from .controller_doors import ensure_all_controller_doors
        ensure_all_controller_doors(db)
        ctrls = {c.id: c for c in db.query(AccessController).all()}
        rows = []
        for d in db.query(AccDoor).order_by(AccDoor.name).all():
            c = ctrls.get(d.controller_id)
            online = (c.status == "online") if c is not None else None
            rows.append({
                "id": d.id, "name": d.name,
                "controller": c.name if c else (d.terminal_sn or None),
                "controller_online": online,
                "emergency_action": d.emergency_action or 0,
                "state": d.lock_state or "normal",
                "changed_at": d.lock_state_at.isoformat() if d.lock_state_at else None,
                "changed_by": d.lock_state_by,
                "error": d.lock_state_error,
            })
        summary = {"total": len(rows),
                   "locked": sum(r["state"] == "locked" for r in rows),
                   "unlocked": sum(r["state"] == "unlocked" for r in rows),
                   "problems": sum(bool(r["error"]) or r["controller_online"] is False for r in rows)}
        return {"summary": summary, "doors": rows}

    async def execute_lockdown(
        self,
        scope: str,
        zone_ids: Optional[List[int]] = None,
        location_ids: Optional[List[int]] = None,
        door_ids: Optional[List[int]] = None,
        action: str = "lock",
        reason: Optional[str] = None,
        initiated_by: Optional[int] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Lock or unlock doors, record each door's state, alert the response team.

        Which doors a Global/Zone command touches:
          lock   → every door except fire exits (emergency action "unlock"), which stay
                   free so people can get out
          unlock → every door except secure doors (emergency action "lock"), which stay
                   locked in an emergency
        Doors picked one by one (scope "door") always get the command.
        Unlocking ends the lockdown(s) it releases — it is not a new emergency.
        """
        if db is None:
            db = next(get_db())

        try:
            if action not in ["lock", "unlock"]:
                raise ValueError("Action must be 'lock' or 'unlock'")
            from .controller_doors import ensure_all_controller_doors
            ensure_all_controller_doors(db)

            if scope == "global":
                target_doors = db.query(AccDoor).all()
                scope_enum = EmergencyScope.GLOBAL.value
            elif scope == "zone" and zone_ids:
                # Muster/assembly points are safe destinations, not lockdown targets.
                muster_ids = self._muster_zone_ids(db)
                zone_ids = [z for z in zone_ids if z not in muster_ids]
                if not zone_ids:
                    raise ValueError(
                        "Muster points are safe assembly areas and cannot be locked "
                        "down or evacuated. Select operational zones instead."
                    )
                terminal_doors = db.query(AccDoor).join(IClockTerminal).filter(
                    IClockTerminal.zone_id.in_(zone_ids)
                ).all()
                target_doors = self._dedupe_doors(
                    terminal_doors + self._controller_doors_for_zones(db, zone_ids)
                )
                scope_enum = EmergencyScope.ZONE.value
            elif scope == "location" and location_ids:
                target_doors = db.query(AccDoor).join(IClockTerminal).filter(
                    IClockTerminal.area_id.in_(location_ids)
                ).all()
                scope_enum = EmergencyScope.LOCATION.value
            elif scope == "door" and door_ids:
                target_doors = db.query(AccDoor).filter(AccDoor.id.in_(door_ids)).all()
                scope_enum = EmergencyScope.DOOR.value
            else:
                raise ValueError("Invalid scope or missing target identifiers")

            by = self._user_label(db, initiated_by)
            verb = "locked" if action == "lock" else "unlocked"
            results: List[Dict[str, Any]] = []
            to_send: List[AccDoor] = []
            for door in target_doors:
                keep = 2 if action == "lock" else 1          # emergency_action that is left alone
                if scope != "door" and (door.emergency_action or 0) == keep:
                    results.append({"door_id": door.id, "door_name": door.name, "result": "skipped",
                                    "reason": "Fire exit — kept free so people can get out" if action == "lock"
                                    else "Secure door — stays locked in an emergency"})
                else:
                    to_send.append(door)

            # One panel takes one connection at a time: doors on the same controller go
            # in turn, different controllers in parallel (an unreachable panel must not
            # hold up the rest of the site).
            groups: Dict[Any, List[AccDoor]] = {}
            for d in to_send:
                groups.setdefault(d.controller_id or f"t:{d.terminal_sn}", []).append(d)

            async def run_group(doors):
                out = []
                for d in doors:
                    ok, err = await self._command_door(db, d, action, by)
                    out.append({"door_id": d.id, "door_name": d.name,
                                "result": "done" if ok else "failed", "reason": None if ok else err})
                return out
            for chunk in await asyncio.gather(*(run_group(g) for g in groups.values())):
                results.extend(chunk)

            done = [r for r in results if r["result"] == "done"]
            failed = [r for r in results if r["result"] == "failed"]
            skipped = [r for r in results if r["result"] == "skipped"]
            now = datetime.now(timezone.utc)

            if not target_doors:
                msg = ("No doors are set up yet — add the ZKTeco controllers under Access Control → "
                       "Controllers. Nothing was locked or unlocked.")
            else:
                msg = f"{len(done)} of {len(target_doors)} door(s) {verb}"
                if failed:
                    msg += f"; {len(failed)} FAILED — check them now"
                if skipped:
                    msg += f"; {len(skipped)} left as they were"
                msg += "."

            emergency_event = EmergencyEvent(
                event_type=EmergencyEventType.LOCKDOWN.value,
                # A lockdown stays ACTIVE until released; an unlock (or a command that
                # touched nothing) is a completed action, not a running emergency.
                status=(EmergencyStatus.ACTIVE.value if action == "lock" and done
                        else EmergencyStatus.RESOLVED.value),
                scope=scope_enum,
                zone_ids=zone_ids,
                door_ids=[d.id for d in target_doors],
                initiated_by=initiated_by,
                initiated_type=EmergencyInitiatedType.MANUAL_UI.value,
                trigger_source="Web UI",
                reason=reason or f"Emergency {action}",
                end_time=None if (action == "lock" and done) else now,
                actions=[{"type": "lockdown", "action": action, "doors": [d.id for d in target_doors],
                          "processed_doors": [r["door_id"] for r in done], "failed_doors": failed,
                          "skipped_doors": skipped, "timestamp": now.isoformat()}],
            )
            db.add(emergency_event)
            db.flush()

            released = 0
            if action == "unlock":
                # A lockdown is over once none of its doors is still locked.
                # Secure doors (emergency action "lock") are meant to stay locked, so they
                # don't keep a lockdown open.
                still_locked = {d.id for d in db.query(AccDoor.id).filter(
                    AccDoor.lock_state == "locked", or_(AccDoor.emergency_action.is_(None), AccDoor.emergency_action != 1)).all()}
                for ev in db.query(EmergencyEvent).filter(
                        EmergencyEvent.event_type == EmergencyEventType.LOCKDOWN.value,
                        EmergencyEvent.status == EmergencyStatus.ACTIVE.value,
                        EmergencyEvent.id != emergency_event.id).all():
                    if not (set(ev.door_ids or []) & still_locked):
                        ev.status, ev.end_time = EmergencyStatus.RESOLVED.value, now
                        released += 1

            await self.log_emergency_operation(
                db=db, user_id=initiated_by, action=f"EMERGENCY_{action.upper()}", target_type="door",
                target_ids=[d.id for d in target_doors], emergency_event_id=emergency_event.id,
                details={"scope": scope, "action": action, "processed_count": len(done),
                         "failed_count": len(failed), "skipped_count": len(skipped), "reason": reason})
            db.commit()

            if target_doors:
                self._announce_lockdown(db, emergency_event.id, action, scope, by, reason, msg, failed)

            await self.broadcast_emergency_update({
                "type": "emergency_lockdown",
                "data": {"emergency_event_id": emergency_event.id, "action": action, "scope": scope,
                         "processed_doors": len(done), "failed_doors": len(failed),
                         "timestamp": now.isoformat()},
            })

            return {
                "success": bool(target_doors) and not failed,
                "emergency_event_id": emergency_event.id,
                "action": action,
                "scope": scope,
                "total_doors": len(target_doors),
                "processed_doors": len(done),
                "failed_doors": len(failed),
                "skipped_doors": len(skipped),
                "lockdowns_ended": released,
                "doors": results,
                "failed_details": failed,
                "message": msg,
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error executing lockdown: {str(e)}")
            raise

    def _announce_lockdown(self, db: Session, event_id: int, action: str, scope: str, by: str,
                           reason: Optional[str], summary: str, failed: List[Dict[str, Any]]) -> None:
        """Bell notification for everyone signed in + WhatsApp/Telegram/email to the response team."""
        word = "LOCKDOWN" if action == "lock" else "DOORS UNLOCKED"
        where = {"global": "whole site", "zone": "selected zones", "door": "selected doors"}.get(scope, scope)
        text_ = f"{word} ({where}) by {by}: {summary}"
        if reason:
            text_ += f" Reason: {reason}."
        if failed:
            text_ += " Failed: " + ", ".join(f["door_name"] for f in failed[:10]) + ("…" if len(failed) > 10 else "")
        title = f"{word} — {summary}"[:200]
        priority = "critical" if failed or action == "lock" else "high"
        try:
            db.execute(text("""
                INSERT INTO sys_notifications (dedup_key, notification_type, title, message, priority, link, expires_at)
                VALUES (:dk, 'emergency', :title, :msg, :pri, '/emergency-response', NOW() + INTERVAL '12 hours')
                ON CONFLICT (dedup_key) DO NOTHING
            """), {"dk": f"lockdown-{event_id}", "title": title, "msg": text_, "pri": priority})
            db.commit()
            from ..api.notifications import broadcast_notification
            asyncio.get_running_loop().create_task(broadcast_notification(
                {"type": "emergency", "title": title, "message": text_, "priority": priority,
                 "link": "/emergency-response"}))
        except Exception as e:  # noqa: BLE001 — a notification must never undo the door commands
            db.rollback()
            logger.warning(f"Lockdown bell notification skipped: {e}")
        try:
            from .notify_dispatch import dispatch_background
            dispatch_background("lockdown", event_id, [], title, text_, None, include_responders=True)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Lockdown team alert skipped: {e}")

    async def activate_fire_mode(
        self,
        zone_id: Optional[int] = None,
        location_id: Optional[int] = None,
        muster_zone_ids: Optional[List[int]] = None,
        action: str = "activate",
        reason: Optional[str] = None,
        initiated_by: Optional[int] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Activate fire mode with comprehensive response"""
        
        if db is None:
            db = next(get_db())
        
        try:
            if action not in ["activate", "clear"]:
                raise ValueError("Action must be 'activate' or 'clear'")
            
            # Get target zone
            if zone_id:
                zone = db.query(Zone).filter(Zone.id == zone_id).first()
                if not zone:
                    raise ValueError(f"Zone {zone_id} not found")
                if zone.zone_type == "MUSTER_POINT":
                    # A muster point is the safe destination people evacuate TO — you
                    # don't activate fire evacuation on it. Headcount there is via the
                    # mustering module (Horus H1 ADMS readers), not fire mode.
                    raise ValueError(
                        "Muster points are safe assembly areas and cannot be the "
                        "target of fire mode. Select an operational zone."
                    )
            else:
                zone = None

            # Scope: location (personnel_area) > zone > global
            if location_id:
                fire_scope = EmergencyScope.LOCATION.value
            elif zone_id:
                fire_scope = EmergencyScope.ZONE.value
            else:
                fire_scope = EmergencyScope.GLOBAL.value

            # Create emergency event
            emergency_event = EmergencyEvent(
                event_type=EmergencyEventType.FIRE.value,
                status=EmergencyStatus.ACTIVE.value if action == "activate" else EmergencyStatus.RESOLVED.value,
                scope=fire_scope,
                zone_ids=[zone_id] if zone_id else [],
                initiated_by=initiated_by,
                initiated_type=EmergencyInitiatedType.MANUAL_UI.value,
                trigger_source="Web UI - Fire Mode",
                reason=reason or f"Fire mode {action}",
                actions=[]
            )
            
            db.add(emergency_event)
            db.flush()
            # Commit immediately so the emergency event row is durable before any
            # child operation (mustering, ZKTeco commands) that shares this session
            # and may call db.rollback() on its own failure path.
            db.commit()

            results = {
                "unlocked_doors": 0,
                "locked_doors": 0,
                "sirens_activated": 0,
                "mustering_started": False,
                "notifications_sent": 0
            }

            from .controller_doors import ensure_all_controller_doors
            ensure_all_controller_doors(db)

            if action == "activate":
                # 1. Unlock fire exits (emergency_action=2) — scoped to the location's readers when given
                _fe_q = db.query(AccDoor).filter(AccDoor.emergency_action == 2)
                if location_id:
                    _fe_q = _fe_q.join(IClockTerminal).filter(IClockTerminal.area_id == location_id)
                fire_exit_doors = _fe_q.all()

                for door in fire_exit_doors:
                    sp = db.begin_nested()
                    try:
                        ok, _err = await self._command_door(db, door, "unlock", "Fire mode")
                        results["unlocked_doors"] += 1 if ok else 0
                        sp.commit()
                    except Exception as e:
                        logger.error(f"Error unlocking fire exit {door.id}: {str(e)}")
                        sp.rollback()  # roll back only this door; prior commands are preserved

                self._add_action(emergency_event, {
                    "type": "unlock_fire_exits",
                    "doors": [d.id for d in fire_exit_doors],
                    "count": results["unlocked_doors"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # 2. Lock danger zones (emergency_action=1) — scoped to the location's readers when given
                _dz_q = db.query(AccDoor).filter(AccDoor.emergency_action == 1)
                if location_id:
                    _dz_q = _dz_q.join(IClockTerminal).filter(IClockTerminal.area_id == location_id)
                danger_zone_doors = _dz_q.all()

                for door in danger_zone_doors:
                    sp = db.begin_nested()
                    try:
                        ok, _err = await self._command_door(db, door, "lock", "Fire mode")
                        results["locked_doors"] += 1 if ok else 0
                        sp.commit()
                    except Exception as e:
                        logger.error(f"Error locking danger zone {door.id}: {str(e)}")
                        sp.rollback()

                self._add_action(emergency_event, {
                    "type": "lock_danger_zones",
                    "doors": [d.id for d in danger_zone_doors],
                    "count": results["locked_doors"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # 3. Turn ON sirens/strobes
                emergency_devices = db.query(EmergencyDevice).filter(
                    EmergencyDevice.device_type.in_([1, 2]),  # Siren, Strobe
                    EmergencyDevice.status != 2  # Not fault
                ).all()

                for device in emergency_devices:
                    sp = db.begin_nested()
                    try:
                        if device.controller_id and device.aux_no:
                            ok, _err = await self._switch_controller_aux(db, device, True)
                            device.status = 1 if ok else 2
                            results["sirens_activated"] += 1 if ok else 0
                        elif device.terminal:
                            await self.zkteco_queue_command(device.terminal.sn, "EMERGENCY_ON")
                            device.status = 1  # ON
                            results["sirens_activated"] += 1
                        sp.commit()
                    except Exception as e:
                        logger.error(f"Error activating siren {device.id}: {str(e)}")
                        sp.rollback()

                self._add_action(emergency_event, {
                    "type": "siren_activation",
                    "devices": [d.id for d in emergency_devices],
                    "count": results["sirens_activated"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # 4. Start mustering event — use MusteringService so that expected
                # personnel are calculated from Personnel.current_zone_id and
                # MusteringExpected rows are created. Without this the headcount
                # shows 0 expected during an actual fire evacuation.
                # MusteringService.start_mustering_event has its own db.commit() on
                # success and db.rollback() on failure. Because the emergency event
                # was committed above, its own rollback cannot affect it.
                # Affected/source zones = the fired zone, or (global) every active
                # OPERATIONAL zone — never a muster point (those are the destinations).
                # Every operational zone (no cap — a "site-wide" fire must list the
                # whole POB; zones with no type set are operational too).
                mustering_zone_ids = [zone_id] if zone_id else MusteringService.operational_zone_ids(db)
                from .notify_dispatch import configured_channels
                live = configured_channels()
                try:
                    muster_result = MusteringService(db).start_mustering_event(
                        zone_ids=mustering_zone_ids,
                        muster_zone_ids=muster_zone_ids,  # chosen assembly points (optional)
                        event_type=3 if "gas" in (reason or "").lower() else 2,  # Gas / Fire
                        initiated_by=initiated_by,
                        notes=f"Evacuation — auto-started by fire mode: {reason or ''}".strip(),
                        # The muster's own alerts: instruction + assembly point to staff and
                        # visitors, situation to the response team, then the all-clear.
                        notify_whatsapp=live["whatsapp"], notify_email=live["email"], notify_sms=live["sms"],
                        notify_telegram=live.get("telegram", False),
                    )
                    mustering_event_id = muster_result["event_id"]
                    # Update the already-committed emergency event with the muster link
                    db.query(EmergencyEvent).filter(EmergencyEvent.id == emergency_event.id).update(
                        {"mustering_event_id": mustering_event_id}
                    )
                    emergency_event.mustering_event_id = mustering_event_id
                    results["mustering_started"] = True

                    self._add_action(emergency_event, {
                        "type": "start_mustering",
                        "mustering_event_id": mustering_event_id,
                        "zone_ids": mustering_zone_ids,
                        "total_expected": muster_result.get("total_expected", 0),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as muster_err:
                    logger.error(f"Fire-mode mustering start failed: {muster_err}")
                    results["mustering_started"] = False
                    # Ensure the session is clean after mustering's rollback
                    try:
                        db.rollback()
                    except Exception:
                        pass

                # 5. Alerts — the muster sent them; only fall back to a general
                # emergency alert if the muster could not start.
                if results.get("mustering_started"):
                    results["notifications_sent"] = muster_result.get("total_expected", 0)
                else:
                    results["notifications_sent"] = await self.send_emergency_notifications(
                        emergency_event.id,
                        [NotificationChannel.WHATSAPP.value, TELEGRAM_CHANNEL, NotificationChannel.EMAIL.value, NotificationChannel.SMS.value],
                        db
                    )
                
            else:  # clear action
                # 1. Sirens / strobes off
                emergency_devices = db.query(EmergencyDevice).filter(
                    EmergencyDevice.device_type.in_([1, 2]),  # Siren, Strobe
                    EmergencyDevice.status.in_([1, 2]),
                ).all()
                for device in emergency_devices:
                    try:
                        if device.controller_id and device.aux_no:
                            ok, _err = await self._switch_controller_aux(db, device, False)
                            device.status = 0 if ok else 2
                        elif device.terminal:
                            await self.zkteco_queue_command(device.terminal.sn, "EMERGENCY_OFF")
                            device.status = 0
                        results["sirens_activated"] += 1
                    except Exception as e:
                        logger.error(f"Error deactivating siren {device.id}: {str(e)}")
                self._add_action(emergency_event, {
                    "type": "siren_deactivation",
                    "devices": [d.id for d in emergency_devices],
                    "count": len(emergency_devices),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # 2. Re-lock the fire exits that were held open (the old clear left
                #    every fire exit standing open after the emergency).
                relocked = 0
                for door in db.query(AccDoor).filter(AccDoor.emergency_action == 2).all():
                    try:
                        ok, _err = await self._command_door(db, door, "lock", "Fire mode cleared")
                        relocked += 1 if ok else 0
                    except Exception as e:
                        logger.error(f"Error re-locking fire exit {door.id}: {e}")
                results["locked_doors"] = relocked
                self._add_action(emergency_event, {"type": "relock_fire_exits", "count": relocked,
                                                "timestamp": datetime.now(timezone.utc).isoformat()})
                db.commit()

                # 3. End running musters the proper way: final headcount, muster
                #    readers back to normal, all-clear to staff + response team.
                active_mustering = db.query(MusteringEvent).filter(MusteringEvent.status == 0).all()
                ended = 0
                for muster in active_mustering:
                    try:
                        MusteringService(db).end_mustering_event(muster.id, initiated_by, "Fire mode cleared")
                        ended += 1
                    except Exception as me:
                        logger.error(f"Error ending muster {muster.id} on fire-mode clear: {me}")
                        db.rollback()
                emergency_event = db.merge(emergency_event)
                emergency_event.actions = list(emergency_event.actions or []) + [{
                    "type": "end_mustering", "events_ended": ended,
                    "timestamp": datetime.now(timezone.utc).isoformat()}]

                # 4. End the fire emergency itself. (Clearing used to record only this
                #    "cleared" row, leaving the original fire event ACTIVE — the site
                #    stayed in EMERGENCY after the operator pressed All Clear.)
                now = datetime.now(timezone.utc)
                fires = db.query(EmergencyEvent).filter(
                    EmergencyEvent.event_type == EmergencyEventType.FIRE.value,
                    EmergencyEvent.status == EmergencyStatus.ACTIVE.value,
                    EmergencyEvent.id != emergency_event.id).all()
                for f in fires:
                    f.status, f.end_time = EmergencyStatus.RESOLVED.value, now
                    self._add_action(f, {"type": "cleared", "by_event": emergency_event.id, "timestamp": now.isoformat()})
                emergency_event.end_time = now
                results["fire_events_ended"] = len(fires)
                results["musters_ended"] = ended

            # Log operation
            await self.log_emergency_operation(
                db=db,
                user_id=initiated_by,
                action=f"FIRE_MODE_{action.upper()}",
                target_type="system",
                emergency_event_id=emergency_event.id,
                details=results
            )
            
            db.commit()
            
            # Broadcast WebSocket update
            await self.broadcast_emergency_update({
                "type": "fire_mode",
                "data": {
                    "emergency_event_id": emergency_event.id,
                    "action": action,
                    "zone_id": zone_id,
                    "results": results,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            })
            
            return {
                "success": True,
                "emergency_event_id": emergency_event.id,
                "action": action,
                "zone_id": zone_id,
                "results": results,
                "message": (f"Fire mode {action} completed successfully" if action == "activate" else
                            (f"Fire mode cleared — {results.get('locked_doors', 0)} fire exit(s) re-locked, "
                             f"{results.get('sirens_activated', 0)} siren(s) off, {results.get('musters_ended', 0)} muster(s) ended."
                             if results.get("fire_events_ended") else "Fire mode was not on — nothing to clear."))
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error activating fire mode: {str(e)}")
            raise

    async def send_emergency_notifications(
        self,
        emergency_event_id: int,
        channels: List[int],
        db: Session
    ) -> int:
        """Alert everyone on board in scope + the response team, on the requested
        channels that are configured. Sent in the background and logged per recipient
        (notify_delivery). Returns the number of people queued.

        Recipients are people ON BOARD — not every active staff record. Staff at home
        on their off-rotation must not be told to evacuate a site they are not on.
        """
        from .notify_dispatch import dispatch_background, onboard_people
        event = db.query(EmergencyEvent).filter(EmergencyEvent.id == emergency_event_id).first()
        if not event:
            raise ValueError(f"Emergency event {emergency_event_id} not found")

        names = {NotificationChannel.SMS.value: "sms", NotificationChannel.EMAIL.value: "email",
                 NotificationChannel.WHATSAPP.value: "whatsapp", TELEGRAM_CHANNEL: "telegram"}
        wanted = [names[c] for c in channels if c in names]
        if not wanted:
            return 0

        type_name = self.emergency_type_names.get(event.event_type, "EMERGENCY")
        zone_ids = event.zone_ids if event.scope == EmergencyScope.ZONE.value else None
        people = onboard_people(db, zone_ids) if (zone_ids or event.scope != EmergencyScope.ZONE.value) else []
        instruction = {
            "FIRE": "Leave the building by the nearest exit and go to your assembly point. Do not use lifts.",
            "GAS": "Stop work, move upwind and go to your assembly point.",
            "LOCKDOWN": "Stay where you are, secure the door and wait for instructions.",
            "MEDICAL": "Keep the area clear for the medical team.",
        }.get(type_name.upper(), "Follow the instructions of your warden.")
        text_msg = f"EMERGENCY — {type_name}: {event.reason or 'emergency declared'}. {instruction}"
        subject = f"EMERGENCY — {type_name}"
        dispatch_background("emergency", event.id, people, subject, text_msg, wanted, include_responders=True)
        return len(people)

    async def get_notification_recipients(
        self,
        channel: int,
        scope: int,
        zone_ids: Optional[List[int]],
        db: Session
    ) -> List[Dict[str, Any]]:
        """Resolve recipient addresses for a channel from the Personnel roster.

        Uses the Personnel app model (which actually carries contact details):
          EMAIL     → Personnel.email
          SMS       → Personnel.phone, falling back to emergency_contact_phone
          WHATSAPP  → same phone fields as SMS

        Scope:
          GLOBAL → every active person
          ZONE   → people whose current_zone_id (access-control live location) is in
                   zone_ids. This is the access-control Zone FK, NOT a T&A area.

        PA/SIREN/PUSH have no per-person address; they are broadcast channels handled
        in send_notification, so this returns [] for them (0 per-recipient rows).
        Addresses are de-duplicated so nobody is messaged twice.
        """
        recipients: List[Dict[str, Any]] = []

        # Broadcast-only channels have no per-recipient address list.
        if channel not in (
            NotificationChannel.SMS.value,
            NotificationChannel.EMAIL.value,
            NotificationChannel.WHATSAPP.value,
        ):
            return recipients

        try:
            query = db.query(Personnel).filter(Personnel.is_active == True)  # noqa: E712

            if scope == EmergencyScope.ZONE.value and zone_ids:
                query = query.filter(Personnel.current_zone_id.in_(zone_ids))
            elif scope == EmergencyScope.ZONE.value and not zone_ids:
                return recipients  # zone scope with no zones → nobody

            seen_addresses = set()
            for person in query.all():
                if channel == NotificationChannel.EMAIL.value:
                    address = person.email
                else:  # SMS or WHATSAPP
                    address = person.phone or person.emergency_contact_phone

                if not address or not address.strip():
                    continue
                address = address.strip()
                if address in seen_addresses:
                    continue
                seen_addresses.add(address)

                recipients.append({
                    "type": RecipientType.USER.value,
                    "id": person.id,
                    "address": address,
                })

        except Exception as e:
            logger.error(f"Error getting notification recipients: {str(e)}")

        return recipients

    async def send_notification(
        self,
        channel: int,
        address: str,
        message: str,
        subject: str = "Emergency Alert",
    ) -> Dict[str, Any]:
        """Send one notification through a specific channel.

        Every channel routes through the SHARED env-configured senders
        (notify_email / notify_sms / notify_whatsapp) so email, SMS and WhatsApp
        all read one config surface and behave identically to mustering alerts.
        The senders block on I/O, so they run via asyncio.to_thread() — the event
        loop is never stalled during an emergency with many recipients. They also
        never raise, so one failed address can't abort the rest.
        """
        try:
            if channel == NotificationChannel.SMS.value:
                from .notify_sms import send_sms
                result = await asyncio.to_thread(send_sms, address, message)
                if result.get("sent"):
                    return {"success": True}
                return {"success": False, "error": result.get("error", "SMS send failed")}

            elif channel == NotificationChannel.EMAIL.value:
                from .notify_email import send_email
                # message is plain text; wrap minimally for the HTML part.
                html = f"<p>{message}</p>"
                result = await asyncio.to_thread(send_email, address, subject, html, message)
                if result.get("sent"):
                    return {"success": True}
                return {"success": False, "error": result.get("error", "Email send failed")}

            elif channel == NotificationChannel.WHATSAPP.value:
                from .notify_whatsapp import send_whatsapp
                result = await asyncio.to_thread(send_whatsapp, address, message)
                if result.get("sent"):
                    return {"success": True}
                return {"success": False, "error": result.get("error", "WhatsApp send failed")}

            elif channel == NotificationChannel.PA.value:
                # PA is a site-wide broadcast, not a per-recipient message.
                logger.info(f"PA broadcast: {message}")
                return {"success": True}

            else:
                return {"success": False, "error": f"Channel {channel} not implemented"}

        except Exception as e:
            logger.error(f"Error sending notification to {address}: {e}")
            return {"success": False, "error": str(e)}

    async def zkteco_queue_command(self, terminal_sn: str, command: str) -> Dict[str, Any]:
        """Queue command to ZKTeco device via ADMS"""
        
        try:
            # Use ADMS service for emergency commands
            result = await zkteco_adms_service.queue_device_command(terminal_sn, command)
            return result
        
        except Exception as e:
            logger.error(f"Error queuing command to {terminal_sn}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def zkteco_queue_device_command(self, terminal_sn: str, command: str) -> Dict[str, Any]:
        """Queue device command to ZKTeco ADMS"""
        
        try:
            # Use ADMS service for command queuing
            result = await zkteco_adms_service.queue_device_command(terminal_sn, command)
            return result
        
        except Exception as e:
            logger.error(f"Error queuing device command: {str(e)}")
            return {"success": False, "error": str(e)}

    async def log_emergency_operation(
        self,
        db: Session,
        user_id: Optional[int],
        action: str,
        target_type: str,
        target_ids: Optional[List[int]] = None,
        emergency_event_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log emergency operation for audit trail"""
        
        try:
            log_entry = BaseOperationLog(
                user_id=user_id,
                action=action,
                table_name="emergency_event" if emergency_event_id else target_type,
                record_id=emergency_event_id or (target_ids[0] if target_ids else None),
                new_values=json.dumps(details) if details else None,
                created_at=datetime.now(timezone.utc)
            )
            
            db.add(log_entry)
            
        except Exception as e:
            logger.error(f"Error logging emergency operation: {str(e)}")

    async def broadcast_emergency_update(self, update_data: Dict[str, Any]):
        """Broadcast emergency update via WebSocket and SSE so every open browser
        tab receives the alert — not only those on the emergency page."""
        try:
            await emergency_websocket_manager.broadcast(update_data)
        except Exception as e:
            logger.error(f"Error broadcasting emergency update via WebSocket: {str(e)}")
        try:
            from ..api.notifications import broadcast_notification
            # Build a human-readable SSE notification from the update payload
            event_type = update_data.get("type", "emergency_update")
            data = update_data.get("data", {})
            if event_type == "emergency_lockdown":
                return          # announced with its door-by-door result in _announce_lockdown
            action = data.get("action", "")
            res = data.get("results") or {}
            if event_type == "fire_mode":
                if action == "clear":
                    title = "Fire Mode cleared — all clear"
                    msg = (f"{res.get('locked_doors', 0)} fire exit(s) re-locked, {res.get('sirens_activated', 0)} "
                           f"siren(s) off, {res.get('musters_ended', 0)} muster(s) ended.")
                else:
                    title = "FIRE MODE ON — evacuate"
                    msg = (f"{res.get('unlocked_doors', 0)} fire exit(s) unlocked, {res.get('sirens_activated', 0)} "
                           f"siren(s) on" + (", site muster started." if res.get("mustering_started") else "."))
            else:
                title = {"panic": "PANIC ALARM", "emergency_status": "Emergency status update"}.get(event_type, "Emergency alert")
                msg = data.get("message") or title
            await broadcast_notification({
                "type": event_type,
                "priority": "high" if action == "clear" else "critical",
                "title": title,
                "message": msg,
                **{k: v for k, v in data.items() if k in ("zone_id", "emergency_event_id")},
            })
        except Exception as e:
            logger.error(f"Error broadcasting emergency update via SSE: {str(e)}")

    async def get_emergency_audit_trail(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[int] = None,
        limit: int = 100,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get comprehensive emergency audit trail"""
        
        if db is None:
            db = next(get_db())
        
        try:
            query = db.query(EmergencyEvent)
            
            if start_time:
                query = query.filter(EmergencyEvent.start_time >= start_time)
            
            if end_time:
                query = query.filter(EmergencyEvent.start_time <= end_time)
            
            if event_type is not None:
                query = query.filter(EmergencyEvent.event_type == event_type)
            
            events = query.order_by(EmergencyEvent.start_time.desc()).limit(limit).all()
            
            audit_trail = []
            for event in events:
                # Get related operation logs
                logs = db.query(BaseOperationLog).filter(
                    BaseOperationLog.table_name == "emergency_event",
                    BaseOperationLog.record_id == event.id
                ).all()
                
                audit_trail.append({
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "event_type_name": self.emergency_type_names.get(event.event_type, "UNKNOWN"),
                    "status": event.status,
                    "status_name": self.emergency_status_names.get(event.status, "UNKNOWN"),
                    "start_time": event.start_time.isoformat(),
                    "end_time": event.end_time.isoformat() if event.end_time else None,
                    "initiated_by": event.initiated_by,
                    "initiated_type": event.initiated_type,
                    "trigger_source": event.trigger_source,
                    "reason": event.reason,
                    "scope": event.scope,
                    "zone_ids": event.zone_ids or [],
                    "door_ids": event.door_ids or [],
                    "actions": event.actions or [],
                    "operation_logs": [
                        {
                            "user_id": log.user_id,
                            "action": log.action,
                            "new_values": log.new_values,
                            "created_at": log.created_at.isoformat()
                        }
                        for log in logs
                    ]
                })
            
            return audit_trail
            
        except Exception as e:
            logger.error(f"Error getting emergency audit trail: {str(e)}")
            raise

    # Transport Logistics Methods
    
    async def get_transport_dashboard(self, db: Session) -> Dict[str, Any]:
        """Get comprehensive transport dashboard"""
        
        try:
            # Get transport statistics
            total_transports = db.query(Transport).count()
            active_transports = db.query(Transport).filter(
                Transport.status.in_([TransportStatus.SCHEDULED.value, TransportStatus.BOARDING.value, TransportStatus.IN_TRANSIT.value])
            ).count()
            
            # Count by type
            helicopter_count = db.query(Transport).filter(Transport.type == TransportType.HELICOPTER.value).count()
            vessel_count = db.query(Transport).filter(Transport.type == TransportType.VESSEL.value).count()
            vehicle_count = db.query(Transport).filter(Transport.type == TransportType.VEHICLE.value).count()
            
            # Maintenance due
            maintenance_due = db.query(Transport).filter(
                or_(
                    Transport.is_maintenance_mode == True,
                    Transport.is_inspection_due == True
                )
            ).count()
            
            # Calculate utilization
            transports = db.query(Transport).all()
            total_utilization = sum(t.utilization_rate or 0 for t in transports)
            avg_utilization = total_utilization / len(transports) if transports else 0
            
            # Calculate costs
            total_cost_per_hour = sum(t.cost_per_hour or 0 for t in transports)
            avg_cost_per_hour = total_cost_per_hour / len(transports) if transports else 0
            
            return {
                "total_transports": total_transports,
                "active_transports": active_transports,
                "helicopter_transports": helicopter_count,
                "vessel_transports": vessel_count,
                "vehicle_transports": vehicle_count,
                "maintenance_due": maintenance_due,
                "average_utilization": round(avg_utilization, 2),
                "total_cost_per_hour": total_cost_per_hour,
                "average_cost_per_hour": round(avg_cost_per_hour, 2),
                "transport_types": {
                    "helicopter": {
                        "total": helicopter_count,
                        "active": db.query(Transport).filter(
                            Transport.type == TransportType.HELICOPTER.value,
                            Transport.status.in_([TransportStatus.SCHEDULED.value, TransportStatus.BOARDING.value, TransportStatus.IN_TRANSIT.value])
                        ).count()
                    },
                    "vessel": {
                        "total": vessel_count,
                        "active": db.query(Transport).filter(
                            Transport.type == TransportType.VESSEL.value,
                            Transport.status.in_([TransportStatus.SCHEDULED.value, TransportStatus.BOARDING.value, TransportStatus.IN_TRANSIT.value])
                        ).count()
                    },
                    "vehicle": {
                        "total": vehicle_count,
                        "active": db.query(Transport).filter(
                            Transport.type == TransportType.VEHICLE.value,
                            Transport.status.in_([TransportStatus.SCHEDULED.value, TransportStatus.BOARDING.value, TransportStatus.IN_TRANSIT.value])
                        ).count()
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting transport dashboard: {str(e)}")
            raise

    async def get_transport_fleet(
        self,
        transport_type: Optional[str] = None,
        include_inactive: bool = False,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get transport fleet information"""
        
        if db is None:
            db = next(get_db())
        
        try:
            query = db.query(Transport)
            
            if transport_type:
                type_map = {"helicopter": 0, "vessel": 1, "vehicle": 2}
                if transport_type.lower() in type_map:
                    query = query.filter(Transport.type == type_map[transport_type.lower()])
            
            if not include_inactive:
                query = query.filter(Transport.is_available == True)
            
            transports = query.all()
            
            fleet_data = []
            for transport in transports:
                fleet_data.append({
                    "id": transport.id,
                    "type": transport.type,
                    "type_name": ["HELICOPTER", "VESSEL", "VEHICLE"][transport.type],
                    "identifier": transport.identifier,
                    "registration_number": transport.registration_number,
                    "operator": transport.operator,
                    "status": transport.status,
                    "status_name": ["SCHEDULED", "BOARDING", "IN_TRANSIT", "ARRIVED", "CANCELLED"][transport.status],
                    "capacity": transport.capacity,
                    "current_pob": transport.current_pob,
                    "base_location": transport.base_location,
                    "current_location": transport.current_location,
                    "fuel_capacity": transport.fuel_capacity,
                    "current_fuel": transport.current_fuel,
                    "flight_hours": transport.flight_hours,
                    "max_altitude": transport.max_altitude,
                    "max_speed": transport.max_speed,
                    "cost_per_hour": transport.cost_per_hour,
                    "utilization_rate": transport.utilization_rate,
                    "performance_rating": transport.performance_rating,
                    "is_available": transport.is_available,
                    "is_maintenance_mode": transport.is_maintenance_mode,
                    "is_inspection_due": transport.is_inspection_due
                })
            
            return fleet_data
            
        except Exception as e:
            logger.error(f"Error getting transport fleet: {str(e)}")
            raise

# Create singleton instance
emergency_service = EmergencyService()
