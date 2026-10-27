"""
BioTime 9.5 Compatible Attendance API Endpoints
Complete REST API for attendance management and calculation
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta, time
from pydantic import BaseModel
import asyncio
import json

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..services.attendance_calculation_service import attendance_calculation_service
from ..services.attendance_validation_service import attendance_validation_service
from ..services.attendance_cache_service import attendance_cache_service
from ..services.attendance_anomaly_service import attendance_anomaly_service
from ..services.attendance_predictive_service import attendance_predictive_service
from ..models.personnel import Personnel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])

# Pydantic models for request/response validation
class TimetableCreate(BaseModel):
    alias: str
    checkin_time: str
    checkout_time: str
    late_minutes: int = 0
    early_minutes: int = 0
    work_day: float = 1.0
    color: str = "#1890ff"
    break_time_start: Optional[str] = None
    break_time_end: Optional[str] = None
    must_checkin: bool = True
    must_checkout: bool = True
    area_id: Optional[int] = None
    is_active: bool = True

class ShiftCreate(BaseModel):
    alias: str
    shift_code: Optional[str] = None
    timetable_id: Optional[int] = None
    work_days: str = "12345"
    cycle_unit: int = 1
    cycle_count: int = 1
    roster_type: int = 0
    # Rich fields (absorbed from shift_management)
    shift_type: Optional[str] = "CUSTOM"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    break_duration: int = 0
    working_hours: int = 8
    is_night_shift: bool = False
    is_weekend_shift: bool = False
    is_flexible: bool = False
    rotation_pattern: Optional[Any] = None
    rotation_cycle_days: Optional[int] = None
    grace_period_minutes: int = 15
    max_late_minutes: int = 60
    max_early_departure_minutes: int = 30
    overtime_threshold_minutes: int = 30
    description: Optional[str] = None
    is_active: bool = True

class ShiftTimetableCreate(BaseModel):
    shift_id: int
    day_of_week: int
    timetable_id: int

class ScheduleCreate(BaseModel):
    emp_code: str
    shift_id: int
    start_date: date
    end_date: date
    status: Optional[str] = "scheduled"
    notes: Optional[str] = None

class HolidayCreate(BaseModel):
    holiday_name: str
    start_date: date
    end_date: date
    holiday_type: int = 0

class LeaveTypeCreate(BaseModel):
    leave_name: str
    unit: int = 0
    accrual_rule: Optional[str] = None
    affects_mustering: bool = True
    max_days_per_year: Optional[int] = None
    requires_approval: bool = True

class LeaveCreate(BaseModel):
    emp_id: int
    leave_type_id: int
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None

class OvertimeRuleCreate(BaseModel):
    rule_name: str
    ot_type: int
    min_minutes: int
    rate: float = 1.0
    area_id: Optional[int] = None

class OvertimeCreate(BaseModel):
    personnel_id: int
    overtime_type: Optional[str] = "daily"
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    hours_worked: Optional[float] = None
    overtime_hours: Optional[float] = None
    compensation_type: Optional[str] = None
    reason: Optional[str] = None

class ManualLogCreate(BaseModel):
    emp_id: int
    punch_time: datetime
    punch_state: int
    reason: Optional[str] = None
    attachment: Optional[str] = None

class CalculationRequest(BaseModel):
    emp_ids: Optional[List[int]] = None
    start_date: str
    end_date: str

# ============ TIMETABLE ENDPOINTS ============

@router.get("/timetables")
async def get_timetables(db: Session = Depends(get_db)):
    """Get all timetables"""
    try:
        timetables = db.execute(text("""
            SELECT
                t.id,
                COALESCE(t.alias, t.name)  AS alias,
                t.start_time::text          AS checkin_time,
                t.end_time::text            AS checkout_time,
                t.late_grace_minutes        AS late_minutes,
                t.early_exit_minutes        AS early_minutes,
                t.work_day,
                t.color,
                t.break_time_start::text    AS break_time_start,
                t.break_time_end::text      AS break_time_end,
                t.must_checkin,
                t.must_checkout,
                t.area_id,
                t.is_active,
                t.created_at,
                t.updated_at,
                a.area_name                 AS area_name,
                COUNT(DISTINCT st.shift_id) AS shift_count
            FROM att_timetable t
            LEFT JOIN personnel_area a       ON t.area_id = a.id
            LEFT JOIN att_shift_timetable st ON t.id = st.timetable_id
            GROUP BY t.id, a.area_name
            ORDER BY t.created_at DESC
        """)).fetchall()

        return {"success": True, "data": [dict(r._mapping) for r in timetables]}
    except Exception as e:
        logger.error(f"Error fetching timetables: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch timetables: {str(e)}")

@router.post("/timetables")
async def create_timetable(
    timetable: TimetableCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new timetable"""
    try:
        is_valid, errors = await attendance_validation_service.validate_timetable(
            timetable.dict(), db
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail={"errors": errors})

        d = timetable.dict()
        result = db.execute(text("""
            INSERT INTO att_timetable (
                name, alias, start_time, end_time,
                late_grace_minutes, early_exit_minutes,
                work_day, color, break_time_start, break_time_end,
                must_checkin, must_checkout, area_id, is_active, created_by
            ) VALUES (
                :alias, :alias, :checkin_time, :checkout_time,
                :late_minutes, :early_minutes,
                :work_day, :color, :break_time_start, :break_time_end,
                :must_checkin, :must_checkout, :area_id, :is_active, :created_by
            ) RETURNING id
        """), {**d, "created_by": getattr(current_user, 'id', None)}).fetchone()

        db.commit()
        return {"success": True, "data": {"id": result.id, **d}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating timetable: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create timetable: {str(e)}")

@router.put("/timetables/{timetable_id}")
async def update_timetable(
    timetable_id: int,
    timetable: TimetableCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update timetable"""
    try:
        is_valid, errors = await attendance_validation_service.validate_timetable(
            timetable.dict(), db
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail={"errors": errors})

        d = timetable.dict()
        db.execute(text("""
            UPDATE att_timetable
            SET name = :alias, alias = :alias,
                start_time = :checkin_time, end_time = :checkout_time,
                late_grace_minutes = :late_minutes, early_exit_minutes = :early_minutes,
                work_day = :work_day, color = :color,
                break_time_start = :break_time_start, break_time_end = :break_time_end,
                must_checkin = :must_checkin, must_checkout = :must_checkout,
                area_id = :area_id, is_active = :is_active,
                updated_at = CURRENT_TIMESTAMP, updated_by = :updated_by
            WHERE id = :timetable_id
        """), {**d, "updated_by": getattr(current_user, 'id', None), "timetable_id": timetable_id})

        db.commit()
        return {"success": True, "message": "Timetable updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating timetable: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update timetable: {str(e)}")

class TimetableStatusUpdate(BaseModel):
    is_active: bool

@router.patch("/timetables/{timetable_id}/status")
async def update_timetable_status(
    timetable_id: int,
    payload: TimetableStatusUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Toggle timetable active / inactive"""
    try:
        db.execute(text("""
            UPDATE att_timetable
            SET is_active = :is_active, updated_at = CURRENT_TIMESTAMP, updated_by = :updated_by
            WHERE id = :timetable_id
        """), {"is_active": payload.is_active, "updated_by": getattr(current_user, 'id', None), "timetable_id": timetable_id})
        db.commit()
        return {"success": True, "message": "Status updated"}
    except Exception as e:
        logger.error(f"Error updating timetable status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

@router.delete("/timetables/{timetable_id}")
async def delete_timetable(
    timetable_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete timetable"""
    try:
        db.execute(text("DELETE FROM att_timetable WHERE id = :timetable_id"), {"timetable_id": timetable_id})
        db.commit()
        return {"success": True, "message": "Timetable deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting timetable: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete timetable: {str(e)}")

# ============ SHIFT ENDPOINTS ============

@router.get("/shifts")
async def get_shifts(db: Session = Depends(get_db)):
    """Get all shifts with timetable info, rich fields, and schedule count"""
    try:
        rows = db.execute(text("""
            SELECT
                s.id,
                COALESCE(s.alias, s.name)                       AS alias,
                COALESCE(s.alias, s.name)                       AS shift_name,
                s.name,
                s.shift_code,
                COALESCE(s.shift_type, 'CUSTOM')                AS shift_type,
                s.timetable_id,
                COALESCE(s.work_days, s.days_of_week, '12345')  AS work_days,
                COALESCE(s.cycle_unit,  1)                       AS cycle_unit,
                COALESCE(s.cycle_count, 1)                       AS cycle_count,
                COALESCE(s.roster_type, 0)                       AS roster_type,
                s.start_time::text                               AS start_time,
                s.end_time::text                                 AS end_time,
                COALESCE(s.break_duration, 0)                    AS break_duration,
                COALESCE(s.working_hours, 8)                     AS working_hours,
                COALESCE(s.is_night_shift,   false)              AS is_night_shift,
                COALESCE(s.is_weekend_shift, false)              AS is_weekend_shift,
                COALESCE(s.is_flexible,      false)              AS is_flexible,
                s.rotation_pattern,
                s.rotation_cycle_days,
                COALESCE(s.grace_period_minutes,       15)       AS grace_period_minutes,
                COALESCE(s.max_late_minutes,           60)       AS max_late_minutes,
                COALESCE(s.max_early_departure_minutes,30)       AS max_early_departure_minutes,
                COALESCE(s.overtime_threshold_minutes, 30)       AS overtime_threshold_minutes,
                s.description,
                COALESCE(s.is_active, true)                      AS is_active,
                t.name                                           AS timetable_name,
                t.start_time::text                               AS timetable_start,
                t.end_time::text                                 AS timetable_end,
                t.late_grace_minutes,
                t.early_exit_minutes,
                (SELECT COUNT(*) FROM att_schedule sc WHERE sc.shift_id = s.id) AS schedule_count
            FROM att_shift s
            LEFT JOIN att_timetable t ON s.timetable_id = t.id
            ORDER BY s.id DESC
        """)).fetchall()
        return {"success": True, "data": [dict(r._mapping) for r in rows]}
    except Exception as e:
        logger.error(f"Error fetching shifts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch shifts: {str(e)}")

@router.post("/shifts")
async def create_shift(
    shift: ShiftCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new shift pattern"""
    try:
        created_by = getattr(current_user, 'id', None)
        d = shift.dict()
        result = db.execute(text("""
            INSERT INTO att_shift (
                name, alias, shift_code, timetable_id,
                work_days, days_of_week, cycle_unit, cycle_count, roster_type,
                shift_type, start_time, end_time, break_duration, working_hours,
                is_night_shift, is_weekend_shift, is_flexible,
                rotation_pattern, rotation_cycle_days,
                grace_period_minutes, max_late_minutes,
                max_early_departure_minutes, overtime_threshold_minutes,
                description, is_active, created_by
            ) VALUES (
                :alias, :alias, :shift_code, :timetable_id,
                :work_days, :work_days, :cycle_unit, :cycle_count, :roster_type,
                :shift_type, :start_time, :end_time, :break_duration, :working_hours,
                :is_night_shift, :is_weekend_shift, :is_flexible,
                :rotation_pattern, :rotation_cycle_days,
                :grace_period_minutes, :max_late_minutes,
                :max_early_departure_minutes, :overtime_threshold_minutes,
                :description, :is_active, :created_by
            )
            RETURNING *
        """), {**d, "created_by": created_by}).fetchone()
        db.commit()
        return {"success": True, "data": dict(result._mapping)}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating shift: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create shift: {str(e)}")

@router.put("/shifts/{shift_id}")
async def update_shift(
    shift_id: int,
    shift: ShiftCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update existing shift pattern"""
    try:
        existing = db.execute(
            text("SELECT id FROM att_shift WHERE id = :id"), {"id": shift_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Shift not found")

        db.execute(text("""
            UPDATE att_shift
               SET name                       = :alias,
                   alias                      = :alias,
                   shift_code                 = :shift_code,
                   timetable_id               = :timetable_id,
                   work_days                  = :work_days,
                   days_of_week               = :work_days,
                   cycle_unit                 = :cycle_unit,
                   cycle_count                = :cycle_count,
                   roster_type                = :roster_type,
                   shift_type                 = :shift_type,
                   start_time                 = :start_time,
                   end_time                   = :end_time,
                   break_duration             = :break_duration,
                   working_hours              = :working_hours,
                   is_night_shift             = :is_night_shift,
                   is_weekend_shift           = :is_weekend_shift,
                   is_flexible                = :is_flexible,
                   rotation_pattern           = :rotation_pattern,
                   rotation_cycle_days        = :rotation_cycle_days,
                   grace_period_minutes       = :grace_period_minutes,
                   max_late_minutes           = :max_late_minutes,
                   max_early_departure_minutes= :max_early_departure_minutes,
                   overtime_threshold_minutes = :overtime_threshold_minutes,
                   description                = :description,
                   is_active                  = :is_active
             WHERE id = :shift_id
        """), {**shift.dict(), "shift_id": shift_id})
        db.commit()
        return {"success": True, "message": "Shift updated"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating shift: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update shift: {str(e)}")

@router.delete("/shifts/{shift_id}")
async def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete shift pattern and clean up dependent records"""
    try:
        existing = db.execute(
            text("SELECT id FROM att_shift WHERE id = :id"), {"id": shift_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Shift not found")

        # Remove schedules assigned to this shift
        db.execute(text("DELETE FROM att_schedule WHERE shift_id = :id"), {"id": shift_id})
        # Nullify historical references (preserve the records themselves)
        db.execute(text("UPDATE att_report SET shift_id = NULL WHERE shift_id = :id"), {"id": shift_id})
        db.execute(text("UPDATE mustering_expected SET shift_id = NULL WHERE shift_id = :id"), {"id": shift_id})
        # att_shift_timetable has CASCADE so no manual cleanup needed
        db.execute(text("DELETE FROM att_shift WHERE id = :id"), {"id": shift_id})
        db.commit()
        return {"success": True, "message": "Shift deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting shift: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete shift: {str(e)}")

@router.post("/shifts/{shift_id}/timetables")
async def assign_timetable_to_shift(
    shift_id: int,
    assignment: ShiftTimetableCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Assign timetable to shift day"""
    try:
        db.execute(text("""
            INSERT INTO att_shift_timetable (shift_id, day_of_week, timetable_id)
            VALUES (:shift_id, :day_of_week, :timetable_id)
            ON CONFLICT (shift_id, day_of_week) 
            DO UPDATE SET timetable_id = :timetable_id
        """), {
            **assignment.dict(),
            "shift_id": shift_id
        })
        
        db.commit()
        return {"success": True, "message": "Timetable assigned to shift successfully"}
    except Exception as e:
        logger.error(f"Error assigning timetable to shift: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to assign timetable: {str(e)}")

# ============ SCHEDULE ENDPOINTS ============

class BatchRangeAssign(BaseModel):
    emp_codes: List[str] = []
    dept_id: Optional[int] = None
    shift_id: int
    start_date: date
    end_date: date
    overwrite: bool = False


@router.get("/schedules/roster")
async def get_schedule_roster(
    month: str = Query(..., description="YYYY-MM"),
    dept_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """BioTime-style roster: all employees × all days for a given month."""
    try:
        from datetime import date as _date, timedelta
        import calendar
        year, mon = int(month.split("-")[0]), int(month.split("-")[1])
        _, days_in_month = calendar.monthrange(year, mon)
        month_start = _date(year, mon, 1)
        month_end   = _date(year, mon, days_in_month)

        # Pull employees from personnel (authoritative) UNION personnel_employee (ADMS orphans).
        # personnel is the single source of truth for UI-created employees.
        q = """
            WITH all_employees AS (
                -- UI-created employees (authoritative)
                SELECT
                    p.emp_code,
                    TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')) AS emp_name,
                    p.department_id AS dept_id
                FROM personnel p
                WHERE p.is_active = true OR p.is_active IS NULL

                UNION

                -- ADMS-only employees not in personnel
                SELECT
                    pe.emp_code,
                    TRIM(COALESCE(pe.first_name,'') || ' ' || COALESCE(pe.last_name,'')) AS emp_name,
                    pe.dept_id
                FROM personnel_employee pe
                WHERE (pe.status IS NULL OR pe.status = 0)
                  AND pe.emp_code NOT IN (SELECT emp_code FROM personnel)
            )
            SELECT
                e.emp_code,
                e.emp_name,
                COALESCE(d.name, 'No Department') AS dept_name,
                e.dept_id,
                s.id        AS schedule_id,
                s.shift_id,
                s.start_date,
                s.end_date,
                COALESCE(sh.alias, sh.name)       AS shift_name,
                COALESCE(sh.shift_code, '')        AS shift_code,
                COALESCE(sh.shift_type, 'CUSTOM') AS shift_type
            FROM all_employees e
            LEFT JOIN departments d ON e.dept_id = d.id
            LEFT JOIN att_schedule s
                ON  e.emp_code = s.emp_code
                AND s.start_date <= :month_end
                AND (s.end_date >= :month_start OR s.end_date IS NULL)
            LEFT JOIN att_shift sh ON s.shift_id = sh.id
            WHERE 1=1
        """
        params: dict = {"month_start": month_start, "month_end": month_end}
        if dept_id:
            q += " AND e.dept_id = :dept_id"
            params["dept_id"] = dept_id
        q += " ORDER BY dept_name, e.emp_name, s.start_date"

        rows = db.execute(text(q), params).fetchall()

        employees: dict = {}
        for r in rows:
            ec = r.emp_code
            if ec not in employees:
                employees[ec] = {
                    "emp_code":  ec,
                    "emp_name":  r.emp_name or ec,
                    "dept_name": r.dept_name,
                    "dept_id":   r.dept_id,
                    "schedule":  {},
                }
            if r.schedule_id:
                s_start = max(r.start_date, month_start)
                s_end   = min(r.end_date, month_end) if r.end_date else month_end
                cur = s_start
                while cur <= s_end:
                    employees[ec]["schedule"][str(cur.day)] = {
                        "schedule_id": r.schedule_id,
                        "shift_id":    r.shift_id,
                        "shift_name":  r.shift_name,
                        "shift_code":  r.shift_code,
                        "shift_type":  r.shift_type,
                    }
                    cur += timedelta(days=1)

        return {
            "success":       True,
            "year":          year,
            "month":         mon,
            "days_in_month": days_in_month,
            "employees":     list(employees.values()),
        }
    except Exception as e:
        logger.error(f"Error building roster: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to build roster: {str(e)}")


@router.post("/schedules/batch-range")
async def batch_range_assign(
    payload: BatchRangeAssign,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Assign one shift to many employees over a date range. Supports overwrite and dept_id."""
    try:
        created_by = getattr(current_user, 'id', None)
        created, skipped, overwritten = 0, 0, 0

        # Resolve emp_codes: if dept_id given, pull all active employees in that department
        emp_codes = list(payload.emp_codes)
        if payload.dept_id:
            dept_rows = db.execute(text("""
                SELECT emp_code FROM personnel
                WHERE department_id = :dept_id AND (is_active = true OR is_active IS NULL)
                UNION
                SELECT emp_code FROM personnel_employee
                WHERE dept_id = :dept_id AND (status IS NULL OR status = 0)
                  AND emp_code NOT IN (SELECT emp_code FROM personnel)
            """), {"dept_id": payload.dept_id}).fetchall()
            emp_codes = [r[0] for r in dept_rows]
            if not emp_codes:
                return {"success": True, "created": 0, "skipped": 0, "overwritten": 0,
                        "total": 0, "message": "No active employees found in this department"}

        for emp_code in emp_codes:
            if payload.overwrite:
                # Remove overlapping schedules first
                db.execute(text("""
                    DELETE FROM att_schedule
                    WHERE emp_code = :emp_code
                      AND start_date <= :end_date
                      AND (end_date >= :start_date OR end_date IS NULL)
                """), {"emp_code": emp_code, "start_date": payload.start_date, "end_date": payload.end_date})
                overwritten += 1
            else:
                # Check for existing overlap
                overlap = db.execute(text("""
                    SELECT id FROM att_schedule
                    WHERE emp_code = :emp_code
                      AND start_date <= :end_date
                      AND (end_date >= :start_date OR end_date IS NULL)
                    LIMIT 1
                """), {"emp_code": emp_code, "start_date": payload.start_date, "end_date": payload.end_date}).fetchone()
                if overlap:
                    skipped += 1
                    continue
            db.execute(text("""
                INSERT INTO att_schedule (emp_code, shift_id, start_date, end_date)
                VALUES (:emp_code, :shift_id, :start_date, :end_date)
            """), {"emp_code": emp_code, "shift_id": payload.shift_id,
                   "start_date": payload.start_date, "end_date": payload.end_date})
            created += 1
        db.commit()
        return {"success": True, "created": created, "skipped": skipped,
                "overwritten": overwritten, "total": len(emp_codes)}
    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch range assign: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to batch assign: {str(e)}")


@router.delete("/schedules/range")
async def delete_schedule_range(
    emp_code: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Clear all schedules for an employee within a date range."""
    try:
        result = db.execute(text("""
            DELETE FROM att_schedule
            WHERE emp_code = :emp_code
              AND start_date <= :end_date
              AND (end_date >= :start_date OR end_date IS NULL)
        """), {"emp_code": emp_code, "start_date": start_date, "end_date": end_date})
        db.commit()
        return {"success": True, "deleted": result.rowcount}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear range: {str(e)}")


@router.get("/schedules/departments")
async def get_schedule_departments(db: Session = Depends(get_db)):
    """Get departments that have active employees."""
    try:
        rows = db.execute(text("""
            SELECT DISTINCT d.id, d.name
            FROM departments d
            WHERE d.id IN (
                SELECT DISTINCT department_id FROM personnel
                WHERE (is_active = true OR is_active IS NULL) AND department_id IS NOT NULL
                UNION
                SELECT DISTINCT dept_id FROM personnel_employee
                WHERE (status IS NULL OR status = 0) AND dept_id IS NOT NULL
            )
            ORDER BY d.name
        """)).fetchall()
        return {"success": True, "data": [dict(r._mapping) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules")
async def get_schedules(
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get employee schedules"""
    try:
        query = """
            SELECT s.id, s.emp_code, s.shift_id, s.start_date, s.end_date, s.created_at,
                   s.start_date AS schedule_date,
                   COALESCE(s.status, 'scheduled') AS status,
                   s.notes,
                   COALESCE(p.id, pe.id) AS personnel_id,
                   TRIM(COALESCE(
                       NULLIF(TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')), ''),
                       NULLIF(TRIM(COALESCE(pe.first_name,'') || ' ' || COALESCE(pe.last_name,'')), ''),
                       s.emp_code
                   )) AS emp_name,
                   COALESCE(sh.alias, sh.name) AS shift_name,
                   COALESCE(sh.work_days, sh.days_of_week) AS days_of_week
            FROM att_schedule s
            LEFT JOIN personnel p ON s.emp_code = p.emp_code
            LEFT JOIN personnel_employee pe ON s.emp_code = pe.emp_code AND p.id IS NULL
            LEFT JOIN att_shift sh ON s.shift_id = sh.id
            WHERE 1=1
        """
        params = {}

        if search:
            query += """
                AND (
                    p.first_name ILIKE :search OR p.last_name ILIKE :search
                    OR pe.first_name ILIKE :search OR pe.last_name ILIKE :search
                    OR s.emp_code ILIKE :search
                )
            """
            params['search'] = f"%{search}%"

        if start_date:
            query += " AND s.end_date >= :start_date"
            params['start_date'] = start_date

        if end_date:
            query += " AND s.start_date <= :end_date"
            params['end_date'] = end_date

        query += " ORDER BY s.id DESC"
        rows = db.execute(text(query), params).fetchall()
        return {"success": True, "data": [dict(r._mapping) for r in rows]}
    except Exception as e:
        logger.error(f"Error fetching schedules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch schedules: {str(e)}")

@router.post("/schedules")
async def create_schedule(
    schedule: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new schedule"""
    try:
        result = db.execute(text("""
            INSERT INTO att_schedule (emp_code, shift_id, start_date, end_date, status, notes)
            VALUES (:emp_code, :shift_id, :start_date, :end_date, :status, :notes)
            RETURNING *
        """), schedule.dict()).fetchone()
        db.commit()
        return {"success": True, "data": dict(result._mapping)}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a schedule assignment"""
    try:
        existing = db.execute(
            text("SELECT id FROM att_schedule WHERE id = :id"), {"id": schedule_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Schedule not found")
        db.execute(text("DELETE FROM att_schedule WHERE id = :id"), {"id": schedule_id})
        db.commit()
        return {"success": True, "message": "Schedule removed"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete schedule: {str(e)}")

@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    schedule: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update an existing schedule assignment"""
    try:
        existing = db.execute(
            text("SELECT id FROM att_schedule WHERE id = :id"), {"id": schedule_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Schedule not found")
        db.execute(text("""
            UPDATE att_schedule
               SET emp_code = :emp_code, shift_id = :shift_id,
                   start_date = :start_date, end_date = :end_date,
                   status = :status, notes = :notes
             WHERE id = :schedule_id
        """), {**schedule.dict(), "schedule_id": schedule_id})
        db.commit()
        return {"success": True, "message": "Schedule updated"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")


@router.get("/schedules/personnel-status")
async def get_personnel_schedule_status(
    schedule_date: str = Query(...),
    db: Session = Depends(get_db)
):
    """Return which personnel are already scheduled on a given date"""
    try:
        rows = db.execute(text("""
            SELECT s.emp_code, s.shift_id, e.id AS personnel_id
            FROM att_schedule s
            LEFT JOIN personnel_employee e ON s.emp_code = e.emp_code
            WHERE s.start_date <= :d AND (s.end_date >= :d OR s.end_date IS NULL)
        """), {"d": schedule_date}).fetchall()
        scheduled = [dict(r._mapping) for r in rows]
        return {"success": True, "scheduled": scheduled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get personnel status: {str(e)}")


@router.post("/schedules/bulk-assign")
async def bulk_assign_schedules(
    shift_id: int = Query(...),
    personnel_ids: List[int] = Query(...),
    schedule_date: str = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Bulk assign a shift to multiple employees for a single date"""
    try:
        # Look up emp_codes for the given personnel_ids
        placeholders = ",".join([f":pid_{i}" for i in range(len(personnel_ids))])
        params = {f"pid_{i}": pid for i, pid in enumerate(personnel_ids)}
        employees = db.execute(
            text(f"SELECT id, emp_code FROM personnel_employee WHERE id IN ({placeholders})"),
            params
        ).fetchall()
        emp_code_map = {e.id: e.emp_code for e in employees}

        created, skipped = [], []
        for pid in personnel_ids:
            emp_code = emp_code_map.get(pid)
            if not emp_code:
                skipped.append(pid)
                continue
            try:
                db.execute(text("""
                    INSERT INTO att_schedule (emp_code, shift_id, start_date, end_date, status)
                    VALUES (:emp_code, :shift_id, :d, :d, 'scheduled')
                    ON CONFLICT DO NOTHING
                """), {"emp_code": emp_code, "shift_id": shift_id, "d": schedule_date})
                created.append(pid)
            except Exception:
                skipped.append(pid)
        db.commit()
        return {
            "success": True,
            "message": f"Assigned {len(created)} schedules",
            "created": created,
            "skipped": skipped,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk assign failed: {str(e)}")


@router.post("/schedules/batch")
async def batch_assign_schedule(
    assignments: List[ScheduleCreate],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Batch assign schedules"""
    try:
        results = []
        for assignment in assignments:
            result = db.execute(text("""
                INSERT INTO att_schedule (emp_code, shift_id, start_date, end_date)
                VALUES (:emp_code, :shift_id, :start_date, :end_date)
                RETURNING *
            """), assignment.dict()).fetchone()
            results.append(dict(result._mapping))
        db.commit()
        return {"success": True, "data": results, "message": f"Created {len(results)} schedules"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch schedule creation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create batch schedules: {str(e)}")

# ============ HOLIDAY ENDPOINTS ============

@router.get("/holidays")
async def get_holidays(db: Session = Depends(get_db)):
    """Get all holidays"""
    try:
        holidays = db.execute(text("""
            SELECT * FROM att_holiday
            WHERE is_active = true
            ORDER BY start_date DESC
        """)).fetchall()

        return {"success": True, "data": [dict(r._mapping) for r in holidays]}
    except Exception as e:
        logger.error(f"Error fetching holidays: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch holidays: {str(e)}")

@router.post("/holidays")
async def create_holiday(
    holiday: HolidayCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new holiday"""
    try:
        result = db.execute(text("""
            INSERT INTO att_holiday (holiday_name, start_date, end_date, holiday_type, created_by)
            VALUES (:holiday_name, :start_date, :end_date, :holiday_type, :created_by)
            RETURNING *
        """), {
            **holiday.dict(),
            "created_by": current_user.id
        }).fetchone()
        
        db.commit()
        return {"success": True, "data": dict(result._mapping)}
    except Exception as e:
        logger.error(f"Error creating holiday: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create holiday: {str(e)}")

# ============ LEAVE ENDPOINTS ============

@router.get("/leave-types")
async def get_leave_types(db: Session = Depends(get_db)):
    """Get all leave types"""
    try:
        leave_types = db.execute(text("""
            SELECT * FROM att_leave_type 
            WHERE is_active = true
            ORDER BY leave_name
        """)).fetchall()
        
        return {"success": True, "data": [dict(r._mapping) for r in leave_types]}
    except Exception as e:
        logger.error(f"Error fetching leave types: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch leave types: {str(e)}")

@router.post("/leave-types")
async def create_leave_type(
    leave_type: LeaveTypeCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new leave type"""
    try:
        result = db.execute(text("""
            INSERT INTO att_leave_type (leave_name, unit, accrual_rule, affects_mustering, 
                                    max_days_per_year, requires_approval, created_by)
            VALUES (:leave_name, :unit, :accrual_rule, :affects_mustering,
                    :max_days_per_year, :requires_approval, :created_by)
            RETURNING *
        """), {
            **leave_type.dict(),
            "created_by": current_user.id
        }).fetchone()
        
        db.commit()
        return {"success": True, "data": dict(result._mapping)}
    except Exception as e:
        logger.error(f"Error creating leave type: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create leave type: {str(e)}")

@router.get("/leaves")
async def get_leaves(
    emp_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get leaves"""
    try:
        query = """
            SELECT l.*, lt.leave_name, lt.affects_mustering,
                   (e.first_name || ' ' || e.last_name) as employee_name, e.emp_code
            FROM att_leave l
            JOIN att_leave_type lt ON l.leave_type_id = lt.id
            JOIN personnel_employee e ON l.emp_id = e.id
            WHERE 1=1
        """
        params = {}
        
        if emp_id:
            query += " AND l.emp_id = :emp_id"
            params['emp_id'] = emp_id
        
        if status is not None:
            query += " AND l.approval_status = :status"
            params['status'] = status
        
        if start_date:
            query += " AND l.end_date >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND l.start_date <= :end_date"
            params['end_date'] = end_date
        
        leaves = db.execute(text(query + " ORDER BY l.created_at DESC"), params).fetchall()
        return {"success": True, "data": [dict(r._mapping) for r in leaves]}
    except Exception as e:
        logger.error(f"Error fetching leaves: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch leaves: {str(e)}")

@router.post("/leaves")
async def create_leave(
    leave: LeaveCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new leave request"""
    try:
        # Validate leave request
        is_valid, errors = await attendance_validation_service.validate_leave_request(
            leave.dict(), db
        )
        
        if not is_valid:
            raise HTTPException(status_code=400, detail={"errors": errors})
        
        # Check leave balance (if applicable)
        has_balance, balance_msg = await attendance_validation_service.check_leave_balance(
            leave.emp_id, leave.leave_type_id, leave.start_time, leave.end_time, db
        )
        
        if not has_balance:
            raise HTTPException(status_code=400, detail={"error": balance_msg})
        
        result = db.execute(text("""
            INSERT INTO att_leave (emp_id, leave_type_id, start_time, end_time, reason, apply_time, created_by)
            VALUES (:emp_id, :leave_type_id, :start_time, :end_time, :reason, CURRENT_TIMESTAMP, :created_by)
            RETURNING *
        """), {
            **leave.dict(),
            "created_by": current_user.id
        }).fetchone()
        
        db.commit()
        return {"success": True, "data": dict(result._mapping)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating leave: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create leave: {str(e)}")

@router.post("/leaves/{leave_id}/approve")
async def approve_leave(
    leave_id: int,
    approval_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Approve/reject leave"""
    try:
        status = approval_data.get('status', 1)  # Default to approved
        db.execute(text("""
            UPDATE att_leave 
            SET approval_status = :status, approver_id = :approver_id, approved_at = CURRENT_TIMESTAMP
            WHERE id = :leave_id
        """), {
            "status": status,
            "approver_id": current_user.id,
            "leave_id": leave_id
        })
        
        db.commit()
        action = "approved" if status == 1 else "rejected"
        return {"success": True, "message": f"Leave {action} successfully"}
    except Exception as e:
        logger.error(f"Error approving leave: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve leave: {str(e)}")

# ============ OVERTIME ENDPOINTS ============

@router.get("/overtime-rules")
async def get_overtime_rules(db: Session = Depends(get_db)):
    """Get all overtime rules"""
    try:
        rules = db.execute(text("""
            SELECT r.*, a.area_name
            FROM att_overtime_rule r
            LEFT JOIN personnel_area a ON r.area_id = a.id
            WHERE COALESCE(r.is_active, true) = true
            ORDER BY r.rule_name
        """)).fetchall()
        return {"success": True, "data": [dict(r._mapping) for r in rules]}
    except Exception as e:
        logger.error(f"Error fetching overtime rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch overtime rules: {str(e)}")

@router.post("/overtime-rules")
async def create_overtime_rule(
    rule: OvertimeRuleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new overtime rule"""
    try:
        result = db.execute(text("""
            INSERT INTO att_overtime_rule (rule_name, ot_type, min_minutes, rate, area_id, created_by)
            VALUES (:rule_name, :ot_type, :min_minutes, :rate, :area_id, :created_by)
            RETURNING *
        """), {
            **rule.dict(),
            "created_by": current_user.id
        }).fetchone()
        
        db.commit()
        return {"success": True, "data": dict(result._mapping)}
    except Exception as e:
        logger.error(f"Error creating overtime rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create overtime rule: {str(e)}")

_OT_STATUS_MAP = {0: 'pending', 1: 'approved', 2: 'rejected', 3: 'cancelled', 4: 'processed'}

def _ot_row(r):
    d = dict(r._mapping)
    d['status'] = _OT_STATUS_MAP.get(d.get('approval_status', 0), 'pending')
    d['date'] = d.get('ot_date')
    d['personnel_id'] = d.get('emp_id')
    d['personnel_name'] = d.get('employee_name')
    d['personnel_emp_code'] = d.get('emp_code_field')
    return d


@router.get("/overtime/summary")
async def get_overtime_summary(db: Session = Depends(get_db)):
    """Get overtime summary statistics"""
    try:
        row = db.execute(text("""
            SELECT
                COUNT(*)                                              AS total,
                COUNT(*) FILTER (WHERE approval_status = 0)          AS pending,
                COUNT(*) FILTER (WHERE approval_status = 1)          AS approved,
                COUNT(*) FILTER (WHERE approval_status = 2)          AS rejected,
                COUNT(*) FILTER (WHERE approval_status = 3)          AS cancelled,
                COALESCE(SUM(overtime_hours) FILTER (WHERE approval_status = 1), 0) AS total_overtime_hours
            FROM att_overtime
        """)).fetchone()
        return {"success": True, "data": dict(row._mapping)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get overtime summary: {str(e)}")


@router.get("/overtime")
async def get_overtime(
    emp_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    overtime_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get overtime records"""
    try:
        query = """
            SELECT o.*,
                   (e.first_name || ' ' || e.last_name)  AS employee_name,
                   e.emp_code                            AS emp_code_field,
                   o.emp_id                              AS personnel_id,
                   o.ot_date                             AS date,
                   CASE o.approval_status
                     WHEN 0 THEN 'pending'
                     WHEN 1 THEN 'approved'
                     WHEN 2 THEN 'rejected'
                     WHEN 3 THEN 'cancelled'
                     WHEN 4 THEN 'processed'
                     ELSE 'pending'
                   END AS status,
                   (e.first_name || ' ' || e.last_name)  AS personnel_name,
                   e.emp_code                            AS personnel_emp_code
            FROM att_overtime o
            JOIN personnel_employee e ON o.emp_id = e.id
            WHERE 1=1
        """
        params = {}

        if emp_id:
            query += " AND o.emp_id = :emp_id"
            params['emp_id'] = emp_id

        if status is not None:
            status_int = next((k for k, v in _OT_STATUS_MAP.items() if v == status), None)
            if status_int is not None:
                query += " AND o.approval_status = :status_int"
                params['status_int'] = status_int

        if overtime_type:
            query += " AND o.overtime_type = :overtime_type"
            params['overtime_type'] = overtime_type

        if start_date:
            query += " AND o.ot_date >= :start_date"
            params['start_date'] = start_date

        if end_date:
            query += " AND o.ot_date <= :end_date"
            params['end_date'] = end_date

        overtime = db.execute(text(query + " ORDER BY o.created_at DESC"), params).fetchall()
        return {"success": True, "data": [dict(r._mapping) for r in overtime]}
    except Exception as e:
        logger.error(f"Error fetching overtime: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch overtime: {str(e)}")

@router.post("/overtime")
async def create_overtime(
    overtime: OvertimeCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create overtime request"""
    try:
        d = overtime.dict()
        minutes = round((d.get('overtime_hours') or 0) * 60) or round((d.get('hours_worked') or 0) * 60) or 0
        result = db.execute(text("""
            INSERT INTO att_overtime (
                emp_id, ot_date, start_time, end_time, minutes, reason,
                overtime_type, hours_worked, overtime_hours, compensation_type,
                apply_time, created_by
            )
            VALUES (
                :personnel_id, :date, :start_time, :end_time, :minutes, :reason,
                :overtime_type, :hours_worked, :overtime_hours, :compensation_type,
                CURRENT_TIMESTAMP, :created_by
            )
            RETURNING *
        """), {**d, "minutes": minutes, "created_by": current_user.id}).fetchone()
        db.commit()
        return {"success": True, "data": dict(result._mapping)}
    except Exception as e:
        logger.error(f"Error creating overtime: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create overtime: {str(e)}")

@router.put("/overtime/{ot_id}")
async def update_overtime(
    ot_id: int,
    overtime: OvertimeCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update an overtime request"""
    try:
        existing = db.execute(text("SELECT id FROM att_overtime WHERE id = :id"), {"id": ot_id}).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Overtime not found")
        d = overtime.dict()
        minutes = round((d.get('overtime_hours') or 0) * 60) or round((d.get('hours_worked') or 0) * 60) or 0
        db.execute(text("""
            UPDATE att_overtime
               SET emp_id = :personnel_id, ot_date = :date, start_time = :start_time,
                   end_time = :end_time, minutes = :minutes, reason = :reason,
                   overtime_type = :overtime_type, hours_worked = :hours_worked,
                   overtime_hours = :overtime_hours, compensation_type = :compensation_type
             WHERE id = :ot_id
        """), {**d, "minutes": minutes, "ot_id": ot_id})
        db.commit()
        return {"success": True, "message": "Overtime updated"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update overtime: {str(e)}")


@router.post("/overtime/{ot_id}/approve")
@router.put("/overtime/{ot_id}/approve")
async def approve_overtime(
    ot_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Approve overtime"""
    try:
        db.execute(text("""
            UPDATE att_overtime
               SET approval_status = 1, approver_id = :approver_id, approved_at = CURRENT_TIMESTAMP
             WHERE id = :ot_id
        """), {"approver_id": current_user.id, "ot_id": ot_id})
        db.commit()
        return {"success": True, "message": "Overtime approved"}
    except Exception as e:
        logger.error(f"Error approving overtime: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve overtime: {str(e)}")


@router.put("/overtime/{ot_id}/reject")
async def reject_overtime(
    ot_id: int,
    body: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Reject overtime with reason"""
    try:
        db.execute(text("""
            UPDATE att_overtime
               SET approval_status = 2, approver_id = :approver_id, approved_at = CURRENT_TIMESTAMP,
                   rejection_reason = :rejection_reason
             WHERE id = :ot_id
        """), {
            "approver_id": current_user.id,
            "ot_id": ot_id,
            "rejection_reason": body.get("rejection_reason"),
        })
        db.commit()
        return {"success": True, "message": "Overtime rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject overtime: {str(e)}")


@router.put("/overtime/{ot_id}/cancel")
async def cancel_overtime(
    ot_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Cancel overtime"""
    try:
        db.execute(text("""
            UPDATE att_overtime SET approval_status = 3 WHERE id = :ot_id
        """), {"ot_id": ot_id})
        db.commit()
        return {"success": True, "message": "Overtime cancelled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel overtime: {str(e)}")


@router.delete("/overtime/{ot_id}")
async def delete_overtime(
    ot_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete overtime record"""
    try:
        existing = db.execute(text("SELECT id FROM att_overtime WHERE id = :id"), {"id": ot_id}).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Overtime not found")
        db.execute(text("DELETE FROM att_overtime WHERE id = :id"), {"id": ot_id})
        db.commit()
        return {"success": True, "message": "Overtime deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete overtime: {str(e)}")

# ============ MANUAL LOG ENDPOINTS ============

@router.get("/manual-logs")
async def get_manual_logs(
    emp_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get manual punch correction logs"""
    try:
        where = ["1=1"]
        params: dict = {}

        if emp_id:
            where.append("ml.emp_id = :emp_id")
            params["emp_id"] = emp_id
        if status is not None:
            where.append("ml.approval_status = :status")
            params["status"] = status
        if search:
            where.append("(LOWER(e.emp_code) LIKE :q OR LOWER(e.first_name || ' ' || e.last_name) LIKE :q)")
            params["q"] = f"%{search.lower()}%"
        if start_date:
            where.append("ml.punch_time >= :start_date")
            params["start_date"] = start_date
        if end_date:
            where.append("ml.punch_time <= :end_date")
            params["end_date"] = end_date

        rows = db.execute(text(f"""
            SELECT ml.id, ml.emp_id, ml.punch_time, ml.punch_state, ml.reason,
                   ml.attachment, ml.apply_time, ml.approval_status,
                   ml.approver_id, ml.approved_at, ml.created_by, ml.created_at,
                   TRIM(e.first_name || ' ' || e.last_name) AS emp_name,
                   e.emp_code,
                   cb.username AS created_by_name
            FROM att_manual_log ml
            JOIN personnel_employee e ON ml.emp_id = e.id
            LEFT JOIN auth_user cb ON ml.created_by = cb.id
            WHERE {' AND '.join(where)}
            ORDER BY ml.created_at DESC
        """), params).fetchall()

        return {"success": True, "data": [dict(r._mapping) for r in rows]}
    except Exception as e:
        logger.error(f"Error fetching manual logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch manual logs: {str(e)}")

@router.post("/manual-logs")
async def create_manual_log(
    log: ManualLogCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a manual punch correction log"""
    try:
        row = db.execute(text("""
            INSERT INTO att_manual_log
                (emp_id, punch_time, punch_state, reason, attachment, apply_time, created_by)
            VALUES
                (:emp_id, :punch_time, :punch_state, :reason, :attachment, CURRENT_TIMESTAMP, :created_by)
            RETURNING id, emp_id, punch_time, punch_state, reason, attachment,
                      apply_time, approval_status, created_by, created_at
        """), {
            "emp_id":      log.emp_id,
            "punch_time":  log.punch_time,
            "punch_state": log.punch_state,
            "reason":      log.reason,
            "attachment":  log.attachment,
            "created_by":  current_user.id,
        }).fetchone()
        db.commit()
        return {"success": True, "data": dict(row._mapping)}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating manual log: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create manual log: {str(e)}")

@router.post("/manual-logs/{log_id}/approve")
async def approve_manual_log(
    log_id: int,
    approval_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Approve or reject a manual punch log"""
    try:
        action = approval_data.get("action", "approve")
        status = 1 if action == "approve" else 2
        existing = db.execute(
            text("SELECT id FROM att_manual_log WHERE id = :id"), {"id": log_id}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Manual log not found")
        db.execute(text("""
            UPDATE att_manual_log
            SET approval_status = :status,
                approver_id     = :approver_id,
                approved_at     = CURRENT_TIMESTAMP
            WHERE id = :log_id
        """), {"status": status, "approver_id": current_user.id, "log_id": log_id})
        db.commit()
        verb = "approved" if action == "approve" else "rejected"
        return {"success": True, "message": f"Manual log {verb} successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving manual log: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve manual log: {str(e)}")

# ============ LIVE PUNCH STREAM (SSE) ============

@router.get("/punch-stream")
async def punch_stream(request: Request):
    """
    Server-Sent Events endpoint — streams punch events to the browser.
    Authenticated via short-lived ticket (query param) issued by /auth/sse-ticket,
    since EventSource doesn't support Authorization headers.
    """
    from ..services.zkteco.live_capture import add_subscriber, remove_subscriber
    from ..core.redis_client import get_redis_client as get_redis

    ticket = request.query_params.get("ticket")
    if not ticket:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Missing SSE ticket"})
    try:
        r = get_redis()
        key = f"sse_ticket:{ticket}"
        user_id = r.getdel(key)  # atomic get-and-delete (single-use)
        if not user_id:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired SSE ticket"})
    except Exception:
        # Redis unavailable — deny access; live punch data must not be served unauthenticated
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"detail": "Auth service temporarily unavailable"})

    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    add_subscriber(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive ping so proxies don't close the connection
                    yield "data: {\"type\":\"ping\"}\n\n"
        finally:
            remove_subscriber(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


# ── Punch direction helpers ───────────────────────────────────────────────────

def _parse_hhmm(s) -> Optional[time]:
    """Parse 'HH:MM' or 'HH:MM:SS' string to time, return None on failure."""
    if not s:
        return None
    try:
        parts = str(s).split(':')
        return time(int(parts[0]), int(parts[1]))
    except Exception:
        return None


def _mins(t: time) -> int:
    return t.hour * 60 + t.minute


def _in_abs_window(punch_t: time, win_start: Optional[time], win_end: Optional[time]) -> bool:
    """True if punch_t falls in [win_start, win_end], handles midnight wrap."""
    if not win_start or not win_end:
        return False
    if win_start <= win_end:
        return win_start <= punch_t <= win_end
    return punch_t >= win_start or punch_t <= win_end


def _classify_punch_direction(row: dict, rules: dict) -> str:
    """
    Classify a single transaction row into 'in' | 'out' | 'auto'.

    Priority:
      1. Explicit state (0/2/4 → in, 1/3/5 → out)
      2. Absolute facility-wide time windows from att_rules
      3. Shift-relative CI/CO windows derived from the employee's shift
    """
    ps = row.get('punch_state')

    # Explicit states
    if ps in (0, 3, 4):
        return 'in'
    if ps in (1, 2, 5):
        return 'out'

    # State 255 / unknown → classify
    pt = row.get('punch_time')
    punch_t = pt.time() if pt and hasattr(pt, 'time') else None
    if not punch_t:
        return 'auto'

    # 1. Absolute facility-wide windows
    ai_s = _parse_hhmm(rules.get('auto_in_start'))
    ai_e = _parse_hhmm(rules.get('auto_in_end'))
    ao_s = _parse_hhmm(rules.get('auto_out_start'))
    ao_e = _parse_hhmm(rules.get('auto_out_end'))

    if _in_abs_window(punch_t, ai_s, ai_e):
        return 'in'
    if _in_abs_window(punch_t, ao_s, ao_e):
        return 'out'

    # 2. Shift-relative windows
    shift_start = _parse_hhmm(row.get('shift_start'))
    shift_end   = _parse_hhmm(row.get('shift_end'))
    if shift_start and shift_end:
        try:
            ci_before = int(rules.get('checkin_window_minutes_before')  or 120)
            ci_after  = int(rules.get('checkin_window_minutes_after')   or 240)
            co_before = int(rules.get('checkout_window_minutes_before') or 240)
            co_after  = int(rules.get('checkout_window_minutes_after')  or 120)

            s_m  = _mins(shift_start)
            e_m  = _mins(shift_end)
            pt_m = _mins(punch_t)
            if e_m <= s_m:          # overnight shift
                e_m += 1440

            def in_window(v, lo, hi):
                lo, hi = lo % 1440, hi % 1440
                if lo <= hi:
                    return lo <= v % 1440 <= hi
                return v % 1440 >= lo or v % 1440 <= hi

            if in_window(pt_m, s_m - ci_before, s_m + ci_after):
                return 'in'
            if in_window(pt_m, e_m - co_before, e_m + co_after):
                return 'out'
        except Exception:
            pass

    return 'auto'


# ============ TRANSACTION ENDPOINTS ============

@router.get("/transactions")
async def get_transactions(
    search: Optional[str] = Query(None),
    emp_code: Optional[str] = Query(None),
    terminal_sn: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    verify_type: Optional[int] = Query(None),
    punch_state: Optional[int] = Query(None),
    dept_id: Optional[int] = Query(None),
    area_alias: Optional[str] = Query(None),
    area_id: Optional[int] = Query(None),
    page: int = Query(1),
    page_size: int = Query(100),
    db: Session = Depends(get_db)
):
    """Get raw punch transactions — BioTime-compatible"""
    try:
        # Join both personnel tables:
        # - personnel (UI-created, authoritative) — match on emp_code OR badge_id
        # - personnel_employee (ADMS-synced) — match on emp_code only
        # This handles F18 direct-connect punches where user_id is badge_id,
        # as well as ADMS punches and UI-only employees not yet in personnel_employee.
        # Also join iclock_terminal → personnel_area so each row carries its system area.
        query = """
            SELECT t.id, t.emp_code, t.punch_time, t.punch_state, t.verify_type,
                   t.work_code, t.terminal_sn, t.area_alias, t.upload_time,
                   COALESCE(
                       NULLIF(TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')), ''),
                       NULLIF(TRIM(COALESCE(pe.first_name,'') || ' ' || COALESCE(pe.last_name,'')), ''),
                       t.emp_code
                   ) AS emp_name,
                   COALESCE(p.id, pe.id) AS emp_id,
                   COALESCE(p.department_id, pe.dept_id) AS dept_id,
                   d.name AS dept_name,
                   COALESCE(sh.alias, sh.name) AS shift_name,
                   sh.id AS shift_id,
                   sh.start_time::text AS shift_start,
                   sh.end_time::text   AS shift_end,
                   trm.area_id         AS area_id,
                   pa.area_name        AS area_name,
                   trm.alias           AS terminal_alias,
                   trm.reader_purpose  AS reader_purpose,
                   MIN(t.punch_time) OVER (PARTITION BY t.emp_code, t.punch_time::date) AS _daily_first,
                   MAX(t.punch_time) OVER (PARTITION BY t.emp_code, t.punch_time::date) AS _daily_last,
                   COUNT(*)          OVER (PARTITION BY t.emp_code, t.punch_time::date) AS _daily_count
            FROM iclock_transaction t
            LEFT JOIN personnel p  ON (t.emp_code = p.emp_code OR t.emp_code = p.badge_id)
            LEFT JOIN personnel_employee pe ON t.emp_code = pe.emp_code AND p.id IS NULL
            LEFT JOIN departments d ON COALESCE(p.department_id, pe.dept_id) = d.id
            LEFT JOIN iclock_terminal trm ON trm.sn = t.terminal_sn
            LEFT JOIN personnel_area  pa  ON pa.id = trm.area_id
            LEFT JOIN LATERAL (
                SELECT sc.shift_id
                FROM att_schedule sc
                WHERE sc.emp_code = t.emp_code
                  AND sc.start_date <= t.punch_time::date
                  AND (sc.end_date IS NULL OR sc.end_date >= t.punch_time::date)
                ORDER BY sc.start_date DESC
                LIMIT 1
            ) latest_sched ON true
            LEFT JOIN att_shift sh ON sh.id = latest_sched.shift_id
            WHERE (trm.reader_purpose IS NULL OR trm.reader_purpose = 'ATTENDANCE')
        """
        params = {}

        if search:
            query += """
                AND (
                    t.emp_code ILIKE :search
                    OR TRIM(COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')) ILIKE :search
                    OR TRIM(COALESCE(pe.first_name,'') || ' ' || COALESCE(pe.last_name,'')) ILIKE :search
                )"""
            params['search'] = f"%{search}%"
        elif emp_code:
            query += " AND t.emp_code = :emp_code"
            params['emp_code'] = emp_code

        if terminal_sn:
            query += " AND t.terminal_sn ILIKE :terminal_sn"
            params['terminal_sn'] = f"%{terminal_sn}%"

        if area_alias:
            query += " AND t.area_alias ILIKE :area_alias"
            params['area_alias'] = f"%{area_alias}%"

        if area_id:
            query += " AND trm.area_id = :area_id"
            params['area_id'] = area_id

        if start_date:
            query += " AND t.punch_time >= :start_date"
            params['start_date'] = start_date

        if end_date:
            query += " AND t.punch_time < CAST(:end_date AS date) + interval '1 day'"
            params['end_date'] = end_date

        if verify_type is not None:
            query += " AND t.verify_type = :verify_type"
            params['verify_type'] = verify_type

        if punch_state is not None:
            query += " AND t.punch_state = :punch_state"
            params['punch_state'] = punch_state

        if dept_id:
            query += " AND COALESCE(p.department_id, pe.dept_id) = :dept_id"
            params['dept_id'] = dept_id

        count_query = f"SELECT COUNT(*) FROM ({query}) sub"
        total = db.execute(text(count_query), params).scalar()

        # Today-only stats — always scoped to CURRENT_DATE regardless of user filters.
        # Uses the same base join/filter as the main query (reader_purpose=ATTENDANCE)
        # but ignores any date, search, or field filters the user has applied.
        today_base = """
            SELECT t.punch_time, t.punch_state, t.verify_type, t.emp_code
            FROM iclock_transaction t
            LEFT JOIN iclock_terminal trm ON trm.sn = t.terminal_sn
            WHERE (trm.reader_purpose IS NULL OR trm.reader_purpose = 'ATTENDANCE')
              AND t.punch_time::date = CURRENT_DATE
        """
        stats_row = db.execute(text(f"""
            SELECT
                COUNT(*)                                                   AS today_count,
                COUNT(*) FILTER (WHERE
                    punch_state = 0
                    OR (punch_state = 255 AND punch_time = _first_of_day)
                )                                                          AS checkin_count,
                COUNT(*) FILTER (WHERE
                    punch_state = 1
                    OR (punch_state = 255 AND punch_time = _last_of_day
                        AND _daily_punches > 1)
                )                                                          AS checkout_count,
                COUNT(*) FILTER (WHERE verify_type = 200)                 AS mobile_count,
                COUNT(DISTINCT emp_code)                                   AS unique_employees
            FROM (
                SELECT *,
                    MIN(punch_time) OVER (PARTITION BY emp_code) AS _first_of_day,
                    MAX(punch_time) OVER (PARTITION BY emp_code) AS _last_of_day,
                    COUNT(*)        OVER (PARTITION BY emp_code) AS _daily_punches
                FROM ({today_base}) AS _base
            ) AS _stats
        """)).fetchone()

        query += " ORDER BY t.punch_time DESC LIMIT :limit OFFSET :offset"
        params['limit'] = page_size
        params['offset'] = (page - 1) * page_size

        rows = db.execute(text(query), params).fetchall()

        # Load rules once for classification
        rule_rows = db.execute(text("SELECT rule_key, rule_value FROM att_rules")).fetchall()
        rules_dict = {r.rule_key: r.rule_value for r in rule_rows}

        transactions = []
        for r in rows:
            row = dict(r._mapping)
            row['classified_direction'] = _classify_punch_direction(row, rules_dict)
            # Pop the private window-function columns and use them to flag
            # which punch is the effective first check-in / last check-out per day.
            daily_first = row.pop('_daily_first', None)
            daily_last  = row.pop('_daily_last',  None)
            daily_count = int(row.pop('_daily_count', 1) or 1)
            pt = row.get('punch_time')
            row['is_first_in'] = bool(pt is not None and daily_first is not None and pt == daily_first)
            row['is_last_out'] = bool(pt is not None and daily_last  is not None and pt == daily_last and daily_count > 1)
            transactions.append(row)

        return {
            "success":   True,
            "data":      transactions,
            "total":     total,
            "page":      page,
            "page_size": page_size,
            "stats": {
                "today_count":       int(stats_row.today_count       or 0),
                "checkin_count":     int(stats_row.checkin_count     or 0),
                "checkout_count":    int(stats_row.checkout_count    or 0),
                "mobile_count":      int(stats_row.mobile_count      or 0),
                "unique_employees":  int(stats_row.unique_employees  or 0),
            },
        }
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {str(e)}")


@router.delete("/transactions/{txn_id}")
async def delete_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a single transaction"""
    try:
        result = db.execute(text("DELETE FROM iclock_transaction WHERE id = :id RETURNING id"), {"id": txn_id})
        db.commit()
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {"success": True, "message": "Transaction deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete transaction: {str(e)}")


@router.delete("/transactions")
async def bulk_delete_transactions(
    ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Bulk delete transactions"""
    try:
        db.execute(text("DELETE FROM iclock_transaction WHERE id = ANY(:ids)"), {"ids": ids})
        db.commit()
        return {"success": True, "message": f"{len(ids)} transaction(s) deleted"}
    except Exception as e:
        logger.error(f"Error bulk deleting transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete transactions: {str(e)}")

@router.post("/transactions/reprocess")
async def reprocess_transactions(
    request: CalculationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Reprocess attendance calculations for a date range"""
    try:
        result = await attendance_calculation_service.calculate_attendance(
            emp_ids=request.emp_ids,
            start_date=request.start_date,
            end_date=request.end_date,
            db=db
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error reprocessing transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reprocess transactions: {str(e)}")


@router.post("/transactions/{txn_id}/reprocess")
async def reprocess_single_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Reprocess attendance calculation for the date of a single transaction"""
    try:
        txn = db.execute(
            text("SELECT emp_code, punch_time FROM iclock_transaction WHERE id = :id"),
            {"id": txn_id}
        ).fetchone()
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        # calculate_attendance takes PERSONNEL ids. This looked up the reader-mirror
        # (personnel_employee) id, which differs from personnel.id whenever the two
        # sequences have drifted — the wrong employee's day was recalculated.
        emp = db.execute(
            text("SELECT id FROM personnel WHERE emp_code = :emp_code OR badge_id = :emp_code LIMIT 1"),
            {"emp_code": txn.emp_code}
        ).fetchone()

        punch_date = txn.punch_time.date() if hasattr(txn.punch_time, 'date') else str(txn.punch_time)[:10]

        if emp:
            result = await attendance_calculation_service.calculate_attendance(
                emp_ids=[emp.id],
                start_date=str(punch_date),
                end_date=str(punch_date),
                db=db
            )
        else:
            result = {"message": "Employee not linked — transaction recorded but no report generated"}

        return {"success": True, "data": result, "transaction_id": txn_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing transaction {txn_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reprocess transaction: {str(e)}")

# ============ CALCULATION ENDPOINTS ============

@router.delete("/timesheet/clear")
async def clear_timesheet(
    start_date: str = Query(...),
    end_date: str = Query(...),
    emp_ids: Optional[str] = Query(None),          # comma-separated personnel_employee.id list
    include_transactions: bool = Query(False),      # also wipe raw punch records
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete att_report rows for the given date range.

    When include_transactions=true (full purge):
      1. Deletes raw punch records from iclock_transaction for the range.
      2. Advances att_stamp on every ADMS terminal and last_attendance_pull on every
         direct-mode device to NOW so readers do not re-upload the deleted data.
      3. Deletes the calculated att_report rows.

    When include_transactions=false (recalculate-only clear):
      Deletes att_report only.  The records will be recreated on the next punch
      or manual recalculation because the underlying transactions still exist.
    """
    from datetime import timezone as _tz
    try:
        params: dict = {"start_date": start_date, "end_date": end_date}
        id_list = [int(x) for x in emp_ids.split(",") if x.strip()] if emp_ids else None

        txn_deleted = 0
        if include_transactions:
            # Resolve emp_codes for the given personnel_employee ids (if scoped)
            if id_list:
                emp_code_rows = db.execute(text(
                    "SELECT emp_code FROM personnel_employee WHERE id = ANY(:ids)"
                ), {"ids": id_list}).fetchall()
                emp_codes = [r.emp_code for r in emp_code_rows]
                txn_result = db.execute(text(
                    "DELETE FROM iclock_transaction "
                    "WHERE punch_time::date BETWEEN :start_date AND :end_date "
                    "AND emp_code = ANY(:codes)"
                ), {**params, "codes": emp_codes})
            else:
                txn_result = db.execute(text(
                    "DELETE FROM iclock_transaction "
                    "WHERE punch_time::date BETWEEN :start_date AND :end_date"
                ), params)
            txn_deleted = txn_result.rowcount

            # Advance watermarks so devices don't re-push the deleted records
            now_utc = datetime.now(_tz.utc)
            now_ts  = int(now_utc.timestamp())

            # ADMS terminals — advance att_stamp
            db.execute(text(
                "UPDATE iclock_terminal SET att_stamp = :ts WHERE att_stamp < :ts"
            ), {"ts": now_ts})

            # Direct-mode devices — advance last_attendance_pull
            db.execute(text(
                "UPDATE devices SET last_attendance_pull = :now "
                "WHERE connection_mode IN ('direct','both') AND ip_address IS NOT NULL"
            ), {"now": now_utc})

        # Delete processed attendance records
        if id_list:
            report_result = db.execute(text(
                "DELETE FROM att_report "
                "WHERE att_date BETWEEN :start_date AND :end_date AND emp_id = ANY(:ids)"
            ), {**params, "ids": id_list})
        else:
            report_result = db.execute(text(
                "DELETE FROM att_report "
                "WHERE att_date BETWEEN :start_date AND :end_date"
            ), params)

        db.commit()
        rpt_deleted = report_result.rowcount
        logger.info(
            f"Cleared {rpt_deleted} att_report + {txn_deleted} iclock_transaction rows "
            f"({start_date}–{end_date}) by user {getattr(current_user, 'id', '?')}"
        )
        return {
            "success": True,
            "report_deleted": rpt_deleted,
            "transactions_deleted": txn_deleted,
            "watermarks_advanced": include_transactions,
            "date_range": {"start": start_date, "end": end_date},
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing timesheet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear timesheet: {str(e)}")


@router.get("/timesheet")
async def get_timesheet(
    search: Optional[str] = Query(None),
    emp_id: Optional[int] = Query(None),
    emp_code: Optional[str] = Query(None),
    dept_id: Optional[int] = Query(None),
    att_status: Optional[int] = Query(None),
    shift_id: Optional[int] = Query(None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    page: int = Query(1),
    page_size: int = Query(100),
    db: Session = Depends(get_db)
):
    """Get calculated timesheet (BioTime replica)"""
    try:
        query = """
            SELECT
                r.id, r.emp_id, r.att_date,
                r.shift_id, r.timetable_id,
                r.check_in, r.check_out,
                r.work_minutes, r.late_minutes, r.early_minutes,
                r.ot_minutes, r.overtime_minutes,
                r.att_status, r.exception_count,
                r.area_compliance, r.department_id,
                r.scheduled_minutes,
                (e.first_name || ' ' || e.last_name) AS emp_name,
                e.emp_code,
                d.name AS dept_name,
                s.name AS shift_name,
                t.start_time AS scheduled_checkin,
                t.end_time   AS scheduled_checkout,
                TO_CHAR(r.att_date, 'Dy') AS day_of_week,
                EXTRACT(DOW FROM r.att_date)::int AS day_num
            FROM att_report r
            JOIN personnel_employee e ON r.emp_id = e.id
            LEFT JOIN departments d ON e.dept_id = d.id
            LEFT JOIN att_shift s ON r.shift_id = s.id
            LEFT JOIN att_timetable t ON r.timetable_id = t.id
            WHERE r.att_date BETWEEN :start_date AND :end_date
        """
        params: dict = {"start_date": start_date, "end_date": end_date}

        if search:
            query += " AND (e.emp_code ILIKE :search OR (e.first_name || ' ' || e.last_name) ILIKE :search)"
            params["search"] = f"%{search}%"
        if emp_id:
            query += " AND r.emp_id = :emp_id"
            params["emp_id"] = emp_id
        if emp_code:
            query += " AND e.emp_code = :emp_code"
            params["emp_code"] = emp_code
        if dept_id:
            query += " AND e.dept_id = :dept_id"
            params["dept_id"] = dept_id
        if att_status is not None:
            query += " AND r.att_status = :att_status"
            params["att_status"] = att_status
        if shift_id:
            query += " AND r.shift_id = :shift_id"
            params["shift_id"] = shift_id

        count_q = f"SELECT COUNT(*) FROM ({query}) sub"
        total = db.execute(text(count_q), params).scalar()

        query += " ORDER BY r.att_date DESC, e.emp_code"
        query += " LIMIT :limit OFFSET :offset"
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

        rows = db.execute(text(query), params).fetchall()
        data = [dict(r._mapping) for r in rows]

        return {"success": True, "data": data, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error(f"Error fetching timesheet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch timesheet: {str(e)}")


@router.get("/timesheet/monthly-summary")
async def get_timesheet_monthly_summary(
    search: Optional[str] = Query(None),
    dept_id: Optional[int] = Query(None),
    shift_id: Optional[int] = Query(None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: Session = Depends(get_db)
):
    """Monthly aggregate summary per employee (BioTime Monthly Summary view)"""
    try:
        query = """
            SELECT
                e.id AS emp_id,
                e.emp_code,
                (e.first_name || ' ' || e.last_name) AS emp_name,
                d.name AS dept_name,
                COUNT(*) FILTER (WHERE r.att_status = 0) AS present_days,
                COUNT(*) FILTER (WHERE r.att_status = 3) AS absent_days,
                COUNT(*) FILTER (WHERE r.att_status = 1) AS late_count,
                COUNT(*) FILTER (WHERE r.att_status = 2) AS early_leave_count,
                COUNT(*) FILTER (WHERE r.att_status = 4) AS leave_count,
                COALESCE(SUM(r.work_minutes), 0) AS total_work_minutes,
                COALESCE(SUM(r.ot_minutes), 0) AS total_ot_minutes,
                COALESCE(SUM(r.late_minutes), 0) AS total_late_minutes,
                COALESCE(SUM(r.early_minutes), 0) AS total_early_minutes,
                COUNT(*) AS total_days,
                CASE WHEN COUNT(*) > 0
                    THEN ROUND(
                        COUNT(*) FILTER (WHERE r.att_status IN (0,1,2))::numeric / COUNT(*) * 100, 1
                    )
                    ELSE 0
                END AS attendance_rate
            FROM att_report r
            JOIN personnel_employee e ON r.emp_id = e.id
            LEFT JOIN departments d ON e.dept_id = d.id
            LEFT JOIN att_shift s ON r.shift_id = s.id
            WHERE r.att_date BETWEEN :start_date AND :end_date
        """
        params: dict = {"start_date": start_date, "end_date": end_date}

        if search:
            query += " AND (e.emp_code ILIKE :search OR (e.first_name || ' ' || e.last_name) ILIKE :search)"
            params["search"] = f"%{search}%"
        if dept_id:
            query += " AND e.dept_id = :dept_id"
            params["dept_id"] = dept_id
        if shift_id:
            query += " AND r.shift_id = :shift_id"
            params["shift_id"] = shift_id

        query += " GROUP BY e.id, e.emp_code, e.first_name, e.last_name, d.name ORDER BY e.emp_code"

        rows = db.execute(text(query), params).fetchall()
        data = [dict(r._mapping) for r in rows]

        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error fetching monthly summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch monthly summary: {str(e)}")

@router.post("/calculate")
async def calculate_attendance(
    request: CalculationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Calculate attendance for date range"""
    try:
        result = await attendance_calculation_service.calculate_attendance(
            emp_ids=request.emp_ids,
            start_date=request.start_date,
            end_date=request.end_date,
            db=db
        )
        
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error calculating attendance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate attendance: {str(e)}")

# ============ EXCEPTIONS ENDPOINTS ============

@router.get("/exceptions")
async def get_exceptions(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    dept_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get attendance exceptions from att_exception table"""
    try:
        import datetime as _dt
        if date and not start_date:
            start_date = date
        if not start_date:
            start_date = _dt.date.today().isoformat()
        if not end_date:
            end_date = start_date

        where = ["ex.att_date BETWEEN :start_date AND :end_date"]
        params: dict = {"start_date": start_date, "end_date": end_date}

        if type:
            where.append("ex.exception_type = :ex_type")
            params["ex_type"] = type
        if dept_id:
            where.append("ex.department_id = :dept_id")
            params["dept_id"] = dept_id
        if search:
            where.append("(LOWER(e.emp_code) LIKE :q OR LOWER(e.first_name || ' ' || e.last_name) LIKE :q)")
            params["q"] = f"%{search.lower()}%"

        rows = db.execute(text(f"""
            SELECT
                ex.id, ex.emp_id, ex.att_date, ex.exception_type,
                ex.deviation_minutes, ex.exception_note, ex.department_id,
                ex.handled_at, ex.handle_action, ex.handle_note, ex.created_at,
                e.emp_code,
                TRIM(e.first_name || ' ' || e.last_name) AS emp_name,
                d.name AS dept_name
            FROM att_exception ex
            JOIN personnel_employee e ON ex.emp_id = e.id
            LEFT JOIN departments d ON e.dept_id = d.id
            WHERE {' AND '.join(where)}
            ORDER BY ex.att_date DESC, ex.created_at DESC
        """), params).fetchall()

        return {"success": True, "data": [dict(r._mapping) for r in rows]}
    except Exception as e:
        logger.error(f"Error fetching exceptions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch exceptions: {str(e)}")

@router.post("/exceptions/handle")
async def handle_exceptions(
    ids: List[int] = Body(...),
    action: str = Body(...),
    note: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Handle (approve / ignore / flag) attendance exceptions"""
    try:
        if action not in ("approve", "ignore", "flag"):
            raise HTTPException(status_code=400, detail="Invalid action. Use: approve, ignore, flag")

        db.execute(text("""
            UPDATE att_exception
            SET handled_at    = CURRENT_TIMESTAMP,
                handle_action = :action,
                handle_note   = :note
            WHERE id = ANY(:ids)
        """), {"action": action, "note": note or "", "ids": ids})
        db.commit()
        return {"success": True, "message": f"{len(ids)} exception(s) {action}d successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error handling exceptions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to handle exceptions: {str(e)}")

# ============ RULES ENDPOINTS ============

def _coerce_rule(v):
    """Convert att_rules text value to its natural Python type."""
    if v is None:
        return None
    if isinstance(v, str):
        if v.lower() == 'true':  return True
        if v.lower() == 'false': return False
        try:
            f = float(v)
            return int(f) if f == int(f) else f
        except (ValueError, TypeError):
            pass
    return v


@router.get("/rules")
async def get_rules(db: Session = Depends(get_db)):
    """Get attendance rules as a flat key-value dict"""
    try:
        rows = db.execute(text("SELECT rule_key, rule_value FROM att_rules ORDER BY rule_key")).fetchall()
        data = {r._mapping['rule_key']: _coerce_rule(r._mapping['rule_value']) for r in rows}
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error fetching rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch rules: {str(e)}")

@router.put("/rules")
async def update_attendance_rules(
    rules: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update global attendance rules"""
    try:
        # Update each rule
        for rule_key, rule_value in rules.items():
            db.execute(text("""
                INSERT INTO att_rules (rule_key, rule_value, updated_by)
                VALUES (:rule_key, :rule_value, :updated_by)
                ON CONFLICT (rule_key) 
                DO UPDATE SET 
                    rule_value = EXCLUDED.rule_value,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = EXCLUDED.updated_by
            """), {
                "rule_key": rule_key,
                "rule_value": rule_value,
                "updated_by": current_user.id
            })
        
        db.commit()
        
        # Clear cache
        await attendance_cache_service.invalidate_date_cache(datetime.now().strftime('%Y-%m-%d'))
        
        return {"success": True, "message": "Rules updated successfully"}
    except Exception as e:
        logger.error(f"Error updating attendance rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update rules: {str(e)}")

# Enhanced Analytics Endpoints

@router.get("/analytics/anomalies/{emp_id}")
async def get_employee_anomalies(
    emp_id: int,
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get anomaly detection results for an employee"""
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        anomalies = await attendance_anomaly_service.detect_employee_anomalies(
            emp_id, start_dt, end_dt, db
        )
        
        return {"success": True, "data": anomalies}
    except Exception as e:
        logger.error(f"Error getting employee anomalies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get anomalies: {str(e)}")

@router.get("/analytics/anomalies/team")
async def get_team_anomalies(
    emp_ids: List[int] = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get anomaly detection results for a team"""
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        team_anomalies = await attendance_anomaly_service.detect_team_anomalies(
            emp_ids, start_dt, end_dt, db
        )
        
        return {"success": True, "data": team_anomalies}
    except Exception as e:
        logger.error(f"Error getting team anomalies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get team anomalies: {str(e)}")

@router.get("/analytics/forecast")
async def get_attendance_forecast(
    start_date: str = Query(...),
    end_date: str = Query(...),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get attendance forecast for specified period"""
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        forecasts = await attendance_predictive_service.generate_attendance_forecast(
            start_dt, end_dt, department_id, db
        )
        
        # Convert to dict for JSON serialization
        forecast_data = [
            {
                "date": f.date(),
                "expected_attendance": f.expected_attendance,
                "confidence_score": f.confidence_score,
                "factors": f.factors,
                "recommendations": f.recommendations
            }
            for f in forecasts
        ]
        
        return {"success": True, "data": forecast_data}
    except Exception as e:
        logger.error(f"Error getting attendance forecast: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get forecast: {str(e)}")

@router.get("/analytics/staffing-prediction")
async def get_staffing_prediction(
    start_date: str = Query(...),
    end_date: str = Query(...),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get staffing needs prediction"""
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        predictions = await attendance_predictive_service.predict_staffing_needs(
            start_dt, end_dt, department_id, db
        )
        
        # Convert to dict for JSON serialization
        prediction_data = [
            {
                "date": p.date,
                "department": p.department,
                "required_staff": p.required_staff,
                "available_staff": p.available_staff,
                "shortage_risk": p.shortage_risk,
                "recommendations": p.recommendations
            }
            for p in predictions
        ]
        
        return {"success": True, "data": prediction_data}
    except Exception as e:
        logger.error(f"Error getting staffing prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get staffing prediction: {str(e)}")

def _month_range(month_str: str):
    """Return (start_date, end_date) for a YYYY-MM string."""
    dt = datetime.strptime(month_str, '%Y-%m')
    start = dt.date().replace(day=1)
    if dt.month == 12:
        end = date(dt.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(dt.year, dt.month + 1, 1) - timedelta(days=1)
    return start, end


@router.get("/analytics/trends")
async def get_attendance_trends(
    month: Optional[str] = Query(None),
    dept_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Daily attendance breakdown for a month or date range."""
    try:
        if month:
            start_dt, end_dt = _month_range(month)
        elif start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt   = datetime.strptime(end_date,   '%Y-%m-%d').date()
        else:
            today    = datetime.now().date()
            start_dt = today.replace(day=1)
            end_dt   = today

        dept_filter = "AND department_id = :dept_id" if dept_id else ""
        params = {"start_dt": start_dt, "end_dt": end_dt}
        if dept_id:
            params["dept_id"] = dept_id

        rows = db.execute(text(f"""
            SELECT
                att_date,
                COUNT(*) FILTER (WHERE work_minutes > 0)                      AS present_count,
                COUNT(*) FILTER (WHERE work_minutes = 0 OR work_minutes IS NULL) AS absent_count,
                COUNT(*) FILTER (WHERE late_minutes > 0)                       AS late_count,
                0                                                               AS leave_count,
                COALESCE(SUM(ot_minutes), 0)                                   AS ot_minutes
            FROM att_report
            WHERE att_date >= :start_dt AND att_date <= :end_dt {dept_filter}
            GROUP BY att_date
            ORDER BY att_date
        """), params).fetchall()

        data = [dict(r._mapping) for r in rows]
        for d in data:
            if hasattr(d.get('att_date'), 'isoformat'):
                d['att_date'] = d['att_date'].isoformat()

        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error getting attendance trends: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get trends: {str(e)}")


@router.get("/analytics/exceptions")
async def get_exception_breakdown(
    month: Optional[str] = Query(None),
    dept_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Exception counts grouped by type for the selected month."""
    try:
        if month:
            start_dt, end_dt = _month_range(month)
        else:
            today    = datetime.now().date()
            start_dt = today.replace(day=1)
            end_dt   = today

        dept_filter = "AND department_id = :dept_id" if dept_id else ""
        params = {"start_dt": start_dt, "end_dt": end_dt}
        if dept_id:
            params["dept_id"] = dept_id

        rows = db.execute(text(f"""
            SELECT exception_type, COUNT(*) AS count
            FROM att_exception
            WHERE att_date >= :start_dt AND att_date <= :end_dt {dept_filter}
            GROUP BY exception_type
            ORDER BY count DESC
        """), params).fetchall()

        return {"success": True, "data": [dict(r._mapping) for r in rows]}
    except Exception as e:
        logger.error(f"Error getting exception breakdown: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get exceptions: {str(e)}")


@router.get("/analytics/top-exceptions")
async def get_top_exception_employees(
    month: Optional[str] = Query(None),
    dept_id: Optional[int] = Query(None),
    limit: int = Query(10),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Top employees ranked by exception count for the selected month."""
    try:
        if month:
            start_dt, end_dt = _month_range(month)
        else:
            today    = datetime.now().date()
            start_dt = today.replace(day=1)
            end_dt   = today

        dept_filter = "AND ex.department_id = :dept_id" if dept_id else ""
        params = {"start_dt": start_dt, "end_dt": end_dt, "lim": limit}
        if dept_id:
            params["dept_id"] = dept_id

        rows = db.execute(text(f"""
            SELECT
                ex.emp_id,
                TRIM(COALESCE(e.first_name,'') || ' ' || COALESCE(e.last_name,'')) AS emp_name,
                e.emp_code,
                COUNT(*)                                                                AS total_exceptions,
                COUNT(*) FILTER (WHERE ex.exception_type = 'late_arrival')             AS late_count,
                COUNT(*) FILTER (WHERE ex.exception_type = 'absent')                   AS absent_count,
                d.name AS dept_name
            FROM att_exception ex
            LEFT JOIN personnel_employee e ON ex.emp_id = e.id
            LEFT JOIN departments        d ON ex.department_id = d.id
            WHERE ex.att_date >= :start_dt AND ex.att_date <= :end_dt {dept_filter}
            GROUP BY ex.emp_id, e.first_name, e.last_name, e.emp_code, d.name
            ORDER BY total_exceptions DESC
            LIMIT :lim
        """), params).fetchall()

        return {"success": True, "data": [dict(r._mapping) for r in rows]}
    except Exception as e:
        logger.error(f"Error getting top exception employees: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get top exceptions: {str(e)}")


@router.get("/analytics/dashboard-stats")
async def get_dashboard_analytics(
    date: str = Query(...),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Comprehensive dashboard stats — today's snapshot + monthly KPIs."""
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
        month_start = target_date.replace(day=1)

        dept_filter      = "AND department_id = :dept_id"      if department_id else ""
        dept_filter_ex   = "AND ex.department_id = :dept_id"   if department_id else ""
        params: dict = {"target_date": target_date, "month_start": month_start, "month_end": target_date}
        if department_id:
            params["dept_id"] = department_id

        # --- today snapshot ---
        # today_punches: raw count from iclock_transaction so it reflects immediately
        # present_today / absent_today: from att_report (calculated data)
        raw_punches_row = db.execute(text("""
            SELECT COUNT(*) AS today_punches
            FROM iclock_transaction
            WHERE punch_time >= :target_date
              AND punch_time <  :target_date + interval '1 day'
        """), {"target_date": target_date}).fetchone()
        today_punches = int(raw_punches_row._mapping['today_punches'] or 0) if raw_punches_row else 0

        today_row = db.execute(text(f"""
            SELECT
                COUNT(*) FILTER (WHERE work_minutes > 0)                           AS present_today,
                COUNT(*) FILTER (WHERE work_minutes = 0 OR work_minutes IS NULL)   AS absent_today
            FROM att_report
            WHERE att_date = :target_date {dept_filter}
        """), params).fetchone()
        tm = today_row._mapping if today_row else {}

        # --- open exceptions (unhandled) ---
        open_ex_row = db.execute(text(f"""
            SELECT COUNT(*) AS cnt FROM att_exception
            WHERE handled_at IS NULL {dept_filter}
        """), params).fetchone()
        open_exceptions = (open_ex_row._mapping['cnt'] or 0) if open_ex_row else 0

        # --- pending approvals (leave + overtime + manual log) ---
        pending_row = db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM att_leave       WHERE approval_status = 0) +
                (SELECT COUNT(*) FROM att_overtime    WHERE approval_status = 0) +
                (SELECT COUNT(*) FROM att_manual_log  WHERE approval_status = 0) AS cnt
        """), {}).fetchone()
        pending_approvals = (pending_row._mapping['cnt'] or 0) if pending_row else 0

        # --- active employee count (status is smallint; 0 = active in BioTime) ---
        active_row = db.execute(text("""
            SELECT COUNT(*) AS cnt FROM personnel_employee
        """), {}).fetchone()
        active_employees = (active_row._mapping['cnt'] or 0) if active_row else 0

        # --- monthly KPIs from att_report ---
        monthly_row = db.execute(text(f"""
            SELECT
                ROUND(AVG(CASE WHEN work_minutes > 0 THEN 100.0 ELSE 0 END), 1)            AS avg_attendance_pct,
                ROUND(AVG(work_minutes), 0)                                                  AS avg_work_minutes,
                COALESCE(SUM(ot_minutes), 0)                                                 AS total_ot_minutes,
                ROUND(100.0 * COUNT(*) FILTER (WHERE late_minutes > 0)
                      / NULLIF(COUNT(*), 0), 1)                                              AS late_rate,
                ROUND(100.0 * COUNT(*) FILTER (WHERE work_minutes = 0 OR work_minutes IS NULL)
                      / NULLIF(COUNT(*), 0), 1)                                              AS absent_rate
            FROM att_report
            WHERE att_date >= :month_start AND att_date <= :month_end {dept_filter}
        """), params).fetchone()
        mm = monthly_row._mapping if monthly_row else {}

        # --- handled exceptions this month ---
        handled_row = db.execute(text(f"""
            SELECT COUNT(*) AS cnt FROM att_exception
            WHERE handled_at IS NOT NULL
              AND att_date >= :month_start AND att_date <= :month_end {dept_filter_ex}
        """), params).fetchone()
        handled_exceptions = (handled_row._mapping['cnt'] or 0) if handled_row else 0

        data = {
            "today_punches":      today_punches,
            "present_today":      int(tm.get('present_today')  or 0),
            "absent_today":       int(tm.get('absent_today')   or 0),
            "exceptions_count":   int(open_exceptions),
            "open_exceptions":    int(open_exceptions),
            "pending_approvals":  int(pending_approvals),
            "active_employees":   int(active_employees),
            "avg_attendance_pct": float(mm.get('avg_attendance_pct') or 0),
            "avg_work_minutes":   int(mm.get('avg_work_minutes')   or 0),
            "total_ot_minutes":   int(mm.get('total_ot_minutes')   or 0),
            "late_rate":          float(mm.get('late_rate')         or 0),
            "absent_rate":        float(mm.get('absent_rate')       or 0),
            "handled_exceptions": int(handled_exceptions),
        }

        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error getting dashboard analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@router.get("/cache/stats")
async def get_cache_statistics(
    current_user = Depends(get_current_user)
):
    """Get cache statistics for monitoring"""
    try:
        cache_stats = await attendance_cache_service.get_cache_stats()
        return {"success": True, "data": cache_stats}
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")

@router.post("/cache/clear")
async def clear_cache(
    cache_type: Optional[str] = Query(None),
    emp_id: Optional[int] = Query(None),
    date: Optional[str] = Query(None),
    current_user = Depends(get_current_user)
):
    """Clear cache entries"""
    try:
        cleared_count = 0
        
        if cache_type == "employee" and emp_id:
            await attendance_cache_service.invalidate_employee_cache(emp_id)
            cleared_count = 1
        elif cache_type == "date" and date:
            await attendance_cache_service.invalidate_date_cache(date)
            cleared_count = 1
        else:
            # Clear expired cache entries
            cleared_count = await attendance_cache_service.clear_expired_cache()
        
        return {"success": True, "message": f"Cleared {cleared_count} cache entries"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


# ── Area-based attendance monitoring ────────────────────────────────────────

def _area_day_range(date_str: str, tz_offset_minutes: int):
    """
    Convert a local calendar date + browser UTC offset into a UTC timestamp range.
    e.g. date='2026-05-31', tz_offset=60 (WAT, UTC+1)
      → start = 2026-05-30 23:00 UTC, end = 2026-05-31 23:00 UTC
    This ensures punches that cross midnight UTC are attributed to the correct local day.
    """
    local_day_start = datetime.strptime(date_str, '%Y-%m-%d')
    utc_start = local_day_start - timedelta(minutes=tz_offset_minutes)
    utc_end   = utc_start + timedelta(days=1)
    return utc_start, utc_end

# punch_state values that mean "person is present / arrived" (not a checkout)
_PRESENT_STATES = (0, 2, 4, 255)   # check-in, break-out, OT-in, unknown/access-event
_ABSENT_STATES  = (1, 3, 5)        # check-out, break-in, OT-out


@router.get("/areas/")
async def get_area_attendance_summary(
    date_str: Optional[str] = Query(None, alias="date"),
    tz_offset: int = Query(0, description="Browser UTC offset in minutes (e.g. 60 for WAT/UTC+1)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Returns every personnel_area with the day's attendance stats."""
    target = date_str or datetime.now().strftime('%Y-%m-%d')
    utc_start, utc_end = _area_day_range(target, tz_offset)
    try:
        rows = db.execute(text("""
            SELECT
                pa.id                            AS area_id,
                pa.area_code                     AS area_code,
                pa.area_name                     AS area_name,
                COUNT(DISTINCT t.sn)             AS reader_count,
                COUNT(tx.id)                     AS punch_count,
                COUNT(DISTINCT tx.emp_code)      AS employee_count,
                MAX(tx.punch_time)               AS last_activity,
                SUM(CASE WHEN tx.punch_state NOT IN (1,3,5) THEN 1 ELSE 0 END) AS checkin_count,
                SUM(CASE WHEN tx.punch_state IN (1,3,5)     THEN 1 ELSE 0 END) AS checkout_count
            FROM personnel_area pa
            LEFT JOIN iclock_terminal t  ON t.area_id = pa.id
            LEFT JOIN iclock_transaction tx
                ON tx.terminal_sn = t.sn
               AND tx.punch_time >= :utc_start
               AND tx.punch_time <  :utc_end
            GROUP BY pa.id, pa.area_code, pa.area_name
            ORDER BY pa.area_name
        """), {"utc_start": utc_start, "utc_end": utc_end}).fetchall()

        present_rows = db.execute(text("""
            SELECT area_id, COUNT(*) AS present_count
            FROM (
                SELECT trm2.area_id, tx.emp_code,
                       ROW_NUMBER() OVER (
                           PARTITION BY tx.emp_code, trm2.area_id
                           ORDER BY tx.punch_time DESC
                       ) AS rn,
                       tx.punch_state
                FROM iclock_transaction tx
                JOIN iclock_terminal trm2 ON trm2.sn = tx.terminal_sn
                WHERE trm2.area_id IS NOT NULL
                  AND tx.punch_time >= :utc_start
                  AND tx.punch_time <  :utc_end
            ) sub
            WHERE rn = 1 AND punch_state NOT IN (1, 3, 5)
            GROUP BY area_id
        """), {"utc_start": utc_start, "utc_end": utc_end}).fetchall()

        present_map = {r.area_id: r.present_count for r in present_rows}

        return {
            "date": target,
            "areas": [
                {
                    "area_id":        r.area_id,
                    "area_code":      r.area_code,
                    "area_name":      r.area_name,
                    "reader_count":   r.reader_count or 0,
                    "punch_count":    r.punch_count or 0,
                    "employee_count": r.employee_count or 0,
                    "present_count":  present_map.get(r.area_id, 0),
                    "checkin_count":  r.checkin_count or 0,
                    "checkout_count": r.checkout_count or 0,
                    "last_activity":  r.last_activity.isoformat() if r.last_activity else None,
                }
                for r in rows
            ],
        }
    except Exception as e:
        logger.error(f"Area attendance summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/areas/{area_id}/current-personnel")
async def get_area_current_personnel(
    area_id: int,
    date_str: Optional[str] = Query(None, alias="date"),
    tz_offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Employees whose last punch in the area during this local day was NOT a checkout.
    Treats punch_state 255 (access-control / undifferentiated event) as presence.
    """
    target = date_str or datetime.now().strftime('%Y-%m-%d')
    utc_start, utc_end = _area_day_range(target, tz_offset)
    try:
        rows = db.execute(text("""
            WITH latest AS (
                SELECT
                    tx.emp_code,
                    tx.punch_time,
                    tx.punch_state,
                    tx.verify_type,
                    t.alias AS terminal_alias,
                    t.sn    AS terminal_sn,
                    ROW_NUMBER() OVER (
                        PARTITION BY tx.emp_code
                        ORDER BY tx.punch_time DESC
                    ) AS rn
                FROM iclock_transaction tx
                JOIN iclock_terminal t ON t.sn = tx.terminal_sn
                WHERE t.area_id = :area_id
                  AND tx.punch_time >= :utc_start
                  AND tx.punch_time <  :utc_end
            )
            SELECT
                l.emp_code, l.punch_time, l.punch_state, l.verify_type,
                l.terminal_alias, l.terminal_sn,
                p.first_name, p.last_name, p.position
            FROM latest l
            LEFT JOIN personnel p ON p.emp_code = l.emp_code
            WHERE l.rn = 1 AND l.punch_state NOT IN (1, 3, 5)
            ORDER BY l.punch_time DESC
        """), {"area_id": area_id, "utc_start": utc_start, "utc_end": utc_end}).fetchall()

        return {
            "area_id": area_id,
            "date": target,
            "present": [
                {
                    "emp_code":       r.emp_code,
                    "name":           f"{r.first_name or ''} {r.last_name or ''}".strip() or r.emp_code,
                    "position":       r.position,
                    "punch_time":     r.punch_time.isoformat() if r.punch_time else None,
                    "punch_state":    r.punch_state,
                    "verify_type":    r.verify_type,
                    "terminal_alias": r.terminal_alias,
                    "terminal_sn":    r.terminal_sn,
                }
                for r in rows
            ],
        }
    except Exception as e:
        logger.error(f"Area current-personnel error (area_id={area_id}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/areas/{area_id}/timesheet")
async def get_area_timesheet(
    area_id: int,
    date_str: Optional[str] = Query(None, alias="date"),
    tz_offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Per-employee daily summary for employees who punched through readers in this area."""
    target = date_str or datetime.now().strftime('%Y-%m-%d')
    utc_start, utc_end = _area_day_range(target, tz_offset)
    try:
        rows = db.execute(text("""
            SELECT
                tx.emp_code,
                p.first_name,
                p.last_name,
                p.position,
                MIN(tx.punch_time)   AS first_punch,
                MAX(tx.punch_time)   AS last_punch,
                COUNT(tx.id)         AS punch_count,
                EXTRACT(EPOCH FROM (MAX(tx.punch_time) - MIN(tx.punch_time)))/60
                                     AS duration_minutes,
                MIN(CASE WHEN tx.punch_state NOT IN (1,3,5) THEN tx.punch_time END) AS first_checkin,
                MAX(CASE WHEN tx.punch_state IN (1,3,5)     THEN tx.punch_time END) AS last_checkout,
                STRING_AGG(DISTINCT t.alias, ', ' ORDER BY t.alias)                 AS readers_used
            FROM iclock_transaction tx
            JOIN iclock_terminal t ON t.sn = tx.terminal_sn
            LEFT JOIN personnel p  ON p.emp_code = tx.emp_code
            WHERE t.area_id = :area_id
              AND tx.punch_time >= :utc_start
              AND tx.punch_time <  :utc_end
            GROUP BY tx.emp_code, p.first_name, p.last_name, p.position
            ORDER BY MIN(tx.punch_time)
        """), {"area_id": area_id, "utc_start": utc_start, "utc_end": utc_end}).fetchall()

        return {
            "area_id": area_id,
            "date": target,
            "records": [
                {
                    "emp_code":         r.emp_code,
                    "name":             f"{r.first_name or ''} {r.last_name or ''}".strip() or r.emp_code,
                    "position":         r.position,
                    "first_punch":      r.first_punch.isoformat()   if r.first_punch   else None,
                    "last_punch":       r.last_punch.isoformat()    if r.last_punch    else None,
                    "first_checkin":    r.first_checkin.isoformat() if r.first_checkin else None,
                    "last_checkout":    r.last_checkout.isoformat() if r.last_checkout else None,
                    "punch_count":      r.punch_count,
                    "duration_minutes": round(r.duration_minutes or 0, 1),
                    "readers_used":     r.readers_used or '',
                }
                for r in rows
            ],
        }
    except Exception as e:
        logger.error(f"Area timesheet error (area_id={area_id}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ CONTRACTOR ATTENDANCE ENDPOINTS ============

@router.get("/contractor-stats")
async def get_contractor_attendance_stats(
    start_date: Optional[str] = Query(None),
    end_date:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dashboard stats for contractor attendance.

    When start_date/end_date are provided the period_contractors and
    period_punches stats reflect that range; otherwise they default to today.
    on_site_now is always the live current-day figure.
    """
    try:
        # Period window — default to today when no range given
        period_start = start_date or "CURRENT_DATE"
        period_end   = end_date   or "CURRENT_DATE"
        # Build date bounds as SQL literals (values already validated as ISO dates by the
        # frontend; we embed them directly in the read-only SELECT with no user-supplied
        # table/column names, so there is no injection surface)
        if start_date:
            ps_expr = f"'{start_date}'::date"
            pe_expr = f"CAST('{end_date}' AS date) + interval '1 day'"
        else:
            ps_expr = "CURRENT_DATE"
            pe_expr = "CURRENT_DATE + interval '1 day'"

        row = db.execute(text(f"""
            SELECT
                /* Unique contractors who punched in the selected period */
                (SELECT COUNT(DISTINCT t.emp_code)
                 FROM iclock_transaction t
                 INNER JOIN contractors c ON c.contractor_code = t.emp_code
                 WHERE t.punch_time >= {ps_expr}
                   AND t.punch_time <  {pe_expr}
                ) AS period_contractors,

                /* Total punches in the selected period */
                (SELECT COUNT(*)
                 FROM iclock_transaction t
                 INNER JOIN contractors c ON c.contractor_code = t.emp_code
                 WHERE t.punch_time >= {ps_expr}
                   AND t.punch_time <  {pe_expr}
                ) AS period_punches,

                /* Currently on-site today: last punch per contractor was a check-in */
                (SELECT COUNT(*)
                 FROM (
                     SELECT DISTINCT ON (t.emp_code) t.punch_state
                     FROM iclock_transaction t
                     INNER JOIN contractors c ON c.contractor_code = t.emp_code
                     WHERE t.punch_time::date = CURRENT_DATE
                     ORDER BY t.emp_code, t.punch_time DESC
                 ) last_punch
                 WHERE last_punch.punch_state IN (0, 255)
                ) AS on_site_now,

                /* Work permits expiring within 30 days */
                (SELECT COUNT(*)
                 FROM contractors c
                 WHERE c.status = 'ACTIVE'
                   AND c.work_permit_expiry IS NOT NULL
                   AND c.work_permit_expiry::date BETWEEN CURRENT_DATE AND CURRENT_DATE + 30
                ) AS permit_expiring,

                /* Already expired permits (active contractors) */
                (SELECT COUNT(*)
                 FROM contractors c
                 WHERE c.status = 'ACTIVE'
                   AND c.work_permit_expiry IS NOT NULL
                   AND c.work_permit_expiry::date < CURRENT_DATE
                ) AS permit_expired,

                /* Failed clearances (medical or background) */
                (SELECT COUNT(*)
                 FROM contractors c
                 WHERE c.status = 'ACTIVE'
                   AND (c.background_check_status = 'FAILED'
                        OR c.medical_clearance_status = 'FAILED')
                ) AS clearance_alerts,

                /* Pending clearances (medical or background) */
                (SELECT COUNT(*)
                 FROM contractors c
                 WHERE c.status = 'ACTIVE'
                   AND (c.background_check_status = 'PENDING'
                        OR c.medical_clearance_status = 'PENDING')
                ) AS clearance_pending,

                /* Total active contractors registered */
                (SELECT COUNT(*) FROM contractors WHERE status = 'ACTIVE') AS total_active
        """)).fetchone()

        data = dict(row._mapping) if row else {}
        # Back-compat aliases so the frontend can keep using today_contractors/today_punches
        data.setdefault("today_contractors", data.get("period_contractors", 0))
        data.setdefault("today_punches",     data.get("period_punches", 0))
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Contractor stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contractor-transactions")
async def get_contractor_transactions(
    search:       Optional[str]  = Query(None),
    vendor_id:    Optional[int]  = Query(None),
    punch_state:  Optional[int]  = Query(None),
    verify_type:  Optional[int]  = Query(None),
    start_date:   Optional[str]  = Query(None),
    end_date:     Optional[str]  = Query(None),
    clearance:    Optional[str]  = Query(None),   # FAILED | EXPIRING | EXPIRED | PENDING
    page:         int            = Query(1, ge=1),
    page_size:    int            = Query(100, ge=1, le=500),
    export:       bool           = Query(False),  # bypass pagination for CSV export
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Punch transactions for contractors only, enriched with vendor + compliance data."""
    try:
        base = """
            FROM iclock_transaction t
            INNER JOIN contractors  c   ON c.contractor_code = t.emp_code
            LEFT  JOIN vendors      v   ON v.id = c.vendor_id
            LEFT  JOIN iclock_terminal trm ON trm.sn = t.terminal_sn
            LEFT  JOIN personnel_area  pa  ON pa.id  = trm.area_id
            WHERE (trm.reader_purpose IS NULL OR trm.reader_purpose = 'ATTENDANCE')
        """
        params: dict = {}

        if search:
            base += """
                AND (
                    t.emp_code ILIKE :search
                    OR (c.first_name || ' ' || c.last_name) ILIKE :search
                    OR c.job_title ILIKE :search
                )"""
            params["search"] = f"%{search}%"

        if vendor_id:
            base += " AND c.vendor_id = :vendor_id"
            params["vendor_id"] = vendor_id

        if punch_state is not None:
            base += " AND t.punch_state = :punch_state"
            params["punch_state"] = punch_state

        if verify_type is not None:
            base += " AND t.verify_type = :verify_type"
            params["verify_type"] = verify_type

        if start_date:
            base += " AND t.punch_time >= :start_date"
            params["start_date"] = start_date

        if end_date:
            base += " AND t.punch_time < CAST(:end_date AS date) + interval '1 day'"
            params["end_date"] = end_date

        if clearance == "FAILED":
            base += " AND (c.background_check_status = 'FAILED' OR c.medical_clearance_status = 'FAILED')"
        elif clearance == "PENDING":
            base += " AND (c.background_check_status = 'PENDING' OR c.medical_clearance_status = 'PENDING')"
        elif clearance == "EXPIRING":
            base += " AND c.work_permit_expiry::date BETWEEN CURRENT_DATE AND CURRENT_DATE + 30"
        elif clearance == "EXPIRED":
            base += " AND c.work_permit_expiry::date < CURRENT_DATE"

        total = db.execute(text(f"SELECT COUNT(*) {base}"), params).scalar() or 0

        if export:
            limit_clause  = "LIMIT 10000 OFFSET 0"
        else:
            params["limit"]  = page_size
            params["offset"] = (page - 1) * page_size
            limit_clause = "LIMIT :limit OFFSET :offset"

        select = f"""
            SELECT
                t.id, t.emp_code, t.punch_time, t.punch_state, t.verify_type,
                t.work_code, t.terminal_sn, t.area_alias, t.upload_time,
                c.id                                      AS contractor_id,
                (c.first_name || ' ' || c.last_name)     AS contractor_name,
                c.first_name, c.last_name,
                c.job_title, c.specialization,
                c.daily_rate, c.currency,
                c.status                                  AS contractor_status,
                c.availability_status,
                c.work_permit_expiry,
                c.work_permit_number,
                c.background_check_status,
                c.medical_clearance_status,
                c.security_clearance,
                v.id                                      AS vendor_id,
                v.vendor_name                             AS vendor_name,
                trm.alias                                 AS terminal_alias,
                trm.reader_purpose,
                pa.area_name
            {base}
            ORDER BY t.punch_time DESC
            {limit_clause}
        """

        rows = db.execute(text(select), params).fetchall()

        def _row(r):
            d = dict(r._mapping)
            if d.get("punch_time"):      d["punch_time"]      = d["punch_time"].isoformat()
            if d.get("upload_time"):     d["upload_time"]     = d["upload_time"].isoformat()
            if d.get("work_permit_expiry"): d["work_permit_expiry"] = d["work_permit_expiry"].isoformat()
            return d

        return {"success": True, "data": [_row(r) for r in rows], "total": total}
    except Exception as e:
        logger.error(f"Contractor transactions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contractor-summary")
async def get_contractor_summary(
    search:     Optional[str]  = Query(None),
    vendor_id:  Optional[int]  = Query(None),
    start_date: Optional[str]  = Query(None),
    end_date:   Optional[str]  = Query(None),
    clearance:  Optional[str]  = Query(None),
    page:       int            = Query(1, ge=1),
    page_size:  int            = Query(50,  ge=1, le=200),
    export:     bool           = Query(False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Per-contractor, per-day attendance summary with clearance flags."""
    try:
        where = """
            WHERE (trm.reader_purpose IS NULL OR trm.reader_purpose = 'ATTENDANCE')
        """
        params: dict = {}

        if search:
            where += " AND ((c.first_name || ' ' || c.last_name) ILIKE :search OR t.emp_code ILIKE :search)"
            params["search"] = f"%{search}%"
        if vendor_id:
            where += " AND c.vendor_id = :vendor_id"
            params["vendor_id"] = vendor_id
        if start_date:
            where += " AND t.punch_time >= :start_date"
            params["start_date"] = start_date
        if end_date:
            where += " AND t.punch_time < CAST(:end_date AS date) + interval '1 day'"
            params["end_date"] = end_date
        if clearance == "FAILED":
            where += " AND (c.background_check_status = 'FAILED' OR c.medical_clearance_status = 'FAILED')"
        elif clearance == "PENDING":
            where += " AND (c.background_check_status = 'PENDING' OR c.medical_clearance_status = 'PENDING')"
        elif clearance == "EXPIRING":
            where += " AND c.work_permit_expiry::date BETWEEN CURRENT_DATE AND CURRENT_DATE + 30"
        elif clearance == "EXPIRED":
            where += " AND c.work_permit_expiry::date < CURRENT_DATE"

        cte = f"""
            WITH raw AS (
                SELECT
                    t.emp_code,
                    t.punch_time::date                          AS work_date,
                    t.punch_time,
                    t.punch_state,
                    c.id                                        AS contractor_id,
                    (c.first_name || ' ' || c.last_name)       AS contractor_name,
                    c.job_title,
                    c.specialization,
                    c.availability_status,
                    c.daily_rate, c.currency,
                    c.status                                    AS contractor_status,
                    c.work_permit_expiry,
                    c.work_permit_number,
                    c.background_check_status,
                    c.medical_clearance_status,
                    c.security_clearance,
                    v.id                                        AS vendor_id,
                    v.vendor_name                               AS vendor_name
                FROM iclock_transaction t
                INNER JOIN contractors  c   ON c.contractor_code = t.emp_code
                LEFT  JOIN vendors      v   ON v.id = c.vendor_id
                LEFT  JOIN iclock_terminal trm ON trm.sn = t.terminal_sn
                {where}
            ),
            agg AS (
                SELECT
                    emp_code,
                    work_date,
                    contractor_id,
                    contractor_name,
                    job_title,
                    specialization,
                    availability_status,
                    daily_rate, currency,
                    contractor_status,
                    work_permit_expiry,
                    work_permit_number,
                    background_check_status,
                    medical_clearance_status,
                    security_clearance,
                    vendor_id, vendor_name,
                    COUNT(*)                                        AS punch_count,
                    MIN(CASE WHEN punch_state IN (0,255) THEN punch_time END) AS first_in,
                    MAX(CASE WHEN punch_state = 1 THEN punch_time END)        AS last_out,
                    ROUND(
                        EXTRACT(EPOCH FROM (
                            MAX(CASE WHEN punch_state = 1 THEN punch_time END)
                            - MIN(CASE WHEN punch_state IN (0,255) THEN punch_time END)
                        )) / 3600.0
                    , 2)                                            AS hours_worked
                FROM raw
                GROUP BY emp_code, work_date, contractor_id, contractor_name,
                         job_title, specialization, availability_status,
                         daily_rate, currency, contractor_status,
                         work_permit_expiry, work_permit_number,
                         background_check_status, medical_clearance_status,
                         security_clearance, vendor_id, vendor_name
            )
            SELECT agg.*, COUNT(*) OVER () AS __total
            FROM agg
        """

        if export:
            limit_clause = "LIMIT 10000 OFFSET 0"
            query_params = params
        else:
            limit_clause = "LIMIT :limit OFFSET :offset"
            query_params = {**params, "limit": page_size, "offset": (page - 1) * page_size}

        rows = db.execute(
            text(f"{cte} ORDER BY work_date DESC, contractor_name {limit_clause}"),
            query_params
        ).fetchall()

        total = rows[0].__total if rows else 0

        def _row(r):
            d = {k: v for k, v in r._mapping.items() if k != "__total"}
            for k in ("work_date", "first_in", "last_out", "work_permit_expiry"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            return d

        return {"success": True, "data": [_row(r) for r in rows], "total": total}
    except Exception as e:
        logger.error(f"Contractor summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
