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
