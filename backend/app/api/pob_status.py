"""
POB Status API — real-time Personnel On Board tracking.

Endpoints:
  GET /dashboard            — KPI strip, location breakdown, live activity feed
  GET /personnel-list       — searchable / filterable onboard personnel list
  GET /department-breakdown — headcount grouped by department
  GET /rotation-overdue     — personnel exceeding rotation limit (28 days)
  GET /attendance-trend     — N-day daily check-in / check-out trend
  GET /verify-methods       — today's biometric verification method breakdown
  GET /export-csv           — download current headcount as CSV
"""

import csv
import io
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

from ..core.database import get_db
from ..core.dependencies import get_current_user

router = APIRouter()

_ROTATION_MAX_DAYS = 28


def _norm_tz(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _location_bucket(name: str) -> str:
    n = name.lower()
    if any(x in n for x in ["offshore", "platform", "rig", "fps", "fpso", "wellhead", "jacket"]):
        return "offshore"
    if any(x in n for x in ["transit", "helicopter", "chopper", "boat", "vessel", "flight", "travel"]):
        return "transit"
    return "onshore"


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_pob_dashboard(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Real-time POB KPIs from personnel.is_onboard, location breakdown, live activity."""

    # ── headcount ──────────────────────────────────────────────────────
    total = db.execute(text(
        "SELECT COUNT(*) FROM personnel WHERE is_onboard = TRUE AND is_active = TRUE"
    )).scalar() or 0

    # Clock-ins / clock-outs the way attendance counts them: SITE-time day, taps on
    # attendance (T&A) readers only, first tap = in, a later tap = out. (The F18 stamps
    # every tap "check-out", so counting punch_state said "0 in, 1 out" for a person
    # whose only tap was their arrival.)
    from ..services.attendance_calculation_service import SITE_TZ
    tz = str(SITE_TZ)
    from ..services.attendance_calculation_service import min_work_minutes
    minw = min_work_minutes(db)   # a tap closer than this to the first is a repeat, not an out

    def flow(day_offset: int):
        row = db.execute(text(f"""
            WITH taps AS (
                SELECT t.emp_code, COUNT(*) AS n,
                       EXTRACT(EPOCH FROM MAX(t.punch_time) - MIN(t.punch_time)) / 60 AS span_min
                FROM iclock_transaction t
                LEFT JOIN iclock_terminal term ON term.sn = t.terminal_sn
                WHERE (t.punch_time AT TIME ZONE '{tz}')::date = (NOW() AT TIME ZONE '{tz}')::date - :off
                  AND COALESCE(NULLIF(term.reader_purpose, ''), 'ATTENDANCE') = 'ATTENDANCE'
                GROUP BY t.emp_code)
            SELECT COUNT(*) AS ins, COUNT(*) FILTER (WHERE n > 1 AND span_min >= :minw) AS outs FROM taps
        """), {"off": day_offset, "minw": minw}).fetchone()
        return int(row.ins or 0), int(row.outs or 0)

    try:
        ci_today, co_today = flow(0)
        ci_yest, co_yest = flow(1)
    except Exception:
        db.rollback()
        ci_today = co_today = ci_yest = co_yest = 0
    active_personnel = db.execute(text("SELECT COUNT(*) FROM personnel WHERE is_active = TRUE")).scalar() or 0

    # ── location breakdown ─────────────────────────────────────────────
    try:
        loc_rows = db.execute(text("""
            SELECT
              COALESCE(NULLIF(TRIM(current_location), ''), 'Unassigned') AS loc,
              COUNT(*) AS cnt
            FROM personnel
            WHERE is_onboard = TRUE AND is_active = TRUE
            GROUP BY loc ORDER BY cnt DESC
        """)).fetchall()
        by_location = {r[0]: int(r[1]) for r in loc_rows}
    except Exception:
        by_location = {}

    offshore = sum(v for k, v in by_location.items() if _location_bucket(k) == "offshore")
    transit  = sum(v for k, v in by_location.items() if _location_bucket(k) == "transit")
    onshore  = total - offshore - transit

    # ── rotation overdue ────────────────────────────────────────────────
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_ROTATION_MAX_DAYS)
        overdue = db.execute(text("""
            SELECT COUNT(*) FROM personnel
            WHERE is_onboard = TRUE AND is_active = TRUE
              AND pob_since IS NOT NULL AND pob_since < :cutoff
        """), {"cutoff": cutoff}).scalar() or 0
    except Exception:
        overdue = 0

    # ── live activity feed: door taps on ACCESS-CONTROL readers (last 24 h) ──
    # Who came on site, moved between zones or was refused. T&A clock-ins are not
    # shown here: a T&A terminal can be in another state or country, so it says
    # nothing about who is on board.
    recent_events = []
    try:
        rows = db.execute(text("""
            SELECT a.id, a."timestamp", a.direction, a.access_granted,
                   COALESCE(NULLIF(a.access_method, ''), NULLIF(a.verification_method, ''), 'Card') AS method,
                   COALESCE(p.full_name, TRIM(p.first_name || ' ' || p.last_name), 'Unknown card') AS pname,
                   COALESCE(z.name, 'Unknown zone') AS loc,
                   COALESCE(p.department, '—') AS dept,
                   a.denial_reason
            FROM access_logs a
            LEFT JOIN personnel p ON p.id = a.personnel_id
            LEFT JOIN zones z ON z.id = a.zone_id
            WHERE a."timestamp" >= NOW() - INTERVAL '24 hours'
            ORDER BY a."timestamp" DESC
            LIMIT 25
        """)).fetchall()
        for r in rows:
            recent_events.append({
                "id":            r.id,
                "timestamp":     r.timestamp.isoformat() if r.timestamp else None,
                "type":          ("DENIED" if not r.access_granted else
                                  "ENTRY" if r.direction == "ENTRY" else "EXIT" if r.direction == "EXIT" else "UNKNOWN"),
                "verify_method": str(r.method).title(),
                "personnel":     r.pname,
                "location":      r.loc,
                "department":    r.dept,
                "reason":        r.denial_reason,
            })
    except Exception as e:
        db.rollback()
        logger.warning(f"Live feed query failed: {e}")

    # ── active transports (ORM — table name is dynamic) ─────────────────
    active_transports = []
    try:
        from ..models.emergency import TransportSchedule
        schedules = db.query(TransportSchedule).filter(
            TransportSchedule.status.in_(["SCHEDULED", "CONFIRMED", "BOARDING"])
        ).order_by(TransportSchedule.departure_time).limit(10).all()
        for s in schedules:
            manifest = s.passenger_manifest or []
            if isinstance(manifest, str):
                import json
                try:
                    manifest = json.loads(manifest)
                except Exception:
                    manifest = []
            active_transports.append({
                "id":                s.id,
                "type":              s.schedule_type,
                "departure_location": s.departure_location,
                "arrival_location":   s.arrival_location,
                "departure_time":     s.departure_time.isoformat() if s.departure_time else None,
                "estimated_arrival":  s.arrival_time.isoformat()   if s.arrival_time   else None,
                "passenger_count":    len(manifest),
                "status":             s.status,
            })
    except Exception as e:
        logger.debug(f"Transports query skipped: {e}")

    # Visitors checked in at the gate are on board too (they are on the muster list).
    try:
        visitors = db.execute(text("SELECT COUNT(*) FROM vis_visit_log WHERE check_out_time IS NULL "
                                   "AND status IN (0, 2)")).scalar() or 0
    except Exception:
        db.rollback()
        visitors = 0
    return {
        "total":                  total,
        "visitors_on_site":       visitors,
        "total_with_visitors":    total + visitors,
        "offshore_count":         offshore,
        "onshore_count":          onshore,
        "transit_count":          transit,
        "by_location":            by_location,
        "checkins_today":         ci_today,
        "checkins_yesterday":     ci_yest,
        "checkouts_today":        co_today,
        "checkouts_yesterday":    co_yest,
        "active_personnel":       active_personnel,
        "rotation_overdue_count": overdue,
        "rotation_max_days":      _ROTATION_MAX_DAYS,
        "recent_events":          recent_events,
        "active_transports":      active_transports,
        "last_updated":           datetime.now(timezone.utc).isoformat(),
    }


# ── Personnel list ────────────────────────────────────────────────────────────

@router.get("/personnel-list")
async def get_pob_personnel_list(
    location:     Optional[str]  = Query(None),
    department:   Optional[str]  = Query(None),
    search:       Optional[str]  = Query(None),
    overdue_only: bool           = Query(False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    where  = ["p.is_onboard = TRUE", "p.is_active = TRUE"]
    params: dict = {}

    if location:
        where.append("LOWER(COALESCE(p.current_location, '')) ILIKE :loc")
        params["loc"] = f"%{location.lower()}%"
    if department:
        where.append("LOWER(COALESCE(p.department, '')) ILIKE :dept")
        params["dept"] = f"%{department.lower()}%"
    if search:
        where.append(
            "(LOWER(COALESCE(p.full_name, TRIM(p.first_name||' '||p.last_name), '')) ILIKE :s"
            " OR LOWER(p.emp_code) ILIKE :s)"
        )
        params["s"] = f"%{search.lower()}%"
    if overdue_only:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_ROTATION_MAX_DAYS)
        where.append("p.pob_since IS NOT NULL AND p.pob_since < :cutoff")
        params["cutoff"] = cutoff

    rows = db.execute(text(f"""
        SELECT
          p.id, p.emp_code,
          COALESCE(p.full_name, TRIM(p.first_name||' '||p.last_name)) AS name,
          COALESCE(p.department, '—') AS dept,
          COALESCE(p.position,   '—') AS pos,
          COALESCE(NULLIF(TRIM(p.current_location), ''), 'Unassigned') AS loc,
          p.pob_since, p.photo_url
        FROM personnel p
        WHERE {' AND '.join(where)}
        ORDER BY p.pob_since ASC NULLS LAST
        LIMIT 500
    """), params).fetchall()

    now  = datetime.now(timezone.utc)
    data = []
    for r in rows:
        ps   = _norm_tz(r[6])
        days = (now - ps).days if ps else None
        data.append({
            "id":               r[0],
            "emp_code":         r[1],
            "name":             r[2],
            "department":       r[3],
            "position":         r[4],
            "location":         r[5],
            "pob_since":        r[6].isoformat() if r[6] else None,
            "days_onboard":     days,
            "rotation_overdue": days is not None and days > _ROTATION_MAX_DAYS,
            "photo_url":        r[7],
        })
    return {"success": True, "data": data, "total": len(data)}


# ── Department breakdown ───────────────────────────────────────────────────────

@router.get("/department-breakdown")
async def get_department_breakdown(db: Session = Depends(get_db)):
    try:
        rows = db.execute(text("""
            SELECT
              COALESCE(NULLIF(TRIM(department), ''), 'Unassigned') AS dept,
              COUNT(*) AS cnt
            FROM personnel
            WHERE is_onboard = TRUE AND is_active = TRUE
            GROUP BY dept ORDER BY cnt DESC LIMIT 20
        """)).fetchall()
        return {"data": [{"department": r[0], "count": int(r[1])} for r in rows]}
    except Exception as e:
        logger.warning(f"Department breakdown failed: {e}")
        return {"data": []}


# ── Rotation overdue ───────────────────────────────────────────────────────────

@router.get("/rotation-overdue")
async def get_rotation_overdue(db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=_ROTATION_MAX_DAYS)
    try:
        rows = db.execute(text("""
            SELECT
              p.id, p.emp_code,
              COALESCE(p.full_name, TRIM(p.first_name||' '||p.last_name)) AS name,
              COALESCE(p.department, '—') AS dept,
              COALESCE(p.position,   '—') AS pos,
              COALESCE(NULLIF(TRIM(p.current_location), ''), 'Unassigned') AS loc,
              p.pob_since
            FROM personnel p
            WHERE p.is_onboard = TRUE AND p.is_active = TRUE
              AND p.pob_since IS NOT NULL AND p.pob_since < :cutoff
            ORDER BY p.pob_since ASC
        """), {"cutoff": cutoff}).fetchall()
    except Exception as e:
        logger.warning(f"Rotation overdue query failed: {e}")
        return {"data": [], "total": 0, "rotation_max_days": _ROTATION_MAX_DAYS}

    now  = datetime.now(timezone.utc)
    data = []
    for r in rows:
        ps   = _norm_tz(r[6])
        days = (now - ps).days if ps else 0
        data.append({
            "id":           r[0],
            "emp_code":     r[1],
            "name":         r[2],
            "department":   r[3],
            "position":     r[4],
            "location":     r[5],
            "pob_since":    r[6].isoformat() if r[6] else None,
            "days_onboard": days,
            "days_overdue": max(0, days - _ROTATION_MAX_DAYS),
        })
    return {"data": data, "total": len(data), "rotation_max_days": _ROTATION_MAX_DAYS}


# ── Last activity (time since last badge event) ────────────────────────────────

# On-site personnel with no badge/reader event for longer than this are surfaced
# as a potential safety concern — earlier than the rotation-overdue (days) view.
_STALE_MINUTES = 120


@router.get("/last-activity")
async def get_last_activity(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """On-site personnel ranked by time since their last badge/reader event
    (longest-idle first) so potentially missing people surface early."""
    try:
        rows = db.execute(text("""
            SELECT
              p.id, p.emp_code,
              COALESCE(p.full_name, TRIM(p.first_name||' '||p.last_name)) AS name,
              COALESCE(p.department, '—') AS dept,
              COALESCE(NULLIF(TRIM(p.current_location), ''), 'Unassigned') AS loc,
              t.last_punch
            FROM personnel p
            LEFT JOIN LATERAL (
              SELECT MAX(punch_time) AS last_punch
              FROM iclock_transaction
              WHERE emp_code = p.emp_code
            ) t ON TRUE
            WHERE p.is_onboard = TRUE AND p.is_active = TRUE
            ORDER BY t.last_punch ASC NULLS FIRST
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    except Exception as e:
        logger.warning(f"Last-activity query failed: {e}")
        return {"data": [], "total": 0, "stale_count": 0, "stale_minutes": _STALE_MINUTES}

    now, data, stale = datetime.now(timezone.utc), [], 0
    for r in rows:
        lp   = _norm_tz(r[5])
        mins = int((now - lp).total_seconds() // 60) if lp else None
        is_stale = mins is None or mins >= _STALE_MINUTES
        stale += 1 if is_stale else 0
        data.append({
            "id":            r[0],
            "emp_code":      r[1],
            "name":          r[2],
            "department":    r[3],
            "location":      r[4],
            "last_event":    r[5].isoformat() if r[5] else None,
            "minutes_since": mins,
            "never_seen":    lp is None,
            "stale":         is_stale,
        })
    return {"data": data, "total": len(data), "stale_count": stale, "stale_minutes": _STALE_MINUTES}


# ── Attendance trend ───────────────────────────────────────────────────────────

@router.get("/attendance-trend")
async def get_attendance_trend(
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        since = date.today() - timedelta(days=days)
        rows  = db.execute(text("""
            SELECT
              punch_time::date                                      AS day,
              COUNT(*)                                              AS total,
              -- 255 = auto-detect / undifferentiated punch; the rest of the system
              -- (attendance.py, ai/tools.py) treats it as a check-in/presence event,
              -- so count it here too — otherwise days with only auto-detect punches
              -- show a flat zero line despite real activity.
              COUNT(*) FILTER (WHERE punch_state IN (0, 255))      AS check_ins,
              COUNT(*) FILTER (WHERE punch_state = 1)              AS check_outs
            FROM iclock_transaction
            WHERE punch_time::date >= :since
            GROUP BY day ORDER BY day
        """), {"since": since}).fetchall()
        return {
            "trend": [
                {"day": str(r[0]), "total": int(r[1]),
                 "check_ins": int(r[2]), "check_outs": int(r[3])}
                for r in rows
            ]
        }
    except Exception as e:
        logger.warning(f"attendance-trend failed: {e}")
        return {"trend": []}


# ── Verify methods ─────────────────────────────────────────────────────────────

@router.get("/verify-methods")
async def get_verify_methods(db: Session = Depends(get_db)) -> Dict[str, Any]:
    LABELS = {0: "Password", 1: "Fingerprint", 2: "Face", 3: "Card"}
    try:
        rows  = db.execute(text("""
            SELECT verify_type, COUNT(*) AS cnt
            FROM iclock_transaction
            WHERE punch_time::date = CURRENT_DATE
            GROUP BY verify_type
        """)).fetchall()
        total = sum(int(r[1]) for r in rows)
        return {
            "methods": [
                {"type":  LABELS.get(r[0], f"Type {r[0]}"),
                 "count": int(r[1]),
                 "pct":   round(int(r[1]) / total * 100) if total else 0}
                for r in rows
            ],
            "total": total,
        }
    except Exception as e:
        logger.warning(f"verify-methods failed: {e}")
        return {"methods": [], "total": 0}


# ── CSV export ─────────────────────────────────────────────────────────────────

@router.get("/export-csv")
async def export_pob_csv(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT
          p.emp_code,
          COALESCE(p.full_name, TRIM(p.first_name||' '||p.last_name)) AS name,
          COALESCE(p.department, '')                                   AS dept,
          COALESCE(p.position,   '')                                   AS pos,
          COALESCE(NULLIF(TRIM(p.current_location), ''), 'Unassigned') AS loc,
          p.pob_since
        FROM personnel p
        WHERE p.is_onboard = TRUE AND p.is_active = TRUE
        ORDER BY p.current_location, p.department
    """)).fetchall()

    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["Emp Code", "Name", "Department", "Position",
                "Location", "POB Since (UTC)", "Days Onboard"])
    now = datetime.now(timezone.utc)
    for r in rows:
        ps   = _norm_tz(r[5])
        days = (now - ps).days if ps else ""
        w.writerow([
            r[0], r[1], r[2], r[3], r[4],
            ps.strftime("%Y-%m-%d %H:%M") if ps else "",
            days,
        ])

    fname = f"POB_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
