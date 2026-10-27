"""
One way to send an alert — musters, emergencies, panic, escalations, all-clear.

    dispatch_background("muster", event.id, people, subject, text)

* Channels: every channel that is configured (email, WhatsApp, SMS) unless a
  subset is given. A channel that isn't configured is recorded as SKIPPED with the
  reason, so the operator can see why nobody got a WhatsApp.
* Recipients: the people passed in, plus the emergency response team from
  Settings → WhatsApp & Alerts (they get every alert), de-duplicated.
* Each recipient × channel is written to notify_delivery (who, where, sent/failed,
  error) — the delivery log shown under Emergency → Notifications.
* Runs in the background (Celery, or a thread if the broker is down) so starting a
  muster is never held up by a slow mail server or WhatsApp gateway.
"""
from __future__ import annotations

import html as _html
import logging
import threading
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

ALL_CHANNELS = ("whatsapp", "email", "sms")


def configured_channels() -> Dict[str, bool]:
    from .notify_email import smtp_configured
    from .notify_sms import sms_configured
    from .notify_whatsapp import whatsapp_configured
    return {"email": smtp_configured(), "whatsapp": whatsapp_configured(), "sms": sms_configured()}


def people_from_personnel(db, *, ids: Iterable[int] = (), emp_codes: Iterable[str] = ()) -> List[Dict[str, str]]:
    """Contact cards for personnel (phone falls back to the emergency-contact phone)."""
    ids, emp_codes = list(ids or []), list(emp_codes or [])
    if not ids and not emp_codes:
        return []
    rows = db.execute(text("""
        SELECT COALESCE(NULLIF(full_name, ''), TRIM(CONCAT(first_name, ' ', last_name)), emp_code) AS name,
               NULLIF(TRIM(email), '') AS email,
               COALESCE(NULLIF(TRIM(phone), ''), NULLIF(TRIM(emergency_contact_phone), '')) AS phone
        FROM personnel
        WHERE is_active AND (id = ANY(:ids) OR emp_code = ANY(:codes))
    """), {"ids": ids, "codes": emp_codes}).fetchall()
    return [{"name": r.name, "email": r.email or "", "phone": r.phone or "", "kind": "personnel"} for r in rows]


def onboard_people(db, zone_ids: Optional[List[int]] = None) -> List[Dict[str, str]]:
    """Everyone on board (optionally only those located in the given zones)."""
    q = "SELECT id FROM personnel WHERE is_active AND is_onboard"
    params: Dict[str, Any] = {}
    if zone_ids:
        q += " AND current_zone_id = ANY(:z)"
        params["z"] = list(zone_ids)
    ids = [r[0] for r in db.execute(text(q), params).fetchall()]
    return people_from_personnel(db, ids=ids)


def responders(db) -> List[Dict[str, str]]:
    from .whatsapp_config import get_responders
    return [{**r, "kind": "responder"} for r in get_responders(db)]


def dispatch(source_type: str, source_id: Optional[int], people: List[Dict[str, str]], subject: str, message: str,
             channels: Optional[Iterable[str]] = None, include_responders: bool = True,
             html_body: Optional[str] = None) -> Dict[str, Any]:
    """Send now (blocking) and log every delivery. Never raises."""
    from ..core.database import SessionLocal
    from .notify_email import send_email
    from .notify_sms import send_sms
    from .notify_whatsapp import send_whatsapp

    db = SessionLocal()
    summary: Dict[str, Any] = {}
    try:
        everyone = list(people or [])
        if include_responders:
            everyone += responders(db)
        cfg = configured_channels()
        wanted = [c for c in (channels or ALL_CHANNELS) if c in ALL_CHANNELS]

        log_rows: List[Dict[str, Any]] = []
        for ch in wanted:
            field = "email" if ch == "email" else "phone"
            by_addr: Dict[str, str] = {}
            for p in everyone:
                addr = (p.get(field) or "").strip()
                if addr and addr not in by_addr:
                    by_addr[addr] = p.get("name") or addr
            if not by_addr:
                summary[ch] = {"sent": 0, "failed": 0, "note": "nobody has a " + ("email address" if ch == "email" else "phone number")}
                continue
            if not cfg.get(ch):
                reason = {"email": "Email (SMTP) is not set up — Settings → Email",
                          "whatsapp": "WhatsApp is not set up — Settings → WhatsApp & Alerts",
                          "sms": "SMS gateway is not set up"}[ch]
                summary[ch] = {"sent": 0, "failed": 0, "skipped": len(by_addr), "note": reason}
                log_rows += [dict(channel=ch, name=n, addr=a, status="SKIPPED", error=reason) for a, n in by_addr.items()]
                continue

            addrs = list(by_addr)
            if ch == "email":
                body = html_body or "<div style='font-family:Arial,sans-serif;font-size:15px'>" + \
                    "".join(f"<p>{_html.escape(line)}</p>" for line in message.split("\n") if line.strip()) + \
                    "<p style='color:#64748b;font-size:12px'>Sent by ApexPOB</p></div>"
                res = send_email(addrs, subject, body, body_text=message)
            elif ch == "whatsapp":
                res = send_whatsapp(addrs, message)
            else:
                res = send_sms(addrs, message)
            failed = set(res.get("failed") or [])
            errors = res.get("errors") or {}
            for a, n in by_addr.items():
                bad = a in failed
                log_rows.append(dict(channel=ch, name=n, addr=a, status="FAILED" if bad else "SENT",
                                     error=(errors.get(a) or res.get("error") or "failed") if bad else None))
            summary[ch] = {"sent": len(addrs) - len(failed), "failed": len(failed)}
            if res.get("error") and failed:
                summary[ch]["note"] = res["error"]

        if log_rows:
            db.execute(text("""
                INSERT INTO notify_delivery (source_type, source_id, channel, recipient_name, address, status, error, subject, message)
                VALUES (:st, :sid, :channel, :name, :addr, :status, :error, :subject, :message)
            """), [dict(r, st=source_type, sid=source_id, subject=subject[:255], message=message[:2000]) for r in log_rows])
            db.commit()
        logger.info("Alert %s#%s dispatched: %s", source_type, source_id, summary)
    except Exception as e:  # noqa: BLE001 — alerts must never break the flow that raised them
        logger.error("Alert %s#%s dispatch failed: %s", source_type, source_id, e)
        db.rollback()
        summary["error"] = str(e)
    finally:
        db.close()
    return summary


def dispatch_background(source_type: str, source_id: Optional[int], people: List[Dict[str, str]], subject: str,
                        message: str, channels: Optional[Iterable[str]] = None, include_responders: bool = True) -> Dict[str, Any]:
    """Queue the alert; returns immediately with what was queued."""
    args = (source_type, source_id, list(people or []), subject, message, list(channels) if channels else None, include_responders)
    try:
        from .mustering_celery_tasks import dispatch_alert
        dispatch_alert.apply_async(args=args, expires=600)
        via = "queue"
    except Exception as e:  # noqa: BLE001 — broker down: still send, in a thread
        logger.warning("Alert queue unavailable (%s) — sending in a thread", e)
        threading.Thread(target=dispatch, args=args, daemon=True).start()
        via = "thread"
    return {"queued": len(people or []), "via": via, "channels": configured_channels()}
