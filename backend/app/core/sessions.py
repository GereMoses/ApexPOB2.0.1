"""
Login-session tracking (Redis-backed).

One helper that EVERY login path calls after issuing a full access token, so the
Settings → Active Sessions UI can list them and revoking one actually logs the
device out. The session record stores the token's `jti` + `exp`, which is what
lets a revoke blacklist the token (not just drop the tracking row).

Keys: sessions:{user_id}:{session_id}  (a Redis hash), auto-expiring at token exp.
Never raises — session tracking must never break login.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from jose import jwt

from .config import settings
from .redis_client import get_redis_client as get_redis

logger = logging.getLogger(__name__)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except Exception:
        return {}


def audit_login(action: str, user_id: Optional[int] = None, request=None,
                ip: Optional[str] = None, remark: Optional[str] = None) -> None:
    """Write a sign-in to the audit log (base_operationlog). Nothing ever recorded
    logins, so the System > Login Log report was always empty. action is 'login' or
    'login_failed'. Best-effort: never blocks or breaks a login."""
    try:
        from sqlalchemy import text
        from .database import SessionLocal
        ua = None
        if request is not None:
            try:
                ip = (request.client.host if request.client else None) or ip
                ua = (request.headers.get("user-agent", "") or "")[:200]
            except Exception:
                pass
        db = SessionLocal()
        try:
            db.execute(text("""
                INSERT INTO base_operationlog (user_id, action, table_name, ip_address, user_agent, remark, created_at)
                VALUES (:u, :a, '/api/v1/auth', :ip, :ua, :r, NOW())
            """), {"u": user_id, "a": action, "ip": ip, "ua": ua, "r": (remark or "")[:200]})
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("audit_login(%s) failed: %s", action, e)


def record_login_session(user_id: int, token: str, request=None,
                         ip: Optional[str] = None, ua: Optional[str] = None) -> Optional[str]:
    """Record a login session for `user_id` tied to `token`'s jti. Returns the
    session_id, or None if Redis is unavailable (best-effort — never raises)."""
    audit_login("login", user_id, request, ip)
    try:
        r = get_redis()
        payload = _decode(token)
        jti = payload.get("jti", "")
        exp = int(payload.get("exp", 0))
        now = datetime.now(timezone.utc)
        ttl = max(int(exp - now.timestamp()), 60) if exp else 3600

        if request is not None:
            try:
                ip = (request.client.host if request.client else None) or ip
                ua = (request.headers.get("user-agent", "") or ua or "")[:200]
            except Exception:
                pass

        session_id = uuid.uuid4().hex
        key = f"sessions:{user_id}:{session_id}"
        r.hset(key, mapping={
            "created_at": now.isoformat(),
            "last_active": now.isoformat(),
            "ip": ip or "unknown",
            "ua": ua or "",
            "jti": jti,
            "exp": exp,
        })
        r.expire(key, ttl)
        return session_id
    except Exception as e:  # noqa: BLE001 — tracking is best-effort
        logger.warning("record_login_session failed for user %s: %s", user_id, e)
        return None
