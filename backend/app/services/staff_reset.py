"""
Global-admin "remove all staff and pull them again from SeamlessHR".

Two modes
---------
keep_history (default, recommended)
    Staff records and their live data (zone stays, POB rows, assignments, payroll
    rows …) are removed. Attendance HISTORY is kept: it hangs off the reader mirror
    (personnel_employee), which is kept inactive (trigger flag pob.keep_mirror) and
    re-attaches when the same employee code is pulled back. What ApexPOB owns — not
    SeamlessHR — is snapshotted and put back on the re-pulled record: Attendance ID,
    card, door PIN, badge, photo, and on-board status/location (so POB and musters
    stay right). Readers are left alone; returning people are unchanged on them.

everything
    A clean start (e.g. sandbox → Marconi tenant): staff, their mirror and all
    history (daily attendance, punches, leave, overtime, biometrics…) are removed,
    everyone ApexPOB loaded is removed from the door panels and T&A terminals, and
    nothing is restored.

Safety: global admin only · typed confirmation · refused while a muster is
running · SeamlessHR must answer BEFORE anything is deleted (when repopulating) ·
every affected table is copied to a backup schema first · audit-logged · the
progress of each run is stored in staff_reset_job.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CONFIRM_PHRASE = "DELETE ALL STAFF"

# ApexPOB-owned fields put back on the re-pulled record (keep_history mode).
RESTORE_FIELDS = ["attendance_id", "card_number", "door_pin_enc", "door_pin_set_at", "badge_id",
                  "is_onboard", "is_pob", "pob_since", "current_zone_id", "current_location",
                  "last_seen", "photo_url", "biometric_enrolled"]

# Tables keyed by emp_code (no foreign key) cleared in "everything" mode.
EMP_CODE_HISTORY = ["iclock_transaction", "controller_user", "ta_terminal_user"]


def _referencing(db: Session, table: str) -> List[Tuple[str, str, str, bool, str]]:
    """(table, column, on_delete, nullable, referenced column) for every foreign key
    pointing at `table` (single-column keys)."""
    rows = db.execute(text("""
        SELECT c.conrelid::regclass::text, a.attname, c.confdeltype, NOT a.attnotnull, ra.attname
        FROM pg_constraint c
        JOIN pg_attribute a  ON a.attrelid = c.conrelid  AND a.attnum = c.conkey[1]
        JOIN pg_attribute ra ON ra.attrelid = c.confrelid AND ra.attnum = c.confkey[1]
        WHERE c.contype = 'f' AND c.confrelid = CAST(:t AS regclass) AND array_length(c.conkey, 1) = 1
    """), {"t": table}).fetchall()
    return [(r[0], r[1], r[2], bool(r[3]), r[4]) for r in rows]


def _purge(db: Session, table: str, where: str, counts: Dict[str, int], keep_links: bool, depth: int = 0) -> None:
    """Delete rows of `table` matching `where`, first dealing with anything that points
    at them, at any depth: rows the database cascades/nulls itself are left to it;
    a nullable link is cleared when `keep_links` (keep the row, drop the link),
    otherwise the pointing rows are purged first."""
    if depth > 6:
        raise RuntimeError(f"link chain too deep at {table}")
    for t, c, d, nullable, refcol in _referencing(db, table):
        if d in ("c", "n", "d") or t == table:
            continue
        sub = f'"{c}" IN (SELECT "{refcol}" FROM "{table}" WHERE {where})'
        if keep_links and nullable:
            n = db.execute(text(f'UPDATE "{t}" SET "{c}" = NULL WHERE {sub}')).rowcount
            if n:
                counts[f"{t}.{c} (unlinked)"] = counts.get(f"{t}.{c} (unlinked)", 0) + n
        else:
            _purge(db, t, sub, counts, keep_links, depth + 1)
    n = db.execute(text(f'DELETE FROM "{table}" WHERE {where}')).rowcount
    if n:
        counts[table] = counts.get(table, 0) + n


def _affected_tables(db: Session, table: str, seen=None) -> set:
    seen = seen if seen is not None else set()
    if table in seen:
        return seen
    seen.add(table)
    for t, *_ in _referencing(db, table):
        _affected_tables(db, t, seen)
    return seen


def _job(db: Session, job_id: int, **fields) -> None:
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    params = {k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else v) for k, v in fields.items()}
    params["id"] = job_id
    db.execute(text(f"UPDATE staff_reset_job SET {sets} WHERE id = :id"), params)
    db.commit()


def _step(db: Session, job_id: int, steps: List[Dict], name: str, **info) -> None:
    steps.append({"step": name, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **info})
    _job(db, job_id, steps=steps)
    logger.warning("Staff reset #%s: %s %s", job_id, name, info or "")


def preflight(db: Session, mode: str, repopulate: bool) -> Dict[str, Any]:
    """Everything that must be true before anything is deleted."""
    out: Dict[str, Any] = {"ok": True, "problems": []}
    if db.execute(text("SELECT 1 FROM mustering_event WHERE status = 0 LIMIT 1")).scalar():
        out["problems"].append("A muster is running — end it first.")
    if repopulate:
        ok, why = seamlesshr_answers(db)
        if not ok:
            out["problems"].append(f"SeamlessHR is not returning staff right now ({why}) — nothing was deleted. "
                                   f"Try again later, or untick 'pull staff back'.")
    out["staff"] = db.execute(text("SELECT count(*) FROM personnel")).scalar()
    out["ok"] = not out["problems"]
    return out


def seamlesshr_answers(db: Session) -> Tuple[bool, str]:
    import asyncio
    import httpx
    from .seamlesshr_service import get_config, build_auth_headers
    cfg = get_config(db)
    if not cfg:
        return False, "not configured"

    async def probe():
        headers = await build_auth_headers(cfg)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(cfg["api_base_url"] + cfg.get("employee_endpoint", "/v1/employees"),
                            headers=headers,
                            # same page size the real pull uses — the sandbox has failed on
                            # larger pages while answering tiny ones
                            params={"page": 1, "limit": int((cfg.get("options") or {}).get("employee_limit") or 25)})
            return r.status_code, r.text[:200]
    try:
        try:
            asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(1) as ex:
                status, body = ex.submit(lambda: asyncio.run(probe())).result()
        except RuntimeError:
            status, body = asyncio.run(probe())
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:120]
    return (status == 200, f"HTTP {status}" if status != 200 else "ok")


def backup(db: Session, job_id: int, tables: List[str]) -> str:
    schema = f"staff_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{job_id}"
    db.execute(text(f'CREATE SCHEMA "{schema}"'))
    for t in sorted(set(tables)):
        db.execute(text(f'CREATE TABLE "{schema}"."{t}" AS TABLE public."{t}"'))
    db.commit()
    return schema


def wipe(db: Session, mode: str, job_id: int, steps: List[Dict]) -> Dict[str, Any]:
    """Delete staff (+ linked data per mode). One transaction; rolls back on any error."""
    keep = mode == "keep_history"
    tables = list(_affected_tables(db, "personnel") | ({"personnel_employee"} if keep else _affected_tables(db, "personnel_employee")))
    if not keep:
        tables += [t for t in EMP_CODE_HISTORY if db.execute(text("SELECT to_regclass(:t)"), {"t": t}).scalar()]
    schema = backup(db, job_id, tables)
    _step(db, job_id, steps, "backup", schema=schema, tables=len(set(tables)))

    snapshot = []
    if keep:
        cols = ", ".join(["emp_code"] + RESTORE_FIELDS)
        snapshot = [dict(r) for r in db.execute(text(f"SELECT {cols} FROM personnel")).mappings().all()]

    deleted: Dict[str, int] = {}
    try:
        if keep:
            # Mirror rows (and the history on them) stay; the trigger marks them inactive.
            db.execute(text("SELECT set_config('pob.keep_mirror', 'on', true)"))
            # Rows that only point at a person lose the link but stay (access logs,
            # transport history…); live per-person data that can't exist without the
            # person goes (zone stays, POB rows, assignments…).
            _purge(db, "personnel", "TRUE", deleted, keep_links=True)
        else:
            for t in EMP_CODE_HISTORY:
                if db.execute(text("SELECT to_regclass(:t)"), {"t": t}).scalar():
                    n = db.execute(text(f'DELETE FROM "{t}"')).rowcount
                    if n:
                        deleted[t] = n
            # Mirror side first (its history), then the people — deleting a person
            # makes the trigger delete its mirror, which history would block.
            _purge(db, "personnel_employee", "TRUE", deleted, keep_links=False)
            _purge(db, "personnel", "TRUE", deleted, keep_links=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    deleted = {k: v for k, v in deleted.items() if v}
    _step(db, job_id, steps, "deleted", rows=deleted)
    return {"backup_schema": schema, "snapshot": snapshot, "deleted": deleted}


def restore_owned_fields(db: Session, snapshot: List[Dict]) -> int:
    """Put ApexPOB-owned fields back on re-pulled people (matched by employee code)."""
    restored = 0
    sets = ", ".join(f"{f} = :{f}" for f in RESTORE_FIELDS)
    for row in snapshot:
        params = {f: row.get(f) for f in RESTORE_FIELDS}
        params["emp_code"] = row["emp_code"]
        try:
            n = db.execute(text(f"UPDATE personnel SET {sets} WHERE emp_code = :emp_code"), params).rowcount
            db.commit()
            restored += n
        except Exception as e:  # noqa: BLE001 — e.g. an Attendance ID now held by someone else
            db.rollback()
            params["attendance_id"] = None
            params["card_number"] = None
            db.execute(text(f"UPDATE personnel SET {sets} WHERE emp_code = :emp_code"), params)
            db.commit()
            logger.warning("Restore for %s without ID/card (conflict): %s", row["emp_code"], e)
            restored += 1
    return restored


def remove_everyone_from_readers(db: Session) -> Dict[str, Any]:
    """Before an 'everything' wipe: take every user ApexPOB loaded off every reader."""
    from ..models.access_controller import AccessController
    from .panel_sync import remove_users
    from ..api.adms_protocol import queue_command
    out: Dict[str, Any] = {"panels": {}, "ta": 0}
    for ctrl in db.query(AccessController).all():
        pins = [r[0] for r in db.execute(text("SELECT pin FROM controller_user WHERE controller_id = :c AND state = 'loaded'"),
                                         {"c": ctrl.id}).fetchall()]
        try:
            out["panels"][ctrl.name] = remove_users(db, ctrl, pins).get("removed", 0)
        except Exception as e:  # noqa: BLE001
            out["panels"][ctrl.name] = f"error: {e}"
    for sn, emp_code in db.execute(text("SELECT sn, emp_code FROM ta_terminal_user WHERE state = 'queued'")).fetchall():
        queue_command(sn, f"DATA DELETE USERINFO PIN={emp_code}", db)   # person still exists → correct PIN
        out["ta"] += 1
    db.commit()
    return out


async def run_reset(job_id: int, mode: str, repopulate: bool) -> None:
    """The background job. Its own session; every step written to staff_reset_job."""
    from ..core.database import SessionLocal
    from .hr_reader_pipeline import set_attendance_ids, update_readers, readiness
    from .seamlesshr_service import pull_employees, pull_leave
    db = SessionLocal()
    steps: List[Dict] = []
    try:
        _job(db, job_id, state="running")
        if mode == "everything":
            _step(db, job_id, steps, "readers_cleared", **remove_everyone_from_readers(db))
        w = wipe(db, mode, job_id, steps)
        _job(db, job_id, backup_schema=w["backup_schema"])
        if not repopulate:
            _job(db, job_id, state="done", finished_at=datetime.now(timezone.utc))
            return
        staff = await pull_employees(db, triggered_by=f"staff_reset#{job_id}")
        if staff.get("error"):
            _step(db, job_id, steps, "pull_failed", error=staff["error"])
            _job(db, job_id, state="failed", error=f"Staff were removed but the pull failed: {staff['error']}. "
                                                   f"Press 'Pull staff & update readers' when SeamlessHR answers. "
                                                   f"Backup: {w['backup_schema']}",
                 finished_at=datetime.now(timezone.utc))
            return
        _step(db, job_id, steps, "pulled", created=staff.get("created"), updated=staff.get("updated"), total=staff.get("total"))
        if mode == "keep_history" and w["snapshot"]:
            _step(db, job_id, steps, "restored", people=restore_owned_fields(db, w["snapshot"]))
        try:
            _step(db, job_id, steps, "leave", on_leave=(await pull_leave(db, triggered_by=f"staff_reset#{job_id}")).get("on_leave", 0))
        except Exception as e:  # noqa: BLE001
            _step(db, job_id, steps, "leave_failed", error=str(e))
        ids = await set_attendance_ids(db)
        _step(db, job_id, steps, "attendance_ids", rule=ids.get("rule"), updated=ids.get("updated"), error=ids.get("error"))
        _step(db, job_id, steps, "readers", **{"summary": str(update_readers(db))[:500]})
        _job(db, job_id, state="done", result=readiness(db), finished_at=datetime.now(timezone.utc))
    except Exception as e:  # noqa: BLE001
        logger.exception("Staff reset #%s failed", job_id)
        db.rollback()
        _job(db, job_id, state="failed", error=str(e)[:1000], finished_at=datetime.now(timezone.utc))
    finally:
        db.close()
