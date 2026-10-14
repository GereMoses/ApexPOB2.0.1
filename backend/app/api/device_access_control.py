"""
Device Access Control API — BioTime-compatible
Covers: Access Levels, Time Zones, Door Parameters, User Authorizations,
        Anti-Passback rules, Blacklist management, and direct door commands.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Boolean, SmallInteger, DateTime, ForeignKey, Text, func
from sqlalchemy import text as sa_text
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

from ..core.database import get_db, Base
from ..services.device_pin import rewrite_command
from ..core.dependencies import get_current_user
from ..models.user import User
from ..models.biotime_models import (
    AccLevel, AccUserAuthorize, AccDoor, IClockTerminal, PersonnelEmployee
)
# Import real AccTimeZone — avoids duplicate class name in SQLAlchemy registry
from ..models.access_control import AccTimeZone

router = APIRouter()


# ─── New table: passback RULES (config) ─────────────────────────────────────
# NOTE: AccAntiPassback in models/access_control.py is a TRACKING table (per-employee
# state). This model stores the door-pair rules configuration and uses a different name.

class AccPassbackRule(Base):
    """Configurable door-pair anti-passback rules (not the tracking state table)."""
    __tablename__ = "acc_passback_rule"
    __table_args__ = {'extend_existing': True}

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False)
    in_door_id  = Column(Integer, ForeignKey("acc_door.id"), nullable=True)
    out_door_id = Column(Integer, ForeignKey("acc_door.id"), nullable=True)
    mode        = Column(SmallInteger, default=1)   # 0=soft warn, 1=hard deny
    is_active   = Column(Boolean, default=True)
    description = Column(Text)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class DeviceBlacklist(Base):
    __tablename__ = "device_blacklist"
    __table_args__ = {'extend_existing': True}

    id          = Column(Integer, primary_key=True, index=True)
    emp_code    = Column(String(20), nullable=False, index=True)
    reason      = Column(Text)
    blocked_at  = Column(DateTime(timezone=True), server_default=func.now())
    blocked_by  = Column(Integer, ForeignKey("users.id"))
    is_active   = Column(Boolean, default=True)
    expires_at  = Column(DateTime(timezone=True), nullable=True)


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class TimeZoneCreate(BaseModel):
    name: str          # stored as timezone_name in AccTimeZone
    start_time: Optional[str] = "08:00"   # "HH:MM"
    end_time:   Optional[str] = "18:00"   # "HH:MM"
    days: Optional[str] = "mon,tue,wed,thu,fri"  # comma-sep day keys

class TimeZoneUpdate(BaseModel):
    name:       Optional[str] = None
    start_time: Optional[str] = None
    end_time:   Optional[str] = None
    days:       Optional[str] = None

class AccessLevelCreate(BaseModel):
    name: str
    description: Optional[str] = None
    time_zone: Optional[str] = "UTC"

class AccessLevelUpdate(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None
    time_zone:   Optional[str] = None

class DoorCreate(BaseModel):
    name: str
    terminal_sn: str
    acc_level_id: Optional[int] = None
    verify_mode: Optional[int] = Field(0, description="0=fingerprint,1=card,2=face,3=card+fp,4=card+face")
    open_duration: Optional[int] = Field(5, description="Door open duration in seconds")
    mustering_mode: bool = False
    emergency_action: Optional[int] = Field(0, description="0=none,1=lock,2=unlock on emergency")

class DoorUpdate(BaseModel):
    name:             Optional[str] = None
    acc_level_id:     Optional[int] = None
    verify_mode:      Optional[int] = None
    open_duration:    Optional[int] = None
    mustering_mode:   Optional[bool] = None
    emergency_action: Optional[int] = None

class UserAuthCreate(BaseModel):
    emp_code:     str
    acc_level_id: int
    start_time:   Optional[str] = None   # "HH:MM"
    end_time:     Optional[str] = None   # "HH:MM"
    valid_days:   Optional[str] = "1,2,3,4,5"

class AntiPassbackCreate(BaseModel):
    name:        str
    in_door_id:  Optional[int] = None
    out_door_id: Optional[int] = None
    mode:        int = Field(1, description="0=soft warn, 1=hard deny")
    description: Optional[str] = None

class BlacklistCreate(BaseModel):
    emp_code:   str
    reason:     Optional[str] = None
    expires_at: Optional[datetime] = None


# ─── Helper ───────────────────────────────────────────────────────────────────

def _queue_cmd(db: Session, sn: str, cmd: str) -> int:
    cmd = rewrite_command(db, cmd)   # PIN=<emp_code> -> reader PIN
    result = db.execute(
        sa_text("INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, status) "
                "VALUES (:sn, :cmd, :now, 0) RETURNING id"),
        {"sn": sn, "cmd": cmd, "now": datetime.now(timezone.utc)}
    )
    db.commit()
    return result.fetchone()[0]


def _tz_slot(start: str, end: str) -> str:
    """Format a time slot for AccTimeZone columns: 'HH:MM-HH:MM'."""
    if start and end:
        return f"{start}-{end}"
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# TIME ZONES  (uses real AccTimeZone from models/access_control.py)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/device/access/timezones/")
async def list_timezones(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = db.query(AccTimeZone).order_by(AccTimeZone.timezone_name).all()
    return {"success": True, "data": [
        {
            "id": r.id,
            "name": r.timezone_name,
            # Reconstruct start/end from first populated weekday slot
            "start_time": (r.mon_time1 or "").split("-")[0] or None,
            "end_time":   (r.mon_time1 or "").split("-")[-1] or None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]}


@router.post("/api/device/access/timezones")
async def create_timezone(
    payload: TimeZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    slot = _tz_slot(payload.start_time, payload.end_time)
    days = set((payload.days or "").lower().split(","))
    tz = AccTimeZone(
        timezone_name=payload.name,
        mon_time1 = slot if "mon" in days else None,
        tue_time1 = slot if "tue" in days else None,
        wed_time1 = slot if "wed" in days else None,
        thu_time1 = slot if "thu" in days else None,
        fri_time1 = slot if "fri" in days else None,
        sat_time1 = slot if "sat" in days else None,
        sun_time1 = slot if "sun" in days else None,
    )
    db.add(tz)
    db.commit()
    db.refresh(tz)
    return {"success": True, "data": {"id": tz.id, "name": tz.timezone_name}}


@router.put("/api/device/access/timezones/{tz_id}")
async def update_timezone(
    tz_id: int,
    payload: TimeZoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tz = db.query(AccTimeZone).filter(AccTimeZone.id == tz_id).first()
    if not tz:
        raise HTTPException(status_code=404, detail="Time zone not found")
    if payload.name:
        tz.timezone_name = payload.name
    if payload.start_time or payload.end_time or payload.days:
        slot = _tz_slot(payload.start_time or "08:00", payload.end_time or "18:00")
        days = set((payload.days or "mon,tue,wed,thu,fri").lower().split(","))
        for day, attr in [("mon","mon_time1"),("tue","tue_time1"),("wed","wed_time1"),
                          ("thu","thu_time1"),("fri","fri_time1"),("sat","sat_time1"),("sun","sun_time1")]:
            setattr(tz, attr, slot if day in days else None)
    db.commit()
    return {"success": True}


@router.delete("/api/device/access/timezones/{tz_id}")
async def delete_timezone(
    tz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tz = db.query(AccTimeZone).filter(AccTimeZone.id == tz_id).first()
    if not tz:
        raise HTTPException(status_code=404, detail="Time zone not found")
    db.delete(tz)
    db.commit()
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# ACCESS LEVELS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/device/access/levels/")
async def list_access_levels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = db.query(AccLevel).order_by(AccLevel.name).all()
    return {"success": True, "data": [
        {"id": r.id, "name": r.name, "description": r.description,
         "time_zone": r.time_zone,
         "user_count": len(r.user_authorizations),
         "door_count":  len(r.doors),
         "created_at":  r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]}


@router.post("/api/device/access/levels")
async def create_access_level(
    payload: AccessLevelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    level = AccLevel(**payload.dict())
    db.add(level)
    db.commit()
    db.refresh(level)
    return {"success": True, "data": {"id": level.id, "name": level.name}}


@router.put("/api/device/access/levels/{level_id}")
async def update_access_level(
    level_id: int,
    payload: AccessLevelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    level = db.query(AccLevel).filter(AccLevel.id == level_id).first()
    if not level:
        raise HTTPException(status_code=404, detail="Access level not found")
    for k, v in payload.dict(exclude_none=True).items():
        setattr(level, k, v)
    level.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True}


@router.delete("/api/device/access/levels/{level_id}")
async def delete_access_level(
    level_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    level = db.query(AccLevel).filter(AccLevel.id == level_id).first()
    if not level:
        raise HTTPException(status_code=404, detail="Access level not found")
    db.delete(level)
    db.commit()
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# DOORS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/device/access/doors/")
async def list_doors(
    terminal_sn: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(AccDoor)
    if terminal_sn:
        q = q.filter(AccDoor.terminal_sn == terminal_sn)
    rows = q.order_by(AccDoor.name).all()
    level_map = {l.id: l.name for l in db.query(AccLevel).all()}
    return {"success": True, "data": [
        {"id": r.id, "name": r.name, "terminal_sn": r.terminal_sn,
         "acc_level_id":   r.acc_level_id,
         "acc_level_name": level_map.get(r.acc_level_id, "—"),
         "mustering_mode":   r.mustering_mode,
         "emergency_action": r.emergency_action,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]}


@router.post("/api/device/access/doors")
async def create_door(
    payload: DoorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == payload.terminal_sn).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal not found")
    door = AccDoor(
        name=payload.name,
        terminal_sn=payload.terminal_sn,
        acc_level_id=payload.acc_level_id,
        mustering_mode=payload.mustering_mode,
        emergency_action=payload.emergency_action,
    )
    db.add(door)
    db.commit()
    db.refresh(door)
    _queue_cmd(db, payload.terminal_sn,
               f"DATA UPDATE DOOR ID={door.id} DOORNAME={payload.name} "
               f"VERIFYMODE={payload.verify_mode or 0} OPENDOOR={payload.open_duration or 5}")
    return {"success": True, "data": {"id": door.id, "name": door.name}}


@router.put("/api/device/access/doors/{door_id}")
async def update_door(
    door_id: int,
    payload: DoorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    door = db.query(AccDoor).filter(AccDoor.id == door_id).first()
    if not door:
        raise HTTPException(status_code=404, detail="Door not found")
    for k, v in payload.dict(exclude_none=True).items():
        if hasattr(door, k):
            setattr(door, k, v)
    door.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True}


@router.delete("/api/device/access/doors/{door_id}")
async def delete_door(
    door_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    door = db.query(AccDoor).filter(AccDoor.id == door_id).first()
    if not door:
        raise HTTPException(status_code=404, detail="Door not found")
    db.delete(door)
    db.commit()
    return {"success": True}


@router.post("/api/device/access/doors/{door_id}/open")
async def open_door(
    door_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    door = db.query(AccDoor).filter(AccDoor.id == door_id).first()
    if not door:
        raise HTTPException(status_code=404, detail="Door not found")
    if not door.terminal_sn:
        raise HTTPException(status_code=400, detail="Door has no associated device")
    cmd_id = _queue_cmd(db, door.terminal_sn, f"OPEN DOOR {door_id}")
    return {"success": True, "data": {"command_id": cmd_id, "message": f"Open door command queued for {door.name}"}}


# ═══════════════════════════════════════════════════════════════════════════════
# USER AUTHORIZATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/device/access/users/")
async def list_user_authorizations(
    emp_code:     Optional[str] = Query(None),
    acc_level_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(AccUserAuthorize)
    if emp_code:
        q = q.filter(AccUserAuthorize.emp_code == emp_code)
    if acc_level_id:
        q = q.filter(AccUserAuthorize.acc_level_id == acc_level_id)
    rows = q.all()
    level_map = {l.id: l.name for l in db.query(AccLevel).all()}
    emp_map   = {e.emp_code: f"{e.first_name or ''} {e.last_name or ''}".strip()
                 for e in db.query(PersonnelEmployee).all()}
    return {"success": True, "data": [
        {"id": r.id, "emp_code": r.emp_code,
         "emp_name":      emp_map.get(r.emp_code, "—"),
         "acc_level_id":  r.acc_level_id,
         "acc_level_name": level_map.get(r.acc_level_id, "—"),
         "start_time":    str(r.start_time) if r.start_time else None,
         "end_time":      str(r.end_time)   if r.end_time   else None,
         "valid_days":    r.valid_days,
         "created_at":    r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]}


@router.post("/api/device/access/users")
async def assign_user_access(
    payload: UserAuthCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(AccUserAuthorize).filter(
        AccUserAuthorize.emp_code == payload.emp_code,
        AccUserAuthorize.acc_level_id == payload.acc_level_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Assignment already exists")
    auth = AccUserAuthorize(
        emp_code=payload.emp_code,
        acc_level_id=payload.acc_level_id,
        valid_days=payload.valid_days,
    )
    db.add(auth)
    db.commit()
    db.refresh(auth)
    # Push to all access-control terminals
    for t in db.query(IClockTerminal).filter(IClockTerminal.device_type == 1).all():
        _queue_cmd(db, t.sn, f"DATA UPDATE USERINFO PIN={payload.emp_code} ACCGROUP={payload.acc_level_id}")
    return {"success": True, "data": {"id": auth.id}}


@router.delete("/api/device/access/users/{auth_id}")
async def remove_user_access(
    auth_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    auth = db.query(AccUserAuthorize).filter(AccUserAuthorize.id == auth_id).first()
    if not auth:
        raise HTTPException(status_code=404, detail="Authorization not found")
    db.delete(auth)
    db.commit()
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# ANTI-PASSBACK RULES  (uses AccPassbackRule — NOT the tracking AccAntiPassback)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/device/access/anti-passback/")
async def list_anti_passback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = db.query(AccPassbackRule).order_by(AccPassbackRule.name).all()
    door_map = {d.id: d.name for d in db.query(AccDoor).all()}
    return {"success": True, "data": [
        {"id": r.id, "name": r.name,
         "in_door_id":   r.in_door_id,  "in_door_name":  door_map.get(r.in_door_id, "—"),
         "out_door_id":  r.out_door_id, "out_door_name": door_map.get(r.out_door_id, "—"),
         "mode": r.mode, "is_active": r.is_active, "description": r.description}
        for r in rows
    ]}


@router.post("/api/device/access/anti-passback")
async def create_anti_passback(
    payload: AntiPassbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rule = AccPassbackRule(**payload.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"success": True, "data": {"id": rule.id, "name": rule.name}}


@router.delete("/api/device/access/anti-passback/{rule_id}")
async def delete_anti_passback(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rule = db.query(AccPassbackRule).filter(AccPassbackRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# BLACKLIST
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/device/access/blacklist/")
async def get_blacklist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = db.query(DeviceBlacklist).filter(DeviceBlacklist.is_active == True).all()
    emp_map = {e.emp_code: f"{e.first_name or ''} {e.last_name or ''}".strip()
               for e in db.query(PersonnelEmployee).all()}
    return {"success": True, "data": [
        {"id": r.id, "emp_code": r.emp_code,
         "emp_name":   emp_map.get(r.emp_code, "—"),
         "reason":     r.reason,
         "blocked_at": r.blocked_at.isoformat() if r.blocked_at else None,
         "expires_at": r.expires_at.isoformat() if r.expires_at else None}
        for r in rows
    ]}


@router.post("/api/device/access/blacklist")
async def add_to_blacklist(
    payload: BlacklistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entry = DeviceBlacklist(
        emp_code=payload.emp_code,
        reason=payload.reason,
        blocked_by=current_user.id,
        expires_at=payload.expires_at,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    for t in db.query(IClockTerminal).all():
        _queue_cmd(db, t.sn, f"DATA UPDATE USERINFO PIN={payload.emp_code} PRIVILEGE=0 ACCGROUP=-1")
    return {"success": True, "data": {"id": entry.id}}


@router.delete("/api/device/access/blacklist/{entry_id}")
async def remove_from_blacklist(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entry = db.query(DeviceBlacklist).filter(DeviceBlacklist.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.is_active = False
    db.commit()
    return {"success": True}
