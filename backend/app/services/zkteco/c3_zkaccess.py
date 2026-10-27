"""
Pure-Python C3 driver via the `zkaccess-c3` library (import name `c3`).

This is the STANDALONE path for the ZKTeco C3-200/C3-400 (and inBio) panels: a
native-Python implementation of the C3 PULL protocol over TCP — no plcommpro.dll,
no Windows, no Wine, no sidecar. Runs inside the POB Docker container. POB replaces
"ESS" as the software talking to the panels, so it is the sole reader.

License note: `zkaccess-c3` is GPLv3 (embedded per project decision).

We adapt its records to POB's existing `C3Event` so the ingest/zone engine is
unchanged. Field mapping is taken from the library's real API (introspected, not
guessed): EventRecord{card_no, pin, port_nr(=door), event_type, in_out_state,
time_second}; InOutDirection ENTRY=0 / EXIT=3.
"""

from __future__ import annotations

import logging
from typing import List

from .c3_controller import C3Event

logger = logging.getLogger(__name__)

# C3 PULL "SetDeviceData" write op. The pure-Python library implements GETDATA (8)
# but not the write; this is the control code that follows it in the protocol.
# VERIFY the write framing against the customer's C3-200/C3-400 before production
# enrolment — until then every write is guarded so a wrong frame only fails a record.
_C3_CMD_SETDATA = 9


def _encode_field(ftype: str, value) -> bytes:
    """Encode one field value as [size_byte][value_bytes] — the same field-size
    framing the panel uses when it returns data (see the library's get_device_data)."""
    if ftype == "i":
        try:
            iv = int(value)
        except (TypeError, ValueError):
            iv = 0
        b = iv.to_bytes(4, "little").rstrip(b"\x00") or b"\x00"
        return bytes([len(b)]) + b
    s = str(value if value is not None else "").encode("ascii", errors="ignore")
    return bytes([len(s)]) + s


def sdk_available() -> bool:
    """True if the pure-Python zkaccess-c3 library is importable."""
    try:
        import c3  # noqa: F401
        return True
    except Exception:
        return False


def _to_c3event(rec) -> C3Event:
    from c3 import consts
    from c3.rtlog import C3DateTime
    ts = None
    if getattr(rec, "time_second", 0):
        try:
            ts = C3DateTime.from_value(rec.time_second)
        except Exception:
            ts = None
    # Normalise the library's InOutDirection (ENTRY=0, EXIT=3) to POB's 0/1 convention
    in_out = 1 if rec.in_out_state == consts.InOutDirection.EXIT else 0
    return C3Event(
        time=ts,
        card_no=str(rec.card_no) if getattr(rec, "card_no", 0) else None,
        pin=str(rec.pin) if getattr(rec, "pin", 0) else None,
        door_id=int(getattr(rec, "port_nr", 0) or 0),
        event_type=int(rec.event_type),
        in_out=in_out,
        verify_type=int(getattr(rec, "verified", 0) or 0),
        raw={"src": "zkaccess-c3"},
    )


class ZKAccessC3Client:
    """Context-manager wrapper over zkaccess-c3 for one panel."""

    def __init__(self, ip: str, port: int = 4370, password: str = ""):
        self.ip, self.port, self.password = ip, port or 4370, password or ""
        self._c3 = None

    def __enter__(self) -> "ZKAccessC3Client":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()

    def connect(self) -> None:
        from c3 import C3
        self._c3 = C3(self.ip, self.port)
        ok = self._c3.connect(self.password or None)
        if not ok:
            raise ConnectionError(f"zkaccess-c3: could not connect to {self.ip}:{self.port}")

    def disconnect(self) -> None:
        try:
            if self._c3 is not None:
                self._c3.disconnect()
        finally:
            self._c3 = None

    def get_rt_log(self) -> List[C3Event]:
        """Realtime access events (door/alarm status records are filtered out)."""
        records = self._c3.get_rt_log()
        return [_to_c3event(r) for r in records if getattr(r, "is_event", lambda: False)()]

    def open_door(self, door_id: int = 1, duration: int = 5) -> bool:
        from c3 import consts
        from c3.controldevice import ControlDeviceOutput
        self._c3.control_device(
            ControlDeviceOutput(int(door_id), consts.ControlOutputAddress.DOOR_OUTPUT, int(duration))
        )
        return True

    def aux_output(self, aux_no: int = 1, duration: int = 255) -> bool:
        """Switch an AUX output (siren / strobe wired to the panel).
        duration 255 = stay on, 0 = off, 1-254 = seconds on."""
        from c3 import consts
        from c3.controldevice import ControlDeviceOutput
        self._c3.control_device(
            ControlDeviceOutput(int(aux_no), consts.ControlOutputAddress.AUX_OUTPUT, int(duration))
        )
        return True

    # ── Enrolment: push users/cards so personnel can badge (write path) ────────
    def push_users(self, users, door_nos=None, timezone_id: int = 1) -> dict:
        """Upload user + card records to the panel so they can badge at its doors.

        users: iterable of dicts {pin, card_no, name?, group?}. door_nos: door
        numbers to authorise (default = door 1). Returns {pushed, failed:[...]}.

        The pure-Python driver has no write op, so this issues SetDeviceData over the
        library transport against the `user` and `userauthorize` data tables (read
        live from the panel's own config), encoding records in the panel's field-size
        format. Every record is guarded: a rejected/mis-framed write fails only that
        record and is reported — it can never crash the backend.
        """
        cfgs = {cf.name.lower(): cf for cf in self._c3._get_device_data_cfg()}
        ucfg = cfgs.get("user")
        acfg = cfgs.get("userauthorize")
        if ucfg is None:
            raise RuntimeError("panel exposes no 'user' data table (has: %s)" % ",".join(cfgs) or "none")
        pushed, failed = 0, []
        for u in users:
            pin = str(u.get("pin") or "").strip()
            if not pin:
                continue
            try:
                rec = {
                    "pin": pin,
                    "cardno": str(u.get("card_no") or ""),
                    "name": str(u.get("name") or "")[:24],
                    "group": u.get("group") or 1,
                }
                if u.get("expire"):
                    # Removal = validity ended yesterday; the panel refuses the user.
                    rec.update(starttime=20000101, endtime=int(u["expire"]))
                self._set_record(ucfg, rec)
                if acfg is not None and not u.get("expire") and door_nos:
                    # AuthorizeDoorId is a BITMASK (door1=1, door2=2, door3=4, door4=8) —
                    # one record for all doors. Writing the door number itself (as before)
                    # made "door 3" mean doors 1+2.
                    mask = 0
                    for dn in (door_nos or [1]):
                        mask |= 1 << (int(dn) - 1)
                    self._set_record(acfg, {
                        "pin": pin,
                        "authorizetimezoneid": int(timezone_id),
                        "authorizedoorid": mask,
                    })
                pushed += 1
            except Exception as exc:  # noqa: BLE001
                failed.append({"pin": pin, "error": str(exc)[:200]})
        return {"pushed": pushed, "failed": failed}

    def _set_record(self, cfg, values: dict) -> None:
        """SetDeviceData for one record. `values` are keyed by lowercased field name;
        only fields the panel actually exposes are sent. VERIFY framing on hardware."""
        fields = sorted((f for f in cfg.fields if f.name.lower() in values), key=lambda f: f.index)
        if not fields:
            raise RuntimeError("no writable fields matched on table '%s'" % cfg.name)
        payload = bytearray([cfg.index, len(fields)])
        payload += bytes(f.index for f in fields)
        for f in fields:
            payload += _encode_field(f.type, values[f.name.lower()])
        self._c3._send_receive(_C3_CMD_SETDATA, list(payload))

    def info(self) -> dict:
        c = self._c3
        return {"serial": getattr(c, "serial_number", None), "name": getattr(c, "device_name", None),
                "firmware": getattr(c, "firmware_version", None), "doors": getattr(c, "nr_of_locks", None)}


def test_connection(ip: str, port: int = 4370, password: str = "") -> dict:
    """Best-effort connect + realtime-log read via the pure-Python driver. Never raises."""
    try:
        with ZKAccessC3Client(ip, port, password) as c:
            events = c.get_rt_log()
            meta = c.info()
        return {"success": True, "message": "Connected via zkaccess-c3 (standalone)",
                "events_buffered": len(events), **meta}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


def enroll_users(ip: str, users, door_nos=None, port: int = 4370, password: str = "",
                 timezone_id: int = 1) -> dict:
    """Connect and push user/card records to a panel so personnel can badge.
    Never raises — returns {success, pushed, failed} or {success: False, error}."""
    try:
        with ZKAccessC3Client(ip, port, password) as c:
            res = c.push_users(users, door_nos=door_nos, timezone_id=timezone_id)
        return {"success": True, **res}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc),
                "note": "C3 SetDeviceData write is verify-on-hardware — confirm the write "
                        "framing against the C3-200/C3-400 panel."}


def probe(ip: str, port: int = 4370, password: str = "") -> dict:
    """Step-by-step diagnostics via the pure-Python driver (the real one in prod):
    TCP reachable → C3 driver present → session handshake → realtime-log sample.
    Never raises; returns the same shape the Probe modal renders."""
    import socket
    report = {"ip": ip, "port": port, "steps": [], "driver": "zkaccess-c3 (pure Python)"}

    def step(name, ok, detail=""):
        report["steps"].append({"step": name, "ok": ok, "detail": str(detail)[:400]})

    try:
        with socket.create_connection((ip, port), timeout=4):
            step("tcp_connect", True, f"{ip}:{port} reachable")
    except Exception as exc:  # noqa: BLE001
        step("tcp_connect", False, exc)
        report["summary"] = "Panel not reachable on the LAN — check IP/port/firewall."
        return report

    if not sdk_available():
        step("c3_driver", False, "zkaccess-c3 not importable")
        report["summary"] = "The pure-Python C3 driver is missing (unexpected — check the image build)."
        return report
    step("c3_driver", True, "pure-Python zkaccess-c3 driver available")

    try:
        with ZKAccessC3Client(ip, port, password) as c:
            step("connect", True, "session established")
            events = c.get_rt_log()
            meta = c.info()
            report["rtlog_parsed_count"] = len(events)
            step("get_rtlog", True,
                 f"{len(events)} event(s)"
                 + (f"; device serial {meta.get('serial')}, fw {meta.get('firmware')}" if meta.get('serial') else ""))
        report["summary"] = ("Connected via the pure-Python C3 driver. "
                             "Present a card at a reader and re-probe to see live events.")
    except Exception as exc:  # noqa: BLE001
        step("connect", False, exc)
        report["summary"] = f"Reachable, but the C3 session failed: {exc}"
    return report
