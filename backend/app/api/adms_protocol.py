"""
ADMS Protocol — BioTime-parity implementation
Handles /iclock/cdata, /iclock/getrequest, /iclock/devicecmd

Key improvements over the original:
  • Batch record parsing — tab-delimited multi-record bodies (devices buffer 100s offline)
  • Record-type routing — ATTLOG / USERINFO / OPERLOG / FINGERTMP / FACETMP
  • Stamp watermark — device only re-uploads records newer than last seen stamp
  • Full BioTime-compatible options block response
  • Device approval workflow — state=0 (pending) must be approved before attendance is processed
  • OPERLOG handler — door events, alarms, tamper written to iclock_operlog
  • USERINFO handler — employee data pushed by device synced to personnel_employee
  • FINGERTMP / FACETMP handler — templates stored in iclock_bio_template
  • pushver-aware responses
  • Full device capability fields stored (UserCount, FpCount, FaceCount, etc.)
  • Per-device heartbeat interval (Delay= in options block)
  • Command builders: USERINFO, FINGERTMP, FACETMP, SET TIMEZONE, USERATT, QUERY ATTLOG
"""

import re
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from ..services.device_planes import is_controller as _is_controller
from ..services.device_planes import is_direct_only as _is_direct_only

from ..core.database import get_db, SessionLocal
from ..services.device_pin import rewrite_command, resolve_emp_code
from ..core.config import settings
from ..models.biotime_models import (
    IClockTerminal, IClockTransaction, IClockDevcmd,
    IClockOperLog, IClockBioTemplate,
    PersonnelEmployee, AccDoor,
    AccLevel, AccUserAuthorize,
    AttShift, AttTimetable, MusteringEvent,
)
from ..models.personnel import Personnel, PersonnelStatus
from ..services.mustering_service import MusteringService
from ..core.websocket import broadcast_zone_update

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Auto-calculation trigger ─────────────────────────────────────────────────
# handle_attlog (sync) writes (emp_code, date_str) pairs here.
# _async_recalculate (async task) drains and processes them.
_pending_recalc: Set[Tuple[str, str]] = set()


async def _async_recalculate(emp_codes: Set[str], date_strs: Set[str]) -> None:
    """Background asyncio task: recalculate att_report for affected employees/dates."""
    from ..services.attendance_calculation_service import attendance_calculation_service
    db = SessionLocal()
    try:
        if not date_strs:
            return
        min_date = min(date_strs)
        max_date = max(date_strs)

        # Resolve personnel IDs for the affected emp_codes
        codes_list = list(emp_codes)
        placeholders = ",".join([f":c{i}" for i in range(len(codes_list))])
        params = {f"c{i}": c for i, c in enumerate(codes_list)}
        rows = db.execute(
            text(f"SELECT id FROM personnel WHERE emp_code IN ({placeholders}) AND is_active = true"),
            params,
        ).fetchall()
        emp_ids = [r.id for r in rows] if rows else None

        result = await attendance_calculation_service.calculate_attendance(
            emp_ids=emp_ids,
            start_date=min_date,
            end_date=max_date,
            db=db,
        )
        logger.info(
            f"Auto-calc triggered by device punch: {result.get('processed',0)} employees "
            f"updated for {min_date}–{max_date}"
        )
    except Exception as exc:
        logger.error(f"Auto-calc background task error: {exc}")
    finally:
        db.close()

# ── Constants ────────────────────────────────────────────────────────────────

ADMS_OK    = "OK"
ADMS_NONE  = "NONE"
ADMS_ERROR = "ERROR="


def _block_controller(sn, db):
    """Refuse ADMS command endpoints for InBio/C3 controllers (no driver yet)."""
    if _is_controller(sn, db):
        raise HTTPException(status_code=400, detail=(
            "InBio/C3 access controller — POB's controller (C3/PULL) driver isn't "
            "available yet, so this command can't be sent from here."))


def _block_direct_only(sn, db):
    """Refuse ADMS-queue-only command endpoints for a Direct (ZKLib TCP) reader.

    A direct-only reader never polls /iclock/getrequest, so a command queued in
    iclock_devcmd would sit there forever, undelivered. Reject with a clear message
    instead of black-holing it. ('both' devices poll too — they are allowed.)"""
    if _is_direct_only(sn, db):
        raise HTTPException(status_code=400, detail=(
            "This reader is in Direct (ZKLib TCP) mode and does not poll for ADMS "
            "commands, so a queued command would never reach it. Set its Connection "
            "Mode to 'adms' or 'both', or use the direct/ZKLib command path."))


def _encode_adms_datetime(dt: datetime) -> int:
    """Encode a datetime for the ZKTeco PUSH protocol's `SET OPTIONS DateTime=<n>`.

    Push-mode firmware does NOT understand the ZKLib-style "DATE TIME <str>" command
    (it replies Return=-1 / UNKNOWN CMD) — it sets its clock from this packed integer:
        ((Y-2000)*12*31 + (M-1)*31 + (D-1))*24*3600 + H*3600 + Min*60 + Sec
    Use naive local wall-clock time (matches build_options_block's DateTime=)."""
    return (((dt.year - 2000) * 12 * 31 + (dt.month - 1) * 31 + (dt.day - 1)) * 24 * 3600
            + dt.hour * 3600 + dt.minute * 60 + dt.second)


def queue_clock_sync(sn: str, db: Session) -> int:
    """Queue the ADMS-correct clock-correction command for a push reader and return
    the command id. ALWAYS use this for ADMS clock sync — never queue the ZKLib-style
    "DATE TIME <str>" form, which push firmware rejects as UNKNOWN CMD (it sets its
    clock from SET OPTIONS DateTime=<encoded> instead)."""
    # Only the newest clock command matters. Older ones still pending/sent are
    # superseded, so a backlog of stale times can never build up in the queue.
    db.execute(text("""
        UPDATE iclock_devcmd SET status = 2, cmd_return = 'Superseded by newer clock sync',
               cmd_return_time = NOW()
        WHERE sn = :sn AND status IN (0, 1) AND cmd_content LIKE 'SET OPTIONS DateTime=%'
    """), {'sn': sn})
    db.commit()
    enc = _encode_adms_datetime(datetime.now())
    return queue_command(sn, f"SET OPTIONS DateTime={enc}", db)


_CLOCK_CMD_PREFIX = "SET OPTIONS DateTime="


def _is_clock_cmd(cmd: str) -> bool:
    return (cmd or "").startswith(_CLOCK_CMD_PREFIX)

# state values on iclock_terminal
STATE_PENDING  = 0
STATE_APPROVED = 1
STATE_REJECTED = 2
STATE_OFFLINE  = 3

# OPERLOG event codes
OPER_EVENT_LABELS = {
    0:   "Door Normal",
    1:   "Door Alarm",
    2:   "Tamper",
    3:   "Anti-Passback",
    4:   "Duress",
    5:   "Fire Unlock",
    6:   "Emergency Lock",
    8:   "Door Open Too Long",
    9:   "Door Open Too Long Cleared",
    200: "Admin Operation",
    255: "Unknown",
}

_SN_RE = re.compile(r'^[A-Za-z0-9\-]{4,30}$')

# ── Pydantic schemas ─────────────────────────────────────────────────────────

class CommandRequest(BaseModel):
    sn: str
    cmd_content: str

class ApproveRequest(BaseModel):
    sn: str
    action: str   # "approve" | "reject"

class PushUsersRequest(BaseModel):
    sn: str
    emp_codes: Optional[List[str]] = None  # None = all employees

class PushTemplatesRequest(BaseModel):
    sn: str
    emp_codes: Optional[List[str]] = None

class PushTimezonesRequest(BaseModel):
    sn: str
    shift_ids: Optional[List[int]] = None  # None = all shifts

class PushAccessLevelsRequest(BaseModel):
    sn: str
    level_ids: Optional[List[int]] = None  # None = all levels

# ── Validation ───────────────────────────────────────────────────────────────

def _valid_sn(sn: str) -> bool:
    return bool(sn and _SN_RE.match(sn))

# ── Body parser ──────────────────────────────────────────────────────────────

# Map the ZKTeco `table=` query value AND OPERLOG line prefixes to our record
# types. Real readers signal attendance with `table=ATTLOG` and user/biometric
# edits with `table=OPERLOG`, whose rows are prefixed USER / FP / FACE / BIODATA.
_TYPE_ALIASES = {
    "ATTLOG": "ATTLOG", "ATTPHOTO": "ATTPHOTO",
    "OPERLOG": "OPERLOG", "OPLOG": "OPERLOG",
    "USER": "USERINFO", "USERINFO": "USERINFO",
    "FP": "FINGERTMP", "FINGERTMP": "FINGERTMP",
    "FACE": "FACETMP", "FACETMP": "FACETMP", "FACEV2": "FACETMP",
    "BIODATA": "BIODATA", "BIOPHOTO": "ATTPHOTO",
}


def _parse_positional_attlog(parts: List[str]) -> Dict[str, str]:
    """Canonical ZKTeco ATTLOG row (no keys), tab-separated positional fields:
        PIN  Time  Status  VerifyType  WorkCode  Reserved…
    This is what BioTime receives — the type comes from the `table=ATTLOG` query
    param, not the body, so there is nothing to key on inside the row."""
    vals = [p.strip() for p in parts]
    if len(vals) < 2 or not vals[0] or not vals[1]:
        return {}
    fields = {"PIN": vals[0], "Time": vals[1]}
    if len(vals) > 2 and vals[2] != "": fields["Status"]   = vals[2]
    if len(vals) > 3 and vals[3] != "": fields["Verify"]   = vals[3]
    if len(vals) > 4 and vals[4] != "": fields["WorkCode"] = vals[4]
    return fields


def parse_adms_body(body: str, table_hint: Optional[str] = None) -> List[Tuple[str, Dict[str, str]]]:
    """
    Parse an ADMS POST body and return a list of (record_type, field_dict) tuples.

    Handles three wire formats ZKTeco devices actually send:

    Format A — legacy key=value, one record per body (pushver 1.x):
        PIN=001\\nTime=2024-01-15 14:30:25\\nStatus=0\\nVerify=1

    Format B — inline prefix, one record per line (most common, pushver 2.x):
        ATTLOG\\tSN=BKMD203\\tUserID=001\\tLogTime=2024-01-15 14:30:25\\tVerifyMode=1\\tInOutStatus=0
        ATTLOG\\tSN=BKMD203\\tUserID=002\\tLogTime=2024-01-15 14:31:00\\tVerifyMode=1\\tInOutStatus=1

    Format C — section header then tab-delimited rows (some firmware variants):
        ATTLOG
        SN=BKMD203\\tUserID=001\\tLogTime=2024-01-15 14:30:25\\tVerifyMode=1\\tInOutStatus=0
    """
    if not body or not body.strip():
        return []

    lines = [l.rstrip('\r') for l in body.strip().split('\n') if l.strip()]
    records: List[Tuple[str, Dict[str, str]]] = []

    KNOWN_TYPES = {"ATTLOG", "OPERLOG", "USERINFO", "FINGERTMP", "FACETMP",
                   "ATTPHOTO", "ENROLL_FP", "FACE", "BIODATA"}

    # ── Canonical path: the URL's `table=` tells us the record type ──────────────
    # This is how BioTime/ZKTeco firmware actually work. When present, trust it:
    #   table=ATTLOG  → positional rows  PIN⇥Time⇥Status⇥Verify⇥WorkCode
    #   table=OPERLOG → rows prefixed USER / FP / FACE / BIODATA (key=value)
    # Rows may still carry their own type prefix (some firmware double-tags); we
    # honour that first, then fall back to the table type from the URL.
    table = _TYPE_ALIASES.get((table_hint or "").strip().upper(), (table_hint or "").strip().upper())
    if table:
        recs: List[Tuple[str, Dict[str, str]]] = []
        for line in lines:
            head = line.split(None, 1)                         # split on first whitespace
            tag  = _TYPE_ALIASES.get(head[0].strip().upper()) if head else None
            if tag and len(head) > 1 and '=' in head[1]:
                fields = _parse_tab_fields(head[1].split('\t'))
                if fields:
                    recs.append((tag, fields))
                    continue
            if '=' in line:                                    # key=value row under this table
                fields = _parse_tab_fields(line.split('\t'))
                if fields:
                    recs.append((table, fields))
            elif table == "ATTLOG":                            # positional punch row
                fields = _parse_positional_attlog(line.split('\t'))
                if fields:
                    recs.append(("ATTLOG", fields))
            # else: positional non-ATTLOG payload (e.g. photo blob) — skip
        if recs:
            return recs
        # table given but nothing parsed → fall through to the heuristics below

    # Detect Format A (legacy key=value): no tab chars, contains '='
    if '\t' not in body and '=' in body:
        fields = _parse_kv_lines(lines)
        if fields:
            # Determine record type from fields
            rtype = "ATTLOG" if ("PIN" in fields or "UserID" in fields) else "UNKNOWN"
            records.append((rtype, fields))
        return records

    # Format B / C
    current_type: Optional[str] = None
    for line in lines:
        parts = line.split('\t')
        first = parts[0].strip().upper()

        if first in KNOWN_TYPES:
            if len(parts) == 1:
                # Format C: section header only — subsequent lines belong to this type
                current_type = first
                continue
            else:
                # Format B: inline prefix with fields on same line
                fields = _parse_tab_fields(parts[1:])
                records.append((first, fields))
        elif current_type:
            # Format C continuation row
            fields = _parse_tab_fields(parts)
            if fields:
                records.append((current_type, fields))
        else:
            # Fallback: try key=value
            fields = _parse_kv_lines([line])
            if fields:
                rtype = "ATTLOG" if ("PIN" in fields or "UserID" in fields) else "UNKNOWN"
                records.append((rtype, fields))

    return records


def _parse_tab_fields(parts: List[str]) -> Dict[str, str]:
    """Parse tab-separated key=value pairs OR positional fields."""
    fields: Dict[str, str] = {}
    for part in parts:
        part = part.strip()
        if '=' in part:
            k, v = part.split('=', 1)
            fields[k.strip()] = v.strip()
    return fields


def _parse_kv_lines(lines: List[str]) -> Dict[str, str]:
    """Parse newline-separated key=value pairs."""
    fields: Dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if '=' in line:
            k, v = line.split('=', 1)
            fields[k.strip()] = v.strip()
    return fields


def parse_device_options(options: str) -> Dict[str, Any]:
    """Parse the ADMS 'options' query-string: UserCount=50,FpCount=100,FW=Ver6.60,..."""
    info: Dict[str, Any] = {}
    if not options:
        return info
    for pair in options.split(','):
        if '=' not in pair:
            continue
        k, v = pair.split('=', 1)
        k, v = k.strip(), v.strip()
        if k in ('UserCount', 'FpCount', 'FaceCount', 'PalmCount', 'LogCount'):
            try:
                info[k] = int(v)
            except ValueError:
                info[k] = 0
        elif k == 'FW':
            info['fw_version'] = v
        elif k in ('DeviceName', '~DeviceName'):
            info['device_name'] = v
        elif k == 'OEMVendor':
            info['oem_vendor'] = v
        elif k == 'Platform':
            info['platform'] = v
        elif k == 'Language':
            info['language'] = v
        elif k == 'MAC':
            info['mac_address'] = v
        elif k == 'IP':
            info['reported_ip'] = v   # device's own LAN IP (some firmware sends this)
        else:
            info[k] = v
    return info

# ── Options block builder ────────────────────────────────────────────────────

def build_options_block(terminal: IClockTerminal, pushver: str) -> str:
    """
    Return the options block sent in response to a heartbeat.

    v1.x devices only understand a small subset of fields — sending v2.x-only
    fields (PushProtVer, PushOptionsFlag, ATTPHOTOStamp, SetTime) causes some
    firmware to treat the response as invalid and stop heartbeating.
    """
    stamp      = terminal.att_stamp  or 0
    op_stamp   = terminal.op_stamp   or 0
    user_stamp = terminal.user_stamp or 0
    delay      = terminal.heartbeat_interval or 10
    server_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # PushVer 2.x AND 3.x (newer Android terminals like Horus) use the full v2
    # options set; only legacy 1.x needs the reduced field list.
    is_v2 = pushver[:1] in ("2", "3")

    lines = [
        "GET OPTION FROM THE SERVER",
        f"Stamp={stamp}",
        f"OpStamp={op_stamp}",
        f"ATTLOGStamp={stamp}",
        f"OPERLOGStamp={op_stamp}",
    ]
    if is_v2:
        lines.append("ATTPHOTOStamp=0")
    lines += [
        f"UserStamp={user_stamp}",
        "ErrorDelay=30",
        f"Delay={delay}",
        "TransTimes=00:00;23:59",
        "TransInterval=1",
        # TransFlag selects WHICH record types the reader uploads. Without it (or
        # with 0s) the reader never transmits attendance — punches stay on-device.
        # 10 ones = upload everything (attlog, oplog, attphoto, bio, etc.).
        "TransFlag=1111111111",
        # Realtime=1 → push each event the moment it happens (not just on the
        # TransInterval/TransTimes schedule). Required for live attendance/zone feeds.
        "Realtime=1",
        "Encrypt=0",
        "TimeZone=0",
        f"DateTime={server_time}",
    ]
    if is_v2:
        lines.append("SetTime=1")
    lines.append(f"ServerVer={pushver}")
    if is_v2:
        lines += ["PushProtVer=2.3.1", "PushOptionsFlag=1"]
    return "\n".join(lines)

# ── Record handlers ──────────────────────────────────────────────────────────

def _parse_punch_time(time_str: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            dt = datetime.strptime(time_str, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        # Reject implausible timestamps from devices with a misconfigured clock
        # (e.g. year 2103). A future-dated punch is permanently "newest", which
        # breaks every latest-punch query (zone occupancy, attendance) forever —
        # better to drop it than poison the data. The device clock is corrected via
        # DateTime= on the next heartbeat, so real punches resume normally.
        now = datetime.now(timezone.utc)
        if dt.year < 2015 or dt.year > now.year + 1:
            return None
        return dt
    return None


def _punch_already_stored(emp_code: str, punch_time: datetime, sn: str, db: Session) -> bool:
    """True if this exact punch is already in iclock_transaction. ZKTeco readers
    resend un-acked batches (and a lost OK duplicates a punch), so we dedupe on
    the same key BioTime uses: (emp_code, punch_time, terminal_sn)."""
    try:
        return db.query(IClockTransaction.id).filter(
            IClockTransaction.emp_code   == emp_code,
            IClockTransaction.punch_time == punch_time,
            IClockTransaction.terminal_sn == sn,
        ).first() is not None
    except Exception:
        db.rollback()
        return False


def handle_attlog(records: List[Dict], sn: str, db: Session) -> Tuple[int, int, Dict[int, int]]:
    """
    Process a batch of ATTLOG records.
    Routes each punch based on the terminal's reader_purpose:
      ATTENDANCE   → write iclock_transaction (T&A)
      ACCESS_ENTRY → zone entry tracking + access_logs (no T&A record)
      ACCESS_EXIT  → zone exit tracking + access_logs (no T&A record)
    Returns (saved_count, latest_stamp, zone_updates) where zone_updates
    is Dict[zone_id → new_occupancy_count] for broadcasting.
    """
    saved = 0
    latest_ts = 0
    affected_codes: Set[str] = set()
    affected_dates: Set[str] = set()
    zone_updates: Dict[int, int] = {}

    # Look up terminal once — determines routing for entire batch
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    reader_purpose = (terminal.reader_purpose if terminal and terminal.reader_purpose
                      else 'ATTENDANCE')

    # Reader's zone name — stamped onto personnel.current_location on check-in so the
    # POB dashboard's location breakdown is meaningful.
    zone_name = None
    if terminal and getattr(terminal, "zone_id", None):
        try:
            _zr = db.execute(text("SELECT name FROM zones WHERE id = :z"), {"z": terminal.zone_id}).fetchone()
            zone_name = _zr.name if _zr else None
        except Exception:
            zone_name = None

    # Check mustering mode for this device once. A reader counts as a muster reader
    # if EITHER its access-door has mustering_mode set OR its purpose is MUSTERING
    # (the simple way to designate a Horus handheld at a muster point) OR it's a
    # mustering-type terminal (device_type=2).
    #
    # Time & attendance terminals NEVER take part in mustering: they can be in another
    # state or country. Mustering works on access-control readers only (zones + doors).
    acc_door = db.query(AccDoor).filter(AccDoor.terminal_sn == sn).first()
    ta_terminal = reader_purpose == 'ATTENDANCE' and getattr(terminal, 'device_type', None) != 2
    mustering_mode = (not ta_terminal) and (
        bool(acc_door and getattr(acc_door, 'mustering_mode', False))
        or reader_purpose == 'MUSTERING'
        or getattr(terminal, 'device_type', None) == 2)
    if not mustering_mode and not ta_terminal:
        # Any reader that stands at a MUSTER POINT (placed there on the zone, or the
        # zone names it as its reader) counts people safe while a muster is running —
        # no need to re-purpose it, and it goes back to normal when the muster ends.
        try:
            at_point = db.execute(text("""
                SELECT 1 FROM zones z
                WHERE z.zone_type = 'MUSTER_POINT'
                  AND (z.reader_sn = :sn OR z.id = :zid)
                  AND EXISTS (SELECT 1 FROM mustering_event WHERE status = 0)
                LIMIT 1"""), {"sn": sn, "zid": getattr(terminal, "zone_id", None) or -1}).scalar()
            mustering_mode = bool(at_point)
        except Exception as e:
            logger.warning("Muster-point reader check failed for %s: %s", sn, e)
            db.rollback()

    for rec in records:
        emp_code = rec.get('PIN') or rec.get('UserID') or rec.get('USERID')
        time_str = rec.get('Time') or rec.get('LogTime') or rec.get('LOGTIME')
        if not emp_code or not time_str:
            continue
        emp_code = resolve_emp_code(db, emp_code)   # reader PIN (SeamlessHR attendance ID) -> emp_code

        punch_time = _parse_punch_time(time_str)
        if not punch_time:
            logger.warning(f"ADMS ATTLOG bad timestamp from {sn}: {time_str!r}")
            continue

        ts_int = int(punch_time.timestamp())
        if ts_int > latest_ts:
            latest_ts = ts_int

        # ── ACCESS_ENTRY / ACCESS_EXIT readers ───────────────────────────────
        # Zone tracking is handled first; then fall through to also write a T&A
        # record to iclock_transaction so attendance calculation still works.
        # punch_state is forced to 0 (check-in) for ENTRY and 1 (check-out) for EXIT
        # so the calculation engine classifies the direction correctly without
        # relying on the device's Status field (which may be 0 for both on some models).
        if reader_purpose in ('ACCESS_ENTRY', 'ACCESS_EXIT'):
            direction = 'ENTRY' if reader_purpose == 'ACCESS_ENTRY' else 'EXIT'
            if mustering_mode:
                # An access-control door at a muster point counts the person safe while a
                # muster runs — and is still recorded as a normal door tap below.
                try:
                    MusteringService(db).process_mustering_punch(emp_code=emp_code, device_sn=sn, check_time=punch_time)
                except Exception as e:
                    logger.warning(f"Muster check-in at access reader {sn} for {emp_code}: {e}")
                    db.rollback()
            try:
                updates = _handle_zone_access(emp_code, sn, punch_time, terminal, direction, db)
                zone_updates.update(updates)
                logger.debug(f"Zone access {direction}: {emp_code}@{sn} zone={terminal.zone_id}")
            except Exception as e:
                logger.error(f"Zone access error {emp_code}@{sn}: {e}")
            # On-board status is set inside _handle_zone_access (entry = on site,
            # exit through a site-boundary zone = off site).
            # Door taps are NOT attendance: time & attendance comes only from T&A
            # readers (same rule as the ZKTeco controllers' access readers).
            saved += 1

            # Write to acc_event so every door swipe appears in the access control log.
            # Use _ensure_access_control_records so door_id is always valid.
            try:
                in_out_val = 0 if direction == 'ENTRY' else 1
                door_id = _ensure_access_control_records(
                    sn, getattr(terminal, 'alias', None) or sn,
                    terminal.zone_id, direction, db
                )

                emp_row = db.execute(text(
                    "SELECT first_name || ' ' || last_name AS full_name "
                    "FROM personnel_employee WHERE emp_code = :code LIMIT 1"
                ), {'code': emp_code}).fetchone()

                db.execute(text("""
                    INSERT INTO acc_event
                        (event_time, terminal_sn, door_id, emp_code, emp_name,
                         event_type, in_out, description)
                    VALUES
                        (:et, :sn, :did, :ec, :en, 0, :io, :desc)
                """), {
                    'et':   punch_time,
                    'sn':   sn,
                    'did':  door_id,
                    'ec':   emp_code,
                    'en':   emp_row.full_name if emp_row else '',
                    'io':   in_out_val,
                    'desc': f'{"Entry" if direction == "ENTRY" else "Exit"} — {terminal.alias or sn}',
                })
                db.flush()
            except Exception as e:
                logger.error(f"acc_event write error {emp_code}@{sn}: {e}")
            continue

        # ── TRANSPORT_CHECKIN reader (helideck / gangway / heliport) ─────────
        # A tap checks the person in to their next manifested flight. The punch is
        # still stored below (raw log), but attendance ignores non-ATTENDANCE readers.
        if reader_purpose == 'TRANSPORT_CHECKIN':
            try:
                from .transport_manifest import checkin_from_reader
                res = checkin_from_reader(db, emp_code, punch_time, sn)
                logger.info("Transport check-in %s@%s: %s", emp_code, sn, res or "no flight found")
            except Exception as te:
                logger.error("Transport check-in error %s@%s: %s", emp_code, sn, te)
                db.rollback()

        # ── ATTENDANCE reader (default) ───────────────────────────────────────
        raw_state = rec.get('Status') or rec.get('InOutStatus') or rec.get('INOUTSTATUS') or '0'
        try:
            punch_state = int(raw_state)
            # Valid range: 0=check-in 1=check-out 2=break-out 3=break-in 4=ot-in 5=ot-out
            if not (0 <= punch_state <= 5):
                logger.warning("ADMS %s: punch_state=%s out of range for %s — reset to 0", sn, punch_state, emp_code)
                punch_state = 0
        except (ValueError, TypeError):
            punch_state = 0

        verify_raw = rec.get('Verify') or rec.get('VerifyMode') or rec.get('VERIFYMODE') or '0'
        try:
            verify_type = int(verify_raw)
        except (ValueError, TypeError):
            verify_type = 0

        work_raw = rec.get('WorkCode') or rec.get('WORKCODE') or '0'
        try:
            work_code = int(work_raw)
        except (ValueError, TypeError):
            work_code = 0

        area_alias = rec.get('Area') or rec.get('AreaAlias') or ''

        if mustering_mode:
            try:
                mustering_service = MusteringService(db)
                mustering_service.process_mustering_punch(
                    emp_code=emp_code, device_sn=sn, check_time=punch_time
                )
                saved += 1
            except Exception as e:
                logger.error(f"Mustering punch error for {emp_code}@{sn}: {e}")
            continue

        # Skip resent/duplicate punches (reader retries an un-acked batch).
        if _punch_already_stored(emp_code, punch_time, sn, db):
            continue

        try:
            txn = IClockTransaction(
                emp_code=emp_code,
                punch_time=punch_time,
                punch_state=punch_state,
                verify_type=verify_type,
                work_code=work_code,
                terminal_sn=sn,
                area_alias=area_alias,
                upload_time=datetime.now(timezone.utc),
            )
            db.add(txn)
            db.flush()
            saved += 1
            affected_codes.add(emp_code)
            affected_dates.add(punch_time.strftime('%Y-%m-%d'))

            # A T&A tap is attendance only. It does NOT put anyone on board, move them
            # into a zone or onto a muster list: T&A terminals can be in another state
            # or country. Presence on site, zones and mustering come from access-control
            # readers (_handle_zone_access / C3 controllers) and flight manifests.

        except Exception as e:
            logger.error(f"ATTLOG save error {emp_code}@{sn}: {e}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as e:
        logger.error(f"ATTLOG batch commit error for {sn}: {e}")
        db.rollback()

    logger.info(f"ATTLOG {sn}: saved {saved}/{len(records)} records, latest_stamp={latest_ts}")

    # ── Time-drift detection ─────────────────────────────────────────────────
    # Compare the most recent punch's LogTime to the server's upload_time.
    # A large gap means the device clock is wrong.  Auto-queue SET DATE TIME
    # to correct it immediately (belt-and-suspenders — DateTime= in the options
    # block already corrects drift on every heartbeat, but this fires a
    # dedicated command for devices whose firmware ignores DateTime=).
    if saved > 0 and affected_codes:
        try:
            server_now  = datetime.now(timezone.utc)
            # latest_ts is the Unix timestamp of the newest punch from the device
            if latest_ts > 0:
                device_time = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
                drift_secs  = abs((server_now - device_time).total_seconds())
                # Ignore drift < 60 s (network latency + normal skew)
                # and > 86400 s (likely a date error, not a clock drift)
                if 60 < drift_secs < 86400:
                    logger.warning(
                        f"ADMS {sn}: clock drift detected — {drift_secs:.0f}s off server time. "
                        f"Queuing SET OPTIONS DateTime correction."
                    )
                    # The reader just pushed punches via /iclock, so it IS on the ADMS
                    # plane and polls getrequest — queue the ADMS-correct clock command.
                    # Push firmware rejects the ZKLib-style "DATE TIME <str>" (UNKNOWN
                    # CMD); it sets its clock from SET OPTIONS DateTime=<encoded>.
                    try:
                        queue_clock_sync(sn, db)
                    except Exception as qe:
                        logger.error(f"Failed to queue clock correction for {sn}: {qe}")
        except Exception as de:
            logger.warning(f"Drift detection non-fatal error for {sn}: {de}")

    # Fire background recalculation for affected employees so att_report
    # is updated within seconds of each punch — no manual trigger needed.
    if saved > 0 and affected_codes:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_async_recalculate(affected_codes, affected_dates))
        except RuntimeError:
            pass  # no event loop in test context — safe to skip

    return saved, latest_ts, zone_updates


def handle_operlog(records: List[Dict], sn: str, db: Session) -> Tuple[int, int]:
    """Process a batch of OPERLOG records → iclock_operlog table."""
    saved = 0
    latest_ts = 0

    for rec in records:
        event_code_raw = rec.get('OperEvent') or rec.get('OPEREVENT') or '255'
        time_str       = rec.get('Time') or rec.get('LogTime') or rec.get('EventTime') or ''
        admin_id       = rec.get('AdminID') or rec.get('UserID') or None
        obj            = rec.get('Object') or rec.get('OBJECT') or None
        param1         = rec.get('Param1') or rec.get('PARAM1') or None
        param2         = rec.get('Param2') or rec.get('PARAM2') or None

        event_time = _parse_punch_time(time_str)
        if not event_time:
            continue

        ts_int = int(event_time.timestamp())
        if ts_int > latest_ts:
            latest_ts = ts_int

        try:
            event_code = int(event_code_raw)
        except (ValueError, TypeError):
            event_code = 255

        try:
            log = IClockOperLog(
                terminal_sn  = sn,
                oper_event   = event_code,
                event_time   = event_time,
                admin_id     = admin_id,
                object_name  = obj,
                param1       = param1,
                param2       = param2,
                raw_data     = str(rec),
            )
            db.add(log)
            saved += 1
        except Exception as e:
            logger.error(f"OPERLOG save error {sn}: {e}")

    try:
        db.commit()
    except Exception as e:
        logger.error(f"OPERLOG batch commit error {sn}: {e}")
        db.rollback()

    logger.info(f"OPERLOG {sn}: saved {saved}/{len(records)} records")
    return saved, latest_ts


def _hr_is_master(db: Session) -> bool:
    """True when the SeamlessHR integration is enabled, i.e. employees come from HR."""
    try:
        row = db.execute(text(
            "SELECT is_enabled FROM hr_integration_config ORDER BY id DESC LIMIT 1")).fetchone()
        return bool(row and row[0])
    except Exception:
        db.rollback()
        return False


def handle_userinfo(records: List[Dict], sn: str, db: Session) -> int:
    """
    Sync employee data pushed by device → personnel_employee.
    Updates existing employees (card_no, name) and creates new ones for
    unrecognised emp_codes so that "Get Users from Device" works fully
    on PushVer 2.x firmware.
    """
    updated = 0
    created = 0
    # Track emp_codes added this batch to avoid duplicates within the same upload
    seen_this_batch: set = set()
    unknown_pins: List[str] = []

    for rec in records:
        emp_code = resolve_emp_code(
            db, str(rec.get('PIN') or rec.get('UserID') or rec.get('USERID') or '').strip())
        name     = str(rec.get('Name') or rec.get('NAME') or '').strip()
        card     = str(rec.get('Card') or rec.get('CardNo') or rec.get('CARDNO') or '').strip()

        if not emp_code or emp_code in seen_this_batch:
            continue
        seen_this_batch.add(emp_code)

        try:
            employee = db.query(PersonnelEmployee).filter(
                PersonnelEmployee.emp_code == emp_code
            ).first()

            if employee:
                if card:
                    employee.card_no = card
                if name and not employee.first_name:
                    parts = name.split()
                    employee.first_name = parts[0]
                    employee.last_name  = " ".join(parts[1:]) if len(parts) > 1 else employee.last_name
                db.flush()
                updated += 1
                logger.debug(f"USERINFO updated emp_code={emp_code} card={card}")
            elif _hr_is_master(db):
                # SeamlessHR owns the employee master: an ID that exists only on a reader
                # must not become a second, ghost employee record. Leave it for HR to add.
                unknown_pins.append(emp_code)
            else:
                parts      = name.split() if name else [emp_code]
                first_name = parts[0]
                last_name  = " ".join(parts[1:]) if len(parts) > 1 else ""
                new_emp = PersonnelEmployee(
                    emp_code   = emp_code,
                    first_name = first_name,
                    last_name  = last_name,
                    card_no    = card or None,
                    status     = 0,
                )
                db.add(new_emp)
                db.flush()
                created += 1
                logger.debug(f"USERINFO created emp_code={emp_code} name={name!r}")

        except Exception as e:
            db.rollback()
            logger.error(f"USERINFO sync error emp_code={emp_code}: {e}")

    try:
        db.commit()
    except Exception as e:
        logger.error(f"USERINFO batch commit error {sn}: {e}")
        db.rollback()

    # Mark user_stamp > 0 so the options block stops sending UserStamp=0
    # and the device won't re-upload on every heartbeat
    db.execute(text(
        "UPDATE iclock_terminal SET user_stamp = 1 WHERE sn = :sn AND user_stamp = 0"
    ), {'sn': sn})
    db.commit()

    if unknown_pins:
        logger.warning(
            "USERINFO %s: %d user ID(s) on the reader match no employee and were NOT created "
            "(SeamlessHR is the employee master): %s",
            sn, len(unknown_pins), ", ".join(unknown_pins[:20]) + (" ..." if len(unknown_pins) > 20 else ""))
    logger.info(f"USERINFO {sn}: updated={updated} created={created} unknown={len(unknown_pins)} total={len(records)}")
    return updated + created


def handle_fingertmp(records: List[Dict], sn: str, db: Session) -> int:
    """Store fingerprint templates uploaded by device → iclock_bio_template."""
    saved = 0
    for rec in records:
        emp_code  = resolve_emp_code(db, rec.get('PIN') or rec.get('UserID') or '')
        finger_id = rec.get('FingerID') or rec.get('FINGERID') or '0'
        size      = rec.get('Size') or rec.get('SIZE') or '0'
        valid     = rec.get('Valid') or rec.get('VALID') or '1'
        tmp_data  = rec.get('TmpData') or rec.get('TMPDATA') or ''
        if not emp_code or not tmp_data:
            continue
        try:
            finger_idx = int(finger_id)
            tpl_size   = int(size) if size else None
            is_valid   = str(valid) not in ('0', 'false', 'False')
        except (ValueError, TypeError):
            finger_idx = 0; tpl_size = None; is_valid = True

        try:
            existing = db.query(IClockBioTemplate).filter(
                IClockBioTemplate.emp_code  == emp_code,
                IClockBioTemplate.finger_id == finger_idx,
            ).first()
            if existing:
                existing.template_data  = tmp_data
                existing.template_size  = tpl_size
                existing.valid          = is_valid
                existing.source_sn      = sn
                existing.updated_at     = datetime.now(timezone.utc)
            else:
                db.add(IClockBioTemplate(
                    emp_code=emp_code, finger_id=finger_idx,
                    template_size=tpl_size, valid=is_valid,
                    template_data=tmp_data, source_sn=sn,
                ))
            saved += 1
        except Exception as e:
            logger.error(f"FINGERTMP save error {emp_code}#{finger_idx}: {e}")

    try:
        db.commit()
    except Exception as e:
        logger.error(f"FINGERTMP batch commit error {sn}: {e}")
        db.rollback()

    logger.info(f"FINGERTMP {sn}: upserted {saved}/{len(records)} templates")
    return saved


def handle_facetmp(records: List[Dict], sn: str, db: Session) -> int:
    """Store face templates — finger_id = -1 convention."""
    face_records = [{**r, 'FingerID': '-1'} for r in records]
    return handle_fingertmp(face_records, sn, db)


def handle_biodata(records: List[Dict], sn: str, db: Session) -> int:
    """Store BIODATA records — the unified biometric format newer Android/face
    terminals (e.g. Horus) push instead of FINGERTMP/FACETMP. Logs the first
    record's shape so the exact field/Type names can be confirmed against the real
    device, then maps into iclock_bio_template (finger_id -1 = face, 0-9 = fp slot).
    BioType mapping is firmware-dependent — VERIFY on the actual Horus."""
    if records:
        logger.info("BIODATA %s: %d record(s); first keys=%s",
                    sn, len(records), list(records[0].keys()))
    mapped: List[Dict] = []
    for r in records:
        pin = r.get('PIN') or r.get('Pin') or r.get('UserID') or r.get('UserPin')
        pin = resolve_emp_code(db, pin) if pin else pin
        tmp = r.get('Tmp') or r.get('TMP') or r.get('TmpData') or r.get('Template') or ''
        if not pin or not tmp:
            continue
        try:
            btype = int(r.get('Type') or r.get('TYPE') or 0)
        except (TypeError, ValueError):
            btype = 0
        if btype in (2, 9):                 # face (visible/IR) — VERIFY
            fid = -1
        else:                                # fingerprint slot from No/Index
            idx = r.get('No') or r.get('Index') or '0'
            fid = int(idx) if str(idx).isdigit() else 0
        mapped.append({'PIN': pin, 'FingerID': str(fid),
                       'Size': r.get('Size') or r.get('SIZE') or '0',
                       'Valid': r.get('Valid') or r.get('VALID') or '1',
                       'TmpData': tmp})
    return handle_fingertmp(mapped, sn, db) if mapped else 0

# ── Terminal management ──────────────────────────────────────────────────────

# Known Docker-internal gateway IPs that are never real device addresses.
# Docker Desktop (Mac) rewrites all source IPs to 192.168.65.1.
# Docker Linux default bridge gateway is 172.17.0.1.
# We guard only these specific IPs — NOT the entire 172.x.x.x range,
# which is a legitimate RFC-1918 private address space used by many devices.
_DOCKER_GATEWAY_IPS: frozenset = frozenset({
    '192.168.65.1',   # Docker Desktop (Mac/Win)
    '172.17.0.1',     # Docker Linux default bridge
    '172.18.0.1',     # Docker custom bridge (common)
    '172.19.0.1',
    '172.20.0.1',
    # Loopback / invalid — never a real device IP; ignore so local requests
    # (health checks, internal tests, a misconfigured reader) can't overwrite a
    # device's real IP and break direct polling.
    '127.0.0.1',
    '::1',
    'localhost',
    '0.0.0.0',
    '',
})


# ── Device deletion suppression ──────────────────────────────────────────────
# When an admin DELETES a reader in the UI, remember its SN so the LAN scanner and
# ADMS auto-registration do not silently re-add it — UI deletes must "stick".
# Re-adding the reader through the UI (create/approve) clears the suppression.

def _ensure_suppression_table(db: Session) -> None:
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS device_suppressed (
            sn TEXT PRIMARY KEY,
            suppressed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))


# These helpers use their OWN short-lived session so a failure here can never
# roll back the caller's transaction (e.g. the terminal delete/create). The
# `db` parameter is accepted for call-site convenience but intentionally unused.

def is_device_suppressed(_db: Session, sn: str) -> bool:
    from ..core.database import SessionLocal
    s = SessionLocal()
    try:
        return s.execute(text("SELECT 1 FROM device_suppressed WHERE sn = :sn"),
                         {"sn": sn}).fetchone() is not None
    except Exception:
        return False
    finally:
        s.close()


def suppress_device(_db: Session, sn: str) -> None:
    from ..core.database import SessionLocal
    s = SessionLocal()
    try:
        s.execute(text("INSERT INTO device_suppressed (sn) VALUES (:sn) "
                       "ON CONFLICT (sn) DO NOTHING"), {"sn": sn})
        s.commit()
    except Exception as e:
        s.rollback()
        logger.warning("suppress_device(%s) failed: %s", sn, e)
    finally:
        s.close()


def unsuppress_device(_db: Session, sn: str) -> None:
    from ..core.database import SessionLocal
    s = SessionLocal()
    try:
        s.execute(text("DELETE FROM device_suppressed WHERE sn = :sn"), {"sn": sn})
        s.commit()
    except Exception as e:
        s.rollback()
        logger.warning("unsuppress_device(%s) failed: %s", sn, e)
    finally:
        s.close()


def upsert_terminal(
    sn: str, client_ip: str, device_info: Dict[str, Any],
    pushver: str, db: Session
) -> Optional[IClockTerminal]:
    """
    Update an existing terminal's heartbeat fields, OR auto-register a new one
    in STATE_PENDING if ZKTECO_AUTO_REGISTER_DEVICES is enabled.
    Returns None if device is rejected.
    """
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()

    if terminal:
        if terminal.state == STATE_REJECTED:
            logger.info(f"Rejected device {sn} attempted connection — ignored")
            return None

        # Always update heartbeat fields regardless of approval state
        terminal.last_activity = datetime.now(timezone.utc)
        # Resolve the best available IP:
        #   1. Use the TCP source IP if it is not a Docker gateway
        #   2. Fall back to the device-reported IP from its options string (LAN IP)
        #   3. Keep the existing stored IP if neither is available
        _is_docker_gateway = client_ip in _DOCKER_GATEWAY_IPS
        best_ip = (
            client_ip if not _is_docker_gateway
            else device_info.get('reported_ip') or (terminal.ip_address if terminal.ip_address not in _DOCKER_GATEWAY_IPS else None)
            or client_ip
        )
        if best_ip and terminal.ip_address != best_ip:
            logger.info(f"ADMS {sn}: IP updated {terminal.ip_address!r} → {best_ip!r}")
            terminal.ip_address = best_ip
        terminal.pushver       = pushver
        if terminal.state == STATE_OFFLINE:
            terminal.state = STATE_APPROVED  # reconnected
        if device_info.get('fw_version'):
            terminal.fw_ver = device_info['fw_version']
        for field in ('UserCount','FpCount','FaceCount','PalmCount','LogCount'):
            if field in device_info:
                col = field.lower().replace('count', '_count')
                if hasattr(terminal, col):
                    setattr(terminal, col, device_info[field])
        for src_key, attr in (('device_name','device_name'), ('oem_vendor','oem_vendor'),
                               ('platform','platform'), ('mac_address','mac_address')):
            if device_info.get(src_key):
                setattr(terminal, attr, device_info[src_key])
        db.commit()

        # Keep devices table in sync so the UI always shows current stats.
        # This runs on every heartbeat (not just state transitions) so user_count,
        # fp_count, firmware, IP, and MAC stay fresh without waiting for state change.
        try:
            db.execute(text("""
                UPDATE devices SET
                    user_count       = COALESCE(NULLIF(:uc, 0), user_count),
                    fp_count         = COALESCE(NULLIF(:fp, 0), fp_count),
                    face_count       = COALESCE(NULLIF(:fc, 0), face_count),
                    mac_address      = COALESCE(NULLIF(:mac, ''), mac_address),
                    firmware_version = COALESCE(NULLIF(:fw, ''), firmware_version),
                    ip_address       = CASE
                        WHEN :ip IS NOT NULL AND :ip NOT IN (
                            '192.168.65.1','172.17.0.1','172.18.0.1','172.19.0.1','172.20.0.1'
                        ) THEN :ip
                        ELSE ip_address
                    END
                WHERE serial_number = :sn
            """), {
                'sn':  sn,
                'uc':  terminal.user_count  or 0,
                'fp':  terminal.fp_count    or 0,
                'fc':  terminal.face_count  or 0,
                'mac': terminal.mac_address or '',
                'fw':  terminal.fw_ver      or '',
                'ip':  terminal.ip_address,
            })
            db.commit()
        except Exception as _sync_err:
            # Must rollback — on Postgres a failed statement aborts the transaction;
            # without this every later query on `db` in this request fails with
            # "current transaction is aborted" until something rolls it back.
            db.rollback()
            logger.warning("devices stat sync failed for %s: %s", sn, _sync_err)

        return terminal

    # New device
    if not settings.ZKTECO_AUTO_REGISTER_DEVICES:
        logger.info(f"New device {sn} rejected — auto-registration disabled")
        return None

    # Respect UI deletions — don't auto-re-add a reader the admin deleted.
    if is_device_suppressed(db, sn):
        logger.info(f"New device {sn} ignored — suppressed (deleted in UI)")
        return None

    # For new devices, prefer the device-reported IP over a Docker gateway address
    _is_docker_gw = client_ip in _DOCKER_GATEWAY_IPS
    stored_ip = (
        client_ip if not _is_docker_gw
        else device_info.get('reported_ip') or client_ip
    )
    new_terminal = IClockTerminal(
        sn            = sn,
        alias         = device_info.get('device_name') or f"Terminal-{sn}",
        ip_address    = stored_ip,
        state         = STATE_PENDING,   # requires admin approval
        pushver       = pushver,
        last_activity = datetime.now(timezone.utc),
        fw_ver        = device_info.get('fw_version', ''),
        device_name   = device_info.get('device_name'),
        platform      = device_info.get('platform'),
        mac_address   = device_info.get('mac_address'),
        oem_vendor    = device_info.get('oem_vendor'),
        user_count    = device_info.get('UserCount', 0),
        fp_count      = device_info.get('FpCount', 0),
        face_count    = device_info.get('FaceCount', 0),
        palm_count    = device_info.get('PalmCount', 0),
        log_count     = device_info.get('LogCount', 0),
        att_stamp     = 0,
        op_stamp      = 0,
        heartbeat_interval = 10,
    )
    db.add(new_terminal)
    db.commit()
    db.refresh(new_terminal)
    logger.info(f"Auto-registered new terminal {sn} from {client_ip} — PENDING approval")

    # Also create a matching row in `devices` so the device appears in the UI immediately.
    # Use a try/except so a failure here never blocks the ADMS protocol response.
    try:
        from ..models.device import Device, DeviceStatus
        existing_dev = db.query(Device).filter(Device.serial_number == sn).first()
        if not existing_dev:
            db.add(Device(
                name             = device_info.get('device_name') or f"Terminal-{sn}",
                serial_number    = sn,
                ip_address       = stored_ip if stored_ip not in _DOCKER_GATEWAY_IPS else None,
                port             = 4370,
                connection_mode  = "adms",
                status           = DeviceStatus.OFFLINE,  # heartbeat will set ONLINE
                auto_poll        = False,
                poll_interval_sec= 300,
            ))
            db.commit()
            logger.info(f"Auto-created devices row for new ADMS terminal {sn}")
    except Exception as dev_exc:
        logger.warning(f"Could not create devices row for {sn}: {dev_exc}")
        db.rollback()

    return new_terminal


def get_pending_commands(sn: str, db: Session) -> List[Dict[str, Any]]:
    result = db.execute(text("""
        SELECT id, cmd_content
        FROM iclock_devcmd
        WHERE sn = :sn AND status = 0
        ORDER BY cmd_commit_time ASC
        LIMIT 10
    """), {'sn': sn}).fetchall()
    return [{'id': r.id, 'cmd_content': r.cmd_content} for r in result]


def mark_commands_sent(cmd_ids: List[int], db: Session):
    if cmd_ids:
        db.execute(text("""
            UPDATE iclock_devcmd
            SET status = 1, cmd_trans_time = :now
            WHERE id = ANY(:ids)
        """), {'now': datetime.now(timezone.utc), 'ids': cmd_ids})
        db.commit()


def _emp_to_zk_pin(emp_code: str) -> int:
    """Extract a numeric ZKTeco PIN from an employee code.
    'EMP001' → 1, 'EMP0010' → 10, 'EMP034' → 34, '42' → 42.
    Falls back to absolute hash mod 65534 if no numeric portion found.
    """
    import re
    m = re.search(r'(\d+)$', emp_code or '')
    if m:
        n = int(m.group(1))
        return max(1, min(n, 65534))
    return (abs(hash(emp_code)) % 65534) + 1


def queue_command(sn: str, cmd: str, db: Session, created_by: Optional[int] = None) -> int:
    cmd = rewrite_command(db, cmd)   # PIN=<emp_code> -> reader PIN
    row = db.execute(text("""
        INSERT INTO iclock_devcmd (sn, cmd_content, status, cmd_commit_time)
        VALUES (:sn, :cmd, 0, :now)
        RETURNING id
    """), {'sn': sn, 'cmd': cmd, 'now': datetime.now(timezone.utc)}).fetchone()
    db.commit()
    return row.id


def _get_direct_device(sn: str, db: Session) -> Optional[Any]:
    """Return the devices row for sn if it has an IP and is in direct/both mode, else None."""
    return db.execute(text("""
        SELECT ip_address, port, connection_mode
        FROM devices
        WHERE serial_number = :sn AND ip_address IS NOT NULL
        LIMIT 1
    """), {'sn': sn}).fetchone()


async def _direct_sync_time(ip: str, port: int) -> Dict[str, Any]:
    """Call zkteco_direct.sync_time and return its result dict."""
    from ..services.zkteco.direct_connection import zkteco_direct
    return await zkteco_direct.sync_time(ip=ip, port=port or 4370)

# ── Zone tracking helpers ────────────────────────────────────────────────────

def _ensure_access_control_records(
    sn: str, terminal_alias: str, zones_zone_id: int, direction: str, db: Session
) -> Optional[int]:
    """
    Lazily create acc_door / acc_zone / acc_zone_door rows the first time a
    zone-access reader punches, so the acc_event table gets a proper door_id
    and the ACZones UI can count occupancy.

    Returns the acc_door.id for use in the acc_event INSERT, or None on error.
    direction: 'ENTRY' → acc_zone_door.direction=0  |  'EXIT' → direction=1
    """
    try:
        # 1. acc_door — one row per terminal
        door_row = db.execute(text(
            "SELECT id FROM acc_door WHERE terminal_sn = :sn LIMIT 1"
        ), {"sn": sn}).fetchone()

        if not door_row:
            # acc_door.terminal_sn FKs to iclock_terminal.sn. Controller-wired
            # readers use a synthetic sn (e.g. "AC3-D1-E") that has no terminal —
            # their occupancy is tracked via zone_personnel_tracking + current_zone_id,
            # not this legacy acc_door/ACZones view. Skip (no FK error, no rollback)
            # when there's no matching terminal to attach the door to.
            term = db.execute(text(
                "SELECT 1 FROM iclock_terminal WHERE sn = :sn LIMIT 1"
            ), {"sn": sn}).fetchone()
            if not term:
                return None
            door_name = f"{terminal_alias or sn} ({'Entry' if direction == 'ENTRY' else 'Exit'})"[:50]
            door_row = db.execute(text("""
                INSERT INTO acc_door (name, terminal_sn)
                VALUES (:name, :sn)
                RETURNING id
            """), {"name": door_name, "sn": sn}).fetchone()

        door_id = door_row.id

        # 2. acc_zone — mirror the zones table entry
        zone_info = db.execute(text(
            "SELECT name FROM zones WHERE id = :zid"
        ), {"zid": zones_zone_id}).fetchone()
        zone_name = (zone_info.name if zone_info else f"Zone-{zones_zone_id}")[:100]

        az_row = db.execute(text(
            "SELECT id FROM acc_zone WHERE zone_name = :n LIMIT 1"
        ), {"n": zone_name}).fetchone()

        if not az_row:
            az_row = db.execute(text("""
                INSERT INTO acc_zone (zone_name)
                VALUES (:n)
                ON CONFLICT (zone_name) DO UPDATE SET zone_name = EXCLUDED.zone_name
                RETURNING id
            """), {"n": zone_name}).fetchone()

        acc_zone_id = az_row.id

        # 3. acc_zone_door — link door to zone with the right direction
        dir_int = 0 if direction == 'ENTRY' else 1
        db.execute(text("""
            INSERT INTO acc_zone_door (zone_id, door_id, direction)
            VALUES (:zid, :did, :dir)
            ON CONFLICT (zone_id, door_id) DO UPDATE SET direction = :dir
        """), {"zid": acc_zone_id, "did": door_id, "dir": dir_int})

        return door_id

    except Exception as exc:
        logger.error("_ensure_access_control_records %s: %s", sn, exc)
        db.rollback()
        return None


def _handle_zone_access(
    emp_code: str, device_sn: str, punch_time: datetime,
    terminal: "IClockTerminal", direction: str, db: Session
) -> Dict[int, int]:
    """
    Route an access-control punch to zone tracking.
    direction = 'ENTRY' | 'EXIT'

    ENTRY:
      - Auto-exits the person from their previous zone (self-corrects missed exits)
      - Creates a CLOCK_IN record in zone_personnel_tracking
      - Sets personnel.current_zone_id

    EXIT:
      - Creates a CLOCK_OUT record in zone_personnel_tracking
      - Clears personnel.current_zone_id

    Returns Dict[zone_id → new_count] for all zones whose occupancy changed.
    """
    zone_id = terminal.zone_id if terminal else None
    if not zone_id:
        logger.warning(f"Access control reader {device_sn} has no zone_id — punch ignored")
        # If a muster is active, a punch at an unconfigured reader is a safety gap:
        # the person is physically present but will appear MISSING in the muster.
        active_muster = db.query(MusteringEvent).filter(MusteringEvent.status == 0).first()
        if active_muster:
            dedup_key = f"muster_punch_no_zone_{device_sn}_{emp_code}_{active_muster.id}"
            db.execute(text("""
                INSERT INTO sys_notifications
                    (dedup_key, notification_type, title, message, priority, expires_at)
                VALUES (:dk, :nt, :title, :msg, :pri, NOW() + INTERVAL '4 hours')
                ON CONFLICT (dedup_key) DO NOTHING
            """), {
                "dk": dedup_key,
                "nt": "muster_punch_dropped",
                "title": "Punch Dropped — Reader Not Assigned to Zone",
                "msg": (
                    f"Employee {emp_code} punched at reader {device_sn} during active "
                    f"muster event #{active_muster.id}, but this reader has no zone_id "
                    f"configured. The punch was NOT recorded in the muster — "
                    f"this person may appear as MISSING."
                ),
                "pri": "critical",
            })
            db.commit()
        else:
            # Outside a muster it is still a gap: nobody tapping here is being located.
            # One alert per reader per day so it is seen without flooding.
            db.execute(text("""
                INSERT INTO sys_notifications
                    (dedup_key, notification_type, title, message, priority, expires_at)
                VALUES (:dk, 'reader_no_zone', :title, :msg, 'high', NOW() + INTERVAL '1 day')
                ON CONFLICT (dedup_key) DO NOTHING
            """), {
                "dk": f"reader_no_zone_{device_sn}_{datetime.now(timezone.utc).date()}",
                "title": "Access Reader Not Assigned to a Zone",
                "msg": (f"Reader {device_sn} is set as an access-control reader but has no zone, "
                        f"so taps there do not update anyone's location. Assign it under "
                        f"Zones → ADMS Readers."),
            })
            db.commit()
        return {}

    # Ensure acc_door/acc_zone/acc_zone_door exist so the ACZones UI can count occupancy
    _ensure_access_control_records(
        device_sn, getattr(terminal, 'alias', None) or device_sn, zone_id, direction, db
    )

    # Look up the person
    person_row = db.execute(text("""
        SELECT id, current_zone_id FROM personnel
        WHERE emp_code = :ec OR badge_id = :ec
        LIMIT 1
    """), {"ec": emp_code}).fetchone()

    personnel_id    = person_row.id            if person_row else None
    current_zone_id = person_row.current_zone_id if person_row else None

    zone_row = db.execute(text(
        "SELECT name, parent_zone_id, COALESCE(is_site_boundary, FALSE) AS boundary "
        "FROM zones WHERE id = :z"), {"z": zone_id}).fetchone()
    zone_name  = zone_row.name if zone_row else None
    parent_id  = zone_row.parent_zone_id if zone_row and zone_row.parent_zone_id != zone_id else None
    boundary   = bool(zone_row.boundary) if zone_row else False

    zone_updates: Dict[int, int] = {}
    access_event = 'ACCESS_ENTRY' if direction == 'ENTRY' else 'ACCESS_EXIT'

    # A reader that was offline uploads its buffer when it reconnects. Those taps are
    # history: applying them as "now" would move the person back to where they were
    # hours ago. Record them, but leave live location and on-board status alone.
    latest = db.execute(text(
        "SELECT MAX(punch_time) FROM zone_personnel_tracking WHERE emp_code = :ec"
    ), {"ec": emp_code}).scalar()
    if latest is not None and punch_time < latest:
        db.execute(text("""
            INSERT INTO zone_personnel_tracking
                (zone_id, emp_code, device_sn, event_type, punch_time, previous_zone_id)
            VALUES (:zid, :ec, :sn, :et, :pt, NULL)
        """), {"zid": zone_id, "ec": emp_code, "sn": device_sn,
               "et": 'CLOCK_IN' if direction == 'ENTRY' else 'CLOCK_OUT', "pt": punch_time})
        db.execute(text("""
            INSERT INTO access_logs
                (personnel_id, event_type, access_granted, timestamp, zone_id, direction)
            VALUES (:pid, :ev, true, :pt, :zid, :dir)
        """), {"pid": personnel_id, "ev": access_event, "pt": punch_time,
               "zid": zone_id, "dir": direction})
        db.commit()
        logger.info("Late upload %s@%s %s (older than last move %s) — history only",
                    emp_code, device_sn, punch_time, latest)
        return {}

    def _track(zid, event_type, prev):
        db.execute(text("""
            INSERT INTO zone_personnel_tracking
                (zone_id, emp_code, device_sn, event_type, punch_time, previous_zone_id)
            VALUES (:zid, :ec, :sn, :et, :pt, :pzid)
        """), {"zid": zid, "ec": emp_code, "sn": device_sn, "et": event_type,
               "pt": punch_time, "pzid": prev})

    if direction == 'ENTRY':
        # Auto-exit from previous zone if different (self-corrects missed exits)
        if current_zone_id and current_zone_id != zone_id:
            _track(current_zone_id, 'CLOCK_OUT', current_zone_id)
            zone_updates[current_zone_id] = _recalc_zone_occupancy(current_zone_id, db)
        _track(zone_id, 'CLOCK_IN', current_zone_id)
        zone_updates[zone_id] = _recalc_zone_occupancy(zone_id, db)
        new_zone = zone_id
    else:
        # Walking out of zone X means they are not wherever else we last had them
        # (e.g. recorded in Site, now leaving through the Gate): close that stay too.
        if current_zone_id and current_zone_id != zone_id:
            _track(current_zone_id, 'CLOCK_OUT', current_zone_id)
            zone_updates[current_zone_id] = _recalc_zone_occupancy(current_zone_id, db)
        _track(zone_id, 'CLOCK_OUT', zone_id)
        zone_updates[zone_id] = _recalc_zone_occupancy(zone_id, db)
        # Leaving a room puts you in the area around it (Control Room -> Main Deck),
        # not "nowhere": the person stays on the map and the muster keeps a last
        # known zone. Only a zone with no parent leaves the person unplaced.
        new_zone = parent_id
        if parent_id:
            _track(parent_id, 'CLOCK_IN', zone_id)
            zone_updates[parent_id] = _recalc_zone_occupancy(parent_id, db)

    if personnel_id:
        db.execute(text(
            "UPDATE personnel SET current_zone_id = :zid WHERE id = :id"
        ), {"zid": new_zone, "id": personnel_id})

    db.execute(text("""
        INSERT INTO access_logs
            (personnel_id, event_type, access_granted, timestamp, zone_id, direction)
        VALUES (:pid, :ev, true, :pt, :zid, :dir)
    """), {"pid": personnel_id, "ev": access_event, "pt": punch_time,
           "zid": zone_id, "dir": direction})

    # On-board status: any entry means the person is on site; only an EXIT through a
    # SITE BOUNDARY zone (gate, helideck, jetty) means they have left. Moving between
    # rooms never takes anyone off board.
    if direction == 'ENTRY':
        onboard = True
    elif boundary and not parent_id:
        onboard = False
    else:
        onboard = None
    _mark_onboard(emp_code, onboard, db, location=zone_name if direction == 'ENTRY' else None)
    if onboard is False and personnel_id:
        db.execute(text("UPDATE personnel SET current_zone_id = NULL WHERE id = :id"),
                   {"id": personnel_id})

    db.commit()
    return zone_updates


def _recalc_zone_occupancy(zone_id: int, db: Session) -> int:
    """
    Recount current occupancy for a zone from zone_personnel_tracking.
    A person is 'in' the zone when their most recent event_type is CLOCK_IN.
    Returns the new count so callers can broadcast it.
    """
    row = db.execute(text("""
        SELECT COUNT(DISTINCT emp_code) AS cnt FROM (
            SELECT DISTINCT ON (emp_code) emp_code, event_type
            FROM zone_personnel_tracking
            WHERE zone_id = :zid
            ORDER BY emp_code, punch_time DESC
        ) last WHERE last.event_type = 'CLOCK_IN'
    """), {"zid": zone_id}).fetchone()
    cnt = int(row.cnt) if row else 0
    db.execute(text("""
        UPDATE zones SET current_occupancy = :cnt, current_personnel_count = :cnt,
            updated_at = NOW() WHERE id = :zid
    """), {"cnt": cnt, "zid": zone_id})
    # Push the new count to the POB dashboard live, from any context (ADMS push,
    # direct poll, live-capture, reset) — so it updates without a refresh.
    try:
        from ..core.websocket import schedule_zone_broadcast
        schedule_zone_broadcast(zone_id, cnt)
    except Exception:
        pass
    return cnt


def _punch_state_mode(db: Session) -> str:
    try:
        v = db.execute(text("SELECT rule_value FROM att_rules WHERE rule_key = 'punch_state_mode'")).scalar()
    except Exception:
        db.rollback()
        v = None
    return str(v or 'first_last').lower()


def _mark_onboard(emp_code: str, onboard, db: Session, location: "Optional[str]" = None) -> None:
    """
    Maintain personnel.is_onboard from an attendance/access punch so the POB
    dashboard, reports and analytics reflect who is actually on site.
      onboard = True  → checked in / entered  → on board
      onboard = False → checked out           → off board
      onboard = None  → leave unchanged (break punches, zone-to-zone exits, unknown state)
    """
    if onboard is None:
        # No status change, but it IS activity: keep last_seen current so the
        # inactivity auto-checkout never evicts someone moving between rooms.
        try:
            db.execute(text("UPDATE personnel SET last_seen = NOW() "
                            "WHERE (emp_code = :ec OR badge_id = :ec) AND is_active = TRUE"),
                       {"ec": emp_code})
            db.commit()
        except Exception as e:
            logger.warning("last_seen update failed for %s: %s", emp_code, e)
            db.rollback()
        return
    try:
        if onboard:
            db.execute(text("""
                UPDATE personnel SET
                    is_onboard = TRUE, is_pob = TRUE,
                    pob_since = COALESCE(pob_since, NOW()),
                    current_location = COALESCE(:loc, current_location),
                    last_seen = NOW(), updated_at = NOW()
                WHERE (emp_code = :ec OR badge_id = :ec) AND is_active = TRUE
            """), {"ec": emp_code, "loc": location})
        else:
            db.execute(text("""
                UPDATE personnel SET
                    is_onboard = FALSE, is_pob = FALSE, pob_since = NULL,
                    last_seen = NOW(), updated_at = NOW()
                WHERE (emp_code = :ec OR badge_id = :ec) AND is_active = TRUE
            """), {"ec": emp_code})
        db.commit()
        if not onboard:
            # Left the site while a muster is running → accounted for, not missing.
            try:
                code = db.execute(text("SELECT emp_code FROM personnel WHERE emp_code = :ec OR badge_id = :ec LIMIT 1"),
                                  {"ec": emp_code}).scalar() or emp_code
                if MusteringService(db).mark_left_site(code):
                    logger.info("Muster: %s tapped out at the gate — marked LEFT SITE", code)
            except Exception as me:
                logger.warning("Muster left-site update failed for %s: %s", emp_code, me)
                db.rollback()
    except Exception as e:
        logger.warning("onboard status update failed for %s: %s", emp_code, e)
        db.rollback()


# ── Core ADMS endpoint ────────────────────────────────────────────────────────

def _real_client_ip(request: Request) -> str:
    """
    Return the real device IP, respecting X-Forwarded-For / X-Real-IP headers
    set by nginx or other reverse proxies sitting in front of the server.
    Falls back to the direct TCP connection address when no proxy headers exist.
    """
    xff = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if xff:
        return xff
    xri = request.headers.get('X-Real-IP', '').strip()
    if xri:
        return xri
    return request.client.host if request.client else ''


async def _handle_cdata(request: Request, db: Session) -> PlainTextResponse:
    sn      = request.query_params.get('SN', '')
    options = request.query_params.get('options', '')
    pushver = request.query_params.get('pushver', '1.0')
    # ZKTeco signals the record type via the `table=` query param (ATTLOG, OPERLOG,
    # ATTPHOTO, …). Some firmware uses `tablename` / `Table`. BioTime relies on this.
    table   = (request.query_params.get('table')
               or request.query_params.get('tablename')
               or request.query_params.get('Table') or '')

    if not _valid_sn(sn):
        logger.warning(f"ADMS bad SN {sn!r} from {_real_client_ip(request)}")
        return PlainTextResponse(f"{ADMS_ERROR}Invalid SN")

    device_info = parse_device_options(options)
    client_ip   = _real_client_ip(request)

    terminal = upsert_terminal(sn, client_ip, device_info, pushver, db)
    if terminal is None:
        return PlainTextResponse(f"{ADMS_ERROR}Device not registered")

    # Rejected devices get an error so they stop trying
    if terminal.state == STATE_REJECTED:
        return PlainTextResponse(f"{ADMS_ERROR}Device rejected")

    # Validate comm_key if configured on this terminal.
    # ZKTeco devices send their comm password as the Key= query parameter.
    stored_key = getattr(terminal, "comm_key", None)
    if stored_key and stored_key not in ("0", "", None):
        device_key = request.query_params.get("Key", "0")
        if device_key != stored_key:
            logger.warning("ADMS %s: comm_key mismatch from %s", sn, client_ip)
            return PlainTextResponse(f"{ADMS_ERROR}Authentication failed")

    # Parse and route the POST body
    body_bytes = await request.body()
    body_str   = body_bytes.decode('utf-8', errors='replace') if body_bytes else ""

    if body_str.strip():
        parsed_records = parse_adms_body(body_str, table_hint=table)
        logger.info(f"ADMS {sn}: table={table or '-'} {len(parsed_records)} records in body")
        # If a non-empty POST parsed to nothing, the firmware is using a wire
        # dialect we don't recognise — log the raw head so we can add support.
        if not parsed_records:
            logger.warning(
                "ADMS %s: NON-EMPTY body parsed to 0 records (table=%r) — raw[:300]=%r",
                sn, table, body_str[:300])

        # Group by record type for batch processing
        by_type: Dict[str, List[Dict]] = {}
        for rtype, fields in parsed_records:
            by_type.setdefault(rtype, []).append(fields)

        # Only process attendance/operlog if device is approved
        if terminal.state == STATE_APPROVED:
            if 'ATTLOG' in by_type:
                saved, latest_ts, zone_updates = handle_attlog(by_type['ATTLOG'], sn, db)
                if latest_ts > (terminal.att_stamp or 0):
                    terminal.att_stamp = latest_ts
                    db.commit()
                # Broadcast live zone occupancy to all connected POB dashboards
                if zone_updates:
                    zone_names = {}
                    try:
                        rows = db.execute(text(
                            "SELECT id, name FROM zones WHERE id = ANY(:ids)"
                        ), {"ids": list(zone_updates.keys())}).fetchall()
                        zone_names = {r.id: r.name for r in rows}
                    except Exception as _zn_exc:
                        # Must rollback — a failed statement aborts the Postgres
                        # transaction; without this the OPERLOG commit below (and
                        # anything else on this session) would fail too.
                        db.rollback()
                        logger.warning("Zone name lookup failed for %s: %s", sn, _zn_exc)
                    for zid, cnt in zone_updates.items():
                        asyncio.create_task(
                            broadcast_zone_update(zid, cnt, zone_names.get(zid, ""))
                        )

            if 'OPERLOG' in by_type:
                _, latest_op = handle_operlog(by_type['OPERLOG'], sn, db)
                if latest_op > (terminal.op_stamp or 0):
                    terminal.op_stamp = latest_op
                    db.commit()

        # USERINFO, FINGERTMP, FACETMP processed regardless of approval state
        # so device-enrolled biometrics aren't lost while pending review
        if 'USERINFO' in by_type:
            handle_userinfo(by_type['USERINFO'], sn, db)

        if 'FINGERTMP' in by_type:
            handle_fingertmp(by_type['FINGERTMP'], sn, db)

        if 'FACETMP' in by_type:
            handle_facetmp(by_type['FACETMP'], sn, db)

        if 'BIODATA' in by_type:
            handle_biodata(by_type['BIODATA'], sn, db)

    # A data-bearing POST is an UPLOAD — the reader expects a bare "OK" to confirm
    # receipt and advance past those records. Returning the options block instead
    # makes the reader think the upload failed, so it resends the same punches
    # every cycle (~20-30s) forever. Options are delivered on the GET handshake and
    # commands via /iclock/getrequest, so acking uploads with OK breaks nothing.
    if request.method == "POST" and body_str.strip():
        return PlainTextResponse(ADMS_OK)

    # Build response: options block + any queued commands
    options_block = build_options_block(terminal, pushver)

    _recover_stale_commands(sn, db)
    pending = get_pending_commands(sn, db)
    if pending:
        cmd_ids   = [c['id'] for c in pending]
        cmd_lines = [f"C:{c['id']}:{c['cmd_content']}" for c in pending]
        mark_commands_sent(cmd_ids, db)
        logger.info(f"ADMS {sn}: delivered {len(cmd_lines)} commands")
        return PlainTextResponse(options_block + "\n" + "\n".join(cmd_lines))

    return PlainTextResponse(options_block)


@router.get("/iclock/cdata", response_class=PlainTextResponse)
async def adms_cdata_get(request: Request, db: Session = Depends(get_db)):
    return await _handle_cdata(request, db)


@router.post("/iclock/cdata", response_class=PlainTextResponse)
async def adms_cdata_post(request: Request, db: Session = Depends(get_db)):
    return await _handle_cdata(request, db)


def _recover_stale_commands(sn: str, db: Session) -> None:
    """
    Reset commands stuck at status=1 (sent but never acked) after 3 minutes.
    REBOOT/SHUTDOWN/SYNCTIME will never ack because the device restarts — mark them done.
    All other commands reset to status=0 so they're re-delivered on the next poll.
    """
    # Commands that will never send an ack: REBOOT (restarts device), DATE TIME (some firmware
    # executes silently), SYNCTIME label. Mark them completed. Everything else reset to pending.
    db.execute(text("""
        UPDATE iclock_devcmd
        SET status = CASE
            WHEN UPPER(TRIM(cmd_content)) ~ '^(REBOOT|SHUTDOWN|SYNCTIME|DATE TIME|SET OPTIONS DATETIME=)' THEN 2
            ELSE 0
        END,
        cmd_return = CASE
            WHEN UPPER(TRIM(cmd_content)) ~ '^(REBOOT|SHUTDOWN|SYNCTIME|DATE TIME|SET OPTIONS DATETIME=)'
            THEN 'Auto-completed (no ack expected)'
            ELSE NULL
        END,
        cmd_return_time = CASE
            WHEN UPPER(TRIM(cmd_content)) ~ '^(REBOOT|SHUTDOWN|SYNCTIME|DATE TIME|SET OPTIONS DATETIME=)'
            THEN NOW()
            ELSE NULL
        END
        WHERE sn = :sn
          AND status = 1
          AND cmd_trans_time < NOW() - INTERVAL '3 minutes'
    """), {'sn': sn})
    # Also cancel commands that ADMS devices never process (ZKLib-only semantics)
    db.execute(text("""
        UPDATE iclock_devcmd
        SET status = 2,
            cmd_return = 'Auto-completed (not an ADMS command)',
            cmd_return_time = NOW()
        WHERE sn = :sn
          AND status IN (0, 1)
          AND UPPER(TRIM(cmd_content)) IN (
              'PULL ATTENDANCE', 'GET LOG', 'GETALLLOG', 'PULL LOG',
              'GET USERINFO', 'GETUSERINFO', 'GET USERS',
              'CLEAR LOG', 'CLEARATTLOG', 'CLEAR ATTENDANCE'
          )
          AND EXISTS (
              SELECT 1 FROM devices
              WHERE serial_number = :sn AND connection_mode = 'adms'
          )
    """), {'sn': sn})
    db.commit()


def _check_comm_key(request: Request, sn: str, db: Session) -> bool:
    """Return False (reject) if terminal has a comm_key and the request Key= doesn't match."""
    try:
        row = db.execute(text(
            "SELECT comm_key FROM iclock_terminal WHERE sn = :sn"
        ), {"sn": sn}).fetchone()
        if row and row[0] and row[0] not in ("0", ""):
            return request.query_params.get("Key", "0") == row[0]
    except Exception as _ck_exc:
        # Rollback so this doesn't poison the session for the rest of the
        # request — this check runs before upsert_terminal/handle_attlog,
        # which would otherwise all silently fail with "transaction aborted".
        db.rollback()
        logger.warning("comm_key check failed for %s: %s", sn, _ck_exc)
    return True  # no key configured — allow


@router.get("/iclock/getrequest", response_class=PlainTextResponse)
async def adms_getrequest(request: Request, db: Session = Depends(get_db)):
    sn = request.query_params.get('SN', '')
    if not _valid_sn(sn):
        return PlainTextResponse(f"{ADMS_ERROR}Invalid SN")

    if not _check_comm_key(request, sn, db):
        logger.warning("ADMS getrequest %s: comm_key mismatch", sn)
        return PlainTextResponse(f"{ADMS_ERROR}Authentication failed")

    # Update last_activity
    db.execute(text(
        "UPDATE iclock_terminal SET last_activity = :now WHERE sn = :sn"
    ), {'now': datetime.now(timezone.utc), 'sn': sn})
    db.commit()

    # Recover commands stuck at "sent" for > 3 minutes (device rebooted / never acked)
    _recover_stale_commands(sn, db)

    pending = get_pending_commands(sn, db)
    if not pending:
        return PlainTextResponse(ADMS_NONE)

    # The F18 (fw 6.80) silently drops a whole batch that contains a clock command —
    # no ack for any line — which stalled every enrolment queued behind it. So a clock
    # command always travels ALONE, after the real work, and carries the time at the
    # moment of delivery (a value encoded when it was queued could be hours stale and
    # would wind the reader's clock back).
    work = [c for c in pending if not _is_clock_cmd(c['cmd_content'])]
    if work:
        pending = work
    else:
        latest = pending[-1]
        pending = [{'id': latest['id'],
                    'cmd_content': f"{_CLOCK_CMD_PREFIX}{_encode_adms_datetime(datetime.now())}"}]
    cmd_ids   = [c['id'] for c in pending]
    cmd_lines = [f"C:{c['id']}:{c['cmd_content']}" for c in pending]
    mark_commands_sent(cmd_ids, db)
    logger.info(f"ADMS getrequest {sn}: delivered {len(cmd_lines)} commands")
    return PlainTextResponse("\n".join(cmd_lines))


@router.post("/iclock/devicecmd", response_class=PlainTextResponse)
async def adms_devicecmd(request: Request, db: Session = Depends(get_db)):
    sn = request.query_params.get('SN', '')
    if not _valid_sn(sn):
        return PlainTextResponse(f"{ADMS_ERROR}Invalid SN")

    body     = await request.body()
    data_str = body.decode('utf-8', errors='replace') if body else ""
    if not data_str.strip():
        return PlainTextResponse(ADMS_OK)

    from urllib.parse import parse_qs
    raw = data_str.strip()
    logger.info(f"devicecmd body from {sn}: {raw[:500]!r}")

    # ZKTeco devices batch multiple command acks in one POST, one per line.
    # Each line is URL-encoded: ID=123&Return=0&CMD=REBOOT
    # Some older firmware sends newline-separated key=value instead.
    # We handle both by splitting on \n and URL-parsing each non-empty line.
    now = datetime.now(timezone.utc)
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue

        if '&' in line:
            parsed = parse_qs(line, keep_blank_values=True)
            fields: Dict[str, str] = {k: v[0] for k, v in parsed.items()}
        else:
            fields = _parse_kv_lines([line])

        cmd_id_str  = fields.get('ID')
        return_code = fields.get('Return', '0')
        cmd_name    = fields.get('CMD', '')

        if not cmd_id_str:
            continue
        try:
            cmd_id = int(cmd_id_str)
            success = return_code.strip() in ('0', 'OK', 'ok', 'Success', 'success')
            final_status = 2 if success else 3
            db.execute(text("""
                UPDATE iclock_devcmd
                SET status = :status, cmd_return_time = :now,
                    cmd_return = :ret
                WHERE id = :id AND status != 2
            """), {
                'status': final_status,
                'now':    now,
                'ret':    f"Return={return_code}&CMD={cmd_name}",
                'id':     cmd_id,
            })
            logger.info(f"devicecmd {sn} cmd={cmd_id} return={return_code!r} → status={final_status}")
        except ValueError:
            logger.warning(f"devicecmd non-numeric ID from {sn}: {cmd_id_str!r}")
        except Exception as e:
            logger.error(f"devicecmd update error for {sn} cmd={cmd_id_str}: {e}")

    db.commit()
    return PlainTextResponse(ADMS_OK)

# ── Admin API endpoints ────────────────────────────────────────────────────────

@router.get("/iclock/test")
async def adms_test():
    return {
        "protocol": "ADMS",
        "version":  "2.3",
        "endpoints": {
            "cdata":     "/iclock/cdata",
            "getrequest":"/iclock/getrequest",
            "devicecmd": "/iclock/devicecmd",
        },
        "features": [
            "batch_record_parsing", "record_type_routing", "stamp_watermark",
            "device_approval_workflow", "operlog_handler", "userinfo_handler",
            "biometric_template_handler", "command_builders",
        ],
        "status": "operational",
    }


@router.get("/iclock/pending-devices")
async def get_pending_devices(db: Session = Depends(get_db)):
    """Return all devices awaiting admin approval (state=0)."""
    rows = db.query(IClockTerminal).filter(
        IClockTerminal.state == STATE_PENDING
    ).order_by(IClockTerminal.created_at.desc()).all()
    return [
        {
            "id":           r.id,
            "sn":           r.sn,
            "alias":        r.alias,
            "ip_address":   r.ip_address,
            "fw_ver":       r.fw_ver,
            "pushver":      r.pushver,
            "user_count":   r.user_count,
            "fp_count":     r.fp_count,
            "face_count":   r.face_count,
            "first_seen":   r.created_at.isoformat() if r.created_at else None,
            "last_activity":r.last_activity.isoformat() if r.last_activity else None,
        }
        for r in rows
    ]


@router.post("/iclock/approve-device")
async def approve_device(body: ApproveRequest, db: Session = Depends(get_db)):
    """Approve or reject a pending device. On approval, auto-queues full user sync."""
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == body.sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")
    if body.action == "approve":
        terminal.state = STATE_APPROVED
        db.commit()
        msg = await _sync_users_to_terminal(terminal, db)
    elif body.action == "reject":
        terminal.state = STATE_REJECTED
        db.commit()
        msg = f"Device {body.sn} rejected"
    else:
        raise HTTPException(400, "action must be 'approve' or 'reject'")
    logger.info(msg)
    return {"detail": msg, "sn": body.sn, "state": terminal.state}


async def _sync_users_to_terminal(terminal: IClockTerminal, db) -> str:
    """
    Push all employees to a terminal.  Strategy depends on ADMS PushVer:
      - PushVer 2.x: queue DATA UPDATE USERINFO commands (device processes on next poll)
      - PushVer 1.x or unknown: use ZKLib direct TCP if IP available; ADMS otherwise
    """
    employees = db.query(PersonnelEmployee).all()
    if not employees:
        return f"Device {terminal.sn} approved — no employees to sync"

    pushver = (terminal.pushver or "").strip()
    use_adms = pushver.startswith("2")

    if use_adms:
        queued = 0
        for emp in employees:
            name = f"{emp.first_name or ''} {emp.last_name or ''}".strip()
            card = getattr(emp, 'card_no', '') or ''
            cmd = (
                f"DATA UPDATE USERINFO\tPin={emp.emp_code}\t"
                f"Name={name}\tCard={card}\tPrivilege=0\t"
                f"Password=\tGroup=1\tTimeZone=0\tVerify=0"
            )
            queue_command(terminal.sn, cmd, db)
            queued += 1
        return f"Device {terminal.sn} approved — {queued} user sync commands queued (ADMS)"

    # PushVer 1.x: DATA UPDATE USERINFO not supported; use ZKLib if IP available
    ip = terminal.ip_address
    if not ip:
        return (
            f"Device {terminal.sn} approved — user sync skipped "
            f"(PushVer {pushver or '1.0'} does not support remote user push and no IP stored)"
        )

    try:
        from ..services.zkteco.direct_connection import zkteco_direct
        # Get existing users to avoid UID conflicts
        # Build emp_code→uid map from device (use emp_code as user_id for proper attendance matching)
        existing = await zkteco_direct.get_users(ip=ip, port=4370)
        code_to_uid: dict = {}
        max_uid = 0
        if existing.get("success"):
            for u in existing.get("users", []):
                uid_val = u.get("uid", 0)
                uid_str = str(u.get("user_id", ""))
                if uid_str:
                    code_to_uid[uid_str] = uid_val
                if uid_val > max_uid:
                    max_uid = uid_val

        synced = 0
        errors = []
        for emp in employees:
            name    = f"{emp.first_name or ''} {emp.last_name or ''}".strip() or emp.emp_code
            uid     = code_to_uid.get(emp.emp_code)
            if uid is None:
                max_uid += 1
                uid = max_uid
            card_str = getattr(emp, 'card_no', '') or ''
            card_int = int(card_str) if card_str.isdigit() else 0
            result  = await zkteco_direct.set_user(
                ip=ip, uid=uid, name=name[:24],
                user_id=emp.emp_code, card=card_int, port=4370
            )
            if result.get("success"):
                synced += 1
            else:
                errors.append(f"{emp.emp_code}: {result.get('error')}")

        parts = [f"Device {terminal.sn} approved — {synced}/{len(employees)} employees pushed via ZKLib"]
        if errors:
            parts.append(f"errors: {'; '.join(errors[:3])}")
        return " — ".join(parts)

    except Exception as e:
        logger.error(f"ZKLib user sync failed for {terminal.sn}: {e}")
        return (
            f"Device {terminal.sn} approved — ZKLib user sync failed ({e}). "
            "Users can be synced manually via the Sync button."
        )


@router.get("/iclock/operlog")
async def get_operlog(
    sn: Optional[str] = None,
    event_type: Optional[int] = None,
    from_dt: Optional[str] = None,
    to_dt: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Return OPERLOG events with optional filters."""
    q = db.query(IClockOperLog)
    if sn:
        q = q.filter(IClockOperLog.terminal_sn == sn)
    if event_type is not None:
        q = q.filter(IClockOperLog.oper_event == event_type)
    if from_dt:
        try:
            q = q.filter(IClockOperLog.event_time >= datetime.fromisoformat(from_dt))
        except ValueError:
            pass
    if to_dt:
        try:
            q = q.filter(IClockOperLog.event_time <= datetime.fromisoformat(to_dt))
        except ValueError:
            pass
    total = q.count()
    rows  = q.order_by(IClockOperLog.event_time.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "results": [
            {
                "id":           r.id,
                "terminal_sn":  r.terminal_sn,
                "oper_event":   r.oper_event,
                "event_label":  OPER_EVENT_LABELS.get(r.oper_event, "Unknown"),
                "event_time":   r.event_time.isoformat() if r.event_time else None,
                "admin_id":     r.admin_id,
                "door_id":      r.door_id,
                "object_name":  r.object_name,
                "param1":       r.param1,
                "param2":       r.param2,
            }
            for r in rows
        ],
    }


@router.get("/iclock/bio-templates")
async def get_bio_templates(
    emp_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return stored biometric templates, optionally filtered by employee."""
    q = db.query(IClockBioTemplate)
    if emp_code:
        q = q.filter(IClockBioTemplate.emp_code == emp_code)
    rows = q.order_by(IClockBioTemplate.emp_code, IClockBioTemplate.finger_id).all()
    return [
        {
            "id":            r.id,
            "emp_code":      r.emp_code,
            "finger_id":     r.finger_id,
            "type":          "face" if r.finger_id == -1 else "fingerprint",
            "template_size": r.template_size,
            "valid":         r.valid,
            "source_sn":     r.source_sn,
            "updated_at":    r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]

# ── Command builder endpoints ─────────────────────────────────────────────────

@router.post("/iclock/cmd/push-users")
async def cmd_push_users(body: PushUsersRequest, db: Session = Depends(get_db)):
    """
    Push employee records to a device.
    PushVer 2.x: queues ADMS DATA UPDATE USERINFO commands.
    PushVer 1.x: uses ZKLib direct TCP (port 4370) if device IP is available.
    """
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == body.sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")
    _block_controller(body.sn, db)

    pushver = (terminal.pushver or "").strip()

    # An ADMS-mode reader is reachable ONLY via the command queue — the server can't
    # open a direct ZKLib TCP connection to a NAT'd/remote reader (it would fail with
    # "Broken pipe"). So always use the ADMS command path for adms readers, even if
    # the reported PushVer is missing/1.x.
    use_adms = pushver.startswith("2") or (terminal.connection_mode or "").lower() == "adms"

    if use_adms:
        # ADMS DATA UPDATE USERINFO — the same rules as the nightly T&A sync:
        # active staff with an Attendance ID only (never leavers), and never a blank
        # Passwd= / Card= that would wipe what was set at the terminal.
        from ..services.panel_sync import active_panel_users
        from ..services.ta_sync import _userinfo
        users, skipped = active_panel_users(db, body.emp_codes or None)
        for u in users:
            queue_command(body.sn, _userinfo(u), db)
            db.execute(text("""
                INSERT INTO ta_terminal_user (sn, pin, emp_code, card_no, state, updated_at)
                VALUES (:s, :p, :e, :c, 'queued', NOW())
                ON CONFLICT (sn, pin) DO UPDATE SET emp_code = EXCLUDED.emp_code, card_no = EXCLUDED.card_no,
                    state = 'queued', updated_at = NOW()"""), {"s": body.sn, "p": u["pin"], "e": u["emp_code"], "c": u["card_no"]})
        db.commit()
        note = f" · {skipped} staff without an Attendance ID skipped" if skipped else ""
        return {"detail": f"Queued {len(users)} USERINFO commands to {body.sn}{note}"}

    # PushVer 1.x — use ZKLib direct TCP
    ip = terminal.ip_address
    if not ip:
        return {
            "detail": (
                f"User sync not available: device {body.sn} uses PushVer {pushver or '1.0'} "
                "which does not support remote user push, and no IP address is stored. "
                "Enroll users directly on the device."
            )
        }

    try:
        from ..services.zkteco.direct_connection import zkteco_direct
        q = db.query(PersonnelEmployee)
        if body.emp_codes:
            q = q.filter(PersonnelEmployee.emp_code.in_(body.emp_codes))
        employees = q.all()

        # Build emp_code→uid map from device
        existing = await zkteco_direct.get_users(ip=ip, port=4370)
        code_to_uid: dict = {}
        max_uid = 0
        if existing.get("success"):
            for u in existing.get("users", []):
                uid_val = u.get("uid", 0)
                uid_str = str(u.get("user_id", ""))
                if uid_str:
                    code_to_uid[uid_str] = uid_val
                if uid_val > max_uid:
                    max_uid = uid_val

        synced = 0
        errors = []
        for emp in employees:
            name    = f"{emp.first_name or ''} {emp.last_name or ''}".strip() or emp.emp_code
            uid     = code_to_uid.get(emp.emp_code)
            if uid is None:
                max_uid += 1
                uid = max_uid
            card_str = getattr(emp, 'card_no', '') or ''
            card_int = int(card_str) if card_str.isdigit() else 0
            result  = await zkteco_direct.set_user(
                ip=ip, uid=uid, name=name[:24],
                user_id=emp.emp_code, card=card_int, port=4370
            )
            if result.get("success"):
                synced += 1
            else:
                errors.append(f"{emp.emp_code}: {result.get('error')}")

        msg = f"Pushed {synced}/{len(employees)} employees to {body.sn} via ZKLib"
        if errors:
            msg += f" — errors: {'; '.join(errors[:3])}"
        return {"detail": msg, "synced": synced, "errors": errors}

    except Exception as e:
        logger.error(f"ZKLib push-users failed for {body.sn}: {e}")
        return {"detail": f"ZKLib user sync failed: {e}", "synced": 0, "errors": [str(e)]}


@router.post("/iclock/cmd/push-templates")
async def cmd_push_templates(body: PushTemplatesRequest, db: Session = Depends(get_db)):
    """
    Queue DATA UPDATE FINGERTMP / FACETMP commands to push biometric templates to a device.
    """
    _block_controller(body.sn, db)
    _block_direct_only(body.sn, db)
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == body.sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")

    q = db.query(IClockBioTemplate).filter(IClockBioTemplate.valid == True)
    if body.emp_codes:
        q = q.filter(IClockBioTemplate.emp_code.in_(body.emp_codes))
    templates = q.all()

    queued = 0
    for tpl in templates:
        if tpl.finger_id == -1:
            cmd = (
                f"DATA UPDATE FACETMP\tPin={tpl.emp_code}\t"
                f"Size={tpl.template_size or 0}\tValid={1 if tpl.valid else 0}\t"
                f"TmpData={tpl.template_data or ''}"
            )
        else:
            cmd = (
                f"DATA UPDATE FINGERTMP\tPin={tpl.emp_code}\t"
                f"FingerID={tpl.finger_id}\t"
                f"Size={tpl.template_size or 0}\tValid={1 if tpl.valid else 0}\t"
                f"TmpData={tpl.template_data or ''}"
            )
        queue_command(body.sn, cmd, db)
        queued += 1

    return {"detail": f"Queued {queued} template commands to {body.sn}"}


@router.post("/iclock/cmd/push-timezones")
async def cmd_push_timezones(body: PushTimezonesRequest, db: Session = Depends(get_db)):
    """
    Queue SET TIMEZONE commands to push shift time rules to a device.
    ZKTeco TIMEZONE format:  ID\tSunTime1\tMonTime1\t...\tSatTime1
    Each time slot is encoded as HHMM (0000=disabled).
    """
    _block_controller(body.sn, db)
    _block_direct_only(body.sn, db)
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == body.sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")

    q = db.query(AttTimetable)
    if body.shift_ids:
        q = q.filter(AttTimetable.id.in_(body.shift_ids))
    timetables = q.limit(50).all()  # ZKTeco devices support up to 50 timezones

    queued = 0
    for idx, tt in enumerate(timetables, start=1):
        # Format: HHMM from time objects, 0000 = disabled
        def fmt(t):
            return f"{t.hour:02d}{t.minute:02d}" if t else "0000"
        start = fmt(tt.start_time)
        end   = fmt(tt.end_time)
        # Apply same time to all 7 days (Mon-Sun) as default
        time_slots = "\t".join([f"{start}{end}"] * 7)
        cmd = f"SET TIMEZONE\t{idx}\t{time_slots}"
        queue_command(body.sn, cmd, db)
        queued += 1

    return {"detail": f"Queued {queued} TIMEZONE commands to {body.sn}"}


@router.post("/iclock/cmd/push-access-levels")
async def cmd_push_access_levels(body: PushAccessLevelsRequest, db: Session = Depends(get_db)):
    """
    Queue DATA UPDATE USERATT commands to push access level assignments to a device.
    USERATT format: UserID=001\tTimeZoneID=1\tDoorID=1\tBooleanValue=1
    """
    _block_controller(body.sn, db)
    _block_direct_only(body.sn, db)
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == body.sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")

    q = db.query(AccUserAuthorize)
    if body.level_ids:
        q = q.filter(AccUserAuthorize.level_id.in_(body.level_ids))
    assignments = q.all()

    queued = 0
    for assn in assignments:
        emp_code = assn.emp_code
        level_id = assn.level_id
        cmd = (
            f"DATA UPDATE USERATT\tPin={emp_code}\t"
            f"TimeZoneID={level_id}\tDoorID=1\tBooleanValue=1"
        )
        queue_command(body.sn, cmd, db)
        queued += 1

    return {"detail": f"Queued {queued} USERATT commands to {body.sn}"}


@router.post("/iclock/cmd/query-attlog")
async def cmd_query_attlog(body: CommandRequest, db: Session = Depends(get_db)):
    """
    Queue a QUERY ATTLOG command so the device re-uploads its full attendance buffer.
    Use this after a data gap (network dropout, device replacement, etc.).
    stamp=0 means 'send everything'.
    """
    _block_controller(body.sn, db)
    _block_direct_only(body.sn, db)
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == body.sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")

    # Reset att_stamp so the options block will send Stamp=0 on next heartbeat,
    # which is the signal for the device to re-upload from the beginning
    terminal.att_stamp = 0
    db.commit()

    cmd_id = queue_command(body.sn, "QUERY ATTLOG", db)
    return {"detail": f"QUERY ATTLOG queued (id={cmd_id}) — att_stamp reset to 0", "cmd_id": cmd_id}


class _SNRequest(BaseModel):
    sn: str

@router.post("/iclock/cmd/pull-users")
async def cmd_pull_users(body: _SNRequest, db: Session = Depends(get_db)):
    """
    Pull all users stored on the device into personnel_employee.

    PushVer 2.x: resets UserStamp=0; device uploads on next heartbeat (~30s).
    PushVer 1.x: fetches directly via ZKLib and upserts employees immediately.

    New users (not in DB) are created as pending employees.
    Existing employees get their card_no updated if the device has one.
    """
    _block_controller(body.sn, db)
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == body.sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")

    pushver = (terminal.pushver or "").strip()

    if pushver.startswith("2"):
        # PushVer 2.x: use ADMS UserStamp mechanism
        terminal.user_stamp = 0
        db.commit()
        return {
            "detail": (
                f"UserStamp reset to 0 for {body.sn} — "
                "device will upload its full user list on next heartbeat (~30s)"
            )
        }

    # PushVer 1.x: pull directly via ZKLib
    ip = terminal.ip_address
    if not ip:
        return {
            "detail": (
                f"Cannot pull users from {body.sn}: PushVer {pushver or '1.0'} "
                "does not support remote user pull via ADMS and no IP is stored."
            )
        }

    try:
        from ..services.zkteco.direct_connection import zkteco_direct
        result = await zkteco_direct.get_users(ip=ip, port=4370)
        if not result.get("success"):
            raise HTTPException(502, f"ZKLib get_users failed: {result.get('error')}")

        raw_users = result.get("users", [])

        # Deduplicate by user_id — device can occasionally report the same user twice,
        # which causes a UniqueViolation when both get staged in the same session.
        seen_ids: set = set()
        device_users = []
        for u in raw_users:
            uid = str(u.get("user_id", "")).strip()
            if uid and uid.isprintable() and uid not in seen_ids:
                seen_ids.add(uid)
                device_users.append(u)

        created = 0
        updated = 0

        for u in device_users:
            raw_id = str(u.get("user_id", "")).strip()
            name   = (u.get("name") or "").strip()
            card   = u.get("card", 0)

            emp = db.query(Personnel).filter(
                Personnel.emp_code == raw_id
            ).first()

            if emp:
                # Only fill in blanks — never overwrite existing data
                if name and not emp.first_name:
                    parts = name.split()
                    emp.first_name = parts[0]
                    emp.last_name  = " ".join(parts[1:]) if len(parts) > 1 else (emp.last_name or "")
                if card and not emp.card_number:
                    emp.card_number = int(card)
                updated += 1
            else:
                parts      = name.split() if name else [raw_id]
                first_name = parts[0]
                last_name  = " ".join(parts[1:]) if len(parts) > 1 else ""
                new_emp = Personnel(
                    emp_code    = raw_id,
                    first_name  = first_name,
                    last_name   = last_name,
                    card_number = int(card) if card else None,
                    status      = PersonnelStatus.INACTIVE,
                )
                db.add(new_emp)
                created += 1

        db.commit()
        skipped = len(raw_users) - len(device_users)
        summary = (
            f"Pulled {len(raw_users)} users from {body.sn} via ZKLib — "
            f"{created} new employees created, {updated} existing updated, "
            f"{skipped} skipped (duplicate / blank ids)"
        )
        now = datetime.utcnow()
        db.execute(text("""
            INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, cmd_trans_time, cmd_return_time, status)
            VALUES (:sn, :cmd, :now, :now, :now, 2)
        """), {"sn": body.sn, "cmd": f"PULL USERS ({created} created, {updated} updated, {skipped} skipped)", "now": now})
        db.commit()
        return {
            "detail": summary,
            "total": len(raw_users),
            "created": created,
            "updated": updated,
            "skipped": skipped,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"ZKLib pull-users failed for {body.sn}: {e}")
        raise HTTPException(500, f"ZKLib pull-users failed: {e}")


@router.patch("/iclock/terminals/{sn}/heartbeat-interval")
async def set_heartbeat_interval(
    sn: str, interval: int, db: Session = Depends(get_db)
):
    """Update per-device heartbeat interval (seconds). Returned as Delay= in options block."""
    if interval < 10 or interval > 3600:
        raise HTTPException(400, "interval must be 10–3600 seconds")
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")
    terminal.heartbeat_interval = interval
    db.commit()
    return {"sn": sn, "heartbeat_interval": interval}


# ── Time synchronisation endpoints ───────────────────────────────────────────

class TimeSyncRequest(BaseModel):
    sn: str

@router.post("/iclock/cmd/sync-time")
async def cmd_sync_time(body: TimeSyncRequest, db: Session = Depends(get_db)):
    """
    Sync a single device clock to server time.

    For direct-IP devices (connection_mode = 'direct'/'both'): connects via
    ZKLib TCP and sets the clock immediately.
    For ADMS push devices: queues a DATE TIME command; the device applies it
    on its next /iclock/getrequest poll.
    """
    _block_controller(body.sn, db)
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == body.sn).first()
    if not terminal:
        raise HTTPException(404, "Device not found")
    if terminal.state != STATE_APPROVED:
        raise HTTPException(400, "Device is not approved — sync not allowed")

    correct_time = datetime.now()
    correct_time_str = correct_time.strftime('%Y-%m-%d %H:%M:%S')

    # Direct (ZKLib TCP) readers: set the clock immediately over TCP.
    dev = _get_direct_device(body.sn, db)
    if dev and (dev.connection_mode or '').lower() in ('direct', 'both'):
        direct_err = None
        try:
            result = await _direct_sync_time(dev.ip_address, dev.port)
            if result.get('success'):
                logger.info(f"Direct time sync OK for {body.sn}: device reports {result.get('device_reports')}")
                return {
                    "success": True,
                    "sn": body.sn,
                    "server_time": correct_time_str,
                    "device_reports": result.get('device_reports'),
                    "method": "direct",
                    "message": "Clock synchronized via direct ZKLib connection",
                }
            direct_err = result.get('error')
        except Exception as exc:
            direct_err = str(exc)

        # Direct attempt failed. Honour strict plane separation: a DIRECT-ONLY reader
        # never polls /iclock/getrequest, so we must NOT fall back to queuing an ADMS
        # command (it would black-hole). Report the failure instead — the reader is
        # most likely offline. ('both' readers DO poll, so the ADMS fallback below is
        # still valid for them.)
        if _is_direct_only(body.sn, db):
            logger.warning(f"Direct time sync failed for {body.sn}: {direct_err} — direct-only reader, NOT queuing ADMS")
            raise HTTPException(status_code=502, detail=(
                f"Direct (ZKLib) clock sync failed: {direct_err or 'reader unreachable'}. "
                "This reader is Direct-only and does not poll for ADMS commands, so nothing "
                "was queued. Check that the reader is online and reachable on the LAN."))
        logger.warning(f"Direct sync failed for {body.sn}: {direct_err} — 'both' mode, falling back to ADMS queue")

    # ADMS command queue path (adms readers, or 'both' readers whose direct attempt
    # failed). Push-mode readers set their clock via SET OPTIONS DateTime=<encoded>.
    # Final plane check: a direct-only reader can reach here when its mode lives only
    # in iclock_terminal (so _get_direct_device, which reads `devices`, returned None
    # and the direct attempt above was skipped). Never queue for it — it won't poll.
    if _is_direct_only(body.sn, db):
        raise HTTPException(status_code=502, detail=(
            "This reader is Direct-only and does not poll for ADMS commands, so nothing "
            "was queued. Check that it is online/reachable on the LAN, or set its "
            "Connection Mode to 'adms'/'both'."))
    cmd_id = queue_clock_sync(body.sn, db)   # supersedes any older clock command
    logger.info(f"ADMS time sync queued for {body.sn}: {correct_time_str} (cmd_id={cmd_id})")
    return {
        "success":     True,
        "sn":          body.sn,
        "server_time": correct_time_str,
        "cmd_id":      cmd_id,
        "method":      "adms",
        "message":     "SET OPTIONS DateTime queued — device will sync on next heartbeat poll",
    }


@router.post("/iclock/cmd/sync-time-all")
async def cmd_sync_time_all(db: Session = Depends(get_db)):
    """
    Sync ALL approved readers to server time.

    Direct-IP devices (connection_mode 'direct'/'both') are synced immediately
    via ZKLib TCP.  ADMS push devices receive a `SET OPTIONS DateTime` command on
    their next heartbeat poll.  Direct sync falls back to ADMS queue on failure.
    """
    terminals = db.query(IClockTerminal).filter(
        IClockTerminal.state == STATE_APPROVED,
        # InBio/C3 controllers don't take ADMS/ZKLib time-sync — skip them so bulk
        # ops never queue junk or raise errors for panels with no driver yet.
        func.coalesce(IClockTerminal.connection_mode, 'adms') != 'controller',
    ).all()

    if not terminals:
        return {"success": True, "queued": 0, "message": "No approved devices found"}

    # Fetch all direct-IP devices in one query
    sn_list = [t.sn for t in terminals]
    sn_csv  = ",".join(f"'{s}'" for s in sn_list)          # safe: SNs are regex-validated
    dev_rows = db.execute(text(f"""
        SELECT serial_number, ip_address, port, connection_mode
        FROM devices
        WHERE serial_number IN ({sn_csv}) AND ip_address IS NOT NULL
    """)).fetchall()
    dev_map = {r.serial_number: r for r in dev_rows}

    correct_time = datetime.now()
    correct_time_str = correct_time.strftime('%Y-%m-%d %H:%M:%S')
    # Encoded form for the PUSH protocol's `SET OPTIONS DateTime=<n>` (see cmd_sync_time).
    enc_datetime = _encode_adms_datetime(correct_time)
    results = []
    queued  = 0

    for t in terminals:
        dev = dev_map.get(t.sn)
        if dev and (dev.connection_mode or '').lower() in ('direct', 'both'):
            direct_err = None
            try:
                result = await _direct_sync_time(dev.ip_address, dev.port)
                if result.get('success'):
                    results.append({
                        "sn": t.sn, "alias": t.alias or t.sn,
                        "method": "direct", "status": "ok",
                        "device_reports": result.get('device_reports'),
                    })
                    queued += 1
                    continue
                direct_err = result.get('error')
            except Exception as exc:
                direct_err = str(exc)

            # Strict plane separation: a DIRECT-ONLY reader doesn't poll the ADMS
            # queue, so don't black-hole a command — record the failure and move on.
            # ('both' readers poll too, so the ADMS fallback below still applies.)
            if _is_direct_only(t.sn, db):
                logger.warning(f"Direct sync failed for {t.sn}: {direct_err} — direct-only, not queuing ADMS")
                results.append({
                    "sn": t.sn, "alias": t.alias or t.sn,
                    "method": "direct", "status": "failed",
                    "error": f"{direct_err or 'reader unreachable'} (direct-only — not queued)",
                })
                continue
            logger.warning(f"Direct sync failed for {t.sn}: {direct_err} — 'both' mode, using ADMS queue")

        # ADMS queue (primary for push devices, fallback for 'both' readers).
        # Final plane check: skip a direct-only reader that reached here because its
        # mode lives only in iclock_terminal (no `devices` row, so the direct attempt
        # above was skipped) — queuing for it would just black-hole.
        if _is_direct_only(t.sn, db):
            results.append({
                "sn": t.sn, "alias": t.alias or t.sn,
                "method": "direct", "status": "skipped",
                "error": "direct-only — does not poll ADMS; not queued",
            })
            continue
        try:
            cmd_id = queue_command(t.sn, f"SET OPTIONS DateTime={enc_datetime}", db)
            results.append({
                "sn": t.sn, "alias": t.alias or t.sn,
                "method": "adms", "status": "queued", "cmd_id": cmd_id,
            })
            queued += 1
        except Exception as e:
            logger.error(f"Failed to queue time sync for {t.sn}: {e}")
            results.append({"sn": t.sn, "alias": t.alias or t.sn, "error": str(e)})

    logger.info(f"Bulk time sync: synced/queued {queued}/{len(terminals)} devices at {correct_time_str}")
    return {
        "success":     True,
        "server_time": correct_time_str,
        "queued":      queued,
        "total":       len(terminals),
        "devices":     results,
    }


@router.get("/iclock/cmd/stuck")
async def get_stuck_commands(older_than_minutes: int = 5, db: Session = Depends(get_db)):
    """
    Surface ADMS commands that are likely BLACK-HOLED — queued (status=0) but on a
    device that can't pick them up because it doesn't poll /iclock/getrequest.

    A command is flagged when it has sat at status=0 for longer than
    `older_than_minutes` AND its device's effective plane is Direct-only or
    Controller (neither polls the ADMS command queue). This is the safety net for
    the guard added to the push-* / query-attlog endpoints: it also catches rows
    queued before the guard existed, or queued via some other path.
    """
    rows = db.execute(text("""
        SELECT c.id, c.sn, c.cmd_content, c.cmd_commit_time,
               EXTRACT(EPOCH FROM (NOW() - c.cmd_commit_time))/60.0 AS age_minutes
        FROM iclock_devcmd c
        WHERE c.status = 0
          AND c.cmd_commit_time < NOW() - (:mins || ' minutes')::interval
        ORDER BY c.cmd_commit_time ASC
        LIMIT 500
    """), {"mins": older_than_minutes}).fetchall()

    stuck = []
    for r in rows:
        if _is_controller(r.sn, db):
            reason = "controller"
        elif _is_direct_only(r.sn, db):
            reason = "direct_only"
        else:
            continue  # adms/both device — legitimately pending, not black-holed
        stuck.append({
            "id":          r.id,
            "sn":          r.sn,
            "cmd_content": (r.cmd_content or "")[:120],
            "queued_at":   r.cmd_commit_time.isoformat() if r.cmd_commit_time else None,
            "age_minutes": round(float(r.age_minutes or 0), 1),
            "reason":      reason,
        })

    return {
        "count":             len(stuck),
        "older_than_minutes": older_than_minutes,
        "commands":          stuck,
        "hint": ("These commands target Direct/Controller devices that don't poll the "
                 "ADMS queue — they will never deliver. Cancel them (DELETE "
                 "/iclock/devcmd/{id} on the device-management API) or fix the device's "
                 "Connection Mode."),
    }


@router.get("/iclock/terminals/time-drift")
async def get_time_drift(db: Session = Depends(get_db)):
    """
    Return real-time clock drift for each approved device.

    Direct-IP devices: queries the device clock live via ZKLib TCP so drift is
    always accurate and up-to-date regardless of historical punch data quality.

    ADMS push-only devices: estimates drift from recent punches (uploaded within
    the last 24 hours and with a <2h punch-to-upload lag so corrupted/batched
    records do not skew the result).  Reports 'no_recent_data' when no suitable
    punch exists.
    """
    from ..services.zkteco.direct_connection import zkteco_direct

    terminals = db.execute(text("""
        SELECT t.sn, t.alias, t.last_activity,
               d.ip_address, d.port, d.connection_mode
        FROM iclock_terminal t
        LEFT JOIN devices d ON d.serial_number = t.sn
        WHERE t.state = :approved AND COALESCE(t.connection_mode, '') <> 'controller'
    """), {"approved": STATE_APPROVED}).fetchall()

    server_now = datetime.now()
    devices    = []

    # Probe all direct-IP device clocks CONCURRENTLY (with a per-probe timeout) so a
    # slow/unreachable reader can't make this endpoint take the sum of all probes —
    # the Devices page calls it, and sequential probes were taking ~11s.
    async def _probe_clock(row):
        try:
            return await asyncio.wait_for(
                zkteco_direct.get_time(ip=row.ip_address, port=row.port or 4370),
                timeout=5,
            )
        except asyncio.TimeoutError:
            return {"success": False, "error": "timeout"}
        except Exception as exc:
            return {"success": False, "error": str(exc) or "unreachable"}

    _direct_rows = [r for r in terminals
                    if r.ip_address and (r.connection_mode or '').lower() in ('direct', 'both')]
    _probe_results: dict = {}
    if _direct_rows:
        _res = await asyncio.gather(*[_probe_clock(r) for r in _direct_rows], return_exceptions=True)
        for _r, _pr in zip(_direct_rows, _res):
            _probe_results[_r.sn] = _pr if isinstance(_pr, dict) else {"success": False, "error": str(_pr)}

    for r in terminals:
        drift       = None
        method      = "none"
        detail      = None
        is_direct   = r.ip_address and (r.connection_mode or '').lower() in ('direct', 'both')

        # ── Direct-IP devices: live clock query (probed concurrently above) ──
        if is_direct:
            try:
                res = _probe_results.get(r.sn) or {"success": False, "error": "unreachable"}
                if res.get('success') and res.get('device_time'):
                    raw = str(res['device_time'])[:19]
                    device_dt = None
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                        try:
                            device_dt = datetime.strptime(raw, fmt)
                            break
                        except ValueError:
                            continue
                    if device_dt:
                        drift  = int((server_now - device_dt).total_seconds())
                        method = "live"
                    else:
                        detail = f"Could not parse device time: {raw}"
                        method = "live_parse_error"
                else:
                    detail = res.get('error', 'unreachable')
                    method = "live_failed"
            except Exception as exc:
                detail = str(exc)
                method = "live_failed"

        # ── ADMS push devices (or fallback): recent punch estimate ───────
        if drift is None:
            recent = db.execute(text("""
                SELECT punch_time, upload_time
                FROM iclock_transaction
                WHERE terminal_sn = :sn
                  AND upload_time >= NOW() - INTERVAL '24 hours'
                  AND ABS(EXTRACT(EPOCH FROM (upload_time - punch_time))) < 7200
                ORDER BY upload_time DESC
                LIMIT 1
            """), {'sn': r.sn}).fetchone()

            if recent:
                pt = recent.punch_time.replace(tzinfo=None) if recent.punch_time else None
                ut = recent.upload_time.replace(tzinfo=None) if recent.upload_time else None
                if pt and ut:
                    drift  = int((ut - pt).total_seconds())
                    method = "recent_punch"
            else:
                method = "no_recent_data"

        # ── Status ───────────────────────────────────────────────────────
        if drift is None:
            drift_status = "unknown"
        elif abs(drift) <= 60:
            drift_status = "ok"
        elif abs(drift) <= 300:
            drift_status = "warning"
        else:
            drift_status = "critical"

        devices.append({
            "sn":            r.sn,
            "alias":         r.alias or r.sn,
            "last_activity": r.last_activity.isoformat() if r.last_activity else None,
            "drift_seconds": drift,
            "drift_status":  drift_status,
            "method":        method,
            "detail":        detail,
        })

    # Sort: critical first, then warning, then ok/unknown
    _order = {"critical": 0, "warning": 1, "ok": 2, "unknown": 3}
    devices.sort(key=lambda d: _order.get(d["drift_status"], 3))

    return {"success": True, "data": devices, "server_time": server_now.isoformat()}
