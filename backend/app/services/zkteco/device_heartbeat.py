"""
ZKTeco Device Heartbeat

Three responsibilities:
1. Direct-mode (ZKLib) devices — TCP probe every 5 s, update devices.status immediately.
2. ADMS-mode terminals — check last_activity age; if stale > ADMS_STALE_SECS → OFFLINE.
3. Auto-discovery — scan known subnets every AUTO_SCAN_INTERVAL seconds for new ZKLib
   readers; auto-register new ones so the admin never has to add them manually.
"""

import asyncio
import ipaddress
import logging
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import text, or_
from ...core.database import SessionLocal
from ...models.device import Device, DeviceStatus
from ...models.biotime_models import IClockTerminal, MusteringEvent

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL  = 5      # seconds between full direct-device sweeps
CONNECT_TIMEOUT     = 3.0    # TCP connect timeout per device
ADMS_STALE_SECS     = 90     # minimum seconds before marking an ADMS terminal offline
MUSTER_STALE_SECS   = 30     # tighter floor for readers in a zone with an active muster event
AUTO_SCAN_INTERVAL  = 60     # seconds between subnet scans for new readers
ZKTECO_PORT         = 4370

# State constants (must match adms_protocol.py)
STATE_PENDING  = 0
STATE_APPROVED = 1
STATE_REJECTED = 2
STATE_OFFLINE  = 3


# ── TCP helpers ───────────────────────────────────────────────────────────────

async def _tcp_reachable(ip: str, port: int) -> bool:
    """Return True if a TCP connection to ip:port succeeds within CONNECT_TIMEOUT."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=CONNECT_TIMEOUT,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


# ── DB helpers ────────────────────────────────────────────────────────────────

def _db_get_direct_targets() -> list:
    """Devices registered in the `devices` table with a direct/both connection mode."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Device)
            .filter(
                Device.ip_address.isnot(None),
                Device.connection_mode.in_(["direct", "both"]),
            )
            .all()
        )
        return [(d.id, d.ip_address, d.port or ZKTECO_PORT,
                 d.serial_number or f"IP-{d.ip_address}") for d in rows]
    finally:
        db.close()


def _db_get_adms_terminals() -> list:
    """
    Return all non-rejected terminals for staleness checking.
    Includes ADMS, direct, and unknown connection modes so no device is left
    stuck in state=3 after a server restart.
    Returns (id, sn, ip_address, state, last_activity, heartbeat_interval, zone_id).
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(IClockTerminal)
            .filter(IClockTerminal.state.notin_([STATE_REJECTED]),
                    # C3/inBio reader ports are mirrored as terminals (connection_mode
                    # 'controller'); they never heartbeat — their panel's health is
                    # watched by the controller poller — so never age them offline.
                    or_(IClockTerminal.connection_mode.is_(None),
                        IClockTerminal.connection_mode != "controller"))
            .all()
        )
        return [
            (t.id, t.sn, t.ip_address, t.state, t.last_activity,
             t.heartbeat_interval or 30, t.zone_id)
            for t in rows
        ]
    finally:
        db.close()


def _db_get_active_muster_zone_ids() -> set:
    """Zone IDs currently under an active muster event (status == 0 = in-progress)."""
    db = SessionLocal()
    try:
        rows = db.query(MusteringEvent.zone_id, MusteringEvent.zone_ids).filter(
            MusteringEvent.status == 0
        ).all()
        zone_ids: set = set()
        for zid, zid_list in rows:
            if zid is not None:
                zone_ids.add(zid)
            if zid_list:
                zone_ids.update(z for z in zid_list if z is not None)
        return zone_ids
    finally:
        db.close()


def _db_update_direct(device_id: int, sn: str, reachable: bool, now: datetime) -> None:
    """Update devices.status + iclock_terminal.state for a direct-mode device."""
    new_status = DeviceStatus.ONLINE if reachable else DeviceStatus.OFFLINE
    new_state  = STATE_APPROVED if reachable else STATE_OFFLINE

    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return
        prev_status = device.status
        device.status = new_status
        if reachable:
            device.last_seen = now

        term = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
        if term and term.state != STATE_REJECTED:
            # Update state regardless of PENDING: a terminal that's in the `devices`
            # table is already known to the system and its state should follow reachability.
            if term.state != new_state:
                term.state = new_state
            if reachable:
                term.last_activity = now

        db.commit()

        if prev_status != new_status:
            logger.info("Heartbeat [direct] %s → %s  (%s)", sn,
                        new_status.value, device.ip_address)
            if new_status == DeviceStatus.ONLINE:
                _on_device_came_online(sn, now)

    except Exception as exc:
        logger.error("Heartbeat DB error for %s: %s", sn, exc)
        db.rollback()
    finally:
        db.close()


def _db_update_adms(terminal_id: int, sn: str, online: bool, now: datetime) -> None:
    """Update iclock_terminal + devices for a terminal based on last_activity age."""
    new_state = STATE_APPROVED if online else STATE_OFFLINE

    db = SessionLocal()
    try:
        term = db.query(IClockTerminal).filter(IClockTerminal.id == terminal_id).first()
        if not term or term.state == STATE_REJECTED:
            return

        # Allow PENDING devices that are actively heartbeating to be promoted to
        # APPROVED automatically — waiting for manual admin approval would leave them
        # showing offline even while physically connected and punching.
        # Manual rejection is still respected (STATE_REJECTED handled above).
        if term.state == STATE_PENDING and online:
            term.state = STATE_APPROVED
            db.commit()
            logger.info("Heartbeat [ADMS] %s auto-approved (actively heartbeating)", sn)

        elif term.state != STATE_PENDING:
            changed = (term.state != new_state)
            if changed:
                term.state = new_state
                db.commit()
                logger.info("Heartbeat [ADMS] %s → %s (last_activity age)",
                            sn, "ONLINE" if online else "OFFLINE")

                # Alert safety officers if a mustering reader loses contact during
                # an active muster event — personnel punching at this reader will
                # buffer on the device and may be missed until it reconnects.
                if not online and term.zone_id:
                    active_muster = db.query(MusteringEvent).filter(
                        MusteringEvent.status == 0,
                    ).first()
                    if active_muster:
                        dedup_key = f"muster_reader_offline_{sn}_{active_muster.id}"
                        alert_title = "Mustering Reader Offline During Active Muster"
                        alert_msg = (
                            f"Reader {term.alias or sn} (SN: {sn}) in zone "
                            f"{term.zone_id} has gone offline during active mustering "
                            f"event #{active_muster.id}. Personnel punching at this "
                            f"reader will NOT be marked safe until the device reconnects."
                        )
                        logger.critical("SAFETY ALERT: %s", alert_msg)
                        # Persist to sys_notifications so the alert survives even if
                        # the SSE broadcast fails (executor thread may have no event loop)
                        from datetime import timedelta as _td
                        db.execute(text("""
                            INSERT INTO sys_notifications
                                (dedup_key, notification_type, title, message, priority, expires_at)
                            VALUES (:dk, :nt, :title, :msg, :pri, NOW() + INTERVAL '24 hours')
                            ON CONFLICT (dedup_key) DO NOTHING
                        """), {
                            "dk": dedup_key,
                            "nt": "mustering_reader_offline",
                            "title": alert_title,
                            "msg": alert_msg,
                            "pri": "critical",
                        })
                        db.commit()
                        from ...api.notifications import notify_sync
                        notify_sync({
                            "type": "mustering_reader_offline",
                            "priority": "critical",
                            "title": alert_title,
                            "message": alert_msg,
                            "dedup_key": dedup_key,
                        })

        # Sync to devices table so the UI shows the right status
        _sync_terminal_to_devices(db, term, online, now)

    except Exception as exc:
        logger.error("Heartbeat ADMS DB error for %s: %s", sn, exc)
        db.rollback()
    finally:
        db.close()


_DOCKER_GATEWAY_IPS = frozenset({
    '192.168.65.1', '172.17.0.1', '172.18.0.1', '172.19.0.1', '172.20.0.1',
})


def _sync_terminal_to_devices(db, term: IClockTerminal, online: bool, now: datetime) -> None:
    """
    Ensure an iclock_terminal row has a matching entry in the `devices` table.
    Creates one if missing; updates status and hardware stats on every call.
    """
    if not term.ip_address or (term.connection_mode or "").lower() == "controller":
        return

    new_status = DeviceStatus.ONLINE if online else DeviceStatus.OFFLINE
    # Use terminal IP only when it is a real device address, not a Docker gateway.
    display_ip = term.ip_address if term.ip_address not in _DOCKER_GATEWAY_IPS else None

    device = db.query(Device).filter(Device.serial_number == term.sn).first()
    if not device:
        device = Device(
            name             = term.alias or term.device_name or f"Terminal-{term.sn}",
            serial_number    = term.sn,
            ip_address       = display_ip,
            port             = ZKTECO_PORT,
            connection_mode  = "adms",
            status           = new_status,
            auto_poll        = False,
            poll_interval_sec= 300,
            last_seen        = now if online else None,
        )
        db.add(device)
        db.commit()
        logger.info("Heartbeat: auto-created devices row for ADMS terminal %s (%s)",
                    term.sn, term.ip_address)
    else:
        if device.status != new_status:
            device.status = new_status
        if online:
            device.last_seen = now
        # Keep IP in sync — skip Docker gateway IPs (they are not real device addresses)
        if display_ip and device.ip_address != display_ip:
            device.ip_address = display_ip

    # Sync hardware stats from iclock_terminal → devices so the UI
    # shows accurate enrolled-user / fingerprint / firmware data.
    stat_map = [
        ('user_count',  'user_count'),
        ('fp_count',    'fp_count'),
        ('face_count',  'face_count'),
        ('mac_address', 'mac_address'),
        ('fw_ver',      'firmware_version'),
    ]
    for term_attr, dev_attr in stat_map:
        val = getattr(term, term_attr, None)
        if val is not None and val != 0 and hasattr(device, dev_attr):
            setattr(device, dev_attr, val)

    db.commit()


def _on_device_came_online(sn: str, now: datetime) -> None:
    """Trigger immediate attendance pull + time sync when a device reconnects."""
    try:
        from ..device_poller import request_immediate_poll
        request_immediate_poll(sn)
    except Exception:
        pass

    # Queue an ADMS clock-correction so the device fixes its clock immediately.
    # Use the shared helper (SET OPTIONS DateTime=<enc>) — push firmware rejects the
    # ZKLib-style "DATE TIME <str>" as UNKNOWN CMD. Skip direct-only readers: they
    # don't poll the ADMS queue, so a queued command would just black-hole (this
    # reconnect path also fires for flapping ADMS readers, which is how thousands of
    # stale commands accumulated before).
    try:
        from ...api.adms_protocol import queue_clock_sync, _is_direct_only
        db2 = SessionLocal()
        try:
            if _is_direct_only(sn, db2):
                logger.debug("Heartbeat: %s is direct-only — skipping ADMS clock queue", sn)
            else:
                queue_clock_sync(sn, db2)
                logger.info("Heartbeat: queued clock sync for %s on reconnect", sn)
        finally:
            db2.close()
    except Exception as te:
        logger.warning("Heartbeat: failed to queue clock sync for %s: %s", sn, te)


# ── Auto-discovery ────────────────────────────────────────────────────────────

def _db_known_ips() -> set:
    """Return all IPs already registered in the devices table."""
    db = SessionLocal()
    try:
        rows = db.query(Device.ip_address).filter(Device.ip_address.isnot(None)).all()
        return {r[0] for r in rows}
    finally:
        db.close()


def _get_local_interface_subnets() -> list:
    """
    Return (ip, prefix_len) for every non-loopback, non-link-local IPv4 interface.

    Tries four methods in order so the function works on Linux, macOS/BSD, Docker,
    and any environment where subprocess commands might be unavailable:

    1. `ip -4 addr show`  — Linux / Docker; gives IP + exact prefix length
    2. `ifconfig`         — macOS / BSD / legacy Linux; parses hex or dotted netmask
    3. Routing socket     — platform-agnostic; asks the OS which local IP routes to
                            the internet without sending any real traffic
    4. socket hostname    — last-resort fallback; assumes /24
    """
    import re, subprocess, socket
    results: list = []

    # ── Method 1: Linux / Docker ──────────────────────────────────────────────
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show"], stderr=subprocess.DEVNULL, timeout=5
        ).decode()
        for m in re.finditer(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", out):
            ip, prefix = m.group(1), int(m.group(2))
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                results.append((ip, prefix))
    except Exception:
        pass

    # ── Method 2: macOS / BSD (`ifconfig` with hex or dotted netmask) ────────
    if not results:
        try:
            out = subprocess.check_output(
                ["ifconfig"], stderr=subprocess.DEVNULL, timeout=5
            ).decode()
            for m in re.finditer(
                r"inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+(0x[0-9a-fA-F]{8}|\d+\.\d+\.\d+\.\d+)",
                out,
            ):
                ip, mask = m.group(1), m.group(2)
                if ip.startswith("127.") or ip.startswith("169.254."):
                    continue
                try:
                    if mask.startswith("0x"):
                        mask_int = int(mask, 16)
                    else:
                        p = [int(x) for x in mask.split(".")]
                        mask_int = (p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]
                    prefix = bin(mask_int & 0xFFFFFFFF).count("1")
                except Exception:
                    prefix = 24
                results.append((ip, prefix))
        except Exception:
            pass

    # ── Method 3: routing socket (no data sent, works everywhere) ────────────
    # Always run this so multi-homed machines include the primary outbound IP even
    # if Methods 1/2 already ran — e.g. Docker containers with host networking.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 53))
            routing_ip = s.getsockname()[0]
        if routing_ip and not routing_ip.startswith("127."):
            if not any(ip == routing_ip for ip, _ in results):
                results.append((routing_ip, 24))
    except Exception:
        pass

    # ── Method 4: socket hostname last-resort ─────────────────────────────────
    if not results:
        try:
            _, _, ip_list = socket.gethostbyname_ex(socket.gethostname())
            for ip in ip_list:
                if not ip.startswith("127."):
                    results.append((ip, 24))
        except Exception:
            pass

    return results


def _get_local_interface_ips() -> list:
    """Backward-compat wrapper — returns only the IP strings."""
    return [ip for ip, _ in _get_local_interface_subnets()]


def _is_containerized() -> bool:
    """
    True if this process is running inside a Docker/Kubernetes container.

    Matters because `_get_local_interface_subnets()` reflects the container's
    network namespace (e.g. the `pob_internal` bridge, typically 172.x), not
    the customer's physical reader LAN (typically 192.168.x or 10.x). Scanning
    the container's own subnet for "new readers" silently finds nothing —
    this was the root cause of new/unknown readers never being auto-discovered
    in the production deployment.
    """
    try:
        if os.path.exists("/.dockerenv"):
            return True
        with open("/proc/1/cgroup", "rt") as f:
            content = f.read()
            if "docker" in content or "kubepods" in content:
                return True
    except Exception:
        pass
    return False


_warned_missing_scan_subnets = False


def _db_get_subnets_to_scan() -> list:
    """
    Derive subnets to scan from:
    1. DEVICE_SCAN_SUBNETS env var — comma-separated reader-LAN ranges. This is
       the ONLY reliable source in a containerized deployment, since the
       container's own interfaces are not on the customer's device LAN.
    2. IPs of devices already in the `devices` table (catch moved DHCP addresses)
    3. IPs of terminals in `iclock_terminal`
    4. All IPv4 interfaces on this server — useful on bare-metal/host-network
       deployments, harmless (just wasted scan time) inside a container.
    Returns a deduplicated list of IPv4Network objects.

    Logs a loud, one-time CRITICAL warning if running in a container with no
    DEVICE_SCAN_SUBNETS configured and no devices registered yet — that
    combination means brand-new readers can NEVER be auto-discovered.
    """
    global _warned_missing_scan_subnets
    db = SessionLocal()
    try:
        device_ips = [r[0] for r in db.query(Device.ip_address).filter(Device.ip_address.isnot(None)).all()]
        from sqlalchemy import text as _sa_text
        term_ips = [r[0] for r in db.execute(
            _sa_text("SELECT ip_address FROM iclock_terminal WHERE ip_address IS NOT NULL")
        ).fetchall()]

        nets = set()

        # Local interfaces — use the actual prefix length so we scan exactly the
        # network this server is on. Reliable on bare metal/host networking;
        # reflects the container's bridge (not the reader LAN) when containerized.
        for ip, prefix in _get_local_interface_subnets():
            try:
                nets.add(ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False))
            except Exception:
                pass

        # Registered device / terminal IPs — no mask stored, assume /24
        for ip in set(device_ips) | set(term_ips):
            try:
                nets.add(ipaddress.IPv4Network(f"{ip}/24", strict=False))
            except Exception:
                pass

        # Drop loopback and link-local
        nets = {n for n in nets if not n.is_loopback and not n.is_link_local}

        # Extra ranges from env var — the only reliable source in containers
        extra = os.getenv("DEVICE_SCAN_SUBNETS", "")
        explicit_nets = set()
        for segment in extra.split(","):
            segment = segment.strip()
            if segment:
                try:
                    net = ipaddress.IPv4Network(segment, strict=False)
                    nets.add(net)
                    explicit_nets.add(net)
                except Exception:
                    logger.warning("Invalid DEVICE_SCAN_SUBNETS entry: %s", segment)

        if _is_containerized() and not explicit_nets and not device_ips and not term_ips and not _warned_missing_scan_subnets:
            _warned_missing_scan_subnets = True
            logger.critical(
                "AUTO-DISCOVERY MISCONFIGURED: this backend is running in a container "
                "with no DEVICE_SCAN_SUBNETS set and no readers registered yet. The "
                "container's own network interfaces (%s) are NOT the customer's reader "
                "LAN, so new readers will never be found automatically. Set "
                "DEVICE_SCAN_SUBNETS=<reader-lan-cidr> (e.g. 192.168.1.0/24) in .env.prod "
                "and restart, or register the first reader manually with its IP.",
                [str(n) for n in nets] or "none detected",
            )

        logger.debug("Scan subnets: %s", [str(n) for n in nets])
        return list(nets)
    finally:
        db.close()


def get_network_diagnostics() -> dict:
    """
    Snapshot of everything relevant to "why can't the server see my readers" —
    used by the /api/device/network-diagnostics endpoint so ops can self-check
    a new deployment before declaring it broken.
    """
    import os as _os
    local_subnets = [f"{ip}/{prefix}" for ip, prefix in _get_local_interface_subnets()]
    scan_subnets = [str(n) for n in _db_get_subnets_to_scan()]
    explicit = _os.getenv("DEVICE_SCAN_SUBNETS", "")
    containerized = _is_containerized()

    db = SessionLocal()
    try:
        device_rows = db.query(Device.id, Device.name, Device.ip_address, Device.serial_number,
                                Device.connection_mode, Device.status).all()
    finally:
        db.close()

    devices = [
        {
            "id": d.id, "name": d.name, "ip_address": d.ip_address,
            "serial_number": d.serial_number, "connection_mode": d.connection_mode,
            "status": d.status.value if d.status else None,
        }
        for d in device_rows
    ]

    warning = None
    if containerized and not explicit.strip() and not devices:
        warning = (
            "Running in a container with DEVICE_SCAN_SUBNETS unset and zero devices "
            "registered — new readers cannot be auto-discovered. Set "
            "DEVICE_SCAN_SUBNETS to the reader LAN's CIDR (e.g. 192.168.1.0/24) in "
            ".env.prod and restart the backend."
        )

    return {
        "containerized": containerized,
        "local_interface_subnets": local_subnets,
        "device_scan_subnets_env": explicit or None,
        "effective_scan_subnets": scan_subnets,
        "registered_devices": devices,
        "warning": warning,
    }


def _db_register_new_device(ip: str, sn: str, now: datetime) -> None:
    """Create or update a `devices` entry for a discovered ZKLib reader."""
    from sqlalchemy import text as sa_text
    db = SessionLocal()
    try:
        # Check by SN first — device may have moved to a new IP
        by_sn = db.query(Device).filter(Device.serial_number == sn).first()
        if by_sn:
            if by_sn.ip_address != ip:
                logger.info("Auto-discovery: IP changed for SN %s: %r → %r", sn, by_sn.ip_address, ip)
                by_sn.ip_address = ip
                by_sn.last_seen  = now
                db.commit()
                # Keep iclock_terminal in sync so the device list shows the new IP
                db.execute(sa_text(
                    "UPDATE iclock_terminal SET ip_address = :ip WHERE sn = :sn"
                ), {"ip": ip, "sn": sn})
                db.commit()
            return

        # Respect UI deletions — don't re-add a reader the admin deleted, even if
        # it is still powered on and reachable on the LAN.
        from ...api.adms_protocol import is_device_suppressed
        if is_device_suppressed(db, sn):
            logger.info("Auto-discovery: %s suppressed (deleted in UI) — not re-adding", sn)
            return

        device = Device(
            name             = f"ZKTeco-{ip}",
            serial_number    = sn,
            ip_address       = ip,
            port             = ZKTECO_PORT,
            connection_mode  = "direct",
            status           = DeviceStatus.ONLINE,
            auto_poll        = True,
            poll_interval_sec= 300,
            last_seen        = now,
        )
        db.add(device)
        db.commit()
        logger.info("Auto-discovered new ZKLib reader: %s  SN=%s", ip, sn)

        # Ensure iclock_terminal entry exists so the device shows in the UI
        from sqlalchemy import text as sa_text2
        db.execute(sa_text2("""
            INSERT INTO iclock_terminal
                (sn, alias, ip_address, state, connection_mode, reader_purpose,
                 last_activity, heartbeat_interval, att_stamp, op_stamp, pushver)
            VALUES
                (:sn, :alias, :ip, 1, 'direct', 'ATTENDANCE',
                 :now, 30, 0, 0, '1.0')
            ON CONFLICT (sn) DO UPDATE SET
                ip_address = EXCLUDED.ip_address,
                last_activity = EXCLUDED.last_activity
        """), {"sn": sn, "alias": f"ZKTeco-{ip}", "ip": ip, "now": now})
        db.commit()
    except Exception as exc:
        logger.warning("Failed to register discovered device %s: %s", ip, exc)
        db.rollback()
    finally:
        db.close()


async def _probe_and_register(ip: str, now: datetime) -> None:
    """Probe a single IP; if it responds on port 4370 register or update its IP in the DB."""
    if not await _tcp_reachable(ip, ZKTECO_PORT):
        return
    try:
        loop = asyncio.get_event_loop()
        sn = await loop.run_in_executor(None, _fetch_sn_sync, ip)
        if sn and not sn.startswith("IP-"):
            # _db_register_new_device handles both new devices and IP-change updates
            await loop.run_in_executor(None, _db_register_new_device, ip, sn, now)
        else:
            logger.debug("Auto-discovery: %s has port 4370 open but is not a ZKTeco device", ip)
    except Exception as exc:
        logger.debug("Auto-discovery: could not get SN from %s: %s", ip, exc)


def _fetch_sn_sync(ip: str) -> str:
    """Synchronous ZKLib connect to read the device serial number."""
    try:
        from zk import ZK
        zk = ZK(ip, port=ZKTECO_PORT, timeout=5, password=0, force_udp=False, ommit_ping=True)
        conn = zk.connect()
        try:
            sn = conn.get_serialnumber()
            return sn or f"IP-{ip}"
        finally:
            conn.disconnect()
    except Exception:
        return f"IP-{ip}"


async def _scan_subnets() -> None:
    """
    Scan all derived subnets concurrently for ZKLib readers.
    Probes EVERY host on every known subnet (including already-registered IPs) so
    that devices whose DHCP address changed are automatically re-discovered and their
    IP is updated in the database without any manual intervention.
    """
    subnets = await asyncio.get_event_loop().run_in_executor(None, _db_get_subnets_to_scan)
    if not subnets:
        return

    now = datetime.now(timezone.utc)
    tasks = [
        _probe_and_register(str(host), now)
        for net in subnets
        for host in net.hosts()
    ]

    if tasks:
        batch = 30
        for i in range(0, len(tasks), batch):
            await asyncio.gather(*tasks[i:i+batch], return_exceptions=True)


# ── Startup reset ─────────────────────────────────────────────────────────────

def reset_stale_states() -> None:
    """
    Called once at startup. Marks STALE approved terminals OFFLINE; terminals
    whose last_activity is still within ADMS_STALE_SECS stay APPROVED so a
    brief restart does not show recently-active devices as offline in the UI.
    """
    db = SessionLocal()
    try:
        from sqlalchemy import text
        stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=ADMS_STALE_SECS)

        # Only flip APPROVED → OFFLINE for terminals whose last heartbeat is stale.
        # Terminals active within the last ADMS_STALE_SECS seconds stay APPROVED.
        db.execute(text(
            "UPDATE iclock_terminal SET state = :offline "
            "WHERE state = 1 AND (last_activity IS NULL OR last_activity < :cutoff)"
        ), {"offline": STATE_OFFLINE, "cutoff": stale_cutoff})

        # Reset devices table entirely; the heartbeat_loop restores direct-mode devices
        # within 5 s via TCP probe, and ADMS-linked ones below via _sync_terminal_to_devices.
        db.query(Device).update({"status": DeviceStatus.OFFLINE})
        db.commit()

        # Re-sync the devices table for terminals that are still APPROVED so their
        # UI status doesn't falsely show OFFLINE after the devices.status bulk reset.
        now = datetime.now(timezone.utc)
        still_active = (
            db.query(IClockTerminal)
            .filter(IClockTerminal.state == STATE_APPROVED)
            .all()
        )
        for term in still_active:
            _sync_terminal_to_devices(db, term, True, now)
        if still_active:
            db.commit()

        logger.info(
            "Heartbeat: startup state reset — %d terminal(s) still active, stale ones set OFFLINE",
            len(still_active),
        )
    except Exception as exc:
        logger.error("Heartbeat: failed to reset states: %s", exc)
        db.rollback()
    finally:
        db.close()


# ── Main loop ─────────────────────────────────────────────────────────────────

async def heartbeat_loop() -> None:
    """
    Main heartbeat loop:
    - Every HEARTBEAT_INTERVAL (5s): TCP-probe all direct-mode devices.
    - Every HEARTBEAT_INTERVAL (5s): Check ADMS terminal last_activity staleness.
    - Every AUTO_SCAN_INTERVAL (60s): Scan subnets for new ZKLib readers.
    """
    logger.info("Device heartbeat started — direct probe every %ds, subnet scan every %ds",
                HEARTBEAT_INTERVAL, AUTO_SCAN_INTERVAL)
    last_scan = 0.0
    _scan_task: asyncio.Task = None  # type: ignore[assignment]

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        now = datetime.now(timezone.utc)
        loop = asyncio.get_event_loop()

        try:
            # ── 1. Direct-mode TCP probes ──────────────────────────────────
            targets = await loop.run_in_executor(None, _db_get_direct_targets)
            if targets:
                await asyncio.gather(
                    *[_probe_direct(*t, now) for t in targets],
                    return_exceptions=True,
                )

            # ── 2. ADMS terminal staleness check ──────────────────────────
            adms = await loop.run_in_executor(None, _db_get_adms_terminals)
            muster_zones = await loop.run_in_executor(None, _db_get_active_muster_zone_ids) if adms else set()
            for (tid, sn, ip, state, last_act, hb_interval, zone_id) in adms:
                # Per-device stale threshold: readers in a zone with an active muster
                # event use a tight floor (personnel safety — must know within
                # seconds if a muster reader stops responding). All others use a
                # looser floor so normal network jitter doesn't flap the status.
                if zone_id is not None and zone_id in muster_zones:
                    per_device_stale = max(hb_interval * 2, MUSTER_STALE_SECS)
                else:
                    per_device_stale = max(hb_interval * 3, ADMS_STALE_SECS)
                stale_cutoff = now - timedelta(seconds=per_device_stale)

                if last_act is None:
                    online = False
                else:
                    if last_act.tzinfo is None:
                        last_act = last_act.replace(tzinfo=timezone.utc)
                    online = last_act >= stale_cutoff
                # Only act when state needs to change
                current_online = (state == STATE_APPROVED)
                if online != current_online:
                    await loop.run_in_executor(
                        None, _db_update_adms, tid, sn, online, now
                    )

            # ── 3. Auto-discovery subnet scan ──────────────────────────────
            import time
            if time.monotonic() - last_scan >= AUTO_SCAN_INTERVAL:
                # Guard: only start a new scan when the previous one has finished.
                # Without this, slow scans (large subnets, unresponsive devices)
                # accumulate tasks and exhaust the thread pool.
                if _scan_task is None or _scan_task.done():
                    last_scan = time.monotonic()
                    _scan_task = asyncio.create_task(_scan_subnets())

        except asyncio.CancelledError:
            logger.info("Device heartbeat stopped")
            break
        except Exception as exc:
            logger.error("Heartbeat loop error: %s", exc)


async def _probe_direct(device_id: int, ip: str, port: int, sn: str,
                        now: datetime) -> None:
    """
    Probe a direct-mode device.  After confirming TCP reachability we do a quick
    ZKLib SN read to guard against a different device having taken over the same IP
    (e.g. DHCP reassignment).  If the SN doesn't match, we treat this device as
    unreachable and trigger a SN-based IP-update for whoever actually answered.
    """
    if not await _tcp_reachable(ip, port):
        await asyncio.get_event_loop().run_in_executor(
            None, _db_update_direct, device_id, sn, False, now
        )
        return

    # Verify identity: read SN from the device that responded
    loop = asyncio.get_event_loop()
    actual_sn = await loop.run_in_executor(None, _fetch_sn_sync, ip)
    if actual_sn and not actual_sn.startswith("IP-") and actual_sn != sn:
        # A different device is at this IP — update its IP record and mark
        # the registered device (sn) as unreachable at its stored address.
        logger.info(
            "Heartbeat [direct] %s: expected SN %s but got %s — IP moved; updating",
            ip, sn, actual_sn,
        )
        await loop.run_in_executor(None, _db_register_new_device, ip, actual_sn, now)
        await loop.run_in_executor(None, _db_update_direct, device_id, sn, False, now)
        return

    await loop.run_in_executor(None, _db_update_direct, device_id, sn, True, now)
