"""
Zones module (Oct 2026 review):
  * zones are fed by access-control readers and ZKTeco controller doors — a T&A
    terminal cannot be assigned to a zone, and controller port mirrors are not offered
  * each zone reports how many doors / access readers feed it
  * a zone covered by a running muster cannot be deleted
  * crossing a zone's capacity raises one alert, not one per tap
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import needs_db


def _c(headers):
    from app.main import app
    return TestClient(app, headers=headers)


def _terminal(db, purpose, zone=None, mode="adms"):
    sn = "Z" + uuid.uuid4().hex[:9].upper()
    tid = db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose, zone_id, connection_mode) "
                          "VALUES (:s, :a, 1, :p, :z, :m) RETURNING id"),
                     {"s": sn, "a": f"{purpose} {sn}", "p": purpose, "z": zone, "m": mode}).scalar()
    db.commit()
    return tid, sn


@needs_db
def test_only_access_readers_join_zones(db, make_zone, superuser_headers):
    c = _c(superuser_headers)
    z = make_zone()
    ta, _ = _terminal(db, "ATTENDANCE")
    acc, _ = _terminal(db, "ACCESS_ENTRY")
    mirror, msn = _terminal(db, "ACCESS_ENTRY", mode="controller")
    r = c.post(f"/api/v1/zones/{z}/assign-reader", json={"device_id": ta})
    assert r.status_code == 400 and "time & attendance" in r.json()["detail"]
    r = c.post(f"/api/v1/zones/{z}/assign-reader", json={"device_id": mirror})
    assert r.status_code == 400 and "Doors" in r.json()["detail"]
    assert c.post(f"/api/v1/zones/{z}/assign-reader", json={"device_id": acc}).status_code == 200
    devs = {d["id"]: d for d in c.get("/api/v1/zones/available-devices").json()}
    assert mirror not in devs and devs[ta]["assignable"] is False and devs[acc]["assignable"] is True
    zone = c.get(f"/api/v1/zones/{z}").json()
    zone = zone.get("data", zone)
    assert zone["access_reader_count"] == 1 and zone["door_count"] == 0


@needs_db
def test_zone_with_running_muster_cannot_be_deleted(db, make_zone, make_person, superuser_headers):
    c = _c(superuser_headers)
    z = make_zone()
    ev = db.execute(text("INSERT INTO mustering_event (event_type, start_time, status, zone_ids) "
                         "VALUES (1, now(), 0, CAST(:ids AS jsonb)) RETURNING id"), {"ids": f"[{z}]"}).scalar()
    db.commit()
    try:
        r = c.delete(f"/api/v1/zones/{z}")
        assert r.status_code == 409 and "muster" in r.json()["detail"].lower()
    finally:
        db.execute(text("UPDATE mustering_event SET status = 1 WHERE id = :e"), {"e": ev})
        db.commit()
    p = make_person()
    db.execute(text("UPDATE personnel SET current_zone_id = :z WHERE id = :i"), {"z": z, "i": p["id"]})
    db.commit()
    r = c.delete(f"/api/v1/zones/{z}")
    assert r.status_code == 200 and "1 person(s)" in r.json()["message"]


@needs_db
def test_over_capacity_alerts_once_per_crossing(db, make_zone, monkeypatch):
    from app.api import adms_protocol as A
    import app.api.notifications as n
    pushed = []
    monkeypatch.setattr(n, "notify_sync", lambda p: pushed.append(p))
    z = make_zone()
    db.execute(text("UPDATE zones SET max_capacity = 1, current_occupancy = 0 WHERE id = :z"), {"z": z})
    db.commit()
    now = datetime.now(timezone.utc)
    for i in range(3):
        db.execute(text("INSERT INTO zone_personnel_tracking (zone_id, emp_code, device_sn, event_type, punch_time) "
                        "VALUES (:z, :e, 'T', 'CLOCK_IN', :t)"), {"z": z, "e": f"CAP{uuid.uuid4().hex[:6]}", "t": now + timedelta(seconds=i)})
        A._recalc_zone_occupancy(z, db)
        db.commit()
    mine = [p for p in pushed if p["type"] == "zone_over_capacity"]
    assert len(mine) == 1 and "2/1" in mine[0]["title"]      # crossed at the 2nd person, not again at the 3rd
