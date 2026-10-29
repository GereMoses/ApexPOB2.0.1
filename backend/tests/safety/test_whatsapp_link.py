"""WhatsApp through one linked phone (Evolution API gateway simulated)."""
import pytest


@pytest.fixture
def gw(monkeypatch):
    """A fake Evolution API gateway."""
    import app.services.whatsapp_link as wl
    state = {"state": "open", "sent": [], "not_on_wa": set()}

    def call(method, path, json=None, timeout=15):
        if path.startswith("/instance/fetchInstances"):
            return [{"name": wl.INSTANCE, "connectionStatus": state["state"],
                     "ownerJid": "2348030000000@s.whatsapp.net", "profileName": "Site Alerts"}]
        if path.startswith("/message/sendText/"):
            if json["number"] in state["not_on_wa"]:
                raise RuntimeError(f"WhatsApp gateway: {json['number']} is not on WhatsApp")
            state["sent"].append((json["number"], json["text"]))
            return {"key": {"id": "x"}}
        raise AssertionError(path)
    monkeypatch.setattr(wl, "_call", call)
    monkeypatch.setattr(wl.time, "sleep", lambda s: None)
    wl._cache["at"] = 0.0
    yield state
    wl._cache["at"] = 0.0


def test_status_shows_the_linked_number(gw):
    from app.services import whatsapp_link
    st = whatsapp_link.status()
    assert st["linked"] and st["number"] == "+2348030000000" and st["name"] == "Site Alerts"
    gw["state"] = "connecting"
    assert whatsapp_link.status() == {"running": True, "linked": False, "state": "connecting",
                                      "number": None, "name": None}


def test_alerts_go_out_from_the_linked_phone_once_per_number(gw):
    from app.services.notify_whatsapp import _send_db
    gw["not_on_wa"].add("2348099999999")
    out = _send_db({"provider": "linked", "country_code": "234"},
                   ["0803 111 2222", "+2348031112222", "08099999999"], "MUSTER NOW")
    assert gw["sent"] == [("2348031112222", "MUSTER NOW")]          # same phone twice → one message
    assert out["sent"] == 1 and out["failed"] == ["08099999999"]       # failures reported as given
    assert "not on WhatsApp" in out["errors"]["08099999999"]


def test_unlinked_phone_fails_fast_and_is_not_ready(gw):
    from app.services.notify_whatsapp import _send_db
    from app.services.whatsapp_config import db_whatsapp_ready
    gw["state"] = "close"
    out = _send_db({"provider": "linked", "country_code": "234"}, ["08031112222"], "x")
    assert out["sent"] == 0 and "not linked" in out["error"] and not gw["sent"]
    assert db_whatsapp_ready({"enabled": True, "provider": "linked"}) is False
