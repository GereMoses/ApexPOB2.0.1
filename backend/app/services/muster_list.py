"""
Printable muster list — everyone on board plus visitors on site, grouped by where
they were last placed, with a tick box per person.

The fallback for when power or the network is down during an emergency: wardens
work from paper. Downloadable any time (Emergency & Mustering → Live board →
Print muster list) and emailed to the response team at each shift change.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _site_now() -> datetime:
    from .attendance_calculation_service import SITE_TZ
    return datetime.now(SITE_TZ)


def muster_roster(db) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    staff = db.execute(text("""
        SELECT p.emp_code,
               COALESCE(NULLIF(p.full_name, ''), TRIM(CONCAT(p.first_name, ' ', p.last_name))) AS name,
               COALESCE(NULLIF(p.department, ''), d.name, '') AS dept,
               COALESCE(p.company, '') AS company, COALESCE(p.phone, '') AS phone,
               COALESCE(z.name, 'Location unknown') AS location
        FROM personnel p
        LEFT JOIN zones z ON z.id = p.current_zone_id
        LEFT JOIN departments d ON d.id = p.department_id
        WHERE p.is_active AND p.is_onboard AND p.on_leave IS NOT TRUE
        ORDER BY location, name
    """)).mappings().all()
    try:
        visitors = db.execute(text("""
            SELECT 'VIS-' || l.id AS emp_code, v.full_name AS name, COALESCE(v.company, '') AS company,
                   COALESCE(v.phone, '') AS phone,
                   COALESCE(NULLIF(TRIM(CONCAT(h.first_name, ' ', h.last_name)), ''), '') AS host
            FROM vis_visit_log l JOIN vis_visitor v ON v.id = l.visitor_id
            LEFT JOIN personnel_employee h ON h.id = l.host_emp_id
            WHERE l.check_out_time IS NULL AND l.status IN (0, 2)
            ORDER BY v.full_name
        """)).mappings().all()
    except Exception as e:  # noqa: BLE001
        logger.warning("muster list: visitors unavailable (%s)", e)
        db.rollback()
        visitors = []
    return [dict(r) for r in staff], [dict(r) for r in visitors]


def build_pdf(db, site_name: str = "ApexPOB") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

    staff, visitors = muster_roster(db)
    now = _site_now()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title="Muster list", author="ApexPOB")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=17, alignment=0, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9.5, textColor=colors.HexColor("#475569"))
    grp = ParagraphStyle("grp", parent=ss["Heading3"], fontSize=11.5, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#0f172a"))
    cell = ParagraphStyle("cell", parent=ss["Normal"], fontSize=8.6, leading=10.5)

    story = [
        Paragraph(f"MUSTER LIST — {site_name}", h1),
        Paragraph(f"Printed {now.strftime('%a %d %b %Y, %H:%M')} (site time) · "
                  f"<b>{len(staff)}</b> on board · <b>{len(visitors)}</b> visitors · "
                  f"<b>{len(staff) + len(visitors)}</b> to account for", sub),
        Paragraph("Tick each person as they reach the assembly point. Report anyone not ticked to the incident controller.", sub),
        Spacer(1, 6),
    ]

    widths = [8 * mm, 58 * mm, 28 * mm, 42 * mm, 30 * mm, 12 * mm, 12 * mm]
    head = ["#", "Name", "ID", "Department / company", "Phone", "Safe", "Hurt"]

    def table(rows: List[List[str]]):
        t = Table([head] + rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.4),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in staff:
        groups.setdefault(p["location"], []).append(p)
    n = 0
    for loc in sorted(groups, key=lambda x: (x == "Location unknown", x)):
        rows = []
        for p in groups[loc]:
            n += 1
            org = " / ".join(x for x in (p["dept"], p["company"]) if x)
            rows.append([str(n), Paragraph(p["name"] or "", cell), p["emp_code"], Paragraph(org, cell), p["phone"], "☐", "☐"])
        story.append(KeepTogether([Paragraph(f"{loc} — {len(rows)}", grp), table(rows[:25])]))
        if len(rows) > 25:
            story.append(table(rows[25:]))
    if visitors:
        rows = []
        for v in visitors:
            n += 1
            org = " / ".join(x for x in (v["company"], f"host {v['host']}" if v["host"] else "") if x)
            rows.append([str(n), Paragraph(v["name"] or "", cell), v["emp_code"], Paragraph(org, cell), v["phone"], "☐", "☐"])
        story += [Paragraph(f"Visitors — {len(rows)}", grp), table(rows)]
    if not staff and not visitors:
        story.append(Paragraph("Nobody is recorded on board.", ss["Normal"]))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(12 * mm, 8 * mm, f"ApexPOB muster list · {now.strftime('%d %b %Y %H:%M')}")
        canvas.drawRightString(A4[0] - 12 * mm, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def email_to_responders(db) -> Dict[str, Any]:
    """Shift-change copy of the muster list to the response team's email."""
    from .notify_email import send_email, smtp_configured
    from .whatsapp_config import get_responders
    emails = sorted({(r.get("email") or "").strip() for r in get_responders(db)} - {""})
    if not emails:
        return {"sent": 0, "note": "no response-team email addresses"}
    if not smtp_configured():
        return {"sent": 0, "note": "email not set up"}
    staff, visitors = muster_roster(db)
    stamp = _site_now().strftime("%Y-%m-%d_%H%M")
    pdf = build_pdf(db)
    return send_email(emails, f"Muster list — {len(staff) + len(visitors)} on site ({_site_now().strftime('%d %b %H:%M')})",
                      f"<p>Attached: the current muster list — <b>{len(staff)}</b> on board and <b>{len(visitors)}</b> visitors.</p>"
                      "<p>Print it and keep it at the muster points; it is the fallback if power or the network fails.</p>",
                      f"Muster list attached — {len(staff)} on board, {len(visitors)} visitors.",
                      attachments=[(f"muster_list_{stamp}.pdf", pdf, "application/pdf")])
