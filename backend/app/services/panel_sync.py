"""
Keep each ZKTeco C3 / inBio panel's user list in step with ApexPOB.

* Active staff with an Attendance ID are loaded (panel user ID = Attendance ID,
  card = personnel.card_number, keypad PIN = their door PIN) and authorised on
  every door of the panel.
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
    from ..core.crypto import decrypt_secret
    q = """SELECT emp_code, attendance_id, card_number, door_pin_enc,
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
        door_pin = ""
        if r.door_pin_enc:
            try:
                door_pin = decrypt_secret(r.door_pin_enc) or ""
            except Exception:  # noqa: BLE001 — a bad secret must not stop the sync
                door_pin = ""
        users.append({"pin": str(r.attendance_id), "emp_code": r.emp_code,
                      "card_no": str(r.card_number) if r.card_number else "", "name": (r.name or "")[:24],
                      "password": door_pin})
    return users, skipped


def _secret_hash(u: Dict) -> str:
    import hashlib
    return hashlib.sha256(f"{u.get('pin')}:{u.get('password') or ''}".encode()).hexdigest() if u.get("password") else ""


def _record(db: Session, ctrl_id: int, users: List[Dict], state: str, failed: Dict[str, str]) -> None:
    for u in users:
        bad = u["pin"] in failed
        db.execute(text("""
            INSERT INTO controller_user (controller_id, pin, emp_code, card_no, secret_hash, state, last_error, updated_at)
            VALUES (:c, :p, :e, :card, :h, :s, :err, NOW())
            ON CONFLICT (controller_id, pin) DO UPDATE SET emp_code = EXCLUDED.emp_code, card_no = EXCLUDED.card_no,
                secret_hash = EXCLUDED.secret_hash, state = EXCLUDED.state, last_error = EXCLUDED.last_error, updated_at = NOW()
        """), {"c": ctrl_id, "p": u["pin"], "e": u.get("emp_code"), "card": u.get("card_no") or "",
               "h": _secret_hash(u), "s": "failed" if bad else state, "err": failed.get(u["pin"])})
    db.commit()


def load_users(db: Session, ctrl, users: List[Dict], door_nos: Optional[List[int]] = None) -> Dict:
    """Write these users to one panel and remember the result. door_nos defaults to
    every door (staff); visitors pass a narrower list (no secure doors)."""
    from .zkteco import c3_zkaccess
    if not users:
        return {"pushed": 0, "failed": []}
    doors = door_nos if door_nos is not None else list(range(1, (ctrl.door_count or 1) + 1))
    res = c3_zkaccess.enroll_users(ctrl.ip_address, users, door_nos=doors,
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
    from .visitor_access import visitor_panel_users, visitor_doors
    wanted, skipped = active_panel_users(db)
    # Visitors on site with a card stay loaded (re-written nightly so their end date
    # rolls forward); once they've left they drop out of `want` and are removed.
    visitors = visitor_panel_users(db)
    want = {u["pin"]: u for u in wanted}
    rows = db.execute(text("SELECT pin, card_no, secret_hash, state FROM controller_user WHERE controller_id = :c"),
                      {"c": ctrl.id}).fetchall()
    have = {r.pin: r for r in rows if r.state == "loaded"}
    to_load = [u for p, u in want.items() if p not in have or (have[p].card_no or "") != (u["card_no"] or "")
               or (have[p].secret_hash or "") != _secret_hash(u)]
    keep = set(want) | {v["pin"] for v in visitors}
    to_remove = [p for p in have if p not in keep]
    out = {"controller": ctrl.name, "to_load": len(to_load), "visitors": len(visitors),
           "to_remove": len(to_remove), "skipped_no_attendance_id": skipped}
    out["load"] = load_users(db, ctrl, to_load)
    if visitors:
        out["visitor_load"] = load_users(db, ctrl, visitors, door_nos=visitor_doors(db, ctrl))
    out["remove"] = remove_users(db, ctrl, to_remove)
    logger.info("Panel sync %s: %s", ctrl.name, {k: v for k, v in out.items() if k not in ("load", "remove", "visitor_load")})
    return out


def sync_all(db: Session) -> List[Dict]:
    from ..models.access_controller import AccessController
    return [sync_controller(db, c) for c in db.query(AccessController).all()]
