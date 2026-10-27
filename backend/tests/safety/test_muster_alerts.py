"""
Mustering + alerting regressions (Oct 2026 deep dive):
  * the expected list never leaves out someone on board whose location is unknown
  * a person NOT on the roster scanning at the muster point grows "expected" and
    never hides a genuinely missing person by shrinking "missing"
  * alerts go to staff + response team, unconfigured channels are logged SKIPPED
  * WhatsApp (Meta Cloud API) sends the approved template with the alert text
"""
import uuid

import pytest
from sqlalchemy import text

from .conftest import needs_db


@pytest.fixture
def sent(monkeypatch):
    """Capture background alerts instead of queueing them to the live worker."""
    calls = []
    import app.services.notify_dispatch as nd

    def fake(source_type, source_id, people, subject, message, channels=None, include_responders=True):
        calls.append(dict(source_type=source_type, source_id=source_id, people=people, subject=subject,
                          message=message, channels=channels, responders=include_responders))
        return {"queued": len(people)}
    monkeypatch.setattr(nd, "dispatch_background", fake)
    return calls


def _muster_point(db, sn):
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose) VALUES (:sn, 'muster', 1, 'MUSTERING') "
                    "ON CONFLICT (sn) DO NOTHING"), {"sn": sn})
    zid = db.execute(text("""INSERT INTO zones (name, code, zone_type, status, reader_sn)
                             VALUES (:n, :c, 'MUSTER_POINT', 'active', :sn) RETURNING id"""),
                     {"n": "MP " + sn, "c": uuid.uuid4().hex[:10].upper(), "sn": sn}).scalar()
    db.commit()
    return zid


def _operational(db):
    return [r[0] for r in db.execute(text("SELECT id FROM zones WHERE zone_type IS DISTINCT FROM 'MUSTER_POINT'"))]


def _end(db, ev):
    from app.services.mustering_service import MusteringService
    try:
        MusteringService(db).end_mustering_event(ev, 1)
    except Exception:
        db.rollback()


def _set(db, emp_code, onboard, zone):
    db.execute(text("UPDATE personnel SET is_onboard = :o, is_pob = :o, current_zone_id = :z WHERE emp_code = :c"),
               {"o": onboard, "z": zone, "c": emp_code})
    db.commit()


@needs_db
def test_site_muster_is_the_pob_list(db, make_person, make_zone, sent):
    from app.services.mustering_service import MusteringService
    deck = make_zone()
    located, unlocated, ashore = make_person(), make_person(), make_person()
    _set(db, located["emp_code"], True, deck)
    _set(db, unlocated["emp_code"], True, None)        # on board, no reader has placed them
    _set(db, ashore["emp_code"], False, None)          # off rotation
    ev = MusteringService(db).start_mustering_event(_operational(db), 0, 1)["event_id"]
    try:
        codes = {r[0] for r in db.execute(text("SELECT emp_code FROM mustering_log WHERE event_id = :e"), {"e": ev})}
        assert located["emp_code"] in codes and unlocated["emp_code"] in codes
        assert ashore["emp_code"] not in codes
    finally:
        _end(db, ev)


@needs_db
def test_area_muster_keeps_unlocated_people(db, make_person, make_zone, sent):
    from app.services.mustering_service import MusteringService
    area, elsewhere = make_zone(), make_zone()
    inside, unknown, other = make_person(), make_person(), make_person()
    _set(db, inside["emp_code"], True, area)
    _set(db, unknown["emp_code"], True, None)
    _set(db, other["emp_code"], True, elsewhere)
    ev = MusteringService(db).start_mustering_event([area], 0, 1)["event_id"]
    try:
        codes = {r[0] for r in db.execute(text("SELECT emp_code FROM mustering_log WHERE event_id = :e"), {"e": ev})}
        assert inside["emp_code"] in codes and unknown["emp_code"] in codes
        assert other["emp_code"] not in codes
    finally:
        _end(db, ev)


@needs_db
def test_unexpected_person_at_muster_point_does_not_hide_a_missing_one(db, make_person, make_zone, sent):
    from app.services.mustering_service import MusteringService
    area = make_zone()
    mp = _muster_point(db, "MP" + uuid.uuid4().hex[:8].upper())
    sn = db.execute(text("SELECT reader_sn FROM zones WHERE id = :z"), {"z": mp}).scalar()
    missing = make_person()
    _set(db, missing["emp_code"], True, area)
    walk_in = make_person()                               # not on board, not on the roster
    svc = MusteringService(db)
    ev = svc.start_mustering_event([area], 0, 1, muster_zone_ids=[mp])["event_id"]
    try:
        before = db.execute(text("SELECT total_expected, total_missing FROM mustering_event WHERE id = :e"), {"e": ev}).fetchone()
        svc.process_mustering_punch(walk_in["emp_code"], sn)
        after = db.execute(text("SELECT total_expected, total_missing, total_safe FROM mustering_event WHERE id = :e"), {"e": ev}).fetchone()
        assert after.total_missing == before.total_missing          # the real missing person still shows
        assert after.total_expected == before.total_expected + 1 and after.total_safe == 1
    finally:
        _end(db, ev)


@needs_db
def test_muster_alerts_staff_team_and_all_clear(db, make_person, make_zone, sent):
    from app.services.mustering_service import MusteringService
    area = make_zone()
    p = make_person()
    _set(db, p["emp_code"], True, area)
    svc = MusteringService(db)
    ev = svc.start_mustering_event([area], 2, 1, notify_whatsapp=True, notify_email=True)["event_id"]
    staff = [c for c in sent if c["source_type"] == "muster" and not c["responders"]]
    team = [c for c in sent if c["source_type"] == "muster" and c["responders"]]
    assert staff and team and staff[0]["channels"] == ["whatsapp", "email"]
    assert any(x["name"] for x in staff[0]["people"]) and "FIRE MUSTER" in staff[0]["message"]
    svc.end_mustering_event(ev, 1)
    clear = [c for c in sent if c["source_type"] == "muster_all_clear"]
    assert len(clear) == 2 and "ALL CLEAR" in clear[0]["message"] and "Safe 0 / expected" in clear[1]["message"]


@needs_db
def test_dispatch_logs_skipped_channels_and_includes_responders(db, monkeypatch):
    import app.services.notify_dispatch as nd
    from app.services.whatsapp_config import save_responders
    monkeypatch.setattr(nd, "configured_channels", lambda: {"email": False, "whatsapp": False, "sms": False})
    save_responders(db, [{"name": "OIM", "email": "oim@example.test", "phone": "08031234567"}])
    sid = int(uuid.uuid4().int % 10**9)
    out = nd.dispatch("test", sid, [{"name": "A", "email": "a@example.test", "phone": "08030000000"}],
                      "s", "m", ["whatsapp", "email"])
    assert out["whatsapp"]["skipped"] == 2 and out["email"]["skipped"] == 2
    rows = db.execute(text("SELECT channel, address, status FROM notify_delivery WHERE source_id = :s"), {"s": sid}).fetchall()
    assert {r.address for r in rows} == {"08030000000", "08031234567", "a@example.test", "oim@example.test"}
    assert {r.status for r in rows} == {"SKIPPED"}
    save_responders(db, [])


def test_meta_whatsapp_sends_template_with_alert_text(monkeypatch):
    import app.services.notify_whatsapp as nw
    cfg = {"enabled": True, "provider": "meta", "country_code": "234", "meta_phone_number_id": "111",
           "meta_access_token": "tok", "meta_template": "pob_alert", "meta_template_lang": "en", "meta_api_version": "v21.0"}
    monkeypatch.setattr(nw, "_db_settings", lambda: cfg)
    posted = []

    class R:
        ok, content, status_code = True, b"x", 200
        def json(self): return {"messages": [{"id": "wamid"}]}

    import requests
    monkeypatch.setattr(requests, "post", lambda url, json=None, headers=None, timeout=None: posted.append((url, json, headers)) or R())
    res = nw.send_whatsapp(["08031112222", "+2348031112222", "08035556666"], "FIRE MUSTER:\nGo to MP-A")
    assert res["sent"] == 2 and len(posted) == 2                                   # duplicates collapsed
    url, body, headers = posted[0]
    assert url.endswith("/v21.0/111/messages") and headers["Authorization"] == "Bearer tok"
    assert body["to"].startswith("234") and body["template"]["name"] == "pob_alert"
    assert body["template"]["components"][0]["parameters"][0]["text"] == "FIRE MUSTER: · Go to MP-A"


def _visitor_on_site(db, name="Ada Visitor"):
    vid = db.execute(text("INSERT INTO vis_visitor (visitor_code, full_name, phone) VALUES (:c, :n, '08039990000') RETURNING id"),
                     {"c": "V" + uuid.uuid4().hex[:8], "n": name}).scalar()
    lid = db.execute(text("INSERT INTO vis_visit_log (visitor_id, check_in_time, status) VALUES (:v, NOW(), 0) RETURNING id"),
                     {"v": vid}).scalar()
    db.commit()
    return lid


@needs_db
def test_visitors_on_site_are_on_the_muster_list_and_can_be_marked(db, make_zone, sent):
    from app.services.mustering_service import MusteringService
    area = make_zone()
    visit = _visitor_on_site(db)
    svc = MusteringService(db)
    ev = svc.start_mustering_event([area], 0, 1, notify_whatsapp=True)["event_id"]
    try:
        code = f"VIS-{visit}"
        st = db.execute(text("SELECT status, emp_name FROM mustering_log WHERE event_id = :e AND emp_code = :c"),
                        {"e": ev, "c": code}).fetchone()
        assert st is not None and st.status == 0 and "visitor" in st.emp_name
        staff = [c for c in sent if c["source_type"] == "muster" and not c["responders"]][0]
        assert any(p.get("kind") == "visitor" and p["phone"] == "08039990000" for p in staff["people"])
        svc.mark_person_status(ev, code, 1, 1)
        assert db.execute(text("SELECT mustering_status FROM vis_visit_log WHERE id = :i"), {"i": visit}).scalar() == 1
        assert svc.get_event_headcount(ev)["total_visitors"] >= 1
    finally:
        db.execute(text("UPDATE vis_visit_log SET status = 1, check_out_time = NOW() WHERE id = :i"), {"i": visit})
        db.commit()
        _end(db, ev)


@needs_db
def test_gate_exit_during_muster_marks_left_site(db, make_person, make_zone, sent):
    from app.api.adms_protocol import _mark_onboard
    from app.services.mustering_service import MusteringService
    area = make_zone()
    p = make_person()
    _set(db, p["emp_code"], True, area)
    svc = MusteringService(db)
    ev = svc.start_mustering_event([area], 0, 1)["event_id"]
    try:
        before = db.execute(text("SELECT total_missing FROM mustering_event WHERE id = :e"), {"e": ev}).scalar()
        _mark_onboard(p["emp_code"], False, db)
        assert db.execute(text("SELECT status FROM mustering_log WHERE event_id = :e AND emp_code = :c"),
                          {"e": ev, "c": p["emp_code"]}).scalar() == 3
        assert db.execute(text("SELECT total_missing FROM mustering_event WHERE id = :e"), {"e": ev}).scalar() == before - 1
        hc = svc.get_event_headcount(ev)
        assert hc["total_left_site"] == 1 and hc["total_accounted"] >= 1
    finally:
        _end(db, ev)


@needs_db
def test_any_reader_at_a_muster_point_counts_people_safe(db, make_person, make_zone, sent):
    from app.api.adms_protocol import handle_attlog
    from app.services.mustering_service import MusteringService
    from datetime import datetime, timezone
    area = make_zone()
    sn = "AT" + uuid.uuid4().hex[:8].upper()
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose) VALUES (:sn, 'gate F18', 1, 'ATTENDANCE')"), {"sn": sn})
    mp = db.execute(text("INSERT INTO zones (name, code, zone_type, status, reader_sn) VALUES (:n, :c, 'MUSTER_POINT', 'active', :sn) RETURNING id"),
                    {"n": "MP " + sn, "c": uuid.uuid4().hex[:10].upper(), "sn": sn}).scalar()
    db.commit()
    pin = str(uuid.uuid4().int)[:8]
    p = make_person(attendance_id=pin)
    _set(db, p["emp_code"], True, area)
    ev = MusteringService(db).start_mustering_event([area], 0, 1, muster_zone_ids=[mp])["event_id"]
    try:
        handle_attlog([{"PIN": pin, "Time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "Status": "0"}], sn, db)
        assert db.execute(text("SELECT status FROM mustering_log WHERE event_id = :e AND emp_code = :c"),
                          {"e": ev, "c": p["emp_code"]}).scalar() == 1
    finally:
        _end(db, ev)


@needs_db
def test_printable_muster_list_has_everyone_on_board_and_visitors(db, make_person, sent):
    from app.services.muster_list import build_pdf, muster_roster
    p = make_person(name="Paper Person")
    _set(db, p["emp_code"], True, None)
    visit = _visitor_on_site(db, "Paper Visitor")
    try:
        staff, visitors = muster_roster(db)
        assert p["emp_code"] in {s["emp_code"] for s in staff}
        assert f"VIS-{visit}" in {v["emp_code"] for v in visitors}
        pdf = build_pdf(db)
        assert pdf[:4] == b"%PDF" and len(pdf) > 1500
    finally:
        db.execute(text("UPDATE vis_visit_log SET status = 1, check_out_time = NOW() WHERE id = :i"), {"i": visit})
        db.commit()


@needs_db
def test_one_tap_site_muster_alerts_on_configured_channels(db, make_person, make_zone, sent, monkeypatch):
    import app.services.notify_dispatch as nd
    from app.services.mustering_service import MusteringService
    monkeypatch.setattr(nd, "configured_channels", lambda: {"email": True, "whatsapp": True, "sms": False})
    make_zone()
    p = make_person()
    _set(db, p["emp_code"], True, None)
    res = MusteringService(db).start_site_muster("mandown", 1)
    try:
        assert res["total_expected"] >= 1
        assert db.execute(text("SELECT event_type, notify_channels FROM mustering_event WHERE id = :e"),
                          {"e": res["event_id"]}).fetchone() == (4, ["whatsapp", "email"])
        assert any(c["source_type"] == "muster" for c in sent)
    finally:
        _end(db, res["event_id"])
