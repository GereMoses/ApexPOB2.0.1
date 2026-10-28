"""
Personnel Shift Management API — now backed by att_shift (single source of truth).
Provides the same response shape as the original shift_management table endpoints
so the Personnel frontend requires no changes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import List, Optional, Dict, Any
from datetime import datetime, date, time, timedelta

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.shift_management import ScheduleManagement
from ..models.personnel import Personnel
from ..schemas.shift_management import (
    ShiftManagementCreate, ShiftManagementUpdate,
    ScheduleManagementCreate, ScheduleManagementUpdate, ScheduleManagementResponse,
    ScheduleSwapRequest, ShiftAssignment
)
from ..models.user import User

router = APIRouter()

# ── helpers ───────────────────────────────────────────────────────────────────

def _row_to_shift(r) -> dict:
    """Map att_shift row → Personnel ShiftManagementResponse shape."""
    d = dict(r._mapping)
    # Normalise field names the frontend expects
    d["shift_name"] = d.get("alias") or d.get("name") or ""
    d["shift_code"] = d.get("shift_code") or ""
    d["start_time"] = d.get("start_time")   # already text or None
    d["end_time"]   = d.get("end_time")
    d["shift_type"] = d.get("shift_type") or "CUSTOM"
    d["break_duration"]             = d.get("break_duration") or 0
    d["working_hours"]              = d.get("working_hours") or 8
    d["is_night_shift"]             = bool(d.get("is_night_shift"))
    d["is_weekend_shift"]           = bool(d.get("is_weekend_shift"))
    d["is_flexible"]                = bool(d.get("is_flexible"))
    d["grace_period_minutes"]       = d.get("grace_period_minutes") or 15
    d["max_late_minutes"]           = d.get("max_late_minutes") or 60
    d["max_early_departure_minutes"]= d.get("max_early_departure_minutes") or 30
    d["overtime_threshold_minutes"] = d.get("overtime_threshold_minutes") or 30
    d["rotation_pattern"]           = d.get("rotation_pattern")
    d["rotation_cycle_days"]        = d.get("rotation_cycle_days")
    d["description"]                = d.get("description")
    d["is_active"]                  = bool(d.get("is_active", True))
    d["created_at"]                 = d.get("created_at")
    d["updated_at"]                 = d.get("updated_at")
    return d

_SELECT_SHIFT = """
    SELECT
        s.id,
        COALESCE(s.alias, s.name)                       AS alias,
        s.name,
        s.shift_code,
        COALESCE(s.shift_type, 'CUSTOM')                AS shift_type,
        s.start_time::text                              AS start_time,
        s.end_time::text                                AS end_time,
        COALESCE(s.break_duration, 0)                   AS break_duration,
        COALESCE(s.working_hours, 8)                    AS working_hours,
        COALESCE(s.is_night_shift,   false)             AS is_night_shift,
        COALESCE(s.is_weekend_shift, false)             AS is_weekend_shift,
        COALESCE(s.is_flexible,      false)             AS is_flexible,
        s.rotation_pattern,
        s.rotation_cycle_days,
        COALESCE(s.grace_period_minutes,        15)     AS grace_period_minutes,
        COALESCE(s.max_late_minutes,            60)     AS max_late_minutes,
        COALESCE(s.max_early_departure_minutes, 30)     AS max_early_departure_minutes,
        COALESCE(s.overtime_threshold_minutes,  30)     AS overtime_threshold_minutes,
        s.description,
        COALESCE(s.is_active, true)                     AS is_active,
        s.created_at,
        s.updated_at
    FROM att_shift s
"""


# ==================== Shift Management Endpoints ====================

@router.post("/shifts", status_code=status.HTTP_201_CREATED)
async def create_shift(
    shift_data: ShiftManagementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new shift — written to att_shift (single source of truth)."""
    # Unique shift_code check
    if shift_data.shift_code:
        existing = db.execute(
            text("SELECT id FROM att_shift WHERE shift_code = :code"),
            {"code": shift_data.shift_code}
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Shift with code '{shift_data.shift_code}' already exists"
            )

    created_by = getattr(current_user, 'id', None)
    d = shift_data.model_dump()
    work_days = "1234567" if d.get("is_weekend_shift") else "12345"
    days_str  = "Mon,Tue,Wed,Thu,Fri,Sat,Sun" if d.get("is_weekend_shift") else "Mon,Tue,Wed,Thu,Fri"
    rp = d.get("rotation_pattern")
    import json as _json
    rotation_pattern_val = _json.dumps(rp) if rp else None

    # Also mirror a timetable entry so devices stay in sync
    tt = db.execute(text("""
        INSERT INTO att_timetable (name, start_time, end_time, late_grace_minutes, early_exit_minutes)
        VALUES (:name, :start_time, :end_time, :late_grace, :early_exit)
        ON CONFLICT DO NOTHING
        RETURNING id
    """), {
        "name":       d["shift_name"],
        "start_time": d["start_time"],
        "end_time":   d["end_time"],
        "late_grace": d.get("grace_period_minutes", 15),
        "early_exit": d.get("max_early_departure_minutes", 30),
    }).fetchone()
    timetable_id = tt.id if tt else None

    row = db.execute(text("""
        INSERT INTO att_shift (
            name, alias, shift_code, timetable_id,
            work_days, days_of_week,
            shift_type, start_time, end_time, break_duration, working_hours,
            is_night_shift, is_weekend_shift, is_flexible,
            rotation_pattern, rotation_cycle_days,
            grace_period_minutes, max_late_minutes,
            max_early_departure_minutes, overtime_threshold_minutes,
            description, is_active, created_by
        ) VALUES (
            :shift_name, :shift_name, :shift_code, :timetable_id,
            :work_days, :days_str,
            :shift_type, :start_time, :end_time, :break_duration, :working_hours,
            :is_night_shift, :is_weekend_shift, :is_flexible,
            CAST(:rotation_pattern AS jsonb), :rotation_cycle_days,
            :grace_period_minutes, :max_late_minutes,
            :max_early_departure_minutes, :overtime_threshold_minutes,
            :description, :is_active, :created_by
        )
        RETURNING *
    """), {
        **d,
        "timetable_id":      timetable_id,
        "work_days":         work_days,
        "days_str":          days_str,
        "rotation_pattern":  rotation_pattern_val,
        "created_by":        created_by,
    }).fetchone()
    db.commit()
    return _row_to_shift(db.execute(
        text(_SELECT_SHIFT + " WHERE s.id = :id"), {"id": row.id}
    ).fetchone())


@router.get("/shifts")
async def get_shifts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    shift_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all shifts from att_shift."""
    where = ["1=1"]
    params: dict = {}
    if is_active is not None:
        where.append("COALESCE(s.is_active, true) = :is_active")
        params["is_active"] = is_active
    if shift_type:
        where.append("s.shift_type = :shift_type")
        params["shift_type"] = shift_type
    if search:
        where.append("(COALESCE(s.alias, s.name) ILIKE :search OR s.shift_code ILIKE :search)")
        params["search"] = f"%{search}%"

    q = _SELECT_SHIFT + " WHERE " + " AND ".join(where)
    q += " ORDER BY COALESCE(s.alias, s.name) LIMIT :limit OFFSET :skip"
    params["limit"] = limit
    params["skip"]  = skip

    rows = db.execute(text(q), params).fetchall()
    return [_row_to_shift(r) for r in rows]


@router.post("/shifts/sync-biotime")
async def sync_shifts_to_biotime(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """No-op — att_shift IS the BioTime table. Returns current count."""
    count = db.execute(text("SELECT COUNT(*) FROM att_shift WHERE COALESCE(is_active, true) = true")).scalar()
    return {"synced": 0, "already_exists": count, "total": count,
            "message": "att_shift is now the single source of truth — no sync needed"}


@router.get("/shifts/{shift_id}")
async def get_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific shift by ID."""
    row = db.execute(
        text(_SELECT_SHIFT + " WHERE s.id = :id"), {"id": shift_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Shift {shift_id} not found")
    return _row_to_shift(row)


@router.put("/shifts/{shift_id}")
async def update_shift(
    shift_id: int,
    shift_data: ShiftManagementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update shift in att_shift."""
    existing = db.execute(
        text("SELECT id FROM att_shift WHERE id = :id"), {"id": shift_id}
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Shift {shift_id} not found")

    d = shift_data.model_dump(exclude_unset=True)
    if not d:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets = []
    params: dict = {"shift_id": shift_id}
    field_map = {
        "shift_name": ("name", "alias"),   # update both name and alias
        "shift_code": ("shift_code",),
        "start_time": ("start_time",),
        "end_time":   ("end_time",),
        "shift_type": ("shift_type",),
        "break_duration":             ("break_duration",),
        "working_hours":              ("working_hours",),
        "is_night_shift":             ("is_night_shift",),
        "is_weekend_shift":           ("is_weekend_shift",),
        "is_flexible":                ("is_flexible",),
        "rotation_pattern":           ("rotation_pattern",),
        "rotation_cycle_days":        ("rotation_cycle_days",),
        "grace_period_minutes":       ("grace_period_minutes",),
        "max_late_minutes":           ("max_late_minutes",),
        "max_early_departure_minutes":("max_early_departure_minutes",),
        "overtime_threshold_minutes": ("overtime_threshold_minutes",),
        "description":                ("description",),
        "is_active":                  ("is_active",),
    }
    for src_field, col_tuple in field_map.items():
        if src_field not in d:
            continue
        val = d[src_field]
        if src_field == "shift_name":
            sets.append("name = :shift_name, alias = :shift_name")
            params["shift_name"] = val
        elif src_field == "rotation_pattern":
            import json as _json
            sets.append("rotation_pattern = CAST(:rotation_pattern AS jsonb)")
            params["rotation_pattern"] = _json.dumps(val) if val else None
        else:
            sets.append(f"{col_tuple[0]} = :{src_field}")
            params[src_field] = val

    db.execute(text(f"UPDATE att_shift SET {', '.join(sets)} WHERE id = :shift_id"), params)
    db.commit()

    row = db.execute(text(_SELECT_SHIFT + " WHERE s.id = :id"), {"id": shift_id}).fetchone()
    return _row_to_shift(row)


@router.delete("/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete shift from att_shift, cleaning up dependents first."""
    existing = db.execute(
        text("SELECT id FROM att_shift WHERE id = :id"), {"id": shift_id}
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Shift {shift_id} not found")

    db.execute(text("DELETE FROM att_schedule WHERE shift_id = :id"),       {"id": shift_id})
    db.execute(text("UPDATE att_report SET shift_id = NULL WHERE shift_id = :id"), {"id": shift_id})
    db.execute(text("UPDATE mustering_expected SET shift_id = NULL WHERE shift_id = :id"), {"id": shift_id})
    # Also clean schedule_management references
    db.execute(text("DELETE FROM schedule_management WHERE shift_id = :id"), {"id": shift_id})
    db.execute(text("DELETE FROM att_shift WHERE id = :id"),                {"id": shift_id})
    db.commit()
    return None


@router.post("/shifts/{shift_id}/assign")
async def assign_shift_to_personnel(
    shift_id: int,
    assignment: ShiftAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign a shift to personnel for a date range."""
    shift_row = db.execute(
        text(_SELECT_SHIFT + " WHERE s.id = :id"), {"id": shift_id}
    ).fetchone()
    if not shift_row:
        raise HTTPException(status_code=404, detail=f"Shift {shift_id} not found")

    personnel = db.query(Personnel).filter(Personnel.id == assignment.personnel_id).first()
    if not personnel:
        raise HTTPException(status_code=404, detail=f"Personnel {assignment.personnel_id} not found")

    shift = _row_to_shift(shift_row)
    start_t = datetime.strptime(shift["start_time"], "%H:%M:%S").time() if shift.get("start_time") else time(8, 0)
    current_date = assignment.start_date.date()
    end_date = assignment.end_date.date() if assignment.end_date else current_date

    while current_date <= end_date:
        sched = ScheduleManagement(
            personnel_id=assignment.personnel_id,
            shift_id=shift_id,
            schedule_date=datetime.combine(current_date, start_t),
            assigned_by=getattr(current_user, 'id', None),
            notes=assignment.notes
        )
        db.add(sched)
        current_date = datetime.fromordinal(current_date.toordinal() + 1).date()

    db.commit()
    return shift


# ==================== Schedule/Roster Management Endpoints ====================

@router.post("/schedules", response_model=ScheduleManagementResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_data: ScheduleManagementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new schedule."""
    personnel = db.query(Personnel).filter(Personnel.id == schedule_data.personnel_id).first()
    if not personnel:
        raise HTTPException(status_code=404, detail=f"Personnel {schedule_data.personnel_id} not found")

    shift_row = db.execute(text("SELECT id FROM att_shift WHERE id = :id"), {"id": schedule_data.shift_id}).fetchone()
    if not shift_row:
        raise HTTPException(status_code=404, detail=f"Shift {schedule_data.shift_id} not found")

    existing = db.query(ScheduleManagement).filter(
        ScheduleManagement.personnel_id == schedule_data.personnel_id,
        ScheduleManagement.schedule_date == schedule_data.schedule_date,
        ScheduleManagement.status.in_(["scheduled", "completed"])
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Personnel already has a schedule for this date/time")

    schedule = ScheduleManagement(**schedule_data.model_dump(), assigned_by=getattr(current_user, 'id', None))
    db.add(schedule)
    db.flush()

    # Mirror to att_schedule
    emp_code = getattr(personnel, 'emp_code', None) or getattr(personnel, 'badge_id', None)
    if emp_code:
        sched_date = schedule_data.schedule_date.date() if hasattr(schedule_data.schedule_date, 'date') else schedule_data.schedule_date
        db.execute(text("""
            INSERT INTO att_schedule (emp_code, shift_id, start_date, end_date)
            VALUES (:emp_code, :shift_id, :start_date, :end_date)
            ON CONFLICT DO NOTHING
        """), {"emp_code": emp_code, "shift_id": schedule_data.shift_id,
               "start_date": sched_date, "end_date": sched_date})

    db.commit()
    db.refresh(schedule)
    return schedule


@router.post("/schedules/bulk-assign")
async def bulk_assign_shift(
    shift_id: int = Query(...),
    personnel_ids: List[int] = Query(...),
    schedule_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk-assign a shift to multiple employees for a given date."""
    shift_row = db.execute(text(_SELECT_SHIFT + " WHERE s.id = :id"), {"id": shift_id}).fetchone()
    if not shift_row:
        raise HTTPException(status_code=404, detail=f"Shift {shift_id} not found")
    shift = _row_to_shift(shift_row)
    start_t = datetime.strptime(shift["start_time"], "%H:%M:%S").time() if shift.get("start_time") else time(8, 0)

    created, skipped, errors = 0, 0, []
    for pid in personnel_ids:
        personnel = db.query(Personnel).filter(Personnel.id == pid).first()
        if not personnel:
            errors.append(f"Personnel {pid} not found")
            continue
        existing = db.query(ScheduleManagement).filter(
            ScheduleManagement.personnel_id == pid,
            func.date(ScheduleManagement.schedule_date) == schedule_date,
            ScheduleManagement.status.in_(["scheduled", "completed"])
        ).first()
        if existing:
            skipped += 1
            continue
        db.add(ScheduleManagement(
            personnel_id=pid, shift_id=shift_id,
            schedule_date=datetime.combine(schedule_date, start_t),
            status="scheduled", assigned_by=getattr(current_user, 'id', None),
        ))
        emp_code = getattr(personnel, 'emp_code', None) or getattr(personnel, 'badge_id', None)
        if emp_code:
            db.execute(text("""
                INSERT INTO att_schedule (emp_code, shift_id, start_date, end_date)
                VALUES (:emp_code, :shift_id, :start_date, :end_date)
                ON CONFLICT DO NOTHING
            """), {"emp_code": emp_code, "shift_id": shift_id,
                   "start_date": schedule_date, "end_date": schedule_date})
        created += 1

    db.commit()
    return {"shift_name": shift["shift_name"], "date": schedule_date.isoformat(),
            "created": created, "skipped_conflicts": skipped,
            "errors": errors, "total_requested": len(personnel_ids)}


@router.get("/schedules", response_model=List[ScheduleManagementResponse])
async def get_schedules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    personnel_id: Optional[int] = Query(None),
    shift_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all schedules with filtering."""
    query = db.query(ScheduleManagement)
    if personnel_id:
        query = query.filter(ScheduleManagement.personnel_id == personnel_id)
    if shift_id:
        query = query.filter(ScheduleManagement.shift_id == shift_id)
    if status:
        query = query.filter(ScheduleManagement.status == status)
    if start_date:
        query = query.filter(ScheduleManagement.schedule_date >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(ScheduleManagement.schedule_date <= datetime.combine(end_date, time.max))
    return query.order_by(ScheduleManagement.schedule_date).offset(skip).limit(limit).all()


@router.get("/schedules/calendar")
async def get_schedule_calendar(
    start_date: date = Query(...),
    end_date: date = Query(...),
    personnel_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get schedule calendar view."""
    q = db.query(ScheduleManagement)
    if personnel_id:
        q = q.filter(ScheduleManagement.personnel_id == personnel_id)
    q = q.filter(
        ScheduleManagement.schedule_date >= datetime.combine(start_date, time.min),
        ScheduleManagement.schedule_date <= datetime.combine(end_date, time.max)
    )
    calendar_data: dict = {}
    for sched in q.all():
        shift_row = db.execute(text(_SELECT_SHIFT + " WHERE s.id = :id"), {"id": sched.shift_id}).fetchone()
        shift = _row_to_shift(shift_row) if shift_row else {}
        dk = sched.schedule_date.date().isoformat()
        calendar_data.setdefault(dk, []).append({
            "id": sched.id,
            "personnel_id": sched.personnel_id,
            "shift_id": sched.shift_id,
            "shift_name": shift.get("shift_name", ""),
            "shift_code": shift.get("shift_code", ""),
            "start_time": shift.get("start_time"),
            "end_time":   shift.get("end_time"),
            "status": sched.status,
        })
    return calendar_data


@router.get("/schedules/personnel-status")
async def get_personnel_schedule_status(
    schedule_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return which personnel already have a schedule on a given date."""
    rows = db.query(
        ScheduleManagement.personnel_id,
        ScheduleManagement.shift_id,
        ScheduleManagement.id.label("schedule_id"),
    ).filter(
        func.date(ScheduleManagement.schedule_date) == schedule_date,
        ScheduleManagement.status.in_(["scheduled", "completed"]),
    ).all()
    return {
        "date": schedule_date.isoformat(),
        "scheduled": [{"personnel_id": r.personnel_id, "shift_id": r.shift_id, "schedule_id": r.schedule_id} for r in rows],
    }


@router.get("/schedules/{schedule_id}", response_model=ScheduleManagementResponse)
async def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sched = db.query(ScheduleManagement).filter(ScheduleManagement.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return sched


@router.put("/schedules/{schedule_id}", response_model=ScheduleManagementResponse)
async def update_schedule(
    schedule_id: int,
    schedule_data: ScheduleManagementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sched = db.query(ScheduleManagement).filter(ScheduleManagement.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    if schedule_data.shift_id and schedule_data.shift_id != sched.shift_id:
        if not db.execute(text("SELECT id FROM att_shift WHERE id = :id"), {"id": schedule_data.shift_id}).fetchone():
            raise HTTPException(status_code=404, detail=f"Shift {schedule_data.shift_id} not found")
    for field, value in schedule_data.model_dump(exclude_unset=True).items():
        setattr(sched, field, value)
    db.commit()
    db.refresh(sched)
    return sched


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sched = db.query(ScheduleManagement).filter(ScheduleManagement.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    db.delete(sched)
    db.commit()
    return None


@router.post("/schedules/{schedule_id}/swap")
async def request_schedule_swap(schedule_id: int, current_user: User = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Schedule swap not yet implemented")


@router.put("/schedules/{schedule_id}/swap/approve")
async def approve_schedule_swap(schedule_id: int, current_user: User = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Schedule swap not yet implemented")


@router.put("/schedules/{schedule_id}/swap/reject")
async def reject_schedule_swap(schedule_id: int, current_user: User = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Schedule swap not yet implemented")


# ==================== Attendance Calculation (Shift-based) ====================

@router.get("/attendance/daily-summary")
async def get_daily_attendance_summary(
    report_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate daily attendance for all scheduled personnel using att_shift rules."""
    schedules = (
        db.query(ScheduleManagement)
        .filter(func.date(ScheduleManagement.schedule_date) == report_date)
        .all()
    )

    records = []
    for sched in schedules:
        personnel = sched.personnel
        if not personnel:
            continue
        emp_code = getattr(personnel, 'emp_code', None) or getattr(personnel, 'badge_id', None)
        if not emp_code:
            continue

        shift_row = db.execute(text(_SELECT_SHIFT + " WHERE s.id = :id"), {"id": sched.shift_id}).fetchone()
        if not shift_row:
            continue
        shift = _row_to_shift(shift_row)

        if not shift.get("start_time") or not shift.get("end_time"):
            continue

        start_t = datetime.strptime(shift["start_time"], "%H:%M:%S").time()
        end_t   = datetime.strptime(shift["end_time"],   "%H:%M:%S").time()

        punches = db.execute(text("""
            SELECT punch_time, punch_state FROM iclock_transaction
            WHERE emp_code = :emp_code AND DATE(punch_time AT TIME ZONE 'UTC') = :punch_date
            ORDER BY punch_time
        """), {"emp_code": emp_code, "punch_date": report_date}).fetchall()

        if not punches:
            punches = db.execute(text("""
                SELECT check_time AS punch_time, check_type AS punch_state FROM checkinout
                WHERE emp_code = :emp_code AND DATE(check_time AT TIME ZONE 'UTC') = :punch_date
                ORDER BY check_time
            """), {"emp_code": emp_code, "punch_date": report_date}).fetchall()

        first_in = next((p.punch_time for p in punches if p.punch_state == 0), None)
        last_out = next((p.punch_time for p in reversed(punches) if p.punch_state == 1), None)

        shift_start_dt = datetime.combine(report_date, start_t)
        shift_end_dt   = datetime.combine(report_date, end_t)
        if shift["is_night_shift"] and end_t < start_t:
            shift_end_dt = datetime.combine(report_date + timedelta(days=1), end_t)

        def naive(dt):
            return dt.replace(tzinfo=None) if dt and getattr(dt, 'tzinfo', None) else dt

        first_in_n, last_out_n = naive(first_in), naive(last_out)
        late_min = early_dep_min = ot_min = worked_min = 0.0
        arrival_status = "absent"
        checkout_status = "normal"

        if first_in_n:
            delta = (first_in_n - shift_start_dt).total_seconds() / 60
            late_min = max(0.0, delta)
            arrival_status = (
                "on_time"   if late_min <= shift["grace_period_minutes"] else
                "late"      if late_min <= shift["max_late_minutes"] else
                "very_late"
            )
            break_dur = shift.get("break_duration") or 0
            if last_out_n is None:
                checkout_status = "missing"
                worked_min = max(0.0, (shift_end_dt - first_in_n).total_seconds() / 60 - break_dur)
            else:
                early_sec = (shift_end_dt - last_out_n).total_seconds()
                if early_sec > 0:
                    early_dep_min = early_sec / 60
                    if early_dep_min > shift["max_early_departure_minutes"]:
                        checkout_status = "early_out"
                else:
                    ot_sec = (last_out_n - shift_end_dt).total_seconds()
                    if ot_sec > shift["overtime_threshold_minutes"] * 60:
                        ot_min = ot_sec / 60
                        checkout_status = "overtime"
                worked_min = max(0.0, (last_out_n - first_in_n).total_seconds() / 60 - break_dur)

        records.append({
            "schedule_id":          sched.id,
            "personnel_id":         sched.personnel_id,
            "personnel_name":       getattr(personnel, 'full_name', None) or emp_code,
            "emp_code":             emp_code,
            "shift_id":             sched.shift_id,
            "shift_name":           shift["shift_name"],
            "shift_start":          shift["start_time"][:5] if shift.get("start_time") else None,
            "shift_end":            shift["end_time"][:5]   if shift.get("end_time")   else None,
            "expected_hours":       shift.get("working_hours", 8),
            "first_checkin":        first_in.isoformat() if first_in else None,
            "last_checkout":        last_out.isoformat() if last_out else None,
            "arrival_status":       arrival_status,
            "checkout_status":      checkout_status,
            "late_minutes":         round(late_min, 1),
            "early_departure_minutes": round(early_dep_min, 1),
            "overtime_minutes":     round(ot_min, 1),
            "total_worked_minutes": round(worked_min, 1),
            "total_worked_hours":   round(worked_min / 60, 2),
            "needs_review":         checkout_status == "missing",
        })

    present = sum(1 for r in records if r["arrival_status"] != "absent")
    return {
        "date": report_date.isoformat(),
        "total_scheduled": len(records),
        "present": present,
        "absent":  len(records) - present,
        "on_time": sum(1 for r in records if r["arrival_status"] == "on_time"),
        "late":    sum(1 for r in records if r["arrival_status"] in ("late", "very_late")),
        "missing_checkout": sum(1 for r in records if r["checkout_status"] == "missing"),
        "overtime":         sum(1 for r in records if r["checkout_status"] == "overtime"),
        "records": records,
    }
