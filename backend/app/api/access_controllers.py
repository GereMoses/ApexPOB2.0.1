"""
Access-Control Controllers API.

Manages the LAN access panels (ZKTeco inBio / C3) and their reader ports for zone
entry/exit. Kept separate from the ADMS / Horus H1 device endpoints on purpose:
different hardware, different protocol (C3 PULL, not ADMS push), different topology
(one IP → many door readers).
"""

from typing import List, Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.access_controller import AccessController, AccessReader
from ..models.zone import Zone
from ..schemas.access_controller import (
    AccessControllerCreate, AccessControllerUpdate, AccessControllerOut,
    AccessReaderCreate, AccessReaderUpdate, AccessReaderOut,
)
from ..services.zkteco import c3_controller as c3
from ..services.zkteco import c3_pull_sdk
from ..services.zkteco import c3_zkaccess
from ..services.access_controller_ingest import poll_controller_once, learn_controller_ports
from ..services.controller_doors import ensure_controller_doors

router = APIRouter(prefix="/access-controllers", tags=["Access Control Controllers"])


# ── ZKTeco C3 model specs (from the official datasheet — not assumptions) ───────
# reader_ports is the number of Wiegand reader ports on the panel. Note the real
# constraint that shapes zone entry/exit tracking:
#   • C3-100 / C3-200 have 2 reader ports PER door → IN + OUT reader per door
#     (card-read on both entry AND exit → full bidirectional zone tracking).
#   • C3-400 has 4 reader ports for 4 doors → 1 reader PER door (entry only);
#     exits are by push-button/REX, so exit is NOT a card read. For bidirectional
#     tracking on a C3-400 you must run it in 2-door mode (IN+OUT on 2 doors).
C3_MODELS = {
    "C3-100": {"doors": 1, "reader_ports": 2, "inputs": 2,  "outputs": 2,
               "readers_per_door": 2, "card_capacity": 30000, "log_capacity": 100000},
    "C3-200": {"doors": 2, "reader_ports": 4, "inputs": 6,  "outputs": 4,
               "readers_per_door": 2, "card_capacity": 30000, "log_capacity": 100000},
    "C3-400": {"doors": 4, "reader_ports": 4, "inputs": 12, "outputs": 8,
               "readers_per_door": 1, "card_capacity": 30000, "log_capacity": 100000},
}


# ── serialization ─────────────────────────────────────────────────────────────
def _reader_out(reader: AccessReader, db: Session) -> AccessReaderOut:
    out = AccessReaderOut.model_validate(reader)
    if reader.zone_id:
        zone = db.query(Zone).filter(Zone.id == reader.zone_id).first()
        out.zone_name = zone.name if zone else None
    return out


def _controller_out(ctrl: AccessController, db: Session) -> AccessControllerOut:
    out = AccessControllerOut.model_validate(ctrl)
    out.readers = [_reader_out(r, db) for r in ctrl.readers]
    return out


def _default_readers(door_count: int, model: str = None) -> List[AccessReader]:
    """Auto-seed reader ports. Uses the real per-model layout for known C3 panels:
    C3-100/200 → IN+OUT per door; C3-400 → 1 (entry) reader per door (exit by button).
    Unknown models default to IN+OUT per door. Operators can add/remove ports or use
    Learn mode to match the actual wiring."""
    spec = C3_MODELS.get((model or "").upper())
    per_door = spec["readers_per_door"] if spec else 2
    readers: List[AccessReader] = []
    for door in range(1, door_count + 1):
        readers.append(AccessReader(door_no=door, direction="ENTRY", name=f"Door {door} Entry"))
        if per_door >= 2:
            readers.append(AccessReader(door_no=door, direction="EXIT", name=f"Door {door} Exit"))
    return readers


@router.get("/models", summary="Known ZKTeco C3 model specs (datasheet)")
def list_models():
    return C3_MODELS


# ── controllers CRUD ──────────────────────────────────────────────────────────
@router.get("", response_model=List[AccessControllerOut])
def list_controllers(db: Session = Depends(get_db)):
    return [_controller_out(c, db) for c in db.query(AccessController).order_by(AccessController.name).all()]


@router.post("", response_model=AccessControllerOut, status_code=status.HTTP_201_CREATED)
def create_controller(body: AccessControllerCreate, db: Session = Depends(get_db)):
    if db.query(AccessController).filter(AccessController.ip_address == body.ip_address).first():
        raise HTTPException(status_code=409, detail=f"A controller with IP {body.ip_address} already exists")

    data = body.model_dump(exclude={"readers"})
    ctrl = AccessController(**data)
    if body.readers:
        ctrl.readers = [AccessReader(**r.model_dump()) for r in body.readers]
    else:
        ctrl.readers = _default_readers(body.door_count, body.model)
    db.add(ctrl)
    db.commit()
    db.refresh(ctrl)
    ensure_controller_doors(db, ctrl)       # every port becomes a door emergencies can act on
    return _controller_out(ctrl, db)


@router.get("/{controller_id}", response_model=AccessControllerOut)
def get_controller(controller_id: int, db: Session = Depends(get_db)):
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    return _controller_out(ctrl, db)


@router.put("/{controller_id}", response_model=AccessControllerOut)
def update_controller(controller_id: int, body: AccessControllerUpdate, db: Session = Depends(get_db)):
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(ctrl, key, value)
    db.commit()
    db.refresh(ctrl)
    ensure_controller_doors(db, ctrl)
    return _controller_out(ctrl, db)


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_controller(controller_id: int, db: Session = Depends(get_db)):
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    db.delete(ctrl)
    db.commit()


# ── readers ───────────────────────────────────────────────────────────────────
@router.post("/{controller_id}/readers", response_model=AccessReaderOut, status_code=status.HTTP_201_CREATED)
def add_reader(controller_id: int, body: AccessReaderCreate, db: Session = Depends(get_db)):
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    dup = db.query(AccessReader).filter(
        AccessReader.controller_id == controller_id,
        AccessReader.door_no == body.door_no,
        AccessReader.direction == body.direction,
    ).first()
    if dup:
        raise HTTPException(status_code=409,
                            detail=f"Door {body.door_no} {body.direction} reader already exists on this controller")
    reader = AccessReader(controller_id=controller_id, **body.model_dump())
    db.add(reader)
    db.commit()
    db.refresh(reader)
    return _reader_out(reader, db)


@router.put("/readers/{reader_id}", response_model=AccessReaderOut)
def update_reader(reader_id: int, body: AccessReaderUpdate, db: Session = Depends(get_db)):
    """Update a reader port — primarily used to assign its zone (entry/exit mapping)."""
    reader = db.query(AccessReader).filter(AccessReader.id == reader_id).first()
    if not reader:
        raise HTTPException(status_code=404, detail="Reader not found")
    if body.zone_id is not None and body.zone_id != 0:
        if not db.query(Zone).filter(Zone.id == body.zone_id).first():
            raise HTTPException(status_code=400, detail=f"Zone {body.zone_id} not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(reader, key, (None if key == "zone_id" and value == 0 else value))
    db.commit()
    db.refresh(reader)
    return _reader_out(reader, db)


@router.delete("/readers/{reader_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reader(reader_id: int, db: Session = Depends(get_db)):
    reader = db.query(AccessReader).filter(AccessReader.id == reader_id).first()
    if not reader:
        raise HTTPException(status_code=404, detail="Reader not found")
    db.delete(reader)
    db.commit()


# ── operations (C3 PULL protocol — transport pending hardware verification) ─────
@router.post("/{controller_id}/probe")
def probe_controller(controller_id: int, db: Session = Depends(get_db)):
    """Diagnose a real panel via the official ZKTeco PULL SDK: TCP reachability,
    SDK library presence, session handshake, and a RAW realtime-log sample (so the
    exact event format is confirmed against the device, not assumed)."""
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    # Prefer the pure-Python driver (the one actually used in prod); the Windows
    # PULL-SDK probe is only a fallback for a mounted libplcommpro.
    if c3_zkaccess.sdk_available():
        return c3_zkaccess.probe(ctrl.ip_address, ctrl.port or 4370, ctrl.comm_password or "")
    return c3_pull_sdk.probe(ctrl.ip_address, ctrl.port or 4370, ctrl.comm_password or "")


@router.get("/sdk/status", summary="Which C3 drivers are available?")
def sdk_status():
    return {
        "zkaccess_c3_available": c3_zkaccess.sdk_available(),   # pure-Python, standalone (preferred)
        "pull_sdk_available": c3_pull_sdk.sdk_available(),      # Windows plcommpro .so, if mounted
    }


@router.post("/{controller_id}/test")
def test_controller(controller_id: int, db: Session = Depends(get_db)):
    """Probe LAN reachability + C3 handshake. Updates the controller's status."""
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    # Prefer the pure-Python standalone driver; fall back to the scaffold.
    if c3_zkaccess.sdk_available():
        result = c3_zkaccess.test_connection(ctrl.ip_address, ctrl.port or 4370, ctrl.comm_password or "")
    else:
        result = c3.test_connection(ctrl.ip_address, ctrl.port or 4370, ctrl.comm_password or "")
    ctrl.status = "online" if result.get("success") else "error"
    ctrl.last_error = None if result.get("success") else result.get("error")
    db.commit()
    return result


@router.post("/{controller_id}/doors/{door_no}/open")
def open_door(controller_id: int, door_no: int, duration: int = 5, db: Session = Depends(get_db)):
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    # Prefer the pure-Python driver (standalone); fall back to the scaffold.
    if c3_zkaccess.sdk_available():
        try:
            with c3_zkaccess.ZKAccessC3Client(ctrl.ip_address, ctrl.port or 4370, ctrl.comm_password or "") as c:
                c.open_door(door_no, duration)
            return {"success": True, "message": f"Door {door_no} opened for {duration}s"}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}
    return c3.open_door(ctrl.ip_address, door_no, duration, ctrl.port or 4370, ctrl.comm_password or "")


@router.post("/{controller_id}/enroll", summary="Push personnel (users + cards) to the controller")
def enroll_personnel(controller_id: int, body: Optional[dict] = None, db: Session = Depends(get_db)):
    """Enrol personnel onto this access panel so they can badge at its doors.

    Body may include ``{"emp_codes": [...]}`` to limit the set; default = all
    active employees that have an emp_code. The employee's ``emp_code`` is used as
    the C3 'pin' (kept identical to the biometric/SeamlessHR identity), ``card_no``
    as the card, and every door on the controller is authorised.
    """
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    if not c3_zkaccess.sdk_available():
        raise HTTPException(status_code=503, detail="C3 driver (zkaccess-c3) unavailable")

    users, skipped = _panel_users(db, (body or {}).get("emp_codes"))

    door_nos = list(range(1, (ctrl.door_count or 1) + 1))
    result = c3_zkaccess.enroll_users(
        ctrl.ip_address, users, door_nos=door_nos,
        port=ctrl.port or 4370, password=ctrl.comm_password or "",
    )
    result["prepared"] = len(users)
    result["skipped_no_attendance_id"] = skipped
    return result


@router.post("/{controller_id}/poll")
def poll_controller(controller_id: int, db: Session = Depends(get_db)):
    """On-demand pull of buffered realtime events → zone occupancy engine."""
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    return poll_controller_once(ctrl, db)


@router.post("/{controller_id}/learn")
def learn_ports(controller_id: int, db: Session = Depends(get_db)):
    """Learn mode: badge at each reader and see which port fired. Auto-registers
    ports as they fire; does NOT affect zone occupancy. Used to map physical
    readers to zones with certainty before going live."""
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    return learn_controller_ports(ctrl, db)


# ── doors: what each one does in an emergency ─────────────────────────────────
_ROLE = {0: "No change", 1: "Lock in a fire", 2: "Fire exit — unlock in a fire"}


class DoorRoleIn(BaseModel):
    name: Optional[str] = None
    emergency_action: Optional[int] = Field(None, ge=0, le=2)


@router.get("/{controller_id}/doors", summary="This controller's doors and their emergency role")
def controller_doors(controller_id: int, db: Session = Depends(get_db)):
    from ..models.biotime_models import AccDoor
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    ensure_controller_doors(db, ctrl)
    doors = db.query(AccDoor).filter(AccDoor.controller_id == controller_id).order_by(AccDoor.port).all()
    return [{"id": d.id, "port": d.port, "name": d.name, "emergency_action": d.emergency_action or 0,
             "role": _ROLE.get(d.emergency_action or 0)} for d in doors]


@router.put("/doors/{door_id}", summary="Rename a door or set what it does in a fire")
def update_door_role(door_id: int, body: DoorRoleIn, db: Session = Depends(get_db)):
    from ..models.biotime_models import AccDoor
    d = db.query(AccDoor).filter(AccDoor.id == door_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Door not found")
    if body.name is not None and body.name.strip():
        d.name = body.name.strip()[:50]
    if body.emergency_action is not None:
        d.emergency_action = body.emergency_action
    db.commit()
    return {"id": d.id, "port": d.port, "name": d.name, "emergency_action": d.emergency_action,
            "role": _ROLE.get(d.emergency_action or 0)}


# ── sirens / strobes on AUX outputs ───────────────────────────────────────────
class SirenIn(BaseModel):
    aux_no: int = Field(..., ge=1, le=8)
    name: str = Field("Siren", max_length=100)
    device_type: int = Field(1, ge=1, le=2)        # 1 = siren, 2 = strobe
    zone_id: Optional[int] = None


@router.get("/{controller_id}/sirens", summary="Sirens / strobes wired to this controller")
def list_sirens(controller_id: int, db: Session = Depends(get_db)):
    from ..models.biotime_models import EmergencyDevice
    rows = db.query(EmergencyDevice).filter(EmergencyDevice.controller_id == controller_id).order_by(EmergencyDevice.aux_no).all()
    return [{"id": r.id, "aux_no": r.aux_no, "name": r.name, "device_type": r.device_type,
             "zone_id": r.zone_id, "status": r.status} for r in rows]


@router.post("/{controller_id}/sirens", status_code=status.HTTP_201_CREATED)
def add_siren(controller_id: int, body: SirenIn, db: Session = Depends(get_db)):
    from ..models.biotime_models import EmergencyDevice
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    if db.query(EmergencyDevice).filter(EmergencyDevice.controller_id == controller_id,
                                        EmergencyDevice.aux_no == body.aux_no).first():
        raise HTTPException(status_code=409, detail=f"AUX output {body.aux_no} already has a device")
    dev = EmergencyDevice(controller_id=controller_id, aux_no=body.aux_no, name=body.name.strip() or "Siren",
                          device_type=body.device_type, zone_id=body.zone_id, status=0)
    db.add(dev)
    db.commit()
    return {"id": dev.id, "aux_no": dev.aux_no, "name": dev.name, "device_type": dev.device_type,
            "zone_id": dev.zone_id, "status": dev.status}


@router.delete("/sirens/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_siren(device_id: int, db: Session = Depends(get_db)):
    from ..models.biotime_models import EmergencyDevice
    dev = db.query(EmergencyDevice).filter(EmergencyDevice.id == device_id, EmergencyDevice.controller_id.isnot(None)).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(dev)
    db.commit()


@router.post("/{controller_id}/aux/{aux_no}/test", summary="Sound an AUX output for a few seconds")
def test_aux(controller_id: int, aux_no: int, seconds: int = 3, db: Session = Depends(get_db)):
    ctrl = db.query(AccessController).filter(AccessController.id == controller_id).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Controller not found")
    try:
        with c3_zkaccess.ZKAccessC3Client(ctrl.ip_address, ctrl.port or 4370, ctrl.comm_password or "") as c:
            c.aux_output(aux_no, max(1, min(30, seconds)))
        return {"success": True, "message": f"AUX {aux_no} on for {seconds}s"}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}



def _panel_users(db: Session, emp_codes=None):
    """Active staff as C3 user records. PIN = Attendance ID; staff without one are skipped."""
    from sqlalchemy import text as _t
    from ..services.device_pin import is_valid_pin
    q = """SELECT emp_code, attendance_id, card_number,
                  COALESCE(NULLIF(full_name, ''), TRIM(CONCAT(first_name, ' ', last_name))) AS name
           FROM personnel WHERE is_active AND COALESCE(status, 'ACTIVE') <> 'TERMINATED'"""
    params = {}
    if emp_codes:
        q += " AND emp_code = ANY(:codes)"
        params["codes"] = list(emp_codes)
    users, skipped = [], 0
    for r in db.execute(_t(q), params).fetchall():
        if not is_valid_pin(r.attendance_id):
            skipped += 1
            continue
        users.append({"pin": str(r.attendance_id), "card_no": str(r.card_number) if r.card_number else "",
                      "name": (r.name or "")[:24]})
    return users, skipped


# ── issuing cards: tap an unknown card, give it to a person ──────────────────
class CardAssignIn(BaseModel):
    card_no: str = Field(..., pattern=r"^\d{1,20}$")
    emp_code: str


@router.get("/cards/unknown", summary="Cards tapped recently that belong to nobody")
def unknown_cards(db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t("""SELECT card_no, controller_id, door_no, reader_name, taps,
                                   last_seen AT TIME ZONE 'Africa/Lagos' AS last_seen
                            FROM controller_unknown_card ORDER BY last_seen DESC LIMIT 50""")).mappings().all()
    return [dict(r, last_seen=r["last_seen"].isoformat(sep=" ", timespec="seconds")) for r in rows]


@router.post("/cards/assign", summary="Issue a card to a person and load it onto every controller")
def assign_card(body: CardAssignIn, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    other = db.execute(_t("SELECT emp_code FROM personnel WHERE card_number = :c AND emp_code <> :e"),
                       {"c": int(body.card_no), "e": body.emp_code}).fetchone()
    if other:
        raise HTTPException(status_code=409, detail=f"Card {body.card_no} already belongs to {other.emp_code}")
    n = db.execute(_t("UPDATE personnel SET card_number = :c, updated_at = NOW() WHERE emp_code = :e AND is_active"),
                   {"c": int(body.card_no), "e": body.emp_code}).rowcount
    if not n:
        raise HTTPException(status_code=404, detail="No active person with that employee code")
    db.execute(_t("DELETE FROM controller_unknown_card WHERE card_no = :c"), {"c": body.card_no})
    db.commit()
    users, skipped = _panel_users(db, [body.emp_code])
    loaded = []
    if users and c3_zkaccess.sdk_available():
        for ctrl in db.query(AccessController).all():
            try:
                r = c3_zkaccess.enroll_users(ctrl.ip_address, users, door_nos=list(range(1, (ctrl.door_count or 1) + 1)),
                                             port=ctrl.port or 4370, password=ctrl.comm_password or "")
                loaded.append({"controller": ctrl.name, "ok": bool(r.get("pushed")), "failed": r.get("failed")})
            except Exception as exc:  # noqa: BLE001
                loaded.append({"controller": ctrl.name, "ok": False, "error": str(exc)[:200]})
    note = None if users else "Saved — but this person has no Attendance ID yet, so the card can't be loaded onto the panels."
    return {"success": True, "card_no": body.card_no, "emp_code": body.emp_code, "controllers": loaded, "note": note}
