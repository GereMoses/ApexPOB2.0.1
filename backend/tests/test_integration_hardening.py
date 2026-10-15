"""
Regression tests for the SeamlessHR / Business Central integration deep-analysis fixes:
  SHR-1/3/4 — export from computed att_report (not raw punches)
  SHR-2      — idempotency key per (employee, date)
  SHR-5      — Fernet field encryption for stored credentials (legacy-plaintext tolerant)
  SHR-6      — base-URL validation (https-only + private-IP/SSRF block)
"""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import Mock


# ─────────────────────────────────────────────────────────────────────────────
# SHR-5 — credential encryption
# ─────────────────────────────────────────────────────────────────────────────

class TestSecretCrypto:
    def test_roundtrip(self):
        from app.core.crypto import encrypt_secret, decrypt_secret, is_encrypted
        secret = "super-secret-api-key-12345"
        enc = encrypt_secret(secret)
        assert is_encrypted(enc), "Encrypted value must carry the enc tag."
        assert enc != secret, "Ciphertext must differ from plaintext."
        assert decrypt_secret(enc) == secret, "Round-trip must recover the original."

    def test_decrypt_legacy_plaintext_passes_through(self):
        """Existing plaintext credentials must keep working (transparent upgrade)."""
        from app.core.crypto import decrypt_secret
        assert decrypt_secret("legacy-plaintext-key") == "legacy-plaintext-key"

    def test_encrypt_is_idempotent(self):
        from app.core.crypto import encrypt_secret
        once = encrypt_secret("k")
        twice = encrypt_secret(once)
        assert once == twice, "Re-encrypting an already-encrypted value must be a no-op."

    def test_empty_passthrough(self):
        from app.core.crypto import encrypt_secret, decrypt_secret
        assert encrypt_secret("") == ""
        assert decrypt_secret("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# SHR-6 — base URL validation
# ─────────────────────────────────────────────────────────────────────────────

class TestBaseUrlValidation:
    def test_rejects_http(self):
        from app.services.attendance_export import validate_integration_base_url, IntegrationUrlError
        with pytest.raises(IntegrationUrlError):
            validate_integration_base_url("http://api.seamlesshr.com")

    def test_rejects_loopback(self):
        from app.services.attendance_export import validate_integration_base_url, IntegrationUrlError
        with pytest.raises(IntegrationUrlError):
            validate_integration_base_url("https://127.0.0.1/api")

    def test_rejects_private_ip(self):
        from app.services.attendance_export import validate_integration_base_url, IntegrationUrlError
        with pytest.raises(IntegrationUrlError):
            validate_integration_base_url("https://10.0.0.5/api")

    def test_rejects_cloud_metadata_ip(self):
        from app.services.attendance_export import validate_integration_base_url, IntegrationUrlError
        with pytest.raises(IntegrationUrlError):
            validate_integration_base_url("https://169.254.169.254/latest/meta-data")

    def test_accepts_public_https_and_strips_slash(self):
        from app.services.attendance_export import validate_integration_base_url
        # 8.8.8.8 is public; using an IP literal avoids DNS in the test.
        assert validate_integration_base_url("https://8.8.8.8/api/") == "https://8.8.8.8/api"

    def test_rejects_empty(self):
        from app.services.attendance_export import validate_integration_base_url, IntegrationUrlError
        with pytest.raises(IntegrationUrlError):
            validate_integration_base_url("")


# ─────────────────────────────────────────────────────────────────────────────
# SHR-1/2/3/4 — export from att_report with idempotency keys
# ─────────────────────────────────────────────────────────────────────────────

def _att_row(emp_code, att_date, check_in, check_out, work_minutes, ot=0):
    r = Mock()
    r.emp_code = emp_code
    r.att_date = att_date
    r.check_in = check_in
    r.check_out = check_out
    r.work_minutes = work_minutes
    r.overtime_minutes = ot
    return r


class TestBuildDailyAttendance:
    def test_reads_att_report_and_keys_each_record(self):
        from app.services import attendance_export as ax

        d = date(2026, 6, 6)
        rows = [
            _att_row("EMP001", d, datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
                     datetime(2026, 6, 6, 20, 0, tzinfo=timezone.utc), 660, ot=60),
        ]
        db = Mock()
        db.execute.return_value.fetchall.return_value = rows

        out = ax.build_daily_attendance(db, d)

        assert len(out) == 1
        rec = out[0]
        assert rec["emp_code"] == "EMP001"
        assert rec["work_minutes"] == 660
        assert rec["overtime_minutes"] == 60
        assert rec["idempotency_key"] == "pob-EMP001-2026-06-06", (
            "Each record must carry a stable (emp, date) idempotency key."
        )

        # Sanity: the query must read att_report, NOT raw iclock_transaction.
        sql = db.execute.call_args[0][0].text
        assert "FROM att_report" in sql, "Exporter must source from computed att_report."
        # Raw punches may only be consulted to find WHICH reader recorded the computed
        # check-in/out (SeamlessHR's deviceSN) — never as a source of times or hours.
        import re
        for m in re.finditer(r"SELECT\s+([\w.]+)\s+FROM\s+iclock_transaction", sql):
            assert m.group(1).endswith("terminal_sn"), (
                "iclock_transaction may only be read for the reader serial, not punches.")
        assert sql.count("FROM iclock_transaction") == len(
            re.findall(r"SELECT\s+[\w.]+terminal_sn\s+FROM\s+iclock_transaction", sql)), (
            "Exporter must source from computed att_report, not raw punches.")

    def test_empty_when_no_computed_attendance(self):
        from app.services import attendance_export as ax
        db = Mock()
        db.execute.return_value.fetchall.return_value = []
        assert ax.build_daily_attendance(db, date(2026, 6, 6)) == []


class TestSeamlessHRPayload:
    def test_payload_shape_and_idempotency(self, monkeypatch):
        from app.services import seamlesshr_service as shr

        canonical = [{
            "emp_code": "EMP001",
            "att_date": date(2026, 6, 6),
            "check_in": datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
            "check_out": datetime(2026, 6, 6, 20, 0, tzinfo=timezone.utc),
            "work_minutes": 660,
            "overtime_minutes": 60,
            "idempotency_key": "pob-EMP001-2026-06-06",
        }]
        monkeypatch.setattr(
            "app.services.attendance_export.build_daily_attendance",
            lambda db, d: canonical,
        )

        records = shr._build_attendance_records(Mock(), date(2026, 6, 6))
        assert records[0]["employee_id"] == "EMP001"
        assert records[0]["total_minutes"] == 660
        assert records[0]["idempotency_key"] == "pob-EMP001-2026-06-06"
        # tz-aware ISO timestamp (offset present) — no naive wall-clock ambiguity
        assert records[0]["clock_in"].endswith("+00:00")


class TestBusinessCentralPayload:
    def test_quantity_is_computed_hours_with_idempotency(self, monkeypatch):
        from app.services import business_central_service as bc

        canonical = [{
            "emp_code": "EMP001",
            "att_date": date(2026, 6, 6),
            "check_in": datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
            "check_out": datetime(2026, 6, 6, 20, 0, tzinfo=timezone.utc),
            "work_minutes": 600,
            "overtime_minutes": 60,
            "idempotency_key": "pob-EMP001-2026-06-06",
        }]
        monkeypatch.setattr(
            "app.services.attendance_export.build_daily_attendance",
            lambda db, d: canonical,
        )

        entries = bc._build_time_entries(Mock(), date(2026, 6, 6))
        assert entries[0]["employeeNumber"] == "EMP001"
        # 600 work + 60 OT = 660 min = 11.0 h
        assert entries[0]["quantity"] == 11.0
        # Idempotency key is kept INTERNAL (underscore-prefixed) ...
        assert entries[0]["_idempotency_key"] == "pob-EMP001-2026-06-06"
        # ... and must NOT be sent to BC — its OData API rejects unknown fields (400).
        payload = {k: v for k, v in entries[0].items() if not k.startswith("_")}
        assert "idempotencyKey" not in payload
        assert "_idempotency_key" not in payload
