"""
Keep the T&A terminals (standalone ZKTeco attendance readers on ADMS, e.g. F18)
in step with ApexPOB — the same people and cards as the door controllers, but over
the ADMS command queue:

  * active staff with an Attendance ID → DATA UPDATE USERINFO (name + card), sent
    when new or when their card changed;
  * someone ApexPOB put on a terminal who is no longer active → DATA DELETE
    USERINFO (removes them, with their fingerprints/face, from that terminal).

Commands carry PIN=<emp_code>; the queue rewrites it to the reader PIN (Attendance
ID) exactly as every other reader command. Fingerprints / faces are still enrolled
at the terminal itself.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def ta_terminals(db: Session) -> List[str]:
    """Attendance terminals reached over ADMS (never controller-port mirrors)."""
    return [r[0] for r in db.execute(text("""
        SELECT sn FROM iclock_terminal
        WHERE COALESCE(NULLIF(reader_purpose, ''), 'ATTENDANCE') = 'ATTENDANCE'
          AND LOWER(COALESCE(connection_mode, 'adms')) IN ('adms', 'both')
        ORDER BY sn""")).fetchall()]


def _userinfo(u: Dict) -> str:
    """Only send fields ApexPOB owns: a blank Passwd= / Card= would WIPE a password or
    card that was set at the terminal itself."""
    name = (u.get("name") or u["emp_code"]).replace("\t", " ")[:24]
    cmd = f"DATA UPDATE USERINFO PIN={u['emp_code']}\tName={name}\tPri=0"
    if u.get("card_no"):
        cmd += f"\tCard={u['card_no']}"
    return cmd + "\tGrp=1\tTZ=0"


def sync_terminal(db: Session, sn: str, emp_codes: Optional[List[str]] = None) -> Dict:
    from .panel_sync import active_panel_users
    from ..api.adms_protocol import queue_command
    wanted, skipped = active_panel_users(db, emp_codes)
    want = {u["pin"]: u for u in wanted}
    rows = db.execute(text("SELECT pin, emp_code, card_no, state FROM ta_terminal_user WHERE sn = :s"), {"s": sn}).fetchall()
    have = {r.pin: r for r in rows if r.state == "queued"}
    to_load = [u for p, u in want.items() if p not in have or (have[p].card_no or "") != (u["card_no"] or "")]
    to_remove = [] if emp_codes else [have[p] for p in have if p not in want]

    for u in to_load:
        queue_command(sn, _userinfo(u), db)
        db.execute(text("""
            INSERT INTO ta_terminal_user (sn, pin, emp_code, card_no, state, updated_at)
            VALUES (:s, :p, :e, :c, 'queued', NOW())
            ON CONFLICT (sn, pin) DO UPDATE SET emp_code = EXCLUDED.emp_code, card_no = EXCLUDED.card_no,
                state = 'queued', updated_at = NOW()"""), {"s": sn, "p": u["pin"], "e": u["emp_code"], "c": u["card_no"]})

    removed = 0
    for r in to_remove:
        # PIN=<emp_code> is rewritten to that person's CURRENT Attendance ID. Only use it
        # if that is still the PIN we loaded; never send a bare number that could be
        # read as somebody else's employee code.
        current = db.execute(text("SELECT attendance_id FROM personnel WHERE emp_code = :e"), {"e": r.emp_code}).scalar()
        if str(current or "") != r.pin:
            logger.warning("T&A %s: %s's PIN changed since it was loaded (%s → %s) — remove it at the terminal",
                           sn, r.emp_code, r.pin, current)
            continue
        queue_command(sn, f"DATA DELETE USERINFO PIN={r.emp_code}", db)
        db.execute(text("UPDATE ta_terminal_user SET state = 'removed', updated_at = NOW() WHERE sn = :s AND pin = :p"),
                   {"s": sn, "p": r.pin})
        removed += 1
    db.commit()
    return {"terminal": sn, "loaded": len(to_load), "removed": removed, "skipped_no_attendance_id": skipped}


def sync_all_terminals(db: Session, emp_codes: Optional[List[str]] = None) -> List[Dict]:
    return [sync_terminal(db, sn, emp_codes) for sn in ta_terminals(db)]
