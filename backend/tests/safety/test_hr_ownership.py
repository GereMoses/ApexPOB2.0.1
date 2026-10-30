"""SeamlessHR owns job roles: titles staff carry become Positions (marked SEAMLESSHR)
whose name/code cannot be changed or deleted in ApexPOB."""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import needs_db


@needs_db
def test_seamlesshr_titles_become_read_only_positions(db, make_person, superuser_headers):
    from app.main import app
    from app.services.seamlesshr_service import sync_positions_from_staff
    title = "Rope Access Tech " + uuid.uuid4().hex[:4]
    p = make_person()
    db.execute(text("UPDATE personnel SET hr_source = 'SEAMLESSHR', position = :t WHERE id = :i"), {"t": title, "i": p["id"]})
    db.commit()
    assert sync_positions_from_staff(db) >= 1
    assert sync_positions_from_staff(db) == 0                                   # idempotent
    pid = db.execute(text("SELECT id FROM positions WHERE position_name = :t AND hr_source = 'SEAMLESSHR'"), {"t": title}).scalar()
    c = TestClient(app, headers=superuser_headers)
    r = c.put(f"/api/v1/positions/{pid}", json={"position_name": "Renamed"})
    assert r.status_code == 403 and "SeamlessHR" in r.json()["detail"]
    assert c.put(f"/api/v1/positions/{pid}", json={"is_safety_critical": True}).status_code == 200   # ApexPOB detail
    assert c.delete(f"/api/v1/positions/{pid}").status_code == 403
