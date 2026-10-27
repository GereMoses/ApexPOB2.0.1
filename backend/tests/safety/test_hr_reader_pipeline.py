"""SeamlessHR staff pull → Attendance IDs → readers (door panels + T&A terminals)."""
import asyncio
import uuid

import pytest
from sqlalchemy import text

from .conftest import needs_db


@pytest.fixture
def hr(monkeypatch):
    import app.services.seamlesshr_service as sh
    state = {"rule": "code_digits", "pulled": 0, "error": None}
    monkeypatch.setattr(sh, "get_config", lambda db: {"options": {"attendance_id_rule": state["rule"]}})

    async def pull_employees(db, triggered_by="manual"):
        state["pulled"] += 1
        return {"error": state["error"]} if state["error"] else {"created": 0, "updated": 0, "total": 0}

    async def pull_leave(db, triggered_by="manual"):
        return {"on_leave": 0}
    monkeypatch.setattr(sh, "pull_employees", pull_employees)
    monkeypatch.setattr(sh, "pull_leave", pull_leave)
    return state


def _hr_person(db, code):
    pid = db.execute(text("""INSERT INTO personnel (emp_code, first_name, last_name, full_name, is_active, status, hr_source)
                             VALUES (:c, 'Ada', 'Okafor', 'Ada Okafor', TRUE, 'ACTIVE', 'SEAMLESSHR') RETURNING id"""),
                     {"c": code}).scalar()
    db.commit()
    return pid


@needs_db
def test_code_digits_rule_sets_ids_and_updates_ta_terminals(db, hr):
    from app.services.hr_reader_pipeline import refresh_staff_and_readers
    n = str(uuid.uuid4().int)[:6].lstrip("0") or "7"
    code = f"MARC {n}"
    _hr_person(db, code)
    sn = "TA" + uuid.uuid4().hex[:8].upper()
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose, connection_mode) VALUES (:s, 'T&A', 1, 'ATTENDANCE', 'adms')"), {"s": sn})
    db.commit()
    out = asyncio.run(refresh_staff_and_readers(db))
    assert hr["pulled"] == 1 and out["attendance_ids"]["rule"] == "code_digits"
    assert db.execute(text("SELECT attendance_id FROM personnel WHERE emp_code = :c"), {"c": code}).scalar() == n
    cmds = [r[0] for r in db.execute(text("SELECT cmd_content FROM iclock_devcmd WHERE sn = :s AND cmd_content LIKE 'DATA UPDATE USERINFO%'"),
                                     {"s": sn}).fetchall()]
    assert any(f"PIN={n}\t" in c and "Ada Okafor" in c for c in cmds)   # reader gets the digits, not "MARC …"
    assert not any("PIN=MARC" in c for c in cmds)
    # leaver after the next pull → removed from the terminal
    db.execute(text("UPDATE personnel SET is_active = FALSE WHERE emp_code = :c"), {"c": code})
    db.commit()
    asyncio.run(refresh_staff_and_readers(db))
    assert db.execute(text("SELECT count(*) FROM iclock_devcmd WHERE sn = :s AND cmd_content = :c"),
                      {"s": sn, "c": f"DATA DELETE USERINFO PIN={n}"}).scalar() == 1


@needs_db
def test_failed_pull_never_touches_readers(db, hr, monkeypatch):
    import app.services.hr_reader_pipeline as p
    hr["error"] = "SeamlessHR unreachable"
    touched = []
    monkeypatch.setattr(p, "update_readers", lambda db: touched.append(1))
    out = asyncio.run(p.refresh_staff_and_readers(db))
    assert out["error"] and touched == []


@needs_db
def test_manual_rule_leaves_ids_alone(db, hr):
    from app.services.hr_reader_pipeline import refresh_staff_and_readers
    hr["rule"] = "manual"
    code = f"MARC {str(uuid.uuid4().int)[:5]}"
    _hr_person(db, code)
    asyncio.run(refresh_staff_and_readers(db))
    assert db.execute(text("SELECT attendance_id FROM personnel WHERE emp_code = :c"), {"c": code}).scalar() is None
