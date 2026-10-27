"""
Report regression tests — the figures operators and payroll read.
(Each was wrong before Oct 2026: UTC times, blank departments, absenteeism counting
rest days and leavers, crew change built from shift taps, last day of a range dropped.)
"""
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .conftest import needs_db

LAGOS = ZoneInfo("Africa/Lagos")
run = asyncio.run


def _report(db, code, **filters):
    from app.services.report_service import ReportService
    return ReportService(db).get_report_data(code, filters, 1, 500)


def _rows_for(result, emp_code):
    return [r for r in result["data"] if r.get("emp_code") == emp_code]


def _attendance_day(db, make_person, make_zone):
    """Yesterday (site time): one person taps 06:55 and 19:40 Lagos; one is scheduled
    and absent. Uses the real reader path and the real calculation."""
    from app.api.adms_protocol import handle_attlog
    from app.services.attendance_calculation_service import attendance_calculation_service as calc
    dep = db.execute(text("INSERT INTO departments (name, code) VALUES ('Report Dept', 'RPTD' || floor(random()*1e6)::text) RETURNING id")).scalar()
    import random
    pin = str(random.randint(10_000_000, 99_999_999))
    present = make_person(attendance_id=pin)
    absent = make_person(attendance_id=str(int(pin) + 1))
    shift = db.execute(text("INSERT INTO att_shift (name, start_time, end_time, work_days, is_active) "
                            "VALUES ('Rpt 07-19', '07:00', '19:00', '1234567', TRUE) RETURNING id")).scalar()
    for p in (present, absent):
        db.execute(text("UPDATE personnel SET department_id = :d, department = 'Report Dept' WHERE id = :i"), {"d": dep, "i": p["id"]})
        db.execute(text("INSERT INTO att_schedule (emp_code, shift_id, start_date, status) VALUES (:c, :s, CURRENT_DATE - 30, 'scheduled')"),
                   {"c": p["emp_code"], "s": shift})
    db.execute(text("INSERT INTO iclock_terminal (sn, alias, state, reader_purpose) VALUES ('RPTTEST', 't', 1, 'ATTENDANCE') ON CONFLICT DO NOTHING"))
    db.commit()
    yday = (datetime.now(LAGOS) - timedelta(days=1)).date()
    for h, m in ((6, 55), (19, 40)):
        t = datetime(yday.year, yday.month, yday.day, h, m, tzinfo=LAGOS).astimezone(ZoneInfo("UTC"))
        handle_attlog([{"PIN": pin, "Time": t.strftime("%Y-%m-%d %H:%M:%S"), "Status": "1"}], "RPTTEST", db)
    ids = [present["id"], absent["id"]]          # calculate_attendance takes PERSONNEL ids
    run(calc.calculate_attendance(emp_ids=ids, start_date=str(yday), end_date=str(yday), db=db))
    return present, absent, yday


@needs_db
def test_attendance_report_in_site_time_with_department(db, make_person, make_zone):
    present, _absent, yday = _attendance_day(db, make_person, make_zone)
    res = _report(db, "att.daily", date=str(yday), emp_code=present["emp_code"])
    rows = _rows_for(res, present["emp_code"])
    assert rows, f"no att.daily row; report total={res['total']}, att_report rows=" + str(db.execute(text(
        "SELECT att_date, check_in, att_status FROM att_report r JOIN personnel_employee e ON e.id = r.emp_id "
        "WHERE e.emp_code = :c"), {"c": present["emp_code"]}).fetchall())
    row = rows[0]
    assert row["check_in"].endswith("06:55") and row["check_out"].endswith("19:40")   # not 05:55 / 18:40 (UTC)
    assert row["department"] == "Report Dept"                                         # was always blank


@needs_db
def test_absenteeism_is_scheduled_and_not_present(db, make_person, make_zone):
    present, absent, yday = _attendance_day(db, make_person, make_zone)
    codes = {r["emp_code"] for r in _report(db, "att.absent", date=str(yday))["data"]}
    assert absent["emp_code"] in codes
    assert present["emp_code"] not in codes
    # someone with no schedule that day (rest / off rotation) is not "absent"
    off = make_person()
    assert off["emp_code"] not in {r["emp_code"] for r in _report(db, "att.absent", date=str(yday))["data"]}


@needs_db
def test_crew_change_comes_from_real_movements(db, make_person, make_zone):
    from app.api import transport_manifest as T
    from app.services.report_service import _site_today
    arriving = make_person()
    f = run(T.create_flight(T.FlightCreate(transport_identifier="RPT-CC", departure_location="Shore",
                                           arrival_location="Rig", departure_time=datetime.now(LAGOS)), db, NS(id=1)))["id"]
    e = run(T.add_manifest_entry(f, T.ManifestEntryCreate(passenger_name="", personnel_id=arriving["id"], direction="INBOUND"), db, NS(id=1)))
    run(T.update_manifest_entry(f, e["id"], T.ManifestEntryUpdate(status="CONFIRMED"), NS(state=NS(user_permissions=["*"])), db, NS(id=1)))
    run(T.update_flight_status(f, T.FlightStatusUpdate(status="COMPLETED"), db, NS(id=1)))
    rows = _rows_for(_report(db, "pob.crew_change", date=str(_site_today())), arriving["emp_code"])
    assert [r["change_type"] for r in rows] == ["MOBILIZE"] and "RPT-CC" in rows[0]["terminal"]


@needs_db
def test_date_range_includes_its_last_day(db, make_person, make_zone):
    from app.api.adms_protocol import _handle_zone_access
    from app.services.report_service import _site_today
    z = make_zone()
    p = make_person()
    _handle_zone_access(p["emp_code"], "RPT", datetime.now(LAGOS) - timedelta(minutes=5), NS(zone_id=z, alias="z"), "ENTRY", db)
    today = str(_site_today())
    rows = _rows_for(_report(db, "zone.access_log", date_from=today, date_to=today), p["emp_code"])
    assert rows, "an event from today must be inside the range today..today"


# ── Reports v2: scheduling, access list and the gap reports ──────────────────

def test_schedule_times_are_site_time_and_naive_utc():
    from datetime import date, timezone
    from app.services.report_scheduler import make_cron, next_run, resolve_filters
    cron = make_cron("weekly", "07:30", 1)                      # Mondays 07:30 Lagos
    after = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)  # a Tuesday
    nxt = next_run(cron, after)
    assert nxt.tzinfo is None and nxt == datetime(2026, 11, 2, 6, 30)   # 07:30 Lagos = 06:30 UTC
    assert next_run(make_cron("monthly", "06:00"), after) == datetime(2026, 11, 1, 5, 0)
    today = date(2026, 10, 27)
    assert resolve_filters({"date_mode": "single", "relative": "yesterday", "department": 4}, today) == \
        {"department": 4, "date": "2026-10-26"}
    r = resolve_filters({"date_mode": "range", "relative": "last_month"}, today)
    assert (r["date_from"], r["date_to"]) == ("2026-09-01", "2026-09-30")
    r = resolve_filters({"date_mode": "range", "relative": "last_week"}, today)
    assert (r["date_from"], r["date_to"]) == ("2026-10-19", "2026-10-25")


@needs_db
def test_gap_reports_run(db, make_person):
    make_person(attendance_id=None)
    for code in ("pob.trend", "att.hr_sync", "personnel.no_pin", "muster.roll_call"):
        res = _report(db, code, date_from="2026-10-01", date_to="2026-10-27")
        assert "data" in res and "total" in res, code
    nopin = _report(db, "personnel.no_pin")
    assert nopin["total"] >= 1


@needs_db
def test_scheduled_report_runs_and_keeps_its_file(db):
    from app.models.report import ReportSchedule, ReportTemplate
    from app.services.report_scheduler import make_cron, next_run, run_due, file_exists
    cron = make_cron("daily", "07:00")
    tpl = ReportTemplate(template_name="[schedule] t", module="personnel", report_code="personnel.employee_list",
                         filters={"date_mode": "none", "relative": None}, created_by=1)
    db.add(tpl); db.flush()
    s = ReportSchedule(template_id=tpl.id, schedule_name="Test sched", cron=cron, format="csv",
                       recipients={"emails": []}, is_active=True, created_by=1,
                       report_code="personnel.employee_list", next_run=datetime(2000, 1, 1))
    db.add(s); db.commit()
    assert run_due(db) >= 1
    db.refresh(s)
    assert s.last_status == "ok", s.last_error
    assert file_exists(s.last_file_path)
    assert s.next_run > datetime.utcnow() and s.last_run is not None
    assert run_due(db) == 0 or s.id not in [x.id for x in db.query(ReportSchedule).filter(ReportSchedule.next_run <= datetime.utcnow())]


@needs_db
def test_allowed_and_schedule_api(db, superuser_headers):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    h = superuser_headers
    a = c.get("/api/v1/report/allowed", headers=h)
    assert a.status_code == 200, a.text
    assert "pob.trend" in a.json()["codes"]
    r = c.post("/api/v1/report/scheduled", headers=h, json={
        "report_code": "att.late", "name": "Late daily", "frequency": "daily", "time": "07:00",
        "format": "xlsx", "emails": ["ops@example.com"], "filters": {}, "date_mode": "single", "relative": "yesterday"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert r.json()["schedule"] == "Every day at 07:00"
    run = c.post(f"/api/v1/report/scheduled/{sid}/run", headers=h)
    assert run.status_code == 200, run.text
    lst = {x["id"]: x for x in c.get("/api/v1/report/scheduled", headers=h).json()}
    assert lst[sid]["has_file"] and lst[sid]["last_status"] in ("ok", "emailed", "email_failed")
    f = c.get(f"/api/v1/report/scheduled/{sid}/file", headers=h)
    assert f.status_code == 200 and len(f.content) > 100
    assert c.delete(f"/api/v1/report/scheduled/{sid}", headers=h).status_code == 200
    assert "Late daily" not in {t.get("template_name") for t in (c.get("/api/v1/report/templates", headers=h).json() or [])
                                if isinstance(t, dict)}
