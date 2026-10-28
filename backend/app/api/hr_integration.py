"""
HR Integration API — SeamlessHR connector management.

Endpoints:
  GET    /config            — get current integration config (API key masked)
  PUT    /config            — save API credentials and settings
  POST   /test-connection   — verify credentials against SeamlessHR
  POST   /sync              — trigger manual sync for a specific date
  GET    /sync/history      — sync log with status and record counts
  GET    /sync/status       — last sync summary + next scheduled run
  GET    /preview/{date}    — preview attendance records that would be sent
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..services.seamlesshr_service import (
    get_config, push_attendance, test_connection,
    _build_attendance_records, pull_employees, pull_leave, handle_webhook_event,
    adopt_attendance_ids, apply_attendance_ids,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_admin(current_user=Depends(get_current_user)):
    if not (current_user.is_superuser or getattr(current_user, "is_global_admin", False)):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConfigIn(BaseModel):
    api_base_url:        str
    # SeamlessHR authenticates with a PAIR of static header credentials:
    #   x-client-secret ← api_key (encrypted at rest)
    #   x-client-id     ← client_id (not secret, stored in options)
    api_key:             Optional[str] = None   # None / empty = keep existing (sent when key field is masked)
    client_id:           Optional[str] = None
    org_id:              Optional[str] = None
    auth_header_name:    Optional[str] = "Authorization"
    attendance_endpoint: Optional[str] = "/biometric/process"
    employee_endpoint:   Optional[str] = "/v1/employees"
    is_enabled:          Optional[bool] = False
    sync_time:           Optional[str] = "00:00"
    # Advanced connector mapping (auth scheme, payload shape, field names, formats).
    # None = keep existing / use defaults.
    options:             Optional[dict] = None


class SyncIn(BaseModel):
    sync_date: Optional[str] = None   # YYYY-MM-DD, defaults to yesterday
    force: bool = False               # re-send even if already sent (admin correction)
    allow_today: bool = False         # permit syncing a not-yet-finalized day


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_integration_config(
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):

    from ..services.seamlesshr_service import _DEFAULT_OPTIONS, _merge_options
    try:
        row = db.execute(text("""
            SELECT api_base_url, api_key, org_id, auth_header_name,
                   attendance_endpoint, employee_endpoint, is_enabled, sync_time, options
            FROM hr_integration_config LIMIT 1
        """)).fetchone()
    except Exception:
        row = None

    if not row:
        return {
            "configured": False,
            # SeamlessHR's published coordinates. Swap the sandbox host for the
            # live one once they issue production credentials.
            "api_base_url": "https://api-sandbox.seamlesshr.app",
            "api_key": "",
            "client_id": "",
            "org_id": "",
            "auth_header_name": "Authorization",
            "attendance_endpoint": "/biometric/process",
            "employee_endpoint": "/v1/employees",
            "is_enabled": False,
            "sync_time": "00:00",
            "options": dict(_DEFAULT_OPTIONS),
        }

    # Mask the API key — only show last 6 chars
    # Mask the PLAINTEXT secret, not the stored ciphertext — otherwise the admin
    # sees the tail of an encrypted blob and cannot recognise their own credential.
    from ..core.crypto import decrypt_secret
    try:
        key = decrypt_secret(row[1]) or ""
    except Exception:
        key = ""
    masked = ("•" * max(0, len(key) - 4)) + key[-4:] if len(key) > 4 else "••••"
    _opts = _merge_options(row[8] if len(row) > 8 else None)

    return {
        "configured":            bool(row[0] and row[1]),
        "api_base_url":          row[0],
        "api_key_masked":        masked,
        # Not a secret — shown in full so the admin can confirm the pairing.
        "client_id":             _opts.get("client_id", ""),
        "org_id":                row[2],
        "auth_header_name":      row[3],
        "attendance_endpoint":   row[4],
        "employee_endpoint":     row[5],
        "is_enabled":            row[6],
        "sync_time":             row[7] or "00:00",
        "options":               _merge_options(row[8] if len(row) > 8 else None),
    }


@router.put("/config")
async def save_integration_config(
    body: ConfigIn,
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):


    # Determine the real API key to store.
    # Keep existing if: key is absent (None), empty, or looks masked (starts with "*").
    # This handles the case where the frontend sends the masked display value when
    # the user didn't change the key.
    raw_key = (body.api_key or "").strip()
    keep_existing = (not raw_key) or raw_key.startswith("*")

    from ..core.crypto import encrypt_secret
    from ..services.attendance_export import validate_integration_base_url, IntegrationUrlError

    # SSRF + TLS guard: never store/send a credential to a non-public or cleartext URL.
    try:
        safe_base_url = validate_integration_base_url(body.api_base_url)
    except IntegrationUrlError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if keep_existing:
        # Existing key is stored encrypted (or legacy plaintext) — preserve it verbatim.
        row = db.execute(text("SELECT api_key FROM hr_integration_config LIMIT 1")).fetchone()
        existing_key = row[0] if row else None
        if not existing_key:
            raise HTTPException(status_code=400, detail="API key is required for the initial setup")
        api_key = existing_key  # already stored form; encrypt_secret() below is idempotent
    else:
        api_key = raw_key

    # Encrypt at rest (idempotent: re-encrypting an already-encrypted value is a no-op).
    api_key = encrypt_secret(api_key)

    # Preserve existing options if the caller didn't send any (partial saves).
    import json as _json
    if body.options is not None:
        merged_options = dict(body.options)
    else:
        prev = db.execute(text("SELECT options FROM hr_integration_config LIMIT 1")).fetchone()
        merged_options = dict(prev[0]) if (prev and prev[0]) else {}

    # client_id is a first-class form field but lives inside options, so the
    # connector stays generic. Blank means "leave whatever is already stored"
    # — same keep-existing rule the API key uses.
    if body.client_id is not None and body.client_id.strip():
        merged_options["client_id"] = body.client_id.strip()

    options_json = _json.dumps(merged_options) if merged_options else None

    db.execute(text("DELETE FROM hr_integration_config"))
    db.execute(text("""
        INSERT INTO hr_integration_config
          (api_base_url, api_key, org_id, auth_header_name,
           attendance_endpoint, employee_endpoint, is_enabled, sync_time, options, updated_at)
        VALUES
          (:base_url, :api_key, :org_id, :auth_name,
           :att_ep, :emp_ep, :enabled, :sync_time, CAST(:options AS JSONB), NOW())
    """), {
        "base_url":  safe_base_url,
        "api_key":   api_key,
        "org_id":    body.org_id,
        "auth_name": body.auth_header_name or "Authorization",
        "att_ep":    body.attendance_endpoint or "/biometric/process",
        "emp_ep":    body.employee_endpoint or "/v1/employees",
        "enabled":   body.is_enabled,
        "sync_time": body.sync_time or "00:00",
        "options":   options_json,
    })
    db.commit()
    logger.info(f"HR integration config updated by {current_user.email}")
    return {"success": True, "message": "Configuration saved"}


# ── Test connection ───────────────────────────────────────────────────────────

@router.post("/test-connection")
async def test_integration_connection(
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):
    cfg = get_config(db)
    if not cfg:
        raise HTTPException(status_code=400, detail="Integration not configured yet")
    result = await test_connection(cfg)
    return result


# ── Manual sync ───────────────────────────────────────────────────────────────

@router.post("/sync")
async def manual_sync(
    body: SyncIn,
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):
    sync_date = None
    if body.sync_date:
        try:
            sync_date = date.fromisoformat(body.sync_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format — use YYYY-MM-DD")

    result = await push_attendance(db, sync_date=sync_date, triggered_by=current_user.email,
                                   force=body.force, allow_today=body.allow_today)
    return result


@router.post("/pull-employees")
async def pull_employees_endpoint(
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):
    """Pull the employee master from SeamlessHR into ApexPOB personnel. Pulled records
    are marked as SeamlessHR-managed and become read-only here (SeamlessHR is the
    system of record). Then: leave, Attendance IDs (by the configured rule) and the
    readers (door panels + T&A terminals) are brought up to date."""
    from ..services.hr_reader_pipeline import refresh_staff_and_readers
    out = await refresh_staff_and_readers(db, triggered_by=getattr(current_user, "email", "manual"))
    if out.get("error"):
        raise HTTPException(status_code=502, detail=out["error"])
    # Keep the old top-level keys (created/updated/…) for existing callers.
    return {"success": True, **out["staff"], "on_leave": out.get("on_leave", 0),
            "attendance_ids": out.get("attendance_ids"), "readers": out.get("readers"),
            "readiness": out.get("readiness")}


class AttendanceIdItem(BaseModel):
    employee_code: str          # SeamlessHR employee code (staff_id)
    attendance_id: str          # SeamlessHR Attendance ID = the reader PIN


class AttendanceIdImport(BaseModel):
    items: list[AttendanceIdItem]


@router.get("/attendance-ids")
async def list_attendance_ids(
    q: str = "",
    status: str = "all",            # all | missing | assigned
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):
    """SeamlessHR-managed employees and the Attendance ID (= reader PIN) each one has.

    `missing` are the ones whose punches are held back from payroll until an ID is
    adopted. Inactive leavers are excluded: they no longer need a reader PIN."""
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    base = "FROM personnel WHERE hr_source = 'SEAMLESSHR' AND COALESCE(is_active, TRUE)"
    params: dict = {}
    where = ""
    if q.strip():
        where += " AND (emp_code ILIKE :q OR full_name ILIKE :q OR attendance_id ILIKE :q)"
        params["q"] = f"%{q.strip()}%"
    if status == "missing":
        where += " AND attendance_id IS NULL"
    elif status == "assigned":
        where += " AND attendance_id IS NOT NULL"

    counts = db.execute(text(
        "SELECT COUNT(*), COUNT(attendance_id) " + base)).fetchone()
    total = db.execute(text("SELECT COUNT(*) " + base + where), params).scalar() or 0
    rows = db.execute(text(
        "SELECT emp_code, full_name, department, attendance_id " + base + where +
        " ORDER BY (attendance_id IS NOT NULL), emp_code LIMIT :lim OFFSET :off"),
        {**params, "lim": page_size, "off": (page - 1) * page_size}).fetchall()
    return {
        "summary": {"employees": counts[0], "assigned": counts[1],
                    "missing": counts[0] - counts[1]},
        "total": total, "page": page, "page_size": page_size,
        "items": [{"emp_code": r[0], "name": r[1], "department": r[2],
                   "attendance_id": r[3]} for r in rows],
    }


@router.post("/adopt-attendance-ids")
async def adopt_attendance_ids_endpoint(
    days: int = 31,
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):
    """Adopt SeamlessHR's Attendance IDs: they become each employee's reader PIN and
    the attendanceId sent with every punch. Run after pull-employees."""
    result = await adopt_attendance_ids(db, days=days)
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    return {"success": True, **result}


@router.post("/import-attendance-ids")
async def import_attendance_ids_endpoint(
    body: AttendanceIdImport,
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):
    """Adopt Attendance IDs from an export supplied by SeamlessHR when the API key
    cannot read attendance records. Same validation as adopt-attendance-ids."""
    pairs = {i.employee_code: i.attendance_id for i in body.items}
    return {"success": True, **apply_attendance_ids(db, pairs)}


@router.post("/webhook")
async def seamlesshr_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive real-time employee events from SeamlessHR (create/update/deactivate).

    SeamlessHR calls this URL directly — it is NOT admin-authenticated; instead the
    request is verified via the `x-seamlesshr-signature` header (HMAC-SHA512 of the
    raw body with the configured webhook secret). On success the employee master is
    upserted (read-only in ApexPOB) or the leaver is offboarded.
    """
    import hmac
    import hashlib
    import json

    raw = await request.body()
    cfg = get_config(db)
    opts = cfg["options"] if cfg else {}
    # HMAC secret: dedicated webhook_secret if set, else fall back to the API secret.
    secret = (opts.get("webhook_secret") or (cfg["api_key"] if cfg else "")) or ""

    if secret:
        provided = request.headers.get("x-seamlesshr-signature", "") or ""
        expected = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, provided):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event = payload.get("event")
    data = payload.get("data") or {}
    result = handle_webhook_event(db, event, data, opts)
    # Joiner / change / leaver → readers now, not tonight.
    readers = None
    try:
        code_field = (opts.get("webhook_field_map") or {}).get("emp_code", "employee_code")
        code = str((data or {}).get(code_field) or "").strip()
        if code and not str(result).startswith("skipped"):
            from ..services.hr_reader_pipeline import person_changed
            readers = await person_changed(db, code)
    except Exception as e:  # noqa: BLE001 — never fail the webhook (SeamlessHR would retry-storm)
        logger.error("Webhook reader update failed: %s", e)
        db.rollback()
    return {"success": True, "event": event, "result": result, "readers_updated": readers is not None}


# ── Sync history ──────────────────────────────────────────────────────────────

@router.get("/sync/history")
async def get_sync_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):

    try:
        rows = db.execute(text("""
            SELECT id, sync_date, triggered_by, status,
                   records_built, records_sent, records_failed,
                   message, created_at
            FROM hr_sync_log
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    except Exception:
        return {"history": [], "total": 0}

    return {
        "history": [
            {
                "id":              r[0],
                "sync_date":       str(r[1]) if r[1] else None,
                "triggered_by":    r[2],
                "status":          r[3],
                "records_built":   r[4],
                "records_sent":    r[5],
                "records_failed":  r[6],
                "message":         r[7],
                "created_at":      r[8].isoformat() if r[8] else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }


# ── Sync status ───────────────────────────────────────────────────────────────

@router.get("/sync/status")
async def get_sync_status(
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):

    cfg = get_config(db)

    last = None
    try:
        row = db.execute(text("""
            SELECT status, records_sent, records_failed, message, created_at, sync_date
            FROM hr_sync_log
            ORDER BY created_at DESC LIMIT 1
        """)).fetchone()
        if row:
            last = {
                "status":          row[0],
                "records_sent":    row[1],
                "records_failed":  row[2],
                "message":         row[3],
                "created_at":      row[4].isoformat() if row[4] else None,
                "sync_date":       str(row[5]) if row[5] else None,
            }
    except Exception:
        pass

    sync_time = cfg["sync_time"] if cfg else "00:00"
    now  = datetime.now(timezone.utc)
    h, m = map(int, sync_time.split(":"))
    next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)

    return {
        "configured":   bool(cfg),
        "enabled":      cfg["is_enabled"] if cfg else False,
        "sync_time":    sync_time,
        "next_run_utc": next_run.isoformat(),
        "last_sync":    last,
    }


# ── Preview ───────────────────────────────────────────────────────────────────

@router.get("/preview/{sync_date}")
async def preview_sync(
    sync_date: str,
    db: Session = Depends(get_db),
    current_user=Depends(_require_admin),
):
    """Show exactly which records would be sent for a given date."""
    try:
        d = date.fromisoformat(sync_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date — use YYYY-MM-DD")

    records = _build_attendance_records(db, d)
    return {
        "sync_date":    sync_date,
        "total":        len(records),
        "records":      records[:100],   # cap preview at 100
        "truncated":    len(records) > 100,
    }


# ── Global admin: remove all staff and pull them back from SeamlessHR ─────────

def _require_global_admin(current_user=Depends(get_current_user)):
    if not getattr(current_user, "is_global_admin", False):
        raise HTTPException(status_code=403, detail="Only the global administrator can remove all staff")
    return current_user


class StaffResetIn(BaseModel):
    mode: str = Field("keep_history", pattern="^(keep_history|everything)$")
    repopulate: bool = True
    confirm: str


@router.get("/staff-reset/preview")
async def staff_reset_preview(mode: str = "keep_history", repopulate: bool = True,
                              db: Session = Depends(get_db), current_user=Depends(_require_global_admin)):
    """What a reset would remove, and whether it can run right now (nothing is changed)."""
    from ..services.staff_reset import preflight, CONFIRM_PHRASE
    pre = await asyncio.to_thread(preflight, db, mode, repopulate)

    def n(sql):
        try:
            return db.execute(text(sql)).scalar() or 0
        except Exception:
            db.rollback()
            return 0
    return {"success": True, "confirm_phrase": CONFIRM_PHRASE, "preflight": pre, "counts": {
        "staff": n("SELECT count(*) FROM personnel"),
        "with_card": n("SELECT count(card_number) FROM personnel"),
        "with_attendance_id": n("SELECT count(*) FROM personnel WHERE COALESCE(attendance_id, '') <> ''"),
        "on_board": n("SELECT count(*) FROM personnel WHERE is_onboard"),
        "daily_attendance_rows": n("SELECT count(*) FROM att_report"),
        "punches": n("SELECT count(*) FROM iclock_transaction"),
    }, "last_jobs": [dict(r) for r in db.execute(text(
        "SELECT id, mode, state, started_by, created_at, finished_at, error FROM staff_reset_job ORDER BY id DESC LIMIT 5")).mappings().all()]}


@router.post("/staff-reset")
async def staff_reset(body: StaffResetIn, background: BackgroundTasks, db: Session = Depends(get_db),
                      current_user=Depends(_require_global_admin)):
    from ..services.staff_reset import preflight, run_reset, CONFIRM_PHRASE
    if (body.confirm or "").strip().upper() != CONFIRM_PHRASE:
        raise HTTPException(status_code=400, detail=f'Type "{CONFIRM_PHRASE}" to confirm')
    if db.execute(text("SELECT 1 FROM staff_reset_job WHERE state IN ('queued', 'running') LIMIT 1")).scalar():
        raise HTTPException(status_code=409, detail="A staff reset is already running")
    pre = await asyncio.to_thread(preflight, db, body.mode, body.repopulate)
    if not pre["ok"]:
        raise HTTPException(status_code=409, detail=" ".join(pre["problems"]))
    who = getattr(current_user, "email", None) or getattr(current_user, "username", "global admin")
    job_id = db.execute(text("""INSERT INTO staff_reset_job (started_by, mode, repopulate) VALUES (:w, :m, :r) RETURNING id"""),
                        {"w": who, "m": body.mode, "r": body.repopulate}).scalar()
    try:
        db.execute(text("""INSERT INTO base_operationlog (user_id, action, table_name, record_id, new_values, created_at)
                           VALUES (:u, 'STAFF_RESET', 'personnel', :j, :v, NOW())"""),
                   {"u": current_user.id, "j": job_id, "v": f'{{"mode": "{body.mode}", "repopulate": {str(body.repopulate).lower()}, "staff": {pre["staff"]}}}'})
    except Exception as e:  # noqa: BLE001 — audit must not block, but log it
        logger.warning("Staff reset audit write failed: %s", e)
        db.rollback()
        job_id = db.execute(text("""INSERT INTO staff_reset_job (started_by, mode, repopulate) VALUES (:w, :m, :r) RETURNING id"""),
                            {"w": who, "m": body.mode, "r": body.repopulate}).scalar()
    db.commit()
    background.add_task(run_reset, job_id, body.mode, body.repopulate)
    return {"success": True, "job_id": job_id,
            "message": "Removing staff" + (" and pulling them back from SeamlessHR — this takes a few minutes." if body.repopulate else ".")}


@router.get("/staff-reset/{job_id}")
async def staff_reset_status(job_id: int, db: Session = Depends(get_db), current_user=Depends(_require_global_admin)):
    row = db.execute(text("SELECT * FROM staff_reset_job WHERE id = :i"), {"i": job_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No such reset")
    return {"success": True, "data": dict(row)}
