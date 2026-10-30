import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Any, Dict
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.leave_management import LeaveManagement, LeaveBalance, LeaveBlackout
from ..models.personnel import Personnel
from ..schemas.leave_management import (
    LeaveManagementCreate, LeaveManagementUpdate, LeaveManagementResponse,
    LeaveBalanceCreate, LeaveBalanceUpdate, LeaveBalanceResponse,
    LeaveBlackoutCreate, LeaveBlackoutUpdate, LeaveBlackoutResponse,
    LeaveApprovalRequest, LEAVE_TYPE_CATALOGUE, LEAVE_TYPE_MAP,
)
from ..models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class InitializeBalancesRequest(BaseModel):
    year: int
    carry_forward: bool = False
    personnel_ids: Optional[List[int]] = None   # None = all active
    leave_type_codes: Optional[List[str]] = None  # None = all types


def _enrich_leave(leave: LeaveManagement) -> LeaveManagement:
    """Attach personnel_name, personnel_emp_code, approved_by_name as transient attrs."""
    p = leave.personnel
    leave.personnel_name = p.full_name if p else None
    leave.personnel_emp_code = (p.badge_id or p.emp_code) if p else None
    leave.approved_by_name = leave.approver.username if leave.approver else None
    return leave


def _enrich_balance(balance: LeaveBalance) -> LeaveBalance:
    p = balance.personnel
    balance.personnel_name = p.full_name if p else None
    balance.personnel_emp_code = (p.badge_id or p.emp_code) if p else None
    return balance


# ── IMPORTANT: all static sub-paths must come before /{leave_id} ─────────────

# ==================== Leave Type Catalogue ====================

@router.get("/leave/types", response_model=List[Dict[str, Any]])
async def get_leave_types(
    current_user: User = Depends(get_current_user)
):
    return LEAVE_TYPE_CATALOGUE


@router.get("/leave/stats")
async def get_leave_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unfiltered aggregate counts for the stat cards — always reflects the full dataset."""
    rows = db.execute(text(
        "SELECT status, COUNT(*) AS cnt FROM leave_management GROUP BY status"
    )).fetchall()
    counts: Dict[str, int] = {r.status: int(r.cnt) for r in rows}
    total = sum(counts.values())
    return {
        "total":    total,
        "pending":  counts.get("pending",  0),
        "approved": counts.get("approved", 0) + counts.get("on_leave", 0),
        "rejected": counts.get("rejected", 0),
        "cancelled": counts.get("cancelled", 0),
    }


# ==================== Leave Balance Endpoints ====================

@router.post("/leave/balance", response_model=LeaveBalanceResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_balance(
    balance_data: LeaveBalanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    personnel = db.query(Personnel).filter(Personnel.id == balance_data.personnel_id).first()
    if not personnel:
        raise HTTPException(status_code=404, detail=f"Personnel {balance_data.personnel_id} not found")

    existing = db.query(LeaveBalance).filter(
        LeaveBalance.personnel_id == balance_data.personnel_id,
        LeaveBalance.leave_type == balance_data.leave_type,
        LeaveBalance.year == balance_data.year,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Leave balance already exists for this personnel, type, and year")

    balance = LeaveBalance(**balance_data.model_dump())
    db.add(balance)
    db.commit()
    db.refresh(balance)
    return _enrich_balance(balance)


@router.get("/leave/balance", response_model=List[LeaveBalanceResponse])
async def get_leave_balances(
    skip: int = Query(0, ge=0),
    limit: int = Query(5000, ge=1, le=10000),
    personnel_id: Optional[int] = Query(None),
    leave_type: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(LeaveBalance)
    if personnel_id:
        query = query.filter(LeaveBalance.personnel_id == personnel_id)
    if leave_type:
        query = query.filter(LeaveBalance.leave_type == leave_type)
    if year:
        query = query.filter(LeaveBalance.year == year)
    if department_id:
        query = query.join(Personnel, Personnel.id == LeaveBalance.personnel_id).filter(
            Personnel.department_id == department_id
        )
    balances = query.order_by(LeaveBalance.personnel_id, LeaveBalance.leave_type).offset(skip).limit(limit).all()
    return [_enrich_balance(b) for b in balances]


@router.post("/leave/balance/initialize")
async def initialize_leave_balances(
    body: InitializeBalancesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bulk-create leave balance records for all active employees for a given year.
    Mirrors BioTime's 'Generate Leave Balance' operation.
    - Skips employees that already have a record for that type+year.
    - If carry_forward=True, rolls unused balance from year-1 into carry_forward_days.
    """
    # status is an UPPERCASE enum describing location (ACTIVE/ONSHORE/OFFSHORE);
    # is_active is the employed flag. The lowercase literal matched nobody.
    personnel_query = db.query(Personnel).filter(Personnel.is_active.is_(True))
    if body.personnel_ids:
        personnel_query = personnel_query.filter(Personnel.id.in_(body.personnel_ids))
    all_personnel = personnel_query.all()

    types_to_init = (
        [LEAVE_TYPE_MAP[c] for c in body.leave_type_codes if c in LEAVE_TYPE_MAP]
        if body.leave_type_codes
        else LEAVE_TYPE_CATALOGUE
    )

    personnel_ids = [p.id for p in all_personnel]

    # Fetch all existing balance records for this year in one query
    existing_set: set = set()
    if personnel_ids:
        existing_rows = db.execute(text(
            "SELECT personnel_id, leave_type FROM leave_balance "
            "WHERE year = :yr AND personnel_id = ANY(:pids)"
        ), {"yr": body.year, "pids": personnel_ids}).fetchall()
        existing_set = {(r.personnel_id, r.leave_type) for r in existing_rows}

    # If carry-forward, fetch previous year balances in one query
    prev_balances: Dict[tuple, Decimal] = {}
    if body.carry_forward and personnel_ids:
        prev_rows = db.execute(text(
            "SELECT personnel_id, leave_type, balance_days FROM leave_balance "
            "WHERE year = :yr AND personnel_id = ANY(:pids) AND balance_days > 0"
        ), {"yr": body.year - 1, "pids": personnel_ids}).fetchall()
        prev_balances = {(r.personnel_id, r.leave_type): Decimal(str(r.balance_days)) for r in prev_rows}

    rows_to_insert = []
    now = datetime.utcnow()
    for p in all_personnel:
        for lt in types_to_init:
            key = (p.id, lt["code"])
            if key in existing_set:
                continue
            carry_fwd = prev_balances.get(key, Decimal("0"))
            total = Decimal(str(lt["default_days"]))
            rows_to_insert.append({
                "personnel_id": p.id,
                "leave_type": lt["code"],
                "year": body.year,
                "total_days": float(total),
                "used_days": 0.0,
                "balance_days": float(total + carry_fwd),
                "carry_forward_days": float(carry_fwd),
                "created_at": now,
                "updated_at": now,
            })

    if rows_to_insert:
        db.execute(text("""
            INSERT INTO leave_balance
                (personnel_id, leave_type, year, total_days, used_days,
                 balance_days, carry_forward_days, created_at, updated_at)
            VALUES
                (:personnel_id, :leave_type, :year, :total_days, :used_days,
                 :balance_days, :carry_forward_days, :created_at, :updated_at)
        """), rows_to_insert)
        db.commit()

    return {
        "year": body.year,
        "personnel_count": len(all_personnel),
        "types_count": len(types_to_init),
        "created": len(rows_to_insert),
        "skipped": len(existing_set),
    }


@router.get("/leave/balance/check")
async def check_leave_balance(
    personnel_id: int = Query(...),
    leave_type: str = Query(...),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return the current balance for a personnel+type+year — used by the leave request form."""
    if not year:
        year = datetime.now().year
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.personnel_id == personnel_id,
        LeaveBalance.leave_type == leave_type,
        LeaveBalance.year == year,
    ).first()
    if not balance:
        return {"has_balance": False, "total_days": 0, "used_days": 0, "balance_days": 0, "carry_forward_days": 0, "year": year}
    return {
        "has_balance": True,
        "total_days": float(balance.total_days),
        "used_days": float(balance.used_days),
        "balance_days": float(balance.balance_days),
        "carry_forward_days": float(balance.carry_forward_days),
        "year": year,
    }


@router.get("/leave/balance/summary/{personnel_id}", response_model=List[LeaveBalanceResponse])
async def get_personnel_balance_summary(
    personnel_id: int,
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not year:
        year = datetime.now().year
    personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
    if not personnel:
        raise HTTPException(status_code=404, detail=f"Personnel {personnel_id} not found")
    balances = db.query(LeaveBalance).filter(
        LeaveBalance.personnel_id == personnel_id,
        LeaveBalance.year == year,
    ).all()
    return [_enrich_balance(b) for b in balances]


@router.put("/leave/balance/{balance_id}", response_model=LeaveBalanceResponse)
async def update_leave_balance(
    balance_id: int,
    balance_data: LeaveBalanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    balance = db.query(LeaveBalance).filter(LeaveBalance.id == balance_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail=f"Leave balance {balance_id} not found")

    update_data = balance_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(balance, field, value)

    if 'total_days' in update_data or 'used_days' in update_data:
        balance.balance_days = balance.total_days - balance.used_days + balance.carry_forward_days

    db.commit()
    db.refresh(balance)
    return _enrich_balance(balance)


@router.delete("/leave/balance/{balance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leave_balance(
    balance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    balance = db.query(LeaveBalance).filter(LeaveBalance.id == balance_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail=f"Leave balance {balance_id} not found")
    db.delete(balance)
    db.commit()
    return None


# ==================== Leave Blackout Endpoints ====================

@router.post("/leave/blackout", response_model=LeaveBlackoutResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_blackout(
    blackout_data: LeaveBlackoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    blackout = LeaveBlackout(**blackout_data.model_dump(), created_by=current_user.id)
    db.add(blackout)
    db.commit()
    db.refresh(blackout)
    return blackout


@router.get("/leave/blackout", response_model=List[LeaveBlackoutResponse])
async def get_leave_blackouts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(LeaveBlackout)
    if start_date:
        query = query.filter(LeaveBlackout.end_date >= start_date)
    if end_date:
        query = query.filter(LeaveBlackout.start_date <= end_date)
    return query.order_by(LeaveBlackout.start_date).offset(skip).limit(limit).all()


@router.put("/leave/blackout/{blackout_id}", response_model=LeaveBlackoutResponse)
async def update_leave_blackout(
    blackout_id: int,
    blackout_data: LeaveBlackoutUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    blackout = db.query(LeaveBlackout).filter(LeaveBlackout.id == blackout_id).first()
    if not blackout:
        raise HTTPException(status_code=404, detail=f"Blackout {blackout_id} not found")
    for field, value in blackout_data.model_dump(exclude_unset=True).items():
        setattr(blackout, field, value)
    db.commit()
    db.refresh(blackout)
    return blackout


@router.delete("/leave/blackout/{blackout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leave_blackout(
    blackout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    blackout = db.query(LeaveBlackout).filter(LeaveBlackout.id == blackout_id).first()
    if not blackout:
        raise HTTPException(status_code=404, detail=f"Blackout {blackout_id} not found")
    db.delete(blackout)
    db.commit()
    return None


# ==================== Leave Calendar ====================

@router.get("/leave/calendar")
async def get_leave_calendar(
    start_date: date = Query(...),
    end_date: date = Query(...),
    personnel_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    leave_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(LeaveManagement).filter(
        LeaveManagement.start_date <= end_date,
        LeaveManagement.end_date >= start_date,
        LeaveManagement.status.in_(["approved", "on_leave"]),
    )
    if personnel_id:
        query = query.filter(LeaveManagement.personnel_id == personnel_id)
    if leave_type:
        query = query.filter(LeaveManagement.leave_type == leave_type)

    leaves = query.all()

    # Filter by department via personnel relationship
    if department_id:
        leaves = [l for l in leaves if l.personnel and l.personnel.department_id == department_id]

    # Build per-day map AND a flat list of unique leave spans for Gantt view
    calendar_data: Dict[str, list] = {}
    spans: Dict[int, dict] = {}  # keyed by leave.id for deduplication

    for leave in leaves:
        p = leave.personnel
        dept = p.department if p else None
        emp_code = (p.badge_id or p.emp_code) if p else None
        entry = {
            "id": leave.id,
            "personnel_id": leave.personnel_id,
            "personnel_name": p.full_name if p else None,
            "emp_code": emp_code,
            "department_id": p.department_id if p else None,
            "department_name": dept.name if dept else None,
            "leave_type": leave.leave_type,
            "status": leave.status,
            "start_date": leave.start_date.isoformat(),
            "end_date": leave.end_date.isoformat(),
            "days_count": float(leave.days_count),
            "reason": leave.reason,
        }

        # Populate per-day map (clipped to requested range)
        cur = max(leave.start_date, start_date)
        clip_end = min(leave.end_date, end_date)
        while cur <= clip_end:
            key = cur.isoformat()
            calendar_data.setdefault(key, []).append(entry)
            cur = datetime.fromordinal(cur.toordinal() + 1).date()

        spans[leave.id] = entry

    return {
        "days": calendar_data,
        "spans": list(spans.values()),
    }


# ==================== Leave Request CRUD ====================

@router.post("/leave", response_model=LeaveManagementResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    leave_data: LeaveManagementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    personnel = db.query(Personnel).filter(Personnel.id == leave_data.personnel_id).first()
    if not personnel:
        raise HTTPException(status_code=404, detail=f"Personnel {leave_data.personnel_id} not found")
    if personnel.hr_source == "SEAMLESSHR":
        # SeamlessHR owns staff leave (governance rule) — leave raised here never reaches
        # SeamlessHR or payroll. Approved SeamlessHR leave is pulled in nightly.
        raise HTTPException(status_code=400, detail=(
            "This employee's leave is managed in SeamlessHR — raise and approve it there; ApexPOB picks it up "
            "automatically. Use this screen only for contractors and others not in SeamlessHR."))

    # Blackout check
    blackouts = db.query(LeaveBlackout).filter(
        LeaveBlackout.start_date <= leave_data.end_date,
        LeaveBlackout.end_date >= leave_data.start_date,
    ).all()
    for bo in blackouts:
        applies = bo.applies_to == "all"
        if not applies and bo.department_id:
            applies = (personnel.department_id == bo.department_id)
        if applies:
            raise HTTPException(status_code=400, detail=f"Dates fall within blackout period: {bo.name}")

    # Overlap check
    overlap = db.query(LeaveManagement).filter(
        LeaveManagement.personnel_id == leave_data.personnel_id,
        LeaveManagement.status.in_(["pending", "approved", "on_leave"]),
        LeaveManagement.start_date <= leave_data.end_date,
        LeaveManagement.end_date >= leave_data.start_date,
    ).first()
    if overlap:
        raise HTTPException(status_code=400, detail="Personnel already has an overlapping leave request")

    # Balance enforcement — BioTime blocks submission when balance is insufficient
    balance_rec = db.query(LeaveBalance).filter(
        LeaveBalance.personnel_id == leave_data.personnel_id,
        LeaveBalance.leave_type == leave_data.leave_type,
        LeaveBalance.year == leave_data.start_date.year,
    ).first()
    if balance_rec is not None and balance_rec.balance_days < leave_data.days_count:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient {leave_data.leave_type} leave balance. "
                f"Available: {float(balance_rec.balance_days):.1f} days, "
                f"Requested: {float(leave_data.days_count):.1f} days."
            ),
        )

    leave = LeaveManagement(**leave_data.model_dump())
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return _enrich_leave(leave)


@router.get("/leave", response_model=List[LeaveManagementResponse])
async def get_leave_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    personnel_id: Optional[int] = Query(None),
    leave_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(LeaveManagement)
    if personnel_id:
        query = query.filter(LeaveManagement.personnel_id == personnel_id)
    if leave_type:
        query = query.filter(LeaveManagement.leave_type == leave_type)
    if status:
        query = query.filter(LeaveManagement.status == status)
    if start_date:
        query = query.filter(LeaveManagement.end_date >= start_date)
    if end_date:
        query = query.filter(LeaveManagement.start_date <= end_date)
    if department_id:
        query = query.join(Personnel, Personnel.id == LeaveManagement.personnel_id).filter(
            Personnel.department_id == department_id
        )
    leaves = query.order_by(LeaveManagement.created_at.desc()).offset(skip).limit(limit).all()
    return [_enrich_leave(l) for l in leaves]


@router.get("/leave/{leave_id}", response_model=LeaveManagementResponse)
async def get_leave_request(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    leave = db.query(LeaveManagement).filter(LeaveManagement.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave request {leave_id} not found")
    return _enrich_leave(leave)


@router.put("/leave/{leave_id}", response_model=LeaveManagementResponse)
async def update_leave_request(
    leave_id: int,
    leave_data: LeaveManagementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    leave = db.query(LeaveManagement).filter(LeaveManagement.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave request {leave_id} not found")
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail="Can only update pending leave requests")
    for field, value in leave_data.model_dump(exclude_unset=True).items():
        setattr(leave, field, value)
    db.commit()
    db.refresh(leave)
    return _enrich_leave(leave)


@router.delete("/leave/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leave_request(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    leave = db.query(LeaveManagement).filter(LeaveManagement.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave request {leave_id} not found")
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail="Can only delete pending leave requests")
    db.delete(leave)
    db.commit()
    return None


# ── Workflow actions — must come after GET/PUT/DELETE /{leave_id} would be defined
# but FastAPI matches by specificity so these /leave/{id}/approve paths are fine here

@router.put("/leave/{leave_id}/approve", response_model=LeaveManagementResponse)
async def approve_leave_request(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    leave = db.query(LeaveManagement).filter(LeaveManagement.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave request {leave_id} not found")
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail=f"Leave request is already {leave.status}")

    # Deduct balance if record exists
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.personnel_id == leave.personnel_id,
        LeaveBalance.leave_type == leave.leave_type,
        LeaveBalance.year == leave.start_date.year,
    ).first()
    if balance:
        if balance.balance_days < leave.days_count:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient leave balance. Available: {balance.balance_days}, Requested: {leave.days_count}",
            )
        balance.used_days += leave.days_count
        balance.balance_days -= leave.days_count

    leave.status = "approved"
    leave.approved_by = current_user.id
    leave.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(leave)
    await _recalc_leave_days(db, leave)
    return _enrich_leave(leave)


@router.put("/leave/{leave_id}/reject", response_model=LeaveManagementResponse)
async def reject_leave_request(
    leave_id: int,
    approval_data: LeaveApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    leave = db.query(LeaveManagement).filter(LeaveManagement.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave request {leave_id} not found")
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail=f"Leave request is already {leave.status}")

    leave.status = "rejected"
    leave.approved_by = current_user.id
    leave.approved_at = datetime.utcnow()
    leave.rejection_reason = approval_data.rejection_reason
    db.commit()
    db.refresh(leave)
    return _enrich_leave(leave)


@router.put("/leave/{leave_id}/cancel", response_model=LeaveManagementResponse)
async def cancel_leave_request(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    leave = db.query(LeaveManagement).filter(LeaveManagement.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail=f"Leave request {leave_id} not found")
    if leave.status not in ["approved", "on_leave"]:
        raise HTTPException(status_code=400, detail="Can only cancel approved or on-leave requests")

    # Restore balance
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.personnel_id == leave.personnel_id,
        LeaveBalance.leave_type == leave.leave_type,
        LeaveBalance.year == leave.start_date.year,
    ).first()
    if balance:
        balance.used_days -= leave.days_count
        balance.balance_days += leave.days_count

    leave.status = "cancelled"
    db.commit()
    db.refresh(leave)
    await _recalc_leave_days(db, leave)
    return _enrich_leave(leave)


async def _recalc_leave_days(db: Session, leave) -> None:
    """Re-score the days already past so the timesheet (and its absence exceptions)
    follow an approval or cancellation straight away — future days are scored nightly."""
    from ..services.attendance_calculation_service import attendance_calculation_service, SITE_TZ
    end = min(leave.end_date, datetime.now(SITE_TZ).date())
    if end < leave.start_date:
        return
    try:
        await attendance_calculation_service.calculate_attendance(
            emp_ids=[leave.personnel_id], start_date=str(leave.start_date), end_date=str(end), db=db)
    except Exception as e:  # noqa: BLE001 — the leave decision stands; the nightly run catches up
        logger.warning("Leave %s: timesheet recalculation failed: %s", leave.id, e)
