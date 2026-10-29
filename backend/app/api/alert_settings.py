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
    provider: Optional[str] = Field(None, pattern="^(meta|linked|termii|twilio)$")
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


# ── WhatsApp through one linked phone (QR pairing, services/whatsapp_link.py) ─

class LinkIn(BaseModel):
    phone: Optional[str] = None      # set → 8-character pairing code instead of a QR


@router.get("/whatsapp/link")
async def whatsapp_link_status(current_user=Depends(get_current_user)):
    from ..services import whatsapp_link
    return {"success": True, "data": await asyncio.to_thread(whatsapp_link.status)}


@router.post("/whatsapp/link")
async def whatsapp_link_start(body: LinkIn, request: Request, current_user=Depends(get_current_user),
                              db: Session = Depends(get_db)):
    _require_change(request, current_user)
    from ..services import whatsapp_link
    from ..services.notify_sms import normalize_msisdn
    phone = None
    if body.phone and body.phone.strip():
        phone = normalize_msisdn(body.phone, str(get_whatsapp_settings(db).get("country_code") or "234"))
    try:
        return {"success": True, "data": await asyncio.to_thread(whatsapp_link.start_link, phone)}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/whatsapp/link")
async def whatsapp_unlink(request: Request, current_user=Depends(get_current_user)):
    _require_change(request, current_user)
    from ..services import whatsapp_link
    try:
        await asyncio.to_thread(whatsapp_link.unlink)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"success": True, "message": "Phone unlinked"}


class Responder(BaseModel):
    name: str = ""
    role: str = ""
    email: str = ""
    phone: str = ""
    telegram_chat_id: Optional[str] = None


class TestIn(BaseModel):
    channel: str = Field(..., pattern="^(email|whatsapp|sms|telegram)$")
    address: str = Field(..., min_length=3)


@router.get("")
async def get_alert_settings(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from ..services.notify_dispatch import configured_channels
    return {"success": True, "data": {
        "whatsapp": _public(get_whatsapp_settings(db)),
        "responders": get_responders(db),
        "telegram": _telegram_public(db),
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
              "phone": body.address if body.channel in ("whatsapp", "sms") else "",
              "telegram": body.address if body.channel == "telegram" else ""}
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



# ── Telegram ──────────────────────────────────────────────────────────────────

def _telegram_public(db: Session) -> Dict[str, Any]:
    from ..services.notify_telegram import get_settings
    t = get_settings(db)
    linked = db.execute(text("SELECT count(*) FROM personnel WHERE is_active AND telegram_chat_id IS NOT NULL")).scalar() or 0
    return {"enabled": t["enabled"], "has_token": bool(t["bot_token"]), "bot_username": t["bot_username"],
            "ready": bool(t["enabled"] and t["bot_token"]), "groups": t["groups"], "linked_people": linked}


class TelegramIn(BaseModel):
    enabled: Optional[bool] = None
    bot_token: Optional[str] = None


class TelegramGroupIn(BaseModel):
    chat_id: str
    title: str = ""
    team: bool = False


class TelegramLinkIn(BaseModel):
    emp_code: Optional[str] = None
    responder_index: Optional[int] = None


@router.put("/telegram")
async def put_telegram(body: TelegramIn, request: Request, current_user=Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require_change(request, current_user)
    from ..services.notify_telegram import save_settings
    try:
        await asyncio.to_thread(save_settings, db, body.enabled, (body.bot_token or "").strip() or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": _telegram_public(db)}


@router.put("/telegram/groups")
async def put_telegram_groups(body: List[TelegramGroupIn], request: Request, current_user=Depends(get_current_user),
                              db: Session = Depends(get_db)):
    _require_change(request, current_user)
    from ..services.notify_telegram import save_groups
    save_groups(db, [g.dict() for g in body])
    return {"success": True, "data": _telegram_public(db)}


@router.post("/telegram/check")
async def telegram_check_now(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Read the bot's updates now (Start presses, groups) instead of waiting for the next poll."""
    _require_change(request, current_user)
    from ..services.notify_telegram import poll_once
    res = await asyncio.to_thread(poll_once, db)
    return {"success": True, "data": {**res, **_telegram_public(db)}}


@router.post("/telegram/link")
async def telegram_link(body: TelegramLinkIn, request: Request, current_user=Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """A personal Start link for one person (or response-team member)."""
    _require_change(request, current_user)
    from ..services.notify_telegram import link_url, responder_key
    try:
        if body.responder_index is not None:
            team = get_responders(db)
            if not 0 <= body.responder_index < len(team):
                raise HTTPException(status_code=404, detail="No such team member")
            return {"success": True, "url": link_url(db, responder_key=responder_key(team[body.responder_index]))}
        if not body.emp_code:
            raise HTTPException(status_code=400, detail="emp_code or responder_index is required")
        return {"success": True, "url": link_url(db, emp_code=body.emp_code)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class TelegramInviteIn(BaseModel):
    scope: str = Field("onboard", pattern="^(onboard|all)$")


@router.post("/telegram/email-links")
async def telegram_email_links(body: TelegramInviteIn, request: Request, current_user=Depends(get_current_user),
                               db: Session = Depends(get_db)):
    """Email each person (on board, or all active staff) without Telegram their own Start link."""
    _require_change(request, current_user)
    from ..services.notify_telegram import link_url
    from ..services.notify_email import send_email, smtp_configured
    if not await asyncio.to_thread(smtp_configured):
        raise HTTPException(status_code=400, detail="Email is not set up — Settings → Email")
    where = "is_active AND telegram_chat_id IS NULL AND COALESCE(TRIM(email), '') <> ''"
    if body.scope == "onboard":
        where += " AND is_onboard"
    people = db.execute(text(f"SELECT emp_code, email, COALESCE(NULLIF(full_name, ''), emp_code) AS name "
                             f"FROM personnel WHERE {where}")).fetchall()
    sent = 0
    for p in people:
        url = link_url(db, emp_code=p.emp_code)
        res = await asyncio.to_thread(
            send_email, p.email, "Get ApexPOB site alerts on Telegram",
            f"<p>Hello {p.name},</p><p>Tap the link below on your phone and press <b>Start</b> to receive site alerts "
            f"(musters, emergencies, all-clear) on Telegram:</p><p><a href='{url}'>{url}</a></p>"
            f"<p style='color:#64748b'>This link is personal — please don't share it.</p>",
            f"Tap {url} on your phone and press Start to receive ApexPOB site alerts on Telegram.")
        sent += res.get("sent", 0)
    return {"success": True, "data": {"emailed": sent, "people": len(people)}}
