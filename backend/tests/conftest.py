"""
Test-wide guard: the suite only ever runs against a THROWAWAY database.

Many tests create zones, staff, terminals and shifts through the app's own database
connection. Run against the live stack, that would write test records into real
data. So the suite refuses to start unless TEST_DATABASE_URL names a database whose
name contains "test"; scripts/run_tests.sh builds one from the live schema (no data),
runs the suite inside the backend container and drops it.
"""
import os

import pytest

_TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
if _TEST_DB and "test" in _TEST_DB.rsplit("/", 1)[-1]:
    # Must happen before anything imports app.core.database (it binds at import).
    os.environ["DATABASE_URL"] = _TEST_DB
    # FastAPI's TestClient calls itself "testserver"; production's host check would
    # answer every request with 400, so tests expecting a rejection passed for the
    # wrong reason. Allowed only inside this throwaway test process.
    _hosts = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]
    if "testserver" not in _hosts:
        os.environ["ALLOWED_HOSTS"] = ",".join(_hosts + ["testserver"])


def _isolate_celery():
    """Never hand a task to the LIVE Celery worker. The test container shares the
    live Redis broker, so an alert queued by a test (dispatch_background → Celery)
    was picked up by the production worker and sent through the live WhatsApp phone
    (29 Oct 2026: made-up test numbers, nothing delivered). Tasks queued during
    tests are recorded here instead and never run."""
    from celery.app.task import Task
    from celery.result import EagerResult

    def _no_send(self, args=None, kwargs=None, **options):
        QUEUED_TASKS.append((self.name, args, kwargs))
        return EagerResult("test-not-sent", None, "PENDING")
    Task.apply_async = _no_send
    try:
        from celery import Celery
        Celery.send_task = lambda self, name, args=None, kwargs=None, **o: (
            QUEUED_TASKS.append((name, args, kwargs)) or EagerResult("test-not-sent", None, "PENDING"))
    except Exception:  # noqa: BLE001
        pass


QUEUED_TASKS = []


def pytest_configure(config):
    _isolate_celery()
    if not (_TEST_DB and "test" in _TEST_DB.rsplit("/", 1)[-1]):
        pytest.exit("Refusing to run: set TEST_DATABASE_URL to a throwaway *test* database "
                    "(use scripts/run_tests.sh). Running against the live database would "
                    "write test records into real data.", returncode=4)


@pytest.fixture
def superuser_headers():
    """Authorization header for a real superuser created in the throwaway database —
    so requests pass the real JWT + RBAC checks instead of mocking them away."""
    from datetime import timedelta
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO auth_user (username, email, password, is_active, is_superuser)
            VALUES ('test_super', 'test_super@example.test', '!unusable', TRUE, TRUE)
            ON CONFLICT (username) DO NOTHING
        """))
        db.commit()
    finally:
        db.close()
    token = create_access_token({"sub": "test_super"}, timedelta(minutes=15))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db_session():
    """A session on the throwaway test database (rolled back and closed after)."""
    from app.core.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
