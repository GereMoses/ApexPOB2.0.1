"""
BioTime 9.5 Compatible Attendance Calculation Engine
Processes iclock_transaction data into att_report records.

Calculation logic mirrors BioTime 9.5:
  - Punch classification uses configurable CI/CO windows, not a fixed midpoint
  - State-255 (auto-detect) punches alternate IN→OUT→IN using window context
  - All IN/OUT pairs per day are summed (break gaps excluded automatically)
  - Break deduction applied when total work exceeds threshold
  - Overnight shifts handled correctly
  - Pre/Post overtime tracked separately
"""
import asyncio
import logging
import datetime as dt
from datetime import datetime, timedelta, time, date
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

DAY_ABBREVS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

STATUS_PRESENT = 0
STATUS_LATE    = 1
STATUS_EARLY   = 2
STATUS_ABSENT  = 3
STATUS_LEAVE   = 4

DIR_IN  = 'in'
DIR_OUT = 'out'

# punch_state values → direction (explicit device states)
_EXPLICIT_DIR: Dict[int, str] = {
    0: DIR_IN,   # check-in
    1: DIR_OUT,  # check-out
    2: DIR_OUT,  # break-out
    3: DIR_IN,   # break-in
    4: DIR_IN,   # OT-in
    5: DIR_OUT,  # OT-out
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_time(val) -> Optional[time]:
    """Normalise a DB value to a time object (handles string, time, timedelta)."""
    if val is None:
        return None
    if isinstance(val, time):
        return val
    if isinstance(val, timedelta):
        total = int(val.total_seconds())
        return time(total // 3600, (total % 3600) // 60)
    if isinstance(val, str):
        parts = val.split(':')
        return time(int(parts[0]), int(parts[1]))
    return val


# Shift times (07:00-19:00) are SITE wall-clock times, but punches are stored as UTC
# instants (readers run on UTC). Every punch must be converted to site time before it
# is compared with a shift, bucketed into a day, or measured for lateness — stripping
# the tz from the UTC value (the previous behaviour) put every Lagos punch an hour
# early: wrong late/early/overtime, and evening punches on the wrong day near midnight.
import os as _os
from zoneinfo import ZoneInfo as _ZoneInfo
try:
    SITE_TZ = _ZoneInfo(_os.getenv("SITE_TIME_ZONE", "Africa/Lagos"))
except Exception:  # bad value must not stop attendance; fall back to Lagos
    SITE_TZ = _ZoneInfo("Africa/Lagos")


def _naive(ts) -> Optional[datetime]:
    """Site-local wall-clock time, tz stripped. Naive input is assumed already local."""
    if ts is None:
        return None
    if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
        return ts.astimezone(SITE_TZ).replace(tzinfo=None)
    return ts


def _t2m(t: time) -> int:
    """Convert time → minutes since midnight."""
    return t.hour * 60 + t.minute


def _m2t(mins: int) -> time:
    """Convert minutes since midnight → time, wrapping at 1440."""
    mins = mins % 1440
    return time(mins // 60, mins % 60)


def _in_window(t: Optional[time], win_start: time, win_end: time) -> bool:
    """True if t falls within [win_start, win_end], handles midnight wrap."""
    if t is None:
        return False
    if win_start <= win_end:
        return win_start <= t <= win_end
    # Window spans midnight  (e.g. 22:00 – 02:00)
    return t >= win_start or t <= win_end


def _is_work_day(work_days: Optional[str], day: date) -> bool:
    """Support both 'Mon,Tue,…' text and BioTime numeric '12345' formats."""
    if not work_days:
        return True
    abbr  = DAY_ABBREVS[day.weekday()]
    digit = str(day.weekday() + 1)           # 1=Mon … 7=Sun
    if any(c.isalpha() for c in work_days):
        return abbr in work_days
    return digit in work_days


# ── Core pairing functions ────────────────────────────────────────────────────

def _classify_punches(
    punches,
    ci_begin: time,
    ci_end:   time,
    co_begin: time,
    co_end:   time,
    min_work_minutes: int = 30,
    allow_multiple_checkins: bool = True,
    ignore_device_state: bool = False,
) -> List[Tuple]:
    """
    Classify each punch as DIR_IN or DIR_OUT.

    Priority order:
      1. Explicit state (0/1/2/3/4/5) → use _EXPLICIT_DIR directly.
         - If allow_multiple_checkins=False and the punch is an explicit IN
           arriving within min_work_minutes of the last confirmed IN, it is
           treated as a duplicate and skipped (None returned for that slot).
      2. Auto-detect (state=255 or unknown):
           a. If a confirmed IN exists and elapsed time < min_work_minutes
              → still IN (grace period, duplicate tap).
           b. If a confirmed IN exists and elapsed time >= min_work_minutes
              → OUT (employee has worked the minimum gap; treat as clock-out).
           c. No prior IN: use shift time windows (CI/CO) to decide.
              - Only in CI window → IN
              - Only in CO window → OUT
              - Ambiguous → alternate from last direction (first punch = IN)

    Returns [(punch_time, direction), ...]  — duplicates are omitted entirely.
    """
    result: List[Tuple] = []
    last_dir:     Optional[str]      = None
    last_in_time: Optional[datetime] = None

    for p in punches:
        # ignore_device_state: the reader's In/Out key is not trusted (staff don't press
        # it, or the reader auto-switches state by time of day), so every punch goes
        # through auto-detect: first tap = IN, a tap after the minimum gap = OUT.
        state    = None if ignore_device_state else p.punch_state
        pt_naive = _naive(p.punch_time)

        if state in _EXPLICIT_DIR:
            direction = _EXPLICIT_DIR[state]

            # Deduplicate close explicit IN punches when multiple check-ins are off
            if direction == DIR_IN and not allow_multiple_checkins and last_in_time is not None:
                elapsed = (pt_naive - last_in_time).total_seconds() / 60 if pt_naive else 0
                if elapsed < min_work_minutes:
                    continue  # drop duplicate IN within grace period

        else:
            # Auto-detect (state=255 or unknown)
            if last_in_time is not None and pt_naive is not None:
                elapsed = (pt_naive - last_in_time).total_seconds() / 60
                if elapsed < min_work_minutes:
                    continue  # within grace period → duplicate tap, drop entirely
                else:
                    direction = DIR_OUT  # past grace period → treat as check-out
            else:
                # No prior IN yet — use shift time windows
                pt_time = pt_naive.time() if pt_naive else None
                in_ci   = _in_window(pt_time, ci_begin, ci_end)
                in_co   = _in_window(pt_time, co_begin, co_end)

                if in_ci and not in_co:
                    direction = DIR_IN
                elif in_co and not in_ci:
                    direction = DIR_OUT
                else:
                    direction = DIR_IN if (last_dir is None or last_dir == DIR_OUT) else DIR_OUT

        result.append((p.punch_time, direction))
        last_dir = direction
        if direction == DIR_IN:
            last_in_time = pt_naive
        elif direction == DIR_OUT:
            last_in_time = None  # reset: next IN starts a new pair

    return result


def min_work_minutes(db) -> int:
    """att_rules.min_work_minutes_for_checkout — a tap closer than this to the day's
    first tap is a repeat tap, not a clock-out. Shared by every screen that labels taps."""
    try:
        v = db.execute(text("SELECT rule_value FROM att_rules WHERE rule_key = 'min_work_minutes_for_checkout'")).scalar()
        return int(v) if v not in (None, "") else 30
    except Exception:
        db.rollback()
        return 30


def _first_in_last_out(punches, min_work_minutes: int = 30) -> List[Tuple]:
    """The site standard: the day's FIRST punch is the clock-in and its LAST punch the
    clock-out, whatever In/Out key the reader recorded. A last punch closer than
    min_work_minutes to the first is a repeat tap, not a clock-out."""
    if not punches:
        return []
    first, last = punches[0], punches[-1]
    out = [(first.punch_time, DIR_IN)]
    if last is not first:
        gap = (_naive(last.punch_time) - _naive(first.punch_time)).total_seconds() / 60
        if gap >= min_work_minutes:
            out.append((last.punch_time, DIR_OUT))
    return out


def _pair_punches(classified: List[Tuple]) -> List[Tuple]:
    """
    Pair sequential IN/OUT punches, matching BioTime 9.5 pairing behaviour:
      - IN followed by OUT → complete pair (in_time, out_time)
      - Two consecutive INs → close first with no out, start new open pair
      - OUT with no preceding IN → record as (None, out_time)
      - Unclosed IN at end of list → record as (in_time, None)  [still at work]

    Returns [(in_time, out_time), ...]  — either value may be None.
    """
    pairs: List[Tuple] = []
    open_in = None

    for punch_time, direction in classified:
        if direction == DIR_IN:
            if open_in is not None:
                pairs.append((open_in, None))  # consecutive INs: close first
            open_in = punch_time
        else:  # OUT
            if open_in is not None:
                pairs.append((open_in, punch_time))
                open_in = None
            else:
                pairs.append((None, punch_time))  # OUT with no preceding IN

    if open_in is not None:
        pairs.append((open_in, None))             # still at work / no clock-out

    return pairs


def _sum_work_minutes(
    pairs: List[Tuple],
    break_deduction_after_hours: float,
    break_deduction_mins: int,
) -> int:
    """
    Sum durations of all complete IN→OUT pairs.
    Then apply break deduction if total work exceeds the threshold.
    Incomplete pairs (missing IN or OUT) contribute nothing.
    """
    total = 0
    for in_t, out_t in pairs:
        if in_t and out_t:
            ci = _naive(in_t)
            co = _naive(out_t)
            if ci and co and co > ci:
                total += int((co - ci).total_seconds() / 60)

    if break_deduction_mins > 0 and total >= int(break_deduction_after_hours * 60):
        total = max(0, total - break_deduction_mins)

    return total


# ── Shift fallback helpers ────────────────────────────────────────────────────

def _shift_to_sched(row) -> Optional[dict]:
    """Convert a raw att_shift / att_timetable row into the same dict shape
    that _process_employee expects from att_schedule + JOIN."""
    if not row:
        return None
    m = row._mapping if hasattr(row, '_mapping') else row
    return {
        "shift_id":          m.get("id") or m.get("shift_id"),
        "shift_name":        m.get("name") or m.get("shift_name"),
        "timetable_id":      m.get("timetable_id"),
        "start_time":        m.get("start_time"),
        "end_time":          m.get("end_time"),
        "days_of_week":      m.get("days_of_week") or m.get("work_days") or "Mon,Tue,Wed,Thu,Fri",
        "late_grace_minutes": m.get("grace_period_minutes"),
        "early_exit_minutes": m.get("max_early_departure_minutes"),
        # sentinel so callers know this came from a fallback, not a direct assignment
        "_is_fallback": True,
    }


def _fetch_default_schedule(db: Session, dept_id: Optional[int], global_shift_id: Optional[int]) -> Optional[dict]:
    """
    Return a fallback schedule dict for an employee with no direct att_schedule entry.

    Lookup order:
      1. departments.default_shift_id  (if dept_id is provided — references the main departments table)
      2. global_shift_id from att_rules
    """
    shift_id = None

    if dept_id:
        row = db.execute(text(
            "SELECT default_shift_id FROM departments WHERE id = :id"
        ), {"id": dept_id}).fetchone()
        if row and row.default_shift_id:
            shift_id = row.default_shift_id

    if not shift_id and global_shift_id:
        shift_id = int(global_shift_id)

    if not shift_id:
        return None

    shift = db.execute(text("""
        SELECT s.id, s.name,
               s.timetable_id,
               COALESCE(s.days_of_week, s.work_days, 'Mon,Tue,Wed,Thu,Fri') AS days_of_week,
               COALESCE(t.start_time, s.start_time)                          AS start_time,
               COALESCE(t.end_time,   s.end_time)                            AS end_time,
               COALESCE(s.grace_period_minutes, t.late_grace_minutes)        AS grace_period_minutes,
               COALESCE(s.max_early_departure_minutes, t.early_exit_minutes) AS max_early_departure_minutes
        FROM att_shift s
        LEFT JOIN att_timetable t ON s.timetable_id = t.id
        WHERE s.id = :id
    """), {"id": shift_id}).fetchone()

    return _shift_to_sched(shift)


# ── Service class ─────────────────────────────────────────────────────────────

class AttendanceCalculationService:

    def _load_rules(self, db: Session) -> dict:
        try:
            rows = db.execute(text("SELECT rule_key, rule_value FROM att_rules")).fetchall()
            return {r.rule_key: r.rule_value for r in rows}
        except Exception:
            return {}

    async def calculate_attendance(
        self,
        emp_ids: Optional[List[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: Session = None,
    ) -> Dict[str, Any]:
        """Calculate attendance for a date range and persist results to att_report.

        All synchronous DB work runs in a thread-pool executor so the uvicorn
        event loop is never blocked — even for large employee sets or long date
        ranges triggered by device punches.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._calculate_sync, emp_ids, start_date, end_date, db
        )

    def _calculate_sync(
        self,
        emp_ids: Optional[List[int]],
        start_date: Optional[str],
        end_date: Optional[str],
        db: Session,
    ) -> Dict[str, Any]:
        """Synchronous core — runs in a thread pool, safe to block."""
        start_dt = dt.date.fromisoformat(start_date) if start_date else dt.date.today()
        end_dt   = dt.date.fromisoformat(end_date)   if end_date   else dt.date.today()

        rules = self._load_rules(db)

        if emp_ids:
            emp_rows = db.execute(text(
                "SELECT id, emp_code, department_id FROM personnel "
                "WHERE is_active = true AND id = ANY(:ids)"
            ), {"ids": emp_ids}).fetchall()
        else:
            emp_rows = db.execute(text(
                "SELECT id, emp_code, department_id FROM personnel "
                "WHERE is_active = true ORDER BY emp_code"
            )).fetchall()

        # Pre-fetch all personnel_employee IDs in one query to avoid N+1 per employee
        emp_codes = [emp.emp_code for emp in emp_rows]
        pe_id_map: dict = {}
        if emp_codes:
            placeholders = ",".join([f":c{i}" for i in range(len(emp_codes))])
            pe_params = {f"c{i}": c for i, c in enumerate(emp_codes)}
            pe_rows = db.execute(
                text(f"SELECT id, emp_code FROM personnel_employee WHERE emp_code IN ({placeholders})"),
                pe_params,
            ).fetchall()
            pe_id_map = {row.emp_code: row.id for row in pe_rows}

        processed, errors = 0, []
        for emp in emp_rows:
            try:
                emp_dict = dict(emp._mapping)
                emp_dict["_pe_id"] = pe_id_map.get(emp.emp_code)  # inject pre-fetched ID
                self._process_employee(emp_dict, start_dt, end_dt, db, rules)
                processed += 1
            except Exception as exc:
                errors.append({"emp_code": emp.emp_code, "error": str(exc)})
                logger.error(f"Attendance calc error for {emp.emp_code}: {exc}")

        db.commit()
        logger.info(
            f"Attendance calculated: {processed} employees, "
            f"{start_dt}–{end_dt}, {len(errors)} errors"
        )
        return {
            "processed": processed,
            "date_range": {"start": start_dt.isoformat(), "end": end_dt.isoformat()},
            "errors": errors,
        }

    def _process_employee(
        self,
        emp: dict,
        start_dt: date,
        end_dt: date,
        db: Session,
        rules: dict = None,
    ):
        emp_code = emp["emp_code"]

        # Fetch active schedules covering the date range
        schedules = db.execute(text("""
            SELECT sc.shift_id, sc.start_date, sc.end_date,
                   sh.name AS shift_name,
                   COALESCE(sh.days_of_week, sh.work_days) AS days_of_week,
                   sh.timetable_id,
                   COALESCE(t.start_time, sh.start_time)                             AS start_time,
                   COALESCE(t.end_time,   sh.end_time)                               AS end_time,
                   COALESCE(t.late_grace_minutes,  sh.grace_period_minutes,       15) AS late_grace_minutes,
                   COALESCE(t.early_exit_minutes,  sh.max_early_departure_minutes, 30) AS early_exit_minutes
            FROM att_schedule sc
            JOIN att_shift    sh ON sc.shift_id    = sh.id
            LEFT JOIN att_timetable t ON sh.timetable_id = t.id
            WHERE sc.emp_code   = :emp_code
              AND sc.start_date <= :end_date
              AND (sc.end_date IS NULL OR sc.end_date >= :start_date)
            ORDER BY sc.start_date DESC
        """), {"emp_code": emp_code, "start_date": start_dt, "end_date": end_dt}).fetchall()
        schedules = [dict(r._mapping) for r in schedules]

        # All punches in the date range, ordered chronologically
        # Time & Attendance and access control are SEPARATE domains in ApexPOB.
        # Only punches from ATTENDANCE-purpose readers may contribute to worked
        # hours; door, zone, muster and emergency readers are access control and
        # must never reach payroll. Without this filter an access-control exit
        # swipe made hours after the employee left the gate is classified as the
        # day's check-out and silently inflates the timesheet.
        #
        # Terminals that are unregistered or have no purpose set are treated as
        # ATTENDANCE — that is the iclock_terminal.reader_purpose column default,
        # so an existing deployment cannot suddenly compute zero hours.
        punch_rows = db.execute(text("""
            SELECT t.punch_time, t.punch_state
            FROM iclock_transaction t
            LEFT JOIN iclock_terminal term ON term.sn = t.terminal_sn
            WHERE t.emp_code = :emp_code
              AND t.punch_time BETWEEN CAST(:start_date AS date) - INTERVAL '1 day'
                                   AND CAST(:end_date AS date) + INTERVAL '1 day'
              AND COALESCE(NULLIF(term.reader_purpose, ''), 'ATTENDANCE') = 'ATTENDANCE'
            ORDER BY t.punch_time
        """), {"emp_code": emp_code, "start_date": start_dt,
               # +1 day: an overnight shift starting on end_dt clocks out the
               # following morning, so that punch must be in the fetch window or
               # the last night of the range computes as zero hours.
               "end_date": end_dt + timedelta(days=1)}).fetchall()

        punches_by_date: Dict[date, list] = {}
        for p in punch_rows:
            d = _naive(p.punch_time).date()     # site-local calendar day
            punches_by_date.setdefault(d, []).append(p)

        # Use pre-fetched ID when available (injected by batch caller); fall back to query
        pe_id = emp.get("_pe_id")
        if pe_id is None:
            pe = db.execute(
                text("SELECT id FROM personnel_employee WHERE emp_code = :code"),
                {"code": emp_code},
            ).fetchone()
            if not pe:
                return
            pe_id = pe.id
        dept_id = emp.get("department_id")
        r       = rules or {}

        # ── Rules from att_rules ──────────────────────────────────────────────
        ci_before       = int(r.get('checkin_window_minutes_before')  or 120)
        ci_after        = int(r.get('checkin_window_minutes_after')   or 240)
        co_before       = int(r.get('checkout_window_minutes_before') or 240)
        co_after        = int(r.get('checkout_window_minutes_after')  or 120)
        break_after     = float(r.get('break_deduction_after')        or 6)
        break_mins      = int(r.get('break_deduction_minutes')        or 0)
        # New rules: grace-period-based punch direction + duplicate suppression
        min_work_mins   = int(r.get('min_work_minutes_for_checkout')  or 30)
        allow_multi_ci  = str(r.get('allow_multiple_checkins') or 'true').lower() != 'false'
        # first_last (default) = first punch IN, last punch OUT;
        # device = trust the reader's In/Out key; auto = shift-window detection.
        state_mode      = str(r.get('punch_state_mode') or 'first_last').lower()
        ignore_state    = state_mode == 'auto'
        # Global grace fallbacks (used when the shift/timetable doesn't specify)
        global_late_grace  = int(r.get('grace_period_minutes')        or 15)
        global_early_grace = int(r.get('early_departure_threshold')   or 30)
        global_shift_id    = r.get('default_shift_id')

        # ── Fallback schedule: dept default → global default ─────────────────
        fallback_sched = _fetch_default_schedule(db, dept_id, global_shift_id)

        # Punches already claimed as the clock-out of a preceding overnight shift.
        # Without this a night worker's 07:00 exit would be counted twice: once
        # closing the night that started the evening before, and again as a stray
        # punch on its own calendar date.
        consumed_overnight: set = set()

        cur = start_dt
        while cur <= end_dt:
            sched = _schedule_for_day(schedules, cur) or fallback_sched
            if not sched:
                cur += timedelta(days=1)
                continue

            work_days = sched.get("days_of_week") or "Mon,Tue,Wed,Thu,Fri"
            if not _is_work_day(work_days, cur):
                cur += timedelta(days=1)
                continue

            start_t = _to_time(sched["start_time"])
            end_t   = _to_time(sched["end_time"])
            if not start_t or not end_t:
                cur += timedelta(days=1)
                continue

            # Grace periods: prefer shift/timetable value, fall back to global att_rules
            late_grace  = int(sched.get("late_grace_minutes")  or global_late_grace)
            early_grace = int(sched.get("early_exit_minutes")  or global_early_grace)

            # ── Scheduled minutes (overnight-safe) ───────────────────────────
            sched_in_dt  = datetime.combine(cur, start_t)
            sched_out_dt = datetime.combine(cur, end_t)
            if sched_out_dt <= sched_in_dt:          # overnight shift
                sched_out_dt += timedelta(days=1)
            sched_mins = int((sched_out_dt - sched_in_dt).total_seconds() / 60)

            # ── BioTime-style detection windows ──────────────────────────────
            s_mins = _t2m(start_t)
            e_mins = _t2m(end_t)
            is_overnight = e_mins <= s_mins
            if is_overnight:                         # overnight shift
                e_mins += 1440

            ci_begin = _m2t((s_mins - ci_before) % 1440)
            ci_end   = _m2t((s_mins + ci_after)  % 1440)
            co_begin = _m2t((e_mins - co_before) % 1440)
            co_end   = _m2t((e_mins + co_after)  % 1440)

            # Punches are bucketed by calendar date, but an overnight shift ends
            # on the FOLLOWING date. Pull the next morning's punches (up to the
            # close of this shift's check-out window) into this business day, or
            # the evening IN and morning OUT never pair and the night is scored
            # as zero hours worked. Anything pulled in is marked consumed so the
            # next iteration does not count it a second time.
            day_punches = [p for p in punches_by_date.get(cur, [])
                           if p.punch_time not in consumed_overnight]
            if is_overnight:
                for p in punches_by_date.get(cur + timedelta(days=1), []):
                    pt = _naive(p.punch_time)
                    if pt and pt.time() <= co_end:
                        day_punches.append(p)
                        consumed_overnight.add(p.punch_time)
                day_punches.sort(key=lambda p: p.punch_time)

            # ── Classify and pair punches ─────────────────────────────────────
            if state_mode == 'first_last':
                classified = _first_in_last_out(day_punches, min_work_mins)
            else:
                classified = _classify_punches(
                    day_punches, ci_begin, ci_end, co_begin, co_end,
                    min_work_minutes=min_work_mins,
                    allow_multiple_checkins=allow_multi_ci,
                    ignore_device_state=ignore_state,
                )
            pairs = _pair_punches(classified)

            # First IN and last OUT across all pairs → stored as check_in/check_out
            check_in  = next((in_t  for in_t,  _     in pairs          if in_t  is not None), None)
            check_out = next((out_t for _,     out_t  in reversed(pairs) if out_t is not None), None)

            # ── Work time: first-in to last-out ──────────────────────────────────
            # Duplicate/accidental repeat punches have no effect — only the
            # chronological first IN and last OUT of the day determine work hours.
            work_mins  = 0
            late_mins  = 0
            early_mins = 0
            ot_mins    = 0

            ci_naive = _naive(check_in)  if check_in  else None
            co_naive = _naive(check_out) if check_out else None

            if ci_naive and co_naive and co_naive > ci_naive:
                total = int((co_naive - ci_naive).total_seconds() / 60)
                if break_mins > 0 and total >= int(break_after * 60):
                    total = max(0, total - break_mins)
                work_mins = total

            if ci_naive and ci_naive > sched_in_dt + timedelta(minutes=late_grace):
                late_mins = int((ci_naive - sched_in_dt).total_seconds() / 60)

            if co_naive and co_naive < sched_out_dt - timedelta(minutes=early_grace):
                early_mins = int((sched_out_dt - co_naive).total_seconds() / 60)

            ot_mins = max(0, work_mins - sched_mins)

            # ── Status (mirrors BioTime exception priority) ───────────────────
            if not day_punches:
                att_status = STATUS_ABSENT
            elif late_mins > 0 and early_mins > 0:
                att_status = STATUS_LATE      # late-in takes priority when both
            elif late_mins > 0:
                att_status = STATUS_LATE
            elif early_mins > 0:
                att_status = STATUS_EARLY
            else:
                att_status = STATUS_PRESENT

            # ── Persist ───────────────────────────────────────────────────────
            db.execute(text("""
                INSERT INTO att_report
                    (emp_id, att_date, shift_id, timetable_id,
                     check_in, check_out,
                     work_minutes, late_minutes, early_minutes,
                     ot_minutes, overtime_minutes,
                     att_status, area_compliance, department_id, scheduled_minutes)
                VALUES
                    (:emp_id, :att_date, :shift_id, :timetable_id,
                     :check_in, :check_out,
                     :work_mins, :late_mins, :early_mins,
                     :ot_mins, :ot_mins,
                     :att_status, true, :dept_id, :sched_mins)
                ON CONFLICT (emp_id, att_date) DO UPDATE SET
                    shift_id          = EXCLUDED.shift_id,
                    timetable_id      = EXCLUDED.timetable_id,
                    check_in          = EXCLUDED.check_in,
                    check_out         = EXCLUDED.check_out,
                    work_minutes      = EXCLUDED.work_minutes,
                    late_minutes      = EXCLUDED.late_minutes,
                    early_minutes     = EXCLUDED.early_minutes,
                    ot_minutes        = EXCLUDED.ot_minutes,
                    overtime_minutes  = EXCLUDED.overtime_minutes,
                    att_status        = EXCLUDED.att_status,
                    department_id     = EXCLUDED.department_id,
                    scheduled_minutes = EXCLUDED.scheduled_minutes,
                    updated_at        = CURRENT_TIMESTAMP
            """), {
                "emp_id":       pe_id,
                "att_date":     cur,
                "shift_id":     sched["shift_id"],
                "timetable_id": sched["timetable_id"],
                "check_in":     check_in,
                "check_out":    check_out,
                "work_mins":    work_mins,
                "late_mins":    late_mins,
                "early_mins":   early_mins,
                "ot_mins":      ot_mins,
                "att_status":   att_status,
                "dept_id":      dept_id,
                "sched_mins":   sched_mins,
            })
            cur += timedelta(days=1)

    @staticmethod
    def _shift_midpoint(shift_start: Optional[time], shift_end: Optional[time]) -> Optional[time]:
        """Kept for any external callers; calculation engine no longer uses this."""
        if not shift_start or not shift_end:
            return None
        s = _t2m(shift_start)
        e = _t2m(shift_end)
        if e <= s:
            e += 1440
        mid = (s + e) // 2 % 1440
        return _m2t(mid)


# ── Module-level helpers (used by service and by _async_recalculate) ──────────

def _schedule_for_day(schedules: list, day: date) -> Optional[dict]:
    for s in schedules:
        sd = s["start_date"]
        ed = s["end_date"]
        if isinstance(sd, datetime):
            sd = sd.date()
        if isinstance(ed, datetime):
            ed = ed.date()
        if sd <= day and (ed is None or ed >= day):
            return s
    return None


attendance_calculation_service = AttendanceCalculationService()
