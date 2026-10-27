"""
Settings → WhatsApp & Alerts.

WhatsApp provider + credentials (DB, secrets encrypted), the emergency response
team who receive every alert, which channels are live, a test send, and the
delivery log of every alert sent.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..services.whatsapp_config import (
    db_whatsapp_ready, get_responders, get_whatsapp_settings, save_responders, save_whatsapp_settings,
)

router = APIRouter(prefix="/api/v1/settings/alerts", tags=["Alert Settings"])
logger = logging.getLogger(__name__)


def _require_change(request: Request, user) -> None:
    perms = getattr(request.state, "user_permissions", None) or []
    if getattr(user, "is_superuser", False) or "*" in perms or "settings.change" in perms:
        return
    raise HTTPException(status_code=403, detail="You need the settings.change permission")


def _public(s: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in s.items() if k not in ("meta_access_token", "termii_api_key", "twilio_token")}
    out.update(has_meta_token=bool(s.get("meta_access_token")), has_termii_key=bool(s.get("termii_api_key")),
               has_twilio_token=bool(s.get("twilio_token")), ready=db_whatsapp_ready(s))
    return out


class WhatsAppIn(BaseModel):
    enabled: Optional[bool] = None
    provider: Optional[str] = Field(None, pattern="^(meta|termii|twilio)$")
    country_code: Optional[str] = None
    meta_phone_number_id: Optional[str] = None
    meta_access_token: Optional[str] = None
    meta_template: Optional[str] = None
    meta_template_lang: Optional[str] = None
    meta_api_version: Optional[str] = None
    termii_api_key: Optional[str] = None
    termii_sender: Optional[str] = None
    termii_base_url: Optional[str] = None
    twilio_sid: Optional[str] = None
    twilio_token: Optional[str] = None
    twilio_from: Optional[str] = None


class Responder(BaseModel):
    name: str = ""
    role: str = ""
    email: str = ""
    phone: str = ""


class TestIn(BaseModel):
    channel: str = Field(..., pattern="^(email|whatsapp|sms)$")
    address: str = Field(..., min_length=3)


@router.get("")
async def get_alert_settings(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from ..services.notify_dispatch import configured_channels
    return {"success": True, "data": {
        "whatsapp": _public(get_whatsapp_settings(db)),
        "responders": get_responders(db),
        "channels": await asyncio.to_thread(configured_channels),
    }}


@router.put("/whatsapp")
async def put_whatsapp(body: WhatsAppIn, request: Request, current_user=Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require_change(request, current_user)
    data = {k: v for k, v in body.dict().items() if v is not None}
    return {"success": True, "data": _public(save_whatsapp_settings(db, data, getattr(current_user, "username", None)))}


@router.put("/responders")
async def put_responders(body: List[Responder], request: Request, current_user=Depends(get_current_user),
                         db: Session = Depends(get_db)):
    _require_change(request, current_user)
    return {"success": True, "data": save_responders(db, [r.dict() for r in body], getattr(current_user, "username", None))}


@router.post("/test")
async def test_send(body: TestIn, request: Request, current_user=Depends(get_current_user)):
    """Send one test message on one channel and log it like a real alert."""
    _require_change(request, current_user)
    from ..services.notify_dispatch import dispatch
    person = {"name": "Test recipient", "email": body.address if body.channel == "email" else "",
              "phone": body.address if body.channel != "email" else ""}
    summary = await asyncio.to_thread(
        dispatch, "test", None, [person], "ApexPOB test alert",
        "ApexPOB test alert — if you received this, alerts on this channel are working.",
        [body.channel], False)
    res = summary.get(body.channel) or {}
    ok = bool(res.get("sent"))
    return {"success": ok, "data": res,
            "message": "Sent — check the inbox / phone." if ok else (res.get("note") or summary.get("error") or "Not sent")}


@router.get("/deliveries")
async def deliveries(source_type: Optional[str] = None, source_id: Optional[int] = None,
                     status: Optional[str] = None, limit: int = Query(200, le=1000),
                     current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    where, params = ["TRUE"], {"limit": limit}
    if source_type:
        where.append("source_type = :st"); params["st"] = source_type
    if source_id is not None:
        where.append("source_id = :sid"); params["sid"] = source_id
    if status:
        where.append("status = :status"); params["status"] = status.upper()
    rows = db.execute(text(f"""
        SELECT id, source_type, source_id, channel, recipient_name, address, status, error, subject, message,
               created_at AT TIME ZONE 'Africa/Lagos' AS created_at
        FROM notify_delivery WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT :limit
    """), params).mappings().all()
    return {"success": True, "data": [dict(r, created_at=r["created_at"].isoformat(sep=" ", timespec="seconds")) for r in rows]}
