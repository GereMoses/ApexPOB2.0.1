"""
Mustering — the most safety-critical flow in ApexPOB.

Replaces the legacy suite, which targeted a MusteringZone model and /zones API that
were merged into Zones long ago (the file could not even be imported). These tests use
the real paths: who is EXPECTED at a muster, a scan at a muster-point reader marking
someone SAFE, MISSING people reported with their last known zone, manual marking, and
the HTTP API with real authentication. Runs on the throwaway database (tests/conftest.py).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app


def _zone(db, name, zone_type="WORK_AREA"):
    zid = db.execute(text("""
        INSERT INTO zones (name, code, zone_type, status) VALUES (:n, :c, :t, 'active') RETURNING id
    """), {"n": name, "c": uuid.uuid4().hex[:10].upper(), "t": zone_type}).scalar()
    db.commit()
    return zid


def _person(db, zone_id=None, onboard=True):
    code = "M" + uuid.uuid4().hex[:8].upper()
    pin = str(uuid.uuid4().int)[:8]
    db.execute(text("""
        INSERT INTO personnel (emp_code, first_name, last_name, is_active, is_onboard, is_pob,
                               current_zone_id, attendance_id, status)
        VALUES (:c, 'Muster', :c, TRUE, :ob, :ob, :z, :pin, 'ACTIVE')
    """), {"c": code, "ob": onboard, "z": zone_id, "pin": pin})
    db.commit()
    return {"emp_code": code, "pin": pin}


def _muster_reader(db, zone_id):
    sn = "MSTR" + uuid.uuid4().hex[:8].upper()
    db.execute(text("""
        INSERT INTO iclock_terminal (sn, alias, state, reader_purpose, zone_id)
        VALUES (:sn, 'Muster reader', 1, 'MUSTERING', :z)
    """), {"sn": sn, "z": zone_id})
    db.commit()
    return sn


def _status(db, event_id, emp_code):
    return db.execute(text("SELECT status FROM mustering_log WHERE event_id = :e AND emp_code = :c"),
                      {"e": event_id, "c": emp_code}).scalar()


@pytest.fixture
def site(db_session):
    """A work zone with one person in it, one on board elsewhere, one off site,
    and a muster point with its reader. Any event left active is ended afterwards."""
    db = db_session
    work = _zone(db, "Deck " + uuid.uuid4().hex[:4])
    other = _zone(db, "Galley " + uuid.uuid4().hex[:4])
    muster = _zone(db, "Muster " + uuid.uuid4().hex[:4], "MUSTER_POINT")
    s = {
        "db": db, "work": work, "other": other, "muster": muster,
        "in_zone": _person(db, work), "elsewhere": _person(db, other), "ashore": _person(db, None, onboard=False),
        "reader": _muster_reader(db, muster),
    }
    yield s
    db.execute(text("UPDATE mustering_event SET status = 1, end_time = now() WHERE status = 0"))
    db.commit()


def _start(site, zones=None):
    from app.services.mustering_service import MusteringService
    r = MusteringService(site["db"]).start_mustering_event(
        zone_ids=zones or [site["work"]], event_type=1, initiated_by=1, muster_zone_ids=[site["muster"]])
    return r["event_id"]


def test_expected_roster_is_people_in_the_affected_zone(site):
    ev = _start(site)
    db = site["db"]
    assert _status(db, ev, site["in_zone"]["emp_code"]) == 0          # expected, not yet safe
    assert _status(db, ev, site["elsewhere"]["emp_code"]) is None      # different zone
    assert _status(db, ev, site["ashore"]["emp_code"]) is None         # off site


def test_scan_at_muster_reader_marks_person_safe(site):
    """The real reader path: a tap on a MUSTERING-purpose reader at the muster point."""
    from app.api.adms_protocol import handle_attlog
    from app.services.mustering_service import MusteringService
    ev = _start(site)
    db = site["db"]
    t = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
    handle_attlog([{"PIN": site["in_zone"]["pin"], "Time": t, "Status": "0"}], site["reader"], db)
    assert _status(db, ev, site["in_zone"]["emp_code"]) == 1
    hc = MusteringService(db).get_event_headcount(ev)
    assert (hc["total_safe"], hc["total_missing"]) == (1, 0)


def test_missing_person_reported_with_last_known_zone(site):
    from app.services.mustering_service import MusteringService
    ev = _start(site)
    missing = MusteringService(site["db"]).get_event_logs(ev, status=0)
    row = next(m for m in missing if m["emp_code"] == site["in_zone"]["emp_code"])
    assert row.get("last_known_zone_id") == site["work"]          # where rescue should look


def test_area_muster_includes_on_board_people_with_unknown_location(site):
    """An area muster lists people located in the area AND everyone on board whose
    location is unknown (they could be there) — never someone a reader places in a
    different zone, never someone off site."""
    db = site["db"]
    unknown = _person(db, None)                                       # on board, no zone
    empty = _zone(db, "Empty " + uuid.uuid4().hex[:4])
    ev = _start(site, zones=[empty])
    assert _status(db, ev, unknown["emp_code"]) == 0                  # expected (location unknown)
    assert _status(db, ev, site["elsewhere"]["emp_code"]) is None     # placed in another zone
    assert _status(db, ev, site["ashore"]["emp_code"]) is None        # off site


def test_manual_mark_and_end_event(site):
    from app.services.mustering_service import MusteringService
    svc = MusteringService(site["db"])
    ev = _start(site)
    svc.mark_person_status(ev, site["in_zone"]["emp_code"], status=1, marked_by=1)
    assert _status(site["db"], ev, site["in_zone"]["emp_code"]) == 1
    svc.end_mustering_event(ev, ended_by=1, reason="drill complete")
    assert site["db"].execute(text("SELECT status FROM mustering_event WHERE id = :e"), {"e": ev}).scalar() != 0


def test_api_start_headcount_missing_and_end(site, superuser_headers):
    client = TestClient(app, headers=superuser_headers)
    r = client.post("/api/mustering/events/start",
                    json={"zone_ids": [site["work"]], "muster_zone_ids": [site["muster"]], "event_type": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    ev = (body.get("data") or body)["event_id"]
    hc = client.get(f"/api/mustering/events/{ev}/headcount/")
    assert hc.status_code == 200, hc.text
    missing = client.get(f"/api/mustering/events/{ev}/missing-persons/")
    assert missing.status_code == 200, missing.text
    assert site["in_zone"]["emp_code"] in missing.text
    end = client.post(f"/api/mustering/events/{ev}/end", json={"reason": "test"})
    assert end.status_code == 200, end.text


def test_api_requires_login():
    r = TestClient(app).post("/api/mustering/events/start", json={"zone_ids": [1], "event_type": 1})
    assert r.status_code == 401
