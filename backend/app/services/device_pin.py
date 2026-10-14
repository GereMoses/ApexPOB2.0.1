"""
Reader PIN <-> employee translation.

Apex POB keys everything (attendance, access, mustering) on personnel.emp_code, but
a ZKTeco reader's user ID (PIN) is numeric — digits only unless the firmware reports
string-ID support, and ZKBioSecurity caps a personnel ID at 9 characters. SeamlessHR's
staff_id values (e.g. EMPLOYEE001) cannot be PINs. SeamlessHR itself defines the
Attendance ID as "the Personnel ID on the biometric device", so that is the PIN:

    reader  <-- pin_for()/rewrite_command() --  emp_code  --> everything else
    reader  --- resolve_emp_code() -->          emp_code

Translation happens only at the two edges (commands out to readers, punches in
from readers) so the rest of the system keeps using emp_code unchanged.

An employee with no attendance_id (local staff, or not yet adopted from SeamlessHR)
passes through unchanged: PIN == emp_code, exactly as before.
"""
import logging
import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 1-9 digits: safe on every ZKTeco firmware (ZKBioSecurity's own personnel-ID cap is 9).
_PIN_RE = re.compile(r"^\d{1,9}$")
# "PIN=<value>" inside a push-protocol command; value ends at whitespace/tab.
_CMD_PIN_RE = re.compile(r"\bPIN=(\S+)")


def is_valid_pin(value: Optional[str]) -> bool:
    return bool(value) and bool(_PIN_RE.match(str(value)))


def pin_for(db: Session, emp_code: str, fallback: Optional[str] = None) -> str:
    """The PIN to give a reader for this employee: attendance_id, else `fallback`
    (e.g. the legacy badge_id), else emp_code."""
    if fallback is None:
        fallback = emp_code
    if not emp_code:
        return fallback
    try:
        row = db.execute(
            text("SELECT attendance_id FROM personnel WHERE emp_code = :c"),
            {"c": str(emp_code)},
        ).fetchone()
    except Exception as e:  # never let a lookup failure block a device command
        logger.warning("pin_for(%s) lookup failed, using fallback: %s", emp_code, e)
        try:
            db.rollback()
        except Exception:
            pass
        return fallback
    if row and row[0] and is_valid_pin(row[0]):
        return str(row[0])
    return fallback


def resolve_emp_code(db: Session, pin: Optional[str]) -> str:
    """Map a PIN reported by a reader back to personnel.emp_code.

    Exact attendance_id match first; then match ignoring leading zeros, because a
    numeric reader may hand back "122" for SeamlessHR's "0122". No match means the
    PIN is already an emp_code (legacy / local staff) and is returned unchanged.
    """
    pin = (str(pin).strip() if pin is not None else "")
    if not pin:
        return pin
    try:
        row = db.execute(
            text("SELECT emp_code FROM personnel WHERE attendance_id = :p LIMIT 1"),
            {"p": pin},
        ).fetchone()
        if row:
            return row[0]
        stripped = pin.lstrip("0")
        if pin.isdigit() and stripped:
            row = db.execute(text(
                "SELECT emp_code FROM personnel "
                "WHERE ltrim(attendance_id, '0') = :s "   # stored IDs are digits-only
                "LIMIT 2"), {"s": stripped}).fetchall()
            if len(row) == 1:
                return row[0][0]
            if len(row) > 1:
                logger.warning("PIN %r matches several attendance IDs ignoring leading "
                               "zeros — treating as an emp_code", pin)
    except Exception as e:
        logger.warning("resolve_emp_code(%r) lookup failed, using as-is: %s", pin, e)
        try:
            db.rollback()
        except Exception:
            pass
    return pin


def rewrite_command(db: Session, cmd: str) -> str:
    """Replace every PIN=<emp_code> in a reader command with that employee's PIN."""
    if not cmd or "PIN=" not in cmd:
        return cmd
    return _CMD_PIN_RE.sub(lambda m: "PIN=" + pin_for(db, m.group(1)), cmd)
