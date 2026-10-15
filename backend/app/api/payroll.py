"""
BioTime 9.5 Payroll API Endpoints with POB Extensions
Complete REST API for payroll management and calculations
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field
import logging

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.payroll import (
    PayStructure, PayItem, PayStructureAssign, PayPeriod, PaySalary, PaySalaryItem,
    PayLoan, PayLoanDeduction, PayZoneAllowance, PayContractorRate, PayAttendanceMapping,
    PayPayslipTemplate, PayBankConfig, PayCalculationLog
)
from ..models.personnel import Personnel
from ..models.department import Department
from ..models.position import Position
from ..services.payroll_service import PayrollService
from ..services.payroll_formula_engine import payroll_formula_engine
from ..services.payroll_payslip_service import PayrollPayslipService
from ..services.payroll_reports_service import PayrollReportsService
from ..services.payroll_loans_service import PayrollLoansService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payroll", tags=["payroll"])

# Pydantic models for request/response validation
class PayStructureCreate(BaseModel):
    structure_name: str = Field(..., min_length=1, max_length=100)
    structure_type: str = Field(default="monthly", pattern="^(monthly|daily|hourly)$")
    description: Optional[str] = None
    effective_date: Optional[date] = None

class PayStructureUpdate(BaseModel):
    structure_name: Optional[str] = Field(None, min_length=1, max_length=100)
    structure_type: Optional[str] = Field(None, pattern="^(monthly|daily|hourly)$")
    description: Optional[str] = None
    effective_date: Optional[date] = None
    is_active: Optional[bool] = None

class PayItemCreate(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=50)
    item_type: str = Field(..., pattern="^(earning|deduction|attendance)$")
    calc_type: str = Field(default="fixed", pattern="^(fixed|formula|attendance)$")
    amount: Optional[float] = Field(None, ge=0)
    formula: Optional[str] = None
    attendance_field: Optional[str] = None
    rate: Optional[float] = Field(None, ge=0)
    sequence: int = Field(default=0, ge=0)
    is_taxable: bool = False
    is_print: bool = True
    is_mandatory: bool = False
    gl_account: Optional[str] = None

class PayStructureAssignCreate(BaseModel):
    assign_type: int = Field(..., ge=0, le=2)  # 0=employee,1=department,2=position
    assign_id: int = Field(..., gt=0)
    priority: int = Field(default=0, ge=0)
    effective_date: Optional[date] = None
    end_date: Optional[date] = None

class PayPeriodCreate(BaseModel):
    period_name: str = Field(..., min_length=1, max_length=50)
    start_date: date
    end_date: date
    pay_date: Optional[date] = None
    description: Optional[str] = None

class PayPeriodUpdate(BaseModel):
    period_name: Optional[str] = Field(None, min_length=1, max_length=50)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    pay_date: Optional[date] = None
    description: Optional[str] = None

class PayrollCalculationRequest(BaseModel):
    period_id: int = Field(..., gt=0)
    emp_ids: Optional[List[int]] = None
    dept_ids: Optional[List[int]] = None
    force_recalc: bool = False

class FormulaTestRequest(BaseModel):
    formula: str = Field(..., min_length=1)
    sample_data: Dict[str, Any] = {}

class SalaryAdjustmentRequest(BaseModel):
    item_id: Optional[int] = None
    item_name: str = Field(..., min_length=1)
    new_value: float
    reason: str = Field(..., min_length=1, max_length=255)

class PayLoanCreate(BaseModel):
    emp_id: int = Field(..., gt=0)
    loan_type: str = Field(default="PERSONAL", max_length=50)
    loan_amount: float = Field(..., gt=0)
    emi_amount: float = Field(..., gt=0)
    interest_rate: float = Field(default=0, ge=0)
    start_date: date
    end_date: date
    reason: Optional[str] = Field(None, max_length=255)

class PayZoneAllowanceCreate(BaseModel):
    structure_id: int = Field(..., gt=0)
    area_id: Optional[int] = None
    zone_name: Optional[str] = None
    allowance_type: int = Field(default=0, ge=0, le=2)  # 0=hourly,1=daily,2=fixed
    amount: float = Field(..., gt=0)
    is_hazard: bool = False
    hazard_rate: Optional[float] = Field(None, ge=0)
    effective_date: Optional[date] = None
    end_date: Optional[date] = None

class PayContractorRateCreate(BaseModel):
    vendor_id: Optional[int] = None
    position_id: Optional[int] = None
    position_name: Optional[str] = None
    hourly_rate: Optional[float] = Field(None, ge=0)
    daily_rate: Optional[float] = Field(None, ge=0)
    weekly_rate: Optional[float] = Field(None, ge=0)
    monthly_rate: Optional[float] = Field(None, ge=0)
    ot_rate: float = Field(default=1.5, gt=0)
    night_shift_rate: float = Field(default=1.25, gt=0)
    holiday_rate: float = Field(default=2.0, gt=0)
    effective_date: Optional[date] = None
    end_date: Optional[date] = None

# Salary Structure Management
@router.get("/structures/", response_model=List[Dict[str, Any]])
async def get_pay_structures(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all salary structures"""
    try:
        query = db.query(PayStructure)
        
        if not include_inactive:
            query = query.filter(PayStructure.is_active == True)
        
        structures = query.order_by(PayStructure.structure_name).all()
        
        result = []
        for structure in structures:
            items = db.query(PayItem).filter(
                PayItem.structure_id == structure.id
            ).order_by(PayItem.sequence).all()
            
            assignments = db.query(PayStructureAssign).filter(
                PayStructureAssign.structure_id == structure.id,
                PayStructureAssign.is_active == True
            ).all()
            
            result.append({
                "id": structure.id,
                "structure_name": structure.structure_name,
                "structure_type": structure.structure_type.value,
                "is_active": structure.is_active,
                "version": structure.version,
                "effective_date": structure.effective_date.isoformat() if structure.effective_date else None,
                "description": structure.description,
                "created_at": structure.created_at.isoformat(),
                "items_count": len(items),
                "assignments_count": len(assignments),
                "items": [
                    {
                        "id": item.id,
                        "item_name": item.item_name,
                        "item_type": item.item_type.value,
                        "calc_type": item.calc_type.value,
                        "amount": float(item.amount) if item.amount else None,
                        "formula": item.formula,
                        "attendance_field": item.attendance_field,
                        "rate": float(item.rate) if item.rate else None,
                        "sequence": item.sequence,
                        "is_taxable": item.is_taxable,
                        "is_print": item.is_print,
                        "is_mandatory": item.is_mandatory,
                        "gl_account": item.gl_account
                    }
                    for item in items
                ],
                "assignments": [
                    {
                        "id": assign.id,
                        "assign_type": assign.assign_type,
                        "assign_id": assign.assign_id,
                        "priority": assign.priority,
                        "effective_date": assign.effective_date.isoformat() if assign.effective_date else None,
                        "end_date": assign.end_date.isoformat() if assign.end_date else None
                    }
                    for assign in assignments
                ]
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting pay structures: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/structures", response_model=Dict[str, Any])
async def create_pay_structure(
    structure_data: PayStructureCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new salary structure"""
    try:
        structure = PayStructure(
            structure_name=structure_data.structure_name,
            structure_type=structure_data.structure_type,
            description=structure_data.description,
            effective_date=structure_data.effective_date,
            created_by=current_user.id if current_user else None
        )
        
        db.add(structure)
        db.flush()
        
        # Create default items for new structure
        default_items = [
            {"item_name": "Basic", "item_type": "earning", "calc_type": "fixed", "amount": 20000, "sequence": 1},
            {"item_name": "HRA", "item_type": "earning", "calc_type": "formula", "formula": "Basic * 0.4", "sequence": 2},
            {"item_name": "OT", "item_type": "earning", "calc_type": "attendance", "attendance_field": "ot_hours", "rate": 1.5, "sequence": 10},
            {"item_name": "Late Deduction", "item_type": "deduction", "calc_type": "attendance", "attendance_field": "late_minutes", "rate": 2.0, "sequence": 20},
            {"item_name": "PF", "item_type": "deduction", "calc_type": "formula", "formula": "Basic * 0.12", "sequence": 30},
            {"item_name": "Tax", "item_type": "deduction", "calc_type": "formula", "formula": "(Basic + HRA) * 0.1", "sequence": 31}
        ]
        
        for item_data in default_items:
            item = PayItem(
                structure_id=structure.id,
                **item_data
            )
            db.add(item)
        
        db.commit()
        
        return {
            "id": structure.id,
            "structure_name": structure.structure_name,
            "message": "Salary structure created successfully with default items"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating pay structure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/structures/{structure_id}", response_model=Dict[str, Any])
async def update_pay_structure(
    structure_id: int,
    structure_data: PayStructureUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update salary structure"""
    try:
        structure = db.query(PayStructure).filter(PayStructure.id == structure_id).first()
        if not structure:
            raise HTTPException(status_code=404, detail="Salary structure not found")
        
        # Update fields
        update_data = structure_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(structure, field, value)
        
        structure.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "id": structure.id,
            "message": "Salary structure updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating pay structure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/structures/{structure_id}", response_model=Dict[str, Any])
async def delete_pay_structure(
    structure_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete salary structure"""
    try:
        structure = db.query(PayStructure).filter(PayStructure.id == structure_id).first()
        if not structure:
            raise HTTPException(status_code=404, detail="Salary structure not found")
        
        # Check if structure is assigned to any employee
        assignments = db.query(PayStructureAssign).filter(
            PayStructureAssign.structure_id == structure_id,
            PayStructureAssign.is_active == True
        ).count()
        
        if assignments > 0:
            raise HTTPException(status_code=400, detail="Cannot delete structure that is assigned to employees")
        
        db.delete(structure)
        db.commit()
        
        return {"message": "Salary structure deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting pay structure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Pay Structure Items
def _check_item_formula(db: Session, structure_id: int, calc_type: Optional[str], formula: Optional[str],
                        sequence: Optional[int], item_id: Optional[int] = None) -> None:
    """Reject a formula that would fail at payroll time. It may use the standard
    variables and pay items that come EARLIER in the structure (lower sequence)."""
    if (calc_type or "") != "formula":
        return
    import re as _re
    earlier = [
        _re.sub(r"\W", "_", r.item_name or "")
        for r in db.query(PayItem).filter(PayItem.structure_id == structure_id).all()
        if r.id != item_id and (sequence is None or (r.sequence or 0) < sequence)
    ]
    check = payroll_formula_engine.validate_formula(formula or "", extra_variables=earlier)
    if not check["is_valid"]:
        raise HTTPException(status_code=400, detail="Invalid formula: " + "; ".join(check["errors"]))


@router.post("/structures/{structure_id}/items", response_model=Dict[str, Any])
async def create_pay_item(
    structure_id: int,
    item_data: PayItemCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new pay item for structure"""
    try:
        structure = db.query(PayStructure).filter(PayStructure.id == structure_id).first()
        if not structure:
            raise HTTPException(status_code=404, detail="Salary structure not found")
        
        _check_item_formula(db, structure_id, item_data.calc_type, item_data.formula, item_data.sequence)
        item = PayItem(
            structure_id=structure_id,
            item_name=item_data.item_name,
            item_type=item_data.item_type,
            calc_type=item_data.calc_type,
            amount=item_data.amount,
            formula=item_data.formula,
            attendance_field=item_data.attendance_field,
            rate=item_data.rate,
            sequence=item_data.sequence,
            is_taxable=item_data.is_taxable,
            is_print=item_data.is_print,
            is_mandatory=item_data.is_mandatory,
            gl_account=item_data.gl_account
        )
        
        db.add(item)
        db.commit()
        
        return {
            "id": item.id,
            "message": "Pay item created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating pay item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/structures/{structure_id}/items/{item_id}", response_model=Dict[str, Any])
async def update_pay_item(
    structure_id: int,
    item_id: int,
    item_data: PayItemCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update pay item"""
    try:
        item = db.query(PayItem).filter(
            PayItem.id == item_id,
            PayItem.structure_id == structure_id
        ).first()
        
        if not item:
            raise HTTPException(status_code=404, detail="Pay item not found")
        
        # Update fields
        update_data = item_data.dict(exclude_unset=True)
        _check_item_formula(db, structure_id, update_data.get("calc_type", item.calc_type),
                            update_data.get("formula", item.formula),
                            update_data.get("sequence", item.sequence), item_id=item.id)
        for field, value in update_data.items():
            setattr(item, field, value)
        
        db.commit()
        
        return {
            "id": item.id,
            "message": "Pay item updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating pay item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/structures/{structure_id}/items/{item_id}", response_model=Dict[str, Any])
async def delete_pay_item(
    structure_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete pay item"""
    try:
        item = db.query(PayItem).filter(
            PayItem.id == item_id,
            PayItem.structure_id == structure_id
        ).first()
        
        if not item:
            raise HTTPException(status_code=404, detail="Pay item not found")
        
        db.delete(item)
        db.commit()
        
        return {"message": "Pay item deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting pay item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Structure Assignment
@router.post("/structures/{structure_id}/assign", response_model=Dict[str, Any])
async def assign_structure(
    structure_id: int,
    assign_data: PayStructureAssignCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Assign structure to employee/department/position"""
    try:
        structure = db.query(PayStructure).filter(PayStructure.id == structure_id).first()
        if not structure:
            raise HTTPException(status_code=404, detail="Salary structure not found")
        
        # Validate assign_type and assign_id
        if assign_data.assign_type == 0:  # Employee
            emp = db.query(Personnel).filter(Personnel.id == assign_data.assign_id).first()
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
        elif assign_data.assign_type == 1:  # Department
            dept = db.query(Department).filter(Department.id == assign_data.assign_id).first()
            if not dept:
                raise HTTPException(status_code=404, detail="Department not found")
        elif assign_data.assign_type == 2:  # Position
            pos = db.query(Position).filter(Position.id == assign_data.assign_id).first()
            if not pos:
                raise HTTPException(status_code=404, detail="Position not found")
        else:
            raise HTTPException(status_code=400, detail="Invalid assign_type")
        
        assignment = PayStructureAssign(
            structure_id=structure_id,
            assign_type=assign_data.assign_type,
            assign_id=assign_data.assign_id,
            priority=assign_data.priority,
            effective_date=assign_data.effective_date,
            end_date=assign_data.end_date
        )
        
        db.add(assignment)
        db.commit()
        
        return {
            "id": assignment.id,
            "message": "Structure assigned successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning structure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Formula Testing
@router.post("/structures/{structure_id}/formula/test", response_model=Dict[str, Any])
async def test_formula(
    structure_id: int,
    test_request: FormulaTestRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Test formula with sample data"""
    try:
        structure = db.query(PayStructure).filter(PayStructure.id == structure_id).first()
        if not structure:
            raise HTTPException(status_code=404, detail="Salary structure not found")
        
        # Test formula
        result = payroll_formula_engine.test_formula(
            test_request.formula,
            test_request.sample_data
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing formula: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Pay Period Management
@router.get("/periods/", response_model=List[Dict[str, Any]])
async def get_pay_periods(
    include_closed: bool = True,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all pay periods"""
    try:
        query = db.query(PayPeriod)
        
        if not include_closed:
            query = query.filter(PayPeriod.status != "closed")
        
        periods = query.order_by(PayPeriod.start_date.desc()).all()
        
        return [
            {
                "id": period.id,
                "period_name": period.period_name,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "pay_date": period.pay_date.isoformat() if period.pay_date else None,
                "status": period.status.value,
                "is_att_locked": period.is_att_locked,
                "description": period.description,
                "created_at": period.created_at.isoformat(),
                "closed_at": period.closed_at.isoformat() if period.closed_at else None
            }
            for period in periods
        ]
        
    except Exception as e:
        logger.error(f"Error getting pay periods: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/periods", response_model=Dict[str, Any])
async def create_pay_period(
    period_data: PayPeriodCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new pay period"""
    try:
        # Check for overlapping periods
        overlapping = db.query(PayPeriod).filter(
            or_(
                and_(
                    PayPeriod.start_date <= period_data.start_date,
                    PayPeriod.end_date >= period_data.start_date
                ),
                and_(
                    PayPeriod.start_date <= period_data.end_date,
                    PayPeriod.end_date >= period_data.end_date
                )
            )
        ).first()
        
        if overlapping:
            raise HTTPException(status_code=400, detail="Period overlaps with existing period")
        
        period = PayPeriod(
            period_name=period_data.period_name,
            start_date=period_data.start_date,
            end_date=period_data.end_date,
            pay_date=period_data.pay_date,
            description=period_data.description,
            created_by=current_user.id if current_user else None
        )
        
        db.add(period)
        db.commit()
        
        return {
            "id": period.id,
            "message": "Pay period created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating pay period: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/periods/{period_id}", response_model=Dict[str, Any])
async def update_pay_period(
    period_id: int,
    period_data: PayPeriodUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update pay period"""
    try:
        period = db.query(PayPeriod).filter(PayPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Pay period not found")
        
        # Cannot update closed period
        if period.status == "closed":
            raise HTTPException(status_code=400, detail="Cannot update closed period")
        
        # Update fields
        update_data = period_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(period, field, value)
        
        db.commit()
        
        return {
            "id": period.id,
            "message": "Pay period updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating pay period: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/periods/{period_id}/close", response_model=Dict[str, Any])
async def close_pay_period(
    period_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Close pay period"""
    try:
        period = db.query(PayPeriod).filter(PayPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Pay period not found")
        
        if period.status == "closed":
            raise HTTPException(status_code=400, detail="Period is already closed")
        
        # Update period status
        period.status = "closed"
        period.is_att_locked = True
        period.closed_at = datetime.utcnow()
        period.closed_by = current_user.id if current_user else None
        
        db.commit()
        
        return {
            "id": period.id,
            "message": "Pay period closed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error closing pay period: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/periods/{period_id}/reopen", response_model=Dict[str, Any])
async def reopen_pay_period(
    period_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Reopen closed pay period (superuser only)"""
    try:
        # Check if user is superuser
        if not (current_user and current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Only superuser can reopen periods")
        
        period = db.query(PayPeriod).filter(PayPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Pay period not found")
        
        if period.status != "closed":
            raise HTTPException(status_code=400, detail="Period is not closed")
        
        # Update period status
        period.status = "open"
        period.is_att_locked = False
        period.closed_at = None
        period.closed_by = None
        
        db.commit()
        
        return {
            "id": period.id,
            "message": "Pay period reopened successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error reopening pay period: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Payroll Calculation
@router.post("/calculate", response_model=Dict[str, Any])
async def calculate_payroll(
    calc_request: PayrollCalculationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Calculate payroll for period and employees"""
    try:
        payroll_service = PayrollService(db)
        
        result = payroll_service.bulk_calculate_salary(
            calc_request.period_id,
            calc_request.emp_ids,
            calc_request.dept_ids
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating payroll: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _has_payroll_admin(current_user, db) -> bool:
    """Return True if user is superuser or has payroll.view permission."""
    if getattr(current_user, "is_superuser", False):
        return True
    row = db.execute(text("""
        SELECT 1 FROM auth_user_role ur
        JOIN auth_role r ON r.id = ur.role_id
        JOIN auth_role_permission rp ON rp.role_id = r.id
        JOIN auth_permission p ON p.id = rp.permission_id
        WHERE ur.user_id = :uid
          AND p.codename IN ('payroll.view', 'payroll.manage', 'payroll.admin')
        LIMIT 1
    """), {"uid": current_user.id}).fetchone()
    return bool(row)


def _own_emp_id(current_user, db) -> int | None:
    """Return the PaySalary.emp_id that belongs to the current user, or None."""
    row = db.execute(text(
        "SELECT id FROM personnel WHERE user_id = :uid LIMIT 1"
    ), {"uid": current_user.id}).fetchone()
    return row[0] if row else None


@router.get("/salaries/", response_model=List[Dict[str, Any]])
async def get_salaries(
    period_id: Optional[int] = Query(None),
    emp_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get calculated salaries — scoped to caller's own record unless payroll admin."""
    try:
        query = db.query(PaySalary)

        # Row-level security: non-admins may only see their own salary
        if not _has_payroll_admin(current_user, db):
            own = _own_emp_id(current_user, db)
            if own is None:
                return []  # user has no personnel record — no payroll data
            query = query.filter(PaySalary.emp_id == own)
        else:
            if emp_id:
                query = query.filter(PaySalary.emp_id == emp_id)

        if period_id:
            query = query.filter(PaySalary.period_id == period_id)

        if status:
            query = query.filter(PaySalary.calc_status == status)
        
        salaries = query.order_by(PaySalary.period_id.desc(), PaySalary.emp_id).all()
        
        result = []
        for salary in salaries:
            # Get salary items
            items = db.query(PaySalaryItem).filter(
                PaySalaryItem.salary_id == salary.id
            ).order_by(PaySalaryItem.calculation_order).all()
            
            result.append({
                "id": salary.id,
                "period_id": salary.period_id,
                "emp_id": salary.emp_id,
                "structure_id": salary.structure_id,
                "employee_name": salary.employee.full_name if salary.employee else "Unknown",
                "employee_badge_id": salary.employee.badge_id if salary.employee else "Unknown",
                "period_name": salary.period.period_name if salary.period else "Unknown",
                "basic_salary": float(salary.basic_salary) if salary.basic_salary else 0,
                "work_days": salary.work_days,
                "present_days": salary.present_days,
                "ot_hours": salary.ot_hours,
                "late_minutes": salary.late_minutes,
                "gross_salary": salary.gross_salary,
                "total_earnings": salary.total_earnings,
                "total_deductions": salary.total_deductions,
                "net_salary": salary.net_salary,
                "calc_status": salary.calc_status.value,
                "is_final": salary.is_final,
                "calc_time": salary.calc_time.isoformat(),
                "zone_hours": salary.zone_hours,
                "night_hours": salary.night_hours,
                "hazard_days": salary.hazard_days,
                "contractor_flag": salary.contractor_flag,
                "items": [
                    {
                        "id": item.id,
                        "item_name": item.item_name,
                        "item_value": item.item_value,
                        "item_type": item.item_type.value,
                        "formula_used": item.formula_used,
                        "source_value": item.source_value,
                        "is_manual_adjustment": item.is_manual_adjustment,
                        "adjustment_reason": item.adjustment_reason
                    }
                    for item in items
                ]
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting salaries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/salaries/{salary_id}", response_model=Dict[str, Any])
async def get_salary_details(
    salary_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detailed salary breakdown — non-admins may only access their own record."""
    try:
        payroll_service = PayrollService(db)

        salary = db.query(PaySalary).filter(PaySalary.id == salary_id).first()
        if not salary:
            raise HTTPException(status_code=404, detail="Salary record not found")

        # Ownership check for non-admin users
        if not _has_payroll_admin(current_user, db):
            own = _own_emp_id(current_user, db)
            if own is None or salary.emp_id != own:
                raise HTTPException(status_code=403, detail="Access denied")
        
        breakdown = payroll_service._get_salary_breakdown(salary)
        
        return breakdown
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting salary details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/salaries/{salary_id}/adjust", response_model=Dict[str, Any])
async def adjust_salary(
    salary_id: int,
    adjustment_data: SalaryAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Manual adjustment to salary — payroll admins only; employees cannot adjust their own."""
    try:
        # Only payroll admins may adjust salaries — no self-service adjustments
        if not _has_payroll_admin(current_user, db):
            raise HTTPException(status_code=403, detail="Salary adjustments require payroll.manage permission")

        salary = db.query(PaySalary).filter(PaySalary.id == salary_id).first()
        if not salary:
            raise HTTPException(status_code=404, detail="Salary record not found")

        if salary.is_final:
            raise HTTPException(status_code=400, detail="Cannot adjust finalized salary")
        
        # Create adjustment item
        adjustment_item = PaySalaryItem(
            salary_id=salary_id,
            item_id=adjustment_data.item_id,
            item_name=adjustment_data.item_name,
            item_value=adjustment_data.new_value,
            item_type="deduction" if adjustment_data.new_value < 0 else "earning",
            is_manual_adjustment=True,
            adjustment_reason=adjustment_data.reason
        )
        
        db.add(adjustment_item)
        
        # Update salary totals
        if adjustment_data.new_value > 0:
            salary.total_earnings += adjustment_data.new_value
        else:
            salary.total_deductions += abs(adjustment_data.new_value)
        
        salary.net_salary = salary.total_earnings - salary.total_deductions
        salary.is_final = False  # Mark as not final after adjustment
        
        db.commit()
        
        return {
            "id": adjustment_item.id,
            "message": "Salary adjusted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error adjusting salary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/salaries/{salary_id}/recalc", response_model=Dict[str, Any])
async def recalculate_salary(
    salary_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Recalculate single employee salary"""
    try:
        salary = db.query(PaySalary).filter(PaySalary.id == salary_id).first()
        if not salary:
            raise HTTPException(status_code=404, detail="Salary record not found")
        
        payroll_service = PayrollService(db)
        
        result = payroll_service.calculate_salary(
            salary.period_id,
            salary.emp_id,
            force_recalc=True
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recalculating salary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Loans Management
@router.get("/loans/", response_model=List[Dict[str, Any]])
async def get_loans(
    emp_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get loans and advances"""
    try:
        query = db.query(PayLoan)
        
        if emp_id:
            query = query.filter(PayLoan.emp_id == emp_id)
        
        if status:
            query = query.filter(PayLoan.status == status)
        
        loans = query.order_by(PayLoan.created_at.desc()).all()
        
        return [
            {
                "id": loan.id,
                "emp_id": loan.emp_id,
                "employee_name": loan.employee.full_name if loan.employee else "Unknown",
                "loan_type": loan.loan_type,
                "loan_amount": float(loan.loan_amount),
                "emi_amount": float(loan.emi_amount),
                "interest_rate": float(loan.interest_rate) if loan.interest_rate else 0,
                "start_date": loan.start_date.isoformat(),
                "end_date": loan.end_date.isoformat(),
                "balance": float(loan.balance),
                "status": loan.status.value,
                "reason": loan.reason,
                "approved_at": loan.approved_at.isoformat() if loan.approved_at else None,
                "created_at": loan.created_at.isoformat()
            }
            for loan in loans
        ]
        
    except Exception as e:
        logger.error(f"Error getting loans: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/loans", response_model=Dict[str, Any])
async def create_loan(
    loan_data: PayLoanCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new loan/advance with validation and EMI calculation"""
    try:
        loans_service = PayrollLoansService(db)
        
        # Convert Pydantic model to dict
        loan_dict = {
            'emp_id': loan_data.emp_id,
            'loan_type': loan_data.loan_type,
            'loan_amount': loan_data.loan_amount,
            'emi_amount': loan_data.emi_amount,
            'interest_rate': loan_data.interest_rate,
            'start_date': loan_data.start_date,
            'end_date': loan_data.end_date,
            'reason': loan_data.reason
        }
        
        result = loans_service.create_loan(loan_dict)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            "id": result['loan_id'],
            "message": "Loan created successfully",
            "emi_schedule": result.get('emi_schedule', [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating loan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/loans/{loan_id}/approve", response_model=Dict[str, Any])
async def approve_loan(
    loan_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Approve loan with proper validation"""
    try:
        loans_service = PayrollLoansService(db)
        
        result = loans_service.approve_loan(loan_id, current_user.id if current_user else None)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {
            "id": loan_id,
            "message": "Loan approved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving loan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# POB Extensions - Zone Allowances
@router.get("/zone-allowances/", response_model=List[Dict[str, Any]])
async def get_zone_allowances(
    structure_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get zone allowances"""
    try:
        query = db.query(PayZoneAllowance)
        
        if structure_id:
            query = query.filter(PayZoneAllowance.structure_id == structure_id)
        
        allowances = query.order_by(PayZoneAllowance.structure_id, PayZoneAllowance.area_id).all()
        
        return [
            {
                "id": allowance.id,
                "structure_id": allowance.structure_id,
                "area_id": allowance.area_id,
                "zone_name": allowance.zone_name,
                "allowance_type": allowance.allowance_type,
                "amount": float(allowance.amount),
                "is_hazard": allowance.is_hazard,
                "hazard_rate": float(allowance.hazard_rate) if allowance.hazard_rate else 0,
                "effective_date": allowance.effective_date.isoformat() if allowance.effective_date else None,
                "end_date": allowance.end_date.isoformat() if allowance.end_date else None,
                "is_active": allowance.is_active
            }
            for allowance in allowances
        ]
        
    except Exception as e:
        logger.error(f"Error getting zone allowances: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/zone-allowances", response_model=Dict[str, Any])
async def create_zone_allowance(
    allowance_data: PayZoneAllowanceCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create zone allowance"""
    try:
        allowance = PayZoneAllowance(
            structure_id=allowance_data.structure_id,
            area_id=allowance_data.area_id,
            zone_name=allowance_data.zone_name,
            allowance_type=allowance_data.allowance_type,
            amount=allowance_data.amount,
            is_hazard=allowance_data.is_hazard,
            hazard_rate=allowance_data.hazard_rate,
            effective_date=allowance_data.effective_date,
            end_date=allowance_data.end_date
        )
        
        db.add(allowance)
        db.commit()
        
        return {
            "id": allowance.id,
            "message": "Zone allowance created successfully"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating zone allowance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# POB Extensions - Contractor Rates
@router.get("/contractor-rates/", response_model=List[Dict[str, Any]])
async def get_contractor_rates(
    vendor_id: Optional[int] = Query(None),
    position_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get contractor rates"""
    try:
        query = db.query(PayContractorRate)
        
        if vendor_id:
            query = query.filter(PayContractorRate.vendor_id == vendor_id)
        
        if position_id:
            query = query.filter(PayContractorRate.position_id == position_id)
        
        rates = query.order_by(PayContractorRate.vendor_id, PayContractorRate.position_id).all()
        
        return [
            {
                "id": rate.id,
                "vendor_id": rate.vendor_id,
                "position_id": rate.position_id,
                "position_name": rate.position_name,
                "hourly_rate": float(rate.hourly_rate) if rate.hourly_rate else None,
                "daily_rate": float(rate.daily_rate) if rate.daily_rate else None,
                "weekly_rate": float(rate.weekly_rate) if rate.weekly_rate else None,
                "monthly_rate": float(rate.monthly_rate) if rate.monthly_rate else None,
                "ot_rate": float(rate.ot_rate),
                "night_shift_rate": float(rate.night_shift_rate),
                "holiday_rate": float(rate.holiday_rate),
                "effective_date": rate.effective_date.isoformat() if rate.effective_date else None,
                "end_date": rate.end_date.isoformat() if rate.end_date else None,
                "is_active": rate.is_active
            }
            for rate in rates
        ]
        
    except Exception as e:
        logger.error(f"Error getting contractor rates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/contractor-rates", response_model=Dict[str, Any])
async def create_contractor_rate(
    rate_data: PayContractorRateCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create contractor rate"""
    try:
        rate = PayContractorRate(
            vendor_id=rate_data.vendor_id,
            position_id=rate_data.position_id,
            position_name=rate_data.position_name,
            hourly_rate=rate_data.hourly_rate,
            daily_rate=rate_data.daily_rate,
            weekly_rate=rate_data.weekly_rate,
            monthly_rate=rate_data.monthly_rate,
            ot_rate=rate_data.ot_rate,
            night_shift_rate=rate_data.night_shift_rate,
            holiday_rate=rate_data.holiday_rate,
            effective_date=rate_data.effective_date,
            end_date=rate_data.end_date
        )
        
        db.add(rate)
        db.commit()
        
        return {
            "id": rate.id,
            "message": "Contractor rate created successfully"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating contractor rate: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Attendance Mapping
@router.get("/attendance-mapping/", response_model=List[Dict[str, Any]])
async def get_attendance_mapping(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get attendance field mapping"""
    try:
        mappings = db.query(PayAttendanceMapping).filter(
            PayAttendanceMapping.is_active == True
        ).order_by(PayAttendanceMapping.attendance_field).all()
        
        return [
            {
                "id": mapping.id,
                "attendance_field": mapping.attendance_field,
                "payroll_item_name": mapping.payroll_item_name,
                "rate": float(mapping.rate),
                "description": mapping.description
            }
            for mapping in mappings
        ]
        
    except Exception as e:
        logger.error(f"Error getting attendance mapping: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/attendance-mapping", response_model=Dict[str, Any])
async def update_attendance_mapping(
    mappings: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update attendance field mapping"""
    try:
        for mapping_data in mappings:
            mapping = db.query(PayAttendanceMapping).filter(
                PayAttendanceMapping.id == mapping_data["id"]
            ).first()
            
            if mapping:
                mapping.payroll_item_name = mapping_data.get("payroll_item_name", mapping.payroll_item_name)
                mapping.rate = mapping_data.get("rate", mapping.rate)
                mapping.description = mapping_data.get("description", mapping.description)
        
        db.commit()
        
        return {"message": "Attendance mapping updated successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating attendance mapping: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Reports and Analytics
@router.get("/reports/summary/", response_model=Dict[str, Any])
async def get_salary_summary(
    period_id: int = Query(...),
    group_by: str = Query(default="department", pattern="^(department|position|employee_type)$"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get comprehensive salary summary report"""
    try:
        reports_service = PayrollReportsService(db)
        
        report_data = reports_service.generate_salary_summary_report(period_id, group_by)
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error getting salary summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/zone-cost/", response_model=Dict[str, Any])
async def get_zone_cost_report(
    period_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get comprehensive zone cost report (POB specific)"""
    try:
        reports_service = PayrollReportsService(db)
        
        report_data = reports_service.generate_zone_cost_report(period_id)
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error getting zone cost report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/contractor-vs-staff/", response_model=Dict[str, Any])
async def get_contractor_vs_staff_report(
    period_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get contractor vs staff cost comparison report"""
    try:
        reports_service = PayrollReportsService(db)
        
        report_data = reports_service.generate_contractor_vs_staff_report(period_id)
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error getting contractor vs staff report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/item-wise/", response_model=Dict[str, Any])
async def get_item_wise_report(
    period_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get item-wise payroll breakdown report"""
    try:
        reports_service = PayrollReportsService(db)
        
        report_data = reports_service.generate_item_wise_report(period_id)
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error getting item-wise report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/variance/", response_model=Dict[str, Any])
async def get_variance_report(
    period_id: int = Query(...),
    compare_period_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get variance report comparing periods"""
    try:
        reports_service = PayrollReportsService(db)
        
        report_data = reports_service.generate_variance_report(period_id, compare_period_id)
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error getting variance report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Bank Sheet Export
@router.get("/bank-sheet/", response_model=Dict[str, Any])
async def get_bank_sheet(
    period_id: int = Query(...),
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    bank_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export bank sheet in specified format"""
    try:
        reports_service = PayrollReportsService(db)
        
        export_result = reports_service.export_bank_sheet(period_id, bank_code, format)
        
        if not export_result["success"]:
            raise HTTPException(status_code=400, detail=export_result["error"])
        
        return export_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting bank sheet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Calculation Logs
@router.get("/calculation-logs/", response_model=List[Dict[str, Any]])
async def get_calculation_logs(
    period_id: Optional[int] = Query(None),
    emp_id: Optional[int] = Query(None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get calculation logs"""
    try:
        query = db.query(PayCalculationLog)
        
        if period_id:
            query = query.filter(PayCalculationLog.period_id == period_id)
        
        if emp_id:
            query = query.filter(PayCalculationLog.emp_id == emp_id)
        
        logs = query.order_by(PayCalculationLog.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": log.id,
                "period_id": log.period_id,
                "emp_id": log.emp_id,
                "calculation_type": log.calculation_type,
                "start_time": log.start_time.isoformat() if log.start_time else None,
                "end_time": log.end_time.isoformat() if log.end_time else None,
                "status": log.status,
                "input_data": log.input_data,
                "result_data": log.result_data,
                "error_message": log.error_message,
                "created_by": log.created_by,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
        
    except Exception as e:
        logger.error(f"Error getting calculation logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Payslip Generation
@router.get("/payslip/{salary_id}/", response_model=Dict[str, Any])
async def get_payslip(
    salary_id: int,
    template_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Generate payslip PDF for a salary record"""
    try:
        payslip_service = PayrollPayslipService(db)
        
        result = payslip_service.generate_payslip_pdf(salary_id, template_id)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating payslip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/payslip/bulk-generate", response_model=Dict[str, Any])
async def bulk_generate_payslips(
    period_id: int = Query(...),
    emp_ids: Optional[List[int]] = Body(None),
    template_id: Optional[int] = Body(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Bulk generate payslips for multiple employees"""
    try:
        payslip_service = PayrollPayslipService(db)
        
        result = payslip_service.bulk_generate_payslips(period_id, emp_ids, template_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in bulk payslip generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/payslip/{salary_id}/send-email", response_model=Dict[str, Any])
async def send_payslip_email(
    salary_id: int,
    template_id: Optional[int] = Body(None),
    password: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Send payslip via email"""
    try:
        payslip_service = PayrollPayslipService(db)
        
        result = payslip_service.send_payslip_email(salary_id, template_id, password)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending payslip email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/payslip/bulk-email", response_model=Dict[str, Any])
async def bulk_send_payslips(
    period_id: int = Query(...),
    emp_ids: Optional[List[int]] = Body(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Bulk send payslips via email"""
    try:
        payslip_service = PayrollPayslipService(db)
        
        result = payslip_service.bulk_send_payslips(period_id, emp_ids)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in bulk email sending: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/payslip/template/", response_model=List[Dict[str, Any]])
async def get_payslip_templates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get payslip templates"""
    try:
        templates = db.query(PayPayslipTemplate).filter(
            PayPayslipTemplate.is_active == True
        ).order_by(PayPayslipTemplate.template_name).all()
        
        return [
            {
                "id": template.id,
                "template_name": template.template_name,
                "template_type": template.template_type,
                "is_default": template.is_default,
                "created_at": template.created_at.isoformat()
            }
            for template in templates
        ]
        
    except Exception as e:
        logger.error(f"Error getting payslip templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/payslip/template", response_model=Dict[str, Any])
async def create_payslip_template(
    template_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create payslip template"""
    try:
        template = PayPayslipTemplate(
            template_name=template_data.get('template_name'),
            template_type=template_data.get('template_type', 'STANDARD'),
            header_html=template_data.get('header_html'),
            body_html=template_data.get('body_html'),
            footer_html=template_data.get('footer_html'),
            css_style=template_data.get('css_style'),
            is_default=template_data.get('is_default', False),
            created_by=current_user.id if current_user else None
        )
        
        db.add(template)
        db.commit()
        
        return {
            "id": template.id,
            "message": "Payslip template created successfully"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating payslip template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Enhanced Loan Management Endpoints
@router.get("/loans/{loan_id}/details/", response_model=Dict[str, Any])
async def get_loan_details(
    loan_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detailed loan information with deduction history"""
    try:
        loans_service = PayrollLoansService(db)
        
        loan_details = loans_service.get_loan_details(loan_id)
        
        if 'error' in loan_details:
            raise HTTPException(status_code=404, detail=loan_details['error'])
        
        return loan_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting loan details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/loans/employee/{emp_id}/", response_model=List[Dict[str, Any]])
async def get_employee_loans(
    emp_id: int,
    include_completed: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all loans for an employee"""
    try:
        loans_service = PayrollLoansService(db)
        
        loans = loans_service.get_employee_loans(emp_id, include_completed)
        
        return loans
        
    except Exception as e:
        logger.error(f"Error getting employee loans: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/loans/summary/", response_model=Dict[str, Any])
async def get_loan_summary(
    emp_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get loan summary statistics"""
    try:
        loans_service = PayrollLoansService(db)
        
        summary = loans_service.get_loan_summary(emp_id)
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting loan summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/loans/process-deductions", response_model=Dict[str, Any])
async def process_loan_deductions(
    period_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Process loan deductions for a pay period"""
    try:
        loans_service = PayrollLoansService(db)
        
        result = loans_service.process_loan_deductions(period_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing loan deductions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/loans/calculate-emi", response_model=Dict[str, Any])
async def calculate_emi_schedule(
    loan_amount: float = Query(..., gt=0),
    interest_rate: float = Query(..., ge=0),
    tenure_months: int = Query(..., gt=0),
    emi_type: str = Query(default="reducing", pattern="^(fixed|reducing)$"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Calculate EMI schedule for a loan"""
    try:
        loans_service = PayrollLoansService(db)
        
        schedule = loans_service.calculate_emi_schedule(
            loan_amount, interest_rate, tenure_months, emi_type
        )
        
        return {
            "loan_amount": loan_amount,
            "interest_rate": interest_rate,
            "tenure_months": tenure_months,
            "emi_type": emi_type,
            "schedule": schedule
        }
        
    except Exception as e:
        logger.error(f"Error calculating EMI schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
