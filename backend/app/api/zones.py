"""
Zone / Area Management API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
from datetime import datetime
import logging
import asyncio
import json

from sqlalchemy import text

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.zone import Zone, ZonePersonnelAssignment
from ..models.biotime_models import PersonnelArea as BioTimeArea
from ..core.websocket import zone_ws_connect, zone_ws_disconnect, broadcast_zone_update

logger = logging.getLogger(__name__)

router = APIRouter()


ZONE_TYPE_LABELS = {
    "LOCATION": "Location",
    "MUSTER_POINT": "Muster Point",
    "WORK_AREA": "Work Area",
    "OUTSIDE": "Outside Area",
    "TRANSIT": "In Transit",
    "RESTRICTED": "Restricted",
    "PUBLIC": "Public",
    "SAFE_HAVEN": "Safe Haven",
    "ACCOMMODATION": "Accommodation",
    "HELIPAD": "Helipad",
    "CONTROL_ROOM": "Control Room",
    "STORAGE": "Storage",
    "EMERGENCY": "Emergency",
}

DEFAULT_TILE_COLORS = {
    "LOCATION": "#52c41a",
    "MUSTER_POINT": "#52c41a",
    "WORK_AREA": "#f5222d",
    "OUTSIDE": "#595959",
    "TRANSIT": "#13c2c2",
    "RESTRICTED": "#6B1E35",
    "ACCOMMODATION": "#6B1E35",
    "SAFE_HAVEN": "#0078D4",
    "HELIPAD": "#0078D4",
    "CONTROL_ROOM": "#6B1E35",
    "STORAGE": "#8B4513",
    "EMERGENCY": "#f5222d",
    "PUBLIC": "#52c41a",
}

HAZARD_COLORS = {
    "LOW": "success",
    "MEDIUM": "warning",
    "HIGH": "error",
    "CRITICAL": "error",
}


def _zone_readers_count(db: Session, zone_id: int) -> dict:
    r = db.execute(text("""
        SELECT
          (SELECT count(*) FROM iclock_terminal t WHERE t.zone_id = :z
             AND COALESCE(t.connection_mode, '') <> 'controller'
             AND COALESCE(NULLIF(t.reader_purpose, ''), 'ATTENDANCE') <> 'ATTENDANCE') AS readers,
          (SELECT count(DISTINCT (ar.controller_id, ar.door_no)) FROM access_readers ar WHERE ar.zone_id = :z) AS doors
    """), {"z": zone_id}).fetchone()
    return {"access_reader_count": int(r.readers or 0), "door_count": int(r.doors or 0)}


def _to_dict(zone: Zone, db: Session) -> dict:
    assigned_count = db.query(ZonePersonnelAssignment).filter(
        ZonePersonnelAssignment.zone_id == zone.id,
        ZonePersonnelAssignment.status == "ACTIVE",
    ).count()

    ztype = (zone.zone_type or "").upper()
    zstatus = (zone.status or "").upper()

    return {
        "id": zone.id,
        "name": zone.name,
        "code": zone.code,
        "zone_type": ztype,
        "zone_type_label": ZONE_TYPE_LABELS.get(ztype, ztype),
        "description": zone.description,
        "status": zstatus,
        "state": zone.state,
        "address": zone.address,
        "latitude": zone.latitude,
        "longitude": zone.longitude,
        "max_capacity": zone.max_capacity,
        "current_occupancy": zone.current_occupancy or 0,
        "current_personnel_count": zone.current_personnel_count or 0,
        "hazard_level": (zone.hazard_level or "LOW").upper(),
        "safety_level": (zone.safety_level or "NORMAL").upper(),
        "access_level": (zone.access_level or "RESTRICTED").upper(),
        "device_count": zone.device_count or 0,
        "zone_manager_id": zone.zone_manager_id,
        "contact_person": zone.contact_person,
        "contact_phone": zone.contact_phone,
        "zkteco_sync_enabled": zone.zkteco_sync_enabled,
        "last_sync_at": zone.last_sync_at.isoformat() if zone.last_sync_at else None,
        "floor_plan_url": zone.floor_plan_url,
        "floor_plan_filename": zone.floor_plan_filename,
        "is_active": zone.is_active,
        "assigned_personnel": assigned_count,
        "occupancy_rate": round((zone.current_occupancy or 0) / zone.max_capacity * 100, 1) if zone.max_capacity else None,
        "parent_zone_id": zone.parent_zone_id,
        "display_color": zone.display_color or DEFAULT_TILE_COLORS.get(ztype),
        "tile_position": zone.tile_position or "auto",
        "is_site_boundary": bool(getattr(zone, "is_site_boundary", False)),
        # Mustering fields — without these the edit form showed them blank.
        # What actually feeds this zone: access-control ADMS readers (T&A terminals are
        # not part of zones) and doors on the ZKTeco controllers.
        **_zone_readers_count(db, zone.id),
        "reader_sn": zone.reader_sn,
        "evac_point": zone.evac_point,
        "evac_gps": zone.evac_gps,
        "created_at": zone.created_at.isoformat() if zone.created_at else None,
        "updated_at": zone.updated_at.isoformat() if zone.updated_at else None,
    }


# ── Static routes BEFORE /{zone_id} ──────────────────────────────────────────

@router.get("/meta/summary")
def get_summary(db: Session = Depends(get_db), _=Depends(get_current_user)):
    total = db.query(Zone).count()
    active = db.query(Zone).filter(Zone.is_active == True, func.upper(Zone.status) == "ACTIVE").count()

    by_type = {}
    for zt, c in db.query(Zone.zone_type, func.count(Zone.id)).group_by(Zone.zone_type).all():
        by_type[(zt or "unknown").upper()] = c

    by_status = {}
    for st, c in db.query(Zone.status, func.count(Zone.id)).group_by(Zone.status).all():
        by_status[(st or "unknown").upper()] = c

    by_hazard = {}
    for hl, c in db.query(Zone.hazard_level, func.count(Zone.id)).group_by(Zone.hazard_level).all():
        by_hazard[(hl or "unknown").upper()] = c

    zk_synced = db.query(Zone).filter(
        Zone.zkteco_sync_enabled == True,
        Zone.last_sync_at != None,
    ).count()
    zk_pending = db.query(Zone).filter(
        Zone.zkteco_sync_enabled == True,
        Zone.last_sync_at == None,
    ).count()

    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "zkteco_synced": zk_synced,
        "zkteco_pending": zk_pending,
        "by_type": by_type,
        "by_status": by_status,
        "by_hazard": by_hazard,
    }


@router.get("/meta/zkteco-compare")
def zkteco_compare(db: Session = Depends(get_db), _=Depends(get_current_user)):
    zones = db.query(Zone).filter(Zone.is_active == True).all()
    bt_areas = db.query(BioTimeArea).all()

    bt_codes = {(a.area_code or "").upper() for a in bt_areas}
    bt_names = {(a.area_name or "").upper() for a in bt_areas}

    matched, local_only = [], []
    for z in zones:
        code_match = z.code.upper() in bt_codes
        name_match = z.name.upper() in bt_names
        if code_match or name_match:
            matched.append({
                "zone_id": z.id, "zone_name": z.name, "zone_code": z.code,
                "code_match": code_match, "name_match": name_match,
            })
        else:
            local_only.append({"zone_id": z.id, "zone_name": z.name, "zone_code": z.code})

    zone_codes = {z.code.upper() for z in zones}
    zone_names = {z.name.upper() for z in zones}
    bt_only = [
        {"area_id": a.id, "area_name": a.area_name, "area_code": a.area_code}
        for a in bt_areas
        if (a.area_code or "").upper() not in zone_codes and (a.area_name or "").upper() not in zone_names
    ]

    return {
        "matched": matched,
        "local_only": local_only,
        "biotime_only": bt_only,
        "total_local": len(zones),
        "total_biotime": len(bt_areas),
        "total_matched": len(matched),
    }


@router.get("/types")
def get_zone_types(_=Depends(get_current_user)):
    return [{"value": k, "label": v} for k, v in ZONE_TYPE_LABELS.items()]


@router.get("/statuses")
def get_zone_statuses(_=Depends(get_current_user)):
    return [
        {"value": "ACTIVE", "label": "Active"},
        {"value": "INACTIVE", "label": "Inactive"},
        {"value": "MAINTENANCE", "label": "Maintenance"},
        {"value": "EMERGENCY", "label": "Emergency"},
        {"value": "LOCKDOWN", "label": "Lockdown"},
    ]


def _muster_occupancy_context(db: Session):
    """During an active muster/drill, zone occupancy must reflect evacuation:
    a person already accounted-for (Safe at a muster point) has LEFT their work
    zone, so they must not still be counted there. Returns
    (safe_emp_codes, safe_count_by_zone, active):
      • safe_emp_codes     — excluded from their work-zone counts, so work zones
                             show only the MISSING (still-in-zone / to be searched).
      • safe_count_by_zone — added to the muster-point zone (the reader they
                             mustered at), so the total POB stays accurate.
    When no drill is active, returns empties and occupancy behaves normally.
    Muster punches write mustering_log (not iclock_transaction), which is why the
    two views drift apart without this reconciliation."""
    event_ids = [r.id for r in db.execute(text(
        "SELECT id FROM mustering_event WHERE status = 0")).fetchall()]
    if not event_ids:
        return set(), {}, False
    safe_codes = {r.emp_code for r in db.execute(text(
        "SELECT DISTINCT emp_code FROM mustering_log "
        "WHERE event_id = ANY(:ids) AND status = 1"), {"ids": event_ids}).fetchall()}
    safe_by_zone = {}
    for r in db.execute(text("""
        SELECT term.zone_id AS zid, COUNT(DISTINCT ml.emp_code) AS cnt
        FROM mustering_log ml
        JOIN iclock_terminal term ON term.sn = ml.device_sn
        WHERE ml.event_id = ANY(:ids) AND ml.status = 1 AND term.zone_id IS NOT NULL
        GROUP BY term.zone_id
    """), {"ids": event_ids}).fetchall():
        safe_by_zone[r.zid] = r.cnt
    return safe_codes, safe_by_zone, True


def _live_zone_occupancy(db: Session):
    """Per-zone live occupancy {zone_id: count}, muster-aware. The single source of
    truth shared by /dashboard and /hierarchy so the POB total always equals the sum
    of the zone cards. During a drill, work zones exclude Safe people and muster zones
    add them (see _muster_occupancy_context). Returns (counts, safe_by_zone, active)."""
    safe_codes, safe_by_zone, muster_active = _muster_occupancy_context(db)
    _exclude_safe = "AND latest.emp_code <> ALL(:safe_codes)" if safe_codes else ""
    # Source of truth = personnel.current_zone_id, maintained by every door / zone
    # reader tap (_handle_zone_access) and read by mustering for "last known zone".
    # The previous source — "last attendance punch is a check-in at a zoned reader" —
    # never counted F18 taps (stamped Check-Out), ignored exits to the parent zone and
    # boundary exits, and could disagree with what a muster reported.
    _exclude_safe = "AND p.emp_code <> ALL(:safe_codes)" if safe_codes else ""
    rows = db.execute(text(f"""
        SELECT p.current_zone_id AS zone_id, COUNT(*) AS cnt
        FROM personnel p
        WHERE p.current_zone_id IS NOT NULL AND p.is_active = TRUE
          {_exclude_safe}
        GROUP BY p.current_zone_id
    """), ({"safe_codes": list(safe_codes)} if safe_codes else {})).fetchall()
    counts = {r.zone_id: r.cnt for r in rows}
    for zid, cnt in safe_by_zone.items():     # move Safe people to the muster zone
        counts[zid] = counts.get(zid, 0) + cnt
    return counts, safe_by_zone, muster_active


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _=Depends(get_current_user)):
    zones = db.query(Zone).order_by(Zone.name).all()

    # Muster-aware per-zone occupancy (shared with /hierarchy so totals always agree):
    # counts distinct employees currently "in" each zone from iclock_transaction; during
    # a drill, Safe personnel are moved from their work zone to the muster point.
    live_count_map, safe_by_zone, muster_active = _live_zone_occupancy(db)

    # Last activity per zone (most recent punch on any terminal in that zone)
    last_activity_map = {}
    for row in db.execute(text("""
        SELECT zone_id, MAX(punch_time) AS last_punch,
               (array_agg(emp_code ORDER BY punch_time DESC))[1] AS last_emp
        FROM zone_personnel_tracking
        WHERE punch_time > NOW() - INTERVAL '30 days'
        GROUP BY zone_id
    """)).fetchall():
        last_activity_map[row.zone_id] = (row.last_emp, row.last_punch)

    reader_count_map = {}
    for row in db.execute(text(
        "SELECT zone_id, COUNT(*) AS cnt FROM iclock_terminal WHERE zone_id IS NOT NULL GROUP BY zone_id"
    )).fetchall():
        reader_count_map[row.zone_id] = row.cnt

    result = []
    for z in zones:
        reader_count = reader_count_map.get(z.id, 0)

        d = _to_dict(z, db)
        # Override stored count with the live, muster-aware count (work zones show
        # missing only during a drill; muster zones already include the Safe headcount).
        live = live_count_map.get(z.id, 0)
        d["current_personnel_count"] = live
        d["current_occupancy"] = live
        d["reader_count"] = reader_count
        if muster_active:
            d["muster_active"] = True
            d["mustered_safe_here"] = safe_by_zone.get(z.id, 0)

        last_emp, last_punch = last_activity_map.get(z.id, (None, None))
        d["last_activity_time"] = last_punch.isoformat() if last_punch else None
        d["last_activity_emp"] = last_emp

        result.append(d)

    # Read-only endpoint: the stored current_personnel_count is maintained by the
    # punch path (_recalc_zone_occupancy). We intentionally do NOT write it back
    # here — a GET must not mutate the DB (avoids lock contention with live punches
    # and the dual-writer conflict with _recalc).
    return result


@router.get("/map-live")
def get_map_live(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Everything the GPS map needs in one call: every zone (with or without GPS)
    and WHO is in it right now, plus on-board people whose zone is unknown — so no
    one on board is ever invisible on the map screen."""
    zones = {z.id: z for z in db.query(Zone).all()}
    people = db.execute(text("""
        SELECT p.emp_code, p.full_name, p.first_name, p.last_name, p.department,
               p.position, p.photo_url, p.current_zone_id, p.is_onboard, p.last_seen,
               (SELECT MAX(t.punch_time) FROM zone_personnel_tracking t
                 WHERE t.emp_code = p.emp_code AND t.zone_id = p.current_zone_id
                   AND t.event_type = 'CLOCK_IN') AS in_zone_since
        FROM personnel p
        WHERE p.is_active = TRUE AND (p.current_zone_id IS NOT NULL OR p.is_onboard = TRUE)
        ORDER BY p.full_name NULLS LAST, p.emp_code
    """)).fetchall()

    def _person(r):
        return {
            "emp_code": r.emp_code,
            "name": (r.full_name or f"{r.first_name or ''} {r.last_name or ''}").strip() or r.emp_code,
            "department": r.department,
            "position": r.position,
            "photo_url": r.photo_url,
            "in_zone_since": r.in_zone_since.isoformat() if r.in_zone_since else None,
            "last_seen": r.last_seen.isoformat() if r.last_seen else None,
        }

    by_zone: dict = {}
    unlocated = []
    for r in people:
        if r.current_zone_id and r.current_zone_id in zones:
            by_zone.setdefault(r.current_zone_id, []).append(_person(r))
        else:
            unlocated.append(_person(r))

    out = []
    for zid, z in zones.items():
        d = _to_dict(z, db)
        d["personnel"] = by_zone.get(zid, [])
        d["current_personnel_count"] = len(d["personnel"])
        d["has_gps"] = z.latitude is not None and z.longitude is not None
        out.append(d)
    out.sort(key=lambda d: (-d["current_personnel_count"], d["name"]))
    onboard_total = sum(1 for r in people if r.is_onboard)
    return {
        "zones": out,
        "unlocated": unlocated,
        "onboard_total": onboard_total,
        "located_total": sum(len(v) for v in by_zone.values()),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/available-devices")
def get_available_devices(db: Session = Depends(get_db), _=Depends(get_current_user)):
    # Controller reader ports are mirrored as terminals — they are mapped to zones by
    # door (assign-door), not here.
    rows = db.execute(text(
        "SELECT id, sn, alias, ip_address, zone_id, last_activity, state, reader_purpose, device_type "
        "FROM iclock_terminal WHERE COALESCE(connection_mode, '') <> 'controller' ORDER BY alias"
    )).fetchall()
    return [
        {
            "id": r.id,
            "sn": r.sn,
            "alias": r.alias or f"Terminal {r.sn}",
            "ip_address": r.ip_address,
            "zone_id": r.zone_id,
            "last_activity": r.last_activity.isoformat() if r.last_activity else None,
            "state": r.state,
            "status": "online" if r.state == 1 else "offline",
            "already_assigned": r.zone_id is not None,
            "reader_purpose": r.reader_purpose or "ATTENDANCE",
            # T&A terminals take no part in zones (they can be in another state/country).
            "assignable": _is_zone_reader(r.reader_purpose, r.device_type),
        }
        for r in rows
    ]


def _is_zone_reader(purpose, device_type=None) -> bool:
    return (purpose or "ATTENDANCE").upper() != "ATTENDANCE" or device_type == 2


@router.get("/available-doors")
def get_available_doors(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """All controller doors, with their controller and current zone (if any).
    A door is a (controller, door_no) unit; access-control zones are fed by doors,
    not readers directly (controller port → door → zone)."""
    rows = db.execute(text("""
        SELECT ar.controller_id, ac.name AS controller_name, ar.door_no,
               MAX(ar.zone_id) AS zone_id
        FROM access_readers ar
        JOIN access_controllers ac ON ac.id = ar.controller_id
        GROUP BY ar.controller_id, ac.name, ar.door_no
        ORDER BY ac.name, ar.door_no
    """)).fetchall()
    return [{
        "controller_id": r.controller_id,
        "controller_name": r.controller_name,
        "door_no": r.door_no,
        "label": f"{r.controller_name} — Door {r.door_no}",
        "zone_id": r.zone_id,
        "already_assigned": r.zone_id is not None,
    } for r in rows]


@router.get("/hierarchy")
def get_hierarchy(db: Session = Depends(get_db), _=Depends(get_current_user)):
    zones = db.query(Zone).filter(Zone.is_active == True).order_by(Zone.name).all()
    zone_dicts = [_to_dict(z, db) for z in zones]

    # Same live, muster-aware counts as /dashboard so the POB total matches the cards.
    live_counts, safe_by_zone, muster_active = _live_zone_occupancy(db)
    for zd in zone_dicts:
        cnt = live_counts.get(zd.get("id"), 0)
        zd["current_personnel_count"] = cnt
        zd["current_occupancy"] = cnt
        if muster_active:
            zd["muster_active"] = True
            zd["mustered_safe_here"] = safe_by_zone.get(zd.get("id"), 0)

    top_level = [zd for zd in zone_dicts if not zd.get("parent_zone_id")]
    by_parent: dict = {}
    for zd in zone_dicts:
        pid = zd.get("parent_zone_id")
        if pid:
            by_parent.setdefault(str(pid), []).append(zd)

    total_pob = sum(zd.get("current_personnel_count", 0) for zd in zone_dicts)
    return {"top_level": top_level, "by_parent": by_parent, "total_pob": total_pob}


@router.get("/public-list")
def get_public_zones(db: Session = Depends(get_db)):
    zones = db.query(Zone).filter(Zone.is_active == True).order_by(Zone.name).all()
    return [{"id": z.id, "name": z.name, "code": z.code, "zone_type": z.zone_type} for z in zones]


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list)
def get_zones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    zone_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Zone)
    if search:
        q = q.filter(or_(
            Zone.name.ilike(f"%{search}%"),
            Zone.code.ilike(f"%{search}%"),
            Zone.description.ilike(f"%{search}%"),
        ))
    if zone_type:
        q = q.filter(Zone.zone_type.ilike(zone_type))
    if status:
        q = q.filter(Zone.status.ilike(status))
    if state:
        q = q.filter(Zone.state.ilike(state))
    if is_active is not None:
        q = q.filter(Zone.is_active == is_active)

    zones = q.order_by(Zone.name).offset(skip).limit(limit).all()
    return [_to_dict(z, db) for z in zones]


@router.get("/activity-feed")
def get_zone_activity_feed(
    limit: int = Query(default=30, le=100),
    since: Optional[str] = Query(default=None, description="ISO timestamp — return only events after this time"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Recent badge events across all zones with personnel details."""
    params: dict = {"limit": limit}
    since_clause = ""
    if since:
        try:
            since_clause = "AND zpt.punch_time > :since"
            params["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            pass

    rows = db.execute(text(f"""
        SELECT
            zpt.id,
            zpt.emp_code,
            zpt.event_type,
            zpt.punch_time,
            zpt.device_sn,
            z.name  AS zone_name,
            z.id    AS zone_id,
            COALESCE(NULLIF(TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')), ''), zpt.emp_code) AS emp_name,
            p.photo_url,
            p.department
        FROM zone_personnel_tracking zpt
        LEFT JOIN zones z ON z.id = zpt.zone_id
        LEFT JOIN personnel p ON p.emp_code = zpt.emp_code
        WHERE 1=1 {since_clause}
        ORDER BY zpt.punch_time DESC
        LIMIT :limit
    """), params).fetchall()

    return [
        {
            "id":         r.id,
            "emp_code":   r.emp_code,
            "emp_name":   r.emp_name,
            "event_type": r.event_type,
            "punch_time": r.punch_time.isoformat() if r.punch_time else None,
            "zone_name":  r.zone_name,
            "zone_id":    r.zone_id,
            "photo_url":  r.photo_url,
            "department": r.department,
            "device_sn":  r.device_sn,
        }
        for r in rows
    ]


@router.get("/{zone_id}")
def get_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return _to_dict(zone, db)


@router.post("", status_code=201)
def create_zone(
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if db.query(Zone).filter(Zone.code == body.get("code")).first():
        raise HTTPException(status_code=400, detail="Zone code already exists")

    zone = Zone(
        name=body["name"],
        code=body["code"],
        zone_type=(body.get("zone_type") or "WORK_AREA").upper(),
        description=body.get("description"),
        status=(body.get("status") or "ACTIVE").upper(),
        state=body.get("state"),
        address=body.get("address"),
        latitude=body.get("latitude"),
        longitude=body.get("longitude"),
        max_capacity=body.get("max_capacity"),
        hazard_level=(body.get("hazard_level") or "LOW").upper(),
        safety_level=(body.get("safety_level") or "NORMAL").upper(),
        access_level=(body.get("access_level") or "RESTRICTED").upper(),
        contact_person=body.get("contact_person"),
        contact_phone=body.get("contact_phone"),
        zkteco_sync_enabled=body.get("zkteco_sync_enabled", True),
        is_active=body.get("is_active", True),
        parent_zone_id=body.get("parent_zone_id"),
        display_color=body.get("display_color"),
        tile_position=body.get("tile_position", "auto"),
        is_site_boundary=bool(body.get("is_site_boundary", False)),
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return _to_dict(zone, db)


@router.put("/{zone_id}")
def update_zone(
    zone_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    # An exit moves a person to the parent zone, so the hierarchy must be a tree.
    if body.get("parent_zone_id"):
        seen, cur = {zone_id}, int(body["parent_zone_id"])
        while cur:
            if cur in seen:
                raise HTTPException(status_code=400,
                                    detail="Parent zone would create a loop (a zone cannot sit inside itself)")
            seen.add(cur)
            cur = db.execute(text("SELECT parent_zone_id FROM zones WHERE id = :z"), {"z": cur}).scalar()

    upper_fields = {"zone_type", "status", "hazard_level", "safety_level", "access_level"}
    for field, value in body.items():
        if hasattr(zone, field) and field not in ("id", "created_at"):
            if field in upper_fields and value:
                value = value.upper()
            setattr(zone, field, value)

    db.commit()
    db.refresh(zone)
    return _to_dict(zone, db)


@router.patch("/{zone_id}/status")
async def update_zone_status(
    zone_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Quick status-only update. LOCKDOWN really locks the zone's doors (it used to be
    a label only — the operator believed a zone was secured when nothing had moved);
    leaving LOCKDOWN releases them."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    new_status = (body.get("status") or "").upper()
    if new_status not in {"ACTIVE", "INACTIVE", "MAINTENANCE", "EMERGENCY", "LOCKDOWN"}:
        raise HTTPException(status_code=400, detail="Invalid status value")
    old_status = (zone.status or "").upper()
    if new_status == "LOCKDOWN" and (zone.zone_type or "").upper() == "MUSTER_POINT":
        raise HTTPException(status_code=400, detail="A muster point is a safe assembly area — it cannot be locked down")
    doors = None
    if new_status != old_status and "LOCKDOWN" in (new_status, old_status):
        from ..services.emergency_service import emergency_service
        action = "lock" if new_status == "LOCKDOWN" else "unlock"
        try:
            doors = await emergency_service.execute_lockdown(
                scope="zone", zone_ids=[zone_id], action=action,
                reason=body.get("reason") or f"Zone {zone.name} set to {new_status.title()}",
                initiated_by=getattr(current_user, "id", None), db=db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        zone = db.query(Zone).filter(Zone.id == zone_id).first()
    zone.status = new_status
    db.commit()
    out = {"success": True, "id": zone_id, "status": new_status}
    if doors is not None:
        out["doors"] = {k: doors.get(k) for k in ("message", "total_doors", "processed_doors", "failed_doors", "skipped_doors")}
    return out


@router.patch("/{zone_id}/position")
def update_zone_position(
    zone_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Quick tile-position-only update for the POB Dashboard layout."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    new_pos = (body.get("tile_position") or "auto").lower()
    if new_pos not in {"auto", "left", "right", "top", "bottom"}:
        raise HTTPException(status_code=400, detail="Invalid tile_position value")
    zone.tile_position = new_pos
    db.commit()
    return {"success": True, "id": zone_id, "tile_position": new_pos}


def _delete_single_zone(db: Session, zone_id: int) -> None:
    """Delete one zone row and its dependent rows. Caller is responsible for commit."""
    # Nullable FKs — SET NULL
    db.execute(text("UPDATE iclock_terminal SET zone_id = NULL WHERE zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE devices SET zone_id = NULL WHERE zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE personnel SET current_zone_id = NULL WHERE current_zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE zone_personnel_tracking SET previous_zone_id = NULL WHERE previous_zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE access_logs SET zone_id = NULL WHERE zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE pay_zone_allowance SET area_id = NULL WHERE area_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE mustering_event SET zone_id = NULL WHERE zone_id = :z"), {"z": zone_id})
    # Muster/assembly-point references on events (NO ACTION FKs — must clear or the
    # delete fails with a foreign-key violation). muster_zone_id is the single
    # assembly point; muster_zone_ids is the multi-select jsonb array.
    db.execute(text("UPDATE mustering_event SET muster_zone_id = NULL WHERE muster_zone_id = :z"), {"z": zone_id})
    db.execute(text(
        "UPDATE mustering_event SET muster_zone_ids = ("
        "  SELECT COALESCE(jsonb_agg(e), '[]'::jsonb) FROM jsonb_array_elements(muster_zone_ids) e"
        "  WHERE e <> to_jsonb(CAST(:z AS int))"
        ") WHERE muster_zone_ids IS NOT NULL AND muster_zone_ids @> to_jsonb(CAST(:z AS int))"
    ), {"z": zone_id})
    db.execute(text("UPDATE access_readers SET zone_id = NULL WHERE zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE emergency_template SET auto_mustering_zone_id = NULL WHERE auto_mustering_zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE emergency_plan SET zone_id = NULL WHERE zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE vis_type SET mustering_zone_id = NULL WHERE mustering_zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE vis_visit_log SET mustering_zone_id = NULL WHERE mustering_zone_id = :z"), {"z": zone_id})
    db.execute(text("UPDATE mtg_room SET mustering_zone_id = NULL WHERE mustering_zone_id = :z"), {"z": zone_id})
    # NOT NULL FKs — DELETE referencing rows first
    db.execute(text("DELETE FROM mustering_drill_schedule WHERE zone_id = :z"), {"z": zone_id})
    # Child rows
    db.execute(text("DELETE FROM zone_personnel_tracking WHERE zone_id = :z"), {"z": zone_id})
    db.execute(text("DELETE FROM zone_reader_assignments WHERE zone_id = :z"), {"z": zone_id})
    db.execute(text("DELETE FROM zone_personnel_assignments WHERE zone_id = :z"), {"z": zone_id})
    db.execute(text("DELETE FROM zones WHERE id = :z"), {"z": zone_id})


def _cascade_delete_zone(db: Session, zone_id: int) -> int:
    """Recursively delete a zone and all its descendants. Returns total zones deleted."""
    children = db.query(Zone.id).filter(Zone.parent_zone_id == zone_id).all()
    total = 1
    for (child_id,) in children:
        total += _cascade_delete_zone(db, child_id)
    _delete_single_zone(db, zone_id)
    return total


@router.delete("/{zone_id}")
def delete_zone(
    zone_id: int,
    cascade: bool = False,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    sub_count = db.query(Zone).filter(Zone.parent_zone_id == zone_id).count()
    if sub_count > 0 and not cascade:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {sub_count} sub-zone(s) belong to this zone. Delete sub-zones first.",
        )

    ids = [zone_id] + ([r[0] for r in db.execute(text(
        "WITH RECURSIVE t AS (SELECT id FROM zones WHERE parent_zone_id = :z "
        "UNION ALL SELECT z.id FROM zones z JOIN t ON z.parent_zone_id = t.id) SELECT id FROM t"),
        {"z": zone_id}).fetchall()] if cascade else [])
    busy = db.execute(text("""
        SELECT id FROM mustering_event WHERE status = 0 AND (
            zone_id = ANY(:ids) OR muster_zone_id = ANY(:ids)
            OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(COALESCE(zone_ids, '[]'::jsonb)) e WHERE e::int = ANY(:ids))
            OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(COALESCE(muster_zone_ids, '[]'::jsonb)) e WHERE e::int = ANY(:ids)))
        LIMIT 1"""), {"ids": ids}).scalar()
    if busy:
        raise HTTPException(status_code=409, detail="A muster that covers this zone is running — end it before deleting the zone")
    located = db.execute(text("SELECT count(*) FROM personnel WHERE current_zone_id = ANY(:ids)"), {"ids": ids}).scalar() or 0
    note = f" {located} person(s) recorded in it now have no zone." if located else ""

    zone_name = zone.name
    if cascade and sub_count > 0:
        total = _cascade_delete_zone(db, zone_id)
        db.commit()
        return {"message": f"Zone '{zone_name}' and {total - 1} sub-zone(s) deleted.{note}"}

    _delete_single_zone(db, zone_id)
    db.commit()
    return {"message": f"Zone '{zone_name}' deleted.{note}"}


@router.get("/{zone_id}/sub-zones")
def get_sub_zones(
    zone_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    children = db.query(Zone).filter(
        Zone.parent_zone_id == zone_id,
        Zone.is_active == True,
    ).order_by(Zone.name).all()
    return [_to_dict(z, db) for z in children]


@router.get("/{zone_id}/personnel")
def get_zone_personnel(
    zone_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    assignments = db.query(ZonePersonnelAssignment).filter(
        ZonePersonnelAssignment.zone_id == zone_id,
        ZonePersonnelAssignment.status == "ACTIVE",
    ).all()
    return [
        {
            "id": a.id,
            "personnel_id": a.personnel_id,
            "role": a.role,
            "access_level": a.access_level,
            "is_primary_zone": a.is_primary_zone,
            "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
            "status": a.status,
        }
        for a in assignments
    ]


def _sync_zone_to_access_control(zone_id: int, db: Session) -> None:
    """
    Keep the Access Control system (acc_zone / acc_door / acc_zone_door) in sync
    whenever a reader is assigned or removed in Zone Management.

    For every terminal with iclock_terminal.zone_id = zone_id we ensure:
      • An acc_door row exists (keyed by terminal_sn)
      • An acc_zone row mirrors the zones.name entry
      • An acc_zone_door row links them with the correct direction
        (reader_purpose=ACCESS_ENTRY → direction=0, ACCESS_EXIT → direction=1,
         anything else → direction=0)

    Also recomputes zones.device_count so the zone card always shows the right
    reader count.
    """
    # Refresh device_count from ground truth
    db.execute(text("""
        UPDATE zones SET device_count = (
            SELECT COUNT(*) FROM iclock_terminal WHERE zone_id = :zid
        ) WHERE id = :zid
    """), {"zid": zone_id})

    zone_row = db.execute(text("SELECT name FROM zones WHERE id = :zid"), {"zid": zone_id}).fetchone()
    if not zone_row:
        return
    zone_name = zone_row.name[:100]

    # Ensure acc_zone exists
    az = db.execute(text("SELECT id FROM acc_zone WHERE zone_name = :n LIMIT 1"), {"n": zone_name}).fetchone()
    if not az:
        az = db.execute(text("""
            INSERT INTO acc_zone (zone_name) VALUES (:n)
            ON CONFLICT (zone_name) DO UPDATE SET zone_name = EXCLUDED.zone_name
            RETURNING id
        """), {"n": zone_name}).fetchone()
    acc_zone_id = az.id

    # Sync each terminal assigned to this zone
    terminals = db.execute(text("""
        SELECT id, sn, alias, reader_purpose FROM iclock_terminal WHERE zone_id = :zid
    """), {"zid": zone_id}).fetchall()

    for t in terminals:
        # Ensure acc_door
        door = db.execute(text(
            "SELECT id FROM acc_door WHERE terminal_sn = :sn LIMIT 1"
        ), {"sn": t.sn}).fetchone()
        if not door:
            rp = t.reader_purpose or "ATTENDANCE"
            suffix = "Entry" if rp == "ACCESS_ENTRY" else "Exit" if rp == "ACCESS_EXIT" else "Reader"
            door_name = f"{t.alias or t.sn} ({suffix})"[:50]
            door = db.execute(text("""
                INSERT INTO acc_door (name, terminal_sn) VALUES (:n, :sn) RETURNING id
            """), {"n": door_name, "sn": t.sn}).fetchone()

        direction = 0 if (t.reader_purpose or "") == "ACCESS_ENTRY" else 1
        db.execute(text("""
            INSERT INTO acc_zone_door (zone_id, door_id, direction)
            VALUES (:zid, :did, :dir)
            ON CONFLICT (zone_id, door_id) DO UPDATE SET direction = :dir
        """), {"zid": acc_zone_id, "did": door.id, "dir": direction})

    # Remove acc_zone_door entries for doors whose terminal is no longer in this zone
    db.execute(text("""
        DELETE FROM acc_zone_door
        WHERE zone_id = :azid
          AND door_id NOT IN (
              SELECT ad.id FROM acc_door ad
              JOIN iclock_terminal t ON t.sn = ad.terminal_sn
              WHERE t.zone_id = :zid
          )
    """), {"azid": acc_zone_id, "zid": zone_id})


# ── Zone ↔ Door assignment (controller port → door → zone) ─────────────────────
# Access-control zones are fed by DOORS, not readers directly. A door is a
# (controller, door_no) unit on a C3/inBio panel; assigning it to a zone maps that
# door's reader ports (access_readers) to the zone.

@router.get("/{zone_id}/doors")
def get_zone_doors(zone_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Doors mapped to this zone (grouped controller/door_no)."""
    rows = db.execute(text("""
        SELECT ar.controller_id, ac.name AS controller_name, ar.door_no
        FROM access_readers ar
        JOIN access_controllers ac ON ac.id = ar.controller_id
        WHERE ar.zone_id = :zid
        GROUP BY ar.controller_id, ac.name, ar.door_no
        ORDER BY ac.name, ar.door_no
    """), {"zid": zone_id}).fetchall()
    return [{
        "controller_id": r.controller_id,
        "controller_name": r.controller_name,
        "door_no": r.door_no,
        "label": f"{r.controller_name} — Door {r.door_no}",
    } for r in rows]


@router.post("/{zone_id}/assign-door")
def assign_door(zone_id: int, body: dict, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Assign a controller door to this zone (maps its reader ports to the zone)."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    cid, dn = body.get("controller_id"), body.get("door_no")
    if cid is None or dn is None:
        raise HTTPException(status_code=400, detail="controller_id and door_no are required")
    n = db.execute(text(
        "UPDATE access_readers SET zone_id = :zid, updated_at = now() "
        "WHERE controller_id = :cid AND door_no = :dn"
    ), {"zid": zone_id, "cid": cid, "dn": dn}).rowcount
    db.commit()
    if not n:
        raise HTTPException(status_code=404, detail="Door not found on that controller")
    return {"message": "Door assigned to zone", "zone_id": zone_id,
            "controller_id": cid, "door_no": dn, "ports_updated": n}


@router.delete("/{zone_id}/doors")
def remove_zone_door(zone_id: int, controller_id: int = Query(...), door_no: int = Query(...),
                     db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Unassign a door from this zone."""
    n = db.execute(text(
        "UPDATE access_readers SET zone_id = NULL, updated_at = now() "
        "WHERE controller_id = :cid AND door_no = :dn AND zone_id = :zid"
    ), {"cid": controller_id, "dn": door_no, "zid": zone_id}).rowcount
    db.commit()
    return {"message": "Door removed from zone" if n else "Door was not assigned to this zone",
            "ports_updated": n}


@router.get("/{zone_id}/readers")
def get_zone_readers(
    zone_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    rows = db.execute(text(
        "SELECT id, sn, alias, ip_address, last_activity, state, reader_purpose "
        "FROM iclock_terminal WHERE zone_id = :zid ORDER BY alias"
    ), {"zid": zone_id}).fetchall()
    return [
        {
            "reader_id": r.id,
            "sn": r.sn,
            "alias": r.alias or f"Terminal {r.sn}",
            "ip_address": r.ip_address,
            "last_activity": r.last_activity.isoformat() if r.last_activity else None,
            "state": r.state,
            "status": "online" if r.state == 1 else "offline",
            "reader_purpose": r.reader_purpose or "ATTENDANCE",
        }
        for r in rows
    ]


@router.post("/{zone_id}/assign-reader")
def assign_reader(
    zone_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    terminal_id = body.get("device_id")
    # Keep the reader's role (set under Devices) unless the caller explicitly sends
    # one. This used to default to ATTENDANCE, so giving an Entry/Exit reader a zone
    # silently turned it back into an attendance reader. Standalone ADMS readers (e.g.
    # the ZKTeco F18) may be Entry/Exit doors themselves — that is how location is
    # tracked on a site without door controllers; controller-wired readers are mapped
    # under Access Control → Controllers instead.
    valid_purposes = {"ATTENDANCE", "ACCESS_ENTRY", "ACCESS_EXIT", "MUSTERING", "POB",
                      "EMERGENCY", "TRANSPORT_CHECKIN"}
    reader_purpose = (body.get("reader_purpose") or "").upper() or None
    if reader_purpose and reader_purpose not in valid_purposes:
        raise HTTPException(status_code=400, detail=f"Unknown reader purpose {reader_purpose}")

    terminal = db.execute(text(
        "SELECT id, sn, alias, zone_id, reader_purpose, device_type, connection_mode "
        "FROM iclock_terminal WHERE id = :tid"
    ), {"tid": terminal_id}).fetchone()
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal not found")
    if (terminal.connection_mode or "") == "controller":
        raise HTTPException(status_code=400, detail="This is a ZKTeco controller door reader — use Doors on the zone instead")
    if not _is_zone_reader(reader_purpose or terminal.reader_purpose, terminal.device_type):
        raise HTTPException(status_code=400, detail=(
            f"{terminal.alias or terminal.sn} is a time & attendance reader. T&A readers are not part of zones "
            f"or mustering — set it to Access Control Entry/Exit (or Mustering) under Devices first."))
    if terminal.zone_id == zone_id:
        raise HTTPException(status_code=400, detail="Terminal already assigned to this zone")

    old_zone_id = terminal.zone_id

    # (Moving a reader used to insert fake CHECK-OUT punches into iclock_transaction
    # for whoever last checked in on it — read by attendance as real taps. People do
    # not move because a reader did; their location stays as recorded.)
    db.execute(text(
        "UPDATE iclock_terminal SET zone_id = :zid, "
        "reader_purpose = COALESCE(:rp, reader_purpose, 'ATTENDANCE') WHERE id = :tid"
    ), {"zid": zone_id, "rp": reader_purpose, "tid": terminal_id})

    db.commit()

    # Sync both zone systems (device_count + acc_zone/acc_door/acc_zone_door)
    _sync_zone_to_access_control(zone_id, db)
    if old_zone_id is not None and old_zone_id != zone_id:
        _sync_zone_to_access_control(old_zone_id, db)
    db.commit()

    moved = old_zone_id is not None and old_zone_id != zone_id
    return {
        "message": "Reader moved to zone" if moved else "Reader assigned to zone",
        "terminal_id": terminal_id,
        "zone_id": zone_id,
        "moved_from": old_zone_id if moved else None,
    }


@router.delete("/{zone_id}/readers/{reader_id}")
def remove_reader(
    zone_id: int,
    reader_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    terminal = db.execute(text(
        "SELECT id, zone_id FROM iclock_terminal WHERE id = :rid"
    ), {"rid": reader_id}).fetchone()
    if not terminal or terminal.zone_id != zone_id:
        raise HTTPException(status_code=404, detail="Terminal not assigned to this zone")

    db.execute(text(
        "UPDATE iclock_terminal SET zone_id = NULL WHERE id = :rid"
    ), {"rid": reader_id})

    db.commit()

    # Sync both systems after removal
    _sync_zone_to_access_control(zone_id, db)
    db.commit()

    return {"message": "Reader removed from zone"}


@router.get("/{zone_id}/current-personnel")
def get_current_personnel(
    zone_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT latest.emp_code, latest.event_type, latest.punch_time, latest.device_sn,
               p.first_name, p.last_name, p.photo_url, p.department, p.position
        FROM (
            SELECT DISTINCT ON (emp_code)
                emp_code, event_type, punch_time, device_sn
            FROM zone_personnel_tracking
            WHERE zone_id = :zid
            ORDER BY emp_code, punch_time DESC
        ) latest
        LEFT JOIN personnel p ON p.emp_code = latest.emp_code
        WHERE latest.event_type = 'CLOCK_IN'
        ORDER BY latest.punch_time DESC
    """), {"zid": zone_id}).fetchall()
    return [
        {
            "emp_code": r.emp_code,
            "full_name": f"{r.first_name or ''} {r.last_name or ''}".strip() or r.emp_code,
            "punch_time": r.punch_time.isoformat() if r.punch_time else None,
            "device_sn": r.device_sn,
            "photo_url": r.photo_url,
            "department": r.department,
            "designation": r.position,
        }
        for r in rows
    ]


@router.get("/{zone_id}/tracking")
def get_tracking_log(
    zone_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT zpt.emp_code, zpt.event_type, zpt.punch_time, zpt.device_sn,
               p.first_name, p.last_name
        FROM zone_personnel_tracking zpt
        LEFT JOIN personnel p ON p.emp_code = zpt.emp_code
        WHERE zpt.zone_id = :zid
        ORDER BY zpt.punch_time DESC
        LIMIT :lim
    """), {"zid": zone_id, "lim": limit}).fetchall()
    return [
        {
            "emp_code": r.emp_code,
            "full_name": f"{r.first_name or ''} {r.last_name or ''}".strip() or r.emp_code,
            "event_type": r.event_type,
            "punch_time": r.punch_time.isoformat() if r.punch_time else None,
            "device_sn": r.device_sn,
        }
        for r in rows
    ]


@router.post("/{zone_id}/reset-occupancy")
def reset_occupancy(
    zone_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Force-reset a zone's occupancy to 0: close every open stay in this zone in
    zone_personnel_tracking, clear personnel.current_zone_id for anyone pointing at
    it, and reset the stored count. Attendance punches are never touched.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    # Location lives in zone_personnel_tracking. This used to also insert a fake
    # CHECK-OUT punch into iclock_transaction, which the attendance engine then read
    # as a real tap (corrupting that person's hours) — removed.
    cleared = []
    now = datetime.utcnow()

    # Also clear any zone_personnel_tracking CLOCK_INs for this zone
    # by inserting CLOCK_OUTs so _recalc_zone_occupancy returns 0
    tracking_stale = db.execute(text("""
        SELECT DISTINCT emp_code, device_sn
        FROM (
            SELECT DISTINCT ON (emp_code) emp_code, event_type, device_sn
            FROM zone_personnel_tracking
            WHERE zone_id = :zid
            ORDER BY emp_code, punch_time DESC
        ) last
        WHERE event_type = 'CLOCK_IN'
    """), {"zid": zone_id}).fetchall()

    for row in tracking_stale:
        db.execute(text("""
            INSERT INTO zone_personnel_tracking
                (zone_id, emp_code, device_sn, event_type, punch_time, previous_zone_id)
            VALUES (:zid, :ec, :sn, 'CLOCK_OUT', :pt, :zid)
        """), {"zid": zone_id, "ec": row.emp_code, "sn": row.device_sn, "pt": now})
        cleared.append(row.emp_code)

    # Clear personnel.current_zone_id for anyone still pointing here
    db.execute(text(
        "UPDATE personnel SET current_zone_id = NULL WHERE current_zone_id = :zid"
    ), {"zid": zone_id})

    # Reset zone counters
    db.execute(text("""
        UPDATE zones SET current_occupancy = 0, current_personnel_count = 0,
            updated_at = NOW() WHERE id = :zid
    """), {"zid": zone_id})

    db.commit()

    return {
        "success": True,
        "zone_id": zone_id,
        "cleared_employees": cleared,
        "cleared_count": len(set(cleared)),
        "message": f"Zone occupancy reset. {len(set(cleared))} phantom check-in(s) cleared.",
    }


@router.post("/{zone_id}/push-to-biotime")
def push_to_biotime(
    zone_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    existing = db.query(BioTimeArea).filter(
        or_(BioTimeArea.area_code == zone.code, BioTimeArea.area_name == zone.name)
    ).first()

    if existing:
        existing.area_code = zone.code
        existing.area_name = zone.name
        db.commit()
        return {"message": "BioTime area updated", "biotime_area_id": existing.id}

    bt = BioTimeArea(area_code=zone.code, area_name=zone.name)
    db.add(bt)
    db.commit()
    db.refresh(bt)

    zone.last_sync_at = datetime.utcnow()
    db.commit()

    return {"message": "Zone pushed to BioTime", "biotime_area_id": bt.id}


# ── Live zone WebSocket ───────────────────────────────────────────────────────

@router.websocket("/ws")
async def zone_live_ws(websocket: WebSocket):
    """
    WebSocket endpoint for live zone occupancy.
    On connect: sends a snapshot of all zone counts.
    Stays open: receives broadcast_zone_update() pushes whenever a reader swipe
    changes a zone's occupancy.
    """
    await zone_ws_connect(websocket)
    try:
        # Use a SHORT-LIVED session for the snapshot only. Do NOT hold a pooled DB
        # connection (Depends(get_db)) for the whole WS lifetime — with several
        # dashboard viewers open that would exhaust the connection pool.
        from ..core.database import SessionLocal
        snap_db = SessionLocal()
        try:
            rows = snap_db.execute(text(
                "SELECT id, name, current_personnel_count FROM zones WHERE is_active = true ORDER BY name"
            )).fetchall()
            snapshot = [
                {"type": "zone_snapshot", "zone_id": r.id,
                 "count": int(r.current_personnel_count or 0), "zone_name": r.name}
                for r in rows
            ]
        finally:
            snap_db.close()
        await websocket.send_text(json.dumps(snapshot))

        # Keep connection open; broadcasts arrive via broadcast_zone_update()
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        zone_ws_disconnect(websocket)
    except Exception:
        zone_ws_disconnect(websocket)


@router.get("/{zone_id}/live-personnel")
def get_zone_live_personnel(
    zone_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Who is currently inside this zone — from zone_personnel_tracking.
    Muster-aware: during a drill, Safe (mustered) people are removed from their work
    zone's list (work zones show only the missing) and instead listed at the muster
    zone they reported to — matching the muster-aware occupancy counts."""
    safe_codes, _safe_by_zone, muster_active = _muster_occupancy_context(db)

    _exclude_safe = "AND last.emp_code <> ALL(:safe)" if safe_codes else ""
    params = {"zid": zone_id}
    if safe_codes:
        params["safe"] = list(safe_codes)

    rows = db.execute(text(f"""
        SELECT
            last.emp_code,
            last.punch_time   AS entry_time,
            last.device_sn,
            COALESCE(TRIM(p.first_name || ' ' || p.last_name), last.emp_code) AS full_name,
            p.photo_url,
            p.department,
            p.position
        FROM (
            SELECT DISTINCT ON (emp_code)
                emp_code, event_type, punch_time, device_sn
            FROM zone_personnel_tracking
            WHERE zone_id = :zid
            ORDER BY emp_code, punch_time DESC
        ) last
        LEFT JOIN personnel p ON p.emp_code = last.emp_code
        WHERE last.event_type = 'CLOCK_IN'
          {_exclude_safe}
        ORDER BY last.punch_time DESC
    """), params).fetchall()

    result = [
        {
            "emp_code":  r.emp_code,
            "full_name": r.full_name,
            "entry_time": r.entry_time.isoformat() if r.entry_time else None,
            "device_sn": r.device_sn,
            "photo_url": r.photo_url,
            "department": r.department,
            "designation": r.position,
            "muster_status": None,
        }
        for r in rows
    ]

    # During a drill, also list the Safe people who mustered at a reader in THIS zone,
    # so the muster zone's list matches its (boosted) occupancy count.
    if muster_active:
        safe_here = db.execute(text("""
            SELECT ml.emp_code, ml.check_time, ml.device_sn,
                   COALESCE(TRIM(p.first_name || ' ' || p.last_name), ml.emp_code) AS full_name,
                   p.photo_url, p.department, p.position
            FROM mustering_log ml
            JOIN iclock_terminal t ON t.sn = ml.device_sn AND t.zone_id = :zid
            JOIN mustering_event e ON e.id = ml.event_id AND e.status = 0
            LEFT JOIN personnel p ON p.emp_code = ml.emp_code
            WHERE ml.status = 1
        """), {"zid": zone_id}).fetchall()
        for r in safe_here:
            result.append({
                "emp_code":  r.emp_code,
                "full_name": r.full_name,
                "entry_time": r.check_time.isoformat() if r.check_time else None,
                "device_sn": r.device_sn,
                "photo_url": r.photo_url,
                "department": r.department,
                "designation": r.position,
                "muster_status": "safe",
            })

    return result
