"""
Personal door PINs for ZKTeco C3 keypad readers ("cards and PINs, mostly cards").

A PIN is 4-6 digits, stored ENCRYPTED on the person (personnel.door_pin_enc) and
loaded onto every panel as that user's keypad password by the panel sync. Admins
see a PIN only once — when it is set or generated — and can send it straight to
the person by WhatsApp / email (the delivery log records that a PIN was sent,
never the PIN itself).
"""
from __future__ import annotations

import re
import secrets
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

_WEAK = {"0000", "1111", "1234", "12345", "123456", "4321", "654321", "000000", "111111"}


def valid_pin(pin: str) -> Optional[str]:
    """None if acceptable, else why not."""
    if not re.fullmatch(r"\d{4,6}", pin or ""):
        return "A door PIN is 4 to 6 digits"
    if pin in _WEAK or len(set(pin)) == 1:
        return "Too easy to guess — choose another"
    return None


def generate_pin(length: int = 6) -> str:
    while True:
        pin = "".join(secrets.choice("0123456789") for _ in range(length))
        if not valid_pin(pin):
            return pin


def set_pin(db: Session, emp_code: str, pin: Optional[str] = None) -> str:
    from ..core.crypto import encrypt_secret
    pin = (pin or "").strip() or generate_pin()
    why = valid_pin(pin)
    if why:
        raise ValueError(why)
    n = db.execute(text("UPDATE personnel SET door_pin_enc = :p, door_pin_set_at = NOW() WHERE emp_code = :e AND is_active"),
                   {"p": encrypt_secret(pin), "e": emp_code}).rowcount
    if not n:
        raise LookupError("No active person with that employee code")
    db.commit()
    return pin


def clear_pin(db: Session, emp_code: str) -> None:
    db.execute(text("UPDATE personnel SET door_pin_enc = NULL, door_pin_set_at = NULL WHERE emp_code = :e"), {"e": emp_code})
    db.commit()


def send_pin(db: Session, emp_code: str, pin: str) -> Dict:
    """WhatsApp / email the PIN to its owner only (not the response team)."""
    from .notify_dispatch import dispatch, people_from_personnel
    people = people_from_personnel(db, emp_codes=[emp_code])
    if not people:
        return {"error": "person not found"}
    msg = (f"Your ApexPOB door PIN is {pin}. Use it with your card at keypad doors. "
           f"Keep it private — do not share it. If someone learns it, ask security for a new one.")
    return dispatch("door_pin", None, people, "Your door PIN", msg, ["whatsapp", "telegram", "email"], include_responders=False,
                    log_text="Door PIN sent (hidden)")
