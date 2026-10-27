"""
Keep each ZKTeco C3 / inBio panel's user list in step with ApexPOB.

* Active staff with an Attendance ID are loaded (PIN = Attendance ID, card =
  personnel.card_number) and authorised on every door of the panel.
* Someone ApexPOB loaded who is no longer active (leaver, suspended, or lost their
  ID) is REMOVED by re-writing their record with an end date of yesterday and no
  card — the panel then refuses them ("card expired"). Panel users ApexPOB did not
  load are never touched.
* What was loaded is remembered in controller_user, so a re-sync only sends changes.

Runs nightly (Celery) and on demand (Controllers → Sync users). The panel write is
the same operation as enrolment — confirm it on the first real panel.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def active_panel_users(db: Session, emp_codes: Optional[List[str]] = None) -> Tuple[List[Dict], int]:
    """Active staff as panel user records; also returns how many were skipped (no Attendance ID)."""
    from .device_pin import is_valid_pin
    q = """SELECT emp_code, attendance_id, card_number,
                  COALESCE(NULLIF(full_name, ''), TRIM(CONCAT(first_name, ' ', last_name))) AS name
           FROM personnel
           WHERE is_active AND COALESCE(UPPER(status), 'ACTIVE') NOT IN ('TERMINATED', 'INACTIVE', 'SUSPENDED')"""
    params = {}
    if emp_codes:
        q += " AND emp_code = ANY(:codes)"
        params["codes"] = list(emp_codes)
    users, skipped = [], 0
    for r in db.execute(text(q), params).fetchall():
        if not is_valid_pin(r.attendance_id):
            skipped += 1
            continue
        users.append({"pin": str(r.attendance_id), "emp_code": r.emp_code,
                      "card_no": str(r.card_number) if r.card_number else "", "name": (r.name or "")[:24]})
    return users, skipped


def _record(db: Session, ctrl_id: int, users: List[Dict], state: str, failed: Dict[str, str]) -> None:
    for u in users:
        bad = u["pin"] in failed
        db.execute(text("""
            INSERT INTO controller_user (controller_id, pin, emp_code, card_no, state, last_error, updated_at)
            VALUES (:c, :p, :e, :card, :s, :err, NOW())
            ON CONFLICT (controller_id, pin) DO UPDATE SET emp_code = EXCLUDED.emp_code, card_no = EXCLUDED.card_no,
                state = EXCLUDED.state, last_error = EXCLUDED.last_error, updated_at = NOW()
        """), {"c": ctrl_id, "p": u["pin"], "e": u.get("emp_code"), "card": u.get("card_no") or "",
               "s": "failed" if bad else state, "err": failed.get(u["pin"])})
    db.commit()


def load_users(db: Session, ctrl, users: List[Dict]) -> Dict:
    """Write these users to one panel and remember the result."""
    from .zkteco import c3_zkaccess
    if not users:
        return {"pushed": 0, "failed": []}
    res = c3_zkaccess.enroll_users(ctrl.ip_address, users, door_nos=list(range(1, (ctrl.door_count or 1) + 1)),
                                   port=ctrl.port or 4370, password=ctrl.comm_password or "")
    if not res.get("success"):
        _record(db, ctrl.id, users, "failed", {u["pin"]: res.get("error", "panel unreachable") for u in users})
        return {"pushed": 0, "failed": [{"pin": u["pin"], "error": res.get("error")} for u in users]}
    failed = {f["pin"]: f.get("error", "") for f in res.get("failed") or []}
    _record(db, ctrl.id, users, "loaded", failed)
    return {"pushed": res.get("pushed", 0), "failed": res.get("failed") or []}


def remove_users(db: Session, ctrl, pins: List[str]) -> Dict:
    """Expire users on a panel: end date yesterday, no card, no doors."""
    from .zkteco import c3_zkaccess
    if not pins:
        return {"removed": 0, "failed": []}
    yesterday = int((date.today() - timedelta(days=1)).strftime("%Y%m%d"))
    users = [{"pin": p, "card_no": "", "name": "", "expire": yesterday} for p in pins]
    res = c3_zkaccess.enroll_users(ctrl.ip_address, users, door_nos=[], port=ctrl.port or 4370,
                                   password=ctrl.comm_password or "")
    failed = {f["pin"]: f.get("error", "") for f in res.get("failed") or []} if res.get("success") else \
        {p: res.get("error", "panel unreachable") for p in pins}
    _record(db, ctrl.id, [{"pin": p} for p in pins], "removed", failed)
    return {"removed": len(pins) - len(failed), "failed": [{"pin": p, "error": e} for p, e in failed.items()]}


def sync_controller(db: Session, ctrl) -> Dict:
    wanted, skipped = active_panel_users(db)
    want = {u["pin"]: u for u in wanted}
    rows = db.execute(text("SELECT pin, card_no, state FROM controller_user WHERE controller_id = :c"),
                      {"c": ctrl.id}).fetchall()
    have = {r.pin: r for r in rows if r.state == "loaded"}
    to_load = [u for p, u in want.items() if p not in have or (have[p].card_no or "") != (u["card_no"] or "")]
    to_remove = [p for p in have if p not in want]
    out = {"controller": ctrl.name, "to_load": len(to_load), "to_remove": len(to_remove),
           "skipped_no_attendance_id": skipped}
    out["load"] = load_users(db, ctrl, to_load)
    out["remove"] = remove_users(db, ctrl, to_remove)
    logger.info("Panel sync %s: %s", ctrl.name, {k: v for k, v in out.items() if k not in ("load", "remove")})
    return out


def sync_all(db: Session) -> List[Dict]:
    from ..models.access_controller import AccessController
    return [sync_controller(db, c) for c in db.query(AccessController).all()]
