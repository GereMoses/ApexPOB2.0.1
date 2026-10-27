#!/usr/bin/env bash
# Reset an ApexPOB login password (run on the server, from the project folder).
#   ./scripts/reset_password.sh            # asks for username + new password
# The password is typed hidden, hashed exactly as the app does, and any login
# lockout for that user is cleared. Nothing is printed or stored in plain text.
set -euo pipefail

read -r -p "Username (e.g. admin or globaladmin): " USERNAME
read -r -s -p "New password (min 10 characters): " PW1; echo
read -r -s -p "Repeat new password: " PW2; echo
[ "$PW1" = "$PW2" ] || { echo "Passwords do not match."; exit 1; }
[ ${#PW1} -ge 10 ] || { echo "Use at least 10 characters."; exit 1; }

RESET_PW="$PW1" docker exec -i -e PYTHONPATH=/app -e RESET_USER="$USERNAME" -e RESET_PW pob_backend python - <<'PY'
import os, sys
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.security import get_password_hash, verify_password

user = os.environ["RESET_USER"]
pw = os.environ["RESET_PW"]
db = SessionLocal()
row = db.execute(text("SELECT id FROM auth_user WHERE username = :u OR email = :u"), {"u": user}).fetchone()
if not row:
    sys.exit(f"No user called {user!r}.")
db.execute(text("UPDATE auth_user SET password = :h, is_active = TRUE WHERE id = :i"),
           {"h": get_password_hash(pw), "i": row.id})
db.commit()
ok = verify_password(pw, db.execute(text("SELECT password FROM auth_user WHERE id = :i"), {"i": row.id}).scalar())
try:  # clear failed-login lockout counters for this user
    from app.core.redis_client import get_redis_client
    r = get_redis_client()
    for pat in (f"*{user}*",):
        for k in r.scan_iter(pat):
            if any(w in k.decode() if isinstance(k, bytes) else k for w in ("login", "lockout", "attempt")):
                r.delete(k)
except Exception:
    pass
print("Password updated for", user, "- verified" if ok else "- VERIFY FAILED")
PY
