"""
SeamlessHR → readers, in one pass:

  1. pull the employee master       (new starters appear, leavers become inactive)
  2. pull approved leave            (on-leave staff are left off muster lists)
  3. set Attendance IDs              (the reader PIN = the ID SeamlessHR matches punches on),
                                     by the rule in Settings → HR Integration
  4. update the readers             door panels (C3/inBio) and T&A terminals: new people and
                                     card changes are sent, leavers removed — only changes

Runs nightly before the attendance push, and from Settings → HR Integration →
"Pull staff & update readers". A SeamlessHR webhook (joiner / change / leaver)
runs steps 3-4 straight away.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def code_digit_pairs(db: Session, emp_codes: Optional[list] = None) -> Dict[str, str]:
    """emp_code → its digits, for SeamlessHR-managed active staff ("MARC 14256" → "14256")."""
    q = "SELECT emp_code FROM personnel WHERE is_active AND hr_source = 'SEAMLESSHR'"
    params: Dict[str, Any] = {}
    if emp_codes:
        q += " AND emp_code = ANY(:c)"
        params["c"] = list(emp_codes)
    out = {}
    for (code,) in db.execute(text(q), params).fetchall():
        digits = re.sub(r"\D", "", code or "").lstrip("0") or ""
        if digits:
            out[code] = digits
    return out


async def set_attendance_ids(db: Session, emp_codes: Optional[list] = None) -> Dict[str, Any]:
    from .seamlesshr_service import get_config, adopt_attendance_ids, apply_attendance_ids
    cfg = get_config(db) or {}
    rule = (cfg.get("options") or {}).get("attendance_id_rule", "seamlesshr")
    if rule == "code_digits":
        rep = apply_attendance_ids(db, code_digit_pairs(db, emp_codes))
    elif rule == "seamlesshr":
        rep = await adopt_attendance_ids(db)
    else:
        rep = {"note": "manual — Attendance IDs are imported or typed in ApexPOB"}
    rep["rule"] = rule
    return rep


def update_readers(db: Session) -> Dict[str, Any]:
    """Send changes to every door panel and T&A terminal (no-op where nothing changed)."""
    from .panel_sync import sync_all
    from .ta_sync import sync_all_terminals
    out: Dict[str, Any] = {}
    try:
        out["door_panels"] = sync_all(db)
    except Exception as e:  # noqa: BLE001 — one family failing must not stop the other
        logger.error("Reader update (door panels) failed: %s", e)
        db.rollback()
        out["door_panels"] = {"error": str(e)}
    try:
        out["ta_terminals"] = sync_all_terminals(db)
    except Exception as e:  # noqa: BLE001
        logger.error("Reader update (T&A terminals) failed: %s", e)
        db.rollback()
        out["ta_terminals"] = {"error": str(e)}
    return out


def readiness(db: Session) -> Dict[str, int]:
    r = db.execute(text("""
        SELECT count(*) AS active,
               count(*) FILTER (WHERE COALESCE(attendance_id, '') <> '') AS with_attendance_id,
               count(card_number) AS with_card
        FROM personnel WHERE is_active""")).mappings().first()
    return dict(r)


async def refresh_staff_and_readers(db: Session, triggered_by: str = "manual") -> Dict[str, Any]:
    from .seamlesshr_service import pull_employees, pull_leave
    result: Dict[str, Any] = {}
    staff = await pull_employees(db, triggered_by=triggered_by)
    result["staff"] = staff
    if staff.get("error"):
        result["error"] = staff["error"]
        return result                      # never touch readers on a failed pull
    try:
        result["on_leave"] = (await pull_leave(db, triggered_by=triggered_by)).get("on_leave", 0)
    except Exception as e:  # noqa: BLE001
        result["on_leave_error"] = str(e)
    result["attendance_ids"] = await set_attendance_ids(db)
    result["readers"] = update_readers(db)
    result["readiness"] = readiness(db)
    logger.info("Staff → readers refresh (%s): staff=%s ids=%s readiness=%s", triggered_by,
                {k: staff.get(k) for k in ("created", "updated", "deactivated", "total")},
                {k: result["attendance_ids"].get(k) for k in ("rule", "updated", "conflicts", "error")},
                result["readiness"])
    return result


async def person_changed(db: Session, emp_code: str) -> Dict[str, Any]:
    """A webhook changed one person: give them an Attendance ID if the rule allows,
    then send changes to the readers (a leaver is removed)."""
    ids = await set_attendance_ids(db, [emp_code]) if emp_code else {}
    return {"attendance_ids": ids, "readers": update_readers(db)}
