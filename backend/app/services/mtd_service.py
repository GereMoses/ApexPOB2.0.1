"""
MTD (Medical, Training, Development) Service
POB Version 2.0 - HSE Compliance Module

This service handles medical records, training certifications, PPE management,
safety inductions, expiry tracking, and compliance enforcement for oil & gas operations.
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
import os
import json
from pathlib import Path

from ..models.mtd import (
    MTDMedicalRecord, MTDCertType, MTDCertification, 
    MTDPPEType, MTDPPEIssue, MTDInductionTemplate, MTDInductionRecord,
    MTDComplianceLog, MTDAuditLog
)
from ..models.personnel import Personnel
from ..models.visitor import Visitor
from ..models.user import User
from ..core.database import get_db
from ..core.dependencies import get_current_user


class MTDService:
    """Service for managing MTD (Medical, Training, Development) operations"""
    
    def __init__(self):
        self.media_base_path = Path("/media/mtd")
        self.ensure_media_directories()
    
    def ensure_media_directories(self):
        """Ensure media directories exist for file uploads"""
        directories = [
            "medical", "certifications", "induction_docs", "ppe_photos"
        ]
        for directory in directories:
            (self.media_base_path / directory).mkdir(parents=True, exist_ok=True)
    
    # ===== MEDICAL RECORDS =====
    
    async def create_medical_record(
        self,
        medical_data: Dict[str, Any],
        db: Session,
        current_user: User
    ) -> Dict[str, Any]:
        """Create or update medical record for employee/visitor"""
        person_type = medical_data.get('person_type')  # 0=employee,1=visitor
        
        if person_type == 0:
            emp_id = medical_data.get('emp_id')
            if not emp_id:
                raise ValueError("Employee ID required for employee medical record")
            
            # Check if record exists
            existing = db.query(MTDMedicalRecord).filter(
                MTDMedicalRecord.emp_id == emp_id
            ).first()
        else:
            visitor_id = medical_data.get('visitor_id')
            if not visitor_id:
                raise ValueError("Visitor ID required for visitor medical record")
            
            existing = db.query(MTDMedicalRecord).filter(
                MTDMedicalRecord.visitor_id == visitor_id
            ).first()
        
        # Validate fit status
        fit_status = medical_data.get('fit_status', 0)
        if fit_status == 2:  # Unfit
            if not medical_data.get('restrictions'):
                raise ValueError("Restrictions required when fit status is Unfit")
        
        # Handle file upload
        cert_path = None
        if medical_data.get('cert_file'):
            cert_path = await self._save_uploaded_file(
                medical_data['cert_file'], 
                "medical",
                f"medical_{person_type}_{emp_id if person_type == 0 else visitor_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
        
        if existing:
            # Update existing record
            for key, value in medical_data.items():
                if key not in ['id', 'created_at', 'updated_time'] and hasattr(existing, key):
                    setattr(existing, key, value)
            
            existing.updated_by = current_user.id
            existing.updated_time = datetime.utcnow()
            if cert_path:
                existing.cert_path = cert_path
            
            db.commit()
            record_id = existing.id
        else:
            # Create new record
            medical_record = MTDMedicalRecord(
                person_type=person_type,
                emp_id=medical_data.get('emp_id'),
                visitor_id=medical_data.get('visitor_id'),
                blood_group=medical_data.get('blood_group'),
                height_cm=medical_data.get('height_cm'),
                weight_kg=medical_data.get('weight_kg'),
                medical_conditions=medical_data.get('medical_conditions'),
                allergies=medical_data.get('allergies'),
                disabilities=medical_data.get('disabilities'),
                fit_status=fit_status,
                restrictions=medical_data.get('restrictions'),
                doctor_name=medical_data.get('doctor_name'),
                last_checkup=medical_data.get('last_checkup'),
                next_due=medical_data.get('next_due'),
                cert_path=cert_path,
                updated_by=current_user.id
            )
            
            db.add(medical_record)
            db.commit()
            record_id = medical_record.id
        
        # Auto-suspend if unfit
        if fit_status == 2 and person_type == 0:
            await self._suspend_employee_for_medical(emp_id, db, current_user)
        
        # Log audit
        await self._create_audit_log(
            user_id=current_user.id,
            record_type="medical_record",
            record_id=record_id,
            action="create" if not existing else "edit",
            details=f"Medical record for {'employee' if person_type == 0 else 'visitor'}",
            db=db
        )
        
        return {
            "success": True,
            "record_id": record_id,
            "message": "Medical record saved successfully"
        }
    
    async def get_medical_records(
        self,
        person_type: Optional[int] = None,
        emp_id: Optional[int] = None,
        visitor_id: Optional[int] = None,
        fit_status: Optional[int] = None,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get medical records with filters"""
        if db is None:
            db = next(get_db())
        
        query = db.query(MTDMedicalRecord)
        
        if person_type is not None:
            query = query.filter(MTDMedicalRecord.person_type == person_type)
        if emp_id:
            query = query.filter(MTDMedicalRecord.emp_id == emp_id)
        if visitor_id:
            query = query.filter(MTDMedicalRecord.visitor_id == visitor_id)
        if fit_status is not None:
            query = query.filter(MTDMedicalRecord.fit_status == fit_status)
        
        records = query.all()
        
        results = []
        for record in records:
            result = {
                "id": record.id,
                "person_type": record.person_type,
                "emp_id": record.emp_id,
                "visitor_id": record.visitor_id,
                "blood_group": record.blood_group,
                "height_cm": record.height_cm,
                "weight_kg": float(record.weight_kg) if record.weight_kg else None,
                "bmi": float(record.bmi) if record.bmi else None,
                "medical_conditions": record.medical_conditions,
                "allergies": record.allergies,
                "disabilities": record.disabilities,
                "fit_status": record.fit_status,
                "fit_status_text": record.fit_status_text,
                "restrictions": record.restrictions,
                "doctor_name": record.doctor_name,
                "last_checkup": record.last_checkup.isoformat() if record.last_checkup else None,
                "next_due": record.next_due.isoformat() if record.next_due else None,
                "days_to_expiry": record.days_to_expiry,
                "is_expired": record.is_expired,
                "cert_path": record.cert_path,
                "updated_time": record.updated_time.isoformat() if record.updated_time else None
            }
            
            # Add personnel/visitor info
            if record.employee:
                result["employee"] = {
                    "id": record.employee.id,
                    "badge_id": record.employee.badge_id,
                    "full_name": record.employee.full_name,
                    "company": record.employee.company
                }
            
            if record.visitor:
                result["visitor"] = {
                    "id": record.visitor.id,
                    "full_name": record.visitor.full_name,
                    "company": record.visitor.company
                }
            
            results.append(result)
        
        return results
    
    # ===== CERTIFICATION MANAGEMENT =====
    
    async def create_cert_type(
        self,
        cert_type_data: Dict[str, Any],
        db: Session,
        current_user: User
    ) -> Dict[str, Any]:
        """Create certification type"""
        cert_type = MTDCertType(
            cert_name=cert_type_data['cert_name'],
            validity_days=cert_type_data['validity_days'],
            is_critical=cert_type_data.get('is_critical', False),
            required_for_dept=cert_type_data.get('required_for_dept', []),
            required_for_position=cert_type_data.get('required_for_position', []),
            required_for_vendor=cert_type_data.get('required_for_vendor', []),
            description=cert_type_data.get('description')
        )
        
        db.add(cert_type)
        db.commit()
        
        return {
            "success": True,
            "cert_type_id": cert_type.id,
            "message": "Certification type created successfully"
        }
    
    async def assign_certification(
        self,
        cert_data: Dict[str, Any],
        db: Session,
        current_user: User
    ) -> Dict[str, Any]:
        """Assign certification to employee/visitor"""
        person_type = cert_data.get('person_type')
        cert_type_id = cert_data.get('cert_type_id')
        
        # Validate cert type exists
        cert_type = db.query(MTDCertType).filter(MTDCertType.id == cert_type_id).first()
        if not cert_type:
            raise ValueError("Certification type not found")
        
        # Calculate expiry date
        issue_date = cert_data.get('issue_date')
        if isinstance(issue_date, str):
            issue_date = datetime.strptime(issue_date, '%Y-%m-%d').date()
        
        expiry_date = issue_date + timedelta(days=cert_type.validity_days)
        
        # Handle file upload
        cert_path = None
        if cert_data.get('cert_file'):
            person_id = cert_data.get('emp_id') if person_type == 0 else cert_data.get('visitor_id')
            cert_path = await self._save_uploaded_file(
                cert_data['cert_file'],
                "certifications",
                f"cert_{person_type}_{person_id}_{cert_type_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
        
        certification = MTDCertification(
            person_type=person_type,
            emp_id=cert_data.get('emp_id'),
            visitor_id=cert_data.get('visitor_id'),
            cert_type_id=cert_type_id,
            cert_no=cert_data.get('cert_no'),
            issuer=cert_data.get('issuer'),
            issue_date=issue_date,
            expiry_date=expiry_date,
            cert_path=cert_path,
            verified_by=current_user.id,
            verified_time=datetime.utcnow()
        )
        
        # Auto-calculate status
        if expiry_date < date.today():
            certification.status = 2  # Expired
        elif expiry_date < date.today() + timedelta(days=30):
            certification.status = 1  # Expiring
        else:
            certification.status = 0  # Valid
        
        db.add(certification)
        db.commit()
        
        # Auto-suspend if critical and expired
        if cert_type.is_critical and certification.status == 2 and person_type == 0:
            await self._suspend_employee_for_certification(
                cert_data.get('emp_id'), cert_type_id, db, current_user
            )
        
        # Log audit
        await self._create_audit_log(
            user_id=current_user.id,
            record_type="certification",
            record_id=certification.id,
            action="create",
            details=f"Assigned {cert_type.cert_name} to {'employee' if person_type == 0 else 'visitor'}",
            db=db
        )
        
        return {
            "success": True,
            "certification_id": certification.id,
            "expiry_date": expiry_date.isoformat(),
            "status": certification.status,
            "message": "Certification assigned successfully"
        }
    
    async def get_certifications(
        self,
        person_type: Optional[int] = None,
        emp_id: Optional[int] = None,
        visitor_id: Optional[int] = None,
        status: Optional[int] = None,
        expiring_days: Optional[int] = None,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get certifications with filters"""
        if db is None:
            db = next(get_db())
        
        query = db.query(MTDCertification).join(MTDCertType)
        
        if person_type is not None:
            query = query.filter(MTDCertification.person_type == person_type)
        if emp_id:
            query = query.filter(MTDCertification.emp_id == emp_id)
        if visitor_id:
            query = query.filter(MTDCertification.visitor_id == visitor_id)
        if status is not None:
            query = query.filter(MTDCertification.status == status)
        if expiring_days:
            expiry_threshold = date.today() + timedelta(days=expiring_days)
            query = query.filter(
                and_(
                    MTDCertification.expiry_date <= expiry_threshold,
                    MTDCertification.expiry_date >= date.today()
                )
            )
        
        records = query.order_by(desc(MTDCertification.issue_date)).all()
        
        results = []
        for record in records:
            result = {
                "id": record.id,
                "person_type": record.person_type,
                "emp_id": record.emp_id,
                "visitor_id": record.visitor_id,
                "cert_type_id": record.cert_type_id,
                "cert_type": {
                    "id": record.cert_type.id,
                    "cert_name": record.cert_type.cert_name,
                    "validity_days": record.cert_type.validity_days,
                    "is_critical": record.cert_type.is_critical
                },
                "cert_no": record.cert_no,
                "issuer": record.issuer,
                "issue_date": record.issue_date.isoformat() if record.issue_date else None,
                "expiry_date": record.expiry_date.isoformat() if record.expiry_date else None,
                "days_to_expiry": record.days_to_expiry,
                "status": record.status,
                "status_text": record.status_text,
                "is_expired": record.is_expired,
                "cert_path": record.cert_path,
                "verified_time": record.verified_time.isoformat() if record.verified_time else None
            }
            
            # Add personnel/visitor info
            if record.employee:
                result["employee"] = {
                    "id": record.employee.id,
                    "badge_id": record.employee.badge_id,
                    "full_name": record.employee.full_name,
                    "company": record.employee.company
                }
            
            if record.visitor:
                result["visitor"] = {
                    "id": record.visitor.id,
                    "full_name": record.visitor.full_name,
                    "company": record.visitor.company
                }
            
            results.append(result)
        
        return results
    
    # ===== PPE MANAGEMENT =====
    
    async def create_ppe_type(
        self,
        ppe_data: Dict[str, Any],
        db: Session,
        current_user: User
    ) -> Dict[str, Any]:
        """Create PPE type"""
        ppe_type = MTDPPEType(
            ppe_name=ppe_data['ppe_name'],
            lifespan_days=ppe_data.get('lifespan_days'),
            requires_calibration=ppe_data.get('requires_calibration', False),
            calib_interval_days=ppe_data.get('calib_interval_days'),
            description=ppe_data.get('description')
        )
        
        db.add(ppe_type)
        db.commit()
        
        return {
            "success": True,
            "ppe_type_id": ppe_type.id,
            "message": "PPE type created successfully"
        }
    
    async def issue_ppe(
        self,
        issue_data: Dict[str, Any],
        db: Session,
        current_user: User
    ) -> Dict[str, Any]:
        """Issue PPE to employee"""
        emp_id = issue_data.get('emp_id')
        ppe_type_id = issue_data.get('ppe_type_id')
        
        # Check if already issued same PPE type
        existing = db.query(MTDPPEIssue).filter(
            and_(
                MTDPPEIssue.emp_id == emp_id,
                MTDPPEIssue.ppe_type_id == ppe_type_id,
                MTDPPEIssue.status == 0  # Still issued
            )
        ).first()
        
        if existing:
            raise ValueError(f"PPE already issued to employee. Return current issue first.")
        
        # Calculate due return date
        ppe_type = db.query(MTDPPEType).filter(MTDPPEType.id == ppe_type_id).first()
        if not ppe_type:
            raise ValueError("PPE type not found")
        
        issue_date = issue_data.get('issue_date', date.today())
        due_return_date = issue_date + timedelta(days=ppe_type.lifespan_days) if ppe_type.lifespan_days else None
        
        ppe_issue = MTDPPEIssue(
            emp_id=emp_id,
            ppe_type_id=ppe_type_id,
            serial_no=issue_data.get('serial_no'),
            issue_date=issue_date,
            due_return_date=due_return_date,
            condition_out=issue_data.get('condition_out', 1),
            last_calib_date=issue_data.get('last_calib_date'),
            issued_by=current_user.id
        )
        
        db.add(ppe_issue)
        db.commit()
        
        return {
            "success": True,
            "ppe_issue_id": ppe_issue.id,
            "due_return_date": due_return_date.isoformat() if due_return_date else None,
            "message": "PPE issued successfully"
        }
    
    async def return_ppe(
        self,
        ppe_issue_id: int,
        return_data: Dict[str, Any],
        db: Session,
        current_user: User
    ) -> Dict[str, Any]:
        """Return issued PPE"""
        ppe_issue = db.query(MTDPPEIssue).filter(MTDPPEIssue.id == ppe_issue_id).first()
        if not ppe_issue:
            raise ValueError("PPE issue not found")
        
        ppe_issue.return_date = return_data.get('return_date', date.today())
        ppe_issue.condition_in = return_data.get('condition_in')
        ppe_issue.status = 1  # Returned
        
        db.commit()
        
        return {
            "success": True,
            "message": "PPE returned successfully"
        }
    
    # ===== INDUCTION MANAGEMENT =====
    
    async def create_induction_template(
        self,
        template_data: Dict[str, Any],
        db: Session,
        current_user: User
    ) -> Dict[str, Any]:
        """Create induction template"""
        template = MTDInductionTemplate(
            template_name=template_data['template_name'],
            video_path=template_data.get('video_path'),
            slides_path=template_data.get('slides_path'),
            quiz_questions=template_data.get('quiz_questions', []),
            passing_score=template_data.get('passing_score', 80),
            validity_days=template_data.get('validity_days', 365),
            required_for_type=template_data.get('required_for_type'),
            description=template_data.get('description')
        )
        
        db.add(template)
        db.commit()
        
        return {
            "success": True,
            "template_id": template.id,
            "message": "Induction template created successfully"
        }
    
    async def take_induction(
        self,
        induction_data: Dict[str, Any],
        db: Session,
        current_user: User
    ) -> Dict[str, Any]:
        """Record induction completion"""
        person_type = induction_data.get('person_type')
        template_id = induction_data.get('template_id')
        
        # Get template
        template = db.query(MTDInductionTemplate).filter(MTDInductionTemplate.id == template_id).first()
        if not template:
            raise ValueError("Induction template not found")
        
        # Calculate score and pass/fail
        score = induction_data.get('score', 0)
        passed = score >= template.passing_score
        
        # Calculate validity
        taken_date = induction_data.get('taken_date', date.today())
        valid_until = taken_date + timedelta(days=template.validity_days)
        
        # Handle signed document
        signed_doc_path = None
        if induction_data.get('signed_doc'):
            person_id = induction_data.get('emp_id') if person_type == 0 else induction_data.get('visitor_id')
            signed_doc_path = await self._save_uploaded_file(
                induction_data['signed_doc'],
                "induction_docs",
                f"induction_{person_type}_{person_id}_{template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
        
        induction_record = MTDInductionRecord(
            person_type=person_type,
            emp_id=induction_data.get('emp_id'),
            visitor_id=induction_data.get('visitor_id'),
            template_id=template_id,
            taken_date=taken_date,
            score=score,
            passed=passed,
            valid_until=valid_until,
            signed_doc=signed_doc_path,
            trainer_emp_id=induction_data.get('trainer_emp_id'),
            quiz_answers=induction_data.get('quiz_answers'),
            completion_time=datetime.utcnow()
        )
        
        db.add(induction_record)
        db.commit()
        
        # Update visitor safety induction status
        if person_type == 1:  # Visitor
            visitor = db.query(Visitor).filter(Visitor.id == induction_data.get('visitor_id')).first()
            if visitor:
                visitor.safety_induction_done = True
                db.commit()
        
        return {
            "success": True,
            "record_id": induction_record.id,
            "passed": passed,
            "valid_until": valid_until.isoformat(),
            "message": "Induction recorded successfully"
        }
    
    # ===== COMPLIANCE AND EXPIRY TRACKING =====
    
    async def get_expiring_items(
        self,
        days: int = 30,
        types: Optional[List[str]] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Get items expiring within specified days"""
        if db is None:
            db = next(get_db())
        
        expiry_threshold = date.today() + timedelta(days=days)
        result = {
            "medical": [],
            "certifications": [],
            "ppe": [],
            "inductions": []
        }
        
        if not types or "medical" in types:
            # Medical records expiring
            medical_records = db.query(MTDMedicalRecord).filter(
                and_(
                    MTDMedicalRecord.next_due <= expiry_threshold,
                    MTDMedicalRecord.next_due >= date.today()
                )
            ).all()
            
            for record in medical_records:
                result["medical"].append({
                    "id": record.id,
                    "person_type": record.person_type,
                    "emp_id": record.emp_id,
                    "visitor_id": record.visitor_id,
                    "next_due": record.next_due.isoformat(),
                    "days_to_expiry": record.days_to_expiry,
                    "person_name": record.employee.full_name if record.employee else record.visitor.full_name if record.visitor else "Unknown"
                })
        
        if not types or "certifications" in types:
            # Certifications expiring
            certs = db.query(MTDCertification).join(MTDCertType).filter(
                and_(
                    MTDCertification.expiry_date <= expiry_threshold,
                    MTDCertification.expiry_date >= date.today()
                )
            ).all()
            
            for cert in certs:
                result["certifications"].append({
                    "id": cert.id,
                    "person_type": cert.person_type,
                    "emp_id": cert.emp_id,
                    "visitor_id": cert.visitor_id,
                    "cert_name": cert.cert_type.cert_name,
                    "is_critical": cert.cert_type.is_critical,
                    "expiry_date": cert.expiry_date.isoformat(),
                    "days_to_expiry": cert.days_to_expiry,
                    "person_name": cert.employee.full_name if cert.employee else cert.visitor.full_name if cert.visitor else "Unknown"
                })
        
        if not types or "ppe" in types:
            # PPE calibration due
            ppe_items = db.query(MTDPPEIssue).join(MTDPPEType).filter(
                and_(
                    MTDPPEIssue.next_calib_date <= expiry_threshold,
                    MTDPPEIssue.next_calib_date >= date.today(),
                    MTDPPEIssue.status == 0  # Still issued
                )
            ).all()
            
            for item in ppe_items:
                result["ppe"].append({
                    "id": item.id,
                    "emp_id": item.emp_id,
                    "ppe_name": item.ppe_type.ppe_name,
                    "serial_no": item.serial_no,
                    "next_calib_date": item.next_calib_date.isoformat() if item.next_calib_date else None,
                    "days_to_calib": (item.next_calib_date - date.today()).days if item.next_calib_date else None,
                    "person_name": item.employee.full_name if item.employee else "Unknown"
                })
        
        if not types or "inductions" in types:
            # Inductions expiring
            inductions = db.query(MTDInductionRecord).join(MTDInductionTemplate).filter(
                and_(
                    MTDInductionRecord.valid_until <= expiry_threshold,
                    MTDInductionRecord.valid_until >= date.today()
                )
            ).all()
            
            for induction in inductions:
                result["inductions"].append({
                    "id": induction.id,
                    "person_type": induction.person_type,
                    "emp_id": induction.emp_id,
                    "visitor_id": induction.visitor_id,
                    "template_name": induction.template.template_name,
                    "valid_until": induction.valid_until.isoformat(),
                    "days_to_expiry": induction.days_to_expiry,
                    "person_name": induction.employee.full_name if induction.employee else induction.visitor.full_name if induction.visitor else "Unknown"
                })
        
        return result
    
    async def get_compliance_report(
        self,
        dept_id: Optional[int] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Get compliance report by department"""
        if db is None:
            db = next(get_db())
        
        # Active staff only — leavers have no compliance to track
        query = db.query(Personnel).filter(Personnel.is_active == True)  # noqa: E712
        if dept_id:
            query = query.filter(Personnel.dept_id == dept_id)
        
        personnel_list = query.all()
        
        total_personnel = len(personnel_list)
        compliant_count = 0
        non_compliant_list = []
        
        for person in personnel_list:
            is_compliant = True
            missing_items = []
            
            # Check medical fitness
            medical = db.query(MTDMedicalRecord).filter(
                MTDMedicalRecord.emp_id == person.id
            ).first()
            
            if not medical or medical.fit_status == 2:  # Unfit
                is_compliant = False
                missing_items.append("Medical Fitness")
            
            # Check critical certifications
            critical_certs = db.query(MTDCertification).join(MTDCertType).filter(
                and_(
                    MTDCertification.emp_id == person.id,
                    MTDCertType.is_critical == True,
                    or_(
                        MTDCertification.status == 2,  # Expired
                        MTDCertification.expiry_date < date.today()
                    )
                )
            ).all()
            
            if critical_certs:
                is_compliant = False
                for cert in critical_certs:
                    missing_items.append(f"{cert.cert_type.cert_name} (Expired)")
            
            # Check overdue PPE
            overdue_ppe = db.query(MTDPPEIssue).filter(
                and_(
                    MTDPPEIssue.emp_id == person.id,
                    MTDPPEIssue.status == 0,  # Still issued
                    MTDPPEIssue.due_return_date < date.today()
                )
            ).count()
            
            if overdue_ppe > 0:
                is_compliant = False
                missing_items.append(f"Overdue PPE ({overdue_ppe} items)")
            
            if is_compliant:
                compliant_count += 1
            else:
                non_compliant_list.append({
                    "personnel_id": person.id,
                    "badge_id": person.badge_id,
                    "full_name": person.full_name,
                    "company": person.company,
                    "missing_items": missing_items
                })
        
        compliance_rate = (compliant_count / total_personnel * 100) if total_personnel > 0 else 0
        
        return {
            "total_personnel": total_personnel,
            "compliant_count": compliant_count,
            "non_compliant_count": total_personnel - compliant_count,
            "compliance_rate": round(compliance_rate, 2),
            "non_compliant_list": non_compliant_list
        }
    
    # ===== HELPER METHODS =====
    
    async def _save_uploaded_file(self, file_data: bytes, directory: str, filename: str) -> str:
        """Save uploaded file to media directory"""
        file_path = self.media_base_path / directory / filename
        with open(file_path, 'wb') as f:
            f.write(file_data)
        return str(file_path)
    
    async def _create_audit_log(
        self,
        user_id: int,
        record_type: str,
        record_id: int,
        action: str,
        details: str,
        db: Session
    ):
        """Create audit log entry"""
        audit_log = MTDAuditLog(
            user_id=user_id,
            record_type=record_type,
            record_id=record_id,
            action=action,
            details=details
        )
        db.add(audit_log)
        db.commit()
    
    async def _suspend_employee_for_medical(
        self, emp_id: int, db: Session, current_user: User
    ):
        """Suspend employee due to medical unfitness"""
        employee = db.query(Personnel).filter(Personnel.id == emp_id).first()
        if employee:
            employee.status = 2  # Suspended
            db.commit()
            
            # Log compliance action
            compliance_log = MTDComplianceLog(
                emp_id=emp_id,
                record_type="medical",
                status=2,  # Non-compliant
                action_taken="Suspended",
                details="Employee suspended due to medical unfitness",
                created_by=current_user.id
            )
            db.add(compliance_log)
            db.commit()
    
    async def _suspend_employee_for_certification(
        self, emp_id: int, cert_type_id: int, db: Session, current_user: User
    ):
        """Suspend employee due to critical certification expiry"""
        employee = db.query(Personnel).filter(Personnel.id == emp_id).first()
        if employee:
            employee.status = 2  # Suspended
            db.commit()
            
            # Log compliance action
            compliance_log = MTDComplianceLog(
                emp_id=emp_id,
                cert_type_id=cert_type_id,
                record_type="certification",
                status=2,  # Non-compliant
                action_taken="Suspended",
                details="Employee suspended due to critical certification expiry",
                created_by=current_user.id
            )
            db.add(compliance_log)
            db.commit()


# Create singleton instance
mtd_service = MTDService()
