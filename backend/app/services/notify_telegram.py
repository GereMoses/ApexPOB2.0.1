"""
Telegram alerts through a bot (Settings → WhatsApp & Alerts → Telegram).

* Setup: create a bot with @BotFather, paste its token. ApexPOB checks it (getMe).
* People: a bot cannot message a phone number — each person presses **Start** on the
  bot once, through their personal link  t.me/<bot>?start=<code>. That links their
  Telegram chat to their staff record (personnel.telegram_chat_id) or to a response-
  team entry. Links can be emailed to staff in bulk.
* Groups: add the bot to a Telegram group (e.g. "Marconi ERT"); ApexPOB sees it and
  the admin ticks it as a TEAM group — team alerts then go to the whole group.
* No inbound connection is needed: ApexPOB POLLS Telegram (getUpdates) every few
  seconds, which works from a LAN server with no public address.

Never raises from send_telegram — returns {"sent", "failed", "errors"?, "error"?}.
"""
from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Dict, Iterable, List, Optional, Union

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"
_P = "telegram."


# ── settings ──────────────────────────────────────────────────────────────────

def _param(db: Session, key: str) -> Optional[str]:
    return db.execute(text("SELECT param_value FROM sys_parameters WHERE param_key = :k"), {"k": _P + key}).scalar()


def _set(db: Session, key: str, value: str, secret: bool = False) -> None:
    from ..core.crypto import encrypt_secret
    v = encrypt_secret(value) if (secret and value) else value
    db.execute(text("""
        INSERT INTO sys_parameters (param_key, param_value, param_type, module, description, is_public, is_encrypted)
        VALUES (:k, :v, 'string', 'notification', :d, FALSE, :e)
        ON CONFLICT (param_key) DO UPDATE SET param_value = EXCLUDED.param_value, is_encrypted = EXCLUDED.is_encrypted
    """), {"k": _P + key, "v": v, "d": f"Telegram: {key}", "e": secret})


def get_settings(db: Session) -> Dict[str, Any]:
    from ..core.crypto import decrypt_secret
    tok = _param(db, "bot_token") or ""
    try:
        groups = json.loads(_param(db, "groups") or "[]")
    except Exception:
        groups = []
    return {"enabled": (_param(db, "enabled") or "false") == "true",
            "bot_token": decrypt_secret(tok) if tok else "",
            "bot_username": _param(db, "bot_username") or "",
            "groups": [g for g in groups if isinstance(g, dict)]}


def save_settings(db: Session, enabled: Optional[bool] = None, bot_token: Optional[str] = None) -> Dict[str, Any]:
    """Store settings. A new token is checked with Telegram first (getMe)."""
    if bot_token:
        me = call(bot_token.strip(), "getMe")
        if not me.get("ok"):
            raise ValueError(f"Telegram did not accept that bot token: {me.get('description') or 'unknown error'}")
        _set(db, "bot_token", bot_token.strip(), secret=True)
        _set(db, "bot_username", me["result"].get("username", ""))
        _set(db, "offset", "0")
    if enabled is not None:
        _set(db, "enabled", "true" if enabled else "false")
    db.commit()
    return get_settings(db)


def save_groups(db: Session, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    _set(db, "groups", json.dumps(groups))
    db.commit()
    return groups


def _ready(s: Dict[str, Any]) -> bool:
    return bool(s.get("enabled") and s.get("bot_token"))


def telegram_configured() -> bool:
    from ..core.database import SessionLocal
    db = SessionLocal()
    try:
        return _ready(get_settings(db))
    except Exception:
        return False
    finally:
        db.close()


# ── Bot API ───────────────────────────────────────────────────────────────────

def call(token: str, method: str, payload: Optional[dict] = None, timeout: float = 15) -> Dict[str, Any]:
    import requests
    try:
        r = requests.post(API.format(token=token, method=method), json=payload or {}, timeout=timeout)
        return r.json() if r.content else {"ok": False, "description": f"HTTP {r.status_code}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "description": str(e)}


def send_telegram(chat_ids: Union[str, Iterable[str]], message: str) -> Dict[str, Any]:
    from ..core.database import SessionLocal
    ids = [chat_ids] if isinstance(chat_ids, (str, int)) else list(chat_ids)
    ids = list(dict.fromkeys(str(c).strip() for c in ids if str(c).strip()))
    if not ids:
        return {"sent": 0, "failed": [], "error": "nobody has linked Telegram"}
    db = SessionLocal()
    try:
        s = get_settings(db)
    finally:
        db.close()
    if not _ready(s):
        return {"sent": 0, "failed": ids, "error": "Telegram is not set up — Settings → WhatsApp & Alerts"}

    def one(cid: str) -> Optional[str]:
        res = call(s["bot_token"], "sendMessage", {"chat_id": cid, "text": message[:4000],
                                                    "disable_web_page_preview": True})
        if res.get("ok"):
            return None
        d = res.get("description") or "failed"
        if res.get("error_code") == 403:
            d += " — the person blocked the bot or never pressed Start"
        return d

    from concurrent.futures import ThreadPoolExecutor
    failed, errors = [], {}
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(ids)))) as pool:
        for cid, err in zip(ids, pool.map(one, ids)):
            if err:
                failed.append(cid)
                errors[cid] = err
    out: Dict[str, Any] = {"sent": len(ids) - len(failed), "failed": failed}
    if errors:
        out["errors"] = errors
        if not out["sent"]:
            out["error"] = next(iter(errors.values()))
    logger.info("notify_telegram: sent %d, failed %d", out["sent"], len(failed))
    return out


# ── linking people ────────────────────────────────────────────────────────────

def link_url(db: Session, emp_code: Optional[str] = None, responder_key: Optional[str] = None) -> str:
    s = get_settings(db)
    if not s.get("bot_username"):
        raise ValueError("Set up the Telegram bot first")
    code = secrets.token_urlsafe(12)[:16]
    db.execute(text("INSERT INTO telegram_link (code, emp_code, responder_key) VALUES (:c, :e, :r)"),
               {"c": code, "e": emp_code, "r": responder_key})
    db.commit()
    return f"https://t.me/{s['bot_username']}?start={code}"


def responder_key(r: Dict[str, Any]) -> str:
    return (r.get("email") or r.get("phone") or r.get("name") or "").strip().lower()


def _link(db: Session, code: str, chat_id: int) -> Optional[str]:
    """Attach a chat to the person/responder behind a link code. Returns their name."""
    row = db.execute(text("SELECT emp_code, responder_key, used_at FROM telegram_link WHERE code = :c"), {"c": code}).fetchone()
    if not row:
        return None
    name = None
    if row.emp_code:
        name = db.execute(text("""UPDATE personnel SET telegram_chat_id = :cid WHERE emp_code = :e AND is_active
                                  RETURNING COALESCE(NULLIF(full_name, ''), emp_code)"""),
                          {"cid": chat_id, "e": row.emp_code}).scalar()
    elif row.responder_key:
        from .whatsapp_config import get_responders, save_responders
        team = get_responders(db)
        for r in team:
            if responder_key(r) == row.responder_key:
                r["telegram_chat_id"] = str(chat_id)
                name = r.get("name")
        if name:
            save_responders(db, team)
    if name:
        db.execute(text("UPDATE telegram_link SET used_at = NOW(), chat_id = :cid WHERE code = :c"), {"cid": chat_id, "c": code})
    db.commit()
    return name


def poll_once(db: Session) -> Dict[str, int]:
    """Read new bot updates: /start <code> links a person; being added to a group
    records the group (the admin then ticks it as a team group)."""
    s = get_settings(db)
    if not _ready(s):
        return {"updates": 0}
    offset = int(_param(db, "offset") or 0)
    res = call(s["bot_token"], "getUpdates", {"offset": offset, "timeout": 0,
                                              "allowed_updates": ["message", "my_chat_member"]})
    if not res.get("ok"):
        logger.warning("Telegram getUpdates failed: %s", res.get("description"))
        return {"updates": 0}
    linked = groups_added = 0
    groups = {str(g["chat_id"]): g for g in s["groups"]}
    for u in res.get("result", []):
        offset = max(offset, u["update_id"] + 1)
        chat = ((u.get("message") or {}).get("chat")) or ((u.get("my_chat_member") or {}).get("chat")) or {}
        ctype, cid = chat.get("type"), chat.get("id")
        if ctype in ("group", "supergroup") and cid is not None:
            status = ((u.get("my_chat_member") or {}).get("new_chat_member") or {}).get("status")
            if status in ("left", "kicked"):
                groups.pop(str(cid), None)
            elif str(cid) not in groups:
                groups[str(cid)] = {"chat_id": str(cid), "title": chat.get("title") or str(cid), "team": False}
                groups_added += 1
            continue
        txt = ((u.get("message") or {}).get("text") or "").strip()
        if ctype == "private" and txt.startswith("/start"):
            parts = txt.split(maxsplit=1)
            name = _link(db, parts[1].strip(), cid) if len(parts) > 1 else None
            reply = (f"✅ Linked to ApexPOB as {name}. Site alerts (musters, emergencies, all-clear) will come here."
                     if name else "This link is not valid any more — ask your ApexPOB administrator for a new one.")
            call(s["bot_token"], "sendMessage", {"chat_id": cid, "text": reply})
            linked += 1 if name else 0
    _set(db, "offset", str(offset))
    if groups_added or len(groups) != len(s["groups"]):
        _set(db, "groups", json.dumps(list(groups.values())))
    db.commit()
    return {"updates": len(res.get("result", [])), "linked": linked, "groups_added": groups_added}


async def telegram_poll_loop() -> None:
    """Leader-only background loop: check the bot for Start presses / groups every 5 s."""
    import asyncio
    from ..core.database import SessionLocal

    def tick():
        db = SessionLocal()
        try:
            return poll_once(db)
        finally:
            db.close()
    while True:
        try:
            if await asyncio.to_thread(telegram_configured):
                await asyncio.to_thread(tick)
        except Exception as e:  # noqa: BLE001
            logger.warning("Telegram poll error: %s", e)
        await asyncio.sleep(5)
