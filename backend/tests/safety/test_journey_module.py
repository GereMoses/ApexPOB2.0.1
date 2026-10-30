"""
Journey Management gaps (Oct 2026 review):
  * a land journey that misses its check-in alerts the response team (once, again
    after 30 min, cleared by a check-in) — it used to show only to whoever opened the page
  * a driver's CONCERN reaches the response team, not only the bell
  * arrival before departure is refused (flights and land journeys)
  * cancelling a flight tells its passengers; notify reports per channel + who can't be reached
  * a journey created by mistake can be deleted — never one somebody boarded
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from .conftest import needs_db

ADMIN = NS(state=NS(user_permissions=["*"]))
run = asyncio.run


@pytest.fixture
def alerts(monkeypatch):
    """Capture response-team alerts instead of queueing them to the live worker."""
    sent = []
    import app.services.notify_dispatch as nd
    monkeypatch.setattr(nd, "dispatch_background",
                        lambda st, sid, people, subj, msg, ch=None, include_responders=True:
                        sent.append(dict(source=st, id=sid, subject=subj, message=msg, team=include_responders)) or {})
    monkeypatch.setattr(nd, "dispatch",
                        lambda st, sid, people, subj, msg, ch=None, include_responders=True:
                        sent.append(dict(source=st, id=sid, subject=subj, message=msg, people=len(people), channels=ch))
                        or {c: {"sent": len(people), "failed": 0} for c in (ch or [])})
    import app.api.notifications as n
    monkeypatch.setattr(n, "notify_sync", lambda payload: None)
    return sent


def _running_journey(db, make_person, **kw):
    from app.api import journey_management as J
    drv = make_person("Dayo Driver")
    db.execute(text("UPDATE personnel SET phone = '08030001111' WHERE id = :i"), {"i": drv["id"]})
    db.commit()
    j = run(J.create_journey(J.JourneyCreate(
        origin="PH", destination="Warri", planned_departure=datetime.now(timezone.utc) + timedelta(minutes=5),
        driver_personnel_id=drv["id"], driver_name="Dayo Driver", vehicle_reg="ABC-123",
        vehicle_check={"tyres": True}, checkin_interval_min=15, **kw), db, NS(id=1)))
    run(J.submit_journey(j["id"], db, NS(id=1)))
    run(J.approve_journey(j["id"], ADMIN, db, NS(id=3)))
    run(J.start_journey(j["id"], db, NS(id=1)))
    return j["id"]


@needs_db
def test_overdue_journey_alerts_team_repeats_and_clears_on_checkin(db, make_person, alerts):
    from app.api import journey_management as J
    jid = _running_journey(db, make_person)
    # Nothing to say while the next check-in isn't late yet.
    assert J.journey_overdue_watch(db) == 0
    db.execute(text("UPDATE journey_plan SET next_checkin_due = NOW() - INTERVAL '40 minutes' WHERE id = :i"), {"i": jid})
    db.commit()
    assert J.journey_overdue_watch(db) >= 1
    mine = [a for a in alerts if a["id"] == jid and a["source"] == "journey_overdue"]
    assert len(mine) == 1 and mine[0]["team"] is True
    assert "08030001111" in mine[0]["message"] and "ABC-123" in mine[0]["message"]
    J.journey_overdue_watch(db)
    assert len([a for a in alerts if a["id"] == jid]) == 1                 # not every minute
    db.execute(text("UPDATE journey_plan SET overdue_alerted_at = NOW() - INTERVAL '31 minutes' WHERE id = :i"), {"i": jid})
    db.commit()
    J.journey_overdue_watch(db)
    assert len([a for a in alerts if a["id"] == jid]) == 2                 # repeated after 30 min
    r = run(J.journey_checkin(jid, J.CheckInBody(location="km 40"), db, NS(id=1, username="ops")))
    assert r["overdue"] is False and r["overdue_alerted_at"] is None
    J.journey_overdue_watch(db)
    assert len([a for a in alerts if a["id"] == jid]) == 2
    run(J.complete_journey(jid, db, NS(id=1)))


@needs_db
def test_driver_concern_reaches_response_team(db, make_person, alerts):
    from app.api import journey_management as J
    jid = _running_journey(db, make_person)
    run(J.journey_checkin(jid, J.CheckInBody(location="Ahoada", status="CONCERN", notes="flat tyre"), db, NS(id=1, username="ops")))
    a = [x for x in alerts if x["id"] == jid and x["source"] == "journey_concern"]
    assert len(a) == 1 and a[0]["team"] and "flat tyre" in a[0]["message"] and "08030001111" in a[0]["message"]
    run(J.complete_journey(jid, db, NS(id=1)))


@needs_db
def test_arrival_before_departure_is_refused(db):
    from app.api import journey_management as J, transport_manifest as T
    dep = datetime.now(timezone.utc) + timedelta(hours=3)
    with pytest.raises(HTTPException) as ex:
        run(J.create_journey(J.JourneyCreate(origin="A", destination="B", planned_departure=dep,
                                             planned_arrival=dep - timedelta(hours=1)), db, NS(id=1)))
    assert ex.value.status_code == 400
    with pytest.raises(HTTPException) as ex:
        run(T.create_flight(T.FlightCreate(transport_identifier="HEL-T", departure_location="Rig", arrival_location="Base",
                                           departure_time=dep, arrival_time=dep - timedelta(minutes=5)), db, NS(id=1)))
    assert ex.value.status_code == 400


@needs_db
def test_cancelling_a_flight_tells_passengers_and_notify_reports_channels(db, make_person, alerts):
    from app.api import transport_manifest as T
    p = make_person()
    fid = run(T.create_flight(T.FlightCreate(transport_identifier="HEL-CX", departure_location="Rig", arrival_location="Base",
                                             departure_time=datetime.now(timezone.utc) + timedelta(hours=4)), db, NS(id=1)))["id"]
    run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="INBOUND"), db, NS(id=1)))
    run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="Guest Visitor", direction="INBOUND"), db, NS(id=1)))
    r = run(T.notify_passengers(fid, T.NotifyBody(), db, NS(id=1)))["result"]
    assert set(r["channels"]) == {"whatsapp", "telegram", "email"}            # SMS off by default
    assert r["registered"] == 1 and r["guests"] == 1 and r["sent_any"]
    r = run(T.update_flight_status(fid, T.FlightStatusUpdate(status="CANCELLED"), db, NS(id=1)))
    assert r["notified"] and r["notified"]["registered"] == 1
    assert any(a["id"] == fid and "CANCELLED" in a["subject"] for a in alerts)


@needs_db
def test_delete_journey_only_before_anyone_boarded(db, make_person):
    from app.api import transport_manifest as T
    mk = lambda tag: run(T.create_flight(T.FlightCreate(transport_identifier="HEL-" + tag, departure_location="Rig",
                                                        arrival_location="Base",
                                                        departure_time=datetime.now(timezone.utc) + timedelta(hours=4)),
                                         db, NS(id=1)))["id"]
    fid = mk("DEL1")
    run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="Guest", direction="INBOUND"), db, NS(id=1)))
    run(T.delete_flight(fid, db, NS(id=1)))
    assert db.execute(text("SELECT count(*) FROM transport_schedule WHERE id = :i"), {"i": fid}).scalar() == 0
    fid = mk("DEL2")
    p = make_person()
    e = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="INBOUND"), db, NS(id=1)))
    run(T.update_manifest_entry(fid, e["id"], T.ManifestEntryUpdate(status="CONFIRMED"), ADMIN, db, NS(id=1)))
    with pytest.raises(HTTPException) as ex:
        run(T.delete_flight(fid, db, NS(id=1)))
    assert ex.value.status_code == 400


@needs_db
def test_adding_inbound_passenger_already_on_board_warns(db, make_person):
    from app.api import transport_manifest as T
    p = make_person(onboard=True)
    fid = run(T.create_flight(T.FlightCreate(transport_identifier="HEL-W", departure_location="Base", arrival_location="Rig",
                                             departure_time=datetime.now(timezone.utc) + timedelta(hours=4)), db, NS(id=1)))["id"]
    r = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="INBOUND"), db, NS(id=1)))
    assert "already on board" in r.get("pob_note", "")


@needs_db
def test_boarding_reports_every_broken_limit_and_override_names_them(db, make_person):
    """Overriding 'flight full' used to silently override an expired medical and the
    payload limit too — the operator was only ever shown the first problem."""
    from app.api import transport_manifest as T
    fid = run(T.create_flight(T.FlightCreate(transport_identifier="HEL-ALL", departure_location="Base", arrival_location="Rig",
                                             transport_capacity=1, transport_max_payload_kg=150,
                                             departure_time=datetime.now(timezone.utc) + timedelta(hours=3)), db, NS(id=1)))["id"]
    a, b = make_person(), make_person()
    db.execute(text("UPDATE personnel SET medical_fitness_date = now() - interval '5 days' WHERE id = :i"), {"i": b["id"]})
    db.commit()
    ea = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=a["id"], direction="INBOUND", body_weight=100), db, NS(id=1)))
    eb = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=b["id"], direction="INBOUND", body_weight=90), db, NS(id=1)))
    run(T.update_manifest_entry(fid, ea["id"], T.ManifestEntryUpdate(status="CONFIRMED"), ADMIN, db, NS(id=1)))
    with pytest.raises(HTTPException) as ex:
        run(T.update_manifest_entry(fid, eb["id"], T.ManifestEntryUpdate(status="CONFIRMED"), ADMIN, db, NS(id=1)))
    d = ex.value.detail
    assert ex.value.status_code == 409 and "capacity" in d and "Not fit" in d and "payload" in d
    r = run(T.update_manifest_entry(fid, eb["id"], T.ManifestEntryUpdate(
        status="CONFIRMED", override_capacity=True, override_compliance=True, override_weight=True, remarks="Agreed"),
        ADMIN, db, NS(id=1, username="ops")))
    assert "seat capacity" in r["remarks"] and "fitness to travel" in r["remarks"] and "weight limit" in r["remarks"]


@needs_db
def test_weigh_in_edit_then_reader_check_in_and_cargo_warning(db, make_person):
    """A passenger booked without a weight can be weighed in (there was no way to);
    a TRANSPORT_CHECKIN reader can exist (the DB refused the purpose) and its tap
    checks them in; cargo that tips the flight over its limit is flagged."""
    from app.api import transport_manifest as T
    from app.api.adms_protocol import handle_attlog
    fid = run(T.create_flight(T.FlightCreate(transport_identifier="HEL-WI", departure_location="Rig", arrival_location="Base",
                                             transport_max_payload_kg=200,
                                             departure_time=datetime.now(timezone.utc) + timedelta(hours=1)), db, NS(id=1)))["id"]
    pin = str(uuid.uuid4().int)[:7]
    p = make_person(attendance_id=pin)
    e = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="OUTBOUND"), db, NS(id=1)))
    r = run(T.edit_manifest_entry(fid, e["id"], T.ManifestEntryDetails(body_weight=95, baggage_weight=10), db, NS(id=1)))
    assert r["body_weight"] == 95 and r["baggage_weight"] == 10
    sn = "TC" + uuid.uuid4().hex[:8].upper()
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose) VALUES (:s, 'Helideck', 1, 'TRANSPORT_CHECKIN')"), {"s": sn})
    db.commit()
    handle_attlog([{"PIN": pin, "Time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "Status": "0"}], sn, db)
    db.expire_all()
    assert db.execute(text("SELECT status FROM manifest_entry WHERE id = :i"), {"i": e["id"]}).scalar() == "CONFIRMED"
    w = run(T.set_cargo(fid, T.CargoUpdate(items=[T.CargoItem(description="Gas", weight_kg=150, dangerous_goods=True)]), db, NS(id=1)))
    assert "Over the payload limit" in w["warning"] and "UN number" in w["warning"]


@needs_db
def test_training_module_certificates_decide_fitness_to_travel(db, make_person):
    """An expired BOSIET recorded in Personnel → Training used to be invisible to the
    flight check (it read personnel JSON nothing fills) — the person boarded anyway."""
    from app.api import transport_manifest as T
    from app.models.personnel import Personnel
    code = "BOS" + uuid.uuid4().hex[:5].upper()
    cid = db.execute(text("INSERT INTO training_courses (course_code, course_name, is_mandatory, valid_period_months) "
                          "VALUES (:c, 'BOSIET test', TRUE, 48) RETURNING id"), {"c": code}).scalar()
    p = make_person()
    db.commit()
    person = lambda: db.query(Personnel).filter(Personnel.id == p["id"]).first()
    c = T.travel_compliance(person())
    assert c["status"] == "warning" and any(f"No {code}" in i for i in c["issues"])          # mandatory, not on file
    eid = db.execute(text("INSERT INTO training_enrollment (personnel_id, course_id, status, completion_date, expiry_date) "
                          "VALUES (:p, :c, 'completed', current_date - 1500, current_date - 3) RETURNING id"),
                     {"p": p["id"], "c": cid}).scalar()
    db.commit(); db.expire_all()
    c = T.travel_compliance(person())
    assert c["status"] == "blocked" and any(f"{code} expired" in i for i in c["issues"])
    fid = run(T.create_flight(T.FlightCreate(transport_identifier="HEL-TR", departure_location="Base", arrival_location="Rig",
                                             departure_time=datetime.now(timezone.utc) + timedelta(hours=2)), db, NS(id=1)))["id"]
    e = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="INBOUND"), db, NS(id=1)))
    with pytest.raises(HTTPException) as ex:
        run(T.update_manifest_entry(fid, e["id"], T.ManifestEntryUpdate(status="CONFIRMED"), ADMIN, db, NS(id=1)))
    assert ex.value.status_code == 409 and f"{code} expired" in ex.value.detail
    db.execute(text("INSERT INTO training_enrollment (personnel_id, course_id, status, completion_date, expiry_date) "
                    "VALUES (:p, :c, 'completed', current_date, current_date + 1400)"), {"p": p["id"], "c": cid})
    db.commit(); db.expire_all()
    assert T.travel_compliance(person())["status"] == "ok"                                      # renewed
    db.execute(text("UPDATE training_enrollment SET expiry_date = current_date + 10 WHERE personnel_id = :p AND id <> :e"),
               {"p": p["id"], "e": eid})
    db.commit(); db.expire_all()
    assert T.travel_compliance(person())["status"] == "warning"                                 # expiring soon
    db.execute(text("DELETE FROM training_enrollment WHERE course_id = :c"), {"c": cid})
    db.execute(text("DELETE FROM training_courses WHERE id = :c"), {"c": cid})
    db.commit()
