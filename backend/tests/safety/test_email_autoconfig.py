"""Email simple setup: address + app password → right server, proven before saving."""
import app.services.email_autoconfig as ea


def test_known_domains_and_mx_detection(monkeypatch):
    monkeypatch.setattr(ea, "_mx", lambda d: {
        "marconi.ng": ["marconi-ng.mail.protection.outlook.com"],
        "acme.com": ["aspmx.l.google.com"],
        "tekk.io": ["inbound-smtp.eu-west-1.amazonaws.com"],
        "small.ng": ["mx1.hostingco.net"],
    }.get(d, []))
    assert ea.detect("a@gmail.com")["candidates"] == [("smtp.gmail.com", 587)]
    assert ea.detect("a@marconi.ng")["candidates"] == [("smtp.office365.com", 587)]
    assert ea.detect("a@acme.com")["provider"] == "google"
    assert ea.detect("a@tekk.io")["candidates"] == [("smtp.mail.eu-west-1.awsapps.com", 465)]
    c = ea.detect("a@small.ng")["candidates"]
    assert c[:2] == [("mail.small.ng", 587), ("mail.small.ng", 465)] and ("mx1.hostingco.net", 465) in c


def test_auto_configure_tries_until_login_works_and_stops_on_bad_password(monkeypatch):
    monkeypatch.setattr(ea, "_mx", lambda d: [])
    tried = []

    def login(host, port, user, pw, timeout=12):
        tried.append((host, port))
        return None if (host, port) == ("smtp.small.ng", 465) else f"Could not reach {host}:{port}"
    monkeypatch.setattr(ea, "try_login", login)
    r = ea.auto_configure("ops@small.ng", "pw")
    assert r["ok"] and (r["smtp_host"], r["smtp_port"]) == ("smtp.small.ng", "465")

    tried.clear()
    monkeypatch.setattr(ea, "try_login", lambda *a, **k: tried.append(a[:2]) or "The email or app password was not accepted. Check both and try again.")
    r = ea.auto_configure("ops@small.ng", "wrong")
    assert not r["ok"] and "not accepted" in r["error"] and len(tried) == 1   # right server, wrong password: stop
