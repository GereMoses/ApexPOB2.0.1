"""
Go-live safety regression suite — POB, zones, attendance, transport, land journeys.

Runs against a THROWAWAY database (schema only, no data) given in TEST_DATABASE_URL.
scripts/run_safety_tests.sh creates one from the live schema, runs this suite and
drops it. Without TEST_DATABASE_URL the database tests are skipped, so this can
never touch a real database by accident.
"""
import os
import uuid

import pytest

_TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
if _TEST_DB:
    if "test" not in _TEST_DB.rsplit("/", 1)[-1]:
        raise RuntimeError("TEST_DATABASE_URL must point at a database whose name contains 'test'")
    # Must be set before anything imports app.core.database (it binds at import).
    os.environ["DATABASE_URL"] = _TEST_DB

needs_db = pytest.mark.skipif(not _TEST_DB, reason="TEST_DATABASE_URL not set (use scripts/run_safety_tests.sh)")


@pytest.fixture
def db():
    from app.core.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def make_person(db):
    """Create a staff record (personnel + its ZKTeco mirror via trigger)."""
    from sqlalchemy import text

    def _make(name="Test Person", onboard=False, attendance_id=None):
        code = "T" + uuid.uuid4().hex[:8].upper()
        first, _, last = name.partition(" ")
        pid = db.execute(text("""
            INSERT INTO personnel (emp_code, first_name, last_name, full_name, is_active,
                                   is_onboard, is_pob, attendance_id, status)
            VALUES (:c, :f, :l, :n, TRUE, :ob, :ob, :aid, 'ACTIVE') RETURNING id
        """), {"c": code, "f": first, "l": last or first, "n": name, "ob": onboard,
               "aid": attendance_id}).scalar()
        db.commit()
        return {"id": pid, "emp_code": code}
    return _make


@pytest.fixture
def make_zone(db):
    from sqlalchemy import text

    def _make(name=None, parent=None, boundary=False):
        name = name or "Z" + uuid.uuid4().hex[:6]
        zid = db.execute(text("""
            INSERT INTO zones (name, code, zone_type, status, parent_zone_id, is_site_boundary)
            VALUES (:n, :c, 'WORK_AREA', 'active', :p, :b) RETURNING id
        """), {"n": name, "c": uuid.uuid4().hex[:10].upper(), "p": parent, "b": boundary}).scalar()
        db.commit()
        return zid
    return _make


def person_state(db, emp_code):
    from sqlalchemy import text
    r = db.execute(text(
        "SELECT p.is_onboard, p.current_zone_id FROM personnel p WHERE emp_code = :c"
    ), {"c": emp_code}).fetchone()
    return bool(r[0]), r[1]
