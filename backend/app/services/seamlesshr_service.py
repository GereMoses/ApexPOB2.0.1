"""
SeamlessHR Integration Service
──────────────────────────────
Pushes daily attendance records from iclock_transaction → SeamlessHR
Time & Attendance module so HR can process payroll.

All API coordinates (base URL, endpoint paths, header names) are stored in
the hr_integration_config table so they can be updated without a code deploy
once SeamlessHR shares their API documentation.

Default assumptions (common REST HR API pattern — update via Settings UI):
  Base URL:             https://api-sandbox.seamlesshr.app  (sandbox; swap for live)
  Auth header:          Authorization: Bearer <api_key>
  Attendance endpoint:  POST /biometric/process   (bare array, max 100/call)
  Employee check:       GET  /v1/employees/{emp_id}

Attendance payload sent per employee per day:
  {
    "employee_id":   "EMP001",
    "date":          "2026-06-06",
    "clock_in":      "08:02:14",
    "clock_out":     "17:45:00",
    "total_minutes": 583,
    "source":        "POB_BIOMETRIC"
  }
"""

import logging
import asyncio
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

# ── Shared httpx client (singleton) ──────────────────────────────────────────
_shr_client: Optional[httpx.AsyncClient] = None
_shr_client_lock = asyncio.Lock()


async def _get_shr_client() -> httpx.AsyncClient:
    global _shr_client
    if _shr_client is None or _shr_client.is_closed:
        async with _shr_client_lock:
            if _shr_client is None or _shr_client.is_closed:
                _shr_client = httpx.AsyncClient(timeout=30)
    return _shr_client


async def close_shr_client() -> None:
    global _shr_client
    if _shr_client and not _shr_client.is_closed:
        await _shr_client.aclose()
        _shr_client = None

logger = logging.getLogger(__name__)

# ── Connector options (all tunable from the DB/UI — no code change needed) ─────
# Defaults reproduce the original behaviour exactly, so an unconfigured `options`
# column changes nothing. Any HR API's quirks are absorbed here.
_DEFAULT_OPTIONS: Dict[str, Any] = {
    # Defaults below are SeamlessHR's PUBLISHED contract (docs.seamlesshr.com):
    #   auth      : x-client-id + x-client-secret headers (no bearer, no OAuth)
    #   push      : POST /biometric/process, a BARE JSON array, max 100 per call
    #   payload   : one record PER PUNCH — {attendanceId, dateTime, type, deviceSN}
    # Every value stays overridable per-tenant from the UI.
    "auth_type":          "dual_header",         # bearer | api_key | basic | oauth2 | dual_header
    "org_header_name":    "",                    # SeamlessHR scopes by client id, not a header
    "payload_wrapper_key": "",                   # "" ⇒ send a bare JSON array
    "batch_size":         100,                   # SeamlessHR hard limit
    "http_method":        "POST",
    # "punch_events" expands each computed day into CLOCK_IN/CLOCK_OUT events
    # (SeamlessHR). "daily_summary" keeps the flat one-row-per-day shape for any
    # HR system that accepts computed totals.
    "payload_style":      "punch_events",        # punch_events | daily_summary
    "clock_in_type":      "CLOCK_IN",
    "clock_out_type":     "CLOCK_OUT",
    # How the timestamp is rendered — see _render_dt.
    #
    # local_naive is the default because SeamlessHR's biometric ingestion is built
    # around ZKTeco ADMS, and the ADMS protocol carries NO timezone: a reader sends
    # its own wall clock as "YYYY-MM-DD HH:MM:SS" and the receiving server decides
    # what it means. In a normal SeamlessHR deployment the customer's readers are
    # set to local time, so what SeamlessHR stores — and returns from
    # GET /v1/attendances, e.g. "2024-11-20 09:43:05" — is local wall clock.
    #
    # ApexPOB sets its readers to UTC (adms_protocol pushes datetime.now() from a
    # UTC container), so a 07:15 Lagos punch is held as 06:15Z. Sending that raw
    # would show up in SeamlessHR as 06:15 — an hour early, every punch. Rendering
    # site-local reproduces exactly what a directly-connected reader would have
    # sent. Switch to offset/utc_naive if SeamlessHR confirm they parse offsets.
    "datetime_style":     "local_naive",      # offset | local_naive | utc_naive
    "time_zone":          "Africa/Lagos",     # site wall clock for local_naive
    "default_device_sn":  "POB-MANUAL",          # when no reader backs the punch
    # attendanceId = the employee's Personnel ID ON THE BIOMETRIC DEVICE, per
    # SeamlessHR support docs. That is the only employee mapping in the payload.
    "attendance_id_source": "device_personnel_id",  # device_personnel_id | idempotency_key
    # Where each person's Attendance ID (= reader PIN = the ID SeamlessHR matches
    # punches on) comes from after a staff pull:
    #   seamlesshr  — read from SeamlessHR's attendance records (needs T&A read access)
    #   code_digits — the digits of the employee code ("MARC 14256" → "14256"); only
    #                 correct if SeamlessHR holds the same number as each Attendance ID
    #   manual      — imported / typed in ApexPOB only
    "attendance_id_rule":   "seamlesshr",
    # Nightly: pull staff + leave, set Attendance IDs, update the readers — then push
    # attendance. Off = the nightly job only pushes attendance (old behaviour).
    "nightly_staff_refresh": True,
    "include_employee_id":  False,               # extra key; their 406 covers unknown fields
    # ApexPOB writes badge_id to the ZKTeco reader as the user_id, so badge_id is
    # the Personnel ID SeamlessHR will have against the employee.
    "employee_id_source": "badge_id",            # emp_code | badge_id | biotime_employee_id
    "time_format":        "iso",                 # iso | hms (HH:MM:SS)
    "field_map":          {},                    # canonical → output key ("" ⇒ omit field)
    "extra_headers":      {},                    # arbitrary static headers
    # ── Dual-header auth for SeamlessHR (auth_type="dual_header") ────────────────
    # SeamlessHR authenticates with x-client-id + x-client-secret (not bearer/OAuth).
    # client-secret reuses the encrypted `api_key`; client-id is stored here.
    "client_id":            "",
    "client_id_header":     "x-client-id",
    "client_secret_header": "x-client-secret",
    # ── Employee PULL (SeamlessHR = master; personnel become read-only in ApexPOB) ──
    # Field names match SeamlessHR's GET /v1/employees list endpoint (firstname/lastname,
    # no underscore; employee_code). Fully overridable per-tenant from the UI.
    "employee_list_key":    "data",              # response key holding the list ("" ⇒ body is the array)
    "employee_page_param":  "page",              # pagination page param ("" ⇒ single page)
    "employee_limit_param": "limit",             # SeamlessHR default page size is only 10
    # SeamlessHR's sandbox costs ~0.3s per record and answers calls made too soon after
    # one another with a bare 400 (no 429). Measured: limit 25/50 succeeded 9/9; limit 10
    # and 100 failed whenever they followed another call closely. So: modest pages with a
    # pause between them, and patient retries (see _get_with_retry).
    "employee_limit":       25,
    "employee_page_delay":  2.0,                 # seconds between pages
    # SeamlessHR's GET /v1/employees returns the HOLDING company (all subsidiaries) when
    # no `company` is sent. Set this to a company NAME to pull only that company
    # (verified in the sandbox: "Integration Company" = 81 staff vs 345 for the holding
    # company). Blank = whole holding company, which is right for a single-company tenant.
    "employee_company":     "",
    "employee_status_field": "status",           # 'active'|'inactive' → drives is_active
    # Field names below are SeamlessHR's DOCUMENTED GET /v1/employees response.
    # NOTE: SeamlessHR returns `staff_name` + `staff_other_names` rather than a
    # split first/last — confirm with them which carries the surname for this
    # tenant, then adjust here if their convention is the reverse.
    # Verified against the sandbox: `staff_name` is the FULL name ("Oluwafemi Areogun")
    # and `staff_other_names` is an extra given name (often null). So first/last are both
    # derived from staff_name — see employee_name_split below.
    "employee_name_split":  True,                # split staff_name → first token / remainder
    "employee_other_names_field": "staff_other_names",   # appended to full_name only
    "employee_field_map": {                      # SeamlessHR field → ApexPOB personnel field
        "emp_code":        "staff_id",
        "first_name":      "staff_name",
        "last_name":       "staff_name",
        "email":           "staff_email",
        "phone":           "staff_phone",
        "department":      "department",
        "position":        "job_title",
        "employment_type": "contract_type",
        "hire_date":       "employment_date",
    },
    # ── Webhook (real-time employee sync FROM SeamlessHR). The webhook `data` object
    # uses first_name/last_name (underscore), unlike the list endpoint above. ──────
    "webhook_secret":       "",                  # HMAC-SHA512 secret configured with SeamlessHR
    "webhook_field_map": {
        "emp_code":        "employee_code",
        "first_name":      "first_name",
        "last_name":       "last_name",
        "email":           "email",
        "phone":           "phone",
        "department":      "department",
        "position":        "job_role",
        "employment_type": "contract_type",
        "hire_date":       "employment_date",
    },
    # ── Leave (SeamlessHR "Get Employees On Leave") → excludes them from muster ────
    "leave_endpoint":     "/v1/leave/on-leave",  # confirm exact path with SeamlessHR
    "leave_list_key":     "data",
    "leave_field_map":    {"emp_code": "employee_code", "leave_end_date": "end_date"},
    # OAuth2 client-credentials (client_secret reuses the encrypted api_key):
    "oauth_token_url":    "",
    "oauth_client_id":    "",
    "oauth_scope":        "",
    "basic_user":         "",                    # for auth_type=basic
}

# Cached OAuth2 token: {"token": str, "exp": epoch_seconds}
_oauth_cache: Dict[str, Any] = {"token": None, "exp": 0.0}


def _merge_options(raw: Optional[Dict]) -> Dict[str, Any]:
    opts = dict(_DEFAULT_OPTIONS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if v is None:
                continue
            # The *_map options are dictionaries of field names. Merge them key by
            # key instead of replacing wholesale: an admin correcting one mapping
            # (say the surname field) must not silently drop every other field
            # from the sync. Pass an explicit "" to disable an individual entry.
            if isinstance(v, dict) and isinstance(_DEFAULT_OPTIONS.get(k), dict):
                merged = dict(_DEFAULT_OPTIONS[k])
                merged.update(v)
                opts[k] = merged
            else:
                opts[k] = v
    return opts


# ── Config helpers ────────────────────────────────────────────────────────────

def get_config(db: Session) -> Optional[Dict[str, Any]]:
    """Load integration config from DB. Returns None if not configured."""
    try:
        row = db.execute(text(
            "SELECT api_base_url, api_key, org_id, auth_header_name, "
            "       attendance_endpoint, employee_endpoint, is_enabled, sync_time, options "
            "FROM hr_integration_config LIMIT 1"
        )).fetchone()
        if not row or not row[0] or not row[1]:
            return None
        from ..core.crypto import decrypt_secret
        return {
            "api_base_url":        row[0].rstrip("/"),
            "api_key":             decrypt_secret(row[1]),  # transparently handles legacy plaintext
            "org_id":              row[2],
            "auth_header_name":    row[3] or "Authorization",
            "attendance_endpoint": row[4] or "/biometric/process",
            "employee_endpoint":   row[5] or "/v1/employees",
            "is_enabled":          bool(row[6]),
            "sync_time":           row[7] or "00:00",  # Bug 2 fix: was missing
            "options":             _merge_options(row[8] if len(row) > 8 else None),
        }
    except Exception as e:
        logger.warning(f"hr_integration_config read error: {e}")  # Bug 4 fix: WARNING not DEBUG
        return None


async def _get_oauth_token(cfg: Dict) -> str:
    """Fetch + cache an OAuth2 client-credentials token (client_secret = api_key)."""
    import time
    opts = cfg["options"]
    if _oauth_cache["token"] and _oauth_cache["exp"] > time.time() + 30:
        return _oauth_cache["token"]
    data = {"grant_type": "client_credentials",
            "client_id": opts.get("oauth_client_id") or cfg.get("org_id") or "",
            "client_secret": cfg["api_key"]}
    if opts.get("oauth_scope"):
        data["scope"] = opts["oauth_scope"]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(opts["oauth_token_url"], data=data)
    resp.raise_for_status()
    body = resp.json()
    _oauth_cache["token"] = body["access_token"]
    _oauth_cache["exp"] = time.time() + int(body.get("expires_in", 3600))
    return _oauth_cache["token"]


async def build_auth_headers(cfg: Dict) -> Dict[str, str]:
    """Build auth headers per the configured scheme. Async because OAuth2 fetches a token."""
    opts = cfg["options"]
    name = cfg["auth_header_name"] or "Authorization"
    key  = cfg["api_key"]
    at   = opts.get("auth_type", "bearer")
    if at == "dual_header":
        # SeamlessHR: x-client-id + x-client-secret (client-secret = the encrypted api_key)
        return {
            opts.get("client_id_header", "x-client-id"): opts.get("client_id") or cfg.get("org_id") or "",
            opts.get("client_secret_header", "x-client-secret"): key,
        }
    if at == "api_key":
        return {name: key}
    if at == "basic":
        import base64
        tok = base64.b64encode(f"{opts.get('basic_user','')}:{key}".encode()).decode()
        return {"Authorization": f"Basic {tok}"}
    if at == "oauth2":
        return {name: f"Bearer {await _get_oauth_token(cfg)}"}
    # default: bearer
    return {name: f"Bearer {key}"}


def _to_payload(r: Dict, opts: Dict, emp_map: Dict[str, str]) -> Dict:
    """Map an internal canonical record to the outbound JSON per configured field
    names / employee-id source / time format. A field mapped to "" is omitted."""
    fm = opts.get("field_map") or {}
    tf = opts.get("time_format", "iso")
    src = opts.get("employee_id_source", "emp_code")
    emp_val = emp_map.get(r["employee_id"], r["employee_id"]) if (src != "emp_code" and emp_map) else r["employee_id"]

    def _t(v):
        if v and tf == "hms":
            try: return datetime.fromisoformat(v).strftime("%H:%M:%S")
            except ValueError: return v
        return v

    out: Dict[str, Any] = {}
    for canon, val in (("employee_id", emp_val), ("date", r["date"]),
                       ("clock_in", _t(r["clock_in"])), ("clock_out", _t(r["clock_out"])),
                       ("total_minutes", r["total_minutes"]), ("overtime_minutes", r["overtime_minutes"]),
                       ("source", r["source"]), ("idempotency_key", r["idempotency_key"])):
        key = fm.get(canon, canon)
        if key != "":
            out[key] = val
    return out


# ── Core sync logic ───────────────────────────────────────────────────────────


def _build_attendance_records(db: Session, sync_date: date) -> List[Dict]:
    """
    Build one SeamlessHR clock-record per employee for sync_date.

    Source of truth is the COMPUTED attendance in att_report (via the shared
    attendance_export.build_daily_attendance), NOT raw iclock_transaction. This is
    what fixes the historical defects:
      • access-control door swipes no longer inflate work hours (att_report respects
        reader_purpose, shifts and breaks);
      • cross-midnight / night shifts are attributed to the correct business day;
      • the day boundary is the shift-resolved att_date, not UTC midnight.

    Each record carries an idempotency_key so a re-run/retry cannot double-post.
    Times are emitted as tz-aware ISO 8601 (with offset) to remove the previous
    naive-wall-clock ambiguity; total_minutes is the authoritative computed figure.
    """
    from .attendance_export import build_daily_attendance

    canonical = build_daily_attendance(db, sync_date)
    records = []
    for c in canonical:
        records.append({
            "employee_id":      c["emp_code"],
            "date":             str(c["att_date"]),
            "clock_in":         c["check_in"].isoformat() if c["check_in"] else None,
            "clock_out":        c["check_out"].isoformat() if c["check_out"] else None,
            "total_minutes":    c["work_minutes"],
            "overtime_minutes": c["overtime_minutes"],
            "source":           "POB_BIOMETRIC",
            "idempotency_key":  c["idempotency_key"],
            "check_in_device_sn":  c.get("check_in_device_sn"),
            "check_out_device_sn": c.get("check_out_device_sn"),
        })
    return records


def _to_punch_events(r: Dict, opts: Dict, emp_map: Dict[str, str]) -> List[Dict]:
    """Expand ONE computed employee-day into the per-punch events SeamlessHR wants.

    SeamlessHR's /biometric/process takes individual events
    ({attendanceId, dateTime, type, deviceSN}), not daily totals — so the flat
    canonical record cannot be sent as-is, and `field_map` (which only renames
    keys) cannot bridge the difference.

    What preserves the "ApexPOB calculates, SeamlessHR consumes" contract is
    WHICH punches get sent: these are the shift-resolved boundaries from
    att_report — access-control door swipes already excluded and cross-midnight
    shifts already attributed to the right business day — not the raw punch
    stream. SeamlessHR therefore only ever sees the clean pair.

    attendanceId is derived from the per-employee-day idempotency key plus the
    event type, so it is stable across retries and unique per event.
    """
    src     = opts.get("employee_id_source", "emp_code")
    if opts.get("attendance_id_source", "device_personnel_id") == "device_personnel_id":
        # SeamlessHR's attendanceId IS the reader PIN = personnel.attendance_id. An
        # employee without one cannot be matched on their side, so send nothing
        # (the caller reports them) instead of a punch SeamlessHR will drop.
        emp_val = emp_map.get(r["employee_id"])
        if not emp_val:
            return []
    else:
        emp_val = emp_map.get(r["employee_id"], r["employee_id"]) if (src != "emp_code" and emp_map) else r["employee_id"]
    fm      = opts.get("field_map") or {}
    default_sn = opts.get("default_device_sn") or "POB-MANUAL"
    dt_style = opts.get("datetime_style", "offset")
    tz_name  = opts.get("time_zone", "Africa/Lagos")

    def _render_dt(iso: str) -> str:
        """Render the timestamp the way SeamlessHR expects.

        Their documentation is inconsistent here: the request example shows
        "2025-07-07T13:45:30" with NO offset, while the schema default shows
        "2025-07-16T08:44:16+00:00" with one. That difference is not cosmetic —
        ApexPOB stores UTC, so a 07:15 Lagos punch is 06:15Z. If SeamlessHR
        ignores the offset and reads the value as local time, every punch lands an
        hour early, every day. Configurable until they confirm which they parse:

          offset      2026-08-19T06:15:00+00:00   (UTC, explicit offset — default)
          local_naive 2026-08-19T07:15:00         (site local time, no offset)
          utc_naive   2026-08-19T06:15:00         (UTC, offset stripped)
        """
        if dt_style == "offset":
            return iso
        try:
            parsed = datetime.fromisoformat(iso)
        except ValueError:
            return iso
        if dt_style == "local_naive":
            try:
                from zoneinfo import ZoneInfo
                parsed = parsed.astimezone(ZoneInfo(tz_name))
            except Exception:
                logger.warning("Unknown time_zone %r — sending UTC instead", tz_name)
        return parsed.replace(tzinfo=None).isoformat()

    def _event(dt: Optional[str], kind: str, sn: Optional[str]) -> Optional[Dict]:
        if not dt:
            return None
        # attendanceId is how SeamlessHR identifies WHOSE punch this is.
        #
        # Their API reference calls it "Unique ID for the attendance record",
        # which reads like a row id — but their support documentation is explicit:
        #   "The Personnel ID is the ID assigned to employees on the Biometric
        #    Device used within your organization. At the point of upload, the
        #    Personnel ID on the biometric device is the attendance ID that will
        #    be uploaded to each employee's profile."
        # (support.seamlesshr.com — biometric machine setup / T&A FAQs)
        #
        # So it is the DEVICE USER ID, and it is the only employee mapping in the
        # payload — which is why the schema has no employee field. It repeats
        # across a day's punches; the record is identified by
        # (attendanceId, dateTime, type). ApexPOB writes badge_id to the reader as
        # the ZK user_id, so that is the value SeamlessHR will have on file.
        if opts.get("attendance_id_source", "device_personnel_id") == "idempotency_key":
            attendance_id = f"{r['idempotency_key']}-{kind}"   # legacy / other HR systems
        else:
            attendance_id = emp_val
        out = {
            "attendanceId": attendance_id,
            "dateTime":     _render_dt(dt),
            "type":         kind,
            "deviceSN":     sn or default_sn,
        }
        # employeeId is NOT in SeamlessHR's schema, and their status-code page
        # documents 406 for "requests that contain references to non-existent
        # fields" — so an extra key is a real rejection risk. Now that
        # attendanceId carries the identity it is redundant; off unless asked for.
        if opts.get("include_employee_id"):
            out["employeeId"] = emp_val
        # Allow per-tenant renaming of any outbound key (e.g. employeeId → staffId).
        return {fm.get(k, k): v for k, v in out.items() if fm.get(k, k) != ""}

    events = [
        _event(r["clock_in"],  opts.get("clock_in_type", "CLOCK_IN"),   r.get("check_in_device_sn")),
        _event(r["clock_out"], opts.get("clock_out_type", "CLOCK_OUT"), r.get("check_out_device_sn")),
    ]
    return [e for e in events if e]


async def push_attendance(
    db: Session,
    sync_date: Optional[date] = None,
    triggered_by: str = "scheduler",
    force: bool = False,
    allow_today: bool = False,
) -> Dict[str, Any]:
    """
    Build attendance records for sync_date (defaults to yesterday) and
    POST them to SeamlessHR. Logs the result to hr_sync_log.

    Idempotency: each (employee, date) is sent at most once — already-sent records are
    skipped so a re-run/retry cannot double-post to payroll.
      • force=True       — re-send even if already sent (admin correction; may duplicate).
      • allow_today=True — permit syncing a not-yet-finalized day (today/future).
    Returns a result summary dict.
    """
    if sync_date is None:
        sync_date = date.today() - timedelta(days=1)

    started_at = datetime.now(timezone.utc)
    result = {
        "sync_date":    str(sync_date),
        "triggered_by": triggered_by,
        "started_at":   started_at.isoformat(),
        "status":       "failed",
        "records_built": 0,
        "records_sent":  0,
        "records_failed": 0,
        "message":      "",
    }

    cfg = get_config(db)
    if not cfg:
        result["message"] = "Integration not configured — add API credentials in Settings → HR Integration"
        _log_sync(db, result)
        return result

    if not cfg["is_enabled"]:
        result["status"]  = "skipped"
        result["message"] = "Integration is disabled"
        _log_sync(db, result)
        return result

    # Don't post a not-yet-finalized day (today/future) to payroll unless explicitly allowed.
    if not allow_today and not force and sync_date >= date.today():
        result["status"]  = "skipped"
        result["message"] = f"{sync_date} is not finalized yet — payroll syncs after the day closes"
        _log_sync(db, result)
        return result

    records = _build_attendance_records(db, sync_date)
    result["records_built"] = len(records)

    if not records:
        result["status"]  = "success"
        result["message"] = f"No attendance records found for {sync_date}"
        _log_sync(db, result)
        return result

    # Idempotency: drop employee-days already sent for this date (unless force re-send).
    if not force:
        from .attendance_export import already_synced_codes
        done = already_synced_codes(db, "hr_synced_records", sync_date)
        if done:
            records = [r for r in records if r["employee_id"] not in done]
        if not records:
            result["status"]  = "success"
            result["message"] = f"All records for {sync_date} already synced — nothing new to send"
            _log_sync(db, result)
            return result

    opts = cfg["options"]
    url     = cfg["api_base_url"] + cfg["attendance_endpoint"]
    headers = {**await build_auth_headers(cfg), "Content-Type": "application/json",
               **(opts.get("extra_headers") or {})}
    if cfg["org_id"] and opts.get("org_header_name"):
        headers[opts["org_header_name"]] = cfg["org_id"]

    # Translate emp_code → alternate employee identifier if configured
    emp_map: Dict[str, str] = {}
    if opts.get("attendance_id_source", "device_personnel_id") == "device_personnel_id":
        for erow in db.execute(text(
                "SELECT emp_code, attendance_id FROM personnel "
                "WHERE emp_code IS NOT NULL AND attendance_id IS NOT NULL")).fetchall():
            if erow[1]:
                emp_map[erow[0]] = str(erow[1])
    elif opts.get("employee_id_source", "emp_code") != "emp_code":
        col = opts["employee_id_source"]
        if col in ("badge_id", "biotime_employee_id"):
            for erow in db.execute(text(f"SELECT emp_code, {col} FROM personnel WHERE emp_code IS NOT NULL")).fetchall():
                if erow[1]:
                    emp_map[erow[0]] = str(erow[1])

    wrapper = opts.get("payload_wrapper_key", "")
    method  = (opts.get("http_method") or "POST").upper()
    batch_size = int(opts.get("batch_size") or 100)
    style   = opts.get("payload_style", "punch_events")

    # One employee-day becomes up to TWO events in punch_events mode, so the
    # provider's batch cap counts EVENTS, not employee-days. Group per day and
    # never split a group across batches: a day is marked synced only when its
    # whole group lands, so a half-sent day can't be skipped on the next run.
    groups: List[tuple] = []
    no_attendance_id: List[str] = []
    for r in records:
        payloads = (_to_punch_events(r, opts, emp_map) if style == "punch_events"
                    else [_to_payload(r, opts, emp_map)])
        if payloads:
            groups.append((r["employee_id"], payloads))
        elif style == "punch_events":
            no_attendance_id.append(r["employee_id"])
    if no_attendance_id:
        logger.warning(
            "SeamlessHR sync %s: %d employee(s) held back — no Attendance ID on file "
            "(adopt IDs from SeamlessHR first): %s",
            sync_date, len(no_attendance_id), ", ".join(sorted(set(no_attendance_id))[:20]))
        result["no_attendance_id"] = sorted(set(no_attendance_id))

    batches: List[List[tuple]] = []
    current: List[tuple] = []
    current_n = 0
    for emp, payloads in groups:
        if current and current_n + len(payloads) > batch_size:
            batches.append(current)
            current, current_n = [], 0
        current.append((emp, payloads))
        current_n += len(payloads)
    if current:
        batches.append(current)

    failed = 0
    sent   = 0

    try:
        client = await _get_shr_client()
        sent_codes = []
        for batch_no, batch in enumerate(batches, 1):
            payload_list = [pl for _, payloads in batch for pl in payloads]
            body = payload_list if not wrapper else {wrapper: payload_list}
            try:
                resp = await client.request(method, url, json=body, headers=headers)
                accepted, detail = _batch_accepted(resp)
                if accepted:
                    sent += len(batch)
                    sent_codes.extend(emp for emp, _ in batch)
                elif resp.status_code in (200, 201, 204):
                    # HTTP 200 with a failure count in the body: SeamlessHR
                    # accepted the request but rejected the punches. Leave the
                    # days unsynced so the next run retries them.
                    logger.warning(
                        "SeamlessHR batch %d (%d events) accepted but not applied: %s",
                        batch_no, len(payload_list), detail,
                    )
                    failed += len(batch)
                else:
                    logger.warning(
                        "SeamlessHR batch %d (%d events) returned %s: %s",
                        batch_no, len(payload_list), resp.status_code, resp.text[:200],
                    )
                    failed += len(batch)
            except httpx.RequestError as e:
                logger.error("SeamlessHR request error (batch %d): %s", batch_no, e)
                failed += len(batch)

        # Record successfully-sent employee-days so a re-run cannot double-post them.
        if sent_codes:
            from .attendance_export import mark_synced
            mark_synced(db, "hr_synced_records", sync_date, sent_codes)

        result["records_sent"]   = sent
        result["records_failed"] = failed
        result["status"]  = "success" if failed == 0 else ("partial" if sent > 0 else "failed")
        result["message"] = (
            f"Sent {sent}/{len(records)} records to SeamlessHR for {sync_date}"
            + (f" ({failed} failed)" if failed else "")
            + (f" ({len(set(no_attendance_id))} held back: no Attendance ID)" if no_attendance_id else "")
        )
        if no_attendance_id and result["status"] == "success":
            result["status"] = "partial"

    except Exception as e:
        result["message"] = f"Unexpected error: {e}"
        logger.exception("SeamlessHR sync crashed")

    _log_sync(db, result)
    logger.info(f"SeamlessHR sync [{result['status']}]: {result['message']}")
    return result


_BATCH_COUNTS_RE = re.compile(
    r"(\d+)\s+attendance records? sent successfully,\s*(\d+)\s+attendance records? failed", re.I)


def _batch_accepted(resp) -> tuple:
    """
    Decide whether a /biometric/process response means the punches were applied.

    SeamlessHR answers HTTP 200 "processed successfully" even when every record
    failed; the truth is in data.message ("0 attendance records sent
    successfully, 1 attendance records failed"). Treat the batch as accepted
    only when the status is 2xx AND no failure count is reported. A body in an
    unrecognised shape falls back to the status code alone.
    """
    if resp.status_code not in (200, 201, 204):
        return False, f"HTTP {resp.status_code}"
    try:
        body = resp.json()
    except Exception:
        return True, ""
    inner = body.get("data") if isinstance(body, dict) else None
    texts = [body.get("message", "")] if isinstance(body, dict) else []
    if isinstance(inner, dict):
        texts.append(inner.get("message", ""))
    for t in texts:
        m = _BATCH_COUNTS_RE.search(str(t))
        if m:
            ok, bad = int(m.group(1)), int(m.group(2))
            return bad == 0, str(t)
    return True, ""


async def test_connection(cfg: Dict) -> Dict[str, Any]:
    """Verify API credentials by hitting the employee endpoint."""
    opts = cfg.get("options") or _DEFAULT_OPTIONS
    url     = cfg["api_base_url"] + cfg.get("employee_endpoint", "/v1/employees")
    headers = {**await build_auth_headers(cfg), "Content-Type": "application/json",
               **(opts.get("extra_headers") or {})}
    if cfg.get("org_id") and opts.get("org_header_name"):
        headers[opts["org_header_name"]] = cfg["org_id"]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await _get_with_retry(client, url, headers, attempts=4)
        if resp.status_code in (200, 201):
            return {"success": True,  "message": f"Connected — HTTP {resp.status_code}"}
        # SeamlessHR answers bad credentials with HTTP 400 {"message":"Unauthorized access"}
        # (and a missing key with 401), not 401/403.
        if resp.status_code == 401 or "unauthorized access" in resp.text.lower():
            return {"success": False, "message": "Authentication failed — check Client ID and Client Secret"}
        if resp.status_code == 403:
            return {"success": False, "message": "Access denied — check Organisation ID and API permissions"}
        if resp.status_code == 404:
            return {"success": False, "message": f"Endpoint not found: {url} — verify the API base URL"}
        return {"success": False, "message": f"Unexpected response: HTTP {resp.status_code}"}
    except httpx.ConnectError:
        return {"success": False, "message": f"Cannot reach {cfg['api_base_url']} — check the URL and network"}
    except httpx.TimeoutException:
        return {"success": False, "message": "Connection timed out — server did not respond within 30s"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── Sync log helper ───────────────────────────────────────────────────────────

def _log_sync(db: Session, result: Dict):
    try:
        db.execute(text("""
            INSERT INTO hr_sync_log
              (sync_date, triggered_by, status, records_built,
               records_sent, records_failed, message, created_at)
            VALUES
              (:sync_date, :triggered_by, :status, :records_built,
               :records_sent, :records_failed, :message, NOW())
        """), {
            "sync_date":      result["sync_date"],
            "triggered_by":   result["triggered_by"],
            "status":         result["status"],
            "records_built":  result["records_built"],
            "records_sent":   result["records_sent"],
            "records_failed": result["records_failed"],
            "message":        result["message"][:500],
        })
        db.commit()
    except Exception as e:
        logger.warning(f"Could not write hr_sync_log: {e}")
        db.rollback()


# ── Employee pull (SeamlessHR is the master; pulled personnel are read-only here) ──

def _link_department(db: Session, person, unmatched: set) -> None:
    """Resolve the department NAME that SeamlessHR sends into ApexPOB's
    departments.id and store it on personnel.department_id.

    Why this matters: shifts hang off departments (departments.default_shift_id),
    and the attendance engine resolves an employee's schedule via
    personnel.department_id — NOT the department name string. A synced employee
    with only the name set therefore has no department as far as the calculation
    is concerned, silently loses the department's shift, and falls through to the
    global default. Matching is case-insensitive on name, then on code.

    A department that does not exist in ApexPOB is left unlinked and reported, so
    an admin can create it and give it a shift, rather than being invented here
    with no shift attached (which would look correct and behave wrongly).
    """
    name = (getattr(person, "department", None) or "").strip()
    if not name:
        # SeamlessHR no longer gives them a department: unlink, rather than leave
        # them on the old one (and its shift).
        person.department_id = None
        return
    row = db.execute(text(
        "SELECT id FROM departments "
        "WHERE lower(name) = lower(:n) OR lower(code) = lower(:n) "
        "ORDER BY id LIMIT 1"
    ), {"n": name}).fetchone()
    if row:
        person.department_id = row[0]
        # A SeamlessHR department hidden earlier because it emptied is back in use.
        db.execute(text("UPDATE departments SET is_active = TRUE WHERE id = :i AND is_active = FALSE"),
                   {"i": row[0]})
        return
    # SeamlessHR is the master for the org structure, so its departments are created
    # here rather than leaving every employee unlinked. A new department has no
    # default shift of its own and uses the global default shift until an admin sets
    # one — reported via `unmatched` so that is visible after the pull.
    base = re.sub(r"[^A-Z0-9]", "", name.upper())[:16] or "DEPT"
    code, n = base, 1
    while db.execute(text("SELECT 1 FROM departments WHERE code = :c"), {"c": code}).fetchone():
        n += 1
        code = f"{base[:16]}{n}"
    new_id = db.execute(text(
        "INSERT INTO departments (name, code, description, is_active) "
        "VALUES (:n, :c, 'Created from SeamlessHR', true) RETURNING id"
    ), {"n": name[:100], "c": code}).scalar()
    person.department_id = new_id
    unmatched.add(name)


# SeamlessHR's sandbox intermittently answers a perfectly valid request with 400/500
# ("An error occurred while processing the request") and the next identical call
# succeeds. A single such blip must not abort a 345-employee pull, nor — worse — be
# mistaken for "end of list" and silently truncate the master.
_RETRY_STATUSES = {400, 408, 425, 429, 500, 502, 503, 504}


def _seamless_date(value) -> Optional[date]:
    """SeamlessHR dates arrive in two shapes:
      - "2018-01-07T23:00:00.000000Z": a SITE-midnight stored as UTC, so the date part
        alone is a day early (this was the employment date of 8 Jan 2018);
      - "16/08/1993": day/month/year (date_of_birth).
    Returns the site calendar date, or None."""
    if not value:
        return None
    v = str(value).strip()
    try:
        if "T" in v:
            from .attendance_calculation_service import SITE_TZ
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(SITE_TZ)
            return dt.date()
        if "/" in v:
            d, m, y = v.split("/")[:3]
            return date(int(y[:4]), int(m), int(d))
        return date.fromisoformat(v[:10])
    except Exception:
        return None


async def _get_with_retry(client: httpx.AsyncClient, url: str, headers: Dict[str, str],
                          params: Optional[Dict] = None, attempts: int = 6) -> httpx.Response:
    """GET with backoff on transient failures. Raises on the final failure."""
    last_exc: Optional[Exception] = None
    resp: Optional[httpx.Response] = None
    for n in range(attempts):
        try:
            resp = await client.get(url, headers=headers, params=params)
            # A 400 "Unauthorized access" is a real credential/permission answer, not a blip.
            if resp.status_code not in _RETRY_STATUSES or "unauthorized" in resp.text.lower():
                return resp
        except (httpx.TransportError, httpx.TimeoutException) as e:
            last_exc = e
            resp = None
        if n < attempts - 1:
            await asyncio.sleep(min(3.0 * (n + 1), 20))
    if resp is not None:
        return resp          # caller's raise_for_status reports the real status
    raise last_exc or RuntimeError("SeamlessHR request failed")


async def _fetch_page_resilient(client, url, headers, page_param, page, limit_param, limit_val,
                                 unreadable: List[int], company: str = ""):
    """Fetch one page; if SeamlessHR keeps rejecting it, fall back to one record at a time
    so a single record their API cannot serialise (observed in the sandbox: it answers
    400 for that record alone, deterministically) does not hide every other employee on
    the page. Positions of records that cannot be read are appended to `unreadable`."""
    params = {}
    if company:
        params["company"] = company
    if page_param:
        params[page_param] = page
    if limit_param:
        params[limit_param] = limit_val
    resp = await _get_with_retry(client, url, headers, params)
    if resp.status_code < 400 or not (page_param and limit_param) or int(limit_val or 1) <= 1:
        resp.raise_for_status()
        return resp.json()
    first = (page - 1) * int(limit_val) + 1
    logger.warning("pull_employees: page %s rejected (HTTP %s) — retrying records %s..%s singly",
                   page, resp.status_code, first, first + int(limit_val) - 1)
    rows, last_body = [], {}
    bad_start = len(unreadable)
    for pos in range(first, first + int(limit_val)):
        r = await _get_with_retry(client, url, headers,
                                  {**({"company": company} if company else {}), page_param: pos, limit_param: 1}, attempts=3)
        if r.status_code >= 400:
            unreadable.append(pos)
            continue
        body = r.json()
        last_body = body
        got = body.get("data") if isinstance(body, dict) else body
        if not got:
            break                      # ran past the end of the list
        rows.extend(got)
        await asyncio.sleep(1.0)
    if not rows and len(unreadable) - bad_start >= int(limit_val):
        # Not one record on the page could be read: SeamlessHR is failing, not a few
        # bad records. Abort the run (logged as an error) rather than skipping on page
        # after page forever.
        del unreadable[bad_start:]
        resp.raise_for_status()
    return {"data": rows} if rows or unreadable else last_body


async def pull_employees(db: Session, triggered_by: str = "manual") -> Dict[str, Any]:
    """Pull the employee master from SeamlessHR and upsert into `personnel`, marking
    each record hr_source='SEAMLESSHR' so its master fields become read-only in ApexPOB.

    Field mapping and pagination are fully config-driven (options.employee_field_map /
    employee_list_key / employee_page_param) — no code change to onboard a new tenant.
    Operational fields (badge, zone, POB, biometrics) are never touched by the pull.
    """
    from ..models.personnel import Personnel

    cfg = get_config(db)
    if not cfg:
        return {"error": "SeamlessHR is not configured", "created": 0, "updated": 0, "skipped": 0, "total": 0}

    opts = cfg["options"]
    fmap = opts.get("employee_field_map") or {}
    code_field = fmap.get("emp_code", "staff_id")
    list_key = opts.get("employee_list_key", "data")
    page_param = opts.get("employee_page_param", "page")
    batch = int(opts.get("batch_size", 50) or 50)
    url = cfg["api_base_url"] + cfg.get("employee_endpoint", "/v1/employees")

    headers = await build_auth_headers(cfg)
    # SeamlessHR scopes by client id, so org_header_name defaults to "". Guard on
    # the name being non-empty or we would send a header with a blank name.
    org_header = opts.get("org_header_name")
    if cfg.get("org_id") and org_header:
        headers[org_header] = cfg["org_id"]

    created = updated = skipped = 0
    seen = 0
    now = datetime.utcnow()
    unmatched_departments: set = set()
    unreadable_positions: List[int] = []

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            limit_param = opts.get("employee_limit_param")
            limit_val = opts.get("employee_limit", 100)
            status_field = opts.get("employee_status_field")
            page = 1
            while True:
                bad_before = len(unreadable_positions)
                body = await _fetch_page_resilient(client, url, headers, page_param, page,
                                                   limit_param, limit_val, unreadable_positions,
                                                   str(opts.get("employee_company") or "").strip())
                if isinstance(body, list):
                    rows = body
                elif isinstance(body, dict):
                    rows = body.get(list_key) if list_key else body
                    if not isinstance(rows, list):
                        rows = body.get("data", []) if isinstance(body.get("data"), list) else []
                else:
                    rows = []

                if not rows and not unreadable_positions:
                    break

                for emp in rows:
                    if not isinstance(emp, dict):
                        skipped += 1
                        continue
                    code = str(emp.get(code_field) or "").strip()
                    if not code:
                        skipped += 1
                        continue
                    seen += 1
                    try:
                        person = db.query(Personnel).filter(Personnel.emp_code == code).first()
                        is_new = person is None
                        if is_new:
                            person = Personnel(emp_code=code, first_name="", last_name="")
                            db.add(person)
                        # Only the mapped MASTER fields — operational state is left alone.
                        for pfield, sfield in fmap.items():
                            if pfield == "emp_code" or not sfield:
                                continue
                            val = emp.get(sfield)
                            if val is not None and hasattr(person, pfield):
                                setattr(person, pfield, val)
                            elif pfield == "department" and sfield in emp:
                                # Explicitly empty in SeamlessHR = no department now.
                                person.department = None
                        if opts.get("employee_name_split", False):
                            full = " ".join(str(emp.get(fmap.get("first_name") or "") or "").split())
                            if full:
                                first, _, rest = full.partition(" ")
                                person.first_name = first
                                person.last_name = rest or first
                            other = str(emp.get(opts.get("employee_other_names_field") or "") or "").strip()
                            person.full_name = f"{full} {other}".strip() if other and other.lower() not in full.lower() else full
                        else:
                            person.full_name = f"{person.first_name or ''} {person.last_name or ''}".strip()
                        # Employment status / exit → drives is_active (offboards leavers).
                        if status_field:
                            sval = str(emp.get(status_field) or "").lower()
                            if sval:
                                person.is_active = sval not in ("inactive", "exited", "terminated", "false", "0")
                        if emp.get("exit_date") or emp.get("exit_status") in (True, "true", 1):
                            person.is_active = False
                            person.is_onboard = False
                            person.is_pob = False
                        _link_department(db, person, unmatched_departments)
                        # Dates: the generic copy above stored employment_date's date
                        # part, which is a day early (UTC-encoded site midnight).
                        hd = _seamless_date(emp.get(fmap.get("hire_date") or "employment_date"))
                        if hd:
                            person.hire_date = hd
                        person.hr_source = "SEAMLESSHR"
                        person.hr_synced_at = now
                        db.flush()
                        # Date of birth lives on the reader mirror (birthday) — it was
                        # never pulled, so the Birthday report was always empty.
                        dob = _seamless_date(emp.get(opts.get("employee_dob_field", "date_of_birth")))
                        if dob:
                            db.execute(text("UPDATE personnel_employee SET birthday = :b WHERE emp_code = :c"),
                                       {"b": dob, "c": code})
                        created += 1 if is_new else 0
                        updated += 0 if is_new else 1
                    except Exception as row_err:
                        db.rollback()
                        skipped += 1
                        logger.warning("pull_employees: skipped %s (%s)", code, row_err)

                db.commit()
                # Stop on a short page. Compare against the page size we actually
                # REQUESTED (employee_limit), not batch_size — batch_size sizes the
                # attendance push, and if it were the larger of the two a full page
                # would look short and the employee master would silently truncate.
                page_size = int(limit_val or batch)
                if not page_param or len(rows) + (len(unreadable_positions) - bad_before) < page_size:
                    break
                page += 1
                await asyncio.sleep(float(opts.get("employee_page_delay", 0) or 0))

        result = {"created": created, "updated": updated, "skipped": skipped, "total": seen}
        # After a COMPLETE pull, a department that SeamlessHR created here and that no
        # employee is in any more was renamed or deleted in SeamlessHR. Hide it (not
        # delete: a shift or history may reference it); it comes back if used again.
        if not unreadable_positions:
            retired = db.execute(text("""
                UPDATE departments d SET is_active = FALSE, updated_at = NOW()
                WHERE d.description = 'Created from SeamlessHR' AND d.is_active = TRUE
                  AND NOT EXISTS (SELECT 1 FROM personnel p WHERE p.department_id = d.id)
                RETURNING d.name
            """)).fetchall()
            db.commit()
            if retired:
                result["retired_departments"] = sorted(r[0] for r in retired)
        if unreadable_positions:
            skipped += len(unreadable_positions)
            result["skipped"] = skipped
            result["unreadable_record_positions"] = unreadable_positions
            logger.warning("pull_employees: SeamlessHR could not return list positions %s "
                           "(HTTP 400 even when requested alone) — ask them to check those records",
                           unreadable_positions)
        # Surface departments SeamlessHR sent that don't exist here. Those staff are
        # unlinked, so they inherit no department shift — the admin needs to create
        # the department and give it a Default Shift, then re-pull.
        if unmatched_departments:
            result["created_departments"] = sorted(unmatched_departments)
            logger.warning(
                "pull_employees: created departments %s from SeamlessHR — they use the "
                "global default shift until a Default Shift is set on each",
                sorted(unmatched_departments),
            )
        _log_sync(db, {
            "sync_date": now.date(), "triggered_by": triggered_by, "status": "success",
            "records_built": seen, "records_sent": created + updated, "records_failed": skipped,
            "message": f"Employee pull: {created} created, {updated} updated, {skipped} skipped",
        })
        logger.info("pull_employees: %s", result)
        return result
    except Exception as e:
        db.rollback()
        logger.error("pull_employees error: %s", e)
        _log_sync(db, {
            "sync_date": now.date(), "triggered_by": triggered_by, "status": "error",
            "records_built": seen, "records_sent": created + updated, "records_failed": skipped,
            "message": f"Employee pull failed: {e}",
        })
        return {"error": str(e), "created": created, "updated": updated, "skipped": skipped, "total": seen}


# ── Attendance IDs (SeamlessHR is the master; the reader PIN follows it) ───────

def _clean_attendance_id(value) -> Optional[str]:
    """SeamlessHR returns the literal string "null" for employees with no ID."""
    v = str(value).strip() if value is not None else ""
    return None if (not v or v.lower() in ("null", "none", "nan")) else v


def apply_attendance_ids(db: Session, pairs: Dict[str, Any]) -> Dict[str, Any]:
    """Store SeamlessHR Attendance IDs on personnel.attendance_id.

    `pairs` maps SeamlessHR employee code (= staff_id = personnel.emp_code) to its
    Attendance ID. Nothing is invented: an ID that is not 1-9 digits (a numeric
    ZKTeco PIN) or that another employee already holds is reported, not stored.
    `repin_required` lists employees whose reader PIN changed — they may already be
    enrolled on readers under the old PIN and need re-syncing to the readers.
    """
    from sqlalchemy import func
    from ..models.personnel import Personnel
    from .device_pin import is_valid_pin

    rep: Dict[str, Any] = {"updated": 0, "unchanged": 0, "unknown_employee": [],
                           "invalid": [], "conflicts": [], "repin_required": []}
    for code, raw in pairs.items():
        code = str(code or "").strip()
        aid = _clean_attendance_id(raw)
        if not code or not aid:
            continue
        person = db.query(Personnel).filter(Personnel.emp_code == code).first()
        if not person:
            rep["unknown_employee"].append(code)
            continue
        if not is_valid_pin(aid):
            rep["invalid"].append({"emp_code": code, "attendance_id": aid})
            continue
        if person.attendance_id == aid:
            rep["unchanged"] += 1
            continue
        # Two IDs differing only by leading zeros ("122"/"0122") cannot be told apart
        # when a numeric reader reports its PIN, so they count as the same ID.
        # (flush below makes earlier rows of this same batch visible: the app's
        # sessions use autoflush=False.)
        other = db.query(Personnel).filter(
            func.ltrim(Personnel.attendance_id, "0") == aid.lstrip("0"),
            Personnel.emp_code != code).first()
        if other:
            rep["conflicts"].append({"emp_code": code, "attendance_id": aid,
                                     "held_by": other.emp_code})
            continue
        old_pin = person.attendance_id or person.emp_code
        person.attendance_id = aid
        db.flush()
        rep["updated"] += 1
        if old_pin != aid:
            rep["repin_required"].append(code)
    db.commit()
    return rep


async def adopt_attendance_ids(db: Session, days: int = 31) -> Dict[str, Any]:
    """Read employeeCode -> attendanceId pairs from SeamlessHR's attendance records
    (GET /v1/attendances) and store them. The employee list does not carry the
    Attendance ID, so this endpoint is the only API source for it."""
    cfg = get_config(db)
    if not cfg:
        return {"error": "SeamlessHR is not configured"}
    headers = await build_auth_headers(cfg)
    url = cfg["api_base_url"] + "/v1/attendances"
    end = date.today()
    start = end - timedelta(days=max(1, days))
    per_page = 100
    pairs: Dict[str, str] = {}
    pages = 0
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            while page <= 200:
                resp = await _get_with_retry(client, url, headers, {
                    "page": page, "perPage": per_page, "dateType": "custom",
                    "startDate": start.isoformat(), "endDate": end.isoformat()})
                if resp.status_code != 200:
                    msg = ""
                    try:
                        msg = resp.json().get("message", "")
                    except Exception:
                        pass
                    if "unauthorized" in msg.lower():
                        return {"error": "SeamlessHR refused the attendance read ('Unauthorized "
                                         "access') — this API key may not have Time & Attendance "
                                         "read access. Ask SeamlessHR to enable it, or use the "
                                         "import endpoint with an export."}
                    return {"error": f"SeamlessHR attendance read failed: HTTP {resp.status_code} {msg}"}
                rows = (resp.json() or {}).get("data") or []
                pages += 1
                for row in rows:
                    aid = _clean_attendance_id(row.get("attendanceId"))
                    code = str(row.get("employeeCode") or "").strip()
                    if aid and code:
                        pairs.setdefault(code, aid)
                if len(rows) < per_page:
                    break
                page += 1
    except httpx.RequestError as e:
        return {"error": f"Cannot reach SeamlessHR: {e}"}
    rep = apply_attendance_ids(db, pairs)
    rep.update({"pairs_found": len(pairs), "pages_read": pages})
    return rep


# ── Webhook handler (real-time employee sync FROM SeamlessHR) ──────────────────

def handle_webhook_event(db: Session, event: str, data: Dict, opts: Dict) -> str:
    """Apply a SeamlessHR employee webhook (create/update/deactivate) to personnel.

    Master fields are written and the record is stamped hr_source='SEAMLESSHR' so it
    becomes read-only in ApexPOB. A deactivate/exit marks the person inactive and
    removes them from POB. Field mapping is config-driven (options.webhook_field_map).
    Never raises — a bad event must not 500 the webhook (SeamlessHR would retry-storm).
    """
    from ..models.personnel import Personnel

    try:
        wfmap = opts.get("webhook_field_map") or {}
        code_field = wfmap.get("emp_code", "employee_code")
        code = str((data or {}).get(code_field) or "").strip()
        if not code:
            return "skipped: no employee_code in payload"

        ev = (event or "").lower()
        person = db.query(Personnel).filter(Personnel.emp_code == code).first()

        if ev in ("deactivate_employee", "exit_employee", "deactivate", "employee_deactivated"):
            if person:
                person.is_active = False
                person.is_onboard = False
                person.is_pob = False
                person.pob_location = None
                person.hr_source = "SEAMLESSHR"
                person.hr_synced_at = datetime.utcnow()
                db.commit()
                return f"deactivated {code}"
            return f"deactivate ignored — {code} not found"

        # create / update
        is_new = person is None
        if is_new:
            person = Personnel(emp_code=code, first_name="", last_name="", is_active=True)
            db.add(person)
        for pfield, sfield in wfmap.items():
            if pfield == "emp_code" or not sfield:
                continue
            val = data.get(sfield)
            if val is not None and hasattr(person, pfield):
                setattr(person, pfield, val)
        person.full_name = f"{person.first_name or ''} {person.last_name or ''}".strip()
        # Same department linking as the full pull — a webhook update must not
        # leave the employee unlinked from their department (and so shiftless).
        _link_department(db, person, set())
        person.is_active = True
        person.hr_source = "SEAMLESSHR"
        person.hr_synced_at = datetime.utcnow()
        db.commit()
        return f"{'created' if is_new else 'updated'} {code}"
    except Exception as e:
        db.rollback()
        logger.error("handle_webhook_event(%s) error: %s", event, e)
        return f"error: {e}"


# ── Leave sync (SeamlessHR "Employees On Leave" → excludes them from muster) ────

async def pull_leave(db: Session, triggered_by: str = "manual") -> Dict[str, Any]:
    """Refresh who is currently on approved leave from SeamlessHR and flag them
    (`personnel.on_leave`) so muster "expected" rosters exclude them — a person away
    on leave is never counted as MISSING in an emergency. Best-effort; never raises.
    Sets on_leave for everyone returned, clears it for everyone else (in one txn, so a
    failed fetch leaves state untouched)."""
    from ..models.personnel import Personnel

    cfg = get_config(db)
    if not cfg:
        return {"error": "SeamlessHR is not configured", "on_leave": 0}

    opts = cfg["options"]
    endpoint = opts.get("leave_endpoint") or "/v1/leave/on-leave"
    list_key = opts.get("leave_list_key", "data")
    lfmap = opts.get("leave_field_map") or {}
    code_field = lfmap.get("emp_code", "employee_code")
    end_field = lfmap.get("leave_end_date", "end_date")
    url = cfg["api_base_url"] + endpoint

    headers = await build_auth_headers(cfg)
    # SeamlessHR scopes by client id, so org_header_name defaults to "". Guard on
    # the name being non-empty or we would send a header with a blank name.
    org_header = opts.get("org_header_name")
    if cfg.get("org_id") and org_header:
        headers[org_header] = cfg["org_id"]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            body = resp.json()
        rows = body if isinstance(body, list) else (body.get(list_key) if isinstance(body, dict) else [])
        if not isinstance(rows, list):
            rows = []

        # Clear everyone first (fetch already succeeded), then set the returned staff.
        db.query(Personnel).filter(Personnel.on_leave == True).update(  # noqa: E712
            {"on_leave": False}, synchronize_session=False)
        count = 0
        for r in rows:
            if not isinstance(r, dict):
                continue
            code = str(r.get(code_field) or "").strip()
            if not code:
                continue
            vals = {"on_leave": True}
            end = r.get(end_field)
            if end:
                try:
                    vals["leave_end_date"] = datetime.fromisoformat(str(end)[:10]).date()
                except Exception:
                    pass
            db.query(Personnel).filter(Personnel.emp_code == code).update(vals, synchronize_session=False)
            count += 1
        db.commit()
        logger.info("pull_leave: %d on leave", count)
        return {"on_leave": count}
    except Exception as e:
        db.rollback()
        logger.warning("pull_leave error: %s", e)
        return {"error": str(e), "on_leave": 0}
