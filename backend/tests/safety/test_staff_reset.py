"""Global admin: remove all staff and pull them back from SeamlessHR."""
import asyncio
import uuid

import pytest
from sqlalchemy import text

from .conftest import needs_db


@pytest.fixture
def seamless(monkeypatch, db):
    """A fake SeamlessHR holding the given employees (emp_code, name)."""
    import app.services.seamlesshr_service as sh
    import app.services.staff_reset as sr
    state = {"staff": [], "up": True}
    monkeypatch.setattr(sr, "seamlesshr_answers", lambda db: (state["up"], "ok" if state["up"] else "HTTP 400"))
    monkeypatch.setattr(sh, "get_config", lambda db: {"options": {"attendance_id_rule": "manual"}})

    async def pull_employees(db, triggered_by="manual"):
        if not state["up"]:
            return {"error": "HTTP 400"}
        for code, name in state["staff"]:
            db.execute(text("""INSERT INTO personnel (emp_code, first_name, last_name, full_name, is_active, status, hr_source)
                               VALUES (:c, :n, 'X', :n, TRUE, 'ACTIVE', 'SEAMLESSHR') ON CONFLICT (emp_code) DO NOTHING"""),
                       {"c": code, "n": name})
        db.commit()
        return {"created": len(state["staff"]), "updated": 0, "total": len(state["staff"])}

    async def pull_leave(db, triggered_by="manual"):
        return {"on_leave": 0}
    monkeypatch.setattr(sh, "pull_employees", pull_employees)
    monkeypatch.setattr(sh, "pull_leave", pull_leave)
    for ev in db.execute(text("SELECT id FROM mustering_event WHERE status = 0")).fetchall():
        db.execute(text("UPDATE mustering_event SET status = 1 WHERE id = :i"), {"i": ev[0]})
    db.commit()
    return state


def _job(db, mode, repopulate=True):
    from app.services.staff_reset import run_reset
    jid = db.execute(text("INSERT INTO staff_reset_job (started_by, mode, repopulate) VALUES ('test', :m, :r) RETURNING id"),
                     {"m": mode, "r": repopulate}).scalar()
    db.commit()
    asyncio.run(run_reset(jid, mode, repopulate))
    db.expire_all()
    return dict(db.execute(text("SELECT * FROM staff_reset_job WHERE id = :i"), {"i": jid}).mappings().first())


def _person(db, code, att_id, card, onboard=True):
    db.execute(text("""INSERT INTO personnel (emp_code, first_name, last_name, full_name, is_active, status, hr_source,
                                              attendance_id, card_number, is_onboard, is_pob)
                       VALUES (:c, 'Ada', 'X', 'Ada X', TRUE, 'ACTIVE', 'SEAMLESSHR', :a, :card, :o, :o)"""),
               {"c": code, "a": att_id, "card": card, "o": onboard})
    db.commit()
    mirror = db.execute(text("SELECT id FROM personnel_employee WHERE emp_code = :c"), {"c": code}).scalar()
    db.execute(text("INSERT INTO att_report (emp_id, att_date, att_status) VALUES (:e, CURRENT_DATE - 1, 0)"), {"e": mirror})
    db.commit()
    return mirror


@needs_db
def test_keep_history_brings_staff_back_with_cards_ids_pob_and_history(db, seamless):
    code = f"MARC {str(uuid.uuid4().int)[:5]}"
    att, card = str(uuid.uuid4().int)[:7], int(str(uuid.uuid4().int)[:9])
    mirror = _person(db, code, att, card)
    seamless["staff"] = [(code, "Ada")]
    job = _job(db, "keep_history")
    assert job["state"] == "done", job["error"]
    p = db.execute(text("SELECT attendance_id, card_number, is_onboard FROM personnel WHERE emp_code = :c"), {"c": code}).fetchone()
    assert p == (att, card, True)                                                  # ApexPOB-owned fields restored
    assert db.execute(text("SELECT id, status FROM personnel_employee WHERE emp_code = :c"), {"c": code}).fetchone() == (mirror, 0)
    assert db.execute(text("SELECT count(*) FROM att_report WHERE emp_id = :e"), {"e": mirror}).scalar() == 1   # history kept + linked
    assert job["backup_schema"] and db.execute(text(
        f'SELECT count(*) FROM "{job["backup_schema"]}".personnel WHERE emp_code = :c'), {"c": code}).scalar() == 1


@needs_db
def test_everything_mode_is_a_clean_start(db, seamless):
    code = f"MARC {str(uuid.uuid4().int)[:5]}"
    _person(db, code, str(uuid.uuid4().int)[:7], int(str(uuid.uuid4().int)[:9]))
    seamless["staff"] = [(code, "Ada")]
    job = _job(db, "everything")
    assert job["state"] == "done", job["error"]
    assert db.execute(text("SELECT attendance_id, card_number, is_onboard FROM personnel WHERE emp_code = :c"),
                      {"c": code}).fetchone() == (None, None, False)
    assert db.execute(text("SELECT count(*) FROM att_report")).scalar() == 0


@needs_db
def test_failed_pull_reports_clearly(db, seamless):
    code = f"MARC {str(uuid.uuid4().int)[:5]}"
    _person(db, code, None, None)
    seamless["up"] = True
    import app.services.seamlesshr_service as sh

    async def broken(db, triggered_by="manual"):
        return {"error": "HTTP 400"}
    sh.pull_employees = broken
    job = _job(db, "keep_history")
    assert job["state"] == "failed" and "Pull staff & update readers" in job["error"] and job["backup_schema"] in job["error"]


@needs_db
def test_refused_when_seamlesshr_down_or_muster_running_and_only_global_admin(db, seamless, superuser_headers):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.staff_reset import preflight
    seamless["up"] = False
    assert not preflight(db, "keep_history", True)["ok"]
    seamless["up"] = True
    ev = db.execute(text("INSERT INTO mustering_event (event_type, start_time, status, total_expected) VALUES (1, NOW(), 0, 0) RETURNING id")).scalar()
    db.commit()
    try:
        assert "muster" in " ".join(preflight(db, "keep_history", True)["problems"]).lower()
    finally:
        db.execute(text("UPDATE mustering_event SET status = 1 WHERE id = :i"), {"i": ev})
        db.commit()
    # a superuser who is not the global admin may not do it
    r = TestClient(app).post("/api/v1/hr-integration/staff-reset", headers=superuser_headers,
                             json={"mode": "keep_history", "confirm": "DELETE ALL STAFF"})
    assert r.status_code == 403
