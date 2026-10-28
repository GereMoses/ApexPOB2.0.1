"""Devices module regressions (28 Oct 2026 review)."""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import needs_db


def _terminal(db, sn, mode="adms", purpose="ATTENDANCE"):
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose, connection_mode, ip_address) "
                    "VALUES (:s, :s, 1, :p, :m, '10.1.1.1') ON CONFLICT (sn) DO NOTHING"), {"s": sn, "m": mode, "p": purpose})
    db.commit()


@needs_db
def test_controller_ports_stay_out_of_device_list_and_heartbeat(db, superuser_headers):
    from app.main import app
    from app.services.zkteco.device_heartbeat import _db_get_adms_terminals
    port = "AC9-D1-" + uuid.uuid4().hex[:3].upper()
    real = "TA" + uuid.uuid4().hex[:8].upper()
    _terminal(db, port, mode="controller", purpose="MUSTERING")
    _terminal(db, real)
    r = TestClient(app).get("/api/device/terminals/", headers=superuser_headers, params={"limit": 500})
    body = r.json()
    rows = body.get("data", body) if isinstance(body, dict) else body
    sns = {d.get("sn") for d in rows}
    assert real in sns and port not in sns
    hb = {t[1] for t in _db_get_adms_terminals()}
    assert real in hb and port not in hb                     # never aged offline → no false muster-reader alarm


@needs_db
def test_push_users_sends_active_staff_only_without_blank_password(db, superuser_headers, make_person):
    from app.main import app
    sn = "TA" + uuid.uuid4().hex[:8].upper()
    _terminal(db, sn)
    pin_a, pin_b = str(uuid.uuid4().int)[:8], str(uuid.uuid4().int)[:8]
    active = make_person(attendance_id=pin_a)
    leaver = make_person(attendance_id=pin_b)
    db.execute(text("UPDATE personnel SET is_active = FALSE WHERE emp_code = :c"), {"c": leaver["emp_code"]})
    db.commit()
    r = TestClient(app).post("/iclock/cmd/push-users", headers=superuser_headers,
                             json={"sn": sn, "emp_codes": [active["emp_code"], leaver["emp_code"]]})
    assert r.status_code == 200, r.text
    cmds = [c[0] for c in db.execute(text("SELECT cmd_content FROM iclock_devcmd WHERE sn = :s"), {"s": sn}).fetchall()]
    assert any(f"PIN={pin_a}\t" in c for c in cmds) and not any(f"PIN={pin_b}\t" in c for c in cmds)
    assert not any("Passwd=" in c or "Card=\t" in c for c in cmds)


@needs_db
def test_enrollment_status_shows_leavers_as_inactive(db, superuser_headers, make_person):
    from app.main import app
    p = make_person()
    db.execute(text("UPDATE personnel SET is_active = FALSE, status = 'ACTIVE' WHERE emp_code = :c"), {"c": p["emp_code"]})
    db.commit()
    r = TestClient(app).get("/api/device/enrollment/status/", headers=superuser_headers)
    assert r.status_code == 200, r.text
    rows = r.json().get("data", r.json())
    rows = rows if isinstance(rows, list) else rows.get("employees", rows.get("items", []))
    row = [x for x in rows if x.get("emp_code") == p["emp_code"]]
    assert row and row[0]["status"] == "inactive"
