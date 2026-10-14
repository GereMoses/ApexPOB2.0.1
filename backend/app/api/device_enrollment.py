"""
Device Biometric Enrollment API
Covers: enrollment status per device/employee, remote enrollment trigger,
        template push to device(s), template deletion, enrollment report.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

from ..core.database import get_db
from ..services.device_pin import rewrite_command, pin_for
from ..core.dependencies import get_current_user
from ..models.user import User
from ..models.biotime_models import (
    IClockBioTemplate, IClockTerminal, PersonnelEmployee
)
from ..models.personnel import Personnel, PersonnelStatus
from ..models.resignation import Resignation, ResignationType
from ..services.device_planes import is_controller as _is_controller

router = APIRouter()

# finger_id 0-9 = fingerprint slots; -1 = face (ADMS); 10-15 = face on direct-connect devices
FACE_FIDS = {-1, 10, 11, 12, 13, 14, 15}

VERIFY_TYPE_MAP = {
    -1: "face",  0: "fp0",  1: "fp1",  2: "fp2",  3: "fp3",  4: "fp4",
     5: "fp5",   6: "fp6",  7: "fp7",  8: "fp8",  9: "fp9",
    10: "face", 11: "face", 12: "face", 13: "face", 14: "face", 15: "face",
}


def _queue_cmd(db: Session, sn: str, cmd: str) -> int:
    cmd = rewrite_command(db, cmd)   # PIN=<emp_code> -> reader PIN
    result = db.execute(
        text("INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, status) "
             "VALUES (:sn, :cmd, :now, 0) RETURNING id"),
        {"sn": sn, "cmd": cmd, "now": datetime.now(timezone.utc)}
    )
    db.commit()
    return result.fetchone()[0]


def _is_adms_reader(terminal, device) -> bool:
    """True when the reader is push-mode (cloud/NAT) — the server CANNOT open a
    direct ZKLib TCP socket to it, so direct pull/enroll would fail with Broken
    pipe. Such readers must be driven through the ADMS command queue instead."""
    mode = (getattr(device, "connection_mode", None)
            or getattr(terminal, "connection_mode", None)
            or "adms").strip().lower()
    return mode not in ("direct", "both")


# ═══════════════════════════════════════════════════════════════════════════════
# ENROLLMENT STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/device/enrollment/status/")
async def get_enrollment_status(
    terminal_sn: Optional[str] = Query(None, description="Filter by device SN"),
    emp_code:    Optional[str] = Query(None, description="Filter by employee code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns a per-employee summary of biometric templates stored.
    If terminal_sn provided, cross-checks which employees have templates
    confirmed on that specific device (based on user_count/fp_count sync).
    """
    q = db.query(IClockBioTemplate).filter(IClockBioTemplate.valid == True)
    if emp_code:
        q = q.filter(IClockBioTemplate.emp_code == emp_code)

    templates = q.all()

    # Group by emp_code
    emp_data: dict = {}
    for t in templates:
        if t.emp_code not in emp_data:
            emp_data[t.emp_code] = {
                "emp_code": t.emp_code,
                "fingerprints": [],
                "face_enrolled": False,
                "total_templates": 0,
                "source_devices": set(),
            }
        if t.finger_id in FACE_FIDS:
            emp_data[t.emp_code]["face_enrolled"] = True
        else:
            slot = VERIFY_TYPE_MAP.get(t.finger_id, f"fp{t.finger_id}")
            emp_data[t.emp_code]["fingerprints"].append(slot)
        emp_data[t.emp_code]["total_templates"] += 1
        if t.source_sn:
            emp_data[t.emp_code]["source_devices"].add(t.source_sn)

    # Build separation reason map for INACTIVE employees from resignations table
    # Use the most recent completed/approved resignation per person
    resignation_map: dict = {}
    for r in db.query(Resignation).order_by(Resignation.created_at.desc()).all():
        if r.personnel_id not in resignation_map:
            resignation_map[r.personnel_id] = r

    # Build full personnel info map from Personnel (authoritative)
    p_info: dict = {}
    for e in db.query(Personnel).all():
        # Resolve separation reason for inactive employees
        separation_reason = None
        if str(getattr(e, "status", "")).upper() == "INACTIVE":
            res = resignation_map.get(e.id)
            if res:
                type_labels = {
                    "RETIREMENT": "Retired",
                    "TERMINATION": "Terminated",
                    "VOLUNTARY": "Resigned",
                    "CONTRACT_END": "Contract Ended",
                }
                rtype = str(res.resignation_type).replace("ResignationType.", "").upper()
                separation_reason = type_labels.get(rtype, res.reason[:60] if res.reason else "Inactive")
            else:
                separation_reason = "Inactive"
        p_info[e.emp_code] = {
            "emp_name": f"{e.first_name or ''} {e.last_name or ''}".strip(),
            "status": str(getattr(e, "status", "active")).replace("PersonnelStatus.", "").lower(),
            "department": e.department or "",
            "position": e.position or "",
            "personnel_type": e.personnel_type or "STAFF",
            "separation_reason": separation_reason,
            "personnel_id": e.id,
            "badge_id": e.badge_id or "",
            "card_number": e.card_number,
        }

    # Fall back to PersonnelEmployee for codes not in Personnel
    pe_info: dict = {}
    for e in db.query(PersonnelEmployee).all():
        if e.emp_code not in p_info:
            pe_info[e.emp_code] = {
                "emp_name": f"{e.first_name or ''} {e.last_name or ''}".strip(),
                "status": "active",
                "department": "",
                "position": "",
                "personnel_type": "STAFF",
                "separation_reason": None,
                "personnel_id": None,
                "badge_id": "",
                "card_number": None,
            }

    def _emp_info(code):
        return p_info.get(code) or pe_info.get(code) or {
            "emp_name": "—", "status": "active", "department": "",
            "position": "", "personnel_type": "STAFF", "separation_reason": None, "personnel_id": None,
        }

    result = []
    for code, info in emp_data.items():
        ei = _emp_info(code)
        result.append({
            **info,
            **ei,
            "source_devices": list(info["source_devices"]),
        })

    # Include all employees who have no templates yet
    if not emp_code:
        enrolled_codes = set(emp_data.keys())
        all_personnel_codes = set(p_info.keys())

        for code, ei in p_info.items():
            if code not in enrolled_codes:
                result.append({
                    "emp_code": code,
                    **ei,
                    "fingerprints": [],
                    "face_enrolled": False,
                    "total_templates": 0,
                    "source_devices": [],
                })
                enrolled_codes.add(code)

        # Orphaned ADMS employees with templates only
        codes_with_templates = set(emp_data.keys())
        for code, ei in pe_info.items():
            if code not in enrolled_codes and code in codes_with_templates:
                result.append({
                    "emp_code": code,
                    **ei,
                    "fingerprints": emp_data[code]["fingerprints"],
                    "face_enrolled": emp_data[code]["face_enrolled"],
                    "total_templates": emp_data[code]["total_templates"],
                    "source_devices": list(emp_data[code]["source_devices"]),
                })

    result.sort(key=lambda x: x["emp_code"])
    return {"success": True, "data": result, "total": len(result)}


@router.get("/api/device/enrollment/report/")
async def get_enrollment_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Enrollment report: stats per device — how many employees have templates
    on each device, broken down by biometric type.
    """
    terminals = db.query(IClockTerminal).all()
    # Count unique employees across both tables
    pe_codes = {e.emp_code for e in db.query(PersonnelEmployee).filter(PersonnelEmployee.status == 0).all()}
    p_codes  = {e.emp_code for e in db.query(Personnel).all()}
    total_employees = len(pe_codes | p_codes)

    # Templates per device
    # finger_id 0-9 = fingerprint; -1 or 10-15 = face (direct-connect devices use 10-15)
    by_device = db.execute(
        text("""
            SELECT source_sn,
                   COUNT(DISTINCT emp_code) as emp_count,
                   SUM(CASE WHEN finger_id BETWEEN 0 AND 9 THEN 1 ELSE 0 END) as fp_count,
                   SUM(CASE WHEN finger_id < 0 OR finger_id >= 10 THEN 1 ELSE 0 END) as face_count
            FROM iclock_bio_template
            WHERE valid = true AND source_sn IS NOT NULL
            GROUP BY source_sn
        """)
    ).fetchall()

    device_stats = {row[0]: {"emp_count": row[1], "fp_count": row[2], "face_count": row[3]}
                    for row in by_device}

    alias_map = {t.sn: (t.alias or t.sn) for t in terminals}

    # Also pull direct-connect device IPs from the `devices` table keyed by serial_number
    from ..models.device import Device
    direct_devices = db.query(Device).filter(Device.ip_address.isnot(None)).all()
    direct_ip_map = {d.serial_number: d.ip_address for d in direct_devices if d.serial_number}

    devices_report = []
    for t in terminals:
        # ip_address may be on iclock_terminal directly, or on the matching devices row
        ip = getattr(t, "ip_address", None) or direct_ip_map.get(t.sn)
        stats = device_stats.get(t.sn, {"emp_count": 0, "fp_count": 0, "face_count": 0})
        devices_report.append({
            "sn": t.sn,
            "alias": t.alias or t.sn,
            "ip_address": ip,
            "enrolled_employees": stats["emp_count"],
            "total_employees": total_employees,
            "enrollment_pct": round(stats["emp_count"] / total_employees * 100, 1) if total_employees else 0,
            "fp_templates": stats["fp_count"],
            "face_templates": stats["face_count"],
            "device_fp_count": t.fp_count,
            "device_face_count": t.face_count,
        })

    # Overall stats
    overall_enrolled = db.query(IClockBioTemplate.emp_code).filter(
        IClockBioTemplate.valid == True
    ).distinct().count()

    return {"success": True, "data": {
        "devices": devices_report,
        "total_employees": total_employees,
        "enrolled_employees": overall_enrolled,
        "not_enrolled": total_employees - overall_enrolled,
        "enrollment_pct": round(overall_enrolled / total_employees * 100, 1) if total_employees else 0,
    }}


# ═══════════════════════════════════════════════════════════════════════════════
# ENABLE ENROLLMENT MODE
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/device/enrollment/enable")
async def enable_enrollment_mode(
    sn: str = Query(..., description="Device serial number"),
    emp_code: Optional[str] = Query(None, description="Pre-select employee on device"),
    finger_id: int = Query(0, description="Finger slot 0-9 to enroll (ignored for face)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remote (ADMS) enrollment trigger — works for cloud/NAT readers that the server
    cannot reach over TCP. Queues commands the reader fetches on its next poll:

      1. DATA UPDATE USERINFO — make sure the employee exists on the reader.
      2. ENROLL_FP            — open the fingerprint-enrollment screen for that PIN.

    The employee then scans on the reader; the captured template is pushed back to
    the server automatically via /iclock/cdata (handle_fingertmp) — no pull needed.

    Uses the ZKTeco PUSH protocol command format (tab-separated, ENROLL_FP — NOT the
    ZKLib "ENROLL FP" form, which push readers reject as UNKNOWN CMD).
    """
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="Device not found")
    if _is_controller(sn, db):
        raise HTTPException(status_code=400, detail=(
            "InBio/C3 access controller — biometric enrollment isn't available via "
            "POB yet (controller driver pending). Enrol on the controller's software."))

    queued = []

    if emp_code:
        # Ensure the user exists on the reader first (idempotent — harmless if already there).
        person = db.query(Personnel).filter(Personnel.emp_code == emp_code).first()
        name = ((person.full_name if person else None)
                or (f"{person.first_name or ''} {person.last_name or ''}".strip() if person else None)
                or emp_code)[:24]
        card = (str(person.card_number) if person and person.card_number else "")
        userinfo = (f"DATA UPDATE USERINFO PIN={emp_code}\t"
                    f"Name={name}\tPri=0\tPasswd=\tCard={card}\tGrp=1\tTZ=0")
        queued.append(_queue_cmd(db, sn, userinfo))

        # Open the enrollment screen for this PIN / finger.
        enroll = (f"ENROLL_FP PIN={emp_code}\tFID={finger_id}\tRETRY=3\tOVERWRITE=1")
        cmd_id = _queue_cmd(db, sn, enroll)
        queued.append(cmd_id)
    else:
        cmd_id = _queue_cmd(db, sn, "ENROLL_FP")
        queued.append(cmd_id)

    return {"success": True, "data": {
        "command_id": cmd_id,
        "command_ids": queued,
        "sn": sn,
        "emp_code": emp_code,
        "finger_id": finger_id,
        "message": (f"Enrollment queued for {terminal.alias or sn}. Go to the reader — it will "
                    f"open the enrollment screen for this employee; the scanned template syncs "
                    f"back automatically."),
    }}


# ═══════════════════════════════════════════════════════════════════════════════
# PUSH TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

class TemplatePushRequest(BaseModel):
    emp_code: str
    target_sns: List[str] = Field(..., description="List of device SNs to push to")
    include_fp: bool = True
    include_face: bool = True


@router.post("/api/device/enrollment/push")
async def push_templates_to_devices(
    payload: TemplatePushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Push biometric templates for an employee to one or more devices.
    Queues DATA UPDATE FINGER / FACE commands.
    """
    # Verify employee exists
    emp = db.query(PersonnelEmployee).filter(
        PersonnelEmployee.emp_code == payload.emp_code
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    templates = db.query(IClockBioTemplate).filter(
        IClockBioTemplate.emp_code == payload.emp_code,
        IClockBioTemplate.valid == True
    ).all()

    if not templates:
        raise HTTPException(status_code=404, detail="No biometric templates found for this employee")

    has_fp   = any(0 <= t.finger_id <= 9 for t in templates)
    has_face = any(t.finger_id in FACE_FIDS for t in templates)

    commands_queued = []
    for sn in payload.target_sns:
        if _is_controller(sn, db):
            continue  # InBio/C3 panels have no template-push driver yet — skip
        terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
        if not terminal:
            continue

        # Always push basic user info first
        _queue_cmd(db, sn, f"DATA UPDATE USERINFO PIN={payload.emp_code}")

        if payload.include_fp and has_fp:
            cmd_id = _queue_cmd(db, sn, f"DATA UPDATE FINGER PIN={payload.emp_code}")
            commands_queued.append({"sn": sn, "type": "fingerprint", "command_id": cmd_id})

        if payload.include_face and has_face:
            cmd_id = _queue_cmd(db, sn, f"DATA UPDATE FACE PIN={payload.emp_code}")
            commands_queued.append({"sn": sn, "type": "face", "command_id": cmd_id})

    return {"success": True, "data": {
        "emp_code": payload.emp_code,
        "devices_targeted": len(payload.target_sns),
        "commands_queued": len(commands_queued),
        "details": commands_queued,
    }}


class AreaTemplatePushRequest(BaseModel):
    emp_code: str
    area_id: int
    include_fp: bool = True
    include_face: bool = True


@router.post("/api/device/enrollment/push-to-area")
async def push_templates_to_area(
    payload: AreaTemplatePushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Push templates to all devices in a given area."""
    terminals = db.query(IClockTerminal).filter(
        IClockTerminal.area_id == payload.area_id
    ).all()

    if not terminals:
        raise HTTPException(status_code=404, detail="No devices in this area")

    target_sns = [t.sn for t in terminals]
    # Reuse the single-push logic
    push_payload = TemplatePushRequest(
        emp_code=payload.emp_code,
        target_sns=target_sns,
        include_fp=payload.include_fp,
        include_face=payload.include_face,
    )

    commands_queued = []
    for sn in target_sns:
        _queue_cmd(db, sn, f"DATA UPDATE USERINFO PIN={payload.emp_code}")
        _queue_cmd(db, sn, f"DATA UPDATE FINGER PIN={payload.emp_code}")
        _queue_cmd(db, sn, f"DATA UPDATE FACE PIN={payload.emp_code}")
        commands_queued.append(sn)

    return {"success": True, "data": {
        "emp_code": payload.emp_code,
        "area_id": payload.area_id,
        "devices": len(target_sns),
        "commands_queued": len(target_sns) * 3,
    }}


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/api/device/enrollment/template")
async def delete_template(
    emp_code: str = Query(...),
    finger_id: Optional[int] = Query(None, description="Specific finger slot; omit for all"),
    push_to_devices: bool = Query(True, description="Also queue delete command on devices"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete biometric template(s) for an employee from the server.
    Optionally queue DATA DELETE FINGER/FACE command on all devices.
    """
    q = db.query(IClockBioTemplate).filter(
        IClockBioTemplate.emp_code == emp_code,
        IClockBioTemplate.valid == True
    )
    if finger_id is not None:
        q = q.filter(IClockBioTemplate.finger_id == finger_id)

    templates = q.all()
    if not templates:
        raise HTTPException(status_code=404, detail="No templates found")

    for t in templates:
        t.valid = False
    db.commit()

    if push_to_devices:
        terminals = db.query(IClockTerminal).all()
        for t in terminals:
            if finger_id is None:
                _queue_cmd(db, t.sn, f"DATA DELETE USERINFO PIN={emp_code}")
            elif finger_id in FACE_FIDS:
                _queue_cmd(db, t.sn, f"DATA DELETE FACE PIN={emp_code}")
            else:
                _queue_cmd(db, t.sn, f"DATA DELETE FINGER PIN={emp_code} FID={finger_id}")

    return {"success": True, "data": {
        "emp_code": emp_code,
        "templates_removed": len(templates),
        "pushed_to_devices": push_to_devices,
    }}


# ═══════════════════════════════════════════════════════════════════════════════
# DIRECT-CONNECT ENDPOINTS (ZKLib TCP — F18 / Huros)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/device/enrollment/pull-from-device")
async def pull_templates_from_device(
    sn: str = Query(..., description="Device serial number"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Pull ALL biometric templates currently stored on a direct-connect ZKTeco device
    and upsert them into iclock_bio_template.  Builds a uid→emp_code map from the
    users already on the device so each template is linked to the right employee.
    """
    from ..services.zkteco.direct_connection import zkteco_direct
    from ..models.device import Device

    # Look up device IP — check iclock_terminal first, then devices table
    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    device   = db.query(Device).filter(Device.serial_number == sn).first()

    if _is_adms_reader(terminal, device):
        raise HTTPException(
            status_code=400,
            detail=("This is a remote (ADMS) reader — its templates cannot be pulled over "
                    "the internet (there is no ADMS 'get all biometrics' command). Enroll on "
                    "the reader and the template syncs back automatically, or do a one-time "
                    "pull while on the same LAN."))

    ip   = getattr(terminal, "ip_address", None) or getattr(device, "ip_address", None)
    port = getattr(device, "port", None) or 4370
    if not ip:
        raise HTTPException(status_code=404, detail="Device not found or has no IP address")

    # Get uid→emp_code map from device users
    users_res = await zkteco_direct.get_users_from_device(ip, port)
    if not users_res["success"]:
        raise HTTPException(status_code=502, detail=f"Could not read users from device: {users_res.get('error')}")

    uid_to_emp = {u["uid"]: u["user_id"] for u in users_res["users"] if u.get("user_id")}

    # Pull templates
    tpl_res = await zkteco_direct.get_templates_from_device(ip, port)
    if not tpl_res["success"]:
        raise HTTPException(status_code=502, detail=f"Could not read templates from device: {tpl_res.get('error')}")

    saved = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    import base64
    for t in tpl_res["templates"]:
        emp_code = uid_to_emp.get(t["uid"])
        if not emp_code:
            skipped += 1
            continue

        tpl_b64 = base64.b64encode(t["template"]).decode() if t["template"] else ""

        # Normalize face fids (10-15 from direct-connect) to -1 (ADMS standard)
        # so templates are compatible with ADMS push commands and detection logic.
        fid = -1 if t["fid"] >= 10 else t["fid"]

        existing = db.query(IClockBioTemplate).filter(
            IClockBioTemplate.emp_code == emp_code,
            IClockBioTemplate.finger_id == fid,
        ).first()

        if existing:
            existing.template_data = tpl_b64
            existing.template_size = len(t["template"]) if t["template"] else 0
            existing.valid = True
            existing.source_sn = sn
            existing.updated_at = now
        else:
            db.add(IClockBioTemplate(
                emp_code=emp_code,
                finger_id=fid,
                template_data=tpl_b64,
                template_size=len(t["template"]) if t["template"] else 0,
                valid=True,
                source_sn=sn,
                created_at=now,
                updated_at=now,
            ))
        saved += 1

    db.commit()
    return {"success": True, "data": {
        "sn": sn,
        "templates_on_device": tpl_res["count"],
        "saved": saved,
        "skipped_no_user_match": skipped,
    }}


class DirectEnrollRequest(BaseModel):
    sn: str           = Field(..., description="Device serial number")
    emp_code: str     = Field(..., description="Employee code (PIN on device)")
    finger_id: int    = Field(0,   description="Finger slot 0-9; use 10 for face (device-specific)")


@router.post("/api/device/enrollment/cancel")
async def cancel_enrollment(
    sn: str = Query(..., description="Device serial number"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel any pending capture on the device and re-enable it."""
    from ..services.zkteco.direct_connection import zkteco_direct
    from ..models.device import Device

    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    device   = db.query(Device).filter(Device.serial_number == sn).first()
    ip   = getattr(terminal, "ip_address", None) or getattr(device, "ip_address", None)
    port = getattr(device, "port", None) or 4370
    if not ip:
        raise HTTPException(status_code=404, detail="Device not found or has no IP address")

    result = await zkteco_direct.cancel_enrollment(ip, port)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Cancel failed"))
    return {"success": True, "data": result}


@router.post("/api/device/enrollment/enroll-direct")
async def enroll_direct(
    payload: DirectEnrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send CMD_STARTENROLL to the device (non-blocking) then disconnect immediately.
    The device activates its fingerprint capture screen — the employee presses their
    finger on the scanner without the server holding the socket open.
    After enrollment, call pull-from-device to sync the template into the database.
    """
    from ..services.zkteco.direct_connection import zkteco_direct
    from ..models.device import Device

    terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == payload.sn).first()
    device   = db.query(Device).filter(Device.serial_number == payload.sn).first()

    if _is_adms_reader(terminal, device):
        raise HTTPException(
            status_code=400,
            detail=("This is a remote (ADMS) reader — live Direct-TCP capture isn't possible "
                    "over the internet. Use ADMS enrollment (Enroll → ADMS mode): it queues "
                    "the enrollment to the reader and the scanned template syncs back "
                    "automatically."))

    ip   = getattr(terminal, "ip_address", None) or getattr(device, "ip_address", None)
    port = getattr(device, "port", None) or 4370
    if not ip:
        raise HTTPException(status_code=404, detail="Device not found or has no IP address")

    # Look up the Personnel record to get badge_id, full name, and card number
    person = db.query(Personnel).filter(Personnel.emp_code == payload.emp_code).first()
    badge_id  = str(person.badge_id or payload.emp_code) if person else payload.emp_code
    full_name = (person.full_name or f"{person.first_name or ''} {person.last_name or ''}".strip() or badge_id)[:24] if person else badge_id
    card_no   = int(person.card_number) if person and person.card_number else 0

    # Fetch users already on the device
    users_res = await zkteco_direct.get_users_from_device(ip, port)
    if not users_res["success"]:
        raise HTTPException(status_code=502, detail="Could not read device users")

    device_users = users_res.get("users", [])

    # Match on user_id == emp_code OR badge_id (handles both sync conventions)
    uid = None
    for u in device_users:
        if u.get("user_id") in (payload.emp_code, badge_id, pin_for(db, payload.emp_code, fallback=badge_id)):
            uid = u["uid"]
            break

    # Auto-register the employee on the device if they are not found
    if uid is None:
        # Pick a uid that doesn't conflict with existing device users
        used_uids = {u["uid"] for u in device_users}
        new_uid   = (person.id if person else None) or max(used_uids, default=0) + 1
        while new_uid in used_uids:
            new_uid += 1

        reg_result = await zkteco_direct.set_user(
            ip=ip, port=port,
            uid=new_uid,
            name=full_name,
            user_id=pin_for(db, payload.emp_code, fallback=badge_id),
            card=card_no,
        )
        if not reg_result.get("success"):
            raise HTTPException(
                status_code=502,
                detail=f"Employee {payload.emp_code} is not on the device and auto-registration failed: {reg_result.get('error', 'unknown error')}"
            )
        uid = new_uid

    result = await zkteco_direct.enroll_and_capture(
        ip, port, uid=uid, user_id=pin_for(db, payload.emp_code, fallback=badge_id), finger_id=payload.finger_id
    )

    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Enrollment failed — employee may not have pressed finger in time"))

    # Save template to DB if captured
    now = datetime.now(timezone.utc)
    if result.get("captured") and result.get("template_b64"):
        existing = db.query(IClockBioTemplate).filter(
            IClockBioTemplate.emp_code == payload.emp_code,
            IClockBioTemplate.finger_id == payload.finger_id,
        ).first()
        if existing:
            existing.template_data = result["template_b64"]
            existing.template_size = result.get("template_size", 0)
            existing.valid = True
            existing.source_sn = payload.sn
            existing.updated_at = now
        else:
            db.add(IClockBioTemplate(
                emp_code=payload.emp_code,
                finger_id=payload.finger_id,
                template_data=result["template_b64"],
                template_size=result.get("template_size", 0),
                valid=True,
                source_sn=payload.sn,
                created_at=now,
                updated_at=now,
            ))
        db.commit()

    return {"success": True, "data": {
        "emp_code": payload.emp_code,
        "finger_id": payload.finger_id,
        "captured": result.get("captured", False),
        "message": "Fingerprint captured and saved to database" if result.get("captured") else "Enrollment completed on device — use Pull Templates to sync",
    }}


# ═══════════════════════════════════════════════════════════════════════════════
# CARD MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class CardAssignRequest(BaseModel):
    emp_code: str  = Field(..., description="Employee code")
    card_number: Optional[int] = Field(None, description="RFID card number (None to unassign)")

class CardSyncRequest(BaseModel):
    emp_code: str       = Field(..., description="Employee code to sync card for")
    target_sns: List[str] = Field(..., description="Device serial numbers to push card to")


@router.post("/api/device/enrollment/card/assign")
async def assign_card(
    payload: CardAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign or unassign a physical RFID card number to an employee."""
    emp = db.query(Personnel).filter(Personnel.emp_code == payload.emp_code).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Check uniqueness — no two employees can share the same card
    if payload.card_number is not None:
        conflict = db.query(Personnel).filter(
            Personnel.card_number == payload.card_number,
            Personnel.emp_code != payload.emp_code,
        ).first()
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Card {payload.card_number} is already assigned to {conflict.emp_code} — {conflict.first_name} {conflict.last_name}"
            )

    emp.card_number = payload.card_number
    db.commit()
    return {
        "success": True,
        "data": {
            "emp_code": emp.emp_code,
            "card_number": emp.card_number,
            "message": f"Card {'assigned' if payload.card_number else 'unassigned'} successfully",
        }
    }


@router.post("/api/device/enrollment/card/sync")
async def sync_card_to_devices(
    payload: CardSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Push the employee's card number to one or more direct-connect devices."""
    from ..services.zkteco.direct_connection import zkteco_direct
    from ..models.device import Device

    emp = db.query(Personnel).filter(Personnel.emp_code == payload.emp_code).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    results = []
    for sn in payload.target_sns:
        terminal = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
        device   = db.query(Device).filter(Device.serial_number == sn).first()
        ip   = getattr(terminal, "ip_address", None) or getattr(device, "ip_address", None)
        port = getattr(device, "port", None) or 4370

        if not ip:
            results.append({"sn": sn, "success": False, "error": "No IP address for device"})
            continue

        # Find the uid for this employee on the device by matching user_id
        users_res = await zkteco_direct.get_device_users(ip, port)
        uid = None
        if users_res.get("success"):
            for u in users_res.get("users", []):
                if str(u.get("user_id", "")) in (str(emp.badge_id or emp.emp_code), pin_for(db, emp.emp_code)):
                    uid = u["uid"]
                    break

        if uid is None:
            results.append({"sn": sn, "success": False, "error": "Employee not found on device — sync personnel first"})
            continue

        res = await zkteco_direct.set_user(
            ip=ip,
            uid=uid,
            name=(emp.full_name or emp.badge_id or emp.emp_code)[:24],
            user_id=pin_for(db, emp.emp_code, fallback=str(emp.badge_id or emp.emp_code)),
            card=int(emp.card_number) if emp.card_number else 0,
            port=port,
        )
        results.append({"sn": sn, "success": res.get("success", False), "error": res.get("error")})

    success_count = sum(1 for r in results if r["success"])
    return {
        "success": True,
        "data": {
            "emp_code": emp.emp_code,
            "card_number": emp.card_number,
            "synced": success_count,
            "total": len(payload.target_sns),
            "results": results,
        }
    }


@router.get("/api/device/enrollment/card/status")
async def get_card_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return card assignment status for all employees."""
    employees = db.query(Personnel).all()
    return {
        "success": True,
        "data": [
            {
                "emp_code": e.emp_code,
                "emp_name": f"{e.first_name or ''} {e.last_name or ''}".strip(),
                "badge_id": e.badge_id,
                "card_number": e.card_number,
                "has_card": e.card_number is not None,
            }
            for e in employees
        ]
    }
