"""
WhatsApp + alerting configuration — DB-backed (Settings → WhatsApp & Alerts), so a
deployment is switched on from the UI, never from backend env.

Stored in sys_parameters (module "notification"):
  whatsapp.*          provider + credentials (secrets encrypted at rest)
  alerts.responders   JSON list of the emergency response team — people who get
                      every muster / emergency / escalation alert whether or not
                      they are on board: [{"name", "role", "email", "phone"}]
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..core.crypto import decrypt_secret, encrypt_secret
from ..models.system import SystemParameter

logger = logging.getLogger(__name__)

_MODULE = "notification"
_PREFIX = "whatsapp."

# key -> (is_secret, is_bool, default)
_FIELDS: Dict[str, tuple] = {
    "enabled": (False, True, False),
    "provider": (False, False, "meta"),            # meta | termii | twilio | generic
    "country_code": (False, False, "234"),         # prepended to local 0-numbers
    # Meta WhatsApp Cloud API (official)
    "meta_phone_number_id": (False, False, ""),
    "meta_access_token": (True, False, ""),
    "meta_template": (False, False, ""),           # approved template with ONE body variable {{1}}
    "meta_template_lang": (False, False, "en"),
    "meta_api_version": (False, False, "v21.0"),
    # Termii (Nigeria)
    "termii_api_key": (True, False, ""),
    "termii_sender": (False, False, ""),
    "termii_base_url": (False, False, "https://api.ng.termii.com"),
    # Twilio
    "twilio_sid": (False, False, ""),
    "twilio_token": (True, False, ""),
    "twilio_from": (False, False, ""),             # e.g. +14155238886
}


def get_whatsapp_settings(db: Session) -> Dict[str, Any]:
    rows = db.query(SystemParameter).filter(SystemParameter.param_key.like(f"{_PREFIX}%")).all()
    stored = {r.param_key[len(_PREFIX):]: r.param_value for r in rows}
    out: Dict[str, Any] = {}
    for key, (is_secret, is_bool, default) in _FIELDS.items():
        raw = stored.get(key)
        if raw is None:
            out[key] = default
        elif is_secret:
            out[key] = decrypt_secret(raw)
        elif is_bool:
            out[key] = str(raw).lower() in ("true", "1", "yes", "on")
        else:
            out[key] = raw
    return out


def save_whatsapp_settings(db: Session, data: Dict[str, Any], updated_by: str = None) -> Dict[str, Any]:
    """Upsert. A blank secret keeps the stored one (the UI never receives secrets)."""
    for key, value in data.items():
        if key not in _FIELDS:
            continue
        is_secret, is_bool, _ = _FIELDS[key]
        if is_secret and (value is None or value == ""):
            continue
        if is_bool:
            val = "true" if (value is True or str(value).lower() in ("true", "1", "yes", "on")) else "false"
        elif is_secret:
            val = encrypt_secret(str(value).strip())
        else:
            val = "" if value is None else str(value).strip()
        _upsert(db, _PREFIX + key, val, is_secret, updated_by, "WhatsApp configuration")
    db.commit()
    return get_whatsapp_settings(db)


def db_whatsapp_ready(s: Dict[str, Any]) -> bool:
    """True when the stored settings are switched on and complete for their provider."""
    if not s.get("enabled"):
        return False
    p = s.get("provider")
    if p == "meta":
        return bool(s.get("meta_phone_number_id") and s.get("meta_access_token"))
    if p == "termii":
        return bool(s.get("termii_api_key") and s.get("termii_sender"))
    if p == "twilio":
        return bool(s.get("twilio_sid") and s.get("twilio_token") and s.get("twilio_from"))
    return False


# ── Emergency response team ─────────────────────────────────────────────────

_RESPONDERS = "alerts.responders"


def get_responders(db: Session) -> List[Dict[str, str]]:
    row = db.query(SystemParameter).filter(SystemParameter.param_key == _RESPONDERS).first()
    try:
        data = json.loads(row.param_value) if row and row.param_value else []
    except Exception:
        data = []
    return [r for r in data if isinstance(r, dict)]


def save_responders(db: Session, responders: List[Dict[str, Any]], updated_by: str = None) -> List[Dict[str, str]]:
    clean = []
    for r in responders or []:
        name = str(r.get("name") or "").strip()
        email = str(r.get("email") or "").strip()
        phone = str(r.get("phone") or "").strip()
        if not (email or phone or r.get("telegram_chat_id") or name):
            continue
        item = {"name": name or email or phone, "role": str(r.get("role") or "").strip(),
                "email": email, "phone": phone}
        if r.get("telegram_chat_id"):
            item["telegram_chat_id"] = str(r["telegram_chat_id"])
        clean.append(item)
    _upsert(db, _RESPONDERS, json.dumps(clean), False, updated_by, "Emergency response team (always alerted)")
    db.commit()
    return clean


def _upsert(db: Session, key: str, value: str, is_secret: bool, updated_by: str, desc: str):
    p = db.query(SystemParameter).filter(SystemParameter.param_key == key).first()
    if p:
        p.param_value = value
        p.is_encrypted = is_secret
        if updated_by:
            p.updated_by = updated_by
    else:
        db.add(SystemParameter(param_key=key, param_value=value, param_type="string", module=_MODULE,
                               description=f"{desc}: {key}", is_public=False, is_encrypted=is_secret,
                               updated_by=updated_by))
