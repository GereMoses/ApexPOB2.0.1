"""
Regression tests for the go-live safety rules (see conftest for how they run).
Each test states the real-world situation it protects.
"""
import asyncio
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from .conftest import needs_db, person_state

LAGOS = timezone(timedelta(hours=1))
ADMIN = NS(state=NS(user_permissions=["*"]))
MANAGER = NS(state=NS(user_permissions=["transport.manage", "journey.manage"]))
run = asyncio.run


# ─── Attendance (no database) ───────────────────────────────────────────────────

def _punch(h, m, state=1):
    return NS(punch_time=datetime(2026, 10, 15, h, m, tzinfo=timezone.utc), punch_state=state)


def test_punch_converted_to_site_time():
    """A 06:02Z punch is 07:02 in Lagos — shifts are compared in site time."""
    from app.services.attendance_calculation_service import _naive
    assert _naive(_punch(6, 2).punch_time) == datetime(2026, 10, 15, 7, 2)


def test_first_in_last_out_ignores_reader_key_and_repeat_taps():
    """The F18 stamps every tap Check-Out; first tap must still be the clock-in."""
    from app.services.attendance_calculation_service import _first_in_last_out, _pair_punches
    pairs = _pair_punches(_first_in_last_out([_punch(6, 2), _punch(6, 4), _punch(18, 5)], 30))
    assert pairs == [(_punch(6, 2).punch_time, _punch(18, 5).punch_time)]


def test_single_or_repeat_taps_give_clock_in_only():
    from app.services.attendance_calculation_service import _first_in_last_out, _pair_punches
    assert _pair_punches(_first_in_last_out([_punch(6, 2), _punch(6, 10)], 30)) == [(_punch(6, 2).punch_time, None)]


# ─── Land journey risk (no database) ────────────────────────────────────────────

def test_night_driving_judged_in_site_time_including_arrival():
    """18:30–19:20 Lagos is a night trip (UTC hours or hourly sampling missed it)."""
    from app.api.journey_management import _crosses_night
    assert _crosses_night(datetime(2026, 10, 20, 18, 30, tzinfo=LAGOS), datetime(2026, 10, 20, 19, 20, tzinfo=LAGOS))
    assert not _crosses_night(datetime(2026, 10, 20, 9, 0, tzinfo=LAGOS), datetime(2026, 10, 20, 12, 0, tzinfo=LAGOS))


def test_seamlesshr_reply_with_failed_records_is_not_success():
    """SeamlessHR answers HTTP 200 even when every record failed."""
    from app.services.seamlesshr_service import _batch_accepted
    bad = NS(status_code=200, json=lambda: {"message": "processed",
             "data": {"message": "0 attendance records sent successfully, 1 attendance records failed"}})
    good = NS(status_code=200, json=lambda: {"message": "processed",
              "data": {"message": "1 attendance records sent successfully, 0 attendance records failed"}})
    assert _batch_accepted(bad)[0] is False
    assert _batch_accepted(good)[0] is True


# ─── Zones & on-board status ───────────────────────────────────────────────────

@needs_db
def test_zone_moves_parent_exit_late_upload_and_boundary(db, make_person, make_zone):
    from app.api.adms_protocol import _handle_zone_access
    site = make_zone("Site")
    gate = make_zone("Gate", boundary=True)
    room = make_zone("Control", parent=site)
    p = make_person()
    t0 = datetime.now(timezone.utc) - timedelta(hours=3)
    tap = lambda z, d, m: _handle_zone_access(p["emp_code"], "T", t0 + timedelta(minutes=m), NS(zone_id=z, alias="t"), d, db)

    tap(gate, "ENTRY", 0)
    assert person_state(db, p["emp_code"]) == (True, gate)          # arrived on site
    tap(room, "ENTRY", 30)
    assert person_state(db, p["emp_code"]) == (True, room)
    tap(room, "EXIT", 60)
    assert person_state(db, p["emp_code"]) == (True, site)          # leaving a room -> parent, not "nowhere"
    tap(room, "ENTRY", 10)                                          # reader buffer uploaded late
    assert person_state(db, p["emp_code"]) == (True, site)          # history only, location unchanged
    tap(gate, "EXIT", 90)
    assert person_state(db, p["emp_code"]) == (False, None)         # boundary exit = off site
    counts = dict(db.execute(text("SELECT id, current_personnel_count FROM zones WHERE id IN (:a,:b,:c)"),
                             {"a": site, "b": gate, "c": room}).fetchall())
    assert counts == {site: 0, gate: 0, room: 0}


@needs_db
def test_attendance_tap_never_changes_on_board_status(db, make_person):
    """T&A terminals can be in another state or country: a tap there (in or out) leaves
    on-board status — and so the muster list — exactly as it was."""
    from app.api.adms_protocol import handle_attlog
    p = make_person(attendance_id="77001", onboard=True)
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose) "
                    "VALUES ('SAFETYTEST1', 't', 1, 'ATTENDANCE') ON CONFLICT DO NOTHING"))
    db.commit()
    t = (datetime.now(timezone.utc) - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S")
    handle_attlog([{"PIN": "77001", "Time": t, "Status": "1"}], "SAFETYTEST1", db)
    assert person_state(db, p["emp_code"])[0] is True


@needs_db
def test_inactivity_checkout_writes_no_fake_attendance_punch(db, make_person, make_zone):
    from app.services import database_admin_service as D
    z = make_zone()
    p = make_person(onboard=True)
    db.execute(text("UPDATE personnel SET current_zone_id=:z, last_seen=now()-interval '3 days' WHERE id=:i"),
               {"z": z, "i": p["id"]})
    db.commit()
    before = db.execute(text("SELECT count(*) FROM iclock_transaction")).scalar()
    D.auto_checkout_stale(db, 2)
    assert person_state(db, p["emp_code"]) == (False, None)
    assert db.execute(text("SELECT count(*) FROM iclock_transaction")).scalar() == before


# ─── Flights / manifests ───────────────────────────────────────────────────────

def _flight(db, **kw):
    from app.api import transport_manifest as T
    args = dict(transport_identifier="HEL-" + kw.pop("tag", "X"), departure_location="Rig",
                arrival_location="Helipad", departure_time=datetime.now(timezone.utc) + timedelta(hours=2))
    args.update(kw)
    return run(T.create_flight(T.FlightCreate(**args), db, NS(id=1)))["id"]


@needs_db
def test_outbound_off_pob_only_on_departure_and_back_if_turned_back(db, make_person):
    from app.api import transport_manifest as T
    p = make_person(onboard=True)
    fid = _flight(db, tag="OUT")
    e = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="OUTBOUND"), db, NS(id=1)))
    run(T.update_manifest_entry(fid, e["id"], T.ManifestEntryUpdate(status="CONFIRMED"), ADMIN, db, NS(id=1)))
    assert person_state(db, p["emp_code"])[0] is True            # boarded, still on the helideck
    run(T.update_flight_status(fid, T.FlightStatusUpdate(status="IN_TRANSIT"), db, NS(id=1)))
    assert person_state(db, p["emp_code"])[0] is False           # flown out
    run(T.update_flight_status(fid, T.FlightStatusUpdate(status="CANCELLED"), db, NS(id=1)))
    assert person_state(db, p["emp_code"])[0] is True            # turned back


@needs_db
def test_inbound_on_pob_at_arrival_in_arrival_zone_and_undo_on_removal(db, make_person, make_zone):
    from app.api import transport_manifest as T
    hz = make_zone("Helipad")
    p = make_person()
    fid = _flight(db, tag="IN")
    e = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="INBOUND"), db, NS(id=1)))
    run(T.update_manifest_entry(fid, e["id"], T.ManifestEntryUpdate(status="CONFIRMED"), ADMIN, db, NS(id=1)))
    assert person_state(db, p["emp_code"])[0] is False           # boarded onshore, not here yet
    run(T.update_flight_status(fid, T.FlightStatusUpdate(status="COMPLETED"), db, NS(id=1)))
    assert person_state(db, p["emp_code"]) == (True, hz)
    run(T.delete_manifest_entry(fid, e["id"], db, NS(id=1)))
    assert person_state(db, p["emp_code"])[0] is False


@needs_db
def test_completed_flight_cannot_be_reopened(db):
    from app.api import transport_manifest as T
    fid = _flight(db, tag="DONE")
    run(T.update_flight_status(fid, T.FlightStatusUpdate(status="COMPLETED"), db, NS(id=1)))
    with pytest.raises(HTTPException) as ex:
        run(T.update_flight_status(fid, T.FlightStatusUpdate(status="SCHEDULED"), db, NS(id=1)))
    assert ex.value.status_code == 400


@needs_db
def test_weight_limit_and_override_rules(db, make_person):
    from app.api import transport_manifest as T
    p = make_person()
    fid = _flight(db, tag="WT", transport_max_payload_kg=300)
    e = run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="INBOUND"), db, NS(id=1)))
    upd = lambda req, **kw: run(T.update_manifest_entry(fid, e["id"], T.ManifestEntryUpdate(status="CONFIRMED", **kw), req, db, NS(id=1, username="u")))
    for req, kw, code in ((ADMIN, {}, 409),                                   # no weight = not 0 kg
                          (MANAGER, {"override_weight": True, "remarks": "x"}, 403),   # needs permission
                          (ADMIN, {"override_weight": True}, 400)):           # needs a reason
        with pytest.raises(HTTPException) as ex:
            upd(req, **kw)
        assert ex.value.status_code == code
    r = upd(ADMIN, override_weight=True, remarks="Scale broken")
    assert r["status"] == "CONFIRMED" and "OVERRIDE" in r["remarks"]


@needs_db
def test_reconcile_never_counts_missing_as_present(db, make_person):
    from app.api import transport_manifest as T
    p = make_person(onboard=True)
    fid = _flight(db, tag="REC")
    run(T.add_manifest_entry(fid, T.ManifestEntryCreate(passenger_name="", personnel_id=p["id"], direction="OUTBOUND"), db, NS(id=1)))
    ev = db.execute(text("INSERT INTO mustering_event (event_type, start_time, status) VALUES (1, now(), 0) RETURNING id")).scalar()
    db.execute(text("INSERT INTO mustering_log (event_id, emp_code, check_time, status) VALUES (:e, :c, now(), 0)"),
               {"e": ev, "c": p["emp_code"]})
    db.commit()
    try:
        r = run(T.reconcile_manifest_with_mustering(fid, db, NS(id=1)))
        assert p["emp_code"] not in r["verified_emp_codes"]
        assert [m["emp_code"] for m in r["missing_in_muster"]] == [p["emp_code"]]
    finally:
        db.execute(text("UPDATE mustering_event SET status = 1 WHERE id = :e"), {"e": ev})
        db.commit()


# ─── Land journeys ─────────────────────────────────────────────────────────────

def _journey(db, **kw):
    from app.api import journey_management as J
    args = dict(origin="PH", destination="Warri", planned_departure=datetime.now(timezone.utc) + timedelta(hours=1))
    args.update(kw)
    return run(J.create_journey(J.JourneyCreate(**args), db, NS(id=1)))


@needs_db
def test_journey_approval_rules_and_vehicle_check(db):
    from app.api import journey_management as J
    j = _journey(db, distance_km=320, risk_factors=["Security"])       # HIGH risk
    assert j["risk_level"] == "HIGH"
    run(J.submit_journey(j["id"], db, NS(id=1)))
    for req, user, code in ((MANAGER, NS(id=3), 403),                  # no approve permission
                            (ADMIN, NS(id=1), 403)):                   # planner approving own trip
        with pytest.raises(HTTPException) as ex:
            run(J.approve_journey(j["id"], req, db, user))
        assert ex.value.status_code == code
    assert run(J.approve_journey(j["id"], ADMIN, db, NS(id=3)))["status"] == "SUBMITTED"   # 1 of 2
    with pytest.raises(HTTPException):
        run(J.approve_journey(j["id"], ADMIN, db, NS(id=3)))           # same approver twice
    assert run(J.approve_journey(j["id"], ADMIN, db, NS(id=4)))["status"] == "APPROVED"
    with pytest.raises(HTTPException):
        run(J.start_journey(j["id"], db, NS(id=1)))                    # no vehicle check yet
    run(J.record_vehicle_check(j["id"], J.VehicleCheckBody(vehicle_check={"tyres": True}), db, NS(id=1)))
    assert run(J.start_journey(j["id"], db, NS(id=1)))["status"] == "IN_PROGRESS"


@needs_db
def test_journey_edit_keeps_manual_risk_factors(db):
    from app.api import journey_management as J
    j = _journey(db, risk_factors=["Security"])
    j = run(J.update_journey(j["id"], J.JourneyUpdate(notes="edited"), db, NS(id=1)))
    assert j["risk_factors"].count("Security") == 1


@needs_db
def test_leaving_site_journey_moves_staff_not_guests_and_undoes(db, make_person, make_zone):
    from app.api import journey_management as J
    make_zone("Jetty")
    p = make_person(onboard=True)
    j = _journey(db, origin="Jetty", destination="Warri", vehicle_check={"tyres": True},
                 passengers=[{"name": "Staff", "emp_code": p["emp_code"]}, {"name": "Guest"}])
    assert j["pob_movement"] == "OUTBOUND"
    run(J.submit_journey(j["id"], db, NS(id=1)))
    run(J.approve_journey(j["id"], ADMIN, db, NS(id=3)))
    r = run(J.start_journey(j["id"], db, NS(id=1)))
    assert person_state(db, p["emp_code"])[0] is False and r["pob_applied_count"] == 1
    run(J.cancel_journey(j["id"], db, NS(id=1)))
    assert person_state(db, p["emp_code"])[0] is True


@needs_db
def test_access_door_tap_puts_person_on_board_but_is_not_attendance(db, make_person, make_zone, superuser_headers):
    """Access-control readers drive on-board status and the door feed; T&A readers drive
    attendance. A door tap writes no attendance punch; a T&A tap never shows in the feed."""
    import uuid as _u
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.adms_protocol import handle_attlog
    z = make_zone()
    acc, ta = "AC" + _u.uuid4().hex[:8].upper(), "TA" + _u.uuid4().hex[:8].upper()
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose, zone_id) VALUES (:s, 'Gate door', 1, 'ACCESS_ENTRY', :z)"), {"s": acc, "z": z})
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose) VALUES (:s, 'Abuja F18', 1, 'ATTENDANCE')"), {"s": ta})
    db.commit()
    pin = str(_u.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    t = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    handle_attlog([{"PIN": pin, "Time": t, "Status": "0"}], acc, db)
    assert person_state(db, p["emp_code"])[0] is True
    assert db.execute(text("SELECT count(*) FROM iclock_transaction WHERE terminal_sn = :s"), {"s": acc}).scalar() == 0
    handle_attlog([{"PIN": pin, "Time": t, "Status": "0"}], ta, db)
    assert db.execute(text("SELECT count(*) FROM iclock_transaction WHERE terminal_sn = :s"), {"s": ta}).scalar() == 1
    feed = TestClient(app, headers=superuser_headers).get("/api/v1/pob-status/dashboard").json()
    feed = (feed.get("data") or feed).get("recent_events", [])
    assert any(e["type"] == "ENTRY" for e in feed)
    assert not any(e["type"] in ("CHECK_IN", "CHECK_OUT", "REPEAT_TAP") for e in feed)
