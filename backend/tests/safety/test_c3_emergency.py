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
        def push_users(self, users, door_nos=None, timezone_id=1):
            for u in users:
                sent.append(("user", self.ip, u["pin"], u.get("card_no"), u.get("expire"), tuple(door_nos or ())))
            return {"pushed": len(users), "failed": []}
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


# ── taps on C3 reader ports → attendance / POB / muster / unknown cards ──────
def _controller_with_reader(c, purpose, zone_id, door_count=1):
    ip = f"10.7.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    ctrl = c.post("/api/v1/access-controllers", json={"name": "Gate", "ip_address": ip, "model": "C3-100", "door_count": door_count}).json()
    for r in ctrl["readers"]:
        c.put(f"/api/v1/access-controllers/readers/{r['id']}", json={"purpose": purpose, "zone_id": zone_id})
    from app.models.access_controller import AccessController
    return ctrl["id"]


def _tap(db, cid, *, pin=None, card=None, direction=0, event_type=0, when=None):
    from datetime import datetime
    from app.models.access_controller import AccessController
    from app.services.access_controller_ingest import ingest_event
    from app.services.zkteco.c3_controller import C3Event
    ctrl = db.query(AccessController).get(cid)
    return ingest_event(ctrl, C3Event(time=when or datetime(2026, 10, 27, 7, 55, 0), card_no=card, pin=pin, door_id=1,
                                      event_type=event_type, in_out=direction, verify_type=4), db)


@needs_db
def test_c3_attendance_tap_becomes_a_punch_in_utc(superuser_headers, panel, db, make_person, make_zone):
    c = _client(superuser_headers)
    gate = make_zone(boundary=True)
    pin = str(uuid.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    cid = _controller_with_reader(c, "ATTENDANCE", gate)
    _tap(db, cid, pin=pin)                               # 07:55 Lagos on the panel
    row = db.execute(text("SELECT punch_time AT TIME ZONE 'UTC', punch_state, t.reader_purpose FROM iclock_transaction x "
                          "JOIN iclock_terminal t ON t.sn = x.terminal_sn WHERE x.emp_code = :c"), {"c": p["emp_code"]}).fetchone()
    assert row is not None and str(row[0]).startswith("2026-10-27 06:55")   # stored in UTC
    assert row[1] == 0 and row[2] == "ATTENDANCE"
    assert db.execute(text("SELECT is_onboard FROM personnel WHERE emp_code = :c"), {"c": p["emp_code"]}).scalar()


@needs_db
def test_refused_card_is_logged_and_can_be_issued(superuser_headers, panel, db, make_person, make_zone):
    c = _client(superuser_headers)
    gate = make_zone(boundary=True)
    pin = str(uuid.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    cid = _controller_with_reader(c, "ATTENDANCE", gate)
    card = str(uuid.uuid4().int)[:9]
    _tap(db, cid, card=card, event_type=27)              # unregistered card
    assert db.execute(text("SELECT count(*) FROM iclock_transaction WHERE terminal_sn LIKE :s"), {"s": f"AC{cid}-%"}).scalar() == 0
    assert card in [u["card_no"] for u in c.get("/api/v1/access-controllers/cards/unknown").json()]
    r = c.post("/api/v1/access-controllers/cards/assign", json={"card_no": card, "emp_code": p["emp_code"]})
    assert r.status_code == 200, r.text
    _tap(db, cid, card=card)                             # same card, now granted
    assert db.execute(text("SELECT count(*) FROM iclock_transaction WHERE emp_code = :c"), {"c": p["emp_code"]}).scalar() == 1


@needs_db
def test_access_only_reader_does_not_count_for_attendance(superuser_headers, panel, db, make_person, make_zone):
    from app.services.attendance_calculation_service import attendance_calculation_service  # noqa: F401
    c = _client(superuser_headers)
    room = make_zone()
    pin = str(uuid.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    cid = _controller_with_reader(c, "ACCESS", room)
    _tap(db, cid, pin=pin)
    assert db.execute(text("SELECT t.reader_purpose FROM iclock_transaction x JOIN iclock_terminal t ON t.sn = x.terminal_sn "
                           "WHERE x.emp_code = :c"), {"c": p["emp_code"]}).scalar() == "ACCESS_ENTRY"   # not counted as attendance


@needs_db
def test_c3_reader_at_muster_point_counts_people_safe(superuser_headers, panel, db, make_person, make_zone):
    from datetime import datetime, timezone
    from app.services.mustering_service import MusteringService
    c = _client(superuser_headers)
    area = make_zone()
    mp = db.execute(text("INSERT INTO zones (name, code, zone_type, status) VALUES (:n, :c, 'MUSTER_POINT', 'active') RETURNING id"),
                    {"n": "MP " + uuid.uuid4().hex[:5], "c": uuid.uuid4().hex[:10].upper()}).scalar()
    db.commit()
    pin = str(uuid.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    db.execute(text("UPDATE personnel SET is_onboard = TRUE, current_zone_id = :z WHERE emp_code = :c"), {"z": area, "c": p["emp_code"]})
    db.commit()
    cid = _controller_with_reader(c, "MUSTERING", mp)
    for ev in db.execute(text("SELECT id FROM mustering_event WHERE status = 0")).fetchall():
        db.execute(text("UPDATE mustering_event SET status = 1 WHERE id = :i"), {"i": ev[0]})
    db.commit()
    ev = MusteringService(db).start_mustering_event([area], 1, None, muster_zone_ids=[mp])["event_id"]
    try:
        _tap(db, cid, pin=pin, when=datetime.now())
        assert db.execute(text("SELECT status FROM mustering_log WHERE event_id = :e AND emp_code = :c"),
                          {"e": ev, "c": p["emp_code"]}).scalar() == 1
    finally:
        MusteringService(db).end_mustering_event(ev, None)



@needs_db
def test_panel_sync_loads_staff_and_removes_leavers(superuser_headers, panel, db, make_person, monkeypatch):
    import app.services.zkteco.c3_zkaccess as z
    monkeypatch.setattr(z, "sdk_available", lambda: True)
    c = _client(superuser_headers)
    ip = f"10.6.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    cid = c.post("/api/v1/access-controllers", json={"name": "Sync", "ip_address": ip, "model": "C3-200", "door_count": 2}).json()["id"]
    pin = str(uuid.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    r = c.post(f"/api/v1/access-controllers/{cid}/sync-users").json()
    assert any(x[0] == "user" and x[1] == ip and x[2] == pin and x[5] == (1, 2) for x in panel)
    assert r["load"]["pushed"] >= 1
    # nothing changed → nothing re-sent for this person
    panel.clear()
    c.post(f"/api/v1/access-controllers/{cid}/sync-users")
    assert not any(x[0] == "user" and x[2] == pin for x in panel)
    # leaver → expired on the panel
    db.execute(text("UPDATE personnel SET is_active = FALSE WHERE emp_code = :c"), {"c": p["emp_code"]})
    db.commit()
    c.post(f"/api/v1/access-controllers/{cid}/sync-users")
    removal = [x for x in panel if x[0] == "user" and x[2] == pin]
    assert removal and removal[0][4] and removal[0][3] == ""            # end date set, card cleared
    states = {u["pin"]: u["state"] for u in c.get(f"/api/v1/access-controllers/{cid}/users").json()}
    assert states[pin] == "removed"


@needs_db
def test_card_import_by_attendance_id(superuser_headers, panel, db, make_person):
    c = _client(superuser_headers)
    pin = str(uuid.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    card = str(uuid.uuid4().int)[:9]
    r = c.post("/api/v1/access-controllers/cards/import", json=[{"key": pin, "card_no": card},
                                                              {"key": "NOBODY", "card_no": "123"},
                                                              {"key": p["emp_code"], "card_no": card}]).json()
    assert r["updated"] == 1 and len(r["problems"]) == 2
    assert db.execute(text("SELECT card_number FROM personnel WHERE emp_code = :c"), {"c": p["emp_code"]}).scalar() == int(card)


@needs_db
def test_fire_alarm_input_starts_fire_mode(superuser_headers, panel, db, monkeypatch):
    import app.services.access_controller_ingest as ing
    fired = []
    monkeypatch.setattr(ing, "_trigger_fire_mode", lambda ctrl, when: fired.append(ctrl.id))
    c = _client(superuser_headers)
    ip = f"10.5.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    cid = c.post("/api/v1/access-controllers", json={"name": "FA", "ip_address": ip, "model": "C3-200", "door_count": 2,
                                                    "fire_alarm_input": 2, "fire_alarm_on": "open"}).json()["id"]
    _tap(db, cid, event_type=221)                         # contact closed (normal) on input 1 → nothing
    _tap(db, cid, event_type=220)                         # input 1 opened — not the fire input
    assert fired == []
    from datetime import datetime
    from app.models.access_controller import AccessController
    from app.services.access_controller_ingest import ingest_event
    from app.services.zkteco.c3_controller import C3Event
    ingest_event(db.query(AccessController).get(cid), C3Event(time=datetime.now(), card_no=None, pin=None, door_id=2,
                                                             event_type=220, in_out=0, verify_type=0), db)
    assert fired == [cid]


@needs_db
def test_door_pin_set_loaded_and_never_logged(superuser_headers, panel, db, make_person, monkeypatch):
    import app.services.zkteco.c3_zkaccess as z
    import app.services.notify_dispatch as nd
    monkeypatch.setattr(z, "sdk_available", lambda: True)
    monkeypatch.setattr(nd, "configured_channels", lambda: {"email": False, "whatsapp": False, "sms": False})
    c = _client(superuser_headers)
    pin = str(uuid.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    assert c.post("/api/v1/access-controllers/pins", json={"emp_code": p["emp_code"], "pin": "1234"}).status_code == 400
    r = c.post("/api/v1/access-controllers/pins", json={"emp_code": p["emp_code"], "send": True}).json()
    door_pin = r["pin"]
    assert len(door_pin) == 6 and door_pin.isdigit()
    stored = db.execute(text("SELECT door_pin_enc FROM personnel WHERE emp_code = :c"), {"c": p["emp_code"]}).scalar()
    assert stored and door_pin not in stored                                   # encrypted at rest
    logged = db.execute(text("SELECT string_agg(message, '|') FROM notify_delivery WHERE source_type = 'door_pin'")).scalar() or ""
    assert door_pin not in logged                                              # never in the delivery log
    status = c.get("/api/v1/access-controllers/pins/status", params={"search": p["emp_code"]}).json()
    assert status["people"][0]["has_pin"] is True and "pin" not in status["people"][0]

    ip = f"10.4.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    cid = c.post("/api/v1/access-controllers", json={"name": "Keypad", "ip_address": ip, "model": "C3-100", "door_count": 1}).json()["id"]
    from app.services.panel_sync import active_panel_users
    users, _ = active_panel_users(db, [p["emp_code"]])
    assert users[0]["password"] == door_pin
    c.post(f"/api/v1/access-controllers/{cid}/sync-users")
    assert any(x[0] == "user" and x[2] == pin for x in panel)
    # a new PIN is re-sent at the next sync; an unchanged one is not
    panel.clear()
    c.post(f"/api/v1/access-controllers/{cid}/sync-users")
    assert not any(x[0] == "user" and x[2] == pin for x in panel)
    c.post("/api/v1/access-controllers/pins", json={"emp_code": p["emp_code"]})
    c.post(f"/api/v1/access-controllers/{cid}/sync-users")
    assert any(x[0] == "user" and x[2] == pin for x in panel)


@needs_db
def test_door_verify_mode_is_written_to_the_panel(superuser_headers, panel, db, monkeypatch):
    import app.services.zkteco.c3_zkaccess as z
    monkeypatch.setattr(z, "sdk_available", lambda: True)
    params = []
    monkeypatch.setattr(z.ZKAccessC3Client, "set_door_verify_mode", lambda self, door, mode: params.append((door, mode)), raising=False)
    c = _client(superuser_headers)
    ip = f"10.3.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    cid = c.post("/api/v1/access-controllers", json={"name": "Lab", "ip_address": ip, "model": "C3-200", "door_count": 2}).json()["id"]
    door = c.get(f"/api/v1/access-controllers/{cid}/doors").json()[1]
    r = c.put(f"/api/v1/access-controllers/doors/{door['id']}", json={"verify_mode": 11}).json()
    assert r["verify_label"] == "Card + PIN" and r["panel"]["ok"] and params == [(2, 11)]
    assert c.put(f"/api/v1/access-controllers/doors/{door['id']}", json={"verify_mode": 7}).status_code == 400
