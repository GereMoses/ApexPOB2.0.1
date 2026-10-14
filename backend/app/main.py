from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
import uvicorn
import os
import asyncio
from typing import Optional
from datetime import datetime, timezone, timedelta

from .core.config import settings
from .core.database import test_db_connection, test_redis_connection, SessionLocal
from .core.rate_limiter import add_rate_limit_middleware
from .api import api_router, direct_router

# Configure logging with UTF-8 encoding
import sys
import os

# Ensure UTF-8 encoding for console output
if sys.platform == "win32":
    # Windows-specific encoding fix
    os.system('chcp 65001 > nul')

# Create formatters with proper encoding
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# File handler with UTF-8 encoding
file_handler = logging.FileHandler(settings.LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)

# Stream handler with UTF-8 encoding
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    handlers=[file_handler, stream_handler],
    force=True
)

logger = logging.getLogger(__name__)

# Holds refs to all long-running background tasks so shutdown can cancel them cleanly.
_background_tasks: list = []


async def _supervised(name: str, loop_func, max_backoff: float = 30.0):
    """
    Run a `while True` background loop forever, auto-restarting it with capped
    exponential backoff if it ever exits or raises. These device-connectivity
    loops (heartbeat, poller, live capture) are the only thing that keeps
    "online/offline" status accurate — if one dies silently with no supervisor,
    every reader it manages freezes at its last known status until someone
    notices and restarts the whole backend. That's exactly the kind of gap
    that goes unnoticed in dev (short uptimes) and bites in a real deployment.
    """
    backoff = 1.0
    while True:
        started = asyncio.get_event_loop().time()
        try:
            await loop_func()
            logger.error("Background task '%s' returned unexpectedly — restarting", name)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Background task '%s' crashed: %s", name, exc, exc_info=True)

        if asyncio.get_event_loop().time() - started > 60:
            backoff = 1.0  # it ran healthily for a while — don't punish it for one blip
        logger.warning("Background task '%s' restarting in %.0fs", name, backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)

# Disable interactive API docs in production
_docs_url = None if settings.ENVIRONMENT == "production" else f"{settings.API_V1_STR}/docs"
_redoc_url = None if settings.ENVIRONMENT == "production" else f"{settings.API_V1_STR}/redoc"
_openapi_url = None if settings.ENVIRONMENT == "production" else f"{settings.API_V1_STR}/openapi.json"

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_url=_openapi_url,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

_INSECURE_SECRETS = {
    "pob-system-production-secret-key-2024-secure-jwt-auth",
    "changethis", "secret", "your-secret-key",
}
_INSECURE_DB_PASSWORDS = {"pob_password", "postgres", "password", "changeme", ""}

_IS_PROD = settings.ENVIRONMENT == "production"

if settings.SECRET_KEY in _INSECURE_SECRETS:
    if _IS_PROD:
        raise RuntimeError(
            "SECRET_KEY is using an insecure default. "
            "Generate one with: python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    logger.warning("⚠️  SECRET_KEY is using an insecure default — change before production")

if settings.DATABASE_PASSWORD in _INSECURE_DB_PASSWORDS:
    if _IS_PROD:
        raise RuntimeError(
            "DATABASE_PASSWORD is using a known-insecure default value. "
            "Set a strong password in the POSTGRES_PASSWORD / DATABASE_PASSWORD environment variable."
        )
    logger.warning("⚠️  DATABASE_PASSWORD is using an insecure default — change before production")

# MIDDLEWARE ORDER MATTERS: in Starlette, last-added runs first.
# RBAC must be added first (runs last/inner) so CORS runs first (outer).

# Add RBAC middleware first — it will run INSIDE CORS
from .core.rbac import RBACMiddleware
app.add_middleware(RBACMiddleware, exclude_paths=[
    "/health", "/status", "/docs", "/redoc", "/openapi.json",
    # Prometheus scrapes with no token. The prod backend publishes no port and nginx
    # does not proxy /metrics, so only containers on the internal network can reach it.
    "/metrics",
    "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi.json",
    "/api/v1/auth/login", "/api/v1/auth/simple-login", "/api/v1/auth/production-login",
    # MFA handshake — consumes the mfa_pending token (which RBAC would reject);
    # the endpoint validates that token itself. Only /verify, not the other /mfa routes.
    "/api/v1/mfa/verify",
    # Subscription public endpoints — no auth required
    "/api/v1/subscription/status", "/api/v1/subscription/activate",
    # ZKTeco ADMS device endpoints — device-initiated, no user auth
    "/iclock/cdata", "/iclock/getrequest", "/iclock/devicecmd", "/iclock/test",
    "/api/v1/iclock/cdata", "/api/v1/iclock/getrequest",
    "/api/v1/iclock/devicecmd", "/api/v1/iclock/test",
    # Visitor kiosk public self-service endpoints
    "/api/visitor/kiosk/check-in", "/api/visitor/kiosk/types",
    # SeamlessHR employee webhook — called by SeamlessHR, verified via HMAC signature
    "/api/v1/hr-integration/webhook",
    # Global search and SSE notifications (token via query param)
    "/api/v1/notifications/stream",
    # Punch-stream SSE uses short-lived ticket auth (no Bearer header support)
    "/api/v1/attendance/punch-stream",
    # Static file serving — browser <img> tags cannot send Authorization headers
    "/uploads/", "/media/",
])
logger.info("✅ RBAC middleware enabled for comprehensive access control")

# License enforcement middleware — runs inside RBAC, outside rate limiter
# Returns 402 for all authenticated requests when subscription is expired,
# except Global Admin (who can log in and renew) and public paths.
_LICENSE_BYPASS_PREFIXES = (
    "/health", "/status", "/docs", "/redoc", "/openapi.json",
    # Prometheus scrapes this with no token on the internal network (nginx does not
    # proxy it). It carries no product functionality, and it is already open without a
    # login while the licence is active, so gating it only blinds monitoring — and its
    # alerts — at the moment a lapsed licence is the thing you would want to hear about.
    "/metrics",
    "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi.json",
    "/api/v1/auth/",
    "/api/v1/subscription/status", "/api/v1/subscription/activate",
    "/iclock/", "/api/v1/iclock/",
    # Machine-to-machine callbacks that authenticate by their own means and have
    # no bearer token to offer. Readers push on /iclock/; SeamlessHR posts
    # HMAC-SHA512-signed employee events here. Blocking these on licence state
    # loses data silently — the sender gets the 402, the operator sees nothing,
    # and employee changes simply stop arriving.
    "/api/v1/hr-integration/webhook",
)

import time as _time
from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
from starlette.responses import JSONResponse as _JSONResponse
from jose import jwt as _jwt, JWTError as _JWTError

_license_cache: dict = {"expires_at": 0.0, "status": "unknown", "days": 0}


def _check_license_db() -> tuple[str, int]:
    """Synchronous DB check — returns (status, days_remaining). Cached 60 s."""
    from .core.database import SessionLocal
    from sqlalchemy import text as _text
    db = SessionLocal()
    try:
        row = db.execute(_text(
            "SELECT expiry_date FROM sys_subscription WHERE is_active = TRUE ORDER BY id DESC LIMIT 1"
        )).fetchone()
        if row is None:
            return "no_license", 0
        expiry = row[0]
        now = datetime.now(timezone.utc)
        # Normalise: handle both DATE and TIMESTAMPTZ columns
        if not hasattr(expiry, 'hour'):
            expiry = datetime(expiry.year, expiry.month, expiry.day, tzinfo=timezone.utc)
        elif expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        delta = expiry - now
        if delta.total_seconds() <= 0:
            return "expired", int(delta.total_seconds() / 86400)
        return "active", int(delta.total_seconds() / 86400)
    except Exception:
        return "active", 9999  # fail-open: don't block if DB check errors
    finally:
        db.close()


class LicenseMiddleware(_BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        # Always bypass public paths
        if any(path.startswith(p) for p in _LICENSE_BYPASS_PREFIXES):
            return await call_next(request)

        # Refresh cache every 60 s
        now = _time.monotonic()
        if now > _license_cache["expires_at"]:
            import asyncio
            status, days = await asyncio.to_thread(_check_license_db)
            _license_cache.update({"status": status, "days": days, "expires_at": now + 60.0})

        if _license_cache["status"] in ("active", "unknown"):
            return await call_next(request)

        # License expired or missing — allow Global Admins through.
        from .core.database import SessionLocal
        from sqlalchemy import text as _text

        def _is_global_admin(where: str, value) -> bool:
            db = SessionLocal()
            try:
                row = db.execute(_text(
                    f"SELECT COALESCE(is_global_admin, FALSE) FROM auth_user WHERE {where}"
                ), value).fetchone()
                return bool(row and row[0])
            except Exception:
                return False
            finally:
                db.close()

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = _jwt.decode(
                    token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
                )
                if _is_global_admin("username = :u OR email = :u", {"u": payload.get("sub", "")}):
                    return await call_next(request)
            except (_JWTError, Exception):
                pass
        else:
            # SSE endpoints (EventSource) cannot send an Authorization header, so
            # they authenticate with a short-lived ?ticket=. Without this branch a
            # Global Admin is let through everywhere EXCEPT their notification and
            # punch streams, which then reconnect in a tight loop against a 402.
            # Read-only lookup — the ticket is left for the stream handler to use.
            ticket = request.query_params.get("ticket")
            if ticket:
                try:
                    from .core.redis_client import get_redis_client
                    uid = get_redis_client().get(f"sse_ticket:{ticket}")
                    if uid:
                        uid = uid.decode() if isinstance(uid, bytes) else str(uid)
                        if _is_global_admin("id = :i", {"i": int(uid)}):
                            return await call_next(request)
                except Exception:
                    pass

        return _JSONResponse(
            status_code=402,
            content={
                "detail": "subscription_expired",
                "message": "Your subscription has expired. Please contact your vendor to renew.",
                "days_remaining": _license_cache["days"],
            },
        )


app.add_middleware(LicenseMiddleware)
logger.info("✅ License enforcement middleware enabled")

# Add CORS middleware last — it will run FIRST (outermost) so preflight OPTIONS
# requests are handled before RBAC ever sees them.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["Content-Disposition"],
)

# Security headers — injected on every response.
# Added innermost (runs outermost) so headers appear on all responses including errors.
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()"
        )
        # HSTS — only in production (meaningless/ harmful over plain HTTP in dev).
        # Sourced from SECURE_HSTS_SECONDS so the config value is actually applied.
        if settings.ENVIRONMENT == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.SECURE_HSTS_SECONDS}; includeSubDomains",
            )
        # Content-Security-Policy — this app's backend serves JSON/API + static
        # uploads only (the SPA is served by nginx). A tight policy here is safe and
        # adds defense-in-depth against injected content. OpenAPI docs are disabled
        # in production so no inline-script allowance is needed.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'",
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware for production security
try:
    app = add_rate_limit_middleware(app)
    logger.info("✅ Rate limiting middleware enabled for production security")
except Exception as e:
    logger.warning(f"⚠️ Rate limiting disabled due to connection issues: {e}")

# Add trusted host middleware — production only.
# In development/staging the proxy may forward with internal Docker hostnames
# (pob_backend:8000, etc.) that won't match any explicit allowlist, causing
# TrustedHostMiddleware to return 400 for every request.
# Only enable this in production where ALLOWED_HOSTS is explicitly configured.
_raw_hosts = os.getenv("ALLOWED_HOSTS", "")
_allowed_hosts = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

if settings.ENVIRONMENT == "production":
    if not _allowed_hosts or "*" in _allowed_hosts:
        raise RuntimeError(
            "ALLOWED_HOSTS must be explicitly set to your domain(s) in production. "
            "Example: ALLOWED_HOSTS=api.yourfacility.com,yourfacility.com"
        )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=_allowed_hosts,
    )
    logger.info("✅ TrustedHostMiddleware enabled: %s", _allowed_hosts)

# Add enhanced exception handlers
from .core.error_handling import (
    global_exception_handler,
    validation_exception_handler,
    database_exception_handler
)
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)

# BioTime 9.5 Authentication is now primary
print("✅ BioTime 9.5 compatible authentication enabled")

# Serve user-uploaded files — creates dirs if missing so first boot doesn't crash
import pathlib
for _d in ("uploads", "media"):
    pathlib.Path(_d).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/media", StaticFiles(directory="media"), name="media")

# Include API router (versioned — /api/v1/...)
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include direct routers (self-prefixed — /api/... without /v1)
# All formerly-scattered router registrations are now in api/__init__.py direct_router.
app.include_router(direct_router)
logger.info("✅ All direct API routers registered")

# ARIA AI assistant endpoints
try:
    from .api.ai import router as ai_router
    app.include_router(ai_router)
    logger.info("✅ ARIA AI router registered")
except Exception as e:
    logger.warning(f"ARIA AI router not loaded: {e}", exc_info=True)

# ADMS protocol endpoints — no authentication, device-initiated, MUST be at root
from .api.adms_protocol import router as adms_router
app.include_router(adms_router, tags=["ADMS Protocol"])

# Prometheus metrics — must be instrumented at module level, before app starts
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app, include_in_schema=False)
    logger.info("✅ Prometheus metrics endpoint active at /metrics")
except ImportError:
    logger.debug("prometheus-fastapi-instrumentator not installed — /metrics disabled")


def _unshadow_static_routes(application) -> int:
    """Move a static route in front of any dynamic route that currently captures it.

    FastAPI matches routes in registration order, so `GET /onboarding/{onboarding_id}`
    registered before `GET /onboarding/types` swallows "types" as an id and the request
    fails with a 422 — the static route is unreachable. Only routes that are *actually*
    shadowed (same method, an earlier dynamic route's pattern matches the static path)
    are moved, and only to just before the first shadowing route; nothing else changes.
    """
    from fastapi.routing import APIRoute
    routes = application.router.routes
    moved = 0
    i = 0
    while i < len(routes):
        r = routes[i]
        if isinstance(r, APIRoute) and "{" not in r.path:
            for j in range(i):
                d = routes[j]
                if (isinstance(d, APIRoute) and "{" in d.path
                        and (r.methods & d.methods) and d.path_regex.match(r.path)):
                    routes.insert(j, routes.pop(i))
                    moved += 1
                    break
        i += 1
    return moved


try:
    _moved = _unshadow_static_routes(app)
    if _moved:
        logger.info("✅ Un-shadowed %d static route(s) hidden behind dynamic path routes", _moved)
except Exception as _e:  # never block start-up over route ordering
    logger.warning("Route un-shadowing skipped: %s", _e)


def _sync_time_one_pass() -> None:
    """Synchronous inner body of the time-sync loop — runs in a thread pool."""
    from .api.adms_protocol import queue_clock_sync, STATE_APPROVED, _get_direct_device
    from .models.biotime_models import IClockTerminal
    db = SessionLocal()
    try:
        terminals = db.query(IClockTerminal).filter(IClockTerminal.state == STATE_APPROVED).all()
        for t in terminals:
            dev = _get_direct_device(t.sn, db)
            if dev and (dev.connection_mode or '').lower() in ('direct', 'both'):
                continue  # direct sync handled by async caller
            try:
                # ADMS-correct clock command (SET OPTIONS DateTime=<enc>); push
                # firmware rejects the ZKLib-style "DATE TIME <str>" as UNKNOWN CMD.
                queue_clock_sync(t.sn, db)
            except Exception as te:
                logger.warning(f"Time sync ADMS queue failed for {t.sn}: {te}")
        logger.info(f"Hourly ADMS time-sync queued for {len(terminals)} reader(s)")
    finally:
        db.close()


async def _time_sync_loop():
    """Hourly: sync clocks on all approved readers. DB work runs off the event loop."""
    from .api.adms_protocol import STATE_APPROVED, _direct_sync_time, _get_direct_device
    from .models.biotime_models import IClockTerminal

    await asyncio.sleep(10)
    logger.info("Time sync loop started — initial sync now, then every hour")

    while True:
        try:
            # Direct-IP devices: async TCP sync — stays on the event loop (non-blocking)
            db = SessionLocal()
            try:
                direct_devs = [
                    (t.sn, dev)
                    for t in db.query(IClockTerminal).filter(IClockTerminal.state == STATE_APPROVED).all()
                    if (dev := _get_direct_device(t.sn, db)) and (dev.connection_mode or '').lower() in ('direct', 'both')
                ]
            finally:
                db.close()

            for sn, dev in direct_devs:
                try:
                    result = await _direct_sync_time(dev.ip_address, dev.port)
                    if not result.get('success'):
                        logger.warning(f"Direct sync failed {sn}: {result.get('error')}")
                except Exception as exc:
                    logger.warning(f"Direct sync exception {sn}: {exc}")

            # ADMS queue for push-only devices — blocking DB write, run in thread
            await asyncio.to_thread(_sync_time_one_pass)

        except Exception as e:
            logger.error(f"Time sync loop error: {e}")

        await asyncio.sleep(3600)


def _attendance_query_pending(yesterday) -> list:
    """Synchronous DB query for employees needing attendance recalculation."""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT DISTINCT p.id AS emp_id, p.emp_code
            FROM iclock_transaction t
            JOIN personnel p ON (t.emp_code = p.emp_code OR t.emp_code = p.badge_id)
            WHERE t.punch_time::date >= :yesterday
              AND (p.is_active = true OR p.is_active IS NULL)
              AND EXISTS (
                    SELECT 1 FROM att_schedule sc
                    WHERE sc.emp_code = p.emp_code
                      AND sc.start_date <= t.punch_time::date
                      AND (sc.end_date IS NULL OR sc.end_date >= t.punch_time::date)
                  )
              AND (
                    NOT EXISTS (
                        SELECT 1 FROM att_report r
                        JOIN personnel_employee pe ON r.emp_id = pe.id
                        WHERE pe.emp_code = p.emp_code
                          AND r.att_date = t.punch_time::date
                    )
                    OR EXISTS (
                        SELECT 1 FROM att_report r
                        JOIN personnel_employee pe ON r.emp_id = pe.id
                        WHERE pe.emp_code = p.emp_code
                          AND r.att_date = t.punch_time::date
                          AND r.updated_at < t.upload_time
                    )
                  )
        """), {"yesterday": yesterday}).fetchall()
        return [r.emp_id for r in rows]
    finally:
        db.close()


async def _attendance_auto_calc_loop():
    """Periodic catch-all attendance recalc. DB query runs in thread pool."""
    from .services.attendance_calculation_service import attendance_calculation_service
    from datetime import date, timedelta
    import time as _time

    await asyncio.sleep(90)
    logger.info("Attendance auto-calc loop started — periodic catch-all every 15 min")

    while True:
        _start = _time.monotonic()
        try:
            today     = date.today()
            yesterday = today - timedelta(days=1)

            emp_ids = await asyncio.to_thread(_attendance_query_pending, yesterday)

            if emp_ids:
                db = SessionLocal()
                try:
                    result = await attendance_calculation_service.calculate_attendance(
                        emp_ids=emp_ids,
                        start_date=str(yesterday),
                        end_date=str(today),
                        db=db,
                    )
                    logger.info(
                        f"Periodic auto-calc: {result.get('processed', 0)} employees "
                        f"updated ({yesterday} – {today})"
                    )
                finally:
                    db.close()
        except Exception as exc:
            logger.error(f"Periodic attendance auto-calc error: {exc}")

        # Sleep for the remainder of the 900s interval so runs don't overlap
        elapsed = _time.monotonic() - _start
        await asyncio.sleep(max(0, 900 - elapsed))


def _drill_check_one_pass(now, retry_cutoff) -> None:
    """Synchronous drill scheduler body — runs in a thread pool."""
    from .models.biotime_models import MusteringDrillSchedule
    from .services.mustering_service import MusteringService
    db = SessionLocal()
    try:
        expired = db.query(MusteringDrillSchedule).filter(
            MusteringDrillSchedule.processed == False,
            MusteringDrillSchedule.auto_start == True,
            MusteringDrillSchedule.scheduled_time < retry_cutoff,
        ).all()
        for schedule in expired:
            schedule.processed = True
            schedule.processed_time = now
            schedule.status = "EXPIRED"
            logger.warning(f"Drill schedule {schedule.id} expired for zone {schedule.zone_id}")
        if expired:
            db.commit()

        due = db.query(MusteringDrillSchedule).filter(
            MusteringDrillSchedule.processed == False,
            MusteringDrillSchedule.auto_start == True,
            MusteringDrillSchedule.scheduled_time <= now,
            MusteringDrillSchedule.scheduled_time >= retry_cutoff,
        ).all()

        for schedule in due:
            try:
                service = MusteringService(db)
                service.start_mustering_event(
                    zone_id=schedule.zone_id,
                    event_type=schedule.event_type,
                    initiated_by=schedule.created_by or 1,
                    notes=f"Auto-triggered drill (schedule #{schedule.id})",
                )
                schedule.processed = True
                schedule.processed_time = now
                schedule.status = "TRIGGERED"
                db.commit()
                logger.info(f"Auto-triggered drill schedule {schedule.id} for zone {schedule.zone_id}")
            except ValueError as ve:
                logger.info(f"Drill schedule {schedule.id} deferred (zone {schedule.zone_id} busy): {ve}")
            except Exception as e:
                logger.error(f"Failed to auto-trigger drill schedule {schedule.id}: {e}")
                db.rollback()
    finally:
        db.close()


async def _seamlesshr_nightly_sync_loop():
    """
    Background loop: push yesterday's attendance to SeamlessHR at the configured
    sync time (default midnight UTC). Checks every minute whether it's time to run.
    """
    from .services.seamlesshr_service import get_config, push_attendance
    from .core.database import SessionLocal
    from sqlalchemy import text as _text

    logger.info("SeamlessHR sync scheduler started — checking every 60 s")

    # Seed last-run from the DB so a restart doesn't re-trigger a sync that already
    # ran today (and so a window miss after restart is still caught up exactly once).
    last_run_date = None
    try:
        _db = SessionLocal()
        try:
            _row = _db.execute(_text(
                "SELECT MAX(created_at::date) FROM hr_sync_log WHERE triggered_by = 'scheduler'"
            )).fetchone()
            if _row and _row[0]:
                last_run_date = str(_row[0])
        finally:
            _db.close()
    except Exception:
        pass

    while True:
        try:
            now       = datetime.now(timezone.utc)
            today_str = str(now.date())

            # Run once per day, at OR AFTER the configured time (window, not exact minute).
            # A missed minute (busy loop, GC) no longer skips the whole day; idempotency
            # keys on the records make a catch-up/duplicate run safe.
            if last_run_date != today_str:
                db = SessionLocal()
                try:
                    cfg = get_config(db)
                    if cfg and cfg.get("is_enabled"):
                        sync_parts = (cfg.get("sync_time") or "00:00").split(":")[:2]
                        sync_h, sync_m = int(sync_parts[0]), int(sync_parts[1])
                        scheduled_today = now.replace(hour=sync_h, minute=sync_m, second=0, microsecond=0)
                        if now >= scheduled_today:
                            logger.info("SeamlessHR: nightly sync starting...")
                            result = await asyncio.wait_for(
                                push_attendance(db, triggered_by="scheduler"),
                                timeout=120.0,
                            )
                            logger.info(f"SeamlessHR nightly sync: {result['status']} — {result['message']}")
                            last_run_date = today_str
                finally:
                    db.close()

        except asyncio.CancelledError:
            logger.info("SeamlessHR sync scheduler stopped")
            break
        except Exception as e:
            logger.error(f"SeamlessHR sync loop error: {e}")

        await asyncio.sleep(60)


async def _bc_nightly_sync_loop():
    """Background loop: push attendance to Business Central at the configured sync time."""
    from .services.business_central_service import get_bc_config, push_attendance as bc_push
    from .core.database import SessionLocal
    from sqlalchemy import text as _text

    logger.info("Business Central sync scheduler started — checking every 60 s")

    # Seed last-run from the DB so a restart doesn't re-trigger a sync already done today.
    last_run_date = None
    try:
        _db = SessionLocal()
        try:
            _row = _db.execute(_text(
                "SELECT MAX(created_at::date) FROM bc_sync_log WHERE triggered_by = 'scheduler'"
            )).fetchone()
            if _row and _row[0]:
                last_run_date = str(_row[0])
        finally:
            _db.close()
    except Exception:
        pass

    while True:
        try:
            now       = datetime.now(timezone.utc)
            today_str = str(now.date())

            # Window-based (run at OR AFTER scheduled time, once/day) — see SeamlessHR loop.
            if last_run_date != today_str:
                db = SessionLocal()
                try:
                    cfg = get_bc_config(db)
                    if cfg and cfg.get("is_enabled"):
                        sync_parts = (cfg.get("sync_time") or "01:00").split(":")[:2]
                        sync_h, sync_m = int(sync_parts[0]), int(sync_parts[1])
                        scheduled_today = now.replace(hour=sync_h, minute=sync_m, second=0, microsecond=0)
                        if now >= scheduled_today:
                            logger.info("Business Central: nightly sync starting...")
                            result = await asyncio.wait_for(
                                bc_push(db, triggered_by="scheduler"),
                                timeout=120.0,
                            )
                            logger.info(f"Business Central nightly sync: {result['status']} — {result['message']}")
                            last_run_date = today_str
                finally:
                    db.close()

        except asyncio.CancelledError:
            logger.info("Business Central sync scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Business Central sync loop error: {e}")

        await asyncio.sleep(60)


async def _drill_auto_end_loop():
    """
    Every 60 s: auto-end any active mustering event that has exceeded its
    max_duration_minutes. This prevents forgotten drills from locking access
    control in drill mode indefinitely.

    Drills with max_duration_minutes=0 are never auto-ended.
    """
    await asyncio.sleep(60)  # brief startup delay
    while True:
        try:
            def _check_and_end():
                db = SessionLocal()
                try:
                    # max_duration_minutes column may not exist in older migrations — skip if absent
                    has_col = db.execute(text("""
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='mustering_event' AND column_name='max_duration_minutes'
                    """)).fetchone()
                    if not has_col:
                        return

                    now = datetime.now(timezone.utc)
                    stale = db.execute(text("""
                        SELECT id, start_time, max_duration_minutes, event_type
                        FROM mustering_event
                        WHERE status = 0
                          AND max_duration_minutes > 0
                          AND start_time + (max_duration_minutes || ' minutes')::interval < :now
                    """), {"now": now}).fetchall()
                    for row in stale:
                        db.execute(text("""
                            UPDATE mustering_event
                            SET status = 2, end_time = :now,
                                notes = COALESCE(notes,'') || ' [AUTO-ENDED: exceeded max_duration_minutes]'
                            WHERE id = :eid
                        """), {"now": now, "eid": row.id})
                        logger.warning(
                            "Auto-ended mustering event id=%s (event_type=%s, started=%s, max=%s min)",
                            row.id, row.event_type, row.start_time, row.max_duration_minutes,
                        )
                    if stale:
                        db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.error("Drill auto-end loop error: %s", exc)
                finally:
                    db.close()

            await asyncio.to_thread(_check_and_end)
        except asyncio.CancelledError:
            logger.info("Drill auto-end loop stopped")
            break
        except Exception as exc:
            logger.error("Drill auto-end outer error: %s", exc)

        await asyncio.sleep(60)


async def _drill_scheduler_loop():
    """Background loop: auto-trigger drill schedules. DB runs off the event loop."""
    logger.info("Drill scheduler started — polling every 30 s")
    while True:
        try:
            now = datetime.now(timezone.utc)
            await asyncio.to_thread(_drill_check_one_pass, now, now - timedelta(minutes=30))
        except asyncio.CancelledError:
            logger.info("Drill scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Drill scheduler loop error: {e}")

        await asyncio.sleep(30)


_LEADER_KEY = "pob:background_leader"
_LEADER_TTL = 30   # seconds — leader must renew within this window
# Renewal happens every _LEADER_RENEW_INTERVAL. Must be well under _LEADER_TTL
# so the key does not expire if the event loop is briefly saturated.
# At TTL=30s and interval=8s we have 3 full renewal cycles before expiry.
_LEADER_RENEW_INTERVAL = 8


_LEADER_RETRY_INTERVAL = 5   # how often a non-leader worker re-checks whether it can take over
_leader_pid: Optional[str] = None  # set once this process becomes leader; used by shutdown to release cleanly


async def _release_leader_lock() -> None:
    """
    Release the leader lock on clean shutdown so a restart/redeploy doesn't have
    to wait out the full TTL before the new process can take over device
    connectivity. Without this, restarting the backend (a normal deploy step)
    left a stale lock in Redis pointing at the now-dead PID; every worker in the
    new process would see "leader is PID=<dead>" and skip starting the
    heartbeat/poller/discovery tasks entirely — with no error, just a quiet
    INFO log — until the stale TTL happened to expire. This was caught live
    during testing: a routine container restart silently disabled all device
    monitoring.
    """
    global _leader_pid
    if not _leader_pid:
        return
    try:
        from .core.redis_client import get_redis_client
        r = get_redis_client()
        if r and r.get(_LEADER_KEY) == _leader_pid:
            r.delete(_LEADER_KEY)
            logger.info("Worker PID=%s released background-task leader lock", _leader_pid)
    except Exception as exc:
        logger.warning("Failed to release leader lock on shutdown: %s", exc)


async def _leader_election_loop(start_device_tasks) -> None:
    """
    Runs on every worker for the lifetime of the process. Whoever holds the
    leader lock renews it; everyone else retries acquisition every
    _LEADER_RETRY_INTERVAL seconds. This makes leadership self-healing: if the
    leader process dies without a clean shutdown (OOM-kill, crash, `kill -9`),
    the Redis key simply expires after _LEADER_TTL seconds and the next
    surviving worker to call SETNX takes over automatically — instead of the
    old one-shot-at-startup design, where a crashed leader meant device
    connectivity was gone for good until someone manually restarted every
    worker in the fleet.
    """
    global _leader_pid
    pid = str(os.getpid())
    is_leader = False

    while True:
        try:
            from .core.redis_client import get_redis_client
            r = get_redis_client()
            if not r:
                if not is_leader:
                    logger.warning("Redis unavailable — PID=%s running background tasks (fail-open)", pid)
                    is_leader = True
                    _leader_pid = None  # nothing to release — no real lock was taken
                    await start_device_tasks()
            elif is_leader:
                r.expire(_LEADER_KEY, _LEADER_TTL)
            elif r.set(_LEADER_KEY, pid, nx=True, ex=_LEADER_TTL):
                logger.info("Worker PID=%s acquired background-task leader lock", pid)
                is_leader = True
                _leader_pid = pid
                await start_device_tasks()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Leader election loop error: %s", exc)

        await asyncio.sleep(_LEADER_RENEW_INTERVAL if is_leader else _LEADER_RETRY_INTERVAL)


@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")

    # Capture the main event loop so background tasks/threads can push live
    # zone-occupancy updates to the POB dashboard from any context. Also start the
    # zone pub/sub listener on EVERY worker (not leader-only) so each worker relays
    # Redis zone updates to its own WS clients — broadcasts are otherwise per-process.
    try:
        from .core.websocket import set_main_loop, zone_pubsub_listener
        set_main_loop(asyncio.get_running_loop())
        _background_tasks.append(asyncio.create_task(zone_pubsub_listener()))
        logger.info("✅ Zone pub/sub listener started (all workers)")
    except Exception as _e:
        logger.warning("Could not start zone pub/sub listener: %s", _e)

    # Test database connection (run sync check off the event loop)
    if await asyncio.to_thread(test_db_connection):
        logger.info("✅ Database connection successful")
        # Apply performance indexes on every startup (idempotent)
        try:
            from .database.indexes import apply_indexes
            from .core.database import SessionLocal as _SL
            _idx_db = _SL()
            try:
                await asyncio.to_thread(apply_indexes, _idx_db)
            finally:
                _idx_db.close()
        except Exception as _ie:
            logger.warning("Index creation skipped: %s", _ie)

        # Ensure the device-deletion suppression table exists (sticky UI deletes)
        try:
            from .api.adms_protocol import _ensure_suppression_table
            from .core.database import SessionLocal as _SL2
            _sup_db = _SL2()
            try:
                _ensure_suppression_table(_sup_db)
                _sup_db.commit()
            finally:
                _sup_db.close()
        except Exception as _se:
            logger.warning("Suppression table init skipped: %s", _se)
    else:
        logger.error("❌ Database connection failed")

    # Test Redis connection
    if await asyncio.to_thread(test_redis_connection):
        logger.info("✅ Redis connection successful")
    else:
        logger.error("❌ Redis connection failed")

    # SSE Redis subscriber — runs on every worker so each worker delivers events
    # to its own connected clients. Publishes via Redis Pub/Sub for cross-worker broadcast.
    try:
        from .api.notifications import start_redis_subscriber
        _background_tasks.append(asyncio.create_task(start_redis_subscriber()))
        logger.info("✅ SSE Redis subscriber started")
    except Exception as _sse_exc:
        logger.warning("SSE Redis subscriber not started: %s", _sse_exc)

    # ── Leader election: only ONE worker runs ZKLib/device background tasks ──
    # With --workers N, every worker would otherwise open 4x concurrent ZKLib
    # connections per device (readers only accept 1) and quadruple-trigger
    # drills/nightly syncs. _leader_election_loop runs on every worker for the
    # process lifetime: whichever one holds the Redis lock starts the device
    # tasks; if that worker ever dies without releasing the lock, another
    # worker automatically takes over once the lease expires — no manual
    # restart needed to restore device monitoring.
    async def _start_leader_only_tasks() -> None:
        _background_tasks.append(asyncio.create_task(_attendance_auto_calc_loop()))
        _background_tasks.append(asyncio.create_task(_drill_auto_end_loop()))
        logger.info("✅ Attendance auto-calc + drill auto-end started (leader)")

        _background_tasks.append(asyncio.create_task(_supervised("time_sync_loop", _time_sync_loop)))
        logger.info("✅ Reader time-sync loop started (leader, auto-restart on crash)")

        from .services.zkteco.device_poller import poller_loop
        _background_tasks.append(asyncio.create_task(_supervised("device_poller", poller_loop)))
        logger.info("✅ ZKTeco device poller started (leader, auto-restart on crash)")

        # C3/inBio access controllers are PULL-only (no ADMS push) — this loop pulls
        # their realtime events into the shared zone engine so controller badges
        # update current_zone_id + occupancy just like ADMS readers do.
        from .services.access_controller_ingest import controller_poller_loop
        _background_tasks.append(asyncio.create_task(_supervised("controller_poller", controller_poller_loop)))
        logger.info("✅ Access-controller poller started (leader, auto-restart on crash)")

        from .services.zkteco.live_capture import live_capture_supervisor
        _background_tasks.append(asyncio.create_task(_supervised("live_capture_supervisor", live_capture_supervisor)))
        logger.info("✅ ZKTeco live capture supervisor started (leader, auto-restart on crash)")

        from .services.zkteco.device_heartbeat import heartbeat_loop, reset_stale_states
        reset_stale_states()
        _background_tasks.append(asyncio.create_task(_supervised("device_heartbeat", heartbeat_loop)))
        logger.info("✅ ZKTeco device heartbeat started (leader, auto-restart on crash)")

        _background_tasks.append(asyncio.create_task(_seamlesshr_nightly_sync_loop()))
        _background_tasks.append(asyncio.create_task(_bc_nightly_sync_loop()))
        logger.info("✅ SeamlessHR + Business Central nightly sync schedulers started (leader)")

    _background_tasks.append(asyncio.create_task(_leader_election_loop(_start_leader_only_tasks)))

    # Migrate subscription expiry columns to TIMESTAMPTZ for time-aware license control
    try:
        _mdb = SessionLocal()
        try:
            # ALTER COLUMN TYPE takes an ACCESS EXCLUSIVE lock and REWRITES the
            # table — even when the column is already the target type. Probe
            # information_schema first (ACCESS SHARE only) so a already-migrated
            # database does no work and takes no exclusive lock on every boot.
            for _tbl, _col in [
                ("sys_subscription", "expiry_date"),
                ("sys_renewal_log",  "previous_expiry"),
                ("sys_renewal_log",  "new_expiry"),
            ]:
                try:
                    _already = _mdb.execute(text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = :t AND column_name = :c "
                        "  AND data_type = 'timestamp with time zone'"
                    ), {"t": _tbl, "c": _col}).fetchone()
                    _mdb.commit()
                    if _already:
                        continue
                    _mdb.execute(text("SET LOCAL lock_timeout = '5s'"))
                    _mdb.execute(text(
                        f"ALTER TABLE {_tbl} ALTER COLUMN {_col} "
                        f"TYPE TIMESTAMPTZ USING {_col}::TIMESTAMPTZ"
                    ))
                    _mdb.commit()
                except Exception:
                    _mdb.rollback()
            logger.info("✅ Subscription expiry columns are TIMESTAMPTZ")
        finally:
            _mdb.close()
    except Exception as _me:
        logger.debug(f"Subscription migration skipped: {_me}")

    # ── Pending schema migrations ────────────────────────────────────────────
    # Applied HERE as well as in db-init, because db-init only runs on a full
    # `docker compose up`. Someone who deploys with `git pull && docker compose
    # restart` — a completely natural thing to type — skips db-init entirely and
    # the schema silently stops tracking the code. That failure is invisible:
    # containers report healthy and features just break, as the empty `users`
    # table did to 55 foreign keys.
    #
    # Guarded by a checksum so this is a no-op on every boot after the first: the
    # file is only re-applied when it actually changes. Every statement in
    # incremental.sql is idempotent (IF NOT EXISTS / OR REPLACE / ON CONFLICT).
    _apply_pending_migrations()

    # Say out loud which build this is. A deploy that pulled the repo but never
    # rebuilt the image leaves old code running while everything reports healthy;
    # this line (and /health) is how you tell.
    import os as _os
    _sha = _os.getenv("APP_GIT_SHA", "unknown")
    _built = _os.getenv("APP_BUILD_TIME", "unknown")
    if _sha == "unknown":
        logger.warning(
            "Running an image with NO build stamp — it was not built by "
            "scripts/deploy.sh, so it may predate the current checkout."
        )
    else:
        logger.info(f"✅ Running build {_sha} (built {_built})")


def _apply_pending_migrations() -> None:
    """Apply database/init/incremental.sql when its contents have changed.

    Records the file's sha256 in schema_migrations so an unchanged file costs one
    cheap SELECT. Failures are logged loudly but never prevent start-up — a
    backend that refuses to boot is worse than one running a slightly older
    schema, and db-init remains the primary path.
    """
    import hashlib
    from pathlib import Path as _Path
    from sqlalchemy import text as _text

    path = _Path("/migrations/incremental.sql")
    if not path.exists():
        logger.debug("No incremental.sql mounted — skipping startup migrations")
        return

    try:
        sql = path.read_text()
    except Exception as e:
        logger.warning(f"Could not read incremental.sql: {e}")
        return
    digest = hashlib.sha256(sql.encode()).hexdigest()

    db = SessionLocal()
    try:
        db.execute(_text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name        VARCHAR(120) PRIMARY KEY,
                checksum    VARCHAR(64)  NOT NULL,
                applied_at  TIMESTAMPTZ  DEFAULT NOW()
            )
        """))
        db.commit()

        row = db.execute(_text(
            "SELECT checksum FROM schema_migrations WHERE name = 'incremental.sql'"
        )).fetchone()
        if row and row[0] == digest:
            logger.info("✅ Schema up to date (incremental.sql unchanged)")
            return

        logger.warning(
            "Schema drift detected — applying incremental.sql (%s). This normally "
            "means the code was deployed without db-init running.",
            "changed" if row else "first run",
        )
        # Bound the wait: if another process holds a conflicting lock we would
        # rather fail this attempt than block start-up behind it.
        db.execute(_text("SET LOCAL lock_timeout = '15s'"))
        db.execute(_text(sql))
        db.execute(_text("""
            INSERT INTO schema_migrations (name, checksum, applied_at)
            VALUES ('incremental.sql', :c, NOW())
            ON CONFLICT (name) DO UPDATE SET checksum = EXCLUDED.checksum,
                                             applied_at = NOW()
        """), {"c": digest})
        db.commit()
        logger.info("✅ incremental.sql applied at startup")
    except Exception as e:
        db.rollback()
        logger.error(
            "Startup migration FAILED — the schema may be behind the code: %s. "
            "Run ./scripts/deploy.sh update, or docker compose up -d to re-run db-init.", e
        )
    finally:
        db.close()

    # Log all registered routes grouped by prefix for operational visibility
    ws_routes   = [r.path for r in app.routes if hasattr(r, "path") and "ws" in r.path.lower()]
    api_routes  = sorted({"/".join(r.path.split("/")[:4]) for r in app.routes
                          if hasattr(r, "path") and r.path.startswith("/api")})
    logger.info(f"📋 API prefixes registered: {api_routes}")
    if ws_routes:
        logger.info(f"🔌 WebSocket routes: {ws_routes}")

    logger.info("🚀 Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event — cancel background tasks and close shared clients."""
    logger.info("🛑 Application shutting down — cancelling background tasks")
    for task in _background_tasks:
        task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)

    # Release the leader lock immediately so a restart/redeploy doesn't have to
    # wait out the TTL before device connectivity resumes (see _release_leader_lock).
    await _release_leader_lock()

    # Close shared httpx clients used by integrations
    try:
        from .services.business_central_service import close_http_client
        await close_http_client()
        logger.info("✅ Business Central httpx client closed")
    except Exception:
        pass
    try:
        from .services.seamlesshr_service import close_shr_client
        await close_shr_client()
        logger.info("✅ SeamlessHR httpx client closed")
    except Exception:
        pass

    logger.info("✅ Shutdown complete")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Lightweight health check — used by Docker. Never blocks the event loop."""
    import os as _os
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        # Which code is actually running. Compare against `git rev-parse --short HEAD`
        # on the server to catch a pull that was never rebuilt.
        "build": _os.getenv("APP_GIT_SHA", "unknown"),
        "built_at": _os.getenv("APP_BUILD_TIME", "unknown"),
    }


@app.get("/status")
async def detailed_status():
    """Detailed status with DB/Redis checks — not used by Docker health check."""
    loop = asyncio.get_event_loop()
    try:
        db_ok = await loop.run_in_executor(None, test_db_connection)
    except Exception:
        db_ok = False
    try:
        redis_ok = await loop.run_in_executor(None, test_redis_connection)
    except Exception:
        redis_ok = False
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
