"""
Visitor Management Service - BioTime 9.5 Compatible + POB Extensions
Complete visitor management with pre-registration, check-in/out, blacklist,
host approval, and mustering integration.
"""

import uuid
import logging
import threading
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.visitor import (
    VisitorType, Visitor, VisitorPreRegistration, VisitorVisitLog, 
    VisitorBlacklist
)
from app.models.personnel import Personnel, PersonnelAssignment
from app.models.device import Device
from app.models.zone import Zone
from app.models.biotime_models import MusteringEvent, MusteringExpected, MusteringLog
from app.models.biotime_models import AccLevel
from app.schemas.visitor import (
    VisitorCreate, VisitorUpdate, VisitorPreRegistrationCreate,
    VisitorCheckIn, VisitorCheckOut, VisitorApprovalRequest
)
from app.core.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class VisitorService:
    """Visitor management service with BioTime compatibility and POB extensions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Visitor Type Management
    def get_visitor_types(self, include_inactive: bool = False) -> List[VisitorType]:
        """Get all visitor types"""
        query = self.db.query(VisitorType)
        if not include_inactive:
            query = query.filter(VisitorType.is_active == True)
        return query.all()
    
    def create_visitor_type(self, type_data: dict) -> VisitorType:
        """Create a new visitor type"""
        visitor_type = VisitorType(**type_data)
        self.db.add(visitor_type)
        self.db.commit()
        self.db.refresh(visitor_type)
        return visitor_type
    
    def update_visitor_type(self, type_id: int, type_data: dict) -> VisitorType:
        """Update visitor type"""
        visitor_type = self.db.query(VisitorType).filter(VisitorType.id == type_id).first()
        if not visitor_type:
            raise NotFoundError(f"Visitor type {type_id} not found")
        
        for field, value in type_data.items():
            setattr(visitor_type, field, value)
        
        self.db.commit()
        self.db.refresh(visitor_type)
        return visitor_type
    
    # Visitor Management
    def get_visitors(self, search: Optional[str] = None, phone: Optional[str] = None,
                    id_no: Optional[str] = None, blacklist: Optional[bool] = None,
                    skip: int = 0, limit: int = 100) -> List[Visitor]:
        """Get visitors with filters"""
        query = self.db.query(Visitor)
        
        if search:
            query = query.filter(Visitor.full_name.ilike(f"%{search}%"))
        if phone:
            query = query.filter(Visitor.phone == phone)
        if id_no:
            query = query.filter(Visitor.id_no == id_no)
        if blacklist is not None:
            query = query.filter(Visitor.is_blacklist == blacklist)
        
        return query.offset(skip).limit(limit).all()
    
    def create_visitor(self, visitor_data: VisitorCreate) -> Visitor:
        """Create a new visitor"""
        # Check if visitor already exists by ID or phone
        existing = self.db.query(Visitor).filter(
            or_(
                Visitor.id_no == visitor_data.id_no,
                Visitor.phone == visitor_data.phone
            )
        ).first()
        
        if existing:
            raise ValidationError("Visitor with this ID or phone already exists")
        
        # Generate visitor code
        visitor_code = self._generate_visitor_code()
        
        visitor = Visitor(
            visitor_code=visitor_code,
            **visitor_data.dict()
        )
        self.db.add(visitor)
        self.db.commit()
        self.db.refresh(visitor)
        return visitor
    
    def update_visitor(self, visitor_id: int, visitor_data: VisitorUpdate) -> Visitor:
        """Update visitor information"""
        visitor = self.db.query(Visitor).filter(Visitor.id == visitor_id).first()
        if not visitor:
            raise NotFoundError(f"Visitor {visitor_id} not found")
        
        for field, value in visitor_data.dict(exclude_unset=True).items():
            setattr(visitor, field, value)
        
        self.db.commit()
        self.db.refresh(visitor)
        return visitor
    
    def blacklist_visitor(self, visitor_id: int, reason: str) -> Visitor:
        """Blacklist a visitor"""
        visitor = self.db.query(Visitor).filter(Visitor.id == visitor_id).first()
        if not visitor:
            raise NotFoundError(f"Visitor {visitor_id} not found")
        
        visitor.is_blacklist = True
        visitor.blacklist_reason = reason
        
        # Also add to blacklist table
        blacklist = VisitorBlacklist(
            full_name=visitor.full_name,
            id_no=visitor.id_no,
            phone=visitor.phone,
            email=visitor.email,
            reason=reason
        )
        self.db.add(blacklist)
        
        self.db.commit()
        self.db.refresh(visitor)
        return visitor
    
    # Pre-Registration Management
    def get_pre_registrations(self, status: Optional[int] = None, host_id: Optional[int] = None,
                            visit_date: Optional[date] = None) -> List[VisitorPreRegistration]:
        """Get pre-registrations with filters"""
        query = self.db.query(VisitorPreRegistration)
        
        if status is not None:
            query = query.filter(VisitorPreRegistration.status == status)
        if host_id is not None:
            query = query.filter(VisitorPreRegistration.host_emp_id == host_id)
        if visit_date is not None:
            query = query.filter(VisitorPreRegistration.visit_date == visit_date)
        
        return query.all()
    
    def create_pre_registration(self, pre_reg_data: VisitorPreRegistrationCreate, 
                              created_by: int) -> VisitorPreRegistration:
        """Create visitor pre-registration"""
        # Create visitor if not exists
        visitor_id = pre_reg_data.visitor_id
        if pre_reg_data.visitor_data and not visitor_id:
            visitor = self.create_visitor(pre_reg_data.visitor_data)
            visitor_id = visitor.id
        
        # Generate QR code
        qr_code = str(uuid.uuid4())
        
        pre_reg = VisitorPreRegistration(
            visitor_id=visitor_id,
            qr_code=qr_code,
            created_by=created_by,
            **pre_reg_data.dict(exclude={'visitor_data', 'visitor_id'})
        )
        self.db.add(pre_reg)
        self.db.commit()
        self.db.refresh(pre_reg)

        # Best-effort notifications: host approval request + visitor confirmation
        self._notify_pre_registration_created(pre_reg)
        return pre_reg

    def approve_pre_registration(self, pre_reg_id: int, approval_data: VisitorApprovalRequest,
                               approved_by: int) -> VisitorPreRegistration:
        """Approve or reject pre-registration"""
        pre_reg = self.db.query(VisitorPreRegistration).filter(
            VisitorPreRegistration.id == pre_reg_id
        ).first()

        if not pre_reg:
            raise NotFoundError(f"Pre-registration {pre_reg_id} not found")

        # Safety screening: never let a blacklisted visitor be approved
        if approval_data.status == 1 and pre_reg.visitor and self._is_blacklisted(pre_reg.visitor):
            raise ValidationError(
                "Visitor is blacklisted and cannot be approved. Remove them from the blacklist first."
            )

        pre_reg.status = approval_data.status
        pre_reg.approval_time = datetime.utcnow()
        pre_reg.approval_by = approved_by
        pre_reg.approval_note = approval_data.note

        self.db.commit()
        self.db.refresh(pre_reg)

        # Best-effort notification to the visitor (approved / rejected)
        self._notify_pre_registration_decided(pre_reg)
        return pre_reg

    def bulk_approve_pre_registrations(self, pre_reg_ids: List[int], status: int,
                                       note: Optional[str], approved_by: int) -> Dict[str, Any]:
        """Approve or reject multiple pre-registrations in one call.

        Returns a per-id summary; an individual failure (e.g. blacklisted visitor)
        never aborts the rest.
        """
        approval = VisitorApprovalRequest(status=status, note=note)
        succeeded, failed = [], []
        for pid in pre_reg_ids:
            try:
                self.approve_pre_registration(pid, approval, approved_by)
                succeeded.append(pid)
            except (ValidationError, NotFoundError) as e:
                self.db.rollback()
                failed.append({"id": pid, "error": str(e)})
        return {
            "succeeded": succeeded,
            "failed": failed,
            "total": len(pre_reg_ids),
        }

    def resend_pre_registration(self, pre_reg_id: int) -> Dict[str, Any]:
        """Re-send the relevant notification for a pre-registration."""
        pre_reg = self.db.query(VisitorPreRegistration).filter(
            VisitorPreRegistration.id == pre_reg_id
        ).first()
        if not pre_reg:
            raise NotFoundError(f"Pre-registration {pre_reg_id} not found")

        # Pending -> re-send host approval request + visitor confirmation.
        # Decided -> re-send the approval/rejection outcome to the visitor.
        # Non-blocking: dispatch in a daemon thread so a slow/unreachable SMTP
        # server can never tie up a request worker (which would starve the pool).
        if pre_reg.status == 0:
            return self._send_pre_reg_emails(pre_reg, blocking=False)
        return self._send_decision_email(pre_reg, blocking=False)

    # ── Notification helpers ──────────────────────────────────────────────
    def _build_notification_payloads(self, pre_reg: VisitorPreRegistration):
        """Assemble the plain dicts the email service expects (no ORM in threads)."""
        v = pre_reg.visitor
        h = pre_reg.host_employee

        def _name(emp):
            if not emp:
                return ""
            return getattr(emp, "full_name", None) or " ".join(
                p for p in [emp.first_name, emp.last_name] if p
            )

        visitor_data = {
            "full_name": v.full_name if v else "",
            "email": v.email if v else None,
            "company": v.company if v else "",
            "visit_date": pre_reg.visit_date.isoformat() if pre_reg.visit_date else "",
            "visit_time_start": str(pre_reg.visit_time_start) if pre_reg.visit_time_start else "",
            "visit_time_end": str(pre_reg.visit_time_end) if pre_reg.visit_time_end else "",
            "purpose": pre_reg.purpose or "",
        }
        host_data = {
            "full_name": _name(h),
            # personnel_employee has no email column today; resolve defensively so
            # host-side email is simply skipped rather than erroring the request.
            "email": getattr(h, "email", None) if h else None,
        }
        return visitor_data, host_data

    def _send_pre_reg_emails(self, pre_reg: VisitorPreRegistration, blocking: bool = False) -> Dict[str, Any]:
        from app.services.email_service import VisitorEmailService
        from app.core.config import settings

        visitor_data, host_data = self._build_notification_payloads(pre_reg)
        qr_code = pre_reg.qr_code
        base = (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
        approval_url = f"{base}/visitor" if base else "the POB visitor portal"

        def _run():
            email = VisitorEmailService()
            results = {}
            try:
                if host_data.get("email"):
                    results["host"] = email.send_host_approval_email(host_data, visitor_data, approval_url)
                if visitor_data.get("email"):
                    results["visitor"] = email.send_visitor_registration_email(
                        visitor_data, qr_code, host_data.get("full_name", "")
                    )
            except Exception as e:  # never let email break the request
                logger.warning("Pre-registration email failed: %s", e)
            return results

        return _run() if blocking else self._fire(_run)

    def _send_decision_email(self, pre_reg: VisitorPreRegistration, blocking: bool = False) -> Dict[str, Any]:
        from app.services.email_service import VisitorEmailService

        visitor_data, host_data = self._build_notification_payloads(pre_reg)
        status_str = "approved" if pre_reg.status == 1 else "rejected"

        def _run():
            email = VisitorEmailService()
            try:
                if visitor_data.get("email"):
                    return {"visitor": email.send_approval_notification_email(
                        visitor_data, host_data, status_str
                    )}
            except Exception as e:
                logger.warning("Approval notification email failed: %s", e)
            return {}

        return _run() if blocking else self._fire(_run)

    def _notify_pre_registration_created(self, pre_reg: VisitorPreRegistration):
        try:
            self._send_pre_reg_emails(pre_reg)
        except Exception as e:
            logger.warning("Failed to dispatch pre-registration notifications: %s", e)

    def _notify_pre_registration_decided(self, pre_reg: VisitorPreRegistration):
        try:
            self._send_decision_email(pre_reg)
        except Exception as e:
            logger.warning("Failed to dispatch approval notification: %s", e)

    @staticmethod
    def _fire(fn) -> Dict[str, Any]:
        """Run a best-effort side effect in a daemon thread (never blocks the request)."""
        threading.Thread(target=fn, daemon=True).start()
        return {"queued": True}
    
    def get_pre_registration_by_qr(self, qr_code: str) -> Optional[VisitorPreRegistration]:
        """Get pre-registration by QR code (public endpoint)"""
        return self.db.query(VisitorPreRegistration).filter(
            VisitorPreRegistration.qr_code == qr_code
        ).first()
    
    # Check-In/Check-Out Management
    def check_in_visitor(self, check_in_data: VisitorCheckIn, device_sn: Optional[str] = None,
                        created_by: Optional[int] = None) -> VisitorVisitLog:
        """Check-in visitor"""
        visitor = None
        pre_reg = None

        if check_in_data.pre_reg_id:
            pre_reg = self.db.query(VisitorPreRegistration).filter(
                VisitorPreRegistration.id == check_in_data.pre_reg_id
            ).first()
            if not pre_reg:
                raise NotFoundError("Pre-registration not found")
            visitor = pre_reg.visitor
            if not visitor:
                raise NotFoundError("Visitor not found")
            pre_reg.status = 3  # checked_in

        elif check_in_data.visitor_id:
            # Returning visitor walk-in — look up existing profile
            visitor = self.db.query(Visitor).filter(Visitor.id == check_in_data.visitor_id).first()
            if not visitor:
                raise NotFoundError("Visitor not found")

        elif check_in_data.visitor_data:
            visitor = self.create_visitor(check_in_data.visitor_data)
        else:
            raise ValidationError("Either pre_reg_id, visitor_id, or visitor_data required")
        
        # Check blacklist
        if self._is_blacklisted(visitor):
            raise ValidationError("Visitor is blacklisted")
        
        # Check if already checked in
        active_visit = self.db.query(VisitorVisitLog).filter(
            and_(
                VisitorVisitLog.visitor_id == visitor.id,
                VisitorVisitLog.status == 0  # checked in
            )
        ).first()
        
        if active_visit:
            raise ValidationError("Visitor is already checked in")
        
        # Generate temporary card number
        card_no = self._generate_temp_card()
        
        # Create visit log
        visit_log = VisitorVisitLog(
            visitor_id=visitor.id,
            pre_reg_id=pre_reg.id if pre_reg else None,
            host_emp_id=check_in_data.host_emp_id or (pre_reg.host_emp_id if pre_reg else None),
            area_id=check_in_data.area_id or (pre_reg.area_id if pre_reg else None),
            card_no=card_no,
            device_sn=device_sn,
            created_by=created_by
        )
        
        # Set mustering zone if active event
        active_event = self.db.query(MusteringEvent).filter(
            MusteringEvent.status == 0  # active
        ).first()
        
        if active_event:
            # Determine mustering zone
            mustering_zone_id = self._get_mustering_zone_for_visitor(
                visit_log.area_id, visitor.visitor_type_id
            )
            visit_log.mustering_zone_id = mustering_zone_id
            
            # Add to mustering expected
            mustering_expected = MusteringExpected(
                event_id=active_event.id,
                personnel_id=None,  # Not a regular employee
                visitor_id=visitor.id,
                mustering_zone_id=mustering_zone_id,
                expected_time=datetime.utcnow()
            )
            self.db.add(mustering_expected)
        
        self.db.add(visit_log)
        self.db.commit()
        self.db.refresh(visit_log)
        
        # Sync to devices
        self._sync_visitor_to_device(visitor, card_no, device_sn)
        
        return visit_log
    
    def check_out_visitor(self, check_out_data: VisitorCheckOut, 
                         device_sn: Optional[str] = None) -> VisitorVisitLog:
        """Check-out visitor"""
        # Find active visit
        visit_log = None
        
        if check_out_data.visitor_code:
            visit_log = self.db.query(VisitorVisitLog).join(Visitor).filter(
                and_(
                    Visitor.visitor_code == check_out_data.visitor_code,
                    VisitorVisitLog.status == 0  # checked in
                )
            ).first()
        elif check_out_data.card_no:
            visit_log = self.db.query(VisitorVisitLog).filter(
                and_(
                    VisitorVisitLog.card_no == check_out_data.card_no,
                    VisitorVisitLog.status == 0  # checked in
                )
            ).first()
        
        if not visit_log:
            raise NotFoundError("Active visitor visit not found")
        
        # Update visit log
        visit_log.check_out_time = datetime.utcnow()
        visit_log.status = 1  # checked out
        
        # Update mustering if active event
        active_event = self.db.query(MusteringEvent).filter(
            MusteringEvent.status == 0
        ).first()
        
        if active_event and visit_log.mustering_zone_id:
            # Mark as safe in mustering log
            mustering_log = MusteringLog(
                event_id=active_event.id,
                personnel_id=None,
                visitor_id=visit_log.visitor_id,
                mustering_zone_id=visit_log.mustering_zone_id,
                status=1,  # safe
                log_time=datetime.utcnow()
            )
            self.db.add(mustering_log)
        
        self.db.commit()
        self.db.refresh(visit_log)
        
        # Remove from devices
        self._remove_visitor_from_device(visit_log.visitor_id, device_sn)
        
        return visit_log
    
    def get_visit_records(self, start_date: Optional[date] = None, end_date: Optional[date] = None,
                         host_id: Optional[int] = None, status: Optional[int] = None,
                         search: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[VisitorVisitLog]:
        """Get visit records with filters"""
        query = self.db.query(VisitorVisitLog)

        if start_date:
            query = query.filter(VisitorVisitLog.check_in_time >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.filter(VisitorVisitLog.check_in_time <= datetime.combine(end_date, time.max))
        if host_id is not None:
            query = query.filter(VisitorVisitLog.host_emp_id == host_id)
        if status is not None:
            query = query.filter(VisitorVisitLog.status == status)
        if search:
            query = query.join(Visitor).filter(Visitor.full_name.ilike(f"%{search}%"))

        return query.order_by(VisitorVisitLog.check_in_time.desc()).offset(skip).limit(limit).all()

    def get_on_site_visitors(self) -> List[VisitorVisitLog]:
        """Get all visitors currently on site"""
        return self.db.query(VisitorVisitLog).filter(
            VisitorVisitLog.status == 0  # checked in
        ).all()

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard summary statistics"""
        today_start = datetime.combine(date.today(), time.min)
        today_end = datetime.combine(date.today(), time.max)

        total_visitors = self.db.query(Visitor).count()
        on_site = self.db.query(VisitorVisitLog).filter(VisitorVisitLog.status == 0).count()
        pending_approval = self.db.query(VisitorPreRegistration).filter(
            VisitorPreRegistration.status == 0
        ).count()
        blacklisted = self.db.query(VisitorBlacklist).filter(VisitorBlacklist.is_active == True).count()
        today_checkins = self.db.query(VisitorVisitLog).filter(
            VisitorVisitLog.check_in_time >= today_start,
            VisitorVisitLog.check_in_time <= today_end
        ).count()

        overstay_count = self.db.query(VisitorVisitLog).filter(VisitorVisitLog.status == 2).count()

        return {
            "total_visitors": total_visitors,
            "on_site": on_site,
            "pending_approval": pending_approval,
            "blacklisted": blacklisted,
            "today_checkins": today_checkins,
            "overstay_count": overstay_count,
        }

    # Blacklist Management
    def get_blacklist(self, search: Optional[str] = None) -> List[VisitorBlacklist]:
        """Get blacklist entries"""
        query = self.db.query(VisitorBlacklist).filter(VisitorBlacklist.is_active == True)
        
        if search:
            query = query.filter(
                or_(
                    VisitorBlacklist.full_name.ilike(f"%{search}%"),
                    VisitorBlacklist.id_no.ilike(f"%{search}%"),
                    VisitorBlacklist.phone.ilike(f"%{search}%")
                )
            )
        
        return query.all()
    
    def add_to_blacklist(self, blacklist_data: dict, added_by: int) -> VisitorBlacklist:
        """Add entry to blacklist"""
        # Check if already exists
        existing = self.db.query(VisitorBlacklist).filter(
            VisitorBlacklist.id_no == blacklist_data['id_no']
        ).first()
        
        if existing:
            existing.is_active = True
            existing.reason = blacklist_data['reason']
        else:
            blacklist = VisitorBlacklist(
                added_by=added_by,
                **blacklist_data
            )
            self.db.add(blacklist)
        
        # Also update visitor if exists
        visitor = self.db.query(Visitor).filter(
            Visitor.id_no == blacklist_data['id_no']
        ).first()
        
        if visitor:
            visitor.is_blacklist = True
            visitor.blacklist_reason = blacklist_data['reason']
        
        self.db.commit()
        return existing if existing else blacklist

    def update_blacklist_entry(self, blacklist_id: int, data: dict) -> VisitorBlacklist:
        """Update a blacklist entry"""
        entry = self.db.query(VisitorBlacklist).filter(VisitorBlacklist.id == blacklist_id).first()
        if not entry:
            raise NotFoundError(f"Blacklist entry {blacklist_id} not found")
        for field, value in data.items():
            setattr(entry, field, value)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def remove_from_blacklist(self, blacklist_id: int) -> bool:
        """Deactivate a blacklist entry"""
        entry = self.db.query(VisitorBlacklist).filter(VisitorBlacklist.id == blacklist_id).first()
        if not entry:
            raise NotFoundError(f"Blacklist entry {blacklist_id} not found")
        entry.is_active = False
        # Un-blacklist the visitor record if they exist
        if entry.id_no:
            visitor = self.db.query(Visitor).filter(Visitor.id_no == entry.id_no).first()
            if visitor:
                visitor.is_blacklist = False
                visitor.blacklist_reason = None
        self.db.commit()
        return True

    # Reports
    def get_daily_report(self, report_date: date) -> Dict[str, Any]:
        """Generate daily visitor report"""
        start_date = datetime.combine(report_date, time.min)
        end_date = datetime.combine(report_date, time.max)
        
        # Get all visits for the day
        visits = self.db.query(VisitorVisitLog).filter(
            VisitorVisitLog.check_in_time >= start_date,
            VisitorVisitLog.check_in_time <= end_date
        ).all()
        
        total_visitors = len(visits)
        checked_in = len([v for v in visits if v.status == 0])
        checked_out = len([v for v in visits if v.status == 1])
        on_site = checked_in
        overstay = len([v for v in visits if v.status == 2])
        
        # Group by visitor type
        by_type = {}
        for visit in visits:
            if visit.visitor and visit.visitor.visitor_type:
                type_name = visit.visitor.visitor_type.type_name
                by_type[type_name] = by_type.get(type_name, 0) + 1
        
        # Group by host
        by_host = {}
        for visit in visits:
            if visit.host_employee:
                emp = visit.host_employee
                host_name = f"{(emp.first_name or '').strip()} {(emp.last_name or '').strip()}".strip()
                by_host[host_name] = by_host.get(host_name, 0) + 1
        
        return {
            'date': report_date,
            'total_visitors': total_visitors,
            'checked_in': checked_in,
            'checked_out': checked_out,
            'on_site': on_site,
            'overstay': overstay,
            'by_type': [{'type': k, 'count': v} for k, v in by_type.items()],
            'by_host': [{'host': k, 'count': v} for k, v in by_host.items()]
        }
    
    def get_overstay_report(self, hours: int = 8) -> List[Dict[str, Any]]:
        """Get visitors who have overstayed"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        overstays = self.db.query(VisitorVisitLog).join(Visitor).filter(
            and_(
                VisitorVisitLog.status == 0,  # still checked in
                VisitorVisitLog.check_in_time < cutoff_time
            )
        ).all()
        
        results = []
        for visit in overstays:
            ci = visit.check_in_time
            if ci.tzinfo is None:
                ci = ci.replace(tzinfo=timezone.utc)
            # (aware - naive raised TypeError: the report crashed whenever anyone overstayed)
            hours_overdue = (datetime.now(timezone.utc) - ci).total_seconds() / 3600 - hours
            
            results.append({
                'visitor_id': visit.visitor_id,
                'visitor_name': visit.visitor.full_name if visit.visitor else 'Unknown',
                'company': visit.visitor.company if visit.visitor else None,
                'host_name': (f"{(visit.host_employee.first_name or '').strip()} {(visit.host_employee.last_name or '').strip()}".strip() if visit.host_employee else None),
                'check_in_time': visit.check_in_time,
                'hours_overdue': hours_overdue,
                'contact_info': {
                    'phone': visit.visitor.phone if visit.visitor else None,
                    'email': visit.visitor.email if visit.visitor else None
                }
            })
        
        return results
    
    def force_check_out_by_log_id(self, log_id: int) -> VisitorVisitLog:
        """Force check-out a visitor by visit log ID"""
        visit_log = self.db.query(VisitorVisitLog).filter(
            VisitorVisitLog.id == log_id,
            VisitorVisitLog.status == 0
        ).first()
        if not visit_log:
            raise NotFoundError(f"Active visit log {log_id} not found")

        visit_log.check_out_time = datetime.utcnow()
        visit_log.status = 1

        # Update pre-registration status if linked
        if visit_log.pre_reg_id:
            pre_reg = self.db.query(VisitorPreRegistration).filter(
                VisitorPreRegistration.id == visit_log.pre_reg_id
            ).first()
            if pre_reg:
                pre_reg.status = 4  # checked_out

        self.db.commit()
        self.db.refresh(visit_log)
        self._remove_visitor_from_device(visit_log.visitor_id)
        return visit_log

    def get_visitor_frequency(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most frequent visitors by visit count"""
        from sqlalchemy import desc
        rows = (
            self.db.query(
                Visitor,
                func.count(VisitorVisitLog.id).label("visit_count"),
                func.max(VisitorVisitLog.check_in_time).label("last_visit"),
            )
            .join(VisitorVisitLog, VisitorVisitLog.visitor_id == Visitor.id)
            .group_by(Visitor.id)
            .order_by(desc("visit_count"))
            .limit(limit)
            .all()
        )
        return [
            {
                "visitor_id":   v.id,
                "visitor_code": v.visitor_code,
                "full_name":    v.full_name,
                "company":      v.company,
                "phone":        v.phone,
                "visit_count":  cnt,
                "last_visit":   last,
                "visitor_type": v.visitor_type.type_name if v.visitor_type else None,
            }
            for v, cnt, last in rows
        ]

    def get_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Return real aggregated analytics data"""
        from sqlalchemy import cast, Date as SADate, extract
        today = date.today()
        period_start = datetime.combine(today - timedelta(days=days), time.min)

        # Overview
        total_visitors = self.db.query(Visitor).count()
        active_visitors = self.db.query(VisitorVisitLog).filter(VisitorVisitLog.status == 0).count()
        total_visits = self.db.query(VisitorVisitLog).filter(
            VisitorVisitLog.check_in_time >= period_start
        ).count()
        blacklist_count = self.db.query(VisitorBlacklist).filter(VisitorBlacklist.is_active == True).count()

        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)
        today_checkins = self.db.query(VisitorVisitLog).filter(
            VisitorVisitLog.check_in_time >= today_start,
            VisitorVisitLog.check_in_time <= today_end
        ).count()

        overstay_count = self.db.query(VisitorVisitLog).filter(VisitorVisitLog.status == 2).count()

        # Average duration (checked-out visits in period)
        completed = self.db.query(VisitorVisitLog).filter(
            VisitorVisitLog.check_in_time >= period_start,
            VisitorVisitLog.check_out_time != None
        ).all()
        avg_hours = 0.0
        if completed:
            total_secs = sum(
                (v.check_out_time - v.check_in_time).total_seconds()
                for v in completed
            )
            avg_hours = round(total_secs / len(completed) / 3600, 2)

        pre_reg_count = self.db.query(VisitorVisitLog).filter(
            VisitorVisitLog.check_in_time >= period_start,
            VisitorVisitLog.pre_reg_id != None
        ).count()
        pre_reg_rate = round(pre_reg_count / total_visits * 100, 1) if total_visits else 0.0

        # Daily trend – last `days` days
        daily_rows = (
            self.db.query(
                cast(VisitorVisitLog.check_in_time, SADate).label("day"),
                func.count().label("cnt")
            )
            .filter(VisitorVisitLog.check_in_time >= period_start)
            .group_by("day")
            .order_by("day")
            .all()
        )
        daily_trend = [{"label": str(r.day), "count": r.cnt} for r in daily_rows]

        # Peak hours (0–23)
        hour_rows = (
            self.db.query(
                extract("hour", VisitorVisitLog.check_in_time).label("hr"),
                func.count().label("cnt")
            )
            .filter(VisitorVisitLog.check_in_time >= period_start)
            .group_by("hr")
            .order_by("hr")
            .all()
        )
        peak_hours = [{"label": f"{int(r.hr):02d}:00", "count": r.cnt} for r in hour_rows]

        # Type distribution
        type_rows = (
            self.db.query(VisitorType.type_name, func.count(VisitorVisitLog.id).label("cnt"))
            .join(Visitor, Visitor.visitor_type_id == VisitorType.id)
            .join(VisitorVisitLog, VisitorVisitLog.visitor_id == Visitor.id)
            .filter(VisitorVisitLog.check_in_time >= period_start)
            .group_by(VisitorType.type_name)
            .order_by(func.count(VisitorVisitLog.id).desc())
            .all()
        )
        type_total = sum(r.cnt for r in type_rows) or 1
        type_distribution = [
            {"type_name": r.type_name, "count": r.cnt, "percentage": round(r.cnt / type_total * 100, 1)}
            for r in type_rows
        ]

        # Top hosts
        from app.models.biotime_models import PersonnelEmployee
        host_rows = (
            self.db.query(
                PersonnelEmployee.first_name,
                PersonnelEmployee.last_name,
                func.count(VisitorVisitLog.id).label("cnt")
            )
            .join(VisitorVisitLog, VisitorVisitLog.host_emp_id == PersonnelEmployee.id)
            .filter(VisitorVisitLog.check_in_time >= period_start)
            .group_by(PersonnelEmployee.id, PersonnelEmployee.first_name, PersonnelEmployee.last_name)
            .order_by(func.count(VisitorVisitLog.id).desc())
            .limit(10)
            .all()
        )
        top_hosts = [
            {"host": f"{(r.first_name or '').strip()} {(r.last_name or '').strip()}".strip(), "count": r.cnt}
            for r in host_rows
        ]

        return {
            "overview": {
                "total_visitors": total_visitors,
                "active_visitors": active_visitors,
                "total_visits": total_visits,
                "avg_visit_duration_hours": avg_hours,
                "today_checkins": today_checkins,
                "overstay_count": overstay_count,
                "blacklist_count": blacklist_count,
                "pre_reg_rate": pre_reg_rate,
            },
            "daily_trend": daily_trend,
            "peak_hours": peak_hours,
            "type_distribution": type_distribution,
            "top_hosts": top_hosts,
        }

    def get_records_for_export(self, start_date: Optional[date] = None,
                               end_date: Optional[date] = None,
                               host_id: Optional[int] = None,
                               status: Optional[int] = None,
                               search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return visit records flattened for CSV export"""
        logs = self.get_visit_records(start_date, end_date, host_id, status, search, skip=0, limit=10000)
        rows = []
        for log in logs:
            duration_hours = None
            if log.check_in_time and log.check_out_time:
                duration_hours = round(
                    (log.check_out_time - log.check_in_time).total_seconds() / 3600, 2
                )
            status_map = {0: "On Site", 1: "Checked Out", 2: "Overstay"}
            rows.append({
                "visitor_code":   log.visitor.visitor_code if log.visitor else "",
                "full_name":      log.visitor.full_name if log.visitor else "",
                "company":        log.visitor.company if log.visitor else "",
                "phone":          log.visitor.phone if log.visitor else "",
                "visitor_type":   log.visitor.visitor_type.type_name if (log.visitor and log.visitor.visitor_type) else "",
                "host":           (f"{(log.host_employee.first_name or '').strip()} {(log.host_employee.last_name or '').strip()}".strip() if log.host_employee else ""),
                "check_in_time":  log.check_in_time.strftime("%Y-%m-%d %H:%M:%S") if log.check_in_time else "",
                "check_out_time": log.check_out_time.strftime("%Y-%m-%d %H:%M:%S") if log.check_out_time else "",
                "duration_hours": duration_hours,
                "card_no":        log.card_no or "",
                "status":         status_map.get(log.status, str(log.status)),
                "area":           log.area.area_name if log.area else "",
                "purpose":        log.pre_registration.purpose if log.pre_registration else "",
            })
        return rows

    # Helper Methods
    def _generate_visitor_code(self) -> str:
        """Generate unique visitor code"""
        today = date.today()
        prefix = f"VIS{today.strftime('%Y%m%d')}"
        
        # Get count for today
        count = self.db.query(Visitor).filter(
            Visitor.visitor_code.like(f"{prefix}%")
        ).count()
        
        return f"{prefix}{count + 1:03d}"
    
    def _generate_temp_card(self) -> str:
        """Generate temporary card number"""
        return f"TMP{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    def _is_blacklisted(self, visitor: Visitor) -> bool:
        """Check if visitor is blacklisted"""
        if visitor.is_blacklist:
            return True
        
        # Check blacklist table
        blacklist = self.db.query(VisitorBlacklist).filter(
            and_(
                VisitorBlacklist.id_no == visitor.id_no,
                VisitorBlacklist.is_active == True
            )
        ).first()
        
        return blacklist is not None
    
    def _get_mustering_zone_for_visitor(self, area_id: Optional[int], 
                                      visitor_type_id: Optional[int]) -> Optional[int]:
        """Get appropriate mustering zone for visitor"""
        # Try visitor type default first
        if visitor_type_id:
            visitor_type = self.db.query(VisitorType).filter(
                VisitorType.id == visitor_type_id
            ).first()
            if visitor_type and visitor_type.mustering_zone_id:
                return visitor_type.mustering_zone_id
        
        # Try area default
        if area_id:
            area = self.db.query(Zone).filter(Zone.id == area_id).first()
            if area and area.mustering_zone_id:
                return area.mustering_zone_id
        
        return None
    
    def _sync_visitor_to_device(self, visitor: Visitor, card_no: str, 
                               device_sn: Optional[str] = None):
        """Sync visitor to access control devices"""
        # This would integrate with the device service
        # For now, just log the action
        print(f"Syncing visitor {visitor.visitor_code} with card {card_no} to devices")
        
        # TODO: Implement actual device sync via iclock_devcmd
        # Send DATA UPDATE USERINFO command to visitor readers
        
    def _remove_visitor_from_device(self, visitor_id: int, device_sn: Optional[str] = None):
        """Remove visitor from access control devices"""
        # This would integrate with the device service
        # For now, just log the action
        print(f"Removing visitor {visitor_id} from devices")
        
        # TODO: Implement actual device removal via iclock_devcmd
        # Send DATA DELETE USERINFO command to visitor readers
