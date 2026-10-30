"""
Visitor module (Oct 2026 deep check):
  * QR check-in works (the gate sent qr_code, which the server did not accept)
  * only an APPROVED pass for TODAY checks in; a used pass cannot be re-approved
  * the visitor type's safety induction is enforced; a card already held is refused
  * host is asked to approve and told when the visitor arrives; the visitor gets the
    QR pass by email (the old mailer read env SMTP and never sent)
  * a visitor arriving during a muster is added to it; leaving marks them left site
  * overstay is flagged once and the host told (the job was never scheduled)
  * the blacklist matches phone / email, not only the ID number
  * visitor cards go onto the door panels and survive the nightly sync until check-out
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import needs_db


@pytest.fixture
def sent(monkeypatch):
    out = []
    import app.services.notify_dispatch as nd
    import app.services.notify_email as ne
    monkeypatch.setattr(nd, "dispatch_background",
                        lambda st, sid, people, subj, msg, ch=None, include_responders=True:
                        out.append(dict(kind=st, id=sid, to=[p.get("name") for p in people], msg=msg)) or {})
    monkeypatch.setattr(ne, "send_email", lambda to, subj, body, text_=None, attachments=None, **k:
                        out.append(dict(kind="email", to=to, subject=subj, attachments=attachments)) or {"sent": 1})
    import types
    import app.services.visitor_access as va

    class Inline:                     # run the visitor helper's background work inline
        def __init__(self, target=None, daemon=None, **k): self.t = target
        def start(self): self.t()
    monkeypatch.setattr(va, "threading", types.SimpleNamespace(Thread=Inline))
    return out


def _c(h):
    from app.main import app
    return TestClient(app, headers=h)


def _host(db, make_person):
    p = make_person("Hilda Host")
    db.execute(text("UPDATE personnel SET phone = '08030002222' WHERE id = :i"), {"i": p["id"]})
    db.commit()
    return db.execute(text("SELECT id FROM personnel_employee WHERE emp_code = :c"), {"c": p["emp_code"]}).scalar()


def _today():
    from app.services.visitor_access import _site_today
    return _site_today()


def _prereg(c, host, **kw):
    body = {"host_emp_id": host, "visit_date": str(kw.pop("day", _today())), "purpose": "E2E test",
            "visitor_data": {"full_name": kw.pop("name", "Vera Visitor " + uuid.uuid4().hex[:4]),
                             "email": "vera@example.com", "phone": kw.pop("phone", "0803" + str(uuid.uuid4().int)[:7]),
                             "company": "Acme", "visitor_type_id": kw.pop("type_id", None)}}
    r = c.post("/api/visitor/pre-register/", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]


@needs_db
def test_pre_registration_to_qr_check_in_end_to_end(db, make_person, superuser_headers, sent):
    c = _c(superuser_headers)
    host = _host(db, make_person)
    t = c.post("/api/visitor/types/", json={"type_name": "Contractor " + uuid.uuid4().hex[:4],
                                           "safety_induction_required": True}).json()["data"]
    pr = _prereg(c, host, type_id=t["id"])
    assert any(s["kind"] == "visitor_request" and "Hilda Host" in s["to"] for s in sent)        # host asked
    # not approved yet → cannot check in
    r = c.post("/api/visitor/check-in/", json={"qr_code": pr["qr_code"]})
    assert r.status_code == 400 and "approval" in r.json()["detail"]
    assert c.post(f"/api/visitor/pre-register/{pr['id']}/approve", json={"status": 1}).status_code == 200
    mail = [s for s in sent if s["kind"] == "email"]
    assert mail and mail[-1]["to"] == "vera@example.com" and mail[-1]["attachments"][0][0] == "visitor-pass.png"
    # induction required
    r = c.post("/api/visitor/check-in/", json={"qr_code": pr["qr_code"]})
    assert r.status_code == 400 and "induction" in r.json()["detail"]
    # card held by a staff member
    staff = make_person()
    db.execute(text("UPDATE personnel SET card_number = '777001' WHERE id = :i"), {"i": staff["id"]})
    db.commit()
    r = c.post("/api/visitor/check-in/", json={"qr_code": pr["qr_code"], "induction_done": True, "card_no": "777001"})
    assert r.status_code == 400 and "already held" in r.json()["detail"]
    r = c.post("/api/visitor/check-in/", json={"qr_code": pr["qr_code"], "induction_done": True, "card_no": "777002"})
    assert r.status_code == 200, r.text
    assert any(s["kind"] == "visitor_arrived" and "Hilda Host" in s["to"] for s in sent)         # host told
    # a used pass cannot be approved again
    assert c.post(f"/api/visitor/pre-register/{pr['id']}/approve", json={"status": 1}).status_code == 400
    assert c.post("/api/visitor/check-out/", json={"card_no": "777002"}).status_code == 200


@needs_db
def test_wrong_day_and_rejected_passes_do_not_check_in(db, make_person, superuser_headers, sent):
    c = _c(superuser_headers)
    host = _host(db, make_person)
    pr = _prereg(c, host, day=_today() + timedelta(days=2))
    c.post(f"/api/visitor/pre-register/{pr['id']}/approve", json={"status": 1})
    r = c.post("/api/visitor/check-in/", json={"qr_code": pr["qr_code"]})
    assert r.status_code == 400 and "booked for" in r.json()["detail"]
    pr = _prereg(c, host)
    c.post(f"/api/visitor/pre-register/{pr['id']}/approve", json={"status": 2, "note": "no"})
    r = c.post("/api/visitor/check-in/", json={"qr_code": pr["qr_code"]})
    assert r.status_code == 400 and "rejected" in r.json()["detail"]


@needs_db
def test_visitor_arriving_during_muster_is_added_and_leaving_marks_left_site(db, make_person, superuser_headers, sent):
    c = _c(superuser_headers)
    host = _host(db, make_person)
    ev = db.execute(text("INSERT INTO mustering_event (event_type, start_time, status, total_expected, total_missing, total_safe) "
                         "VALUES (1, now(), 0, 0, 0, 0) RETURNING id")).scalar()
    db.commit()
    try:
        r = c.post("/api/visitor/check-in/", json={"visitor_data": {"full_name": "Walter Walkin"}, "host_emp_id": host})
        assert r.status_code == 200, r.text
        vid = r.json()["data"]["id"]
        row = db.execute(text("SELECT status FROM mustering_log WHERE event_id = :e AND emp_code = :c"),
                         {"e": ev, "c": f"VIS-{vid}"}).first()
        assert row and row.status == 0                                   # on the list, still to report
        code = db.execute(text("SELECT v.visitor_code FROM vis_visit_log l JOIN vis_visitor v ON v.id = l.visitor_id "
                               "WHERE l.id = :i"), {"i": vid}).scalar()
        assert c.post("/api/visitor/check-out/", json={"visitor_code": code}).status_code == 200
        db.expire_all()
        assert db.execute(text("SELECT status FROM mustering_log WHERE event_id = :e AND emp_code = :c"),
                          {"e": ev, "c": f"VIS-{vid}"}).scalar() == 3   # left site
    finally:
        db.execute(text("UPDATE mustering_event SET status = 1 WHERE id = :e"), {"e": ev})
        db.commit()


@needs_db
def test_overstay_flagged_once_and_host_told_and_can_still_check_out(db, make_person, superuser_headers, sent):
    from app.services.mustering_celery_tasks import visitor_overstay_check
    c = _c(superuser_headers)
    host = _host(db, make_person)
    r = c.post("/api/visitor/check-in/", json={"visitor_data": {"full_name": "Olga Overstay"}, "host_emp_id": host})
    vid = r.json()["data"]["id"]
    db.execute(text("UPDATE vis_visit_log SET check_in_time = now() - interval '9 hours' WHERE id = :i"), {"i": vid})
    db.commit()
    visitor_overstay_check()
    visitor_overstay_check()
    assert len([s for s in sent if s["kind"] == "visitor_overstay" and s["id"] == vid]) == 1
    db.expire_all()
    assert db.execute(text("SELECT status FROM vis_visit_log WHERE id = :i"), {"i": vid}).scalar() == 2
    assert c.post(f"/api/visitor/check-out/{vid}/force/").status_code == 200      # overstayers can leave


@needs_db
def test_blacklist_matches_phone_not_only_id(db, make_person, superuser_headers, sent):
    c = _c(superuser_headers)
    host = _host(db, make_person)
    phone = "0809" + str(uuid.uuid4().int)[:7]
    assert c.post("/api/visitor/blacklist/", json={"id_no": "X" + uuid.uuid4().hex[:6], "phone": phone,
                                                  "reason": "E2E"}).status_code in (200, 201)
    r = c.post("/api/visitor/check-in/", json={"visitor_data": {"full_name": "Bad Actor", "phone": phone,
                                                                "id_no": "DIFFERENT1"}, "host_emp_id": host})
    assert r.status_code == 400 and "blacklisted" in r.json()["detail"].lower()


@needs_db
def test_visitor_card_on_panels_until_check_out(db, make_person, superuser_headers, sent, monkeypatch):
    import app.services.zkteco.c3_zkaccess as z
    pushed = []
    monkeypatch.setattr(z, "enroll_users", lambda ip, users, door_nos=None, **k:
                        pushed.append((ip, [(u["pin"], u.get("card_no"), u.get("expire")) for u in users], door_nos))
                        or {"success": True, "pushed": len(users), "failed": []})
    from app.services import panel_sync
    from app.models.access_controller import AccessController
    c = _c(superuser_headers)
    ip = f"10.4.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    cid = c.post("/api/v1/access-controllers", json={"name": "Gate panel V", "ip_address": ip, "model": "C3-200",
                                                     "door_count": 2}).json()["id"]
    secure = c.get(f"/api/v1/access-controllers/{cid}/doors").json()[1]["id"]
    c.put(f"/api/v1/access-controllers/doors/{secure}", json={"emergency_action": 1})
    host = _host(db, make_person)
    card = str(880000 + uuid.uuid4().int % 9999)
    vid = c.post("/api/visitor/check-in/", json={"visitor_data": {"full_name": "Carla Card"}, "host_emp_id": host,
                                                 "card_no": card}).json()["data"]["id"]
    pin = str(900_000_000 + vid)
    mine = [p for p in pushed if p[0] == ip]
    assert mine and (pin, card) == mine[-1][1][0][:2] and mine[-1][2] == [1]      # loaded, secure door 2 excluded
    ctrl = db.query(AccessController).filter(AccessController.id == cid).first()
    pushed.clear()
    panel_sync.sync_controller(db, ctrl)                                           # nightly: still on site → kept
    assert any(pin in [u[0] for u in p[1]] and p[2] == [1] for p in pushed if p[0] == ip)
    code = db.execute(text("SELECT v.visitor_code FROM vis_visit_log l JOIN vis_visitor v ON v.id = l.visitor_id "
                           "WHERE l.id = :i"), {"i": vid}).scalar()
    pushed.clear()
    c.post("/api/visitor/check-out/", json={"visitor_code": code})
    removed = [p for p in pushed if p[0] == ip and p[2] == []]
    assert removed and removed[0][1][0][0] == pin                                   # card expired on the panel
