"""
Employee Self-Service API Endpoints
API endpoints for employee self-service functionality
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timedelta

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..services.attendance_calculation_service import attendance_calculation_service
from ..services.shift_scheduling_service import shift_scheduling_service
from ..services.holiday_service import holiday_service
from ..services.overtime_advanced_service import overtime_calculation_service
from sqlalchemy import text

router = APIRouter(prefix="/self-service", tags=["self-service"])


@router.get("/my-attendance")
async def get_my_attendance(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's attendance records
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        # Get attendance summary using stored procedure
        result = db.execute(text("""
            SELECT * FROM get_attendance_summary(:emp_code, :start_date, :end_date)
        """), {'emp_code': emp_code, 'start_date': start_date, 'end_date': end_date})
        
        attendance_records = []
        for row in result:
            attendance_records.append({
                'date': row[0].isoformat() if row[0] else None,
                'check_in_time': row[1].isoformat() if row[1] else None,
                'check_out_time': row[2].isoformat() if row[2] else None,
                'work_hours': float(row[3]) if row[3] else 0,
                'late_minutes': row[4],
                'early_departure': row[5],
                'status': row[6],
                'is_holiday': row[7]
            })
        
        return {
            'success': True,
            'data': attendance_records,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get attendance: {str(e)}"
        )


@router.post("/leave-request")
async def submit_leave_request(
    leave_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit leave request
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        result = db.execute(text("""
            INSERT INTO att_leave (
                emp_code, leave_type, start_time, end_time, 
                days_count, status, created_at, updated_at
            )
            VALUES (
                :emp_code, :leave_type, :start_time, :end_time,
                :days_count, 0, :created_at, :updated_at
            )
            RETURNING id
        """), {
            'emp_code': emp_code,
            'leave_type': leave_data['leave_type'],
            'start_time': leave_data['start_time'],
            'end_time': leave_data['end_time'],
            'days_count': leave_data.get('days_count', 1),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })
        
        leave_id = result.fetchone()[0]
        db.commit()
        
        return {
            'success': True,
            'message': 'Leave request submitted successfully',
            'leave_id': leave_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit leave request: {str(e)}"
        )


@router.get("/my-leave-requests")
async def get_my_leave_requests(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's leave requests
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        result = db.execute(text("""
            SELECT l.id, t.leave_name, l.start_time, l.end_time,
                   GREATEST(EXTRACT(EPOCH FROM (l.end_time - l.start_time)) / 86400.0, 0) AS days_count,
                   l.approval_status, l.approver_id, l.approved_at, l.created_at
            FROM att_leave l
            JOIN personnel_employee e ON e.id = l.emp_id
            LEFT JOIN att_leave_type t ON t.id = l.leave_type_id
            WHERE e.emp_code = :emp_code
            ORDER BY l.created_at DESC
        """), {'emp_code': emp_code})
        
        leave_requests = []
        for row in result:
            leave_requests.append({
                'id': row[0],
                'leave_type': row[1],
                'start_time': row[2].isoformat() if row[2] else None,
                'end_time': row[3].isoformat() if row[3] else None,
                'days_count': float(row[4]) if row[4] else 0,
                'status': row[5],
                'approved_by': row[6],
                'approved_time': row[7].isoformat() if row[7] else None,
                'created_at': row[8].isoformat() if row[8] else None
            })
        
        return {
            'success': True,
            'data': leave_requests
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get leave requests: {str(e)}"
        )


@router.get("/my-schedule")
async def get_my_schedule(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's schedule
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=30)
        
        result = db.execute(text("""
            SELECT 
                sch.start_date, sch.end_date,
                s.id as shift_id, s.name as shift_name,
                t.id as timetable_id, t.name as timetable_name,
                t.start_time, t.end_time
            FROM att_schedule sch
            JOIN att_shift s ON sch.shift_id = s.id
            JOIN att_timetable t ON s.timetable_id = t.id
            WHERE sch.emp_code = :emp_code
            AND sch.start_date <= :end_date
            AND (sch.end_date IS NULL OR sch.end_date >= :start_date)
            ORDER BY sch.start_date
        """), {'emp_code': emp_code, 'start_date': start_date, 'end_date': end_date})
        
        schedule = []
        for row in result:
            schedule.append({
                'start_date': row[0].isoformat() if row[0] else None,
                'end_date': row[1].isoformat() if row[1] else None,
                'shift_id': row[2],
                'shift_name': row[3],
                'timetable_id': row[4],
                'timetable_name': row[5],
                'start_time': str(row[6]),
                'end_time': str(row[7])
            })
        
        return {
            'success': True,
            'data': schedule,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schedule: {str(e)}"
        )


@router.get("/my-profile")
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        result = db.execute(text("""
            SELECT 
                id, emp_code, first_name, last_name, dept_id, area_id,
                hire_date, birthday, sex, photo, card_no, status
            FROM personnel_employee
            WHERE emp_code = :emp_code
        """), {'emp_code': emp_code})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        profile = {
            'id': row[0],
            'emp_code': row[1],
            'first_name': row[2],
            'last_name': row[3],
            'dept_id': row[4],
            'area_id': row[5],
            'hire_date': row[6].isoformat() if row[6] else None,
            'birthday': row[7].isoformat() if row[7] else None,
            'sex': row[8],
            'photo': row[9],
            'card_no': row[10],
            'status': row[11]
        }
        
        return {
            'success': True,
            'data': profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )


@router.put("/my-profile")
async def update_my_profile(
    profile_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        allowed_fields = ['first_name', 'last_name', 'sex', 'photo']
        update_fields = {}
        
        for field in allowed_fields:
            if field in profile_data:
                update_fields[field] = profile_data[field]
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
        
        # Build dynamic update query
        set_clauses = []
        params = {'emp_code': emp_code, 'updated_at': datetime.utcnow()}
        
        for field, value in update_fields.items():
            set_clauses.append(f"{field} = :{field}")
            params[field] = value
        
        query = f"""
            UPDATE personnel_employee
            SET {', '.join(set_clauses)}, updated_at = :updated_at
            WHERE emp_code = :emp_code
        """
        
        db.execute(text(query), params)
        db.commit()
        
        return {
            'success': True,
            'message': 'Profile updated successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.get("/my-overtime")
async def get_my_overtime(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's overtime records
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        result = db.execute(text("""
            SELECT 
                id, overtime_date, overtime_rule_id, start_time, end_time,
                total_minutes, rate, overtime_amount, status, 
                approved_by, approved_time, notes, created_at
            FROM overtime_record
            WHERE emp_code = :emp_code
            AND overtime_date BETWEEN :start_date AND :end_date
            ORDER BY overtime_date DESC
        """), {'emp_code': emp_code, 'start_date': start_date, 'end_date': end_date})
        
        overtime_records = []
        for row in result:
            overtime_records.append({
                'id': row[0],
                'overtime_date': row[1].isoformat() if row[1] else None,
                'overtime_rule_id': row[2],
                'start_time': str(row[3]) if row[3] else None,
                'end_time': str(row[4]) if row[4] else None,
                'total_minutes': row[5],
                'rate': float(row[6]) if row[6] else 0,
                'overtime_amount': float(row[7]) if row[7] else 0,
                'status': row[8],
                'approved_by': row[9],
                'approved_time': row[10].isoformat() if row[10] else None,
                'notes': row[11],
                'created_at': row[12].isoformat() if row[12] else None
            })
        
        return {
            'success': True,
            'data': overtime_records,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get overtime: {str(e)}"
        )


@router.post("/overtime-request")
async def submit_overtime_request(
    overtime_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit overtime request
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        
        result = db.execute(text("""
            INSERT INTO ssr (
                user_id, ssr_type, request_date, start_time, end_time,
                reason, status, created_at, updated_at
            )
            VALUES (
                (SELECT id FROM personnel_employee WHERE emp_code = :emp_code),
                1, :request_date, :start_time, :end_time,
                :reason, 0, :created_at, :updated_at
            )
            RETURNING id
        """), {
            'emp_code': emp_code,
            'request_date': overtime_data['request_date'],
            'start_time': overtime_data.get('start_time'),
            'end_time': overtime_data.get('end_time'),
            'reason': overtime_data.get('reason', ''),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })
        
        request_id = result.fetchone()[0]
        db.commit()
        
        return {
            'success': True,
            'message': 'Overtime request submitted successfully',
            'request_id': request_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit overtime request: {str(e)}"
        )


@router.get("/holidays")
async def get_holidays(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get holidays calendar
    """
    try:
        holidays = holiday_service.get_all_holidays(db, year)
        
        return {
            'success': True,
            'data': holidays,
            'year': year or date.today().year
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get holidays: {str(e)}"
        )


@router.get("/dashboard-summary")
async def get_dashboard_summary(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get self-service dashboard summary
    """
    try:
        emp_code = getattr(current_user, 'emp_code', None) or current_user.username
        today = date.today()
        month_start = today.replace(day=1)
        
        # Get attendance summary for current month
        try:
            attendance_result = db.execute(text("""
                SELECT
                    COUNT(*) as total_days,
                    COUNT(*) as present_days,
                    AVG(work_hours) as avg_work_hours
                FROM (
                    SELECT punch_date,
                           EXTRACT(EPOCH FROM (MAX(punch_time) - MIN(punch_time)))/3600 as work_hours
                    FROM (
                        SELECT DATE(punch_time) as punch_date, punch_time
                        FROM iclock_transaction
                        WHERE emp_code = :emp_code
                        AND DATE(punch_time) >= :month_start
                    ) t
                    GROUP BY punch_date
                ) daily
            """), {'emp_code': emp_code, 'month_start': month_start})
        except Exception:
            db.rollback()
            attendance_result = None
        
        attendance_row = attendance_result.fetchone() if attendance_result else None

        # Get pending leave requests
        try:
            leave_result = db.execute(text("""
                SELECT COUNT(*) FROM att_leave
                WHERE emp_code = :emp_code AND status = 0
            """), {'emp_code': emp_code})
            leave_row = leave_result.fetchone()
            pending_leaves = leave_row[0] if leave_row else 0
        except Exception:
            db.rollback()
            pending_leaves = 0

        # Get pending overtime requests
        try:
            overtime_result = db.execute(text("""
                SELECT COUNT(*) FROM ssr
                WHERE user_id = (SELECT id FROM personnel_employee WHERE emp_code = :emp_code)
                AND ssr_type = 1 AND status = 0
            """), {'emp_code': emp_code})
            overtime_row = overtime_result.fetchone()
            pending_overtime = overtime_row[0] if overtime_row else 0
        except Exception:
            db.rollback()
            pending_overtime = 0
        
        return {
            'success': True,
            'data': {
                'attendance': {
                    'total_days': attendance_row[0] if attendance_row else 0,
                    'present_days': attendance_row[1] if attendance_row else 0,
                    'avg_work_hours': round(attendance_row[2], 2) if attendance_row and attendance_row[2] else 0
                },
                'pending_leaves': pending_leaves,
                'pending_overtime': pending_overtime,
                'current_date': today.isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard summary: {str(e)}"
        )
