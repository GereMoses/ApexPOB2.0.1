"""
WhatsApp through ONE linked phone — the site's own number, paired like WhatsApp Web.

Drives the self-hosted Evolution API gateway (docker-compose.prod.yml service
`whatsapp-gateway`, profile "whatsapp"). The phone is linked once from
Settings → WhatsApp & Alerts by scanning a QR code (or typing a pairing code);
after that every alert goes out from that number. No Meta account or template.

  WHATSAPP_GATEWAY_URL   default http://whatsapp-gateway:8080
  WHATSAPP_API_KEY       the gateway's AUTHENTICATION_API_KEY (.env.prod)

This is an UNOFFICIAL WhatsApp client (against Meta's terms) — numbers used for bulk
sending can be banned. Use a dedicated SIM, never a person's own number, and keep
Telegram / email on so an emergency never depends on WhatsApp alone. Sends are
paced (one at a time, ~1 s apart) because a burst to the whole muster list is
exactly what WhatsApp's spam detection looks for.
"""
from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

INSTANCE = "apexpob"
_cache: Dict[str, Any] = {"at": 0.0, "linked": False}


def _base() -> str:
    return os.getenv("WHATSAPP_GATEWAY_URL", "http://whatsapp-gateway:8080").rstrip("/")


def _call(method: str, path: str, json: Optional[dict] = None, timeout: float = 15) -> Any:
    try:
        r = requests.request(method, _base() + path, json=json, timeout=timeout,
                             headers={"apikey": os.getenv("WHATSAPP_API_KEY", "")})
    except requests.RequestException as exc:
        raise GatewayDown("The WhatsApp gateway is not running — start it with "
                          "`docker compose --profile whatsapp up -d whatsapp-gateway`") from exc
    data = r.json() if r.content else {}
    if r.status_code == 401:
        raise RuntimeError("The WhatsApp gateway refused the API key (WHATSAPP_API_KEY in .env.prod)")
    if not r.ok:
        msg = data.get("response", {}).get("message") if isinstance(data, dict) else None
        if isinstance(msg, list):
            msg = "; ".join(
                (f"{m.get('number')} is not on WhatsApp" if m.get("exists") is False else str(m.get("message") or m))
                if isinstance(m, dict) else str(m) for m in msg)
        raise RuntimeError(f"WhatsApp gateway: {msg or data or r.status_code}")
    return data


class GatewayDown(RuntimeError):
    pass


def _instance() -> Optional[dict]:
    rows = _call("GET", "/instance/fetchInstances")      # filtered by name it 404s when absent
    rows = rows if isinstance(rows, list) else [rows]
    return next((r for r in rows if isinstance(r, dict) and r.get("name") == INSTANCE), None)


def status() -> Dict[str, Any]:
    """{running, linked, state, number, name} — never raises."""
    st = _status()
    _cache.update(at=time.monotonic(), linked=st["linked"])
    return st


def _status() -> Dict[str, Any]:
    try:
        inst = _instance()
    except GatewayDown as exc:
        return {"running": False, "linked": False, "state": "gateway_down", "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"running": True, "linked": False, "state": "error", "error": str(exc)}
    if not inst:
        return {"running": True, "linked": False, "state": "not_created"}
    state = inst.get("connectionStatus") or "close"
    jid = str(inst.get("ownerJid") or "")
    return {"running": True, "linked": state == "open", "state": state,
            "number": ("+" + jid.split("@")[0]) if state == "open" and jid else None,
            "name": inst.get("profileName") if state == "open" else None}


def linked_cached(ttl: float = 15) -> bool:
    """Is the phone linked? Cached briefly — asked on every alert and settings load."""
    if time.monotonic() - _cache["at"] > ttl:
        status()
    return _cache["linked"]


def start_link(phone: Optional[str] = None) -> Dict[str, Any]:
    """Begin pairing. Returns {qr: data-URL png, pairing_code} — scan the QR in
    WhatsApp → Linked devices, or (with `phone`) type the 8-character code instead."""
    inst = _instance()
    if inst and inst.get("connectionStatus") == "open":
        return {"linked": True}
    body = {"instanceName": INSTANCE, "integration": "WHATSAPP-BAILEYS", "qrcode": True,
            "groupsIgnore": True, "rejectCall": False}
    if phone:
        # The gateway only issues a pairing code to a session created with the number.
        if inst:
            _call("DELETE", f"/instance/delete/{INSTANCE}")
            for _ in range(20):
                time.sleep(0.5)
                if not _instance():
                    break
        data = _call("POST", "/instance/create", {**body, "number": phone}, timeout=30).get("qrcode") or {}
        code = data.get("pairingCode")
        if not code or code == "None":
            raise RuntimeError("WhatsApp did not give a pairing code — use the QR code instead")
        return {"linked": False, "pairing_code": code}
    if not inst:
        _call("POST", "/instance/create", body, timeout=30)
    data = _call("GET", f"/instance/connect/{INSTANCE}", timeout=30)
    return {"linked": False, "qr": data.get("base64")}


def unlink() -> None:
    try:
        _call("DELETE", f"/instance/logout/{INSTANCE}")
    except RuntimeError as exc:
        if "not connected" not in str(exc).lower():
            raise
    _call("DELETE", f"/instance/delete/{INSTANCE}")


def send(numbers: List[str], message: str) -> Dict[str, Any]:
    """Send `message` to international-format numbers (no '+'), paced one by one."""
    st = status()
    if not st["linked"]:
        err = st.get("error") or "WhatsApp phone is not linked — Settings → WhatsApp & Alerts → Linked phone"
        return {"sent": 0, "failed": numbers, "error": err}
    sent, failed, errors = 0, [], {}
    for i, n in enumerate(numbers):
        if i:
            time.sleep(random.uniform(0.8, 1.6))
        try:
            _call("POST", f"/message/sendText/{INSTANCE}", {"number": n, "text": message}, timeout=30)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            failed.append(n)
            errors[n] = str(exc)
            logger.warning("WhatsApp (linked) to %s failed: %s", n, exc)
    out: Dict[str, Any] = {"sent": sent, "failed": failed}
    if errors:
        out["errors"] = errors
        if not sent:
            out["error"] = next(iter(errors.values()))
    logger.info("notify_whatsapp(linked): sent %d, failed %d", sent, len(failed))
    return out
