"""
Role-Based Access Control (RBAC) Middleware and Decorators

This module provides comprehensive RBAC functionality including:
- Permission-based access control
- Role hierarchy support
- Middleware for request-level permission checking
- Decorators for function-level permission enforcement
- Caching for performance optimization
"""

import functools
import json
import logging
from datetime import datetime
from typing import List, Optional, Union, Callable
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .database import get_db
from .dependencies import get_current_user
from ..models.system import UserExtension
from ..models.user import User

logger = logging.getLogger(__name__)

# Security scheme for JWT tokens
security = HTTPBearer(auto_error=False)

# Route-permission rules: (path_prefix, frozenset_of_methods, required_permission)
# Rules are evaluated in order; first match wins.
# Superusers bypass all rules. Paths not matched have no extra permission check.
_ROUTE_RULES = [
    # Settings — user management
    ("/api/v1/settings/users",        frozenset({"GET","POST","PUT","PATCH","DELETE"}), "settings.manage_users"),
    ("/api/v1/settings/roles",        frozenset({"GET","POST","PUT","PATCH","DELETE"}), "settings.manage_roles"),
    ("/api/v1/settings/permissions",  frozenset({"GET","POST","PUT","PATCH","DELETE"}), "settings.manage_roles"),
    ("/api/v1/settings/company",      frozenset({"GET","PUT","PATCH"}),                 "settings.change"),
    ("/api/v1/settings",              frozenset({"GET"}),                               "settings.view"),
    ("/api/v1/settings",              frozenset({"PUT","PATCH","DELETE"}),              "settings.change"),
    # Personnel
    ("/api/v1/personnel",             frozenset({"GET"}),                               "personnel.view"),
    ("/api/v1/personnel",             frozenset({"POST","PUT","PATCH","DELETE"}),       "personnel.change"),
    # Departments / Positions (lookup lists used by forms)
    ("/api/v1/departments",           frozenset({"GET"}),                               "personnel.view"),
    ("/api/v1/departments",           frozenset({"POST","PUT","PATCH","DELETE"}),       "personnel.change"),
    ("/api/v1/positions",             frozenset({"GET"}),                               "personnel.view"),
    ("/api/v1/positions",             frozenset({"POST","PUT","PATCH","DELETE"}),       "personnel.change"),
    # Attendance
    ("/api/v1/attendance",            frozenset({"GET"}),                               "attendance.view"),
    ("/api/v1/attendance",            frozenset({"POST","PUT","PATCH","DELETE"}),       "attendance.change"),
    # Devices / BioTime / ZKTeco
    ("/api/v1/devices",               frozenset({"GET"}),                               "devices.view"),
    ("/api/v1/devices",               frozenset({"POST","PUT","PATCH","DELETE"}),       "devices.change"),
    ("/api/v1/biotime",               frozenset({"GET"}),                               "devices.view"),
    ("/api/v1/biotime",               frozenset({"POST","PUT","PATCH","DELETE"}),       "devices.change"),
    ("/api/v1/zkteco",                frozenset({"GET","POST","PUT","PATCH","DELETE"}), "devices.sync"),
    # Access Control
    ("/api/access-control",           frozenset({"GET"}),                               "access_control.view"),
    ("/api/access-control",           frozenset({"POST","PUT","PATCH","DELETE"}),       "access_control.change"),
    # Reports
    ("/api/v1/report",                frozenset({"GET","POST"}),                        "reports.view"),
    # Visitors
    ("/api/visitor",                  frozenset({"GET"}),                               "visitors.view"),
    ("/api/visitor",                  frozenset({"POST","PUT","PATCH","DELETE"}),       "visitors.add"),
    # Emergency
    ("/api/emergency",                frozenset({"GET"}),                               "emergency.view"),
    ("/api/emergency",                frozenset({"POST","PUT","PATCH","DELETE"}),       "emergency.manage"),
    # Mustering
    ("/api/mustering",                frozenset({"GET"}),                               "mustering.view"),
    ("/api/mustering",                frozenset({"POST","PUT","PATCH","DELETE"}),       "mustering.manage"),
    # POB Status / Zones
    ("/api/v1/pob-status",            frozenset({"GET"}),                               "pob.view"),
    ("/api/v1/pob-status",            frozenset({"POST","PUT","PATCH","DELETE"}),       "pob.change"),
    ("/api/v1/zones",                 frozenset({"GET"}),                               "pob.view"),
    ("/api/v1/zones",                 frozenset({"POST","PUT","PATCH","DELETE"}),       "pob.change"),
    # Journey management (flights/voyages + land journeys). Approving a journey and
    # overriding transport limits are checked inside the endpoints (journey.approve,
    # transport.override) because those paths carry an id and cannot be matched here.
    ("/api/v1/transport",             frozenset({"GET"}),                               "transport.view"),
    ("/api/v1/transport",             frozenset({"POST","PUT","PATCH","DELETE"}),       "transport.manage"),
    ("/api/v1/journeys",              frozenset({"GET"}),                               "journey.view"),
    ("/api/v1/journeys",              frozenset({"POST","PUT","PATCH","DELETE"}),       "journey.manage"),
    # Payroll / MTD / Meeting (no dedicated permission — map to nearest)
    ("/api/v1/payroll",               frozenset({"GET"}),                               "reports.view"),
    ("/api/v1/payroll",               frozenset({"POST","PUT","PATCH","DELETE"}),       "settings.change"),
    ("/api/mtd",                      frozenset({"GET"}),                               "reports.view"),
    ("/api/mtd",                      frozenset({"POST","PUT","PATCH","DELETE"}),       "settings.change"),
    ("/api/meeting",                  frozenset({"GET"}),                               "reports.view"),
    ("/api/meeting",                  frozenset({"POST","PUT","PATCH","DELETE"}),       "settings.change"),
]


def _match_route_permission(path: str, method: str) -> Optional[str]:
    """Return the required permission codename for this path+method, or None."""
    for prefix, methods, permission in _ROUTE_RULES:
        if path.startswith(prefix) and method in methods:
            return permission
    return None


class RBACMiddleware(BaseHTTPMiddleware):
    """
    RBAC Middleware for FastAPI applications
    
    This middleware checks user permissions for each request based on:
    - JWT token validation
    - User role assignments
    - Permission requirements
    - Module-specific access rules
    """
    
    def __init__(self, app, exclude_paths: List[str] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/favicon.ico",
            "/static",
            "/api/auth/",        # all auth endpoints (login, refresh, simple-login, etc.)
            "/api/v1/auth/",
            "/api/v1/mfa/verify",  # MFA handshake: consumes the mfa_pending token the
                                   # RBAC middleware would otherwise reject; the endpoint
                                   # validates that token itself. (Only /verify — the
                                   # other /mfa routes still require a full token + RBAC.)
            "/iclock/",          # all ZKTeco ADMS endpoints (no auth)
            "/api/v1/iclock/cdata",
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request through RBAC checks"""

        # Always pass OPTIONS preflight requests through — CORS middleware handles them
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip RBAC for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            response = await call_next(request)
            return response

        try:
            # Get authorization header (also accept ?token= query param for SSE)
            authorization = request.headers.get("authorization")
            if not authorization:
                qs_token = request.query_params.get("token")
                if qs_token:
                    authorization = f"Bearer {qs_token}"
            api_key = request.headers.get("x-api-key")

            # Public endpoints always pass through — even if a stale/expired token
            # header was sent (e.g. the browser's apiService attaches the old token
            # to every request including the login call itself).
            if self._is_public_endpoint(request.url.path):
                response = await call_next(request)
                return response

            # No credentials at all on a protected endpoint
            if not authorization and not api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"}
                )

            # Get user from JWT or API key
            user = None
            if authorization:
                try:
                    user = await self._get_user_from_token(authorization, request)
                except Exception as e:
                    logger.warning(f"Token validation failed: {e}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid authentication token"}
                    )
            elif api_key:
                try:
                    user = await self._get_user_from_api_key(api_key, request)
                except Exception as e:
                    logger.warning(f"API key validation failed: {e}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid API key"}
                    )
            
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication failed"}
                )
            
            # Store user in request state for later use
            request.state.user = user
            user_permissions = await self._get_user_permissions(user.id)
            request.state.user_permissions = user_permissions

            # Enforce route-level permissions for non-superusers
            if "*" not in user_permissions:
                required = _match_route_permission(request.url.path, request.method)
                if required and required not in user_permissions:
                    logger.warning(
                        "Permission denied: user=%s path=%s method=%s required=%s",
                        getattr(user, "username", user.id),
                        request.url.path, request.method, required,
                    )
                    return JSONResponse(
                        status_code=403,
                        content={"detail": f"Access denied: missing permission '{required}'"},
                    )

            # Continue with request
            response = await call_next(request)
            
            # Log operation after response
            await self._log_operation(request, response, user)
            
            return response
            
        except Exception as e:
            try:
                logger.error(f"RBAC middleware error: {type(e).__name__}: {e.args}")
            except Exception:
                logger.error(f"RBAC middleware error (could not serialize exception): {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public"""
        public_endpoints = [
            "/api/auth/",
            "/api/v1/auth/",
            "/api/v1/health",
            "/api/v1/status",
            "/health",
            "/iclock/",
        ]
        return any(path.startswith(endpoint) for endpoint in public_endpoints)
    
    async def _get_user_from_token(self, authorization: str, request: Request) -> User:
        """Get user from JWT token"""
        try:
            # Remove 'Bearer ' prefix
            token = authorization.replace("Bearer ", "")
            
            # Use existing security module to validate token
            from .database import SessionLocal
            db = SessionLocal()
            try:
                user = await get_current_user(token, db)
                return user
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting user from token: {e}")
            raise
    
    async def _get_user_from_api_key(self, api_key: str, request: Request) -> User:
        """Get user from API key"""
        from .database import SessionLocal
        from ..models.system import ApiKey
        db = SessionLocal()
        try:
            # Find API key in database
            key_record = db.query(ApiKey).filter(
                ApiKey.api_key == api_key,
                ApiKey.is_active == True
            ).first()
            
            if not key_record:
                raise HTTPException(status_code=401, detail="Invalid API key")
            
            # Check if API key has expired
            if key_record.expiry_date and key_record.expiry_date < datetime.now().date():
                raise HTTPException(status_code=401, detail="API key expired")
            
            # Check IP whitelist
            if key_record.ip_whitelist:
                client_ip = request.client.host
                if client_ip not in key_record.ip_whitelist:
                    raise HTTPException(status_code=403, detail="IP not whitelisted")
            
            # Update usage statistics
            key_record.last_used = datetime.now()
            key_record.usage_count += 1
            db.commit()
            
            # Get user who created the API key
            user = db.query(User).filter(User.id == key_record.created_by).first()
            return user
            
        finally:
            db.close()
    
    async def _get_user_permissions(self, user_id: int) -> List[str]:
        """Get user permissions from database with caching."""
        try:
            from .database import SessionLocal
            from .redis_client import get_redis_client
            from sqlalchemy import text as sa_text

            cache_key = f"user_permissions:{user_id}"

            rc = get_redis_client()
            if rc is not None:
                try:
                    cached = rc.get(cache_key)
                    if cached:
                        return json.loads(cached)
                except Exception:
                    pass

            db = SessionLocal()
            try:
                # Check superuser flag first — superusers have all permissions
                su = db.execute(sa_text(
                    "SELECT is_superuser FROM auth_user WHERE id = :uid"
                ), {"uid": user_id}).fetchone()
                if su and su.is_superuser:
                    return ["*"]

                rows = db.execute(sa_text("""
                    SELECT DISTINCT p.codename
                    FROM auth_user_role ur
                    JOIN auth_role r ON r.id = ur.role_id AND r.is_active = true
                    JOIN auth_role_permission rp ON rp.role_id = r.id
                    JOIN auth_permission p ON p.id = rp.permission_id
                    WHERE ur.user_id = :uid
                """), {"uid": user_id}).fetchall()

                permissions_list = [row.codename for row in rows]

                if rc is not None:
                    try:
                        rc.setex(cache_key, 900, json.dumps(permissions_list))
                    except Exception:
                        pass

                return permissions_list

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return []
    
    async def _log_operation(self, request: Request, response, user):
        """Persist every state-changing request and every denied request to base_operationlog."""
        try:
            if self._is_public_endpoint(request.url.path):
                return
            method = request.method
            # Only log writes and access denials — skip noisy GETs that succeed
            if method == "GET" and response.status_code < 400:
                return

            from .database import SessionLocal
            from datetime import datetime, timezone
            from sqlalchemy import text as _text

            action = self._get_action_from_method(method)
            status_code = response.status_code
            username = getattr(user, "username", str(getattr(user, "id", "unknown")))
            user_id  = getattr(user, "id", None)

            db = SessionLocal()
            try:
                db.execute(_text("""
                    INSERT INTO base_operationlog
                        (user_id, action, table_name, new_values, ip_address, created_at)
                    VALUES
                        (:uid, :action, :table_name, :new_values, :ip, :ts)
                """), {
                    "uid":        user_id,
                    "action":     action,
                    "table_name": request.url.path,
                    "new_values": f"{method} {request.url.path} → {status_code} | user={username}",
                    "ip":         request.client.host if request.client else "",
                    "ts":         datetime.now(timezone.utc),
                })
                db.commit()
            except Exception as db_exc:
                db.rollback()
                # Fall back to structured logger if DB write fails — never block the response
                logger.warning("Audit log DB write failed: %s | %s %s %s user=%s",
                               db_exc, method, request.url.path, status_code, username)
            finally:
                db.close()
        except Exception:
            pass
    
    def _get_action_from_method(self, method: str) -> str:
        """Map HTTP method to action"""
        action_map = {
            "GET": "view",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete"
        }
        return action_map.get(method, "unknown")


# Permission decorators
def require_permission(permission_code: str):
    """
    Decorator to require specific permission for API endpoint
    
    Args:
        permission_code: The permission code required (e.g., "personnel.create")
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from kwargs (FastAPI dependency injection)
            request = kwargs.get('request')
            if not request:
                request = args[0] if args else None
            
            if not request:
                raise HTTPException(status_code=500, detail="Request object not found")
            
            # Get user permissions from request state
            user_permissions = getattr(request.state, 'user_permissions', [])
            
            # Check if user has required permission
            if permission_code not in user_permissions:
                logger.warning(
                    f"Permission denied: User missing '{permission_code}' permission",
                    extra={
                        "permission": permission_code,
                        "user_permissions": user_permissions
                    }
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied. Required permission: {permission_code}"
                )
            
            # Call original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_permission(permission_codes: List[str]):
    """
    Decorator to require any of the specified permissions
    
    Args:
        permission_codes: List of permission codes (user needs at least one)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get('request') or (args[0] if args else None)
            
            if not request:
                raise HTTPException(status_code=500, detail="Request object not found")
            
            user_permissions = getattr(request.state, 'user_permissions', [])
            
            # Check if user has any of the required permissions
            if not any(perm in user_permissions for perm in permission_codes):
                logger.warning(
                    f"Permission denied: User missing any of {permission_codes} permissions",
                    extra={
                        "required_permissions": permission_codes,
                        "user_permissions": user_permissions
                    }
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied. Required one of: {', '.join(permission_codes)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_all_permissions(permission_codes: List[str]):
    """
    Decorator to require all of the specified permissions
    
    Args:
        permission_codes: List of permission codes (user needs all of them)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get('request') or (args[0] if args else None)
            
            if not request:
                raise HTTPException(status_code=500, detail="Request object not found")
            
            user_permissions = getattr(request.state, 'user_permissions', [])
            
            # Check if user has all required permissions
            missing_permissions = [perm for perm in permission_codes if perm not in user_permissions]
            
            if missing_permissions:
                logger.warning(
                    f"Permission denied: User missing permissions {missing_permissions}",
                    extra={
                        "required_permissions": permission_codes,
                        "missing_permissions": missing_permissions,
                        "user_permissions": user_permissions
                    }
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied. Missing permissions: {', '.join(missing_permissions)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(role_name: str):
    """
    Decorator to require specific role
    
    Args:
        role_name: The role name required (e.g., "Administrator")
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get('request') or (args[0] if args else None)
            
            if not request:
                raise HTTPException(status_code=500, detail="Request object not found")
            
            # Get user from request state
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Check user's roles
            from .database import SessionLocal
            from sqlalchemy import text as sa_text

            db = SessionLocal()
            try:
                match = db.execute(sa_text("""
                    SELECT 1 FROM auth_user_role ur
                    JOIN auth_role r ON r.id = ur.role_id AND r.is_active = true
                    WHERE ur.user_id = :uid AND r.name = :role
                    LIMIT 1
                """), {"uid": user.id, "role": role_name}).fetchone()

                if not match:
                    logger.warning(
                        f"Role access denied: User does not have role '{role_name}'",
                        extra={
                            "required_role": role_name,
                            "user_id": user.id
                        }
                    )
                    raise HTTPException(
                        status_code=403,
                        detail=f"Access denied. Required role: {role_name}"
                    )
                
                return await func(*args, **kwargs)
                
            finally:
                db.close()
        
        return wrapper
    return decorator


def log_operation(module: str, action: str = None):
    """
    Decorator to automatically log operations
    
    Args:
        module: The module name (e.g., "personnel", "device")
        action: The action name (optional, will be inferred from HTTP method)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get('request') or (args[0] if args else None)
            
            if not request:
                return await func(*args, **kwargs)
            
            # Get user from request state
            user = getattr(request.state, 'user', None)
            
            # Execute function
            try:
                result = await func(*args, **kwargs)
                
                # Log successful operation
                await _log_function_operation(
                    request, user, module, action or func.__name__, 
                    "success", None, result
                )
                
                return result
                
            except Exception as e:
                # Log failed operation
                await _log_function_operation(
                    request, user, module, action or func.__name__, 
                    "error", str(e), None
                )
                raise
        
        return wrapper
    return decorator


async def _log_function_operation(request, user, module: str, action: str,
                              result: str, error_msg: str = None, response_data=None):
    """Log operations via Python logger (OperationLog DB model not yet active)."""
    try:
        username = getattr(user, 'username', None) or (user.id if user else 'anon')
        if result != "success":
            logger.warning("RBAC func audit %s %s %s → %s error=%s",
                           action, module, getattr(request, 'url', ''), result, error_msg)
    except Exception:
        pass


# FastAPI dependencies
async def get_current_user_with_permissions(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """
    FastAPI dependency to get current user with permissions
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get user from token
    user = await get_current_user(credentials.credentials, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    # Get user permissions
    from .rbac import RBACMiddleware
    rbac = RBACMiddleware(None)
    user_permissions = await rbac._get_user_permissions(user.id)
    
    # Store in request state
    request.state.user = user
    request.state.user_permissions = user_permissions
    
    return user


async def check_permission(permission_code: str, request: Request):
    """
    Check if current user has specific permission
    """
    user_permissions = getattr(request.state, 'user_permissions', [])
    return permission_code in user_permissions


# Utility functions
def clear_user_permission_cache(user_id: int):
    """Clear permission cache for specific user"""
    try:
        from .redis_client import redis_client
        cache_key = f"user_permissions:{user_id}"
        redis_client.delete(cache_key)
        logger.info(f"Cleared permission cache for user {user_id}")
    except Exception as e:
        logger.error(f"Error clearing permission cache: {e}")


def clear_all_permission_cache():
    """Clear all permission caches"""
    try:
        from .redis_client import redis_client
        pattern = "user_permissions:*"
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
            logger.info(f"Cleared {len(keys)} permission cache entries")
    except Exception as e:
        logger.error(f"Error clearing all permission caches: {e}")


# Permission checking functions — use auth_* tables (BioTime-compatible)
async def has_permission(user_id: int, permission_code: str, db: Session) -> bool:
    """Check if user has a specific permission codename via auth_* tables."""
    try:
        from sqlalchemy import text as sa_text
        su = db.execute(sa_text("SELECT is_superuser FROM auth_user WHERE id = :uid"), {"uid": user_id}).fetchone()
        if su and su.is_superuser:
            return True
        row = db.execute(sa_text("""
            SELECT 1 FROM auth_user_role ur
            JOIN auth_role r ON r.id = ur.role_id AND r.is_active = true
            JOIN auth_role_permission rp ON rp.role_id = r.id
            JOIN auth_permission p ON p.id = rp.permission_id AND p.codename = :perm
            WHERE ur.user_id = :uid
            LIMIT 1
        """), {"uid": user_id, "perm": permission_code}).fetchone()
        return row is not None
    except Exception as e:
        logger.error(f"Error checking permission: {e}")
        return False


async def get_user_permissions_list(user_id: int, db: Session) -> List[str]:
    """Get all permission codenames for a user via auth_* tables."""
    try:
        from sqlalchemy import text as sa_text
        su = db.execute(sa_text("SELECT is_superuser FROM auth_user WHERE id = :uid"), {"uid": user_id}).fetchone()
        if su and su.is_superuser:
            return ["*"]
        rows = db.execute(sa_text("""
            SELECT DISTINCT p.codename
            FROM auth_user_role ur
            JOIN auth_role r ON r.id = ur.role_id AND r.is_active = true
            JOIN auth_role_permission rp ON rp.role_id = r.id
            JOIN auth_permission p ON p.id = rp.permission_id
            WHERE ur.user_id = :uid
        """), {"uid": user_id}).fetchall()
        return [row.codename for row in rows]
    except Exception as e:
        logger.error(f"Error getting user permissions: {e}")
        return []
