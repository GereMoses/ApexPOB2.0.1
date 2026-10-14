"""
Vendor/Contractor Management API
REST API endpoints for vendor and contractor management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from typing import List, Optional
import logging

from ..core.database import get_db
from ..services.vendor_contractor_service import vendor_contractor_service
from ..schemas.vendor_contractor import (
    VendorCreate, VendorUpdate, VendorResponse, VendorContractCreate, VendorContractResponse,
    ContractorCreate, ContractorResponse, ContractAssignmentCreate, ContractAssignmentResponse,
    VendorComplianceCreate, VendorComplianceResponse, VendorStatisticsResponse,
    BulkVendorAction, BulkVendorResponse, VendorSearchResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vendor-contractor", tags=["Vendor/Contractor Management"])


@router.get("/vendors", response_model=dict)
async def get_vendors(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search term for vendor name or code"),
    vendor_type: Optional[str] = Query(None, description="Filter by vendor type"),
    status: Optional[str] = Query(None, description="Filter by vendor status"),
    service_area: Optional[str] = Query(None, description="Filter by service area"),
    db: Session = Depends(get_db)
):
    """
    Get vendors with filtering and pagination
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        search: Search term for vendor name or code
        vendor_type: Filter by vendor type
        status: Filter by vendor status
        service_area: Filter by service area
        db: Database session
        
    Returns:
        Paginated list of vendors
    """
    try:
        result = await vendor_contractor_service.get_vendors(
            db, skip, limit, search, vendor_type, status, service_area
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "total_count": result["total_count"],
                "skip": result["skip"],
                "limit": result["limit"],
                "page": (result["skip"] // result["limit"]) + 1,
                "total_pages": (result["total_count"] + result["limit"] - 1) // result["limit"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get vendors")
            )
    except Exception as e:
        logger.error(f"Error in get_vendors: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/vendors/{vendor_id}", response_model=dict)
async def get_vendor_by_id(
    vendor_id: int,
    db: Session = Depends(get_db)
):
    """
    Get vendor by ID
    
    Args:
        vendor_id: Vendor ID
        db: Database session
        
    Returns:
        Vendor details
    """
    try:
        from ..models.vendor_contractor import Vendor
        
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        
        if not vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor not found"
            )
        
        # Enhance with related data
        vendor_data = {
            "id": vendor.id,
            "vendor_code": vendor.vendor_code,
            "vendor_name": vendor.vendor_name,
            "vendor_type": vendor.vendor_type.value,
            "status": vendor.status.value,
            "description": vendor.description,
            "contact_person": vendor.contact_person,
            "email": vendor.email,
            "phone": vendor.phone,
            "mobile": vendor.mobile,
            "fax": vendor.fax,
            "address_line1": vendor.address_line1,
            "address_line2": vendor.address_line2,
            "city": vendor.city,
            "state": vendor.state,
            "country": vendor.country,
            "postal_code": vendor.postal_code,
            "business_registration": vendor.business_registration,
            "tax_id": vendor.tax_id,
            "website": vendor.website,
            "services_offered": vendor.services_offered,
            "service_areas": vendor.service_areas,
            "certifications": vendor.certifications,
            "payment_terms": vendor.payment_terms,
            "credit_limit": vendor.credit_limit,
            "currency": vendor.currency,
            "compliance_status": vendor.compliance_status.value if vendor.compliance_status else None,
            "last_compliance_check": vendor.last_compliance_check,
            "next_compliance_due": vendor.next_compliance_due,
            "risk_rating": vendor.risk_rating,
            "performance_score": vendor.performance_score,
            "total_contracts": vendor.total_contracts,
            "active_contracts": vendor.active_contracts,
            "created_by": vendor.created_by,
            "created_at": vendor.created_at,
            "updated_by": vendor.updated_by,
            "updated_at": vendor.updated_at,
            "notes": vendor.notes
        }
        
        return {
            "success": True,
            "data": vendor_data
        }
        
    except Exception as e:
        logger.error(f"Error in get_vendor_by_id: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/vendors", response_model=dict)
async def create_vendor(
    vendor: VendorCreate,
    db: Session = Depends(get_db)
):
    """
    Create new vendor
    
    Args:
        vendor: Vendor creation data
        db: Database session
        
    Returns:
        Created vendor details
    """
    try:
        result = await vendor_contractor_service.create_vendor(
            vendor.dict(), db, created_by=1  # TODO: Get actual user ID
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "message": "Vendor created successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create vendor")
            )
    except Exception as e:
        logger.error(f"Error in create_vendor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.put("/vendors/{vendor_id}", response_model=dict)
async def update_vendor(
    vendor_id: int,
    vendor: VendorUpdate,
    db: Session = Depends(get_db)
):
    """
    Update existing vendor
    
    Args:
        vendor_id: Vendor ID
        vendor: Vendor update data
        db: Database session
        
    Returns:
        Updated vendor details
    """
    try:
        result = await vendor_contractor_service.update_vendor(
            vendor_id, vendor.dict(exclude_unset=True), db, updated_by=1
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "message": "Vendor updated successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to update vendor")
            )
    except Exception as e:
        logger.error(f"Error in update_vendor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/vendors/contracts", response_model=dict)
async def create_vendor_contract(
    contract: VendorContractCreate,
    db: Session = Depends(get_db)
):
    """
    Create vendor contract
    
    Args:
        contract: Contract creation data
        db: Database session
        
    Returns:
        Created contract details
    """
    try:
        result = await vendor_contractor_service.create_vendor_contract(
            contract.dict(), db, created_by=1
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "message": "Contract created successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create contract")
            )
    except Exception as e:
        logger.error(f"Error in create_vendor_contract: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/vendors/contracts", response_model=dict)
async def get_vendor_contracts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    vendor_id: Optional[int] = Query(None, description="Filter by vendor ID"),
    status: Optional[str] = Query(None, description="Filter by contract status"),
    db: Session = Depends(get_db)
):
    """
    Get vendor contracts
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        vendor_id: Filter by vendor ID
        status: Filter by contract status
        db: Database session
        
    Returns:
        List of vendor contracts
    """
    try:
        from ..models.vendor_contractor import VendorContract, Vendor
        
        query = db.query(VendorContract)
        
        if vendor_id:
            query = query.filter(VendorContract.vendor_id == vendor_id)
        
        if status:
            query = query.filter(VendorContract.status == status)
        
        contracts = query.order_by(desc(VendorContract.created_at)).offset(skip).limit(limit).all()
        
        result_contracts = []
        for contract in contracts:
            contract_data = {
                "id": contract.id,
                "vendor_id": contract.vendor_id,
                "contract_number": contract.contract_number,
                "contract_name": contract.contract_name,
                "contract_type": contract.contract_type,
                "status": contract.status.value,
                "start_date": contract.start_date,
                "end_date": contract.end_date,
                "renewal_date": contract.renewal_date,
                "notice_period_days": contract.notice_period_days,
                "total_value": contract.total_value,
                "currency": contract.currency,
                "payment_terms": contract.payment_terms,
                "billing_frequency": contract.billing_frequency,
                "sla_requirements": contract.sla_requirements,
                "penalty_clauses": contract.penalty_clauses,
                "scope_of_work": contract.scope_of_work,
                "deliverables": contract.deliverables,
                "key_performance_indicators": contract.key_performance_indicators,
                "contract_manager": contract.contract_manager,
                "legal_reviewer": contract.legal_reviewer,
                "approved_by": contract.approved_by,
                "approved_at": contract.approved_at,
                "performance_score": contract.performance_score,
                "compliance_score": contract.compliance_score,
                "last_performance_review": contract.last_performance_review,
                "created_by": contract.created_by,
                "created_at": contract.created_at,
                "updated_by": contract.updated_by,
                "updated_at": contract.updated_at,
                "notes": contract.notes
            }
            
            # Add vendor info
            if contract.vendor:
                contract_data["vendor_name"] = contract.vendor.vendor_name
                contract_data["vendor_code"] = contract.vendor.vendor_code
            
            result_contracts.append(contract_data)
        
        return {
            "success": True,
            "data": result_contracts
        }
        
    except Exception as e:
        logger.error(f"Error in get_vendor_contracts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/contractors", response_model=dict)
async def create_contractor(
    contractor: ContractorCreate,
    db: Session = Depends(get_db)
):
    """
    Create new contractor
    
    Args:
        contractor: Contractor creation data
        db: Database session
        
    Returns:
        Created contractor details
    """
    try:
        result = await vendor_contractor_service.create_contractor(
            contractor.dict(), db, created_by=1
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "message": "Contractor created successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create contractor")
            )
    except Exception as e:
        logger.error(f"Error in create_contractor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/contractors", response_model=dict)
async def get_contractors(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search term for contractor name"),
    vendor_id: Optional[int] = Query(None, description="Filter by vendor ID"),
    status: Optional[str] = Query(None, description="Filter by contractor status"),
    availability_status: Optional[str] = Query(None, description="Filter by availability status"),
    db: Session = Depends(get_db)
):
    """
    Get contractors
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        search: Search term for contractor name
        vendor_id: Filter by vendor ID
        status: Filter by contractor status
        availability_status: Filter by availability status
        db: Database session
        
    Returns:
        List of contractors
    """
    try:
        from ..models.vendor_contractor import Contractor, Vendor
        
        query = db.query(Contractor)
        
        if search:
            query = query.filter(
                or_(
                    Contractor.first_name.ilike(f"%{search}%"),
                    Contractor.last_name.ilike(f"%{search}%"),
                    Contractor.email.ilike(f"%{search}%")
                )
            )
        
        if vendor_id:
            query = query.filter(Contractor.vendor_id == vendor_id)
        
        if status:
            query = query.filter(Contractor.status == status)
        
        if availability_status:
            query = query.filter(Contractor.availability_status == availability_status)
        
        contractors = query.order_by(Contractor.last_name, Contractor.first_name).offset(skip).limit(limit).all()
        
        result_contractors = []
        for contractor in contractors:
            contractor_data = {
                "id": contractor.id,
                "vendor_id": contractor.vendor_id,
                "contractor_code": contractor.contractor_code,
                "first_name": contractor.first_name,
                "last_name": contractor.last_name,
                "email": contractor.email,
                "phone": contractor.phone,
                "date_of_birth": contractor.date_of_birth,
                "national_id": contractor.national_id,
                "passport_number": contractor.passport_number,
                "work_permit_number": contractor.work_permit_number,
                "work_permit_expiry": contractor.work_permit_expiry,
                "job_title": contractor.job_title,
                "specialization": contractor.specialization,
                "experience_years": contractor.experience_years,
                "hourly_rate": contractor.hourly_rate,
                "daily_rate": contractor.daily_rate,
                "currency": contractor.currency,
                "skills": contractor.skills,
                "certifications": contractor.certifications,
                "security_clearance": contractor.security_clearance,
                "status": contractor.status,
                "availability_status": contractor.availability_status,
                "preferred_work_locations": contractor.preferred_work_locations,
                "background_check_status": contractor.background_check_status,
                "background_check_date": contractor.background_check_date,
                "medical_clearance_status": contractor.medical_clearance_status,
                "medical_clearance_date": contractor.medical_clearance_date,
                "created_by": contractor.created_by,
                "created_at": contractor.created_at,
                "updated_by": contractor.updated_by,
                "updated_at": contractor.updated_at,
                "notes": contractor.notes
            }
            
            # Add vendor info
            if contractor.vendor:
                contractor_data["vendor_name"] = contractor.vendor.vendor_name
                contractor_data["vendor_code"] = contractor.vendor.vendor_code
            
            result_contractors.append(contractor_data)
        
        return {
            "success": True,
            "data": result_contractors
        }
        
    except Exception as e:
        logger.error(f"Error in get_contractors: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/contractors/assignments", response_model=dict)
async def create_contract_assignment(
    assignment: ContractAssignmentCreate,
    db: Session = Depends(get_db)
):
    """
    Create contract assignment
    
    Args:
        assignment: Assignment creation data
        db: Database session
        
    Returns:
        Created assignment details
    """
    try:
        result = await vendor_contractor_service.create_contract_assignment(
            assignment.dict(), db, created_by=1
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "message": "Assignment created successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create assignment")
            )
    except Exception as e:
        logger.error(f"Error in create_contract_assignment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/contractors/assignments", response_model=dict)
async def get_contract_assignments(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    contractor_id: Optional[int] = Query(None, description="Filter by contractor ID"),
    contract_id: Optional[int] = Query(None, description="Filter by contract ID"),
    status: Optional[str] = Query(None, description="Filter by assignment status"),
    db: Session = Depends(get_db)
):
    """
    Get contract assignments
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        contractor_id: Filter by contractor ID
        contract_id: Filter by contract ID
        status: Filter by assignment status
        db: Database session
        
    Returns:
        List of contract assignments
    """
    try:
        from ..models.vendor_contractor import ContractAssignment, Contractor, VendorContract, Vendor
        from ..models.personnel import Personnel
        from ..models.department import Department
        
        query = db.query(ContractAssignment)
        
        if contractor_id:
            query = query.filter(ContractAssignment.contractor_id == contractor_id)
        
        if contract_id:
            query = query.filter(ContractAssignment.contract_id == contract_id)
        
        if status:
            query = query.filter(ContractAssignment.status == status)
        
        assignments = query.order_by(desc(ContractAssignment.created_at)).offset(skip).limit(limit).all()
        
        result_assignments = []
        for assignment in assignments:
            assignment_data = {
                "id": assignment.id,
                "contract_id": assignment.contract_id,
                "contractor_id": assignment.contractor_id,
                "personnel_id": assignment.personnel_id,
                "project_name": assignment.project_name,
                "project_code": assignment.project_code,
                "role": assignment.role,
                "department_id": assignment.department_id,
                "start_date": assignment.start_date,
                "end_date": assignment.end_date,
                "actual_end_date": assignment.actual_end_date,
                "hourly_rate": assignment.hourly_rate,
                "daily_rate": assignment.daily_rate,
                "overtime_rate": assignment.overtime_rate,
                "currency": assignment.currency,
                "status": assignment.status,
                "performance_rating": assignment.performance_rating,
                "completion_status": assignment.completion_status,
                "assigned_by": assignment.assigned_by,
                "supervisor_id": assignment.supervisor_id,
                "approved_by": assignment.approved_by,
                "approved_at": assignment.approved_at,
                "created_by": assignment.created_by,
                "created_at": assignment.created_at,
                "updated_by": assignment.updated_by,
                "updated_at": assignment.updated_at,
                "notes": assignment.notes
            }
            
            # Add related info
            if assignment.contract:
                assignment_data["contract_name"] = assignment.contract.contract_name
                assignment_data["contract_number"] = assignment.contract.contract_number
            
            if assignment.contractor:
                assignment_data["contractor_name"] = f"{assignment.contractor.first_name} {assignment.contractor.last_name}"
            
            if assignment.personnel:
                assignment_data["personnel_name"] = assignment.personnel.full_name
            
            if assignment.department:
                assignment_data["department_name"] = assignment.department.name
            
            result_assignments.append(assignment_data)
        
        return {
            "success": True,
            "data": result_assignments
        }
        
    except Exception as e:
        logger.error(f"Error in get_contract_assignments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/vendors/compliance", response_model=dict)
async def create_vendor_compliance(
    compliance: VendorComplianceCreate,
    db: Session = Depends(get_db)
):
    """
    Create vendor compliance record
    
    Args:
        compliance: Compliance creation data
        db: Database session
        
    Returns:
        Created compliance record details
    """
    try:
        result = await vendor_contractor_service.create_vendor_compliance(
            compliance.dict(), db, created_by=1
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "message": "Compliance record created successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create compliance record")
            )
    except Exception as e:
        logger.error(f"Error in create_vendor_compliance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/vendors/bulk-action", response_model=dict)
async def bulk_vendor_action(
    action: BulkVendorAction,
    db: Session = Depends(get_db)
):
    """
    Perform bulk action on multiple vendors
    
    Args:
        action: Bulk action request
        db: Database session
        
    Returns:
        Bulk action results
    """
    try:
        result = await vendor_contractor_service.bulk_vendor_action(
            action.vendor_ids, action.action, action.reason, action.notes, db
        )
        
        return {
            "success": True,
            "total_vendors": result["total_vendors"],
            "successful_actions": result["successful_actions"],
            "failed_actions": result["failed_actions"],
            "action_results": result["action_results"],
            "errors": result["errors"]
        }
        
    except Exception as e:
        logger.error(f"Error in bulk_vendor_action: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/statistics", response_model=dict)
async def get_vendor_statistics(
    db: Session = Depends(get_db)
):
    """
    Get vendor management statistics
    
    Args:
        db: Database session
        
    Returns:
        Vendor statistics
    """
    try:
        result = await vendor_contractor_service.get_vendor_statistics(db)
        
        if result["success"]:
            return {
                "success": True,
                "data": result["data"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get statistics")
            )
    except Exception as e:
        logger.error(f"Error in get_vendor_statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/alerts/contract-expiry", response_model=dict)
async def get_contract_expiry_alerts(
    db: Session = Depends(get_db)
):
    """
    Get contract expiry alerts
    
    Args:
        db: Database session
        
    Returns:
        Contract expiry alerts
    """
    try:
        alerts = await vendor_contractor_service.check_contract_expiry_alerts(db)
        
        return {
            "success": True,
            "data": alerts
        }
        
    except Exception as e:
        logger.error(f"Error in get_contract_expiry_alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/alerts/compliance-expiry", response_model=dict)
async def get_compliance_expiry_alerts(
    db: Session = Depends(get_db)
):
    """
    Get compliance expiry alerts
    
    Args:
        db: Database session
        
    Returns:
        Compliance expiry alerts
    """
    try:
        alerts = await vendor_contractor_service.check_compliance_expiry_alerts(db)
        
        return {
            "success": True,
            "data": alerts
        }
        
    except Exception as e:
        logger.error(f"Error in get_compliance_expiry_alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/vendor-types", response_model=dict)
async def get_vendor_types():
    """
    Get available vendor types
    
    Returns:
        List of vendor types
    """
    return {
        "success": True,
        "data": [
            {"value": "SERVICE_PROVIDER", "label": "Service Provider"},
            {"value": "EQUIPMENT_SUPPLIER", "label": "Equipment Supplier"},
            {"value": "CONSULTING_FIRM", "label": "Consulting Firm"},
            {"value": "STAFFING_AGENCY", "label": "Staffing Agency"},
            {"value": "TRAINING_PROVIDER", "label": "Training Provider"},
            {"value": "SOFTWARE_VENDOR", "label": "Software Vendor"},
            {"value": "MAINTENANCE_PROVIDER", "label": "Maintenance Provider"}
        ]
    }


@router.get("/contract-statuses", response_model=dict)
async def get_contract_statuses():
    """
    Get available contract statuses
    
    Returns:
        List of contract statuses
    """
    return {
        "success": True,
        "data": [
            {"value": "DRAFT", "label": "Draft"},
            {"value": "ACTIVE", "label": "Active"},
            {"value": "EXPIRED", "label": "Expired"},
            {"value": "TERMINATED", "label": "Terminated"},
            {"value": "RENEWAL_PENDING", "label": "Renewal Pending"},
            {"value": "SUSPENDED", "label": "Suspended"}
        ]
    }
