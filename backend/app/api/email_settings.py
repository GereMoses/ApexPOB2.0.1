"""
Email settings API — UI-managed, DB-backed email configuration.

Lets each deployment configure its own sending domain + SMTP server from
Settings → Email (nothing in backend env), generate a DKIM keypair, see the
SPF/DKIM/DMARC DNS records to publish, and send a test message.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..services.email_config import (
    build_dns_records,
    generate_dkim_keypair,
    get_email_settings,
    save_email_settings,
)

router = APIRouter(prefix="/api/v1/settings/email", tags=["Email Settings"])
logger = logging.getLogger(__name__)


class EmailSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    smtp_host: Optional[str] = Field(None, description="SMTP server hostname")
    smtp_port: Optional[str] = Field(None, description="SMTP port (587 STARTTLS / 465 SSL / 25)")
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = Field(None, description="Leave blank to keep the current password")
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    use_tls: Optional[bool] = None
    sending_domain: Optional[str] = Field(None, description="Domain mail is sent from, e.g. alerts.company.com")
    dkim_selector: Optional[str] = None


class EmailTestRequest(BaseModel):
    address: str = Field(..., description="Where to send the test email")


def _public_view(settings: dict) -> dict:
    """Never expose the SMTP password or DKIM private key over the API."""
    return {
        "enabled": settings.get("enabled", False),
        "smtp_host": settings.get("smtp_host", ""),
        "smtp_port": settings.get("smtp_port", "587"),
        "smtp_user": settings.get("smtp_user", ""),
        "has_password": bool(settings.get("smtp_password")),
        "from_address": settings.get("from_address", ""),
        "from_name": settings.get("from_name", ""),
        "use_tls": settings.get("use_tls", True),
        "sending_domain": settings.get("sending_domain", ""),
        "dkim_selector": settings.get("dkim_selector", "pob"),
        "has_dkim": bool(settings.get("dkim_public_key")),
        "configured": bool(str(settings.get("smtp_host") or "").strip()),
        "dns_records": build_dns_records(settings),
    }


@router.get("")
async def get_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current email config (secrets masked) + the DNS records to publish."""
    return {"success": True, "data": _public_view(get_email_settings(db))}


@router.put("")
async def update_settings(
    payload: EmailSettingsUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save email config. A blank smtp_password keeps the stored one."""
    data = {k: v for k, v in payload.dict().items() if v is not None}
    try:
        updated = save_email_settings(db, data, updated_by=getattr(current_user, "username", None))
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving email settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "data": _public_view(updated)}


@router.post("/dkim/generate")
async def generate_dkim(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a fresh DKIM keypair for the sending domain and store it.
    The private key is kept encrypted; the public key becomes the DKIM DNS record."""
    settings = get_email_settings(db)
    if not (settings.get("sending_domain") or "").strip():
        raise HTTPException(status_code=400, detail="Set a sending domain before generating a DKIM key")

    pair = generate_dkim_keypair()
    updated = save_email_settings(
        db,
        {
            "dkim_private_key": pair["private_pem"],
            "dkim_public_key": pair["public_b64"],
            "dkim_selector": settings.get("dkim_selector") or "pob",
        },
        updated_by=getattr(current_user, "username", None),
    )
    return {"success": True, "data": _public_view(updated)}


@router.get("/dns")
async def get_dns_records(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The SPF/DKIM/DMARC records the customer must publish for their domain."""
    return {"success": True, "data": {"dns_records": build_dns_records(get_email_settings(db))}}


@router.post("/test")
async def send_test(
    payload: EmailTestRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a test email using the SAVED config (save before testing)."""
    address = (payload.address or "").strip()
    if not address:
        raise HTTPException(status_code=400, detail="A destination email address is required")

    from ..services.notify_email import send_email
    result = await asyncio.to_thread(
        send_email,
        address,
        "Apex POB — email test",
        "<p>This is a test from Apex POB. If you received it, email delivery is working.</p>",
        "This is a test from Apex POB. If you received it, email delivery is working.",
    )
    ok = bool(result.get("sent"))
    return {
        "success": ok,
        "data": {
            "address": address,
            "sent": result.get("sent", 0),
            "failed": result.get("failed", []),
            "error": result.get("error"),
        },
    }


# ── Simple setup: address + app password ───────────────────────────────────

class QuickSetupRequest(BaseModel):
    email: str = Field(..., description="The mailbox alerts are sent from")
    app_password: str = Field(..., min_length=4, description="App password for that mailbox")
    from_name: Optional[str] = Field(None, description="Name shown as the sender")


@router.get("/detect")
async def detect_provider(email: str, current_user=Depends(get_current_user)):
    """Which mail provider an address belongs to (shown as the admin types)."""
    from ..services.email_autoconfig import detect
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a full email address")
    info = await asyncio.to_thread(detect, email.strip())
    info.pop("candidates", None)
    return {"success": True, "data": info}


@router.post("/quick-setup")
async def quick_setup(
    payload: QuickSetupRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Find the right server for the address, prove the login works, then save."""
    from ..services.email_autoconfig import auto_configure
    email = payload.email.strip()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a full email address")
    pw = payload.app_password.replace(" ", "")     # Google shows app passwords in groups of 4
    found = await asyncio.to_thread(auto_configure, email, pw)
    if not found["ok"]:
        return {"success": False, "message": found["error"],
                "data": {k: found.get(k) for k in ("provider", "provider_name", "help_url")}}
    updated = save_email_settings(db, {
        "enabled": True, "smtp_host": found["smtp_host"], "smtp_port": found["smtp_port"],
        "smtp_user": email, "smtp_password": pw, "from_address": email,
        "from_name": (payload.from_name or "").strip() or "Apex POB", "use_tls": True,
    }, updated_by=getattr(current_user, "username", None))
    return {"success": True, "message": f"Connected — alerts will be sent from {email} via {found['provider_name']}.",
            "data": {**_public_view(updated), "provider_name": found["provider_name"]}}
