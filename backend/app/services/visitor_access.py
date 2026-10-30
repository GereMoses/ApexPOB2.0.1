"""
Visitors ↔ the rest of ApexPOB: door cards on the ZKTeco panels, and messages to
the host and the visitor.

Door cards
  A visitor handed a physical card at the gate is loaded onto every C3 panel as a
  panel user: ID 9<visit id, 8 digits> (staff Attendance IDs are ≤ 8 digits, so they
  never clash), their card, valid until tomorrow (the nightly sync extends it while
  they stay on site). Secure doors — doors set to stay LOCKED in an emergency — are
  not opened for visitors. Check-out (or the nightly sync, once they're gone)
  expires the card. Without a physical card the visitor gets no door access and is
  escorted.

Messages (WhatsApp / Telegram / email via the shared dispatcher + the mailbox set
under Settings → Email — the old visitor mailer read env SMTP and never sent):
  * new pre-registration  → host: please approve
  * approved              → visitor: QR code by email (+ WhatsApp text)
  * rejected              → visitor
  * checked in            → host: your visitor has arrived
  * overstay              → host + bell
"""
from __future__ import annotations

import io
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

VISITOR_PIN_BASE = 900_000_000


def visitor_pin(visit_id: int) -> str:
    return str(VISITOR_PIN_BASE + int(visit_id))


def is_temp_card(card_no: Optional[str]) -> bool:
    return not card_no or str(card_no).upper().startswith("TMP")


def _site_today():
    from .attendance_calculation_service import SITE_TZ
    return datetime.now(SITE_TZ).date()


# ── door cards ────────────────────────────────────────────────────────────────

def visitor_panel_users(db: Session, visit_ids: Optional[List[int]] = None) -> List[Dict]:
    """Visitors on site holding a physical card, as panel user records."""
    q = """SELECT l.id, l.card_no, v.full_name FROM vis_visit_log l JOIN vis_visitor v ON v.id = l.visitor_id
           WHERE l.check_out_time IS NULL AND l.status IN (0, 2)
             AND COALESCE(l.card_no, '') <> '' AND UPPER(l.card_no) NOT LIKE 'TMP%'"""
    params: Dict = {}
    if visit_ids:
        q += " AND l.id = ANY(:ids)"
        params["ids"] = list(visit_ids)
    expire = int((_site_today() + timedelta(days=1)).strftime("%Y%m%d"))
    return [{"pin": visitor_pin(r.id), "emp_code": f"VIS-{r.id}", "card_no": str(r.card_no),
             "name": (r.full_name or "Visitor")[:24], "password": "", "expire": expire, "visitor": True}
            for r in db.execute(text(q), params).fetchall()]


def visitor_doors(db: Session, ctrl) -> List[int]:
    """Doors of this panel a visitor card may open — every door except secure ones."""
    secure = {r[0] for r in db.execute(text(
        "SELECT port FROM acc_door WHERE controller_id = :c AND emergency_action = 1"), {"c": ctrl.id}).fetchall()}
    return [d for d in range(1, (ctrl.door_count or 1) + 1) if d not in secure]


def card_in_use(db: Session, card_no: str, except_visit: Optional[int] = None) -> Optional[str]:
    """Who already holds this card number (staff or a visitor on site), else None."""
    staff = db.execute(text("""SELECT COALESCE(NULLIF(full_name, ''), emp_code) FROM personnel
                               WHERE is_active AND CAST(card_number AS TEXT) = :c LIMIT 1"""), {"c": card_no}).scalar()
    if staff:
        return f"staff member {staff}"
    vis = db.execute(text("""SELECT v.full_name FROM vis_visit_log l JOIN vis_visitor v ON v.id = l.visitor_id
                             WHERE l.check_out_time IS NULL AND l.status IN (0, 2) AND TRIM(l.card_no) = :c
                               AND l.id <> COALESCE(:x, -1) LIMIT 1"""), {"c": card_no, "x": except_visit}).scalar()
    return f"visitor {vis} (still on site)" if vis else None


def _panels(db: Session):
    from ..models.access_controller import AccessController
    return db.query(AccessController).all()


def load_visitor_card(visit_id: int) -> None:
    """Background: put this visitor's card on every panel."""
    from ..core.database import SessionLocal
    from . import panel_sync

    def run():
        db = SessionLocal()
        try:
            users = visitor_panel_users(db, [visit_id])
            for ctrl in _panels(db) if users else []:
                try:
                    panel_sync.load_users(db, ctrl, users, door_nos=visitor_doors(db, ctrl))
                except Exception as e:  # noqa: BLE001 — one dead panel must not stop the rest
                    logger.warning("Visitor card %s → panel %s failed: %s", visit_id, ctrl.name, e)
        finally:
            db.close()
    threading.Thread(target=run, daemon=True).start()


def remove_visitor_card(visit_id: int) -> None:
    """Background: expire this visitor's card on every panel it was loaded on."""
    from ..core.database import SessionLocal
    from . import panel_sync

    def run():
        db = SessionLocal()
        try:
            pin = visitor_pin(visit_id)
            ids = [r[0] for r in db.execute(text(
                "SELECT controller_id FROM controller_user WHERE pin = :p AND state = 'loaded'"), {"p": pin}).fetchall()]
            for ctrl in _panels(db):
                if ctrl.id in ids:
                    try:
                        panel_sync.remove_users(db, ctrl, [pin])
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Visitor card %s removal on %s failed: %s", visit_id, ctrl.name, e)
        finally:
            db.close()
    threading.Thread(target=run, daemon=True).start()


# ── messages ──────────────────────────────────────────────────────────────────

def host_people(db: Session, host_emp_id: Optional[int]) -> List[Dict]:
    """The host's own WhatsApp / Telegram / email (host_emp_id is a personnel_employee id)."""
    if not host_emp_id:
        return []
    code = db.execute(text("SELECT emp_code FROM personnel_employee WHERE id = :i"), {"i": host_emp_id}).scalar()
    if not code:
        return []
    from .notify_dispatch import people_from_personnel
    return people_from_personnel(db, emp_codes=[code])


def _when(pre_reg) -> str:
    d = pre_reg.visit_date.strftime("%a %d %b %Y") if pre_reg.visit_date else "date to be confirmed"
    t = f" {str(pre_reg.visit_time_start)[:5]}" if pre_reg.visit_time_start else ""
    return d + t


def notify_host_approval(db: Session, pre_reg) -> Dict:
    from .notify_dispatch import dispatch_background
    v = pre_reg.visitor
    host = host_people(db, pre_reg.host_emp_id)
    if not host:
        return {"host": "no contact on record"}
    msg = (f"Visitor request: {v.full_name if v else 'A visitor'}"
           f"{' (' + v.company + ')' if v and v.company else ''} wants to visit you on {_when(pre_reg)}"
           f"{' — ' + pre_reg.purpose if pre_reg.purpose else ''}. "
           f"Approve or reject in ApexPOB → Visitor → Host Approval.")
    return dispatch_background("visitor_request", pre_reg.id, host, "Visitor waiting for your approval", msg,
                               None, include_responders=False)


def _qr_png(value: str) -> bytes:
    import qrcode
    buf = io.BytesIO()
    qrcode.make(value).save(buf, format="PNG")
    return buf.getvalue()


def notify_visitor_decision(db: Session, pre_reg) -> Dict:
    """Approved → QR code by email (+ WhatsApp text); rejected → a short note."""
    from .notify_dispatch import dispatch_background
    v = pre_reg.visitor
    if not v:
        return {}
    host = host_people(db, pre_reg.host_emp_id)
    host_name = host[0]["name"] if host else "your host"
    approved = pre_reg.status == 1
    if approved:
        subject = f"Your visit on {_when(pre_reg)} is approved"
        text_msg = (f"Hello {v.full_name}, your visit to {host_name} on {_when(pre_reg)} is approved. "
                    f"Show this code at the gate: {pre_reg.qr_code}. Bring a photo ID.")
    else:
        subject = "Your visit request"
        text_msg = (f"Hello {v.full_name}, your visit request for {_when(pre_reg)} was not approved"
                    f"{': ' + pre_reg.approval_note if pre_reg.approval_note else ''}. Please contact {host_name}.")
    out: Dict = {}
    if v.email:
        from .notify_email import send_email
        att = [("visitor-pass.png", _qr_png(pre_reg.qr_code), "image/png")] if approved else None
        body = f"<p>{text_msg}</p>" + ("<p>Your gate pass QR code is attached.</p>" if approved else "")
        email = v.email
        threading.Thread(target=lambda: send_email(email, subject, body, text_msg, attachments=att), daemon=True).start()
        out["email"] = "queued"
    if v.phone:
        out["whatsapp"] = dispatch_background("visitor_pass", pre_reg.id,
                                              [{"name": v.full_name, "phone": v.phone, "kind": "visitor"}],
                                              subject, text_msg, ["whatsapp", "sms"], include_responders=False)
    return out


def notify_host_arrival(db: Session, visit_log) -> Dict:
    from .notify_dispatch import dispatch_background
    host = host_people(db, visit_log.host_emp_id)
    if not host:
        return {}
    v = visit_log.visitor
    msg = (f"Your visitor {v.full_name if v else ''}{' (' + v.company + ')' if v and v.company else ''} "
           f"has arrived and checked in at the gate.")
    return dispatch_background("visitor_arrived", visit_log.id, host, "Your visitor has arrived", msg,
                               None, include_responders=False)


def notify_overstay(db: Session, visit_log, hours_over: float) -> None:
    from .notify_dispatch import dispatch_background
    v = visit_log.visitor
    who = f"{v.full_name if v else 'A visitor'}{' (' + v.company + ')' if v and v.company else ''}"
    msg = f"{who} is still on site {hours_over:.1f} h past their expected departure. Please arrange check-out."
    db.execute(text("""
        INSERT INTO sys_notifications (dedup_key, notification_type, title, message, priority, link, expires_at)
        VALUES (:dk, 'visitor_overstay', :t, :m, 'high', '/visitor', NOW() + INTERVAL '24 hours')
        ON CONFLICT (dedup_key) DO NOTHING
    """), {"dk": f"visitor_overstay_{visit_log.id}", "t": f"Visitor overstay: {who}", "m": msg})
    db.commit()
    host = host_people(db, visit_log.host_emp_id)
    if host:
        dispatch_background("visitor_overstay", visit_log.id, host, "Your visitor has overstayed", msg,
                            None, include_responders=False)
