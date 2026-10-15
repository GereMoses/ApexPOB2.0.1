"""
BioTime 9.5 Payroll Service with POB Extensions
Complete payroll calculation service with attendance mapping
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case, extract, Numeric, Date
import logging
import re

from ..models.payroll import (
    PayStructure, PayItem, PayStructureAssign, PayPeriod, PaySalary, PaySalaryItem,
    PayLoan, PayLoanDeduction, PayZoneAllowance, PayContractorRate, PayAttendanceMapping,
    PayCalculationLog, PayCalcStatus, PayPeriodStatus, PayLoanStatus
)
from ..models.personnel import Personnel
from ..models.department import Department
from ..models.position import Position
from ..models.vendor_contractor import VendorContract
from ..models.zone import Zone
from .payroll_formula_engine import payroll_formula_engine

logger = logging.getLogger(__name__)


class PayrollService:
    """Complete payroll calculation service"""
    
    def __init__(self, db: Session):
        self.db = db
        self.formula_engine = payroll_formula_engine
    
    def get_employee_structure(self, emp_id: int, period_date: date = None) -> Optional[PayStructure]:
        """
        Get the applicable salary structure for an employee
        
        Priority: Employee > Position > Department
        """
        if period_date is None:
            period_date = date.today()
        
        # Get employee assignments with priority
        assignments = self.db.query(PayStructureAssign).join(PayStructure).filter(
            PayStructureAssign.emp_id == emp_id,
            PayStructure.is_active == True,
            PayStructureAssign.is_active == True,
            or_(
                PayStructureAssign.effective_date.is_(None),
                PayStructureAssign.effective_date <= period_date
            ),
            or_(
                PayStructureAssign.end_date.is_(None),
                PayStructureAssign.end_date >= period_date
            )
        ).order_by(PayStructureAssign.priority.desc()).all()
        
        # Check employee-specific assignment first
        for assignment in assignments:
            if assignment.assign_type == 0:  # Employee
                return assignment.structure
        
        # Check position assignment
        emp = self.db.query(Personnel).filter(Personnel.id == emp_id).first()
        if emp and emp.position_id:
            for assignment in assignments:
                if assignment.assign_type == 2 and assignment.assign_id == emp.position_id:  # Position
                    return assignment.structure
        
        # Check department assignment
        if emp and emp.department_id:
            for assignment in assignments:
                if assignment.assign_type == 1 and assignment.assign_id == emp.department_id:  # Department
                    return assignment.structure
        
        return None
    
    def get_attendance_data(self, emp_id: int, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get attendance data for payroll calculation period
        """
        try:
            # Query attendance data from att_report (BioTime table)
            attendance_query = self.db.query(
                func.count().label('total_days'),
                func.sum(func.coalesce(func.cast(func.json_extract_path_text('att_report', 'work_time'), Numeric), 0)).label('total_work_time'),
                func.sum(func.coalesce(func.cast(func.json_extract_path_text('att_report', 'ot_minutes'), Numeric), 0)).label('total_ot_minutes'),
                func.sum(func.coalesce(func.cast(func.json_extract_path_text('att_report', 'late_minutes'), Numeric), 0)).label('total_late_minutes'),
                func.sum(func.coalesce(func.cast(func.json_extract_path_text('att_report', 'leave_days'), Numeric), 0)).label('total_leave_days'),
                func.sum(func.coalesce(func.cast(func.json_extract_path_text('att_report', 'absent_days'), Numeric), 0)).label('total_absent_days'),
                func.count(func.distinct(func.json_extract_path_text('att_report', 'area_id'))).label('areas_worked')
            ).filter(
                func.json_extract_path_text('att_report', 'emp_id') == str(emp_id),
                func.cast(func.json_extract_path_text('att_report', 'att_date'), Date) >= start_date,
                func.cast(func.json_extract_path_text('att_report', 'att_date'), Date) <= end_date
            ).first()
            
            # Get zone-specific data for POB extensions
            zone_data = self.db.query(
                func.json_extract_path_text('att_report', 'area_id').label('area_id'),
                func.sum(func.coalesce(func.cast(func.json_extract_path_text('att_report', 'work_time'), Numeric), 0)).label('zone_work_time'),
                func.sum(func.coalesce(func.cast(func.json_extract_path_text('att_report', 'night_hours'), Numeric), 0)).label('zone_night_hours'),
                func.count().label('zone_days')
            ).filter(
                func.json_extract_path_text('att_report', 'emp_id') == str(emp_id),
                func.cast(func.json_extract_path_text('att_report', 'att_date'), Date) >= start_date,
                func.cast(func.json_extract_path_text('att_report', 'att_date'), Date) <= end_date,
                func.json_extract_path_text('att_report', 'area_id').isnot(None)
            ).group_by(func.json_extract_path_text('att_report', 'area_id')).all()
            
            # Calculate derived values
            work_days = attendance_query.total_days or 0
            present_days = work_days - (attendance_query.total_absent_days or 0)
            ot_hours = (attendance_query.total_ot_minutes or 0) / 60
            
            # Zone calculations for POB
            zone_hours = 0
            night_hours = 0
            hazard_days = 0
            
            for zone_row in zone_data:
                zone_hours += zone_row.zone_work_time or 0
                night_hours += zone_row.zone_night_hours or 0
                
                # Check if zone is hazardous
                area_id = zone_row.area_id
                if area_id:
                    zone = self.db.query(Zone).filter(Zone.id == int(area_id)).first()
                    if zone and getattr(zone, 'is_hazardous', False):
                        hazard_days += zone_row.zone_days or 0
            
            return {
                'work_days': float(work_days),
                'present_days': float(present_days),
                'absent_days': float(attendance_query.total_absent_days or 0),
                'leave_days': float(attendance_query.total_leave_days or 0),
                'work_hours': float(attendance_query.total_work_time or 0),
                'ot_hours': float(ot_hours),
                'late_minutes': int(attendance_query.total_late_minutes or 0),
                'zone_hours': float(zone_hours),
                'night_hours': float(night_hours),
                'hazard_days': float(hazard_days),
                'areas_worked': int(attendance_query.areas_worked or 0),
                'zone_breakdown': [
                    {
                        'area_id': row.area_id,
                        'work_time': float(row.zone_work_time or 0),
                        'night_hours': float(row.zone_night_hours or 0),
                        'days': int(row.zone_days or 0)
                    }
                    for row in zone_data
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting attendance data for emp {emp_id}: {str(e)}")
            return {
                'work_days': 0, 'present_days': 0, 'absent_days': 0, 'leave_days': 0,
                'work_hours': 0, 'ot_hours': 0, 'late_minutes': 0,
                'zone_hours': 0, 'night_hours': 0, 'hazard_days': 0,
                'areas_worked': 0, 'zone_breakdown': []
            }
    
    def calculate_salary(self, period_id: int, emp_id: int, 
                         force_recalc: bool = False) -> Dict[str, Any]:
        """
        Calculate salary for an employee for a specific period
        """
        result = {
            'success': False,
            'salary_id': None,
            'error': None,
            'calculation_details': {}
        }
        
        try:
            # Get period
            period = self.db.query(PayPeriod).filter(PayPeriod.id == period_id).first()
            if not period:
                result['error'] = 'Pay period not found'
                return result
            
            # Check if period allows calculation
            if period.status == PayPeriodStatus.CLOSED and not force_recalc:
                result['error'] = 'Period is closed - cannot recalculate'
                return result
            
            # Get employee
            emp = self.db.query(Personnel).filter(Personnel.id == emp_id).first()
            if not emp:
                result['error'] = 'Employee not found'
                return result
            
            # Get salary structure
            structure = self.get_employee_structure(emp_id, period.start_date)
            if not structure:
                result['error'] = 'No salary structure assigned to employee'
                return result
            
            # Check if salary already exists
            existing_salary = self.db.query(PaySalary).filter(
                PaySalary.period_id == period_id,
                PaySalary.emp_id == emp_id
            ).first()
            
            if existing_salary and not force_recalc:
                result['salary_id'] = existing_salary.id
                result['success'] = True
                result['calculation_details'] = self._get_salary_breakdown(existing_salary)
                return result
            
            # Get attendance data
            attendance_data = self.get_attendance_data(emp_id, period.start_date, period.end_date)
            
            # Get contractor rates if applicable
            contractor_rates = None
            if emp.personnel_type == 'CONTRACTOR':
                contractor_rates = self.db.query(PayContractorRate).filter(
                    PayContractorRate.vendor_id == emp.vendor_id,
                    or_(
                        PayContractorRate.position_id == emp.position_id,
                        PayContractorRate.position_id.is_(None)
                    ),
                    PayContractorRate.is_active == True,
                    or_(
                        PayContractorRate.effective_date.is_(None),
                        PayContractorRate.effective_date <= period.start_date
                    ),
                    or_(
                        PayContractorRate.end_date.is_(None),
                        PayContractorRate.end_date >= period.end_date
                    )
                ).order_by(PayContractorRate.position_id.desc().nullslast()).first()
            
            # Calculate salary items
            salary_items = []
            total_earnings = Decimal('0')
            total_deductions = Decimal('0')
            
            # Get pay items from structure
            pay_items = self.db.query(PayItem).filter(
                PayItem.structure_id == structure.id
            ).order_by(PayItem.sequence).all()
            
            earlier_items: Dict[str, float] = {}   # e.g. {"HRA": 400.0} for later formulas
            for item in pay_items:
                item_result = self._calculate_pay_item(
                    item, attendance_data, emp, contractor_rates, structure, earlier_items
                )
                
                if item_result['success']:
                    salary_items.append(item_result)
                    key = re.sub(r'\W', '_', item.item_name or '')
                    if key.isidentifier():
                        earlier_items[key] = float(item_result['value'])
                    
                    if item.item_type == 'earning':
                        total_earnings += Decimal(str(item_result['value']))
                    else:
                        total_deductions += Decimal(str(item_result['value']))
                else:
                    # A pay item that cannot be calculated must stop this payslip:
                    # skipping a failed deduction (e.g. Tax) silently overpays.
                    self.db.rollback()
                    result['error'] = f"Pay item '{item.item_name}' could not be calculated: {item_result['error']}"
                    logger.error("Payslip for emp %s stopped: %s", emp_id, result['error'])
                    return result
            
            # Calculate POB zone allowances
            zone_allowances = self._calculate_zone_allowances(
                structure.id, attendance_data, emp
            )
            for allowance in zone_allowances:
                total_earnings += Decimal(str(allowance['value']))
                salary_items.append(allowance)
            
            # Calculate loan deductions
            loan_deductions = self._calculate_loan_deductions(emp_id, period_id)
            for deduction in loan_deductions:
                total_deductions += Decimal(str(deduction['value']))
                salary_items.append(deduction)
            
            # Calculate totals
            gross_salary = total_earnings
            net_salary = gross_salary - total_deductions
            
            # Create or update salary record
            if existing_salary:
                salary = existing_salary
                # Remove existing items
                self.db.query(PaySalaryItem).filter(
                    PaySalaryItem.salary_id == salary.id
                ).delete()
            else:
                salary = PaySalary(
                    period_id=period_id,
                    emp_id=emp_id,
                    structure_id=structure.id
                )
                self.db.add(salary)
                self.db.flush()  # Get the ID
            
            # Update salary record
            salary.basic_salary = contractor_rates.monthly_rate if contractor_rates else Decimal('20000')  # Default
            salary.work_days = attendance_data['work_days']
            salary.present_days = attendance_data['present_days']
            salary.ot_hours = attendance_data['ot_hours']
            salary.late_minutes = attendance_data['late_minutes']
            salary.leave_days = attendance_data['leave_days']
            salary.absent_days = attendance_data['absent_days']
            salary.gross_salary = float(gross_salary)
            salary.total_earnings = float(total_earnings)
            salary.total_deductions = float(total_deductions)
            salary.net_salary = float(net_salary)
            salary.zone_hours = attendance_data['zone_hours']
            salary.night_hours = attendance_data['night_hours']
            salary.hazard_days = attendance_data['hazard_days']
            salary.contractor_flag = emp.personnel_type == 'CONTRACTOR'
            salary.calc_status = PayCalcStatus.CALCULATED
            salary.calc_time = datetime.utcnow()
            
            # Create salary item records
            for item_data in salary_items:
                salary_item = PaySalaryItem(
                    salary_id=salary.id,
                    item_id=item_data.get('item_id'),
                    item_name=item_data['name'],
                    item_value=float(item_data['value']),
                    item_type=item_data['type'],
                    formula_used=item_data.get('formula_used'),
                    source_value=item_data.get('source_value'),
                    calculation_order=item_data.get('sequence', 0),
                    is_manual_adjustment=item_data.get('is_manual_adjustment', False),
                    adjustment_reason=item_data.get('adjustment_reason')
                )
                self.db.add(salary_item)
            
            # Log calculation
            self._log_calculation(period_id, emp_id, 'SALARY', {
                'attendance_data': attendance_data,
                'structure_id': structure.id,
                'gross_salary': float(gross_salary),
                'net_salary': float(net_salary),
                'items_count': len(salary_items)
            }, True)
            
            self.db.commit()
            
            result['success'] = True
            result['salary_id'] = salary.id
            result['calculation_details'] = self._get_salary_breakdown(salary)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error calculating salary for emp {emp_id}: {str(e)}")
            result['error'] = str(e)
            
            # Log failed calculation
            self._log_calculation(period_id, emp_id, 'SALARY', {'error': str(e)}, False)
        
        return result
    
    def _calculate_pay_item(self, item: PayItem, attendance_data: Dict[str, Any],
                           emp: Personnel, contractor_rates: Optional[PayContractorRate],
                           structure: PayStructure,
                           earlier_items: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Calculate a single payroll item"""
        
        result = {
            'success': False,
            'name': item.item_name,
            'value': 0,
            'type': item.item_type.value,
            'formula_used': None,
            'source_value': None,
            'sequence': item.sequence,
            'error': None
        }
        
        try:
            if item.calc_type == 'fixed':
                # Fixed amount
                result['value'] = float(item.amount or 0)
                
            elif item.calc_type == 'attendance':
                # Attendance-based calculation
                attendance_field = item.attendance_field
                source_value = attendance_data.get(attendance_field, 0)
                rate = float(item.rate or 1.0)
                
                result['value'] = source_value * rate
                result['source_value'] = source_value
                
            elif item.calc_type == 'formula':
                # Formula-based calculation
                # Prepare variables for formula
                variables = {
                    'Basic': float(contractor_rates.monthly_rate if contractor_rates else 20000),
                    'BasicSalary': float(contractor_rates.monthly_rate if contractor_rates else 20000),
                    'WorkDays': attendance_data['work_days'],
                    'PresentDays': attendance_data['present_days'],
                    'AbsentDays': attendance_data['absent_days'],
                    'LeaveDays': attendance_data['leave_days'],
                    'OTHours': attendance_data['ot_hours'],
                    'LateMinutes': attendance_data['late_minutes'],
                    'WorkHours': attendance_data['work_hours'],
                    'ZoneHours': attendance_data['zone_hours'],
                    'NightHours': attendance_data['night_hours'],
                    'HazardDays': attendance_data['hazard_days'],
                    'ContractorFlag': emp.personnel_type == 'CONTRACTOR',
                    'Department': emp.department or '',
                    'Position': emp.position or '',
                    'EmployeeType': emp.personnel_type,
                    'AreaID': attendance_data.get('area_id', 0)
                }
                # Values of pay items calculated earlier in the structure (by
                # sequence), so e.g. Tax = (Basic + HRA) * 0.1 works.
                variables.update(earlier_items or {})
                
                # Evaluate formula
                formula_result = self.formula_engine.evaluate_formula(item.formula, variables)
                
                if formula_result['success']:
                    result['value'] = float(formula_result['value'])
                    result['formula_used'] = item.formula
                else:
                    result['error'] = formula_result['error']
                    return result
            
            else:
                result['error'] = f'Unknown calculation type: {item.calc_type}'
                return result
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error calculating pay item {item.item_name}: {str(e)}")
        
        return result
    
    def _calculate_zone_allowances(self, structure_id: int, attendance_data: Dict[str, Any],
                                 emp: Personnel) -> List[Dict[str, Any]]:
        """Calculate POB zone allowances"""
        
        allowances = []
        
        try:
            # Get zone allowances for structure
            zone_allowances = self.db.query(PayZoneAllowance).filter(
                PayZoneAllowance.structure_id == structure_id,
                PayZoneAllowance.is_active == True
            ).all()
            
            for zone_allowance in zone_allowances:
                # Check if employee worked in this zone
                zone_worked = False
                zone_days = 0
                zone_hours = 0
                
                for zone_breakdown in attendance_data.get('zone_breakdown', []):
                    if str(zone_breakdown['area_id']) == str(zone_allowance.area_id):
                        zone_worked = True
                        zone_days = zone_breakdown['days']
                        zone_hours = zone_breakdown['work_time']
                        break
                
                if zone_worked:
                    # Calculate allowance based on type
                    if zone_allowance.allowance_type == 0:  # hourly
                        allowance_value = zone_hours * float(zone_allowance.amount)
                    elif zone_allowance.allowance_type == 1:  # daily
                        allowance_value = zone_days * float(zone_allowance.amount)
                    else:  # fixed
                        allowance_value = float(zone_allowance.amount)
                    
                    # Add hazard premium if applicable
                    if zone_allowance.is_hazard and zone_allowance.hazard_rate:
                        hazard_premium = allowance_value * (float(zone_allowance.hazard_rate) / 100)
                        allowance_value += hazard_premium
                    
                    allowances.append({
                        'name': f"Zone Allowance - {zone_allowance.zone_name or 'Zone ' + str(zone_allowance.area_id)}",
                        'value': allowance_value,
                        'type': 'earning',
                        'sequence': 1000,  # High sequence for allowances
                        'formula_used': f"Zone {zone_allowance.area_id} - {zone_allowance.allowance_type} * {zone_allowance.amount}",
                        'source_value': zone_hours if zone_allowance.allowance_type == 0 else zone_days
                    })
        
        except Exception as e:
            logger.error(f"Error calculating zone allowances: {str(e)}")
        
        return allowances
    
    def _calculate_loan_deductions(self, emp_id: int, period_id: int) -> List[Dict[str, Any]]:
        """Calculate loan deductions for employee"""
        
        deductions = []
        
        try:
            # Get active loans for employee
            active_loans = self.db.query(PayLoan).filter(
                PayLoan.emp_id == emp_id,
                PayLoan.status == PayLoanStatus.ACTIVE
            ).all()
            
            for loan in active_loans:
                # Check if already deducted for this period
                existing_deduction = self.db.query(PayLoanDeduction).filter(
                    PayLoanDeduction.loan_id == loan.id,
                    PayLoanDeduction.period_id == period_id
                ).first()
                
                if not existing_deduction:
                    # Calculate EMI
                    emi_amount = float(loan.emi_amount)
                    
                    deductions.append({
                        'name': f"Loan EMI - {loan.loan_type}",
                        'value': emi_amount,
                        'type': 'deduction',
                        'sequence': 2000,  # High sequence for deductions
                        'formula_used': f"EMI: {emi_amount}",
                        'source_value': None,
                        'loan_id': loan.id
                    })
        
        except Exception as e:
            logger.error(f"Error calculating loan deductions: {str(e)}")
        
        return deductions
    
    def _get_salary_breakdown(self, salary: PaySalary) -> Dict[str, Any]:
        """Get detailed salary breakdown"""
        
        items = self.db.query(PaySalaryItem).filter(
            PaySalaryItem.salary_id == salary.id
        ).order_by(PaySalaryItem.calculation_order).all()
        
        breakdown = {
            'salary_id': salary.id,
            'employee': {
                'id': salary.emp_id,
                'name': salary.employee.full_name if salary.employee else 'Unknown',
                'badge_id': salary.employee.badge_id if salary.employee else 'Unknown'
            },
            'period': {
                'id': salary.period_id,
                'name': salary.period.period_name if salary.period else 'Unknown',
                'start_date': salary.period.start_date.isoformat() if salary.period else None,
                'end_date': salary.period.end_date.isoformat() if salary.period else None
            },
            'attendance_data': {
                'work_days': salary.work_days,
                'present_days': salary.present_days,
                'absent_days': salary.absent_days,
                'leave_days': salary.leave_days,
                'ot_hours': salary.ot_hours,
                'late_minutes': salary.late_minutes,
                'zone_hours': salary.zone_hours,
                'night_hours': salary.night_hours,
                'hazard_days': salary.hazard_days
            },
            'totals': {
                'gross_salary': salary.gross_salary,
                'total_earnings': salary.total_earnings,
                'total_deductions': salary.total_deductions,
                'net_salary': salary.net_salary
            },
            'items': [
                {
                    'name': item.item_name,
                    'value': item.item_value,
                    'type': item.item_type.value,
                    'formula_used': item.formula_used,
                    'source_value': item.source_value,
                    'is_manual_adjustment': item.is_manual_adjustment,
                    'adjustment_reason': item.adjustment_reason
                }
                for item in items
            ]
        }
        
        return breakdown
    
    def _log_calculation(self, period_id: int, emp_id: int, calc_type: str,
                        data: Dict[str, Any], success: bool, error: str = None):
        """Log calculation for audit trail"""
        
        try:
            log_entry = PayCalculationLog(
                period_id=period_id,
                emp_id=emp_id,
                calculation_type=calc_type,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                status='COMPLETED' if success else 'FAILED',
                input_data=data if success else None,
                result_data=data if success else None,
                error_message=error
            )
            
            self.db.add(log_entry)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error logging calculation: {str(e)}")
    
    def bulk_calculate_salary(self, period_id: int, emp_ids: List[int] = None,
                            dept_ids: List[int] = None) -> Dict[str, Any]:
        """Bulk calculate salary for multiple employees"""
        
        result = {
            'success': False,
            'processed': 0,
            'failed': 0,
            'errors': [],
            'calculation_ids': []
        }
        
        try:
            # Get employees to process
            employees_query = self.db.query(Personnel).filter(Personnel.is_active == True)
            
            if emp_ids:
                employees_query = employees_query.filter(Personnel.id.in_(emp_ids))
            
            if dept_ids:
                employees_query = employees_query.filter(Personnel.department_id.in_(dept_ids))
            
            employees = employees_query.all()
            
            for emp in employees:
                calc_result = self.calculate_salary(period_id, emp.id)
                
                if calc_result['success']:
                    result['processed'] += 1
                    result['calculation_ids'].append(calc_result['salary_id'])
                else:
                    result['failed'] += 1
                    result['errors'].append({
                        'emp_id': emp.id,
                        'emp_name': emp.full_name,
                        'error': calc_result['error']
                    })
            
            result['success'] = True
            
        except Exception as e:
            logger.error(f"Error in bulk calculation: {str(e)}")
            result['errors'].append({'error': str(e)})
        
        return result
