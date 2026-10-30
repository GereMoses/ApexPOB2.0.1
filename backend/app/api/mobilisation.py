"""
Site mobilisation — "is this person ready to go to site?"

Replaces the generic HR onboarding (job title, buddy, exit interview…), which duplicated
SeamlessHR: SeamlessHR owns who the person is; ApexPOB owns whether they are fit, carded,
briefed and booked to go to site.

Most items are read live from what ApexPOB already holds, so they can never be ticked
while untrue: medical in date on the mobilisation day, certificates (the same check that
stops boarding), access card on file and loaded on every door controller, emergency
contact and a phone for muster alerts, biometrics, travel booked. A few are confirmed by
HSE (induction given, PPE issued, accommodation). Mobilising does NOT put the person on
board — POB comes from the access readers and journeys.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.personnel import Personnel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mobilisation", tags=["Site Mobilisation"])

MANUAL = {
    "induction":     ("Site safety induction given", True),
    "ppe":           ("PPE issued", True),
    "accommodation": ("Accommodation / bed allocated", False),
}


class MobiliseCreate(BaseModel):
    personnel_ids: List[int] = Field(..., min_length=1)
    mobilise_date: date
    notes: Optional[str] = None


class CheckBody(BaseModel):
    item: str
    done: bool
    note: Optional[str] = None


class MobiliseBody(BaseModel):
    override_reason: Optional[str] = None


class UpdateBody(BaseModel):
    mobilise_date: Optional[date] = None
    notes: Optional[str] = None


def _who(u) -> str:
    return getattr(u, "full_name", None) or getattr(u, "username", None) or f"user {getattr(u, 'id', '')}"


def _item(code, label, required, state, detail, **extra) -> Dict:
    return {"code": code, "label": label, "required": required, "state": state, "detail": detail,
            "kind": "manual" if code in MANUAL else "auto", **extra}


def _has_certificates(p: Personnel) -> bool:
    """Any certificate on file at all (travel_compliance says "ok" on a medical alone)."""
    from .transport_manifest import _scan_training_module
    def _items(v):
        return v if isinstance(v, list) else (v.get("items", []) if isinstance(v, dict) else [])
    return bool(_items(p.training_records) or _items(p.certifications) or _scan_training_module(p, []))


def checklist(db: Session, mob, p: Personnel) -> List[Dict]:
    """Every item, worked out now. state: pass | warn | fail | na."""
    from .transport_manifest import travel_compliance, _parse_date
    day = mob.mobilise_date
    out: List[Dict] = []

    med = _parse_date(p.medical_fitness_date)
    if med is None:
        out.append(_item("medical", "Medical fitness", True, "fail", "No medical fitness date on file (Personnel → edit)"))
    elif med < day:
        out.append(_item("medical", "Medical fitness", True, "fail", f"Expires {med:%d %b %Y} — before the mobilisation date"))
    elif med <= day + timedelta(days=30):
        out.append(_item("medical", "Medical fitness", True, "warn", f"Valid, but expires {med:%d %b %Y}"))
    else:
        out.append(_item("medical", "Medical fitness", True, "pass", f"Valid until {med:%d %b %Y}"))

    tc = travel_compliance(p)
    certs = [i for i in tc.get("issues", []) if not i.lower().startswith("medical")]
    if tc["status"] == "blocked" and any("expired" in i for i in certs):
        out.append(_item("certificates", "Safety certificates", True, "fail", "; ".join(certs)))
    elif certs and tc["status"] in ("warning", "blocked"):
        out.append(_item("certificates", "Safety certificates", True, "warn", "; ".join(certs)))
    elif tc["status"] == "unknown" or not _has_certificates(p):
        out.append(_item("certificates", "Safety certificates", True, "warn", "No certificates recorded in Personnel → Training"))
    else:
        out.append(_item("certificates", "Safety certificates", True, "pass", "All recorded certificates in date"))

    card = str(p.card_number) if p.card_number else None
    out.append(_item("card", "Access card", True, "pass" if card else "fail",
                     f"Card {card}" if card else "No access card number on file"))

    panels = db.execute(text("SELECT count(*) FROM access_controllers")).scalar() or 0
    if not panels:
        out.append(_item("card_loaded", "Card loaded on door controllers", False, "na", "No door controllers set up"))
    else:
        loaded = db.execute(text("""SELECT count(DISTINCT controller_id) FROM controller_user
                                    WHERE emp_code = :c AND state = 'loaded'"""), {"c": p.emp_code}).scalar() or 0
        state = "pass" if loaded >= panels else "fail"
        detail = (f"On all {panels} controller(s)" if state == "pass" else
                  f"On {loaded} of {panels} controller(s)" + ("" if card else " — needs a card first"))
        out.append(_item("card_loaded", "Card loaded on door controllers", True, state, detail))

    fingers = db.execute(text("SELECT count(*) FROM iclock_bio_template WHERE emp_code = :c AND COALESCE(valid, TRUE)"),
                         {"c": p.emp_code}).scalar() or 0
    bio = fingers or p.biometric_enrolled or p.face_template
    out.append(_item("biometric", "Fingerprint / face enrolled", False, "pass" if bio else "warn",
                     f"{fingers} fingerprint(s)" if fingers else ("Enrolled" if bio else "Not enrolled — card only")))

    ec = p.emergency_contact if isinstance(p.emergency_contact, dict) else {}
    nok = (p.emergency_contact_name or ec.get("name") or "").strip()
    nok_phone = (p.emergency_contact_phone or ec.get("phone") or "").strip()
    out.append(_item("emergency_contact", "Emergency contact (next of kin)", True,
                     "pass" if nok_phone else "fail",
                     f"{nok or 'Contact'} · {nok_phone}" if nok_phone else "No emergency contact phone on file"))

    out.append(_item("phone", "Phone for muster / emergency alerts", True, "pass" if p.phone else "fail",
                     p.phone or "No phone number on file"))

    lo, hi = day - timedelta(days=3), day + timedelta(days=1)
    flight = db.execute(text("""
        SELECT s.departure_time, s.departure_location, s.arrival_location FROM manifest_entry e
        JOIN transport_schedule s ON s.id = e.schedule_id
        WHERE e.personnel_id = :p AND UPPER(COALESCE(e.status, '')) NOT IN ('CANCELLED', 'OFFLOADED', 'NO_SHOW')
          AND UPPER(COALESCE(s.status, '')) NOT IN ('CANCELLED')
          AND s.departure_time::date BETWEEN :lo AND :hi
        ORDER BY s.departure_time LIMIT 1"""), {"p": p.id, "lo": lo, "hi": hi}).first()
    road = None if flight else db.execute(text("""
        SELECT planned_departure, origin, destination, reference FROM journey_plan
        WHERE passengers @> CAST(:j AS jsonb) AND UPPER(COALESCE(status, '')) NOT IN ('CANCELLED', 'REJECTED')
          AND planned_departure::date BETWEEN :lo AND :hi
        ORDER BY planned_departure LIMIT 1"""), {"j": f'[{{"emp_code": "{p.emp_code}"}}]', "lo": lo, "hi": hi}).first()
    if flight:
        out.append(_item("travel", "Travel booked", False, "pass",
                         f"Flight {flight.departure_time:%d %b %H:%M} {flight.departure_location} → {flight.arrival_location}"))
    elif road:
        out.append(_item("travel", "Travel booked", False, "pass",
                         f"Road journey {road.reference or ''} {road.planned_departure:%d %b %H:%M} {road.origin} → {road.destination}"))
    else:
        out.append(_item("travel", "Travel booked", False, "warn", "Not on a flight manifest or land journey around this date"))

    ticks = mob.checks or {}
    induction_course = db.execute(text("""
        SELECT c.course_name, MAX(COALESCE(e.expiry_date, DATE '9999-12-31')) AS valid_to
        FROM training_courses c JOIN training_enrollment e ON e.course_id = c.id AND e.personnel_id = :p
        WHERE (c.course_name ILIKE '%induction%' OR c.course_code ILIKE '%induc%')
          AND (LOWER(e.status) IN ('completed', 'passed', 'certified') OR e.completion_date IS NOT NULL)
        GROUP BY c.course_name ORDER BY 2 DESC LIMIT 1"""), {"p": p.id}).first()
    for code, (label, required) in MANUAL.items():
        t = ticks.get(code) or {}
        if code == "induction" and induction_course and induction_course.valid_to >= day:
            out.append(_item(code, label, required, "pass", f"{induction_course.course_name} recorded in Training"))
        elif t.get("done"):
            out.append(_item(code, label, required, "pass",
                             f"Confirmed by {t.get('by')} {t.get('at', '')[:10]}" + (f" — {t['note']}" if t.get("note") else ""),
                             by=t.get("by"), at=t.get("at")))
        else:
            out.append(_item(code, label, required, "fail" if required else "warn", "Not confirmed yet"))
    return out


def _summary(items: List[Dict]) -> Dict:
    blocking = [i for i in items if i["required"] and i["state"] == "fail"]
    return {"ready": not blocking, "blocking": [i["label"] for i in blocking],
            "done": sum(1 for i in items if i["state"] in ("pass", "na")), "total": len(items),
            "warnings": [i["label"] for i in items if i["state"] == "warn"]}


def _load(db: Session, mob_id: int):
    m = db.execute(text("SELECT * FROM site_mobilisation WHERE id = :i"), {"i": mob_id}).first()
    if not m:
        raise HTTPException(404, "Mobilisation not found")
    return m


def _view(db: Session, m, with_items: bool = True) -> Dict:
    p = db.get(Personnel, m.personnel_id)
    row = {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in m._mapping.items()}
    if p is None:
        return {**row, "person": None, "ready": False, "blocking": ["Person no longer exists"], "items": []}
    dept = db.execute(text("SELECT name FROM departments WHERE id = :i"), {"i": p.department_id}).scalar() if p.department_id else None
    row["person"] = {"id": p.id, "emp_code": p.emp_code, "name": p.full_name or f"{p.first_name} {p.last_name}",
                     "department": dept, "position": p.position, "company": p.company,
                     "hr_source": p.hr_source, "is_onboard": bool(p.is_onboard)}
    items = checklist(db, m, p) if m.status == "PREPARING" or with_items else []
    if items:
        row.update(_summary(items))
    if with_items:
        row["items"] = items
    return row


@router.get("")
def list_mobilisations(status: Optional[str] = Query(None), search: Optional[str] = Query(None),
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = """SELECT m.* FROM site_mobilisation m JOIN personnel p ON p.id = m.personnel_id WHERE TRUE"""
    params: Dict = {}
    if status:
        q += " AND m.status = :s"
        params["s"] = status.upper()
    if search:
        q += " AND (p.full_name ILIKE :q OR p.emp_code ILIKE :q)"
        params["q"] = f"%{search}%"
    q += " ORDER BY (m.status = 'PREPARING') DESC, m.mobilise_date, m.id"
    rows = [_view(db, m, with_items=False) for m in db.execute(text(q), params).fetchall()]
    prep = [r for r in rows if r["status"] == "PREPARING"]
    soon = date.today() + timedelta(days=7)
    return {"data": rows, "stats": {
        "preparing": len(prep), "ready": sum(1 for r in prep if r.get("ready")),
        "not_ready": sum(1 for r in prep if not r.get("ready")),
        "due_7_days_not_ready": sum(1 for r in prep if not r.get("ready") and date.fromisoformat(r["mobilise_date"]) <= soon),
        "mobilised": sum(1 for r in rows if r["status"] == "MOBILISED")}}


@router.post("")
def create_mobilisations(body: MobiliseCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    created, skipped = [], []
    for pid in dict.fromkeys(body.personnel_ids):
        p = db.get(Personnel, pid)
        if not p or not p.is_active:
            skipped.append({"personnel_id": pid, "reason": "not an active person"})
            continue
        open_ = db.execute(text("SELECT id FROM site_mobilisation WHERE personnel_id = :p AND status = 'PREPARING'"),
                           {"p": pid}).scalar()
        if open_:
            skipped.append({"personnel_id": pid, "name": p.full_name, "reason": "already being prepared"})
            continue
        mid = db.execute(text("""INSERT INTO site_mobilisation (personnel_id, mobilise_date, notes, created_by)
                                 VALUES (:p, :d, :n, :u) RETURNING id"""),
                         {"p": pid, "d": body.mobilise_date, "n": body.notes, "u": _who(user)}).scalar()
        created.append(mid)
    db.commit()
    return {"created": created, "skipped": skipped}


@router.get("/{mob_id}")
def get_mobilisation(mob_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _view(db, _load(db, mob_id))


@router.put("/{mob_id}")
def update_mobilisation(mob_id: int, body: UpdateBody, db: Session = Depends(get_db), user=Depends(get_current_user)):
    m = _load(db, mob_id)
    if m.status != "PREPARING":
        raise HTTPException(400, f"Already {m.status.lower()}")
    db.execute(text("""UPDATE site_mobilisation SET mobilise_date = COALESCE(:d, mobilise_date),
                       notes = COALESCE(:n, notes), updated_at = NOW() WHERE id = :i"""),
               {"d": body.mobilise_date, "n": body.notes, "i": mob_id})
    db.commit()
    return _view(db, _load(db, mob_id))


@router.post("/{mob_id}/check")
def tick(mob_id: int, body: CheckBody, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if body.item not in MANUAL:
        raise HTTPException(400, "Only induction, PPE and accommodation are confirmed by hand — the rest is read from the records")
    m = _load(db, mob_id)
    if m.status != "PREPARING":
        raise HTTPException(400, f"Already {m.status.lower()}")
    checks = dict(m.checks or {})
    checks[body.item] = ({"done": True, "by": _who(user), "at": datetime.now(timezone.utc).isoformat(), "note": body.note}
                         if body.done else {"done": False})
    db.execute(text("UPDATE site_mobilisation SET checks = CAST(:c AS jsonb), updated_at = NOW() WHERE id = :i"),
               {"c": __import__("json").dumps(checks), "i": mob_id})
    db.commit()
    return _view(db, _load(db, mob_id))


@router.post("/{mob_id}/mobilise")
def mobilise(mob_id: int, body: MobiliseBody, db: Session = Depends(get_db), user=Depends(get_current_user)):
    m = _load(db, mob_id)
    if m.status != "PREPARING":
        raise HTTPException(400, f"Already {m.status.lower()}")
    v = _view(db, m)
    reason = (body.override_reason or "").strip()
    if not v.get("ready") and len(reason) < 5:
        raise HTTPException(409, "Not ready to mobilise — outstanding: " + ", ".join(v.get("blocking", []))
                            + ". Give a reason to mobilise anyway.")
    db.execute(text("""UPDATE site_mobilisation SET status = 'MOBILISED', mobilised_at = NOW(), mobilised_by = :u,
                       override_reason = :r, outstanding = CAST(:o AS jsonb), updated_at = NOW() WHERE id = :i"""),
               {"u": _who(user), "r": reason or None, "o": __import__("json").dumps(v.get("blocking", [])), "i": mob_id})
    db.commit()
    return _view(db, _load(db, mob_id), with_items=False)


@router.post("/{mob_id}/cancel")
def cancel(mob_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    m = _load(db, mob_id)
    if m.status != "PREPARING":
        raise HTTPException(400, f"Already {m.status.lower()}")
    db.execute(text("UPDATE site_mobilisation SET status = 'CANCELLED', updated_at = NOW() WHERE id = :i"), {"i": mob_id})
    db.commit()
    return {"ok": True}


@router.delete("/{mob_id}")
def delete(mob_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    m = _load(db, mob_id)
    if m.status == "MOBILISED":
        raise HTTPException(400, "A mobilisation that happened stays on record — it can't be deleted")
    db.execute(text("DELETE FROM site_mobilisation WHERE id = :i"), {"i": mob_id})
    db.commit()
    return {"ok": True}
