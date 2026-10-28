"""
Enhanced Error Handling and Recovery Mechanisms
Comprehensive error handling with logging, recovery, and user-friendly responses
"""

import logging
import traceback
from typing import Dict, Any, Optional, Union
from datetime import datetime
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class POBException(Exception):
    """Base exception class for Apex POB"""
    def __init__(
        self,
        message: str,
        error_code: str = None,
        details: Dict[str, Any] = None,
        severity: str = "error"
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.severity = severity
        self.timestamp = datetime.utcnow()
        super().__init__(message)

class DatabaseException(POBException):
    """Database-related exceptions"""
    pass

class ValidationException(POBException):
    """Data validation exceptions"""
    pass

class AuthenticationException(POBException):
    """Authentication-related exceptions"""
    pass

class AuthorizationException(POBException):
    """Authorization-related exceptions"""
    pass

class ZKTecoDeviceException(POBException):
    """ZKTeco device communication exceptions"""
    pass

class BusinessLogicException(POBException):
    """Business logic validation exceptions"""
    pass

class ExternalServiceException(POBException):
    """External service communication exceptions"""
    pass

class ErrorHandler:
    """Centralized error handling and recovery"""
    
    @staticmethod
    def handle_database_error(error: Exception, operation: str = None) -> Dict[str, Any]:
        """Handle database errors with appropriate recovery suggestions"""
        error_type = type(error).__name__
        error_message = str(error)
        
        # Log the error with context
        logger.error(f"Database error in {operation}: {error_type}: {error_message}")
        logger.debug(f"Database error traceback: {traceback.format_exc()}")
        
        # Determine error category and recovery actions
        if isinstance(error, IntegrityError):
            if "unique" in error_message.lower():
                return {
                    "error": "DUPLICATE_RECORD",
                    "message": "Record already exists with these values",
                    "details": {
                        "operation": operation,
                        "suggestion": "Check if this record already exists or use different values"
                    },
                    "recovery_action": "verify_unique_fields",
                    "severity": "warning"
                }
            elif "foreign key" in error_message.lower():
                # Two different situations share this error: deleting something other
                # records still point at ("still referenced"), or saving a link to a
                # record that doesn't exist. Say which.
                in_use = "still referenced" in error_message.lower() or "update or delete" in error_message.lower()
                return {
                    "error": "IN_USE" if in_use else "FOREIGN_KEY_VIOLATION",
                    "message": ("This record is still used by other records, so it can't be deleted"
                                if in_use else "Referenced record does not exist"),
                    "details": {
                        "operation": operation,
                        "suggestion": ("Remove or reassign the records that use it first, or deactivate it instead"
                                       if in_use else "Ensure referenced records exist before creating this record")
                    },
                    "recovery_action": "verify_references",
                    "severity": "error"
                }
            elif "not null" in error_message.lower():
                return {
                    "error": "NULL_VIOLATION",
                    "message": "Required field cannot be empty",
                    "details": {
                        "operation": operation,
                        "suggestion": "Provide all required fields"
                    },
                    "recovery_action": "fill_required_fields",
                    "severity": "warning"
                }
        
        elif isinstance(error, OperationalError):
            if "connection" in error_message.lower():
                return {
                    "error": "CONNECTION_LOST",
                    "message": "Database connection lost",
                    "details": {
                        "operation": operation,
                        "suggestion": "Database connection issue, please try again"
                    },
                    "recovery_action": "retry_operation",
                    "severity": "error"
                }
            elif "timeout" in error_message.lower():
                return {
                    "error": "TIMEOUT",
                    "message": "Database operation timed out",
                    "details": {
                        "operation": operation,
                        "suggestion": "Operation took too long, try with smaller data sets"
                    },
                    "recovery_action": "reduce_data_size",
                    "severity": "warning"
                }
        
        # Generic database error
        return {
            "error": "DATABASE_ERROR",
            "message": "Database operation failed",
            "details": {
                "operation": operation,
                "error_type": error_type,
                "suggestion": "Please try again or contact support"
            },
            "recovery_action": "retry_or_contact_support",
            "severity": "error"
        }
    
    @staticmethod
    def handle_validation_error(error: ValidationError, operation: str = None) -> Dict[str, Any]:
        """Handle Pydantic validation errors"""
        logger.error(f"Validation error in {operation}: {error}")
        
        errors = []
        for err in error.errors():
            loc = err.get("loc", ())
            field = ".".join(str(l) for l in loc) if loc else "unknown"
            errors.append({
                "field": field,
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
                "input": err.get("input")
            })
        
        return {
            "error": "VALIDATION_ERROR",
            "message": "Invalid data provided",
            "details": {
                "operation": operation,
                "validation_errors": errors,
                "suggestion": "Check all required fields and data formats"
            },
            "recovery_action": "fix_validation_errors",
            "severity": "warning"
        }
    
    @staticmethod
    def handle_authentication_error(error: Exception, operation: str = None) -> Dict[str, Any]:
        """Handle authentication errors"""
        logger.error(f"Authentication error in {operation}: {error}")
        
        return {
            "error": "AUTHENTICATION_ERROR",
            "message": "Authentication failed",
            "details": {
                "operation": operation,
                "suggestion": "Check your credentials and try again"
            },
            "recovery_action": "reauthenticate",
            "severity": "warning"
        }
    
    @staticmethod
    def handle_authorization_error(error: Exception, operation: str = None) -> Dict[str, Any]:
        """Handle authorization errors"""
        logger.error(f"Authorization error in {operation}: {error}")
        
        return {
            "error": "AUTHORIZATION_ERROR",
            "message": "You don't have permission to perform this action",
            "details": {
                "operation": operation,
                "suggestion": "Contact your administrator for required permissions"
            },
            "recovery_action": "request_permissions",
            "severity": "warning"
        }
    
    @staticmethod
    def handle_zkteco_error(error: Exception, operation: str = None) -> Dict[str, Any]:
        """Handle ZKTeco device communication errors"""
        logger.error(f"ZKTeco device error in {operation}: {error}")
        
        error_message = str(error).lower()
        
        if "connection" in error_message or "timeout" in error_message:
            return {
                "error": "DEVICE_CONNECTION_ERROR",
                "message": "Cannot connect to ZKTeco device",
                "details": {
                    "operation": operation,
                    "suggestion": "Check device connectivity and network configuration"
                },
                "recovery_action": "check_device_connection",
                "severity": "error"
            }
        elif "authentication" in error_message:
            return {
                "error": "DEVICE_AUTH_ERROR",
                "message": "Device authentication failed",
                "details": {
                    "operation": operation,
                    "suggestion": "Check device credentials and configuration"
                },
                "recovery_action": "verify_device_credentials",
                "severity": "error"
            }
        
        return {
            "error": "DEVICE_ERROR",
            "message": "ZKTeco device operation failed",
            "details": {
                "operation": operation,
                "suggestion": "Check device status and configuration"
            },
            "recovery_action": "check_device_status",
            "severity": "error"
        }
    
    @staticmethod
    def handle_business_logic_error(error: BusinessLogicException) -> Dict[str, Any]:
        """Handle business logic validation errors"""
        logger.error(f"Business logic error: {error.message}")
        
        return {
            "error": error.error_code or "BUSINESS_LOGIC_ERROR",
            "message": error.message,
            "details": error.details,
            "recovery_action": error.details.get("recovery_action", "review_business_rules"),
            "severity": error.severity
        }
    
    @staticmethod
    def handle_external_service_error(error: Exception, service: str = None) -> Dict[str, Any]:
        """Handle external service communication errors"""
        logger.error(f"External service error ({service}): {error}")
        
        return {
            "error": "EXTERNAL_SERVICE_ERROR",
            "message": f"Communication with {service or 'external service'} failed",
            "details": {
                "service": service,
                "suggestion": "Service may be temporarily unavailable"
            },
            "recovery_action": "retry_later",
            "severity": "warning"
        }
    
    @staticmethod
    def create_error_response(error_info: Dict[str, Any], status_code: int = 500) -> JSONResponse:
        """Create standardized error response"""
        response_data = {
            "success": False,
            "error": error_info["error"],
            "message": error_info["message"],
            "details": error_info.get("details", {}),
            "recovery_action": error_info.get("recovery_action", "contact_support"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )

def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}")
    logger.debug(f"Unhandled exception traceback: {traceback.format_exc()}")
    
    error_info = {
        "error": "INTERNAL_SERVER_ERROR",
        "message": "An unexpected error occurred",
        "details": {
            "path": str(request.url),
            "method": request.method,
            "suggestion": "Please try again or contact support if the problem persists"
        },
        "recovery_action": "retry_or_contact_support",
        "severity": "error"
    }
    
    return ErrorHandler.create_error_response(error_info, status.HTTP_500_INTERNAL_SERVER_ERROR)

def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI validation exception handler"""
    error_info = ErrorHandler.handle_validation_error(exc, f"{request.method} {request.url}")
    return ErrorHandler.create_error_response(error_info, status.HTTP_422_UNPROCESSABLE_ENTITY)

def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Database exception handler"""
    operation = f"{request.method} {request.url}"
    error_info = ErrorHandler.handle_database_error(exc, operation)
    
    # Determine appropriate status code
    if error_info["error"] in ["DUPLICATE_RECORD", "NULL_VIOLATION"]:
        status_code = status.HTTP_400_BAD_REQUEST
    elif error_info["error"] == "IN_USE":
        status_code = status.HTTP_409_CONFLICT
    elif error_info["error"] == "FOREIGN_KEY_VIOLATION":
        status_code = status.HTTP_404_NOT_FOUND
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    return ErrorHandler.create_error_response(error_info, status_code)

# Recovery mechanisms
class RecoveryManager:
    """Manages recovery actions for different error types"""
    
    @staticmethod
    def suggest_recovery_action(error_info: Dict[str, Any]) -> str:
        """Suggest recovery action based on error type"""
        recovery_action = error_info.get("recovery_action", "contact_support")
        
        action_map = {
            "verify_unique_fields": "Check if this record already exists with the same unique values",
            "verify_references": "Ensure all referenced records exist before creating this record",
            "fill_required_fields": "Provide all required fields marked as mandatory",
            "retry_operation": "Wait a moment and try the operation again",
            "reduce_data_size": "Try with smaller data sets or add pagination",
            "retry_or_contact_support": "Try again or contact support if the problem persists",
            "fix_validation_errors": "Correct the validation errors shown above",
            "reauthenticate": "Log out and log back in with valid credentials",
            "request_permissions": "Contact your administrator for the required permissions",
            "check_device_connection": "Verify device is online and network connectivity",
            "verify_device_credentials": "Check device authentication credentials",
            "check_device_status": "Verify device is powered on and functioning properly",
            "review_business_rules": "Review business rules and constraints",
            "retry_later": "Try again later when the service is available"
        }
        
        return action_map.get(recovery_action, "Contact support for assistance")
    
    @staticmethod
    def can_retry(error_info: Dict[str, Any]) -> bool:
        """Determine if the operation can be retried"""
        retry_actions = [
            "retry_operation",
            "retry_or_contact_support",
            "retry_later"
        ]
        
        return error_info.get("recovery_action") in retry_actions
    
    @staticmethod
    def get_retry_delay(attempt: int, max_delay: int = 60) -> int:
        """Calculate retry delay with exponential backoff"""
        import math
        delay = min(math.pow(2, attempt), max_delay)
        return int(delay)
