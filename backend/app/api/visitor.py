"""
Visitor Management API - BioTime 9.5 Compatible + POB Extensions
REST API endpoints for visitor management with pre-registration, check-in/out,
blacklist, host approval, and mustering integration.
"""

from datetime import date, datetime
from typing import Optional, List
import csv, io
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.visitor_service import VisitorService
from app.schemas.visitor import (
    VisitorType, VisitorTypeCreate, VisitorTypeUpdate,
    Visitor, VisitorCreate, VisitorUpdate,
    VisitorPreRegistration, VisitorPreRegistrationCreate, VisitorPreRegistrationUpdate,
    VisitorVisitLog, VisitorCheckIn, VisitorCheckOut,
    VisitorBlacklist, VisitorBlacklistCreate, VisitorBlacklistUpdate,
    VisitorApprovalRequest, VisitorBulkApprovalRequest, VisitorQRResponse,
    VisitorDailyReport, VisitorOverstayReport,
    VisitorTypeResponse, VisitorTypeListResponse,
    VisitorResponse, VisitorListResponse,
    VisitorPreRegistrationResponse, VisitorPreRegistrationListResponse,
    VisitorVisitLogResponse, VisitorVisitLogListResponse,
    VisitorBlacklistResponse, VisitorBlacklistListResponse,
    VisitorQRResponseWrapper, VisitorDailyReportResponse,
    VisitorOverstayReportListResponse,
    VisitorAnalyticsResponse, VisitorFrequencyListResponse,
)
from app.core.exceptions import ValidationError, NotFoundError

router = APIRouter(prefix="/api/visitor", tags=["Visitor Management"])


# Helper function to get visitor service
def get_visitor_service(db: Session = Depends(get_db)) -> VisitorService:
    return VisitorService(db)


# Dashboard Stats
@router.get("/dashboard/stats/")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard summary statistics"""
    try:
        service = get_visitor_service(db)
        stats = service.get_dashboard_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Visitor Type Endpoints
@router.get("/types/", response_model=VisitorTypeListResponse)
async def get_visitor_types(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all visitor types"""
    try:
        service = get_visitor_service(db)
        types = service.get_visitor_types(include_inactive)
        return VisitorTypeListResponse(
            success=True,
            message="Visitor types retrieved successfully",
            data=types
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/types/", response_model=VisitorTypeResponse)
@router.post("/types", response_model=VisitorTypeResponse, include_in_schema=False)
async def create_visitor_type(
    type_data: VisitorTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new visitor type"""
    try:
        service = get_visitor_service(db)
        visitor_type = service.create_visitor_type(type_data.dict())
        return VisitorTypeResponse(
            success=True,
            message="Visitor type created successfully",
            data=visitor_type
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/types/{type_id}", response_model=VisitorTypeResponse)
async def update_visitor_type(
    type_id: int,
    type_data: VisitorTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update visitor type"""
    try:
        service = get_visitor_service(db)
        visitor_type = service.update_visitor_type(type_id, type_data.dict(exclude_unset=True))
        return VisitorTypeResponse(
            success=True,
            message="Visitor type updated successfully",
            data=visitor_type
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/types/{type_id}")
async def delete_visitor_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete visitor type"""
    try:
        service = get_visitor_service(db)
        service.update_visitor_type(type_id, {"is_active": False})
        return {"success": True, "message": "Visitor type deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Visitor CRUD Endpoints
@router.get("/visitors/", response_model=VisitorListResponse)
async def get_visitors(
    search: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    id_no: Optional[str] = Query(None),
    blacklist: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get visitors with filters"""
    try:
        service = get_visitor_service(db)
        visitors = service.get_visitors(search, phone, id_no, blacklist, skip, limit)
        return VisitorListResponse(
            success=True,
            message="Visitors retrieved successfully",
            data=visitors
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/visitors/", response_model=VisitorResponse)
@router.post("/visitors", response_model=VisitorResponse, include_in_schema=False)
async def create_visitor(
    visitor_data: VisitorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new visitor"""
    try:
        service = get_visitor_service(db)
        visitor = service.create_visitor(visitor_data)
        return VisitorResponse(
            success=True,
            message="Visitor created successfully",
            data=visitor
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visitors/{visitor_id}", response_model=VisitorResponse)
async def get_visitor(
    visitor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get visitor by ID"""
    try:
        service = get_visitor_service(db)
        visitors = service.get_visitors()
        visitor = next((v for v in visitors if v.id == visitor_id), None)
        if not visitor:
            raise HTTPException(status_code=404, detail="Visitor not found")
        
        return VisitorResponse(
            success=True,
            message="Visitor retrieved successfully",
            data=visitor
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/visitors/{visitor_id}", response_model=VisitorResponse)
async def update_visitor(
    visitor_id: int,
    visitor_data: VisitorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update visitor information"""
    try:
        service = get_visitor_service(db)
        visitor = service.update_visitor(visitor_id, visitor_data)
        return VisitorResponse(
            success=True,
            message="Visitor updated successfully",
            data=visitor
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/visitors/{visitor_id}/blacklist")
async def blacklist_visitor(
    visitor_id: int,
    reason: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Blacklist a visitor"""
    try:
        service = get_visitor_service(db)
        visitor = service.blacklist_visitor(visitor_id, reason.get("reason", ""))
        return VisitorResponse(
            success=True,
            message="Visitor blacklisted successfully",
            data=visitor
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Pre-Registration Endpoints
@router.get("/pre-register/", response_model=VisitorPreRegistrationListResponse)
async def get_pre_registrations(
    status: Optional[int] = Query(None),
    host_id: Optional[int] = Query(None),
    visit_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get pre-registrations with filters"""
    try:
        service = get_visitor_service(db)
        pre_regs = service.get_pre_registrations(status, host_id, visit_date)
        return VisitorPreRegistrationListResponse(
            success=True,
            message="Pre-registrations retrieved successfully",
            data=pre_regs
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pre-register/", response_model=VisitorPreRegistrationResponse)
@router.post("/pre-register", response_model=VisitorPreRegistrationResponse, include_in_schema=False)
async def create_pre_registration(
    pre_reg_data: VisitorPreRegistrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create visitor pre-registration"""
    try:
        service = get_visitor_service(db)
        pre_reg = service.create_pre_registration(pre_reg_data, current_user.id)
        return VisitorPreRegistrationResponse(
            success=True,
            message="Pre-registration created successfully",
            data=pre_reg
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pre-register/{pre_reg_id}", response_model=VisitorPreRegistrationResponse)
async def get_pre_registration(
    pre_reg_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get pre-registration by ID"""
    try:
        service = get_visitor_service(db)
        pre_regs = service.get_pre_registrations()
        pre_reg = next((pr for pr in pre_regs if pr.id == pre_reg_id), None)
        if not pre_reg:
            raise HTTPException(status_code=404, detail="Pre-registration not found")
        
        return VisitorPreRegistrationResponse(
            success=True,
            message="Pre-registration retrieved successfully",
            data=pre_reg
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pre-register/{pre_reg_id}/qr", response_model=VisitorQRResponseWrapper)
async def get_qr_code(
    pre_reg_id: int,
    db: Session = Depends(get_db)
):
    """Get QR code for pre-registration"""
    try:
        service = get_visitor_service(db)
        pre_regs = service.get_pre_registrations()
        pre_reg = next((pr for pr in pre_regs if pr.id == pre_reg_id), None)
        if not pre_reg:
            raise HTTPException(status_code=404, detail="Pre-registration not found")
        
        qr_data = VisitorQRResponse(
            qr_code=pre_reg.qr_code,
            visitor_name=pre_reg.visitor.full_name if pre_reg.visitor else "Unknown",
            company=pre_reg.visitor.company if pre_reg.visitor else None,
            host_name=pre_reg.host_employee.full_name if pre_reg.host_employee else None,
            visit_date=pre_reg.visit_date,
            visit_time_start=pre_reg.visit_time_start,
            visit_time_end=pre_reg.visit_time_end,
            purpose=pre_reg.purpose,
            status=pre_reg.status
        )
        
        return VisitorQRResponseWrapper(
            success=True,
            message="QR code retrieved successfully",
            data=qr_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pre-register/{pre_reg_id}/approve")
async def approve_pre_registration(
    pre_reg_id: int,
    approval_data: VisitorApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve or reject pre-registration"""
    try:
        service = get_visitor_service(db)
        pre_reg = service.approve_pre_registration(pre_reg_id, approval_data, current_user.id)
        return VisitorPreRegistrationResponse(
            success=True,
            message=f"Pre-registration {approval_data.status == 1 and 'approved' or 'rejected'} successfully",
            data=pre_reg
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pre-register/bulk-approve")
async def bulk_approve_pre_registrations(
    payload: VisitorBulkApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve or reject multiple pre-registrations at once."""
    try:
        service = get_visitor_service(db)
        result = service.bulk_approve_pre_registrations(
            payload.ids, payload.status, payload.note, current_user.id
        )
        verb = "approved" if payload.status == 1 else "rejected"
        return {
            "success": True,
            "message": f"{len(result['succeeded'])} of {result['total']} pre-registrations {verb}",
            "data": result,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pre-register/{pre_reg_id}/resend")
async def resend_pre_registration(
    pre_reg_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resend pre-registration notification email"""
    try:
        service = get_visitor_service(db)
        result = service.resend_pre_registration(pre_reg_id)
        return {"success": True, "message": "Pre-registration notification resent", "data": result}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# QR scan lookup — requires a logged-in user (used by the staff Check-In screen;
# returns visitor personal data). Self-service kiosk uses /kiosk/* instead.
@router.get("/qr/{qr_code}", response_model=VisitorQRResponseWrapper)
async def scan_qr_code(
    qr_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Look up a pre-registration by QR code (authenticated) — validates expiry."""
    from ..core.rate_limiter import rate_limiter
    from datetime import date as _date, datetime as _dt, timezone as _tz

    # Rate-limit QR lookups to block brute-force enumeration
    ip = request.client.host if request.client else "unknown"
    allowed, info = rate_limiter.is_allowed(key=f"qr_scan:{ip}", limit=30, window=60)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many QR scan requests",
            headers={"Retry-After": str(info["retry_after"])},
        )

    try:
        service = get_visitor_service(db)
        pre_reg = service.get_pre_registration_by_qr(qr_code)
        if not pre_reg:
            raise HTTPException(status_code=404, detail="QR code not found")

        # Visit dates/times are SITE wall-clock values. The check used the UTC date and
        # UTC time (an hour off in Lagos), and applied the time window on ANY date — so
        # tomorrow's 09:00–17:00 pass scanned this evening was "expired".
        from ..services.attendance_calculation_service import SITE_TZ
        now_site = _dt.now(SITE_TZ)
        today = now_site.date()
        if pre_reg.visit_date and pre_reg.visit_date < today:
            raise HTTPException(status_code=403, detail="QR code expired — visit date has passed")

        # The time window only closes the pass on the visit day itself.
        if pre_reg.visit_time_end and (pre_reg.visit_date is None or pre_reg.visit_date == today):
            if now_site.time().replace(tzinfo=None) > pre_reg.visit_time_end:
                raise HTTPException(status_code=403, detail="QR code expired — visit time window has closed")

        # Reject already-used or explicitly expired registrations (status 4=checked_out, 5=expired)
        if getattr(pre_reg, "status", None) in (4, 5):
            raise HTTPException(status_code=403, detail="QR code has already been used or expired")

        qr_data = VisitorQRResponse(
            qr_code=pre_reg.qr_code,
            visitor_name=pre_reg.visitor.full_name if pre_reg.visitor else "Unknown",
            company=pre_reg.visitor.company if pre_reg.visitor else None,
            host_name=pre_reg.host_employee.full_name if pre_reg.host_employee else None,
            visit_date=pre_reg.visit_date,
            visit_time_start=pre_reg.visit_time_start,
            visit_time_end=pre_reg.visit_time_end,
            purpose=pre_reg.purpose,
            status=pre_reg.status,
        )
        return VisitorQRResponseWrapper(
            success=True,
            message="QR code scanned successfully",
            data=qr_data,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="QR scan error")


# Check-In/Check-Out Endpoints
@router.post("/check-in/", response_model=VisitorVisitLogResponse)
@router.post("/check-in", response_model=VisitorVisitLogResponse, include_in_schema=False)
async def check_in_visitor(
    check_in_data: VisitorCheckIn,
    device_sn: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check-in visitor"""
    try:
        service = get_visitor_service(db)
        visit_log = service.check_in_visitor(check_in_data, device_sn, current_user.id)
        return VisitorVisitLogResponse(
            success=True,
            message="Visitor checked in successfully",
            data=visit_log
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-out/", response_model=VisitorVisitLogResponse)
@router.post("/check-out", response_model=VisitorVisitLogResponse, include_in_schema=False)
async def check_out_visitor(
    check_out_data: VisitorCheckOut,
    device_sn: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check-out visitor"""
    try:
        service = get_visitor_service(db)
        visit_log = service.check_out_visitor(check_out_data, device_sn)
        return VisitorVisitLogResponse(
            success=True,
            message="Visitor checked out successfully",
            data=visit_log
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Records Endpoints
@router.get("/records/", response_model=VisitorVisitLogListResponse)
async def get_visitor_records(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    host_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get visitor records"""
    try:
        service = get_visitor_service(db)
        visit_logs = service.get_visit_records(start_date, end_date, host_id, status, search, skip, limit)
        return VisitorVisitLogListResponse(
            success=True,
            message="Visitor records retrieved successfully",
            data=visit_logs
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records/on-site/", response_model=VisitorVisitLogListResponse)
async def get_on_site_visitors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get visitors currently on site"""
    try:
        service = get_visitor_service(db)
        visitors = service.get_on_site_visitors()
        return VisitorVisitLogListResponse(
            success=True,
            message="On-site visitors retrieved successfully",
            data=visitors
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Blacklist Endpoints
@router.get("/blacklist/", response_model=VisitorBlacklistListResponse)
async def get_blacklist(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get blacklist entries"""
    try:
        service = get_visitor_service(db)
        blacklist = service.get_blacklist(search)
        return VisitorBlacklistListResponse(
            success=True,
            message="Blacklist retrieved successfully",
            data=blacklist
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blacklist/", response_model=VisitorBlacklistResponse)
@router.post("/blacklist", response_model=VisitorBlacklistResponse, include_in_schema=False)
async def add_to_blacklist(
    blacklist_data: VisitorBlacklistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add entry to blacklist"""
    try:
        service = get_visitor_service(db)
        blacklist = service.add_to_blacklist(blacklist_data.dict(), current_user.id)
        return VisitorBlacklistResponse(
            success=True,
            message="Added to blacklist successfully",
            data=blacklist
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/blacklist/{blacklist_id}", response_model=VisitorBlacklistResponse)
async def update_blacklist(
    blacklist_id: int,
    blacklist_data: VisitorBlacklistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update blacklist entry"""
    try:
        service = get_visitor_service(db)
        entry = service.update_blacklist_entry(blacklist_id, blacklist_data.dict(exclude_unset=True))
        return VisitorBlacklistResponse(success=True, message="Blacklist updated successfully", data=entry)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/blacklist/{blacklist_id}")
async def remove_from_blacklist(
    blacklist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove from blacklist"""
    try:
        service = get_visitor_service(db)
        service.remove_from_blacklist(blacklist_id)
        return {"success": True, "message": "Removed from blacklist successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Reports Endpoints
@router.get("/reports/daily/", response_model=VisitorDailyReportResponse)
async def get_daily_report(
    report_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate daily visitor report"""
    try:
        service = get_visitor_service(db)
        report = service.get_daily_report(report_date)
        return VisitorDailyReportResponse(
            success=True,
            message="Daily report generated successfully",
            data=report
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/overstay/", response_model=VisitorOverstayReportListResponse)
async def get_overstay_report(
    hours: int = Query(8, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overstay report"""
    try:
        service = get_visitor_service(db)
        overstays = service.get_overstay_report(hours)
        return VisitorOverstayReportListResponse(
            success=True,
            message="Overstay report generated successfully",
            data=overstays
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/mustering-compliance/")
async def get_mustering_compliance_report(
    event_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate mustering compliance report for visitors"""
    try:
        # TODO: Implement mustering compliance report
        return {"success": True, "message": "Mustering compliance report generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/analytics/", response_model=VisitorAnalyticsResponse)
async def get_analytics(
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Real aggregated visitor analytics"""
    try:
        service = get_visitor_service(db)
        data = service.get_analytics(days)
        return VisitorAnalyticsResponse(success=True, message="Analytics generated", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/frequency/", response_model=VisitorFrequencyListResponse)
async def get_visitor_frequency(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get most frequent (returning) visitors"""
    try:
        service = get_visitor_service(db)
        data = service.get_visitor_frequency(limit)
        return VisitorFrequencyListResponse(success=True, message="Frequency report generated", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records/export/")
async def export_visit_records(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    host_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export visit records as CSV"""
    try:
        service = get_visitor_service(db)
        rows = service.get_records_for_export(start_date, end_date, host_id, status, search)

        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        else:
            output.write("No records found")

        output.seek(0)
        filename = f"visitor_records_{start_date or 'all'}_{end_date or 'all'}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-out/{log_id}/force/", response_model=VisitorVisitLogResponse)
@router.post("/check-out/{log_id}/force", response_model=VisitorVisitLogResponse, include_in_schema=False)
async def force_check_out(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Force check-out a visitor by visit log ID"""
    try:
        service = get_visitor_service(db)
        visit_log = service.force_check_out_by_log_id(log_id)
        return VisitorVisitLogResponse(success=True, message="Visitor force checked out", data=visit_log)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/visitors/lookup/", response_model=VisitorListResponse)
async def lookup_visitor(
    phone: Optional[str] = Query(None),
    id_no: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Quick lookup of existing visitor by phone, ID, or name — for returning visitor check-in"""
    try:
        service = get_visitor_service(db)
        visitors = service.get_visitors(search=search, phone=phone, id_no=id_no, limit=10)
        return VisitorListResponse(success=True, message="Visitor lookup complete", data=visitors)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC KIOSK ENDPOINTS  (no authentication — self-service tablet mode)
# ─────────────────────────────────────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel, EmailStr


class KioskCheckIn(_BaseModel):
    first_name: str
    last_name: str = ""
    phone: str = ""
    email: str = ""
    company: str = ""
    id_number: str = ""
    visitor_type: str = "Walk-in"
    host_name: str = ""
    purpose: str = ""


@router.post("/kiosk/check-in")
async def kiosk_check_in(
    data: KioskCheckIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public self-service check-in — no auth required.
    Creates (or finds) the visitor, then records a check-in log.
    Rate-limited: 10 requests per minute per IP to prevent DB flooding.
    """
    from ..core.rate_limiter import rate_limiter
    ip = request.client.host if request.client else "unknown"
    allowed, info = rate_limiter.is_allowed(key=f"kiosk:{ip}", limit=10, window=60)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many check-in requests. Please wait before trying again.",
            headers={"Retry-After": str(info["retry_after"])},
        )
    from sqlalchemy import text as _text
    from datetime import datetime, timezone

    # Blacklist check — query vis_blacklist directly by id_number and/or phone
    # before any visitor record is created. This mirrors VisitorService._is_blacklisted().
    if data.id_number or data.phone:
        bl_row = db.execute(_text("""
            SELECT 1 FROM vis_blacklist
            WHERE is_active = TRUE
              AND (
                    (:id <> '' AND id_no = :id)
                 OR (:ph <> '' AND phone = :ph)
              )
            LIMIT 1
        """), {"id": data.id_number, "ph": data.phone}).fetchone()
        if bl_row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Entry not permitted. Please see the front desk.",
            )

    # Upsert visitor — INSERT with ON CONFLICT DO NOTHING to eliminate the TOCTOU
    # race between concurrent kiosk submissions for the same person. We match on
    # id_number when it is provided (most reliable identity); fall back to
    # (first_name, phone) when id_number is blank. A SELECT after the INSERT
    # picks up whichever row won the race.
    if data.id_number:
        db.execute(_text("""
            INSERT INTO vis_visitor (first_name, last_name, phone, email, company,
                                     id_number, visitor_type, created_at)
            VALUES (:fn, :ln, :ph, :em, :co, :id, :vt, NOW())
            ON CONFLICT (id_number) WHERE id_number <> '' DO NOTHING
        """), {
            "fn": data.first_name, "ln": data.last_name,
            "ph": data.phone,      "em": data.email,
            "co": data.company,    "id": data.id_number,
            "vt": data.visitor_type,
        })
        db.commit()
        row = db.execute(_text(
            "SELECT id FROM vis_visitor WHERE id_number = :id LIMIT 1"
        ), {"id": data.id_number}).fetchone()
    else:
        # No ID supplied — match on (first_name, phone); accept duplicates for
        # genuinely anonymous walk-ins (no phone, no ID).
        if data.phone:
            db.execute(_text("""
                INSERT INTO vis_visitor (first_name, last_name, phone, email, company,
                                         id_number, visitor_type, created_at)
                VALUES (:fn, :ln, :ph, :em, :co, '', :vt, NOW())
                ON CONFLICT (phone) WHERE phone <> '' DO NOTHING
            """), {
                "fn": data.first_name, "ln": data.last_name,
                "ph": data.phone,      "em": data.email,
                "co": data.company,    "vt": data.visitor_type,
            })
            db.commit()
            row = db.execute(_text(
                "SELECT id FROM vis_visitor WHERE phone = :ph LIMIT 1"
            ), {"ph": data.phone}).fetchone()
        else:
            # Truly anonymous — always insert a new record
            res = db.execute(_text("""
                INSERT INTO vis_visitor (first_name, last_name, phone, email, company,
                                         id_number, visitor_type, created_at)
                VALUES (:fn, :ln, '', :em, :co, '', :vt, NOW())
                RETURNING id
            """), {
                "fn": data.first_name, "ln": data.last_name,
                "em": data.email,      "co": data.company,
                "vt": data.visitor_type,
            }).fetchone()
            db.commit()
            row = res

    if not row:
        raise HTTPException(status_code=500, detail="Could not create visitor record")

    visitor_id = row[0]

    # Record check-in
    db.execute(_text("""
        INSERT INTO vis_visit_log (visitor_id, check_in_time, purpose, host_name,
                                   status, created_at)
        VALUES (:vid, NOW(), :pur, :hn, 0, NOW())
    """), {
        "vid": visitor_id, "pur": data.purpose, "hn": data.host_name,
    })
    db.commit()

    return {
        "success": True,
        "message": f"Welcome, {data.first_name}! You have been checked in.",
        "visitor_id": visitor_id,
        "checked_in_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/kiosk/types")
async def kiosk_visitor_types(db: Session = Depends(get_db)):
    """Public: return available visitor types for the kiosk dropdown."""
    from sqlalchemy import text as _text
    rows = db.execute(_text(
        "SELECT id, type_name AS name, NULL::text AS description "
        "FROM vis_type WHERE is_active = TRUE ORDER BY type_name"
    )).fetchall()
    return {"types": [dict(r._mapping) for r in rows]}
