"""
Mustering API - Complete Mustering System for POB v2.0
Real-time headcount tracking, drill management, compliance reports
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timezone, timedelta
import json
import asyncio
import logging

from app.core.database import get_db
from app.services.mustering_service import MusteringService
from app.services.mustering_websocket_enhanced import enhanced_manager, disconnect_from_event, broadcast_to_event
from app.core.dependencies import get_current_user
from app.models.user import User as AuthUser
try:
    from app.api.biotime_auth import log_operation
except Exception:
    async def log_operation(*args, **kwargs): pass

# Router
router = APIRouter()

# Configure logging
logger = logging.getLogger(__name__)

# Enhanced WebSocket connection manager
class MusteringConnectionManager:
    def __init__(self):
        pass  # Use enhanced manager

    async def connect(self, websocket: WebSocket, event_id: int):
        connection_id = f"conn_{datetime.utcnow().timestamp()}_{id(websocket)}"
        return await enhanced_manager.connect_to_event(websocket, event_id, connection_id)

    async def disconnect(self, websocket: WebSocket, event_id: int):
        await enhanced_manager.disconnect_from_event(websocket, event_id)

    async def broadcast_to_event(self, event_id: int, message: str):
        await enhanced_manager.broadcast_to_event(event_id, message)

manager = MusteringConnectionManager()

# Pydantic Models
class MusteringEventStart(BaseModel):
    zone_ids: List[int] = Field(..., min_items=1, description="Affected/source zone IDs (who is expected)")
    muster_zone_ids: Optional[List[int]] = Field(None, description="Target assembly points (MUSTER_POINT zones); personnel go to the nearest. Empty = any muster point.")
    event_type: int = Field(..., description="Event type: 0=Real, 1=Drill, 2=Fire, 3=Gas, 4=ManDown")
    notify_sms: bool = Field(default=False, description="Send SMS notifications")
    notify_email: bool = Field(default=False, description="Send email notifications")
    notify_whatsapp: bool = Field(default=False, description="Send WhatsApp notifications")
    notify_siren: bool = Field(default=False, description="Trigger sirens")
    notes: Optional[str] = Field(None, description="Event notes")

class MusteringEventEnd(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for ending event")

class MusteringPersonMark(BaseModel):
    emp_code: str = Field(..., description="Employee code")
    status: int = Field(..., ge=0, le=3, description="Status: 0=Missing, 1=Safe, 2=Injured, 3=Left site")

class MusteringZoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Zone name")
    capacity: Optional[int] = Field(None, gt=0, description="Zone capacity")
    evac_point: Optional[str] = Field(None, max_length=100, description="Evacuation point")
    evac_gps: Optional[str] = Field(None, max_length=50, description="GPS coordinates")
    zone_type: int = Field(default=0, description="Zone type: 0=Assembly, 1=Safe Room, 2=Hospital")
    reader_sn: Optional[str] = Field(None, max_length=50, description="Reader serial number")
    description: Optional[str] = Field(None, description="Zone description")
    latitude: Optional[float] = Field(None, description="Latitude for map marker")
    longitude: Optional[float] = Field(None, description="Longitude for map marker")

class MusteringZoneMapUpdate(BaseModel):
    map_x: Optional[float] = Field(None, description="X position on zone map (SVG units)")
    map_y: Optional[float] = Field(None, description="Y position on zone map (SVG units)")
    map_connections: Optional[str] = Field(None, description="JSON array of connected zone IDs")

class DrillScheduleIn(BaseModel):
    zone_id: int = Field(..., description="Zone ID")
    event_type: int = Field(..., description="Event type")
    scheduled_time: datetime = Field(..., description="Scheduled time")
    participant_type: int = Field(default=0, description="Participant type: 0=all, 1=dept, 2=shift")
    participant_id: Optional[int] = Field(None, description="Department or shift ID")
    template_id: Optional[int] = Field(None, description="Template ID")
    auto_start: bool = Field(default=True, description="Auto-start drill")

class MusteringTemplateIn(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=100, description="Template name")
    event_type: Optional[int] = Field(None, description="Event type")
    notify_sms: Optional[bool] = Field(None, description="Send SMS notifications")
    notify_email: Optional[bool] = Field(None, description="Send email notifications")
    notify_users: Optional[str] = Field(None, description="JSON array of user IDs")
    actions: Optional[Dict[str, Any]] = Field(None, description="Template actions")

class SearchSweepCreate(BaseModel):
    emp_code: str = Field(..., description="Employee code of the person being searched for")
    area_searched: str = Field(..., min_length=1, max_length=200, description="Area/location searched")
    result: str = Field(..., description="Search result: NOT_FOUND | FOUND_SAFE | FOUND_INJURED")
    notes: Optional[str] = Field(None, description="Additional notes")

_MUSTER_ZONE_INT_MAP = {0: "MUSTER_POINT", 1: "EMERGENCY", 2: "SAFE_HAVEN"}
_MUSTER_ZONE_STR_MAP = {"MUSTER_POINT": 0, "LOCATION": 0, "EMERGENCY": 1, "SAFE_HAVEN": 2}
_MUSTER_ZONE_TYPES = list(_MUSTER_ZONE_STR_MAP.keys())

def _gen_zone_code(name: str, db: Session) -> str:
    import re as _re
    from sqlalchemy import text as _text
    base = _re.sub(r"[^A-Z0-9]", "", name.upper())[:12] or "MZ"
    existing = {r[0] for r in db.execute(_text("SELECT code FROM zones")).fetchall()}
    code, n = base, 1
    while code in existing:
        code = f"{base}{n}"; n += 1
    return code

# Zone Management

@router.get("/api/mustering/zones/")
async def list_mustering_zones(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all mustering zones (zone_type in MUSTER_POINT, EMERGENCY, SAFE_HAVEN)"""
    try:
        service = MusteringService(db)
        zones = db.query(MusteringZone).filter(
            MusteringZone.is_active == True,
        ).order_by(MusteringZone.name).all()

        # Build safe-count map from active event logs (status=1 means confirmed safe/present)
        active_event_ids = [
            row[0] for row in db.query(MusteringEvent.id).filter(MusteringEvent.status == 0).all()
        ]
        occupancy_map: dict = {}
        if active_event_ids:
            from sqlalchemy import func as sqlfunc
            rows = (
                db.query(MusteringEvent.zone_id, sqlfunc.count(MusteringLog.id))
                .join(MusteringLog, MusteringLog.event_id == MusteringEvent.id)
                .filter(MusteringEvent.id.in_(active_event_ids), MusteringLog.status == 1)
                .group_by(MusteringEvent.zone_id)
                .all()
            )
            occupancy_map = {zone_id: cnt for zone_id, cnt in rows}

        result = []
        for zone in zones:
            result.append({
                "id": zone.id,
                "name": zone.name,
                "capacity": zone.max_capacity,
                "evac_point": zone.evac_point,
                "evac_gps": zone.evac_gps,
                "zone_type": _MUSTER_ZONE_STR_MAP.get(zone.zone_type, 0),
                # Raw zones.zone_type string (e.g. MUSTER_POINT, LOCATION) — the int
                # zone_type above collapses several kinds to 0, so callers that need to
                # tell a muster point from a work zone must use this.
                "zone_kind": zone.zone_type,
                "reader_sn": zone.reader_sn,
                "description": zone.description,
                "map_x": zone.map_x,
                "map_y": zone.map_y,
                "map_connections": zone.map_connections,
                "latitude": zone.latitude,
                "longitude": zone.longitude,
                "current_occupancy": occupancy_map.get(zone.id, 0),
                "adms_occupancy": int(zone.current_occupancy or 0),
                "created_at": zone.created_at,
                "updated_at": zone.updated_at,
            })

        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Error listing mustering zones: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/mustering/zones")
async def create_mustering_zone(
    zone_data: MusteringZoneCreate,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new mustering zone"""
    try:
        if zone_data.capacity and zone_data.capacity <= 0:
            raise HTTPException(status_code=400, detail="Capacity must be greater than 0")

        zone = MusteringZone(
            name=zone_data.name,
            code=_gen_zone_code(zone_data.name, db),
            zone_type=_MUSTER_ZONE_INT_MAP.get(zone_data.zone_type, "MUSTER_POINT"),
            max_capacity=zone_data.capacity,
            evac_point=zone_data.evac_point,
            evac_gps=zone_data.evac_gps,
            reader_sn=zone_data.reader_sn,
            description=zone_data.description,
            latitude=str(zone_data.latitude) if zone_data.latitude is not None else None,
            longitude=str(zone_data.longitude) if zone_data.longitude is not None else None,
            status="ACTIVE",
            is_active=True,
        )
        db.add(zone)
        db.commit()
        db.refresh(zone)

        log_operation(
            db=db,
            user_id=current_user.id,
            action="CREATE_MUSTERING_ZONE",
            table_name="zones",
            record_id=zone.id,
            new_values=str(zone_data.dict()),
        )

        return {"success": True, "data": {"id": zone.id, "message": "Zone created successfully"}}

    except Exception as e:
        logger.error(f"Error creating mustering zone: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/mustering/zones/{zone_id}")
async def update_mustering_zone(
    zone_id: int,
    zone_data: MusteringZoneCreate,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a mustering zone"""
    try:
        zone = db.query(MusteringZone).filter(MusteringZone.id == zone_id).first()
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")

        old_data = {
            "name": zone.name,
            "capacity": zone.max_capacity,
            "evac_point": zone.evac_point,
            "evac_gps": zone.evac_gps,
            "zone_type": zone.zone_type,
            "reader_sn": zone.reader_sn,
            "description": zone.description,
        }
        
        field_map = {"capacity": "max_capacity"}
        for field, value in zone_data.dict(exclude_unset=True).items():
            if field == "zone_type":
                zone.zone_type = _MUSTER_ZONE_INT_MAP.get(value, "MUSTER_POINT")
            elif field in ("latitude", "longitude"):
                setattr(zone, field, str(value) if value is not None else None)
            else:
                setattr(zone, field_map.get(field, field), value)

        db.commit()

        log_operation(
            db=db,
            user_id=current_user.id,
            action="UPDATE_MUSTERING_ZONE",
            table_name="zones",
            record_id=zone_id,
            old_values=str(old_data),
            new_values=str(zone_data.dict(exclude_unset=True)),
        )

        return {"success": True, "data": {"message": "Zone updated successfully"}}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating mustering zone: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/mustering/zones/{zone_id}")
async def delete_mustering_zone(
    zone_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a mustering zone"""
    try:
        zone = db.query(MusteringZone).filter(MusteringZone.id == zone_id).first()
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")
        
        # Check if zone has events
        event_count = db.query(MusteringEvent).filter(MusteringEvent.zone_id == zone_id).count()
        if event_count > 0:
            raise HTTPException(status_code=400, detail="Cannot delete zone with existing events")
        
        db.delete(zone)
        db.commit()
        
        log_operation(
            db=db,
            user_id=current_user.id,
            action="DELETE_MUSTERING_ZONE",
            table_name="zones",
            record_id=zone_id
        )
        
        return {"success": True, "data": {"message": "Zone deleted successfully"}}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting mustering zone: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/api/mustering/zones/{zone_id}/map-position")
async def update_zone_map_position(
    zone_id: int,
    data: MusteringZoneMapUpdate,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update zone map layout position and connections — does not require zone to be unused"""
    try:
        zone = db.query(MusteringZone).filter(MusteringZone.id == zone_id).first()
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")
        for field, value in data.dict(exclude_unset=True).items():
            setattr(zone, field, value)
        db.commit()
        return {"success": True, "data": {"message": "Map position updated"}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating zone map position: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Event Management

@router.get("/api/mustering/events/")
async def list_mustering_events(
    status: Optional[int] = Query(None, description="Filter by status: 0=active, 1=completed, 2=cancelled"),
    zone_id: Optional[int] = Query(None, description="Filter by zone ID"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List mustering events"""
    try:
        service = MusteringService(db)
        
        query = db.query(MusteringEvent)
        
        if status is not None:
            query = query.filter(MusteringEvent.status == status)
        
        if zone_id is not None:
            query = query.filter(MusteringEvent.zone_id == zone_id)
        
        if start_date:
            query = query.filter(MusteringEvent.start_time >= start_date)
        
        if end_date:
            query = query.filter(MusteringEvent.start_time <= end_date)
        
        events = query.order_by(MusteringEvent.start_time.desc()).all()
        
        # Pre-load all zones for name resolution
        from app.models.zone import Zone as ZoneModel
        all_zones = {z.id: z.name for z in db.query(ZoneModel.id, ZoneModel.name).all()}

        result = []
        for event in events:
            headcount = service.get_event_headcount(event.id)
            # Resolve zone names from zone_ids (JSONB list) or fall back to zone_id FK
            ev_zone_ids = event.zone_ids or ([event.zone_id] if event.zone_id else [])
            ev_zone_names = [all_zones.get(zid) for zid in ev_zone_ids if zid in all_zones]
            result.append({
                "id": event.id,
                "zone_id": event.zone_id,
                "zone_ids": ev_zone_ids,
                "zone_name": ", ".join(filter(None, ev_zone_names)) or (event.zone.name if event.zone else None),
                "zone_names": ev_zone_names,
                "muster_zone_id": event.muster_zone_id,
                "muster_zone_name": all_zones.get(event.muster_zone_id) if event.muster_zone_id else None,
                "muster_zone_ids": event.muster_zone_ids or ([event.muster_zone_id] if event.muster_zone_id else []),
                "muster_zone_names": [all_zones.get(z) for z in (event.muster_zone_ids or ([event.muster_zone_id] if event.muster_zone_id else [])) if z in all_zones],
                "event_type": event.event_type,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "status": event.status,
                "initiated_by": event.initiated_by,
                "total_expected": event.total_expected,
                "total_safe": event.total_safe,
                "total_missing": event.total_missing,
                "total_injured": event.total_injured,
                "notes": event.notes,
                "headcount": headcount
            })
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Error listing mustering events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/mustering/events/start")
async def start_mustering_event(
    event_data: MusteringEventStart,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a mustering event"""
    try:
        service = MusteringService(db)
        
        result = service.start_mustering_event(
            zone_ids=event_data.zone_ids,
            muster_zone_ids=event_data.muster_zone_ids,
            event_type=event_data.event_type,
            initiated_by=current_user.id,
            notify_sms=event_data.notify_sms,
            notify_email=event_data.notify_email,
            notify_whatsapp=event_data.notify_whatsapp,
            notify_siren=event_data.notify_siren,
            notes=event_data.notes
        )

        # Muster-reader readiness: a drill can only auto-mark Safe if at least one
        # muster-point reader is ONLINE. A reader counts as a muster point via any of
        # the three ways handle_attlog detects mustering (acc_door.mustering_mode,
        # reader_purpose=MUSTERING, or device_type=2). If none are online, the headcount
        # can't capture punches → silent 0% safe; surface a warning so the operator
        # marks people Safe manually instead of trusting an empty count.
        from sqlalchemy import text as _text
        rr = db.execute(_text("""
            SELECT COUNT(*) FILTER (WHERE t.state = 1) AS online,
                   COUNT(*)                              AS total
            FROM iclock_terminal t
            LEFT JOIN acc_door d ON d.terminal_sn = t.sn
            WHERE d.mustering_mode = true
               OR t.reader_purpose = 'MUSTERING'
               OR t.device_type = 2
        """)).fetchone()
        result["muster_readers_total"]  = rr.total or 0
        result["muster_readers_online"] = rr.online or 0
        if (rr.online or 0) == 0:
            result["warning"] = (
                "No muster-point reader is online. Automatic headcount cannot capture "
                "punches for this drill — mark personnel Safe manually, or bring a "
                "muster reader online first."
            )

        log_operation(
            db=db,
            user_id=current_user.id,
            action="START_MUSTERING_EVENT",
            table_name="mustering_event",
            record_id=result["event_id"],
            new_values=str(event_data.dict())
        )
        
        # Broadcast event start
        await manager.broadcast_to_event(
            result["event_id"],
            json.dumps({
                "type": "event_started",
                "data": result
            })
        )
        
        return {"success": True, "data": result}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting mustering event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/mustering/events/{event_id}/end")
async def end_mustering_event(
    event_id: int,
    end_data: MusteringEventEnd,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """End a mustering event"""
    try:
        service = MusteringService(db)
        
        result = service.end_mustering_event(
            event_id=event_id,
            ended_by=current_user.id,
            reason=end_data.reason
        )
        
        log_operation(
            db=db,
            user_id=current_user.id,
            action="END_MUSTERING_EVENT",
            table_name="mustering_event",
            record_id=event_id,
            new_values=f"reason: {end_data.reason}"
        )
        
        # Broadcast event end
        await manager.broadcast_to_event(
            event_id,
            json.dumps({
                "type": "event_ended",
                "data": result
            })
        )
        
        return {"success": True, "data": result}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error ending mustering event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/events/{event_id}/headcount/")
async def get_event_headcount(
    event_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get real-time headcount for an event"""
    try:
        service = MusteringService(db)
        headcount = service.get_event_headcount(event_id)
        
        return {"success": True, "data": headcount}
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting event headcount: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/events/{event_id}/logs/")
async def get_event_logs(
    event_id: int,
    status: Optional[int] = Query(None, description="Filter by status: 0=missing, 1=safe, 2=injured"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=1000, description="Items per page"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get logs for a mustering event"""
    try:
        service = MusteringService(db)
        logs = service.get_event_logs(event_id, status)
        
        # Pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_logs = logs[start:end]
        
        return {
            "success": True,
            "data": {
                "logs": paginated_logs,
                "total": len(logs),
                "page": page,
                "limit": limit,
                "pages": (len(logs) + limit - 1) // limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting event logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/mustering/events/{event_id}/mark")
async def mark_person_status(
    event_id: int,
    mark_data: MusteringPersonMark,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually mark a person's status"""
    try:
        service = MusteringService(db)
        
        result = service.mark_person_status(
            event_id=event_id,
            emp_code=mark_data.emp_code,
            status=mark_data.status,
            marked_by=current_user.id
        )
        
        log_operation(
            db=db,
            user_id=current_user.id,
            action="MARK_PERSON_STATUS",
            table_name="mustering_log",
            record_id=event_id,
            new_values=f"emp_code: {mark_data.emp_code}, status: {mark_data.status}"
        )
        
        # Broadcast status update
        await manager.broadcast_to_event(
            event_id,
            json.dumps({
                "type": "status_updated",
                "data": result
            })
        )
        
        return {"success": True, "data": result}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking person status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/events/{event_id}/export/")
async def export_mustering_event(
    event_id: int,
    format: str = Query("excel", description="Export format: excel | csv"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a formatted report for a mustering event (Excel or CSV)."""
    from fastapi.responses import Response
    try:
        service = MusteringService(db)
        fmt = format.lower().strip()
        if fmt not in ("excel", "csv"):
            raise HTTPException(status_code=400, detail="format must be 'excel' or 'csv'")
        data, content_type, filename = service.export_event_report(event_id, fmt)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting mustering event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Accountability closure loop endpoints ───────────────────────────────────────

@router.get("/api/mustering/events/{event_id}/missing-persons/")
async def get_missing_persons(
    event_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all currently missing persons for an active event, enriched with:
    - minutes missing (escalation clock)
    - escalation level: 0=new, 1=10-min alert, 2=20-min search ordered, 3=30-min critical
    - last known biometric location
    - search sweep history
    """
    try:
        service = MusteringService(db)
        persons = service.get_missing_with_escalation(event_id)
        return {"success": True, "data": persons}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting missing persons for event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mustering/events/{event_id}/search-sweeps")
async def record_search_sweep(
    event_id: int,
    body: SearchSweepCreate,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Record a manual search sweep for a missing person.
    If result is FOUND_SAFE or FOUND_INJURED, the person is automatically
    marked with the corresponding status in the mustering log.
    """
    try:
        service = MusteringService(db)
        searcher_name = f"{getattr(current_user, 'first_name', '') or ''} {getattr(current_user, 'last_name', '') or ''}".strip() or current_user.username
        result = service.record_search_sweep(
            event_id=event_id,
            emp_code=body.emp_code,
            area_searched=body.area_searched,
            result_status=body.result,
            searcher_id=current_user.id,
            searcher_name=searcher_name,
            notes=body.notes,
        )

        await manager.broadcast_to_event(
            event_id,
            json.dumps({"type": "sweep_recorded", "data": result}),
        )

        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error recording search sweep for event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/mustering/events/{event_id}/search-sweeps/")
async def list_search_sweeps(
    event_id: int,
    emp_code: Optional[str] = Query(None, description="Filter by employee code"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all search sweeps for a mustering event, optionally filtered by employee."""
    try:
        service = MusteringService(db)
        sweeps = service.get_event_sweeps(event_id, emp_code)
        return {"success": True, "data": sweeps}
    except Exception as e:
        logger.error(f"Error listing search sweeps for event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket for real-time updates

@router.websocket("/ws/mustering/events/{event_id}")
async def websocket_endpoint(websocket: WebSocket, event_id: int):
    """WebSocket endpoint for real-time mustering updates — requires valid JWT."""
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

    await websocket.accept()
    await manager.connect(websocket, event_id)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, event_id)

# Drill Planning endpoints

@router.get("/api/mustering/drills/")
async def list_drill_schedules(
    zone_id: Optional[int] = Query(None, description="Filter by zone ID"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List drill schedules"""
    try:
        query = db.query(MusteringDrillSchedule)

        if zone_id is not None:
            query = query.filter(MusteringDrillSchedule.zone_id == zone_id)

        schedules = query.order_by(MusteringDrillSchedule.scheduled_time.desc()).all()
        
        result = []
        for schedule in schedules:
            result.append({
                "id": schedule.id,
                "zone_id": schedule.zone_id,
                "zone_name": schedule.zone.name if schedule.zone else None,
                "event_type": schedule.event_type,
                "scheduled_time": schedule.scheduled_time.isoformat() if schedule.scheduled_time else None,
                "participant_type": schedule.participant_type,
                "participant_id": schedule.participant_id,
                "template_id": schedule.template_id,
                "auto_start": schedule.auto_start,
                "created_by": schedule.created_by,
                "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
                "processed": schedule.processed,
                "processed_time": schedule.processed_time.isoformat() if schedule.processed_time else None,
                "status": schedule.status or ("COMPLETED" if schedule.processed else "PENDING"),
            })

        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Error listing drill schedules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/mustering/drills")
async def create_drill_schedule(
    drill_data: DrillScheduleIn,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new drill schedule"""
    try:
        # Validate scheduled time is not in the past
        if drill_data.scheduled_time.replace(tzinfo=None) < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Scheduled time cannot be in the past")

        # Validate zone exists
        zone = db.query(MusteringZone).filter(MusteringZone.id == drill_data.zone_id).first()
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")

        # Create schedule
        new_schedule = MusteringDrillSchedule(
            zone_id=drill_data.zone_id,
            event_type=drill_data.event_type,
            scheduled_time=drill_data.scheduled_time,
            participant_type=drill_data.participant_type,
            participant_id=drill_data.participant_id,
            template_id=drill_data.template_id,
            auto_start=drill_data.auto_start,
            created_by=current_user.id
        )
        
        db.add(new_schedule)
        db.commit()
        db.refresh(new_schedule)
        
        log_operation(
            db=db,
            user_id=current_user.id,
            action="CREATE_DRILL_SCHEDULE",
            table_name="mustering_drill_schedule",
            record_id=new_schedule.id,
            new_values=str(drill_data.dict())
        )
        
        return {"success": True, "data": {"id": new_schedule.id, "message": "Drill schedule created successfully"}}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating drill schedule: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/mustering/drills/{drill_id}/trigger")
async def trigger_drill_now(
    drill_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger a drill immediately"""
    try:
        schedule = db.query(MusteringDrillSchedule).filter(MusteringDrillSchedule.id == drill_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Drill schedule not found")
        
        # Start the drill immediately
        service = MusteringService(db)
        event_result = service.start_mustering_event(
            zone_ids=[schedule.zone_id],
            event_type=schedule.event_type,
            initiated_by=current_user.id,
            notes=f"Manually triggered drill from schedule {drill_id}"
        )
        
        # Mark schedule as processed
        schedule.processed = True
        schedule.processed_time = datetime.utcnow()
        db.commit()
        
        log_operation(
            db=db,
            user_id=current_user.id,
            action="TRIGGER_DRILL",
            table_name="mustering_drill_schedule",
            record_id=drill_id,
            new_values=f"Event ID: {event_result['event_id']}"
        )
        
        return {"success": True, "data": event_result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering drill: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Template Management endpoints

@router.get("/api/mustering/templates/")
async def list_mustering_templates(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List mustering templates"""
    try:
        templates = db.query(MusteringEventTemplate).order_by(MusteringEventTemplate.template_name).all()
        
        result = []
        for template in templates:
            result.append({
                "id": template.id,
                "template_name": template.template_name,
                "event_type": template.event_type,
                "notify_sms": template.notify_sms,
                "notify_email": template.notify_email,
                "notify_users": template.notify_users,
                "actions": template.actions,
                "created_at": template.created_at,
                "updated_at": template.updated_at
            })
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Error listing mustering templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/mustering/templates")
async def create_mustering_template(
    template_data: MusteringTemplateIn,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new mustering template"""
    try:
        new_template = MusteringEventTemplate(
            template_name=template_data.template_name,
            event_type=template_data.event_type,
            notify_sms=template_data.notify_sms,
            notify_email=template_data.notify_email,
            notify_users=template_data.notify_users,
            actions=str(template_data.actions) if template_data.actions else None,
        )
        
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        
        log_operation(
            db=db,
            user_id=current_user.id,
            action="CREATE_MUSTERING_TEMPLATE",
            table_name="mustering_template",
            record_id=new_template.id,
            new_values=str(template_data.dict())
        )
        
        return {"success": True, "data": {"id": new_template.id, "message": "Template created successfully"}}
        
    except Exception as e:
        logger.error(f"Error creating mustering template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/mustering/templates/{template_id}")
async def update_mustering_template(
    template_id: int,
    template_data: MusteringTemplateIn,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a mustering template"""
    try:
        template = db.query(MusteringEventTemplate).filter(MusteringEventTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        old_data = {
            "template_name": template.template_name,
            "event_type": template.event_type,
            "notify_sms": template.notify_sms,
            "notify_email": template.notify_email,
            "notify_users": template.notify_users,
            "actions": template.actions
        }
        
        for field, value in template_data.dict(exclude_unset=True).items():
            setattr(template, field, value)
        
        db.commit()
        
        log_operation(
            db=db,
            user_id=current_user.id,
            action="UPDATE_MUSTERING_TEMPLATE",
            table_name="mustering_template",
            record_id=template_id,
            old_values=str(old_data),
            new_values=str(template_data.dict(exclude_unset=True))
        )
        
        return {"success": True, "data": {"message": "Template updated successfully"}}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating mustering template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/mustering/templates/{template_id}")
async def delete_mustering_template(
    template_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a mustering template"""
    try:
        template = db.query(MusteringEventTemplate).filter(MusteringEventTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check if template is being used by any schedules
        schedules_using = db.query(MusteringDrillSchedule).filter(
            MusteringDrillSchedule.template_id == template_id
        ).count()
        
        if schedules_using > 0:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete template that is being used by scheduled drills"
            )
        
        db.delete(template)
        db.commit()
        
        log_operation(
            db=db,
            user_id=current_user.id,
            action="DELETE_MUSTERING_TEMPLATE",
            table_name="mustering_template",
            record_id=template_id
        )
        
        return {"success": True, "data": {"message": "Template deleted successfully"}}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting mustering template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Compliance endpoints

@router.get("/api/mustering/reports/compliance/")
async def get_compliance_report(
    start_date: Optional[date] = Query(None, description="Start date for report period"),
    end_date: Optional[date] = Query(None, description="End date for report period"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get compliance report"""
    try:
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow().date()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Get events in date range
        events = db.query(MusteringEvent).filter(
            MusteringEvent.start_time >= start_date,
            MusteringEvent.start_time <= end_date,
            MusteringEvent.status == 1  # Completed
        ).all()
        
        if not events:
            return {
                "success": True,
                "data": {
                    "total_events": 0,
                    "avg_muster_time_minutes": 0,
                    "percent_accounted_10min": 0,
                    "drills_this_month": 0,
                    "compliance_score": 100
                }
            }
        
        # Calculate metrics
        total_events = len(events)
        total_duration = sum(
            (event.end_time - event.start_time).total_seconds() / 60 
            for event in events 
            if event.end_time
        )
        avg_muster_time = total_duration / total_events if total_events > 0 else 0
        
        # Calculate % accounted in < 10 minutes
        events_under_10min = sum(
            1 for event in events 
            if event.end_time and (event.end_time - event.start_time).total_seconds() <= 600
        )
        percent_accounted_10min = (events_under_10min / total_events * 100) if total_events > 0 else 0
        
        # Count drills this month
        current_month_start = datetime.utcnow().replace(day=1).date()
        drills_this_month = db.query(MusteringEvent).filter(
            MusteringEvent.start_time >= current_month_start,
            MusteringEvent.event_type == 1,  # Drill
            MusteringEvent.status == 1
        ).count()
        
        # Calculate compliance score
        compliance_score = min(100, (
            percent_accounted_10min * 0.6 +  # 60% weight
            (100 - min(avg_muster_time, 30)) * 0.4  # 40% weight (lower time is better)
        ))
        
        return {
            "success": True,
            "data": {
                "total_events": total_events,
                "avg_muster_time_minutes": round(avg_muster_time, 2),
                "percent_accounted_10min": round(percent_accounted_10min, 2),
                "drills_this_month": drills_this_month,
                "compliance_score": round(compliance_score, 2),
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Advanced Analytics endpoints

@router.get("/api/mustering/analytics/event-performance/")
async def get_event_performance_analytics(
    start_date: Optional[date] = Query(None, description="Start date for analytics"),
    end_date: Optional[date] = Query(None, description="End date for analytics"),
    zone_id: Optional[int] = Query(None, description="Filter by zone ID"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive event performance analytics"""
    try:
        from app.services.mustering_analytics import MusteringAnalyticsService
        analytics_service = MusteringAnalyticsService(db)
        
        analytics = analytics_service.get_event_performance_analytics(
            start_date=start_date,
            end_date=end_date,
            zone_id=zone_id
        )
        
        return {"success": True, "data": analytics}
        
    except Exception as e:
        logger.error(f"Error in get_event_performance_analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/analytics/personnel-history/")
async def get_personnel_mustering_history(
    emp_code: Optional[str] = Query(None, description="Filter by employee code"),
    start_date: Optional[date] = Query(None, description="Start date for history"),
    end_date: Optional[date] = Query(None, description="End date for history"),
    limit: int = Query(100, description="Limit number of records"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed personnel mustering history"""
    try:
        from app.services.mustering_analytics import MusteringAnalyticsService
        analytics_service = MusteringAnalyticsService(db)
        
        history = analytics_service.get_personnel_mustering_history(
            emp_code=emp_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return {"success": True, "data": history}
        
    except Exception as e:
        logger.error(f"Error in get_personnel_mustering_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/analytics/zone-utilization/")
async def get_zone_utilization_analytics(
    zone_id: Optional[int] = Query(None, description="Filter by zone ID"),
    start_date: Optional[date] = Query(None, description="Start date for analytics"),
    end_date: Optional[date] = Query(None, description="End date for analytics"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get zone utilization and capacity analytics"""
    try:
        from app.services.mustering_analytics import MusteringAnalyticsService
        analytics_service = MusteringAnalyticsService(db)
        
        analytics = analytics_service.get_zone_utilization_analytics(
            zone_id=zone_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return {"success": True, "data": analytics}
        
    except Exception as e:
        logger.error(f"Error in get_zone_utilization_analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/analytics/drill-effectiveness/")
async def get_drill_effectiveness_analytics(
    start_date: Optional[date] = Query(None, description="Start date for analytics"),
    end_date: Optional[date] = Query(None, description="End date for analytics"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get drill effectiveness analytics"""
    try:
        from app.services.mustering_analytics import MusteringAnalyticsService
        analytics_service = MusteringAnalyticsService(db)
        
        analytics = analytics_service.get_drill_effectiveness_analytics(
            start_date=start_date,
            end_date=end_date
        )
        
        return {"success": True, "data": analytics}
        
    except Exception as e:
        logger.error(f"Error in get_drill_effectiveness_analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/analytics/realtime/{event_id}")
async def get_realtime_analytics(
    event_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get real-time analytics for active event"""
    try:
        from app.services.mustering_analytics import MusteringAnalyticsService
        analytics_service = MusteringAnalyticsService(db)
        
        analytics = analytics_service.get_realtime_metrics(event_id)
        
        return {"success": True, "data": analytics}
        
    except Exception as e:
        logger.error(f"Error in get_realtime_analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Mobile Mustering endpoints

# The mobile view calls /check-in/ (hyphenated). Accept both: a marshal
# checking someone in during a live muster must not 404 over a hyphen.
@router.post("/api/mustering/mobile/checkin")
@router.post("/api/mustering/mobile/check-in")
async def mobile_checkin(
    checkin_data: dict,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register mobile check-in for mustering"""
    try:
        from app.services.mustering_mobile import MobileMusteringService
        mobile_service = MobileMusteringService(db)
        
        result = mobile_service.register_mobile_checkin(
            event_id=checkin_data.get("event_id"),
            emp_code=checkin_data.get("emp_code"),
            gps_coordinates=checkin_data.get("gps_coordinates"),
            photo_base64=checkin_data.get("photo_base64"),
            device_info=checkin_data.get("device_info"),
            notes=checkin_data.get("notes"),
            checked_by=current_user.id
        )
        
        # Broadcast real-time update
        from app.api.mustering import manager
        await manager.broadcast_to_event(
            result["event_id"],
            json.dumps({
                "type": "mobile_checkin",
                "data": result
            })
        )
        
        return {"success": True, "data": result}
        
    except ValueError as e:
        logger.error(f"Validation error in mobile check-in: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in mobile check-in: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/mobile/checkins/{event_id}")
async def get_mobile_checkins(
    event_id: int,
    status: Optional[int] = Query(None, description="Filter by status"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    limit: int = Query(100, description="Limit results"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get mobile check-ins for an event"""
    try:
        from app.services.mustering_mobile import MobileMusteringService
        mobile_service = MobileMusteringService(db)
        
        checkins = mobile_service.get_mobile_checkins(
            event_id=event_id,
            status=status,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        return {"success": True, "data": checkins}
        
    except Exception as e:
        logger.error(f"Error getting mobile check-ins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# The mobile view posts to /upload-photo/; keep the original name too.
@router.post("/api/mustering/mobile/emergency-photo")
@router.post("/api/mustering/mobile/upload-photo")
async def upload_emergency_photo(
    photo_data: dict,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload emergency photo during mustering"""
    try:
        from app.services.mustering_mobile import MobileMusteringService
        mobile_service = MobileMusteringService(db)
        
        result = mobile_service.upload_emergency_photo(
            event_id=photo_data.get("event_id"),
            emp_code=photo_data.get("emp_code"),
            photo_base64=photo_data.get("photo_base64"),
            gps_coordinates=photo_data.get("gps_coordinates"),
            taken_by=current_user.id,
            description=photo_data.get("description")
        )
        
        # Broadcast real-time update
        from app.api.mustering import manager
        await manager.broadcast_to_event(
            result["event_id"],
            json.dumps({
                "type": "emergency_photo",
                "data": result
            })
        )
        
        return {"success": True, "data": result}
        
    except ValueError as e:
        logger.error(f"Validation error in emergency photo upload: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading emergency photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/mustering/mobile/emergency-alert")
async def send_emergency_alert(
    alert_data: dict,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send emergency alert for missing personnel"""
    try:
        from app.services.mustering_mobile import MobileMusteringService
        mobile_service = MobileMusteringService(db)
        
        result = mobile_service.send_emergency_alert(
            event_id=alert_data.get("event_id"),
            emp_codes=alert_data.get("emp_codes"),
            message=alert_data.get("message"),
            alert_type=alert_data.get("alert_type", "MISSING_PERSONNEL"),
            priority=alert_data.get("priority", "HIGH")
        )
        
        # Broadcast real-time update
        from app.api.mustering import manager
        await manager.broadcast_to_event(
            result["event_id"],
            json.dumps({
                "type": "emergency_alert",
                "data": result
            })
        )
        
        return {"success": True, "data": result}
        
    except ValueError as e:
        logger.error(f"Validation error in emergency alert: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending emergency alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/mobile/missing-personnel/{event_id}")
async def get_missing_personnel_locations(
    event_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get last known locations for missing personnel"""
    try:
        from app.services.mustering_mobile import MobileMusteringService
        mobile_service = MobileMusteringService(db)
        
        locations = mobile_service.get_missing_personnel_locations(event_id)
        
        return {"success": True, "data": locations}
        
    except Exception as e:
        logger.error(f"Error getting missing personnel locations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/mobile/statistics/")
async def get_mobile_mustering_statistics(
    start_date: Optional[date] = Query(None, description="Start date for statistics"),
    end_date: Optional[date] = Query(None, description="End date for statistics"),
    zone_id: Optional[int] = Query(None, description="Filter by zone ID"),
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get mobile mustering statistics"""
    try:
        from app.services.mustering_mobile import MobileMusteringService
        mobile_service = MobileMusteringService(db)
        
        stats = mobile_service.get_mobile_mustering_statistics(
            start_date=start_date,
            end_date=end_date,
            zone_id=zone_id
        )
        
        return {"success": True, "data": stats}
        
    except Exception as e:
        logger.error(f"Error getting mobile mustering statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/mustering/websocket/metrics/")
async def get_websocket_metrics(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get WebSocket connection metrics"""
    try:
        metrics = await enhanced_manager.get_connection_metrics()
        return {"success": True, "data": metrics}
        
    except Exception as e:
        logger.error(f"Error getting WebSocket metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Simulation and training endpoints — service removed (mustering_simulation.py had a
# syntax error and is no longer present). Return 501 so callers get a clear signal.

@router.post("/api/mustering/simulation/start")
@router.post("/api/mustering/simulation/{simulation_id}/end")
@router.post("/api/mustering/simulation/{simulation_id}/punch")
@router.get("/api/mustering/simulation/{simulation_id}/progress/")
@router.get("/api/mustering/simulation/active/")
@router.get("/api/mustering/simulation/history/")
@router.post("/api/mustering/simulation/{simulation_id}/auto-progress")
@router.get("/api/mustering/training/scenarios/")
@router.post("/api/mustering/training/scenarios")
@router.get("/api/mustering/simulation/metrics/")
async def simulation_not_implemented(*args, **kwargs):
    raise HTTPException(status_code=501, detail="Mustering simulation is not available in this build.")


# External integration endpoints — service removed (mustering_integration.py had no
# working configuration). Return 501 so callers get a clear signal.

@router.post("/api/mustering/integration/sap/{event_id}/sync")
@router.post("/api/mustering/integration/hse/{event_id}/notify")
@router.post("/api/mustering/integration/fire/{event_id}/trigger")
@router.post("/api/mustering/integration/medical/{event_id}/alert")
@router.get("/api/mustering/integration/status/")
@router.post("/api/mustering/integration/test/{integration_type}")
async def integration_not_implemented(*args, **kwargs):
    raise HTTPException(status_code=501, detail="External integrations are not configured in this build.")


# Import models at the end to avoid circular imports
from app.models.biotime_models import (
    MusteringEvent, MusteringLog,
    MusteringDrillSchedule, MusteringEventTemplate,
)
from app.models.zone import Zone as MusteringZone  # alias for backwards-compat within this module
