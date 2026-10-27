"""
ZKTeco C3/inBio controllers in an emergency:
  * adding a controller creates a door record per port (emergencies act on doors)
  * fire mode unlocks fire exits + switches sirens on AUX outputs
  * clearing fire mode re-locks the fire exits, silences sirens and ends the
    muster properly (all-clear sent)
The panel is simulated: we capture the commands instead of opening a TCP socket.
"""
import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import needs_db


@pytest.fixture
def panel(monkeypatch):
    sent = []
    import app.services.zkteco.c3_zkaccess as z

    class FakeC3:
        def __init__(self, ip, port=4370, password=""): self.ip = ip
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def open_door(self, door, duration): sent.append(("door", self.ip, door, duration)); return True
        def aux_output(self, aux, duration): sent.append(("aux", self.ip, aux, duration)); return True
    monkeypatch.setattr(z, "ZKAccessC3Client", FakeC3)
    import app.services.notify_dispatch as nd
    monkeypatch.setattr(nd, "dispatch_background", lambda *a, **k: sent.append(("alert", a[0])) or {})
    monkeypatch.setattr(nd, "configured_channels", lambda: {"email": True, "whatsapp": True, "sms": False})
    return sent


def _client(headers):
    from app.main import app
    return TestClient(app, headers=headers)


@needs_db
def test_controller_doors_roles_and_sirens(superuser_headers, panel, db):
    c = _client(superuser_headers)
    ip = f"10.9.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    r = c.post("/api/v1/access-controllers", json={"name": "Gate panel", "ip_address": ip, "model": "C3-400", "door_count": 4})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    doors = c.get(f"/api/v1/access-controllers/{cid}/doors").json()
    assert [d["port"] for d in doors] == [1, 2, 3, 4] and all(d["emergency_action"] == 0 for d in doors)
    r = c.put(f"/api/v1/access-controllers/doors/{doors[0]['id']}", json={"name": "Main exit", "emergency_action": 2})
    assert r.json()["role"].startswith("Fire exit")
    r = c.post(f"/api/v1/access-controllers/{cid}/sirens", json={"aux_no": 1, "name": "Yard siren"})
    assert r.status_code == 201, r.text
    assert c.post(f"/api/v1/access-controllers/{cid}/sirens", json={"aux_no": 1}).status_code == 409
    assert c.post(f"/api/v1/access-controllers/{cid}/aux/1/test").json()["success"]
    assert ("aux", ip, 1, 3) in panel


@needs_db
def test_fire_mode_unlocks_then_clear_relocks_and_ends_muster(superuser_headers, panel, db, make_person, make_zone):
    from app.services.emergency_service import emergency_service
    c = _client(superuser_headers)
    ip = f"10.8.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    cid = c.post("/api/v1/access-controllers", json={"name": "Fire panel", "ip_address": ip, "model": "C3-200", "door_count": 2}).json()["id"]
    exit_door = c.get(f"/api/v1/access-controllers/{cid}/doors").json()[0]
    c.put(f"/api/v1/access-controllers/doors/{exit_door['id']}", json={"emergency_action": 2})
    c.post(f"/api/v1/access-controllers/{cid}/sirens", json={"aux_no": 2, "name": "Siren"})
    make_zone()
    p = make_person()
    db.execute(text("UPDATE personnel SET is_onboard = TRUE WHERE emp_code = :c"), {"c": p["emp_code"]})
    db.commit()
    for ev in db.execute(text("SELECT id FROM mustering_event WHERE status = 0")).fetchall():
        db.execute(text("UPDATE mustering_event SET status = 1 WHERE id = :i"), {"i": ev[0]})
    db.commit()

    asyncio.run(emergency_service.activate_fire_mode(zone_id=None, location_id=None, muster_zone_ids=None,
                                                     action="activate", reason="test fire", initiated_by=None, db=db))
    assert ("door", ip, 1, 255) in panel                 # fire exit held open
    assert ("aux", ip, 2, 255) in panel                  # siren on
    assert db.execute(text("SELECT count(*) FROM mustering_event WHERE status = 0")).scalar() == 1

    asyncio.run(emergency_service.activate_fire_mode(zone_id=None, location_id=None, muster_zone_ids=None,
                                                     action="clear", reason="all clear", initiated_by=None, db=db))
    assert ("door", ip, 1, 0) in panel                   # fire exit locked again
    assert ("aux", ip, 2, 0) in panel                    # siren off
    assert db.execute(text("SELECT count(*) FROM mustering_event WHERE status = 0")).scalar() == 0
    assert ("alert", "muster") in panel and ("alert", "muster_all_clear") in panel
