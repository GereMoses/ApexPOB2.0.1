"""
Scheduled reports.

A schedule = a report (report_code) + saved filters + a frequency + recipients. The
beat job (mustering_celery_tasks.run_due_report_schedules) runs due schedules: it builds
the file with ExportService, emails it when SMTP is configured, and records the outcome
(last_status / last_error / last_file_path) so the file can also be downloaded from the
Scheduled reports list.

Frequencies are stored in rpt_schedule.cron in standard cron form, limited to:
  "M H * * *"   daily at H:M
  "M H * * D"   weekly on ISO weekday D (1 = Monday … 7 = Sunday) at H:M
  "M H 1 * *"   monthly on the 1st at H:M
all in SITE time.

Date filters are saved RELATIVE (e.g. "yesterday", "last 7 days") and resolved at
run time — a schedule that always reported the day it was created would be useless.
"""
import logging
import os
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

FORMAT_MIME = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _site_tz():
    from .attendance_calculation_service import SITE_TZ
    return SITE_TZ


def make_cron(frequency: str, at: str, weekday: Optional[int] = None) -> str:
    h, m = (int(x) for x in (at or "07:00").split(":")[:2])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("time must be HH:MM")
    if frequency == "daily":
        return f"{m} {h} * * *"
    if frequency == "weekly":
        d = int(weekday or 1)
        if not 1 <= d <= 7:
            raise ValueError("weekday must be 1 (Monday) … 7 (Sunday)")
        return f"{m} {h} * * {d}"
    if frequency == "monthly":
        return f"{m} {h} 1 * *"
    raise ValueError("frequency must be daily, weekly or monthly")


def describe_cron(cron: str) -> Dict[str, Any]:
    m, h, dom, _mon, dow = cron.split()
    at = f"{int(h):02d}:{int(m):02d}"
    if dom == "1":
        return {"frequency": "monthly", "time": at, "label": f"Monthly on the 1st at {at}"}
    if dow != "*":
        day = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][int(dow) - 1]
        return {"frequency": "weekly", "time": at, "weekday": int(dow), "label": f"Every {day} at {at}"}
    return {"frequency": "daily", "time": at, "label": f"Every day at {at}"}


def next_run(cron: str, after: Optional[datetime] = None) -> datetime:
    """Next run strictly after `after`, computed in site time. Returned as NAIVE UTC —
    rpt_schedule's columns are timestamp-without-zone holding UTC, and an aware value
    would be cast through the session time zone (reports set it to site time)."""
    tz = _site_tz()
    after = (after or datetime.now(timezone.utc)).astimezone(tz)
    m, h, dom, _mon, dow = cron.split()
    m, h = int(m), int(h)
    day = after.date()
    for _ in range(400):
        cand = datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
        ok = (dom == "1" and day.day == 1) or (dom == "*" and (dow == "*" or day.isoweekday() == int(dow)))
        if ok and cand > after:
            return cand.astimezone(timezone.utc).replace(tzinfo=None)
        day += timedelta(days=1)
    raise ValueError(f"cannot compute next run for {cron!r}")


def resolve_filters(saved: Dict[str, Any], today: Optional[date] = None) -> Dict[str, Any]:
    """Turn saved {date_mode, relative, ...fixed filters} into the report's filters."""
    today = today or datetime.now(_site_tz()).date()
    f = {k: v for k, v in (saved or {}).items() if k not in ("date_mode", "relative")}
    mode, rel = (saved or {}).get("date_mode"), (saved or {}).get("relative") or ""
    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    ranges = {
        "today": (today, today),
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "7d": (today - timedelta(days=6), today),
        "30d": (today - timedelta(days=29), today),
        "month": (first_this_month, today),
        "last_month": (last_month_end.replace(day=1), last_month_end),
        "last_week": (today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 1)),
    }
    if mode == "range":
        a, b = ranges.get(rel, ranges["7d"])
        f["date_from"], f["date_to"] = a.isoformat(), b.isoformat()
    elif mode == "single":
        a, _ = ranges.get(rel, ranges["yesterday"])
        f["date"] = a.isoformat()
    elif mode == "month":
        d = last_month_end if rel == "last_month" else today
        f["month"] = d.strftime("%Y-%m")
    elif mode == "monthNumber":
        f["month"] = (last_month_end if rel == "last_month" else today).month
    return f


def run_schedule(db: Session, sched, title: Optional[str] = None) -> Dict[str, Any]:
    """Build the file, email it (if SMTP is set up and there are recipients), record it."""
    from ..models.report import ReportExportLog
    from .export_service import ExportService
    from .notify_email import send_email, smtp_configured

    code = sched.report_code or (sched.template.report_code if sched.template else None)
    saved = (sched.template.filters if sched.template else None) or {}
    filters = resolve_filters(saved)
    fmt = (sched.format or "xlsx").lower()
    title = title or sched.schedule_name
    now = datetime.now(timezone.utc)
    log = ReportExportLog(template_id=sched.template_id, user_id=sched.created_by, format=fmt,
                          filters=filters, status="pending")
    db.add(log)
    db.commit()
    db.refresh(log)
    result: Dict[str, Any] = {"schedule_id": sched.id}
    try:
        path = ExportService(db).generate_export(log.id, code, filters, fmt)
        sched.last_file_path = path
        sched.last_rows = log.row_count
        emails = [e for e in ((sched.recipients or {}).get("emails") or []) if e]
        if emails and smtp_configured():
            with open(path, "rb") as fh:
                data = fh.read()
            stamp = datetime.now(_site_tz()).strftime("%Y-%m-%d")
            fname = f"{title}_{stamp}.{fmt}".replace(" ", "_")
            period = filters.get("date") or (f"{filters.get('date_from')} to {filters.get('date_to')}"
                                              if filters.get("date_from") else filters.get("month") or "current")
            sent = send_email(emails, f"[ApexPOB] {title} — {period}",
                              f"<p>Attached: <b>{title}</b> ({period}), {log.row_count or 0} rows.</p>"
                              f"<p style='color:#64748b'>Scheduled report from ApexPOB.</p>",
                              f"Attached: {title} ({period}), {log.row_count or 0} rows.",
                              attachments=[(fname, data, FORMAT_MIME[fmt])])
            sched.last_status = "emailed" if sent.get("sent") else "email_failed"
            sched.last_error = None if sent.get("sent") else (sent.get("error") or f"failed: {sent.get('failed')}")
        else:
            sched.last_status = "ok"
            sched.last_error = None if emails == [] else "Email not configured (Settings → Email) — file kept for download"
        result.update(status=sched.last_status, rows=log.row_count)
    except Exception as e:
        logger.error("Scheduled report %s (%s) failed: %s", sched.id, code, e)
        sched.last_status = "failed"
        sched.last_error = str(e)[:500]
        result.update(status="failed", error=str(e))
    sched.last_run = now.replace(tzinfo=None)
    sched.next_run = next_run(sched.cron, now)
    db.commit()
    return result


def run_due(db: Session) -> int:
    from ..models.report import ReportSchedule
    now = datetime.now(timezone.utc)
    due = (db.query(ReportSchedule)
           .filter(ReportSchedule.is_active.is_(True), ReportSchedule.report_code.isnot(None),
                   ReportSchedule.next_run <= now.replace(tzinfo=None))
           .all())
    for s in due:
        run_schedule(db, s)
    return len(due)


def file_exists(path: Optional[str]) -> bool:
    return bool(path) and os.path.exists(path)
