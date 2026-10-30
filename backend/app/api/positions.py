"""
Position Management API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select, outerjoin, case
from typing import Optional
import logging

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.position import Position, PositionAssignment
from ..models.department import Department
from ..models.personnel import Personnel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/positions", tags=["Position Management"])


def _assigned_count_subquery():
    """Reusable subquery: current assigned count per position."""
    return (
        select(
            PositionAssignment.position_id,
            func.count(PositionAssignment.id).label("assigned_count"),
        )
        .where(PositionAssignment.is_current == True)
        .group_by(PositionAssignment.position_id)
        .subquery()
    )


def _pos_to_dict(pos, dept_name=None, dept_code=None, assigned_count=0):
    """Convert a Position row (+ optional pre-fetched dept/count) to dict."""
    return {
        "id": pos.id,
        "position_code": pos.position_code,
        "position_name": pos.position_name,
        "hr_source": getattr(pos, "hr_source", None),
        "hr_managed": getattr(pos, "hr_source", None) == "SEAMLESSHR",
        "description": pos.description,
        "parent_id": pos.parent_id,
        "level": pos.level,
        "sort_order": pos.sort_order,
        "department_id": pos.department_id,
        "department": {"id": pos.department_id, "name": dept_name, "code": dept_code} if dept_name else None,
        "position_type": (pos.position_type or "").lower() or None,
        "job_category": (pos.job_category or "").lower() or None,
        "grade_level": pos.grade_level,
        "required_certifications": pos.required_certifications,
        "required_skills": pos.required_skills,
        "min_experience_years": pos.min_experience_years,
        "education_level": pos.education_level,
        "salary_range_min": float(pos.salary_range_min) if pos.salary_range_min is not None else None,
        "salary_range_max": float(pos.salary_range_max) if pos.salary_range_max is not None else None,
        "currency": pos.currency or "USD",
        "headcount": pos.headcount or 1,
        "is_active": pos.is_active,
        "is_safety_critical": pos.is_safety_critical,
        "requires_background_check": pos.requires_background_check,
        "assigned_count": int(assigned_count or 0),
        "notes": pos.notes,
        "created_at": pos.created_at.isoformat() if pos.created_at else None,
        "updated_at": pos.updated_at.isoformat() if pos.updated_at else None,
    }


# ── Static routes BEFORE /{position_id} ──────────────────────────────────────

@router.get("/meta/summary")
def get_summary(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    assigned_sq = _assigned_count_subquery()

    total    = db.query(Position).count()
    active   = db.query(Position).filter(Position.is_active == True).count()
    safety   = db.query(Position).filter(Position.is_safety_critical == True).count()

    # Vacant = active positions with 0 current assignments
    vacant = (
        db.query(Position)
        .outerjoin(assigned_sq, Position.id == assigned_sq.c.position_id)
        .filter(Position.is_active == True)
        .filter(func.coalesce(assigned_sq.c.assigned_count, 0) == 0)
        .count()
    )

    # Understaffed = active, assigned_count < headcount
    understaffed = (
        db.query(Position)
        .outerjoin(assigned_sq, Position.id == assigned_sq.c.position_id)
        .filter(Position.is_active == True)
        .filter(func.coalesce(assigned_sq.c.assigned_count, 0) < func.coalesce(Position.headcount, 1))
        .count()
    )

    by_type = {}
    for t, c in db.query(Position.position_type, func.count(Position.id)).group_by(Position.position_type).all():
        by_type[(t or "unspecified").lower()] = c

    by_category = {}
    for cat, c in db.query(Position.job_category, func.count(Position.id)).group_by(Position.job_category).all():
        by_category[(cat or "unspecified").lower()] = c

    by_dept: dict = {}
    for dept_id, c in db.query(Position.department_id, func.count(Position.id)).group_by(Position.department_id).all():
        if dept_id:
            d = db.query(Department).filter_by(id=dept_id).first()
            name = d.name if d else f"dept_{dept_id}"
        else:
            name = "Unassigned"
        by_dept[name] = c

    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "safety_critical": safety,
        "vacant": vacant,
        "understaffed": understaffed,
        "by_type": by_type,
        "by_category": by_category,
        "by_department": by_dept,
    }


@router.get("/types")
def get_position_types(_=Depends(get_current_user)):
    return [
        {"value": "executive",  "label": "Executive"},
        {"value": "manager",    "label": "Manager"},
        {"value": "supervisor", "label": "Supervisor"},
        {"value": "staff",      "label": "Staff"},
        {"value": "contractor", "label": "Contractor"},
    ]


@router.get("/categories")
def get_job_categories(_=Depends(get_current_user)):
    return [
        {"value": "technical",   "label": "Technical"},
        {"value": "operations",  "label": "Operations"},
        {"value": "safety",      "label": "Safety"},
        {"value": "admin",       "label": "Administration"},
        {"value": "support",     "label": "Support"},
    ]


@router.get("/hierarchy")
def get_hierarchy(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    assigned_sq = _assigned_count_subquery()

    def build_node(pos):
        dept_name = pos.department.name if pos.department else None
        dept_code = pos.department.code if pos.department else None
        cnt_row = db.execute(
            select(func.coalesce(assigned_sq.c.assigned_count, 0))
            .where(assigned_sq.c.position_id == pos.id)
        ).scalar() or 0
        node = _pos_to_dict(pos, dept_name, dept_code, cnt_row)
        q = db.query(Position).filter(Position.parent_id == pos.id)
        if not include_inactive:
            q = q.filter(Position.is_active == True)
        node["children"] = [build_node(c) for c in q.order_by(Position.sort_order).all()]
        return node

    q = db.query(Position).filter(Position.parent_id == None)
    if not include_inactive:
        q = q.filter(Position.is_active == True)
    return [build_node(p) for p in q.order_by(Position.sort_order, Position.position_name).all()]


@router.get("/assignments")
def list_assignments(
    personnel_id: Optional[int] = Query(None),
    position_id: Optional[int] = Query(None),
    assignment_status: Optional[str] = Query(None),
    is_current: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(PositionAssignment)
    if personnel_id:
        q = q.filter(PositionAssignment.personnel_id == personnel_id)
    if position_id:
        q = q.filter(PositionAssignment.position_id == position_id)
    if assignment_status:
        q = q.filter(PositionAssignment.status == assignment_status.upper())
    if is_current is not None:
        q = q.filter(PositionAssignment.is_current == is_current)

    rows = q.order_by(PositionAssignment.start_date.desc()).all()

    results = []
    for a in rows:
        # Enrich with personnel name
        personnel_name = None
        emp_code = None
        if a.personnel_id:
            p = db.query(Personnel).filter(Personnel.id == a.personnel_id).first()
            if p:
                personnel_name = f"{p.first_name} {p.last_name}".strip()
                emp_code = p.emp_code

        # Enrich with position name
        position_name = None
        position_code = None
        if a.position_id:
            pos = db.query(Position).filter(Position.id == a.position_id).first()
            if pos:
                position_name = pos.position_name
                position_code = pos.position_code

        results.append({
            "id": a.id,
            "personnel_id": a.personnel_id,
            "personnel_name": personnel_name,
            "emp_code": emp_code,
            "position_id": a.position_id,
            "position_name": position_name,
            "position_code": position_code,
            "department_id": a.department_id,
            "assignment_type": (a.assignment_type or "").lower(),
            "start_date": a.start_date.isoformat() if a.start_date else None,
            "end_date": a.end_date.isoformat() if a.end_date else None,
            "status": (a.status or "").lower(),
            "is_current": a.is_current,
            "notes": a.notes,
        })
    return results


@router.get("/vacancies")
def get_vacancies(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Active positions with 0 current assignments."""
    assigned_sq = _assigned_count_subquery()
    rows = (
        db.query(
            Position,
            Department.name.label("dept_name"),
            Department.code.label("dept_code"),
            func.coalesce(assigned_sq.c.assigned_count, 0).label("assigned_count"),
        )
        .outerjoin(Department, Position.department_id == Department.id)
        .outerjoin(assigned_sq, Position.id == assigned_sq.c.position_id)
        .filter(Position.is_active == True)
        .filter(func.coalesce(assigned_sq.c.assigned_count, 0) == 0)
        .order_by(Position.is_safety_critical.desc(), Position.position_name)
        .all()
    )
    return [_pos_to_dict(r.Position, r.dept_name, r.dept_code, 0) for r in rows]


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/")
def get_positions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    position_type: Optional[str] = Query(None),
    job_category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_safety_critical: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    assigned_sq = _assigned_count_subquery()

    q = (
        db.query(
            Position,
            Department.name.label("dept_name"),
            Department.code.label("dept_code"),
            func.coalesce(assigned_sq.c.assigned_count, 0).label("assigned_count"),
        )
        .outerjoin(Department, Position.department_id == Department.id)
        .outerjoin(assigned_sq, Position.id == assigned_sq.c.position_id)
    )

    if search:
        q = q.filter(or_(
            Position.position_name.ilike(f"%{search}%"),
            Position.position_code.ilike(f"%{search}%"),
            Position.description.ilike(f"%{search}%"),
        ))
    if department_id is not None:
        q = q.filter(Position.department_id == department_id)
    if position_type:
        q = q.filter(Position.position_type.ilike(position_type))
    if job_category:
        q = q.filter(Position.job_category.ilike(job_category))
    if is_active is not None:
        q = q.filter(Position.is_active == is_active)
    if is_safety_critical is not None:
        q = q.filter(Position.is_safety_critical == is_safety_critical)

    total = q.count()
    rows = q.order_by(Position.sort_order, Position.position_name).offset(skip).limit(limit).all()

    return {
        "data": [_pos_to_dict(r.Position, r.dept_name, r.dept_code, r.assigned_count) for r in rows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{position_id}")
def get_position(
    position_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    assigned_sq = _assigned_count_subquery()
    row = (
        db.query(
            Position,
            Department.name.label("dept_name"),
            Department.code.label("dept_code"),
            func.coalesce(assigned_sq.c.assigned_count, 0).label("assigned_count"),
        )
        .outerjoin(Department, Position.department_id == Department.id)
        .outerjoin(assigned_sq, Position.id == assigned_sq.c.position_id)
        .filter(Position.id == position_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Position not found")
    return _pos_to_dict(row.Position, row.dept_name, row.dept_code, row.assigned_count)


@router.post("", status_code=201)
def create_position(
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if db.query(Position).filter(Position.position_code == body.get("position_code")).first():
        raise HTTPException(status_code=400, detail="Position code already exists")

    pos = Position(
        position_code=body["position_code"],
        position_name=body["position_name"],
        description=body.get("description"),
        department_id=body.get("department_id"),
        parent_id=body.get("parent_id"),
        level=body.get("level", 1),
        sort_order=body.get("sort_order", 0),
        position_type=(body.get("position_type") or "").upper() or None,
        job_category=(body.get("job_category") or "").upper() or None,
        grade_level=body.get("grade_level"),
        required_certifications=body.get("required_certifications"),
        required_skills=body.get("required_skills"),
        min_experience_years=body.get("min_experience_years", 0),
        education_level=body.get("education_level"),
        salary_range_min=body.get("salary_range_min"),
        salary_range_max=body.get("salary_range_max"),
        currency=body.get("currency", "USD"),
        headcount=body.get("headcount", 1),
        is_active=body.get("is_active", True),
        is_safety_critical=body.get("is_safety_critical", False),
        requires_background_check=body.get("requires_background_check", False),
        notes=body.get("notes"),
        created_by=current_user.id,
    )
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return _pos_to_dict(pos, assigned_count=0)


@router.put("/{position_id}")
def update_position(
    position_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    pos = db.query(Position).filter(Position.id == position_id).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if getattr(pos, "hr_source", None) == "SEAMLESSHR":
        # SeamlessHR owns job roles: the name/code come from there. ApexPOB-only details
        # (safety-critical, required certificates, …) stay editable.
        locked = [f for f in ("position_name", "position_code") if f in body and body[f] != getattr(pos, f)]
        if locked:
            raise HTTPException(status_code=403, detail=(
                "This position comes from SeamlessHR — rename it there and it syncs here. "
                f"Read-only here: {', '.join(locked)}."))

    # Allow position_code change — check uniqueness only if it changed
    new_code = body.get("position_code")
    if new_code and new_code != pos.position_code:
        conflict = db.query(Position).filter(
            Position.position_code == new_code,
            Position.id != position_id,
        ).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Position code already in use")

    UPDATABLE = {
        "position_code", "position_name", "description", "department_id",
        "parent_id", "level", "sort_order", "grade_level",
        "required_certifications", "required_skills", "min_experience_years",
        "education_level", "salary_range_min", "salary_range_max", "currency",
        "headcount", "is_active", "is_safety_critical", "requires_background_check", "notes",
    }
    for field, value in body.items():
        if field not in UPDATABLE:
            continue
        if field in ("position_type", "job_category") and value:
            value = value.upper()
        setattr(pos, field, value)

    pos.updated_by = current_user.id
    db.commit()
    db.refresh(pos)

    dept_name = pos.department.name if pos.department else None
    dept_code = pos.department.code if pos.department else None
    cnt = db.query(func.count(PositionAssignment.id)).filter(
        PositionAssignment.position_id == pos.id,
        PositionAssignment.is_current == True,
    ).scalar() or 0
    return _pos_to_dict(pos, dept_name, dept_code, cnt)


@router.delete("/{position_id}")
def delete_position(
    position_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    pos = db.query(Position).filter(Position.id == position_id).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if getattr(pos, "hr_source", None) == "SEAMLESSHR":
        raise HTTPException(status_code=403, detail="This position comes from SeamlessHR — remove it there")

    active_assignments = db.query(PositionAssignment).filter(
        PositionAssignment.position_id == position_id,
        PositionAssignment.is_current == True,
    ).count()
    if active_assignments > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot deactivate: {active_assignments} active assignment(s). Reassign personnel first.",
        )

    pos.is_active = False
    db.commit()
    return {"message": "Position deactivated successfully"}


@router.post("/bulk-action")
def bulk_action(
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Bulk activate or deactivate positions.
    body: { action: "activate"|"deactivate", ids: [int, ...] }
    """
    action = (body.get("action") or "").lower()
    ids    = body.get("ids") or []
    if action not in ("activate", "deactivate"):
        raise HTTPException(status_code=400, detail="action must be 'activate' or 'deactivate'")
    if not ids:
        raise HTTPException(status_code=400, detail="ids list is required")

    results = {"success": [], "failed": []}

    for pos_id in ids:
        pos = db.query(Position).filter(Position.id == pos_id).first()
        if not pos:
            results["failed"].append({"id": pos_id, "reason": "Not found"})
            continue

        if action == "deactivate":
            active_cnt = db.query(PositionAssignment).filter(
                PositionAssignment.position_id == pos_id,
                PositionAssignment.is_current == True,
            ).count()
            if active_cnt > 0:
                results["failed"].append({"id": pos_id, "reason": f"{active_cnt} active assignment(s)"})
                continue

        pos.is_active  = action == "activate"
        pos.updated_by = current_user.id
        results["success"].append(pos_id)

    db.commit()
    return results


@router.post("/duplicate/{position_id}", status_code=201)
def duplicate_position(
    position_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Clone a position with a new code and name."""
    src = db.query(Position).filter(Position.id == position_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Source position not found")

    new_code = body.get("position_code")
    new_name = body.get("position_name")
    if not new_code or not new_name:
        raise HTTPException(status_code=400, detail="position_code and position_name are required")
    if db.query(Position).filter(Position.position_code == new_code).first():
        raise HTTPException(status_code=400, detail="Position code already exists")

    clone = Position(
        position_code=new_code,
        position_name=new_name,
        description=src.description,
        department_id=src.department_id,
        parent_id=src.parent_id,
        level=src.level,
        sort_order=src.sort_order,
        position_type=src.position_type,
        job_category=src.job_category,
        grade_level=src.grade_level,
        required_certifications=src.required_certifications,
        required_skills=src.required_skills,
        min_experience_years=src.min_experience_years,
        education_level=src.education_level,
        salary_range_min=src.salary_range_min,
        salary_range_max=src.salary_range_max,
        currency=src.currency,
        headcount=src.headcount,
        is_active=True,
        is_safety_critical=src.is_safety_critical,
        requires_background_check=src.requires_background_check,
        notes=src.notes,
        created_by=current_user.id,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return _pos_to_dict(clone, assigned_count=0)


@router.post("/assignments")
def create_assignment(
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from datetime import datetime

    def parse_dt(v):
        return datetime.fromisoformat(v) if isinstance(v, str) else v

    a = PositionAssignment(
        personnel_id=body["personnel_id"],
        position_id=body["position_id"],
        department_id=body.get("department_id"),
        assignment_type=(body.get("assignment_type") or "PRIMARY").upper(),
        start_date=parse_dt(body["start_date"]),
        end_date=parse_dt(body["end_date"]) if body.get("end_date") else None,
        notes=body.get("notes"),
        assigned_by=current_user.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "personnel_id": a.personnel_id, "position_id": a.position_id}
