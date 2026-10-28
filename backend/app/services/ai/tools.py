"""
ARIA Tool Executors — live DB queries for every Apex POB area.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _safe(row) -> dict:
    if row is None:
        return {}
    d = dict(row._mapping)
    for k, v in d.items():
        if isinstance(v, (date, datetime)):
            d[k] = v.isoformat()
        elif hasattr(v, '__float__'):
            d[k] = float(v)
    return d


def execute_tool(name: str, args: dict, db: Session) -> Any:
    executors = {
        # ── Core operations ──
        "get_dashboard_stats":    _dashboard_stats,
        "get_onsite_personnel":   _onsite_personnel,
        "get_attendance_summary": _attendance_summary,
        "get_att_report":         _att_report,
        "get_pob_status":         _pob_status,
        # ── Personnel & HR ──
        "get_departments":        _departments,
        "get_positions":          _positions,
        "get_personnel_list":     _personnel_list,
        "search_personnel":       _search_personnel,
        "get_employment_contracts": _employment_contracts,
        "get_disciplinary":       _disciplinary,
        "get_performance":        _performance,
        "get_resignations":       _resignations,
        # ── Attendance & Time ──
        "get_shifts":             _shifts,
        "get_schedules":          _schedules,
        "get_holidays":           _holidays,
        "get_att_exceptions":     _att_exceptions,
        "get_overtime":           _overtime,
        "get_leave_requests":     _leave_requests,
        "get_leave_balance":      _leave_balance,
        # ── Contractors & Compliance ──
        "get_expiring_items":     _expiring_items,
        "get_contractor_status":  _contractor_status,
        # ── Visitors ──
        "get_visitor_summary":    _visitor_summary,
        # ── Zones & Access ──
        "get_zones_summary":      _zones_summary,
        "get_zones_detail":       _zones_detail,
        "get_access_control":     _access_control,
        "get_areas":              _areas,
        # ── Emergency & Safety ──
        "get_emergency_events":   _emergency_events,
        "get_mustering":          _mustering,
        # ── Devices ──
        "get_devices":            _devices,
        # ── Transport ──
        "get_transport":          _transport,
        # ── Meetings ──
        "get_meeting_rooms":      _meeting_rooms,
        # ── Training ──
        "get_training":           _training,
        # ── Security & Anomalies ──
        "get_anomaly_alerts":     _anomaly_alerts,
        # ── Notifications ──
        "get_notifications":      _notifications,
    }
    fn = executors.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(args, db)
    except Exception as e:
        logger.error(f"Tool {name} error: {e}", exc_info=True)
        return {"error": str(e)}


# ── Core operations ────────────────────────────────────────────────────────────

def _dashboard_stats(args, db):
    row = db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM personnel WHERE status = 'ACTIVE')                AS total_employees,
            (SELECT COUNT(*) FROM vis_visit_log WHERE status = 0)                   AS visitors_onsite,
            (SELECT COUNT(*) FROM vis_pre_registration WHERE status = 0)            AS pending_visitor_approvals,
            (SELECT COUNT(*) FROM vis_blacklist WHERE is_active = true)             AS blacklisted_visitors,
            (SELECT COUNT(*) FROM contractors WHERE status = 'ACTIVE')              AS active_contractors,
            (SELECT COUNT(DISTINCT emp_code) FROM iclock_transaction
             WHERE punch_time::date = CURRENT_DATE)                                 AS punches_today,
            (SELECT COUNT(*) FROM iclock_transaction
             WHERE punch_time::date = CURRENT_DATE AND punch_state IN (0,255))      AS checkins_today,
            (SELECT COUNT(*) FROM contractors c
             WHERE c.status = 'ACTIVE'
               AND c.work_permit_expiry IS NOT NULL
               AND c.work_permit_expiry::date <= CURRENT_DATE + 30)                 AS permit_alerts,
            (SELECT COUNT(*) FROM leave_management
             WHERE LOWER(status) NOT IN ('approved','rejected'))                    AS pending_leaves,
            (SELECT COUNT(*) FROM iclock_terminal)                                  AS total_readers,
            (SELECT COUNT(*) FROM iclock_terminal
             WHERE last_activity >= NOW() - INTERVAL '10 minutes')                 AS readers_online,
            (SELECT COUNT(*) FROM devices WHERE is_active = true)                   AS total_devices,
            (SELECT COUNT(*) FROM devices WHERE status = 'ONLINE')                  AS devices_online,
            (SELECT COUNT(*) FROM departments WHERE is_active = true)               AS total_departments,
            (SELECT COUNT(*) FROM zones WHERE LOWER(status) = 'active')             AS active_zones,
            (SELECT COUNT(*) FROM training_courses WHERE is_mandatory = true)       AS mandatory_courses,
            (SELECT COUNT(*) FROM emergency_event WHERE status = 0)                 AS active_emergencies
    """)).fetchone()
    return _safe(row)


def _onsite_personnel(args, db):
    limit = min(args.get("limit", 30) or 30, 100)
    dept  = args.get("department") or ""
    dept_filter = "AND d.name ILIKE :dept" if dept else ""
    rows = db.execute(text(f"""
        SELECT
            COALESCE(NULLIF(TRIM(p.first_name||' '||COALESCE(p.last_name,'')),'' ),'Unknown') AS name,
            p.emp_code, d.name AS department,
            MIN(t.punch_time) AS checked_in_at,
            pa.area_name AS area
        FROM iclock_transaction t
        INNER JOIN personnel p ON (t.emp_code = p.emp_code OR t.emp_code = p.badge_id)
        LEFT  JOIN departments d  ON d.id = p.department_id
        LEFT  JOIN iclock_terminal trm ON trm.sn = t.terminal_sn
        LEFT  JOIN personnel_area  pa  ON pa.id = trm.area_id
        WHERE t.punch_time::date = CURRENT_DATE
          AND t.punch_state IN (0, 255)
          {dept_filter}
          AND NOT EXISTS (
              SELECT 1 FROM iclock_transaction t2
              WHERE t2.emp_code = t.emp_code
                AND t2.punch_time::date = CURRENT_DATE
                AND t2.punch_state = 1
                AND t2.punch_time > t.punch_time
          )
        GROUP BY p.emp_code, p.first_name, p.last_name, d.name, pa.area_name
        ORDER BY checked_in_at DESC
        LIMIT :lim
    """), {"dept": f"%{dept}%", "lim": limit} if dept else {"lim": limit}).fetchall()
    return {"count": len(rows), "personnel": [_safe(r) for r in rows]}


def _attendance_summary(args, db):
    start = args.get("start_date") or args.get("date") or date.today().isoformat()
    end   = args.get("end_date")   or start
    rows  = db.execute(text("""
        SELECT d.name AS department,
               COUNT(DISTINCT t.emp_code)                       AS unique_punches,
               COUNT(*) FILTER (WHERE t.punch_state IN (0,255)) AS checkins
        FROM iclock_transaction t
        LEFT JOIN personnel p  ON (t.emp_code = p.emp_code OR t.emp_code = p.badge_id)
        LEFT JOIN departments d ON d.id = p.department_id
        WHERE t.punch_time::date BETWEEN :s AND :e
        GROUP BY d.name ORDER BY unique_punches DESC LIMIT 20
    """), {"s": start, "e": end}).fetchall()
    return {"period": f"{start} to {end}", "by_department": [_safe(r) for r in rows]}


def _att_report(args, db):
    from datetime import date as _date, timedelta
    # Support explicit date range OR last-N-days
    start = args.get("start_date")
    end   = args.get("end_date")
    if not start:
        days  = args.get("days", 7) or 7
        start = (_date.today() - timedelta(days=days - 1)).isoformat()
        end   = _date.today().isoformat()
    if not end:
        end = start
    rows = db.execute(text("""
        SELECT
            TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS name,
            p.emp_code, d.name AS department,
            r.att_date, r.check_in, r.check_out,
            r.work_minutes, r.late_minutes, r.ot_minutes,
            CASE r.att_status
                WHEN 0 THEN 'Present' WHEN 1 THEN 'Late'
                WHEN 2 THEN 'Absent'  WHEN 4 THEN 'Day-off'
                ELSE 'Other' END AS status
        FROM att_report r
        LEFT JOIN personnel_employee pe ON pe.id = r.emp_id
        LEFT JOIN personnel p  ON p.emp_code = pe.emp_code
        LEFT JOIN departments d ON d.id = r.department_id
        WHERE r.att_date BETWEEN :start AND :end
        ORDER BY r.att_date DESC, p.first_name
        LIMIT 200
    """), {"start": start, "end": end}).fetchall()
    stats = db.execute(text("""
        SELECT
            COUNT(*)                                          AS total_records,
            COUNT(*) FILTER (WHERE att_status = 0)           AS present,
            COUNT(*) FILTER (WHERE att_status = 1)           AS late,
            COUNT(*) FILTER (WHERE att_status = 2)           AS absent,
            ROUND(AVG(work_minutes))                         AS avg_work_minutes,
            SUM(late_minutes)                                AS total_late_minutes,
            SUM(ot_minutes)                                  AS total_ot_minutes
        FROM att_report WHERE att_date BETWEEN :start AND :end
    """), {"start": start, "end": end}).fetchone()
    return {
        "period": f"{start}" if start == end else f"{start} to {end}",
        "stats": _safe(stats),
        "records": [_safe(r) for r in rows],
    }


def _pob_status(args, db):
    row = db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM personnel WHERE status = 'ACTIVE')    AS total_personnel,
            (SELECT COUNT(DISTINCT emp_code) FROM iclock_transaction
             WHERE punch_time::date = CURRENT_DATE
               AND punch_state IN (0,255))                               AS punched_in_today,
            (SELECT COUNT(*) FROM leave_management
             WHERE LOWER(status) = 'approved'
               AND start_date <= CURRENT_DATE
               AND end_date   >= CURRENT_DATE)                           AS on_approved_leave,
            (SELECT COUNT(*) FROM contractors
             WHERE status = 'ACTIVE'
               AND availability_status = 'ON_ASSIGNMENT')               AS contractors_on_assignment,
            (SELECT COUNT(*) FROM pob_status WHERE status = 'active')   AS pob_locations
    """)).fetchone()
    locations = db.execute(text("""
        SELECT location, personnel_count, status, last_updated
        FROM pob_status ORDER BY personnel_count DESC LIMIT 10
    """)).fetchall()
    return {"summary": _safe(row), "locations": [_safe(r) for r in locations]}


# ── Personnel & HR ─────────────────────────────────────────────────────────────

def _departments(args, db):
    rows = db.execute(text("""
        SELECT d.name, d.code, d.department_type, d.status,
               d.max_personnel, d.current_personnel_count,
               (SELECT COUNT(*) FROM personnel p WHERE p.department_id = d.id AND p.status = 'ACTIVE') AS actual_count,
               d.contact_person, d.is_active
        FROM departments d ORDER BY d.name
    """)).fetchall()
    return {"count": len(rows), "departments": [_safe(r) for r in rows]}


def _positions(args, db):
    rows = db.execute(text("""
        SELECT pos.position_name, pos.position_code, pos.position_type,
               d.name AS department, pos.grade_level, pos.is_safety_critical, pos.is_active,
               (SELECT COUNT(*) FROM personnel p WHERE p.position = pos.position_name) AS headcount
        FROM positions pos
        LEFT JOIN departments d ON d.id = pos.department_id
        ORDER BY pos.position_name
    """)).fetchall()
    return {"count": len(rows), "positions": [_safe(r) for r in rows]}


def _personnel_list(args, db):
    dept   = args.get("department") or ""
    status = args.get("status", "ACTIVE") or "ACTIVE"
    dept_f = "AND d.name ILIKE :dept" if dept else ""
    rows = db.execute(text(f"""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS name,
               p.emp_code, p.position, p.status,
               d.name AS department,
               (SELECT MAX(t.punch_time) FROM iclock_transaction t
                WHERE t.emp_code = p.emp_code) AS last_seen
        FROM personnel p
        LEFT JOIN departments d ON d.id = p.department_id
        WHERE p.status = :status {dept_f}
        ORDER BY p.first_name LIMIT 50
    """), {"status": status, "dept": f"%{dept}%"} if dept else {"status": status}).fetchall()
    return {"count": len(rows), "personnel": [_safe(r) for r in rows]}


def _search_personnel(args, db):
    q    = args.get("query", "") or ""
    rows = db.execute(text("""
        SELECT p.emp_code,
               TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS name,
               d.name AS department, p.position, p.status,
               p.email, p.phone,
               (SELECT MAX(t.punch_time) FROM iclock_transaction t
                WHERE t.emp_code = p.emp_code) AS last_seen
        FROM personnel p
        LEFT JOIN departments d ON d.id = p.department_id
        WHERE p.emp_code ILIKE :q OR p.first_name ILIKE :q
           OR p.last_name ILIKE :q OR d.name ILIKE :q
           OR p.position ILIKE :q
        LIMIT 15
    """), {"q": f"%{q}%"}).fetchall()
    return {"count": len(rows), "results": [_safe(r) for r in rows]}


def _employment_contracts(args, db):
    rows = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               ec.contract_number, ec.contract_type, ec.job_title,
               ec.start_date, ec.end_date, ec.status, ec.currency,
               d.name AS department
        FROM employment_contracts ec
        LEFT JOIN personnel p ON ec.personnel_id = p.id
        LEFT JOIN departments d ON ec.department_id = d.id
        ORDER BY ec.start_date DESC LIMIT 20
    """)).fetchall()
    return {"count": len(rows), "contracts": [_safe(r) for r in rows]}


def _disciplinary(args, db):
    rows = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               dc.case_number, dc.incident_type, dc.severity_level,
               dc.incident_date, dc.status, dc.description
        FROM disciplinary_cases dc
        LEFT JOIN personnel p ON dc.personnel_id = p.id
        ORDER BY dc.incident_date DESC LIMIT 20
    """)).fetchall()
    return {"count": len(rows), "cases": [_safe(r) for r in rows]}


def _performance(args, db):
    rows = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               pa.appraisal_date, pa.overall_rating, pa.performance_score,
               pa.goals_achieved, pa.status, pa.strengths, pa.areas_for_improvement
        FROM performance_appraisals pa
        LEFT JOIN personnel p ON pa.personnel_id = p.id
        ORDER BY pa.appraisal_date DESC LIMIT 20
    """)).fetchall()
    return {"count": len(rows), "appraisals": [_safe(r) for r in rows]}


def _resignations(args, db):
    rows = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               r.resignation_type, r.status, r.resignation_date,
               r.last_working_day, r.reason, r.handover_completed
        FROM resignations r
        LEFT JOIN personnel p ON r.personnel_id = p.id
        ORDER BY r.resignation_date DESC LIMIT 20
    """)).fetchall()
    return {"count": len(rows), "resignations": [_safe(r) for r in rows]}


# ── Attendance & Time ──────────────────────────────────────────────────────────

def _shifts(args, db):
    rows = db.execute(text("""
        SELECT name, shift_code, shift_type,
               start_time, end_time, working_hours,
               is_night_shift, is_weekend_shift, is_active,
               days_of_week, grace_period_minutes
        FROM att_shift ORDER BY name
    """)).fetchall()
    return {"count": len(rows), "shifts": [_safe(r) for r in rows]}


def _schedules(args, db):
    rows = db.execute(text("""
        SELECT sm.name, sm.status,
               TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               s.name AS shift_name
        FROM schedule_management sm
        LEFT JOIN personnel p ON sm.id = p.id
        LEFT JOIN att_shift s ON sm.id = s.id
        ORDER BY sm.name LIMIT 20
    """)).fetchall()
    return {"count": len(rows), "schedules": [_safe(r) for r in rows]}


def _holidays(args, db):
    rows = db.execute(text("""
        SELECT holiday_name, start_date, end_date, holiday_type, description, is_active
        FROM att_holiday
        WHERE start_date >= CURRENT_DATE - 30
        ORDER BY start_date LIMIT 20
    """)).fetchall()
    return {"count": len(rows), "holidays": [_safe(r) for r in rows]}


def _att_exceptions(args, db):
    rows = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               ae.att_date, ae.exception_type, ae.deviation_minutes,
               ae.exception_note, ae.handle_action
        FROM att_exception ae
        LEFT JOIN personnel_employee pe ON pe.id = ae.emp_id
        LEFT JOIN personnel p ON p.emp_code = pe.emp_code
        ORDER BY ae.att_date DESC LIMIT 20
    """)).fetchall()
    return {"count": len(rows), "exceptions": [_safe(r) for r in rows]}


def _overtime(args, db):
    start = args.get("start_date")
    end   = args.get("end_date")
    date_filter = ""
    params: dict = {}
    if start:
        date_filter += " AND om.date >= :start"
        params["start"] = start
    if end:
        date_filter += " AND om.date <= :end"
        params["end"] = end
    rows = db.execute(text(f"""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               om.overtime_type, om.date, om.hours_worked,
               om.status, om.compensation_type, om.reason
        FROM overtime_management om
        LEFT JOIN personnel p ON om.personnel_id = p.id
        WHERE 1=1 {date_filter}
        ORDER BY om.date DESC LIMIT 50
    """), params).fetchall()
    stats = db.execute(text(f"""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'approved')  AS approved,
               COUNT(*) FILTER (WHERE status = 'pending')   AS pending,
               ROUND(SUM(hours_worked)::numeric, 1)         AS total_hours
        FROM overtime_management WHERE 1=1 {date_filter}
    """), params).fetchone()
    return {"stats": _safe(stats), "records": [_safe(r) for r in rows]}


def _leave_requests(args, db):
    status = (args.get("status", "all") or "all").lower()
    limit  = min(args.get("limit", 15) or 15, 100)
    start  = args.get("start_date")
    end    = args.get("end_date")
    filters = []
    params: dict = {"lim": limit}
    if status != "all":
        filters.append("LOWER(lr.status) = :status")
        params["status"] = status
    if start:
        filters.append("lr.end_date >= :start")
        params["start"] = start
    if end:
        filters.append("lr.start_date <= :end")
        params["end"] = end
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = db.execute(text(f"""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               p.emp_code, lr.leave_type, lr.start_date, lr.end_date,
               lr.status, lr.days_count, lr.reason
        FROM leave_management lr
        LEFT JOIN personnel p ON lr.personnel_id = p.id
        {where}
        ORDER BY lr.created_at DESC LIMIT :lim
    """), params).fetchall()
    return {"count": len(rows), "requests": [_safe(r) for r in rows]}


def _leave_balance(args, db):
    rows = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               lb.leave_type, lb.total_days, lb.used_days,
               lb.balance_days, lb.carry_forward_days, lb.year
        FROM leave_balance lb
        LEFT JOIN personnel p ON lb.personnel_id = p.id
        WHERE lb.year = EXTRACT(YEAR FROM CURRENT_DATE)
        ORDER BY lb.balance_days ASC LIMIT 30
    """)).fetchall()
    return {"count": len(rows), "balances": [_safe(r) for r in rows]}


# ── Contractors & Compliance ───────────────────────────────────────────────────

def _expiring_items(args, db):
    days      = args.get("days", 30) or 30
    item_type = args.get("item_type", "all") or "all"
    cutoff    = (date.today() + timedelta(days=days)).isoformat()
    results   = {}

    if item_type in ("work_permits", "all"):
        rows = db.execute(text("""
            SELECT (c.first_name||' '||c.last_name) AS name, c.contractor_code,
                   v.vendor_name AS vendor, c.work_permit_expiry,
                   CASE WHEN c.work_permit_expiry::date < CURRENT_DATE
                        THEN 'EXPIRED' ELSE 'EXPIRING' END AS status
            FROM contractors c
            LEFT JOIN vendors v ON v.id = c.vendor_id
            WHERE c.status = 'ACTIVE'
              AND c.work_permit_expiry IS NOT NULL
              AND c.work_permit_expiry::date <= :cutoff
            ORDER BY c.work_permit_expiry LIMIT 20
        """), {"cutoff": cutoff}).fetchall()
        results["work_permits"] = [_safe(r) for r in rows]

    if item_type in ("medical", "all"):
        rows = db.execute(text("""
            SELECT (c.first_name||' '||c.last_name) AS name, c.contractor_code,
                   c.medical_clearance_status, c.medical_clearance_date
            FROM contractors c
            WHERE c.status = 'ACTIVE'
              AND c.medical_clearance_status IN ('FAILED', 'PENDING')
            ORDER BY c.medical_clearance_date NULLS LAST LIMIT 20
        """)).fetchall()
        results["medical_alerts"] = [_safe(r) for r in rows]

    return results


def _contractor_status(args, db):
    vendor = args.get("vendor_name") or ""
    vf = "AND v.vendor_name ILIKE :vendor" if vendor else ""
    row = db.execute(text(f"""
        SELECT
            COUNT(*) FILTER (WHERE c.status = 'ACTIVE')                              AS total_active,
            COUNT(*) FILTER (WHERE c.work_permit_expiry::date < CURRENT_DATE
                             AND c.work_permit_expiry IS NOT NULL
                             AND c.status = 'ACTIVE')                                 AS expired_permits,
            COUNT(*) FILTER (WHERE c.work_permit_expiry::date BETWEEN CURRENT_DATE AND CURRENT_DATE+30
                             AND c.work_permit_expiry IS NOT NULL
                             AND c.status = 'ACTIVE')                                 AS expiring_soon,
            COUNT(*) FILTER (WHERE c.medical_clearance_status = 'FAILED'
                             AND c.status = 'ACTIVE')                                 AS failed_medical,
            COUNT(*) FILTER (WHERE c.background_check_status = 'FAILED'
                             AND c.status = 'ACTIVE')                                 AS failed_background
        FROM contractors c
        LEFT JOIN vendors v ON v.id = c.vendor_id
        {vf}
    """), {"vendor": f"%{vendor}%"} if vendor else {}).fetchone()
    return _safe(row)


# ── Visitors ───────────────────────────────────────────────────────────────────

def _visitor_summary(args, db):
    target_date = args.get("start_date") or date.today().isoformat()
    row = db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM vis_visit_log WHERE status = 0)                    AS on_site,
            (SELECT COUNT(*) FROM vis_visit_log
             WHERE check_in_time::date = :d)                                         AS checked_in_on_date,
            (SELECT COUNT(*) FROM vis_pre_registration WHERE status = 0)             AS pending_approvals,
            (SELECT COUNT(*) FROM vis_blacklist WHERE is_active = true)              AS blacklisted,
            (SELECT COUNT(*) FROM vis_visit_log WHERE status = 2)                    AS overstays,
            (SELECT COUNT(*) FROM vis_visitor)                                       AS total_visitors_ever
    """), {"d": target_date}).fetchone()
    recent = db.execute(text("""
        SELECT vv.full_name AS name, vv.phone, vr.check_in_time, vr.check_out_time, vr.status
        FROM vis_visit_log vr
        LEFT JOIN vis_visitor vv ON vv.id = vr.visitor_id
        WHERE vr.check_in_time::date = :d
        ORDER BY vr.check_in_time DESC LIMIT 10
    """), {"d": target_date}).fetchall()
    result = _safe(row)
    result["date"] = target_date
    result["recent_visitors"] = [_safe(r) for r in recent]
    return result


# ── Zones & Access ─────────────────────────────────────────────────────────────

def _zones_summary(args, db):
    row = db.execute(text("""
        SELECT COUNT(*) AS total_zones,
               COUNT(*) FILTER (WHERE LOWER(status) = 'active')   AS active_zones,
               COUNT(*) FILTER (WHERE LOWER(status) != 'active')  AS inactive_zones
        FROM zones
    """)).fetchone()
    types = db.execute(text("""
        SELECT zone_type, COUNT(*) AS count
        FROM zones GROUP BY zone_type ORDER BY count DESC
    """)).fetchall()
    result = _safe(row)
    result["by_type"] = [{"zone_type": r[0], "count": r[1]} for r in types]
    return result


def _zones_detail(args, db):
    rows = db.execute(text("""
        SELECT z.name, z.code, z.zone_type, z.status,
               (SELECT COUNT(*) FROM zone_personnel_assignments zpa
                WHERE zpa.zone_id = z.id AND LOWER(zpa.status) = 'active') AS assigned_personnel,
               (SELECT COUNT(*) FROM zone_reader_assignments zra
                WHERE zra.zone_id = z.id) AS assigned_readers
        FROM zones z ORDER BY z.name LIMIT 50
    """)).fetchall()
    return {"count": len(rows), "zones": [_safe(r) for r in rows]}


def _access_control(args, db):
    levels = db.execute(text("""
        SELECT al.name, al.is_active, al.mustering_only,
               (SELECT COUNT(*) FROM acc_userauthorize ua WHERE ua.acc_level_id = al.id) AS user_count,
               (SELECT COUNT(*) FROM acc_level_door ld WHERE ld.level_id = al.id)    AS door_count
        FROM acc_level al ORDER BY al.name
    """)).fetchall()
    doors = db.execute(text("""
        SELECT ad.name, ad.mustering_mode, ad.fire_linkage,
               it.alias AS reader, it.ip_address
        FROM acc_door ad
        LEFT JOIN iclock_terminal it ON it.sn = ad.terminal_sn
        ORDER BY ad.name
    """)).fetchall()
    return {
        "access_levels": [_safe(r) for r in levels],
        "doors": [_safe(r) for r in doors],
    }


def _areas(args, db):
    rows = db.execute(text("""
        SELECT pa.area_name, pa.area_code,
               (SELECT COUNT(*) FROM iclock_terminal it
                WHERE it.area_id = pa.id) AS readers_in_area
        FROM personnel_area pa ORDER BY pa.area_name
    """)).fetchall()
    return {"count": len(rows), "areas": [_safe(r) for r in rows]}


# ── Emergency & Safety ─────────────────────────────────────────────────────────

def _emergency_events(args, db):
    rows = db.execute(text("""
        SELECT ee.id, ee.event_type, ee.status, ee.trigger_source,
               ee.reason, ee.start_time, ee.end_time,
               TRIM(u.first_name||' '||COALESCE(u.last_name,'')) AS initiated_by_name
        FROM emergency_event ee
        LEFT JOIN auth_user u ON u.id = ee.initiated_by
        ORDER BY ee.start_time DESC LIMIT 10
    """)).fetchall()
    active = db.execute(text(
        "SELECT COUNT(*) FROM emergency_event WHERE status = 0"
    )).scalar()
    return {"active_count": active, "events": [_safe(r) for r in rows]}


def _mustering(args, db):
    events = db.execute(text("""
        SELECT me.id, me.event_type, me.status, me.start_time, me.end_time,
               me.total_expected, me.total_safe, me.total_missing, me.total_injured,
               z.name AS zone_name
        FROM mustering_event me
        LEFT JOIN zones z ON z.id = me.zone_id
        ORDER BY me.start_time DESC LIMIT 10
    """)).fetchall()
    drills = db.execute(text("""
        SELECT md.scheduled_time, md.status, md.processed, z.name AS zone_name
        FROM mustering_drill_schedule md
        LEFT JOIN zones z ON z.id = md.zone_id
        WHERE md.scheduled_time >= CURRENT_DATE - 30
        ORDER BY md.scheduled_time DESC LIMIT 10
    """)).fetchall()
    return {
        "recent_events": [_safe(r) for r in events],
        "recent_drills": [_safe(r) for r in drills],
    }


# ── Devices ────────────────────────────────────────────────────────────────────

def _devices(args, db):
    rows = db.execute(text("""
        SELECT d.name, d.serial_number, d.device_type, d.model,
               d.ip_address, d.status, d.is_active,
               d.last_seen, d.last_heartbeat,
               z.name AS zone
        FROM devices d
        LEFT JOIN zones z ON z.id = d.zone_id
        ORDER BY d.status, d.name
    """)).fetchall()
    stats = db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'ONLINE')  AS online,
            COUNT(*) FILTER (WHERE status = 'OFFLINE') AS offline
        FROM devices WHERE is_active = true
    """)).fetchone()
    readers = db.execute(text("""
        SELECT sn, alias, ip_address, state, last_activity,
               CASE WHEN last_activity >= NOW() - INTERVAL '10 minutes'
                    THEN 'ONLINE' ELSE 'OFFLINE' END AS connectivity
        FROM iclock_terminal ORDER BY alias
    """)).fetchall()
    return {
        "device_stats": _safe(stats),
        "devices": [_safe(r) for r in rows],
        "readers": [_safe(r) for r in readers],
    }


# ── Transport ──────────────────────────────────────────────────────────────────

def _transport(args, db):
    vehicles = db.execute(text("""
        SELECT t.identifier, t.type, t.operator, t.capacity,
               t.current_pob, t.status, t.is_available,
               t.flight_hours, t.is_maintenance_mode
        FROM transport t ORDER BY t.identifier
    """)).fetchall()
    schedules = db.execute(text("""
        SELECT ts.schedule_type, ts.departure_location, ts.arrival_location,
               ts.departure_time, ts.status, ts.priority,
               t.identifier AS vehicle
        FROM transport_schedule ts
        LEFT JOIN transport t ON t.id = ts.transport_id
        WHERE ts.departure_time >= CURRENT_DATE - 7
        ORDER BY ts.departure_time DESC LIMIT 10
    """)).fetchall()
    return {
        "vehicles": [_safe(r) for r in vehicles],
        "schedules": [_safe(r) for r in schedules],
    }


# ── Meeting Rooms ──────────────────────────────────────────────────────────────

def _meeting_rooms(args, db):
    rooms = db.execute(text("""
        SELECT mr.room_name, mr.capacity, mr.location,
               mr.require_approval, mr.is_emergency_assembly,
               CASE mr.status WHEN 0 THEN 'Available' WHEN 1 THEN 'In Use'
                              WHEN 2 THEN 'Maintenance' ELSE 'Unknown' END AS status
        FROM mtg_room mr ORDER BY mr.room_name
    """)).fetchall()
    bookings = db.execute(text("""
        SELECT mb.title, mb.start_time, mb.end_time,
               mr.room_name, mb.attendee_count,
               CASE mb.status WHEN 0 THEN 'Pending' WHEN 1 THEN 'Approved'
                              WHEN 2 THEN 'Rejected' WHEN 3 THEN 'Completed'
                              ELSE 'Unknown' END AS status
        FROM mtg_booking mb
        LEFT JOIN mtg_room mr ON mr.id = mb.room_id
        WHERE mb.start_time >= CURRENT_DATE - 7
        ORDER BY mb.start_time DESC LIMIT 10
    """)).fetchall()
    return {
        "rooms": [_safe(r) for r in rooms],
        "recent_bookings": [_safe(r) for r in bookings],
    }


# ── Training ───────────────────────────────────────────────────────────────────

def _training(args, db):
    courses = db.execute(text("""
        SELECT tc.course_code, tc.course_name, tc.category,
               tc.duration_hours, tc.is_mandatory, tc.valid_period_months,
               (SELECT COUNT(*) FROM training_enrollment te
                WHERE te.course_id = tc.id) AS enrollments,
               (SELECT COUNT(*) FROM training_enrollment te
                WHERE te.course_id = tc.id AND te.status = 'certified') AS certified
        FROM training_courses tc ORDER BY tc.is_mandatory DESC, tc.course_name
    """)).fetchall()
    enrollments = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               tc.course_name, te.status, te.enrollment_date,
               te.completion_date, te.score, te.expiry_date
        FROM training_enrollment te
        LEFT JOIN training_courses tc ON tc.id = te.course_id
        LEFT JOIN personnel p ON p.id = te.personnel_id
        ORDER BY te.enrollment_date DESC LIMIT 20
    """)).fetchall()
    return {
        "courses": [_safe(r) for r in courses],
        "enrollments": [_safe(r) for r in enrollments],
    }


# ── Security & Anomalies ───────────────────────────────────────────────────────

def _anomaly_alerts(args, db):
    limit = min(args.get("limit", 20) or 20, 50)
    start = args.get("start_date")
    end   = args.get("end_date")
    if start:
        date_cond = "t.punch_time::date BETWEEN :start AND :end"
        params = {"start": start, "end": end or start, "lim": limit}
    else:
        days = args.get("days", 7) or 7
        date_cond = "t.punch_time >= CURRENT_DATE - (:days * INTERVAL '1 day')"
        params = {"days": days, "lim": limit}
    rows = db.execute(text(f"""
        SELECT
            COALESCE(NULLIF(TRIM(p.first_name||' '||COALESCE(p.last_name,'')),'' ), t.emp_code) AS name,
            t.emp_code, t.punch_time, t.terminal_sn,
            CASE WHEN EXTRACT(HOUR FROM t.punch_time) NOT BETWEEN 5 AND 23
                 THEN 'UNUSUAL_HOUR' ELSE 'FLAGGED' END AS anomaly_type
        FROM iclock_transaction t
        LEFT JOIN personnel p ON (t.emp_code = p.emp_code OR t.emp_code = p.badge_id)
        WHERE {date_cond}
          AND EXTRACT(HOUR FROM t.punch_time) NOT BETWEEN 5 AND 23
        ORDER BY t.punch_time DESC LIMIT :lim
    """), params).fetchall()
    return {"count": len(rows), "alerts": [_safe(r) for r in rows]}


# ── Notifications ──────────────────────────────────────────────────────────────

def _notifications(args, db):
    rows = db.execute(text("""
        SELECT title, message, notification_type, priority, is_read, created_at
        FROM sys_notifications
        ORDER BY created_at DESC LIMIT 10
    """)).fetchall()
    unread = db.execute(text(
        "SELECT COUNT(*) FROM sys_notifications WHERE NOT is_read"
    )).scalar()
    return {"unread": unread, "notifications": [_safe(r) for r in rows]}
