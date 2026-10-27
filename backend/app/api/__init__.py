from fastapi import APIRouter
import logging

_logger = logging.getLogger(__name__)

# Core APIs - Essential Only
from .auth import router as auth_router
from .personnel import router as personnel_router
from .devices import router as devices_router
from .pob_status import router as pob_status_router
from .zones import router as zones_router
from .zone_assignments import router as zone_assignments_router
from .departments import router as departments_router
from .roles import router as roles_router

# BioTime APIs - Consolidated to 3 core modules
from .biotime_auth import router as biotime_auth_router
from .biotime_personnel import router as biotime_personnel_router
from .biotime_attendance_api import router as biotime_attendance_router

# ZKTeco APIs - Essential Only
from .zkteco import router as zkteco_router
from .biometric import router as biometric_router

# ADMS Protocol is registered in main.py at root level (no /api/v1 prefix)
# so ZKTeco devices reach /iclock/cdata directly. Import only for reference.
from .adms_protocol import router as adms_protocol_router  # noqa: F401

# Health & System
from .health import router as health_router
from .notifications import router as notifications_router

# Main API router
api_router = APIRouter()

# Core Authentication
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# ── Personnel sub-routers registered FIRST so their literal paths (e.g. /shifts)
#    are matched before the generic /{personnel_id} route in personnel_router ──────
from .shift_management import router as shift_management_router
from .leave_management import router as leave_management_router
from .overtime_management import router as overtime_management_router
from .training_management import router as training_management_router
from .performance_management import router as performance_management_router
from .disciplinary_management import router as disciplinary_management_router
from .promotion_transfer import router as promotion_transfer_router
from .employment_contract import router as employment_contract_router
from .benefits_management import router as benefits_management_router
from .resignation import router as resignation_router
from .onboarding import router as onboarding_router
from .custom_attributes import router as custom_attributes_router
from .vendor_contractor import router as vendor_contractor_router

api_router.include_router(shift_management_router, prefix="/personnel", tags=["Shift Management"])
api_router.include_router(leave_management_router, prefix="/personnel", tags=["Leave Management"])
api_router.include_router(overtime_management_router, prefix="/personnel", tags=["Overtime Management"])
api_router.include_router(training_management_router, prefix="/personnel", tags=["Training Management"])
api_router.include_router(performance_management_router, prefix="/personnel", tags=["Performance Management"])
api_router.include_router(disciplinary_management_router, prefix="/personnel", tags=["Disciplinary Management"])
api_router.include_router(promotion_transfer_router, prefix="/personnel", tags=["Promotion/Transfer"])
api_router.include_router(employment_contract_router, prefix="/personnel", tags=["Employment Contract"])
api_router.include_router(benefits_management_router, prefix="/personnel", tags=["Benefits Management"])
api_router.include_router(resignation_router, prefix="/personnel", tags=["Resignation Management"])
api_router.include_router(onboarding_router, prefix="/personnel", tags=["Onboarding Management"])
api_router.include_router(custom_attributes_router, prefix="/personnel", tags=["Custom Attributes"])
api_router.include_router(vendor_contractor_router, prefix="/personnel", tags=["Vendor/Contractor Management"])

# Generic personnel router LAST — its /{personnel_id} pattern must not shadow the above
api_router.include_router(personnel_router, prefix="/personnel", tags=["Personnel Management"])
api_router.include_router(devices_router, tags=["Device Management"])
api_router.include_router(pob_status_router, prefix="/pob-status", tags=["POB Status"])
# NOTE: attendance, access_control, visitor, mustering, device_management are registered
# directly in main.py with their own full-path prefixes — do NOT double-register here.
api_router.include_router(zones_router, prefix="/zones", tags=["Zone Management"])
api_router.include_router(zone_assignments_router, tags=["Zone Assignments"])
api_router.include_router(departments_router, tags=["Department Management"])
api_router.include_router(roles_router, prefix="/roles", tags=["Role Management"])

# Positions
from .positions import router as positions_router
api_router.include_router(positions_router, tags=["Position Management"])

# Reports - registered in main.py with try/except due to optional dependencies

# BioTime 9.5 APIs - Primary
api_router.include_router(biotime_auth_router, prefix="/biotime/auth", tags=["BioTime Authentication"])
api_router.include_router(biotime_personnel_router, prefix="/biotime", tags=["BioTime Personnel"])
api_router.include_router(biotime_attendance_router, prefix="/biotime", tags=["BioTime Attendance"])

# ZKTeco Device APIs
api_router.include_router(zkteco_router, prefix="/zkteco", tags=["ZKTeco Devices"])
api_router.include_router(biometric_router, tags=["Biometric Management"])

# ZKTeco Direct IP Connection (port 4370 / ZKLib protocol)
from .zkteco_direct import router as zkteco_direct_router
api_router.include_router(zkteco_direct_router, prefix="/zkteco", tags=["ZKTeco Direct IP"])

# Access-Control Controllers (LAN inBio/C3 panels — separate from ADMS readers)
from .access_controllers import router as access_controllers_router
api_router.include_router(access_controllers_router, tags=["Access Control Controllers"])

# Device Auto-Discovery (pending ADMS approvals + on-demand network scan)
from .device_discovery import router as device_discovery_router
api_router.include_router(device_discovery_router, tags=["Device Auto-Discovery"])

# System & Health
api_router.include_router(health_router, prefix="/health", tags=["Health Checks"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])

# Subscription / License management
from .subscription import router as subscription_router
api_router.include_router(subscription_router, prefix="/subscription", tags=["Subscription"])

# Database Backup management (Global Admin only)
from .backup import router as backup_router
api_router.include_router(backup_router, prefix="/backup", tags=["Backup Management"])

# Database administration — overview, occupancy reset/auto-checkout, maintenance,
# retention, integrity (Global Admin only)
from .database_admin import router as database_admin_router
api_router.include_router(database_admin_router, prefix="/database", tags=["Database Admin"])

# HR Integration — SeamlessHR connector
from .hr_integration import router as hr_integration_router
api_router.include_router(hr_integration_router, prefix="/hr-integration", tags=["HR Integration"])

# Business Central Integration
from .bc_integration import router as bc_integration_router
api_router.include_router(bc_integration_router, prefix="/bc-integration", tags=["Business Central Integration"])

# Transport Manifest & Reconciliation
from .transport_manifest import router as transport_manifest_router
api_router.include_router(transport_manifest_router, tags=["Transport Manifest"])
from .journey_management import router as journey_management_router
api_router.include_router(journey_management_router, tags=["Journey Management"])

# Performance Monitoring
from .performance_monitoring import router as performance_router
api_router.include_router(performance_router, tags=["Performance Monitoring"])

# Self-Service Portal
from .self_service import router as self_service_router
api_router.include_router(self_service_router, tags=["Self-Service"])

# Mobile API
from .mobile import router as mobile_router
api_router.include_router(mobile_router, tags=["Mobile"])

# (Personnel sub-routers already registered above before personnel_router)

# ── Direct router ─────────────────────────────────────────────────────────────
# Routers that embed their own full /api/... prefix in the router or in each
# endpoint path. Registered in main.py WITHOUT an extra prefix so paths stay as
# defined. Previously scattered across main.py imports.
direct_router = APIRouter()

# Required direct routers (always present — import errors are fatal)
from .attendance import router as attendance_router
from .settings import router as settings_router
from .email_settings import router as email_settings_router
from .alert_settings import router as alert_settings_router
from .access_control import router as access_control_router
from .visitor import router as visitor_router
from .device_management import router as device_management_router_direct
from .mustering import router as mustering_router_direct

direct_router.include_router(attendance_router, tags=["Attendance"])
direct_router.include_router(settings_router, tags=["Settings"])
direct_router.include_router(email_settings_router, tags=["Email Settings"])
direct_router.include_router(alert_settings_router, tags=["Alert Settings"])
direct_router.include_router(access_control_router, tags=["Access Control"])
direct_router.include_router(visitor_router, tags=["Visitor Management"])
direct_router.include_router(device_management_router_direct, tags=["Device Management Direct"])
direct_router.include_router(mustering_router_direct, tags=["Mustering Direct"])

# Optional direct routers (wrapped — missing deps or incomplete modules)
try:
    from .device_access_control import router as device_ac_router
    direct_router.include_router(device_ac_router, tags=["Device Access Control"])
except Exception as e:
    _logger.warning(f"Device Access Control API disabled: {e}")

try:
    from .device_enrollment import router as device_enrollment_router
    direct_router.include_router(device_enrollment_router, tags=["Device Enrollment"])
except Exception as e:
    _logger.warning(f"Device Enrollment API disabled: {e}")

try:
    from .emergency import router as emergency_api_router
    direct_router.include_router(emergency_api_router, tags=["Emergency Management"])
except Exception as e:
    _logger.warning(f"Emergency API disabled: {e}")

try:
    from .mtd import router as mtd_api_router
    direct_router.include_router(mtd_api_router, tags=["MTD"])
except Exception as e:
    _logger.warning(f"MTD API disabled: {e}")

try:
    from .payroll import router as payroll_api_router
    direct_router.include_router(payroll_api_router, tags=["Payroll"])
except Exception as e:
    _logger.warning(f"Payroll API disabled: {e}")

try:
    from .payroll_statutory import router as payroll_statutory_router
    direct_router.include_router(payroll_statutory_router, tags=["Payroll Statutory (NG)"])
except Exception as e:
    _logger.warning(f"Payroll Statutory API disabled: {e}")

try:
    from .meeting import router as meeting_api_router
    direct_router.include_router(meeting_api_router, tags=["Meeting"])
except Exception as e:
    _logger.warning(f"Meeting API disabled: {e}")

try:
    from .report import router as report_api_router
    direct_router.include_router(report_api_router, prefix="/api/v1", tags=["Reports"])
except Exception as e:
    _logger.warning(f"Reports API disabled: {e}")

try:
    from .biotime_analytics import router as biotime_analytics_router
    direct_router.include_router(biotime_analytics_router, prefix="/api/v1/biotime/analytics", tags=["BioTime Analytics"])
except Exception as e:
    _logger.warning(f"BioTime Analytics API disabled: {e}")

# Device WebSocket — authenticated real-time device status streams
try:
    from .device_websocket import router as device_ws_router
    direct_router.include_router(device_ws_router, tags=["Device WebSocket"])
except Exception as e:
    _logger.warning(f"Device WebSocket disabled: {e}")

# Compliance email — manual trigger + preview
try:
    from .compliance_email_api import router as compliance_email_router
    direct_router.include_router(compliance_email_router, tags=["Compliance Email"])
except Exception as e:
    _logger.warning(f"Compliance Email API disabled: {e}")

# Document management — file upload for certifications, permits, medical records
try:
    from .documents import router as documents_router
    api_router.include_router(documents_router, tags=["Document Management"])
except Exception as e:
    _logger.warning(f"Documents API disabled: {e}")

# MFA/2FA — TOTP setup and verification
try:
    from .mfa import router as mfa_router
    api_router.include_router(mfa_router, tags=["MFA/2FA"])
except Exception as e:
    _logger.warning(f"MFA API disabled: {e}")

# Global search — cross-module entity lookup
try:
    from .search import router as search_router
    api_router.include_router(search_router, tags=["Global Search"])
except Exception as e:
    _logger.warning(f"Global Search API disabled: {e}")

# Session management — view and revoke active user sessions
try:
    from .sessions import router as sessions_router
    direct_router.include_router(sessions_router, tags=["Sessions"])
except Exception as e:
    _logger.warning(f"Sessions API disabled: {e}")

# Audit trail — query base_operationlog
try:
    from .audit import router as audit_router
    direct_router.include_router(audit_router, tags=["Audit Trail"])
except Exception as e:
    _logger.warning(f"Audit API disabled: {e}")

# Reports — PDF/CSV download
try:
    from .reports import router as reports_router
    direct_router.include_router(reports_router, tags=["PDF Reports"])
except Exception as e:
    _logger.warning(f"Reports (PDF) API disabled: {e}")

# NOTE: mustering_emergency_api, qr_codes exist as files but are intentionally
# not registered — they are unfinished modules. Register when complete.

# Export for main app
__all__ = ["api_router", "direct_router"]
