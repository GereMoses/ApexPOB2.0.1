"""
Session Management API — view and revoke active user sessions.

Revoking a session doesn't just drop its tracking row — it blacklists the
session's token `jti`, so the device is actually logged out on its next request
(get_current_user rejects blacklisted jtis). Sessions are recorded on every login
path via app.core.sessions.record_login_session.
"""
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db
from ..core.config import settings
from ..core.dependencies import get_current_user
from ..core.redis_client import get_redis_client as get_redis
from ..core.security import blacklist_token

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


def _current_jti(request: Request) -> str:
    """jti of the token making THIS request, so the UI can flag the current device."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return ""
    try:
        payload = jwt.decode(auth[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("jti", "") or ""
    except Exception:
        return ""


def _blacklist_from_hash(data: dict) -> None:
    """Blacklist a session's token using the jti+exp stored on its hash."""
    jti = (data or {}).get("jti", "")
    if not jti:
        return
    try:
        exp = int((data or {}).get("exp", 0))
    except (TypeError, ValueError):
        exp = 0
    ttl = max(exp - int(time.time()), 1) if exp else 7 * 24 * 3600
    blacklist_token(jti, ttl)


@router.get("/")
async def list_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return all active sessions for the current user from Redis."""
    cur_jti = _current_jti(request)
    try:
        r = get_redis()
        keys = r.keys(f"sessions:{current_user.id}:*")
        sessions = []
        for key in keys:
            data = r.hgetall(key)
            if not data:
                continue
            sessions.append({
                "session_id": str(key).split(":")[-1],
                "created_at":  data.get("created_at", ""),
                "last_active": data.get("last_active", ""),
                "ip_address":  data.get("ip", ""),
                "user_agent":  data.get("ua", ""),
                "current":     bool(cur_jti) and data.get("jti", "") == cur_jti,
            })
        # Newest first
        sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return {"sessions": sessions, "count": len(sessions)}
    except Exception:
        rows = db.execute(text("""
            SELECT id, created_at, created_at AS last_active, ip_address, device_info AS user_agent, is_active
            FROM user_sessions WHERE user_id = :uid AND is_active = true
            ORDER BY created_at DESC LIMIT 20
        """), {"uid": current_user.id}).fetchall()
        return {"sessions": [dict(r._mapping) for r in rows], "count": len(rows)}


@router.delete("/{session_id}")
async def revoke_session(
    session_id: str,
    current_user=Depends(get_current_user),
):
    """Revoke a specific session — blacklists its token then removes the record,
    so the device is logged out on its next request."""
    try:
        r = get_redis()
        key = f"sessions:{current_user.id}:{session_id}"
        data = r.hgetall(key)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        _blacklist_from_hash(data)
        r.delete(key)
        return {"success": True, "message": "Session revoked"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def revoke_all_sessions(
    current_user=Depends(get_current_user),
):
    """Revoke ALL sessions for the current user (log out everywhere)."""
    try:
        r = get_redis()
        keys = r.keys(f"sessions:{current_user.id}:*")
        for key in keys:
            try:
                _blacklist_from_hash(r.hgetall(key))
            except Exception:
                pass
        if keys:
            r.delete(*keys)
        return {"success": True, "revoked": len(keys)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def list_all_sessions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Admin: list active sessions for all users."""
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Admin only")
    rows = db.execute(text("""
        SELECT us.id, us.user_id, u.username, us.created_at,
               us.created_at AS last_active, us.ip_address, us.is_active
        FROM user_sessions us
        LEFT JOIN auth_user u ON u.id = us.user_id
        WHERE us.is_active = true
        ORDER BY us.created_at DESC LIMIT 100
    """)).fetchall()
    return {"sessions": [dict(r._mapping) for r in rows], "count": len(rows)}
