"""
Attendance Validation Service
Comprehensive validation and business rules for attendance processing
"""

from datetime import datetime, timedelta, time
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from ..models.personnel import Personnel
import logging

logger = logging.getLogger(__name__)

class AttendanceValidationService:
    """Service for attendance validation and business rules enforcement"""
    
    def __init__(self):
        self.validation_rules = {
            'max_daily_hours': 24.0,       # allow overnight / 12-h+ oil & gas shifts
            'max_weekly_hours': 84.0,
            'min_break_minutes': 15,
            'grace_period_minutes': 15,
            'round_punches_to': 5,
            'max_consecutive_days': 14,
            'min_hours_between_shifts': 8,
            'max_overtime_daily': 12.0,
            'max_overtime_weekly': 60.0,
        }
    
    async def validate_timetable(self, timetable_data: Dict[str, Any], db: Session) -> Tuple[bool, List[str]]:
        """
        Validate timetable data and business rules
        """
        errors = []
        
        # Check required fields
        if not timetable_data.get('alias'):
            errors.append("Timetable alias is required")
        
        if not timetable_data.get('checkin_time'):
            errors.append("Check-in time is required")
        
        if not timetable_data.get('checkout_time'):
            errors.append("Check-out time is required")
        
        # Validate time format and logic
        try:
            def _parse_time(s):
                for fmt in ('%H:%M:%S', '%H:%M'):
                    try:
                        return datetime.strptime(s, fmt).time()
                    except ValueError:
                        pass
                raise ValueError(f"Cannot parse time: {s}")

            checkin_time = _parse_time(timetable_data['checkin_time'])
            checkout_time = _parse_time(timetable_data['checkout_time'])

            # Calculate work hours — handle overnight shifts (checkout < checkin)
            checkin_dt  = datetime.combine(datetime.min.date(), checkin_time)
            checkout_dt = datetime.combine(datetime.min.date(), checkout_time)
            if checkout_dt <= checkin_dt:
                checkout_dt += timedelta(days=1)   # overnight shift
            work_hours = (checkout_dt - checkin_dt).total_seconds() / 3600

            if work_hours > self.validation_rules['max_daily_hours']:
                errors.append(f"Work hours cannot exceed {self.validation_rules['max_daily_hours']} hours")

            if work_hours < 0.5:
                errors.append("Work hours must be at least 30 minutes")
            
        except ValueError as e:
            errors.append("Invalid time format. Use HH:MM or HH:MM:SS")
        
        # Validate grace periods
        late_minutes = timetable_data.get('late_minutes', 0)
        early_minutes = timetable_data.get('early_minutes', 0)
        
        if late_minutes < 0 or late_minutes > 480:
            errors.append("Late grace minutes must be between 0 and 480")

        if early_minutes < 0 or early_minutes > 480:
            errors.append("Early grace minutes must be between 0 and 480")
        
        # Validate work day value
        work_day = timetable_data.get('work_day', 1.0)
        if work_day < 0.1 or work_day > 2.0:
            errors.append("Work day must be between 0.1 and 2.0")
        
        # Validate break times if provided
        break_start = timetable_data.get('break_time_start')
        break_end = timetable_data.get('break_time_end')
        
        if break_start and break_end:
            try:
                break_start_time = _parse_time(break_start)
                break_end_time = _parse_time(break_end)
                
                if break_start_time >= break_end_time:
                    errors.append("Break start time must be before break end time")

                # Check break is within work hours (overnight-safe: compare as datetimes)
                base = datetime.min.date()
                bs_dt = datetime.combine(base, break_start_time)
                be_dt = datetime.combine(base, break_end_time)
                if bs_dt < checkin_dt:
                    bs_dt += timedelta(days=1)
                    be_dt += timedelta(days=1)
                if not (checkin_dt <= bs_dt and be_dt <= checkout_dt):
                    errors.append("Break times must be within work hours")
                
                # Calculate break duration
                break_start_dt = datetime.combine(datetime.min.date(), break_start_time)
                break_end_dt = datetime.combine(datetime.min.date(), break_end_time)
                break_minutes = (break_end_dt - break_start_dt).total_seconds() / 60
                
                if break_minutes < self.validation_rules['min_break_minutes']:
                    errors.append(f"Break must be at least {self.validation_rules['min_break_minutes']} minutes")
                    
            except ValueError:
                errors.append("Invalid break time format. Use HH:MM:SS format")
        
        return len(errors) == 0, errors
    
    async def validate_shift(self, shift_data: Dict[str, Any], db: Session) -> Tuple[bool, List[str]]:
        """
        Validate shift data and business rules
        """
        errors = []
        
        # Check required fields
        if not shift_data.get('alias'):
            errors.append("Shift alias is required")
        
        if not shift_data.get('work_days'):
            errors.append("Work days are required")
        
        # Validate work days format
        # Same formats the screen saves and the attendance engine reads
        # (_is_work_day): day digits '12345' (1 = Mon … 7 = Sun) or 'Mon,Tue,…'.
        work_days = str(shift_data.get('work_days', '') or '')
        names = {'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'}
        if any(c.isalpha() for c in work_days):
            bad = [d for d in (x.strip() for x in work_days.split(',')) if d and d not in names]
            if bad:
                errors.append(f"Unknown work day(s): {', '.join(bad)} — use Mon,Tue,…")
        elif work_days and not all(c in '1234567' for c in work_days):
            errors.append("Work days must be day numbers 1–7 (1 = Monday), e.g. 12345")
        
        # Validate cycle settings
        cycle_unit = shift_data.get('cycle_unit', 0)
        cycle_count = shift_data.get('cycle_count', 1)
        
        if cycle_unit < 0 or cycle_unit > 2:
            errors.append("Cycle unit must be 0 (Daily), 1 (Weekly), or 2 (Monthly)")
        
        if cycle_count < 1 or cycle_count > 365:
            errors.append("Cycle count must be between 1 and 365")
        
        # Validate roster type
        roster_type = shift_data.get('roster_type', 0)
        if roster_type < 0 or roster_type > 2:
            errors.append("Roster type must be 0 (Regular), 1 (Rotating), or 2 (Flexible)")
        
        return len(errors) == 0, errors
    
    async def validate_schedule(self, schedule_data: Dict[str, Any], db: Session) -> Tuple[bool, List[str]]:
        """
        Validate schedule data and business rules
        """
        errors = []
        
        # Check required fields
        if not schedule_data.get('emp_id'):
            errors.append("Employee ID is required")
        
        if not schedule_data.get('shift_id'):
            errors.append("Shift ID is required")
        
        if not schedule_data.get('start_date'):
            errors.append("Start date is required")
        
        if not schedule_data.get('end_date'):
            errors.append("End date is required")
        
        # Validate employee exists
        if schedule_data.get('emp_id'):
            employee = db.query(Personnel).filter(Personnel.id == schedule_data['emp_id']).first()
            if not employee:
                errors.append("Employee not found")
            elif not employee.is_active:
                errors.append("Employee is not active")
        
        # Validate date logic
        try:
            start_date = datetime.strptime(schedule_data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(schedule_data['end_date'], '%Y-%m-%d').date()
            
            if start_date > end_date:
                errors.append("Start date must be before or equal to end date")
            
            # Check for overly long schedules
            schedule_duration = (end_date - start_date).days + 1
            if schedule_duration > 365:
                errors.append("Schedule duration cannot exceed 365 days")
            
            # Check for past dates
            today = datetime.now().date()
            if end_date < today:
                errors.append("End date cannot be in the past")
            
        except ValueError:
            errors.append("Invalid date format. Use YYYY-MM-DD format")
        
        return len(errors) == 0, errors
    
    async def validate_leave_request(self, leave_data: Dict[str, Any], db: Session) -> Tuple[bool, List[str]]:
        """
        Validate leave request and business rules
        """
        errors = []
        
        # Check required fields
        if not leave_data.get('emp_id'):
            errors.append("Employee ID is required")
        
        if not leave_data.get('leave_type_id'):
            errors.append("Leave type ID is required")
        
        if not leave_data.get('start_time'):
            errors.append("Start time is required")
        
        if not leave_data.get('end_time'):
            errors.append("End time is required")
        
        # Validate employee exists and is active
        if leave_data.get('emp_id'):
            employee = db.query(Personnel).filter(Personnel.id == leave_data['emp_id']).first()
            if not employee:
                errors.append("Employee not found")
            elif not employee.is_active:
                errors.append("Employee is not active")
        
        # Validate date logic
        try:
            start_time = datetime.fromisoformat(leave_data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(leave_data['end_time'].replace('Z', '+00:00'))
            
            if start_time >= end_time:
                errors.append("Start time must be before end time")
            
            # Check for reasonable leave duration
            leave_duration = (end_time - start_time).total_seconds() / 3600
            if leave_duration > 720:  # 30 days
                errors.append("Leave duration cannot exceed 30 days")
            
            if leave_duration < 1:  # 1 hour
                errors.append("Leave duration must be at least 1 hour")
            
        except ValueError:
            errors.append("Invalid datetime format")
        
        # Validate reason length
        reason = leave_data.get('reason', '')
        if len(reason) > 500:
            errors.append("Reason cannot exceed 500 characters")
        
        return len(errors) == 0, errors
    
    async def validate_overtime_request(self, ot_data: Dict[str, Any], db: Session) -> Tuple[bool, List[str]]:
        """
        Validate overtime request and business rules
        """
        errors = []
        
        # Check required fields
        if not ot_data.get('emp_id'):
            errors.append("Employee ID is required")
        
        if not ot_data.get('ot_date'):
            errors.append("Overtime date is required")
        
        if not ot_data.get('minutes'):
            errors.append("Overtime minutes are required")
        
        # Validate employee exists and is active
        if ot_data.get('emp_id'):
            employee = db.query(Personnel).filter(Personnel.id == ot_data['emp_id']).first()
            if not employee:
                errors.append("Employee not found")
            elif not employee.is_active:
                errors.append("Employee is not active")
        
        # Validate date
        try:
            ot_date = datetime.strptime(ot_data['ot_date'], '%Y-%m-%d').date()
            
            # Check for future dates (more than 7 days)
            future_limit = datetime.now().date() + timedelta(days=7)
            if ot_date > future_limit:
                errors.append("Overtime date cannot be more than 7 days in the future")
            
            # Check for very old dates
            past_limit = datetime.now().date() - timedelta(days=30)
            if ot_date < past_limit:
                errors.append("Overtime date cannot be more than 30 days in the past")
            
        except ValueError:
            errors.append("Invalid date format. Use YYYY-MM-DD format")
        
        # Validate minutes
        minutes = ot_data.get('minutes', 0)
        if minutes < 1:
            errors.append("Overtime minutes must be at least 1")
        
        if minutes > 480:  # 8 hours
            errors.append("Overtime minutes cannot exceed 480 (8 hours)")
        
        # Validate time range if provided
        start_time = ot_data.get('start_time')
        end_time = ot_data.get('end_time')
        
        if start_time and end_time:
            try:
                start_dt = datetime.strptime(f"{ot_data['ot_date']} {start_time}", '%Y-%m-%d %H:%M')
                end_dt = datetime.strptime(f"{ot_data['ot_date']} {end_time}", '%Y-%m-%d %H:%M')
                
                if start_dt >= end_dt:
                    errors.append("Start time must be before end time")
                
                # Calculate actual minutes and validate
                actual_minutes = (end_dt - start_dt).total_seconds() / 60
                if abs(actual_minutes - minutes) > 5:
                    errors.append("Time range does not match specified minutes")
                    
            except ValueError:
                errors.append("Invalid time format. Use HH:MM format")
        
        # Validate reason length
        reason = ot_data.get('reason', '')
        if len(reason) > 500:
            errors.append("Reason cannot exceed 500 characters")
        
        return len(errors) == 0, errors
    
    async def validate_manual_log(self, log_data: Dict[str, Any], db: Session) -> Tuple[bool, List[str]]:
        """
        Validate manual log request and business rules
        """
        errors = []
        
        # Check required fields
        if not log_data.get('emp_id'):
            errors.append("Employee ID is required")
        
        if not log_data.get('punch_time'):
            errors.append("Punch time is required")
        
        if not log_data.get('punch_state') is not None:
            errors.append("Punch state is required")
        
        # Validate employee exists and is active
        if log_data.get('emp_id'):
            employee = db.query(Personnel).filter(Personnel.id == log_data['emp_id']).first()
            if not employee:
                errors.append("Employee not found")
            elif not employee.is_active:
                errors.append("Employee is not active")
        
        # Validate punch time
        try:
            punch_time = datetime.fromisoformat(log_data['punch_time'].replace('Z', '+00:00'))
            
            # Check for future times (more than 1 hour)
            future_limit = datetime.now() + timedelta(hours=1)
            if punch_time > future_limit:
                errors.append("Punch time cannot be more than 1 hour in the future")
            
        except ValueError:
            errors.append("Invalid datetime format")
        
        # Validate punch state
        punch_state = log_data.get('punch_state')
        if punch_state not in [0, 1]:
            errors.append("Punch state must be 0 (Check In) or 1 (Check Out)")
        
        # Validate reason length
        reason = log_data.get('reason', '')
        if len(reason) > 500:
            errors.append("Reason cannot exceed 500 characters")
        
        return len(errors) == 0, errors
    
    async def validate_attendance_calculation(self, calc_data: Dict[str, Any], db: Session) -> Tuple[bool, List[str]]:
        """
        Validate attendance calculation parameters
        """
        errors = []
        
        # Validate date range
        start_date = calc_data.get('start_date')
        end_date = calc_data.get('end_date')
        
        if not start_date or not end_date:
            errors.append("Start date and end date are required")
        
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if start_dt > end_dt:
                errors.append("Start date must be before or equal to end date")
            
            # Check date range limits
            date_range = (end_dt - start_dt).days + 1
            if date_range > 365:
                errors.append("Date range cannot exceed 365 days")
            
            if date_range < 1:
                errors.append("Date range must be at least 1 day")
            
        except ValueError:
            errors.append("Invalid date format. Use YYYY-MM-DD format")
        
        # Validate employee IDs if provided
        emp_ids = calc_data.get('emp_ids')
        if emp_ids and not isinstance(emp_ids, list):
            errors.append("Employee IDs must be a list")
        
        if emp_ids and len(emp_ids) > 100:
            errors.append("Cannot process more than 100 employees at once")
        
        return len(errors) == 0, errors
    
    async def check_duplicate_schedule(self, emp_id: int, start_date: str, end_date: str, db: Session, exclude_id: Optional[int] = None) -> bool:
        """
        Check for duplicate schedules
        """
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Query for overlapping schedules
            query = """
                SELECT COUNT(*) as count
                FROM att_schedule 
                WHERE emp_id = :emp_id
                AND is_active = true
                AND (
                    (start_date <= :end_date AND end_date >= :start_date)
                )
            """
            
            params = {
                'emp_id': emp_id,
                'start_date': start_dt,
                'end_date': end_dt
            }
            
            if exclude_id:
                query += " AND id != :exclude_id"
                params['exclude_id'] = exclude_id
            
            result = db.execute(query, params).fetchone()
            return result.count > 0
            
        except Exception as e:
            logger.error(f"Error checking duplicate schedule: {e}")
            return False
    
    async def check_leave_balance(self, emp_id: int, leave_type_id: int, start_time: datetime, end_time: datetime, db: Session) -> Tuple[bool, str]:
        """
        Check if employee has sufficient leave balance
        """
        try:
            # Get leave type details
            leave_type_query = """
                SELECT max_days_per_year, affects_mustering
                FROM att_leave_type 
                WHERE id = :leave_type_id AND is_active = true
            """
            
            leave_type = db.execute(leave_type_query, {'leave_type_id': leave_type_id}).fetchone()
            
            if not leave_type:
                return False, "Leave type not found"
            
            # Calculate leave duration in days
            leave_duration = (end_time - start_time).total_seconds() / (3600 * 24)
            
            # For now, return True (balance checking would require accrual tracking)
            # In a real implementation, this would check against accrued leave balance
            
            return True, "Sufficient balance"
            
        except Exception as e:
            logger.error(f"Error checking leave balance: {e}")
            return False, "Error checking leave balance"
    
    async def validate_overtime_rules(self, ot_data: Dict[str, Any], db: Session) -> Tuple[bool, List[str]]:
        """
        Validate overtime request against overtime rules
        """
        errors = []
        
        try:
            ot_date = datetime.strptime(ot_data['ot_date'], '%Y-%m-%d').date()
            minutes = ot_data.get('minutes', 0)
            
            # Check if it's a weekend
            is_weekend = ot_date.weekday() >= 5  # Saturday=5, Sunday=6
            
            # Check if it's a holiday
            holiday_query = """
                SELECT COUNT(*) as count
                FROM att_holiday 
                WHERE :ot_date BETWEEN start_date AND end_date 
                AND is_active = true
            """
            
            holiday_result = db.execute(holiday_query, {'ot_date': ot_date}).fetchone()
            is_holiday = holiday_result.count > 0
            
            # Apply different rules based on date type
            if is_weekend:
                max_minutes = 480  # 8 hours for weekends
            elif is_holiday:
                max_minutes = 480  # 8 hours for holidays
            else:
                max_minutes = 240  # 4 hours for regular days
            
            if minutes > max_minutes:
                day_type = "weekend" if is_weekend else ("holiday" if is_holiday else "regular")
                errors.append(f"Overtime for {day_type} cannot exceed {max_minutes} minutes")
            
        except Exception as e:
            logger.error(f"Error validating overtime rules: {e}")
            errors.append("Error validating overtime rules")
        
        return len(errors) == 0, errors

# Global instance
attendance_validation_service = AttendanceValidationService()
