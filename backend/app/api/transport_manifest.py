"""
Transport Manifest & Reconciliation API
Helideck / gangway check-in reconciliation for accurate POB tracking.
"""

import asyncio
import io
import logging
from datetime import datetime, date, time as dtime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.biotime_models import MusteringEvent, MusteringLog
from ..models.emergency import (
    ManifestEntry,
    Transport,
    TransportSchedule,
)
from ..models.personnel import Personnel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transport", tags=["Transport Manifest"])


# ─── Pydantic schemas ──────────────────────────────────────────────────────────

class FlightCreate(BaseModel):
    transport_identifier: str          # e.g. "ZS-HEL1" — created if not found
    transport_type: int = 3            # TransportType enum: 3 = HELICOPTER, 4 = VESSEL
    transport_operator: Optional[str] = None
    transport_capacity: int = 12
    transport_max_payload_kg: Optional[float] = None   # weight-and-balance limit (kg)

    schedule_type: str = "CHARTER"     # REGULAR, CHARTER, STANDBY
    departure_location: str
    arrival_location: str
    departure_time: datetime
    arrival_time: Optional[datetime] = None
    notes: Optional[str] = None

    # Recurring generation (e.g. daily/weekly crew-change rotations)
    repeat_frequency: Optional[str] = None   # DAILY | WEEKLY
    repeat_count: int = 1                     # number of occurrences incl. the first (cap 60)


class ManifestEntryCreate(BaseModel):
    passenger_name: str
    direction: str = "INBOUND"         # INBOUND / OUTBOUND
    emp_code: Optional[str] = None
    company: Optional[str] = None
    id_number: Optional[str] = None
    personnel_id: Optional[int] = None
    body_weight: Optional[float] = None      # kg
    baggage_weight: Optional[float] = None    # kg
    remarks: Optional[str] = None


class CheckInRequest(BaseModel):
    emp_code: str                      # from a badge / QR scan at the helideck / gangway


class ManifestEntryUpdate(BaseModel):
    status: str                        # CONFIRMED / NO_SHOW / OFFLOADED / MANIFESTED
    remarks: Optional[str] = None
    override_capacity: bool = False    # confirm even if the flight is at seat capacity
    override_compliance: bool = False  # board even if not fit to travel (expired medical/cert)
    override_weight: bool = False      # board even if it exceeds the weight-and-balance limit


class FlightStatusUpdate(BaseModel):
    status: str                        # SCHEDULED / CONFIRMED / CANCELLED / COMPLETED / IN_TRANSIT


class CrewMember(BaseModel):
    name: str
    role: str = "PILOT"                # PILOT / CO_PILOT / CAPTAIN / DRIVER / CREW
    license_no: Optional[str] = None


class CrewUpdate(BaseModel):
    crew: List[CrewMember]


class CargoItem(BaseModel):
    description: str
    weight_kg: float = 0
    type: str = "GENERAL"              # GENERAL / EQUIPMENT / FOOD / DANGEROUS_GOODS
    dangerous_goods: bool = False
    un_number: Optional[str] = None    # UN dangerous-goods number
    remarks: Optional[str] = None


class CargoUpdate(BaseModel):
    items: List[CargoItem]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _schedule_to_dict(s: TransportSchedule) -> Dict[str, Any]:
    entries = s.manifest_entries or []
    confirmed  = sum(1 for e in entries if e.status == "CONFIRMED")
    no_show    = sum(1 for e in entries if e.status == "NO_SHOW")
    offloaded  = sum(1 for e in entries if e.status == "OFFLOADED")
    manifested = sum(1 for e in entries if e.status == "MANIFESTED")
    inbound    = sum(1 for e in entries if e.direction == "INBOUND")
    outbound   = sum(1 for e in entries if e.direction == "OUTBOUND")

    t = s.transport
    capacity = (t.capacity if t and t.capacity else 0)
    seated = confirmed + manifested  # people who hold/took a seat
    body_kg    = sum((e.body_weight or 0) for e in entries)
    baggage_kg = sum((e.baggage_weight or 0) for e in entries)

    cargo = s.cargo_manifest or []
    cargo_kg = sum((c.get("weight_kg") or 0) for c in cargo if isinstance(c, dict))
    has_dg = any(c.get("dangerous_goods") for c in cargo if isinstance(c, dict))
    crew = s.crew or []

    # Departure delay (minutes) = actual − scheduled, once it has actually departed
    delay_min = None
    if s.actual_departure_time and s.departure_time:
        delay_min = round((s.actual_departure_time - s.departure_time).total_seconds() / 60)

    return {
        "id": s.id,
        "schedule_type": s.schedule_type,
        "departure_location": s.departure_location,
        "arrival_location": s.arrival_location,
        "departure_time": s.departure_time.isoformat() if s.departure_time else None,
        "arrival_time": s.arrival_time.isoformat() if s.arrival_time else None,
        "actual_departure_time": s.actual_departure_time.isoformat() if s.actual_departure_time else None,
        "actual_arrival_time": s.actual_arrival_time.isoformat() if s.actual_arrival_time else None,
        "departure_delay_min": delay_min,
        "status": s.status,
        "transport": {
            "id": t.id,
            "identifier": t.identifier,
            "type": t.type,
            "operator": t.operator,
            "capacity": t.capacity,
        } if t else None,
        "pax_total": len(entries),
        "pax_confirmed": confirmed,
        "pax_no_show": no_show,
        "pax_offloaded": offloaded,
        "pax_manifested": manifested,
        "pax_inbound": inbound,
        "pax_outbound": outbound,
        # Seats & weight-and-balance
        "capacity": capacity,
        "seats_taken": seated,
        "seats_available": max(capacity - seated, 0) if capacity else None,
        "overbooked": bool(capacity and seated > capacity),
        "body_weight_kg": round(body_kg, 1),
        "baggage_weight_kg": round(baggage_kg, 1),
        "cargo_weight_kg": round(cargo_kg, 1),
        "total_weight_kg": round(body_kg + baggage_kg + cargo_kg, 1),
        "max_payload_kg": (t.max_payload_kg if t else None),
        "over_payload": bool(t and t.max_payload_kg and (body_kg + baggage_kg + cargo_kg) > t.max_payload_kg),
        # Crew & cargo
        "crew": crew,
        "crew_count": len(crew),
        "cargo": cargo,
        "cargo_count": len(cargo),
        "has_dangerous_goods": has_dg,
        "is_reconciled": manifested == 0 and len(entries) > 0,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _entry_to_dict(e: ManifestEntry) -> Dict[str, Any]:
    return {
        "id": e.id,
        "schedule_id": e.schedule_id,
        "passenger_name": e.passenger_name,
        "emp_code": e.emp_code,
        "company": e.company,
        "id_number": e.id_number,
        "direction": e.direction,
        "status": e.status,
        "personnel_id": e.personnel_id,
        "body_weight": e.body_weight,
        "baggage_weight": e.baggage_weight,
        "confirmed_at": e.confirmed_at.isoformat() if e.confirmed_at else None,
        "confirmed_by_id": e.confirmed_by_id,
        "remarks": e.remarks,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _parse_date(v):
    """Best-effort date parse from mixed JSONB / DB values. None if unparseable."""
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v)[:19]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:len(fmt) + 2], fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def travel_compliance(p: Optional[Personnel]) -> Dict[str, Any]:
    """Assess fitness to travel: medical + safety training / certifications.

    status: ok | warning | blocked. `blocked` = an expired critical record (should
    stop boarding); `warning` = missing or soon-to-expire records (allow, but flag).
    Never raises — an unparseable record is simply skipped.
    """
    if p is None:
        return {"status": "warning", "issues": ["Guest / not a registered person — no compliance records"]}

    issues: List[str] = []
    blocked = warning = False
    today = date.today()
    soon = today + timedelta(days=30)

    med = _parse_date(getattr(p, "medical_fitness_date", None))
    if med is None:
        pass   # judged below: missing records are "unknown", not a warning
    elif med < today:
        issues.append(f"Medical expired {med.isoformat()}"); blocked = True
    elif med <= soon:
        issues.append(f"Medical expires {med.isoformat()}"); warning = True

    def _scan(records) -> bool:
        nonlocal blocked, warning
        items = records if isinstance(records, list) else (records.get("items", []) if isinstance(records, dict) else [])
        found = False
        for it in items:
            if not isinstance(it, dict):
                continue
            exp = _parse_date(it.get("expiry_date") or it.get("valid_until")
                              or it.get("expires") or it.get("expiry") or it.get("valid_to"))
            if exp is None:
                continue
            found = True
            name = it.get("name") or it.get("type") or it.get("title") or "Certification"
            if exp < today:
                issues.append(f"{name} expired {exp.isoformat()}"); blocked = True
            elif exp <= soon:
                issues.append(f"{name} expires {exp.isoformat()}"); warning = True
        return found

    has_training = _scan(getattr(p, "training_records", None))
    has_certs = _scan(getattr(p, "certifications", None))
    if med is None and not has_training and not has_certs:
        # No records at all (nothing feeds them yet — SeamlessHR does not send them).
        # Flagging every passenger as a warning teaches people to ignore the column;
        # report "unknown" and keep blocking only on a record that has EXPIRED.
        return {"status": "unknown", "issues": ["No medical / training records on file"]}

    status = "blocked" if blocked else ("warning" if warning else "ok")
    return {"status": status, "issues": issues}


# ─── Site time, permissions ─────────────────────────────────────────────────────

def _site_tz():
    from ..services.attendance_calculation_service import SITE_TZ
    return SITE_TZ


def _site_today() -> date:
    return datetime.now(_site_tz()).date()


def _site_day_bounds(d: date):
    """[start, end) of a SITE calendar day as aware datetimes. Day filters used UTC
    midnight, so a 00:30 Lagos flight was listed (and counted) on the previous day."""
    start = datetime.combine(d, dtime.min, tzinfo=_site_tz())
    return start, start + timedelta(days=1)


def _perm(request: Optional[Request], code: str) -> bool:
    perms = getattr(getattr(request, "state", None), "user_permissions", None) or []
    return "*" in perms or code in perms


# ─── POB movements (driven by the flight's REAL status) ─────────────────────────
#
# Confirming a passenger means "checked in / boarded" — nothing more. POB changes
# only when the flight actually moves:
#   OUTBOUND passenger  → off board when the flight DEPARTS (IN_TRANSIT/COMPLETED)
#   INBOUND passenger   → on board when the flight ARRIVES (COMPLETED)
# Previously POB changed at confirm: a cancelled inbound flight left its passengers
# "on board", and an outbound passenger was taken off POB (and marked safe in an
# active muster) while still standing on the helideck. _sync_entry_pob is the single
# rule, re-run after every change, so every case is also reversible.

_DEPARTED = {"IN_TRANSIT", "COMPLETED"}
_ARRIVED = {"COMPLETED"}

_FLIGHT_TRANSITIONS = {
    "SCHEDULED":  {"CONFIRMED", "IN_TRANSIT", "COMPLETED", "CANCELLED"},
    "CONFIRMED":  {"SCHEDULED", "IN_TRANSIT", "COMPLETED", "CANCELLED"},
    "IN_TRANSIT": {"COMPLETED", "CANCELLED"},          # cancelled in transit = turned back
    "CANCELLED":  {"SCHEDULED"},                        # reinstate
    "COMPLETED":  set(),
}


def _zone_for_location(db: Session, location: Optional[str]) -> Optional[int]:
    """Zone whose name or code is the arrival/departure point (e.g. 'Helideck')."""
    if not location:
        return None
    row = db.execute(text(
        "SELECT id FROM zones WHERE lower(name) = lower(:l) OR lower(code) = lower(:l) "
        "ORDER BY id LIMIT 1"), {"l": location.strip()}).fetchone()
    return row[0] if row else None


def _go_onboard(db: Session, personnel_id: int, location: Optional[str]) -> None:
    from .adms_protocol import _recalc_zone_occupancy
    p = db.execute(text("SELECT emp_code, current_zone_id FROM personnel WHERE id = :i"),
                   {"i": personnel_id}).fetchone()
    if not p:
        return
    zone_id = _zone_for_location(db, location)
    db.execute(text("""
        UPDATE personnel SET is_onboard = TRUE, is_pob = TRUE,
               pob_since = COALESCE(pob_since, NOW()), pob_location = :loc,
               current_location = COALESCE(:loc, current_location),
               last_seen = NOW(), updated_at = NOW()
        WHERE id = :i
    """), {"i": personnel_id, "loc": location})
    if zone_id and p.current_zone_id != zone_id:
        # Place them in the arrival point's zone so they show on the live map.
        if p.current_zone_id:
            db.execute(text("""INSERT INTO zone_personnel_tracking
                (zone_id, emp_code, device_sn, event_type, punch_time, previous_zone_id)
                VALUES (:z, :ec, 'TRANSPORT', 'CLOCK_OUT', NOW(), :z)"""),
                {"z": p.current_zone_id, "ec": p.emp_code})
        db.execute(text("""INSERT INTO zone_personnel_tracking
            (zone_id, emp_code, device_sn, event_type, punch_time, previous_zone_id)
            VALUES (:z, :ec, 'TRANSPORT', 'CLOCK_IN', NOW(), :pz)"""),
            {"z": zone_id, "ec": p.emp_code, "pz": p.current_zone_id})
        db.execute(text("UPDATE personnel SET current_zone_id = :z WHERE id = :i"),
                   {"z": zone_id, "i": personnel_id})
        for z in {zone_id, p.current_zone_id} - {None}:
            _recalc_zone_occupancy(z, db)


def _go_offboard(db: Session, personnel_id: int) -> None:
    from ..services.database_admin_service import _off_board
    _off_board(db, "id = :pid", {"pid": personnel_id})
    db.execute(text("UPDATE personnel SET pob_location = NULL WHERE id = :i"), {"i": personnel_id})


def _mark_departed_in_muster(db: Session, emp_code: Optional[str], user_id) -> None:
    """A passenger who has actually flown out is not on the installation: mark them
    accounted-for in any active muster so they are not searched for."""
    if not emp_code:
        return
    active_event = db.query(MusteringEvent).filter(MusteringEvent.status == 0).first()
    if not active_event:
        return
    log = db.query(MusteringLog).filter(MusteringLog.event_id == active_event.id,
                                        MusteringLog.emp_code == emp_code).first()
    if log and log.status != 1:
        from ..services.mustering_service import MusteringService
        MusteringService(db).mark_person_status(active_event.id, emp_code, status=1,
                                                marked_by=user_id or 0)


def _sync_entry_pob(db: Session, schedule: TransportSchedule, entry: ManifestEntry,
                    user_id=None, removing: bool = False) -> None:
    """Make this passenger's POB state match reality. Idempotent."""
    if not entry.personnel_id:
        return
    st = (schedule.status or "").upper()
    should = (not removing and entry.status == "CONFIRMED" and (
        (entry.direction == "OUTBOUND" and st in _DEPARTED) or
        (entry.direction == "INBOUND" and st in _ARRIVED)))
    if should and not entry.pob_applied_at:
        if entry.direction == "OUTBOUND":
            _go_offboard(db, entry.personnel_id)
            _mark_departed_in_muster(db, entry.emp_code, user_id)
        else:
            _go_onboard(db, entry.personnel_id, schedule.arrival_location)
        entry.pob_applied_at = datetime.now(timezone.utc)
    elif not should and entry.pob_applied_at:
        # Undo: an outbound passenger whose flight turned back (or who was offloaded /
        # removed after departure) is back where they left from; an inbound passenger
        # recorded as arrived by mistake is taken off again.
        if entry.direction == "OUTBOUND":
            _go_onboard(db, entry.personnel_id, schedule.departure_location)
        else:
            _go_offboard(db, entry.personnel_id)
        entry.pob_applied_at = None


# ─── Flight endpoints ──────────────────────────────────────────────────────────

@router.get("/flights")
async def list_flights(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    flight_status: Optional[str] = Query(None, alias="status"),
    direction: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    """List flights with optional date/status filters. Defaults to today ± 7 days."""
    if date_from is None:
        date_from = _site_today() - timedelta(days=7)
    if date_to is None:
        date_to = _site_today() + timedelta(days=7)

    q = (
        db.query(TransportSchedule)
        .options(
            joinedload(TransportSchedule.transport),
            joinedload(TransportSchedule.manifest_entries),
        )
        .filter(
            TransportSchedule.departure_time >= _site_day_bounds(date_from)[0],
            TransportSchedule.departure_time < _site_day_bounds(date_to)[1],
        )
    )
    if flight_status:
        q = q.filter(TransportSchedule.status == flight_status.upper())

    schedules = q.order_by(TransportSchedule.departure_time).all()

    # Optional direction filter — filter schedules that have entries in that direction
    if direction:
        direction_up = direction.upper()
        schedules = [
            s for s in schedules
            if any(e.direction == direction_up for e in (s.manifest_entries or []))
            or not s.manifest_entries  # include empty flights too
        ]

    return {
        "flights": [_schedule_to_dict(s) for s in schedules],
        "total": len(schedules),
        "date_from": str(date_from),
        "date_to": str(date_to),
    }


@router.post("/flights", status_code=status.HTTP_201_CREATED)
async def create_flight(
    payload: FlightCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new flight/voyage schedule, auto-creating the transport if not found."""
    transport = (
        db.query(Transport)
        .filter(Transport.identifier == payload.transport_identifier)
        .first()
    )
    if transport:
        # Details the user actually filled in update the aircraft/vessel — they were
        # frozen at first use, so a wrong capacity or payload limit could never be fixed.
        sent = payload.__fields_set__
        if "transport_capacity" in sent and payload.transport_capacity:
            transport.capacity = payload.transport_capacity
        if "transport_max_payload_kg" in sent:
            transport.max_payload_kg = payload.transport_max_payload_kg
        if "transport_operator" in sent and payload.transport_operator:
            transport.operator = payload.transport_operator
        if "transport_type" in sent:
            transport.type = payload.transport_type
    if not transport:
        transport = Transport(
            identifier=payload.transport_identifier,
            type=payload.transport_type,
            operator=payload.transport_operator,
            capacity=payload.transport_capacity,
            max_payload_kg=payload.transport_max_payload_kg,
            is_available=True,
        )
        db.add(transport)
        db.flush()

    # Build the departure/arrival times for each occurrence (recurring rotations).
    step = None
    freq = (payload.repeat_frequency or "").upper()
    if freq == "DAILY":
        step = timedelta(days=1)
    elif freq == "WEEKLY":
        step = timedelta(weeks=1)
    occurrences = max(1, min(payload.repeat_count or 1, 60)) if step else 1

    first_schedule = None
    for i in range(occurrences):
        offset = (step * i) if step else timedelta(0)
        schedule = TransportSchedule(
            transport_id=transport.id,
            schedule_type=payload.schedule_type,
            departure_location=payload.departure_location,
            arrival_location=payload.arrival_location,
            departure_time=payload.departure_time + offset,
            arrival_time=(payload.arrival_time + offset) if payload.arrival_time else None,
            frequency=freq or None,
            status="SCHEDULED",
            special_requirements=payload.notes,
        )
        db.add(schedule)
        if first_schedule is None:
            db.flush()
            first_schedule = schedule
    db.commit()

    schedule = (
        db.query(TransportSchedule)
        .options(
            joinedload(TransportSchedule.transport),
            joinedload(TransportSchedule.manifest_entries),
        )
        .filter(TransportSchedule.id == first_schedule.id)
        .one()
    )
    out = _schedule_to_dict(schedule)
    out["occurrences_created"] = occurrences
    return out


@router.get("/flights/{flight_id}")
async def get_flight(
    flight_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    schedule = (
        db.query(TransportSchedule)
        .options(
            joinedload(TransportSchedule.transport),
            joinedload(TransportSchedule.manifest_entries),
        )
        .filter(TransportSchedule.id == flight_id)
        .first()
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Flight not found")
    return _schedule_to_dict(schedule)


@router.patch("/flights/{flight_id}/status")
async def update_flight_status(
    flight_id: int,
    payload: FlightStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    schedule = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Flight not found")

    new_status = payload.status.upper()
    cur = (schedule.status or "SCHEDULED").upper()
    if new_status != cur and new_status not in _FLIGHT_TRANSITIONS.get(cur, set()):
        raise HTTPException(status_code=400, detail=f"A {cur} flight cannot be changed to {new_status}")
    now = datetime.now(timezone.utc)
    # Stamp actuals on the real-world transitions so delays can be computed.
    if new_status == "IN_TRANSIT" and not schedule.actual_departure_time:
        schedule.actual_departure_time = now
    if new_status == "COMPLETED" and not schedule.actual_arrival_time:
        schedule.actual_arrival_time = now
        if not schedule.actual_departure_time:  # completed without an explicit depart
            schedule.actual_departure_time = schedule.departure_time

    schedule.status = new_status
    # POB follows the real movement: departure takes outbound passengers off,
    # arrival puts inbound passengers on, and cancelling (turned back) undoes both.
    for e in db.query(ManifestEntry).filter(ManifestEntry.schedule_id == flight_id).all():
        _sync_entry_pob(db, schedule, e, getattr(_, "id", None))
    db.commit()
    delay = None
    if schedule.actual_departure_time and schedule.departure_time:
        delay = round((schedule.actual_departure_time - schedule.departure_time).total_seconds() / 60)
    return {
        "id": flight_id,
        "status": schedule.status,
        "actual_departure_time": schedule.actual_departure_time.isoformat() if schedule.actual_departure_time else None,
        "actual_arrival_time": schedule.actual_arrival_time.isoformat() if schedule.actual_arrival_time else None,
        "departure_delay_min": delay,
    }


# ─── Manifest endpoints ────────────────────────────────────────────────────────

@router.get("/flights/{flight_id}/manifest")
async def get_manifest(
    flight_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    schedule = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Flight not found")

    entries = (
        db.query(ManifestEntry)
        .filter(ManifestEntry.schedule_id == flight_id)
        .order_by(ManifestEntry.direction, ManifestEntry.passenger_name)
        .all()
    )

    # Resolve compliance for all registered passengers in one query
    pids = [e.personnel_id for e in entries if e.personnel_id]
    people = {p.id: p for p in db.query(Personnel).filter(Personnel.id.in_(pids)).all()} if pids else {}

    out_entries = []
    for e in entries:
        d = _entry_to_dict(e)
        d["compliance"] = travel_compliance(people.get(e.personnel_id) if e.personnel_id else None)
        out_entries.append(d)

    return {
        "flight_id": flight_id,
        "entries": out_entries,
        "total": len(entries),
        "summary": _schedule_to_dict(schedule),
    }


@router.post("/flights/{flight_id}/manifest", status_code=status.HTTP_201_CREATED)
async def add_manifest_entry(
    flight_id: int,
    payload: ManifestEntryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Add a passenger to the manifest. If emp_code given, auto-fills name from personnel."""
    schedule = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Flight not found")
    if schedule.status in ("COMPLETED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Cannot add passengers to a {schedule.status} flight")

    personnel_id = payload.personnel_id
    passenger_name = payload.passenger_name.strip()

    # Auto-lookup by emp_code / personnel_id (also used for the compliance check)
    person = None
    if personnel_id:
        person = db.query(Personnel).filter(Personnel.id == personnel_id).first()
    elif payload.emp_code:
        person = db.query(Personnel).filter(Personnel.emp_code == payload.emp_code).first()
        if person:
            personnel_id = person.id
    if person and not passenger_name:
        passenger_name = f"{person.first_name} {person.last_name}".strip()
    # Store the person's real code even when they were picked by id — badge check-in,
    # the helideck reader and reconcile all match on emp_code.
    emp_code = (person.emp_code if person else None) or payload.emp_code
    if person or emp_code:
        dup = db.query(ManifestEntry).filter(
            ManifestEntry.schedule_id == flight_id,
            (ManifestEntry.personnel_id == personnel_id) if person else (ManifestEntry.emp_code == emp_code),
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"{passenger_name} is already on this manifest")

    entry = ManifestEntry(
        schedule_id=flight_id,
        personnel_id=personnel_id,
        passenger_name=passenger_name,
        emp_code=emp_code,
        company=payload.company,
        id_number=payload.id_number,
        body_weight=payload.body_weight,
        baggage_weight=payload.baggage_weight,
        direction=payload.direction.upper(),
        status="MANIFESTED",
        remarks=payload.remarks,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    out = _entry_to_dict(entry)
    out["compliance"] = travel_compliance(person)
    return out


def _set_entry_status(db: Session, flight_id: int, entry: ManifestEntry,
                      payload: "ManifestEntryUpdate", user_id=None,
                      can_override: bool = False, actor: str = "") -> Dict[str, Any]:
    """Core of confirm / no-show / offload / reset — shared by the manifest screen,
    badge check-in and the helideck reader. Raises HTTPException on a limit."""
    schedule = (db.query(TransportSchedule).options(joinedload(TransportSchedule.transport))
                .filter(TransportSchedule.id == flight_id).first())
    if not schedule:
        raise HTTPException(status_code=404, detail="Flight not found")
    if (schedule.status or "").upper() == "CANCELLED":
        raise HTTPException(status_code=400, detail="This flight is cancelled — reinstate it first")

    new_status = payload.status.upper()
    allowed = {"MANIFESTED", "CONFIRMED", "NO_SHOW", "OFFLOADED"}
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {allowed}")

    overrides = [n for n, f in (("seat capacity", payload.override_capacity),
                                ("fitness to travel", payload.override_compliance),
                                ("weight limit", payload.override_weight)) if f]
    if overrides:
        # Boarding someone over a safety limit is a deliberate, accountable decision.
        if not can_override:
            raise HTTPException(status_code=403,
                                detail="Overriding a boarding limit needs the transport.override permission")
        if not (payload.remarks or "").strip():
            raise HTTPException(status_code=400, detail="Give a reason for the override")

    if new_status == "CONFIRMED" and entry.status != "CONFIRMED":
        t = schedule.transport
        cap = t.capacity if t else None
        if cap and not payload.override_capacity:
            already = db.query(ManifestEntry).filter(
                ManifestEntry.schedule_id == flight_id, ManifestEntry.status == "CONFIRMED",
                ManifestEntry.id != entry.id).count()
            if already >= cap:
                raise HTTPException(status_code=409,
                                    detail=f"Flight is at capacity ({already}/{cap}). Offload a passenger or override.")

        if entry.personnel_id and not payload.override_compliance:
            person = db.query(Personnel).filter(Personnel.id == entry.personnel_id).first()
            comp = travel_compliance(person)
            if comp["status"] == "blocked":
                raise HTTPException(status_code=409,
                                    detail=f"Not fit to travel — {'; '.join(comp['issues'])}. Override to board.")

        max_kg = getattr(t, "max_payload_kg", None) if t else None
        if max_kg and not payload.override_weight:
            # A missing weight used to count as 0 kg, silently defeating the limit.
            if entry.body_weight is None:
                raise HTTPException(status_code=409,
                                    detail="Passenger weight missing — enter body weight (kg) before boarding "
                                           "(this aircraft/vessel has a payload limit).")
            confirmed_wt = (db.query(func.coalesce(func.sum(
                func.coalesce(ManifestEntry.body_weight, 0) + func.coalesce(ManifestEntry.baggage_weight, 0)), 0))
                .filter(ManifestEntry.schedule_id == flight_id, ManifestEntry.status == "CONFIRMED",
                        ManifestEntry.id != entry.id).scalar() or 0)
            cargo_wt = sum((c.get("weight_kg") or 0) for c in (schedule.cargo_manifest or []) if isinstance(c, dict))
            projected = float(confirmed_wt) + float(cargo_wt) + float(entry.body_weight or 0) + float(entry.baggage_weight or 0)
            if projected > float(max_kg):
                raise HTTPException(status_code=409,
                                    detail=f"Over payload limit — {projected:.0f} kg would exceed {max_kg:.0f} kg. "
                                           f"Offload weight or override.")

    entry.status = new_status
    if payload.remarks is not None:
        entry.remarks = payload.remarks
    if overrides:
        note = f"[OVERRIDE {', '.join(overrides)} by {actor or user_id}] {payload.remarks.strip()}"
        entry.remarks = note
        logger.warning("Transport override on flight %s passenger %s: %s", flight_id, entry.passenger_name, note)
    if new_status == "CONFIRMED":
        entry.confirmed_at = datetime.now(timezone.utc)
        entry.confirmed_by_id = user_id
    else:
        entry.confirmed_at = None
        entry.confirmed_by_id = None

    _sync_entry_pob(db, schedule, entry, user_id)
    db.commit()
    return _entry_to_dict(entry)


@router.patch("/flights/{flight_id}/manifest/{entry_id}")
async def update_manifest_entry(
    flight_id: int,
    entry_id: int,
    payload: ManifestEntryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Confirm (boarded), mark no-show, offload, or reset a passenger. POB itself
    moves with the flight's departure / arrival — see _sync_entry_pob."""
    entry = (db.query(ManifestEntry)
             .filter(ManifestEntry.id == entry_id, ManifestEntry.schedule_id == flight_id).first())
    if not entry:
        raise HTTPException(status_code=404, detail="Manifest entry not found")
    return _set_entry_status(db, flight_id, entry, payload, getattr(current_user, "id", None),
                             can_override=_perm(request, "transport.override"),
                             actor=getattr(current_user, "username", "") or getattr(current_user, "email", ""))


@router.post("/flights/{flight_id}/checkin")
async def checkin_by_badge(
    flight_id: int,
    payload: CheckInRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Check a passenger in by scanning their badge / QR / reader PIN at the
    helideck or gangway."""
    from ..services.device_pin import resolve_emp_code
    raw = (payload.emp_code or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="emp_code is required")
    emp = resolve_emp_code(db, raw)   # a scanned reader PIN (Attendance ID) → emp_code
    entry = (db.query(ManifestEntry)
             .filter(ManifestEntry.schedule_id == flight_id,
                     func.lower(ManifestEntry.emp_code).in_([emp.lower(), raw.lower()]))
             .order_by(ManifestEntry.id).first())
    if not entry:
        raise HTTPException(status_code=404, detail=f"{raw} is not on this flight's manifest")
    if entry.status == "CONFIRMED":
        return {**_entry_to_dict(entry), "already_checked_in": True}
    result = _set_entry_status(db, flight_id, entry, ManifestEntryUpdate(status="CONFIRMED"),
                               getattr(current_user, "id", None))
    result["checked_in"] = True
    result["passenger_name"] = entry.passenger_name
    return result


def checkin_from_reader(db: Session, emp_code: str, punch_time: datetime, device_sn: str) -> Optional[str]:
    """A tap on a reader set to TRANSPORT_CHECKIN (helideck / gangway / heliport)
    checks the person in to their next flight: the one they are manifested on that
    departs between 1 h before and 6 h after the tap. A blocked boarding (capacity,
    weight, fitness) raises a notification instead of boarding them silently."""
    pt = punch_time if punch_time.tzinfo else punch_time.replace(tzinfo=timezone.utc)
    entry = (db.query(ManifestEntry).join(TransportSchedule)
             .filter(func.lower(ManifestEntry.emp_code) == (emp_code or "").lower(),
                     ManifestEntry.status.in_(["MANIFESTED", "NO_SHOW"]),
                     TransportSchedule.status.in_(["SCHEDULED", "CONFIRMED"]),
                     TransportSchedule.departure_time >= pt - timedelta(hours=1),
                     TransportSchedule.departure_time <= pt + timedelta(hours=6))
             .order_by(TransportSchedule.departure_time).first())
    if not entry:
        return None
    try:
        _set_entry_status(db, entry.schedule_id, entry, ManifestEntryUpdate(status="CONFIRMED"),
                          actor=f"reader {device_sn}")
        return "checked_in"
    except HTTPException as e:
        db.rollback()
        db.execute(text("""
            INSERT INTO sys_notifications (dedup_key, notification_type, title, message, priority, expires_at)
            VALUES (:dk, 'transport_checkin_blocked', :t, :m, 'high', NOW() + INTERVAL '1 day')
            ON CONFLICT (dedup_key) DO NOTHING
        """), {"dk": f"tcheckin_{entry.id}_{pt:%Y%m%d%H%M}",
               "t": f"Check-in blocked: {entry.passenger_name}",
               "m": f"{entry.passenger_name} tapped at {device_sn} but could not be boarded on flight "
                    f"#{entry.schedule_id}: {e.detail}"})
        db.commit()
        return "blocked"


# ─── Crew & cargo (per-journey) ─────────────────────────────────────────────────

@router.get("/flights/{flight_id}/crew")
async def get_crew(flight_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    s = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Flight not found")
    return {"crew": s.crew or []}


@router.put("/flights/{flight_id}/crew")
async def set_crew(flight_id: int, payload: CrewUpdate, db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    s = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Flight not found")
    s.crew = [m.dict() for m in payload.crew]
    db.commit()
    return {"crew": s.crew}


@router.get("/flights/{flight_id}/cargo")
async def get_cargo(flight_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    s = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Flight not found")
    items = s.cargo_manifest or []
    return {
        "items": items,
        "total_weight_kg": round(sum((c.get("weight_kg") or 0) for c in items if isinstance(c, dict)), 1),
        "has_dangerous_goods": any(c.get("dangerous_goods") for c in items if isinstance(c, dict)),
    }


@router.put("/flights/{flight_id}/cargo")
async def set_cargo(flight_id: int, payload: CargoUpdate, db: Session = Depends(get_db),
                    _=Depends(get_current_user)):
    s = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Flight not found")
    s.cargo_manifest = [i.dict() for i in payload.items]
    db.commit()
    return {"items": s.cargo_manifest}


# ─── Notifications, export & analytics ──────────────────────────────────────────

class NotifyBody(BaseModel):
    subject: Optional[str] = None
    message: Optional[str] = None
    email: bool = True
    sms: bool = False


@router.post("/flights/{flight_id}/notify")
async def notify_passengers(flight_id: int, payload: NotifyBody, db: Session = Depends(get_db),
                            _=Depends(get_current_user)) -> Dict[str, Any]:
    """Notify the manifested passengers of this flight by email / SMS (booking,
    schedule change, delay). Reuses the shared env-configured senders."""
    s = (
        db.query(TransportSchedule)
        .options(joinedload(TransportSchedule.transport), joinedload(TransportSchedule.manifest_entries))
        .filter(TransportSchedule.id == flight_id).first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Flight not found")

    ident = s.transport.identifier if s.transport else f"#{flight_id}"
    route = f"{s.departure_location} → {s.arrival_location}"
    when = s.departure_time.astimezone(_site_tz()).strftime("%d %b %Y %H:%M") if s.departure_time else "TBC"
    subject = payload.subject or f"Transport {ident}: {route}"
    body = payload.message or (
        f"You are manifested on {ident} ({route}), departing {when}. "
        f"Please be at the departure point in good time with your ID."
    )

    result = await _notify_passengers(db, s, subject, body, payload.email, payload.sms)
    return {"success": True, "result": result}


async def _notify_passengers(db: Session, s: TransportSchedule, subject: str, body: str,
                             email: bool = True, sms: bool = False) -> Dict[str, Any]:
    entries = [e for e in (s.manifest_entries or []) if e.status not in ("NO_SHOW", "OFFLOADED")]
    pids = [e.personnel_id for e in entries if e.personnel_id]
    people = {p.id: p for p in db.query(Personnel).filter(Personnel.id.in_(pids)).all()} if pids else {}
    result: Dict[str, Any] = {"email": None, "sms": None}

    if email:
        from ..services.notify_email import send_email, smtp_configured
        emails = sorted({people[e.personnel_id].email for e in entries
                         if e.personnel_id and people.get(e.personnel_id) and people[e.personnel_id].email})
        if not smtp_configured():
            result["email"] = {"sent": 0, "error": "Email not configured (Settings → Email)"}
        else:
            result["email"] = await asyncio.to_thread(send_email, list(emails), subject, f"<p>{body}</p>", body)

    if sms:
        from ..services.notify_sms import send_sms, sms_configured
        phones = sorted({(people[e.personnel_id].phone or people[e.personnel_id].emergency_contact_phone)
                         for e in entries if e.personnel_id and people.get(e.personnel_id)
                         and (people[e.personnel_id].phone or people[e.personnel_id].emergency_contact_phone)})
        if not sms_configured():
            result["sms"] = {"sent": 0, "error": "SMS gateway not configured"}
        else:
            result["sms"] = await asyncio.to_thread(send_sms, list(phones), body)
    return result


class FlightUpdate(BaseModel):
    departure_location: Optional[str] = None
    arrival_location: Optional[str] = None
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    schedule_type: Optional[str] = None
    notes: Optional[str] = None
    notify: bool = True          # tell passengers when the time changes


@router.put("/flights/{flight_id}")
async def update_flight(flight_id: int, payload: FlightUpdate, db: Session = Depends(get_db),
                        current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Reschedule / edit a flight (there was no way to change one once created). A
    time change notifies the passengers automatically when email/SMS is set up."""
    s = (db.query(TransportSchedule)
         .options(joinedload(TransportSchedule.transport), joinedload(TransportSchedule.manifest_entries))
         .filter(TransportSchedule.id == flight_id).first())
    if not s:
        raise HTTPException(status_code=404, detail="Flight not found")
    if (s.status or "").upper() in ("COMPLETED", "CANCELLED", "IN_TRANSIT"):
        raise HTTPException(status_code=400, detail=f"A {s.status} flight cannot be edited")
    old_dep = s.departure_time
    data = payload.dict(exclude_unset=True)
    data.pop("notify", None)
    if "notes" in data:
        s.special_requirements = data.pop("notes")
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    out = _schedule_to_dict(s)
    moved = payload.departure_time and old_dep and abs((payload.departure_time - old_dep).total_seconds()) >= 60
    if moved and payload.notify and s.manifest_entries:
        ident = s.transport.identifier if s.transport else f"#{flight_id}"
        when = s.departure_time.astimezone(_site_tz()).strftime("%d %b %Y %H:%M")
        out["notified"] = await _notify_passengers(
            db, s, f"Schedule change: {ident} {s.departure_location} → {s.arrival_location}",
            f"Your transport {ident} ({s.departure_location} → {s.arrival_location}) now departs {when}.",
            email=True, sms=True)
    return out


@router.get("/flights/{flight_id}/manifest.xlsx")
async def export_manifest_xlsx(flight_id: int, db: Session = Depends(get_db),
                               _=Depends(get_current_user)):
    """Download a printable Excel manifest for the pilot / captain."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    s = (
        db.query(TransportSchedule)
        .options(joinedload(TransportSchedule.transport), joinedload(TransportSchedule.manifest_entries))
        .filter(TransportSchedule.id == flight_id).first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Flight not found")

    summary = _schedule_to_dict(s)
    ident = s.transport.identifier if s.transport else f"#{flight_id}"
    wb = Workbook()
    ws = wb.active
    ws.title = "Manifest"
    thin = Side(style="thin", color="FFB0B0B0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr_fill = PatternFill("solid", fgColor="FF1E3A8A")

    ws.merge_cells("A1:G1")
    ws["A1"] = f"TRANSPORT MANIFEST — {ident}"
    ws["A1"].font = Font(bold=True, size=15, color="FFFFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="FF111827")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    meta = [
        ("Route", f"{s.departure_location} → {s.arrival_location}"),
        ("Departure", s.departure_time.astimezone(_site_tz()).strftime("%d %b %Y  %H:%M") if s.departure_time else "—"),
        ("Operator", (s.transport.operator if s.transport else "") or "—"),
        ("Crew", ", ".join(f"{c.get('name')} ({c.get('role')})" for c in (s.crew or [])) or "—"),
        ("Weight", f"{summary['total_weight_kg']} kg  (pax {summary['body_weight_kg']} + bag {summary['baggage_weight_kg']} + cargo {summary['cargo_weight_kg']})"),
        ("Seats", f"{summary['seats_taken']}/{summary['capacity'] or '—'}"),
    ]
    r = 2
    for label, val in meta:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
        ws.cell(row=r, column=2, value=val)
        r += 1

    r += 1
    headers = ["#", "Passenger", "Emp/ID", "Company", "Direction", "Weight (kg)", "Status"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFFFF")
        cell.fill = hdr_fill
        cell.border = border
        cell.alignment = Alignment(horizontal="center")
    for i, e in enumerate(sorted(s.manifest_entries or [], key=lambda x: (x.direction, x.passenger_name)), 1):
        r += 1
        wt = (e.body_weight or 0) + (e.baggage_weight or 0)
        row = [i, e.passenger_name, e.emp_code or e.id_number or "", e.company or "",
               e.direction, wt or "", e.status]
        for c, val in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.border = border

    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["D"].width = 20
    for col in ("A", "C", "E", "F", "G"):
        ws.column_dimensions[col].width = 14

    buf = io.BytesIO()
    wb.save(buf)
    fname = f"manifest_{ident}_{s.departure_time.strftime('%Y%m%d') if s.departure_time else flight_id}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/analytics")
async def transport_analytics(db: Session = Depends(get_db), _=Depends(get_current_user)) -> Dict[str, Any]:
    """Dashboard metrics: today's activity, on-time %, and a 7-day POB movement trend."""
    today = _site_today()
    day_start, day_end = _site_day_bounds(today)

    todays = db.query(TransportSchedule).filter(
        TransportSchedule.departure_time >= day_start,
        TransportSchedule.departure_time < day_end,
    ).all()
    today_ids = [f.id for f in todays]
    today_entries = (
        db.query(ManifestEntry).filter(ManifestEntry.schedule_id.in_(today_ids)).all()
        if today_ids else []
    )
    pax_moved = sum(1 for e in today_entries if e.status == "CONFIRMED")

    # On-time %: of flights that actually departed, how many within 15 min of schedule
    departed = db.query(TransportSchedule).filter(
        TransportSchedule.actual_departure_time.isnot(None)
    ).order_by(TransportSchedule.actual_departure_time.desc()).limit(100).all()
    on_time = 0
    for f in departed:
        if f.departure_time and f.actual_departure_time:
            delay = (f.actual_departure_time - f.departure_time).total_seconds() / 60
            if delay <= 15:
                on_time += 1
    on_time_pct = round(on_time / len(departed) * 100) if departed else None

    # 7-day POB movement trend (confirmed arrivals − departures per day)
    trend = []
    for d in range(6, -1, -1):
        day = today - timedelta(days=d)
        ds, de = _site_day_bounds(day)
        fids = [r[0] for r in db.query(TransportSchedule.id).filter(
            TransportSchedule.departure_time >= ds, TransportSchedule.departure_time < de).all()]
        arr = dep = 0
        if fids:
            for e in db.query(ManifestEntry).filter(ManifestEntry.schedule_id.in_(fids),
                                                    ManifestEntry.status == "CONFIRMED",
                                                    ManifestEntry.pob_applied_at.isnot(None)).all():
                if e.direction == "INBOUND":
                    arr += 1
                else:
                    dep += 1
        trend.append({"date": day.isoformat(), "arrivals": arr, "departures": dep, "net": arr - dep})

    return {
        "flights_today": len(todays),
        "pax_moved_today": pax_moved,
        "on_time_pct": on_time_pct,
        "pob_trend": trend,
    }


@router.delete("/flights/{flight_id}/manifest/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manifest_entry(
    flight_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    entry = (
        db.query(ManifestEntry)
        .filter(ManifestEntry.id == entry_id, ManifestEntry.schedule_id == flight_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Manifest entry not found")
    schedule = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if schedule:
        _sync_entry_pob(db, schedule, entry, removing=True)   # undo any POB change first
    db.delete(entry)
    db.commit()


# ─── POB impact summary ────────────────────────────────────────────────────────

@router.get("/pob-summary")
async def pob_summary(
    summary_date: Optional[date] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    """POB delta for a given day (defaults to today): confirmed arrivals minus confirmed departures."""
    if summary_date is None:
        summary_date = _site_today()

    day_start, day_end = _site_day_bounds(summary_date)

    flights_today = (
        db.query(TransportSchedule)
        .filter(
            TransportSchedule.departure_time >= day_start,
            TransportSchedule.departure_time < day_end,
        )
        .all()
    )

    flight_ids = [f.id for f in flights_today]
    if not flight_ids:
        return {
            "date": str(summary_date),
            "confirmed_arrivals": 0,
            "confirmed_departures": 0,
            "no_shows": 0,
            "pob_delta": 0,
            "flights_today": 0,
            "discrepancies": [],
        }

    entries = (
        db.query(ManifestEntry)
        .filter(ManifestEntry.schedule_id.in_(flight_ids))
        .all()
    )

    # Count only movements that actually happened (flight arrived / departed) — a
    # boarded passenger on a flight that has not moved has not changed POB yet.
    confirmed_inbound  = [e for e in entries if e.status == "CONFIRMED" and e.direction == "INBOUND" and e.pob_applied_at]
    confirmed_outbound = [e for e in entries if e.status == "CONFIRMED" and e.direction == "OUTBOUND" and e.pob_applied_at]
    no_shows = [e for e in entries if e.status == "NO_SHOW"]

    # Discrepancies: passengers still MANIFESTED on completed / in-transit flights
    completed_ids = {f.id for f in flights_today if f.status in ("COMPLETED", "IN_TRANSIT")}
    unreconciled = [
        {
            "flight_id": e.schedule_id,
            "passenger_name": e.passenger_name,
            "emp_code": e.emp_code,
            "direction": e.direction,
        }
        for e in entries
        if e.status == "MANIFESTED" and e.schedule_id in completed_ids
    ]

    return {
        "date": str(summary_date),
        "confirmed_arrivals": len(confirmed_inbound),
        "confirmed_departures": len(confirmed_outbound),
        "no_shows": len(no_shows),
        "pob_delta": len(confirmed_inbound) - len(confirmed_outbound),
        "flights_today": len(flights_today),
        "discrepancies": unreconciled,
    }


# ─── Personnel search helper ───────────────────────────────────────────────────

@router.get("/personnel-search")
async def search_personnel(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Quick search for adding registered personnel to a manifest."""
    term = f"%{q}%"
    results = (
        db.query(Personnel)
        .filter(
            (Personnel.first_name + " " + Personnel.last_name).ilike(term)
            | Personnel.emp_code.ilike(term)
        )
        # status is an UPPERCASE enum describing location (ACTIVE/ONSHORE/OFFSHORE);
        # is_active is the employed flag. The lowercase literal matched nobody.
        .filter(Personnel.is_active.is_(True))
        .limit(20)
        .all()
    )
    return [
        {
            "id": p.id,
            "emp_code": p.emp_code,
            "name": f"{p.first_name} {p.last_name}".strip(),
            "company": getattr(p, "company", None),
            "department": p.department if hasattr(p, "department") and isinstance(p.department, str) else None,
        }
        for p in results
    ]


# ─── Mustering reconciliation ──────────────────────────────────────────────────

@router.get("/flights/{flight_id}/reconcile")
async def reconcile_manifest_with_mustering(
    flight_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Cross-check the flight manifest against the current live mustering headcount.

    Returns three lists:
    - verified:        manifest passengers confirmed accounted for in mustering
    - missing_in_muster: on manifest but NOT yet checked in to any muster zone
    - extra_on_platform: in live muster but NOT on this manifest (unexpected personnel)

    A departure should only be authorised when missing_in_muster is empty.
    """
    schedule = db.query(TransportSchedule).filter(TransportSchedule.id == flight_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Flight schedule not found")

    # Passengers who should be ON the installation now: outbound passengers waiting
    # to fly out (inbound passengers are, by definition, not there yet).
    manifest_emp_codes: set = {
        e.emp_code for e in (schedule.manifest_entries or [])
        if e.emp_code and e.direction == "OUTBOUND"
        and e.status not in ("CANCELLED", "NO_SHOW", "OFFLOADED")
    }

    # Headcount = people ACCOUNTED FOR in an active muster (status 1 = safe). This
    # used to take every muster log row, including status 0 = MISSING, so a missing
    # person was reported as verified present.
    muster_emp_codes: set = {r[0] for r in db.execute(text("""
        SELECT DISTINCT ml.emp_code
        FROM mustering_log ml
        JOIN mustering_event me ON me.id = ml.event_id
        WHERE me.status = 0 AND ml.status = 1
    """)).fetchall()}
    active_muster = db.execute(text("SELECT 1 FROM mustering_event WHERE status = 0 LIMIT 1")).first()

    if not active_muster:
        # No muster: use live on-board status (was: any attendance punch in 24 h).
        muster_emp_codes = {r[0] for r in db.execute(text(
            "SELECT emp_code FROM personnel WHERE is_onboard = TRUE AND is_active = TRUE"
        )).fetchall()}
        headcount_source = "onboard"
    else:
        headcount_source = "active_muster"

    verified             = sorted(manifest_emp_codes & muster_emp_codes)
    missing_in_muster    = sorted(manifest_emp_codes - muster_emp_codes)
    # "Extra" only means something against a muster headcount; against the whole
    # on-board list it would just be everyone not on this flight.
    extra_on_platform    = sorted(muster_emp_codes - manifest_emp_codes) if active_muster else []

    # Enrich missing list with names for the safety officer
    def _name(emp_code: str) -> str:
        row = db.execute(text(
            "SELECT first_name || ' ' || COALESCE(last_name,'') FROM personnel WHERE emp_code=:c LIMIT 1"
        ), {"c": emp_code}).fetchone()
        return row[0].strip() if row else emp_code

    return {
        "flight_id":        flight_id,
        "headcount_source": headcount_source,
        "reconciled":       len(missing_in_muster) == 0,
        "summary": {
            "manifest_total":   len(manifest_emp_codes),
            "verified":         len(verified),
            "missing_in_muster": len(missing_in_muster),
            "extra_on_platform": len(extra_on_platform),
        },
        "missing_in_muster": [
            {"emp_code": c, "name": _name(c)} for c in missing_in_muster
        ],
        "extra_on_platform": [
            {"emp_code": c, "name": _name(c)} for c in extra_on_platform
        ],
        "verified_emp_codes": verified,
        "generated_at": datetime.now().isoformat(),
    }
