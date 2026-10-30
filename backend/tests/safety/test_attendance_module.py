"""
Attendance (Oct 2026 review):
  * an APPROVED manual log becomes a punch and the day is recalculated — it reaches the
    timesheet and the SeamlessHR records (approval used to change only the log status)
  * a scheduled person on approved leave / SeamlessHR leave is LEAVE, not ABSENT
  * a public holiday with no taps is not an absence
"""
import asyncio
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import needs_db

LAGOS = ZoneInfo("Africa/Lagos")
run = asyncio.run


def _scheduled_person(db, make_person):
    p = make_person(attendance_id=str(random.randint(10_000_000, 99_999_999)))
    shift = db.execute(text("INSERT INTO att_shift (name, start_time, end_time, work_days, is_active) "
                            "VALUES ('T 07-19', '07:00', '19:00', '1234567', TRUE) RETURNING id")).scalar()
    db.execute(text("INSERT INTO att_schedule (emp_code, shift_id, start_date, status) VALUES (:c, :s, CURRENT_DATE - 30, 'scheduled')"),
               {"c": p["emp_code"], "s": shift})
    db.commit()
    pe = db.execute(text("SELECT id FROM personnel_employee WHERE emp_code = :c"), {"c": p["emp_code"]}).scalar()
    return p, pe


def _status(db, pe, day):
    return db.execute(text("SELECT att_status, check_in, check_out, work_minutes FROM att_report WHERE emp_id = :e AND att_date = :d"),
                      {"e": pe, "d": day}).first()


@needs_db
def test_approved_manual_log_reaches_timesheet_and_seamlesshr(db, make_person, superuser_headers):
    from app.main import app
    from app.services.seamlesshr_service import _build_attendance_records
    p, pe = _scheduled_person(db, make_person)
    yday = (datetime.now(LAGOS) - timedelta(days=1)).date()
    c = TestClient(app, headers=superuser_headers)
    ids = []
    for h, state in ((7, 0), (19, 1)):
        t = datetime(yday.year, yday.month, yday.day, h, 0, tzinfo=LAGOS)
        r = c.post("/api/v1/attendance/manual-logs", json={"emp_id": pe, "punch_time": t.isoformat(),
                                                           "punch_state": state, "reason": "Reader was down"})
        assert r.status_code in (200, 201), r.text
        ids.append(db.execute(text("SELECT max(id) FROM att_manual_log WHERE emp_id = :e"), {"e": pe}).scalar())
    for i in ids:
        r = c.post(f"/api/v1/attendance/manual-logs/{i}/approve", json={"action": "approve"})
        assert r.status_code == 200 and "recalculated" in r.json()["message"], r.text
    db.expire_all()
    row = _status(db, pe, yday)
    assert row and row.att_status == 0 and row.work_minutes >= 11 * 60          # 07:00–19:00 present
    recs = [x for x in _build_attendance_records(db, yday) if x["employee_id"] == p["emp_code"]]
    assert recs and recs[0]["clock_in"] and recs[0]["clock_out"]               # goes to SeamlessHR
    # rejecting the clock-out takes it back out
    c.post(f"/api/v1/attendance/manual-logs/{ids[1]}/approve", json={"action": "reject"})
    assert db.execute(text("SELECT count(*) FROM iclock_transaction WHERE area_alias = :t"), {"t": f"manual:{ids[1]}"}).scalar() == 0


@needs_db
def test_leave_and_holiday_are_not_absences(db, make_person):
    from app.services.attendance_calculation_service import attendance_calculation_service as calc
    on_leave, pe_leave = _scheduled_person(db, make_person)
    shr_leave, pe_shr = _scheduled_person(db, make_person)
    absent, pe_abs = _scheduled_person(db, make_person)
    yday = (datetime.now(LAGOS) - timedelta(days=1)).date()
    db.execute(text("INSERT INTO att_leave (emp_id, start_time, end_time, approval_status, reason) "
                    "VALUES (:e, :s, :t, 1, 'annual')"),
               {"e": pe_leave, "s": datetime(yday.year, yday.month, yday.day, 0, 0, tzinfo=LAGOS),
                "t": datetime(yday.year, yday.month, yday.day, 23, 0, tzinfo=LAGOS)})
    db.execute(text("UPDATE personnel SET on_leave = TRUE, leave_end_date = CURRENT_DATE + 3 WHERE id = :i"), {"i": shr_leave["id"]})
    db.commit()
    ids = [on_leave["id"], shr_leave["id"], absent["id"]]
    run(calc.calculate_attendance(emp_ids=ids, start_date=str(yday), end_date=str(yday), db=db))
    db.expire_all()
    assert _status(db, pe_leave, yday).att_status == 4        # approved leave
    assert _status(db, pe_shr, yday).att_status == 4          # SeamlessHR leave
    assert _status(db, pe_abs, yday).att_status == 3          # genuinely absent
    hid = db.execute(text("INSERT INTO att_holiday (holiday_name, start_date, end_date, holiday_type, is_active) "
                          "VALUES ('Test holiday', :d, :d, 0, TRUE) RETURNING id"), {"d": yday}).scalar()
    db.commit()
    try:
        run(calc.calculate_attendance(emp_ids=[absent["id"]], start_date=str(yday), end_date=str(yday), db=db))
        db.expire_all()
        assert _status(db, pe_abs, yday) is None              # holiday: no absence on record
    finally:
        db.execute(text("DELETE FROM att_holiday WHERE id = :i"), {"i": hid})
        db.commit()


@needs_db
def test_seamlesshr_owns_staff_leave_overtime_and_only_its_staff_are_pushed(db, make_person, superuser_headers):
    from app.main import app
    from app.services.seamlesshr_service import only_seamlesshr_staff
    shr, pe_shr = _scheduled_person(db, make_person)
    local, pe_local = _scheduled_person(db, make_person)
    db.execute(text("UPDATE personnel SET hr_source = 'SEAMLESSHR' WHERE id = :i"), {"i": shr["id"]})
    db.commit()
    c = TestClient(app, headers=superuser_headers)
    lt = db.execute(text("INSERT INTO att_leave_type (leave_name) VALUES ('T annual') RETURNING id")).scalar()
    db.commit()
    body = lambda e: {"emp_id": e, "leave_type_id": lt, "start_time": "2030-01-05T08:00:00", "end_time": "2030-01-06T17:00:00"}
    r = c.post("/api/v1/attendance/leaves", json=body(pe_shr))
    assert r.status_code == 400 and "SeamlessHR" in r.json()["detail"]
    r = c.post("/api/v1/attendance/overtime", json={"personnel_id": pe_shr, "date": "2030-01-05", "hours_worked": 2})
    assert r.status_code == 400 and "SeamlessHR" in r.json()["detail"]
    r = c.post("/api/v1/attendance/overtime", json={"personnel_id": pe_local, "date": "2030-01-05", "hours_worked": 2})
    assert r.status_code in (200, 201), r.text                                    # contractor: allowed here
    kept, dropped = only_seamlesshr_staff(db, [{"employee_id": shr["emp_code"]}, {"employee_id": local["emp_code"]}])
    assert [k["employee_id"] for k in kept] == [shr["emp_code"]] and [d["employee_id"] for d in dropped] == [local["emp_code"]]


@needs_db
def test_exceptions_raised_for_late_missing_punch_and_absent(db, make_person):
    """att_exception was never written — the Exceptions tab was always empty."""
    from app.services.attendance_calculation_service import attendance_calculation_service as calc
    late, pe_late = _scheduled_person(db, make_person)
    gone, pe_gone = _scheduled_person(db, make_person)
    day = (datetime.now(LAGOS) - timedelta(days=2)).date()
    while day.weekday() > 4:                                            # Day shift runs Mon–Fri
        day -= timedelta(days=1)
    db.execute(text("""INSERT INTO iclock_transaction (emp_code, punch_time, punch_state, verify_type, work_code, upload_time)
                       VALUES (:c, :t, 0, 1, 0, NOW())"""),
               {"c": late["emp_code"], "t": datetime(day.year, day.month, day.day, 7, 40, tzinfo=LAGOS)})
    db.commit()
    ex = lambda pe: dict(db.execute(text("SELECT exception_type, handled_at IS NOT NULL FROM att_exception WHERE emp_id = :e AND att_date = :d"),
                                    {"e": pe, "d": day}).fetchall())
    recalc = lambda: run(calc.calculate_attendance(emp_ids=[late["id"], gone["id"]], start_date=str(day), end_date=str(day), db=db))
    recalc(); db.expire_all()
    assert ex(pe_late) == {"late_arrival": False, "missing_punch": False}
    assert ex(pe_gone) == {"absent": False}
    # supervisor excuses the missing punch → a recalculation doesn't raise it again
    db.execute(text("UPDATE att_exception SET handled_at = NOW(), handle_action = 'approve' WHERE emp_id = :e AND exception_type = 'missing_punch'"), {"e": pe_late})
    db.commit()
    recalc(); db.expire_all()
    assert ex(pe_late) == {"late_arrival": False, "missing_punch": True}
    # the clock-out turns up → no open missing punch, late stays
    db.execute(text("DELETE FROM att_exception WHERE emp_id = :e"), {"e": pe_late})
    db.execute(text("""INSERT INTO iclock_transaction (emp_code, punch_time, punch_state, verify_type, work_code, upload_time)
                       VALUES (:c, :t, 1, 1, 0, NOW())"""),
               {"c": late["emp_code"], "t": datetime(day.year, day.month, day.day, 19, 5, tzinfo=LAGOS)})
    db.commit()
    recalc(); db.expire_all()
    assert ex(pe_late) == {"late_arrival": False}


@needs_db
def test_leaves_screen_refuses_seamlesshr_staff_and_its_leave_counts(db, make_person, superuser_headers):
    """The Leaves tab posts to /personnel/leave (leave_management), not /attendance/leaves."""
    from app.main import app
    from app.services.attendance_calculation_service import attendance_calculation_service as calc
    shr, _ = _scheduled_person(db, make_person)
    local, pe_local = _scheduled_person(db, make_person)
    db.execute(text("UPDATE personnel SET hr_source = 'SEAMLESSHR' WHERE id = :i"), {"i": shr["id"]})
    db.commit()
    c = TestClient(app, headers=superuser_headers)
    day = (datetime.now(LAGOS) - timedelta(days=3)).date()
    body = lambda pid: {"personnel_id": pid, "leave_type": "annual", "start_date": str(day), "end_date": str(day), "days_count": 1}
    r = c.post("/api/v1/personnel/leave", json=body(shr["id"]))
    assert r.status_code == 400 and "SeamlessHR" in r.json()["detail"]
    r = c.post("/api/v1/personnel/leave", json=body(local["id"]))
    assert r.status_code == 201, r.text
    run(calc.calculate_attendance(emp_ids=[local["id"]], start_date=str(day), end_date=str(day), db=db))
    db.expire_all()
    assert _status(db, pe_local, day).att_status == 3                  # absent until the leave is approved
    assert c.put(f"/api/v1/personnel/leave/{r.json()['id']}/approve").status_code == 200
    db.expire_all()
    assert _status(db, pe_local, day).att_status == 4                  # approval re-scores the day at once
    assert c.put(f"/api/v1/personnel/leave/{r.json()['id']}/cancel").status_code == 200
    db.expire_all()
    assert _status(db, pe_local, day).att_status == 3
