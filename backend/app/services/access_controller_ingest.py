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


def ingest_event(controller: AccessController, event: C3Event, db: Session) -> Dict[int, int]:
    """Route one controller event to zone tracking.

    Returns {zone_id: new_occupancy} for changed zones, or {} if the event could
    not be mapped (unconfigured reader, no zone, or no identifiable person)."""
    # Lazy import: avoids a circular import at module load (adms_protocol imports
    # plenty of models). The zone engine lives there and is shared on purpose.
    from ..api.adms_protocol import _handle_zone_access

    direction = _direction_from_inout(event.in_out)

    reader = (
        db.query(AccessReader)
        .filter(
            AccessReader.controller_id == controller.id,
            AccessReader.door_no == event.door_id,
            AccessReader.direction == direction,
            AccessReader.status == "active",
        )
        .first()
    )
    if not reader:
        logger.debug(
            "Controller %s door %s/%s has no active reader mapping — event ignored",
            controller.id, event.door_id, direction,
        )
        return {}
    if not reader.zone_id:
        logger.warning(
            "Reader %s (controller %s door %s/%s) has no zone — event ignored",
            reader.id, controller.id, event.door_id, direction,
        )
        return {}

    emp_code = event.pin or event.card_no
    if emp_code:
        # The panel reports the reader PIN (SeamlessHR Attendance ID) — map it back
        # to the employee code, exactly as the ADMS path does.
        from .device_pin import resolve_emp_code
        emp_code = resolve_emp_code(db, emp_code)
    if not emp_code:
        logger.debug("Controller %s event has no pin/cardno — cannot identify person", controller.id)
        return {}

    punch_time = event.time or datetime.utcnow()
    # Synthetic device SN keeps the audit trail traceable to the exact reader-port.
    device_sn = f"AC{controller.id}-D{event.door_id}-{direction[0]}"

    # _handle_zone_access only reads `.zone_id` and `.alias` off the terminal; a
    # lightweight shim lets us reuse the shared engine without an iclock_terminal.
    shim = SimpleNamespace(zone_id=reader.zone_id, alias=reader.name or device_sn)

    updates = _handle_zone_access(emp_code, device_sn, punch_time, shim, direction, db)

    reader.last_event_at = punch_time
    db.commit()
    return updates


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
