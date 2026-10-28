from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import io
import logging

logger = logging.getLogger(__name__)

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.personnel import Personnel, PersonnelStatus, AttendanceLog
from ..schemas.personnel import PersonnelCreate, PersonnelResponse, PersonnelUpdate
from ..schemas.personnel_biotime import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    DepartmentCreate, DepartmentUpdate, DepartmentResponse,
    PositionCreate, PositionUpdate, PositionResponse,
    AreaCreate, AreaUpdate, AreaResponse,
    ResignationCreate, ResignationResponse,
    VendorCreate, VendorUpdate, VendorResponse,
    OnboardingTaskCreate, OnboardingTaskUpdate, OnboardingTaskResponse,
    OnboardingTemplateCreate, OnboardingTemplateResponse
)
from ..services.file_upload import file_upload_service
from ..services.bulk_import import bulk_import_service
from ..services.personnel_status import personnel_status_service
from ..services.certification_training import certification_training_service
from ..services.medical_fitness import medical_fitness_service
from ..services.badge_printing import badge_printing_service
from ..services.audit_trail import audit_trail_service
from ..services.personnel_analytics import personnel_analytics_service
from ..services.personnel_export import personnel_export_service
from ..services.zone_service import ZoneService
from ..services.biotime_sync_service import biotime_sync_service
from ..services.personnel_biotime_service import PersonnelBioTimeService

router = APIRouter()

# Initialize zone service for zones-only architecture
zone_service = ZoneService()


def _person_to_dict(p: Personnel) -> Dict[str, Any]:
    """Serialize a Personnel ORM row to a plain dict with all BioTime + POB fields."""
    def _iso(v):
        return v.isoformat() if v else None

    return {
        "id": p.id,
        "emp_code": p.emp_code,
        "badge_id": p.badge_id,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "full_name": p.full_name or f"{p.first_name or ''} {p.last_name or ''}".strip(),
        "email": p.email,
        "phone": p.phone,
        "address": getattr(p, "address", None),
        "nationality": getattr(p, "nationality", None),
        "id_number": getattr(p, "id_number", None),
        "passport_number": getattr(p, "passport_number", None),
        "hire_date": _iso(getattr(p, "hire_date", None)),
        "company": p.company,
        "department": p.department,
        "department_id": p.department_id,
        "role": p.role,
        "position": p.position,
        "employment_type": getattr(p, "employment_type", "EMPLOYEE"),
        "personnel_type": p.personnel_type,
        # A leaver (is_active False) may still carry SeamlessHR's "ACTIVE" text.
        "status": "INACTIVE" if p.is_active is False else (p.status.value if hasattr(p.status, "value") else (p.status or "ACTIVE")),
        "is_active": p.is_active is not False,
        "is_onboard": p.is_onboard or False,
        "is_pob": getattr(p, "is_pob", False) or False,
        "safety_critical": p.safety_critical or False,
        "biometric_enrolled": p.biometric_enrolled or False,
        "compliance_score": p.compliance_score or 0.0,
        "current_zone_id": p.current_zone_id,
        "current_location": p.current_location,
        "photo_url": p.photo_url,
        "blood_group": p.blood_group,
        "emergency_contact_name": getattr(p, "emergency_contact_name", None),
        "emergency_contact_phone": getattr(p, "emergency_contact_phone", None),
        "medical_conditions": p.medical_conditions,
        "biotime_employee_id": p.biotime_employee_id,
        "biometric_quality_score": p.biometric_quality_score or 0.0,
        # HR system-of-record: when 'SEAMLESSHR', master fields are read-only here.
        "hr_source": getattr(p, "hr_source", None),
        "hr_synced_at": _iso(getattr(p, "hr_synced_at", None)),
        "hr_managed": getattr(p, "hr_source", None) == "SEAMLESSHR",
        "on_leave": bool(getattr(p, "on_leave", False)),
        "leave_end_date": _iso(getattr(p, "leave_end_date", None)),
        "last_seen": _iso(p.last_seen),
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


@router.get("/employees", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any])
async def get_personnel(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, INACTIVE, OFFSHORE, etc.)"),
    location: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search across name, badge_id, email"),
    is_onboard: Optional[bool] = Query(None, description="Filter by onboard status"),
    blood_group: Optional[str] = Query(None, description="Filter by blood group"),
    personnel_type: Optional[str] = Query(None, description="Filter by personnel type"),
    certification_status: Optional[str] = Query(None, description="Filter by certification status"),
    safety_critical: Optional[bool] = Query(None, description="Filter by safety critical status"),
    biometric_enrolled: Optional[bool] = Query(None, description="Filter by biometric enrollment"),
    sort_by: Optional[str] = Query("full_name", description="Sort by field"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get personnel list with advanced filtering and search"""
    try:
        query = db.query(Personnel)
        
        # Status filtering — accept both ACTIVE and active (DB stores uppercase)
        if status:
            if status.upper() == "INACTIVE":
                query = query.filter(or_(Personnel.is_active == False, Personnel.status.ilike(status)))  # noqa: E712
            else:
                query = query.filter(Personnel.status.ilike(status), Personnel.is_active != False)  # noqa: E712
        
        # Zone filtering (zones-only architecture)
        if location:
            # Filter by zone name or zone_id
            query = query.filter(Personnel.current_zone_id.ilike(f"%{location}%"))
        
        # Company filtering
        if company:
            query = query.filter(Personnel.company.ilike(f"%{company}%"))
    
    # Department filtering
        if department:
            query = query.filter(Personnel.department.ilike(f"%{department}%"))
        
        # Role filtering
        if role:
            query = query.filter(Personnel.role.ilike(f"%{role}%"))
        
        # Onboard status filtering
        if is_onboard is not None:
            query = query.filter(Personnel.is_onboard == is_onboard)
        
        # Blood group filtering
        if blood_group:
            query = query.filter(Personnel.blood_group == blood_group)
        
        # Oil & Gas specific filtering
        if personnel_type:
            query = query.filter(Personnel.personnel_type == personnel_type)
        
        if safety_critical is not None:
            query = query.filter(Personnel.safety_critical == safety_critical)
        
        if biometric_enrolled is not None:
            query = query.filter(Personnel.biometric_enrolled == biometric_enrolled)
        
        # Certification status filtering (compliance score based)
        if certification_status:
            if certification_status == "compliant":
                query = query.filter(Personnel.compliance_score >= 90)
            elif certification_status == "expiring":
                query = query.filter(Personnel.compliance_score.between(70, 89))
            elif certification_status == "expired":
                query = query.filter(Personnel.compliance_score < 70)
        
        # Global search across multiple fields
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                Personnel.full_name.ilike(search_term) |
                Personnel.emp_code.ilike(search_term) |
                Personnel.badge_id.ilike(search_term) |
                Personnel.email.ilike(search_term) |
                Personnel.phone.ilike(search_term) |
                Personnel.company.ilike(search_term)
            )
        
        # Sorting
        if sort_by:
            sort_column = getattr(Personnel, sort_by, Personnel.full_name)
            if sort_order == "asc":
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())
        else:
            # Default order by created_at descending (newest first)
            query = query.order_by(Personnel.created_at.desc())
        
        total = query.count()
        # page_size takes priority over limit; skip overrides page if provided explicitly
        effective_size = page_size if page_size != 50 or limit == 100 else limit
        effective_skip = skip if skip != 0 else (page - 1) * page_size
        personnel = query.offset(effective_skip).limit(page_size).all()

        results = [_person_to_dict(p) for p in personnel]

        return {
            "results": results,
            "count": total,
            "current_page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    except Exception as e:
        print(f"Error in get_personnel: {e}")
        import traceback
        traceback.print_exc()
        return {"results": [], "count": 0, "current_page": 1, "page_size": page_size, "total_pages": 0}


@router.get("/status-summary")
async def get_status_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get personnel status summary
    
    Args:
        db: Database session
        
    Returns:
        Status summary statistics
    """
    try:
        summary = await personnel_status_service.get_status_summary(db=db)
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status summary: {str(e)}"
        )


@router.get("/onboard")
async def get_onboard_personnel(
    location: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get all currently onboard personnel
    
    Args:
        location: Filter by location (optional)
        zone: Filter by zone (optional)
        db: Database session
        
    Returns:
        List of onboard personnel
    """
    try:
        personnel = await personnel_status_service.get_onboard_personnel(
            location=location,
            zone=zone,
            db=db
        )
        return personnel
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get onboard personnel: {str(e)}"
        )


@router.post("/bulk-reset-onboard")
async def bulk_reset_onboard(
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict:
    """
    Clear is_onboard + pob_since for a list of personnel IDs.
    If ids is empty or omitted, resets ALL currently onboard personnel.
    """
    ids = body.get("ids", [])
    if ids:
        result = db.execute(
            text("UPDATE personnel SET is_onboard = FALSE, is_pob = FALSE, pob_since = NULL WHERE id = ANY(:ids) AND is_onboard = TRUE RETURNING id"),
            {"ids": ids},
        )
    else:
        result = db.execute(
            text("UPDATE personnel SET is_onboard = FALSE, is_pob = FALSE, pob_since = NULL WHERE is_onboard = TRUE RETURNING id")
        )
    cleared = [r[0] for r in result.fetchall()]
    db.commit()
    return {
        "success": True,
        "cleared_count": len(cleared),
        "cleared_ids": cleared,
        "message": f"{len(cleared)} personnel marked as offboard.",
    }


@router.get("/dashboard")
async def get_personnel_dashboard(db: Session = Depends(get_db)) -> dict:
    """Get comprehensive personnel dashboard data"""
    try:
        # Basic statistics
        total = db.query(Personnel).filter(Personnel.is_active == True).count()
        active = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.status == PersonnelStatus.ACTIVE).count()
        offshore = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.status == PersonnelStatus.OFFSHORE).count()
        onshore = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.status == PersonnelStatus.ONSHORE).count()
        onboard = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.is_onboard == True).count()
        inactive_total = db.query(Personnel).filter(Personnel.is_active == False).count()  # noqa: E712
        
        # Oil & Gas specific metrics
        safety_critical = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.safety_critical == True).count()
        biometric_enrolled = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.biometric_enrolled == True).count()
        
        # Personnel type breakdown
        staff_count = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.personnel_type == "STAFF").count()
        contractor_count = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.personnel_type == "CONTRACTOR").count()
        visitor_count = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.personnel_type == "VISITOR").count()
        
        # Compliance metrics
        compliant_count = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.compliance_score >= 90).count()
        expiring_count = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.compliance_score.between(70, 89)).count()
        expired_count = db.query(Personnel).filter(Personnel.is_active == True).filter(Personnel.compliance_score < 70).count()
        
        # Calculate compliance score
        avg_compliance = 0
        if total > 0:
            avg_compliance_score = db.query(func.avg(Personnel.compliance_score)).filter(Personnel.is_active == True).scalar() or 0
            avg_compliance = round(float(avg_compliance_score), 1)
        
        # Zone distribution (zones-only architecture)
        zone_data = db.query(
            Personnel.current_zone_id,
            func.count(Personnel.id).label('count')
        ).filter(Personnel.current_zone_id.isnot(None)).group_by(Personnel.current_zone_id).all()
        
        zone_distribution = {f"Zone {zone_id}": count for zone_id, count in zone_data}
        
        return {
            "total_personnel": total,                 # active staff (leavers excluded)
            "inactive_personnel": inactive_total,
            "onboard_count": onboard,                 # the screen's "On Board (POB)" card
            "contractor_count": contractor_count,
            "safety_critical_count": safety_critical,
            "offshore_count": offshore,
            "onshore_count": onshore,
            "compliance_score": avg_compliance,
            "safety_critical": safety_critical,
            "personnel_types": {
                "staff": staff_count,
                "contractor": contractor_count,
                "visitor": visitor_count
            },
            "certification_status": {
                "compliant": compliant_count,
                "expiring": expiring_count,
                "expired": expired_count
            },
            "biometric_status": {
                "enrolled": biometric_enrolled,
                "not_enrolled": total - biometric_enrolled
            },
            "zone_distribution": zone_distribution,
            "utilization_metrics": {
                "personnel_in_rotation": onboard,
                "personnel_available": total - onboard,
                "rotation_utilization": round((onboard / total * 100), 1) if total > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard data: {str(e)}"
        )


@router.get("/unassigned")
async def get_unassigned_personnel(db: Session = Depends(get_db)) -> dict:
    """
    Get personnel without department assignments
    
    Args:
        db: Database session
        
    Returns:
        List of unassigned personnel
    """
    try:
        # Import here to avoid circular imports
        from ..models.department import DepartmentPersonnel
        
        # Get all personnel
        all_personnel = db.query(Personnel).filter(
            Personnel.status == PersonnelStatus.ACTIVE
        ).all()
        
        # Get personnel with assignments
        assigned_personnel_ids = db.query(DepartmentPersonnel.personnel_id).filter(
            DepartmentPersonnel.status == "active"
        ).distinct().all()
        
        assigned_ids = set(p[0] for p in assigned_personnel_ids)
        
        # Filter unassigned personnel
        unassigned = []
        for person in all_personnel:
            if person.id not in assigned_ids:
                unassigned.append({
                    "id": person.id,
                    "badge_id": person.badge_id,
                    "full_name": person.full_name,
                    "email": person.email,
                    "phone": person.phone,
                    "company": person.company,
                    "role": person.role,
                    "position": person.position,
                    "status": person.status,
                    "is_onboard": person.is_onboard
                })
        
        return {
            "success": True,
            "count": len(unassigned),
            "personnel": unassigned
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch unassigned personnel: {str(e)}"
        )


@router.get("/location-summary")
async def get_current_location_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get current location summary of all personnel

    Args:
        db: Database session

    Returns:
        Location summary statistics
    """
    try:
        summary = await zone_service.get_current_location_summary(db=db)
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get location summary: {str(e)}"
        )


@router.get("/by-location")
async def get_personnel_by_location(
    location: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
    status: Optional[PersonnelStatus] = Query(None),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get personnel filtered by location and/or zone
    
    Args:
        location: Filter by location (optional)
        zone: Filter by zone (optional)
        status: Filter by status (optional)
        db: Database session
        
    Returns:
        List of personnel at specified location
    """
    try:
        personnel = await zone_service.get_personnel_by_location(
            location=location,
            zone=zone,
            status=status,
            db=db
        )
        return personnel
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personnel by location: {str(e)}"
        )


@router.get("/zone-capacity")
async def get_zone_capacity_status(
    zone: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get zone capacity status
    
    Args:
        zone: Specific zone to check (optional)
        db: Database session
        
    Returns:
        Zone capacity information
    """
    try:
        capacity_status = await zone_service.get_zone_capacity_status(
            zone=zone,
            db=db
        )
        return capacity_status
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get zone capacity status: {str(e)}"
        )


@router.get("/location-analytics")
async def get_location_analytics(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get location analytics and insights
    
    Args:
        hours: Number of hours for analytics
        db: Database session
        
    Returns:
        Location analytics data
    """
    try:
        analytics = await zone_service.get_location_analytics(
            hours=hours,
            db=db
        )
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get location analytics: {str(e)}"
        )


@router.get("/badge/{badge_id}", response_model=PersonnelResponse)
async def get_personnel_by_badge(
    badge_id: str,
    db: Session = Depends(get_db)
) -> Personnel:
    """Get personnel by badge ID"""
    personnel = db.query(Personnel).filter(Personnel.badge_id == badge_id).first()
    if not personnel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personnel not found"
        )
    return personnel


@router.post("", response_model=Dict[str, Any])
async def create_personnel(
    personnel_data: PersonnelCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Register a new employee — BioTime-standard fields"""
    # Duplicate emp_code check
    if db.query(Personnel).filter(Personnel.emp_code == personnel_data.emp_code).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Employee code already exists")

    # Duplicate email check
    if personnel_data.email:
        if db.query(Personnel).filter(Personnel.email == personnel_data.email).first():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # card_no → badge_id; fallback to emp_code when no card provided
    card_no = personnel_data.card_no or personnel_data.emp_code
    full_name = f"{personnel_data.first_name} {personnel_data.last_name}".strip()

    person = Personnel(
        emp_code=personnel_data.emp_code,
        badge_id=card_no,
        first_name=personnel_data.first_name,
        last_name=personnel_data.last_name,
        full_name=full_name,
        email=personnel_data.email,
        phone=personnel_data.phone,
        company=personnel_data.company,
        department_id=personnel_data.department_id,
        department=personnel_data.department,
        role=personnel_data.role,
        position=personnel_data.position,
        employment_type=personnel_data.employment_type,
        personnel_type=personnel_data.personnel_type,
        safety_critical=personnel_data.safety_critical,
        is_onboard=personnel_data.is_onboard,
        is_pob=personnel_data.is_onboard,
        current_zone_id=personnel_data.current_zone_id,
        status=personnel_data.status,
        blood_group=personnel_data.blood_group,
        emergency_contact_name=personnel_data.emergency_contact_name,
        emergency_contact_phone=personnel_data.emergency_contact_phone,
        medical_conditions=personnel_data.medical_conditions,
        hire_date=personnel_data.hire_date,
        nationality=personnel_data.nationality,
        id_number=personnel_data.id_number,
        passport_number=personnel_data.passport_number,
        is_active=True,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return _person_to_dict(person)


@router.put("/{personnel_id}", response_model=Dict[str, Any])
async def update_personnel(
    personnel_id: int,
    personnel_data: PersonnelUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update employee — BioTime-standard fields"""
    person = db.query(Personnel).filter(Personnel.id == personnel_id).first()
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Personnel not found")

    data = personnel_data.dict(exclude_unset=True)

    # Field → DB column mapping
    field_map = {
        "emp_code": "emp_code",
        "card_no": "badge_id",       # card_no from BioTime → badge_id in DB
        "first_name": "first_name",
        "last_name": "last_name",
        "email": "email",
        "phone": "phone",
        "company": "company",
        "department_id": "department_id",
        "department": "department",
        "role": "role",
        "position": "position",
        "employment_type": "employment_type",
        "personnel_type": "personnel_type",
        "safety_critical": "safety_critical",
        "is_onboard": "is_onboard",
        "current_zone_id": "current_zone_id",
        "status": "status",
        "blood_group": "blood_group",
        "emergency_contact_name": "emergency_contact_name",
        "emergency_contact_phone": "emergency_contact_phone",
        "medical_conditions": "medical_conditions",
        "hire_date": "hire_date",
        "nationality": "nationality",
        "id_number": "id_number",
        "passport_number": "passport_number",
    }

    # SeamlessHR is the system of record for employee MASTER data. If this person was
    # synced from SeamlessHR, its master fields are read-only in ApexPOB — reject any
    # attempt to change them (operational fields below stay editable). Defence-in-depth:
    # the UI also disables these fields.
    HR_MASTERED_FIELDS = {
        "emp_code", "first_name", "last_name", "email", "phone", "company",
        "department", "department_id", "role", "position", "employment_type",
        "personnel_type", "hire_date", "nationality", "id_number", "passport_number",
    }
    if getattr(person, "hr_source", None) == "SEAMLESSHR":
        blocked = []
        for f in HR_MASTERED_FIELDS:
            if f in data:
                db_field = field_map.get(f, f)
                if getattr(person, db_field, None) != data[f]:
                    blocked.append(f)
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "This employee is managed by SeamlessHR (system of record). "
                    f"These fields are read-only here: {', '.join(sorted(blocked))}. "
                    "Update them in SeamlessHR; they sync back to ApexPOB."
                ),
            )

    # Snapshot the old value of each field about to change, for the audit trail (#1).
    _to_j = lambda v: v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
    changed = {}
    for schema_field, db_field in field_map.items():
        if schema_field in data:
            old, new = getattr(person, db_field, None), data[schema_field]
            if old != new:
                changed[db_field] = (_to_j(old), _to_j(new))
            setattr(person, db_field, new)

    # Keep derived fields in sync
    if "first_name" in data or "last_name" in data:
        person.full_name = f"{person.first_name or ''} {person.last_name or ''}".strip()
    if "is_onboard" in data:
        person.is_pob = data["is_onboard"]

    # Department is stored twice — department_id (the real link) and department
    # (a display name). They must never disagree: shifts hang off the ID via
    # departments.default_shift_id, while every screen shows the NAME. A caller
    # that sets only one leaves a record that reads "Maintenance" but inherits
    # Marine's night shift. Reconcile whichever side was supplied.
    if "department_id" in data and "department" not in data:
        if person.department_id:
            drow = db.execute(
                text("SELECT name FROM departments WHERE id = :i"), {"i": person.department_id}
            ).fetchone()
            person.department = drow[0] if drow else None
        else:
            person.department = None
    elif "department" in data and "department_id" not in data:
        if person.department:
            drow = db.execute(text(
                "SELECT id FROM departments WHERE lower(name) = lower(:n) OR lower(code) = lower(:n) "
                "ORDER BY id LIMIT 1"
            ), {"n": person.department}).fetchone()
            person.department_id = drow[0] if drow else None
        else:
            person.department_id = None

    db.commit()
    db.refresh(person)

    # Record who changed which fields (old → new) in the operation log
    # (base_operationlog — the durable audit table). Best-effort: never fail the update.
    if changed:
        try:
            import json as _json
            from ..models.biotime_models import BaseOperationLog
            db.add(BaseOperationLog(
                user_id=getattr(current_user, "id", None),
                action="PROFILE_UPDATE",
                table_name="personnel",
                record_id=person.id,
                old_values=_json.dumps({k: v[0] for k, v in changed.items()}),
                new_values=_json.dumps({k: v[1] for k, v in changed.items()}),
            ))
            db.commit()
        except Exception as e:
            db.rollback()
            import logging
            logging.getLogger(__name__).warning("Audit log for personnel %s failed: %s", person.id, e)

    return _person_to_dict(person)


@router.delete("/{personnel_id}")
async def delete_personnel(
    personnel_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """Delete personnel"""
    personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
    if not personnel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personnel not found"
        )

    # SeamlessHR owns the employee lifecycle — don't allow deleting a mastered record
    # in ApexPOB (offboard in SeamlessHR; the change syncs back).
    if getattr(personnel, "hr_source", None) == "SEAMLESSHR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This employee is managed by SeamlessHR and cannot be deleted in ApexPOB. "
                   "Offboard them in SeamlessHR.",
        )

    try:
        from sqlalchemy import text
        p = {"personnel_id": personnel_id}

        # The DB trigger sync_personnel_to_employee() fires on DELETE personnel
        # and tries to DELETE from personnel_employee.  Several att_* and other
        # tables FK-reference personnel_employee.id WITHOUT ON DELETE CASCADE,
        # so we must remove those rows first or the trigger raises a
        # ForeignKeyViolation.  Use savepoints so an absent table/column
        # (e.g. after a schema migration) doesn't roll back the whole tx.
        pe_row = db.execute(
            text(
                "SELECT pe.id FROM personnel_employee pe "
                "JOIN personnel prs ON pe.emp_code = prs.emp_code "
                "WHERE prs.id = :personnel_id"
            ),
            p,
        ).fetchone()
        if pe_row:
            pe_id = pe_row[0]
            pe_p = {"pe_id": pe_id}
            # All tables whose emp_id/user_id/personnel_id column FK-references
            # personnel_employee.id without CASCADE.
            _pe_dep_tables = [
                ("att_report",           "emp_id"),
                ("att_exception",        "emp_id"),
                ("att_overtime",         "emp_id"),
                ("att_manual_log",       "emp_id"),
                ("checkinout",           "user_id"),
                ("onboarding_task",      "emp_id"),
                ("transport_crew",       "personnel_id"),
                ("vis_pre_registration", "host_emp_id"),
                ("vis_visit_log",        "host_emp_id"),
                ("mtg_attendee",         "emp_id"),
                ("ssr_userdevicebind",   "user_id"),
            ]
            for _tbl, _col in _pe_dep_tables:
                _sp = f"sp_pe_{_tbl}"
                try:
                    db.execute(text(f"SAVEPOINT {_sp}"))
                    db.execute(text(f"DELETE FROM {_tbl} WHERE {_col} = :pe_id"), pe_p)
                except Exception:
                    db.execute(text(f"ROLLBACK TO SAVEPOINT {_sp}"))
            # Nullable organiser/approval references — NULL them rather than
            # deleting the whole booking/action-item row.
            _pe_nullable_refs = [
                ("mtg_booking",          "organizer_emp_id"),
                ("mtg_booking",          "approval_by"),
                ("mtg_action_item",      "assignee_emp_id"),
                ("mtg_action_item",      "created_by"),
                ("mtg_minutes",          "uploaded_by"),
                ("vis_pre_registration", "approval_by"),
                ("emergency_device_maintenance", "supervisor_id"),
                ("emergency_device_maintenance", "technician_id"),
                ("mtd_induction_record", "trainer_emp_id"),
            ]
            for _tbl, _col in _pe_nullable_refs:
                _sp = f"sp_pe_null_{_tbl}_{_col}"
                try:
                    db.execute(text(f"SAVEPOINT {_sp}"))
                    db.execute(text(f"UPDATE {_tbl} SET {_col} = NULL WHERE {_col} = :pe_id"), pe_p)
                except Exception:
                    db.execute(text(f"ROLLBACK TO SAVEPOINT {_sp}"))

        # Clean up FK-dependent rows on personnel.id — use savepoints so a
        # missing table/column doesn't roll back the whole transaction.
        for table in (
            "department_personnel",
            "personnel_department",
            "zone_personnel_assignments",
            "zone_personnel_tracking",
            "personnel_assignments",
            "transport_assignments",
            "contract_assignments",
            "position_assignments",
        ):
            sp = f"sp_{table}"
            try:
                db.execute(text(f"SAVEPOINT {sp}"))
                db.execute(text(f"DELETE FROM {table} WHERE personnel_id = :personnel_id"), p)
            except Exception:
                db.execute(text(f"ROLLBACK TO SAVEPOINT {sp}"))

        db.execute(text("DELETE FROM personnel WHERE id = :personnel_id"), p)
        db.commit()
        return {"message": "Personnel deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete personnel: {str(e)}"
        )




@router.get("/stats/summary")
async def get_personnel_stats(db: Session = Depends(get_db)) -> dict:
    """Get personnel statistics"""
    total = db.query(Personnel).count()
    active = db.query(Personnel).filter(Personnel.status == PersonnelStatus.ACTIVE).count()
    inactive = db.query(Personnel).filter(Personnel.status == PersonnelStatus.INACTIVE).count()
    on_leave = db.query(Personnel).filter(Personnel.status == PersonnelStatus.ON_LEAVE).count()
    onboard = db.query(Personnel).filter(Personnel.is_onboard == True).count()
    
    return {
        "total_personnel": total,
        "active_personnel": active,
        "inactive_personnel": inactive,
        "on_leave_personnel": on_leave,
        "personnel_onboard": onboard,
        "personnel_not_onboard": total - onboard
    }



@router.post("/{personnel_id}/upload-photo")
async def upload_personnel_photo(
    personnel_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> dict:
    """
    Upload personnel photo
    
    Args:
        personnel_id: Personnel ID
        file: Photo file to upload
        db: Database session
        
    Returns:
        Upload result with photo URL
    """
    try:
        photo_url = await file_upload_service.upload_personnel_photo(
            file=file,
            personnel_id=personnel_id,
            db=db
        )
        
        return {
            "success": True,
            "message": "Photo uploaded successfully",
            "photo_url": photo_url,
            "personnel_id": personnel_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload photo: {str(e)}"
        )


@router.delete("/{personnel_id}/photo")
async def delete_personnel_photo(
    personnel_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """
    Delete personnel photo
    
    Args:
        personnel_id: Personnel ID
        db: Database session
        
    Returns:
        Deletion result
    """
    try:
        success = file_upload_service.delete_personnel_photo(
            personnel_id=personnel_id,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found or no photo to delete"
            )
        
        return {
            "success": True,
            "message": "Photo deleted successfully",
            "personnel_id": personnel_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete photo: {str(e)}"
        )


@router.post("/import/excel")
async def import_personnel_from_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Import personnel from Excel file
    
    Args:
        file: Excel file to import
        db: Database session
        
    Returns:
        Import result with statistics
    """
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)"
        )
    
    result = await bulk_import_service.import_from_excel(file, db)
    return result


@router.post("/import/csv")
async def import_personnel_from_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Import personnel from CSV file
    
    Args:
        file: CSV file to import
        db: Database session
        
    Returns:
        Import result with statistics
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file (.csv)"
        )
    
    result = await bulk_import_service.import_from_csv(file, db)
    return result


@router.get("/import/template/excel")
async def get_excel_template():
    """
    Download Excel import template
    
    Returns:
        Excel template file
    """
    template_bytes = await bulk_import_service.get_import_template("excel")
    
    return StreamingResponse(
        io.BytesIO(template_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=personnel_import_template.xlsx"}
    )


@router.get("/import/template/csv")
async def get_csv_template():
    """
    Download CSV import template
    
    Returns:
        CSV template file
    """
    template_bytes = await bulk_import_service.get_import_template("csv")
    
    return StreamingResponse(
        io.BytesIO(template_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=personnel_import_template.csv"}
    )


@router.get("/search/advanced", response_model=List[PersonnelResponse])
async def advanced_personnel_search(
    q: str = Query(..., description="Search query"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to search: name,badge_id,email,phone,company,role,department"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
) -> List[Personnel]:
    """
    Advanced personnel search with field-specific search
    
    Args:
        q: Search query string
        fields: Comma-separated fields to search (default: all fields)
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of matching personnel
    """
    query = db.query(Personnel)
    
    # Default fields if none specified
    if not fields:
        fields = "name,badge_id,email,phone,company,role,department"
    
    field_list = [field.strip().lower() for field in fields.split(',')]
    
    # Build search conditions
    search_conditions = []
    search_term = f"%{q}%"
    
    if 'name' in field_list:
        search_conditions.append(Personnel.full_name.ilike(search_term))
    
    if 'badge_id' in field_list:
        search_conditions.append(Personnel.badge_id.ilike(search_term))
    
    if 'email' in field_list:
        search_conditions.append(Personnel.email.ilike(search_term))
    
    if 'phone' in field_list:
        search_conditions.append(Personnel.phone.ilike(search_term))
    
    if 'company' in field_list:
        search_conditions.append(Personnel.company.ilike(search_term))
    
    if 'role' in field_list:
        search_conditions.append(Personnel.role.ilike(search_term))
    
    if 'department' in field_list:
        search_conditions.append(Personnel.department.ilike(search_term))
    
    # Apply search conditions with OR logic
    if search_conditions:
        from sqlalchemy import or_
        query = query.filter(or_(*search_conditions))
    
    # Order by relevance (exact matches first, then partial)
    query = query.order_by(
        Personnel.full_name.ilike(f"{q}").desc(),
        Personnel.badge_id.ilike(f"{q}").desc(),
        Personnel.full_name.asc()
    )
    
    personnel = query.offset(skip).limit(limit).all()
    return personnel


@router.get("/search/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
) -> Dict[str, List[str]]:
    """
    Get search suggestions for personnel
    
    Args:
        q: Search query string
        limit: Maximum number of suggestions to return
        db: Database session
        
    Returns:
        Dictionary with suggestions for different fields
    """
    search_term = f"%{q}%"
    
    # Get name suggestions
    name_suggestions = db.query(Personnel.full_name).filter(
        Personnel.full_name.ilike(search_term)
    ).limit(limit).all()
    name_suggestions = [name[0] for name in name_suggestions]
    
    # Get badge ID suggestions
    badge_suggestions = db.query(Personnel.badge_id).filter(
        Personnel.badge_id.ilike(search_term)
    ).limit(limit).all()
    badge_suggestions = [badge[0] for badge in badge_suggestions]
    
    # Get company suggestions
    company_suggestions = db.query(Personnel.company).filter(
        Personnel.company.ilike(search_term)
    ).distinct().limit(limit).all()
    company_suggestions = [company[0] for company in company_suggestions]
    
    # Get role suggestions
    role_suggestions = db.query(Personnel.role).filter(
        Personnel.role.ilike(search_term)
    ).distinct().limit(limit).all()
    role_suggestions = [role[0] for role in role_suggestions]
    
    # Get department suggestions
    department_suggestions = db.query(Personnel.department).filter(
        Personnel.department.ilike(search_term)
    ).distinct().limit(limit).all()
    department_suggestions = [dept[0] for dept in department_suggestions if dept[0]]
    
    return {
        "names": name_suggestions,
        "badge_ids": badge_suggestions,
        "companies": company_suggestions,
        "roles": role_suggestions,
        "departments": department_suggestions
    }


@router.get("/{personnel_id}", response_model=Dict[str, Any])
async def get_personnel_by_id(
    personnel_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a single employee with full BioTime + POB fields"""
    person = db.query(Personnel).filter(Personnel.id == personnel_id).first()
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Personnel not found")
    return _person_to_dict(person)


@router.post("/{personnel_id}/status")
async def update_personnel_status(
    personnel_id: int,
    status: PersonnelStatus,
    location: Optional[str] = None,
    zone: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update personnel status
    
    Args:
        personnel_id: Personnel ID
        status: New status
        location: Current location (optional)
        zone: Current zone (optional)
        notes: Status change notes (optional)
        db: Database session
        
    Returns:
        Status update result
    """
    try:
        result = await personnel_status_service.update_personnel_status(
            personnel_id=personnel_id,
            new_status=status,
            location=location,
            zone=zone,
            notes=notes,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update personnel status: {str(e)}"
        )


@router.post("/{personnel_id}/check-in")
async def check_in_personnel(
    personnel_id: int,
    location: str,
    zone: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check in personnel (mark as ONBOARD)
    
    Args:
        personnel_id: Personnel ID
        location: Check-in location
        zone: Check-in zone (optional)
        notes: Check-in notes (optional)
        db: Database session
        
    Returns:
        Check-in result
    """
    try:
        result = await personnel_status_service.check_in_personnel(
            personnel_id=personnel_id,
            location=location,
            zone=zone,
            notes=notes,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check in personnel: {str(e)}"
        )


@router.post("/{personnel_id}/check-out")
async def check_out_personnel(
    personnel_id: int,
    location: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check out personnel (mark as OFFBOARD)
    
    Args:
        personnel_id: Personnel ID
        location: Check-out location (optional)
        notes: Check-out notes (optional)
        db: Database session
        
    Returns:
        Check-out result
    """
    try:
        result = await personnel_status_service.check_out_personnel(
            personnel_id=personnel_id,
            location=location,
            notes=notes,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check out personnel: {str(e)}"
        )


@router.get("/{personnel_id}/status-history")
async def get_personnel_status_history(
    personnel_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get personnel status history
    
    Args:
        personnel_id: Personnel ID
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of status history records
    """
    try:
        history = await personnel_status_service.get_personnel_status_history(
            personnel_id=personnel_id,
            limit=limit,
            db=db
        )
        return history
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personnel status history: {str(e)}"
        )


@router.get("/{personnel_id}/certifications")
async def get_personnel_certifications(
    personnel_id: int,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get personnel certifications"""
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        # Extract certifications from JSONB field
        certifications = personnel.certifications or []
        
        # Format certifications for frontend
        formatted_certs = []
        for cert in certifications:
            formatted_certs.append({
                "id": cert.get("id"),
                "name": cert.get("name", "Unknown Certification"),
                "number": cert.get("number", ""),
                "issuer": cert.get("issuer", ""),
                "issue_date": cert.get("issue_date"),
                "expiry_date": cert.get("expiry_date"),
                "status": cert.get("status", "unknown"),
                "certificate_url": cert.get("certificate_url"),
                "verification_status": cert.get("verification_status", "pending")
            })
        
        return formatted_certs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get certifications: {str(e)}"
        )


@router.get("/{personnel_id}/emergency-contacts")
async def get_personnel_emergency_contacts(
    personnel_id: int,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get personnel emergency contacts"""
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        # Extract emergency contacts from JSONB field
        emergency_contacts = personnel.emergency_contact or []
        
        # Handle both single contact and array of contacts
        if isinstance(emergency_contacts, dict):
            emergency_contacts = [emergency_contacts]
        
        # Format emergency contacts for frontend
        formatted_contacts = []
        for contact in emergency_contacts:
            formatted_contacts.append({
                "id": contact.get("id"),
                "full_name": contact.get("full_name", ""),
                "relationship": contact.get("relationship", ""),
                "phone": contact.get("phone", ""),
                "mobile": contact.get("mobile", ""),
                "email": contact.get("email", ""),
                "is_primary": contact.get("is_primary", False),
                "address": contact.get("address", ""),
                "city": contact.get("city", ""),
                "state": contact.get("state", ""),
                "postal_code": contact.get("postal_code", "")
            })
        
        return formatted_contacts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get emergency contacts: {str(e)}"
        )


@router.get("/{personnel_id}/activity")
async def get_personnel_activity(
    personnel_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get personnel recent activity"""
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        # Get attendance logs for this personnel
        attendance_logs = db.query(AttendanceLog).filter(
            AttendanceLog.personnel_id == personnel_id
        ).order_by(AttendanceLog.timestamp.desc()).limit(limit).all()
        
        # Format activity for frontend
        activities = []
        for log in attendance_logs:
            activities.append({
                "id": log.id,
                "type": log.event_type.lower(),
                "title": f"{log.event_type.replace('_', ' ').title()}",
                "description": f"Personnel {log.event_type.replace('_', ' ')} at {log.location or 'Unknown Location'}",
                "location": log.location,
                "timestamp": log.timestamp.isoformat(),
                "device_id": log.device_id,
                "verification_method": log.verification_method
            })
        
        return activities
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personnel activity: {str(e)}"
        )


@router.post("/{personnel_id}/emergency-contacts")
async def add_personnel_emergency_contact(
    personnel_id: int,
    contact_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Add emergency contact for personnel"""
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        # Get existing contacts
        existing_contacts = personnel.emergency_contact or []
        if isinstance(existing_contacts, dict):
            existing_contacts = [existing_contacts]
        
        # Add new contact
        new_contact = {
            "id": len(existing_contacts) + 1,
            "full_name": contact_data.get("full_name"),
            "relationship": contact_data.get("relationship"),
            "phone": contact_data.get("phone"),
            "mobile": contact_data.get("mobile"),
            "email": contact_data.get("email"),
            "is_primary": contact_data.get("is_primary", False),
            "address": contact_data.get("address"),
            "city": contact_data.get("city"),
            "state": contact_data.get("state"),
            "postal_code": contact_data.get("postal_code"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        existing_contacts.append(new_contact)
        personnel.emergency_contact = existing_contacts
        
        db.commit()
        
        return {
            "success": True,
            "message": "Emergency contact added successfully",
            "contact": new_contact
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add emergency contact: {str(e)}"
        )


@router.post("/{personnel_id}/certifications")
async def add_personnel_certification(
    personnel_id: int,
    certification_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add certification to personnel record
    
    Args:
        personnel_id: Personnel ID
        certification_data: Certification details
        db: Database session
        
    Returns:
        Added certification information
    """
    try:
        result = await certification_training_service.add_personnel_certification(
            personnel_id=personnel_id,
            certification_data=certification_data,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add certification: {str(e)}"
        )


@router.get("/{personnel_id}/certifications")
async def get_personnel_certifications(
    personnel_id: int,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get personnel certifications
    
    Args:
        personnel_id: Personnel ID
        status: Filter by status (optional)
        db: Database session
        
    Returns:
        List of certifications
    """
    try:
        certifications = await certification_training_service.get_personnel_certifications(
            personnel_id=personnel_id,
            status=status,
            db=db
        )
        return certifications
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get certifications: {str(e)}"
        )


@router.get("/certifications/compliance-report")
async def get_certification_compliance_report(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get certification compliance report
    
    Args:
        db: Database session
        
    Returns:
        Compliance report statistics
    """
    try:
        report = await certification_training_service.get_certification_compliance_report(db=db)
        return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get compliance report: {str(e)}"
        )


@router.post("/{personnel_id}/location")
async def update_personnel_location(
    personnel_id: int,
    location: str,
    zone: Optional[str] = None,
    coordinates: Optional[Dict[str, float]] = None,
    source: str = "MANUAL",
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update personnel location in real-time
    
    Args:
        personnel_id: Personnel ID
        location: Current location
        zone: Current zone (optional)
        coordinates: GPS coordinates (optional)
        source: Location source (MANUAL, BIOMETRIC, RFID, GPS)
        notes: Location update notes (optional)
        db: Database session
        
    Returns:
        Location update result
    """
    try:
        result = await zone_service.update_personnel_location(
            personnel_id=personnel_id,
            location=location,
            zone=zone,
            coordinates=coordinates,
            source=source,
            notes=notes,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update personnel location: {str(e)}"
        )


@router.get("/{personnel_id}/location-history")
async def get_personnel_location_history(
    personnel_id: int,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get personnel location history
    
    Args:
        personnel_id: Personnel ID
        hours: Number of hours of history to retrieve
        db: Database session
        
    Returns:
        List of location history records
    """
    try:
        history = await zone_service.get_personnel_location_history(
            personnel_id=personnel_id,
            hours=hours,
            db=db
        )
        return history
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get location history: {str(e)}"
        )


@router.post("/{personnel_id}/emergency-contacts")
async def add_emergency_contact(
    personnel_id: int,
    contact_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add emergency contact to personnel record
    
    Args:
        personnel_id: Personnel ID
        contact_data: Contact details
        db: Database session
        
    Returns:
        Added contact information
    """
    try:
        result = await emergency_contact_service.add_emergency_contact(
            personnel_id=personnel_id,
            contact_data=contact_data,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add emergency contact: {str(e)}"
        )


@router.post("/{personnel_id}/medical-fitness")
async def create_medical_fitness_record(
    personnel_id: int,
    fitness_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create medical fitness record for personnel
    
    Args:
        personnel_id: Personnel ID
        fitness_data: Fitness assessment details
        db: Database session
        
    Returns:
        Created fitness record information
    """
    try:
        result = await medical_fitness_service.create_medical_fitness_record(
            personnel_id=personnel_id,
            fitness_data=fitness_data,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create medical fitness record: {str(e)}"
        )


@router.get("/{personnel_id}/medical-fitness")
async def get_personnel_fitness_records(
    personnel_id: int,
    assessment_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get personnel medical fitness records
    
    Args:
        personnel_id: Personnel ID
        assessment_type: Filter by assessment type (optional)
        status: Filter by fitness status (optional)
        db: Database session
        
    Returns:
        List of fitness records
    """
    try:
        records = await medical_fitness_service.get_personnel_fitness_records(
            personnel_id=personnel_id,
            assessment_type=assessment_type,
            status=status,
            db=db
        )
        return records
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fitness records: {str(e)}"
        )


@router.put("/{personnel_id}/medical-fitness/{fitness_record_id}/status")
async def update_fitness_status(
    personnel_id: int,
    fitness_record_id: str,
    fitness_status: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update fitness status
    
    Args:
        personnel_id: Personnel ID
        fitness_record_id: Fitness record ID
        fitness_status: New fitness status
        notes: Update notes (optional)
        db: Database session
        
    Returns:
        Update result
    """
    try:
        result = await medical_fitness_service.update_fitness_status(
            personnel_id=personnel_id,
            fitness_record_id=fitness_record_id,
            fitness_status=fitness_status,
            notes=notes,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update fitness status: {str(e)}"
        )


@router.post("/{personnel_id}/medical-alerts")
async def create_medical_alert(
    personnel_id: int,
    alert_type: str,
    message: str,
    severity: str = "MEDIUM",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create medical alert for personnel
    
    Args:
        personnel_id: Personnel ID
        alert_type: Alert type
        message: Alert message
        severity: Alert severity (LOW, MEDIUM, HIGH, CRITICAL)
        db: Database session
        
    Returns:
        Alert creation result
    """
    try:
        alert = await medical_fitness_service.create_medical_alert(
            personnel_id=personnel_id,
            alert_type=alert_type,
            message=message,
            severity=severity,
            db=db
        )
        return alert
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create medical alert: {str(e)}"
        )


@router.get("/{personnel_id}/medical-alerts")
async def get_medical_alerts(
    personnel_id: int,
    severity: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get medical alerts
    
    Args:
        personnel_id: Filter by personnel ID (optional)
        severity: Filter by severity (optional)
        resolved: Filter by resolved status (optional)
        db: Database session
        
    Returns:
        List of medical alerts
    """
    try:
        alerts = await medical_fitness_service.get_medical_alerts(
            personnel_id=personnel_id,
            severity=severity,
            resolved=resolved,
            db=db
        )
        return alerts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get medical alerts: {str(e)}"
        )


@router.get("/medical-fitness/expiring")
async def get_fitness_expiry_alerts(
    days_ahead: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get fitness records expiring within specified days
    
    Args:
        days_ahead: Number of days ahead to check
        db: Database session
        
    Returns:
        List of expiring fitness records
    """
    try:
        expiring_records = await medical_fitness_service.get_fitness_expiry_alerts(
            days_ahead=days_ahead,
            db=db
        )
        return expiring_records
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get expiring fitness records: {str(e)}"
        )


@router.get("/medical-fitness/compliance-report")
async def get_fitness_compliance_report(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get medical fitness compliance report
    
    Args:
        db: Database session
        
    Returns:
        Fitness compliance statistics
    """
    try:
        report = await medical_fitness_service.get_fitness_compliance_report(db=db)
        return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fitness compliance report: {str(e)}"
        )


@router.get("/{personnel_id}/medical-summary")
async def get_medical_summary(
    personnel_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive medical summary for personnel
    
    Args:
        personnel_id: Personnel ID
        db: Database session
        
    Returns:
        Medical summary
    """
    try:
        summary = await medical_fitness_service.get_medical_summary(
            personnel_id=personnel_id,
            db=db
        )
        return summary
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get medical summary: {str(e)}"
        )


@router.post("/{personnel_id}/badges")
async def create_badge_record(
    personnel_id: int,
    badge_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create badge record for personnel
    
    Args:
        personnel_id: Personnel ID
        badge_data: Badge details
        db: Database session
        
    Returns:
        Created badge record information
    """
    try:
        result = await badge_printing_service.create_badge_record(
            personnel_id=personnel_id,
            badge_data=badge_data,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create badge record: {str(e)}"
        )


@router.get("/{personnel_id}/badges")
async def get_personnel_badges(
    personnel_id: int,
    badge_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get personnel badge records
    
    Args:
        personnel_id: Personnel ID
        badge_type: Filter by badge type (optional)
        status: Filter by printing status (optional)
        db: Database session
        
    Returns:
        List of badge records
    """
    try:
        badges = await badge_printing_service.get_personnel_badges(
            personnel_id=personnel_id,
            badge_type=badge_type,
            status=status,
            db=db
        )
        return badges
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get badge records: {str(e)}"
        )


@router.put("/{personnel_id}/badges/{badge_record_id}/print-status")
async def update_badge_printing_status(
    personnel_id: int,
    badge_record_id: str,
    printing_status: str,
    printer_used: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update badge printing status
    
    Args:
        personnel_id: Personnel ID
        badge_record_id: Badge record ID
        printing_status: New printing status
        printer_used: Printer used (optional)
        notes: Update notes (optional)
        db: Database session
        
    Returns:
        Update result
    """
    try:
        result = await badge_printing_service.update_badge_printing_status(
            personnel_id=personnel_id,
            badge_record_id=badge_record_id,
            printing_status=printing_status,
            printer_used=printer_used,
            notes=notes,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update badge printing status: {str(e)}"
        )


@router.get("/badges/printing-summary")
async def get_badge_printing_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get badge printing summary statistics
    
    Args:
        db: Database session
        
    Returns:
        Badge printing summary
    """
    try:
        summary = await badge_printing_service.get_badge_printing_summary(db=db)
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get badge printing summary: {str(e)}"
        )


@router.post("/badges/batch")
async def create_badge_printing_batch(
    personnel_ids: List[int],
    badge_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create badge records for multiple personnel (batch operation)
    
    Args:
        personnel_ids: List of personnel IDs
        badge_data: Common badge data
        db: Database session
        
    Returns:
        Batch creation result
    """
    try:
        result = await badge_printing_service.create_badge_printing_batch(
            personnel_ids=personnel_ids,
            badge_data=badge_data,
            db=db
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create badge batch: {str(e)}"
        )


@router.get("/badges/expiring")
async def get_badge_expiry_alerts(
    days_ahead: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get badges expiring within specified days
    
    Args:
        days_ahead: Number of days ahead to check
        db: Database session
        
    Returns:
        List of expiring badges
    """
    try:
        expiring_badges = await badge_printing_service.get_badge_expiry_alerts(
            days_ahead=days_ahead,
            db=db
        )
        return expiring_badges
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get expiring badges: {str(e)}"
        )


@router.post("/badges/template")
async def generate_badge_template(
    badge_type: str,
    access_level: str,
    template_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate badge template for printing
    
    Args:
        badge_type: Badge type
        access_level: Access level
        template_data: Template configuration data
        db: Database session
        
    Returns:
        Badge template configuration
    """
    try:
        template = await badge_printing_service.generate_badge_template(
            badge_type=badge_type,
            access_level=access_level,
            template_data=template_data
        )
        return template
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate badge template: {str(e)}"
        )


@router.post("/{personnel_id}/audit-trail")
async def create_audit_entry(
    personnel_id: int,
    event_type: str,
    description: str,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    severity: str = "LOW",
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create audit entry for personnel
    
    Args:
        personnel_id: Personnel ID
        event_type: Type of event
        description: Event description
        old_values: Previous values (optional)
        new_values: New values (optional)
        severity: Event severity level
        user_id: User who performed the action (optional)
        ip_address: IP address of the action (optional)
        user_agent: User agent string (optional)
        db: Database session
        
    Returns:
        Created audit entry
    """
    try:
        result = await audit_trail_service.create_audit_entry(
            personnel_id=personnel_id,
            event_type=event_type,
            description=description,
            old_values=old_values,
            new_values=new_values,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create audit entry: {str(e)}"
        )


@router.get("/{personnel_id}/audit-trail")
async def get_personnel_audit_trail(
    personnel_id: int,
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get personnel audit trail
    
    Args:
        personnel_id: Personnel ID
        event_type: Filter by event type (optional)
        severity: Filter by severity (optional)
        start_date: Filter by start date (optional)
        end_date: Filter by end date (optional)
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of audit entries
    """
    try:
        audit_trail = await audit_trail_service.get_personnel_audit_trail(
            personnel_id=personnel_id,
            event_type=event_type,
            severity=severity,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            db=db
        )
        return audit_trail
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit trail: {str(e)}"
        )


@router.get("/{personnel_id}/audit-summary")
async def get_audit_summary(
    personnel_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get audit summary for personnel
    
    Args:
        personnel_id: Personnel ID
        days: Number of days to analyze
        db: Database session
        
    Returns:
        Audit summary statistics
    """
    try:
        summary = await audit_trail_service.get_audit_summary(
            personnel_id=personnel_id,
            days=days,
            db=db
        )
        return summary
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit summary: {str(e)}"
        )


@router.get("/{personnel_id}/compliance-report")
async def get_compliance_report(
    personnel_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get compliance report for personnel
    
    Args:
        personnel_id: Personnel ID
        db: Database session
        
    Returns:
        Compliance report
    """
    try:
        report = await audit_trail_service.get_compliance_report(
            personnel_id=personnel_id,
            db=db
        )
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get compliance report: {str(e)}"
        )


@router.get("/audit/system-report")
async def get_system_audit_report(
    days: int = Query(30, ge=1, le=365),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get system-wide audit report
    
    Args:
        days: Number of days to analyze
        event_type: Filter by event type (optional)
        severity: Filter by severity (optional)
        db: Database session
        
    Returns:
        System audit report
    """
    try:
        report = await audit_trail_service.get_system_audit_report(
            days=days,
            event_type=event_type,
            severity=severity,
            db=db
        )
        return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system audit report: {str(e)}"
        )


@router.get("/{personnel_id}/audit-export")
async def export_audit_trail(
    personnel_id: int,
    format_type: str = Query("json", pattern="^(json|csv)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Export audit trail for personnel
    
    Args:
        personnel_id: Personnel ID
        format_type: Export format (json, csv)
        start_date: Filter by start date (optional)
        end_date: Filter by end date (optional)
        db: Database session
        
    Returns:
        Export result
    """
    try:
        export_result = await audit_trail_service.export_audit_trail(
            personnel_id=personnel_id,
            format_type=format_type,
            start_date=start_date,
            end_date=end_date,
            db=db
        )
        return export_result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export audit trail: {str(e)}"
        )


@router.get("/analytics/overview")
async def get_personnel_overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get comprehensive personnel overview analytics
    
    Args:
        db: Database session
        
    Returns:
        Personnel overview analytics
    """
    try:
        overview = await personnel_analytics_service.get_personnel_overview(db=db)
        return overview
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personnel overview: {str(e)}"
        )


@router.get("/analytics/attendance")
async def get_attendance_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get attendance analytics and patterns
    
    Args:
        days: Number of days to analyze
        db: Database session
        
    Returns:
        Attendance analytics data
    """
    try:
        analytics = await personnel_analytics_service.get_attendance_analytics(days=days, db=db)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get attendance analytics: {str(e)}"
        )


@router.get("/analytics/location")
async def get_location_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get location analytics and movement patterns
    
    Args:
        days: Number of days to analyze
        db: Database session
        
    Returns:
        Location analytics data
    """
    try:
        analytics = await personnel_analytics_service.get_location_analytics(days=days, db=db)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get location analytics: {str(e)}"
        )


@router.get("/analytics/certifications")
async def get_certification_analytics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get certification compliance analytics
    
    Args:
        db: Database session
        
    Returns:
        Certification analytics data
    """
    try:
        analytics = await personnel_analytics_service.get_certification_analytics(db=db)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get certification analytics: {str(e)}"
        )


@router.get("/analytics/medical-fitness")
async def get_medical_fitness_analytics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get medical fitness analytics
    
    Args:
        db: Database session
        
    Returns:
        Medical fitness analytics data
    """
    try:
        analytics = await personnel_analytics_service.get_medical_fitness_analytics(db=db)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get medical fitness analytics: {str(e)}"
        )


@router.get("/analytics/performance-metrics")
async def get_performance_metrics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive performance metrics
    
    Args:
        days: Number of days to analyze
        db: Database session
        
    Returns:
        Performance metrics dashboard
    """
    try:
        metrics = await personnel_analytics_service.get_performance_metrics(days=days, db=db)
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance metrics: {str(e)}"
        )


@router.get("/dashboard")
async def get_dashboard_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get comprehensive personnel dashboard data for oil & gas operations
    
    Args:
        db: Database session
        
    Returns:
        Dashboard data with oil & gas specific metrics
    """
    try:
        # Total personnel count
        total_personnel = db.query(Personnel).count()
        
        # Personnel by status
        offshore_count = db.query(Personnel).filter(Personnel.status == PersonnelStatus.OFFSHORE).count()
        onshore_count = db.query(Personnel).filter(Personnel.status == PersonnelStatus.ONSHORE).count()
        transit_count = db.query(Personnel).filter(Personnel.status == PersonnelStatus.TRANSIT).count()
        on_leave_count = db.query(Personnel).filter(Personnel.status == PersonnelStatus.ON_LEAVE).count()
        
        # Safety critical personnel
        safety_critical = db.query(Personnel).filter(Personnel.safety_critical == True).count()
        
        # Personnel by type
        staff_count = db.query(Personnel).filter(Personnel.personnel_type == "STAFF").count()
        contractor_count = db.query(Personnel).filter(Personnel.personnel_type == "CONTRACTOR").count()
        visitor_count = db.query(Personnel).filter(Personnel.personnel_type == "VISITOR").count()
        
        # Biometric enrollment
        biometric_enrolled = db.query(Personnel).filter(Personnel.biometric_enrolled == True).count()
        biometric_not_enrolled = total_personnel - biometric_enrolled
        
        # Compliance metrics
        avg_compliance_score = db.query(func.avg(Personnel.compliance_score)).scalar() or 0
        compliant_count = db.query(Personnel).filter(Personnel.compliance_score >= 90).count()
        expiring_count = db.query(Personnel).filter(Personnel.compliance_score.between(70, 89)).count()
        non_compliant_count = db.query(Personnel).filter(Personnel.compliance_score < 70).count()
        
        # Zone distribution (zones-only architecture)
        zone_query = db.query(
            Personnel.current_zone_id,
            func.count(Personnel.id).label('count')
        ).filter(Personnel.current_zone_id.isnot(None)).group_by(Personnel.current_zone_id).all()
        
        zone_distribution = {
            f"Zone {zone_id}": count for zone_id, count in zone_query
        }
        
        # Company distribution
        company_query = db.query(
            Personnel.company,
            func.count(Personnel.id).label('count')
        ).group_by(Personnel.company).all()
        
        company_distribution = {
            company: count for company, count in company_query
        }
        
        # Recent activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        recent_updates = db.query(Personnel).filter(
            Personnel.updated_at >= yesterday
        ).count()
        
        recent_checkins = db.query(Personnel).filter(
            Personnel.last_seen >= yesterday
        ).count()
        
        dashboard_data = {
            # Overview metrics
            "total_personnel": total_personnel,
            "offshore_count": offshore_count,
            "onshore_count": onshore_count,
            "transit_count": transit_count,
            "on_leave_count": on_leave_count,
            "safety_critical": safety_critical,
            "compliance_score": round(float(avg_compliance_score), 1),
            
            # Personnel type breakdown
            "personnel_types": {
                "STAFF": staff_count,
                "CONTRACTOR": contractor_count,
                "VISITOR": visitor_count
            },
            
            # Biometric metrics
            "biometric_metrics": {
                "enrolled": biometric_enrolled,
                "not_enrolled": biometric_not_enrolled,
                "enrollment_rate": round((biometric_enrolled / total_personnel * 100) if total_personnel > 0 else 0, 1)
            },
            
            # Compliance metrics
            "compliance_metrics": {
                "compliant": compliant_count,
                "expiring": expiring_count,
                "non_compliant": non_compliant_count,
                "average_score": round(float(avg_compliance_score), 1)
            },
            
            # Zone and company distribution (zones-only architecture)
            "zone_distribution": zone_distribution,
            "company_distribution": company_distribution,
            
            # Recent activity
            "recent_activity": {
                "updates": recent_updates,
                "checkins": recent_checkins
            },
            
            # Status breakdown
            "status_breakdown": {
                "ACTIVE": db.query(Personnel).filter(Personnel.status == PersonnelStatus.ACTIVE).count(),
                "INACTIVE": db.query(Personnel).filter(Personnel.status == PersonnelStatus.INACTIVE).count(),
                "ON_LEAVE": on_leave_count,
                "TRANSIT": transit_count,
                "OFFSHORE": offshore_count,
                "ONSHORE": onshore_count
            }
        }
        
        return dashboard_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard data: {str(e)}"
        )


@router.post("/{personnel_id}/biometric-enroll")
async def enroll_biometric(
    personnel_id: int,
    biometric_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Enroll personnel in biometric system
    
    Args:
        personnel_id: Personnel ID
        biometric_data: Biometric enrollment data
        db: Database session
        
    Returns:
        Enrollment result
    """
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        # Update biometric enrollment status
        personnel.biometric_enrolled = True
        personnel.biometric_data = biometric_data
        
        # Calculate compliance score based on biometric enrollment
        if personnel.compliance_score < 70:
            personnel.compliance_score = min(100, personnel.compliance_score + 20)
        
        db.commit()
        
        return {
            "success": True,
            "message": "Biometric enrollment successful",
            "personnel_id": personnel_id,
            "enrolled_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enroll biometric: {str(e)}"
        )


@router.put("/{personnel_id}/emergency-contact")
async def update_emergency_contact(
    personnel_id: int,
    emergency_contact: Dict[str, str],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update emergency contact information
    
    Args:
        personnel_id: Personnel ID
        emergency_contact: Emergency contact data
        db: Database session
        
    Returns:
        Update result
    """
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        # Update emergency contact
        personnel.emergency_contact = emergency_contact
        
        db.commit()
        
        return {
            "success": True,
            "message": "Emergency contact updated successfully",
            "personnel_id": personnel_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update emergency contact: {str(e)}"
        )


@router.get("/{personnel_id}/compliance-status")
async def get_compliance_status(
    personnel_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get personnel compliance status
    
    Args:
        personnel_id: Personnel ID
        db: Database session
        
    Returns:
        Compliance status information
    """
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        # Analyze compliance based on certifications and training
        compliance_issues = []
        
        # Check biometric enrollment
        if not personnel.biometric_enrolled:
            compliance_issues.append("Biometric enrollment required")
        
        # Check emergency contact
        if not personnel.emergency_contact:
            compliance_issues.append("Emergency contact information missing")
        
        # Check compliance score
        compliance_level = "COMPLIANT"
        if personnel.compliance_score < 70:
            compliance_level = "NON_COMPLIANT"
        elif personnel.compliance_score < 90:
            compliance_level = "EXPIRING_SOON"
        
        return {
            "personnel_id": personnel_id,
            "compliance_score": personnel.compliance_score,
            "compliance_level": compliance_level,
            "compliance_issues": compliance_issues,
            "biometric_enrolled": personnel.biometric_enrolled,
            "safety_critical": personnel.safety_critical,
            "last_updated": personnel.updated_at.isoformat() if personnel.updated_at else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get compliance status: {str(e)}"
        )


@router.get("/export/templates")
async def get_export_templates() -> Dict[str, Any]:
    """
    Get available export templates
    
    Returns:
        Export templates and field groups
    """
    try:
        templates = await personnel_export_service.get_export_templates()
        return templates
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get export templates: {str(e)}"
        )


@router.post("/export/preview")
async def get_export_preview(
    template: str = Query("BASIC"),
    filters: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get export preview with sample data
    
    Args:
        template: Export template
        filters: Export filters (optional)
        db: Database session
        
    Returns:
        Export preview with sample records
    """
    try:
        preview = await personnel_export_service.get_export_preview(
            template=template,
            filters=filters,
            db=db
        )
        return preview
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get export preview: {str(e)}"
        )


@router.post("/export")
async def export_personnel_data(
    export_format: str = Query("CSV", pattern="^(csv|excel|json|pdf)$"),
    template: str = Query("BASIC"),
    filters: Optional[Dict[str, Any]] = None,
    fields: Optional[List[str]] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Export personnel data in specified format
    
    Args:
        export_format: Export format (CSV, EXCEL, JSON, PDF)
        template: Export template (BASIC, DETAILED, CONTACTS, etc.)
        filters: Export filters (optional)
        fields: Custom field selection (optional)
        db: Database session
        
    Returns:
        Export result with file data
    """
    try:
        result = await personnel_export_service.export_personnel_data(
            export_format=export_format.upper(),
            template=template,
            filters=filters,
            fields=fields,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export personnel data: {str(e)}"
        )


@router.post("/export/schedule")
async def schedule_export(
    export_config: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Schedule export job for large datasets
    
    Args:
        export_config: Export configuration
        db: Database session
        
    Returns:
        Scheduled export job information
    """
    try:
        job = await personnel_export_service.schedule_export(
            export_config=export_config,
            db=db
        )
        return job
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule export: {str(e)}"
        )


@router.get("/export/history")
async def get_export_history(
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get export history
    
    Args:
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        Export history records
    """
    try:
        history = await personnel_export_service.get_export_history(
            limit=limit,
            db=db
        )
        return history
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get export history: {str(e)}"
        )


@router.get("/{personnel_id}/activity")
async def get_personnel_activity(
    personnel_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get personnel recent activity
    
    Args:
        personnel_id: Personnel ID
        limit: Maximum number of activities to return
        db: Database session
        
    Returns:
        List of recent activities
    """
    try:
        # Get recent activities (this could be from audit trail or events table)
        activities = []
        
        # Get recent activities from audit trail
        activities = []
        try:
            from ..models.audit import AuditLog
            
            # Get audit logs for personnel-related activities
            audit_query = db.query(AuditLog).filter(
                AuditLog.table_name == "personnel"
            ).order_by(AuditLog.created_at.desc()).limit(limit).all()
            
            for audit in audit_query:
                activities.append({
                    "id": audit.id,
                    "title": f"Personnel {audit.action.title()}",
                    "description": audit.description or f"Personnel record was {audit.action}",
                    "timestamp": audit.created_at.isoformat() if audit.created_at else None,
                    "location": "System",
                    "type": audit.action.upper(),
                    "user_id": audit.user_id,
                    "record_id": audit.record_id
                })
        except Exception as e:
            logger.warning(f"Could not fetch personnel activities: {e}")
            # Return empty list if query fails
        
        return activities[:limit]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personnel activity: {str(e)}"
        )


@router.post("/update-badge-ids")
async def update_all_badge_ids(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Update all personnel with auto-generated badge IDs for consistency
    
    This endpoint generates consistent badge IDs based on personnel name and company,
    ensuring that the same person always has the same badge ID across all assignments.
    """
    try:
        from ..services.department_service import DepartmentService
        
        department_service = DepartmentService()
        result = await department_service.update_personnel_badge_ids(db)
        
        if result["success"]:
            return {
                "message": f"Successfully updated {result['updated_count']} of {result['total_personnel']} personnel badge IDs",
                "total_personnel": result["total_personnel"],
                "updated_count": result["updated_count"],
                "updates": result["updates"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to update badge IDs")
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update badge IDs: {str(e)}"
        )


# BioTime Integration Endpoints

@router.post("/sync/biotime")
async def sync_personnel_from_biotime(
    force_sync: bool = Query(False, description="Force full sync regardless of last sync time"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Sync personnel data from BioTime to Apex POB
    
    Args:
        force_sync: Force full sync regardless of last sync time
        db: Database session
        
    Returns:
        Sync result with statistics
    """
    try:
        result = await biotime_sync_service.sync_personnel_from_biotime(db, force_sync=force_sync)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync from BioTime: {str(e)}"
        )


@router.post("/sync/to-biotime")
async def sync_personnel_to_biotime(
    personnel_ids: Optional[List[int]] = Query(None, description="Specific personnel IDs to sync"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Sync personnel data from POB to BioTime
    
    Args:
        personnel_ids: Specific personnel IDs to sync (None for all)
        db: Database session
        
    Returns:
        Sync result with statistics
    """
    try:
        result = await biotime_sync_service.sync_personnel_to_biotime(db, personnel_ids=personnel_ids)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync to BioTime: {str(e)}"
        )


@router.get("/sync/biotime-status")
async def get_biotime_sync_status() -> Dict[str, Any]:
    """
    Get current BioTime synchronization status
    
    Returns:
        Sync status information
    """
    try:
        result = await biotime_sync_service.get_sync_status()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )


@router.post("/sync/biotime/full")
async def force_full_biotime_sync(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Force full synchronization with BioTime
    
    Args:
        db: Database session
        
    Returns:
        Full sync result
    """
    try:
        result = await biotime_sync_service.force_full_sync(db)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to force full sync: {str(e)}"
        )


@router.post("/{personnel_id}/biometric/enroll")
async def enroll_personnel_biometric(
    personnel_id: int,
    biometric_type: str = Query(..., description="Type of biometric (fingerprint, face)"),
    template_data: Dict[str, Any] = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Enroll biometric template for personnel and sync with BioTime
    
    Args:
        personnel_id: Personnel ID
        biometric_type: Type of biometric (fingerprint, face)
        template_data: Template data
        db: Database session
        
    Returns:
        Enrollment result
    """
    try:
        result = await biotime_sync_service.enroll_biometric_template(
            personnel_id=personnel_id,
            biometric_type=biometric_type,
            template_data=template_data,
            db=db
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enroll biometric: {str(e)}"
        )


@router.post("/{personnel_id}/biometric/verify")
async def verify_personnel_biometric(
    personnel_id: int,
    biometric_data: Dict[str, Any] = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Real-time biometric verification
    
    Args:
        personnel_id: Personnel ID
        biometric_data: Biometric data for verification
        db: Database session
        
    Returns:
        Verification result
    """
    try:
        result = await biotime_sync_service.verify_biometric_realtime(
            personnel_id=personnel_id,
            biometric_data=biometric_data,
            db=db
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify biometric: {str(e)}"
        )


@router.get("/{personnel_id}/biometric/templates")
async def get_personnel_biometric_templates(
    personnel_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get biometric templates for personnel
    
    Args:
        personnel_id: Personnel ID
        db: Database session
        
    Returns:
        Biometric templates
    """
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        templates = {
            "fingerprint_templates": personnel.fingerprint_templates or [],
            "face_template": personnel.face_template,
            "biometric_enrolled": personnel.biometric_enrolled,
            "biometric_data": personnel.biometric_data or {}
        }
        
        return {
            "success": True,
            "personnel_id": personnel_id,
            "templates": templates
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get biometric templates: {str(e)}"
        )


@router.delete("/{personnel_id}/biometric/{template_id}")
async def delete_personnel_biometric_template(
    personnel_id: int,
    template_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete biometric template
    
    Args:
        personnel_id: Personnel ID
        template_id: Template ID
        db: Database session
        
    Returns:
        Deletion result
    """
    try:
        personnel = db.query(Personnel).filter(Personnel.id == personnel_id).first()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personnel not found"
            )
        
        # Remove template from local database
        if personnel.fingerprint_templates:
            personnel.fingerprint_templates = [
                t for t in personnel.fingerprint_templates 
                if t.get("id") != template_id
            ]
        
        if template_id == "face_template":
            personnel.face_template = None
        
        # Update biometric enrollment status
        if not personnel.fingerprint_templates and not personnel.face_template:
            personnel.biometric_enrolled = False
        
        personnel.updated_at = datetime.utcnow()
        db.commit()
        
        # TODO: Delete from BioTime when API is available
        
        return {
            "success": True,
            "message": "Biometric template deleted successfully",
            "template_id": template_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete biometric template: {str(e)}"
        )


# ============================================================================
# BioTime 9.5 Compatible Employee Endpoints
# ============================================================================

@router.get("/employees/", response_model=List[EmployeeResponse])
async def get_employees(
    search: Optional[str] = Query(None, description="Search by emp_code/name/dept"),
    dept_id: Optional[int] = Query(None, description="Filter by department"),
    area_id: Optional[int] = Query(None, description="Filter by area"),
    status: Optional[int] = Query(None, description="Filter by status (0=active, 1=resigned)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> List[EmployeeResponse]:
    """Get list of employees with BioTime 9.5 compatibility"""
    service = PersonnelBioTimeService(db)
    return await service.get_employees(
        search=search, dept_id=dept_id, area_id=area_id, 
        status=status, page=page, limit=limit
    )

@router.post("/employees", response_model=EmployeeResponse)
async def create_employee(
    employee: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> EmployeeResponse:
    """Create new employee - BioTime compatible"""
    # Check permissions: Only Superuser/Registrar can POST
    if not current_user.is_superuser and current_user.role not in ['registrar', 'hr_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    service = PersonnelBioTimeService(db)
    result = await service.create_employee(employee, current_user.id)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result['data']

@router.get("/employees/{emp_id}/", response_model=EmployeeResponse)
async def get_employee(
    emp_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> EmployeeResponse:
    """Get employee details by ID"""
    service = PersonnelBioTimeService(db)
    employee = await service.get_employee(emp_id)
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # ESS can only view self
    if current_user.role == 'ess' and current_user.personnel_id != emp_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return employee

@router.put("/employees/{emp_id}", response_model=EmployeeResponse)
async def update_employee(
    emp_id: int,
    employee: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> EmployeeResponse:
    """Update employee - BioTime compatible"""
    service = PersonnelBioTimeService(db)
    
    # Check permissions
    if current_user.role == 'ess' and current_user.personnel_id != emp_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user.role not in ['superuser', 'registrar', 'hr_admin', 'dept_manager']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    result = await service.update_employee(emp_id, employee, current_user.id)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result['data']

@router.delete("/employees/{emp_id}")
async def delete_employee(
    emp_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete employee - Soft delete (set status=1)"""
    # Only Superuser/Registrar can DELETE
    if not current_user.is_superuser and current_user.role not in ['registrar', 'hr_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    service = PersonnelBioTimeService(db)
    result = await service.delete_employee(emp_id, current_user.id)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return {"message": "Employee deleted successfully"}

@router.post("/employees/batch-import")
async def batch_import_employees(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Batch import employees from CSV/XLSX"""
    if not current_user.is_superuser and current_user.role not in ['registrar', 'hr_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    service = PersonnelBioTimeService(db)
    return await service.batch_import_employees(file, current_user.id)

@router.get("/employees/export/")
async def export_employees(
    format: str = Query("xlsx", description="Export format (xlsx/csv)"),
    ids: Optional[str] = Query(None, description="Comma-separated employee IDs"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export employees to Excel/CSV"""
    service = PersonnelBioTimeService(db)
    
    employee_ids = [int(id.strip()) for id in ids.split(',')] if ids else None
    
    if format == "xlsx":
        return await service.export_employees_xlsx(employee_ids)
    else:
        return await service.export_employees_csv(employee_ids)

# BioTime Biometric endpoints
@router.post("/employees/{emp_id}/enroll")
async def enroll_employee_biometric(
    emp_id: int,
    enrollment_data: dict = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Enroll biometric - Send command to device"""
    service = PersonnelBioTimeService(db)
    
    if not current_user.is_superuser and current_user.role not in ['registrar', 'hr_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    result = await service.enroll_biometric(emp_id, enrollment_data, current_user.id)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result

@router.post("/employees/{emp_id}/bio-data")
async def save_biometric_data(
    emp_id: int,
    bio_data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Save biometric template to DB and sync to devices"""
    service = PersonnelBioTimeService(db)
    
    if not current_user.is_superuser and current_user.role not in ['registrar', 'hr_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    result = await service.save_biometric_data(emp_id, bio_data, current_user.id)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result

@router.delete("/employees/{emp_id}/bio-data")
async def delete_biometric_data(
    emp_id: int,
    bio_data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete biometric data from DB and devices"""
    service = PersonnelBioTimeService(db)
    
    if not current_user.is_superuser and current_user.role not in ['registrar', 'hr_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    result = await service.delete_biometric_data(emp_id, bio_data, current_user.id)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result




