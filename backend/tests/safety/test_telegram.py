"""Telegram alerts: bot setup, personal Start links, team groups, delivery (Telegram simulated)."""
import uuid

import pytest
from sqlalchemy import text

from .conftest import needs_db


@pytest.fixture
def tg(monkeypatch, db):
    """A fake Telegram Bot API."""
    import app.services.notify_telegram as nt
    state = {"updates": [], "sent": [], "token_ok": True}

    def call(token, method, payload=None, timeout=15):
        payload = payload or {}
        if method == "getMe":
            return {"ok": True, "result": {"username": "ApexPOBTestBot"}} if state["token_ok"] else \
                   {"ok": False, "description": "Unauthorized", "error_code": 401}
        if method == "getUpdates":
            ups, state["updates"] = state["updates"], []
            return {"ok": True, "result": ups}
        if method == "sendMessage":
            state["sent"].append((str(payload["chat_id"]), payload["text"]))
            return {"ok": True, "result": {"message_id": 1}}
        return {"ok": False}
    monkeypatch.setattr(nt, "call", call)
    yield state
    db.execute(text("DELETE FROM sys_parameters WHERE param_key LIKE 'telegram.%'"))
    db.commit()


def _upd(uid, chat, text_=None, member_status=None):
    u = {"update_id": uid}
    if member_status:
        u["my_chat_member"] = {"chat": chat, "new_chat_member": {"status": member_status}}
    else:
        u["message"] = {"chat": chat, "text": text_ or ""}
    return u


@needs_db
def test_bot_token_checked_link_start_and_alert(db, tg, make_person):
    from app.services import notify_telegram as nt
    from app.services.notify_dispatch import dispatch
    tg["token_ok"] = False
    with pytest.raises(ValueError):
        nt.save_settings(db, True, "bad-token")
    tg["token_ok"] = True
    s = nt.save_settings(db, True, "123:good")
    assert s["bot_username"] == "ApexPOBTestBot" and nt.telegram_configured()

    p = make_person()
    url = nt.link_url(db, emp_code=p["emp_code"])
    code = url.split("start=")[1]
    assert url.startswith("https://t.me/ApexPOBTestBot?start=")
    tg["updates"] = [_upd(10, {"id": 555001, "type": "private"}, f"/start {code}")]
    assert nt.poll_once(db)["linked"] == 1
    assert db.execute(text("SELECT telegram_chat_id FROM personnel WHERE emp_code = :c"), {"c": p["emp_code"]}).scalar() == 555001
    assert tg["sent"][-1][0] == "555001" and "Linked to ApexPOB" in tg["sent"][-1][1]

    from app.services.notify_dispatch import people_from_personnel
    out = dispatch("test", None, people_from_personnel(db, emp_codes=[p["emp_code"]]), "FIRE MUSTER",
                   "Go to Muster Point A", ["telegram"], include_responders=False)
    assert out["telegram"]["sent"] == 1 and tg["sent"][-1] == ("555001", "FIRE MUSTER\n\nGo to Muster Point A")


@needs_db
def test_team_group_detected_and_gets_team_alerts(db, tg):
    from app.services import notify_telegram as nt
    from app.services.notify_dispatch import dispatch
    nt.save_settings(db, True, "123:good")
    tg["updates"] = [_upd(20, {"id": -100777, "type": "supergroup", "title": "Marconi ERT"}, member_status="member")]
    assert nt.poll_once(db)["groups_added"] == 1
    groups = nt.get_settings(db)["groups"]
    assert groups == [{"chat_id": "-100777", "title": "Marconi ERT", "team": False}]
    nt.save_groups(db, [{**groups[0], "team": True}])
    dispatch("test", None, [], "PANIC ALARM", "Gate 2", ["telegram"], include_responders=True)
    assert ("-100777", "PANIC ALARM\n\nGate 2") in tg["sent"]


@needs_db
def test_responder_link_survives_team_save(db, tg):
    from app.services import notify_telegram as nt
    from app.services.whatsapp_config import save_responders, get_responders
    nt.save_settings(db, True, "123:good")
    save_responders(db, [{"name": "OIM", "email": "oim@example.test"}])
    url = nt.link_url(db, responder_key=nt.responder_key(get_responders(db)[0]))
    tg["updates"] = [_upd(30, {"id": 999, "type": "private"}, f"/start {url.split('start=')[1]}")]
    nt.poll_once(db)
    team = get_responders(db)
    assert team[0]["telegram_chat_id"] == "999"
    save_responders(db, team)                                # e.g. the admin edits the team later
    assert get_responders(db)[0]["telegram_chat_id"] == "999"
    save_responders(db, [])
