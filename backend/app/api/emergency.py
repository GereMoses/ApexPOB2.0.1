"""
Emergency Management API - POB v2.0
Complete REST API for emergency operations, lockdown, fire mode, notifications
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect, BackgroundTasks, Header, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import json
import asyncio
import logging
import csv
from io import StringIO

from app.core.database import get_db
from app.models.emergency import (
    EmergencyEvent, EmergencyTemplate, EmergencyNotification,
    EmergencyPlan, EmergencyPanicLog, Transport, TransportMaintenance,
    FlightLog, TransportCrew, TransportSchedule, TransportInventory,
    EmergencyEventType, EmergencyStatus, EmergencyScope, EmergencyInitiatedType,
    NotificationChannel, NotificationStatus, RecipientType, PanicType
)
from app.models.biotime_models import EmergencyDevice
from app.models.biotime_models import (
    IClockTerminal, AccDoor, MusteringEvent,
    AuthUser, PersonnelEmployee, BaseOperationLog
)
from app.models.zone import Zone
from app.core.dependencies import get_current_user
from app.models.user import User as AuthUser
try:
    from app.api.biotime_auth import log_operation
except Exception:
    async def log_operation(*args, **kwargs): pass
from app.services.emergency_service import emergency_service
from app.services.emergency_websocket import emergency_websocket_manager

# Router
router = APIRouter(prefix="/api/emergency", tags=["emergency"])

# Configure logging
logger = logging.getLogger(__name__)

# Use the shared singleton so that emergency_service.broadcast_emergency_update()
# and the WS endpoint both write to the same connection list.
emergency_manager = emergency_websocket_manager

# Pydantic Models
class LockdownRequest(BaseModel):
    scope: str = Field(..., description="global, zone, location, or door")
    zone_ids: Optional[List[int]] = Field(None, description="Zone IDs for zone scope")
    location_ids: Optional[List[int]] = Field(None, description="Area/location IDs for location scope")
    door_ids: Optional[List[int]] = Field(None, description="Door IDs for door scope")
    action: str = Field(..., description="lock or unlock")
    reason: Optional[str] = Field(None, description="Reason for lockdown")

class FireModeRequest(BaseModel):
    zone_id: Optional[int] = Field(None, description="Zone ID (optional for global)")
    location_id: Optional[int] = Field(None, description="Area/location ID (optional for location scope)")
    muster_zone_ids: Optional[List[int]] = Field(None, description="Target assembly points (MUSTER_POINT zones); evacuees go to the nearest. Empty = any muster point.")
    action: str = Field(..., description="activate or clear")
    reason: Optional[str] = Field(None, description="Reason for fire mode")

class EmergencyNotificationRequest(BaseModel):
    template_id: Optional[int] = Field(None, description="Template ID")
    event_type: Optional[int] = Field(None, description="Event type")
    channels: Dict[str, bool] = Field(..., description="Channel settings")
    recipients: Dict[str, Any] = Field(..., description="Recipient settings")
    message: Optional[str] = Field(None, description="Custom message")

class EmergencyTemplateCreate(BaseModel):
    template_name: str = Field(..., description="Template name")
    event_type: int = Field(..., description="Event type")
    description: Optional[str] = Field(None, description="Template description")
    actions: List[Dict[str, Any]] = Field(..., description="Actions list")
    notify_channels: Dict[str, Any] = Field(..., description="Notification channels")
    auto_mustering: bool = Field(True, description="Auto mustering")
    auto_mustering_zone_id: Optional[int] = Field(None, description="Auto mustering zone")

class EmergencyPlanCreate(BaseModel):
    plan_name: str = Field(..., description="Plan name")
    event_type: Optional[int] = Field(None, description="Event type")
    zone_id: Optional[int] = Field(None, description="Zone ID")
    steps: str = Field(..., description="Plan steps (markdown)")
    contacts: List[Dict[str, str]] = Field(..., description="Emergency contacts")

class PanicButtonRequest(BaseModel):
    location: str = Field(..., description="Panic location")
    reason: Optional[str] = Field(None, description="Panic reason")

class TransportCreate(BaseModel):
    type: int = Field(..., description="Transport type")
    identifier: str = Field(..., description="Transport identifier")
    registration_number: Optional[str] = Field(None, description="Registration number")
    operator: Optional[str] = Field(None, description="Operator")
    capacity: int = Field(12, description="Capacity")
    base_location: Optional[str] = Field(None, description="Base location")
    cost_per_hour: Optional[float] = Field(None, description="Cost per hour")

# Dashboard Endpoints

@router.get("/status/")
async def get_emergency_status(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get emergency system status and dashboard data
    """
    try:
        dashboard_data = await emergency_service.get_emergency_dashboard(db)
        return {
            "success": True,
            "data": dashboard_data
        }
    except Exception as e:
        logger.error(f"Error getting emergency status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Lockdown Endpoints

@router.get("/doors/state")
async def door_states(current_user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every door's current state (as last commanded) and its controller's health."""
    return {"success": True, "data": emergency_service.door_states(db)}


@router.post("/lockdown")
async def emergency_lockdown(
    request: LockdownRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute emergency lockdown
    """
    try:
        # Validate reason is provided
        if not request.reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reason is required for emergency operations"
            )
        
        result = await emergency_service.execute_lockdown(
            scope=request.scope,
            zone_ids=request.zone_ids,
            location_ids=request.location_ids,
            door_ids=request.door_ids,
            action=request.action,
            reason=request.reason,
            initiated_by=current_user.id,
            db=db
        )
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing lockdown: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Fire Mode Endpoints

@router.post("/fire-mode")
async def fire_mode_control(
    raw_request: Request,
    request: FireModeRequest,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Activate or clear fire mode — requires emergency.manage permission (enforced by RBAC middleware).
    Defense-in-depth: explicit check here in case middleware is bypassed (tests, internal calls).
    """
    try:
        user_perms = getattr(raw_request.state, 'user_permissions', set())
        if (
            not current_user.is_superuser
            and "*" not in user_perms
            and "emergency.manage" not in user_perms
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for fire mode activation"
            )
        result = await emergency_service.activate_fire_mode(
            zone_id=request.zone_id,
            location_id=request.location_id,
            muster_zone_ids=request.muster_zone_ids,
            action=request.action,
            reason=request.reason,
            initiated_by=current_user.id,
            db=db
        )
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error controlling fire mode: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Mass Notification Endpoints

@router.get("/templates/")
async def list_emergency_templates(
    event_type: Optional[int] = Query(None, description="Filter by event type"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List emergency notification templates
    """
    try:
        query = db.query(EmergencyTemplate).filter(EmergencyTemplate.is_active == True)
        
        if event_type is not None:
            query = query.filter(EmergencyTemplate.event_type == event_type)
        
        templates = query.all()
        
        return {
            "success": True,
            "data": [
                {
                    "id": t.id,
                    "template_name": t.template_name,
                    "event_type": t.event_type,
                    "description": t.description,
                    "actions": t.actions,
                    "notify_channels": t.notify_channels,
                    "auto_mustering": t.auto_mustering,
                    "auto_mustering_zone_id": t.auto_mustering_zone_id,
                    "is_default": t.is_default
                }
                for t in templates
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing emergency templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/templates")
async def create_emergency_template(
    template_data: EmergencyTemplateCreate,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create emergency notification template
    """
    try:
        new_template = EmergencyTemplate(
            template_name=template_data.template_name,
            event_type=template_data.event_type,
            description=template_data.description,
            actions=template_data.actions,
            notify_channels=template_data.notify_channels,
            auto_mustering=template_data.auto_mustering,
            auto_mustering_zone_id=template_data.auto_mustering_zone_id
        )
        
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        
        # Log operation
        log_operation(
            db=db,
            user_id=current_user.id,
            action="CREATE_EMERGENCY_TEMPLATE",
            table_name="emergency_template",
            record_id=new_template.id,
            new_values=json.dumps(template_data.dict())
        )
        
        return {
            "success": True,
            "data": {
                "id": new_template.id,
                "template_name": new_template.template_name,
                "event_type": new_template.event_type,
                "message": "Emergency template created successfully"
            }
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating emergency template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/notify")
async def send_emergency_notification(
    request: EmergencyNotificationRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send emergency notification
    """
    try:
        # Derive scope + target zones from the UI's recipient picker instead of
        # always blasting everyone. "all" → global; "zones" → the selected access-
        # control zones (people are matched by Personnel.current_zone_id).
        recipients = request.recipients or {}
        rtype = (recipients.get("type") or "all").lower()
        target_zone_ids = None
        if rtype == "zones" and recipients.get("zones"):
            scope_val = EmergencyScope.ZONE.value
            target_zone_ids = [int(z) for z in recipients["zones"]]
        else:
            # all / departments / users → global for now (dept/user targeting TBD)
            scope_val = EmergencyScope.GLOBAL.value

        # Create emergency event for notification
        emergency_event = EmergencyEvent(
            event_type=request.event_type or EmergencyEventType.LOCKDOWN.value,
            status=EmergencyStatus.ACTIVE.value,
            scope=scope_val,
            zone_ids=target_zone_ids,
            initiated_by=current_user.id,
            initiated_type=EmergencyInitiatedType.MANUAL_UI.value,
            trigger_source="Web UI - Notification",
            reason=request.message or "Emergency notification",
            actions=[{
                "type": "notification",
                "channels": request.channels,
                "recipients": request.recipients,
                "timestamp": datetime.now().isoformat()
            }]
        )

        db.add(emergency_event)
        db.flush()
        
        # Send notifications
        channels = []
        for channel_name, enabled in request.channels.items():
            if enabled:
                channel_map = {"sms": 0, "email": 1, "whatsapp": 2, "push": 3, "pa": 4, "siren": 5, "telegram": 6}
                if channel_name.lower() in channel_map:
                    channels.append(channel_map[channel_name.lower()])

        sent_count = await emergency_service.send_emergency_notifications(
            emergency_event.id, channels, db
        )

        db.commit()

        # Tell the operator WHY nothing went out (unconfigured gateway) rather than
        # silently reporting "sent to 0 recipients".
        cfg = _notification_channel_config()
        requested = {c for c, on in request.channels.items() if on}
        unconfigured = sorted(
            c for c in requested if c in cfg and not cfg[c]
        )
        message = (f"Alert is going out to {sent_count} people on board and the response team — "
                   f"see the delivery log for each message")
        if unconfigured:
            message += (f". Not set up: {', '.join(unconfigured)} "
                        f"(Settings → {'Email' if unconfigured == ['email'] else 'WhatsApp & Alerts'}).")

        return {
            "success": True,
            "data": {
                "emergency_event_id": emergency_event.id,
                "notifications_sent": sent_count,
                "channel_config": cfg,
                "unconfigured_channels": unconfigured,
                "message": message,
            }
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error sending emergency notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def _notification_channel_config() -> Dict[str, bool]:
    """Which delivery channels have a configured gateway on the server right now."""
    from app.services.notify_email import smtp_configured
    from app.services.notify_sms import sms_configured
    from app.services.notify_whatsapp import whatsapp_configured
    from app.services.notify_telegram import telegram_configured
    return {
        "email": smtp_configured(),
        "sms": sms_configured(),
        "whatsapp": whatsapp_configured(),
        "telegram": telegram_configured(),
    }


class NotificationTestRequest(BaseModel):
    channel: str = Field(..., description="email, sms, or whatsapp")
    address: str = Field(..., description="Destination email address or phone number")


@router.get("/notify/config")
async def get_notification_config(
    current_user: AuthUser = Depends(get_current_user),
):
    """Report which notification channels are configured, so the UI can show
    'not configured' badges instead of failing silently."""
    return {"success": True, "data": _notification_channel_config()}


@router.post("/notify/test")
async def send_notification_test(
    request: NotificationTestRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """Send a single test message on one channel to one address so an operator can
    verify each gateway end-to-end. Returns the raw sender result (sent/failed/error)."""
    channel = (request.channel or "").lower()
    address = (request.address or "").strip()
    if not address:
        raise HTTPException(status_code=400, detail="A destination address is required")

    body = "POB test alert — if you received this, this channel is working."
    subject = "POB notification test"

    try:
        if channel == "email":
            from app.services.notify_email import send_email
            result = await asyncio.to_thread(
                send_email, address, subject, f"<p>{body}</p>", body
            )
        elif channel == "sms":
            from app.services.notify_sms import send_sms
            result = await asyncio.to_thread(send_sms, address, body)
        elif channel == "whatsapp":
            from app.services.notify_whatsapp import send_whatsapp
            result = await asyncio.to_thread(send_whatsapp, address, body)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown channel '{request.channel}'")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notification test error ({channel} → {address}): {e}")
        raise HTTPException(status_code=500, detail=str(e))

    ok = bool(result.get("sent"))
    return {
        "success": ok,
        "data": {
            "channel": channel,
            "address": address,
            "sent": result.get("sent", 0),
            "failed": result.get("failed", []),
            "error": result.get("error"),
        },
    }

@router.get("/notifications/")
async def list_emergency_notifications(
    event_id: Optional[int] = Query(None, description="Filter by emergency event ID"),
    status: Optional[str] = Query(None, description="SENT | FAILED | SKIPPED"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Every alert delivery (emergency, muster, all-clear, escalation, panic, test) —
    one row per recipient × channel, newest first."""
    from sqlalchemy import text as _t
    where, params = ["TRUE"], {}
    if event_id is not None:
        where.append("source_type = 'emergency' AND source_id = :eid"); params["eid"] = event_id
    if status:
        where.append("status = :st"); params["st"] = str(status).upper()
    rows = db.execute(_t(f"""
        SELECT id, source_type, source_id, channel, recipient_name, address, status, error, subject, message,
               created_at AT TIME ZONE 'Africa/Lagos' AS created_at
        FROM notify_delivery WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT 500
    """), params).mappings().all()
    return {"success": True, "data": [{
        "id": r["id"], "source_type": r["source_type"], "source_id": r["source_id"],
        "emergency_event_id": r["source_id"] if r["source_type"] == "emergency" else None,
        "channel_name": "NOT ALERTED" if r["channel"] == "none" else r["channel"].upper(), "recipient_name": r["recipient_name"],
        "recipient_addr": r["address"], "message": r["message"], "subject": r["subject"],
        "status_name": r["status"], "error_msg": r["error"],
        "sent_time": r["created_at"].isoformat(sep=" ", timespec="seconds") if r["status"] == "SENT" else None,
        "created_at": r["created_at"].isoformat(sep=" ", timespec="seconds"),
    } for r in rows]}


# Siren/Strobe Control Endpoints

@router.get("/devices/")
async def list_emergency_devices(
    device_type: Optional[int] = Query(None, description="Filter by device type"),
    zone_id: Optional[int] = Query(None, description="Filter by zone ID"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List emergency devices (sirens, strobes, etc.)
    """
    try:
        query = db.query(EmergencyDevice)
        
        if device_type is not None:
            query = query.filter(EmergencyDevice.device_type == device_type)
        
        if zone_id is not None:
            query = query.filter(EmergencyDevice.zone_id == zone_id)
        
        devices = query.all()
        
        return {
            "success": True,
            "data": [
                {
                    "id": d.id,
                    "terminal_sn": d.terminal_sn,
                    "device_type": d.device_type,
                    "device_type_name": ["", "SIREN", "STROBE", "LOCK", "SPEAKER", "PANIC_BUTTON"][d.device_type],
                    "zone_id": d.zone_id,
                    "status": d.status,
                    "status_name": ["OFF", "ON", "FAULT"][d.status],
                    "last_heartbeat": d.last_heartbeat.isoformat() if d.last_heartbeat else None,
                    "test_schedule": d.test_schedule,
                    "location_description": d.location_description
                }
                for d in devices
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing emergency devices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/devices/{device_id}/toggle")
async def toggle_emergency_device(
    device_id: int,
    status: int = Query(..., description="Device status (0=OFF, 1=ON)"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle emergency device status
    """
    try:
        device = db.query(EmergencyDevice).filter(EmergencyDevice.id == device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Emergency device not found"
            )
        
        # Update device status
        old_status = device.status
        device.status = status
        device.last_heartbeat = datetime.now()
        
        # Queue command to device
        if device.terminal:
            command = "EMERGENCY_ON" if status == 1 else "EMERGENCY_OFF"
            result = await emergency_service.zkteco_queue_command(device.terminal_sn, command)
            
            if not result.get("success"):
                device.status = old_status  # Revert on failure
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to send command to device: {result.get('error')}"
                )
        
        db.commit()
        
        # Log operation
        log_operation(
            db=db,
            user_id=current_user.id,
            action="TOGGLE_EMERGENCY_DEVICE",
            table_name="emergency_device",
            record_id=device_id,
            old_values=f"status: {old_status}",
            new_values=f"status: {status}"
        )
        
        return {
            "success": True,
            "data": {
                "device_id": device_id,
                "old_status": old_status,
                "new_status": status,
                "command_sent": command,
                "message": f"Device {'activated' if status == 1 else 'deactivated'} successfully"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error toggling emergency device: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/devices/test-all")
async def test_all_emergency_devices(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test all emergency devices
    """
    try:
        devices = db.query(EmergencyDevice).filter(
            EmergencyDevice.device_type.in_([1, 2]),  # Siren, Strobe
            EmergencyDevice.status != 2  # Not fault
        ).all()
        
        test_results = []
        
        for device in devices:
            try:
                if device.terminal:
                    # Send test command
                    result = await emergency_service.zkteco_queue_command(
                        device.terminal_sn, "EMERGENCY_TEST"
                    )
                    
                    test_results.append({
                        "device_id": device.id,
                        "terminal_sn": device.terminal_sn,
                        "success": result.get("success", False),
                        "error": result.get("error") if not result.get("success") else None
                    })
            
            except Exception as e:
                test_results.append({
                    "device_id": device.id,
                    "terminal_sn": device.terminal_sn,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "data": {
                "total_devices": len(devices),
                "successful_tests": len([r for r in test_results if r["success"]]),
                "failed_tests": len([r for r in test_results if not r["success"]]),
                "results": test_results
            }
        }
        
    except Exception as e:
        logger.error(f"Error testing emergency devices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Trigger Endpoints

@router.post("/panic")
async def panic_button_trigger(
    request: PanicButtonRequest,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Soft panic button trigger from UI
    """
    try:
        # Create panic log
        panic_log = EmergencyPanicLog(
            terminal_sn=None,  # Soft panic
            panic_type=PanicType.SOFT_UI.value,
            emp_code=current_user.username,
            location=request.location,
            reason=request.reason
        )
        
        db.add(panic_log)
        db.flush()
        
        # Create emergency event
        emergency_event = EmergencyEvent(
            event_type=EmergencyEventType.INTRUDER.value,
            status=EmergencyStatus.ACTIVE.value,
            scope=EmergencyScope.ZONE.value,
            initiated_by=current_user.id,
            initiated_type=EmergencyInitiatedType.PANIC_BUTTON.value,
            trigger_source=f"Soft Panic Button - {request.location}",
            reason=request.reason or "Panic button activated",
            actions=[{
                "type": "panic_trigger",
                "panic_log_id": panic_log.id,
                "location": request.location,
                "timestamp": datetime.now().isoformat()
            }]
        )
        
        db.add(emergency_event)
        db.flush()
        
        # Link panic log to emergency event
        panic_log.emergency_event_id = emergency_event.id
        
        # Get panic template and trigger actions
        panic_template = db.query(EmergencyTemplate).filter(
            EmergencyTemplate.event_type == EmergencyEventType.INTRUDER.value,
            EmergencyTemplate.is_active == True
        ).first()
        
        if panic_template:
            # Execute template actions
            for action in panic_template.actions:
                if action.get("type") == "lockdown":
                    # Execute lockdown
                    await emergency_service.execute_lockdown(
                        scope="global",
                        action="lock",
                        reason=f"Panic button activated at {request.location}",
                        initiated_by=current_user.id,
                        db=db
                    )
        
        db.commit()

        # A panic with nobody told is useless: alert the response team immediately.
        from app.services.notify_dispatch import dispatch_background
        who = getattr(current_user, "first_name", None) or current_user.username
        dispatch_background(
            "panic", emergency_event.id, [],
            f"PANIC ALARM — {request.location or 'location not given'}",
            f"PANIC ALARM raised by {who} at {request.location or 'unknown location'}"
            f"{': ' + request.reason if request.reason else ''}. Respond now and confirm in ApexPOB.",
            include_responders=True)

        return {
            "success": True,
            "data": {
                "emergency_event_id": emergency_event.id,
                "panic_log_id": panic_log.id,
                "message": "Panic button activated successfully"
            }
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing panic button: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/trigger")
async def emergency_trigger_webhook(
    trigger_type: str = Query(..., description="Trigger type: panic, fire, etc."),
    source: str = Query(..., description="Trigger source"),
    template_id: Optional[int] = Query(None, description="Template ID to execute"),
    location: Optional[str] = Query(None, description="Trigger location"),
    api_key: Optional[str] = Header(None, description="API key for authentication"),
    db: Session = Depends(get_db)
):
    """
    Public webhook for emergency triggers (fire panel, external systems)
    """
    from ..core.config import settings
    webhook_key = getattr(settings, "EMERGENCY_WEBHOOK_KEY", None)
    try:
        # Reject if no key is configured in production — misconfiguration must be explicit
        if not webhook_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Emergency webhook not configured — set EMERGENCY_WEBHOOK_KEY",
            )
        if not api_key or api_key != webhook_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        
        # Map trigger type to event type
        trigger_map = {
            "panic": EmergencyEventType.INTRUDER.value,
            "fire": EmergencyEventType.FIRE.value,
            "gas": EmergencyEventType.GAS.value,
            "medical": EmergencyEventType.MEDICAL.value
        }
        
        event_type = trigger_map.get(trigger_type.lower())
        if event_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trigger type"
            )
        
        # Create emergency event
        emergency_event = EmergencyEvent(
            event_type=event_type,
            status=EmergencyStatus.ACTIVE.value,
            scope=EmergencyScope.GLOBAL.value,
            initiated_type=EmergencyInitiatedType.API.value,
            trigger_source=f"API: {source}",
            reason=f"Emergency trigger via {source}",
            actions=[{
                "type": "external_trigger",
                "trigger_type": trigger_type,
                "source": source,
                "location": location,
                "timestamp": datetime.now().isoformat()
            }]
        )
        
        db.add(emergency_event)
        db.flush()
        
        db.commit()

        # Respond — before this, a fire-panel alarm only wrote a row and did nothing.
        #   fire / gas → fire mode: unlock fire exits, sirens, site-wide muster, alerts
        #   panic / medical → alert the response team (and everyone on board for panic)
        response: Dict[str, Any] = {}
        try:
            if trigger_type.lower() in ("fire", "gas"):
                emergency_event.status = EmergencyStatus.RESOLVED.value  # fire mode raises its own event
                db.commit()
                response = await emergency_service.activate_fire_mode(
                    zone_id=None, location_id=None, muster_zone_ids=None, action="activate",
                    reason=f"{trigger_type.upper()} alarm from {source}" + (f" at {location}" if location else ""),
                    initiated_by=None, db=db)
            else:
                from app.services.notify_dispatch import dispatch_background
                what = "PANIC ALARM" if trigger_type.lower() == "panic" else "MEDICAL EMERGENCY"
                dispatch_background("emergency", emergency_event.id, [], f"{what} — {location or source}",
                                    f"{what} from {source}" + (f" at {location}" if location else "")
                                    + ". Respond now and confirm in ApexPOB.", include_responders=True)
                response = {"alerted": "response team"}
        except Exception as resp_err:
            logger.error(f"External trigger response failed: {resp_err}")
            response = {"error": str(resp_err)}
        
        return {
            "success": True,
            "data": {
                "emergency_event_id": emergency_event.id,
                "trigger_type": trigger_type,
                "source": source,
                "response": response,
                "message": "Emergency trigger processed successfully"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing emergency trigger: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Emergency Plan Endpoints

@router.get("/plans/")
async def list_emergency_plans(
    event_type: Optional[int] = Query(None, description="Filter by event type"),
    zone_id: Optional[int] = Query(None, description="Filter by zone ID"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List emergency response plans
    """
    try:
        query = db.query(EmergencyPlan).filter(EmergencyPlan.is_active == True)
        
        if event_type is not None:
            query = query.filter(EmergencyPlan.event_type == event_type)
        
        if zone_id is not None:
            query = query.filter(EmergencyPlan.zone_id == zone_id)
        
        plans = query.all()
        
        return {
            "success": True,
            "data": [
                {
                    "id": p.id,
                    "plan_name": p.plan_name,
                    "event_type": p.event_type,
                    "zone_id": p.zone_id,
                    "steps": p.steps,
                    "contacts": p.contacts,
                    "last_reviewed": p.last_reviewed.isoformat() if p.last_reviewed else None,
                    "next_review": p.next_review.isoformat() if p.next_review else None
                }
                for p in plans
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing emergency plans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/plans")
async def create_emergency_plan(
    plan_data: EmergencyPlanCreate,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create emergency response plan
    """
    try:
        new_plan = EmergencyPlan(
            plan_name=plan_data.plan_name,
            event_type=plan_data.event_type,
            zone_id=plan_data.zone_id,
            steps=plan_data.steps,
            contacts=plan_data.contacts,
            last_reviewed=date.today(),
            next_review=date.today() + timedelta(days=365)
        )
        
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)
        
        # Log operation
        log_operation(
            db=db,
            user_id=current_user.id,
            action="CREATE_EMERGENCY_PLAN",
            table_name="emergency_plan",
            record_id=new_plan.id,
            new_values=json.dumps(plan_data.dict())
        )
        
        return {
            "success": True,
            "data": {
                "id": new_plan.id,
                "plan_name": new_plan.plan_name,
                "message": "Emergency plan created successfully"
            }
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating emergency plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Audit Trail Endpoints

@router.get("/audit/")
async def get_emergency_audit_trail(
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    event_type: Optional[int] = Query(None, description="Event type filter"),
    limit: int = Query(100, description="Result limit"),
    export: bool = Query(False, description="Export to CSV"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get emergency audit trail
    """
    try:
        audit_data = await emergency_service.get_emergency_audit_trail(
            start_time=start_time,
            end_time=end_time,
            event_type=event_type,
            limit=limit,
            db=db
        )
        
        if export:
            # Export to CSV
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                "Event ID", "Event Type", "Status", "Start Time", "End Time",
                "Initiated By", "Trigger Source", "Reason", "Scope", "Actions"
            ])
            
            # Data
            for event in audit_data:
                writer.writerow([
                    event["event_id"],
                    event["event_type_name"],
                    event["status_name"],
                    event["start_time"],
                    event["end_time"] or "",
                    event["initiated_by"] or "",
                    event["trigger_source"],
                    event["reason"] or "",
                    event["scope"],
                    json.dumps(event["actions"])
                ])
            
            output.seek(0)
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=emergency_audit.csv"}
            )
        
        return {
            "success": True,
            "data": audit_data
        }
        
    except Exception as e:
        logger.error(f"Error getting emergency audit trail: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Transport Logistics Endpoints

@router.get("/transport/dashboard/")
async def get_transport_dashboard(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transport logistics dashboard
    """
    try:
        dashboard_data = await emergency_service.get_transport_dashboard(db)
        return {
            "success": True,
            "data": dashboard_data
        }
        
    except Exception as e:
        logger.error(f"Error getting transport dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/transport/fleet/")
async def get_transport_fleet(
    transport_type: Optional[str] = Query(None, description="Filter by transport type"),
    include_inactive: bool = Query(False, description="Include inactive transports"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transport fleet information
    """
    try:
        fleet_data = await emergency_service.get_transport_fleet(
            transport_type=transport_type,
            include_inactive=include_inactive,
            db=db
        )
        return {
            "success": True,
            "data": fleet_data
        }
        
    except Exception as e:
        logger.error(f"Error getting transport fleet: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# WebSocket Endpoint

@router.websocket("/ws/emergency/")
async def emergency_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time emergency updates — requires valid JWT via ?token= param.

    We call receive_text() with a 30-second timeout so that client disconnects
    are detected promptly. On timeout we send a keepalive ping to this connection
    only. Broadcasts (lockdown, fire mode, etc.) come through emergency_manager
    and reach all connections independently.
    """
    from datetime import timezone as _tz
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        from ..core.security import verify_token
        verify_token(token, token_type="access")
    except Exception:
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid token")
        return

    await emergency_manager.connect(websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await emergency_manager.send_to_connection(
                    websocket,
                    {"type": "ping", "timestamp": datetime.now(_tz.utc).isoformat()},
                )
    except WebSocketDisconnect:
        pass
    finally:
        emergency_manager.disconnect(websocket)

async def broadcast_emergency_update(update_data: Dict[str, Any]):
    """Broadcast emergency update to all connected clients."""
    await emergency_manager.broadcast(update_data)

# ================================
# ENHANCED EMERGENCY FEATURES
# ================================

@router.get("/dashboard/enhanced")
async def get_enhanced_emergency_dashboard(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enhanced emergency dashboard with analytics"""
    try:
        # Get active emergency events
        active_events = db.query(EmergencyEvent).filter(
            EmergencyEvent.status == EmergencyStatus.ACTIVE.value
        ).all()
        
        # Get device health status
        total_devices = db.query(IClockTerminal).count()
        online_devices = db.query(IClockTerminal).filter(IClockTerminal.state == 1).count()
        
        # Get recent panic logs
        recent_panics = db.query(EmergencyPanicLog).order_by(
            EmergencyPanicLog.panic_time.desc()
        ).limit(5).all()

        return {
            "active_events": len(active_events),
            "events": [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "scope": event.scope,
                    "initiated_at": event.start_time.isoformat() if event.start_time else None,
                    "initiated_by": event.initiated_by,
                    "status": event.status
                }
                for event in active_events
            ],
            "device_health": {
                "total_devices": total_devices,
                "online_devices": online_devices,
                "offline_devices": total_devices - online_devices,
                "health_percentage": (online_devices / total_devices * 100) if total_devices > 0 else 0
            },
            "recent_panics": [
                {
                    "id": panic.id,
                    "panic_type": panic.panic_type,
                    "location": panic.location,
                    "timestamp": panic.panic_time.isoformat() if panic.panic_time else None,
                    "resolved": panic.resolved_time is not None
                }
                for panic in recent_panics
            ],
            "system_status": "operational"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics")
async def get_emergency_metrics(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get emergency response metrics"""
    try:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        total_events = db.query(EmergencyEvent).filter(
            EmergencyEvent.start_time >= thirty_days_ago
        ).count()

        resolved_events = db.query(EmergencyEvent).filter(
            EmergencyEvent.start_time >= thirty_days_ago,
            EmergencyEvent.status == EmergencyStatus.RESOLVED.value
        ).count()

        active_events = db.query(EmergencyEvent).filter(
            EmergencyEvent.status == EmergencyStatus.ACTIVE.value
        ).count()

        # Average resolution time in minutes (events that have end_time set)
        avg_row = db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (end_time - start_time))/60)
                FROM emergency_event
                WHERE start_time >= :cutoff AND end_time IS NOT NULL
            """),
            {"cutoff": thirty_days_ago}
        ).scalar()
        avg_resolution_time = round(float(avg_row), 2) if avg_row else 0

        return {
            "period": "Last 30 days",
            "total_events": total_events,
            "resolved_events": resolved_events,
            "resolution_rate": round((resolved_events / total_events * 100), 1) if total_events > 0 else 0,
            "average_resolution_time": avg_resolution_time,
            "active_events": active_events,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
