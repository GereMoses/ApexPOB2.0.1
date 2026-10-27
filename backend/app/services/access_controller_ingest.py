"""
Access-controller event ingestion.

Bridges the C3/inBio controller realtime log into the SAME zone-occupancy engine
the ADMS readers use. A controller emits one event per card read, tagged with a
door number and an in/out flag. We resolve `(controller, door_no, direction)` to
an `AccessReader` → its `zone_id`, then hand off to `_handle_zone_access`, so POB
totals and mustering stay consistent across both reader families.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time as _time
from datetime import datetime
from types import SimpleNamespace
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.access_controller import AccessController, AccessReader
from ..services.zkteco.c3_controller import C3Event

logger = logging.getLogger(__name__)


def _direction_from_inout(in_out: int) -> str:
    """C3 inoutstate: 0 = entry side, 1 = exit side (panel-configured)."""
    return "EXIT" if int(in_out) == 1 else "ENTRY"


# ── Mock / simulation mode ─────────────────────────────────────────────────────
# A controller whose serial number starts with "MOCK" is a simulated panel: no TCP
# connection is attempted; instead it emits one synthetic event per poll, rotating
# through its doors so you can exercise learn-mode + zone assignment without real
# hardware. Consistent with the existing mock-device patterns in this codebase.
_MOCK_SEQ: Dict[int, int] = {}   # controller_id → rotation counter


def _is_mock(controller: AccessController) -> bool:
    sn = (controller.serial_number or "").upper()
    return sn.startswith("MOCK")


def _mock_emp_codes(db: Session) -> List[str]:
    rows = db.execute(text(
        "SELECT emp_code FROM personnel WHERE emp_code IS NOT NULL ORDER BY id LIMIT 6"
    )).fetchall()
    return [r.emp_code for r in rows] or ["EMP001"]


def _mock_rtlog(controller: AccessController, db: Session) -> List[C3Event]:
    """One synthetic event per call, cycling door1-IN, door1-OUT, … then a door
    BEYOND door_count to demonstrate learn-mode auto-discovering an unmapped port."""
    doors = max(1, controller.door_count or 1)
    # (door_no, in_out): each door's entry then exit, plus one surprise door (doors+1)
    seq = [(d, io) for d in range(1, doors + 1) for io in (0, 1)]
    seq.append((doors + 1, 0))   # a port that wasn't seeded — fires "new port" in learn

    n = _MOCK_SEQ.get(controller.id, 0)
    _MOCK_SEQ[controller.id] = n + 1
    door_no, in_out = seq[n % len(seq)]

    emps = _mock_emp_codes(db)
    emp = emps[n % len(emps)]

    return [C3Event(
        time=datetime.utcnow(),
        card_no=None,
        pin=emp,
        door_id=door_no,
        event_type=0,
        in_out=in_out,
        verify_type=1,
        raw={"mock": "1"},
    )]


def _fetch_via_sidecar(controller: AccessController, base_url: str) -> List[C3Event]:
    """Fetch realtime events from a Windows PULL SDK sidecar (plcommpro.dll host).
    The sidecar returns the RAW RTLog text; we parse it with the authoritative parser."""
    import httpx
    from ..services.zkteco.c3_controller import _parse_rtlog_text
    payload = {"ip": controller.ip_address, "port": controller.port or 4370,
               "passwd": controller.comm_password or ""}
    headers = {}
    token = os.environ.get("ZK_SDK_SIDECAR_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=15) as client:
        resp = client.post(base_url.rstrip("/") + "/rtlog", json=payload, headers=headers)
        resp.raise_for_status()
        return _parse_rtlog_text(resp.json().get("raw", ""))


def _fetch_rtlog(controller: AccessController, db: Session) -> List[C3Event]:
    """Read buffered realtime events. Order of preference:
    1. mock generator (simulated controllers);
    2. the pure-Python zkaccess-c3 driver — the STANDALONE path (in-container, no
       DLL); this is the production driver for the real C3-200/C3-400 panels;
    3. a Windows PULL SDK sidecar (ZK_SDK_SIDECAR_URL) — legacy fallback;
    4. the official PULL SDK loaded locally (libplcommpro.so), if present;
    5. the scaffold binary client (unverified) as a last resort."""
    if _is_mock(controller):
        return _mock_rtlog(controller, db)

    from ..services.zkteco import c3_zkaccess
    if c3_zkaccess.sdk_available():
        with c3_zkaccess.ZKAccessC3Client(
            controller.ip_address, controller.port or 4370, controller.comm_password or ""
        ) as c:
            return c.get_rt_log()

    sidecar = os.environ.get("ZK_SDK_SIDECAR_URL")
    if sidecar:
        return _fetch_via_sidecar(controller, sidecar)

    from ..services.zkteco import c3_pull_sdk
    if c3_pull_sdk.sdk_available():
        with c3_pull_sdk.PullSDKClient(
            controller.ip_address, controller.port or 4370, controller.comm_password or ""
        ) as c:
            return c.get_rt_log()

    from ..services.zkteco.c3_controller import C3Controller, C3Config
    with C3Controller(C3Config(
        ip=controller.ip_address,
        port=controller.port or 4370,
        password=controller.comm_password or "",
    )) as c3:
        return c3.get_rt_log()


# ZKTeco C3 event codes (zkaccess-c3 consts.EventType)
GRANTED = {0, 1, 2, 3, 14, 15, 16, 17, 18, 19, 101, 103, 203, 208}      # a person passed the door
DURESS = {101, 103}                                                    # duress PIN / finger: silent alarm
DENIED = {20, 21, 22, 23, 24, 25, 27, 29, 30, 31, 33, 34, 35, 41, 42}  # a person was refused
ALARMS = {28, 102, 255}                                                # door held / forced / alarm
_DENIAL = {20: "Tapped again too quickly", 21: "Door not active at this time", 22: "Outside allowed hours",
           23: "Access denied", 24: "Anti-passback", 25: "Interlock", 27: "Unregistered card",
           29: "Card expired", 30: "Wrong password", 31: "Fingerprint tapped too quickly", 33: "Fingerprint expired",
           34: "Unregistered fingerprint", 35: "Door not active at this time", 41: "Verify type not allowed",
           42: "Wiegand format error", 28: "Door held open too long", 102: "Door forced open", 255: "Door alarm"}


def _to_utc(t):
    """C3 panels keep SITE time (their access hours depend on it); punches are
    stored in UTC like every other reader's."""
    from datetime import timezone as _tz
    from .attendance_calculation_service import SITE_TZ
    if t is None:
        return datetime.now(_tz.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=SITE_TZ)
    return t.astimezone(_tz.utc)


_CLOCK_SYNCED: Dict[int, float] = {}


def _sync_clock_daily(controller: AccessController) -> None:
    """Keep the panel clock on site time (once a day, and after a restart of POB)."""
    if _is_mock(controller) or _time.time() - _CLOCK_SYNCED.get(controller.id, 0) < 86400:
        return
    try:
        from ..services.zkteco import c3_zkaccess
        from .attendance_calculation_service import SITE_TZ
        if not c3_zkaccess.sdk_available():
            return
        with c3_zkaccess.ZKAccessC3Client(controller.ip_address, controller.port or 4370,
                                          controller.comm_password or "") as c:
            c._c3.set_device_datetime(datetime.now(SITE_TZ).replace(tzinfo=None))
        _CLOCK_SYNCED[controller.id] = _time.time()
        logger.info("Controller %s clock set to site time", controller.id)
    except Exception as e:  # noqa: BLE001 — a clock hiccup must not stop event polling
        logger.warning("Controller %s clock sync failed: %s", controller.id, e)


def _person_for(db: Session, event: C3Event) -> str:
    """emp_code for a tap: the panel PIN (= Attendance ID) first, else the card number."""
    from .device_pin import resolve_emp_code
    pin = (event.pin or "").strip()
    if pin and pin != "0":
        code = resolve_emp_code(db, pin)
        if code:
            return code
    card = (event.card_no or "").strip()
    if card and card != "0" and card.isdigit():
        row = db.execute(text("SELECT emp_code FROM personnel WHERE card_number = :c AND is_active LIMIT 1"),
                         {"c": int(card)}).fetchone()
        if row:
            return row.emp_code
    return ""


def reader_terminal_sn(reader: AccessReader) -> str:
    """Each reader port is mirrored as a terminal (iclock_terminal) so its taps go
    through the same attendance / POB / muster engine as an ADMS reader."""
    return f"AC{reader.controller_id}-D{reader.door_no}-{(reader.direction or 'E')[0]}"[:20]


def _terminal_purpose(reader: AccessReader) -> str:
    if reader.purpose in ("ATTENDANCE", "MUSTERING"):
        return reader.purpose
    return "ACCESS_EXIT" if reader.direction == "EXIT" else "ACCESS_ENTRY"


def _ensure_reader_terminal(db: Session, controller: AccessController, reader: AccessReader) -> str:
    """Mirror the reader port as a terminal on the CONTROLLER plane — so no ADMS
    command is ever queued for it — kept fresh (last_activity) by its taps."""
    sn = reader_terminal_sn(reader)
    db.execute(text("""
        INSERT INTO iclock_terminal (sn, alias, state, reader_purpose, zone_id, ip_address, connection_mode, last_activity)
        VALUES (:sn, :alias, 1, :purpose, :zone, :ip, 'controller', NOW())
        ON CONFLICT (sn) DO UPDATE SET alias = EXCLUDED.alias, reader_purpose = EXCLUDED.reader_purpose,
                                       zone_id = EXCLUDED.zone_id, state = 1, connection_mode = 'controller',
                                       last_activity = NOW()
    """), {"sn": sn, "alias": (reader.name or f"{controller.name} door {reader.door_no} {reader.direction.lower()}")[:50],
           "purpose": _terminal_purpose(reader), "zone": reader.zone_id, "ip": controller.ip_address})
    return sn


def _log_access(db: Session, emp_code: str, device: str, zone_id, direction: str, when, granted: bool,
                reason: str = None, event_type: int = None) -> None:
    sp = db.begin_nested()      # a logging failure must never undo the tap itself
    try:
        db.execute(text("""
            INSERT INTO access_logs (personnel_id, notes, event_type, access_granted, access_method,
                                     timestamp, denial_reason, error_code, zone_id, direction)
            VALUES ((SELECT id FROM personnel WHERE emp_code = :ec LIMIT 1), :dev, :et, :ok, 'C3', :ts, :why, :code, :z, :dir)
        """), {"ec": emp_code or "", "dev": device, "et": "ACCESS" if granted else "DENIED", "ok": granted,
               "ts": when, "why": reason, "code": str(event_type) if event_type is not None else None,
               "z": zone_id, "dir": direction})
        sp.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("access_logs write skipped: %s", e)
        sp.rollback()


def ingest_event(controller: AccessController, event: C3Event, db: Session) -> Dict[int, int]:
    """One controller tap → the same outcome as a tap on an ADMS reader.

    Granted tap:
      * MUSTERING reader (or any reader at a muster point during a muster) → counted safe
      * otherwise a punch row (iclock_transaction) on the reader's mirror terminal —
        ATTENDANCE readers feed attendance (first in / last out) and the SeamlessHR
        push; ACCESS readers are door-only — plus zone tracking / POB at boundaries,
        and an entry tap at an attendance reader marks the person on board.
    Refused tap: written to access_logs (security events); an unregistered card is
    remembered so it can be issued to a person. Duress PIN/finger: silent alarm.
    Returns {zone_id: new_occupancy} for changed zones.
    """
    from ..api.adms_protocol import _handle_zone_access, _punch_already_stored, _mark_onboard
    from ..models.biotime_models import IClockTransaction

    direction = _direction_from_inout(event.in_out)
    punch_time = _to_utc(event.time)
    reader = (
        db.query(AccessReader)
        .filter(AccessReader.controller_id == controller.id, AccessReader.door_no == event.door_id,
                AccessReader.direction == direction, AccessReader.status == "active")
        .first()
    )
    device = reader_terminal_sn(reader) if reader else f"AC{controller.id}-D{event.door_id}-{direction[0]}"
    zone_id = reader.zone_id if reader else None
    et = int(event.event_type) if event.event_type is not None else 0

    # ── fire alarm panel contact on an AUX input → fire mode ───────────────────
    if et in (220, 221) and controller.fire_alarm_input and int(event.door_id) == int(controller.fire_alarm_input):
        alarm = (et == 220 and (controller.fire_alarm_on or "open") == "open") or \
                (et == 221 and controller.fire_alarm_on == "close")
        if alarm:
            _trigger_fire_mode(controller, punch_time)
        return {}

    # ── refused / alarm ────────────────────────────────────────────────────────
    if et not in GRANTED:
        if et == 27 and event.card_no and str(event.card_no) != "0":
            db.execute(text("""
                INSERT INTO controller_unknown_card (card_no, controller_id, door_no, reader_name, taps, last_seen)
                VALUES (:c, :ctl, :d, :n, 1, NOW())
                ON CONFLICT (card_no) DO UPDATE SET taps = controller_unknown_card.taps + 1, last_seen = NOW(),
                    controller_id = EXCLUDED.controller_id, door_no = EXCLUDED.door_no, reader_name = EXCLUDED.reader_name
            """), {"c": str(event.card_no), "ctl": controller.id, "d": event.door_id,
                   "n": (reader.name if reader else None) or f"{controller.name} door {event.door_id}"})
        if et in DENIED or et in ALARMS:
            _log_access(db, _person_for(db, event), device, zone_id, direction, punch_time, False,
                        _DENIAL.get(et, f"event {et}"), et)
        db.commit()
        return {}

    emp_code = _person_for(db, event)
    if et in DURESS:
        try:
            from .notify_dispatch import dispatch_background
            where = (reader.name if reader else None) or f"{controller.name} door {event.door_id}"
            dispatch_background("panic", None, [], f"DURESS ALARM — {where}",
                                f"DURESS ALARM: {emp_code or 'someone'} opened {where} under duress "
                                f"(duress PIN/finger). Respond now — do not approach alone.", include_responders=True)
        except Exception as e:  # noqa: BLE001
            logger.error("Duress alert failed: %s", e)
    if not reader:
        logger.debug("Controller %s door %s/%s has no active reader mapping — event ignored",
                     controller.id, event.door_id, direction)
        return {}
    if not emp_code:
        logger.debug("Controller %s tap with no known pin/card", controller.id)
        return {}

    sn = _ensure_reader_terminal(db, controller, reader)
    _log_access(db, emp_code, sn, zone_id, direction, punch_time, True, None, et)

    # Muster point: counted safe (the ADMS path does the same for its muster readers).
    at_point = reader.purpose == "MUSTERING" or bool(db.execute(text("""
        SELECT 1 FROM zones z WHERE z.id = :z AND z.zone_type = 'MUSTER_POINT'
          AND EXISTS (SELECT 1 FROM mustering_event WHERE status = 0)"""), {"z": zone_id or -1}).scalar())
    if at_point:
        try:
            from .mustering_service import MusteringService
            MusteringService(db).process_mustering_punch(emp_code=emp_code, device_sn=sn, check_time=punch_time)
        except Exception as e:  # noqa: BLE001 — no active muster etc.
            logger.info("Muster-point tap %s@%s not counted: %s", emp_code, sn, e)
            db.rollback()
        reader.last_event_at = punch_time
        db.commit()
        return {}

    updates: Dict[int, int] = {}
    if not _punch_already_stored(emp_code, punch_time, sn, db):
        db.add(IClockTransaction(emp_code=emp_code, punch_time=punch_time,
                                 punch_state=0 if direction == "ENTRY" else 1,
                                 verify_type=int(event.verify_type or 0), work_code=0, terminal_sn=sn,
                                 area_alias=(reader.name or "")[:50]))
        db.flush()
        if zone_id:
            shim = SimpleNamespace(zone_id=zone_id, alias=reader.name or sn)
            updates = _handle_zone_access(emp_code, sn, punch_time, shim, direction, db) or {}
        if reader.purpose == "ATTENDANCE" and direction == "ENTRY":
            _mark_onboard(emp_code, True, db)
        if reader.purpose == "ATTENDANCE":
            _recalc_later(emp_code, punch_time)

    reader.last_event_at = punch_time
    db.commit()
    return updates


def _trigger_fire_mode(controller: AccessController, when: datetime) -> None:
    """The fire alarm panel tripped: fire exits open, sirens, site-wide muster, alerts.
    Ignored if a fire emergency is already running (contacts chatter)."""
    import threading

    def run():
        from ..core.database import SessionLocal
        db = SessionLocal()
        try:
            busy = db.execute(text("SELECT 1 FROM emergency_event WHERE event_type IN (1, 2) AND status = 0 LIMIT 1")).scalar()
            if busy:
                logger.info("Fire alarm input on controller %s — fire mode already active", controller.id)
                return
            from .emergency_service import emergency_service
            logger.warning("FIRE ALARM input tripped on controller %s (%s) — activating fire mode", controller.id, controller.name)
            asyncio.run(emergency_service.activate_fire_mode(
                zone_id=None, location_id=None, muster_zone_ids=None, action="activate",
                reason=f"Fire alarm panel ({controller.name} AUX IN {controller.fire_alarm_input})",
                initiated_by=None, db=db))
        except Exception as e:  # noqa: BLE001
            logger.error("Fire alarm → fire mode failed: %s", e)
        finally:
            db.close()
    threading.Thread(target=run, daemon=True).start()


def _recalc_later(emp_code: str, punch_time: datetime) -> None:
    """Recalculate that person's day in the background (same as an ADMS punch)."""
    import threading

    def run():
        try:
            from ..api.adms_protocol import _async_recalculate
            from .attendance_calculation_service import SITE_TZ
            from datetime import timezone as _tz
            pt = punch_time if punch_time.tzinfo else punch_time.replace(tzinfo=_tz.utc)
            asyncio.run(_async_recalculate({emp_code}, {pt.astimezone(SITE_TZ).strftime("%Y-%m-%d")}))
        except Exception as e:  # noqa: BLE001
            logger.warning("Attendance recalc after controller tap failed for %s: %s", emp_code, e)
    threading.Thread(target=run, daemon=True).start()


def poll_controller_once(controller: AccessController, db: Session) -> Dict[str, object]:
    """Pull buffered realtime events from one controller and ingest them.

    Never raises: a transport/protocol failure marks the controller offline and
    is reported back, so a single bad panel can never take down the poller."""
    result: Dict[str, object] = {"controller_id": controller.id, "events": 0, "zone_updates": {}}
    all_updates: Dict[int, int] = {}
    try:
        events: List[C3Event] = _fetch_rtlog(controller, db)
        for ev in events:
            all_updates.update(ingest_event(controller, ev, db))
        controller.status = "online"
        controller.last_seen = datetime.utcnow()
        controller.last_error = None
        result["events"] = len(events)
        _sync_clock_daily(controller)
    except Exception as exc:  # noqa: BLE001 — isolate per-controller failures
        controller.status = "error"
        controller.last_error = str(exc)[:255]
        result["error"] = str(exc)
        logger.warning("Controller %s poll failed: %s", controller.id, exc)
    db.commit()
    result["zone_updates"] = all_updates
    return result


def _poll_controller_by_id(controller_id: int) -> Dict[str, object]:
    """Fresh-session poll of one controller — safe to run in a worker thread.

    Each poll owns its own Session so a blocking C3 connect can run off the event
    loop without sharing a session across threads.
    """
    from ..core.database import SessionLocal
    db = SessionLocal()
    try:
        ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
        if not ctrl:
            return {"controller_id": controller_id, "error": "not found"}
        return poll_controller_once(ctrl, db)
    finally:
        db.close()


async def controller_poller_loop() -> None:
    """Leader-only loop: poll every ``poll_enabled`` access controller for buffered
    C3/inBio events on its own ``poll_interval_sec``, feeding the SAME zone engine
    the ADMS readers use. This is what makes a badge at a controller-wired reader
    update ``personnel.current_zone_id`` + zone occupancy in near-real time — the
    pull-side equivalent of the ADMS push path.

    Each due controller is polled off the event loop (``asyncio.to_thread``) with a
    fresh session, so a slow or offline panel can neither block the loop nor corrupt
    a shared session. Runs under ``_supervised`` so a crash auto-restarts.
    """
    logger.info("Access-controller poller started — first check in 5s, then per-controller interval")
    last_polled: Dict[int, float] = {}
    first = True
    while True:
        await asyncio.sleep(5 if first else 2)  # base tick; per-controller interval gates actual polls
        first = False
        try:
            from ..core.database import SessionLocal
            db = SessionLocal()
            try:
                enabled = db.query(
                    AccessController.id, AccessController.poll_interval_sec
                ).filter(AccessController.poll_enabled == True).all()  # noqa: E712
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001 — a listing hiccup must not kill the loop
            logger.error("controller poller: could not list controllers: %s", exc)
            continue

        now = _time.monotonic()
        for cid, interval in enabled:
            interval = interval or 5
            if now - last_polled.get(cid, 0.0) >= interval:
                last_polled[cid] = now
                try:
                    await asyncio.to_thread(_poll_controller_by_id, cid)
                except Exception as exc:  # noqa: BLE001 — isolate per-controller failures
                    logger.warning("controller %s poll error: %s", cid, exc)


# Sanity bound — a real panel won't address more doors than this; protects against
# a garbled door id auto-creating hundreds of bogus ports during learn mode.
MAX_LEARN_DOORS = 16


def _ensure_reader(controller: AccessController, door_no: int, direction: str,
                   db: Session) -> tuple[AccessReader, bool]:
    """Find the reader port for (controller, door_no, direction), creating it if a
    real punch arrives on a port we hadn't registered. Returns (reader, created)."""
    reader = (
        db.query(AccessReader)
        .filter(
            AccessReader.controller_id == controller.id,
            AccessReader.door_no == door_no,
            AccessReader.direction == direction,
        )
        .first()
    )
    if reader:
        return reader, False
    reader = AccessReader(
        controller_id=controller.id,
        door_no=door_no,
        direction=direction,
        name=f"Door {door_no} {'Entry' if direction == 'ENTRY' else 'Exit'}",
        status="active",
    )
    db.add(reader)
    db.flush()  # assign id without ending the transaction
    return reader, True


def learn_controller_ports(controller: AccessController, db: Session) -> Dict[str, object]:
    """Learn-mode poll: pull buffered events and surface which physical port fired.

    Unlike `poll_controller_once`, this does NOT feed zone occupancy — presenting a
    card to identify a reader must not move people in/out of zones. It auto-creates
    any reader port that fires but wasn't registered yet, so the operator literally
    *sees the ports the readers are wired to* as they badge at each one."""
    result: Dict[str, object] = {"controller_id": controller.id, "events": [], "created": 0}
    fired: List[dict] = []
    created = 0
    try:
        events: List[C3Event] = _fetch_rtlog(controller, db)

        for ev in events:
            door_no = int(ev.door_id)
            if door_no < 1 or door_no > MAX_LEARN_DOORS:
                continue
            direction = _direction_from_inout(ev.in_out)
            reader, was_created = _ensure_reader(controller, door_no, direction, db)
            created += 1 if was_created else 0
            when = ev.time or datetime.utcnow()
            reader.last_event_at = when
            fired.append({
                "door_no": door_no,
                "direction": direction,
                "identity": ev.pin or ev.card_no,
                "time": when.isoformat(),
                "reader_id": reader.id,
                "zone_id": reader.zone_id,
                "created": was_created,
            })

        controller.status = "online"
        controller.last_seen = datetime.utcnow()
        controller.last_error = None
        result["events"] = fired
        result["created"] = created
    except Exception as exc:  # noqa: BLE001 — isolate per-controller failures
        controller.status = "error"
        controller.last_error = str(exc)[:255]
        result["error"] = str(exc)
        logger.warning("Controller %s learn-poll failed: %s", controller.id, exc)
    db.commit()
    return result
