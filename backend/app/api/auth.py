from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import text
from typing import Any
import logging
import time
import uuid

from ..core.database import get_db
from ..core.security import create_access_token, verify_password, get_password_hash
from ..core.config import settings
from ..core.dependencies import get_current_user
from ..core.redis_client import get_redis_client as get_redis
from ..core.sessions import record_login_session
from ..schemas.auth import Token, UserCreate, UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_ATTEMPTS  = 5      # lockout after N consecutive failures
LOCKOUT_SECS  = 900    # 15-minute lockout window
ATTEMPT_TTL   = 1800   # attempt counter TTL (30 min)
IP_MAX_ATTEMPTS = 30   # per-IP failure ceiling (catches spray across many usernames)

# Pre-computed bcrypt hash of a random string. Used to burn ~the same CPU time on
# a non-existent user as on a real one, so response latency does not reveal whether
# a username exists (user-enumeration defense). Generated once at import.
_DUMMY_HASH = get_password_hash("timing-equalizer-not-a-real-password")


def _burn_password_time() -> None:
    """Run a throwaway bcrypt verify to equalize timing for unknown users."""
    try:
        verify_password("x", _DUMMY_HASH)
    except Exception:
        pass


def _lockout_key(username: str) -> str:
    return f"login_lockout:{username.lower()}"

def _attempt_key(username: str) -> str:
    return f"login_attempts:{username.lower()}"

def _ip_attempt_key(ip: str) -> str:
    return f"login_attempts_ip:{ip}"

def _client_ip(request: Request) -> str:
    """Spoof-resistant client IP — trust only headers our nginx sets (see rate_limiter).

    X-Real-IP is overwritten by nginx with the true peer; the rightmost X-Forwarded-For
    token is appended by nginx. Both resist client spoofing for the nginx→backend topology.
    """
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"

def _check_lockout(username: str, ip: str = None) -> None:
    """Raise 429 if this account OR this source IP is currently locked out.

    IP-scoped locking catches credential-spray (many usernames from one IP) that
    the username-only counter misses, while the username counter still protects a
    single account from distributed guessing.
    """
    try:
        r = get_redis()
        keys = [_lockout_key(username)]
        if ip:
            keys.append(f"login_lockout_ip:{ip}")
        for k in keys:
            locked_until = r.get(k)
            if locked_until:
                remaining = int(locked_until) - int(time.time())
                if remaining > 0:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Too many failed attempts. Try again in {remaining // 60}m {remaining % 60}s.",
                        headers={"Retry-After": str(remaining)},
                    )
    except HTTPException:
        raise
    except Exception as e:
        # Redis unavailable — fail open, but make the degradation LOUD so ops can
        # see that brute-force protection is currently disabled.
        logger.error("Login lockout backend unavailable — brute-force protection DEGRADED: %s", e)

def _record_failed(username: str, ip: str = None) -> None:
    """Increment failure counters (per-username and per-IP); lock out on threshold."""
    from ..core.sessions import audit_login
    audit_login("login_failed", None, None, ip, remark=f"username: {username}")
    try:
        r = get_redis()
        key = _attempt_key(username)
        attempts = r.incr(key)
        r.expire(key, ATTEMPT_TTL)
        logger.warning("Failed login attempt %s/%s for %s (ip=%s)", attempts, MAX_ATTEMPTS, username, ip)
        if attempts >= MAX_ATTEMPTS:
            lock_until = int(time.time()) + LOCKOUT_SECS
            r.set(_lockout_key(username), lock_until, ex=LOCKOUT_SECS)
            logger.warning("Account %s locked out for %s seconds", username, LOCKOUT_SECS)

        if ip:
            ip_key = _ip_attempt_key(ip)
            ip_attempts = r.incr(ip_key)
            r.expire(ip_key, ATTEMPT_TTL)
            if ip_attempts >= IP_MAX_ATTEMPTS:
                lock_until = int(time.time()) + LOCKOUT_SECS
                r.set(f"login_lockout_ip:{ip}", lock_until, ex=LOCKOUT_SECS)
                logger.warning("Source IP %s locked out for %s seconds (%s failures)",
                               ip, LOCKOUT_SECS, ip_attempts)
    except Exception as e:
        logger.error("Could not record failed login (lockout backend down): %s", e)

def _clear_failed(username: str, ip: str = None) -> None:
    """Clear failure counters on successful login."""
    try:
        r = get_redis()
        r.delete(_attempt_key(username))
        r.delete(_lockout_key(username))
        if ip:
            r.delete(_ip_attempt_key(ip))
    except Exception:
        pass


def _get_user_auth_info(db, user_id: int):
    """Return (roles: list[str], permissions: list[str]) for a user."""
    rows = db.execute(text("""
        SELECT DISTINCT r.name AS role_name, p.codename
        FROM auth_user_role ur
        JOIN auth_role r ON r.id = ur.role_id AND r.is_active = true
        LEFT JOIN auth_role_permission rp ON rp.role_id = r.id
        LEFT JOIN auth_permission p ON p.id = rp.permission_id
        WHERE ur.user_id = :uid
    """), {"uid": user_id}).fetchall()
    roles       = list({row.role_name for row in rows if row.role_name})
    permissions = list({row.codename  for row in rows if row.codename})
    return roles, permissions

_FALLBACK_TIMEOUT  = 480    # 8 hours
_MAX_SESSION_MINS  = 10080  # 7 days hard ceiling

def _get_session_timeout(db: Session) -> int:
    """Read session_timeout_minutes from att_rules, capped at 7 days."""
    try:
        row = db.execute(text("SELECT rule_value FROM att_rules WHERE rule_key = 'session_timeout_minutes'")).fetchone()
        mins = int(row.rule_value) if row and row.rule_value else _FALLBACK_TIMEOUT
        if mins == 0:
            return _MAX_SESSION_MINS  # treat 0 = "never" as the maximum allowed
        return max(1, min(mins, _MAX_SESSION_MINS))
    except Exception:
        db.rollback()   # rollback so caller's session stays usable
        return _FALLBACK_TIMEOUT


def _mfa_pending_if_enabled(db: Session, user_id: int, sub: str, client_ip: str = None):
    """If this account has TOTP 2FA enabled, return the short-lived mfa_pending
    response the client must exchange at /api/v1/mfa/verify; otherwise None.

    Every login path calls this AFTER a correct password so a valid password alone
    can never mint a full session token when 2FA is on — closing the bypass where
    an attacker used an alternate login endpoint to skip the second factor.
    """
    try:
        row = db.execute(text(
            "SELECT COALESCE(totp_enabled, FALSE) FROM auth_user WHERE id = :uid"
        ), {"uid": user_id}).fetchone()
        totp_enabled = bool(row[0]) if row else False
    except Exception:
        db.rollback()   # totp column may not exist yet — treat as disabled, keep session usable
        totp_enabled = False

    if not totp_enabled:
        return None

    mfa_token = create_access_token(
        data={"sub": sub, "mfa_pending": True},
        expires_delta=timedelta(minutes=5),
    )
    _clear_failed(sub, client_ip)
    return {
        "access_token": mfa_token,
        "token_type": "bearer",
        "mfa_required": True,
        "message": "MFA verification required. Submit your TOTP code to /api/v1/mfa/verify.",
    }


@router.post("/production-login", response_model=dict)
async def production_login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Production-ready login endpoint with robust error handling and account lockout."""
    client_ip = _client_ip(request)
    _check_lockout(form_data.username, client_ip)
    try:
        logger.info("Login attempt received")

        # Query user directly with SQL
        query = text("""
            SELECT id, username, email, password, is_active, is_superuser,
                   COALESCE(is_global_admin, FALSE) AS is_global_admin
            FROM auth_user
            WHERE username = :username OR email = :username
        """)

        result = db.execute(query, {"username": form_data.username})
        user_data = result.fetchone()

        if not user_data:
            logger.warning("Failed login: user not found")
            # Burn equivalent bcrypt time so response latency does not reveal that
            # the username is unknown (user-enumeration defense).
            _burn_password_time()
            _record_failed(form_data.username, client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Verify password
        password_valid = False
        try:
            password_valid = verify_password(form_data.password, user_data.password)
        except Exception as bcrypt_error:
            logger.error("Password verification error: %s", type(bcrypt_error).__name__)

        if not password_valid:
            logger.warning("Failed login: invalid password")
            _record_failed(form_data.username, client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        if not user_data.is_active:
            logger.warning(f"Inactive user login attempt: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive"
            )
        
        # 2FA gate — if enabled, hand back a short-lived pending token that must be
        # exchanged at /api/v1/mfa/verify with a valid TOTP code.
        _mfa = _mfa_pending_if_enabled(db, user_data.id, user_data.username, client_ip)
        if _mfa:
            return _mfa

        # Create access token using DB-configured timeout
        timeout_mins = _get_session_timeout(db)
        access_token_expires = timedelta(minutes=timeout_mins)
        access_token = create_access_token(
            data={"sub": user_data.username},
            expires_delta=access_token_expires
        )

        _clear_failed(form_data.username, client_ip)
        logger.info("Successful login for user: %s", user_data.username)

        # Track session in Redis (with the token jti) so the session-management UI
        # can list it and revoking it actually invalidates the token.
        record_login_session(user_data.id, access_token, request)

        roles, permissions = _get_user_auth_info(db, user_data.id)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": timeout_mins * 60,
            "user": {
                "id": user_data.id,
                "username": user_data.username,
                "email": user_data.email,
                "is_active": user_data.is_active,
                "is_superuser": user_data.is_superuser,
                "is_global_admin": bool(user_data.is_global_admin),
                "roles": roles,
                "permissions": permissions,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Production login error: {type(e).__name__}: {str(e)}")
        logger.error(f"Production login error details: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login service temporarily unavailable"
        )

@router.post("/simple-login", response_model=dict)
async def simple_login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Dev-only login endpoint — shared brute-force lockout with production-login.

    Disabled in production so it can never be used to sidestep the hardened
    production-login flow; the React app uses production-login when deployed.
    """
    if str(getattr(settings, "ENVIRONMENT", "development")).lower() == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        _check_lockout(form_data.username)

        query = text("""
            SELECT id, username, email, password, is_active, is_superuser,
                   COALESCE(is_global_admin, FALSE) AS is_global_admin
            FROM auth_user
            WHERE username = :username OR email = :username
        """)

        result = db.execute(query, {"username": form_data.username})
        user_data = result.fetchone()

        if not user_data or not verify_password(form_data.password, user_data.password):
            _record_failed(form_data.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if not user_data.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive"
            )

        # 2FA gate — never issue a full token on password alone when TOTP is on.
        _mfa = _mfa_pending_if_enabled(db, user_data.id, user_data.username)
        if _mfa:
            _clear_failed(form_data.username)
            return _mfa

        _clear_failed(form_data.username)

        # Create access token using DB-configured timeout
        timeout_mins = _get_session_timeout(db)
        access_token_expires = timedelta(minutes=timeout_mins)
        access_token = create_access_token(
            data={"sub": user_data.username},
            expires_delta=access_token_expires
        )

        # Track session (with jti) so it appears in Active Sessions and is revocable.
        record_login_session(user_data.id, access_token, request)

        roles, permissions = _get_user_auth_info(db, user_data.id)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": timeout_mins * 60,
            "user": {
                "id": user_data.id,
                "username": user_data.username,
                "email": user_data.email,
                "is_active": user_data.is_active,
                "is_superuser": user_data.is_superuser,
                "is_global_admin": bool(user_data.is_global_admin),
                "roles": roles,
                "permissions": permissions,
            }
        }
    except Exception as e:
        logger.error(f"Simple login error: {type(e).__name__}: {str(e)}")
        logger.error(f"Simple login error details: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {str(e)}"
        )
#     db.refresh(user)
#     
#     return user


@router.post("/login", response_model=dict)
async def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """Authenticate user and return access token (or an mfa_pending response)."""
    try:
        # Use raw SQL to find user
        query = text("""
            SELECT id, username, email, password, is_active, is_superuser,
                   first_name, last_name, COALESCE(is_global_admin, FALSE) AS is_global_admin
            FROM auth_user
            WHERE username = :username OR email = :username
        """)
        
        result = db.execute(query, {"username": form_data.username})
        user_data = result.fetchone()
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id, username, email, password, is_active, is_superuser, first_name, last_name, is_global_admin = user_data
        
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        # Verify password
        if not verify_password(form_data.password, password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 2FA gate — never issue a full token on password alone when TOTP is on.
        _mfa = _mfa_pending_if_enabled(db, user_id, username)
        if _mfa:
            return _mfa

        # Create access token using DB-configured timeout
        timeout_mins = _get_session_timeout(db)
        access_token_expires = timedelta(minutes=timeout_mins)
        access_token = create_access_token(
            data={"sub": email}, expires_delta=access_token_expires
        )

        # Track session (with jti) so it appears in Active Sessions and is revocable.
        record_login_session(user_id, access_token, request)

        # Update last login
        update_query = text("UPDATE auth_user SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id")
        db.execute(update_query, {"user_id": user_id})
        db.commit()

        roles, permissions = _get_user_auth_info(db, user_id)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": timeout_mins * 60,
            "user": {
                "id": user_id,
                "username": username,
                "email": email,
                "is_active": is_active,
                "is_superuser": is_superuser,
                "is_global_admin": bool(is_global_admin),
                "first_name": first_name or username,
                "last_name": last_name or "",
                "roles": roles,
                "permissions": permissions,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("simple_login error: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login service temporarily unavailable",
        )


@router.get("/me")
async def get_current_user_info(
    current_user = Depends(get_current_user)
) -> Any:
    """Get current user information"""
    try:
        from ..core.database import SessionLocal
        _db = SessionLocal()
        try:
            roles, permissions = _get_user_auth_info(_db, current_user.id)
        finally:
            _db.close()
        return {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "phone": current_user.phone,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "is_verified": current_user.is_verified,
            "is_global_admin": bool(getattr(current_user, "is_global_admin", False)),
            "roles": roles,
            "permissions": permissions,
        }
        
    except Exception as e:
        logger.error("Get current user error: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user info"
        )


@router.post("/logout")
async def logout(
    request: Request,
    current_user=Depends(get_current_user),
) -> Any:
    """
    Revoke the current access token by adding its jti to the Redis blacklist.
    Also removes the session tracking key so the Sessions UI reflects the logout.
    """
    from ..core.security import blacklist_token
    from jose import jwt as _jwt, JWTError as _JWTError

    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

    if token:
        try:
            payload = _jwt.decode(
                token, settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},  # blacklist even if already expired
            )
            jti = payload.get("jti", "")
            exp = payload.get("exp", 0)
            if jti:
                remaining = max(int(exp) - int(time.time()), 1)
                blacklist_token(jti, remaining)
        except _JWTError:
            pass  # malformed token — nothing to revoke

    # Remove session tracking key from Redis
    try:
        r = get_redis()
        # Sessions are stored as sessions:{user_id}:{uuid}; scan and remove matching user's keys
        pattern = f"sessions:{current_user.id}:*"
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=100)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        pass

    return {"message": "Successfully logged out"}


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Sliding-session refresh: present a valid access token and receive a new one
    with a full, fresh expiry. The old token remains valid until it expires
    (allows multiple browser tabs to refresh concurrently without conflict).

    Called proactively by the frontend every 30 minutes so active sessions
    never time out. If the token is already expired this returns 401 and the
    client must re-authenticate.
    """
    from jose import jwt as _jwt, JWTError as _JWTError
    from ..core.security import _is_blacklisted

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = auth_header[7:]

    try:
        payload = _jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except _JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired or invalid")

    # Only genuine access/refresh tokens may be exchanged for a new session.
    # Rejects password-reset tokens (which carry a valid sub=email) being
    # replayed here to mint an access token.
    if payload.get("type") not in ("access", "refresh"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    jti = payload.get("jti", "")
    if jti and _is_blacklisted(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # Look up the user to confirm the account is still active
    user_row = db.execute(
        text("SELECT id, username, is_active FROM auth_user WHERE username = :s OR email = :s"),
        {"s": subject},
    ).fetchone()
    if not user_row or not user_row.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    timeout_mins = _get_session_timeout(db)
    new_token = create_access_token(
        data={"sub": subject},
        expires_delta=timedelta(minutes=timeout_mins),
    )

    # Refresh the session tracking TTL in Redis
    try:
        r = get_redis()
        pattern = f"sessions:{user_row.id}:*"
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=100)
            for key in keys:
                r.expire(key, timeout_mins * 60)
                r.hset(key, "last_active", datetime.now(timezone.utc).isoformat())
            if cursor == 0:
                break
    except Exception:
        pass

    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": timeout_mins * 60,
    }


@router.post("/sse-ticket")
async def create_sse_ticket(
    current_user=Depends(get_current_user),
) -> dict:
    """
    Issue a short-lived (30 s), single-use SSE ticket.
    The ticket is stored in Redis; SSE endpoints accept it via ?ticket= instead of
    a long-lived JWT in the URL — this keeps the full token out of server logs.
    """
    try:
        r = get_redis()
        ticket = uuid.uuid4().hex
        # Map ticket → user_id; 30-second TTL is enough for the browser to open the EventSource
        r.setex(f"sse_ticket:{ticket}", 30, str(current_user.id))
        return {"ticket": ticket}
    except Exception:
        raise HTTPException(status_code=503, detail="Ticket service unavailable")
