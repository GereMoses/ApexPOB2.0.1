"""
Site mobilisation (replaces the HR onboarding that duplicated SeamlessHR): the checklist is
read from the records, so nothing can be ticked while untrue; HSE confirms induction / PPE;
mobilising with items outstanding needs a reason and keeps what was outstanding.
"""
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import needs_db


def _client(h):
    from app.main import app
    return TestClient(app, headers=h)


@needs_db
def test_not_ready_person_needs_a_reason_and_is_not_put_on_board(db, make_person, superuser_headers):
    c = _client(superuser_headers)
    p = make_person("Mob Blank")
    day = str(date.today() + timedelta(days=5))
    r = c.post("/api/v1/mobilisation", json={"personnel_ids": [p["id"]], "mobilise_date": day})
    assert r.status_code == 200 and len(r.json()["created"]) == 1, r.text
    mid = r.json()["created"][0]
    again = c.post("/api/v1/mobilisation", json={"personnel_ids": [p["id"]], "mobilise_date": day}).json()
    assert again["created"] == [] and again["skipped"][0]["reason"] == "already being prepared"
    v = c.get(f"/api/v1/mobilisation/{mid}").json()
    assert v["ready"] is False
    for label in ("Medical fitness", "Access card", "Emergency contact (next of kin)", "Site safety induction given", "PPE issued"):
        assert label in v["blocking"]
    assert c.post(f"/api/v1/mobilisation/{mid}/check", json={"item": "medical", "done": True}).status_code == 400
    r = c.post(f"/api/v1/mobilisation/{mid}/mobilise", json={})
    assert r.status_code == 409 and "Medical fitness" in r.json()["detail"]
    r = c.post(f"/api/v1/mobilisation/{mid}/mobilise", json={"override_reason": "Emergency call-out, medical tomorrow"})
    assert r.status_code == 200 and r.json()["status"] == "MOBILISED"
    row = db.execute(text("SELECT override_reason, outstanding FROM site_mobilisation WHERE id = :i"), {"i": mid}).first()
    assert row.override_reason.startswith("Emergency") and "Medical fitness" in row.outstanding
    assert db.execute(text("SELECT is_onboard FROM personnel WHERE id = :i"), {"i": p["id"]}).scalar() is False
    assert c.delete(f"/api/v1/mobilisation/{mid}").status_code == 400          # stays on record


@needs_db
def test_ready_when_records_are_in_order_and_hse_confirms(db, make_person, superuser_headers):
    c = _client(superuser_headers)
    p = make_person("Mob Ready")
    db.execute(text("""UPDATE personnel SET medical_fitness_date = :m, card_number = 77123456, phone = '+2348000000001',
                       emergency_contact_name = 'Kin', emergency_contact_phone = '+2348000000002' WHERE id = :i"""),
               {"m": date.today() + timedelta(days=200), "i": p["id"]})
    db.execute(text("""INSERT INTO controller_user (controller_id, pin, emp_code, card_no, state)
                       SELECT id, '5550001', :c, '77123456', 'loaded' FROM access_controllers"""), {"c": p["emp_code"]})
    db.commit()
    mid = c.post("/api/v1/mobilisation", json={"personnel_ids": [p["id"]],
                                               "mobilise_date": str(date.today() + timedelta(days=3))}).json()["created"][0]
    v = c.get(f"/api/v1/mobilisation/{mid}").json()
    assert set(v["blocking"]) == {"Site safety induction given", "PPE issued"}, v["blocking"]
    c.post(f"/api/v1/mobilisation/{mid}/check", json={"item": "induction", "done": True})
    v = c.post(f"/api/v1/mobilisation/{mid}/check", json={"item": "ppe", "done": True, "note": "Coverall, boots"}).json()
    assert v["ready"] is True and "Coverall" in next(i for i in v["items"] if i["code"] == "ppe")["detail"]
    certs = next(i for i in v["items"] if i["code"] == "certificates")
    assert certs["state"] == "warn" and "No certificates" in certs["detail"]      # a medical alone isn't certificates
    # medical lapsing before the date breaks readiness again
    db.execute(text("UPDATE personnel SET medical_fitness_date = :m WHERE id = :i"), {"m": date.today() + timedelta(days=1), "i": p["id"]})
    db.commit()
    assert c.get(f"/api/v1/mobilisation/{mid}").json()["blocking"] == ["Medical fitness"]
    db.execute(text("UPDATE personnel SET medical_fitness_date = :m WHERE id = :i"), {"m": date.today() + timedelta(days=200), "i": p["id"]})
    db.commit()
    r = c.post(f"/api/v1/mobilisation/{mid}/mobilise", json={})
    assert r.status_code == 200 and r.json()["status"] == "MOBILISED"
    stats = c.get("/api/v1/mobilisation").json()["stats"]
    assert stats["mobilised"] >= 1
    db.execute(text("DELETE FROM controller_user WHERE pin = '5550001'"))
    db.commit()
