"""
ZKTeco Device Poller

Background service that periodically connects to non-ADMS (or dual-mode) ZKTeco
devices via ZKLib (port 4370), pulls attendance records since the last pull, deduplicates
them against iclock_transaction, and inserts any new ones — exactly the same table
that ADMS-push devices write to so all downstream reporting is unified.

The poller is started as a single asyncio task in main.py startup.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import or_

from ...core.database import SessionLocal
from ...models.device import Device, DeviceStatus
from ...models.biotime_models import IClockTransaction, IClockTerminal
from ...models.personnel import Personnel
from ..device_pin import resolve_emp_code
from .direct_connection import zkteco_direct

logger = logging.getLogger(__name__)

# SNs that the heartbeat service flagged as just-came-online — poller drains this
# before its normal 60-second sweep so reconnected devices sync immediately.
_immediate_poll_sns: set = set()


def request_immediate_poll(sn: str) -> None:
    """Called (thread-safe under GIL) by the heartbeat service on online transition."""
    _immediate_poll_sns.add(sn)


# Punch-state int → int (IClockTransaction.punch_state is SmallInteger)
_PUNCH_MAP = {
    0: 0,   # check-in
    1: 1,   # check-out
    2: 2,   # break-out
    3: 3,   # break-in
    4: 4,   # overtime-in
    5: 5,   # overtime-out
}


def _ensure_terminal(db: Session, device: Device, sn: str) -> None:
    """Make sure iclock_terminal has a row for this device (create if missing)."""
    existing = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    if not existing:
        db.add(IClockTerminal(
            sn=sn,
            alias=device.name,
            ip_address=device.ip_address,
            state=1,
        ))
        db.flush()


def _resolve_emp_code(db: Session, user_id: str) -> str:
    """
    Resolve the ZKTeco user_id (which may be badge_id OR emp_code) to the
    canonical emp_code stored in the personnel table.
    Falls back to user_id unchanged if no match found.
    """
    if not user_id:
        return user_id
    # SeamlessHR attendance ID (the PIN we write to the reader) wins; it also
    # matches ignoring leading zeros. No attendance-ID match returns user_id as-is.
    by_attendance = resolve_emp_code(db, user_id)
    if by_attendance != user_id:
        return by_attendance
    emp = db.query(Personnel).filter(
        or_(Personnel.badge_id == user_id, Personnel.emp_code == user_id)
    ).first()
    return emp.emp_code if emp else user_id


def _save_records(db: Session, device: Device, records: list, sn: str) -> int:
    """
    Insert attendance records into iclock_transaction, skipping duplicates.
    For ACCESS_ENTRY / ACCESS_EXIT readers also fires zone tracking so that
    ZKLib-polled devices update zone occupancy exactly like ADMS-push devices.
    Returns count of newly inserted rows.
    """
    from ...api.adms_protocol import _handle_zone_access

    # Resolve terminal once so we don't query on every record.
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    reader_purpose = terminal.reader_purpose if terminal and terminal.reader_purpose else 'ATTENDANCE'
    is_access_reader = reader_purpose in ('ACCESS_ENTRY', 'ACCESS_EXIT')
    direction = 'ENTRY' if reader_purpose == 'ACCESS_ENTRY' else 'EXIT'

    inserted = 0
    zone_updates: dict = {}

    for rec in records:
        ts_str = rec["timestamp"]               # already ISO string from direct_connection
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # user_id from ZKLib is the badge_id set on the device (may differ from emp_code)
        raw_id = str(rec["user_id"]) if rec.get("user_id") else str(rec["uid"])
        emp_code = _resolve_emp_code(db, raw_id)

        # Access readers get a forced direction; attendance readers use the device punch type
        if is_access_reader:
            punch_state = 0 if reader_purpose == 'ACCESS_ENTRY' else 1
        else:
            punch_state = _PUNCH_MAP.get(rec.get("punch", 0), 0)

        # Dedup: same device + employee + timestamp (to the second)
        exists = db.query(IClockTransaction).filter(
            IClockTransaction.terminal_sn == sn,
            IClockTransaction.emp_code == emp_code,
            IClockTransaction.punch_time == ts,
        ).first()

        if exists:
            continue

        # Zone tracking for access-control readers — mirrors handle_attlog behaviour
        if is_access_reader:
            try:
                from ...api.adms_protocol import _ensure_access_control_records
                _ensure_access_control_records(
                    sn, getattr(terminal, 'alias', None) or sn,
                    terminal.zone_id, direction, db,
                )
                updates = _handle_zone_access(emp_code, sn, ts, terminal, direction, db)
                zone_updates.update(updates)
            except Exception as exc:
                logger.error("Poller: zone access error %s@%s: %s", emp_code, sn, exc)
                db.rollback()

        db.add(IClockTransaction(
            emp_code=emp_code,
            punch_time=ts,
            punch_state=punch_state,
            terminal_sn=sn,
            area_alias=device.location_description or device.name,
            upload_time=datetime.now(timezone.utc),
        ))
        inserted += 1

    if inserted:
        db.commit()
        logger.info("Poller: inserted %d new records from %s (%s)", inserted, device.name, device.ip_address)

    # Broadcast zone occupancy changes to WebSocket clients
    if zone_updates:
        try:
            from ...core.websocket import broadcast_zone_update
            for zone_id, count in zone_updates.items():
                asyncio.ensure_future(broadcast_zone_update(zone_id, count))
        except Exception as exc:
            logger.warning("Poller: zone broadcast error: %s", exc)

    return inserted


async def poll_device(device: Device, db: Session) -> dict:
    """
    Pull attendance records from a single device, save new ones, update timestamps.
    Returns a summary dict.
    """
    ip = device.ip_address
    port = device.port or 4370
    sn = device.serial_number or f"IP-{ip}"
    # ZKLib returns naive device-local datetimes.  Always pass `since` as a
    # naive datetime so the comparison inside get_attendance is consistent.
    # DB may store TIMESTAMPTZ (aware) or naive; normalise to naive UTC here.
    since_raw = device.last_attendance_pull
    if since_raw is None:
        since = None
    elif since_raw.tzinfo is not None:
        since = since_raw.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        since = since_raw

    try:
        result = await asyncio.wait_for(
            zkteco_direct.get_attendance(ip=ip, port=port, since=since),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Poller: get_attendance timed out for %s after 30s", ip)
        device.status = DeviceStatus.OFFLINE
        db.commit()
        return {"device_id": device.id, "success": False, "error": "Connection timed out"}

    if not result.get("success"):
        logger.warning("Poller: failed to pull from %s — %s", ip, result.get("error"))
        device.status = DeviceStatus.OFFLINE
        db.commit()
        # STATE_OFFLINE = 3  (NOT 0 — 0 is STATE_PENDING / awaiting admin approval)
        term = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
        if term and term.state not in (0, 2):  # preserve PENDING and REJECTED
            term.state = 3
            db.commit()
        return {"device_id": device.id, "success": False, "error": result.get("error")}

    records = result.get("records", [])
    _ensure_terminal(db, device, sn)
    inserted = _save_records(db, device, records, sn)

    # Update pull timestamp and mark online
    now = datetime.now(timezone.utc)
    device.last_attendance_pull = now
    device.status = DeviceStatus.ONLINE
    device.last_seen = now
    db.commit()

    # Keep IClockTerminal in sync: state=1 (online) + fresh last_activity
    term = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    if term:
        term.state = 1
        term.last_activity = now
        db.commit()

    # Sync device clock immediately after every successful pull so attendance
    # timestamps are accurate without waiting for the hourly time-sync loop.
    try:
        time_result = await asyncio.wait_for(
            zkteco_direct.sync_time(ip=ip, port=port), timeout=15.0,
        )
        if time_result.get("success"):
            logger.info("Poller: time sync OK for %s — device reported %s",
                        ip, time_result.get("device_reports"))
        else:
            logger.warning("Poller: time sync failed for %s: %s",
                           ip, time_result.get("error"))
    except asyncio.TimeoutError:
        logger.warning("Poller: time sync timed out for %s after 15s", ip)
    except Exception as exc:
        logger.warning("Poller: time sync error for %s: %s", ip, exc)

    return {
        "device_id": device.id,
        "name": device.name,
        "ip": ip,
        "success": True,
        "pulled": len(records),
        "new_records": inserted,
        "polled_at": now.isoformat(),
    }


async def poller_loop() -> None:
    """
    Main background loop.  Starts immediately on the first iteration (5 s delay),
    then wakes every 60 s to check which devices are due for a poll.

    Immediate-poll queue: heartbeat_loop calls request_immediate_poll(sn) when a
    device transitions offline→online; those devices are polled right away without
    waiting for the 60 s cycle.
    """
    logger.info("Device poller started — first check in 5 s, then every 60 s")
    first = True
    while True:
        await asyncio.sleep(5 if first else 60)
        first = False
        try:
            db: Session = SessionLocal()
            try:
                now = datetime.now(timezone.utc)

                # ── Immediate-poll queue (reconnected devices) ──────────────
                if _immediate_poll_sns:
                    urgent = list(_immediate_poll_sns)
                    _immediate_poll_sns.clear()
                    for sn in urgent:
                        device = db.query(Device).filter(
                            Device.serial_number == sn,
                            Device.ip_address.isnot(None),
                        ).first()
                        if device:
                            logger.info("Poller: immediate pull triggered for %s (reconnected)", sn)
                            try:
                                await poll_device(device, db)
                            except Exception as exc:
                                logger.error("Poller: immediate poll error for %s: %s", sn, exc)

                # ── Scheduled poll cycle ────────────────────────────────────
                candidates = (
                    db.query(Device)
                    .filter(
                        Device.auto_poll == True,
                        Device.ip_address.isnot(None),
                        Device.connection_mode.in_(["direct", "both"]),
                    )
                    .all()
                )

                for device in candidates:
                    if device.last_attendance_pull:
                        last_pull = device.last_attendance_pull
                        if last_pull.tzinfo is None:
                            last_pull = last_pull.replace(tzinfo=timezone.utc)
                        elapsed = (now - last_pull).total_seconds()
                        if elapsed < device.poll_interval_sec:
                            continue

                    try:
                        await poll_device(device, db)
                    except Exception as exc:
                        logger.error("Poller: unhandled error for device %s: %s", device.id, exc)

            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("Device poller stopped")
            break
        except Exception as exc:
            logger.error("Poller loop error: %s", exc)
