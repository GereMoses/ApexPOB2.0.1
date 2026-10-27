"""
Email auto-setup: an address + app password is all an admin types.

The mail server is worked out from the address:
  1. Well-known consumer domains (gmail.com, outlook.com, yahoo.com …).
  2. For a company domain, its MX records tell us who hosts the mailbox —
     Google Workspace, Microsoft 365, Zoho, Yahoo, GoDaddy, Namecheap…
  3. Otherwise mail.<domain> / smtp.<domain> are tried on 587 then 465.
Every candidate is proven by actually logging in before anything is saved.
"""
from __future__ import annotations

import logging
import smtplib
import socket
import ssl
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# name, host, port, help link for creating an app password
PROVIDERS: Dict[str, Tuple[str, str, int, str]] = {
    "google":    ("Gmail / Google Workspace", "smtp.gmail.com", 587, "https://myaccount.google.com/apppasswords"),
    "microsoft": ("Microsoft 365 / Outlook", "smtp.office365.com", 587, "https://account.microsoft.com/security"),
    "outlook":   ("Outlook.com / Hotmail", "smtp-mail.outlook.com", 587, "https://account.microsoft.com/security"),
    "yahoo":     ("Yahoo Mail", "smtp.mail.yahoo.com", 465, "https://login.yahoo.com/account/security"),
    "zoho":      ("Zoho Mail", "smtp.zoho.com", 465, "https://accounts.zoho.com/home#security/app_password"),
    "icloud":    ("iCloud Mail", "smtp.mail.me.com", 587, "https://appleid.apple.com/account/manage"),
    "godaddy":   ("GoDaddy Email", "smtpout.secureserver.net", 465, ""),
    "namecheap": ("Namecheap Private Email", "mail.privateemail.com", 465, ""),
    "titan":     ("Titan Email", "smtp.titan.email", 465, ""),
}

_DOMAINS = {
    "gmail.com": "google", "googlemail.com": "google",
    "outlook.com": "outlook", "hotmail.com": "outlook", "live.com": "outlook", "msn.com": "outlook",
    "yahoo.com": "yahoo", "ymail.com": "yahoo", "yahoo.co.uk": "yahoo",
    "zoho.com": "zoho", "zohomail.com": "zoho",
    "icloud.com": "icloud", "me.com": "icloud", "mac.com": "icloud",
}

_MX_HINTS = [
    ("google.com", "google"), ("googlemail.com", "google"),
    ("protection.outlook.com", "microsoft"), ("outlook.com", "microsoft"),
    ("yahoodns.net", "yahoo"), ("zoho.", "zoho"),
    ("secureserver.net", "godaddy"), ("privateemail.com", "namecheap"), ("titan.email", "titan"),
]


def _mx(domain: str) -> List[str]:
    try:
        import dns.resolver
        ans = dns.resolver.resolve(domain, "MX", lifetime=5)
        return [str(r.exchange).rstrip(".").lower() for r in sorted(ans, key=lambda r: r.preference)]
    except Exception as e:  # noqa: BLE001
        logger.info("MX lookup for %s failed: %s", domain, e)
        return []


def detect(email: str) -> Dict[str, object]:
    """Best guess + ordered candidates for an address. No network login here."""
    domain = email.rsplit("@", 1)[-1].strip().lower()
    key = _DOMAINS.get(domain)
    mx = [] if key else _mx(domain)
    if not key:
        for hint, prov in _MX_HINTS:
            if any(hint in m for m in mx):
                key = prov
                break
    cands: List[Tuple[str, int]] = []
    workmail = next((m for m in mx if m.startswith("inbound-smtp.") and m.endswith(".amazonaws.com")), None)
    if not key and workmail:
        region = workmail.split(".")[1]                       # inbound-smtp.<region>.amazonaws.com
        return {"provider": "workmail", "provider_name": "Amazon WorkMail", "help_url": "",
                "domain": domain, "mx": mx[:3], "candidates": [(f"smtp.mail.{region}.awsapps.com", 465)]}
    if key:
        name, host, port, help_url = PROVIDERS[key]
        cands.append((host, port))
    else:
        name, help_url = f"Mail server for {domain}", ""
        for h in (f"mail.{domain}", f"smtp.{domain}", *(mx[:1])):
            cands += [(h, 587), (h, 465)]
    return {"provider": key or "custom", "provider_name": name, "help_url": help_url,
            "domain": domain, "mx": mx[:3], "candidates": cands}


def try_login(host: str, port: int, user: str, password: str, timeout: int = 12) -> Optional[str]:
    """None when the login works, else a plain-English reason."""
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        with server:
            server.login(user, password)
        return None
    except smtplib.SMTPAuthenticationError as e:
        msg = (e.smtp_error or b"").decode(errors="ignore")
        if "5.7.139" in msg or "SmtpClientAuthentication" in msg or "basic authentication is disabled" in msg.lower():
            return ("Microsoft 365 has SMTP sign-in switched off for this mailbox. An admin must enable "
                    "'Authenticated SMTP' for it (Microsoft 365 admin → Users → Mail → Manage email apps).")
        if "Application-specific password required" in msg or "InvalidSecondFactor" in msg:
            return "This account needs an APP password, not the normal sign-in password."
        return "The email or app password was not accepted. Check both and try again."
    except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError) as e:
        return f"Could not reach {host}:{port} ({e.__class__.__name__})."
    except smtplib.SMTPException as e:
        return f"{host}:{port} refused the connection: {e}"


def auto_configure(email: str, password: str) -> Dict[str, object]:
    """Find the server that accepts this login. Returns the settings to save, or the error."""
    info = detect(email)
    last_err = "No mail server could be found for this address."
    for host, port in info["candidates"]:
        err = try_login(host, port, email, password)
        if err is None:
            return {"ok": True, "smtp_host": host, "smtp_port": str(port), **info}
        last_err = err
        if "not accepted" in err or "APP password" in err or "Microsoft 365" in err:
            break           # right server, wrong credentials — don't keep trying others
    return {"ok": False, "error": last_err, **info}
