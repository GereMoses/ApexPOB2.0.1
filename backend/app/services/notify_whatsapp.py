"""
Shared WhatsApp sender — DB-configured first (Settings → WhatsApp & Alerts), env as fallback.

DB providers (services/whatsapp_config.py):
  meta    Meta WhatsApp Cloud API — the OFFICIAL route (no ban risk). Business-initiated
          messages must use an APPROVED TEMPLATE; ours has one body variable {{1}} that
          carries the alert text. Without a template, a plain text message is sent, which
          WhatsApp only delivers inside 24 h of the recipient last messaging the number.
  termii  Termii WhatsApp channel (Nigeria).
  twilio  Twilio WhatsApp.

Env fallback (unchanged): provider is chosen by WHATSAPP_PROVIDER (termii | twilio | generic); if unset it
falls back to SMS_PROVIDER (so a single Termii account powers both), then to
auto-detection.

  Termii (Nigeria — recommended):
    WHATSAPP_PROVIDER=termii   (or just SMS_PROVIDER=termii)
    SMS_API_KEY                Termii API key (shared with SMS)
    WHATSAPP_SENDER_ID         approved WhatsApp sender (falls back to SMS_SENDER_ID)
    TERMII_BASE_URL            default https://api.ng.termii.com
    Delivered via Termii's send endpoint with channel="whatsapp". The recipient
    number must be WhatsApp-enabled; template pre-approval may be required by Meta.

  Twilio WhatsApp:
    TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / WHATSAPP_FROM (e.g. whatsapp:+14155238886)

  Generic HTTP gateway:
    WHATSAPP_API_URL           POST endpoint; body {"api_key","to","message"}
    WHATSAPP_API_KEY

Never raises — returns {"sent": N, "failed": [...], "error"?: str}. The HTTP
calls block, so async callers must run these via asyncio.to_thread().
"""

from __future__ import annotations

import logging
import os
import time as _time
from typing import Dict, Iterable, List, Union

from .notify_sms import normalize_msisdn, TERMII_DEFAULT_BASE

logger = logging.getLogger(__name__)


def _db_settings() -> Dict[str, object]:
    """Stored settings when switched on and complete, else {} (→ env fallback)."""
    try:
        from ..core.database import SessionLocal
        from .whatsapp_config import get_whatsapp_settings, db_whatsapp_ready
        db = SessionLocal()
        try:
            s = get_whatsapp_settings(db)
            return s if db_whatsapp_ready(s) else {}
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — DB down must not stop env-based sending
        logger.warning("notify_whatsapp: could not load DB settings (%s) — using env", exc)
        return {}


def _provider() -> str:
    """Which WhatsApp backend is usable, or '' when WhatsApp is off."""
    explicit = os.getenv("WHATSAPP_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    # A Termii account does both — inherit the SMS provider when it's Termii.
    if os.getenv("SMS_PROVIDER", "").strip().lower() == "termii":
        return "termii"
    if os.getenv("WHATSAPP_API_URL"):
        return "generic"
    if os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and os.getenv("WHATSAPP_FROM"):
        return "twilio"
    return ""


def whatsapp_configured() -> bool:
    """True if the selected WhatsApp provider has the creds it needs to send."""
    if _db_settings():
        return True
    provider = _provider()
    if provider == "termii":
        return bool(os.getenv("SMS_API_KEY"))
    if provider == "twilio":
        return bool(
            os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")
            and os.getenv("WHATSAPP_FROM")
        )
    if provider == "generic":
        return bool(os.getenv("WHATSAPP_API_URL"))
    return False


def _clean(to: Union[str, Iterable[str]]) -> List[str]:
    recipients: List[str] = [to] if isinstance(to, str) else [r for r in to if r]
    return [r.strip() for r in recipients if r and r.strip()]


def send_whatsapp(to: Union[str, Iterable[str]], message: str) -> Dict[str, object]:
    """Send one WhatsApp message to one or many numbers via env-configured provider.

    Returns {"sent": N, "failed": [num, ...], "error"?: str}. Fails soft.
    """
    recipients = list(dict.fromkeys(_clean(to)))
    if not recipients:
        return {"sent": 0, "failed": [], "error": "no recipients with a phone number"}

    db_cfg = _db_settings()
    if db_cfg:
        return _send_db(db_cfg, recipients, message)

    provider = _provider()
    if not whatsapp_configured():
        return {
            "sent": 0,
            "failed": recipients,
            "error": "WhatsApp not configured — set WHATSAPP_PROVIDER (or SMS_PROVIDER=termii) "
                     "and its credentials",
        }

    if provider == "termii":
        return _send_termii(recipients, message)
    if provider == "twilio":
        return _send_twilio(recipients, message)
    return _send_generic(recipients, message)


def _finish(sent: int, failed: List[str], tag: str) -> Dict[str, object]:
    logger.info("notify_whatsapp(%s): sent %d, failed %d", tag, sent, len(failed))
    out: Dict[str, object] = {"sent": sent, "failed": failed}
    if sent == 0 and failed:
        out["error"] = f"all sends failed via {tag} — check credentials/sender and gateway"
    return out


def _send_termii(recipients: List[str], message: str) -> Dict[str, object]:
    import requests

    base = os.getenv("TERMII_BASE_URL", TERMII_DEFAULT_BASE).rstrip("/")
    url = f"{base}/api/sms/send"
    api_key = os.getenv("SMS_API_KEY", "")
    sender = os.getenv("WHATSAPP_SENDER_ID") or os.getenv("SMS_SENDER_ID") or "N-Alert"

    sent, failed = 0, []
    for number in recipients:
        try:
            payload = {
                "to": normalize_msisdn(number),
                "from": sender,
                "sms": message,
                "type": "plain",
                "channel": "whatsapp",
                "api_key": api_key,
            }
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            if data.get("message_id"):
                sent += 1
            else:
                failed.append(number)
                logger.warning("Termii WhatsApp to %s returned no message_id: %s", number, data)
        except Exception as exc:  # noqa: BLE001
            failed.append(number)
            logger.warning("Termii WhatsApp to %s failed: %s", number, exc)
    return _finish(sent, failed, "termii")


def _send_generic(recipients: List[str], message: str) -> Dict[str, object]:
    """POST to any HTTP WhatsApp gateway, self-hosted included.

    The body shape was fixed (api_key in the body, fields to/message), which no
    self-hosted gateway actually uses — Evolution API wants a Bearer/apikey
    header and {"number", "text"}, WAHA wants {"chatId", "text", "session"}. So
    the field names and auth header are configurable, defaults unchanged:

        WHATSAPP_API_URL          POST endpoint
        WHATSAPP_API_KEY          credential
        WHATSAPP_API_KEY_HEADER   send the key as this HEADER (e.g. "apikey")
        WHATSAPP_API_HEADERS      extra headers as JSON
        WHATSAPP_FIELD_TO         recipient field   (default "to")
        WHATSAPP_FIELD_MESSAGE    message field     (default "message")
        WHATSAPP_EXTRA_BODY       constant body fields as JSON (e.g. session name)

    NOTE: a self-hosted gateway drives an UNOFFICIAL WhatsApp client. It violates
    Meta's terms and such numbers are commonly banned within weeks. Do not make
    it the only route for an emergency alert — keep email or SMS alongside it.
    """
    import json as _json
    import requests

    url = os.getenv("WHATSAPP_API_URL", "")
    api_key = os.getenv("WHATSAPP_API_KEY", "")
    key_header = os.getenv("WHATSAPP_API_KEY_HEADER", "").strip()
    f_to = os.getenv("WHATSAPP_FIELD_TO", "to")
    f_msg = os.getenv("WHATSAPP_FIELD_MESSAGE", "message")

    headers: Dict[str, str] = {}
    try:
        headers.update(_json.loads(os.getenv("WHATSAPP_API_HEADERS", "") or "{}"))
    except Exception:
        logger.warning("WHATSAPP_API_HEADERS is not valid JSON — ignoring it")
    if key_header and api_key:
        headers[key_header] = api_key

    extra: Dict[str, object] = {}
    try:
        extra.update(_json.loads(os.getenv("WHATSAPP_EXTRA_BODY", "") or "{}"))
    except Exception:
        logger.warning("WHATSAPP_EXTRA_BODY is not valid JSON — ignoring it")

    # A self-hosted gateway runs on a phone and WILL sometimes be slow or
    # offline. Notifications dispatch synchronously while a muster is being
    # activated, so an unbounded per-recipient loop could leave the operator
    # watching a spinner for minutes during an emergency. Bound the single
    # request AND the whole run; anything not attempted is reported failed
    # rather than silently dropped.
    req_timeout = float(os.getenv("WHATSAPP_TIMEOUT", "8"))
    budget = float(os.getenv("WHATSAPP_TOTAL_TIMEOUT", "30"))
    started = _time.monotonic()

    sent, failed = 0, []
    for number in recipients:
        if _time.monotonic() - started > budget:
            failed.append(number)
            logger.warning("WHATSAPP time budget of %.0fs exhausted — %s not attempted", budget, number)
            continue
        try:
            body: Dict[str, object] = {f_to: number, f_msg: message}
            if api_key and not key_header:
                body["api_key"] = api_key
            body.update(extra)
            resp = requests.post(url, json=body, headers=headers, timeout=req_timeout)
            resp.raise_for_status()
            sent += 1
        except Exception as exc:  # noqa: BLE001
            failed.append(number)
            logger.warning("WhatsApp to %s failed: %s", number, exc)
    return _finish(sent, failed, "generic")


def _send_twilio(recipients: List[str], message: str) -> Dict[str, object]:
    from_addr = os.getenv("WHATSAPP_FROM")  # e.g. "whatsapp:+14155238886"
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    try:
        from twilio.rest import Client
    except ImportError:
        return {"sent": 0, "failed": recipients, "error": "twilio library not installed"}

    client = Client(sid, token)
    sent, failed = 0, []
    for number in recipients:
        try:
            to_addr = number if number.startswith("whatsapp:") else f"whatsapp:{number}"
            client.messages.create(body=message, from_=from_addr, to=to_addr)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            failed.append(number)
            logger.warning("Twilio WhatsApp to %s failed: %s", number, exc)
    return _finish(sent, failed, "twilio")


# ── DB-configured providers ────────────────────────────────────────────────

def _flat(text: str, limit: int = 1000) -> str:
    """Template variables may not contain newlines/tabs or 4+ spaces (Meta rule)."""
    import re
    t = re.sub(r"[\r\n\t]+", " · ", text or "")
    t = re.sub(r" {4,}", "   ", t).strip()
    return t[:limit]


def _parallel(recipients: List[str], one, tag: str) -> Dict[str, object]:
    """Send to many numbers concurrently (an emergency to 300 people must not take
    300 × round-trip). `one(number)` returns None on success or an error string."""
    from concurrent.futures import ThreadPoolExecutor
    workers = max(1, min(8, len(recipients)))
    sent, failed, errors = 0, [], {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for number, err in zip(recipients, pool.map(one, recipients)):
            if err:
                failed.append(number)
                errors[number] = err
            else:
                sent += 1
    out = _finish(sent, failed, tag)
    if errors:
        out["errors"] = errors
        if sent == 0:
            out["error"] = next(iter(errors.values()))
    return out


def _send_db(cfg: Dict[str, object], recipients: List[str], message: str) -> Dict[str, object]:
    import requests
    cc = str(cfg.get("country_code") or "234")
    # One message per real number: '0803…' and '+234803…' are the same phone.
    seen, unique = set(), []
    for n in recipients:
        key = normalize_msisdn(n, cc)
        if key not in seen:
            seen.add(key)
            unique.append(n)
    recipients = unique
    provider = cfg.get("provider")

    if provider == "meta":
        ver = str(cfg.get("meta_api_version") or "v21.0")
        url = f"https://graph.facebook.com/{ver}/{cfg['meta_phone_number_id']}/messages"
        headers = {"Authorization": f"Bearer {cfg['meta_access_token']}"}
        template = str(cfg.get("meta_template") or "").strip()

        lang = cfg.get("meta_template_lang") or ("en_US" if template == "hello_world" else "en")

        def template_body(to: str, with_text: bool) -> dict:
            t = {"name": template, "language": {"code": lang}}
            if with_text:
                t["components"] = [{"type": "body", "parameters": [{"type": "text", "text": _flat(message)}]}]
            return {"messaging_product": "whatsapp", "to": to, "type": "template", "template": t}

        def post(body: dict):
            r = requests.post(url, json=body, headers=headers, timeout=15)
            data = r.json() if r.content else {}
            if r.ok and data.get("messages"):
                return None, None
            err = (data.get("error") or {})
            return (f"{err.get('message') or r.status_code}" + (f" ({err.get('code')})" if err.get("code") else ""),
                    err.get("code"))

        def one(number: str):
            to = normalize_msisdn(number, cc)
            try:
                if not template:
                    # Free-form text: only delivered inside 24 h of the person messaging you.
                    return post({"messaging_product": "whatsapp", "to": to, "type": "text",
                                 "text": {"preview_url": False, "body": message[:4096]}})[0]
                # Meta's ready-made test template "hello_world" has no text slot.
                with_text = template != "hello_world"
                err, code = post(template_body(to, with_text))
                if err and with_text and code == 132000:
                    # The approved template has a different number of slots — still
                    # get *a* message through rather than nothing.
                    err, code = post(template_body(to, False))
                return err
            except Exception as exc:  # noqa: BLE001
                return str(exc)
        return _parallel(recipients, one, "meta")

    if provider == "termii":
        url = f"{str(cfg.get('termii_base_url') or TERMII_DEFAULT_BASE).rstrip('/')}/api/sms/send"

        def one(number: str):
            try:
                r = requests.post(url, json={"to": normalize_msisdn(number, cc), "from": cfg["termii_sender"],
                                             "sms": message, "type": "plain", "channel": "whatsapp",
                                             "api_key": cfg["termii_api_key"]}, timeout=15)
                data = r.json() if r.content else {}
                return None if data.get("message_id") else str(data.get("message") or data or r.status_code)
            except Exception as exc:  # noqa: BLE001
                return str(exc)
        return _parallel(recipients, one, "termii")

    if provider == "twilio":
        sid, token = str(cfg["twilio_sid"]), str(cfg["twilio_token"])
        frm = str(cfg["twilio_from"])
        frm = frm if frm.startswith("whatsapp:") else f"whatsapp:{frm if frm.startswith('+') else '+' + frm}"
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

        def one(number: str):
            try:
                r = requests.post(url, data={"From": frm, "To": f"whatsapp:+{normalize_msisdn(number, cc)}", "Body": message},
                                  auth=(sid, token), timeout=15)
                return None if r.ok else str((r.json() if r.content else {}).get("message") or r.status_code)
            except Exception as exc:  # noqa: BLE001
                return str(exc)
        return _parallel(recipients, one, "twilio")

    if provider == "linked":
        from . import whatsapp_link
        intl = {normalize_msisdn(n, cc): n for n in recipients}
        out = whatsapp_link.send(list(intl), message)
        out["failed"] = [intl.get(n, n) for n in out.get("failed", [])]
        if out.get("errors"):
            out["errors"] = {intl.get(n, n): e for n, e in out["errors"].items()}
        return out

    return {"sent": 0, "failed": recipients, "error": f"unknown WhatsApp provider {provider!r}"}
