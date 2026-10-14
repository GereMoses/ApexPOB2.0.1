"""
Compliance Email Task — daily digest of expiring permits and failed medicals.

Schedule: daily at 06:00 UTC via Celery Beat.

Sends one HTML email to all configured recipients summarising:
  - Work permits expiring in the next 30 days
  - Medical clearances that are FAILED or PENDING
  - Training certifications expiring in the next 14 days
"""
import os
import logging
import asyncio
from datetime import date, timedelta
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ── Email settings ─────────────────────────────────────────────────────────────
SMTP_HOST    = os.getenv("SMTP_HOST", "")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER", "")
SMTP_PASS    = os.getenv("SMTP_PASS", "")
SMTP_FROM    = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TLS     = os.getenv("SMTP_TLS", "true").lower() == "true"
# Comma-separated list of recipient emails
COMPLIANCE_EMAILS = [
    e.strip() for e in os.getenv("COMPLIANCE_EMAIL_RECIPIENTS", "").split(",")
    if e.strip()
]
PERMIT_WARN_DAYS  = int(os.getenv("PERMIT_WARN_DAYS", "30"))
TRAINING_WARN_DAYS = int(os.getenv("TRAINING_WARN_DAYS", "14"))


def _fetch_data(db):
    """Fetch all compliance data in a single pass."""
    today = date.today()

    # Expiring work permits
    permit_cutoff = (today + timedelta(days=PERMIT_WARN_DAYS)).isoformat()
    permits = db.execute(text("""
        SELECT (c.first_name||' '||COALESCE(c.last_name,'')) AS name,
               c.contractor_code, c.work_permit_expiry,
               v.vendor_name AS vendor
        FROM contractors c
        LEFT JOIN vendors v ON v.id = c.vendor_id
        WHERE c.status = 'ACTIVE'
          AND c.work_permit_expiry IS NOT NULL
          AND c.work_permit_expiry::date <= :cut
        ORDER BY c.work_permit_expiry
    """), {"cut": permit_cutoff}).fetchall()

    # Failed / pending medical clearances
    medicals = db.execute(text("""
        SELECT (c.first_name||' '||COALESCE(c.last_name,'')) AS name,
               c.contractor_code, c.medical_clearance_status, v.vendor_name AS vendor
        FROM contractors c
        LEFT JOIN vendors v ON v.id = c.vendor_id
        WHERE c.status = 'ACTIVE'
          AND c.medical_clearance_status IN ('FAILED','PENDING')
        ORDER BY c.medical_clearance_status, c.first_name
    """)).fetchall()

    # Expiring training certifications
    training_cutoff = (today + timedelta(days=TRAINING_WARN_DAYS)).isoformat()
    training = db.execute(text("""
        SELECT TRIM(p.first_name||' '||COALESCE(p.last_name,'')) AS name,
               p.emp_code, tc.course_name AS course, te.expiry_date
        FROM training_enrollment te
        JOIN training_courses tc ON tc.id = te.course_id
        JOIN personnel p ON p.id = te.personnel_id
        WHERE te.status = 'completed'
          AND te.expiry_date IS NOT NULL
          AND te.expiry_date::date <= :cut
        ORDER BY te.expiry_date
    """), {"cut": training_cutoff}).fetchall()

    return permits, medicals, training


def _build_html(permits, medicals, training):
    today = date.today().isoformat()

    def table(headers, rows, empty_msg):
        if not rows:
            return f'<p style="color:#6B7A8D;font-style:italic">{empty_msg}</p>'
        ths = "".join(f"<th>{h}</th>" for h in headers)
        trs = ""
        for row in rows:
            tds = "".join(f"<td>{v or '—'}</td>" for v in row)
            trs += f"<tr>{tds}</tr>"
        return f"""
        <table border="0" cellspacing="0" cellpadding="6" width="100%"
               style="border-collapse:collapse;font-size:13px">
          <thead><tr style="background:#34495E;color:#fff">{ths}</tr></thead>
          <tbody>{trs}</tbody>
        </table>"""

    permit_table = table(
        ["Name", "Code", "Vendor", "Permit Expiry"],
        [(r.name, r.contractor_code, r.vendor, str(r.work_permit_expiry)) for r in permits],
        "No work permits expiring in the next 30 days."
    )
    medical_table = table(
        ["Name", "Code", "Vendor", "Medical Status"],
        [(r.name, r.contractor_code, r.vendor, r.medical_clearance_status) for r in medicals],
        "No failed or pending medical clearances."
    )
    training_table = table(
        ["Name", "Emp Code", "Course", "Expiry"],
        [(r.name, r.emp_code, r.course, str(r.expiry_date)) for r in training],
        "No training certifications expiring soon."
    )

    return f"""
    <html><body style="font-family:Segoe UI,Arial,sans-serif;color:#1F2937;background:#F9FAFB;padding:0;margin:0">
    <div style="max-width:800px;margin:20px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)">
      <div style="background:#1E2A3B;padding:20px 28px">
        <h1 style="color:#fff;margin:0;font-size:20px">Apex POB — Daily Compliance Digest</h1>
        <p style="color:#8892A4;margin:4px 0 0;font-size:13px">Report date: {today}</p>
      </div>
      <div style="padding:24px 28px">

        <h2 style="color:#DC2626;font-size:15px;border-left:4px solid #DC2626;padding-left:10px;margin:0 0 12px">
          ⚠️  Work Permits Expiring (next {PERMIT_WARN_DAYS} days) — {len(permits)} record(s)
        </h2>
        {permit_table}

        <h2 style="color:#D97706;font-size:15px;border-left:4px solid #D97706;padding-left:10px;margin:24px 0 12px">
          🩺  Medical Issues — {len(medicals)} record(s)
        </h2>
        {medical_table}

        <h2 style="color:#7C3AED;font-size:15px;border-left:4px solid #7C3AED;padding-left:10px;margin:24px 0 12px">
          📋  Training Certifications Expiring (next {TRAINING_WARN_DAYS} days) — {len(training)} record(s)
        </h2>
        {training_table}

      </div>
      <div style="background:#F3F4F6;padding:14px 28px;font-size:11px;color:#9CA3AF;text-align:center">
        This email was sent automatically by the POB Management System.
        Do not reply to this email.
      </div>
    </div>
    </body></html>"""


async def _send_email(subject: str, html: str, recipients: list) -> bool:
    if not SMTP_HOST or not recipients:
        logger.warning("Compliance email skipped — SMTP_HOST or recipients not configured")
        return False
    try:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_FROM
        msg["To"]      = ", ".join(recipients)
        msg.attach(MIMEText(html, "html"))

        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASS,
            start_tls=SMTP_TLS,
        )
        logger.info("Compliance digest sent to %s", recipients)
        return True
    except Exception as e:
        logger.error("Failed to send compliance email: %s", e)
        return False


def send_compliance_digest(db=None) -> dict:
    """
    Synchronous entry point — can be called from Celery task or a manual trigger.
    If db is None, creates its own session.
    """
    own_session = db is None
    if own_session:
        from app.core.database import SessionLocal
        db = SessionLocal()

    try:
        permits, medicals, training = _fetch_data(db)

        if not permits and not medicals and not training:
            logger.info("Compliance digest: nothing to report today")
            return {"sent": False, "reason": "nothing_to_report"}

        html    = _build_html(permits, medicals, training)
        today   = date.today().isoformat()
        subject = f"[POB] Compliance Digest {today} — {len(permits)} permits, {len(medicals)} medical, {len(training)} training"

        sent = asyncio.run(_send_email(subject, html, COMPLIANCE_EMAILS))
        return {
            "sent": sent,
            "permits": len(permits),
            "medicals": len(medicals),
            "training": len(training),
            "recipients": COMPLIANCE_EMAILS,
        }
    finally:
        if own_session:
            db.close()
