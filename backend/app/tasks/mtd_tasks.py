import asyncio
"""
MTD (Medical, Training, Development) Celery Tasks
POB Version 2.0 - HSE Compliance Module

Background tasks for expiry checking, auto-suspension, notifications,
and compliance enforcement for oil and gas operations.
"""

from celery import Celery
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from ..core.database import get_db
from ..models.mtd import (
    MTDMedicalRecord, MTDCertification, MTDPPEIssue, MTDInductionRecord,
    MTDCertType, MTDPPEType, MTDInductionTemplate
)
from ..models.personnel import Personnel
from ..models.user import User
from ..services.mtd_service import mtd_service

logger = logging.getLogger(__name__)

celery_app = Celery('mtd_tasks')


@celery_app.task
def check_medical_expiry():
    """Check medical record expiry and suspend unfit personnel"""
    db = next(get_db())
    try:
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        
        # Get medical records expiring or expired
        expiring_records = db.query(MTDMedicalRecord).filter(
            and_(
                MTDMedicalRecord.next_due <= warning_threshold,
                MTDMedicalRecord.next_due.isnot(None)
            )
        ).all()
        
        expired_records = db.query(MTDMedicalRecord).filter(
            and_(
                MTDMedicalRecord.next_due < today,
                MTDMedicalRecord.next_due.isnot(None)
            )
        ).all()
        
        for record in expiring_records:
            days_to_expiry = (record.next_due - today).days
            if days_to_expiry <= 0:
                # Medical expired - suspend personnel
                if record.person_type == 0:  # Employee
                    employee = db.query(Personnel).filter(Personnel.id == record.emp_id).first()
                    if employee:
                        employee.status = 2  # Suspended
                        db.commit()
                        logger.info(f"Suspended employee {employee.full_name} due to expired medical record")
                        
                        # Create compliance log
                        from ..models.mtd import MTDComplianceLog
                        compliance_log = MTDComplianceLog(
                            emp_id=record.emp_id,
                            record_type="medical",
                            status=2,  # Non-compliant
                            action_taken="Suspended",
                            details=f"Employee suspended due to expired medical checkup (was due on {record.next_due})",
                            created_by=1  # System user
                        )
                        db.add(compliance_log)
                        db.commit()
            
            elif days_to_expiry <= 30:
                # Send warning notification
                logger.info(f"Medical checkup expiring for {record.emp_id} in {days_to_expiry} days")
                # TODO: Send email/SMS notification
        
        for record in expired_records:
            days_overdue = (today - record.next_due).days
            logger.warning(f"Medical checkup overdue by {days_overdue} days for {record.emp_id}")
            
    except Exception as e:
        logger.error(f"Error in medical expiry check: {str(e)}")
    finally:
        db.close()


@celery_app.task
def check_certification_expiry():
    """Check certification expiry and suspend personnel with critical expired certs"""
    db = next(get_db())
    try:
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        
        # Get certifications expiring or expired
        expiring_certs = db.query(MTDCertification).join(MTDCertType).filter(
            and_(
                MTDCertification.expiry_date <= warning_threshold,
                MTDCertification.expiry_date.isnot(None)
            )
        ).all()
        
        expired_certs = db.query(MTDCertification).join(MTDCertType).filter(
            and_(
                MTDCertification.expiry_date < today,
                MTDCertification.expiry_date.isnot(None)
            )
        ).all()
        
        for cert in expiring_certs:
            days_to_expiry = (cert.expiry_date - today).days
            if days_to_expiry <= 0:
                # Certification expired
                if cert.cert_type.is_critical:
                    # Critical cert expired - suspend personnel
                    if cert.person_type == 0:  # Employee
                        employee = db.query(Personnel).filter(Personnel.id == cert.emp_id).first()
                        if employee:
                            employee.status = 2  # Suspended
                            db.commit()
                            logger.info(f"Suspended employee {employee.full_name} due to expired critical certification {cert.cert_type.cert_name}")
                            
                            # Create compliance log
                            from ..models.mtd import MTDComplianceLog
                            compliance_log = MTDComplianceLog(
                                emp_id=cert.emp_id,
                                cert_type_id=cert.cert_type_id,
                                record_type="certification",
                                status=2,  # Non-compliant
                                action_taken="Suspended",
                                details=f"Employee suspended due to expired critical certification {cert.cert_type.cert_name} (was due on {cert.expiry_date})",
                                created_by=1  # System user
                            )
                            db.add(compliance_log)
                            db.commit()
                else:
                    # Non-critical cert expired
                    logger.warning(f"Non-critical certification expired for {cert.emp_id}: {cert.cert_type.cert_name}")
            
            elif days_to_expiry <= 30:
                # Send warning notification
                logger.info(f"Certification expiring for {cert.emp_id}: {cert.cert_type.cert_name} in {days_to_expiry} days")
                # TODO: Send email/SMS notification
        
        for cert in expired_certs:
            days_overdue = (today - cert.expiry_date).days
            if cert.cert_type.is_critical:
                logger.warning(f"Critical certification overdue by {days_overdue} days for {cert.emp_id}: {cert.cert_type.cert_name}")
            else:
                logger.warning(f"Certification overdue by {days_overdue} days for {cert.emp_id}: {cert.cert_type.cert_name}")
            
    except Exception as e:
        logger.error(f"Error in certification expiry check: {str(e)}")
    finally:
        db.close()


@celery_app.task
def check_ppe_calibration_due():
    """Check PPE calibration due dates and send alerts"""
    db = next(get_db())
    try:
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        
        # Get PPE items requiring calibration
        calibration_due = db.query(MTDPPEIssue).join(MTDPPEType).filter(
            and_(
                MTDPPEIssue.next_calib_date <= warning_threshold,
                MTDPPEIssue.next_calib_date.isnot(None),
                MTDPPEIssue.status == 0,  # Still issued
                MTDPPEType.requires_calibration == True
            )
        ).all()
        
        overdue_calibration = db.query(MTDPPEIssue).join(MTDPPEType).filter(
            and_(
                MTDPPEIssue.next_calib_date < today,
                MTDPPEIssue.next_calib_date.isnot(None),
                MTDPPEIssue.status == 0,  # Still issued
                MTDPPEType.requires_calibration == True
            )
        ).all()
        
        for item in calibration_due:
            days_to_calib = (item.next_calib_date - today).days
            if days_to_calib <= 0:
                logger.warning(f"PPE calibration overdue by {abs(days_to_calib)} days for {item.emp_id}: {item.ppe_type.ppe_name}")
            else:
                logger.info(f"PPE calibration due for {item.emp_id}: {item.ppe_type.ppe_name} in {days_to_calib} days")
        
        for item in overdue_calibration:
            days_overdue = (today - item.next_calib_date).days
            logger.error(f"PPE calibration overdue by {days_overdue} days for {item.emp_id}: {item.ppe_type.ppe_name}")
            
    except Exception as e:
        logger.error(f"Error in PPE calibration check: {str(e)}")
    finally:
        db.close()


@celery_app.task
def check_induction_expiry():
    """Check induction expiry and send alerts"""
    db = next(get_db())
    try:
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        
        # Get inductions expiring
        expiring_inductions = db.query(MTDInductionRecord).join(MTDInductionTemplate).filter(
            and_(
                MTDInductionRecord.valid_until <= warning_threshold,
                MTDInductionRecord.valid_until.isnot(None)
            )
        ).all()
        
        expired_inductions = db.query(MTDInductionRecord).join(MTDInductionTemplate).filter(
            and_(
                MTDInductionRecord.valid_until < today,
                MTDInductionRecord.valid_until.isnot(None)
            )
        ).all()
        
        for induction in expiring_inductions:
            days_to_expiry = (induction.valid_until - today).days
            if days_to_expiry <= 0:
                logger.warning(f"Induction expired for {induction.emp_id}: {induction.template.template_name}")
            else:
                logger.info(f"Induction expiring for {induction.emp_id}: {induction.template.template_name} in {days_to_expiry} days")
        
        for induction in expired_inductions:
            days_overdue = (today - induction.valid_until).days
            logger.error(f"Induction expired by {days_overdue} days for {induction.emp_id}: {induction.template.template_name}")
            
    except Exception as e:
        logger.error(f"Error in induction expiry check: {str(e)}")
    finally:
        db.close()


@celery_app.task
def generate_compliance_report():
    """Generate daily compliance report"""
    db = next(get_db())
    try:
        today = date.today()
        
        # Get overall compliance statistics
        total_personnel = db.query(Personnel).filter(Personnel.is_active == True).count()
        
        # Get compliance data using service
        compliance_report = asyncio.run(mtd_service.get_compliance_report(db=db))
        
        logger.info(f"Daily compliance report generated: {compliance_report}")
        
        # TODO: Send report via email or save to file
        
    except Exception as e:
        logger.error(f"Error generating compliance report: {str(e)}")
    finally:
        db.close()


@celery_app.task
def send_expiry_notifications():
    """Send notifications for expiring items"""
    db = next(get_db())
    try:
        # Get all expiring items
        expiring_data = asyncio.run(mtd_service.get_expiring_items(days=30, db=db))
        
        total_expiring = (
            len(expiring_data.get('medical', [])) +
            len(expiring_data.get('certifications', [])) +
            len(expiring_data.get('ppe', [])) +
            len(expiring_data.get('inductions', []))
        )
        
        if total_expiring > 0:
            logger.info(f"Sending expiry notifications for {total_expiring} items")
            # TODO: Implement email/SMS notifications
            # TODO: Create notification records
        
    except Exception as e:
        logger.error(f"Error sending expiry notifications: {str(e)}")
    finally:
        db.close()


@celery_app.task
def auto_suspend_non_compliant():
    """Automatically suspend personnel with critical compliance issues"""
    db = next(get_db())
    try:
        # Get non-compliant personnel from compliance service
        compliance_report = asyncio.run(mtd_service.get_compliance_report(db=db))
        
        non_compliant_personnel = compliance_report.get('non_compliant_list', [])
        
        suspended_count = 0
        for person_data in non_compliant_personnel:
            emp_id = person_data['personnel_id']
            employee = db.query(Personnel).filter(Personnel.id == emp_id).first()
            
            if employee and employee.status != 2:  # Not already suspended
                employee.status = 2  # Suspended
                db.commit()
                suspended_count += 1
                
                # Create compliance log
                from ..models.mtd import MTDComplianceLog
                compliance_log = MTDComplianceLog(
                    emp_id=emp_id,
                    record_type="enforcement",
                    status=2,  # Non-compliant
                    action_taken="Suspended",
                    details="Automatically suspended due to critical compliance issues",
                    created_by=1  # System user
                )
                db.add(compliance_log)
                db.commit()
                
                logger.info(f"Auto-suspended employee {employee.full_name} due to compliance issues")
        
        logger.info(f"Auto-suspended {suspended_count} personnel for compliance issues")
        
    except Exception as e:
        logger.error(f"Error in auto-suspension task: {str(e)}")
    finally:
        db.close()


# Schedule periodic tasks
@celery_app.task
def schedule_daily_checks():
    """Schedule all daily MTD checks"""
    try:
        # Run all checks
        check_medical_expiry.delay()
        check_certification_expiry.delay()
        check_ppe_calibration_due.delay()
        check_induction_expiry.delay()
        generate_compliance_report.delay()
        send_expiry_notifications.delay()
        
        logger.info("Scheduled daily MTD compliance checks")
        
    except Exception as e:
        logger.error(f"Error scheduling daily checks: {str(e)}")


# Configure Celery Beat schedule for daily execution
from celery.schedules import crontab
from celery.beat import Scheduler

# Run daily at 8:00 AM
crontab_schedule = crontab(
    schedule_daily_checks.s(),
    hour=8,
    minute=0,
    name='mtd-daily-compliance-checks'
)
