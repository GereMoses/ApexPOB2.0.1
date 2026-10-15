"""
Land Journey Management (JMP) API.

Road-transport journey plans with automatic risk assessment, an approval
workflow, and check-in-call tracking. A journey that misses its next check-in
(or overshoots its ETA) is reported OVERDUE so the control room can escalate.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.journey import JourneyPlan, JourneyCheckIn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journeys", tags=["Journey Management"])

# Grace period after a check-in is due before the journey is flagged overdue.
OVERDUE_GRACE_MIN = 10


# ─── Schemas ────────────────────────────────────────────────────────────────────

class JourneyCreate(BaseModel):
    origin: str
    destination: str
    route_description: Optional[str] = None
    distance_km: Optional[float] = None
    purpose: Optional[str] = None
    driver_name: Optional[str] = None
    driver_license: Optional[str] = None
    driver_personnel_id: Optional[int] = None
    vehicle_reg: Optional[str] = None
    vehicle_type: Optional[str] = None
    passengers: Optional[List[Dict[str, Any]]] = None
    planned_departure: datetime
    planned_arrival: Optional[datetime] = None
    checkin_interval_min: int = 60
    risk_factors: Optional[List[str]] = None
    risk_notes: Optional[str] = None
    vehicle_check: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class JourneyUpdate(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    route_description: Optional[str] = None
    distance_km: Optional[float] = None
    purpose: Optional[str] = None
    driver_name: Optional[str] = None
    driver_license: Optional[str] = None
    vehicle_reg: Optional[str] = None
    vehicle_type: Optional[str] = None
    passengers: Optional[List[Dict[str, Any]]] = None
    planned_departure: Optional[datetime] = None
    planned_arrival: Optional[datetime] = None
    checkin_interval_min: Optional[int] = None
    risk_factors: Optional[List[str]] = None
    risk_notes: Optional[str] = None
    vehicle_check: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class RejectBody(BaseModel):
    reason: Optional[str] = None


class CheckInBody(BaseModel):
    location: Optional[str] = None
    status: str = "OK"          # OK / CONCERN
    reported_by: Optional[str] = None
    notes: Optional[str] = None


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _site_tz():
    from ..services.attendance_calculation_service import SITE_TZ
    return SITE_TZ


def _perm(request: Optional[Request], code: str) -> bool:
    perms = getattr(getattr(request, "state", None), "user_permissions", None) or []
    return "*" in perms or code in perms


def _crosses_night(dep: Optional[datetime], arr: Optional[datetime]) -> bool:
    """True if any part of the trip falls in night hours (19:00–06:00 SITE time —
    this used UTC hours, so a 18:00–19:00 Lagos departure was not flagged)."""
    if not dep:
        return False
    dep = dep.astimezone(_site_tz())
    end = (arr.astimezone(_site_tz()) if arr else dep + timedelta(hours=2))
    night = lambda t: t.hour >= 19 or t.hour < 6
    # Sample along the trip AND the arrival itself (hourly steps from 18:30 never
    # looked at a 19:20 arrival, so the trip was not flagged).
    cur = dep
    while cur <= end:
        if night(cur):
            return True
        cur += timedelta(minutes=30)
    return night(end)


def compute_risk(distance_km, dep, arr, factors) -> tuple:
    """Suggest a risk level from distance, night driving and manual factors."""
    score, reasons = 0, []
    if distance_km and distance_km > 300:
        score += 2; reasons.append("Long distance (>300 km)")
    elif distance_km and distance_km > 150:
        score += 1; reasons.append("Distance >150 km")
    if _crosses_night(_aware(dep), _aware(arr)):
        score += 2; reasons.append("Night driving")
    for f in (factors or []):
        score += 1; reasons.append(f)
    level = "HIGH" if score >= 3 else ("MEDIUM" if score >= 1 else "LOW")
    return level, reasons


def _overdue_info(j: JourneyPlan) -> Dict[str, Any]:
    """Transient overdue calc — a journey IN_PROGRESS past its next check-in (or ETA)."""
    if j.status != "IN_PROGRESS":
        return {"overdue": False, "minutes_overdue": 0}
    now = _now()
    due = _aware(j.next_checkin_due)
    eta = _aware(j.planned_arrival)
    worst = None
    if due and now > due + timedelta(minutes=OVERDUE_GRACE_MIN):
        worst = due
    if eta and now > eta + timedelta(minutes=OVERDUE_GRACE_MIN):
        worst = min(worst, eta) if worst else eta
    if worst:
        return {"overdue": True, "minutes_overdue": int((now - worst).total_seconds() // 60)}
    return {"overdue": False, "minutes_overdue": 0}


def _to_dict(j: JourneyPlan, with_checkins: bool = False) -> Dict[str, Any]:
    od = _overdue_info(j)
    d = {
        "id": j.id,
        "reference": j.reference,
        "origin": j.origin,
        "destination": j.destination,
        "route_description": j.route_description,
        "distance_km": j.distance_km,
        "purpose": j.purpose,
        "driver_name": j.driver_name,
        "driver_license": j.driver_license,
        "driver_personnel_id": j.driver_personnel_id,
        "vehicle_reg": j.vehicle_reg,
        "vehicle_type": j.vehicle_type,
        "passengers": j.passengers or [],
        "passenger_count": j.passenger_count or (len(j.passengers) if j.passengers else 0),
        "planned_departure": j.planned_departure.isoformat() if j.planned_departure else None,
        "planned_arrival": j.planned_arrival.isoformat() if j.planned_arrival else None,
        "actual_departure": j.actual_departure.isoformat() if j.actual_departure else None,
        "actual_arrival": j.actual_arrival.isoformat() if j.actual_arrival else None,
        "checkin_interval_min": j.checkin_interval_min,
        "last_checkin_at": j.last_checkin_at.isoformat() if j.last_checkin_at else None,
        "next_checkin_due": j.next_checkin_due.isoformat() if j.next_checkin_due else None,
        "risk_level": j.risk_level,
        "risk_factors": j.risk_factors or [],
        "risk_notes": j.risk_notes,
        "vehicle_check": j.vehicle_check or {},
        "vehicle_check_ok": j.vehicle_check_ok,
        "status": j.status,
        "approved_by_id": j.approved_by_id,
        "approved_at": j.approved_at.isoformat() if j.approved_at else None,
        "second_approved_by_id": j.second_approved_by_id,
        "second_approved_at": j.second_approved_at.isoformat() if j.second_approved_at else None,
        "approvals_required": 2 if j.risk_level == "HIGH" else 1,
        "approvals_given": (1 if j.approved_by_id else 0) + (1 if j.second_approved_by_id else 0),
        "risk_manual_factors": j.risk_manual_factors or [],
        "created_by_id": j.created_by_id,
        "rejection_reason": j.rejection_reason,
        "notes": j.notes,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "overdue": od["overdue"],
        "minutes_overdue": od["minutes_overdue"],
    }
    if with_checkins:
        d["checkins"] = [
            {
                "id": c.id,
                "checkin_time": c.checkin_time.isoformat() if c.checkin_time else None,
                "location": c.location,
                "status": c.status,
                "reported_by": c.reported_by,
                "notes": c.notes,
            }
            for c in sorted(j.checkins, key=lambda x: x.checkin_time or _now(), reverse=True)
        ]
    return d


def _get(db: Session, journey_id: int) -> JourneyPlan:
    j = db.query(JourneyPlan).filter(JourneyPlan.id == journey_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Journey not found")
    return j


# ─── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_journeys(
    status: Optional[str] = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(JourneyPlan)
    if status:
        q = q.filter(JourneyPlan.status == status.upper())
    if active_only:
        q = q.filter(JourneyPlan.status.in_(["APPROVED", "IN_PROGRESS", "SUBMITTED"]))
    journeys = q.order_by(JourneyPlan.planned_departure.desc()).limit(300).all()
    return {"journeys": [_to_dict(j) for j in journeys], "count": len(journeys)}


@router.get("/stats")
async def journey_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    journeys = db.query(JourneyPlan).filter(
        JourneyPlan.status.in_(["SUBMITTED", "APPROVED", "IN_PROGRESS"])
    ).all()
    in_progress = [j for j in journeys if j.status == "IN_PROGRESS"]
    overdue = [j for j in in_progress if _overdue_info(j)["overdue"]]
    return {
        "pending_approval": sum(1 for j in journeys if j.status == "SUBMITTED"),
        "approved": sum(1 for j in journeys if j.status == "APPROVED"),
        "in_progress": len(in_progress),
        "overdue": len(overdue),
        "overdue_journeys": [_to_dict(j) for j in overdue],
    }


@router.post("", status_code=201)
async def create_journey(payload: JourneyCreate, db: Session = Depends(get_db),
                         current_user=Depends(get_current_user)):
    level, reasons = compute_risk(payload.distance_km, payload.planned_departure,
                                  payload.planned_arrival, payload.risk_factors)
    j = JourneyPlan(
        origin=payload.origin, destination=payload.destination,
        route_description=payload.route_description, distance_km=payload.distance_km,
        purpose=payload.purpose, driver_name=payload.driver_name,
        driver_license=payload.driver_license, driver_personnel_id=payload.driver_personnel_id,
        vehicle_reg=payload.vehicle_reg, vehicle_type=payload.vehicle_type,
        passengers=payload.passengers, passenger_count=len(payload.passengers or []),
        planned_departure=payload.planned_departure, planned_arrival=payload.planned_arrival,
        checkin_interval_min=payload.checkin_interval_min or 60,
        risk_level=level, risk_factors=reasons, risk_notes=payload.risk_notes,
        risk_manual_factors=payload.risk_factors or [],
        vehicle_check=payload.vehicle_check,
        vehicle_check_ok=bool(payload.vehicle_check) and all(payload.vehicle_check.values()),
        status="DRAFT", notes=payload.notes,
        created_by_id=getattr(current_user, "id", None),
    )
    db.add(j)
    db.flush()
    j.reference = f"JMP-{j.id:04d}"
    db.commit()
    return _to_dict(j, with_checkins=True)


@router.get("/{journey_id}")
async def get_journey(journey_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    j = db.query(JourneyPlan).options(joinedload(JourneyPlan.checkins)).filter(
        JourneyPlan.id == journey_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Journey not found")
    return _to_dict(j, with_checkins=True)


@router.put("/{journey_id}")
async def update_journey(journey_id: int, payload: JourneyUpdate, db: Session = Depends(get_db),
                         _=Depends(get_current_user)):
    j = _get(db, journey_id)
    if j.status not in ("DRAFT", "REJECTED", "SUBMITTED"):
        raise HTTPException(status_code=400, detail=f"Cannot edit a {j.status} journey")
    data = payload.dict(exclude_unset=True)
    manual = data.pop("risk_factors", None)
    if manual is not None:
        j.risk_manual_factors = manual
    for k, v in data.items():
        setattr(j, k, v)
    if payload.passengers is not None:
        j.passenger_count = len(payload.passengers)
    if payload.vehicle_check is not None:
        j.vehicle_check_ok = bool(payload.vehicle_check) and all(payload.vehicle_check.values())
    # Recompute from the planner's OWN factors (kept separately). Previously an edit
    # without factors dropped them, and an edit sending back the stored list counted
    # automatic reasons (e.g. "Night driving") a second time.
    level, reasons = compute_risk(j.distance_km, j.planned_departure, j.planned_arrival,
                                  j.risk_manual_factors or [])
    j.risk_level, j.risk_factors = level, reasons
    if j.status == "SUBMITTED":
        # A changed plan must be approved as changed.
        j.approved_by_id = j.approved_at = None
        j.second_approved_by_id = j.second_approved_at = None
    db.commit()
    return _to_dict(j, with_checkins=True)


@router.delete("/{journey_id}", status_code=204)
async def delete_journey(journey_id: int, request: Request, db: Session = Depends(get_db),
                         current_user=Depends(get_current_user)):
    j = _get(db, journey_id)
    # An approved / running / finished journey is a safety record — cancel it instead.
    if j.status not in ("DRAFT", "REJECTED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"A {j.status} journey cannot be deleted — cancel it instead")
    if j.created_by_id and j.created_by_id != getattr(current_user, "id", None) and not _perm(request, "journey.approve"):
        raise HTTPException(status_code=403, detail="Only the planner or an approver can delete this journey")
    db.delete(j)
    db.commit()


# ─── Workflow ─────────────────────────────────────────────────────────────────

@router.post("/{journey_id}/submit")
async def submit_journey(journey_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    j = _get(db, journey_id)
    if j.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(status_code=400, detail=f"Cannot submit a {j.status} journey")
    j.status = "SUBMITTED"
    j.rejection_reason = None
    db.commit()
    return _to_dict(j)


@router.post("/{journey_id}/approve")
async def approve_journey(journey_id: int, request: Request, db: Session = Depends(get_db),
                          current_user=Depends(get_current_user)):
    if not _perm(request, "journey.approve"):
        raise HTTPException(status_code=403, detail="Approving journeys needs the journey.approve permission")
    j = _get(db, journey_id)
    if j.status != "SUBMITTED":
        raise HTTPException(status_code=400, detail="Only a submitted journey can be approved")
    uid = getattr(current_user, "id", None)
    if j.created_by_id and uid == j.created_by_id:
        raise HTTPException(status_code=403, detail="You cannot approve a journey you planned")
    if j.approved_by_id is None:
        j.approved_by_id, j.approved_at = uid, _now()
    elif j.risk_level == "HIGH" and j.second_approved_by_id is None:
        if uid == j.approved_by_id:
            raise HTTPException(status_code=403, detail="A HIGH-risk journey needs a second, different approver")
        j.second_approved_by_id, j.second_approved_at = uid, _now()
    # HIGH risk needs two different approvers; anything else needs one.
    if j.risk_level != "HIGH" or j.second_approved_by_id:
        j.status = "APPROVED"
    db.commit()
    return _to_dict(j)


@router.post("/{journey_id}/reject")
async def reject_journey(journey_id: int, payload: RejectBody, request: Request,
                         db: Session = Depends(get_db), _=Depends(get_current_user)):
    if not _perm(request, "journey.approve"):
        raise HTTPException(status_code=403, detail="Rejecting journeys needs the journey.approve permission")
    j = _get(db, journey_id)
    if j.status != "SUBMITTED":
        raise HTTPException(status_code=400, detail="Only a submitted journey can be rejected")
    j.status = "REJECTED"
    j.rejection_reason = payload.reason
    j.approved_by_id = j.approved_at = None
    j.second_approved_by_id = j.second_approved_at = None
    db.commit()
    return _to_dict(j)


class VehicleCheckBody(BaseModel):
    vehicle_check: Dict[str, Any]


@router.post("/{journey_id}/vehicle-check")
async def record_vehicle_check(journey_id: int, payload: VehicleCheckBody, db: Session = Depends(get_db),
                               _=Depends(get_current_user)):
    """Record the pre-trip inspection. It is done just before departure — usually
    after approval, when the plan itself can no longer be edited."""
    j = _get(db, journey_id)
    if j.status in ("IN_PROGRESS", "COMPLETED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Cannot change the vehicle check of a {j.status} journey")
    j.vehicle_check = payload.vehicle_check
    j.vehicle_check_ok = bool(payload.vehicle_check) and all(payload.vehicle_check.values())
    db.commit()
    return _to_dict(j)


@router.post("/{journey_id}/start")
async def start_journey(journey_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    j = _get(db, journey_id)
    if j.status != "APPROVED":
        raise HTTPException(status_code=400, detail="Journey must be APPROVED before it can start")
    if not j.vehicle_check_ok:
        raise HTTPException(status_code=400,
                            detail="The pre-trip vehicle check is not complete / not passed — record it before starting")
    now = _now()
    j.status = "IN_PROGRESS"
    j.actual_departure = now
    j.last_checkin_at = now
    j.next_checkin_due = now + timedelta(minutes=j.checkin_interval_min or 60)
    db.commit()
    return _to_dict(j)


@router.post("/{journey_id}/checkin")
async def journey_checkin(journey_id: int, payload: CheckInBody, db: Session = Depends(get_db),
                          current_user=Depends(get_current_user)):
    j = _get(db, journey_id)
    if j.status != "IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Only an in-progress journey can check in")
    now = _now()
    db.add(JourneyCheckIn(
        journey_id=j.id, checkin_time=now, location=payload.location,
        status=(payload.status or "OK").upper(),
        reported_by=payload.reported_by or getattr(current_user, "username", None),
        notes=payload.notes,
    ))
    j.last_checkin_at = now
    j.next_checkin_due = now + timedelta(minutes=j.checkin_interval_min or 60)
    db.commit()
    if (payload.status or "OK").upper() == "CONCERN":
        # A driver reporting a problem is exactly what the control room must see now.
        ref = j.reference or f"JMP-{j.id}"
        msg = (f"⚠️ {ref} {j.origin} → {j.destination}: driver {j.driver_name or ''} reported a CONCERN"
               f"{' at ' + payload.location if payload.location else ''}. {payload.notes or ''}").strip()
        dk = f"journey_concern_{j.id}_{now:%Y%m%d%H%M%S}"
        db.execute(text("""
            INSERT INTO sys_notifications (dedup_key, notification_type, title, message, priority, expires_at)
            VALUES (:dk, 'journey_concern', :t, :m, 'critical', NOW() + INTERVAL '48 hours')
            ON CONFLICT (dedup_key) DO NOTHING
        """), {"dk": dk, "t": f"Journey concern {ref}", "m": msg})
        db.commit()
        try:
            from .notifications import notify_sync
            notify_sync({"type": "journey_concern", "priority": "critical",
                         "title": f"Journey concern {ref}", "message": msg,
                         "dedup_key": dk, "journey_id": j.id})
        except Exception as e:
            logger.warning("journey concern broadcast failed: %s", e)
    return _to_dict(j, with_checkins=True)


@router.post("/{journey_id}/complete")
async def complete_journey(journey_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    j = _get(db, journey_id)
    if j.status != "IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Only an in-progress journey can be completed")
    j.status = "COMPLETED"
    j.actual_arrival = _now()
    j.next_checkin_due = None
    db.commit()
    return _to_dict(j)


@router.post("/{journey_id}/cancel")
async def cancel_journey(journey_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    j = _get(db, journey_id)
    if j.status in ("COMPLETED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Journey already {j.status}")
    j.status = "CANCELLED"
    j.next_checkin_due = None
    db.commit()
    return _to_dict(j)


@router.get("/{journey_id}/checkins")
async def list_checkins(journey_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    _get(db, journey_id)
    rows = db.query(JourneyCheckIn).filter(
        JourneyCheckIn.journey_id == journey_id
    ).order_by(JourneyCheckIn.checkin_time.desc()).all()
    return {"checkins": [
        {
            "id": c.id, "checkin_time": c.checkin_time.isoformat() if c.checkin_time else None,
            "location": c.location, "status": c.status, "reported_by": c.reported_by, "notes": c.notes,
        } for c in rows
    ]}
