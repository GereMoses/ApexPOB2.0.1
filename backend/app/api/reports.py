"""
Report Export API — generate downloadable CSV and PDF reports.
"""
import csv
import io
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db
from ..core.dependencies import get_current_user


def _site_tz():
    from ..services.attendance_calculation_service import SITE_TZ
    return SITE_TZ


def _site_today() -> date:
    from datetime import datetime
    return datetime.now(_site_tz()).date()


def _site_session(db: Session) -> None:
    """Run this export in SITE time: times print as Lagos wall clock (they printed
    as UTC, e.g. 06:00:00+00:00 for a 07:00 tap) and dates follow the site's day."""
    db.execute(text("SELECT set_config('TimeZone', :tz, true)"), {"tz": getattr(_site_tz(), "key", "Africa/Lagos")})


# att_report.emp_id is personnel_employee.id (the reader mirror) — joining it straight
# to personnel.id only worked while the two ids happened to match. Status codes are
# 0 Present, 1 Late, 2 Early leave, 3 Absent, 4 Leave (2 was printed "Absent" and 3
# "Other").
_ATTENDANCE_SQL = """
    SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS name,
           p.emp_code, d.name AS department,
           r.att_date,
           to_char(r.check_in,  'YYYY-MM-DD HH24:MI') AS check_in,
           to_char(r.check_out, 'YYYY-MM-DD HH24:MI') AS check_out,
           ROUND(r.work_minutes / 60.0, 2) AS work_hours,
           r.late_minutes, r.ot_minutes,
           CASE r.att_status WHEN 0 THEN 'Present' WHEN 1 THEN 'Late' WHEN 2 THEN 'Early leave'
                             WHEN 3 THEN 'Absent'  WHEN 4 THEN 'Leave' ELSE 'Other' END AS status
    FROM att_report r
    JOIN personnel_employee pe ON pe.id = r.emp_id
    LEFT JOIN personnel p ON p.emp_code = pe.emp_code
    LEFT JOIN departments d ON d.id = COALESCE(r.department_id, p.department_id)
    WHERE r.att_date BETWEEN :start AND :end
    ORDER BY r.att_date DESC, p.first_name
    LIMIT :lim
"""

# Who is ON BOARD now, and where — the export used to list every active employee.
_POB_SQL = """
    SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS name,
           p.emp_code, d.name AS department, p.position, p.company,
           COALESCE(z.name, 'Location unknown') AS zone,
           to_char(p.pob_since, 'YYYY-MM-DD HH24:MI') AS pob_since,
           to_char(p.last_seen, 'YYYY-MM-DD HH24:MI') AS last_seen
    FROM personnel p
    LEFT JOIN departments d ON d.id = p.department_id
    LEFT JOIN zones z ON z.id = p.current_zone_id
    WHERE p.is_onboard = TRUE AND p.is_active = TRUE
    ORDER BY z.name NULLS LAST, p.first_name
    LIMIT 2000
"""

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


# ── PDF helpers ───────────────────────────────────────────────────────────────

def _pdf_response(pdf_bytes: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_PDF_PUNCT = {"\u2022": "-", "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
              "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2192": "->", "\u00a0": " "}


def _pdf_text(v) -> str:
    """fpdf2's built-in Helvetica is Latin-1 only; any other character (a bullet, an
    em dash, a Yoruba/Igbo diacritic in a name) raises FPDFUnicodeEncodingException and
    kills the whole export. Map common punctuation, fold accents where possible, and
    replace anything left with '?'."""
    import unicodedata
    s = "" if v is None else str(v)
    for k, r in _PDF_PUNCT.items():
        s = s.replace(k, r)
    try:
        s.encode("latin-1")
        return s
    except UnicodeEncodeError:
        pass
    folded = "".join(c if ord(c) < 256 else (unicodedata.normalize("NFKD", c)[:1] or "?")
                     for c in s)
    return folded.encode("latin-1", "replace").decode("latin-1")


def _build_pdf(title: str, subtitle: str, headers: list, rows: list,
               col_widths: list = None) -> bytes:
    """Build a simple tabular PDF with fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 not installed — run: pip install fpdf2")

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_fill_color(30, 42, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, _pdf_text(title), ln=True, fill=True, align='C')

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, _pdf_text(subtitle), ln=True, align='C')
    pdf.ln(3)

    # Column widths
    usable_w = 277  # A4 landscape usable width (mm)
    if col_widths is None:
        w = usable_w / len(headers) if headers else usable_w
        col_widths = [w] * len(headers)

    # Table header
    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, _pdf_text(h)[:30], border=1, fill=True, align='C')
    pdf.ln()

    # Rows
    pdf.set_font("Helvetica", "", 7)
    for ridx, row in enumerate(rows):
        pdf.set_fill_color(248, 249, 250) if ridx % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(40, 40, 40)
        for i, cell in enumerate(row):
            val = _pdf_text(cell)[:35]
            pdf.cell(col_widths[i], 6, val, border=1, fill=True)
        pdf.ln()

    # Footer
    pdf.set_y(-10)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, _pdf_text(f"Generated: {_site_today()}  \u2022  {len(rows)} record(s)"), align='C')

    return bytes(pdf.output())


_FORMULA_CHARS = ('=', '+', '-', '@', '\t', '\r')


def _safe_cell(v) -> str:
    """Neutralise CSV formula injection: prefix dangerous leading chars with a tab."""
    s = str(v) if v is not None else ""
    return ("\t" + s) if s and s[0] in _FORMULA_CHARS else s


def _csv_response(rows: list, headers: list, filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_safe_cell(v) for v in row])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/attendance/csv")
async def attendance_csv(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    start = start_date or (_site_today() - timedelta(days=7)).isoformat()
    end   = end_date   or _site_today().isoformat()
    _site_session(db)
    rows = db.execute(text(_ATTENDANCE_SQL), {"start": start, "end": end, "lim": 5000}).fetchall()
    return _csv_response(
        [[r.name, r.emp_code, r.department, r.att_date, r.check_in, r.check_out,
          r.work_hours, r.late_minutes, r.ot_minutes, r.status] for r in rows],
        ["Name", "Emp Code", "Department", "Date", "Check In", "Check Out",
         "Work Hours", "Late Mins", "OT Mins", "Status"],
        f"attendance_{start}_{end}.csv",
    )


@router.get("/compliance/csv")
async def compliance_csv(
    days: int = Query(default=60),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    cutoff = (_site_today() + timedelta(days=days)).isoformat()
    rows = db.execute(text("""
        SELECT (c.first_name||' '||c.last_name) AS name,
               c.contractor_code, v.vendor_name AS vendor,
               c.work_permit_expiry, c.medical_clearance_status,
               c.background_check_status, c.status
        FROM contractors c
        LEFT JOIN vendors v ON v.id = c.vendor_id
        WHERE c.status = 'ACTIVE'
          AND (c.work_permit_expiry::date <= :cutoff OR c.medical_clearance_status IN ('FAILED','PENDING'))
        ORDER BY c.work_permit_expiry NULLS LAST
        LIMIT 1000
    """), {"cutoff": cutoff}).fetchall()
    return _csv_response(
        [[r.name, r.contractor_code, r.vendor, r.work_permit_expiry,
          r.medical_clearance_status, r.background_check_status, r.status] for r in rows],
        ["Name", "Contractor Code", "Vendor", "Permit Expiry",
         "Medical Status", "Background Check", "Status"],
        "compliance_report.csv",
    )


@router.get("/pob/csv")
async def pob_csv(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _site_session(db)
    rows = db.execute(text(_POB_SQL)).fetchall()
    return _csv_response(
        [[r.name, r.emp_code, r.department, r.position, r.company, r.zone, r.pob_since, r.last_seen] for r in rows],
        ["Name", "Emp Code", "Department", "Position", "Company", "Zone", "On board since", "Last seen"],
        f"pob_report_{_site_today()}.csv",
    )


@router.get("/visitors/csv")
async def visitors_csv(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    start = start_date or (_site_today() - timedelta(days=30)).isoformat()
    end   = end_date   or _site_today().isoformat()
    rows = db.execute(text("""
        SELECT vv.full_name, vv.phone, vv.email, vv.company,
               vl.check_in_time, vl.check_out_time,
               CASE vl.status WHEN 0 THEN 'On-site' WHEN 1 THEN 'Checked-out' ELSE 'Other' END AS status
        FROM vis_visit_log vl
        LEFT JOIN vis_visitor vv ON vv.id = vl.visitor_id
        WHERE vl.check_in_time::date BETWEEN :start AND :end
        ORDER BY vl.check_in_time DESC LIMIT 2000
    """), {"start": start, "end": end}).fetchall()
    return _csv_response(
        [[r.full_name, r.phone, r.email, r.company, r.check_in_time, r.check_out_time, r.status] for r in rows],
        ["Name", "Phone", "Email", "Company", "Check In", "Check Out", "Status"],
        f"visitors_{start}_{end}.csv",
    )


@router.get("/leave/csv")
async def leave_csv(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS employee,
               p.emp_code, lm.leave_type, lm.start_date, lm.end_date,
               lm.days_count, lm.status, lm.reason
        FROM leave_management lm
        LEFT JOIN personnel p ON lm.personnel_id = p.id
        ORDER BY lm.created_at DESC LIMIT 2000
    """)).fetchall()
    return _csv_response(
        [[r.employee, r.emp_code, r.leave_type, r.start_date, r.end_date, r.days_count, r.status, r.reason] for r in rows],
        ["Employee", "Emp Code", "Leave Type", "Start", "End", "Days", "Status", "Reason"],
        "leave_report.csv",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PDF ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/attendance/pdf")
async def attendance_pdf(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    start = start_date or (_site_today() - timedelta(days=7)).isoformat()
    end   = end_date   or _site_today().isoformat()
    _site_session(db)
    rows = db.execute(text(_ATTENDANCE_SQL), {"start": start, "end": end, "lim": 2000}).fetchall()

    data = [[r.name, r.emp_code, r.department or "", str(r.att_date),
             str(r.check_in or ""), str(r.check_out or ""),
             str(r.work_hours or ""), str(r.late_minutes or "0"),
             str(r.ot_minutes or "0"), r.status] for r in rows]
    pdf = _build_pdf(
        "Attendance Report",
        f"Period: {start} to {end}",
        ["Name", "Emp Code", "Department", "Date", "In", "Out", "Hrs", "Late", "OT", "Status"],
        data,
        col_widths=[40, 22, 30, 22, 18, 18, 14, 14, 14, 20],
    )
    return _pdf_response(pdf, f"attendance_{start}_{end}.pdf")


@router.get("/compliance/pdf")
async def compliance_pdf(
    days: int = Query(default=60),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    cutoff = (_site_today() + timedelta(days=days)).isoformat()
    rows = db.execute(text("""
        SELECT (c.first_name||' '||c.last_name) AS name,
               c.contractor_code, v.vendor_name AS vendor,
               c.work_permit_expiry, c.medical_clearance_status,
               c.background_check_status, c.status
        FROM contractors c
        LEFT JOIN vendors v ON v.id = c.vendor_id
        WHERE c.status = 'ACTIVE'
          AND (c.work_permit_expiry::date <= :cutoff OR c.medical_clearance_status IN ('FAILED','PENDING'))
        ORDER BY c.work_permit_expiry NULLS LAST
        LIMIT 1000
    """), {"cutoff": cutoff}).fetchall()

    data = [[r.name, r.contractor_code, r.vendor or "", str(r.work_permit_expiry or ""),
             r.medical_clearance_status or "", r.background_check_status or "", r.status or ""] for r in rows]
    pdf = _build_pdf(
        "Compliance Report",
        f"Permits expiring within {days} days  •  Generated: {_site_today()}",
        ["Name", "Code", "Vendor", "Permit Expiry", "Medical Status", "Background", "Status"],
        data,
        col_widths=[50, 28, 40, 28, 36, 36, 24],
    )
    return _pdf_response(pdf, "compliance_report.pdf")


@router.get("/pob/pdf")
async def pob_pdf(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _site_session(db)
    rows = db.execute(text(_POB_SQL)).fetchall()

    data = [[r.name, r.emp_code, r.department or "", r.position or "",
             r.zone or "", str(r.pob_since or "")] for r in rows]
    pdf = _build_pdf(
        "Personnel On Board (POB) Report",
        f"As of {_site_today()}  •  {len(data)} on board",
        ["Name", "Emp Code", "Department", "Position", "Zone", "On board since"],
        data,
        col_widths=[50, 28, 50, 50, 32, 30],
    )
    return _pdf_response(pdf, f"pob_report_{_site_today()}.pdf")


@router.get("/visitors/pdf")
async def visitors_pdf(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    start = start_date or (_site_today() - timedelta(days=30)).isoformat()
    end   = end_date   or _site_today().isoformat()
    rows = db.execute(text("""
        SELECT vv.full_name, vv.phone, vv.email, vv.company,
               vl.check_in_time::text, vl.check_out_time::text,
               CASE vl.status WHEN 0 THEN 'On-site' WHEN 1 THEN 'Checked-out' ELSE 'Other' END AS status
        FROM vis_visit_log vl
        LEFT JOIN vis_visitor vv ON vv.id = vl.visitor_id
        WHERE vl.check_in_time::date BETWEEN :start AND :end
        ORDER BY vl.check_in_time DESC LIMIT 2000
    """), {"start": start, "end": end}).fetchall()

    data = [[r.full_name or "", r.phone or "", r.email or "", r.company or "",
             str(r.check_in_time or ""), str(r.check_out_time or ""), r.status] for r in rows]
    pdf = _build_pdf(
        "Visitor Log Report",
        f"Period: {start} to {end}",
        ["Name", "Phone", "Email", "Company", "Check In", "Check Out", "Status"],
        data,
        col_widths=[40, 28, 48, 40, 36, 36, 22],
    )
    return _pdf_response(pdf, f"visitors_{start}_{end}.pdf")
