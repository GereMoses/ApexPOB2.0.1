"""
ZKTeco Live Capture Service

Holds a persistent TCP connection to each device using ZKLib's live_capture()
generator, which the device firmware pushes punch events to the moment they occur.

Design:
- One daemon threading.Thread per device (never touches uvicorn's thread pool).
- Thread → asyncio bridged via loop.call_soon_threadsafe into an asyncio.Queue.
- On each real punch: save to DB + notify all SSE subscribers instantly.
- Reconnects automatically after any disconnect.
"""

import logging
import threading
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session
from sqlalchemy import or_

from ...core.database import SessionLocal
from ...models.device import Device
from ...models.biotime_models import IClockTransaction
from ...models.personnel import Personnel
from ..device_pin import resolve_emp_code

logger = logging.getLogger(__name__)

# ── SSE subscriber registry ──────────────────────────────────────────────────
_punch_subscribers: Set[asyncio.Queue] = set()
_sub_lock = threading.Lock()

# ── Per-device ZK daemon thread tracker (device_id → current thread) ─────────
_device_threads: Dict[int, Optional[threading.Thread]] = {}
_device_threads_lock = threading.Lock()


def add_subscriber(q: asyncio.Queue) -> None:
    with _sub_lock:
        _punch_subscribers.add(q)


def remove_subscriber(q: asyncio.Queue) -> None:
    with _sub_lock:
        _punch_subscribers.discard(q)


def _broadcast(event: Dict, loop: asyncio.AbstractEventLoop) -> None:
    """Called from the event loop thread — put event in every SSE queue."""
    dead: Set[asyncio.Queue] = set()
    with _sub_lock:
        targets = list(_punch_subscribers)
    for q in targets:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.add(q)
    if dead:
        with _sub_lock:
            _punch_subscribers.difference_update(dead)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _resolve_emp_code(db: Session, user_id: str) -> str:
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


def _save_punch(db: Session, sn: str, area: str, rec) -> Optional[Dict]:
    from ...models.biotime_models import IClockTerminal
    from ...api.adms_protocol import _handle_zone_access, _ensure_access_control_records

    ts = rec.timestamp
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    raw_id = str(rec.user_id) if rec.user_id else str(getattr(rec, "uid", ""))
    emp_code = _resolve_emp_code(db, raw_id)

    # Look up terminal to determine reader purpose and apply correct routing
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    reader_purpose = terminal.reader_purpose if terminal and terminal.reader_purpose else 'ATTENDANCE'
    is_access_reader = reader_purpose in ('ACCESS_ENTRY', 'ACCESS_EXIT')

    # Force punch direction for access readers; use raw device value for attendance
    if is_access_reader:
        punch_state = 0 if reader_purpose == 'ACCESS_ENTRY' else 1
    else:
        punch_state = int(rec.punch) if hasattr(rec, "punch") and rec.punch is not None else 0

    exists = db.query(IClockTransaction).filter(
        IClockTransaction.terminal_sn == sn,
        IClockTransaction.emp_code == emp_code,
        IClockTransaction.punch_time == ts,
    ).first()
    if exists:
        return None

    # Zone tracking for access-control readers
    if is_access_reader:
        direction = 'ENTRY' if reader_purpose == 'ACCESS_ENTRY' else 'EXIT'
        try:
            _ensure_access_control_records(
                sn, getattr(terminal, 'alias', None) or sn,
                terminal.zone_id, direction, db,
            )
            _handle_zone_access(emp_code, sn, ts, terminal, direction, db)
        except Exception as exc:
            logger.error("Live capture zone access error %s@%s: %s", emp_code, sn, exc)
            db.rollback()

    txn = IClockTransaction(
        emp_code=emp_code,
        punch_time=ts,
        punch_state=punch_state,
        terminal_sn=sn,
        area_alias=area,
        upload_time=datetime.now(timezone.utc),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return {
        "type":        "punch",
        "id":          txn.id,
        "emp_code":    emp_code,
        "punch_time":  ts.isoformat(),
        "punch_state": punch_state,
        "terminal_sn": sn,
    }


# ── Daemon thread: pure blocking ZK I/O, isolated from uvicorn ───────────────

def _zk_thread(ip: str, port: int, stop_evt: threading.Event,
               async_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
    """
    Dedicated daemon thread.  Opens a ZKLib live_capture() session and pushes
    each event into async_queue via call_soon_threadsafe so the event loop is
    never touched from this thread directly.

    Sends:
      - attendance record objects  (real punch)
      - None                       (idle heartbeat tick — ignored)
      - Exception instance         (connection error — triggers reconnect)
    """
    from zk import ZK

    def _put(item):
        if not loop.is_closed():
            loop.call_soon_threadsafe(async_queue.put_nowait, item)

    try:
        zk = ZK(ip, port=port, timeout=8, password=0, force_udp=False, ommit_ping=True)
        conn = zk.connect()
    except Exception as exc:
        _put(exc)
        return

    try:
        # new_timeout (if supported) makes live_capture yield None every N seconds
        # so stop_evt is checked promptly; fall back if the pyzk version is old.
        try:
            gen = conn.live_capture(new_timeout=3)
        except TypeError:
            gen = conn.live_capture()

        for record in gen:
            if stop_evt.is_set():
                break
            _put(record)   # None = idle tick, attendance object = real event

    except Exception as exc:
        _put(exc)
    finally:
        try:
            conn.disconnect()
        except Exception:
            pass


# ── Async task for one device ─────────────────────────────────────────────────

async def _device_live_capture(device_id: int,
                                loop: asyncio.AbstractEventLoop) -> None:
    RETRY_BASE    = 5
    RETRY_MAX     = 300   # max 5 min between retries for persistently offline devices
    STABLE_THRESH = 30    # seconds connected before we consider it "stable" and reset backoff
    retry         = RETRY_BASE

    def _get_device_config():
        db: Session = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if not device or not device.ip_address:
                return None
            return (device.ip_address, device.port or 4370,
                    device.serial_number or f"IP-{device.ip_address}",
                    device.location_description or device.name or device.serial_number or str(device_id))
        finally:
            db.close()

    while True:
        # Fresh DB lookup each cycle — run in executor to avoid blocking event loop
        cfg = await asyncio.get_event_loop().run_in_executor(None, _get_device_config)
        if cfg is None:
            logger.warning("Live capture: device %s not found — stopping", device_id)
            return
        ip, port, sn, area = cfg

        # Fast reachability probe (~2s) BEFORE the full 8s ZK connect. An offline
        # reader is common (network blip, powered down); without this each retry ties
        # up a worker thread + a DB session for 8s+, and enough of those under load
        # starve request handling so even logins time out. Unreachable → back off
        # and skip the expensive connect entirely.
        def _reachable():
            import socket
            try:
                with socket.create_connection((ip, int(port)), timeout=2):
                    return True
            except Exception:
                return False

        if not await asyncio.get_event_loop().run_in_executor(None, _reachable):
            retry = min(retry * 2, RETRY_MAX)
            logger.debug("Live capture: %s (%s:%s) unreachable — retry in %ss", sn, ip, port, retry)
            await asyncio.sleep(retry)
            continue

        logger.info("Live capture: connecting to %s (%s:%s)", sn, ip, port)

        stop_evt   = threading.Event()
        async_q: asyncio.Queue = asyncio.Queue(maxsize=200)

        thread = threading.Thread(
            target=_zk_thread,
            args=(ip, port, stop_evt, async_q, loop),
            daemon=True,
            name=f"zk-{sn}",
        )
        with _device_threads_lock:
            _device_threads[device_id] = thread
        thread.start()

        punch_count  = 0
        connect_time = asyncio.get_event_loop().time()
        db = None  # opened lazily on the first real punch — an idle/offline reader
                   # must not hold a pooled DB connection while it waits.
        try:
            while True:
                try:
                    # Wait up to 10 s for the next item; yield control every tick
                    item = await asyncio.wait_for(async_q.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    # No event in 10 s — check if thread is still alive
                    if not thread.is_alive():
                        break
                    continue
                except asyncio.CancelledError:
                    stop_evt.set()
                    return

                if isinstance(item, Exception):
                    logger.warning("Live capture %s error: %s", ip, item)
                    break

                if item is None:
                    continue   # idle heartbeat tick

                try:
                    if db is None:
                        db = SessionLocal()
                    event = _save_punch(db, sn, area, item)
                    if event:
                        punch_count += 1
                        logger.info("Live punch: emp=%s state=%s via %s",
                                    event["emp_code"], event["punch_state"], sn)
                        _broadcast(event, loop)
                except Exception as exc:
                    logger.error("Live capture %s save error: %s", ip, exc)
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    # Re-create session so the pool connection is fully released
                    try:
                        db.close()
                    except Exception:
                        pass
                    from ...core.database import SessionLocal as _SL
                    db = _SL()
        finally:
            stop_evt.set()
            if db is not None:
                db.close()
            with _device_threads_lock:
                _device_threads[device_id] = None

        thread.join(timeout=5)
        connected_for = asyncio.get_event_loop().time() - connect_time
        if connected_for >= STABLE_THRESH or punch_count > 0:
            # Connection was stable — reset backoff so next reconnect is fast
            retry = RETRY_BASE
        else:
            # Quick failure — apply exponential backoff
            retry = min(retry * 2, RETRY_MAX)
        logger.info("Live capture %s: offline (%s punches, %.0fs connected) — retry in %ss",
                    sn, punch_count, connected_for, retry)


# ── Module-level task registry (populated by supervisor) ─────────────────────

_tasks: Dict[int, asyncio.Task] = {}
_loop: Optional[asyncio.AbstractEventLoop] = None


async def with_device_released(device_id: int, coro):
    """
    Cancel the live-capture task for *device_id*, wait for the ZK daemon thread
    to disconnect (freeing the device's single TCP slot), run *coro*, then let
    the supervisor restart capture on its next 30-second poll.
    """
    # 1. Signal the asyncio task to stop (sets stop_evt inside it)
    task = _tasks.get(device_id)
    if task and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    # 2. Wait for the daemon thread (which holds the TCP connection) to exit.
    #    new_timeout=3 means it wakes every 3 s at most; total wait ≤ 8 s.
    loop = asyncio.get_event_loop()
    with _device_threads_lock:
        thread = _device_threads.get(device_id)
    if thread and thread.is_alive():
        await loop.run_in_executor(None, thread.join, 8)

    # 3. Give the device's TCP stack a moment to release the slot
    await asyncio.sleep(1)
    return await coro


# ── Supervisor ────────────────────────────────────────────────────────────────

def _db_get_poll_devices() -> list:
    """Synchronous DB read for supervisor — run in executor."""
    db: Session = SessionLocal()
    try:
        devices = (
            db.query(Device)
            .filter(
                Device.auto_poll == True,
                Device.ip_address.isnot(None),
                Device.connection_mode.in_(["direct", "both"]),
            )
            .all()
        )
        return [(d.id, d.name, d.ip_address) for d in devices]
    finally:
        db.close()


async def live_capture_supervisor() -> None:
    global _loop
    logger.info("Live capture supervisor started")
    _loop = asyncio.get_event_loop()
    loop  = _loop
    tasks = _tasks  # reference module-level dict

    while True:
        try:
            device_list = await asyncio.get_event_loop().run_in_executor(
                None, _db_get_poll_devices
            )
            current_ids = {did for did, _, _ in device_list}

            for did, name, ip in device_list:
                if did not in tasks or tasks[did].done():
                    tasks[did] = asyncio.create_task(
                        _device_live_capture(did, loop),
                        name=f"live-capture-{did}",
                    )
                    logger.info("Live capture supervisor: started task for %s (%s)", name, ip)

            for did in list(tasks):
                if did not in current_ids:
                    tasks[did].cancel()
                    del tasks[did]

        except asyncio.CancelledError:
            for t in tasks.values():
                t.cancel()
            return
        except Exception as exc:
            logger.error("Live capture supervisor error: %s", exc)

        await asyncio.sleep(30)
