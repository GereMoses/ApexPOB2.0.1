"""
BioTime 9.5 Compatible Report Service with POB Extensions
Comprehensive reporting service aggregating data from all 12 modules
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import logging
try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    _PANDAS_AVAILABLE = False
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case, extract, text, desc, Time
from sqlalchemy.dialects.postgresql import JSONB

# Import all module models
from ..models.personnel import Personnel
from ..models.personnel import AttendanceLog
from ..models.department import Department
from ..models.access_control import AccEvent as AccessEvent
from ..models.device import Device
from ..models.biotime_models import MusteringEvent, MusteringLog, MusteringExpected, MusteringDrillSchedule, PersonnelEmployee, ZonePersonnelTracking, IClockOperLog
from ..models.emergency import EmergencyEvent, EmergencyNotification
from ..models.payroll import PaySalary, PaySalaryItem, PayPeriod, PayZoneAllowance
from ..models.visitor import VisitorVisitLog, VisitorPreRegistration, VisitorBlacklist
from ..models.meeting import MeetingBooking, MeetingAttendance, MeetingRoom
from ..models.mtd import MTDCertification, MTDMedicalRecord, MTDPPEIssue, MTDInductionRecord
from ..models.biotime_models import BaseOperationLog, AuthUser
from ..models.system import Company as BaseCompany

logger = logging.getLogger(__name__)


def _site_tz():
    from .attendance_calculation_service import SITE_TZ
    return SITE_TZ


def _day_after(d) -> str:
    """Exclusive upper bound for a date_to filter on a TIMESTAMP column. Comparing a
    timestamp with <= 'YYYY-MM-DD' stops at 00:00 of that day, so the whole last day
    of every chosen range was silently dropped."""
    return (date.fromisoformat(str(d)[:10]) + timedelta(days=1)).isoformat()


def _site_today() -> date:
    """Today on the SITE calendar. _site_today() is the container's UTC date, so
    between 00:00 and 01:00 Lagos every "today" default pointed at yesterday."""
    return datetime.now(_site_tz()).date()


class ReportService:
    """Comprehensive BioTime 9.5 compatible report service with POB extensions"""

    # Report registry - maps report codes to functions
    REPORT_REGISTRY = {}

    # Filter schema: maps report_code → {filter_key: expected_type}
    # Used by validate_filters() to strip unknown keys and coerce types.
    FILTER_SCHEMA: Dict[str, Dict[str, type]] = {
        'personnel.employee_list':  {'department': str, 'personnel_type': str, 'is_active': bool, 'search': str},
        'personnel.dept_summary':   {'department': str},
        'personnel.birthday':       {'month': int},
        'personnel.anniversary':    {'month': int, 'department': str},
        'personnel.contractor':     {'department': str, 'search': str},
        'att.daily':                {'date_from': str, 'date_to': str, 'date': str, 'department': str, 'emp_code': str, 'status': str},
        'att.monthly':              {'month': str, 'department': str},
        'att.summary':              {'date_from': str, 'date_to': str, 'department': str},
        'att.late':                 {'date': str, 'department': str},
        'att.early':                {'date': str, 'department': str},
        'att.absent':               {'date': str, 'department': str},
        'att.ot':                   {'date': str, 'department': str},
        'att.leave':                {'date_from': str, 'date_to': str, 'department': str},
        'att.shift':                {'date_from': str, 'date_to': str},
        'att.exceptions':           {'date_from': str, 'date_to': str, 'department': str},
        'ac.events':                {'date_from': str, 'date_to': str, 'emp_code': str, 'terminal_sn': str},
        'ac.door_status':           {},
        'ac.antipassback':          {'date': str},
        'ac.first_card':            {'date': str},
        'ac.inout_count':           {'date': str},
        'device.status':            {},
        'device.transactions':      {'date_from': str, 'date_to': str},
        'device.offline':           {'date_from': str, 'date_to': str},
        'device.firmware':          {},
        'muster.event':             {'event_id': int},
        'muster.drill_log':         {'date_from': str, 'date_to': str},
        'muster.headcount':         {'event_id': int},
        'muster.missing':           {'event_id': int, 'dept_name': str},
        'muster.compliance':        {'date_from': str, 'date_to': str},
        'muster.zone_performance':  {'date_from': str},
        'emergency.events':         {'event_type': str, 'date_from': str, 'date_to': str},
        'emergency.lockdown':       {'date_from': str, 'date_to': str},
        'emergency.siren':          {'date_from': str},
        'emergency.notification':   {'date_from': str, 'date_to': str},
        'emergency.response':       {'date_from': str},
        'pay.salary_summary':       {'period_id': int},
        'pay.payslip_bulk':         {'period_id': int},
        'pay.bank_sheet':           {'period_id': int},
        'pay.item_wise':            {'period_id': int},
        'pay.variance':             {'period_id': int},
        'pay.zone_cost':            {'period_id': int},
        'pay.contractor_cost':      {'period_id': int},
        'visitor.daily_log':        {'date': str},
        'visitor.host_report':      {'date_from': str, 'date_to': str},
        'visitor.overstay':         {'date_from': str, 'date_to': str},
        'visitor.blacklist':        {},
        'visitor.type_summary':     {'date_from': str, 'date_to': str},
        'visitor.induction':        {},
        'meeting.utilization':      {'date_from': str, 'date_to': str},
        'meeting.booking_log':      {'date_from': str, 'date_to': str},
        'meeting.attendance':       {'date_from': str, 'date_to': str},
        'meeting.noshow':           {'date_from': str, 'date_to': str},
        'meeting.minutes':          {'date_from': str, 'date_to': str},
        'mtd.cert_expiry':          {'days_ahead': int, 'department': str},
        'mtd.medical_expiry':       {'days_ahead': int},
        'mtd.ppe_issue':            {'date_from': str, 'date_to': str},
        'mtd.induction':            {},
        'mtd.compliance_matrix':    {},
        'mtd.non_compliant':        {'department': str},
        'system.operation_log':     {'date_from': str, 'date_to': str, 'module': str},
        'system.login_log':         {'date_from': str, 'date_to': str},
        'system.data_audit':        {'date_from': str, 'date_to': str, 'module': str},
        'system.license_usage':     {},
        'system.api_usage':         {'date_from': str, 'date_to': str},
        # Zone Security & Audit Reports
        'zone.access_log':          {'zone_id': int, 'emp_code': str, 'date_from': str, 'date_to': str},
        'zone.person_trail':        {'emp_code': str, 'date_from': str, 'date_to': str},
        'zone.current_occupancy':   {},
        'zone.security_events':     {'zone_id': int, 'date_from': str, 'date_to': str, 'event_type': str},
        # POB Operations Reports
        'pob.daily_manifest':           {'department': str, 'company': str, 'personnel_type': str, 'zone_id': int},
        'pob.crew_change':              {'date': str, 'change_type': str},
        'pob.rotation_overdue':         {'threshold_days': int, 'department': str, 'company': str},
        'pob.zone_occupancy_history':   {'zone_id': int, 'date_from': str, 'date_to': str},
        'travel.flights':               {'date_from': str, 'date_to': str, 'status': str},
        'pob.trend':                    {'date_from': str, 'date_to': str},
        'att.hr_sync':                  {'date_from': str, 'date_to': str, 'status': str},
        'personnel.no_pin':             {'department': str},
        'ac.door_access':               {'department': str, 'search': str, 'status': str},
        'muster.roll_call':             {'event_id': int, 'status': str},
        'travel.passengers':            {'date_from': str, 'date_to': str, 'direction': str, 'search': str},
        'travel.journeys':              {'date_from': str, 'date_to': str, 'status': str},
        'pob.headcount_by_company':     {'company': str},
    }
    
    def __init__(self, db: Session):
        self.db = db
        self._page = 1
        self._page_size = 50
        self._register_reports()

    def _paginate(self, query):
        """Return (rows, total) using SQL COUNT + LIMIT/OFFSET."""
        total = query.count()
        rows = query.limit(self._page_size).offset((self._page - 1) * self._page_size).all()
        return rows, total

    @staticmethod
    def _fmt_dt(dt, fmt='%Y-%m-%dT%H:%M:%S'):
        """Format a datetime as ISO-8601. Returns '' for None."""
        if dt is None:
            return ''
        try:
            return dt.strftime(fmt)
        except Exception:
            return str(dt)

    def validate_filters(self, report_code: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Strip unknown filter keys and coerce types. Raises ValueError for bad values."""
        schema = self.FILTER_SCHEMA.get(report_code)
        if schema is None:
            return filters  # Unknown code — let get_report_data raise ValueError

        cleaned: Dict[str, Any] = {}
        for key, value in filters.items():
            if key not in schema:
                logger.warning("report=%s dropped_unknown_filter=%s", report_code, key)
                continue
            if value is None:
                continue
            expected = schema[key]
            try:
                if expected is int:
                    cleaned[key] = int(value)
                elif expected is bool:
                    if isinstance(value, bool):
                        cleaned[key] = value
                    elif isinstance(value, str):
                        cleaned[key] = value.lower() in ('true', '1', 'yes')
                    else:
                        cleaned[key] = bool(value)
                else:
                    cleaned[key] = str(value)
            except (ValueError, TypeError):
                raise ValueError(f"Filter '{key}' must be {expected.__name__}, got {value!r}")
        return cleaned
    
    def _register_reports(self):
        """Register all report functions"""
        # Personnel Reports
        self.REPORT_REGISTRY.update({
            'personnel.employee_list': self.personnel_employee_list,
            'personnel.dept_summary': self.personnel_department_summary,
            'personnel.birthday': self.personnel_birthday_list,
            'personnel.anniversary': self.personnel_anniversary_list,
            'personnel.contractor': self.personnel_contractor_list,
        })
        
        # Attendance Reports
        self.REPORT_REGISTRY.update({
            'att.daily': self.attendance_daily_report,
            'att.monthly': self.attendance_monthly_summary,
            'att.summary': self.attendance_summary_report,
            'att.late': self.attendance_late_report,
            'att.early': self.attendance_early_report,
            'att.absent': self.attendance_absent_report,
            'att.ot': self.attendance_overtime_report,
            'att.leave': self.attendance_leave_report,
            'att.shift': self.attendance_shift_schedule,
            'att.exceptions': self.attendance_exceptions,
        })
        
        # Access Control Reports
        self.REPORT_REGISTRY.update({
            'ac.events': self.access_control_events,
            'ac.door_status': self.access_control_door_status,
            'ac.antipassback': self.access_control_anti_passback,
            'ac.first_card': self.access_control_first_card,
            'ac.inout_count': self.access_control_inout_count,
        })
        
        # Device Reports
        self.REPORT_REGISTRY.update({
            'device.status': self.device_status_report,
            'device.transactions': self.device_transaction_count,
            'device.offline': self.device_offline_history,
            'device.firmware': self.device_firmware_version,
        })
        
        # Mustering Reports (POB Extension)
        self.REPORT_REGISTRY.update({
            'muster.event': self.mustering_event_report,
            'muster.drill_log': self.mustering_drill_log,
            'muster.headcount': self.mustering_headcount_timeline,
            'muster.missing': self.mustering_missing_persons,
            'muster.compliance': self.mustering_compliance_percentage,
            'muster.zone_performance': self.mustering_zone_performance,
        })
        
        # Emergency Reports (POB Extension)
        self.REPORT_REGISTRY.update({
            'emergency.events': self.emergency_event_log,
            'emergency.lockdown': self.emergency_lockdown_log,
            'emergency.siren': self.emergency_siren_activation,
            'emergency.notification': self.emergency_notification_delivery,
            'emergency.response': self.emergency_response_time,
        })
        
        # Payroll Reports
        self.REPORT_REGISTRY.update({
            'pay.salary_summary': self.payroll_salary_summary,
            'pay.payslip_bulk': self.payroll_payslip_bulk,
            'pay.bank_sheet': self.payroll_bank_sheet,
            'pay.item_wise': self.payroll_item_wise,
            'pay.variance': self.payroll_variance,
            'pay.zone_cost': self.payroll_zone_cost,
            'pay.contractor_cost': self.payroll_contractor_cost,
        })
        
        # Visitor Reports
        self.REPORT_REGISTRY.update({
            'visitor.daily_log': self.visitor_daily_log,
            'visitor.host_report': self.visitor_host_report,
            'visitor.overstay': self.visitor_overstay_report,
            'visitor.blacklist': self.visitor_blacklist_report,
            'visitor.type_summary': self.visitor_type_summary,
            'visitor.induction': self.visitor_induction_status,
        })
        
        # Meeting Reports
        self.REPORT_REGISTRY.update({
            'meeting.utilization': self.meeting_room_utilization,
            'meeting.booking_log': self.meeting_booking_log,
            'meeting.attendance': self.meeting_attendance,
            'meeting.noshow': self.meeting_noshow,
            'meeting.minutes': self.meeting_minutes_status,
        })
        
        # MTD Reports (POB Extension)
        self.REPORT_REGISTRY.update({
            'mtd.cert_expiry': self.mtd_certification_expiry,
            'mtd.medical_expiry': self.mtd_medical_expiry,
            'mtd.ppe_issue': self.mtd_ppe_issue,
            'mtd.induction': self.mtd_induction_status,
            'mtd.compliance_matrix': self.mtd_compliance_matrix,
            'mtd.non_compliant': self.mtd_non_compliant,
        })
        
        # System Reports
        self.REPORT_REGISTRY.update({
            'system.operation_log': self.system_operation_log,
            'system.login_log': self.system_login_log,
            'system.data_audit': self.system_data_audit,
            'system.license_usage': self.system_license_usage,
            'system.api_usage': self.system_api_usage,
        })

        # Zone Security & Audit Reports
        self.REPORT_REGISTRY.update({
            'zone.access_log':        self.zone_access_log,
            'zone.person_trail':      self.zone_person_trail,
            'zone.current_occupancy': self.zone_current_occupancy,
            'zone.security_events':   self.zone_security_events,
        })

        # POB Operations Reports
        self.REPORT_REGISTRY.update({
            'pob.daily_manifest':           self.pob_daily_manifest,
            'pob.crew_change':              self.pob_crew_change,
            'pob.rotation_overdue':         self.pob_rotation_overdue,
            'pob.zone_occupancy_history':   self.pob_zone_occupancy_history,
            'travel.flights':               self.travel_flights,
            'pob.trend':                    self.pob_trend,
            'att.hr_sync':                  self.attendance_hr_sync,
            'personnel.no_pin':             self.personnel_no_pin,
            'ac.door_access':               self.ac_door_access,
            'muster.roll_call':             self.muster_roll_call,
            'travel.passengers':            self.travel_passengers,
            'travel.journeys':              self.travel_journeys,
            'pob.headcount_by_company':     self.pob_headcount_by_company,
        })
    
    def get_report_data(self, report_code: str, filters: Dict[str, Any], 
                       page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """
        Generic report data endpoint
        
        Args:
            report_code: Report code from registry
            filters: Filter parameters
            page: Page number
            page_size: Page size
            
        Returns:
            Dict with columns, rows, total count
        """
        try:
            if report_code not in self.REPORT_REGISTRY:
                raise ValueError(f"Report code '{report_code}' not found")
            
            # Get report function
            report_func = self.REPORT_REGISTRY[report_code]

            # Set pagination state so handlers can call self._paginate()
            self._page = page
            self._page_size = page_size

            # Validate and clean filters against the known schema
            filters = self.validate_filters(report_code, filters)

            # Run the report in SITE time: timestamps come back as Lagos wall clock and
            # ::date / date filters follow the site's day. Reports were in UTC, so every
            # time shown was an hour behind (a 06:55 tap printed as 05:55).
            tz_name = getattr(_site_tz(), "key", "Africa/Lagos")
            self.db.execute(text("SELECT set_config('TimeZone', :tz, false)"), {"tz": tz_name})
            try:
                result = report_func(filters)
            finally:
                self.db.execute(text("SELECT set_config('TimeZone', 'UTC', false)"))

            data = result.get('data', [])
            if 'total' in result:
                # Handler applied SQL-level pagination already
                total = result['total']
                paginated_data = data
            else:
                # Legacy handler: Python-level slice (safe fallback)
                total = len(data)
                start = (page - 1) * page_size
                end = start + page_size
                paginated_data = data[start:end]

            return {
                'columns': result.get('columns', []),
                'data': paginated_data,
                'total': total,
                'summary': result.get('summary', {}),
                'chart_data': result.get('chart_data', {}),
                'timezone': getattr(_site_tz(), "key", "Africa/Lagos"),
            }
            
        except Exception as e:
            logger.error(f"Error generating report {report_code}: {str(e)}")
            raise
    
    # ==================== PERSONNEL REPORTS ====================
    
    def personnel_employee_list(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Employee list with details"""
        query = self.db.query(Personnel)

        if filters.get('department'):
            query = query.filter(Personnel.department == filters['department'])
        if filters.get('personnel_type'):
            query = query.filter(Personnel.personnel_type == filters['personnel_type'])
        if filters.get('is_active') is not None:
            query = query.filter(Personnel.is_active == filters['is_active'])
        if filters.get('search'):
            search = f"%{filters['search']}%"
            query = query.filter(Personnel.full_name.ilike(search))
        
        query = query.order_by(Personnel.full_name)
        personnel, total = self._paginate(query)

        columns = [
            {'field': 'badge_id', 'label': 'Badge ID', 'type': 'text'},
            {'field': 'full_name', 'label': 'Full Name', 'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
            {'field': 'position', 'label': 'Position', 'type': 'text'},
            {'field': 'email', 'label': 'Email', 'type': 'text'},
            {'field': 'phone', 'label': 'Phone', 'type': 'text'},
            {'field': 'personnel_type', 'label': 'Type', 'type': 'text'},
            {'field': 'is_active', 'label': 'Active', 'type': 'boolean'},
        ]

        data = []
        for p in personnel:
            data.append({
                'badge_id': p.badge_id or '',
                'full_name': p.full_name or '',
                'department': p.department or '',
                'position': p.position or '',
                'email': p.email or '',
                'phone': p.phone or '',
                'personnel_type': p.personnel_type or '',
                'is_active': p.is_active or False,
            })

        return {
            'columns': columns,
            'data': data,
            'total': total,
            'summary': {'total_employees': total}
        }
    
    def personnel_department_summary(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Personnel count by department"""
        result = self.db.query(
            Personnel.department,
            func.count(Personnel.id).label('total_count'),
            func.sum(case((Personnel.is_active == True, 1), else_=0)).label('active_count'),
            func.sum(case((Personnel.personnel_type == 'Contractor', 1), else_=0)).label('contractor_count')
        ).group_by(Personnel.department).all()
        
        columns = [
            {'field': 'department', 'label': 'Department', 'type': 'text'},
            {'field': 'total_count', 'label': 'Total Count', 'type': 'number'},
            {'field': 'active_count', 'label': 'Active Count', 'type': 'number'},
            {'field': 'contractor_count', 'label': 'Contractor Count', 'type': 'number'},
        ]
        
        data = []
        for row in result:
            data.append({
                'department': row.department or 'Unknown',
                'total_count': row.total_count or 0,
                'active_count': row.active_count or 0,
                'contractor_count': row.contractor_count or 0,
            })
        
        # Chart data for bar chart
        chart_data = {
            'labels': [row['department'] for row in data],
            'datasets': [{
                'label': 'Total Employees',
                'data': [row['total_count'] for row in data],
                'backgroundColor': '#4F81BD'
            }]
        }
        
        return {
            'columns': columns,
            'data': data,
            'chart_data': chart_data,
            'summary': {'total_departments': len(data)}
        }
    
    def personnel_birthday_list(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Employee birthdays by month"""
        month_filter = filters.get('month')

        query = self.db.query(PersonnelEmployee).filter(
            PersonnelEmployee.birthday.isnot(None),
            PersonnelEmployee.status == 0,
        )
        if month_filter:
            query = query.filter(extract('month', PersonnelEmployee.birthday) == month_filter)
        query = query.order_by(extract('month', PersonnelEmployee.birthday), extract('day', PersonnelEmployee.birthday))
        employees, total = self._paginate(query)

        columns = [
            {'field': 'emp_code',   'label': 'Badge ID',    'type': 'text'},
            {'field': 'full_name',  'label': 'Full Name',   'type': 'text'},
            {'field': 'birth_date', 'label': 'Birth Date',  'type': 'date'},
            {'field': 'age',        'label': 'Age',         'type': 'number'},
        ]

        data = []
        today = _site_today()
        for emp in employees:
            if emp.birthday:
                age = today.year - emp.birthday.year - ((today.month, today.day) < (emp.birthday.month, emp.birthday.day))
                data.append({
                    'emp_code':   emp.emp_code or '',
                    'full_name':  f"{emp.first_name or ''} {emp.last_name or ''}".strip(),
                    'birth_date': emp.birthday.strftime('%Y-%m-%d'),
                    'age': age,
                })

        # Chart: aggregate by month across ALL records (separate query)
        month_agg = self.db.query(
            extract('month', PersonnelEmployee.birthday).label('m'),
            func.count().label('cnt')
        ).filter(PersonnelEmployee.birthday.isnot(None)).group_by('m').order_by('m').all()
        month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        chart_data = {
            'labels': [month_names[int(r.m) - 1] for r in month_agg],
            'datasets': [{'label': 'Birthdays', 'data': [r.cnt for r in month_agg], 'backgroundColor': '#9BBB59'}]
        }
        
        return {
            'columns': columns,
            'data': data,
            'total': total,
            'chart_data': chart_data,
            'summary': {'total_birthdays': total}
        }

    # ==================== ATTENDANCE REPORTS ====================
    
    _ATT_STATUS = {0: 'Present', 1: 'Late', 2: 'Early Leave', 3: 'Absent', 4: 'Leave', 5: 'Holiday', 6: 'Weekend'}

    def attendance_daily_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attendance audit report — one row per employee per day.
        Supports any date range via date_from / date_to.
        Joins att_report (computed) with att_timetable (scheduled) and
        iclock_transaction (raw punch count) for full audit trail.
        """
        default_from = (_site_today() - timedelta(days=6)).strftime('%Y-%m-%d')
        default_to   = _site_today().strftime('%Y-%m-%d')
        date_from = filters.get('date_from', filters.get('date', default_from))
        date_to   = filters.get('date_to',   filters.get('date', default_to))

        sql = text("""
            SELECT
                r.att_date,
                e.emp_code,
                (e.first_name || ' ' || e.last_name)   AS full_name,
                COALESCE(d.dept_name, '')               AS department,
                -- Scheduled times from timetable
                t.start_time                            AS scheduled_in,
                t.end_time                              AS scheduled_out,
                r.scheduled_minutes,
                -- Actual from att_report (computed by attendance_calculation_service)
                r.check_in,
                r.check_out,
                r.work_minutes,
                r.late_minutes,
                r.early_minutes,
                r.ot_minutes,
                r.att_status,
                -- Raw punch count from iclock_transaction for cross-verification
                COALESCE(tx.punch_count, 0)            AS punch_count
            FROM att_report r
            JOIN personnel_employee e ON r.emp_id = e.id
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            LEFT JOIN att_timetable t ON r.timetable_id = t.id
            LEFT JOIN (
                SELECT emp_code, punch_time::date AS p_date, COUNT(*) AS punch_count
                FROM iclock_transaction
                WHERE punch_time::date BETWEEN :date_from AND :date_to
                GROUP BY emp_code, punch_time::date
            ) tx ON tx.emp_code = e.emp_code AND tx.p_date = r.att_date
            WHERE r.att_date BETWEEN :date_from AND :date_to
            ORDER BY r.att_date DESC, d.dept_name, full_name
        """)
        params = {'date_from': date_from, 'date_to': date_to}

        if filters.get('emp_code'):
            sql = text(sql.text.replace(
                'WHERE r.att_date BETWEEN',
                'WHERE e.emp_code = :emp_code AND r.att_date BETWEEN'
            ))
            params['emp_code'] = filters['emp_code']

        rows = self.db.execute(sql, params).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        if filters.get('status'):
            want = filters['status'].lower()
            status_rev = {v.lower(): k for k, v in self._ATT_STATUS.items()}
            if want in status_rev:
                rows = [r for r in rows if r._mapping['att_status'] == status_rev[want]]

        columns = [
            {'field': 'att_date',          'label': 'Date',           'type': 'date',     'width': 110},
            {'field': 'emp_code',           'label': 'Emp Code',       'type': 'text',     'width': 100},
            {'field': 'full_name',          'label': 'Full Name',      'type': 'text',     'width': 160},
            {'field': 'department',         'label': 'Department',     'type': 'text',     'width': 130},
            {'field': 'scheduled_in',       'label': 'Sched In',       'type': 'text',     'width': 90},
            {'field': 'scheduled_out',      'label': 'Sched Out',      'type': 'text',     'width': 90},
            {'field': 'check_in',           'label': 'Actual In',      'type': 'datetime', 'width': 140},
            {'field': 'check_out',          'label': 'Actual Out',     'type': 'datetime', 'width': 140},
            {'field': 'work_hours',         'label': 'Work Hrs',       'type': 'number',   'width': 90},
            {'field': 'scheduled_hours',    'label': 'Sched Hrs',      'type': 'number',   'width': 90},
            {'field': 'late_minutes',       'label': 'Late (min)',      'type': 'number',   'width': 90},
            {'field': 'early_minutes',      'label': 'Early (min)',     'type': 'number',   'width': 90},
            {'field': 'ot_minutes',         'label': 'OT (min)',        'type': 'number',   'width': 80},
            {'field': 'punch_count',        'label': 'Punches',         'type': 'number',   'width': 80},
            {'field': 'status',             'label': 'Status',          'type': 'text',     'width': 100},
        ]

        data = []
        status_counts: Dict[str, int] = {}
        for r in rows:
            m = r._mapping
            ci, co = m['check_in'], m['check_out']
            st = self._ATT_STATUS.get(m['att_status'], 'Unknown')
            status_counts[st] = status_counts.get(st, 0) + 1

            # Format scheduled times (stored as timedelta in postgres time columns)
            def fmt_time(val):
                if val is None:
                    return ''
                if hasattr(val, 'strftime'):
                    return val.strftime('%H:%M')
                if hasattr(val, 'seconds'):          # timedelta
                    s = int(val.total_seconds())
                    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"
                return str(val)[:5]

            data.append({
                'att_date':       str(m['att_date']),
                'emp_code':       m['emp_code'],
                'full_name':      m['full_name'],
                'department':     m['department'],
                'scheduled_in':   fmt_time(m['scheduled_in']),
                'scheduled_out':  fmt_time(m['scheduled_out']),
                'check_in':       ci.strftime('%Y-%m-%d %H:%M') if ci else '',
                'check_out':      co.strftime('%Y-%m-%d %H:%M') if co else '',
                'work_hours':     round((m['work_minutes'] or 0) / 60, 2),
                'scheduled_hours': round((m['scheduled_minutes'] or 0) / 60, 2),
                'late_minutes':   m['late_minutes'] or 0,
                'early_minutes':  m['early_minutes'] or 0,
                'ot_minutes':     m['ot_minutes'] or 0,
                'punch_count':    m['punch_count'] or 0,
                'status':         st,
            })

        present = status_counts.get('Present', 0) + status_counts.get('Late', 0) + status_counts.get('Early Leave', 0)
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                'date_from':    date_from,
                'date_to':      date_to,
                'total_records': len(data),
                'present':      present,
                'absent':       status_counts.get('Absent', 0),
                'late':         status_counts.get('Late', 0),
                'leave':        status_counts.get('Leave', 0),
            },
        }
    
    def attendance_monthly_summary(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Monthly attendance summary from att_report"""
        month_filter = filters.get('month', _site_today().strftime('%Y-%m'))
        year, month = map(int, month_filter.split('-'))
        start_date = date(year, month, 1)
        end_date = date(year + (month // 12), (month % 12) + 1, 1) - timedelta(days=1)

        sql = text("""
            SELECT e.emp_code,
                   (e.first_name || ' ' || e.last_name) AS full_name,
                   COALESCE(d.dept_name, '') AS department,
                   COUNT(*) FILTER (WHERE r.att_status IN (0,1,2)) AS present_days,
                   COUNT(*) FILTER (WHERE r.att_status = 3)        AS absent_days,
                   COUNT(*) FILTER (WHERE r.att_status = 1)        AS late_days,
                   ROUND(SUM(r.work_minutes)::numeric / 60, 2)     AS total_work_hours,
                   SUM(r.late_minutes)                             AS total_late_minutes
            FROM att_report r
            JOIN personnel_employee e ON r.emp_id = e.id
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            WHERE r.att_date BETWEEN :start_date AND :end_date
            GROUP BY e.id, e.emp_code, e.first_name, e.last_name, d.dept_name
            ORDER BY d.dept_name, full_name
        """)
        rows = self.db.execute(sql, {'start_date': start_date, 'end_date': end_date}).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        columns = [
            {'field': 'emp_code',           'label': 'Emp Code',        'type': 'text'},
            {'field': 'full_name',          'label': 'Full Name',       'type': 'text'},
            {'field': 'department',         'label': 'Department',      'type': 'text'},
            {'field': 'present_days',       'label': 'Present Days',    'type': 'number'},
            {'field': 'absent_days',        'label': 'Absent Days',     'type': 'number'},
            {'field': 'late_days',          'label': 'Late Days',       'type': 'number'},
            {'field': 'total_work_hours',   'label': 'Work Hours',      'type': 'number'},
            {'field': 'total_late_minutes', 'label': 'Late Minutes',    'type': 'number'},
        ]
        data = [dict(r._mapping) for r in rows]

        dept_summary: Dict[str, int] = {}
        for row in data:
            d = row.get('department', '')
            dept_summary[d] = dept_summary.get(d, 0) + int(row.get('present_days') or 0)

        chart_data = {
            'labels': list(dept_summary.keys()),
            'datasets': [{'label': 'Present Days', 'data': list(dept_summary.values()), 'backgroundColor': '#0078D4'}],
        }
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'chart_data': chart_data,
            'summary': {'total_employees': len(data), 'month': month_filter},
        }
    
    def attendance_late_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Late arrival report from att_report — employees with late_minutes > 0"""
        date_filter = filters.get('date', (_site_today() - timedelta(days=1)).strftime('%Y-%m-%d'))  # = the picker's default

        sql = text("""
            SELECT e.emp_code,
                   (e.first_name || ' ' || e.last_name) AS full_name,
                   COALESCE(d.dept_name, '') AS department,
                   r.check_in, r.late_minutes
            FROM att_report r
            JOIN personnel_employee e ON r.emp_id = e.id
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            WHERE r.att_date = :att_date AND r.late_minutes > 0
            ORDER BY r.late_minutes DESC
        """)
        rows = self.db.execute(sql, {'att_date': date_filter}).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        columns = [
            {'field': 'emp_code',     'label': 'Emp Code',   'type': 'text'},
            {'field': 'full_name',    'label': 'Full Name',  'type': 'text'},
            {'field': 'department',   'label': 'Department', 'type': 'text'},
            {'field': 'check_in',     'label': 'Check In',   'type': 'datetime'},
            {'field': 'late_minutes', 'label': 'Late (min)', 'type': 'number'},
        ]
        data = []
        for r in rows:
            m = r._mapping
            ci = m['check_in']
            data.append({
                'emp_code':     m['emp_code'],
                'full_name':    m['full_name'],
                'department':   m['department'],
                'check_in':     ci.strftime('%Y-%m-%d %H:%M') if ci else '',
                'late_minutes': m['late_minutes'] or 0,
            })

        dept_late: Dict[str, int] = {}
        for row in data:
            dept_late[row['department']] = dept_late.get(row['department'], 0) + row['late_minutes']

        chart_data = {
            'labels': list(dept_late.keys()),
            'datasets': [{'label': 'Late Minutes', 'data': list(dept_late.values()), 'backgroundColor': '#F79646'}],
        }
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'chart_data': chart_data,
            'summary': {
                'total_late': len(data),
                'total_late_minutes': sum(r['late_minutes'] for r in data),
                'date': date_filter,
            },
        }
    
    # ==================== MUSTERING REPORTS (POB EXTENSION) ====================
    
    # ── Mustering label maps ─────────────────────────────────────────────────
    _MUSTER_EVENT_TYPE = {
        0: 'Real Emergency', 1: 'Drill', 2: 'Fire',
        3: 'Gas', 4: 'Man Down',
    }
    _MUSTER_STATUS  = {0: 'Active', 1: 'Completed'}
    _MUSTER_LOG_STATUS = {0: 'Missing', 1: 'Safe', 2: 'Injured'}

    def mustering_event_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """All mustering events with full headcount and compliance data."""
        default_from = (_site_today() - timedelta(days=30)).strftime('%Y-%m-%d')
        default_to   = _site_today().strftime('%Y-%m-%d')
        date_from = filters.get('date_from', default_from)
        date_to   = filters.get('date_to',   default_to)
        event_id  = filters.get('event_id')

        params: Dict[str, Any] = {'date_from': date_from, 'date_to': date_to}
        event_clause = "AND me.id = :event_id" if event_id else ""
        if event_id:
            params['event_id'] = int(event_id)

        rows = self.db.execute(text(f"""
            SELECT
                me.id,
                me.event_type,
                me.status,
                COALESCE(z.name, 'All Zones')   AS zone_name,
                u.username                       AS initiated_by,
                me.start_time,
                me.end_time,
                ROUND(EXTRACT(EPOCH FROM (me.end_time - me.start_time)) / 60, 1)
                                                 AS duration_min,
                me.total_expected,
                me.total_safe,
                me.total_missing,
                me.total_injured,
                CASE WHEN me.total_expected > 0
                    THEN ROUND(me.total_safe::numeric / me.total_expected * 100, 1)
                    ELSE NULL END                AS compliance_pct,
                COALESCE(me.description, '')     AS description
            FROM mustering_event me
            LEFT JOIN zones z     ON me.zone_id      = z.id
            LEFT JOIN auth_user u ON me.initiated_by = u.id
            WHERE me.start_time::date BETWEEN :date_from AND :date_to
              {event_clause}
            ORDER BY me.start_time DESC
        """), params).fetchall()

        columns = [
            {'field': 'event_id',       'label': 'Event ID',       'type': 'number'},
            {'field': 'event_type',     'label': 'Event Type',     'type': 'text'},
            {'field': 'status',         'label': 'Status',         'type': 'text'},
            {'field': 'zone_name',      'label': 'Zone',           'type': 'text'},
            {'field': 'initiated_by',   'label': 'Initiated By',   'type': 'text'},
            {'field': 'start_time',     'label': 'Start Time',     'type': 'datetime'},
            {'field': 'end_time',       'label': 'End Time',       'type': 'datetime'},
            {'field': 'duration_min',   'label': 'Duration (min)', 'type': 'number'},
            {'field': 'total_expected', 'label': 'Expected',       'type': 'number'},
            {'field': 'total_safe',     'label': 'Safe',           'type': 'number'},
            {'field': 'total_missing',  'label': 'Missing',        'type': 'number'},
            {'field': 'total_injured',  'label': 'Injured',        'type': 'number'},
            {'field': 'compliance_pct', 'label': 'Compliance %',   'type': 'percentage'},
            {'field': 'description',    'label': 'Notes',          'type': 'text'},
        ]
        data = [{
            'event_id':       r.id,
            'event_type':     self._MUSTER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'status':         self._MUSTER_STATUS.get(r.status, 'Unknown'),
            'zone_name':      r.zone_name or '',
            'initiated_by':   r.initiated_by or '',
            'start_time':     r.start_time.strftime('%Y-%m-%d %H:%M') if r.start_time else '',
            'end_time':       r.end_time.strftime('%Y-%m-%d %H:%M') if r.end_time else 'Ongoing',
            'duration_min':   float(r.duration_min) if r.duration_min else 0,
            'total_expected': r.total_expected or 0,
            'total_safe':     r.total_safe or 0,
            'total_missing':  r.total_missing or 0,
            'total_injured':  r.total_injured or 0,
            'compliance_pct': float(r.compliance_pct) if r.compliance_pct is not None else None,
            'description':    r.description or '',
        } for r in rows]

        pct_values = [r['compliance_pct'] for r in data if r['compliance_pct'] is not None]
        type_counts: Dict[str, int] = {}
        for r in data:
            type_counts[r['event_type']] = type_counts.get(r['event_type'], 0) + 1

        return {
            'columns': columns, 'data': data,
            'total': len(data),
            'chart_data': {
                'labels': list(type_counts.keys()),
                'values': list(type_counts.values()),
            },
            'summary': {
                'total_events':    len(data),
                'active':          sum(1 for r in data if r['status'] == 'Active'),
                'avg_compliance':  round(sum(pct_values) / len(pct_values), 1) if pct_values else 0,
                'total_safe':      sum(r['total_safe']    for r in data),
                'total_missing':   sum(r['total_missing'] for r in data),
                'total_injured':   sum(r['total_injured'] for r in data),
            },
        }

    def mustering_compliance_matrix(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Mustering compliance by zone and time"""
        from ..models.zone import Zone
        from sqlalchemy import case as sa_case
        query = (
            self.db.query(
                Zone.name.label('zone_name'),
                func.count(MusteringEvent.id).label('total_drills'),
                func.sum(sa_case(
                    (MusteringEvent.total_safe >= MusteringEvent.total_expected, 1), else_=0
                )).label('compliant_drills'),
                func.avg(
                    func.extract('epoch', MusteringEvent.end_time - MusteringEvent.start_time) / 60
                ).label('avg_response_time'),
            )
            .join(Zone, MusteringEvent.zone_id == Zone.id)
            .group_by(Zone.name)
        )
        if filters.get('date_from'):
            query = query.filter(MusteringEvent.start_time >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(MusteringEvent.start_time < _day_after(filters['date_to']))

        results = query.all()

        columns = [
            {'field': 'zone_name',        'label': 'Zone',          'type': 'text'},
            {'field': 'total_drills',      'label': 'Total Drills',  'type': 'number'},
            {'field': 'compliant_drills',  'label': 'Compliant',     'type': 'number'},
            {'field': 'avg_response_time', 'label': 'Avg Response',  'type': 'number'},
            {'field': 'compliance_rate',   'label': 'Compliance Rate','type': 'percentage'},
        ]
        data = []
        for row in results:
            compliance_rate = round((row.compliant_drills / row.total_drills * 100), 2) if row.total_drills else 0
            data.append({
                'zone_name':        row.zone_name or 'Unknown',
                'total_drills':     row.total_drills or 0,
                'compliant_drills': row.compliant_drills or 0,
                'avg_response_time':round(float(row.avg_response_time or 0), 2),
                'compliance_rate':  compliance_rate,
            })

        heatmap_data = {
            'zones': [row['zone_name'] for row in data],
            'compliance_rates': [row['compliance_rate'] for row in data],
        }
        return {
            'columns': columns,
            'data': data,
            'chart_data': {'heatmap': heatmap_data},
            'summary': {
                'total_zones': len(data),
                'avg_compliance_rate': sum(r['compliance_rate'] for r in data) / len(data) if data else 0,
            },
        }
    
    # ==================== EMERGENCY REPORTS (POB EXTENSION) ====================
    
    # ── Emergency label maps ──────────────────────────────────────────────────
    _EMER_EVENT_TYPE = {
        0: 'Lockdown', 1: 'Fire', 2: 'Gas', 3: 'Intruder', 4: 'Medical', 5: 'All Clear',
    }
    _EMER_STATUS = {0: 'Active', 1: 'Resolved', 2: 'Cancelled'}
    _EMER_SCOPE  = {0: 'Global', 1: 'Zone', 2: 'Door'}
    _EMER_INIT   = {0: 'Manual UI', 1: 'Panic Button', 2: 'Fire Panel', 3: 'API'}
    _NOTIF_CHANNEL = {0: 'SMS', 1: 'Email', 2: 'WhatsApp', 3: 'Push', 4: 'PA', 5: 'Siren'}
    _NOTIF_STATUS  = {0: 'Pending', 1: 'Sent', 2: 'Failed', 3: 'Delivered'}
    _PANIC_TYPE    = {0: 'Soft (UI)', 1: 'Hard (AUX)'}

    def emergency_event_log(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Full emergency event audit trail — enriched with zone names and initiator details."""
        params: Dict[str, Any] = {}
        type_clause = date_from_clause = date_to_clause = ""
        if filters.get('event_type'):
            type_clause = "AND e.event_type = :event_type"
            params['event_type'] = int(filters['event_type'])
        if filters.get('date_from'):
            date_from_clause = "AND e.start_time >= :date_from"
            params['date_from'] = filters['date_from']
        if filters.get('date_to'):
            date_to_clause = "AND e.start_time < CAST(:date_to AS date) + INTERVAL '1 day'"
            params['date_to'] = filters['date_to']

        rows = self.db.execute(text(f"""
            SELECT
                e.id,
                e.event_type,
                e.status,
                e.scope,
                e.start_time,
                e.end_time,
                COALESCE(
                    (SELECT string_agg(z.name, ', ' ORDER BY z.name)
                     FROM zones z WHERE z.id = ANY(e.zone_ids)),
                    'Global'
                )                                               AS zone_names,
                e.trigger_source,
                e.reason,
                e.initiated_type,
                COALESCE(
                    NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''),
                    u.username,
                    'System'
                )                                               AS initiator_name,
                u.username                                      AS initiator_username,
                EXTRACT(EPOCH FROM (COALESCE(e.end_time, now()) - e.start_time))/60 AS duration_min,
                (SELECT COUNT(*) FROM emergency_panic_log p WHERE p.emergency_event_id = e.id) AS panic_count,
                (SELECT COUNT(*) FROM emergency_notification n WHERE n.emergency_event_id = e.id) AS notif_count
            FROM emergency_event e
            LEFT JOIN auth_user u ON e.initiated_by = u.id
            WHERE 1=1
              {type_clause}
              {date_from_clause}
              {date_to_clause}
            ORDER BY e.start_time DESC
        """), params).fetchall()

        columns = [
            {'field': 'event_id',          'label': 'Event ID',        'type': 'number'},
            {'field': 'start_time',         'label': 'Start Time',      'type': 'datetime'},
            {'field': 'end_time',           'label': 'End Time',        'type': 'datetime'},
            {'field': 'event_type',         'label': 'Event Type',      'type': 'text'},
            {'field': 'status',             'label': 'Status',          'type': 'text'},
            {'field': 'scope',              'label': 'Scope',           'type': 'text'},
            {'field': 'zone_names',         'label': 'Zones Affected',  'type': 'text'},
            {'field': 'trigger_source',     'label': 'Trigger Source',  'type': 'text'},
            {'field': 'reason',             'label': 'Reason',          'type': 'text'},
            {'field': 'initiator',          'label': 'Initiated By',    'type': 'text'},
            {'field': 'initiated_type',     'label': 'Initiation Type', 'type': 'text'},
            {'field': 'duration_min',       'label': 'Duration (min)',  'type': 'number'},
            {'field': 'panic_count',        'label': 'Panic Triggers',  'type': 'number'},
            {'field': 'notification_count', 'label': 'Notifications',   'type': 'number'},
        ]
        data = [{
            'event_id':          r.id,
            'start_time':        r.start_time.strftime('%Y-%m-%d %H:%M:%S') if r.start_time else '',
            'end_time':          r.end_time.strftime('%Y-%m-%d %H:%M:%S') if r.end_time else '—',
            'event_type':        self._EMER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'status':            self._EMER_STATUS.get(r.status, 'Active'),
            'scope':             self._EMER_SCOPE.get(r.scope, 'Global'),
            'zone_names':        r.zone_names or 'Global',
            'trigger_source':    r.trigger_source or '—',
            'reason':            r.reason or '—',
            'initiator':         r.initiator_name or '—',
            'initiated_type':    self._EMER_INIT.get(r.initiated_type, 'Manual UI'),
            'duration_min':      round(float(r.duration_min or 0), 2),
            'panic_count':       int(r.panic_count or 0),
            'notification_count':int(r.notif_count or 0),
        } for r in rows]

        type_dist: Dict[str, int] = {}
        for row in data:
            t = row['event_type']
            type_dist[t] = type_dist.get(t, 0) + 1
        active = sum(1 for r in rows if (r.status or 0) == 0)
        durations = [r['duration_min'] for r in data if r['duration_min'] > 0]
        return {
            'columns': columns,
            'data': data,
            'total': len(data),
            'summary': {
                'total_events':    len(data),
                'active':          active,
                'resolved':        len(data) - active,
                'avg_duration_min': round(sum(durations) / len(durations), 2) if durations else 0,
                'type_distribution': type_dist,
            },
        }
    
    # ==================== PAYROLL REPORTS ====================
    
    # ── Payroll label maps ────────────────────────────────────────────────────
    _PAY_CALC_STATUS = {
        'PENDING': 'Pending', 'CALCULATED': 'Calculated',
        'VERIFIED': 'Verified', 'APPROVED': 'Approved',
    }
    _PAY_PERIOD_STATUS = {
        'OPEN': 'Open', 'CALCULATING': 'Calculating',
        'CLOSED': 'Closed', 'CANCELLED': 'Cancelled',
    }
    _PAY_ITEM_TYPE = {'EARNING': 'Earning', 'DEDUCTION': 'Deduction', 'ATTENDANCE': 'Attendance'}

    @staticmethod
    def _latest_period_id(db) -> int | None:
        row = db.execute(text(
            "SELECT id FROM pay_period ORDER BY end_date DESC LIMIT 1"
        )).fetchone()
        return row.id if row else None

    @staticmethod
    def _period_meta(db, period_id: int) -> dict:
        row = db.execute(text(
            "SELECT period_name, start_date, end_date, status FROM pay_period WHERE id = :pid"
        ), {'pid': period_id}).fetchone()
        if not row:
            return {}
        return {
            'period_id':   period_id,
            'period_name': row.period_name,
            'start_date':  str(row.start_date),
            'end_date':    str(row.end_date),
            'period_status': row.status or '',
        }

    @staticmethod
    def _employee_roster_context(db) -> dict:
        """Fallback context when no payroll periods exist — shows payroll-ready headcount."""
        rows = db.execute(text("""
            SELECT department,
                   COUNT(*)                                         AS total,
                   COUNT(CASE WHEN is_active THEN 1 END)           AS active,
                   COUNT(CASE WHEN personnel_type='CONTRACTOR' THEN 1 END) AS contractors
            FROM personnel
            GROUP BY department
            ORDER BY department
        """)).fetchall()
        return {
            'no_payroll_data': True,
            'message': 'No payroll periods found. Create a pay period to run payroll.',
            'employee_roster': [
                {'department': r.department or 'Unassigned',
                 'total': int(r.total), 'active': int(r.active),
                 'contractors': int(r.contractors)}
                for r in rows
            ],
            'total_active_employees': sum(int(r.active) for r in rows),
        }

    def payroll_salary_summary(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Salary summary by department for a pay period — with period header and dept breakdown."""
        period_id = filters.get('period_id') or self._latest_period_id(self.db)
        if not period_id:
            return {'columns': [], 'data': [], 'total': 0,
                    'summary': self._employee_roster_context(self.db)}

        rows = self.db.execute(text("""
            SELECT
                COALESCE(NULLIF(p.department, ''), 'Unassigned')   AS department,
                COUNT(s.id)                                         AS employee_count,
                COALESCE(SUM(s.basic_salary),     0)               AS total_basic,
                COALESCE(SUM(s.gross_salary),     0)               AS total_gross,
                COALESCE(SUM(s.total_earnings),   0)               AS total_earnings,
                COALESCE(SUM(s.total_deductions), 0)               AS total_deductions,
                COALESCE(SUM(s.net_salary),       0)               AS total_net,
                COALESCE(AVG(s.gross_salary),     0)               AS avg_gross,
                COALESCE(AVG(s.net_salary),       0)               AS avg_net,
                COALESCE(SUM(s.ot_hours),         0)               AS total_ot_hours,
                COALESCE(SUM(s.present_days),     0)               AS total_present_days,
                COALESCE(SUM(s.absent_days),      0)               AS total_absent_days
            FROM pay_salary s
            JOIN personnel p ON s.emp_id = p.id
            WHERE s.period_id = :pid
            GROUP BY COALESCE(NULLIF(p.department, ''), 'Unassigned')
            ORDER BY department
        """), {'pid': period_id}).fetchall()

        columns = [
            {'field': 'department',       'label': 'Department',    'type': 'text'},
            {'field': 'employee_count',   'label': 'Employees',     'type': 'number'},
            {'field': 'total_basic',      'label': 'Total Basic',   'type': 'currency'},
            {'field': 'total_earnings',   'label': 'Total Earnings','type': 'currency'},
            {'field': 'total_deductions', 'label': 'Deductions',    'type': 'currency'},
            {'field': 'total_gross',      'label': 'Total Gross',   'type': 'currency'},
            {'field': 'total_net',        'label': 'Total Net',     'type': 'currency'},
            {'field': 'avg_gross',        'label': 'Avg Gross',     'type': 'currency'},
            {'field': 'avg_net',          'label': 'Avg Net',       'type': 'currency'},
            {'field': 'total_ot_hours',   'label': 'OT Hours',      'type': 'number'},
            {'field': 'total_present_days','label': 'Present Days', 'type': 'number'},
            {'field': 'total_absent_days', 'label': 'Absent Days',  'type': 'number'},
        ]
        data = [{
            'department':       r.department,
            'employee_count':   int(r.employee_count),
            'total_basic':      float(r.total_basic),
            'total_earnings':   float(r.total_earnings),
            'total_deductions': float(r.total_deductions),
            'total_gross':      float(r.total_gross),
            'total_net':        float(r.total_net),
            'avg_gross':        round(float(r.avg_gross), 2),
            'avg_net':          round(float(r.avg_net), 2),
            'total_ot_hours':   float(r.total_ot_hours),
            'total_present_days': float(r.total_present_days),
            'total_absent_days':  float(r.total_absent_days),
        } for r in rows]

        chart_data = {
            'labels': [r['department'] for r in data],
            'datasets': [
                {'label': 'Gross Salary', 'data': [r['total_gross'] for r in data], 'backgroundColor': '#4F81BD'},
                {'label': 'Net Salary',   'data': [r['total_net']   for r in data], 'backgroundColor': '#70AD47'},
            ],
        }
        meta = self._period_meta(self.db, period_id)
        return {
            'columns': columns, 'data': data, 'chart_data': chart_data,
            'total': len(data),
            'summary': {
                **meta,
                'total_employees':    sum(r['employee_count']   for r in data),
                'total_gross':        round(sum(r['total_gross'] for r in data), 2),
                'total_net':          round(sum(r['total_net']   for r in data), 2),
                'total_deductions':   round(sum(r['total_deductions'] for r in data), 2),
            },
        }

    def payroll_zone_cost(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """POB zone cost analysis — salary data grouped by employee's current zone, with zone allowance config."""
        period_id = filters.get('period_id') or self._latest_period_id(self.db)

        # Zone allowance configuration (always available regardless of period data)
        allowance_rows = self.db.execute(text("""
            SELECT
                COALESCE(z.name, za.zone_name, 'Unknown Zone') AS zone_name,
                za.allowance_type,
                za.amount                                       AS allowance_amount,
                za.is_hazard,
                za.hazard_rate,
                za.effective_date,
                za.end_date,
                za.is_active
            FROM pay_zone_allowance za
            LEFT JOIN zones z ON za.area_id = z.id
            ORDER BY zone_name
        """)).fetchall()

        # Salary breakdown by zone (when period data exists)
        salary_rows = []
        if period_id:
            salary_rows = self.db.execute(text("""
                SELECT
                    COALESCE(z.name, p.current_location, 'Unassigned') AS zone_name,
                    COUNT(s.id)                                         AS employee_count,
                    COALESCE(SUM(s.zone_hours),   0)                   AS total_zone_hours,
                    COALESCE(SUM(s.night_hours),  0)                   AS total_night_hours,
                    COALESCE(SUM(s.hazard_days),  0)                   AS total_hazard_days,
                    COALESCE(SUM(s.gross_salary), 0)                   AS total_gross,
                    COALESCE(SUM(s.net_salary),   0)                   AS total_net
                FROM pay_salary s
                JOIN personnel p ON s.emp_id = p.id
                LEFT JOIN zones z ON p.current_zone_id = z.id
                WHERE s.period_id = :pid
                  AND (s.zone_hours > 0 OR s.night_hours > 0 OR s.hazard_days > 0)
                GROUP BY COALESCE(z.name, p.current_location, 'Unassigned')
                ORDER BY total_gross DESC
            """), {'pid': period_id}).fetchall()

        columns = [
            {'field': 'zone_name',         'label': 'Zone',             'type': 'text'},
            {'field': 'employee_count',    'label': 'Employees',        'type': 'number'},
            {'field': 'total_zone_hours',  'label': 'Zone Hours',       'type': 'number'},
            {'field': 'total_night_hours', 'label': 'Night Hours',      'type': 'number'},
            {'field': 'total_hazard_days', 'label': 'Hazard Days',      'type': 'number'},
            {'field': 'total_gross',       'label': 'Total Gross',      'type': 'currency'},
            {'field': 'total_net',         'label': 'Total Net',        'type': 'currency'},
        ]
        data = [{
            'zone_name':         r.zone_name,
            'employee_count':    int(r.employee_count),
            'total_zone_hours':  float(r.total_zone_hours),
            'total_night_hours': float(r.total_night_hours),
            'total_hazard_days': float(r.total_hazard_days),
            'total_gross':       float(r.total_gross),
            'total_net':         float(r.total_net),
        } for r in salary_rows]

        allowance_config = [{
            'zone_name':       r.zone_name,
            'allowance_amount':float(r.allowance_amount),
            'is_hazard':       bool(r.is_hazard),
            'hazard_rate':     float(r.hazard_rate or 0),
            'effective_date':  str(r.effective_date) if r.effective_date else '',
            'end_date':        str(r.end_date) if r.end_date else '',
            'is_active':       bool(r.is_active),
        } for r in allowance_rows]

        chart_data = {
            'labels': [r['zone_name'] for r in data],
            'datasets': [
                {'label': 'Total Gross', 'data': [r['total_gross'] for r in data], 'backgroundColor': '#F79646'},
                {'label': 'Total Net',   'data': [r['total_net']   for r in data], 'backgroundColor': '#4F81BD'},
            ],
        }
        meta = self._period_meta(self.db, period_id) if period_id else {}
        return {
            'columns': columns, 'data': data, 'chart_data': chart_data,
            'total': len(data),
            'summary': {
                **meta,
                'total_zones':      len(data),
                'total_gross':      round(sum(r['total_gross'] for r in data), 2),
                'total_net':        round(sum(r['total_net']   for r in data), 2),
                'allowance_config': allowance_config,
                **(self._employee_roster_context(self.db) if not period_id else {}),
            },
        }

    # ==================== VISITOR REPORTS ====================
    
    # ── Visitor label maps ────────────────────────────────────────────────────
    _VIS_LOG_STATUS  = {0: 'On Site', 1: 'Checked Out', 2: 'Overstay'}
    _VIS_PREREG_STATUS = {
        0: 'Pending', 1: 'Approved', 2: 'Rejected',
        3: 'Checked In', 4: 'Checked Out', 5: 'Expired',
    }
    _VIS_ID_TYPE = {0: 'National ID', 1: 'Passport', 2: 'Driver\'s License'}
    _VIS_MUSTER_STATUS = {0: 'Missing', 1: 'Safe'}

    # ── Shared visitor base SQL (visit log + all enrichment joins) ────────────
    _VIS_BASE_SQL = """
        SELECT
            vl.id                                                    AS log_id,
            v.visitor_code,
            v.full_name                                              AS visitor_name,
            COALESCE(v.company, '')                                  AS company,
            COALESCE(vt.type_name, 'General')                       AS visitor_type,
            v.id_type,
            COALESCE(v.id_no, '')                                    AS id_no,
            v.phone,
            v.email,
            v.safety_induction_done,
            vl.check_in_time,
            vl.check_out_time,
            vl.status                                                AS log_status,
            vl.card_no,
            vl.badge_printed,
            vl.overstay_alert_sent,
            EXTRACT(EPOCH FROM (
                COALESCE(vl.check_out_time, now()) - vl.check_in_time
            ))/3600                                                  AS duration_hours,
            COALESCE(he.first_name || ' ' || TRIM(he.last_name), '') AS host_name,
            COALESCE(he.emp_code, '')                                AS host_emp_code,
            COALESCE(pa.area_name, '')                               AS area_name,
            COALESCE(pr.purpose, '')                                 AS visit_purpose,
            COALESCE(pr.vehicle_no, '')                              AS vehicle_no,
            pr.id IS NOT NULL                                        AS pre_registered,
            COALESCE(vt.default_visit_hours, 8)                     AS allowed_hours
        FROM vis_visit_log vl
        JOIN vis_visitor v          ON vl.visitor_id    = v.id
        LEFT JOIN vis_type vt       ON v.visitor_type_id = vt.id
        LEFT JOIN vis_pre_registration pr ON vl.pre_reg_id = pr.id
        LEFT JOIN personnel_employee he   ON vl.host_emp_id = he.id
        LEFT JOIN personnel_area pa       ON vl.area_id     = pa.id
    """

    def visitor_daily_log(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Daily visitor check-in/out log — enriched with visitor type, host, area, and pre-reg details."""
        date_filter = filters.get('date', _site_today().strftime('%Y-%m-%d'))

        rows = self.db.execute(text(self._VIS_BASE_SQL + """
            WHERE DATE(vl.check_in_time) = :dt
            ORDER BY vl.check_in_time
        """), {'dt': date_filter}).fetchall()

        columns = [
            {'field': 'visitor_code',    'label': 'Visitor Code',   'type': 'text'},
            {'field': 'visitor_name',    'label': 'Visitor Name',   'type': 'text'},
            {'field': 'company',         'label': 'Company',        'type': 'text'},
            {'field': 'visitor_type',    'label': 'Type',           'type': 'text'},
            {'field': 'host_name',       'label': 'Host',           'type': 'text'},
            {'field': 'area_name',       'label': 'Area',           'type': 'text'},
            {'field': 'check_in_time',   'label': 'Check In',       'type': 'datetime'},
            {'field': 'check_out_time',  'label': 'Check Out',      'type': 'datetime'},
            {'field': 'duration_hours',  'label': 'Hours on Site',  'type': 'number'},
            {'field': 'visit_purpose',   'label': 'Purpose',        'type': 'text'},
            {'field': 'status',          'label': 'Status',         'type': 'text'},
            {'field': 'badge_printed',   'label': 'Badge Printed',  'type': 'boolean'},
            {'field': 'pre_registered',  'label': 'Pre-Registered', 'type': 'boolean'},
            {'field': 'card_no',         'label': 'Card No',        'type': 'text'},
        ]
        data = [{
            'visitor_code':   r.visitor_code or '',
            'visitor_name':   r.visitor_name or '',
            'company':        r.company or '',
            'visitor_type':   r.visitor_type,
            'host_name':      r.host_name or '—',
            'area_name':      r.area_name or '—',
            'check_in_time':  r.check_in_time.strftime('%Y-%m-%d %H:%M') if r.check_in_time else '',
            'check_out_time': r.check_out_time.strftime('%Y-%m-%d %H:%M') if r.check_out_time else '—',
            'duration_hours': round(float(r.duration_hours or 0), 2),
            'visit_purpose':  r.visit_purpose or '—',
            'status':         self._VIS_LOG_STATUS.get(r.log_status, 'On Site'),
            'badge_printed':  bool(r.badge_printed),
            'pre_registered': bool(r.pre_registered),
            'card_no':        r.card_no or '—',
        } for r in rows]

        # Fallback context: show today's pre-registrations and all registered visitors
        prereg_today = self.db.execute(text("""
            SELECT v.full_name, v.company, pr.purpose, pr.visit_date,
                   pr.visit_time_start, pr.visit_time_end, pr.status AS prereg_status,
                   COALESCE(he.first_name || ' ' || TRIM(he.last_name), '') AS host_name
            FROM vis_pre_registration pr
            LEFT JOIN vis_visitor v ON pr.visitor_id = v.id
            LEFT JOIN personnel_employee he ON pr.host_emp_id = he.id
            WHERE pr.visit_date = :dt
            ORDER BY pr.visit_time_start
        """), {'dt': date_filter}).fetchall()

        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                'date':               date_filter,
                'total_visitors':     len(data),
                'on_site':            sum(1 for r in rows if (r.log_status or 0) == 0),
                'checked_out':        sum(1 for r in rows if (r.log_status or 0) == 1),
                'overstay':           sum(1 for r in rows if (r.log_status or 0) == 2),
                'pre_registrations':  len(prereg_today),
                'prereg_details':     [{
                    'visitor_name': r.full_name or '',
                    'company':      r.company or '',
                    'host_name':    r.host_name or '',
                    'purpose':      r.purpose or '',
                    'time_slot':    f"{r.visit_time_start or ''}–{r.visit_time_end or ''}",
                    'status':       self._VIS_PREREG_STATUS.get(r.prereg_status, 'Pending'),
                } for r in prereg_today],
            },
        }

    def visitor_overstay_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Visitors who exceeded their allowed site duration — uses per-type allowed hours."""
        params: Dict[str, Any] = {}
        date_from_clause = date_to_clause = ""
        if filters.get('date_from'):
            date_from_clause = "AND DATE(vl.check_in_time) >= :date_from"
            params['date_from'] = filters['date_from']
        if filters.get('date_to'):
            date_to_clause = "AND DATE(vl.check_in_time) <= :date_to"
            params['date_to'] = filters['date_to']

        rows = self.db.execute(text(f"""
            SELECT * FROM ({self._VIS_BASE_SQL}) base
            WHERE (
                log_status = 2
                OR duration_hours > allowed_hours
            )
            {date_from_clause}
            {date_to_clause}
            ORDER BY duration_hours DESC
        """), params).fetchall()

        columns = [
            {'field': 'visitor_code',    'label': 'Visitor Code',    'type': 'text'},
            {'field': 'visitor_name',    'label': 'Visitor Name',    'type': 'text'},
            {'field': 'company',         'label': 'Company',         'type': 'text'},
            {'field': 'visitor_type',    'label': 'Type',            'type': 'text'},
            {'field': 'host_name',       'label': 'Host',            'type': 'text'},
            {'field': 'area_name',       'label': 'Area',            'type': 'text'},
            {'field': 'check_in_time',   'label': 'Check In',        'type': 'datetime'},
            {'field': 'hours_on_site',   'label': 'Hours on Site',   'type': 'number'},
            {'field': 'allowed_hours',   'label': 'Allowed Hours',   'type': 'number'},
            {'field': 'overstay_hours',  'label': 'Overstay Hours',  'type': 'number'},
            {'field': 'alert_sent',      'label': 'Alert Sent',      'type': 'boolean'},
            {'field': 'status',          'label': 'Status',          'type': 'text'},
        ]
        data = []
        for r in rows:
            dur   = round(float(r.duration_hours or 0), 2)
            allowed = float(r.allowed_hours or 8)
            data.append({
                'visitor_code':   r.visitor_code or '',
                'visitor_name':   r.visitor_name or '',
                'company':        r.company or '',
                'visitor_type':   r.visitor_type,
                'host_name':      r.host_name or '—',
                'area_name':      r.area_name or '—',
                'check_in_time':  r.check_in_time.strftime('%Y-%m-%d %H:%M') if r.check_in_time else '',
                'hours_on_site':  dur,
                'allowed_hours':  allowed,
                'overstay_hours': round(max(dur - allowed, 0), 2),
                'alert_sent':     bool(r.overstay_alert_sent),
                'status':         self._VIS_LOG_STATUS.get(r.log_status, 'On Site'),
            })

        overstay_ranges: Dict[str, int] = {'0–2 h': 0, '2–4 h': 0, '4–8 h': 0, '8 h+': 0}
        for r in data:
            h = r['overstay_hours']
            if h <= 2:   overstay_ranges['0–2 h'] += 1
            elif h <= 4: overstay_ranges['2–4 h'] += 1
            elif h <= 8: overstay_ranges['4–8 h'] += 1
            else:        overstay_ranges['8 h+']  += 1
        chart_data = {
            'labels': list(overstay_ranges.keys()),
            'datasets': [{'label': 'Overstay Count',
                          'data': list(overstay_ranges.values()),
                          'backgroundColor': '#C0504D'}],
        }
        avg = round(sum(r['overstay_hours'] for r in data) / len(data), 2) if data else 0
        return {
            'columns': columns, 'data': data, 'chart_data': chart_data,
            'total': len(data),
            'summary': {
                'total_overstays':     len(data),
                'avg_overstay_hours':  avg,
                'alerts_sent':         sum(1 for r in data if r['alert_sent']),
                'alerts_pending':      sum(1 for r in data if not r['alert_sent']),
                'overstay_ranges':     overstay_ranges,
            },
        }
    
    # ==================== MTD REPORTS (POB EXTENSION) ====================
    
    def mtd_compliance_matrix(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """MTD compliance matrix - POB HSE compliance grid"""
        # Get all employees and their certifications
        personnel_query = self.db.query(Personnel).filter(Personnel.is_active == True)
        
        if filters.get('department'):
            personnel_query = personnel_query.filter(Personnel.department == filters['department'])
        
        personnel = personnel_query.all()
        
        # Certificate types by NAME (mtd_cert_type); certificates keyed to the reader
        # mirror (personnel_employee) by emp_code. The old code used MTDCertification
        # .cert_type / .personnel_id, which do not exist (the report always crashed),
        # and ran one query per employee.
        cert_type_list = [r[0] for r in self.db.execute(text(
            "SELECT cert_name FROM mtd_cert_type ORDER BY cert_name")).fetchall()]
        latest: Dict[tuple, Any] = {}
        for r in self.db.execute(text("""
            SELECT pe.emp_code, ct.cert_name, MAX(c.expiry_date) AS expiry_date
            FROM mtd_certification c
            JOIN mtd_cert_type ct ON ct.id = c.cert_type_id
            JOIN personnel_employee pe ON pe.id = c.emp_id
            WHERE c.person_type = 0
            GROUP BY pe.emp_code, ct.cert_name
        """)).fetchall():
            latest[(r.emp_code, r.cert_name)] = r.expiry_date

        # Build compliance matrix
        data = []
        for person in personnel:
            cert_status = {}
            for cert_type in cert_type_list:
                expiry = latest.get((person.emp_code, cert_type))
                if expiry:
                    days_to_expiry = (expiry - _site_today()).days
                    if days_to_expiry < 0:
                        cert_status[cert_type] = 'Expired'
                    elif days_to_expiry <= 30:
                        cert_status[cert_type] = 'Expiring'
                    else:
                        cert_status[cert_type] = 'Valid'
                else:
                    cert_status[cert_type] = 'N/A'
            
            row = {
                'badge_id': person.badge_id or '',
                'full_name': person.full_name or '',
                'department': person.department or '',
            }
            row.update(cert_status)
            data.append(row)
        
        # Dynamic columns based on certification types
        columns = [
            {'field': 'badge_id', 'label': 'Badge ID', 'type': 'text'},
            {'field': 'full_name', 'label': 'Full Name', 'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
        ]
        
        for cert_type in cert_type_list:
            columns.append({'field': cert_type, 'label': cert_type, 'type': 'status'})
        
        # Summary statistics
        total_cells = len(data) * len(cert_type_list)
        valid_count = sum(1 for row in data for cert in cert_type_list if row.get(cert) == 'Valid')
        expiring_count = sum(1 for row in data for cert in cert_type_list if row.get(cert) == 'Expiring')
        expired_count = sum(1 for row in data for cert in cert_type_list if row.get(cert) == 'Expired')
        
        return {
            'columns': columns,
            'data': data,
            'summary': {
                'total_employees': len(data),
                'total_certifications': total_cells,
                'valid_count': valid_count,
                'expiring_count': expiring_count,
                'expired_count': expired_count,
                'compliance_rate': (valid_count / total_cells * 100) if total_cells > 0 else 0
            }
        }
    
    # ==================== SYSTEM REPORTS ====================
    
    def system_operation_log(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """System operation log"""
        query = self.db.query(BaseOperationLog).join(AuthUser)
        
        if filters.get('date_from'):
            query = query.filter(BaseOperationLog.created_at >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(BaseOperationLog.created_at < _day_after(filters['date_to']))
        if filters.get('module'):
            query = query.filter(BaseOperationLog.table_name == filters['module'])

        query = query.order_by(desc(BaseOperationLog.created_at))
        logs, total = self._paginate(query)

        columns = [
            {'field': 'timestamp', 'label': 'Time', 'type': 'datetime'},
            {'field': 'user', 'label': 'User', 'type': 'text'},
            {'field': 'ip_address', 'label': 'IP Address', 'type': 'text'},
            {'field': 'module', 'label': 'Module', 'type': 'text'},
            {'field': 'action', 'label': 'Action', 'type': 'text'},
            {'field': 'target', 'label': 'Target', 'type': 'text'},
        ]

        data = []
        for log in logs:
            data.append({
                'timestamp': log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
                'user': log.user.username if log.user else '',
                'ip_address': log.ip_address or '',
                'module': log.table_name or '',
                'action': log.action or '',
                'target': f"{log.table_name}#{log.record_id}" if log.record_id else log.table_name or '',
            })

        return {
            'columns': columns,
            'data': data,
            'total': total,
            'summary': {
                'total_operations': total,
            }
        }
    
    # ==================== PERSONNEL (continued) ====================

    def personnel_anniversary_list(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Work anniversary listing"""
        month_filter = filters.get('month')
        query = self.db.query(Personnel).filter(Personnel.hire_date.isnot(None))
        if month_filter:
            query = query.filter(extract('month', Personnel.hire_date) == month_filter)
        if filters.get('department'):
            query = query.filter(Personnel.department == filters['department'])
        query = query.order_by(Personnel.full_name)
        personnel, total = self._paginate(query)

        columns = [
            {'field': 'badge_id',      'label': 'Badge ID',      'type': 'text'},
            {'field': 'full_name',     'label': 'Full Name',     'type': 'text'},
            {'field': 'department',    'label': 'Department',    'type': 'text'},
            {'field': 'hire_date',     'label': 'Hire Date',     'type': 'date'},
            {'field': 'years_service', 'label': 'Years Service', 'type': 'number'},
        ]
        today = _site_today()
        data = []
        for p in personnel:
            if p.hire_date:
                yrs = today.year - p.hire_date.year - (
                    (today.month, today.day) < (p.hire_date.month, p.hire_date.day)
                )
                data.append({
                    'badge_id':      p.badge_id or '',
                    'full_name':     p.full_name or '',
                    'department':    p.department or '',
                    'hire_date':     p.hire_date.strftime('%Y-%m-%d'),
                    'years_service': yrs,
                })
        return {'columns': columns, 'data': data, 'total': total, 'summary': {'total': total}}

    def personnel_contractor_list(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Contractor personnel listing"""
        query = self.db.query(Personnel).filter(
            Personnel.personnel_type.ilike('%contractor%')
        )
        if filters.get('department'):
            query = query.filter(Personnel.department == filters['department'])
        if filters.get('search'):
            query = query.filter(Personnel.full_name.ilike(f"%{filters['search']}%"))
        query = query.order_by(Personnel.full_name)
        personnel, total = self._paginate(query)

        columns = [
            {'field': 'badge_id',        'label': 'Badge ID',    'type': 'text'},
            {'field': 'full_name',       'label': 'Full Name',   'type': 'text'},
            {'field': 'department',      'label': 'Department',  'type': 'text'},
            {'field': 'position',        'label': 'Position',    'type': 'text'},
            {'field': 'personnel_type',  'label': 'Type',        'type': 'text'},
            {'field': 'hire_date',       'label': 'Start Date',  'type': 'date'},
            {'field': 'is_active',       'label': 'Active',      'type': 'boolean'},
        ]
        data = [{
            'badge_id':       p.badge_id or '',
            'full_name':      p.full_name or '',
            'department':     p.department or '',
            'position':       p.position or '',
            'personnel_type': p.personnel_type or '',
            'hire_date':      p.hire_date.strftime('%Y-%m-%d') if p.hire_date else '',
            'is_active':      p.is_active or False,
        } for p in personnel]
        return {'columns': columns, 'data': data, 'total': total, 'summary': {'total_contractors': total}}

    # ==================== ATTENDANCE (continued) ====================

    def attendance_summary_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Overall attendance statistics for a date range from att_report"""
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        sql = text("""
            SELECT e.emp_code,
                   (e.first_name || ' ' || e.last_name) AS full_name,
                   COALESCE(d.dept_name, '') AS department,
                   COUNT(*) FILTER (WHERE r.att_status IN (0,1,2)) AS present_days,
                   COUNT(*) FILTER (WHERE r.att_status = 3)        AS absent_days,
                   COUNT(*) FILTER (WHERE r.att_status = 4)        AS leave_days,
                   ROUND(SUM(r.work_minutes)::numeric / 60, 2)     AS total_work_hours,
                   SUM(r.late_minutes)                             AS total_late_minutes,
                   SUM(r.ot_minutes)                               AS total_ot_minutes
            FROM att_report r
            JOIN personnel_employee e ON r.emp_id = e.id
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            WHERE r.att_date BETWEEN :date_from AND :date_to
            GROUP BY e.id, e.emp_code, e.first_name, e.last_name, d.dept_name
            ORDER BY d.dept_name, full_name
        """)
        rows = self.db.execute(sql, {'date_from': date_from, 'date_to': date_to}).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        columns = [
            {'field': 'emp_code',           'label': 'Emp Code',     'type': 'text'},
            {'field': 'full_name',          'label': 'Full Name',    'type': 'text'},
            {'field': 'department',         'label': 'Department',   'type': 'text'},
            {'field': 'present_days',       'label': 'Present Days', 'type': 'number'},
            {'field': 'absent_days',        'label': 'Absent Days',  'type': 'number'},
            {'field': 'leave_days',         'label': 'Leave Days',   'type': 'number'},
            {'field': 'total_work_hours',   'label': 'Work Hours',   'type': 'number'},
            {'field': 'total_late_minutes', 'label': 'Late Min',     'type': 'number'},
            {'field': 'total_ot_minutes',   'label': 'OT Min',       'type': 'number'},
        ]
        data = [dict(r._mapping) for r in rows]
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                'total_employees': len(data),
                'total_present_days': sum(int(r.get('present_days') or 0) for r in data),
                'date_from': date_from, 'date_to': date_to,
            },
        }

    def attendance_early_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Early departure from att_report — employees with early_minutes > 0"""
        date_filter = filters.get('date', (_site_today() - timedelta(days=1)).strftime('%Y-%m-%d'))  # = the picker's default

        sql = text("""
            SELECT e.emp_code,
                   (e.first_name || ' ' || e.last_name) AS full_name,
                   COALESCE(d.dept_name, '') AS department,
                   r.check_out, r.early_minutes
            FROM att_report r
            JOIN personnel_employee e ON r.emp_id = e.id
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            WHERE r.att_date = :att_date AND r.early_minutes > 0
            ORDER BY r.early_minutes DESC
        """)
        rows = self.db.execute(sql, {'att_date': date_filter}).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        columns = [
            {'field': 'emp_code',      'label': 'Emp Code',    'type': 'text'},
            {'field': 'full_name',     'label': 'Full Name',   'type': 'text'},
            {'field': 'department',    'label': 'Department',  'type': 'text'},
            {'field': 'check_out',     'label': 'Check Out',   'type': 'datetime'},
            {'field': 'early_minutes', 'label': 'Early (min)', 'type': 'number'},
        ]
        data = []
        for r in rows:
            m = r._mapping
            co = m['check_out']
            data.append({
                'emp_code':      m['emp_code'],
                'full_name':     m['full_name'],
                'department':    m['department'],
                'check_out':     co.strftime('%Y-%m-%d %H:%M') if co else '',
                'early_minutes': m['early_minutes'] or 0,
            })
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {'total_early': len(data), 'date': date_filter},
        }

    def attendance_absent_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Employees scheduled to work on the date who did not attend (att_status=3).
        Previously anyone WITHOUT an attendance row counted too — but rows exist only for
        scheduled days, so every off-rotation / rest-day employee (and every leaver)
        was listed as absent."""
        date_filter = filters.get('date', (_site_today() - timedelta(days=1)).strftime('%Y-%m-%d'))  # = the picker's default

        sql = text("""
            SELECT e.emp_code,
                   (e.first_name || ' ' || e.last_name) AS full_name,
                   COALESCE(d.dept_name, '') AS department,
                   COALESCE(r.att_status, -1) AS att_status
            FROM att_report r
            JOIN personnel_employee e ON e.id = r.emp_id
            JOIN personnel p ON p.emp_code = e.emp_code
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            WHERE r.att_date = :att_date
              AND r.att_status = 3                       -- scheduled to work, no attendance
              AND p.is_active = TRUE                     -- still employed
              AND COALESCE(p.on_leave, FALSE) = FALSE
            ORDER BY d.dept_name, full_name
        """)
        rows = self.db.execute(sql, {'att_date': date_filter}).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        columns = [
            {'field': 'emp_code',   'label': 'Emp Code',   'type': 'text'},
            {'field': 'full_name',  'label': 'Full Name',  'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
            {'field': 'reason',     'label': 'Reason',     'type': 'text'},
        ]
        data = [{
            'emp_code':   r._mapping['emp_code'],
            'full_name':  r._mapping['full_name'],
            'department': r._mapping['department'],
            'reason':     'Scheduled, no attendance',
        } for r in rows]
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {'total_absent': len(data), 'date': date_filter},
        }

    def attendance_overtime_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Overtime report from att_report — employees with ot_minutes > 0"""
        date_filter = filters.get('date', (_site_today() - timedelta(days=1)).strftime('%Y-%m-%d'))  # = the picker's default

        sql = text("""
            SELECT e.emp_code,
                   (e.first_name || ' ' || e.last_name) AS full_name,
                   COALESCE(d.dept_name, '') AS department,
                   r.check_in, r.check_out,
                   r.work_minutes,
                   GREATEST(r.ot_minutes, r.overtime_minutes, 0) AS ot_minutes
            FROM att_report r
            JOIN personnel_employee e ON r.emp_id = e.id
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            WHERE r.att_date = :att_date
              AND GREATEST(r.ot_minutes, r.overtime_minutes, 0) > 0
            ORDER BY ot_minutes DESC
        """)
        rows = self.db.execute(sql, {'att_date': date_filter}).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        columns = [
            {'field': 'emp_code',   'label': 'Emp Code',   'type': 'text'},
            {'field': 'full_name',  'label': 'Full Name',  'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
            {'field': 'check_in',   'label': 'Check In',   'type': 'datetime'},
            {'field': 'check_out',  'label': 'Check Out',  'type': 'datetime'},
            {'field': 'work_hours', 'label': 'Work Hours', 'type': 'number'},
            {'field': 'ot_hours',   'label': 'OT Hours',   'type': 'number'},
        ]
        data = []
        for r in rows:
            m = r._mapping
            ci, co = m['check_in'], m['check_out']
            data.append({
                'emp_code':   m['emp_code'],
                'full_name':  m['full_name'],
                'department': m['department'],
                'check_in':   ci.strftime('%Y-%m-%d %H:%M') if ci else '',
                'check_out':  co.strftime('%Y-%m-%d %H:%M') if co else '',
                'work_hours': round((m['work_minutes'] or 0) / 60, 2),
                'ot_hours':   round((m['ot_minutes'] or 0) / 60, 2),
            })
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                'total_with_ot': len(data),
                'total_ot_hours': round(sum(r['ot_hours'] for r in data), 2),
                'date': date_filter,
            },
        }

    def attendance_leave_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Leave records from att_leave table"""
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        sql = text("""
            SELECT e.emp_code,
                   (e.first_name || ' ' || e.last_name) AS full_name,
                   COALESCE(d.dept_name, '') AS department,
                   l.start_time::date AS start_date,
                   l.end_time::date   AS end_date,
                   lt.leave_name      AS leave_type,
                   l.reason,
                   CASE l.approval_status
                       WHEN 0 THEN 'Pending'
                       WHEN 1 THEN 'Approved'
                       WHEN 2 THEN 'Rejected'
                       ELSE 'Unknown'
                   END AS approval_status
            FROM att_leave l
            JOIN personnel_employee e ON l.emp_id = e.id
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            LEFT JOIN att_leave_type lt ON l.leave_type_id = lt.id
            WHERE l.start_time::date <= :date_to
              AND l.end_time::date   >= :date_from
            ORDER BY l.start_time DESC
        """)
        rows = self.db.execute(sql, {'date_from': date_from, 'date_to': date_to}).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        columns = [
            {'field': 'emp_code',         'label': 'Emp Code',    'type': 'text'},
            {'field': 'full_name',         'label': 'Full Name',   'type': 'text'},
            {'field': 'department',        'label': 'Department',  'type': 'text'},
            {'field': 'start_date',        'label': 'Start Date',  'type': 'date'},
            {'field': 'end_date',          'label': 'End Date',    'type': 'date'},
            {'field': 'leave_type',        'label': 'Leave Type',  'type': 'text'},
            {'field': 'approval_status',   'label': 'Status',      'type': 'text'},
        ]
        data = []
        for r in rows:
            m = r._mapping
            data.append({
                'emp_code':       m['emp_code'],
                'full_name':      m['full_name'],
                'department':     m['department'],
                'start_date':     str(m['start_date']) if m['start_date'] else '',
                'end_date':       str(m['end_date']) if m['end_date'] else '',
                'leave_type':     m['leave_type'] or 'Leave',
                'approval_status': m['approval_status'],
            })
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {'total_leave_records': len(data), 'date_from': date_from, 'date_to': date_to},
        }

    def attendance_shift_schedule(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Shift schedule overview"""
        total = 0
        try:
            from ..models.shift_management import ScheduleManagement
            query = self.db.query(ScheduleManagement)
            if filters.get('date_from'):
                query = query.filter(ScheduleManagement.start_date >= filters['date_from'])
            if filters.get('date_to'):
                query = query.filter(ScheduleManagement.end_date <= filters['date_to'])
            schedules, total = self._paginate(query)
        except Exception:
            schedules = []

        columns = [
            {'field': 'emp_id',      'label': 'Employee ID',  'type': 'text'},
            {'field': 'shift_name',  'label': 'Shift',        'type': 'text'},
            {'field': 'start_date',  'label': 'Start Date',   'type': 'date'},
            {'field': 'end_date',    'label': 'End Date',     'type': 'date'},
        ]
        data = [{
            'emp_id':     getattr(s, 'emp_id', '') or '',
            'shift_name': getattr(s, 'shift_name', '') or '',
            'start_date': s.start_date.strftime('%Y-%m-%d') if getattr(s, 'start_date', None) else '',
            'end_date':   s.end_date.strftime('%Y-%m-%d') if getattr(s, 'end_date', None) else '',
        } for s in schedules]
        return {'columns': columns, 'data': data, 'total': total, 'summary': {'total_schedules': total}}

    def attendance_exceptions(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Attendance exceptions from att_exception table"""
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        sql = text("""
            SELECT e.emp_code,
                   (e.first_name || ' ' || e.last_name) AS full_name,
                   COALESCE(d.dept_name, '') AS department,
                   ex.att_date, ex.exception_type, ex.deviation_minutes,
                   ex.exception_note,
                   CASE ex.handle_action
                       WHEN 'approved' THEN 'Approved'
                       WHEN 'rejected' THEN 'Rejected'
                       ELSE 'Pending'
                   END AS handle_status
            FROM att_exception ex
            JOIN personnel_employee e ON ex.emp_id = e.id
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON e.dept_id = d.id
            WHERE ex.att_date BETWEEN :date_from AND :date_to
            ORDER BY ex.att_date DESC, d.dept_name
        """)
        rows = self.db.execute(sql, {'date_from': date_from, 'date_to': date_to}).fetchall()

        if filters.get('department'):
            dept = filters['department'].lower()
            rows = [r for r in rows if dept in (r._mapping['department'] or '').lower()]

        columns = [
            {'field': 'emp_code',          'label': 'Emp Code',      'type': 'text'},
            {'field': 'full_name',         'label': 'Full Name',     'type': 'text'},
            {'field': 'department',        'label': 'Department',    'type': 'text'},
            {'field': 'att_date',          'label': 'Date',          'type': 'date'},
            {'field': 'exception_type',    'label': 'Exception',     'type': 'text'},
            {'field': 'deviation_minutes', 'label': 'Deviation (min)','type': 'number'},
            {'field': 'handle_status',     'label': 'Status',        'type': 'text'},
        ]
        data = []
        for r in rows:
            m = r._mapping
            data.append({
                'emp_code':          m['emp_code'],
                'full_name':         m['full_name'],
                'department':        m['department'],
                'att_date':          str(m['att_date']) if m['att_date'] else '',
                'exception_type':    m['exception_type'] or '',
                'deviation_minutes': m['deviation_minutes'] or 0,
                'handle_status':     m['handle_status'],
            })
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {'total_exceptions': len(data), 'date_from': date_from, 'date_to': date_to},
        }

    # ==================== ACCESS CONTROL ====================

    # ── ZKTeco event type labels ─────────────────────────────────────────────
    _AC_EVENT_TYPE = {
        0: 'Normal Access',    1: 'Fingerprint Access', 2: 'Card Access',
        3: 'Password Access',  4: 'Face Access',        5: 'Emergency Unlock',
        6: 'Emergency Lock',   7: 'Door Alarm',         8: 'Duress',
        9: 'Anti-Passback',   10: 'Interlock',
    }
    _AC_VERIFY   = {0: 'Password', 1: 'Fingerprint', 2: 'Face', 3: 'Card'}
    _AC_INOUT    = {0: 'In', 1: 'Out'}

    def access_control_events(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Complete door-access event log.

        Unions two authoritative sources so no event is missed:
          • acc_event  — dedicated access-control event table (emergency, door alarms,
                         and normal card swipes written by the ADMS handler).
          • iclock_transaction filtered to ACCESS_ENTRY / ACCESS_EXIT terminals —
                         back-fill for any punches that arrived before the acc_event
                         write was in place.
        Deduplication: iclock_transaction rows are excluded when acc_event already
        holds a matching (emp_code, terminal_sn, same-minute) record.
        """
        default_from = (_site_today() - timedelta(days=6)).strftime('%Y-%m-%d')
        default_to   = _site_today().strftime('%Y-%m-%d')
        date_from    = filters.get('date_from', default_from)
        date_to      = filters.get('date_to',   default_to)
        emp_filter   = filters.get('emp_code', '')
        term_filter  = filters.get('terminal_sn', '')

        params: Dict[str, Any] = {'date_from': date_from, 'date_to': date_to}
        emp_clause  = "AND ae.emp_code = :emp_code"  if emp_filter  else ""
        term_clause = "AND ae.terminal_sn = :term"   if term_filter else ""
        if emp_filter:  params['emp_code'] = emp_filter
        if term_filter: params['term']     = term_filter

        rows = self.db.execute(text(f"""
            -- Source 1: acc_event (every door/security event)
            SELECT
                ae.event_time,
                ae.emp_code,
                COALESCE(NULLIF(ae.emp_name,''), pe.first_name || ' ' || pe.last_name, ae.emp_code) AS full_name,
                COALESCE(dept.dept_name, '')  AS department,
                ae.terminal_sn,
                COALESCE(t.alias, ae.terminal_sn) AS terminal_name,
                COALESCE(d.name, '')          AS door_name,
                ae.event_type,
                COALESCE(ae.description, '')  AS event_description,
                ae.in_out,
                ae.verify_type,
                'acc_event'                   AS source
            FROM acc_event ae
            LEFT JOIN personnel_employee pe   ON ae.emp_code   = pe.emp_code
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) dept ON pe.dept_id  = dept.id
            LEFT JOIN iclock_terminal t       ON ae.terminal_sn = t.sn
            LEFT JOIN acc_door d              ON ae.door_id    = d.id
            WHERE ae.event_time::date BETWEEN :date_from AND :date_to
              {emp_clause.replace('ae.emp_code','ae.emp_code')}
              {term_clause.replace('ae.terminal_sn','ae.terminal_sn')}

            UNION ALL

            -- Source 2: iclock_transaction from access readers (back-fill gap)
            SELECT
                tx.punch_time                 AS event_time,
                tx.emp_code,
                COALESCE(pe.first_name || ' ' || pe.last_name, tx.emp_code) AS full_name,
                COALESCE(dept.dept_name, '')  AS department,
                tx.terminal_sn,
                COALESCE(t.alias, tx.terminal_sn) AS terminal_name,
                COALESCE(d.name, '')          AS door_name,
                0                             AS event_type,
                CASE t.reader_purpose
                    WHEN 'ACCESS_ENTRY' THEN 'Facility Entry'
                    WHEN 'ACCESS_EXIT'  THEN 'Facility Exit'
                    ELSE 'Badge Swipe'
                END                           AS event_description,
                CASE t.reader_purpose WHEN 'ACCESS_ENTRY' THEN 0 ELSE 1 END AS in_out,
                tx.verify_type,
                'transaction'                 AS source
            FROM iclock_transaction tx
            JOIN  iclock_terminal t  ON tx.terminal_sn = t.sn
                                    AND t.reader_purpose IN ('ACCESS_ENTRY','ACCESS_EXIT')
            LEFT JOIN personnel_employee pe   ON tx.emp_code    = pe.emp_code
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) dept ON pe.dept_id   = dept.id
            LEFT JOIN acc_door d ON d.terminal_sn = tx.terminal_sn
                AND d.id = (
                    SELECT CASE t.reader_purpose
                        WHEN 'ACCESS_ENTRY' THEN MIN(ad.id) ELSE MAX(ad.id) END
                    FROM acc_door ad WHERE ad.terminal_sn = tx.terminal_sn
                )
            WHERE tx.punch_time::date BETWEEN :date_from AND :date_to
              AND NOT EXISTS (
                  SELECT 1 FROM acc_event ae2
                  WHERE ae2.emp_code    = tx.emp_code
                    AND ae2.terminal_sn = tx.terminal_sn
                    AND DATE_TRUNC('minute', ae2.event_time) = DATE_TRUNC('minute', tx.punch_time)
              )
              {'AND tx.emp_code = :emp_code'  if emp_filter  else ''}
              {'AND tx.terminal_sn = :term'   if term_filter else ''}

            ORDER BY event_time DESC
        """), params).fetchall()

        columns = [
            {'field': 'event_time',        'label': 'Date & Time',   'type': 'datetime'},
            {'field': 'emp_code',           'label': 'Badge ID',      'type': 'text'},
            {'field': 'full_name',          'label': 'Name',          'type': 'text'},
            {'field': 'department',         'label': 'Department',    'type': 'text'},
            {'field': 'door_name',          'label': 'Door',          'type': 'text'},
            {'field': 'terminal_name',      'label': 'Terminal',      'type': 'text'},
            {'field': 'event_description',  'label': 'Event',         'type': 'text'},
            {'field': 'direction',          'label': 'Direction',     'type': 'text'},
            {'field': 'verify_method',      'label': 'Verify Method', 'type': 'text'},
            {'field': 'source',             'label': 'Source',        'type': 'text'},
        ]
        data = [{
            'event_time':       r.event_time.strftime('%Y-%m-%d %H:%M:%S') if r.event_time else '',
            'emp_code':         r.emp_code or '',
            'full_name':        r.full_name or '',
            'department':       r.department or '',
            'door_name':        r.door_name or '—',
            'terminal_name':    r.terminal_name or '',
            'event_description':self._AC_EVENT_TYPE.get(r.event_type, r.event_description or ''),
            'direction':        self._AC_INOUT.get(r.in_out, 'N/A') if r.in_out is not None else 'N/A',
            'verify_method':    self._AC_VERIFY.get(r.verify_type, 'N/A') if r.verify_type is not None else 'N/A',
            'source':           r.source or '',
        } for r in rows]

        access_count = sum(1 for r in data if r['event_description'] not in ('Emergency Unlock','Emergency Lock'))
        emergency_count = len(data) - access_count
        return {
            'columns': columns, 'data': data,
            'total': len(data),
            'summary': {
                'total_events':    len(data),
                'access_events':   access_count,
                'emergency_events':emergency_count,
                'date_from':       date_from,
                'date_to':         date_to,
            },
        }

    def access_control_door_status(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Door configuration and status — one row per configured door."""
        rows = self.db.execute(text("""
            SELECT
                d.id                                          AS door_id,
                d.name                                        AS door_name,
                d.terminal_sn,
                COALESCE(t.alias, 'Terminal ' || d.terminal_sn) AS terminal_alias,
                t.ip_address,
                t.reader_purpose,
                t.last_activity,
                CASE
                    WHEN t.last_activity > NOW() - INTERVAL '2 hours'  THEN 'Online'
                    WHEN t.last_activity > NOW() - INTERVAL '24 hours' THEN 'Warning'
                    WHEN t.last_activity IS NULL                        THEN 'Never Connected'
                    ELSE 'Offline'
                END                                           AS terminal_status,
                d.anti_passback,
                d.first_card_open,
                d.relay_time,
                d.open_duration,
                d.mustering_mode,
                COALESCE(ev.event_count, 0)                  AS total_events,
                ev.last_event_time,
                COALESCE(ev.unique_users, 0)                 AS unique_users
            FROM acc_door d
            LEFT JOIN iclock_terminal t ON t.sn = d.terminal_sn
            LEFT JOIN (
                SELECT door_id,
                       COUNT(*)                AS event_count,
                       MAX(event_time)         AS last_event_time,
                       COUNT(DISTINCT emp_code) FILTER (WHERE emp_code IS NOT NULL) AS unique_users
                FROM acc_event
                GROUP BY door_id
            ) ev ON ev.door_id = d.id
            ORDER BY d.id
        """)).fetchall()

        purpose_labels = {
            'ACCESS_ENTRY': 'Access Entry', 'ACCESS_EXIT': 'Access Exit',
            'ATTENDANCE': 'Attendance', 'MUSTERING': 'Mustering',
        }
        columns = [
            {'field': 'door_name',      'label': 'Door Name',       'type': 'text'},
            {'field': 'terminal_sn',    'label': 'Terminal SN',     'type': 'text'},
            {'field': 'terminal_alias', 'label': 'Terminal',        'type': 'text'},
            {'field': 'ip_address',     'label': 'IP Address',      'type': 'text'},
            {'field': 'reader_purpose', 'label': 'Purpose',         'type': 'text'},
            {'field': 'terminal_status','label': 'Status',          'type': 'text'},
            {'field': 'last_contact',   'label': 'Last Contact',    'type': 'datetime'},
            {'field': 'total_events',   'label': 'Total Events',    'type': 'number'},
            {'field': 'unique_users',   'label': 'Unique Users',    'type': 'number'},
            {'field': 'last_event',     'label': 'Last Event',      'type': 'datetime'},
            {'field': 'anti_passback',  'label': 'Anti-Passback',   'type': 'text'},
            {'field': 'relay_time',     'label': 'Relay Time (s)',  'type': 'number'},
            {'field': 'open_duration',  'label': 'Open Duration (s)','type': 'number'},
            {'field': 'mustering_mode', 'label': 'Mustering Mode',  'type': 'text'},
        ]
        apb_map = {0: 'Off', 1: 'In Only', 2: 'Out Only', 3: 'In/Out'}
        data = [{
            'door_name':       r.door_name or '',
            'terminal_sn':     r.terminal_sn or '',
            'terminal_alias':  r.terminal_alias or '',
            'ip_address':      r.ip_address or '',
            'reader_purpose':  purpose_labels.get(r.reader_purpose, r.reader_purpose or 'N/A'),
            'terminal_status': r.terminal_status or 'Unknown',
            'last_contact':    r.last_activity.strftime('%Y-%m-%d %H:%M') if r.last_activity else 'Never',
            'total_events':    r.total_events or 0,
            'unique_users':    r.unique_users or 0,
            'last_event':      r.last_event_time.strftime('%Y-%m-%d %H:%M') if r.last_event_time else 'Never',
            'anti_passback':   apb_map.get(r.anti_passback, str(r.anti_passback)),
            'relay_time':      r.relay_time or 0,
            'open_duration':   r.open_duration or 0,
            'mustering_mode':  'Yes' if r.mustering_mode else 'No',
        } for r in rows]

        online = sum(1 for r in data if r['terminal_status'] == 'Online')
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total_doors':    len(data),
                'online':         online,
                'offline':        len(data) - online,
                'total_events':   sum(r['total_events'] for r in data),
            },
        }

    def access_control_anti_passback(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Anti-passback violations from acc_antipassback table"""
        rows = self.db.execute(text("""
            SELECT
                a.emp_code,
                COALESCE(e.first_name || ' ' || e.last_name, a.emp_code) AS full_name,
                COALESCE(d.name, 'Door #' || a.door_id::text) AS door_name,
                a.last_event_time,
                a.last_event_type,
                a.last_terminal_sn
            FROM acc_antipassback a
            LEFT JOIN personnel_employee e ON a.emp_code = e.emp_code
            LEFT JOIN acc_door d ON a.door_id = d.id
            ORDER BY a.last_event_time DESC
        """)).fetchall()

        event_type_map = {1: 'APB In Violation', 2: 'APB Out Violation', 0: 'Normal'}
        columns = [
            {'field': 'emp_code',         'label': 'Badge ID',    'type': 'text'},
            {'field': 'full_name',         'label': 'Name',        'type': 'text'},
            {'field': 'door_name',         'label': 'Door',        'type': 'text'},
            {'field': 'last_event_time',   'label': 'Last Event',  'type': 'datetime'},
            {'field': 'violation_type',    'label': 'Type',        'type': 'text'},
            {'field': 'last_terminal_sn',  'label': 'Terminal',    'type': 'text'},
        ]
        data = [{
            'emp_code':        r.emp_code or '',
            'full_name':       r.full_name or '',
            'door_name':       r.door_name or '',
            'last_event_time': r.last_event_time.strftime('%Y-%m-%d %H:%M:%S') if r.last_event_time else '',
            'violation_type':  event_type_map.get(r.last_event_type, f'Type {r.last_event_type}'),
            'last_terminal_sn': r.last_terminal_sn or '',
        } for r in rows]
        return {
            'columns': columns, 'data': data,
            'summary': {'total_violations': len(data)},
        }

    def access_control_first_card(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """First access event per employee per door for a given day.

        Source priority: acc_event (has door_id + direction) → falls back to
        iclock_transaction for access-reader terminals not yet in acc_event.
        """
        date_filter = filters.get('date', _site_today().strftime('%Y-%m-%d'))
        rows = self.db.execute(text("""
            WITH combined AS (
                -- Source 1: acc_event (most accurate — has door and direction)
                SELECT
                    ae.emp_code,
                    ae.terminal_sn,
                    ae.door_id,
                    ae.event_time AS event_ts
                FROM acc_event ae
                WHERE ae.event_time::date = :date_filter
                  AND ae.event_type IN (0,1,2,3,4)   -- access events only, not emergency
                  AND ae.emp_code IS NOT NULL

                UNION ALL

                -- Source 2: iclock_transaction from access readers (back-fill)
                SELECT
                    tx.emp_code,
                    tx.terminal_sn,
                    (SELECT MIN(ad.id) FROM acc_door ad WHERE ad.terminal_sn = tx.terminal_sn) AS door_id,
                    tx.punch_time AS event_ts
                FROM iclock_transaction tx
                JOIN iclock_terminal tt ON tx.terminal_sn = tt.sn
                                       AND tt.reader_purpose IN ('ACCESS_ENTRY','ACCESS_EXIT')
                WHERE tx.punch_time::date = :date_filter
                  AND NOT EXISTS (
                      SELECT 1 FROM acc_event ae2
                      WHERE ae2.emp_code    = tx.emp_code
                        AND ae2.terminal_sn = tx.terminal_sn
                        AND ae2.event_time::date = :date_filter
                        AND ae2.event_type IN (0,1,2,3,4)
                  )
            ),
            first_per_emp_door AS (
                SELECT emp_code, terminal_sn, door_id,
                       MIN(event_ts) AS first_event
                FROM combined
                GROUP BY emp_code, terminal_sn, door_id
            )
            SELECT
                f.emp_code,
                COALESCE(pe.first_name || ' ' || pe.last_name, f.emp_code) AS full_name,
                COALESCE(dept.dept_name, '')   AS department,
                COALESCE(t.alias, f.terminal_sn) AS terminal_name,
                COALESCE(d.name, '—')          AS door_name,
                f.first_event
            FROM first_per_emp_door f
            LEFT JOIN personnel_employee pe    ON f.emp_code    = pe.emp_code
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) dept ON pe.dept_id   = dept.id
            LEFT JOIN iclock_terminal t        ON f.terminal_sn = t.sn
            LEFT JOIN acc_door d               ON f.door_id     = d.id
            ORDER BY f.first_event, f.emp_code
        """), {'date_filter': date_filter}).fetchall()

        columns = [
            {'field': 'emp_code',     'label': 'Badge ID',    'type': 'text'},
            {'field': 'full_name',    'label': 'Name',        'type': 'text'},
            {'field': 'department',   'label': 'Department',  'type': 'text'},
            {'field': 'door_name',    'label': 'Door',        'type': 'text'},
            {'field': 'terminal_name','label': 'Terminal',    'type': 'text'},
            {'field': 'first_event',  'label': 'First Entry', 'type': 'text'},
        ]
        data = [{
            'emp_code':      r.emp_code or '',
            'full_name':     r.full_name or '',
            'department':    r.department or '',
            'door_name':     r.door_name or '—',
            'terminal_name': r.terminal_name or '',
            'first_event':   r.first_event.strftime('%H:%M:%S') if r.first_event else '',
        } for r in rows]
        return {
            'columns': columns, 'data': data,
            'summary': {'total_employees': len(data), 'date': date_filter},
        }

    def access_control_inout_count(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """In/out count per door for a given date.

        Uses acc_event (has proper in_out direction) as primary source and
        falls back to iclock_transaction for access readers not yet in acc_event.
        """
        date_filter = filters.get('date', _site_today().strftime('%Y-%m-%d'))
        rows = self.db.execute(text("""
            WITH combined AS (
                -- Source 1: acc_event — has door_id + proper in_out direction
                SELECT
                    ae.terminal_sn,
                    ae.door_id,
                    ae.emp_code,
                    ae.in_out
                FROM acc_event ae
                WHERE ae.event_time::date = :date_filter
                  AND ae.event_type IN (0,1,2,3,4)
                  AND ae.emp_code IS NOT NULL

                UNION ALL

                -- Source 2: iclock_transaction from access readers (back-fill)
                SELECT
                    tx.terminal_sn,
                    (CASE tt.reader_purpose
                        WHEN 'ACCESS_ENTRY' THEN (SELECT MIN(ad.id) FROM acc_door ad WHERE ad.terminal_sn = tx.terminal_sn)
                        ELSE                     (SELECT MAX(ad.id) FROM acc_door ad WHERE ad.terminal_sn = tx.terminal_sn)
                     END)                                  AS door_id,
                    tx.emp_code,
                    CASE tt.reader_purpose WHEN 'ACCESS_ENTRY' THEN 0 ELSE 1 END AS in_out
                FROM iclock_transaction tx
                JOIN iclock_terminal tt ON tx.terminal_sn = tt.sn
                                       AND tt.reader_purpose IN ('ACCESS_ENTRY','ACCESS_EXIT')
                WHERE tx.punch_time::date = :date_filter
                  AND NOT EXISTS (
                      SELECT 1 FROM acc_event ae2
                      WHERE ae2.emp_code    = tx.emp_code
                        AND ae2.terminal_sn = tx.terminal_sn
                        AND ae2.event_time::date = :date_filter
                        AND ae2.event_type IN (0,1,2,3,4)
                  )
            )
            SELECT
                c.terminal_sn,
                COALESCE(t.alias, c.terminal_sn)         AS terminal_name,
                COALESCE(d.name, '—')                    AS door_name,
                COUNT(*) FILTER (WHERE c.in_out = 0)     AS in_count,
                COUNT(*) FILTER (WHERE c.in_out = 1)     AS out_count,
                COUNT(*)                                  AS total_events,
                COUNT(DISTINCT c.emp_code)                AS unique_employees
            FROM combined c
            LEFT JOIN iclock_terminal t ON c.terminal_sn = t.sn
            LEFT JOIN acc_door d        ON c.door_id      = d.id
            GROUP BY c.terminal_sn, t.alias, d.name
            ORDER BY c.terminal_sn
        """), {'date_filter': date_filter}).fetchall()

        columns = [
            {'field': 'door_name',        'label': 'Door',             'type': 'text'},
            {'field': 'terminal_name',    'label': 'Terminal',         'type': 'text'},
            {'field': 'in_count',         'label': 'In',               'type': 'number'},
            {'field': 'out_count',        'label': 'Out',              'type': 'number'},
            {'field': 'total_events',     'label': 'Total Events',     'type': 'number'},
            {'field': 'unique_employees', 'label': 'Unique Employees', 'type': 'number'},
        ]
        data = [{
            'door_name':        r.door_name or '—',
            'terminal_name':    r.terminal_name or '',
            'in_count':         r.in_count or 0,
            'out_count':        r.out_count or 0,
            'total_events':     r.total_events or 0,
            'unique_employees': r.unique_employees or 0,
        } for r in rows]
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total_in':        sum(r['in_count']     for r in data),
                'total_out':       sum(r['out_count']    for r in data),
                'total_events':    sum(r['total_events'] for r in data),
                'date':            date_filter,
            },
        }

    # ==================== DEVICE REPORTS ====================

    _DEVICE_BASE_SQL = """
        SELECT
            COALESCE(NULLIF(TRIM(d.name), ''), NULLIF(TRIM(t.alias), ''),
                     'Terminal ' || COALESCE(d.serial_number, t.sn)) AS device_name,
            COALESCE(d.serial_number, t.sn)                          AS serial_number,
            COALESCE(d.ip_address, t.ip_address)                     AS ip_address,
            COALESCE(NULLIF(TRIM(d.model), ''), NULLIF(TRIM(t.device_model), ''), 'N/A') AS model,
            COALESCE(d.manufacturer, 'ZKTeco')                       AS manufacturer,
            COALESCE(NULLIF(d.firmware_version, ''), NULLIF(t.fw_ver, ''), 'N/A') AS firmware_version,
            COALESCE(d.hardware_version, 'N/A')                      AS hardware_version,
            COALESCE(t.reader_purpose, d.device_type, 'N/A')         AS device_purpose,
            COALESCE(z.name, '')                                      AS zone_name,
            COALESCE(t.connection_mode, d.connection_mode, 'N/A')    AS connection_mode,
            COALESCE(t.mac_address, d.mac_address, '')               AS mac_address,
            COALESCE(d.last_seen, t.last_activity, d.last_heartbeat) AS last_contact,
            COALESCE(d.user_count, t.user_count, 0)                  AS user_count,
            COALESCE(d.fp_count,   t.fp_count,   0)                  AS fp_count,
            COALESCE(d.face_count, t.face_count, 0)                  AS face_count,
            COALESCE(tx.tx_count, 0)                                  AS total_transactions,
            tx.last_transaction
        FROM devices d
        FULL OUTER JOIN iclock_terminal t ON d.serial_number = t.sn
        LEFT JOIN zones z ON z.id = COALESCE(t.zone_id, d.zone_id)
        LEFT JOIN (
            SELECT terminal_sn,
                   COUNT(*)        AS tx_count,
                   MAX(punch_time) AS last_transaction
            FROM iclock_transaction
            GROUP BY terminal_sn
        ) tx ON tx.terminal_sn = COALESCE(d.serial_number, t.sn)
    """

    @staticmethod
    def _connectivity_status(last_contact, now_utc):
        """Derive human-readable connectivity status from last contact timestamp."""
        if last_contact is None:
            return 'Never Connected'
        lc = last_contact.astimezone(timezone.utc).replace(tzinfo=None) if last_contact.tzinfo else last_contact
        hours_ago = (now_utc - lc).total_seconds() / 3600
        if hours_ago <= 2:
            return 'Online'
        if hours_ago <= 24:
            return 'Warning'
        return 'Offline'

    def device_status_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Full device inventory with real-time connectivity and enrollment stats."""
        rows = self.db.execute(text(self._DEVICE_BASE_SQL + " ORDER BY device_name")).fetchall()

        now = datetime.utcnow()
        purpose_labels = {
            'ATTENDANCE':   'Attendance',
            'ACCESS_ENTRY': 'Access Entry',
            'ACCESS_EXIT':  'Access Exit',
            'MUSTERING':    'Mustering',
            'POB':          'POB',
            'EMERGENCY':    'Emergency',
        }

        columns = [
            {'field': 'device_name',        'label': 'Device Name',     'type': 'text'},
            {'field': 'serial_number',       'label': 'Serial No',       'type': 'text'},
            {'field': 'ip_address',          'label': 'IP Address',      'type': 'text'},
            {'field': 'model',               'label': 'Model',           'type': 'text'},
            {'field': 'manufacturer',        'label': 'Manufacturer',    'type': 'text'},
            {'field': 'device_purpose',      'label': 'Purpose',         'type': 'text'},
            {'field': 'zone_name',           'label': 'Zone',            'type': 'text'},
            {'field': 'connectivity_status', 'label': 'Status',          'type': 'text'},
            {'field': 'last_contact',        'label': 'Last Contact',    'type': 'datetime'},
            {'field': 'connection_mode',     'label': 'Connection',      'type': 'text'},
            {'field': 'firmware_version',    'label': 'Firmware',        'type': 'text'},
            {'field': 'user_count',          'label': 'Users Enrolled',  'type': 'number'},
            {'field': 'fp_count',            'label': 'Fingerprints',    'type': 'number'},
            {'field': 'face_count',          'label': 'Faces',           'type': 'number'},
            {'field': 'total_transactions',  'label': 'Total Punches',   'type': 'number'},
            {'field': 'last_transaction',    'label': 'Last Transaction','type': 'datetime'},
        ]

        data = []
        for r in rows:
            status = self._connectivity_status(r.last_contact, now)
            data.append({
                'device_name':        r.device_name or '',
                'serial_number':      r.serial_number or '',
                'ip_address':         r.ip_address or '',
                'model':              r.model or '',
                'manufacturer':       r.manufacturer or '',
                'device_purpose':     purpose_labels.get(r.device_purpose, r.device_purpose or 'N/A'),
                'zone_name':          r.zone_name or '',
                'connectivity_status':status,
                'last_contact':       r.last_contact.strftime('%Y-%m-%d %H:%M') if r.last_contact else 'Never',
                'connection_mode':    r.connection_mode.upper() if r.connection_mode else 'N/A',
                'firmware_version':   r.firmware_version or 'N/A',
                'user_count':         r.user_count or 0,
                'fp_count':           r.fp_count or 0,
                'face_count':         r.face_count or 0,
                'total_transactions': r.total_transactions or 0,
                'last_transaction':   r.last_transaction.strftime('%Y-%m-%d %H:%M') if r.last_transaction else 'N/A',
            })

        online  = sum(1 for r in data if r['connectivity_status'] == 'Online')
        warning = sum(1 for r in data if r['connectivity_status'] == 'Warning')
        offline = sum(1 for r in data if r['connectivity_status'] in ('Offline', 'Never Connected'))
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total_devices':      len(data),
                'online':             online,
                'warning':            warning,
                'offline':            offline,
                'total_transactions': sum(r['total_transactions'] for r in data),
            },
        }

    def device_transaction_count(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Daily transaction volume per device terminal with device details."""
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        rows = self.db.execute(text("""
            SELECT
                t.sn AS terminal_sn,
                COALESCE(NULLIF(TRIM(d.name), ''), NULLIF(TRIM(t.alias), ''),
                         'Terminal ' || t.sn) AS device_name,
                COALESCE(t.reader_purpose, 'N/A') AS device_purpose,
                COALESCE(z.name, '')               AS zone_name,
                tx.punch_date,
                tx.punch_count,
                tx.unique_employees
            FROM iclock_terminal t
            LEFT JOIN devices d ON d.serial_number = t.sn
            LEFT JOIN zones z ON z.id = t.zone_id
            JOIN (
                SELECT terminal_sn,
                       punch_time::date         AS punch_date,
                       COUNT(*)                 AS punch_count,
                       COUNT(DISTINCT emp_code) AS unique_employees
                FROM iclock_transaction
                WHERE punch_time::date BETWEEN :date_from AND :date_to
                GROUP BY terminal_sn, punch_time::date
            ) tx ON tx.terminal_sn = t.sn
            ORDER BY tx.punch_date DESC, device_name
        """), {'date_from': date_from, 'date_to': date_to}).fetchall()

        purpose_labels = {
            'ATTENDANCE': 'Attendance', 'ACCESS_ENTRY': 'Access Entry',
            'ACCESS_EXIT': 'Access Exit', 'MUSTERING': 'Mustering',
            'POB': 'POB', 'EMERGENCY': 'Emergency',
        }
        columns = [
            {'field': 'punch_date',       'label': 'Date',             'type': 'date'},
            {'field': 'device_name',      'label': 'Device Name',      'type': 'text'},
            {'field': 'terminal_sn',      'label': 'Serial No',        'type': 'text'},
            {'field': 'device_purpose',   'label': 'Purpose',          'type': 'text'},
            {'field': 'zone_name',        'label': 'Zone',             'type': 'text'},
            {'field': 'punch_count',      'label': 'Punches',          'type': 'number'},
            {'field': 'unique_employees', 'label': 'Unique Employees', 'type': 'number'},
        ]
        data = [{
            'punch_date':       str(r.punch_date),
            'device_name':      r.device_name or '',
            'terminal_sn':      r.terminal_sn or '',
            'device_purpose':   purpose_labels.get(r.device_purpose, r.device_purpose or 'N/A'),
            'zone_name':        r.zone_name or '',
            'punch_count':      r.punch_count or 0,
            'unique_employees': r.unique_employees or 0,
        } for r in rows]

        total = sum(r['punch_count'] for r in data)
        days  = len({r['punch_date'] for r in data})
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total_punches':   total,
                'active_days':     days,
                'daily_average':   round(total / days, 1) if days else 0,
                'date_from':       date_from,
                'date_to':         date_to,
            },
        }

    def device_offline_history(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """All devices offline or not seen within threshold — merged across both device tables."""
        threshold_hours = int(filters.get('offline_hours', 24))
        threshold_dt = datetime.utcnow() - timedelta(hours=threshold_hours)

        rows = self.db.execute(text(self._DEVICE_BASE_SQL + """
            WHERE COALESCE(d.last_seen, t.last_activity, d.last_heartbeat) IS NULL
               OR COALESCE(d.last_seen, t.last_activity, d.last_heartbeat) < :threshold_dt
            ORDER BY last_contact ASC NULLS FIRST
        """), {'threshold_dt': threshold_dt}).fetchall()

        now = datetime.utcnow()
        purpose_labels = {
            'ATTENDANCE': 'Attendance', 'ACCESS_ENTRY': 'Access Entry',
            'ACCESS_EXIT': 'Access Exit', 'MUSTERING': 'Mustering',
        }
        columns = [
            {'field': 'device_name',        'label': 'Device Name',     'type': 'text'},
            {'field': 'serial_number',       'label': 'Serial No',       'type': 'text'},
            {'field': 'ip_address',          'label': 'IP Address',      'type': 'text'},
            {'field': 'model',               'label': 'Model',           'type': 'text'},
            {'field': 'device_purpose',      'label': 'Purpose',         'type': 'text'},
            {'field': 'zone_name',           'label': 'Zone',            'type': 'text'},
            {'field': 'connectivity_status', 'label': 'Status',          'type': 'text'},
            {'field': 'last_contact',        'label': 'Last Contact',    'type': 'datetime'},
            {'field': 'offline_duration',    'label': 'Offline Duration','type': 'text'},
        ]
        data = []
        for r in rows:
            status = self._connectivity_status(r.last_contact, now)
            if r.last_contact:
                lc = r.last_contact.astimezone(timezone.utc).replace(tzinfo=None) if r.last_contact.tzinfo else r.last_contact
                hrs = (now - lc).total_seconds() / 3600
                if hrs >= 24:
                    duration = f'{int(hrs // 24)}d {int(hrs % 24)}h'
                else:
                    duration = f'{round(hrs, 1)} hours'
            else:
                duration = 'Never connected'
            data.append({
                'device_name':        r.device_name or '',
                'serial_number':      r.serial_number or '',
                'ip_address':         r.ip_address or '',
                'model':              r.model or '',
                'device_purpose':     purpose_labels.get(r.device_purpose, r.device_purpose or 'N/A'),
                'zone_name':          r.zone_name or '',
                'connectivity_status':status,
                'last_contact':       r.last_contact.strftime('%Y-%m-%d %H:%M') if r.last_contact else 'Never',
                'offline_duration':   duration,
            })

        never    = sum(1 for r in data if r['last_contact'] == 'Never')
        offline  = sum(1 for r in data if r['connectivity_status'] == 'Offline')
        warning  = sum(1 for r in data if r['connectivity_status'] == 'Warning')
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total_offline':     len(data),
                'never_connected':   never,
                'offline':           offline,
                'warning':           warning,
                'threshold_hours':   threshold_hours,
            },
        }

    def device_firmware_version(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Firmware and hardware version inventory across all devices."""
        rows = self.db.execute(text(self._DEVICE_BASE_SQL + " ORDER BY device_name")).fetchall()

        columns = [
            {'field': 'device_name',      'label': 'Device Name',      'type': 'text'},
            {'field': 'serial_number',     'label': 'Serial No',        'type': 'text'},
            {'field': 'manufacturer',      'label': 'Manufacturer',     'type': 'text'},
            {'field': 'model',             'label': 'Model',            'type': 'text'},
            {'field': 'firmware_version',  'label': 'Firmware Version', 'type': 'text'},
            {'field': 'hardware_version',  'label': 'HW Version',       'type': 'text'},
            {'field': 'device_purpose',    'label': 'Purpose',          'type': 'text'},
            {'field': 'zone_name',         'label': 'Zone',             'type': 'text'},
            {'field': 'connection_mode',   'label': 'Connection',       'type': 'text'},
            {'field': 'mac_address',       'label': 'MAC Address',      'type': 'text'},
            {'field': 'last_contact',      'label': 'Last Contact',     'type': 'datetime'},
        ]

        purpose_labels = {
            'ATTENDANCE': 'Attendance', 'ACCESS_ENTRY': 'Access Entry',
            'ACCESS_EXIT': 'Access Exit', 'MUSTERING': 'Mustering',
            'POB': 'POB', 'EMERGENCY': 'Emergency',
        }
        version_counts: Dict[str, int] = {}
        data = []
        for r in rows:
            fw = r.firmware_version or 'N/A'
            version_counts[fw] = version_counts.get(fw, 0) + 1
            data.append({
                'device_name':     r.device_name or '',
                'serial_number':   r.serial_number or '',
                'manufacturer':    r.manufacturer or '',
                'model':           r.model or '',
                'firmware_version':fw,
                'hardware_version':r.hardware_version or 'N/A',
                'device_purpose':  purpose_labels.get(r.device_purpose, r.device_purpose or 'N/A'),
                'zone_name':       r.zone_name or '',
                'connection_mode': r.connection_mode.upper() if r.connection_mode else 'N/A',
                'mac_address':     r.mac_address or 'N/A',
                'last_contact':    r.last_contact.strftime('%Y-%m-%d %H:%M') if r.last_contact else 'Never',
            })
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total_devices':    len(data),
                'firmware_versions': version_counts,
            },
        }

    # ==================== MUSTERING (continued) ====================

    def mustering_drill_log(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Drill schedule history with zone name, outcome, and linked event results."""
        default_from = (_site_today() - timedelta(days=90)).strftime('%Y-%m-%d')
        default_to   = _site_today().strftime('%Y-%m-%d')
        date_from = filters.get('date_from', default_from)
        date_to   = filters.get('date_to',   default_to)

        rows = self.db.execute(text("""
            SELECT
                ds.id,
                ds.scheduled_time,
                z.name                              AS zone_name,
                ds.event_type,
                ds.status,
                ds.processed,
                ds.processed_time,
                ds.auto_start,
                -- Find the mustering event triggered closest to this scheduled time
                me.id                               AS triggered_event_id,
                me.total_expected,
                me.total_safe,
                me.total_missing,
                me.total_injured,
                CASE WHEN me.total_expected > 0
                    THEN ROUND(me.total_safe::numeric / me.total_expected * 100, 1)
                    ELSE NULL END                   AS compliance_pct,
                ROUND(EXTRACT(EPOCH FROM (me.end_time - me.start_time)) / 60, 1)
                                                    AS duration_min
            FROM mustering_drill_schedule ds
            LEFT JOIN zones z ON ds.zone_id = z.id
            LEFT JOIN LATERAL (
                SELECT me2.id, me2.total_expected, me2.total_safe,
                       me2.total_missing, me2.total_injured,
                       me2.start_time, me2.end_time
                FROM mustering_event me2
                WHERE me2.zone_id     = ds.zone_id
                  AND me2.event_type  = ds.event_type
                  AND me2.start_time BETWEEN ds.scheduled_time - INTERVAL '10 minutes'
                                         AND ds.scheduled_time + INTERVAL '60 minutes'
                ORDER BY ABS(EXTRACT(EPOCH FROM (me2.start_time - ds.scheduled_time)))
                LIMIT 1
            ) me ON true
            WHERE ds.scheduled_time::date BETWEEN :date_from AND :date_to
            ORDER BY ds.scheduled_time DESC
        """), {'date_from': date_from, 'date_to': date_to}).fetchall()

        columns = [
            {'field': 'scheduled_time',     'label': 'Scheduled Time',    'type': 'datetime'},
            {'field': 'zone_name',           'label': 'Zone',              'type': 'text'},
            {'field': 'event_type',          'label': 'Type',              'type': 'text'},
            {'field': 'status',              'label': 'Status',            'type': 'text'},
            {'field': 'processed_time',      'label': 'Triggered At',      'type': 'datetime'},
            {'field': 'auto_start',          'label': 'Auto-Start',        'type': 'text'},
            {'field': 'triggered_event_id',  'label': 'Event ID',          'type': 'number'},
            {'field': 'total_expected',      'label': 'Expected',          'type': 'number'},
            {'field': 'total_safe',          'label': 'Safe',              'type': 'number'},
            {'field': 'total_missing',       'label': 'Missing',           'type': 'number'},
            {'field': 'total_injured',       'label': 'Injured',           'type': 'number'},
            {'field': 'compliance_pct',      'label': 'Compliance %',      'type': 'percentage'},
            {'field': 'duration_min',        'label': 'Duration (min)',    'type': 'number'},
        ]
        data = [{
            'scheduled_time':    r.scheduled_time.strftime('%Y-%m-%d %H:%M') if r.scheduled_time else '',
            'zone_name':         r.zone_name or '',
            'event_type':        self._MUSTER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'status':            r.status or '',
            'processed_time':    r.processed_time.strftime('%Y-%m-%d %H:%M') if r.processed_time else '—',
            'auto_start':        'Yes' if r.auto_start else 'No',
            'triggered_event_id':r.triggered_event_id or '—',
            'total_expected':    r.total_expected or 0,
            'total_safe':        r.total_safe or 0,
            'total_missing':     r.total_missing or 0,
            'total_injured':     r.total_injured or 0,
            'compliance_pct':    float(r.compliance_pct) if r.compliance_pct is not None else None,
            'duration_min':      float(r.duration_min) if r.duration_min else 0,
        } for r in rows]

        triggered = sum(1 for r in data if r['processed_time'] != '—')
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total_drills':  len(data),
                'triggered':     triggered,
                'pending':       len(data) - triggered,
            },
        }

    def mustering_headcount_timeline(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Headcount roll-call for a mustering event — every person accounted for."""
        event_id = filters.get('event_id')
        if not event_id:
            # Default to the most recent event that has log records
            row = self.db.execute(text(
                "SELECT event_id FROM mustering_log ORDER BY check_time DESC LIMIT 1"
            )).fetchone()
            event_id = row.event_id if row else None

        params: Dict[str, Any] = {'event_id': event_id}

        # Event header
        event_row = self.db.execute(text("""
            SELECT me.id, me.event_type, me.status, me.start_time, me.end_time,
                   z.name AS zone_name, u.username AS initiated_by,
                   me.total_expected, me.total_safe, me.total_missing, me.total_injured
            FROM mustering_event me
            LEFT JOIN zones z     ON me.zone_id      = z.id
            LEFT JOIN auth_user u ON me.initiated_by = u.id
            WHERE me.id = :event_id
        """), params).fetchone()

        rows = self.db.execute(text("""
            SELECT
                ml.check_time,
                ml.emp_code,
                ml.emp_name,
                COALESCE(NULLIF(ml.dept_name,''), d.dept_name, '') AS department,
                ml.status,
                COALESCE(ml.device_alias, '')      AS device_alias,
                COALESCE(ml.last_punch_area, '')   AS last_punch_area,
                SUM(CASE WHEN ml.status = 1 THEN 1 ELSE 0 END)
                    OVER (ORDER BY ml.check_time ROWS UNBOUNDED PRECEDING) AS cumulative_safe,
                SUM(CASE WHEN ml.status = 0 THEN 1 ELSE 0 END)
                    OVER (ORDER BY ml.check_time ROWS UNBOUNDED PRECEDING) AS cumulative_missing
            FROM mustering_log ml
            LEFT JOIN personnel_employee pe  ON ml.emp_code  = pe.emp_code
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON pe.dept_id   = d.id
            WHERE ml.event_id = :event_id
            ORDER BY ml.check_time
        """), params).fetchall()

        columns = [
            {'field': 'check_time',        'label': 'Check Time',       'type': 'datetime'},
            {'field': 'emp_code',           'label': 'Badge ID',         'type': 'text'},
            {'field': 'emp_name',           'label': 'Name',             'type': 'text'},
            {'field': 'department',         'label': 'Department',       'type': 'text'},
            {'field': 'status',             'label': 'Status',           'type': 'text'},
            {'field': 'device_alias',       'label': 'Muster Point',     'type': 'text'},
            {'field': 'last_punch_area',    'label': 'Last Known Area',  'type': 'text'},
            {'field': 'cumulative_safe',    'label': 'Running Safe',     'type': 'number'},
            {'field': 'cumulative_missing', 'label': 'Running Missing',  'type': 'number'},
        ]
        data = [{
            'check_time':        r.check_time.strftime('%Y-%m-%d %H:%M:%S') if r.check_time else '',
            'emp_code':          r.emp_code or '',
            'emp_name':          r.emp_name or '',
            'department':        r.department or '',
            'status':            self._MUSTER_LOG_STATUS.get(r.status, 'Unknown'),
            'device_alias':      r.device_alias or '',
            'last_punch_area':   r.last_punch_area or '',
            'cumulative_safe':   int(r.cumulative_safe or 0),
            'cumulative_missing':int(r.cumulative_missing or 0),
        } for r in rows]

        summary: Dict[str, Any] = {
            'total': len(data),
            'safe':    sum(1 for r in data if r['status'] == 'Safe'),
            'missing': sum(1 for r in data if r['status'] == 'Missing'),
            'injured': sum(1 for r in data if r['status'] == 'Injured'),
        }
        if event_row:
            summary.update({
                'event_id':    event_row.id,
                'event_type':  self._MUSTER_EVENT_TYPE.get(event_row.event_type, ''),
                'event_status':self._MUSTER_STATUS.get(event_row.status, ''),
                'zone_name':   event_row.zone_name or '',
                'initiated_by':event_row.initiated_by or '',
                'start_time':  event_row.start_time.strftime('%Y-%m-%d %H:%M') if event_row.start_time else '',
                'end_time':    event_row.end_time.strftime('%Y-%m-%d %H:%M') if event_row.end_time else 'Ongoing',
                'expected':    event_row.total_expected or 0,
            })
        return {'columns': columns, 'data': data, 'summary': summary}

    def mustering_missing_persons(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """All unaccounted-for persons across mustering events, with last known location."""
        event_id  = filters.get('event_id')
        dept_name = filters.get('dept_name', '')

        params: Dict[str, Any] = {}
        event_clause = "AND ml.event_id = :event_id" if event_id else ""
        dept_clause  = "AND (ml.dept_name = :dept_name OR d.dept_name = :dept_name)" if dept_name else ""
        if event_id:  params['event_id']  = int(event_id)
        if dept_name: params['dept_name'] = dept_name

        rows = self.db.execute(text(f"""
            SELECT
                ml.event_id,
                me.start_time                               AS event_time,
                me.event_type,
                COALESCE(z.name, '')                        AS zone_name,
                ml.emp_code,
                ml.emp_name,
                COALESCE(NULLIF(ml.dept_name,''), d.dept_name, '') AS department,
                COALESCE(ml.last_punch_area, '')            AS last_punch_area,
                ml.check_time                               AS last_seen
            FROM mustering_log ml
            JOIN  mustering_event me ON ml.event_id  = me.id
            LEFT JOIN zones z        ON me.zone_id   = z.id
            LEFT JOIN personnel_employee pe  ON ml.emp_code = pe.emp_code
            LEFT JOIN (SELECT id, name AS dept_name FROM departments) d ON pe.dept_id  = d.id
            WHERE ml.status = 0
              {event_clause}
              {dept_clause}
            ORDER BY me.start_time DESC, ml.emp_name
        """), params).fetchall()

        columns = [
            {'field': 'event_id',      'label': 'Event ID',        'type': 'number'},
            {'field': 'event_time',    'label': 'Event Time',      'type': 'datetime'},
            {'field': 'event_type',    'label': 'Event Type',      'type': 'text'},
            {'field': 'zone_name',     'label': 'Zone',            'type': 'text'},
            {'field': 'emp_code',      'label': 'Badge ID',        'type': 'text'},
            {'field': 'emp_name',      'label': 'Name',            'type': 'text'},
            {'field': 'department',    'label': 'Department',      'type': 'text'},
            {'field': 'last_punch_area','label': 'Last Known Area','type': 'text'},
            {'field': 'last_seen',     'label': 'Last Seen',       'type': 'datetime'},
        ]
        data = [{
            'event_id':       r.event_id or 0,
            'event_time':     r.event_time.strftime('%Y-%m-%d %H:%M') if r.event_time else '',
            'event_type':     self._MUSTER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'zone_name':      r.zone_name or '',
            'emp_code':       r.emp_code or '',
            'emp_name':       r.emp_name or '',
            'department':     r.department or '',
            'last_punch_area':r.last_punch_area or '—',
            'last_seen':      r.last_seen.strftime('%Y-%m-%d %H:%M:%S') if r.last_seen else '',
        } for r in rows]
        return {
            'columns': columns, 'data': data,
            'total': len(data),
            'summary': {'total_missing': len(data)},
        }

    def mustering_compliance_percentage(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Per-event compliance with grade and full headcount breakdown."""
        default_from = (_site_today() - timedelta(days=30)).strftime('%Y-%m-%d')
        default_to   = _site_today().strftime('%Y-%m-%d')
        date_from = filters.get('date_from', default_from)
        date_to   = filters.get('date_to',   default_to)

        rows = self.db.execute(text("""
            SELECT
                me.id                                        AS event_id,
                me.event_type,
                CASE me.status WHEN 0 THEN 'Active' ELSE 'Completed' END AS status,
                COALESCE(z.name, '')                         AS zone_name,
                u.username                                   AS initiated_by,
                me.start_time,
                ROUND(EXTRACT(EPOCH FROM (me.end_time - me.start_time)) / 60, 1)
                                                             AS duration_min,
                me.total_expected,
                me.total_safe,
                me.total_missing,
                me.total_injured,
                CASE WHEN me.total_expected > 0
                    THEN ROUND(me.total_safe::numeric / me.total_expected * 100, 1)
                    ELSE 0 END                               AS compliance_pct,
                CASE
                    WHEN me.total_expected = 0 THEN 'N/A'
                    WHEN me.total_safe::numeric / NULLIF(me.total_expected,0) >= 0.95 THEN 'Excellent'
                    WHEN me.total_safe::numeric / NULLIF(me.total_expected,0) >= 0.80 THEN 'Good'
                    WHEN me.total_safe::numeric / NULLIF(me.total_expected,0) >= 0.60 THEN 'Fair'
                    ELSE 'Poor'
                END                                          AS compliance_grade
            FROM mustering_event me
            LEFT JOIN zones z     ON me.zone_id      = z.id
            LEFT JOIN auth_user u ON me.initiated_by = u.id
            WHERE me.start_time::date BETWEEN :date_from AND :date_to
            ORDER BY me.start_time DESC
        """), {'date_from': date_from, 'date_to': date_to}).fetchall()

        columns = [
            {'field': 'event_id',        'label': 'Event ID',       'type': 'number'},
            {'field': 'event_type',      'label': 'Type',           'type': 'text'},
            {'field': 'status',          'label': 'Status',         'type': 'text'},
            {'field': 'zone_name',       'label': 'Zone',           'type': 'text'},
            {'field': 'initiated_by',    'label': 'Initiated By',   'type': 'text'},
            {'field': 'start_time',      'label': 'Date & Time',    'type': 'datetime'},
            {'field': 'duration_min',    'label': 'Duration (min)', 'type': 'number'},
            {'field': 'total_expected',  'label': 'Expected',       'type': 'number'},
            {'field': 'total_safe',      'label': 'Safe',           'type': 'number'},
            {'field': 'total_missing',   'label': 'Missing',        'type': 'number'},
            {'field': 'total_injured',   'label': 'Injured',        'type': 'number'},
            {'field': 'compliance_pct',  'label': 'Compliance %',   'type': 'percentage'},
            {'field': 'compliance_grade','label': 'Grade',          'type': 'text'},
        ]
        data = [{
            'event_id':        r.event_id,
            'event_type':      self._MUSTER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'status':          r.status or '',
            'zone_name':       r.zone_name or '',
            'initiated_by':    r.initiated_by or '',
            'start_time':      r.start_time.strftime('%Y-%m-%d %H:%M') if r.start_time else '',
            'duration_min':    float(r.duration_min) if r.duration_min else 0,
            'total_expected':  r.total_expected or 0,
            'total_safe':      r.total_safe or 0,
            'total_missing':   r.total_missing or 0,
            'total_injured':   r.total_injured or 0,
            'compliance_pct':  float(r.compliance_pct) if r.compliance_pct is not None else 0,
            'compliance_grade':r.compliance_grade or 'N/A',
        } for r in rows]

        pcts = [r['compliance_pct'] for r in data if r['total_expected'] > 0]
        grade_counts: Dict[str, int] = {}
        for r in data:
            grade_counts[r['compliance_grade']] = grade_counts.get(r['compliance_grade'], 0) + 1

        return {
            'columns': columns, 'data': data,
            'total': len(data),
            'summary': {
                'total_events':       len(data),
                'avg_compliance_pct': round(sum(pcts) / len(pcts), 1) if pcts else 0,
                'grade_distribution': grade_counts,
                'excellent':          grade_counts.get('Excellent', 0),
                'poor':               grade_counts.get('Poor', 0),
            },
        }

    def mustering_zone_performance(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Zone-level mustering performance aggregated across all events."""
        date_from = filters.get('date_from', (_site_today() - timedelta(days=365)).strftime('%Y-%m-%d'))

        rows = self.db.execute(text("""
            SELECT
                z.name                                       AS zone_name,
                COUNT(me.id)                                 AS total_events,
                COUNT(me.id) FILTER (WHERE me.event_type = 1)
                                                             AS total_drills,
                COUNT(me.id) FILTER (WHERE me.event_type IN (0,2,3,4))
                                                             AS total_real_events,
                COUNT(me.id) FILTER (
                    WHERE me.total_expected > 0
                      AND me.total_safe >= me.total_expected)
                                                             AS fully_compliant,
                ROUND(AVG(
                    CASE WHEN me.total_expected > 0
                        THEN me.total_safe::numeric / me.total_expected * 100
                    END), 1)                                 AS avg_compliance_pct,
                ROUND(AVG(
                    EXTRACT(EPOCH FROM (me.end_time - me.start_time)) / 60
                ) FILTER (WHERE me.end_time IS NOT NULL), 1) AS avg_duration_min,
                MIN(CASE WHEN me.total_expected > 0
                    THEN ROUND(me.total_safe::numeric / me.total_expected * 100, 1)
                END)                                         AS min_compliance_pct,
                MAX(CASE WHEN me.total_expected > 0
                    THEN ROUND(me.total_safe::numeric / me.total_expected * 100, 1)
                END)                                         AS max_compliance_pct,
                COALESCE(SUM(me.total_injured), 0)           AS total_injured,
                MAX(me.start_time)                           AS last_event_time
            FROM mustering_event me
            JOIN zones z ON me.zone_id = z.id
            WHERE me.start_time::date >= :date_from
            GROUP BY z.id, z.name
            ORDER BY avg_compliance_pct DESC NULLS LAST
        """), {'date_from': date_from}).fetchall()

        columns = [
            {'field': 'zone_name',          'label': 'Zone',              'type': 'text'},
            {'field': 'total_events',        'label': 'Total Events',      'type': 'number'},
            {'field': 'total_drills',        'label': 'Drills',            'type': 'number'},
            {'field': 'total_real_events',   'label': 'Real Emergencies',  'type': 'number'},
            {'field': 'fully_compliant',     'label': 'Fully Compliant',   'type': 'number'},
            {'field': 'avg_compliance_pct',  'label': 'Avg Compliance %',  'type': 'percentage'},
            {'field': 'min_compliance_pct',  'label': 'Worst %',           'type': 'percentage'},
            {'field': 'max_compliance_pct',  'label': 'Best %',            'type': 'percentage'},
            {'field': 'avg_duration_min',    'label': 'Avg Duration (min)','type': 'number'},
            {'field': 'total_injured',       'label': 'Total Injured',     'type': 'number'},
            {'field': 'last_event_time',     'label': 'Last Event',        'type': 'datetime'},
        ]
        data = [{
            'zone_name':         r.zone_name or '',
            'total_events':      r.total_events or 0,
            'total_drills':      r.total_drills or 0,
            'total_real_events': r.total_real_events or 0,
            'fully_compliant':   r.fully_compliant or 0,
            'avg_compliance_pct':float(r.avg_compliance_pct) if r.avg_compliance_pct is not None else 0,
            'min_compliance_pct':float(r.min_compliance_pct) if r.min_compliance_pct is not None else 0,
            'max_compliance_pct':float(r.max_compliance_pct) if r.max_compliance_pct is not None else 0,
            'avg_duration_min':  float(r.avg_duration_min) if r.avg_duration_min is not None else 0,
            'total_injured':     r.total_injured or 0,
            'last_event_time':   r.last_event_time.strftime('%Y-%m-%d %H:%M') if r.last_event_time else '',
        } for r in rows]

        return {
            'columns': columns, 'data': data,
            'summary': {
                'zones_assessed':    len(data),
                'overall_avg_pct':   round(
                    sum(r['avg_compliance_pct'] for r in data) / len(data), 1
                ) if data else 0,
            },
        }

    # ==================== EMERGENCY (continued) ====================

    def emergency_lockdown_log(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Lockdown, Fire, and Gas emergency event history — enriched with zone names and initiator."""
        params: Dict[str, Any] = {}
        date_from_clause = date_to_clause = ""
        if filters.get('date_from'):
            date_from_clause = "AND e.start_time >= :date_from"
            params['date_from'] = filters['date_from']
        if filters.get('date_to'):
            date_to_clause = "AND e.start_time < CAST(:date_to AS date) + INTERVAL '1 day'"
            params['date_to'] = filters['date_to']

        rows = self.db.execute(text(f"""
            SELECT
                e.id,
                e.event_type,
                e.status,
                e.scope,
                e.start_time,
                e.end_time,
                e.reason,
                e.trigger_source,
                COALESCE(
                    (SELECT string_agg(z.name, ', ' ORDER BY z.name)
                     FROM zones z WHERE z.id = ANY(e.zone_ids)),
                    'Global'
                )                                               AS zone_names,
                COALESCE(
                    NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''),
                    u.username, 'System'
                )                                               AS initiator_name,
                EXTRACT(EPOCH FROM (COALESCE(e.end_time, now()) - e.start_time))/60 AS duration_min
            FROM emergency_event e
            LEFT JOIN auth_user u ON e.initiated_by = u.id
            WHERE e.event_type IN (0, 1, 2)   -- Lockdown, Fire, Gas
              {date_from_clause}
              {date_to_clause}
            ORDER BY e.start_time DESC
        """), params).fetchall()

        columns = [
            {'field': 'event_id',    'label': 'Event ID',       'type': 'number'},
            {'field': 'start_time',  'label': 'Start Time',     'type': 'datetime'},
            {'field': 'end_time',    'label': 'End Time',       'type': 'datetime'},
            {'field': 'event_type',  'label': 'Type',           'type': 'text'},
            {'field': 'status',      'label': 'Status',         'type': 'text'},
            {'field': 'scope',       'label': 'Scope',          'type': 'text'},
            {'field': 'zone_names',  'label': 'Zones Affected', 'type': 'text'},
            {'field': 'trigger_source','label':'Trigger Source','type': 'text'},
            {'field': 'reason',      'label': 'Reason',         'type': 'text'},
            {'field': 'initiated_by','label': 'Initiated By',   'type': 'text'},
            {'field': 'duration_min','label': 'Duration (min)', 'type': 'number'},
        ]
        data = [{
            'event_id':    r.id,
            'start_time':  r.start_time.strftime('%Y-%m-%d %H:%M:%S') if r.start_time else '',
            'end_time':    r.end_time.strftime('%Y-%m-%d %H:%M:%S') if r.end_time else '—',
            'event_type':  self._EMER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'status':      self._EMER_STATUS.get(r.status, 'Active'),
            'scope':       self._EMER_SCOPE.get(r.scope, 'Global'),
            'zone_names':  r.zone_names or 'Global',
            'trigger_source': r.trigger_source or '—',
            'reason':      r.reason or '—',
            'initiated_by':r.initiator_name or '—',
            'duration_min':round(float(r.duration_min or 0), 2),
        } for r in rows]

        active = sum(1 for r in rows if (r.status or 0) == 0)
        return {
            'columns': columns, 'data': data,
            'total': len(data),
            'summary': {
                'total_lockdowns': len(data),
                'active': active,
                'resolved': len(data) - active,
            },
        }

    def emergency_siren_activation(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Siren activations — from notification channel=5 (Siren) and emergency event actions."""
        params: Dict[str, Any] = {}
        date_from_clause = ""
        if filters.get('date_from'):
            date_from_clause = "AND e.start_time >= :date_from"
            params['date_from'] = filters['date_from']

        # Pull siren notifications (channel=5) joined with their events
        notif_rows = self.db.execute(text(f"""
            SELECT
                e.id                                            AS event_id,
                e.event_type,
                e.start_time,
                e.status,
                COALESCE(
                    (SELECT string_agg(z.name, ', ' ORDER BY z.name)
                     FROM zones z WHERE z.id = ANY(e.zone_ids)),
                    'Global'
                )                                               AS zone_names,
                e.trigger_source,
                e.reason,
                n.sent_time                                     AS siren_sent_time,
                n.status                                        AS siren_status,
                COALESCE(
                    NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''),
                    u.username, 'System'
                )                                               AS initiator_name,
                'Notification Channel'                          AS activation_source
            FROM emergency_notification n
            JOIN emergency_event e ON n.emergency_event_id = e.id
            LEFT JOIN auth_user u ON e.initiated_by = u.id
            WHERE n.channel = 5   -- SIREN channel
              {date_from_clause}
        """), params).fetchall()

        # Also pull events where actions JSONB contains siren-type entries
        action_rows = self.db.execute(text(f"""
            SELECT
                e.id                                            AS event_id,
                e.event_type,
                e.start_time,
                e.status,
                COALESCE(
                    (SELECT string_agg(z.name, ', ' ORDER BY z.name)
                     FROM zones z WHERE z.id = ANY(e.zone_ids)),
                    'Global'
                )                                               AS zone_names,
                e.trigger_source,
                e.reason,
                e.start_time                                    AS siren_sent_time,
                0                                               AS siren_status,
                COALESCE(
                    NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''),
                    u.username, 'System'
                )                                               AS initiator_name,
                'Event Action'                                  AS activation_source
            FROM emergency_event e
            LEFT JOIN auth_user u ON e.initiated_by = u.id
            WHERE e.actions IS NOT NULL
              AND jsonb_typeof(e.actions) = 'array'
              AND EXISTS (
                  SELECT 1 FROM jsonb_array_elements(e.actions) a
                  WHERE a->>'type' ILIKE '%siren%'
              )
              {date_from_clause}
        """), params).fetchall()

        # Deduplicate — prefer notification rows; add action rows whose event_id isn't already present
        seen_ids = {r.event_id for r in notif_rows}
        combined = list(notif_rows) + [r for r in action_rows if r.event_id not in seen_ids]
        # If nothing at all: fall back to all emergency events (fire/lockdown always trigger alarms)
        if not combined:
            combined = self.db.execute(text(f"""
                SELECT
                    e.id AS event_id, e.event_type, e.start_time, e.status,
                    COALESCE(
                        (SELECT string_agg(z.name, ', ' ORDER BY z.name)
                         FROM zones z WHERE z.id = ANY(e.zone_ids)),
                        'Global'
                    )                                           AS zone_names,
                    e.trigger_source, e.reason,
                    e.start_time                                AS siren_sent_time,
                    0                                           AS siren_status,
                    COALESCE(
                        NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''),
                        u.username, 'System'
                    )                                           AS initiator_name,
                    'Implicit (All Emergencies)'                AS activation_source
                FROM emergency_event e
                LEFT JOIN auth_user u ON e.initiated_by = u.id
                WHERE 1=1 {date_from_clause}
                ORDER BY e.start_time DESC
            """), params).fetchall()

        combined.sort(key=lambda r: r.start_time or r.siren_sent_time or '', reverse=True)

        columns = [
            {'field': 'event_id',         'label': 'Event ID',      'type': 'number'},
            {'field': 'activation_time',  'label': 'Activated At',  'type': 'datetime'},
            {'field': 'event_type',       'label': 'Event Type',    'type': 'text'},
            {'field': 'status',           'label': 'Event Status',  'type': 'text'},
            {'field': 'zone_names',       'label': 'Zones',         'type': 'text'},
            {'field': 'trigger_source',   'label': 'Trigger',       'type': 'text'},
            {'field': 'reason',           'label': 'Reason',        'type': 'text'},
            {'field': 'initiated_by',     'label': 'Initiated By',  'type': 'text'},
            {'field': 'siren_status',     'label': 'Siren Status',  'type': 'text'},
            {'field': 'activation_source','label': 'Source',        'type': 'text'},
        ]
        data = [{
            'event_id':          r.event_id,
            'activation_time':   (r.siren_sent_time or r.start_time).strftime('%Y-%m-%d %H:%M:%S') if (r.siren_sent_time or r.start_time) else '',
            'event_type':        self._EMER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'status':            self._EMER_STATUS.get(r.status, 'Active'),
            'zone_names':        r.zone_names or 'Global',
            'trigger_source':    r.trigger_source or '—',
            'reason':            r.reason or '—',
            'initiated_by':      r.initiator_name or '—',
            'siren_status':      self._NOTIF_STATUS.get(int(r.siren_status or 0), 'Pending'),
            'activation_source': r.activation_source or '—',
        } for r in combined]

        return {
            'columns': columns, 'data': data,
            'total': len(data),
            'summary': {'total_activations': len(data)},
        }

    def emergency_notification_delivery(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Emergency notification delivery status — enriched with event details and channel/status labels."""
        params: Dict[str, Any] = {}
        date_from_clause = date_to_clause = ""
        if filters.get('date_from'):
            date_from_clause = "AND n.sent_time >= :date_from"
            params['date_from'] = filters['date_from']
        if filters.get('date_to'):
            date_to_clause = "AND n.sent_time < CAST(:date_to AS date) + INTERVAL '1 day'"
            params['date_to'] = filters['date_to']

        rows = self.db.execute(text(f"""
            SELECT
                n.id,
                n.emergency_event_id,
                e.event_type,
                e.start_time                                    AS event_start,
                n.channel,
                n.recipient_type,
                n.recipient_addr,
                n.message,
                n.status,
                n.sent_time,
                n.delivered_time,
                n.error_msg,
                COALESCE(
                    (SELECT string_agg(z.name, ', ' ORDER BY z.name)
                     FROM zones z WHERE z.id = ANY(e.zone_ids)),
                    'Global'
                )                                               AS zone_names
            FROM emergency_notification n
            JOIN emergency_event e ON n.emergency_event_id = e.id
            WHERE 1=1
              {date_from_clause}
              {date_to_clause}
            ORDER BY n.sent_time DESC NULLS LAST, n.id DESC
        """), params).fetchall()

        columns = [
            {'field': 'notif_id',       'label': 'Notif ID',       'type': 'number'},
            {'field': 'event_id',       'label': 'Event ID',       'type': 'number'},
            {'field': 'event_type',     'label': 'Event Type',     'type': 'text'},
            {'field': 'event_start',    'label': 'Event Time',     'type': 'datetime'},
            {'field': 'zone_names',     'label': 'Zones',          'type': 'text'},
            {'field': 'channel',        'label': 'Channel',        'type': 'text'},
            {'field': 'recipient_addr', 'label': 'Recipient',      'type': 'text'},
            {'field': 'status',         'label': 'Status',         'type': 'text'},
            {'field': 'sent_time',      'label': 'Sent Time',      'type': 'datetime'},
            {'field': 'delivered_time', 'label': 'Delivered Time', 'type': 'datetime'},
            {'field': 'error_msg',      'label': 'Error',          'type': 'text'},
        ]
        data = [{
            'notif_id':       r.id,
            'event_id':       r.emergency_event_id,
            'event_type':     self._EMER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'event_start':    r.event_start.strftime('%Y-%m-%d %H:%M') if r.event_start else '',
            'zone_names':     r.zone_names or 'Global',
            'channel':        self._NOTIF_CHANNEL.get(r.channel, f'Ch {r.channel}'),
            'recipient_addr': r.recipient_addr or '—',
            'status':         self._NOTIF_STATUS.get(r.status, 'Pending'),
            'sent_time':      r.sent_time.strftime('%Y-%m-%d %H:%M:%S') if r.sent_time else '—',
            'delivered_time': r.delivered_time.strftime('%Y-%m-%d %H:%M:%S') if r.delivered_time else '—',
            'error_msg':      r.error_msg or '',
        } for r in rows]

        status_dist: Dict[str, int] = {}
        channel_dist: Dict[str, int] = {}
        for row in data:
            status_dist[row['status']]  = status_dist.get(row['status'], 0) + 1
            channel_dist[row['channel']] = channel_dist.get(row['channel'], 0) + 1
        delivered = sum(1 for r in rows if (r.status or 0) == 3)
        failed    = sum(1 for r in rows if (r.status or 0) == 2)
        return {
            'columns': columns, 'data': data,
            'total': len(data),
            'summary': {
                'total':            len(data),
                'delivered':        delivered,
                'failed':           failed,
                'pending':          len(data) - delivered - failed,
                'status_breakdown': status_dist,
                'channel_breakdown':channel_dist,
            },
        }

    def emergency_response_time(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Emergency response time metrics — event duration + panic-button response times."""
        params: Dict[str, Any] = {}
        date_from_clause = ""
        if filters.get('date_from'):
            date_from_clause = "AND e.start_time >= :date_from"
            params['date_from'] = filters['date_from']

        # Event-level response times
        event_rows = self.db.execute(text(f"""
            SELECT
                e.id,
                e.event_type,
                e.status,
                e.start_time,
                e.end_time,
                e.trigger_source,
                e.reason,
                COALESCE(
                    (SELECT string_agg(z.name, ', ' ORDER BY z.name)
                     FROM zones z WHERE z.id = ANY(e.zone_ids)),
                    'Global'
                )                                               AS zone_names,
                COALESCE(
                    NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''),
                    u.username, 'System'
                )                                               AS initiator_name,
                EXTRACT(EPOCH FROM (COALESCE(e.end_time, now()) - e.start_time))/60 AS duration_min,
                (SELECT COUNT(*) FROM emergency_panic_log p WHERE p.emergency_event_id = e.id) AS panic_count
            FROM emergency_event e
            LEFT JOIN auth_user u ON e.initiated_by = u.id
            WHERE 1=1 {date_from_clause}
            ORDER BY e.start_time DESC
        """), params).fetchall()

        # Panic-log response times (panic_time → resolved_time)
        panic_rows = self.db.execute(text(f"""
            SELECT
                p.id,
                p.emergency_event_id,
                p.panic_time,
                p.panic_type,
                p.emp_code,
                p.location,
                p.reason,
                p.resolved_time,
                COALESCE(
                    NULLIF(TRIM(ru.first_name || ' ' || ru.last_name), ''),
                    ru.username
                )                                               AS resolved_by_name,
                CASE WHEN p.resolved_time IS NOT NULL
                     THEN EXTRACT(EPOCH FROM (p.resolved_time - p.panic_time))/60
                     ELSE NULL
                END                                             AS response_min
            FROM emergency_panic_log p
            LEFT JOIN auth_user ru ON p.resolved_by = ru.id
            ORDER BY p.panic_time DESC
        """), {}).fetchall()

        columns = [
            {'field': 'event_id',       'label': 'Event ID',       'type': 'number'},
            {'field': 'start_time',     'label': 'Start Time',     'type': 'datetime'},
            {'field': 'end_time',       'label': 'End Time',       'type': 'datetime'},
            {'field': 'event_type',     'label': 'Event Type',     'type': 'text'},
            {'field': 'status',         'label': 'Status',         'type': 'text'},
            {'field': 'zone_names',     'label': 'Zones',          'type': 'text'},
            {'field': 'trigger_source', 'label': 'Trigger Source', 'type': 'text'},
            {'field': 'initiated_by',   'label': 'Initiated By',   'type': 'text'},
            {'field': 'duration_min',   'label': 'Duration (min)', 'type': 'number'},
            {'field': 'panic_count',    'label': 'Panic Triggers', 'type': 'number'},
        ]
        data = [{
            'event_id':      r.id,
            'start_time':    r.start_time.strftime('%Y-%m-%d %H:%M:%S') if r.start_time else '',
            'end_time':      r.end_time.strftime('%Y-%m-%d %H:%M:%S') if r.end_time else '—',
            'event_type':    self._EMER_EVENT_TYPE.get(r.event_type, f'Type {r.event_type}'),
            'status':        self._EMER_STATUS.get(r.status, 'Active'),
            'zone_names':    r.zone_names or 'Global',
            'trigger_source':r.trigger_source or '—',
            'initiated_by':  r.initiator_name or '—',
            'duration_min':  round(float(r.duration_min or 0), 2),
            'panic_count':   int(r.panic_count or 0),
        } for r in event_rows]

        panic_columns = [
            {'field': 'panic_id',      'label': 'Panic ID',        'type': 'number'},
            {'field': 'event_id',      'label': 'Event ID',        'type': 'number'},
            {'field': 'panic_time',    'label': 'Panic Time',      'type': 'datetime'},
            {'field': 'panic_type',    'label': 'Panic Type',      'type': 'text'},
            {'field': 'emp_code',      'label': 'Badge ID',        'type': 'text'},
            {'field': 'location',      'label': 'Location',        'type': 'text'},
            {'field': 'reason',        'label': 'Reason',          'type': 'text'},
            {'field': 'resolved_time', 'label': 'Resolved At',     'type': 'datetime'},
            {'field': 'resolved_by',   'label': 'Resolved By',     'type': 'text'},
            {'field': 'response_min',  'label': 'Response (min)',  'type': 'number'},
        ]
        panic_data = [{
            'panic_id':      p.id,
            'event_id':      p.emergency_event_id or '—',
            'panic_time':    p.panic_time.strftime('%Y-%m-%d %H:%M:%S') if p.panic_time else '',
            'panic_type':    self._PANIC_TYPE.get(p.panic_type, 'Soft (UI)'),
            'emp_code':      p.emp_code or '—',
            'location':      p.location or '—',
            'reason':        p.reason or '—',
            'resolved_time': p.resolved_time.strftime('%Y-%m-%d %H:%M:%S') if p.resolved_time else 'Unresolved',
            'resolved_by':   p.resolved_by_name or '—',
            'response_min':  round(float(p.response_min), 2) if p.response_min is not None else None,
        } for p in panic_rows]

        durations = [r['duration_min'] for r in data if r['duration_min'] > 0]
        panic_times = [p['response_min'] for p in panic_data if p['response_min'] is not None]
        return {
            'columns': columns,
            'data': data,
            'total': len(data),
            'summary': {
                'total_events':        len(data),
                'avg_duration_min':    round(sum(durations) / len(durations), 2) if durations else 0,
                'max_duration_min':    round(max(durations), 2) if durations else 0,
                'min_duration_min':    round(min(durations), 2) if durations else 0,
                'total_panic_logs':    len(panic_data),
                'avg_panic_response_min': round(sum(panic_times) / len(panic_times), 2) if panic_times else 0,
                'unresolved_panics':   sum(1 for p in panic_data if p['resolved_time'] == 'Unresolved'),
                'panic_logs':          {'columns': panic_columns, 'data': panic_data},
            },
        }

    # ==================== PAYROLL (continued) ====================

    def payroll_payslip_bulk(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk payslip listing — full salary breakdown per employee for a period."""
        period_id = filters.get('period_id') or self._latest_period_id(self.db)
        if not period_id:
            return {'columns': [], 'data': [], 'total': 0,
                    'summary': self._employee_roster_context(self.db)}

        params: Dict[str, Any] = {'pid': period_id}
        dept_clause = ""
        if filters.get('department'):
            dept_clause = "AND COALESCE(NULLIF(p.department,''), 'Unassigned') = :dept"
            params['dept'] = filters['department']

        rows = self.db.execute(text(f"""
            SELECT
                p.emp_code,
                COALESCE(p.badge_id, p.emp_code)                    AS badge_id,
                COALESCE(p.full_name,
                    TRIM(p.first_name || ' ' || p.last_name))       AS full_name,
                COALESCE(NULLIF(p.department,''), 'Unassigned')      AS department,
                COALESCE(NULLIF(p.position,''), '—')                 AS position,
                p.employment_type,
                p.personnel_type,
                s.id                                                  AS salary_id,
                COALESCE(s.basic_salary, 0)                           AS basic_salary,
                COALESCE(s.total_earnings, 0)                         AS total_earnings,
                COALESCE(s.total_deductions, 0)                       AS total_deductions,
                COALESCE(s.gross_salary, 0)                           AS gross_salary,
                COALESCE(s.net_salary, 0)                             AS net_salary,
                COALESCE(s.work_days, 0)                              AS work_days,
                COALESCE(s.present_days, 0)                           AS present_days,
                COALESCE(s.absent_days, 0)                            AS absent_days,
                COALESCE(s.leave_days, 0)                             AS leave_days,
                COALESCE(s.ot_hours, 0)                               AS ot_hours,
                COALESCE(s.late_minutes, 0)                           AS late_minutes,
                s.calc_status,
                s.is_final,
                s.calc_time,
                COALESCE(
                    NULLIF(TRIM(cu.full_name),''), cu.username
                )                                                     AS calc_by_name,
                COALESCE(
                    NULLIF(TRIM(vu.full_name),''), vu.username
                )                                                     AS verified_by_name
            FROM pay_salary s
            JOIN personnel p    ON s.emp_id = p.id
            LEFT JOIN users cu  ON s.calc_by = cu.id
            LEFT JOIN users vu  ON s.verified_by = vu.id
            WHERE s.period_id = :pid
              {dept_clause}
            ORDER BY p.department, p.full_name
        """), params).fetchall()

        columns = [
            {'field': 'badge_id',         'label': 'Badge ID',       'type': 'text'},
            {'field': 'full_name',         'label': 'Full Name',      'type': 'text'},
            {'field': 'department',        'label': 'Department',     'type': 'text'},
            {'field': 'position',          'label': 'Position',       'type': 'text'},
            {'field': 'employment_type',   'label': 'Emp. Type',      'type': 'text'},
            {'field': 'basic_salary',      'label': 'Basic',          'type': 'currency'},
            {'field': 'total_earnings',    'label': 'Earnings',       'type': 'currency'},
            {'field': 'total_deductions',  'label': 'Deductions',     'type': 'currency'},
            {'field': 'gross_salary',      'label': 'Gross',          'type': 'currency'},
            {'field': 'net_salary',        'label': 'Net',            'type': 'currency'},
            {'field': 'present_days',      'label': 'Present Days',   'type': 'number'},
            {'field': 'absent_days',       'label': 'Absent Days',    'type': 'number'},
            {'field': 'ot_hours',          'label': 'OT Hours',       'type': 'number'},
            {'field': 'calc_status',       'label': 'Status',         'type': 'text'},
            {'field': 'calc_by',           'label': 'Calculated By',  'type': 'text'},
        ]
        data = [{
            'badge_id':        r.badge_id or r.emp_code or '',
            'full_name':       r.full_name or '',
            'department':      r.department,
            'position':        r.position,
            'employment_type': r.employment_type or '',
            'basic_salary':    float(r.basic_salary),
            'total_earnings':  float(r.total_earnings),
            'total_deductions':float(r.total_deductions),
            'gross_salary':    float(r.gross_salary),
            'net_salary':      float(r.net_salary),
            'present_days':    float(r.present_days),
            'absent_days':     float(r.absent_days),
            'ot_hours':        float(r.ot_hours),
            'calc_status':     self._PAY_CALC_STATUS.get(str(r.calc_status or ''), str(r.calc_status or 'Pending')),
            'calc_by':         r.calc_by_name or '—',
        } for r in rows]

        meta = self._period_meta(self.db, period_id)
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                **meta,
                'total_employees':  len(data),
                'total_gross':      round(sum(r['gross_salary']    for r in data), 2),
                'total_net':        round(sum(r['net_salary']       for r in data), 2),
                'total_deductions': round(sum(r['total_deductions'] for r in data), 2),
                'finalized':        sum(1 for r in rows if r.is_final),
                'pending':          sum(1 for r in rows if not r.is_final),
            },
        }

    def payroll_bank_sheet(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Bank payment sheet — one row per employee with net salary for transfer."""
        period_id = filters.get('period_id') or self._latest_period_id(self.db)
        if not period_id:
            return {'columns': [], 'data': [], 'total': 0,
                    'summary': self._employee_roster_context(self.db)}

        rows = self.db.execute(text("""
            SELECT
                COALESCE(p.badge_id, p.emp_code)                    AS badge_id,
                p.emp_code,
                COALESCE(p.full_name,
                    TRIM(p.first_name || ' ' || p.last_name))       AS full_name,
                COALESCE(NULLIF(p.department,''), 'Unassigned')      AS department,
                COALESCE(NULLIF(p.position,''), '—')                 AS position,
                COALESCE(s.net_salary, 0)                            AS net_salary,
                s.calc_status,
                s.is_final
            FROM pay_salary s
            JOIN personnel p ON s.emp_id = p.id
            WHERE s.period_id = :pid
            ORDER BY p.department, p.full_name
        """), {'pid': period_id}).fetchall()

        columns = [
            {'field': 'badge_id',    'label': 'Badge ID',    'type': 'text'},
            {'field': 'full_name',   'label': 'Full Name',   'type': 'text'},
            {'field': 'department',  'label': 'Department',  'type': 'text'},
            {'field': 'position',    'label': 'Position',    'type': 'text'},
            {'field': 'net_salary',  'label': 'Net Salary',  'type': 'currency'},
            {'field': 'calc_status', 'label': 'Status',      'type': 'text'},
            {'field': 'is_final',    'label': 'Finalized',   'type': 'boolean'},
        ]
        data = [{
            'badge_id':   r.badge_id or r.emp_code,
            'full_name':  r.full_name or '',
            'department': r.department,
            'position':   r.position,
            'net_salary': float(r.net_salary),
            'calc_status':self._PAY_CALC_STATUS.get(str(r.calc_status or ''), str(r.calc_status or 'Pending')),
            'is_final':   bool(r.is_final),
        } for r in rows]

        meta = self._period_meta(self.db, period_id)
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                **meta,
                'total_employees': len(data),
                'total_net':       round(sum(r['net_salary'] for r in data), 2),
                'finalized':       sum(1 for r in rows if r.is_final),
                'pending':         sum(1 for r in rows if not r.is_final),
            },
        }

    def payroll_item_wise(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Item-wise salary breakdown — every earning and deduction line per employee."""
        period_id = filters.get('period_id') or self._latest_period_id(self.db)
        if not period_id:
            # Show pay item catalog from pay_item table even without a period
            catalog = self.db.execute(text("""
                SELECT i.item_name, i.item_type, i.calc_type,
                       COALESCE(i.amount, 0) AS amount,
                       ps.structure_name, i.is_taxable, i.is_mandatory
                FROM pay_item i
                JOIN pay_structure ps ON i.structure_id = ps.id
                ORDER BY i.item_type, i.sequence
            """)).fetchall()
            columns = [
                {'field': 'structure_name', 'label': 'Structure',  'type': 'text'},
                {'field': 'item_name',       'label': 'Item Name',  'type': 'text'},
                {'field': 'item_type',       'label': 'Type',       'type': 'text'},
                {'field': 'calc_type',       'label': 'Calc Type',  'type': 'text'},
                {'field': 'amount',          'label': 'Amount',     'type': 'currency'},
                {'field': 'is_taxable',      'label': 'Taxable',    'type': 'boolean'},
                {'field': 'is_mandatory',    'label': 'Mandatory',  'type': 'boolean'},
            ]
            data = [{
                'structure_name': r.structure_name,
                'item_name':      r.item_name,
                'item_type':      self._PAY_ITEM_TYPE.get(str(r.item_type or ''), str(r.item_type or '')),
                'calc_type':      str(r.calc_type or ''),
                'amount':         float(r.amount),
                'is_taxable':     bool(r.is_taxable),
                'is_mandatory':   bool(r.is_mandatory),
            } for r in catalog]
            ctx = self._employee_roster_context(self.db)
            ctx['catalog_items'] = len(data)
            return {'columns': columns, 'data': data, 'total': len(data), 'summary': ctx}

        rows = self.db.execute(text("""
            SELECT
                COALESCE(p.badge_id, p.emp_code)                    AS badge_id,
                COALESCE(p.full_name,
                    TRIM(p.first_name || ' ' || p.last_name))       AS full_name,
                COALESCE(NULLIF(p.department,''), 'Unassigned')      AS department,
                si.item_name,
                si.item_type,
                COALESCE(si.item_value, 0)                           AS amount,
                si.is_manual_adjustment,
                si.adjustment_reason,
                si.formula_used
            FROM pay_salary_item si
            JOIN pay_salary s  ON si.salary_id = s.id
            JOIN personnel p   ON s.emp_id = p.id
            WHERE s.period_id = :pid
            ORDER BY p.department, p.full_name, si.item_type,
                     COALESCE(si.calculation_order, 999)
        """), {'pid': period_id}).fetchall()

        columns = [
            {'field': 'badge_id',   'label': 'Badge ID',   'type': 'text'},
            {'field': 'full_name',  'label': 'Full Name',  'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
            {'field': 'item_name',  'label': 'Item',       'type': 'text'},
            {'field': 'item_type',  'label': 'Type',       'type': 'text'},
            {'field': 'amount',     'label': 'Amount',     'type': 'currency'},
            {'field': 'is_manual',  'label': 'Manual Adj.','type': 'boolean'},
            {'field': 'adj_reason', 'label': 'Adj. Reason','type': 'text'},
        ]
        data = [{
            'badge_id':   r.badge_id or '',
            'full_name':  r.full_name or '',
            'department': r.department,
            'item_name':  r.item_name or '',
            'item_type':  self._PAY_ITEM_TYPE.get(str(r.item_type or ''), str(r.item_type or '')),
            'amount':     float(r.amount),
            'is_manual':  bool(r.is_manual_adjustment),
            'adj_reason': r.adjustment_reason or '',
        } for r in rows]

        earnings    = sum(r['amount'] for r in data if r['item_type'] == 'Earning')
        deductions  = sum(r['amount'] for r in data if r['item_type'] == 'Deduction')
        meta = self._period_meta(self.db, period_id)

        # Aggregate totals by item name for management summary
        item_totals: Dict[str, float] = {}
        for r in data:
            item_totals[r['item_name']] = round(item_totals.get(r['item_name'], 0) + r['amount'], 2)

        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                **meta,
                'total_items':       len(data),
                'total_earnings':    round(earnings, 2),
                'total_deductions':  round(deductions, 2),
                'item_totals':       item_totals,
            },
        }

    def payroll_variance(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Period-over-period salary variance — highlights increases, decreases, and new/exited staff."""
        # Resolve period IDs — need two consecutive periods
        period_a = filters.get('period_a')
        period_b = filters.get('period_b')
        if not period_a or not period_b:
            periods = self.db.execute(text(
                "SELECT id, period_name FROM pay_period ORDER BY end_date DESC LIMIT 2"
            )).fetchall()
            if len(periods) >= 2:
                period_b, period_a = periods[0].id, periods[1].id  # b=current, a=previous
            else:
                ctx = self._employee_roster_context(self.db)
                ctx['message'] = 'Need at least 2 pay periods for variance analysis.'
                return {'columns': [], 'data': [], 'total': 0, 'summary': ctx}

        rows = self.db.execute(text("""
            SELECT
                COALESCE(p.badge_id, p.emp_code)                    AS badge_id,
                COALESCE(p.full_name,
                    TRIM(p.first_name || ' ' || p.last_name))       AS full_name,
                COALESCE(NULLIF(p.department,''), 'Unassigned')      AS department,
                COALESCE(sa.gross_salary, 0)                         AS gross_prev,
                COALESCE(sb.gross_salary, 0)                         AS gross_curr,
                COALESCE(sa.net_salary,   0)                         AS net_prev,
                COALESCE(sb.net_salary,   0)                         AS net_curr,
                COALESCE(sa.total_deductions, 0)                     AS ded_prev,
                COALESCE(sb.total_deductions, 0)                     AS ded_curr,
                CASE
                    WHEN sa.id IS NULL THEN 'New'
                    WHEN sb.id IS NULL THEN 'Exited'
                    ELSE 'Continued'
                END                                                   AS emp_status
            FROM personnel p
            LEFT JOIN pay_salary sa ON sa.emp_id = p.id AND sa.period_id = :pid_a
            LEFT JOIN pay_salary sb ON sb.emp_id = p.id AND sb.period_id = :pid_b
            WHERE sa.id IS NOT NULL OR sb.id IS NOT NULL
            ORDER BY p.department, p.full_name
        """), {'pid_a': period_a, 'pid_b': period_b}).fetchall()

        meta_a = self._period_meta(self.db, period_a)
        meta_b = self._period_meta(self.db, period_b)

        columns = [
            {'field': 'badge_id',      'label': 'Badge ID',          'type': 'text'},
            {'field': 'full_name',     'label': 'Full Name',         'type': 'text'},
            {'field': 'department',    'label': 'Department',        'type': 'text'},
            {'field': 'emp_status',    'label': 'Status',            'type': 'text'},
            {'field': 'net_prev',      'label': 'Net (Previous)',    'type': 'currency'},
            {'field': 'net_curr',      'label': 'Net (Current)',     'type': 'currency'},
            {'field': 'net_variance',  'label': 'Net Variance',      'type': 'currency'},
            {'field': 'variance_pct',  'label': 'Variance %',        'type': 'percentage'},
            {'field': 'gross_prev',    'label': 'Gross (Previous)',  'type': 'currency'},
            {'field': 'gross_curr',    'label': 'Gross (Current)',   'type': 'currency'},
        ]
        data = []
        for r in rows:
            net_prev = float(r.net_prev)
            net_curr = float(r.net_curr)
            variance = round(net_curr - net_prev, 2)
            var_pct  = round((variance / net_prev * 100), 2) if net_prev else 0
            data.append({
                'badge_id':     r.badge_id or '',
                'full_name':    r.full_name or '',
                'department':   r.department,
                'emp_status':   r.emp_status,
                'net_prev':     net_prev,
                'net_curr':     net_curr,
                'net_variance': variance,
                'variance_pct': var_pct,
                'gross_prev':   float(r.gross_prev),
                'gross_curr':   float(r.gross_curr),
            })

        increased  = sum(1 for r in data if r['net_variance'] > 0)
        decreased  = sum(1 for r in data if r['net_variance'] < 0)
        unchanged  = sum(1 for r in data if r['net_variance'] == 0 and r['emp_status'] == 'Continued')
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                'previous_period':   meta_a.get('period_name', ''),
                'current_period':    meta_b.get('period_name', ''),
                'total_employees':   len(data),
                'increased':         increased,
                'decreased':         decreased,
                'unchanged':         unchanged,
                'new_employees':     sum(1 for r in data if r['emp_status'] == 'New'),
                'exited_employees':  sum(1 for r in data if r['emp_status'] == 'Exited'),
                'total_net_variance':round(sum(r['net_variance'] for r in data), 2),
            },
        }

    def payroll_contractor_cost(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Contractor payroll cost analysis — contractors vs staff cost breakdown."""
        period_id = filters.get('period_id') or self._latest_period_id(self.db)

        # Always show contractor headcount (even without period data)
        contractor_roster = self.db.execute(text("""
            SELECT
                COALESCE(p.badge_id, p.emp_code)                    AS badge_id,
                COALESCE(p.full_name,
                    TRIM(p.first_name || ' ' || p.last_name))       AS full_name,
                COALESCE(NULLIF(p.department,''), 'Unassigned')      AS department,
                COALESCE(NULLIF(p.position,''), '—')                 AS position,
                p.personnel_type,
                p.employment_type,
                p.hire_date,
                p.is_active,
                p.is_pob
            FROM personnel p
            WHERE UPPER(p.personnel_type) = 'CONTRACTOR'
            ORDER BY p.department, p.full_name
        """)).fetchall()

        if not period_id:
            columns = [
                {'field': 'badge_id',      'label': 'Badge ID',     'type': 'text'},
                {'field': 'full_name',     'label': 'Full Name',    'type': 'text'},
                {'field': 'department',    'label': 'Department',   'type': 'text'},
                {'field': 'position',      'label': 'Position',     'type': 'text'},
                {'field': 'hire_date',     'label': 'Hire Date',    'type': 'date'},
                {'field': 'is_pob',        'label': 'POB',          'type': 'boolean'},
            ]
            data = [{
                'badge_id':  r.badge_id or '',
                'full_name': r.full_name or '',
                'department':r.department,
                'position':  r.position,
                'hire_date': str(r.hire_date) if r.hire_date else '',
                'is_pob':    bool(r.is_pob),
            } for r in contractor_roster]
            ctx = self._employee_roster_context(self.db)
            ctx['total_contractors'] = len(data)
            ctx['no_period_data'] = True
            return {'columns': columns, 'data': data, 'total': len(data), 'summary': ctx}

        rows = self.db.execute(text("""
            SELECT
                COALESCE(p.badge_id, p.emp_code)                    AS badge_id,
                COALESCE(p.full_name,
                    TRIM(p.first_name || ' ' || p.last_name))       AS full_name,
                COALESCE(NULLIF(p.department,''), 'Unassigned')      AS department,
                COALESCE(NULLIF(p.position,''), '—')                 AS position,
                p.personnel_type,
                COALESCE(s.basic_salary,     0)                      AS basic_salary,
                COALESCE(s.gross_salary,     0)                      AS gross_salary,
                COALESCE(s.total_deductions, 0)                      AS total_deductions,
                COALESCE(s.net_salary,       0)                      AS net_salary,
                COALESCE(s.zone_hours,       0)                      AS zone_hours,
                COALESCE(s.hazard_days,      0)                      AS hazard_days,
                s.calc_status,
                s.contractor_flag
            FROM pay_salary s
            JOIN personnel p ON s.emp_id = p.id
            WHERE s.period_id = :pid
              AND UPPER(p.personnel_type) = 'CONTRACTOR'
            ORDER BY p.department, p.full_name
        """), {'pid': period_id}).fetchall()

        columns = [
            {'field': 'badge_id',        'label': 'Badge ID',     'type': 'text'},
            {'field': 'full_name',        'label': 'Full Name',    'type': 'text'},
            {'field': 'department',       'label': 'Department',   'type': 'text'},
            {'field': 'position',         'label': 'Position',     'type': 'text'},
            {'field': 'basic_salary',     'label': 'Basic',        'type': 'currency'},
            {'field': 'gross_salary',     'label': 'Gross',        'type': 'currency'},
            {'field': 'total_deductions', 'label': 'Deductions',   'type': 'currency'},
            {'field': 'net_salary',       'label': 'Net',          'type': 'currency'},
            {'field': 'zone_hours',       'label': 'Zone Hours',   'type': 'number'},
            {'field': 'hazard_days',      'label': 'Hazard Days',  'type': 'number'},
            {'field': 'calc_status',      'label': 'Status',       'type': 'text'},
        ]
        data = [{
            'badge_id':        r.badge_id or '',
            'full_name':       r.full_name or '',
            'department':      r.department,
            'position':        r.position,
            'basic_salary':    float(r.basic_salary),
            'gross_salary':    float(r.gross_salary),
            'total_deductions':float(r.total_deductions),
            'net_salary':      float(r.net_salary),
            'zone_hours':      float(r.zone_hours),
            'hazard_days':     float(r.hazard_days),
            'calc_status':     self._PAY_CALC_STATUS.get(str(r.calc_status or ''), str(r.calc_status or 'Pending')),
        } for r in rows]

        meta = self._period_meta(self.db, period_id)
        # Dept breakdown
        dept_totals: Dict[str, float] = {}
        for r in data:
            dept_totals[r['department']] = round(dept_totals.get(r['department'], 0) + r['net_salary'], 2)

        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                **meta,
                'total_contractors':     len(data),
                'total_contractor_roster': len(contractor_roster),
                'unpaid_contractors':    len(contractor_roster) - len(data),
                'total_gross':           round(sum(r['gross_salary'] for r in data), 2),
                'total_net':             round(sum(r['net_salary']   for r in data), 2),
                'dept_breakdown':        dept_totals,
            },
        }

    # ==================== VISITOR (continued) ====================

    def visitor_host_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Visitors grouped by host employee — enriched with host dept and visit metrics."""
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        # Actual visit log data grouped by host
        log_rows = self.db.execute(text("""
            SELECT
                COALESCE(he.first_name || ' ' || TRIM(he.last_name), 'Unknown') AS host_name,
                he.emp_code                                          AS host_emp_code,
                COUNT(vl.id)                                         AS visit_count,
                COUNT(DISTINCT vl.visitor_id)                        AS unique_visitors,
                ROUND(AVG(EXTRACT(EPOCH FROM (
                    COALESCE(vl.check_out_time, now()) - vl.check_in_time
                ))/3600)::numeric, 2)                                AS avg_duration_hours,
                MAX(vl.check_in_time)                                AS last_visit
            FROM vis_visit_log vl
            LEFT JOIN personnel_employee he ON vl.host_emp_id = he.id
            WHERE DATE(vl.check_in_time) BETWEEN :df AND :dt
            GROUP BY he.id, he.first_name, he.last_name, he.emp_code
            ORDER BY visit_count DESC
        """), {'df': date_from, 'dt': date_to}).fetchall()

        # Pre-registration data grouped by host (always available)
        prereg_rows = self.db.execute(text("""
            SELECT
                COALESCE(he.first_name || ' ' || TRIM(he.last_name), 'Unknown') AS host_name,
                he.emp_code                                          AS host_emp_code,
                COUNT(pr.id)                                         AS prereg_count,
                COUNT(CASE WHEN pr.status IN (3,4) THEN 1 END)      AS prereg_fulfilled,
                MIN(pr.visit_date)                                   AS first_visit_date,
                MAX(pr.visit_date)                                   AS last_visit_date
            FROM vis_pre_registration pr
            JOIN personnel_employee he ON pr.host_emp_id = he.id
            GROUP BY he.id, he.first_name, he.last_name, he.emp_code
            ORDER BY prereg_count DESC
        """)).fetchall()

        columns = [
            {'field': 'host_name',          'label': 'Host',              'type': 'text'},
            {'field': 'host_emp_code',       'label': 'Emp Code',          'type': 'text'},
            {'field': 'visit_count',         'label': 'Total Visits',      'type': 'number'},
            {'field': 'unique_visitors',     'label': 'Unique Visitors',   'type': 'number'},
            {'field': 'avg_duration_hours',  'label': 'Avg Duration (h)',  'type': 'number'},
            {'field': 'last_visit',          'label': 'Last Visit',        'type': 'datetime'},
        ]
        data = [{
            'host_name':         r.host_name,
            'host_emp_code':     r.host_emp_code or '—',
            'visit_count':       int(r.visit_count),
            'unique_visitors':   int(r.unique_visitors),
            'avg_duration_hours':float(r.avg_duration_hours or 0),
            'last_visit':        r.last_visit.strftime('%Y-%m-%d %H:%M') if r.last_visit else '—',
        } for r in log_rows]

        prereg_summary = [{
            'host_name':       r.host_name,
            'host_emp_code':   r.host_emp_code or '—',
            'prereg_count':    int(r.prereg_count),
            'prereg_fulfilled':int(r.prereg_fulfilled),
            'first_visit_date':str(r.first_visit_date) if r.first_visit_date else '',
            'last_visit_date': str(r.last_visit_date)  if r.last_visit_date  else '',
        } for r in prereg_rows]

        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                'date_from':        date_from,
                'date_to':          date_to,
                'total_hosts':      len(data),
                'total_visits':     sum(r['visit_count'] for r in data),
                'pre_reg_summary':  prereg_summary,
            },
        }

    def visitor_blacklist_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Blacklisted visitors — from vis_blacklist table and flagged vis_visitor records."""
        # vis_blacklist table entries
        bl_rows = self.db.execute(text("""
            SELECT
                bl.id,
                COALESCE(bl.full_name, '') AS full_name,
                bl.id_no,
                COALESCE(bl.phone, '')     AS phone,
                COALESCE(bl.email, '')     AS email,
                bl.reason,
                COALESCE(
                    NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''),
                    u.username, 'System'
                )                          AS added_by_name,
                bl.added_time,
                bl.is_active,
                'blacklist_table'          AS source
            FROM vis_blacklist bl
            LEFT JOIN auth_user u ON bl.added_by = u.id
            ORDER BY bl.added_time DESC
        """)).fetchall()

        # vis_visitor records flagged as blacklisted
        flagged_rows = self.db.execute(text("""
            SELECT
                v.id,
                v.full_name,
                v.id_no,
                COALESCE(v.phone, '') AS phone,
                COALESCE(v.email, '') AS email,
                COALESCE(v.blacklist_reason, 'Flagged in visitor record') AS reason,
                'System'              AS added_by_name,
                v.updated_time        AS added_time,
                true                  AS is_active,
                'visitor_flag'        AS source
            FROM vis_visitor v
            WHERE v.is_blacklist = true
              AND NOT EXISTS (
                SELECT 1 FROM vis_blacklist bl WHERE bl.id_no = v.id_no
              )
            ORDER BY v.updated_time DESC
        """)).fetchall()

        combined = list(bl_rows) + list(flagged_rows)

        columns = [
            {'field': 'full_name',  'label': 'Full Name',  'type': 'text'},
            {'field': 'id_no',      'label': 'ID Number',  'type': 'text'},
            {'field': 'phone',      'label': 'Phone',      'type': 'text'},
            {'field': 'email',      'label': 'Email',      'type': 'text'},
            {'field': 'reason',     'label': 'Reason',     'type': 'text'},
            {'field': 'added_by',   'label': 'Added By',   'type': 'text'},
            {'field': 'added_time', 'label': 'Date Added', 'type': 'datetime'},
            {'field': 'is_active',  'label': 'Active',     'type': 'boolean'},
            {'field': 'source',     'label': 'Source',     'type': 'text'},
        ]
        data = [{
            'full_name':  r.full_name or '—',
            'id_no':      r.id_no or '—',
            'phone':      r.phone or '—',
            'email':      r.email or '—',
            'reason':     r.reason or '—',
            'added_by':   r.added_by_name,
            'added_time': r.added_time.strftime('%Y-%m-%d %H:%M') if r.added_time else '—',
            'is_active':  bool(r.is_active),
            'source':     'Blacklist Register' if r.source == 'blacklist_table' else 'Visitor Flag',
        } for r in combined]
        active = sum(1 for r in data if r['is_active'])
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                'total_blacklisted': len(data),
                'active':            active,
                'inactive':          len(data) - active,
            },
        }

    def visitor_type_summary(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Visitor type distribution — visit counts, induction compliance, avg duration per type."""
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        # Visit log breakdown by type
        log_rows = self.db.execute(text("""
            SELECT
                COALESCE(vt.type_name, 'General')                   AS visitor_type,
                COUNT(vl.id)                                         AS visit_count,
                COUNT(DISTINCT vl.visitor_id)                        AS unique_visitors,
                ROUND(AVG(EXTRACT(EPOCH FROM (
                    COALESCE(vl.check_out_time, now()) - vl.check_in_time
                ))/3600)::numeric, 2)                                AS avg_duration_hours,
                COUNT(CASE WHEN vl.status = 2 THEN 1 END)           AS overstay_count,
                COUNT(CASE WHEN vl.badge_printed THEN 1 END)        AS badges_printed
            FROM vis_visit_log vl
            JOIN vis_visitor v     ON vl.visitor_id    = v.id
            LEFT JOIN vis_type vt  ON v.visitor_type_id = vt.id
            WHERE DATE(vl.check_in_time) BETWEEN :df AND :dt
            GROUP BY COALESCE(vt.type_name, 'General')
            ORDER BY visit_count DESC
        """), {'df': date_from, 'dt': date_to}).fetchall()

        # Registered visitors by type (always available)
        registered_rows = self.db.execute(text("""
            SELECT
                COALESCE(vt.type_name, 'General')          AS visitor_type,
                COUNT(v.id)                                 AS registered_count,
                COUNT(CASE WHEN v.safety_induction_done THEN 1 END) AS induction_done,
                COUNT(CASE WHEN v.is_blacklist THEN 1 END) AS blacklisted,
                vt.induction_required,
                vt.default_visit_hours,
                vt.contractor_visitor
            FROM vis_visitor v
            LEFT JOIN vis_type vt ON v.visitor_type_id = vt.id
            GROUP BY COALESCE(vt.type_name, 'General'), vt.induction_required,
                     vt.default_visit_hours, vt.contractor_visitor
            ORDER BY registered_count DESC
        """)).fetchall()

        columns = [
            {'field': 'visitor_type',       'label': 'Visitor Type',       'type': 'text'},
            {'field': 'visit_count',        'label': 'Total Visits',       'type': 'number'},
            {'field': 'unique_visitors',    'label': 'Unique Visitors',    'type': 'number'},
            {'field': 'avg_duration_hours', 'label': 'Avg Duration (h)',   'type': 'number'},
            {'field': 'overstay_count',     'label': 'Overstays',          'type': 'number'},
            {'field': 'badges_printed',     'label': 'Badges Printed',     'type': 'number'},
        ]
        data = [{
            'visitor_type':       r.visitor_type,
            'visit_count':        int(r.visit_count),
            'unique_visitors':    int(r.unique_visitors),
            'avg_duration_hours': float(r.avg_duration_hours or 0),
            'overstay_count':     int(r.overstay_count),
            'badges_printed':     int(r.badges_printed),
        } for r in log_rows]

        # Use registered breakdown when no visit log data
        if not data:
            columns = [
                {'field': 'visitor_type',       'label': 'Visitor Type',      'type': 'text'},
                {'field': 'registered_count',   'label': 'Registered',        'type': 'number'},
                {'field': 'induction_done',     'label': 'Induction Done',    'type': 'number'},
                {'field': 'induction_pct',      'label': 'Induction %',       'type': 'percentage'},
                {'field': 'blacklisted',        'label': 'Blacklisted',       'type': 'number'},
                {'field': 'default_hours',      'label': 'Allowed Hours',     'type': 'number'},
                {'field': 'contractor',         'label': 'Contractor Type',   'type': 'boolean'},
            ]
            data = [{
                'visitor_type':     r.visitor_type,
                'registered_count': int(r.registered_count),
                'induction_done':   int(r.induction_done),
                'induction_pct':    round(int(r.induction_done) / int(r.registered_count) * 100, 1) if r.registered_count else 0,
                'blacklisted':      int(r.blacklisted),
                'default_hours':    int(r.default_visit_hours or 8),
                'contractor':       bool(r.contractor_visitor),
            } for r in registered_rows]

        chart_data = {
            'labels': [r['visitor_type'] for r in data],
            'datasets': [{'label': 'Visitors',
                          'data': [r.get('visit_count', r.get('registered_count', 0)) for r in data],
                          'backgroundColor': '#4F81BD'}],
        }
        return {
            'columns': columns, 'data': data, 'chart_data': chart_data,
            'total': len(data),
            'summary': {
                'date_from':     date_from,
                'date_to':       date_to,
                'total_visits':  sum(r.get('visit_count', 0) for r in data),
                'total_registered': sum(r.get('registered_count', 0) for r in data),
            },
        }

    def visitor_induction_status(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Visitor safety induction compliance — from vis_visitor flags and mtd_induction_record."""
        # Induction records for visitors from mtd_induction_record
        induction_rows = self.db.execute(text("""
            SELECT
                v.visitor_code,
                v.full_name                                           AS visitor_name,
                COALESCE(v.company, '')                               AS company,
                COALESCE(vt.type_name, 'General')                    AS visitor_type,
                v.safety_induction_done                               AS flag_done,
                ir.id                                                 AS record_id,
                ir.taken_date,
                ir.passed,
                ir.score,
                ir.valid_until,
                COALESCE(it.template_name, '')                       AS template_name
            FROM vis_visitor v
            LEFT JOIN vis_type vt          ON v.visitor_type_id     = vt.id
            LEFT JOIN mtd_induction_record ir ON ir.visitor_id      = v.id
            LEFT JOIN mtd_induction_template it ON ir.template_id   = it.id
            ORDER BY v.full_name, ir.taken_date DESC
        """)).fetchall()

        # Deduplicate — keep the most recent record per visitor
        seen: set = set()
        unique_rows = []
        for r in induction_rows:
            if r.visitor_code not in seen:
                seen.add(r.visitor_code)
                unique_rows.append(r)

        columns = [
            {'field': 'visitor_code',  'label': 'Visitor Code',     'type': 'text'},
            {'field': 'visitor_name',  'label': 'Visitor Name',     'type': 'text'},
            {'field': 'company',       'label': 'Company',          'type': 'text'},
            {'field': 'visitor_type',  'label': 'Type',             'type': 'text'},
            {'field': 'compliant',     'label': 'Compliant',        'type': 'boolean'},
            {'field': 'induction_done','label': 'Induction Done',   'type': 'boolean'},
            {'field': 'taken_date',    'label': 'Date Taken',       'type': 'date'},
            {'field': 'passed',        'label': 'Passed',           'type': 'boolean'},
            {'field': 'score',         'label': 'Score',            'type': 'number'},
            {'field': 'valid_until',   'label': 'Valid Until',      'type': 'date'},
            {'field': 'template',      'label': 'Template',         'type': 'text'},
        ]
        data = []
        for r in unique_rows:
            done = bool(r.flag_done) or (r.record_id is not None and bool(r.passed))
            data.append({
                'visitor_code':  r.visitor_code or '',
                'visitor_name':  r.visitor_name or '',
                'company':       r.company or '',
                'visitor_type':  r.visitor_type,
                'compliant':     done,
                'induction_done':bool(r.flag_done),
                'taken_date':    r.taken_date.strftime('%Y-%m-%d') if r.taken_date else '—',
                'passed':        bool(r.passed) if r.passed is not None else None,
                'score':         float(r.score) if r.score is not None else None,
                'valid_until':   r.valid_until.strftime('%Y-%m-%d') if r.valid_until else '—',
                'template':      r.template_name or '—',
            })

        compliant   = sum(1 for r in data if r['compliant'])
        non_compliant = len(data) - compliant
        return {
            'columns': columns, 'data': data, 'total': len(data),
            'summary': {
                'total_visitors':  len(data),
                'compliant':       compliant,
                'non_compliant':   non_compliant,
                'compliance_pct':  round(compliant / len(data) * 100, 1) if data else 0,
            },
        }

    # ==================== MEETING REPORTS ====================

    def meeting_room_utilization(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Meeting room utilization percentage"""
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        results = (
            self.db.query(
                MeetingRoom.id,
                MeetingRoom.room_name,
                MeetingRoom.capacity,
                func.count(MeetingBooking.id).label('booking_count'),
                func.sum(
                    func.extract('epoch', MeetingBooking.end_time - MeetingBooking.start_time) / 3600
                ).label('booked_hours'),
            )
            .outerjoin(MeetingBooking, (MeetingBooking.room_id == MeetingRoom.id) & (
                func.date(MeetingBooking.start_time) >= date_from
            ) & (
                func.date(MeetingBooking.end_time) <= date_to
            ))
            .group_by(MeetingRoom.id, MeetingRoom.room_name, MeetingRoom.capacity)
            .all()
        )
        columns = [
            {'field': 'room_name',     'label': 'Room',          'type': 'text'},
            {'field': 'capacity',      'label': 'Capacity',      'type': 'number'},
            {'field': 'booking_count', 'label': 'Bookings',      'type': 'number'},
            {'field': 'booked_hours',  'label': 'Booked Hours',  'type': 'number'},
        ]
        data = [{
            'room_name':     r.room_name or '',
            'capacity':      r.capacity or 0,
            'booking_count': r.booking_count or 0,
            'booked_hours':  round(float(r.booked_hours or 0), 2),
        } for r in results]
        return {
            'columns': columns, 'data': data,
            'summary': {'total_rooms': len(data), 'total_bookings': sum(r['booking_count'] for r in data)},
        }

    def meeting_booking_log(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Meeting booking history"""
        query = self.db.query(MeetingBooking)
        if filters.get('date_from'):
            query = query.filter(func.date(MeetingBooking.start_time) >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(func.date(MeetingBooking.start_time) <= filters['date_to'])

        query = query.order_by(desc(MeetingBooking.start_time))
        bookings, total = self._paginate(query)
        columns = [
            {'field': 'meeting_code',  'label': 'Code',       'type': 'text'},
            {'field': 'title',         'label': 'Title',      'type': 'text'},
            {'field': 'start_time',    'label': 'Start',      'type': 'datetime'},
            {'field': 'end_time',      'label': 'End',        'type': 'datetime'},
            {'field': 'attendee_count','label': 'Attendees',  'type': 'number'},
            {'field': 'status',        'label': 'Status',     'type': 'number'},
        ]
        data = [{
            'meeting_code':  b.meeting_code or '',
            'title':         b.title or '',
            'start_time':    b.start_time.strftime('%Y-%m-%d %H:%M') if b.start_time else '',
            'end_time':      b.end_time.strftime('%Y-%m-%d %H:%M') if b.end_time else '',
            'attendee_count':b.attendee_count or 0,
            'status':        b.status or 0,
        } for b in bookings]
        return {
            'columns': columns, 'data': data,
            'total': total,
            'summary': {'total_bookings': total},
        }

    def meeting_attendance(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Meeting attendance records"""
        query = self.db.query(MeetingAttendance)
        if filters.get('date_from'):
            query = query.filter(func.date(MeetingAttendance.check_in_time) >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(func.date(MeetingAttendance.check_in_time) <= filters['date_to'])

        query = query.order_by(desc(MeetingAttendance.check_in_time))
        records, total = self._paginate(query)
        columns = [
            {'field': 'booking_id',   'label': 'Booking ID',   'type': 'number'},
            {'field': 'check_in_time','label': 'Check In',     'type': 'datetime'},
            {'field': 'check_out_time','label': 'Check Out',   'type': 'datetime'},
            {'field': 'status',       'label': 'Status',       'type': 'number'},
        ]
        status_map = {0: 'Present', 1: 'Late', 2: 'Absent'}
        data = [{
            'booking_id':    r.booking_id or 0,
            'check_in_time': r.check_in_time.strftime('%Y-%m-%d %H:%M') if r.check_in_time else '',
            'check_out_time':r.check_out_time.strftime('%Y-%m-%d %H:%M') if r.check_out_time else '',
            'status':        status_map.get(r.status, 'Unknown'),
        } for r in records]
        return {
            'columns': columns, 'data': data,
            'total': total,
            'summary': {'total_records': total},
        }

    def meeting_noshow(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Bookings with no attendee check-ins"""
        from ..models.meeting import MeetingAttendee
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        attended_booking_ids = {
            r[0] for r in self.db.query(MeetingAttendance.booking_id).distinct().all()
        }
        bookings = (
            self.db.query(MeetingBooking)
            .filter(
                func.date(MeetingBooking.start_time) >= date_from,
                func.date(MeetingBooking.start_time) <= date_to,
                MeetingBooking.status == 3,  # completed
            )
            .all()
        )
        no_shows = [b for b in bookings if b.id not in attended_booking_ids]
        columns = [
            {'field': 'meeting_code', 'label': 'Code',     'type': 'text'},
            {'field': 'title',        'label': 'Title',    'type': 'text'},
            {'field': 'start_time',   'label': 'Start',    'type': 'datetime'},
        ]
        data = [{
            'meeting_code': b.meeting_code or '',
            'title':        b.title or '',
            'start_time':   b.start_time.strftime('%Y-%m-%d %H:%M') if b.start_time else '',
        } for b in no_shows]
        return {
            'columns': columns, 'data': data,
            'summary': {'total_no_shows': len(data)},
        }

    def meeting_minutes_status(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Meeting minutes completion status"""
        from ..models.meeting import MeetingMinutes
        date_from = filters.get('date_from', _site_today().replace(day=1).strftime('%Y-%m-%d'))
        date_to   = filters.get('date_to',   _site_today().strftime('%Y-%m-%d'))

        bookings = (
            self.db.query(MeetingBooking)
            .filter(
                func.date(MeetingBooking.start_time) >= date_from,
                func.date(MeetingBooking.start_time) <= date_to,
                MeetingBooking.status.in_([1, 3]),
            )
            .all()
        )
        minutes_map = {
            r[0] for r in self.db.query(MeetingMinutes.booking_id).distinct().all()
        }
        columns = [
            {'field': 'meeting_code',     'label': 'Code',          'type': 'text'},
            {'field': 'title',            'label': 'Title',         'type': 'text'},
            {'field': 'start_time',       'label': 'Date',          'type': 'datetime'},
            {'field': 'minutes_status',   'label': 'Minutes Filed', 'type': 'boolean'},
        ]
        data = [{
            'meeting_code':  b.meeting_code or '',
            'title':         b.title or '',
            'start_time':    b.start_time.strftime('%Y-%m-%d %H:%M') if b.start_time else '',
            'minutes_status':b.id in minutes_map,
        } for b in bookings]
        filed = sum(1 for r in data if r['minutes_status'])
        return {
            'columns': columns, 'data': data,
            'summary': {'total': len(data), 'minutes_filed': filed, 'pending': len(data) - filed},
        }

    # ==================== MTD REPORTS ====================

    def mtd_certification_expiry(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Certifications expiring within specified days"""
        days_ahead = int(filters.get('days_ahead', 60))
        cutoff = _site_today() + timedelta(days=days_ahead)

        query = (
            self.db.query(MTDCertification)
            .filter(
                MTDCertification.expiry_date.isnot(None),
                MTDCertification.expiry_date <= cutoff,
            )
            .order_by(MTDCertification.expiry_date)
        )
        if filters.get('department'):
            from ..models.mtd import MTDCertType
            query = (
                query.join(
                    MTDCertType, MTDCertification.cert_type_id == MTDCertType.id
                )
            )

        certs, total = self._paginate(query)
        columns = [
            {'field': 'emp_id',      'label': 'Employee ID',  'type': 'number'},
            {'field': 'cert_no',     'label': 'Cert Number',  'type': 'text'},
            {'field': 'cert_type',   'label': 'Cert Type',    'type': 'text'},
            {'field': 'expiry_date', 'label': 'Expiry Date',  'type': 'date'},
            {'field': 'days_left',   'label': 'Days Left',    'type': 'number'},
            {'field': 'status',      'label': 'Status',       'type': 'text'},
        ]
        today = _site_today()
        status_map = {0: 'Valid', 1: 'Expiring', 2: 'Expired'}
        data = [{
            'emp_id':      c.emp_id or 0,
            'cert_no':     c.cert_no or '',
            'cert_type':   c.cert_type.cert_name if c.cert_type else '',
            'expiry_date': c.expiry_date.strftime('%Y-%m-%d') if c.expiry_date else '',
            'days_left':   (c.expiry_date - today).days if c.expiry_date else 0,
            'status':      status_map.get(c.status, 'Unknown'),
        } for c in certs]
        return {
            'columns': columns, 'data': data,
            'total': total,
            'summary': {
                'total': total,
                'expired': sum(1 for r in data if r['days_left'] < 0),
                'expiring_soon': sum(1 for r in data if 0 <= r['days_left'] <= 30),
            },
        }

    def mtd_medical_expiry(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Medical certificates expiring within specified days"""
        days_ahead = int(filters.get('days_ahead', 60))
        cutoff = _site_today() + timedelta(days=days_ahead)

        records = (
            self.db.query(MTDMedicalRecord)
            .filter(
                MTDMedicalRecord.next_due.isnot(None),
                MTDMedicalRecord.next_due <= cutoff,
                MTDMedicalRecord.person_type == 0,  # employee
            )
            .order_by(MTDMedicalRecord.next_due)
            .all()
        )
        today = _site_today()
        columns = [
            {'field': 'emp_id',     'label': 'Employee ID', 'type': 'number'},
            {'field': 'fit_status', 'label': 'Fit Status',  'type': 'text'},
            {'field': 'next_due',   'label': 'Next Due',    'type': 'date'},
            {'field': 'days_left',  'label': 'Days Left',   'type': 'number'},
            {'field': 'doctor_name','label': 'Doctor',      'type': 'text'},
        ]
        fit_map = {0: 'Fit', 1: 'Restricted', 2: 'Unfit'}
        data = [{
            'emp_id':     r.emp_id or 0,
            'fit_status': fit_map.get(r.fit_status, 'Unknown'),
            'next_due':   r.next_due.strftime('%Y-%m-%d') if r.next_due else '',
            'days_left':  (r.next_due - today).days if r.next_due else 0,
            'doctor_name':r.doctor_name or '',
        } for r in records]
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total': len(data),
                'overdue': sum(1 for r in data if r['days_left'] < 0),
            },
        }

    def mtd_ppe_issue(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """PPE issuance records"""
        query = self.db.query(MTDPPEIssue)
        if filters.get('status') is not None:
            query = query.filter(MTDPPEIssue.status == filters['status'])
        if filters.get('date_from'):
            query = query.filter(MTDPPEIssue.issue_date >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(MTDPPEIssue.issue_date <= filters['date_to'])

        issues = query.order_by(desc(MTDPPEIssue.issue_date)).limit(500).all()
        columns = [
            {'field': 'emp_id',          'label': 'Employee ID', 'type': 'number'},
            {'field': 'ppe_type',         'label': 'PPE Type',    'type': 'text'},
            {'field': 'serial_no',        'label': 'Serial No',   'type': 'text'},
            {'field': 'issue_date',       'label': 'Issue Date',  'type': 'date'},
            {'field': 'due_return_date',  'label': 'Return Due',  'type': 'date'},
            {'field': 'status',           'label': 'Status',      'type': 'text'},
        ]
        status_map = {0: 'Issued', 1: 'Returned', 2: 'Lost', 3: 'Expired'}
        data = [{
            'emp_id':         i.emp_id or 0,
            'ppe_type':       i.ppe_type.ppe_name if i.ppe_type else '',
            'serial_no':      i.serial_no or '',
            'issue_date':     i.issue_date.strftime('%Y-%m-%d') if i.issue_date else '',
            'due_return_date':i.due_return_date.strftime('%Y-%m-%d') if i.due_return_date else '',
            'status':         status_map.get(i.status, 'Unknown'),
        } for i in issues]
        return {
            'columns': columns, 'data': data,
            'summary': {
                'total': len(data),
                'issued': sum(1 for r in data if r['status'] == 'Issued'),
            },
        }

    def mtd_induction_status(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Safety induction completion status"""
        query = self.db.query(MTDInductionRecord).filter(MTDInductionRecord.person_type == 0)
        if filters.get('date_from'):
            query = query.filter(MTDInductionRecord.taken_date >= filters['date_from'])

        records = query.order_by(desc(MTDInductionRecord.taken_date)).limit(500).all()
        columns = [
            {'field': 'emp_id',     'label': 'Employee ID', 'type': 'number'},
            {'field': 'taken_date', 'label': 'Taken Date',  'type': 'date'},
            {'field': 'passed',     'label': 'Passed',      'type': 'boolean'},
            {'field': 'score',      'label': 'Score',       'type': 'number'},
            {'field': 'valid_until','label': 'Valid Until', 'type': 'date'},
        ]
        data = [{
            'emp_id':     r.emp_id or 0,
            'taken_date': r.taken_date.strftime('%Y-%m-%d') if r.taken_date else '',
            'passed':     r.passed or False,
            'score':      r.score or 0,
            'valid_until':r.valid_until.strftime('%Y-%m-%d') if r.valid_until else '',
        } for r in records]
        passed = sum(1 for r in data if r['passed'])
        return {
            'columns': columns, 'data': data,
            'summary': {'total': len(data), 'passed': passed, 'failed': len(data) - passed},
        }

    def mtd_non_compliant(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Active employees with expired certifications"""
        expired_emp_ids = {
            r[0] for r in
            self.db.query(MTDCertification.emp_id)
            .filter(
                MTDCertification.status == 2,  # expired
                MTDCertification.emp_id.isnot(None),
            )
            .distinct()
            .all()
        }
        if not expired_emp_ids:
            return {'columns': [], 'data': [], 'summary': {'total_non_compliant': 0}}

        query = self.db.query(Personnel).filter(
            Personnel.id.in_(expired_emp_ids),
            Personnel.is_active == True,
        )
        if filters.get('department'):
            query = query.filter(Personnel.department == filters['department'])

        query = query.order_by(Personnel.department, Personnel.full_name)
        personnel, total = self._paginate(query)
        columns = [
            {'field': 'badge_id',   'label': 'Badge ID',   'type': 'text'},
            {'field': 'full_name',  'label': 'Full Name',  'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
        ]
        data = [{
            'badge_id':   p.badge_id or '',
            'full_name':  p.full_name or '',
            'department': p.department or '',
        } for p in personnel]
        return {
            'columns': columns, 'data': data,
            'total': total,
            'summary': {'total_non_compliant': total},
        }

    # ==================== SYSTEM REPORTS (continued) ====================

    def system_login_log(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Sign-in history — successful and failed (written by core.sessions.audit_login)."""
        params: Dict[str, Any] = {}
        where = "l.action IN ('login', 'login_failed')"
        if filters.get('date_from'):
            where += " AND l.created_at >= CAST(:df AS date)"
            params['df'] = filters['date_from']
        if filters.get('date_to'):
            where += " AND l.created_at < CAST(:dt AS date) + INTERVAL '1 day'"   # whole last day
            params['dt'] = filters['date_to']
        total = self.db.execute(text(f"SELECT count(*) FROM base_operationlog l WHERE {where}"), params).scalar()
        params.update(lim=self._page_size, off=(self._page - 1) * self._page_size)
        rows = self.db.execute(text(f"""
            SELECT l.created_at, l.action, l.ip_address, l.user_agent, l.remark, u.username
            FROM base_operationlog l LEFT JOIN auth_user u ON u.id = l.user_id
            WHERE {where} ORDER BY l.created_at DESC LIMIT :lim OFFSET :off
        """), params).fetchall()
        columns = [
            {'field': 'timestamp',  'label': 'Time',       'type': 'datetime'},
            {'field': 'user',       'label': 'User',       'type': 'text'},
            {'field': 'result',     'label': 'Result',     'type': 'text'},
            {'field': 'ip_address', 'label': 'IP Address', 'type': 'text'},
            {'field': 'device',     'label': 'Browser / Device', 'type': 'text'},
        ]
        data = [{
            'timestamp':  self._fmt_dt(r.created_at, '%Y-%m-%d %H:%M:%S'),
            'user':       r.username or (r.remark or '').replace('username: ', ''),
            'result':     'Success' if r.action == 'login' else 'Failed',
            'ip_address': r.ip_address or '',
            'device':     (r.user_agent or '')[:80],
        } for r in rows]
        failed = self.db.execute(text(
            f"SELECT count(*) FROM base_operationlog l WHERE {where} AND l.action = 'login_failed'"), params).scalar()
        return {'columns': columns, 'data': data, 'total': total,
                'summary': {'total_attempts': total, 'failed': failed}}

    def system_data_audit(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Data change audit log"""
        query = self.db.query(BaseOperationLog)
        if filters.get('date_from'):
            query = query.filter(BaseOperationLog.created_at >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(BaseOperationLog.created_at < _day_after(filters['date_to']))
        if filters.get('module'):
            query = query.filter(BaseOperationLog.table_name == filters['module'])

        query = query.order_by(desc(BaseOperationLog.created_at))
        logs, total = self._paginate(query)
        columns = [
            {'field': 'timestamp',  'label': 'Time',       'type': 'datetime'},
            {'field': 'user',       'label': 'User',       'type': 'text'},
            {'field': 'module',     'label': 'Module',     'type': 'text'},
            {'field': 'action',     'label': 'Action',     'type': 'text'},
            {'field': 'target',     'label': 'Target',     'type': 'text'},
            {'field': 'old_values', 'label': 'Old Values', 'type': 'text'},
            {'field': 'new_values', 'label': 'New Values', 'type': 'text'},
        ]
        data = [{
            'timestamp':  l.created_at.strftime('%Y-%m-%d %H:%M:%S') if l.created_at else '',
            'user':       l.user.username if getattr(l, 'user', None) else '',
            'module':     l.table_name or '',
            'action':     l.action or '',
            'target':     f"{l.table_name}#{l.record_id}" if l.record_id else l.table_name or '',
            'old_values': (l.old_values or '')[:100],
            'new_values': (l.new_values or '')[:100],
        } for l in logs]
        return {
            'columns': columns, 'data': data,
            'total': total,
            'summary': {'total_changes': total},
        }

    def system_license_usage(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """System resource utilization summary"""
        from ..models.device import Device
        total_users    = self.db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).scalar() or 0
        total_devices  = self.db.query(func.count(Device.id)).scalar() or 0

        columns = [
            {'field': 'resource',  'label': 'Resource', 'type': 'text'},
            {'field': 'used',      'label': 'Used',     'type': 'number'},
        ]
        data = [
            {'resource': 'Active Users',  'used': total_users},
            {'resource': 'Total Devices', 'used': total_devices},
        ]
        return {
            'columns': columns, 'data': data,
            'summary': {'active_users': total_users, 'total_devices': total_devices},
        }

    def system_api_usage(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """API usage by module"""
        # There is no "module" column (the report always crashed): derive it from the
        # request path recorded by the RBAC audit, e.g. /api/v1/zones/5 -> zones.
        params: Dict[str, Any] = {}
        where = "table_name LIKE '/api/%'"
        if filters.get('date_from'):
            where += " AND created_at >= CAST(:df AS date)"
            params['df'] = filters['date_from']
        if filters.get('date_to'):
            where += " AND created_at < CAST(:dt AS date) + INTERVAL '1 day'"
            params['dt'] = filters['date_to']
        results = self.db.execute(text(f"""
            SELECT CASE WHEN split_part(table_name, '/', 3) = 'v1' THEN split_part(table_name, '/', 4)
                        ELSE split_part(table_name, '/', 3) END AS module,
                   COUNT(*) AS call_count
            FROM base_operationlog WHERE {where}
            GROUP BY 1 ORDER BY 2 DESC
        """), params).fetchall()

        columns = [
            {'field': 'module',     'label': 'Module',      'type': 'text'},
            {'field': 'call_count', 'label': 'API Calls',   'type': 'number'},
        ]
        data = [{'module': r.module or 'Unknown', 'call_count': r.call_count or 0} for r in results]
        chart_data = {
            'labels': [r['module'] for r in data],
            'datasets': [{'label': 'API Calls', 'data': [r['call_count'] for r in data], 'backgroundColor': '#4F81BD'}],
        }
        return {
            'columns': columns, 'data': data, 'chart_data': chart_data,
            'summary': {'total_calls': sum(r['call_count'] for r in data)},
        }

    # ==================== ZONE SECURITY & AUDIT REPORTS ====================

    def zone_access_log(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete entry/exit history per zone — the primary audit trail.
        Each row = one punch event (CLOCK_IN or CLOCK_OUT).
        Dwell time is computed by pairing each CLOCK_IN with the next CLOCK_OUT
        for the same (emp_code, zone_id) combination.
        """
        from ..models.zone import Zone

        query = (
            self.db.query(ZonePersonnelTracking, Zone.name.label('zone_name'),
                          PersonnelEmployee.first_name, PersonnelEmployee.last_name)
            .outerjoin(Zone, Zone.id == ZonePersonnelTracking.zone_id)
            .outerjoin(PersonnelEmployee, PersonnelEmployee.emp_code == ZonePersonnelTracking.emp_code)
        )

        if filters.get('zone_id'):
            query = query.filter(ZonePersonnelTracking.zone_id == filters['zone_id'])
        if filters.get('emp_code'):
            query = query.filter(ZonePersonnelTracking.emp_code == filters['emp_code'])
        if filters.get('date_from'):
            query = query.filter(ZonePersonnelTracking.punch_time >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(ZonePersonnelTracking.punch_time < _day_after(filters['date_to']))

        query = query.order_by(ZonePersonnelTracking.emp_code, ZonePersonnelTracking.punch_time)
        rows, total = self._paginate(query)

        # Build dwell-time map: {(emp_code, zone_id): last CLOCK_IN time}
        dwell_map: Dict[tuple, datetime] = {}
        data = []
        for tracking, zone_name, first_name, last_name in rows:
            key = (tracking.emp_code, tracking.zone_id)
            dwell_minutes = None
            if tracking.event_type == 'CLOCK_IN':
                dwell_map[key] = tracking.punch_time
            elif tracking.event_type == 'CLOCK_OUT' and key in dwell_map:
                delta = tracking.punch_time - dwell_map.pop(key)
                dwell_minutes = int(delta.total_seconds() / 60)

            full_name = f"{first_name or ''} {last_name or ''}".strip() or tracking.emp_code
            data.append({
                'punch_time':    self._fmt_dt(tracking.punch_time),
                'emp_code':      tracking.emp_code,
                'full_name':     full_name,
                'zone_name':     zone_name or f"Zone {tracking.zone_id}",
                'event_type':    tracking.event_type,
                'device_sn':     tracking.device_sn or '',
                'dwell_minutes': dwell_minutes,
            })

        columns = [
            {'field': 'punch_time',    'label': 'Time',          'type': 'datetime'},
            {'field': 'emp_code',      'label': 'Emp Code',      'type': 'text'},
            {'field': 'full_name',     'label': 'Name',          'type': 'text'},
            {'field': 'zone_name',     'label': 'Zone',          'type': 'text'},
            {'field': 'event_type',    'label': 'Event',         'type': 'text'},
            {'field': 'device_sn',     'label': 'Device SN',     'type': 'text'},
            {'field': 'dwell_minutes', 'label': 'Dwell (min)',   'type': 'number'},
        ]
        # Chart: events per zone
        zone_counts: Dict[str, int] = {}
        for row in data:
            zone_counts[row['zone_name']] = zone_counts.get(row['zone_name'], 0) + 1
        chart_data = {
            'labels': list(zone_counts.keys()),
            'datasets': [{'label': 'Access Events', 'data': list(zone_counts.values()), 'backgroundColor': '#3B82F6'}],
        }
        return {
            'columns': columns, 'data': data, 'chart_data': chart_data,
            'total': total,
            'summary': {'total_events': total},
            'timezone': 'UTC',
        }

    def zone_person_trail(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full movement trail for one person across all zones — answers
        "who entered zone X, stole something, and left?"
        emp_code filter is required; date range is optional but strongly recommended.
        Each consecutive CLOCK_IN/CLOCK_OUT pair yields a 'visit' row with dwell time.
        """
        from ..models.zone import Zone

        emp_code = filters.get('emp_code', '').strip()
        if not emp_code:
            return {
                'columns': [], 'data': [], 'total': 0,
                'summary': {'error': 'emp_code filter is required'},
                'timezone': 'UTC',
            }

        query = (
            self.db.query(ZonePersonnelTracking, Zone.name.label('zone_name'), Zone.zone_type)
            .outerjoin(Zone, Zone.id == ZonePersonnelTracking.zone_id)
            .filter(ZonePersonnelTracking.emp_code == emp_code)
        )
        if filters.get('date_from'):
            query = query.filter(ZonePersonnelTracking.punch_time >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(ZonePersonnelTracking.punch_time < _day_after(filters['date_to']))

        query = query.order_by(ZonePersonnelTracking.punch_time)
        rows, total = self._paginate(query)

        # Collapse raw punches into visit rows
        visits = []
        pending_entry: Optional[dict] = None
        for tracking, zone_name, zone_type in rows:
            zname = zone_name or f"Zone {tracking.zone_id}"
            if tracking.event_type == 'CLOCK_IN':
                pending_entry = {
                    'zone_id':      tracking.zone_id,
                    'zone_name':    zname,
                    'zone_type':    zone_type or '',
                    'entry_time':   self._fmt_dt(tracking.punch_time),
                    'exit_time':    '',
                    'dwell_minutes': None,
                    'device_sn':    tracking.device_sn or '',
                    '_entry_dt':    tracking.punch_time,
                }
                visits.append(pending_entry)
            elif tracking.event_type == 'CLOCK_OUT':
                # Find the most recent open entry for this zone
                for visit in reversed(visits):
                    if visit['zone_id'] == tracking.zone_id and visit['exit_time'] == '':
                        visit['exit_time'] = self._fmt_dt(tracking.punch_time)
                        delta = tracking.punch_time - visit['_entry_dt']
                        visit['dwell_minutes'] = int(delta.total_seconds() / 60)
                        break
                else:
                    # Orphan exit (no matching entry in this page)
                    visits.append({
                        'zone_id':      tracking.zone_id,
                        'zone_name':    zname,
                        'zone_type':    zone_type or '',
                        'entry_time':   '',
                        'exit_time':    self._fmt_dt(tracking.punch_time),
                        'dwell_minutes': None,
                        'device_sn':    tracking.device_sn or '',
                        '_entry_dt':    None,
                    })

        # Remove internal helper key before returning
        for v in visits:
            v.pop('_entry_dt', None)

        # Fetch employee name
        emp = self.db.query(PersonnelEmployee).filter(PersonnelEmployee.emp_code == emp_code).first()
        emp_name = f"{emp.first_name or ''} {emp.last_name or ''}".strip() if emp else emp_code

        columns = [
            {'field': 'zone_name',     'label': 'Zone',         'type': 'text'},
            {'field': 'zone_type',     'label': 'Zone Type',    'type': 'text'},
            {'field': 'entry_time',    'label': 'Entry Time',   'type': 'datetime'},
            {'field': 'exit_time',     'label': 'Exit Time',    'type': 'datetime'},
            {'field': 'dwell_minutes', 'label': 'Dwell (min)',  'type': 'number'},
            {'field': 'device_sn',     'label': 'Device SN',   'type': 'text'},
        ]
        chart_data = {
            'labels': [v['zone_name'] for v in visits if v['dwell_minutes'] is not None],
            'datasets': [{'label': 'Dwell Time (min)',
                          'data': [v['dwell_minutes'] for v in visits if v['dwell_minutes'] is not None],
                          'backgroundColor': '#8B5CF6'}],
        }
        return {
            'columns': columns, 'data': visits, 'chart_data': chart_data,
            'total': total,
            'summary': {
                'emp_code': emp_code,
                'emp_name': emp_name,
                'total_punches': total,
                'zones_visited': len({v['zone_name'] for v in visits}),
            },
            'timezone': 'UTC',
        }

    def zone_current_occupancy(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Who is currently inside each zone.
        Derived from ZonePersonnelTracking: a person is "inside" if their last
        event for a given zone is CLOCK_IN (no matching CLOCK_OUT after it).
        """
        from ..models.zone import Zone

        # Subquery: last event per (emp_code, zone_id)
        latest_sq = (
            self.db.query(
                ZonePersonnelTracking.emp_code,
                ZonePersonnelTracking.zone_id,
                func.max(ZonePersonnelTracking.punch_time).label('last_punch'),
            )
            .group_by(ZonePersonnelTracking.emp_code, ZonePersonnelTracking.zone_id)
            .subquery()
        )

        # Join back to get event_type of that latest punch
        inside_query = (
            self.db.query(
                ZonePersonnelTracking.emp_code,
                ZonePersonnelTracking.zone_id,
                ZonePersonnelTracking.punch_time,
                ZonePersonnelTracking.event_type,
                Zone.name.label('zone_name'),
                Zone.zone_type,
                Zone.max_capacity,
                PersonnelEmployee.first_name,
                PersonnelEmployee.last_name,
            )
            .join(latest_sq, and_(
                ZonePersonnelTracking.emp_code == latest_sq.c.emp_code,
                ZonePersonnelTracking.zone_id  == latest_sq.c.zone_id,
                ZonePersonnelTracking.punch_time == latest_sq.c.last_punch,
            ))
            .outerjoin(Zone, Zone.id == ZonePersonnelTracking.zone_id)
            .outerjoin(PersonnelEmployee, PersonnelEmployee.emp_code == ZonePersonnelTracking.emp_code)
            .filter(ZonePersonnelTracking.event_type == 'CLOCK_IN')
            .order_by(Zone.name, ZonePersonnelTracking.emp_code)
        )

        rows, total = self._paginate(inside_query)

        # Aggregate by zone
        zone_summary: Dict[str, dict] = {}
        data = []
        for emp_code, zone_id, punch_time, event_type, zone_name, zone_type, max_cap, first_name, last_name in rows:
            zname = zone_name or f"Zone {zone_id}"
            full_name = f"{first_name or ''} {last_name or ''}".strip() or emp_code
            data.append({
                'zone_name':    zname,
                'zone_type':    zone_type or '',
                'emp_code':     emp_code,
                'full_name':    full_name,
                'entry_time':   self._fmt_dt(punch_time),
                'max_capacity': max_cap or 0,
            })
            if zname not in zone_summary:
                zone_summary[zname] = {'count': 0, 'max_capacity': max_cap or 0}
            zone_summary[zname]['count'] += 1

        columns = [
            {'field': 'zone_name',    'label': 'Zone',         'type': 'text'},
            {'field': 'zone_type',    'label': 'Zone Type',    'type': 'text'},
            {'field': 'emp_code',     'label': 'Emp Code',     'type': 'text'},
            {'field': 'full_name',    'label': 'Name',         'type': 'text'},
            {'field': 'entry_time',   'label': 'Entered At',   'type': 'datetime'},
            {'field': 'max_capacity', 'label': 'Max Capacity', 'type': 'number'},
        ]
        chart_data = {
            'labels': list(zone_summary.keys()),
            'datasets': [{'label': 'Current Occupancy',
                          'data': [z['count'] for z in zone_summary.values()],
                          'backgroundColor': '#10B981'}],
        }
        return {
            'columns': columns, 'data': data, 'chart_data': chart_data,
            'total': total,
            'summary': {
                'total_personnel_inside': total,
                'zones_occupied': len(zone_summary),
                'zone_breakdown': [{'zone': k, 'count': v['count'], 'max_capacity': v['max_capacity']}
                                   for k, v in zone_summary.items()],
            },
            'timezone': 'UTC',
        }

    def zone_security_events(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Security events from BOTH reader families, newest first:
          * ZKTeco controller (C3/inBio) taps that were REFUSED (unregistered or expired
            card, wrong hours, anti-passback, wrong PIN…) and door alarms (forced, held
            open) — access_logs written by the controller ingest;
          * ADMS terminal alarms (tamper, duress, anti-passback…) — iclock_operlog.
        """
        df, dt = self._range(filters, back_days=6)
        params: Dict[str, Any] = {'df': df, 'dt': dt}
        zone_sql = ""
        if filters.get('zone_id'):
            zone_sql = " AND zone_id = :z"
            params['z'] = int(filters['zone_id'])
        oper_labels = {1: 'Alarm', 2: 'Tamper', 3: 'Anti-passback', 4: 'Duress', 5: 'Fire unlock',
                       6: 'Emergency lock', 9: 'Door open too long'}
        rows = self.db.execute(text(f"""
            SELECT * FROM (
                SELECT a.timestamp AS t, COALESCE(a.denial_reason, 'Refused') AS what,
                       COALESCE(NULLIF(p.full_name, ''), p.emp_code, '') AS who,
                       COALESCE(a.notes, '') AS device, a.zone_id, a.direction, 'Controller' AS source
                FROM access_logs a LEFT JOIN personnel p ON p.id = a.personnel_id
                WHERE a.access_granted = FALSE
                UNION ALL
                SELECT o.event_time, 'OPER' || o.oper_event::text, COALESCE(o.admin_id, ''),
                       o.terminal_sn, t.zone_id, NULL, 'Terminal'
                FROM iclock_operlog o LEFT JOIN iclock_terminal t ON t.sn = o.terminal_sn
                WHERE o.oper_event IN (1, 2, 3, 4, 5, 6, 9)
            ) x
            WHERE t >= CAST(:df AS date) AND t < CAST(:dt AS date) + INTERVAL '1 day' {zone_sql}
            ORDER BY t DESC LIMIT 5000
        """), params).fetchall()
        zones = {z.id: z.name for z in self.db.execute(text("SELECT id, name FROM zones")).fetchall()}
        data, counts = [], {}
        for r in rows:
            what = oper_labels.get(int(r.what[4:]), r.what) if str(r.what).startswith('OPER') else r.what
            if filters.get('event_type') and str(filters['event_type']).lower() not in what.lower():
                continue
            data.append({
                'event_time': self._fmt_dt(r.t), 'event_type': what, 'person': r.who or '—',
                'reader': r.device or '—', 'zone_name': zones.get(r.zone_id, '') if r.zone_id else '',
                'direction': (r.direction or '').title(), 'source': r.source,
            })
            counts[what] = counts.get(what, 0) + 1
        columns = [
            {'field': 'event_time', 'label': 'Time', 'type': 'datetime'},
            {'field': 'event_type', 'label': 'Event', 'type': 'status'},
            {'field': 'person', 'label': 'Person / card', 'type': 'text'},
            {'field': 'reader', 'label': 'Reader', 'type': 'text'},
            {'field': 'zone_name', 'label': 'Zone', 'type': 'text'},
            {'field': 'direction', 'label': 'In / out', 'type': 'text'},
            {'field': 'source', 'label': 'Source', 'type': 'text'},
        ]
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
        return {'columns': columns, 'data': data,
                'summary': {'total_events': len(data), 'refused_taps': sum(1 for d in data if d['source'] == 'Controller'),
                            'unregistered_cards': counts.get('Unregistered card', 0),
                            'door_alarms': sum(v for k, v in counts.items() if k in ('Door forced open', 'Door held open too long', 'Door alarm'))},
                'chart_data': {'labels': [k for k, _ in top], 'datasets': [{'label': 'Events', 'data': [v for _, v in top]}]}}

    def pob_daily_manifest(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Current onboard personnel manifest — who is on the platform right now."""
        from ..models.zone import Zone
        params: Dict[str, Any] = {}
        where_clauses = ["p.is_onboard = TRUE"]

        if filters.get('department'):
            where_clauses.append("COALESCE(NULLIF(p.department,''), 'Unassigned') = :department")
            params['department'] = filters['department']
        if filters.get('company'):
            where_clauses.append("COALESCE(NULLIF(p.company,''), 'Unknown') = :company")
            params['company'] = filters['company']
        if filters.get('personnel_type'):
            where_clauses.append("p.personnel_type = :personnel_type")
            params['personnel_type'] = filters['personnel_type']
        if filters.get('zone_id'):
            where_clauses.append("p.current_zone_id = :zone_id")
            params['zone_id'] = filters['zone_id']

        where_sql = " AND ".join(where_clauses)
        rows = self.db.execute(text(f"""
            SELECT
                p.emp_code,
                COALESCE(p.badge_id, p.emp_code)                        AS badge_id,
                COALESCE(p.full_name, TRIM(p.first_name || ' ' || p.last_name)) AS full_name,
                COALESCE(NULLIF(p.department, ''), 'Unassigned')         AS department,
                COALESCE(NULLIF(p.position, ''), '—')                    AS position,
                COALESCE(NULLIF(p.company, ''), 'Unknown')               AS company,
                p.personnel_type,
                p.employment_type,
                COALESCE(z.name, 'Unknown Zone')                         AS current_zone,
                p.pob_since,
                CASE
                    WHEN p.pob_since IS NOT NULL
                    THEN ROUND(EXTRACT(EPOCH FROM (NOW() - p.pob_since)) / 86400, 1)
                    ELSE NULL
                END                                                       AS days_onboard
            FROM personnel p
            LEFT JOIN zones z ON z.id = p.current_zone_id
            WHERE {where_sql}
            ORDER BY days_onboard DESC NULLS LAST, p.full_name
        """), params).fetchall()

        total = len(rows)
        start = (self._page - 1) * self._page_size
        page_rows = rows[start:start + self._page_size]

        data = []
        by_zone: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        by_company: Dict[str, int] = {}
        total_days = 0.0
        days_count = 0

        for r in rows:
            by_zone[r.current_zone] = by_zone.get(r.current_zone, 0) + 1
            by_type[r.personnel_type or 'STAFF'] = by_type.get(r.personnel_type or 'STAFF', 0) + 1
            by_company[r.company] = by_company.get(r.company, 0) + 1
            if r.days_onboard is not None:
                total_days += float(r.days_onboard)
                days_count += 1

        for r in page_rows:
            data.append({
                'emp_code':       r.emp_code,
                'badge_id':       r.badge_id,
                'full_name':      r.full_name,
                'department':     r.department,
                'position':       r.position,
                'company':        r.company,
                'personnel_type': r.personnel_type or 'STAFF',
                'employment_type': r.employment_type or '—',
                'current_zone':   r.current_zone,
                'pob_since':      self._fmt_dt(r.pob_since),
                'days_onboard':   float(r.days_onboard) if r.days_onboard is not None else None,
            })

        columns = [
            {'field': 'badge_id',       'label': 'Badge',        'type': 'text'},
            {'field': 'full_name',       'label': 'Name',         'type': 'text'},
            {'field': 'department',      'label': 'Department',   'type': 'text'},
            {'field': 'position',        'label': 'Position',     'type': 'text'},
            {'field': 'company',         'label': 'Company',      'type': 'text'},
            {'field': 'personnel_type',  'label': 'Type',         'type': 'text'},
            {'field': 'current_zone',    'label': 'Zone',         'type': 'text'},
            {'field': 'pob_since',       'label': 'Mobilized',    'type': 'datetime'},
            {'field': 'days_onboard',    'label': 'Days Onboard', 'type': 'number'},
        ]
        chart_data = {
            'labels': list(by_zone.keys()),
            'datasets': [{'label': 'Onboard by Zone', 'data': list(by_zone.values()),
                          'backgroundColor': '#3B82F6'}],
        }
        avg_days = round(total_days / days_count, 1) if days_count else 0
        return {
            'columns': columns, 'data': data, 'total': total,
            'chart_data': chart_data,
            'summary': {
                'total_onboard': total,
                'by_zone':       by_zone,
                'by_type':       by_type,
                'by_company':    by_company,
                'avg_days_onboard': avg_days,
            },
        }

    def pob_crew_change(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """People who actually arrived on (MOBILIZE) or left (DEMOBILIZE) the site on a
        date: flights/voyages and land journeys that moved POB, and taps through a
        site-boundary zone (gate / helideck / jetty).

        It used to treat every attendance check-in as a mobilisation and every
        check-out as a demobilisation — daily shift taps, not crew changes (and with
        the F18 stamping every tap Check-Out, everyone "demobilised" daily) — while
        real arrivals and departures by helicopter or boat never appeared."""
        target_date = filters.get('date', str(_site_today()))
        change_type_filter = filters.get('change_type', '').upper()  # MOBILIZE or DEMOBILIZE
        params: Dict[str, Any] = {'d': target_date}

        moves = self.db.execute(text("""
            -- flights / voyages (POB moved when the flight departed / arrived)
            SELECT p.emp_code, me.pob_applied_at AS at,
                   CASE WHEN me.direction = 'INBOUND' THEN 'MOBILIZE' ELSE 'DEMOBILIZE' END AS change_type,
                   COALESCE(tr.identifier, 'Flight') || ': ' || ts.departure_location || ' → ' || ts.arrival_location AS via
            FROM manifest_entry me
            JOIN transport_schedule ts ON ts.id = me.schedule_id
            LEFT JOIN transport tr ON tr.id = ts.transport_id
            JOIN personnel p ON p.id = me.personnel_id
            WHERE me.pob_applied_at IS NOT NULL AND me.pob_applied_at::date = CAST(:d AS date)
            UNION ALL
            -- land journeys that crossed the site boundary
            SELECT p.emp_code, j.pob_applied_at,
                   CASE WHEN j.pob_movement = 'INBOUND' THEN 'MOBILIZE' ELSE 'DEMOBILIZE' END,
                   COALESCE(j.reference, 'Journey') || ': ' || j.origin || ' → ' || j.destination
            FROM journey_plan j
            CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(j.pob_applied_ids, '[]'::jsonb)) pid
            JOIN personnel p ON p.id = pid::int
            WHERE j.pob_applied_at IS NOT NULL AND j.pob_applied_at::date = CAST(:d AS date)
            UNION ALL
            -- taps through a site-boundary zone
            SELECT p.emp_code, al.timestamp,
                   CASE WHEN al.event_type = 'ACCESS_ENTRY' THEN 'MOBILIZE' ELSE 'DEMOBILIZE' END,
                   z.name
            FROM access_logs al
            JOIN zones z ON z.id = al.zone_id AND z.is_site_boundary = TRUE
            JOIN personnel p ON p.id = al.personnel_id
            WHERE al.event_type IN ('ACCESS_ENTRY', 'ACCESS_EXIT') AND al.timestamp::date = CAST(:d AS date)
        """), params).fetchall()
        if change_type_filter in ('MOBILIZE', 'DEMOBILIZE'):
            moves = [m for m in moves if m.change_type == change_type_filter]

        codes = list({m.emp_code for m in moves})
        personnel_map: Dict[str, Any] = {}
        if codes:
            for pr in self.db.execute(text("""
                SELECT emp_code,
                       COALESCE(full_name, TRIM(first_name || ' ' || last_name)) AS full_name,
                       COALESCE(NULLIF(department,''), 'Unassigned') AS department,
                       COALESCE(NULLIF(company,''), 'Unknown') AS company,
                       COALESCE(NULLIF(position,''), '—') AS position,
                       personnel_type
                FROM personnel WHERE emp_code = ANY(:codes)
            """), {"codes": codes}).fetchall():
                personnel_map[pr.emp_code] = pr

        data = []
        for m in moves:
            pr = personnel_map.get(m.emp_code)
            data.append({
                'emp_code':       m.emp_code,
                'full_name':      pr.full_name if pr else m.emp_code,
                'department':     pr.department if pr else '—',
                'company':        pr.company if pr else '—',
                'position':       pr.position if pr else '—',
                'personnel_type': pr.personnel_type if pr else '—',
                'change_type':    m.change_type,
                'change_time':    self._fmt_dt(m.at),
                'terminal':       m.via or '',
            })
        data.sort(key=lambda x: x['change_time'])
        mobilize_count = sum(1 for d in data if d['change_type'] == 'MOBILIZE')
        demobilize_count = len(data) - mobilize_count
        total = len(data)
        start = (self._page - 1) * self._page_size
        page_data = data[start:start + self._page_size]

        columns = [
            {'field': 'full_name',      'label': 'Name',         'type': 'text'},
            {'field': 'change_type',    'label': 'Change',       'type': 'text'},
            {'field': 'change_time',    'label': 'Time',         'type': 'datetime'},
            {'field': 'department',     'label': 'Department',   'type': 'text'},
            {'field': 'company',        'label': 'Company',      'type': 'text'},
            {'field': 'position',       'label': 'Position',     'type': 'text'},
            {'field': 'personnel_type', 'label': 'Type',         'type': 'text'},
            {'field': 'terminal',       'label': 'Via',          'type': 'text'},
        ]
        chart_data = {
            'labels': ['Mobilized', 'Demobilized'],
            'datasets': [{'label': f'Crew Change {target_date}',
                          'data': [mobilize_count, demobilize_count],
                          'backgroundColor': ['#10B981', '#EF4444']}],
        }
        return {
            'columns': columns, 'data': page_data, 'total': total,
            'chart_data': chart_data,
            'summary': {
                'date':              target_date,
                'mobilize_count':    mobilize_count,
                'demobilize_count':  demobilize_count,
                'net_change':        mobilize_count - demobilize_count,
            },
        }

    # ==================== GAP REPORTS ====================

    def pob_trend(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """POB per day over a range (pob_daily_snapshot, recorded every 15 min)."""
        df, dt = self._range(filters, back_days=29)
        rows = self.db.execute(text("""
            SELECT snap_date, pob_last, pob_peak, pob_low, by_company
            FROM pob_daily_snapshot WHERE snap_date BETWEEN CAST(:df AS date) AND CAST(:dt AS date)
            ORDER BY snap_date
        """), {'df': df, 'dt': dt}).fetchall()
        moves = {str(r.d): (int(r.arr), int(r.dep)) for r in self.db.execute(text("""
            SELECT d, SUM(arr) arr, SUM(dep) dep FROM (
              SELECT me.pob_applied_at::date d, (me.direction='INBOUND')::int arr, (me.direction='OUTBOUND')::int dep
              FROM manifest_entry me WHERE me.pob_applied_at::date BETWEEN CAST(:df AS date) AND CAST(:dt AS date)
              UNION ALL
              SELECT j.pob_applied_at::date, CASE WHEN j.pob_movement='INBOUND' THEN jsonb_array_length(COALESCE(j.pob_applied_ids,'[]')) ELSE 0 END,
                     CASE WHEN j.pob_movement='OUTBOUND' THEN jsonb_array_length(COALESCE(j.pob_applied_ids,'[]')) ELSE 0 END
              FROM journey_plan j WHERE j.pob_applied_at::date BETWEEN CAST(:df AS date) AND CAST(:dt AS date)
            ) x GROUP BY d
        """), {'df': df, 'dt': dt}).fetchall()}
        data = []
        for r in rows:
            arr, dep = moves.get(str(r.snap_date), (0, 0))
            top = sorted((r.by_company or {}).items(), key=lambda kv: -kv[1])[:3]
            data.append({'date': str(r.snap_date), 'pob': r.pob_last, 'peak': r.pob_peak, 'low': r.pob_low,
                         'arrivals': arr, 'departures': dep,
                         'top_companies': ', '.join(f"{k} {v}" for k, v in top) or '—'})
        columns = [
            {'field': 'date', 'label': 'Date', 'type': 'date'},
            {'field': 'pob', 'label': 'POB (end of day)', 'type': 'number'},
            {'field': 'peak', 'label': 'Peak', 'type': 'number'},
            {'field': 'low', 'label': 'Low', 'type': 'number'},
            {'field': 'arrivals', 'label': 'Arrivals', 'type': 'number'},
            {'field': 'departures', 'label': 'Departures', 'type': 'number'},
            {'field': 'top_companies', 'label': 'Largest companies', 'type': 'text'},
        ]
        return {'columns': columns, 'data': data,
                'chart_data': {'labels': [d['date'][5:] for d in data],
                               'datasets': [{'label': 'POB', 'data': [d['pob'] for d in data]}]},
                'summary': {'days': len(data),
                            'latest_pob': data[-1]['pob'] if data else None,
                            'highest': max((d['peak'] for d in data), default=None),
                            'average': round(sum(d['pob'] for d in data) / len(data)) if data else None}}

    def attendance_hr_sync(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Every SeamlessHR run: attendance pushed for payroll and staff pulled — with
        failures, so payroll problems are visible before pay day."""
        df, dt = self._range(filters, back_days=29)
        params: Dict[str, Any] = {'df': df, 'dt': dt}
        where = "created_at >= CAST(:df AS date) AND created_at < CAST(:dt AS date) + INTERVAL '1 day'"
        if filters.get('status'):
            where += " AND status = :st"
            params['st'] = filters['status'].lower()
        rows = self.db.execute(text(f"""
            SELECT created_at, sync_date, triggered_by, status, records_built, records_sent, records_failed, message
            FROM hr_sync_log WHERE {where} ORDER BY created_at DESC
        """), params).fetchall()
        data = [{
            'run_at': self._fmt_dt(r.created_at, '%Y-%m-%d %H:%M'),
            'kind': 'Staff pull' if (r.message or '').lower().startswith('employee pull') else 'Attendance push',
            'for_date': str(r.sync_date) if r.sync_date else '—',
            'triggered_by': r.triggered_by or '—',
            'status': (r.status or '').title(),
            'built': r.records_built or 0, 'sent': r.records_sent or 0, 'failed': r.records_failed or 0,
            'message': r.message or '',
        } for r in rows]
        columns = [
            {'field': 'run_at', 'label': 'Run at', 'type': 'datetime'},
            {'field': 'kind', 'label': 'Type', 'type': 'text'},
            {'field': 'for_date', 'label': 'For date', 'type': 'date'},
            {'field': 'status', 'label': 'Result', 'type': 'status'},
            {'field': 'sent', 'label': 'Sent', 'type': 'number'},
            {'field': 'failed', 'label': 'Failed', 'type': 'number'},
            {'field': 'triggered_by', 'label': 'By', 'type': 'text'},
            {'field': 'message', 'label': 'Message', 'type': 'text'},
        ]
        return {'columns': columns, 'data': data, 'summary': {
            'runs': len(data),
            'failed_runs': sum(1 for d in data if d['status'] in ('Error', 'Failed')),
            'records_sent': sum(d['sent'] for d in data if d['kind'] == 'Attendance push'),
            'records_failed': sum(d['failed'] for d in data if d['kind'] == 'Attendance push'),
        }}

    def ac_door_access(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Can each person get through the doors? Attendance ID (panel user ID),
        card, keypad PIN, and how many ZKTeco panels have them loaded."""
        params: Dict[str, Any] = {}
        where = "p.is_active = TRUE"
        if filters.get('department'):
            where += " AND (p.department = :dept OR d.name = :dept)"
            params['dept'] = filters['department']
        if filters.get('search'):
            where += " AND (p.full_name ILIKE :q OR p.emp_code ILIKE :q)"
            params['q'] = f"%{filters['search']}%"
        rows = self.db.execute(text(f"""
            SELECT p.emp_code, COALESCE(NULLIF(p.full_name, ''), TRIM(CONCAT(p.first_name, ' ', p.last_name))) AS name,
                   COALESCE(NULLIF(p.department, ''), d.name, '') AS dept,
                   COALESCE(p.attendance_id, '') AS att_id, p.card_number, p.door_pin_enc IS NOT NULL AS has_pin,
                   (SELECT count(*) FROM controller_user u WHERE u.emp_code = p.emp_code AND u.state = 'loaded') AS panels,
                   (SELECT count(*) FROM controller_user u WHERE u.emp_code = p.emp_code AND u.state = 'failed') AS failed
            FROM personnel p LEFT JOIN departments d ON d.id = p.department_id
            WHERE {where} ORDER BY name
        """), params).fetchall()
        n_panels = self.db.execute(text("SELECT count(*) FROM access_controllers")).scalar() or 0
        data = []
        for r in rows:
            gaps = [g for g, ok in (("Attendance ID", bool(r.att_id)), ("card", bool(r.card_number))) if not ok]
            if not gaps and n_panels and r.panels < n_panels:
                gaps.append("not on every panel" if not r.failed else "panel load failed")
            status = "Ready" if not gaps else "Missing " + ", ".join(gaps)
            if filters.get('status') == 'missing' and not gaps:
                continue
            data.append({'emp_code': r.emp_code, 'name': r.name, 'department': r.dept,
                         'attendance_id': r.att_id or '—', 'card': str(r.card_number) if r.card_number else '—',
                         'pin': 'Yes' if r.has_pin else 'No', 'panels': f"{r.panels} / {n_panels}", 'status': status})
        columns = [
            {'field': 'name', 'label': 'Name', 'type': 'text'},
            {'field': 'emp_code', 'label': 'Emp code', 'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
            {'field': 'attendance_id', 'label': 'Attendance ID', 'type': 'text'},
            {'field': 'card', 'label': 'Card', 'type': 'text'},
            {'field': 'pin', 'label': 'Door PIN', 'type': 'text'},
            {'field': 'panels', 'label': 'On panels', 'type': 'text'},
            {'field': 'status', 'label': 'Status', 'type': 'status'},
        ]
        total = len(rows)
        ready = sum(1 for d in data if d['status'] == 'Ready')
        return {'columns': columns, 'data': data, 'summary': {
            'active_staff': total, 'ready': ready,
            'without_card': sum(1 for r in rows if not r.card_number),
            'without_attendance_id': sum(1 for r in rows if not r.att_id),
            'with_pin': sum(1 for r in rows if r.has_pin)}}

    def personnel_no_pin(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Active staff without an Attendance ID: they cannot be enrolled on a reader,
        and none of their attendance can be sent to SeamlessHR for payroll."""
        params: Dict[str, Any] = {}
        where = "p.is_active = TRUE AND (p.attendance_id IS NULL OR p.attendance_id = '')"
        if filters.get('department'):
            where += " AND p.department = :dep"
            params['dep'] = filters['department']
        rows = self.db.execute(text(f"""
            SELECT p.emp_code, COALESCE(p.full_name, TRIM(p.first_name || ' ' || p.last_name)) AS name,
                   p.department, p.position, p.company, p.hr_source, p.is_onboard
            FROM personnel p WHERE {where} ORDER BY p.department NULLS LAST, name
        """), params).fetchall()
        active = self.db.execute(text("SELECT count(*) FROM personnel WHERE is_active = TRUE")).scalar() or 0
        data = [{'emp_code': r.emp_code, 'full_name': r.name, 'department': r.department or '—',
                 'position': r.position or '—', 'company': r.company or '—',
                 'source': 'SeamlessHR' if r.hr_source == 'SEAMLESSHR' else 'ApexPOB',
                 'on_board': 'Yes' if r.is_onboard else 'No'} for r in rows]
        columns = [
            {'field': 'emp_code', 'label': 'Staff code', 'type': 'text'},
            {'field': 'full_name', 'label': 'Name', 'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
            {'field': 'position', 'label': 'Position', 'type': 'text'},
            {'field': 'company', 'label': 'Company', 'type': 'text'},
            {'field': 'source', 'label': 'Record from', 'type': 'text'},
            {'field': 'on_board', 'label': 'On board', 'type': 'text'},
        ]
        return {'columns': columns, 'data': data, 'summary': {
            'without_pin': len(data), 'active_staff': active,
            'coverage_pct': round((active - len(data)) / active * 100) if active else None,
        }}

    def muster_roll_call(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Everyone expected at one muster, with their outcome and where they were."""
        ev = filters.get('event_id')
        if not ev:
            ev = self.db.execute(text("SELECT id FROM mustering_event ORDER BY start_time DESC LIMIT 1")).scalar()
        if not ev:
            return {'columns': [], 'data': [], 'summary': {}}
        params: Dict[str, Any] = {'e': ev}
        where = "ml.event_id = :e"
        st = {'safe': 1, 'missing': 0, 'injured': 2}.get((filters.get('status') or '').lower())
        if st is not None:
            where += " AND ml.status = :s"
            params['s'] = st
        rows = self.db.execute(text(f"""
            SELECT ml.emp_code, COALESCE(ml.emp_name, p.full_name) AS name, COALESCE(ml.dept_name, p.department) AS dept,
                   ml.status, ml.check_time, ml.device_alias, ml.location, ml.last_punch_area, z.name AS live_zone
            FROM mustering_log ml
            LEFT JOIN personnel p ON p.emp_code = ml.emp_code
            LEFT JOIN zones z ON z.id = p.current_zone_id
            WHERE {where} ORDER BY ml.status, name
        """), params).fetchall()
        label = {0: 'Missing', 1: 'Safe', 2: 'Injured'}
        data = [{'emp_code': r.emp_code, 'full_name': r.name or r.emp_code, 'department': r.dept or '—',
                 'status': label.get(r.status, str(r.status)),
                 'accounted_at': self._fmt_dt(r.check_time, '%Y-%m-%d %H:%M') if r.status != 0 else '',
                 'where': r.device_alias or r.location or '',
                 'last_zone': r.last_punch_area or r.live_zone or '—'} for r in rows]
        columns = [
            {'field': 'full_name', 'label': 'Name', 'type': 'text'},
            {'field': 'emp_code', 'label': 'Staff code', 'type': 'text'},
            {'field': 'department', 'label': 'Department', 'type': 'text'},
            {'field': 'status', 'label': 'Status', 'type': 'status'},
            {'field': 'accounted_at', 'label': 'Accounted at', 'type': 'datetime'},
            {'field': 'where', 'label': 'Mustered at', 'type': 'text'},
            {'field': 'last_zone', 'label': 'Last known zone', 'type': 'text'},
        ]
        return {'columns': columns, 'data': data, 'summary': {
            'event': int(ev), 'expected': len(data),
            'safe': sum(1 for d in data if d['status'] == 'Safe'),
            'missing': sum(1 for d in data if d['status'] == 'Missing'),
        }}

    # ==================== TRAVEL (flights / voyages / land journeys) ====================

    def _range(self, filters: Dict[str, Any], back_days: int = 6):
        df = filters.get('date_from') or str(_site_today() - timedelta(days=back_days))
        dt = filters.get('date_to') or str(_site_today())
        return df, dt

    def travel_flights(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Flights / voyages in a date range with passengers, weight and punctuality."""
        df, dt = self._range(filters)
        params: Dict[str, Any] = {'df': df, 'dt': dt}
        where = "ts.departure_time >= CAST(:df AS date) AND ts.departure_time < CAST(:dt AS date) + INTERVAL '1 day'"
        if filters.get('status'):
            where += " AND ts.status = :st"
            params['st'] = filters['status'].upper()
        rows = self.db.execute(text(f"""
            SELECT ts.id, tr.identifier, tr.type, ts.departure_location, ts.arrival_location,
                   ts.departure_time, ts.actual_departure_time, ts.actual_arrival_time, ts.status,
                   tr.capacity,
                   COUNT(me.id) FILTER (WHERE me.direction = 'INBOUND')  AS inbound,
                   COUNT(me.id) FILTER (WHERE me.direction = 'OUTBOUND') AS outbound,
                   COUNT(me.id) FILTER (WHERE me.status = 'CONFIRMED')   AS boarded,
                   COUNT(me.id) FILTER (WHERE me.status = 'NO_SHOW')     AS no_show
            FROM transport_schedule ts
            LEFT JOIN transport tr ON tr.id = ts.transport_id
            LEFT JOIN manifest_entry me ON me.schedule_id = ts.id
            WHERE {where}
            GROUP BY ts.id, tr.identifier, tr.type, tr.capacity
            ORDER BY ts.departure_time
        """), params).fetchall()
        kinds = {1: 'Fixed wing', 2: 'Vehicle', 3: 'Helicopter', 4: 'Vessel'}
        data = []
        for r in rows:
            delay = None
            if r.actual_departure_time and r.departure_time:
                delay = round((r.actual_departure_time - r.departure_time).total_seconds() / 60)
            data.append({
                'departure_time': self._fmt_dt(r.departure_time, '%Y-%m-%d %H:%M'),
                'transport': r.identifier or f"#{r.id}",
                'type': kinds.get(r.type, '—'),
                'route': f"{r.departure_location} → {r.arrival_location}",
                'status': (r.status or '').replace('_', ' ').title(),
                'inbound': int(r.inbound), 'outbound': int(r.outbound),
                'boarded': int(r.boarded), 'no_show': int(r.no_show),
                'seats': r.capacity or 0,
                'delay_min': delay,
            })
        columns = [
            {'field': 'departure_time', 'label': 'Departs',  'type': 'datetime'},
            {'field': 'transport',      'label': 'Transport', 'type': 'text'},
            {'field': 'type',           'label': 'Type',      'type': 'text'},
            {'field': 'route',          'label': 'Route',     'type': 'text'},
            {'field': 'status',         'label': 'Status',    'type': 'status'},
            {'field': 'inbound',        'label': 'Inbound',   'type': 'number'},
            {'field': 'outbound',       'label': 'Outbound',  'type': 'number'},
            {'field': 'boarded',        'label': 'Boarded',   'type': 'number'},
            {'field': 'no_show',        'label': 'No-show',   'type': 'number'},
            {'field': 'delay_min',      'label': 'Delay (min)', 'type': 'number'},
        ]
        departed = [d for d in data if d['delay_min'] is not None]
        on_time = sum(1 for d in departed if d['delay_min'] <= 15)
        return {'columns': columns, 'data': data, 'summary': {
            'flights': len(data),
            'passengers_boarded': sum(d['boarded'] for d in data),
            'no_shows': sum(d['no_show'] for d in data),
            'on_time_pct': round(on_time / len(departed) * 100) if departed else None,
        }}

    def travel_passengers(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Everyone manifested on a flight / voyage in the range — who travelled, when, and
        whether their POB moved (i.e. the flight actually departed / arrived)."""
        df, dt = self._range(filters)
        params: Dict[str, Any] = {'df': df, 'dt': dt}
        where = "ts.departure_time >= CAST(:df AS date) AND ts.departure_time < CAST(:dt AS date) + INTERVAL '1 day'"
        if filters.get('direction'):
            where += " AND me.direction = :dir"
            params['dir'] = filters['direction'].upper()
        if filters.get('search'):
            where += " AND (me.passenger_name ILIKE :q OR me.emp_code ILIKE :q OR COALESCE(me.company,'') ILIKE :q)"
            params['q'] = f"%{filters['search']}%"
        rows = self.db.execute(text(f"""
            SELECT me.passenger_name, me.emp_code, COALESCE(NULLIF(me.company,''), p.company) AS company,
                   p.department, me.direction, me.status, me.pob_applied_at, me.remarks,
                   ts.departure_time, ts.departure_location, ts.arrival_location, tr.identifier
            FROM manifest_entry me
            JOIN transport_schedule ts ON ts.id = me.schedule_id
            LEFT JOIN transport tr ON tr.id = ts.transport_id
            LEFT JOIN personnel p ON p.id = me.personnel_id
            WHERE {where}
            ORDER BY ts.departure_time, me.passenger_name
        """), params).fetchall()
        data = [{
            'departure_time': self._fmt_dt(r.departure_time, '%Y-%m-%d %H:%M'),
            'passenger': r.passenger_name, 'emp_code': r.emp_code or '—',
            'company': r.company or '—', 'department': r.department or '—',
            'direction': 'Arriving' if r.direction == 'INBOUND' else 'Leaving',
            'flight': f"{r.identifier or ''} {r.departure_location} → {r.arrival_location}".strip(),
            'status': {'CONFIRMED': 'Boarded', 'NO_SHOW': 'No-show', 'OFFLOADED': 'Offloaded'}.get(r.status, 'Manifested'),
            'pob_moved': self._fmt_dt(r.pob_applied_at, '%Y-%m-%d %H:%M') if r.pob_applied_at else '—',
            'remarks': r.remarks or '',
        } for r in rows]
        columns = [
            {'field': 'departure_time', 'label': 'Departs',    'type': 'datetime'},
            {'field': 'passenger',      'label': 'Passenger',  'type': 'text'},
            {'field': 'emp_code',       'label': 'Staff code', 'type': 'text'},
            {'field': 'company',        'label': 'Company',    'type': 'text'},
            {'field': 'direction',      'label': 'Direction',  'type': 'text'},
            {'field': 'flight',         'label': 'Flight / voyage', 'type': 'text'},
            {'field': 'status',         'label': 'Status',     'type': 'status'},
            {'field': 'pob_moved',      'label': 'POB updated', 'type': 'datetime'},
            {'field': 'remarks',        'label': 'Remarks',    'type': 'text'},
        ]
        return {'columns': columns, 'data': data, 'summary': {
            'passengers': len(data),
            'arriving': sum(1 for d in data if d['direction'] == 'Arriving'),
            'leaving': sum(1 for d in data if d['direction'] == 'Leaving'),
            'no_shows': sum(1 for d in data if d['status'] == 'No-show'),
        }}

    def travel_journeys(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Land journey plans in a range: route, driver, risk, approvals, status, check-ins."""
        df, dt = self._range(filters)
        params: Dict[str, Any] = {'df': df, 'dt': dt}
        where = "j.planned_departure >= CAST(:df AS date) AND j.planned_departure < CAST(:dt AS date) + INTERVAL '1 day'"
        if filters.get('status'):
            where += " AND j.status = :st"
            params['st'] = filters['status'].upper()
        rows = self.db.execute(text(f"""
            SELECT j.*, (SELECT COUNT(*) FROM journey_checkin c WHERE c.journey_id = j.id) AS checkins,
                   (SELECT COUNT(*) FROM journey_checkin c WHERE c.journey_id = j.id AND c.status = 'CONCERN') AS concerns
            FROM journey_plan j WHERE {where} ORDER BY j.planned_departure
        """), params).fetchall()
        data = [{
            'planned_departure': self._fmt_dt(r.planned_departure, '%Y-%m-%d %H:%M'),
            'reference': r.reference,
            'route': f"{r.origin} → {r.destination}",
            'driver': r.driver_name or '—',
            'vehicle': r.vehicle_reg or '—',
            'passengers': r.passenger_count or 0,
            'risk': (r.risk_level or '').title(),
            'status': (r.status or '').replace('_', ' ').title(),
            'checkins': int(r.checkins), 'concerns': int(r.concerns),
            'pob_effect': {'OUTBOUND': 'Leaving site', 'INBOUND': 'Arriving'}.get(r.pob_movement or '', '—'),
        } for r in rows]
        columns = [
            {'field': 'planned_departure', 'label': 'Departs',   'type': 'datetime'},
            {'field': 'reference',  'label': 'Ref',        'type': 'text'},
            {'field': 'route',      'label': 'Route',      'type': 'text'},
            {'field': 'driver',     'label': 'Driver',     'type': 'text'},
            {'field': 'vehicle',    'label': 'Vehicle',    'type': 'text'},
            {'field': 'passengers', 'label': 'Pax',        'type': 'number'},
            {'field': 'risk',       'label': 'Risk',       'type': 'status'},
            {'field': 'status',     'label': 'Status',     'type': 'status'},
            {'field': 'checkins',   'label': 'Check-ins',  'type': 'number'},
            {'field': 'concerns',   'label': 'Concerns',   'type': 'number'},
            {'field': 'pob_effect', 'label': 'POB effect', 'type': 'text'},
        ]
        return {'columns': columns, 'data': data, 'summary': {
            'journeys': len(data),
            'high_risk': sum(1 for d in data if d['risk'] == 'High'),
            'completed': sum(1 for d in data if d['status'] == 'Completed'),
            'concerns_reported': sum(d['concerns'] for d in data),
        }}

    def pob_rotation_overdue(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Personnel who have been onboard longer than the rotation threshold."""
        threshold_days = int(filters.get('threshold_days') or 28)
        params: Dict[str, Any] = {'threshold': threshold_days}
        where_clauses = [
            "p.is_onboard = TRUE",
            "p.pob_since IS NOT NULL",
            "EXTRACT(EPOCH FROM (NOW() - p.pob_since)) / 86400 > :threshold",
        ]
        if filters.get('department'):
            where_clauses.append("COALESCE(NULLIF(p.department,''), 'Unassigned') = :department")
            params['department'] = filters['department']
        if filters.get('company'):
            where_clauses.append("COALESCE(NULLIF(p.company,''), 'Unknown') = :company")
            params['company'] = filters['company']

        where_sql = " AND ".join(where_clauses)
        rows = self.db.execute(text(f"""
            SELECT
                p.emp_code,
                COALESCE(p.badge_id, p.emp_code) AS badge_id,
                COALESCE(p.full_name, TRIM(p.first_name || ' ' || p.last_name)) AS full_name,
                COALESCE(NULLIF(p.department,''), 'Unassigned') AS department,
                COALESCE(NULLIF(p.position,''), '—') AS position,
                COALESCE(NULLIF(p.company,''), 'Unknown') AS company,
                p.personnel_type,
                COALESCE(z.name, 'Unknown Zone') AS current_zone,
                p.pob_since,
                ROUND(EXTRACT(EPOCH FROM (NOW() - p.pob_since)) / 86400, 1) AS days_onboard,
                ROUND(EXTRACT(EPOCH FROM (NOW() - p.pob_since)) / 86400, 1) - :threshold AS days_overdue
            FROM personnel p
            LEFT JOIN zones z ON z.id = p.current_zone_id
            WHERE {where_sql}
            ORDER BY days_onboard DESC
        """), params).fetchall()

        total = len(rows)
        start = (self._page - 1) * self._page_size
        page_rows = rows[start:start + self._page_size]

        data = []
        by_dept: Dict[str, int] = {}
        critical_count = 0  # > threshold * 1.5
        for r in rows:
            by_dept[r.department] = by_dept.get(r.department, 0) + 1
            if float(r.days_onboard) > threshold_days * 1.5:
                critical_count += 1

        for r in page_rows:
            data.append({
                'badge_id':      r.badge_id,
                'full_name':     r.full_name,
                'department':    r.department,
                'position':      r.position,
                'company':       r.company,
                'personnel_type': r.personnel_type or 'STAFF',
                'current_zone':  r.current_zone,
                'pob_since':     self._fmt_dt(r.pob_since),
                'days_onboard':  float(r.days_onboard),
                'days_overdue':  float(r.days_overdue),
            })

        columns = [
            {'field': 'badge_id',      'label': 'Badge',         'type': 'text'},
            {'field': 'full_name',     'label': 'Name',          'type': 'text'},
            {'field': 'department',    'label': 'Department',    'type': 'text'},
            {'field': 'company',       'label': 'Company',       'type': 'text'},
            {'field': 'current_zone',  'label': 'Zone',          'type': 'text'},
            {'field': 'pob_since',     'label': 'Mobilized',     'type': 'datetime'},
            {'field': 'days_onboard',  'label': 'Days Onboard',  'type': 'number'},
            {'field': 'days_overdue',  'label': 'Days Overdue',  'type': 'number'},
        ]
        chart_data = {
            'labels': list(by_dept.keys()),
            'datasets': [{'label': 'Overdue by Department', 'data': list(by_dept.values()),
                          'backgroundColor': '#F59E0B'}],
        }
        return {
            'columns': columns, 'data': data, 'total': total,
            'chart_data': chart_data,
            'summary': {
                'total_overdue':   total,
                'threshold_days':  threshold_days,
                'critical_count':  critical_count,
                'by_department':   by_dept,
            },
        }

    def pob_zone_occupancy_history(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Daily check-in and check-out counts per zone over a date range."""
        date_from = filters.get('date_from', str(_site_today() - timedelta(days=6)))
        date_to   = filters.get('date_to',   str(_site_today()))
        params: Dict[str, Any] = {'df': date_from, 'dt': date_to}
        zone_clause = ""
        if filters.get('zone_id'):
            zone_clause = "AND term.zone_id = :zone_id"
            params['zone_id'] = filters['zone_id']

        # Zone movements (door / zone readers, transport arrivals) are recorded in
        # zone_personnel_tracking. This used to count ATTENDANCE punches by their In/Out
        # key at readers that have a zone — not zone entries and exits at all.
        zone_clause = zone_clause.replace("term.zone_id", "zt.zone_id")
        rows = self.db.execute(text(f"""
            SELECT
                z.id   AS zone_id,
                z.name AS zone_name,
                zt.punch_time::date AS punch_date,
                COUNT(*) FILTER (WHERE zt.event_type = 'CLOCK_IN')  AS checkin_count,
                COUNT(*) FILTER (WHERE zt.event_type = 'CLOCK_OUT') AS checkout_count,
                COUNT(DISTINCT zt.emp_code) FILTER (WHERE zt.event_type = 'CLOCK_IN') AS unique_entrants
            FROM zone_personnel_tracking zt
            JOIN zones z ON z.id = zt.zone_id
            WHERE zt.punch_time::date BETWEEN CAST(:df AS date) AND CAST(:dt AS date)
              {zone_clause}
            GROUP BY z.id, z.name, zt.punch_time::date
            ORDER BY punch_date, z.name
        """), params).fetchall()

        total = len(rows)
        start = (self._page - 1) * self._page_size
        page_rows = rows[start:start + self._page_size]

        data = []
        zone_totals: Dict[str, int] = {}
        for r in page_rows:
            data.append({
                'zone_name':      r.zone_name,
                'punch_date':     str(r.punch_date),
                'checkin_count':  int(r.checkin_count),
                'checkout_count': int(r.checkout_count),
                'unique_entrants': int(r.unique_entrants),
            })
        for r in rows:
            zone_totals[r.zone_name] = zone_totals.get(r.zone_name, 0) + int(r.checkin_count)

        columns = [
            {'field': 'zone_name',      'label': 'Zone',            'type': 'text'},
            {'field': 'punch_date',     'label': 'Date',            'type': 'text'},
            {'field': 'checkin_count',  'label': 'Check-Ins',       'type': 'number'},
            {'field': 'checkout_count', 'label': 'Check-Outs',      'type': 'number'},
            {'field': 'unique_entrants','label': 'Unique Entrants',  'type': 'number'},
        ]
        chart_data = {
            'labels': list(zone_totals.keys()),
            'datasets': [{'label': 'Total Check-Ins', 'data': list(zone_totals.values()),
                          'backgroundColor': '#6366F1'}],
        }
        return {
            'columns': columns, 'data': data, 'total': total,
            'chart_data': chart_data,
            'summary': {
                'date_range':    f'{date_from} to {date_to}',
                'by_zone':       zone_totals,
                'total_events':  sum(zone_totals.values()),
            },
        }

    def pob_headcount_by_company(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Onboard headcount broken down by company, department, and personnel type."""
        params: Dict[str, Any] = {}
        where_clauses = ["p.is_onboard = TRUE"]
        if filters.get('company'):
            where_clauses.append("COALESCE(NULLIF(p.company,''), 'Unknown') = :company")
            params['company'] = filters['company']

        where_sql = " AND ".join(where_clauses)
        rows = self.db.execute(text(f"""
            SELECT
                COALESCE(NULLIF(p.company,''), 'Unknown')               AS company,
                COALESCE(NULLIF(p.department,''), 'Unassigned')         AS department,
                COALESCE(p.personnel_type, 'STAFF')                     AS personnel_type,
                COUNT(*)                                                 AS headcount,
                COUNT(CASE WHEN p.pob_since IS NOT NULL THEN 1 END)     AS with_pob_since,
                ROUND(AVG(CASE
                    WHEN p.pob_since IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (NOW() - p.pob_since)) / 86400
                    ELSE NULL
                END), 1)                                                  AS avg_days_onboard,
                MIN(p.pob_since)                                          AS earliest_mobilization,
                MAX(p.pob_since)                                          AS latest_mobilization
            FROM personnel p
            WHERE {where_sql}
            GROUP BY company, department, personnel_type
            ORDER BY headcount DESC, company, department
        """), params).fetchall()

        total = len(rows)
        start = (self._page - 1) * self._page_size
        page_rows = rows[start:start + self._page_size]

        data = []
        by_company: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        grand_total = 0

        for r in rows:
            by_company[r.company] = by_company.get(r.company, 0) + int(r.headcount)
            by_type[r.personnel_type] = by_type.get(r.personnel_type, 0) + int(r.headcount)
            grand_total += int(r.headcount)

        for r in page_rows:
            data.append({
                'company':             r.company,
                'department':          r.department,
                'personnel_type':      r.personnel_type,
                'headcount':           int(r.headcount),
                'avg_days_onboard':    float(r.avg_days_onboard) if r.avg_days_onboard is not None else None,
                'earliest_mobilization': self._fmt_dt(r.earliest_mobilization),
                'latest_mobilization':   self._fmt_dt(r.latest_mobilization),
            })

        columns = [
            {'field': 'company',               'label': 'Company',            'type': 'text'},
            {'field': 'department',             'label': 'Department',         'type': 'text'},
            {'field': 'personnel_type',         'label': 'Type',               'type': 'text'},
            {'field': 'headcount',              'label': 'Headcount',          'type': 'number'},
            {'field': 'avg_days_onboard',       'label': 'Avg Days Onboard',   'type': 'number'},
            {'field': 'earliest_mobilization',  'label': 'Earliest Mobilized', 'type': 'datetime'},
            {'field': 'latest_mobilization',    'label': 'Latest Mobilized',   'type': 'datetime'},
        ]
        chart_data = {
            'labels': list(by_company.keys()),
            'datasets': [{'label': 'Onboard by Company', 'data': list(by_company.values()),
                          'backgroundColor': '#10B981'}],
        }
        return {
            'columns': columns, 'data': data, 'total': total,
            'chart_data': chart_data,
            'summary': {
                'grand_total_onboard': grand_total,
                'by_company':          by_company,
                'by_type':             by_type,
                'company_count':       len(by_company),
            },
        }
