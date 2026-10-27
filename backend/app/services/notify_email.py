"""
Shared email sender — DB-configured first, env as fallback.

Config source order (so production customers manage everything from the Settings
UI, never backend env):
  1. Database (sys_parameters `email.*`, set via Settings → Email) — preferred.
  2. Environment variables (SMTP_HOST/SMTP_USER/… ) — dev/bootstrap fallback.

When a DKIM private key + sending domain are configured, outgoing mail is
DKIM-signed (via dkimpy) so the customer's published DKIM DNS record validates.
Signing is best-effort: if dkimpy is missing or signing fails, the mail still
goes out unsigned.

Never raises — returns {"sent": N, "failed": [...], "error"?: str} so a mail
outage can never break the flow that triggered it (avoids worker starvation).
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Iterable, List, Optional, Union

logger = logging.getLogger(__name__)


def _env_settings() -> Dict[str, object]:
    host = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER") or ""
    user = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or ""
    return {
        "smtp_host": host,
        "smtp_port": os.getenv("SMTP_PORT", "587"),
        "smtp_user": user,
        "smtp_password": os.getenv("SMTP_PASSWORD", ""),
        "from_address": os.getenv("EMAIL_FROM") or os.getenv("FROM_EMAIL") or user or "no-reply@pob",
        "from_name": os.getenv("EMAIL_FROM_NAME", "Apex POB"),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() != "false",
        "sending_domain": os.getenv("EMAIL_SENDING_DOMAIN", ""),
        "dkim_selector": os.getenv("DKIM_SELECTOR", "pob"),
        "dkim_private_key": "",
        "source": "env",
    }


def _load_settings() -> Dict[str, object]:
    """Return the effective email settings — DB when configured, else env."""
    try:
        from ..core.database import SessionLocal
        from .email_config import db_smtp_configured, get_email_settings

        db = SessionLocal()
        try:
            if db_smtp_configured(db):
                s = get_email_settings(db)
                s["from_address"] = s.get("from_address") or s.get("smtp_user") or "no-reply@pob"
                s["source"] = "db"
                return s
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — DB down must not stop env-based sending
        logger.warning("notify_email: could not load DB settings (%s) — using env", exc)
    return _env_settings()


def smtp_configured() -> bool:
    """True if a usable SMTP host is set (DB or env)."""
    return bool(str(_load_settings().get("smtp_host") or "").strip())


def _maybe_dkim_sign(raw: bytes, settings: Dict[str, object]) -> bytes:
    """DKIM-sign the raw message if a key + domain are configured. Best-effort."""
    domain = str(settings.get("sending_domain") or "").strip()
    private_key = str(settings.get("dkim_private_key") or "").strip()
    selector = str(settings.get("dkim_selector") or "pob").strip()
    if not domain or not private_key:
        return raw
    try:
        import dkim  # dkimpy
        signature = dkim.sign(
            message=raw,
            selector=selector.encode(),
            domain=domain.encode(),
            privkey=private_key.encode(),
            include_headers=[b"from", b"to", b"subject", b"date"],
        )
        return signature + raw
    except ModuleNotFoundError:
        logger.warning("notify_email: dkimpy not installed — sending unsigned")
    except Exception as exc:  # noqa: BLE001 — signing must never block delivery
        logger.warning("notify_email: DKIM signing failed (%s) — sending unsigned", exc)
    return raw


def send_email(
    to: Union[str, Iterable[str]],
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
    attachments: Optional[List[tuple]] = None,
) -> Dict[str, object]:
    """Send one email (to one or many recipients) via DB/env-configured SMTP.

    attachments: optional [(filename, bytes, mime_type), ...] (e.g. scheduled reports).
    Returns {"sent": N, "failed": [addr, ...], "error"?: str}. Fails soft.
    """
    recipients: List[str] = [to] if isinstance(to, str) else [r for r in to if r]
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return {"sent": 0, "failed": [], "error": "no recipients with an email address"}

    s = _load_settings()
    host = str(s.get("smtp_host") or "").strip()
    if not host:
        return {
            "sent": 0,
            "failed": recipients,
            "error": "SMTP not configured — set it in Settings → Email (or SMTP_HOST env)",
        }

    try:
        port = int(str(s.get("smtp_port") or "587"))
    except ValueError:
        port = 587
    user = str(s.get("smtp_user") or "")
    password = str(s.get("smtp_password") or "")
    sender = str(s.get("from_address") or user or "no-reply@pob")
    from_name = str(s.get("from_name") or "").strip()
    from_header = f"{from_name} <{sender}>" if from_name else sender
    use_tls = bool(s.get("use_tls", True))

    sent, failed = 0, []
    try:
        # Port 465 = implicit SSL (SMTPS); 587/25 = plain connection upgraded by STARTTLS.
        conn = smtplib.SMTP_SSL(host, port, timeout=15) if port == 465 else smtplib.SMTP(host, port, timeout=15)
        with conn as server:
            server.ehlo()
            if use_tls and port != 465:
                try:
                    server.starttls()
                    server.ehlo()
                except Exception:
                    pass  # server without STARTTLS (e.g. local catcher) — continue plain
            if user:
                server.login(user, password)
            for addr in recipients:
                try:
                    body = MIMEMultipart("alternative")
                    if body_text:
                        body.attach(MIMEText(body_text, "plain"))
                    body.attach(MIMEText(body_html, "html"))
                    if attachments:
                        from email.mime.application import MIMEApplication
                        msg = MIMEMultipart("mixed")
                        msg.attach(body)
                        for fname, data, mime in attachments:
                            part = MIMEApplication(data, _subtype=(mime or "octet-stream").split("/")[-1])
                            part.add_header("Content-Disposition", "attachment", filename=fname)
                            msg.attach(part)
                    else:
                        msg = body
                    msg["Subject"] = subject
                    msg["From"] = from_header
                    msg["To"] = addr
                    raw = _maybe_dkim_sign(msg.as_bytes(), s)
                    server.sendmail(sender, [addr], raw)
                    sent += 1
                except Exception as exc:  # noqa: BLE001 — one bad address must not fail the rest
                    failed.append(addr)
                    logger.warning("Email to %s failed: %s", addr, exc)
        logger.info("notify_email: sent %d, failed %d (src=%s, subject=%r)",
                    sent, len(failed), s.get("source"), subject)
        return {"sent": sent, "failed": failed}
    except Exception as exc:  # noqa: BLE001 — connection/auth error must not raise
        logger.error("notify_email: SMTP send failed (%s:%s): %s", host, port, exc)
        return {"sent": 0, "failed": recipients, "error": str(exc)}
