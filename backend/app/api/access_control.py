"""
Access Control API - BioTime 9.5 Compatible
Complete SQL-based implementation — no ORM field-name mismatches.
Tables: acc_timezone, acc_level, acc_level_door, acc_door, acc_userauthorize,
        acc_event, acc_interlock_group, acc_interlock_door, acc_linkage,
        acc_antipassback, acc_first_card, acc_multi_card, acc_multi_card_user
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import asyncio
import logging

from app.core.database import get_db
from app.services.device_pin import rewrite_command
from app.core.dependencies import get_current_user
from app.core.websocket import ConnectionManager
from app.services.emergency_service import EmergencyService
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/access-control", tags=["access-control"])
manager = ConnectionManager()


# ── helpers ──────────────────────────────────────────────────────────────────

def _rows(result) -> List[dict]:
    return [dict(r._mapping) for r in result]

def _one(result) -> Optional[dict]:
    r = result.fetchone()
    return dict(r._mapping) if r else None

def _serial(obj):
    """JSON-safe serialiser for datetime / date / time objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serialisable")


def _queue_ac_sync(emp_code: str, level_id: int, db: Session, revoke: bool = False):
    """Queue ADMS USERINFO command to every terminal linked to doors in the given level."""
    try:
        # Collect timezone IDs assigned to this level
        tz_rows = db.execute(text(
            "SELECT DISTINCT timezone_id FROM acc_level_door WHERE level_id = :lid"
        ), {"lid": level_id}).fetchall()
        tz_ids = [r._mapping["timezone_id"] for r in tz_rows]
        tz1 = tz_ids[0] if len(tz_ids) > 0 else 0
        tz2 = tz_ids[1] if len(tz_ids) > 1 else 0
        tz3 = tz_ids[2] if len(tz_ids) > 2 else 0

        # Find all terminals linked to doors in this level
        term_rows = db.execute(text("""
            SELECT DISTINCT d.terminal_sn
            FROM acc_level_door ld
            JOIN acc_door d ON d.id = ld.door_id
            WHERE ld.level_id = :lid AND d.terminal_sn IS NOT NULL
        """), {"lid": level_id}).fetchall()

        if revoke:
            cmd = f"DATA UPDATE USERINFO PIN={emp_code} TZ1=0 TZ2=0 TZ3=0 Group=0 VerifyStyle=0"
        else:
            cmd = f"DATA UPDATE USERINFO PIN={emp_code} TZ1={tz1} TZ2={tz2} TZ3={tz3} Group=1 VerifyStyle=131"

        cmd = rewrite_command(db, cmd)   # PIN=<emp_code> -> reader PIN
        for row in term_rows:
            sn = row._mapping["terminal_sn"]
            db.execute(text(
                "INSERT INTO iclock_devcmd (sn, cmd_content, status, cmd_commit_time) "
                "VALUES (:sn, :cmd, 0, NOW())"
            ), {"sn": sn, "cmd": cmd})
    except Exception as e:
        logger.warning(f"AC device sync skipped: {e}")


# ── Pydantic request bodies ───────────────────────────────────────────────────

class TimeZoneBody(BaseModel):
    timezone_name: str
    sun_time1: Optional[str] = None; sun_time2: Optional[str] = None; sun_time3: Optional[str] = None
    mon_time1: Optional[str] = None; mon_time2: Optional[str] = None; mon_time3: Optional[str] = None
    tue_time1: Optional[str] = None; tue_time2: Optional[str] = None; tue_time3: Optional[str] = None
    wed_time1: Optional[str] = None; wed_time2: Optional[str] = None; wed_time3: Optional[str] = None
    thu_time1: Optional[str] = None; thu_time2: Optional[str] = None; thu_time3: Optional[str] = None
    fri_time1: Optional[str] = None; fri_time2: Optional[str] = None; fri_time3: Optional[str] = None
    sat_time1: Optional[str] = None; sat_time2: Optional[str] = None; sat_time3: Optional[str] = None
    hol1_time1: Optional[str] = None; hol1_time2: Optional[str] = None; hol1_time3: Optional[str] = None
    hol2_time1: Optional[str] = None; hol2_time2: Optional[str] = None; hol2_time3: Optional[str] = None
    hol3_time1: Optional[str] = None; hol3_time2: Optional[str] = None; hol3_time3: Optional[str] = None
    emergency_override: bool = False

class LevelBody(BaseModel):
    level_name: str
    description: Optional[str] = None
    mustering_only: bool = False
    is_active: bool = True

class DoorBody(BaseModel):
    terminal_sn: Optional[str] = None      # legacy standalone/T&A door
    controller_id: Optional[int] = None    # C3/inBio panel the reader is wired to
    port: Optional[int] = None             # door_no / port on that controller
    door_name: str
    relay_time: int = 5
    door_sensor_type: int = 0
    alarm_delay: int = 30
    open_duration: int = 15
    anti_passback: int = 0
    first_card_open: bool = False
    interlock_group: int = 0
    emergency_action: int = 0
    mustering_mode: bool = False
    fire_linkage: bool = False

class LevelDoorBody(BaseModel):
    door_id: int
    timezone_id: int

class UserLevelBody(BaseModel):
    emp_codes: Optional[List[str]] = []
    emp_ids: Optional[List[int]] = []
    dept_ids: Optional[List[int]] = []
    valid_from: Optional[str] = None  # YYYY-MM-DD
    valid_to: Optional[str] = None    # YYYY-MM-DD

class InterlockBody(BaseModel):
    group_name: str
    description: Optional[str] = None
    door_ids: List[int] = []

class LinkageBody(BaseModel):
    terminal_sn: str
    input_type: int = 0
    output_action: int = 0
    output_door_id: Optional[int] = None
    output_terminal_sn: Optional[str] = None

class MultiCardBody(BaseModel):
    door_id: int
    min_cards: int = 2
    emp_codes: List[str] = []

class EmergencyBody(BaseModel):
    action: str  # "lock" | "unlock"
    door_ids: List[int] = []
    reason: Optional[str] = None

class MusteringBody(BaseModel):
    door_ids: List[int]
    mustering_mode: bool


# ══════════════════════════════════════════════════════════════════════════════
# TIME ZONE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/timezones/")
async def get_timezones(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text("SELECT * FROM acc_timezone ORDER BY id")).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.post("/timezones")
async def create_timezone(body: TimeZoneBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    fields = body.dict()
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(f":{k}" for k in fields)
    row = db.execute(
        text(f"INSERT INTO acc_timezone ({cols}) VALUES ({placeholders}) RETURNING *"),
        fields
    ).fetchone()
    db.commit()
    return {"success": True, "data": dict(row._mapping)}


@router.get("/timezones/{tz_id}")
async def get_timezone(tz_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT * FROM acc_timezone WHERE id = :id"), {"id": tz_id}).fetchone()
    if not row:
        raise HTTPException(404, "Time zone not found")
    return {"success": True, "data": dict(row._mapping)}


@router.put("/timezones/{tz_id}")
async def update_timezone(tz_id: int, body: TimeZoneBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT id FROM acc_timezone WHERE id = :id"), {"id": tz_id}).fetchone()
    if not row:
        raise HTTPException(404, "Time zone not found")
    fields = body.dict()
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    fields["_id"] = tz_id
    row = db.execute(
        text(f"UPDATE acc_timezone SET {sets}, updated_at = NOW() WHERE id = :_id RETURNING *"),
        fields
    ).fetchone()
    db.commit()
    return {"success": True, "data": dict(row._mapping)}


@router.delete("/timezones/{tz_id}")
async def delete_timezone(tz_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    in_use = db.execute(text("SELECT id FROM acc_level_door WHERE timezone_id = :id LIMIT 1"), {"id": tz_id}).fetchone()
    if in_use:
        raise HTTPException(400, "Time zone is in use by an access level")
    db.execute(text("DELETE FROM acc_timezone WHERE id = :id"), {"id": tz_id})
    db.commit()
    return {"success": True, "message": "Time zone deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# ACCESS LEVELS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/levels/")
async def get_levels(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT l.*,
               l.name AS level_name,
               COUNT(DISTINCT ld.id)  AS door_count,
               COUNT(DISTINCT ua.id)  AS user_count
        FROM acc_level l
        LEFT JOIN acc_level_door ld ON ld.level_id = l.id
        LEFT JOIN acc_userauthorize ua ON ua.acc_level_id = l.id
        GROUP BY l.id
        ORDER BY l.id
    """)).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.post("/levels")
async def create_level(body: LevelBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("""
        INSERT INTO acc_level (name, description, mustering_only, is_active)
        VALUES (:name, :description, :mustering_only, :is_active) RETURNING *
    """), {"name": body.level_name, "description": body.description,
           "mustering_only": body.mustering_only, "is_active": body.is_active}).fetchone()
    db.commit()
    d = dict(row._mapping); d["level_name"] = d["name"]
    return {"success": True, "data": d}


@router.get("/levels/{level_id}")
async def get_level(level_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT *, name AS level_name FROM acc_level WHERE id = :id"), {"id": level_id}).fetchone()
    if not row:
        raise HTTPException(404, "Access level not found")
    return {"success": True, "data": dict(row._mapping)}


@router.put("/levels/{level_id}")
async def update_level(level_id: int, body: LevelBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT id FROM acc_level WHERE id = :id"), {"id": level_id}).fetchone()
    if not row:
        raise HTTPException(404, "Access level not found")
    row = db.execute(text("""
        UPDATE acc_level SET name=:name, description=:description, mustering_only=:mo,
               is_active=:ia, updated_at=NOW() WHERE id=:id RETURNING *, name AS level_name
    """), {"name": body.level_name, "description": body.description,
           "mo": body.mustering_only, "ia": body.is_active, "id": level_id}).fetchone()
    db.commit()
    d = dict(row._mapping); d["level_name"] = d["name"]
    return {"success": True, "data": d}


@router.delete("/levels/{level_id}")
async def delete_level(level_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT id FROM acc_level WHERE id = :id"), {"id": level_id}).fetchone()
    if not row:
        raise HTTPException(404, "Access level not found")
    in_use = db.execute(text("SELECT id FROM acc_userauthorize WHERE acc_level_id = :id LIMIT 1"), {"id": level_id}).fetchone()
    if in_use:
        raise HTTPException(400, "Access level is assigned to users — remove all user assignments first")
    # Null out FK references from doors and visitor tables before deleting
    db.execute(text("UPDATE acc_door SET acc_level_id = NULL WHERE acc_level_id = :id"), {"id": level_id})
    db.execute(text("UPDATE vis_type SET access_level_id = NULL WHERE access_level_id = :id"), {"id": level_id})
    db.execute(text("UPDATE acc_visitor_access SET acc_level_id = NULL WHERE acc_level_id = :id"), {"id": level_id})
    db.execute(text("DELETE FROM acc_level_door WHERE level_id = :id"), {"id": level_id})
    db.execute(text("DELETE FROM acc_level WHERE id = :id"), {"id": level_id})
    db.commit()
    return {"success": True, "message": "Access level deleted"}


# ── Level → Door/Timezone pairs ───────────────────────────────────────────────

@router.get("/levels/{level_id}/doors/")
async def get_level_doors(level_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT ld.id, ld.level_id, ld.door_id, ld.timezone_id,
               d.name AS door_name, tz.timezone_name
        FROM acc_level_door ld
        JOIN acc_door d ON d.id = ld.door_id
        JOIN acc_timezone tz ON tz.id = ld.timezone_id
        WHERE ld.level_id = :lid
        ORDER BY ld.id
    """), {"lid": level_id}).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.post("/levels/{level_id}/doors")
async def add_level_door(level_id: int, body: LevelDoorBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    existing = db.execute(text(
        "SELECT id FROM acc_level_door WHERE level_id=:l AND door_id=:d AND timezone_id=:t"
    ), {"l": level_id, "d": body.door_id, "t": body.timezone_id}).fetchone()
    if existing:
        raise HTTPException(400, "Door-timezone pair already exists for this level")
    row = db.execute(text("""
        INSERT INTO acc_level_door (level_id, door_id, timezone_id)
        VALUES (:l, :d, :t) RETURNING *
    """), {"l": level_id, "d": body.door_id, "t": body.timezone_id}).fetchone()
    db.commit()
    return {"success": True, "data": dict(row._mapping)}


@router.delete("/levels/{level_id}/doors/{pair_id}")
async def remove_level_door(level_id: int, pair_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.execute(text("DELETE FROM acc_level_door WHERE id = :id AND level_id = :lid"), {"id": pair_id, "lid": level_id})
    db.commit()
    return {"success": True, "message": "Door removed from access level"}


@router.post("/levels/{level_id}/copy")
async def copy_level(level_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    level = db.execute(text("SELECT * FROM acc_level WHERE id = :id"), {"id": level_id}).fetchone()
    if not level:
        raise HTTPException(404, "Access level not found")
    lm = level._mapping
    new_row = db.execute(text("""
        INSERT INTO acc_level (name, description, mustering_only, is_active)
        VALUES (:name, :desc, :mo, :ia) RETURNING *, name AS level_name
    """), {
        "name": f"Copy of {lm['name']}",
        "desc": lm.get("description"),
        "mo":   lm.get("mustering_only", False),
        "ia":   lm.get("is_active", True),
    }).fetchone()
    new_id = new_row._mapping["id"]
    pairs = db.execute(text(
        "SELECT door_id, timezone_id FROM acc_level_door WHERE level_id = :lid"
    ), {"lid": level_id}).fetchall()
    for p in pairs:
        db.execute(text(
            "INSERT INTO acc_level_door (level_id, door_id, timezone_id) VALUES (:l, :d, :t)"
        ), {"l": new_id, "d": p._mapping["door_id"], "t": p._mapping["timezone_id"]})
    db.commit()
    d = dict(new_row._mapping)
    return {"success": True, "data": d}


# ── Level → Users ─────────────────────────────────────────────────────────────

@router.get("/levels/{level_id}/users/")
async def get_level_users(level_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT ua.id, ua.emp_code, ua.acc_level_id AS level_id,
               ua.start_time, ua.end_time, ua.valid_days,
               TRIM(COALESCE(e.first_name,'') || ' ' || COALESCE(e.last_name,'')) AS emp_name,
               e.id AS personnel_id
        FROM acc_userauthorize ua
        LEFT JOIN personnel_employee e ON e.emp_code = ua.emp_code
        WHERE ua.acc_level_id = :lid
        ORDER BY ua.emp_code
    """), {"lid": level_id}).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.post("/levels/{level_id}/assign")
async def assign_level(level_id: int, body: UserLevelBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    level = db.execute(text("SELECT id FROM acc_level WHERE id = :id"), {"id": level_id}).fetchone()
    if not level:
        raise HTTPException(404, "Access level not found")

    emp_codes: List[str] = list(body.emp_codes or [])

    # Resolve emp_ids → emp_codes
    if body.emp_ids:
        for eid in body.emp_ids:
            r = db.execute(text("SELECT emp_code FROM personnel_employee WHERE id = :id"), {"id": eid}).fetchone()
            if r:
                emp_codes.append(r._mapping["emp_code"])

    # Resolve dept_ids → emp_codes
    if body.dept_ids:
        for did in body.dept_ids:
            dept_emps = db.execute(text("SELECT emp_code FROM personnel_employee WHERE dept_id = :d"), {"d": did}).fetchall()
            emp_codes.extend(r._mapping["emp_code"] for r in dept_emps)

    emp_codes = list(set(emp_codes))
    added = 0
    for code in emp_codes:
        exists = db.execute(text(
            "SELECT id FROM acc_userauthorize WHERE emp_code=:c AND acc_level_id=:l"
        ), {"c": code, "l": level_id}).fetchone()
        if not exists:
            db.execute(text(
                "INSERT INTO acc_userauthorize (emp_code, acc_level_id, valid_from, valid_to) "
                "VALUES (:c, :l, :vf, :vt)"
            ), {"c": code, "l": level_id, "vf": body.valid_from, "vt": body.valid_to})
        else:
            db.execute(text(
                "UPDATE acc_userauthorize SET valid_from=:vf, valid_to=:vt WHERE emp_code=:c AND acc_level_id=:l"
            ), {"vf": body.valid_from, "vt": body.valid_to, "c": code, "l": level_id})
        added += 1
        _queue_ac_sync(code, level_id, db)

    db.commit()
    return {"success": True, "message": f"Assigned {added} employees to access level"}


@router.delete("/levels/{level_id}/users/{auth_id}")
async def remove_level_user(level_id: int, auth_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT emp_code FROM acc_userauthorize WHERE id=:id AND acc_level_id=:lid"),
                     {"id": auth_id, "lid": level_id}).fetchone()
    if row:
        _queue_ac_sync(row._mapping["emp_code"], level_id, db, revoke=True)
    db.execute(text("DELETE FROM acc_userauthorize WHERE id=:id AND acc_level_id=:lid"), {"id": auth_id, "lid": level_id})
    db.commit()
    return {"success": True, "message": "User removed from access level"}


# ── User Level query (all assignments for an employee) ─────────────────────────

@router.get("/user-levels/")
async def get_user_levels(
    emp_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    q = """
        SELECT ua.id, ua.emp_code, ua.acc_level_id AS level_id, l.name AS level_name,
               ua.start_time, ua.end_time, ua.valid_days, ua.valid_from, ua.valid_to,
               TRIM(COALESCE(e.first_name,'') || ' ' || COALESCE(e.last_name,'')) AS emp_name,
               CASE WHEN ua.valid_to IS NOT NULL AND ua.valid_to < CURRENT_DATE THEN TRUE ELSE FALSE END AS is_expired
        FROM acc_userauthorize ua
        JOIN acc_level l ON l.id = ua.acc_level_id
        LEFT JOIN personnel_employee e ON e.emp_code = ua.emp_code
    """
    params: dict = {}
    if emp_code:
        q += " WHERE ua.emp_code = :emp_code"
        params["emp_code"] = emp_code
    q += " ORDER BY ua.emp_code, l.name"
    rows = db.execute(text(q), params).fetchall()
    return {"success": True, "data": _rows(rows)}


# ══════════════════════════════════════════════════════════════════════════════
# DOORS
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# TERMINAL LIST (for door-assignment selector)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/terminals/")
async def get_ac_terminals(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Return all ADMS terminals enriched with their current door assignment and zone.
    Used to populate the terminal selector when creating or editing doors.
    """
    rows = db.execute(text("""
        SELECT
            t.sn,
            COALESCE(t.alias, t.sn)                  AS alias,
            t.ip_address,
            t.state,
            t.reader_purpose,
            t.device_type,
            t.last_activity,
            t.zone_id,
            z.name                                    AS zone_name,
            CASE WHEN t.state = 1
                      AND t.last_activity IS NOT NULL
                      AND t.last_activity > NOW() - make_interval(secs =>
                              GREATEST(COALESCE(t.heartbeat_interval, 30) * 5, 90)::float)
                 THEN true ELSE false END              AS is_online,
            t.last_activity                           AS last_seen,
            COUNT(d.id)                               AS door_count,
            MIN(d.id)                                 AS door_id,
            STRING_AGG(d.name, ', ' ORDER BY d.id)   AS door_name
        FROM iclock_terminal t
        LEFT JOIN zones z  ON z.id  = t.zone_id
        LEFT JOIN acc_door d ON d.terminal_sn = t.sn
        GROUP BY t.sn, t.alias, t.ip_address, t.state, t.reader_purpose,
                 t.device_type, t.last_activity, t.zone_id, z.name, t.heartbeat_interval
        ORDER BY is_online DESC, COALESCE(t.alias, t.sn)
    """)).fetchall()
    return {"success": True, "data": _rows(rows)}


_DOOR_COLS = """
    d.id, d.name AS door_name, d.terminal_sn, d.acc_level_id,
    d.controller_id, d.port,
    (SELECT name FROM access_controllers ac WHERE ac.id = d.controller_id) AS controller_name,
    d.relay_time, d.door_sensor_type, d.alarm_delay, d.open_duration,
    d.anti_passback, d.first_card_open, d.interlock_group,
    d.emergency_action, d.mustering_mode, d.fire_linkage,
    d.created_at, d.updated_at,
    COALESCE(t.alias, t.sn)        AS terminal_name,
    t.last_activity                AS terminal_last_seen,
    CASE WHEN t.state = 1
              AND t.last_activity IS NOT NULL
              AND t.last_activity > NOW() - make_interval(secs =>
                      GREATEST(COALESCE(t.heartbeat_interval, 30) * 5, 90)::float)
         THEN true ELSE false END  AS is_online
"""

@router.get("/doors/")
async def get_doors(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text(f"""
        SELECT {_DOOR_COLS}
        FROM acc_door d
        LEFT JOIN iclock_terminal t ON t.sn = d.terminal_sn
        ORDER BY d.id
    """)).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.post("/doors")
async def create_door(body: DoorBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # A door belongs to a controller port (preferred) or a legacy standalone terminal.
    if body.controller_id is not None:
        ctrl = db.execute(text("SELECT id FROM access_controllers WHERE id = :id"),
                          {"id": body.controller_id}).fetchone()
        if not ctrl:
            raise HTTPException(404, "Controller not found")
        if body.port is None:
            raise HTTPException(400, "Select the controller port for this door")
    elif body.terminal_sn:
        term = db.execute(text("SELECT sn FROM iclock_terminal WHERE sn = :sn"),
                          {"sn": body.terminal_sn}).fetchone()
        if not term:
            raise HTTPException(404, "Terminal not found")
    else:
        raise HTTPException(400, "Select a controller and port (or a terminal) for the door")
    row = db.execute(text("""
        INSERT INTO acc_door
          (name, terminal_sn, controller_id, port, relay_time, door_sensor_type, alarm_delay,
           open_duration, anti_passback, first_card_open, interlock_group,
           emergency_action, mustering_mode, fire_linkage)
        VALUES
          (:name, :tsn, :cid, :port, :rt, :dst, :ad, :od, :apb, :fco, :ig, :ea, :mm, :fl)
        RETURNING *
    """), {
        "name": body.door_name, "tsn": body.terminal_sn,
        "cid": body.controller_id, "port": body.port,
        "rt": body.relay_time, "dst": body.door_sensor_type,
        "ad": body.alarm_delay, "od": body.open_duration,
        "apb": body.anti_passback, "fco": body.first_card_open,
        "ig": body.interlock_group, "ea": body.emergency_action,
        "mm": body.mustering_mode, "fl": body.fire_linkage,
    }).fetchone()
    db.commit()
    d = dict(row._mapping); d["door_name"] = d["name"]
    return {"success": True, "data": d}


@router.get("/doors/{door_id}")
async def get_door(door_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text(f"""
        SELECT {_DOOR_COLS} FROM acc_door d
        LEFT JOIN iclock_terminal t ON t.sn = d.terminal_sn
        WHERE d.id = :id
    """), {"id": door_id}).fetchone()
    if not row:
        raise HTTPException(404, "Door not found")
    return {"success": True, "data": dict(row._mapping)}


@router.put("/doors/{door_id}")
async def update_door(door_id: int, body: DoorBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT id FROM acc_door WHERE id = :id"), {"id": door_id}).fetchone()
    if not row:
        raise HTTPException(404, "Door not found")
    row = db.execute(text("""
        UPDATE acc_door SET
          name=:name, controller_id=:cid, port=:port,
          relay_time=:rt, door_sensor_type=:dst, alarm_delay=:ad,
          open_duration=:od, anti_passback=:apb, first_card_open=:fco,
          interlock_group=:ig, emergency_action=:ea, mustering_mode=:mm,
          fire_linkage=:fl, updated_at=NOW()
        WHERE id=:id RETURNING *
    """), {
        "name": body.door_name, "cid": body.controller_id, "port": body.port,
        "rt": body.relay_time, "dst": body.door_sensor_type,
        "ad": body.alarm_delay, "od": body.open_duration, "apb": body.anti_passback,
        "fco": body.first_card_open, "ig": body.interlock_group, "ea": body.emergency_action,
        "mm": body.mustering_mode, "fl": body.fire_linkage, "id": door_id,
    }).fetchone()
    db.commit()
    d = dict(row._mapping); d["door_name"] = d["name"]
    return {"success": True, "data": d}


@router.delete("/doors/{door_id}")
async def delete_door(
    door_id: int,
    force: bool = Query(False, description="Also delete associated access events"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    row = db.execute(text("SELECT COUNT(*) AS cnt FROM acc_event WHERE door_id=:id"), {"id": door_id}).fetchone()
    event_count = row._mapping["cnt"] if row else 0
    if event_count > 0 and not force:
        raise HTTPException(400, f"Cannot delete door with {event_count} access event(s). Use force=true to delete anyway.")
    if event_count > 0:
        db.execute(text("DELETE FROM acc_event WHERE door_id=:id"), {"id": door_id})
    db.execute(text("DELETE FROM acc_level_door WHERE door_id=:id"), {"id": door_id})
    db.execute(text("DELETE FROM acc_interlock_door WHERE door_id=:id"), {"id": door_id})
    db.execute(text("DELETE FROM acc_door WHERE id=:id"), {"id": door_id})
    db.commit()
    return {"success": True, "message": "Door deleted"}


@router.post("/doors/{door_id}/open")
async def remote_open_door(door_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Require explicit access-control permission — authentication alone is not enough
    if not getattr(current_user, "is_superuser", False):
        perm = db.execute(text("""
            SELECT 1 FROM auth_user_role ur
            JOIN auth_role r ON r.id = ur.role_id
            JOIN auth_role_permission rp ON rp.role_id = r.id
            JOIN auth_permission p ON p.id = rp.permission_id
            WHERE ur.user_id = :uid
              AND p.codename IN ('access_control.change', 'access_control.manage', 'access_control.open_door')
            LIMIT 1
        """), {"uid": current_user.id}).fetchone()
        if not perm:
            raise HTTPException(status_code=403, detail="Permission denied: access_control.change required")

    door = db.execute(text("SELECT id, name, terminal_sn FROM acc_door WHERE id=:id"), {"id": door_id}).fetchone()
    if not door:
        raise HTTPException(404, "Door not found")
    db.execute(text("""
        INSERT INTO acc_event (event_time, terminal_sn, door_id, emp_code, emp_name, event_type, description)
        VALUES (NOW(), :sn, :did, :ec, :en, 1, 'Remote door open')
    """), {
        "sn": door._mapping["terminal_sn"],
        "did": door_id,
        "ec": getattr(current_user, "username", "system"),
        "en": getattr(current_user, "first_name", "") + " " + getattr(current_user, "last_name", ""),
    })
    db.commit()
    return {"success": True, "message": "Door open command sent"}


def _require_ac_permission(current_user, db) -> None:
    """Raise 403 unless caller is superuser or has access_control.change."""
    if getattr(current_user, "is_superuser", False):
        return
    perm = db.execute(text("""
        SELECT 1 FROM auth_user_role ur
        JOIN auth_role r ON r.id = ur.role_id
        JOIN auth_role_permission rp ON rp.role_id = r.id
        JOIN auth_permission p ON p.id = rp.permission_id
        WHERE ur.user_id = :uid
          AND p.codename IN ('access_control.change', 'access_control.manage')
        LIMIT 1
    """), {"uid": current_user.id}).fetchone()
    if not perm:
        raise HTTPException(status_code=403, detail="Permission denied: access_control.change required")


@router.post("/doors/{door_id}/sync")
async def sync_door(door_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require_ac_permission(current_user, db)
    row = db.execute(text("SELECT id FROM acc_door WHERE id=:id"), {"id": door_id}).fetchone()
    if not row:
        raise HTTPException(404, "Door not found")
    return {"success": True, "message": "Door configuration sync queued"}


@router.post("/doors/set-mustering-mode")
async def set_mustering_mode(body: MusteringBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require_ac_permission(current_user, db)
    if body.door_ids:
        # Parameterized: use ANY(:ids) to avoid f-string SQL injection
        db.execute(
            text("UPDATE acc_door SET mustering_mode=:mm WHERE id = ANY(:ids)"),
            {"mm": body.mustering_mode, "ids": list(body.door_ids)},
        )
    db.commit()
    return {"success": True, "message": f"Mustering mode {'enabled' if body.mustering_mode else 'disabled'} on {len(body.door_ids)} doors"}


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONS / EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/events/")
async def get_events(
    skip: int = 0,
    limit: int = 100,
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    door_id: Optional[int] = Query(None),
    emp_code: Optional[str] = Query(None),
    event_type: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    filters, params = [], {"skip": skip, "limit": limit}
    if start_time:  filters.append("e.event_time >= :start_time");  params["start_time"]  = start_time
    if end_time:    filters.append("e.event_time <= :end_time");    params["end_time"]    = end_time
    if door_id:     filters.append("e.door_id = :door_id");         params["door_id"]     = door_id
    if emp_code:    filters.append("e.emp_code = :emp_code");        params["emp_code"]    = emp_code
    if event_type is not None:
        filters.append("e.event_type = :event_type"); params["event_type"] = event_type

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = db.execute(text(f"""
        SELECT e.*, d.name AS door_name,
               COALESCE(e.photo_url, pe.photo) AS employee_photo
        FROM acc_event e
        LEFT JOIN acc_door d ON d.id = e.door_id
        LEFT JOIN personnel_employee pe ON pe.emp_code = e.emp_code
        {where}
        ORDER BY e.event_time DESC
        OFFSET :skip LIMIT :limit
    """), params).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.websocket("/events/ws")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    # Use a SHORT-LIVED session per poll — never hold a pooled DB connection (and an
    # open transaction) for the whole WS lifetime, which exhausts the pool and leaves
    # "idle in transaction" connections when several clients are connected.
    from ..core.database import SessionLocal
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                pass
            _db = SessionLocal()
            try:
                rows = _db.execute(text("""
                    SELECT e.*, d.name AS door_name,
                           COALESCE(e.photo_url, pe.photo) AS employee_photo
                    FROM acc_event e
                    LEFT JOIN acc_door d ON d.id = e.door_id
                    LEFT JOIN personnel_employee pe ON pe.emp_code = e.emp_code
                    ORDER BY e.event_time DESC LIMIT 20
                """)).fetchall()
                data = _rows(rows)
            finally:
                _db.close()
            for item in data:
                for k, v in item.items():
                    if isinstance(v, datetime):
                        item[k] = v.isoformat()
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# ANTI-PASSBACK
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/antipassback/")
async def get_antipassback(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT d.id AS door_id, d.name AS door_name, d.anti_passback, d.terminal_sn
        FROM acc_door d ORDER BY d.id
    """)).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.put("/antipassback")
async def update_antipassback(
    settings: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_ac_permission(current_user, db)
    for s in settings:
        db.execute(text("UPDATE acc_door SET anti_passback=:apb WHERE id=:id"),
                   {"apb": s.get("anti_passback", 0), "id": s["door_id"]})
    db.commit()
    return {"success": True, "message": "Anti-passback settings updated"}


# ══════════════════════════════════════════════════════════════════════════════
# FIRST-CARD OPEN
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/first-card/")
async def get_first_card(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT d.id AS door_id, d.name AS door_name, d.first_card_open, d.terminal_sn,
               fc.emp_code AS last_first_card_emp, fc.first_card_time AS last_first_card_time,
               tz.timezone_name AS first_card_timezone
        FROM acc_door d
        LEFT JOIN LATERAL (
            SELECT * FROM acc_first_card WHERE door_id = d.id ORDER BY created_at DESC LIMIT 1
        ) fc ON true
        LEFT JOIN acc_timezone tz ON tz.id = fc.timezone_id
        ORDER BY d.id
    """)).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.put("/first-card")
async def update_first_card(
    settings: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    for s in settings:
        db.execute(text("UPDATE acc_door SET first_card_open=:fco WHERE id=:id"),
                   {"fco": s.get("first_card_open", False), "id": s["door_id"]})
    db.commit()
    return {"success": True, "message": "First-card open settings updated"}


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-CARD OPEN
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/multi-card/")
async def get_multi_card(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT mc.id, mc.door_id, mc.min_cards, mc.created_at, mc.updated_at,
               d.name AS door_name,
               COALESCE(
                 json_agg(json_build_object('id', mu.id, 'emp_code', mu.emp_code))
                 FILTER (WHERE mu.id IS NOT NULL), '[]'
               ) AS members
        FROM acc_multi_card mc
        JOIN acc_door d ON d.id = mc.door_id
        LEFT JOIN acc_multi_card_user mu ON mu.multi_card_id = mc.id
        GROUP BY mc.id, d.name
        ORDER BY mc.id
    """)).fetchall()
    return {"success": True, "data": _rows(rows)}


@router.post("/multi-card")
async def create_multi_card(body: MultiCardBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    door = db.execute(text("SELECT id FROM acc_door WHERE id=:id"), {"id": body.door_id}).fetchone()
    if not door:
        raise HTTPException(404, "Door not found")
    mc = db.execute(text("""
        INSERT INTO acc_multi_card (door_id, min_cards) VALUES (:did, :mc) RETURNING *
    """), {"did": body.door_id, "mc": body.min_cards}).fetchone()
    for code in body.emp_codes:
        db.execute(text("INSERT INTO acc_multi_card_user (multi_card_id, emp_code) VALUES (:mid, :ec)"),
                   {"mid": mc._mapping["id"], "ec": code})
    db.commit()
    return {"success": True, "data": dict(mc._mapping)}


@router.put("/multi-card/{mc_id}")
async def update_multi_card(mc_id: int, body: MultiCardBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    mc = db.execute(text("SELECT id FROM acc_multi_card WHERE id=:id"), {"id": mc_id}).fetchone()
    if not mc:
        raise HTTPException(404, "Multi-card config not found")
    db.execute(text("UPDATE acc_multi_card SET min_cards=:mc, updated_at=NOW() WHERE id=:id"),
               {"mc": body.min_cards, "id": mc_id})
    db.execute(text("DELETE FROM acc_multi_card_user WHERE multi_card_id=:id"), {"id": mc_id})
    for code in body.emp_codes:
        db.execute(text("INSERT INTO acc_multi_card_user (multi_card_id, emp_code) VALUES (:mid, :ec)"),
                   {"mid": mc_id, "ec": code})
    db.commit()
    return {"success": True, "message": "Multi-card config updated"}


@router.delete("/multi-card/{mc_id}")
async def delete_multi_card(mc_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.execute(text("DELETE FROM acc_multi_card_user WHERE multi_card_id=:id"), {"id": mc_id})
    db.execute(text("DELETE FROM acc_multi_card WHERE id=:id"), {"id": mc_id})
    db.commit()
    return {"success": True, "message": "Multi-card config deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# INTERLOCK
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/interlock/")
async def get_interlock_groups(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    groups = db.execute(text("SELECT * FROM acc_interlock_group ORDER BY id")).fetchall()
    result = []
    for g in groups:
        gd = dict(g._mapping)
        doors = db.execute(text("""
            SELECT ild.id AS assignment_id, d.id AS door_id, d.name AS door_name, d.terminal_sn
            FROM acc_interlock_door ild
            JOIN acc_door d ON d.id = ild.door_id
            WHERE ild.group_id = :gid
        """), {"gid": gd["id"]}).fetchall()
        gd["doors"] = _rows(doors)
        result.append(gd)
    return {"success": True, "data": result}


@router.post("/interlock")
async def create_interlock_group(body: InterlockBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if len(body.door_ids) < 2:
        raise HTTPException(400, "Interlock group requires at least 2 doors")
    grp = db.execute(text("""
        INSERT INTO acc_interlock_group (group_name, description) VALUES (:n, :d) RETURNING *
    """), {"n": body.group_name, "d": body.description}).fetchone()
    for did in body.door_ids:
        db.execute(text("INSERT INTO acc_interlock_door (group_id, door_id) VALUES (:g, :d)"),
                   {"g": grp._mapping["id"], "d": did})
    db.commit()
    return {"success": True, "data": dict(grp._mapping)}


@router.put("/interlock/{group_id}")
async def update_interlock_group(group_id: int, body: InterlockBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    grp = db.execute(text("SELECT id FROM acc_interlock_group WHERE id=:id"), {"id": group_id}).fetchone()
    if not grp:
        raise HTTPException(404, "Interlock group not found")
    if len(body.door_ids) < 2:
        raise HTTPException(400, "Interlock group requires at least 2 doors")
    db.execute(text("UPDATE acc_interlock_group SET group_name=:n, description=:d WHERE id=:id"),
               {"n": body.group_name, "d": body.description, "id": group_id})
    db.execute(text("DELETE FROM acc_interlock_door WHERE group_id=:id"), {"id": group_id})
    for did in body.door_ids:
        db.execute(text("INSERT INTO acc_interlock_door (group_id, door_id) VALUES (:g, :d)"),
                   {"g": group_id, "d": did})
    db.commit()
    return {"success": True, "message": "Interlock group updated"}


@router.delete("/interlock/{group_id}")
async def delete_interlock_group(group_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.execute(text("DELETE FROM acc_interlock_door WHERE group_id=:id"), {"id": group_id})
    db.execute(text("DELETE FROM acc_interlock_group WHERE id=:id"), {"id": group_id})
    db.commit()
    return {"success": True, "message": "Interlock group deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# LINKAGE
# ══════════════════════════════════════════════════════════════════════════════

INPUT_LABELS  = {0: "Door Sensor", 1: "Auxiliary Input", 2: "Fire Panel"}
OUTPUT_LABELS = {0: "Open Door", 1: "Alarm", 2: "Siren", 3: "Strobe"}

@router.get("/linkage/")
async def get_linkages(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT l.*, d.name AS output_door_name
        FROM acc_linkage l
        LEFT JOIN acc_door d ON d.id = l.output_door_id
        ORDER BY l.id
    """)).fetchall()
    data = _rows(rows)
    for item in data:
        item["input_type_label"]  = INPUT_LABELS.get(item.get("input_type"), "Unknown")
        item["output_action_label"] = OUTPUT_LABELS.get(item.get("output_action"), "Unknown")
    return {"success": True, "data": data}


@router.post("/linkage")
async def create_linkage(body: LinkageBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("""
        INSERT INTO acc_linkage (terminal_sn, input_type, output_action, output_door_id, output_terminal_sn)
        VALUES (:tsn, :it, :oa, :odid, :otsn) RETURNING *
    """), {
        "tsn": body.terminal_sn, "it": body.input_type, "oa": body.output_action,
        "odid": body.output_door_id, "otsn": body.output_terminal_sn,
    }).fetchone()
    db.commit()
    return {"success": True, "data": dict(row._mapping)}


@router.put("/linkage/{linkage_id}")
async def update_linkage(linkage_id: int, body: LinkageBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT id FROM acc_linkage WHERE id=:id"), {"id": linkage_id}).fetchone()
    if not row:
        raise HTTPException(404, "Linkage not found")
    db.execute(text("""
        UPDATE acc_linkage SET terminal_sn=:tsn, input_type=:it, output_action=:oa,
               output_door_id=:odid, output_terminal_sn=:otsn WHERE id=:id
    """), {
        "tsn": body.terminal_sn, "it": body.input_type, "oa": body.output_action,
        "odid": body.output_door_id, "otsn": body.output_terminal_sn, "id": linkage_id,
    })
    db.commit()
    return {"success": True, "message": "Linkage updated"}


@router.delete("/linkage/{linkage_id}")
async def delete_linkage(linkage_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.execute(text("DELETE FROM acc_linkage WHERE id=:id"), {"id": linkage_id})
    db.commit()
    return {"success": True, "message": "Linkage deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# EMERGENCY
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/emergency/status/")
async def get_emergency_status(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    locked = db.execute(text(
        "SELECT COUNT(*) AS cnt FROM acc_event WHERE event_type=6 AND event_time > NOW() - INTERVAL '1 hour'"
    )).fetchone()._mapping["cnt"]
    unlocked = db.execute(text(
        "SELECT COUNT(*) AS cnt FROM acc_event WHERE event_type=5 AND event_time > NOW() - INTERVAL '1 hour'"
    )).fetchone()._mapping["cnt"]
    return {"success": True, "data": {
        "emergency_active": locked > 0,
        "emergency_locks": int(locked),
        "fire_unlocks": int(unlocked),
    }}


@router.post("/emergency/action")
async def emergency_action(body: EmergencyBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if body.action not in ("lock", "unlock"):
        raise HTTPException(400, "Action must be 'lock' or 'unlock'")
    event_type = 6 if body.action == "lock" else 5

    door_ids = body.door_ids
    if not door_ids:
        door_ids = [r._mapping["id"] for r in db.execute(text("SELECT id FROM acc_door")).fetchall()]

    for did in door_ids:
        door = db.execute(text("SELECT name, terminal_sn FROM acc_door WHERE id=:id"), {"id": did}).fetchone()
        if not door:
            continue
        db.execute(text("""
            INSERT INTO acc_event (event_time, terminal_sn, door_id, emp_code, emp_name, event_type, description)
            VALUES (NOW(), :sn, :did, :ec, :en, :et, :desc)
        """), {
            "sn": door._mapping["terminal_sn"],
            "did": did,
            "ec": getattr(current_user, "username", "system"),
            "en": getattr(current_user, "first_name", ""),
            "et": event_type,
            "desc": f"Emergency {body.action}" + (f": {body.reason}" if body.reason else ""),
        })

    db.commit()
    return {"success": True, "message": f"Emergency {body.action} applied to {len(door_ids)} doors"}


class EmergencyLockBody(BaseModel):
    reason: str


@router.post("/emergency/lock-all")
async def emergency_lock_all(
    body: EmergencyLockBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=403,
            detail="Emergency lock-all requires superuser privileges",
        )
    if not body.reason or len(body.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="A reason of at least 5 characters is required")

    # Delegate to EmergencyService so an EmergencyEvent row is created, the
    # lockdown is auditable from the emergency dashboard, and device RELAY
    # commands are queued — the old implementation only wrote acc_event rows.
    result = await EmergencyService().execute_lockdown(
        scope="global",
        action="lock",
        reason=body.reason.strip(),
        initiated_by=getattr(current_user, "id", None),
        db=db,
    )
    return {"success": True, "message": result.get("message", "Emergency lock applied"), **result}


class EmergencyUnlockBody(BaseModel):
    reason: str


@router.post("/emergency/unlock-all")
async def emergency_unlock_all(
    body: EmergencyUnlockBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=403,
            detail="Emergency unlock-all requires superuser privileges",
        )
    if not body.reason or len(body.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="A reason of at least 5 characters is required")

    result = await EmergencyService().execute_lockdown(
        scope="global",
        action="unlock",
        reason=body.reason.strip(),
        initiated_by=getattr(current_user, "id", None),
        db=db,
    )
    return {"success": True, "message": result.get("message", "Emergency unlock applied"), **result}


# ══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/reports/events/")
async def events_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str]   = Query(None),
    door_ids: Optional[str]   = Query(None),
    event_types: Optional[str]= Query(None),
    emp_codes: Optional[str]  = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    filters, params = [], {}
    if start_date: filters.append("e.event_time >= :sd");  params["sd"] = start_date
    if end_date:   filters.append("e.event_time <= :ed");  params["ed"] = end_date
    if door_ids:
        ids = [int(x) for x in door_ids.split(",") if x.strip()]
        if ids: filters.append(f"e.door_id IN ({','.join(str(i) for i in ids)})")
    if event_types:
        types = [int(x) for x in event_types.split(",") if x.strip()]
        if types: filters.append(f"e.event_type IN ({','.join(str(t) for t in types)})")
    if emp_codes:
        codes = [c.strip() for c in emp_codes.split(",") if c.strip()]
        if codes:
            quoted = ",".join(f"'{c}'" for c in codes)
            filters.append(f"e.emp_code IN ({quoted})")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = db.execute(text(f"""
        SELECT e.*, d.name AS door_name FROM acc_event e
        LEFT JOIN acc_door d ON d.id = e.door_id
        {where} ORDER BY e.event_time DESC LIMIT 5000
    """), params).fetchall()

    data = _rows(rows)
    for item in data:
        for k, v in item.items():
            if isinstance(v, datetime):
                item[k] = v.isoformat()

    granted = sum(1 for r in data if r.get("event_type") == 0)
    denied  = sum(1 for r in data if r.get("event_type") in (2, 3, 4))

    return {"success": True, "data": {
        "total_events": len(data),
        "access_granted": granted,
        "access_denied": denied,
        "events": data,
        "generated_at": datetime.utcnow().isoformat(),
    }}


@router.get("/reports/door-status/")
async def door_status_report(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    doors = db.execute(text(f"""
        SELECT {_DOOR_COLS}
        FROM acc_door d LEFT JOIN iclock_terminal t ON t.sn = d.terminal_sn
        ORDER BY d.id
    """)).fetchall()
    data = _rows(doors)
    for item in data:
        last = db.execute(text("""
            SELECT event_time, event_type FROM acc_event WHERE door_id=:id
            ORDER BY event_time DESC LIMIT 1
        """), {"id": item["id"]}).fetchone()
        item["last_event"] = dict(last._mapping) if last else None

    return {"success": True, "data": {
        "total_doors": len(data),
        "online_doors": sum(1 for d in data if d.get("is_online")),
        "doors": data,
        "generated_at": datetime.utcnow().isoformat(),
    }}


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard/")
async def get_dashboard(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        total_doors  = db.execute(text("SELECT COUNT(*) AS c FROM acc_door")).fetchone()._mapping["c"]
        online_doors = db.execute(text("""
            SELECT COUNT(*) AS c FROM acc_door d
            JOIN iclock_terminal t ON t.sn = d.terminal_sn
            WHERE t.state = 1
              AND t.last_activity IS NOT NULL
              AND t.last_activity > NOW() - make_interval(secs =>
                      GREATEST(COALESCE(t.heartbeat_interval, 30) * 5, 90)::float)
        """)).fetchone()._mapping["c"]
        total_levels = db.execute(text("SELECT COUNT(*) AS c FROM acc_level")).fetchone()._mapping["c"]
        today_events = db.execute(text(
            "SELECT COUNT(*) AS c FROM acc_event WHERE event_time::date = CURRENT_DATE"
        )).fetchone()._mapping["c"]
        granted_today = db.execute(text(
            "SELECT COUNT(*) AS c FROM acc_event WHERE event_time::date=CURRENT_DATE AND event_type=0"
        )).fetchone()._mapping["c"]
        denied_today = db.execute(text(
            "SELECT COUNT(*) AS c FROM acc_event WHERE event_time::date=CURRENT_DATE AND event_type IN (2,3,4)"
        )).fetchone()._mapping["c"]
        emergency_events = db.execute(text(
            "SELECT COUNT(*) AS c FROM acc_event WHERE event_time > NOW()-INTERVAL '24h' AND event_type IN (5,6)"
        )).fetchone()._mapping["c"]
        mustering_events = db.execute(text(
            "SELECT COUNT(*) AS c FROM acc_event WHERE event_time > NOW()-INTERVAL '24h' AND event_type=7"
        )).fetchone()._mapping["c"]
        total_users = db.execute(text(
            "SELECT COUNT(DISTINCT emp_code) AS c FROM acc_userauthorize"
        )).fetchone()._mapping["c"]

        recent_events = db.execute(text("""
            SELECT e.id, e.event_time, e.event_type, e.emp_code, e.emp_name, e.terminal_sn,
                   d.name AS door_name
            FROM acc_event e LEFT JOIN acc_door d ON d.id=e.door_id
            ORDER BY e.event_time DESC LIMIT 10
        """)).fetchall()
        events_data = _rows(recent_events)
        for item in events_data:
            if isinstance(item.get("event_time"), datetime):
                item["event_time"] = item["event_time"].isoformat()

        return {"success": True, "data": {
            "door_statistics": {
                "total": int(total_doors),
                "online": int(online_doors),
                "offline": int(total_doors - online_doors),
                "online_percentage": round((online_doors / total_doors * 100) if total_doors else 0, 1),
            },
            "access_levels": {"total": int(total_levels)},
            "today_activity": {
                "total_events":    int(today_events),
                "access_granted":  int(granted_today),
                "access_denied":   int(denied_today),
                "emergency_events":int(emergency_events),
                "mustering_events":int(mustering_events),
            },
            "active_users": int(total_users),
            "recent_events": events_data,
            "system_health": {
                "database": "healthy",
                "adms_service": "running",
                "last_check": datetime.utcnow().isoformat(),
            },
        }}
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# GUARD TOUR
# ══════════════════════════════════════════════════════════════════════════════

class GuardTourBody(BaseModel):
    tour_name: str
    description: Optional[str] = None
    interval_minutes: int = 60
    is_active: bool = True
    checkpoints: List[Dict[str, Any]] = []  # [{door_id, sequence_order, time_window_minutes}]

class GuardTourScheduleBody(BaseModel):
    tour_id: int
    guard_emp_code: str
    scheduled_start: str   # ISO datetime
    scheduled_end: Optional[str] = None

class GuardTourLogBody(BaseModel):
    schedule_id: int
    checkpoint_id: int
    emp_code: str
    scan_time: str         # ISO datetime


@router.get("/guard-tour/")
async def get_guard_tours(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    tours = db.execute(text("SELECT * FROM acc_guard_tour ORDER BY id")).fetchall()
    result = []
    for t in tours:
        td = dict(t._mapping)
        cps = db.execute(text("""
            SELECT gtc.*, d.name AS door_name
            FROM acc_guard_tour_checkpoint gtc
            LEFT JOIN acc_door d ON d.id = gtc.door_id
            WHERE gtc.tour_id = :tid ORDER BY gtc.sequence_order
        """), {"tid": td["id"]}).fetchall()
        td["checkpoints"] = _rows(cps)
        result.append(td)
    return {"success": True, "data": result}


@router.post("/guard-tour")
async def create_guard_tour(body: GuardTourBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("""
        INSERT INTO acc_guard_tour (tour_name, description, interval_minutes, is_active)
        VALUES (:n, :d, :im, :ia) RETURNING *
    """), {"n": body.tour_name, "d": body.description, "im": body.interval_minutes, "ia": body.is_active}).fetchone()
    tid = row._mapping["id"]
    for cp in body.checkpoints:
        db.execute(text("""
            INSERT INTO acc_guard_tour_checkpoint (tour_id, door_id, sequence_order, time_window_minutes)
            VALUES (:tid, :did, :seq, :tw)
        """), {"tid": tid, "did": cp["door_id"], "seq": cp["sequence_order"],
               "tw": cp.get("time_window_minutes", 10)})
    db.commit()
    return {"success": True, "data": dict(row._mapping)}


@router.put("/guard-tour/{tour_id}")
async def update_guard_tour(tour_id: int, body: GuardTourBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not db.execute(text("SELECT id FROM acc_guard_tour WHERE id=:id"), {"id": tour_id}).fetchone():
        raise HTTPException(404, "Tour not found")
    db.execute(text("""
        UPDATE acc_guard_tour SET tour_name=:n, description=:d, interval_minutes=:im, is_active=:ia WHERE id=:id
    """), {"n": body.tour_name, "d": body.description, "im": body.interval_minutes, "ia": body.is_active, "id": tour_id})
    db.execute(text("DELETE FROM acc_guard_tour_checkpoint WHERE tour_id=:id"), {"id": tour_id})
    for cp in body.checkpoints:
        db.execute(text("""
            INSERT INTO acc_guard_tour_checkpoint (tour_id, door_id, sequence_order, time_window_minutes)
            VALUES (:tid, :did, :seq, :tw)
        """), {"tid": tour_id, "did": cp["door_id"], "seq": cp["sequence_order"],
               "tw": cp.get("time_window_minutes", 10)})
    db.commit()
    return {"success": True, "message": "Tour updated"}


@router.delete("/guard-tour/{tour_id}")
async def delete_guard_tour(tour_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.execute(text("DELETE FROM acc_guard_tour_checkpoint WHERE tour_id=:id"), {"id": tour_id})
    db.execute(text("DELETE FROM acc_guard_tour WHERE id=:id"), {"id": tour_id})
    db.commit()
    return {"success": True, "message": "Tour deleted"}


@router.get("/guard-tour/schedules/")
async def get_tour_schedules(
    tour_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    q = """
        SELECT s.*, t.tour_name,
               TRIM(COALESCE(e.first_name,'') || ' ' || COALESCE(e.last_name,'')) AS guard_name_full
        FROM acc_guard_tour_schedule s
        JOIN acc_guard_tour t ON t.id = s.tour_id
        LEFT JOIN personnel_employee e ON e.emp_code = s.guard_emp_code
    """
    params: dict = {}
    if tour_id:
        q += " WHERE s.tour_id = :tid"
        params["tid"] = tour_id
    q += " ORDER BY s.scheduled_start DESC LIMIT 200"
    rows = db.execute(text(q), params).fetchall()
    data = _rows(rows)
    for item in data:
        for k, v in item.items():
            if isinstance(v, datetime):
                item[k] = v.isoformat()
    return {"success": True, "data": data}


@router.post("/guard-tour/schedules")
async def create_tour_schedule(body: GuardTourScheduleBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    emp = db.execute(text(
        "SELECT TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) AS name FROM personnel_employee WHERE emp_code=:c"
    ), {"c": body.guard_emp_code}).fetchone()
    guard_name = emp._mapping["name"] if emp else body.guard_emp_code
    row = db.execute(text("""
        INSERT INTO acc_guard_tour_schedule (tour_id, guard_emp_code, guard_name, scheduled_start, scheduled_end, status)
        VALUES (:tid, :ec, :gn, :ss, :se, 'pending') RETURNING *
    """), {"tid": body.tour_id, "ec": body.guard_emp_code, "gn": guard_name,
           "ss": body.scheduled_start, "se": body.scheduled_end}).fetchone()
    db.commit()
    d = dict(row._mapping)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return {"success": True, "data": d}


@router.post("/guard-tour/log")
async def log_guard_scan(body: GuardTourLogBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    sched = db.execute(text("SELECT id, tour_id FROM acc_guard_tour_schedule WHERE id=:id"), {"id": body.schedule_id}).fetchone()
    if not sched:
        raise HTTPException(404, "Schedule not found")
    db.execute(text("""
        INSERT INTO acc_guard_tour_log (schedule_id, checkpoint_id, emp_code, scan_time, is_on_time)
        VALUES (:sid, :cid, :ec, :st, TRUE)
    """), {"sid": body.schedule_id, "cid": body.checkpoint_id, "ec": body.emp_code, "st": body.scan_time})
    # Auto-update schedule status to in_progress
    db.execute(text("UPDATE acc_guard_tour_schedule SET status='in_progress' WHERE id=:id AND status='pending'"),
               {"id": body.schedule_id})
    db.commit()
    return {"success": True, "message": "Scan logged"}


@router.get("/guard-tour/schedules/{schedule_id}/compliance/")
async def get_tour_compliance(schedule_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    sched = db.execute(text("""
        SELECT s.*, t.tour_name FROM acc_guard_tour_schedule s
        JOIN acc_guard_tour t ON t.id = s.tour_id WHERE s.id=:id
    """), {"id": schedule_id}).fetchone()
    if not sched:
        raise HTTPException(404, "Schedule not found")
    sd = dict(sched._mapping)
    for k, v in sd.items():
        if isinstance(v, datetime): sd[k] = v.isoformat()

    checkpoints = db.execute(text("""
        SELECT gtc.*, d.name AS door_name FROM acc_guard_tour_checkpoint gtc
        LEFT JOIN acc_door d ON d.id = gtc.door_id
        WHERE gtc.tour_id = :tid ORDER BY gtc.sequence_order
    """), {"tid": sd["tour_id"]}).fetchall()

    logs = db.execute(text(
        "SELECT * FROM acc_guard_tour_log WHERE schedule_id=:sid ORDER BY scan_time"
    ), {"sid": schedule_id}).fetchall()
    scanned_cp_ids = {r._mapping["checkpoint_id"] for r in logs}

    cp_list = []
    for cp in checkpoints:
        cpd = dict(cp._mapping)
        cpd["scanned"] = cpd["id"] in scanned_cp_ids
        cp_list.append(cpd)

    total = len(cp_list)
    scanned = sum(1 for c in cp_list if c["scanned"])
    return {"success": True, "data": {
        "schedule": sd,
        "checkpoints": cp_list,
        "compliance_pct": round((scanned / total * 100) if total else 0, 1),
        "scanned": scanned,
        "total": total,
    }}


# ══════════════════════════════════════════════════════════════════════════════
# VISITOR ACCESS
# ══════════════════════════════════════════════════════════════════════════════

class VisitorBody(BaseModel):
    emp_code: str
    level_id: Optional[int] = None
    door_ids: List[int] = []
    valid_from: str
    valid_to: str
    note: Optional[str] = None


@router.get("/visitors/")
async def get_visitors(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Auto-set is_revoked=False for past-valid_to records (derive expiry at query time)
    rows = db.execute(text("""
        SELECT v.id, v.emp_code, v.level_id, v.door_ids, v.valid_from, v.valid_to,
               v.note, v.is_revoked, v.created_at,
               l.name AS level_name,
               TRIM(COALESCE(e.first_name,'') || ' ' || COALESCE(e.last_name,'')) AS emp_name
        FROM acc_visitor_access v
        LEFT JOIN acc_level l ON l.id = v.level_id
        LEFT JOIN personnel_employee e ON e.emp_code = v.emp_code
        ORDER BY v.created_at DESC
    """)).fetchall()
    data = _rows(rows)
    for item in data:
        for k, v in item.items():
            if isinstance(v, datetime): item[k] = v.isoformat()
    return {"success": True, "data": data}


@router.post("/visitors")
async def create_visitor(body: VisitorBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("""
        INSERT INTO acc_visitor_access
          (emp_code, level_id, door_ids, valid_from, valid_to, note, is_revoked, status)
        VALUES (:ec, :lid, CAST(:dids AS jsonb), :vf, :vt, :note, false, 'active') RETURNING id
    """), {
        "ec": body.emp_code, "lid": body.level_id, "dids": json.dumps(body.door_ids),
        "vf": body.valid_from, "vt": body.valid_to, "note": body.note,
    }).fetchone()
    db.commit()
    return {"success": True, "data": {"id": row._mapping["id"]}}


@router.put("/visitors/{visitor_id}")
async def update_visitor(visitor_id: int, body: VisitorBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not db.execute(text("SELECT id FROM acc_visitor_access WHERE id=:id"), {"id": visitor_id}).fetchone():
        raise HTTPException(404, "Visitor record not found")
    db.execute(text("""
        UPDATE acc_visitor_access
        SET level_id=:lid, door_ids=CAST(:dids AS jsonb), valid_from=:vf, valid_to=:vt, note=:note
        WHERE id=:id
    """), {
        "lid": body.level_id, "dids": json.dumps(body.door_ids),
        "vf": body.valid_from, "vt": body.valid_to, "note": body.note, "id": visitor_id,
    })
    db.commit()
    return {"success": True, "message": "Visitor updated"}


@router.patch("/visitors/{visitor_id}/revoke")
async def revoke_visitor(visitor_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.execute(text("UPDATE acc_visitor_access SET is_revoked=true, status='revoked' WHERE id=:id"), {"id": visitor_id})
    db.commit()
    return {"success": True, "message": "Visitor access revoked"}


@router.delete("/visitors/{visitor_id}")
async def delete_visitor(visitor_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.execute(text("DELETE FROM acc_visitor_access WHERE id=:id"), {"id": visitor_id})
    db.commit()
    return {"success": True, "message": "Visitor record deleted"}




# ══════════════════════════════════════════════════════════════════════════════
# HOLIDAY INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/timezones/holidays-preview/")
async def preview_holidays(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Return upcoming holidays so the user can decide which timezone holiday group to apply them to."""
    rows = db.execute(text("""
        SELECT id, holiday_name, start_date AS holiday_date, holiday_type
        FROM att_holiday WHERE start_date >= CURRENT_DATE ORDER BY start_date LIMIT 30
    """)).fetchall()
    data = _rows(rows)
    for item in data:
        for k, v in item.items():
            if isinstance(v, datetime): item[k] = v.isoformat()
    return {"success": True, "data": data}


class HolidayApplyBody(BaseModel):
    holiday_group: int = 1          # 1, 2, or 3 → maps to hol1/hol2/hol3 interval columns
    start_time: str = "00:00"       # HH:MM
    end_time: str = "23:59"         # HH:MM
    timezone_ids: Optional[List[int]] = None   # None = apply to all timezones


@router.post("/timezones/apply-holidays")
async def apply_holidays(body: HolidayApplyBody, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Write holiday time intervals into acc_timezone hol{n}_time1 columns."""
    if body.holiday_group not in (1, 2, 3):
        raise HTTPException(400, "holiday_group must be 1, 2 or 3")
    prefix = f"hol{body.holiday_group}"
    interval_val = f"{body.start_time}-{body.end_time}"
    if body.timezone_ids:
        ids_sql = ",".join(str(i) for i in body.timezone_ids)
        db.execute(text(f"""
            UPDATE acc_timezone SET {prefix}_time1 = :iv, updated_at = NOW()
            WHERE id IN ({ids_sql})
        """), {"iv": interval_val})
    else:
        db.execute(text(f"UPDATE acc_timezone SET {prefix}_time1 = :iv, updated_at = NOW()"), {"iv": interval_val})
    db.commit()
    return {"success": True, "message": f"Holiday group {body.holiday_group} interval set to {interval_val} on all selected timezones"}
