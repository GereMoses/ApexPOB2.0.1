"""
Report Module API Endpoints
BioTime 9.5 compatible with POB extensions
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.dependencies import get_db, get_current_active_user
from ..core.rbac import require_role
from ..models.biotime_models import AuthUser
from ..models.report import ReportTemplate, ReportSchedule, ReportExportLog, ReportUserPreset, ReportFavorite
from ..services.report_service import ReportService
from ..services.export_service import ExportService
from ..services.email_service import ReportEmailService as EmailService
from ..core.permissions import (
    check_report_permission,
    can_access_custom_builder,
    can_delete_template,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["reports"])


# Pydantic Models
class ReportDataRequest(BaseModel):
    report_code: str = Field(..., description="Report code from registry")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filter parameters")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=1000, description="Page size")


class ReportExportRequest(BaseModel):
    report_code: str = Field(..., description="Report code to export")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filter parameters")
    format: str = Field(default="pdf", pattern="^(pdf|xlsx|csv)$", description="Export format")


class ReportTemplateCreate(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=100)
    module: str = Field(..., min_length=1, max_length=50)
    report_code: str = Field(..., min_length=1, max_length=100)
    filters: Dict[str, Any] = Field(default_factory=dict)
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    group_by: Optional[str] = None
    chart_type: str = Field(default="none", pattern="^(none|bar|line|pie|heatmap)$")
    is_public: bool = False
    description: Optional[str] = None


class ReportTemplateUpdate(BaseModel):
    template_name: Optional[str] = Field(None, min_length=1, max_length=100)
    filters: Optional[Dict[str, Any]] = None
    columns: Optional[List[Dict[str, Any]]] = None
    group_by: Optional[str] = None
    chart_type: Optional[str] = Field(None, pattern="^(none|bar|line|pie|heatmap)$")
    is_public: Optional[bool] = None
    description: Optional[str] = None


class ReportScheduleCreate(BaseModel):
    template_id: int = Field(..., gt=0)
    schedule_name: str = Field(..., min_length=1, max_length=100)
    cron: str = Field(..., min_length=5, max_length=50)  # Basic cron validation
    format: str = Field(default="pdf", pattern="^(pdf|xlsx|csv)$")
    recipients: Dict[str, List[int]] = Field(..., description="{users: [], emails: [], roles: []}")


class ReportScheduleUpdate(BaseModel):
    schedule_name: Optional[str] = Field(None, min_length=1, max_length=100)
    cron: Optional[str] = Field(None, min_length=5, max_length=50)
    format: Optional[str] = Field(None, pattern="^(pdf|xlsx|csv)$")
    recipients: Optional[Dict[str, List[int]]] = None
    is_active: Optional[bool] = None


class ReportPresetCreate(BaseModel):
    template_id: Optional[int] = None
    preset_name: str = Field(..., min_length=1, max_length=100)
    preset_type: str = Field(..., pattern="^(filter|column|both)$")
    filters: Optional[Dict[str, Any]] = None
    columns: Optional[List[Dict[str, Any]]] = None
    is_default: bool = False


# ==================== TEMPLATES ====================

@router.get("/templates/", response_model=List[Dict[str, Any]])
async def get_report_templates(
    module: Optional[str] = Query(None, description="Filter by module"),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Get report templates with filtering"""
    query = db.query(ReportTemplate)
    
    # Apply filters
    if module:
        query = query.filter(ReportTemplate.module == module)
    if is_public is not None:
        query = query.filter(ReportTemplate.is_public == is_public)
    
    # Show user's own templates and public templates
    query = query.filter(
        (ReportTemplate.created_by == current_user.id) | 
        (ReportTemplate.is_public == True)
    )
    
    templates = query.all()
    
    result = []
    for template in templates:
        result.append({
            "id": template.id,
            "template_name": template.template_name,
            "module": template.module,
            "report_code": template.report_code,
            "description": template.description,
            "is_system": template.is_system,
            "is_public": template.is_public,
            "created_by": template.created_by,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat(),
            "group_by": template.group_by,
            "chart_type": template.chart_type,
            "is_favorite": bool(db.query(ReportFavorite).filter(
                ReportFavorite.user_id == current_user.id,
                ReportFavorite.template_id == template.id
            ).first())
        })
    
    return result


@router.post("/templates", response_model=Dict[str, Any])
async def create_report_template(
    template: ReportTemplateCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_role("HR"))
):
    """Create new report template"""
    # Check permission for module
    if not check_report_permission(current_user, template.module, "create", db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Check if report_code already exists for this user
    existing = db.query(ReportTemplate).filter(
        ReportTemplate.report_code == template.report_code,
        ReportTemplate.created_by == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Report code already exists")
    
    # Create template
    db_template = ReportTemplate(
        template_name=template.template_name,
        module=template.module,
        report_code=template.report_code,
        filters=template.filters,
        columns=template.columns,
        group_by=template.group_by,
        chart_type=template.chart_type,
        is_public=template.is_public,
        description=template.description,
        created_by=current_user.id
    )
    
    try:
        db.add(db_template)
        db.commit()
        db.refresh(db_template)
    except Exception as e:
        logger.error("create_template user=%s name=%s error=%s", current_user.id, template.template_name, e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create template")

    logger.info("create_template user=%s id=%s name=%s module=%s",
                current_user.id, db_template.id, db_template.template_name, db_template.module)
    return {
        "id": db_template.id,
        "template_name": db_template.template_name,
        "module": db_template.module,
        "report_code": db_template.report_code,
        "message": "Template created successfully"
    }


@router.get("/templates/{template_id}", response_model=Dict[str, Any])
async def get_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Get specific report template"""
    template = db.query(ReportTemplate).filter(
        ReportTemplate.id == template_id,
        (ReportTemplate.created_by == current_user.id) | 
        (ReportTemplate.is_public == True)
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "id": template.id,
        "template_name": template.template_name,
        "module": template.module,
        "report_code": template.report_code,
        "description": template.description,
        "filters": template.filters,
        "columns": template.columns,
        "group_by": template.group_by,
        "chart_type": template.chart_type,
        "is_public": template.is_public,
        "is_system": template.is_system,
        "created_by": template.created_by,
        "created_at": template.created_at.isoformat(),
        "updated_at": template.updated_at.isoformat()
    }


@router.put("/templates/{template_id}", response_model=Dict[str, Any])
async def update_report_template(
    template_id: int,
    template: ReportTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Update report template"""
    from ..core.permissions import can_modify_template
    db_template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()

    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    if db_template.is_system:
        raise HTTPException(status_code=403, detail="Cannot edit system templates")

    if not can_modify_template(current_user, db_template, db):
        raise HTTPException(status_code=403, detail="Cannot edit templates you do not own")
    
    # Update fields
    if template.template_name is not None:
        db_template.template_name = template.template_name
    if template.filters is not None:
        db_template.filters = template.filters
    if template.columns is not None:
        db_template.columns = template.columns
    if template.group_by is not None:
        db_template.group_by = template.group_by
    if template.chart_type is not None:
        db_template.chart_type = template.chart_type
    if template.is_public is not None:
        db_template.is_public = template.is_public
    if template.description is not None:
        db_template.description = template.description
    
    db_template.updated_at = datetime.utcnow()
    try:
        db.commit()
    except Exception as e:
        logger.error("update_template user=%s id=%s error=%s", current_user.id, template_id, e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update template")

    logger.info("update_template user=%s id=%s", current_user.id, template_id)
    return {"message": "Template updated successfully"}


@router.delete("/templates/{template_id}", response_model=Dict[str, Any])
async def delete_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Delete report template"""
    db_template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()

    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    if db_template.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system templates")

    if not can_delete_template(current_user, db_template, db):
        raise HTTPException(status_code=403, detail="Cannot delete templates you do not own")
    
    name = db_template.template_name
    try:
        db.delete(db_template)
        db.commit()
    except Exception as e:
        logger.error("delete_template user=%s id=%s error=%s", current_user.id, template_id, e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete template")

    logger.info("delete_template user=%s id=%s name=%s", current_user.id, template_id, name)
    return {"message": "Template deleted successfully"}


@router.post("/templates/{template_id}/clone", response_model=Dict[str, Any])
async def clone_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Clone report template to user's templates"""
    original = db.query(ReportTemplate).filter(
        ReportTemplate.id == template_id,
        (ReportTemplate.created_by == current_user.id) | 
        (ReportTemplate.is_public == True)
    ).first()
    
    if not original:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create clone
    clone = ReportTemplate(
        template_name=f"{original.template_name} (Copy)",
        module=original.module,
        report_code=original.report_code,
        filters=original.filters,
        columns=original.columns,
        group_by=original.group_by,
        chart_type=original.chart_type,
        is_public=False,  # Clones are private by default
        description=original.description,
        created_by=current_user.id
    )
    
    try:
        db.add(clone)
        db.commit()
        db.refresh(clone)
    except Exception as e:
        logger.error("clone_template user=%s source_id=%s error=%s", current_user.id, template_id, e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to clone template")

    logger.info("clone_template user=%s source_id=%s new_id=%s", current_user.id, template_id, clone.id)
    return {
        "id": clone.id,
        "template_name": clone.template_name,
        "message": "Template cloned successfully"
    }


# ==================== DATA ENDPOINTS ====================

# Report codes use short prefixes (att., pob., zone., muster., travel. …) but the
# permissions are named report.<module>.<action> with the long module names. Checking
# report.att.view etc. — permissions that do not exist — refused every non-superuser.
_REPORT_PERMISSION_MODULE = {
    'att': 'attendance', 'personnel': 'personnel', 'pob': 'personnel', 'travel': 'personnel',
    'muster': 'mustering', 'emergency': 'emergency', 'visitor': 'visitor',
    'ac': 'access_control', 'zone': 'access_control', 'device': 'access_control',
    'pay': 'payroll', 'mtd': 'mtd', 'meeting': 'personnel', 'system': 'access_control',
}


def report_permission_module(report_code: str) -> str:
    prefix = (report_code or '').split('.')[0]
    return _REPORT_PERMISSION_MODULE.get(prefix, prefix)


@router.post("/data", response_model=Dict[str, Any])
async def get_report_data(
    request: ReportDataRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Get report data - generic endpoint"""
    # Extract module from report code
    module = report_permission_module(request.report_code)
    
    # Check permission
    if not check_report_permission(current_user, module, "view", db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    report_service = ReportService(db)
    try:
        result = report_service.get_report_data(
            request.report_code,
            request.filters,
            request.page,
            request.page_size
        )
        logger.info("report_data user=%s code=%s page=%s total=%s",
                    current_user.id, request.report_code, request.page, result.get('total', '?'))
        return result
    except ValueError as e:
        logger.warning("report_data user=%s code=%s bad_request=%s", current_user.id, request.report_code, e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("report_data user=%s code=%s error=%s", current_user.id, request.report_code, e)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/dashboard/{widget_code}", response_model=Dict[str, Any])
async def get_dashboard_widget(
    widget_code: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Get dashboard widget data"""
    # Extract module from widget code
    module = widget_code.split('.')[0]
    
    # Check permission
    if not check_report_permission(current_user, module, "view", db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Get widget data (simplified report with default filters)
    report_service = ReportService(db)
    try:
        result = report_service.get_report_data(widget_code, {}, 1, 10)
        return {
            "widget_code": widget_code,
            "data": result.get("summary", {}),
            "chart_data": result.get("chart_data", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating widget: {str(e)}")


# ==================== EXPORT ENDPOINTS ====================

@router.post("/export", response_model=Dict[str, Any])
async def export_report(
    request: ReportExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Export report - async processing"""
    # Extract module from report code
    module = report_permission_module(request.report_code)
    
    # Check export permission
    if not check_report_permission(current_user, module, "export", db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Create export log
    export_log = ReportExportLog(
        template_id=None,  # Will be set if template exists
        user_id=current_user.id,
        format=request.format,
        filters=request.filters,
        status="pending"
    )
    
    db.add(export_log)
    db.commit()
    db.refresh(export_log)
    
    # Queue export task
    export_service = ExportService(db)
    task_id = export_service.queue_export(
        export_log.id,
        request.report_code,
        request.filters,
        request.format
    )
    
    export_log.task_id = task_id
    db.commit()

    logger.info("export_queued user=%s code=%s format=%s task=%s",
                current_user.id, request.report_code, request.format, task_id)
    return {
        "task_id": task_id,
        "export_id": export_log.id,
        "message": "Export queued successfully"
    }


@router.post("/export/file")
async def export_report_file(
    request: ReportExportRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Build the export in this request and return the file.

    The queued /export path relies on a Celery app ("report_exports") that has no
    broker and no worker, so a queued export never completed (rpt_export_log was
    empty). Reports here are small enough to build inline."""
    from fastapi.responses import FileResponse
    import os as _os
    module = report_permission_module(request.report_code)
    if not check_report_permission(current_user, module, "export", db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    log = ReportExportLog(template_id=None, user_id=current_user.id, format=request.format,
                          filters=request.filters, status="pending")
    db.add(log); db.commit(); db.refresh(log)
    try:
        path = ExportService(db).generate_export(log.id, request.report_code, request.filters, request.format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("export_file user=%s code=%s error=%s", current_user.id, request.report_code, e)
        raise HTTPException(status_code=500, detail="Could not build the export")
    media = {"pdf": "application/pdf", "csv": "text/csv",
             "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}[request.format]
    name = f"{request.report_code.replace('.', '_')}_{log.id}.{request.format}"
    logger.info("export_file user=%s code=%s format=%s", current_user.id, request.report_code, request.format)
    return FileResponse(path, media_type=media, filename=_os.path.basename(name))


@router.get("/export/{task_id}/status/", response_model=Dict[str, Any])
async def get_export_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Get export task status"""
    export_log = db.query(ReportExportLog).filter(
        ReportExportLog.task_id == task_id,
        ReportExportLog.user_id == current_user.id
    ).first()
    
    if not export_log:
        raise HTTPException(status_code=404, detail="Export not found")
    
    return {
        "task_id": task_id,
        "status": export_log.status,
        "progress": export_log.row_count,
        "file_path": export_log.file_path,
        "error_message": export_log.error_message,
        "created_at": export_log.export_time.isoformat()
    }


@router.get("/export/{task_id}/download/")
async def download_export(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Download exported file"""
    export_log = db.query(ReportExportLog).filter(
        ReportExportLog.task_id == task_id,
        ReportExportLog.user_id == current_user.id,
        ReportExportLog.status == "completed"
    ).first()
    
    if not export_log:
        raise HTTPException(status_code=404, detail="Export not found or not completed")
    
    # Return file (implementation depends on file storage)
    from fastapi.responses import FileResponse
    return FileResponse(
        path=export_log.file_path,
        filename=export_log.file_path.split("/")[-1],
        media_type='application/octet-stream'
    )


# ==================== SCHEDULE ENDPOINTS ====================

@router.get("/schedules/", response_model=List[Dict[str, Any]])
async def get_report_schedules(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Get report schedules"""
    schedules = db.query(ReportSchedule).filter(
        ReportSchedule.created_by == current_user.id
    ).all()
    
    result = []
    for schedule in schedules:
        result.append({
            "id": schedule.id,
            "template_id": schedule.template_id,
            "schedule_name": schedule.schedule_name,
            "cron": schedule.cron,
            "format": schedule.format,
            "recipients": schedule.recipients,
            "is_active": schedule.is_active,
            "last_run": schedule.last_run.isoformat() if schedule.last_run else None,
            "next_run": schedule.next_run.isoformat() if schedule.next_run else None,
            "created_at": schedule.created_at.isoformat()
        })
    
    return result


@router.post("/schedules", response_model=Dict[str, Any])
async def create_report_schedule(
    schedule: ReportScheduleCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_role("HR"))
):
    """Create report schedule"""
    # Validate template exists and user has access
    template = db.query(ReportTemplate).filter(
        ReportTemplate.id == schedule.template_id,
        (ReportTemplate.created_by == current_user.id) | 
        (ReportTemplate.is_public == True)
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Check permission for module
    if not check_report_permission(current_user, template.module, "schedule", db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Create schedule
    db_schedule = ReportSchedule(
        template_id=schedule.template_id,
        schedule_name=schedule.schedule_name,
        cron=schedule.cron,
        format=schedule.format,
        recipients=schedule.recipients,
        created_by=current_user.id
    )
    
    try:
        db.add(db_schedule)
        db.commit()
        db.refresh(db_schedule)
    except Exception as e:
        logger.error("create_schedule user=%s name=%s error=%s", current_user.id, schedule.schedule_name, e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create schedule")

    logger.info("create_schedule user=%s id=%s name=%s cron=%s",
                current_user.id, db_schedule.id, db_schedule.schedule_name, db_schedule.cron)
    return {
        "id": db_schedule.id,
        "schedule_name": db_schedule.schedule_name,
        "message": "Schedule created successfully"
    }


@router.put("/schedules/{schedule_id}", response_model=Dict[str, Any])
async def update_report_schedule(
    schedule_id: int,
    schedule: ReportScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Update report schedule"""
    db_schedule = db.query(ReportSchedule).filter(
        ReportSchedule.id == schedule_id,
        ReportSchedule.created_by == current_user.id
    ).first()
    
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Update fields
    if schedule.schedule_name is not None:
        db_schedule.schedule_name = schedule.schedule_name
    if schedule.cron is not None:
        db_schedule.cron = schedule.cron
    if schedule.format is not None:
        db_schedule.format = schedule.format
    if schedule.recipients is not None:
        db_schedule.recipients = schedule.recipients
    if schedule.is_active is not None:
        db_schedule.is_active = schedule.is_active
    
    db_schedule.updated_at = datetime.utcnow()
    try:
        db.commit()
    except Exception as e:
        logger.error("update_schedule user=%s id=%s error=%s", current_user.id, schedule_id, e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update schedule")

    logger.info("update_schedule user=%s id=%s", current_user.id, schedule_id)
    return {"message": "Schedule updated successfully"}


@router.delete("/schedules/{schedule_id}", response_model=Dict[str, Any])
async def delete_report_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Delete report schedule"""
    db_schedule = db.query(ReportSchedule).filter(
        ReportSchedule.id == schedule_id,
        ReportSchedule.created_by == current_user.id
    ).first()
    
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    name = db_schedule.schedule_name
    try:
        db.delete(db_schedule)
        db.commit()
    except Exception as e:
        logger.error("delete_schedule user=%s id=%s error=%s", current_user.id, schedule_id, e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete schedule")

    logger.info("delete_schedule user=%s id=%s name=%s", current_user.id, schedule_id, name)
    return {"message": "Schedule deleted successfully"}


@router.post("/schedules/{schedule_id}/run-now", response_model=Dict[str, Any])
async def run_schedule_now(
    schedule_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Trigger schedule immediately"""
    db_schedule = db.query(ReportSchedule).filter(
        ReportSchedule.id == schedule_id,
        ReportSchedule.created_by == current_user.id
    ).first()
    
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Queue immediate execution
    export_service = ExportService(db)
    task_id = export_service.queue_scheduled_export(db_schedule.id)
    
    return {
        "task_id": task_id,
        "message": "Schedule triggered successfully"
    }


# ==================== USER PRESETS ====================

@router.get("/presets/", response_model=List[Dict[str, Any]])
async def get_user_presets(
    template_id: Optional[int] = Query(None),
    preset_type: Optional[str] = Query(None, pattern="^(filter|column|both)$"),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Get user presets"""
    query = db.query(ReportUserPreset).filter(
        ReportUserPreset.user_id == current_user.id
    )
    
    if template_id:
        query = query.filter(ReportUserPreset.template_id == template_id)
    if preset_type:
        query = query.filter(ReportUserPreset.preset_type == preset_type)
    
    presets = query.all()
    
    result = []
    for preset in presets:
        result.append({
            "id": preset.id,
            "template_id": preset.template_id,
            "preset_name": preset.preset_name,
            "preset_type": preset.preset_type,
            "filters": preset.filters,
            "columns": preset.columns,
            "is_default": preset.is_default,
            "created_at": preset.created_at.isoformat()
        })
    
    return result


@router.post("/presets", response_model=Dict[str, Any])
async def create_user_preset(
    preset: ReportPresetCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Create user preset"""
    # Validate template if provided
    if preset.template_id:
        template = db.query(ReportTemplate).filter(
            ReportTemplate.id == preset.template_id,
            (ReportTemplate.created_by == current_user.id) | 
            (ReportTemplate.is_public == True)
        ).first()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
    
    # Create preset
    db_preset = ReportUserPreset(
        user_id=current_user.id,
        template_id=preset.template_id,
        preset_name=preset.preset_name,
        preset_type=preset.preset_type,
        filters=preset.filters,
        columns=preset.columns,
        is_default=preset.is_default
    )
    
    db.add(db_preset)
    db.commit()
    db.refresh(db_preset)
    
    return {
        "id": db_preset.id,
        "preset_name": db_preset.preset_name,
        "message": "Preset created successfully"
    }


# ==================== FAVORITES ====================

@router.post("/favorites/{template_id}", response_model=Dict[str, Any])
async def add_favorite(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Add template to favorites"""
    # Validate template
    template = db.query(ReportTemplate).filter(
        ReportTemplate.id == template_id,
        (ReportTemplate.created_by == current_user.id) | 
        (ReportTemplate.is_public == True)
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Check if already favorited
    existing = db.query(ReportFavorite).filter(
        ReportFavorite.user_id == current_user.id,
        ReportFavorite.template_id == template_id
    ).first()
    
    if existing:
        return {"message": "Already in favorites"}
    
    # Add favorite
    favorite = ReportFavorite(
        user_id=current_user.id,
        template_id=template_id
    )
    
    db.add(favorite)
    db.commit()
    
    return {"message": "Added to favorites"}


@router.delete("/favorites/{template_id}", response_model=Dict[str, Any])
async def remove_favorite(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Remove template from favorites"""
    favorite = db.query(ReportFavorite).filter(
        ReportFavorite.user_id == current_user.id,
        ReportFavorite.template_id == template_id
    ).first()
    
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    db.delete(favorite)
    db.commit()
    
    return {"message": "Removed from favorites"}


@router.get("/favorites/", response_model=List[Dict[str, Any]])
async def get_favorites(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_active_user)
):
    """Get user favorite templates"""
    favorites = db.query(ReportTemplate).join(ReportFavorite).filter(
        ReportFavorite.user_id == current_user.id
    ).all()
    
    result = []
    for template in favorites:
        result.append({
            "id": template.id,
            "template_name": template.template_name,
            "module": template.module,
            "report_code": template.report_code,
            "description": template.description,
            "is_system": template.is_system,
            "created_at": template.created_at.isoformat()
        })
    
    return result


# ==================== CUSTOM BUILDER (POB EXTENSION) ====================

@router.get("/builder/meta/", response_model=Dict[str, Any])
async def get_builder_metadata(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_role("staff"))
):
    """Get metadata for custom report builder"""
    # This would return available modules, tables, and fields
    # Simplified version for now
    return {
        "modules": [
            {"code": "personnel", "name": "Personnel", "tables": ["personnel", "department"]},
            {"code": "attendance", "name": "Attendance", "tables": ["attendance_report", "overtime_record"]},
            {"code": "mustering", "name": "Mustering", "tables": ["mustering_event", "mustering_log"]},
            {"code": "emergency", "name": "Emergency", "tables": ["emergency_event"]},
            {"code": "payroll", "name": "Payroll", "tables": ["pay_salary", "pay_salary_item"]},
            {"code": "visitor", "name": "Visitor", "tables": ["visitor_visit_log"]},
            {"code": "meeting", "name": "Meeting", "tables": ["meeting_booking"]},
            {"code": "mtd", "name": "MTD", "tables": ["mtd_certification"]},
        ],
        "field_types": ["text", "number", "date", "datetime", "boolean", "currency", "percentage"],
        "aggregate_functions": ["count", "sum", "avg", "min", "max"],
        "chart_types": ["none", "bar", "line", "pie", "heatmap"]
    }


@router.post("/builder/preview", response_model=Dict[str, Any])
async def preview_custom_report(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_role("staff"))
):
    """Preview custom report data"""
    try:
        from ..services.custom_report_builder_service import CustomReportBuilderService
        builder_service = CustomReportBuilderService(db)
        
        result = builder_service.preview_report(request)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Preview failed'))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing custom report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== COMPREHENSIVE CUSTOM BUILDER ====================

@router.get("/custom-builder/tables")
async def get_custom_builder_tables(db: Session = Depends(get_db)):
    """Get available tables and relationships for custom report builder"""
    try:
        from ..services.custom_report_builder_service import CustomReportBuilderService
        builder_service = CustomReportBuilderService(db)
        
        tables = builder_service.get_available_tables()
        relationships = builder_service.get_table_relationships()
        
        return {
            "success": True,
            "tables": tables,
            "relationships": relationships
        }
    except Exception as e:
        logger.error(f"Error getting custom builder tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/custom-builder/validate")
async def validate_custom_report(report_config: dict, db: Session = Depends(get_db)):
    """Validate custom report configuration"""
    try:
        from ..services.custom_report_builder_service import CustomReportBuilderService
        builder_service = CustomReportBuilderService(db)
        
        validation = builder_service.validate_report_config(report_config)
        
        return {
            "success": True,
            "validation": validation
        }
        
    except Exception as e:
        logger.error(f"Error validating custom report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/custom-builder/save")
async def save_custom_report(
    report_data: dict,
    current_user: AuthUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Save custom report configuration"""
    try:
        from ..services.custom_report_builder_service import CustomReportBuilderService
        builder_service = CustomReportBuilderService(db)
        
        # Check if user has permission to create custom reports
        if not can_access_custom_builder(current_user, db):
            raise HTTPException(status_code=403, detail="Insufficient permissions to create custom reports")
        
        result = builder_service.save_custom_report(
            report_config=report_data['config'],
            user_id=current_user.id,
            name=report_data['name'],
            description=report_data.get('description')
        )
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Save failed'))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving custom report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/custom-builder/saved")
async def get_saved_custom_reports(
    current_user: AuthUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's saved custom reports"""
    try:
        from ..services.custom_report_builder_service import CustomReportBuilderService
        builder_service = CustomReportBuilderService(db)
        
        # Get user's custom reports
        custom_reports = db.query(ReportTemplate).filter(
            ReportTemplate.module == 'custom',
            ReportTemplate.created_by == current_user.id
        ).all()
        
        # Get public custom reports
        public_reports = db.query(ReportTemplate).filter(
            ReportTemplate.module == 'custom',
            ReportTemplate.is_public == True
        ).all()
        
        reports = []

        # Add user's reports
        for report in custom_reports:
            reports.append({
                'id': report.id,
                'name': report.template_name,
                'description': report.description,
                'created_at': report.created_at.isoformat() if report.created_at else None,
                'is_owner': True
            })

        # Add public reports (excluding user's own)
        for report in public_reports:
            if report.created_by != current_user.id:
                reports.append({
                    'id': report.id,
                    'name': report.template_name,
                    'description': report.description,
                    'created_at': report.created_at.isoformat() if report.created_at else None,
                    'is_owner': False
                })
        
        return {
            "success": True,
            "reports": reports
        }
        
    except Exception as e:
        logger.error(f"Error getting saved custom reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/custom-builder/load/{template_id}")
async def load_custom_report(
    template_id: int,
    current_user: AuthUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Load saved custom report configuration"""
    try:
        from ..services.custom_report_builder_service import CustomReportBuilderService
        builder_service = CustomReportBuilderService(db)
        
        result = builder_service.load_custom_report(template_id, current_user.id)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=404, detail=result.get('error', 'Report not found'))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading custom report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/custom-builder/{template_id}")
async def delete_custom_report(
    template_id: int,
    current_user: AuthUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete saved custom report"""
    try:
        # Get template
        template = db.query(ReportTemplate).filter(
            ReportTemplate.id == template_id,
            ReportTemplate.module == 'custom'
        ).first()
        
        if not template:
            raise HTTPException(status_code=404, detail="Custom report not found")
        
        # Check permissions
        if not can_delete_template(current_user, template, db):
            raise HTTPException(status_code=403, detail="Insufficient permissions to delete this report")
        
        db.delete(template)
        db.commit()
        
        return {
            "success": True,
            "message": "Custom report deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting custom report: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/custom-builder/{template_id}/execute")
async def execute_custom_report(
    template_id: int,
    export_request: Optional[dict] = None,
    current_user: AuthUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Execute saved custom report with optional export"""
    try:
        from ..services.custom_report_builder_service import CustomReportBuilderService
        builder_service = CustomReportBuilderService(db)
        
        # Load report configuration
        load_result = builder_service.load_custom_report(template_id, current_user.id)
        
        if not load_result['success']:
            raise HTTPException(status_code=404, detail=load_result.get('error', 'Report not found'))
        
        config = load_result['template']['config']
        
        # Execute query
        query, parameters = builder_service.generate_sql_query(config)
        data = builder_service.execute_custom_query(query, parameters)
        
        # Handle export if requested
        if export_request:
            from ..services.export_service import ExportService
            export_service = ExportService(db)
            
            export_format = export_request.get('format', 'xlsx')
            filename = f"custom_report_{template_id}"
            
            export_result = export_service.generate_export(
                data=data,
                format=export_format,
                filename=filename,
                report_name=load_result['template']['name']
            )
            
            if export_result['success']:
                return {
                    "success": True,
                    "data": data,
                    "export": export_result
                }
            else:
                return {
                    "success": False,
                    "error": export_result.get('error', 'Export failed')
                }
        
        return {
            "success": True,
            "data": data,
            "row_count": len(data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing custom report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
