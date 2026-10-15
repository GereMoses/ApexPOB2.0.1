#!/usr/bin/env bash
# Backend test suite on a THROWAWAY database, in a THROWAWAY container.
#   ./scripts/run_tests.sh                 # whole suite
#   ./scripts/run_tests.sh tests/safety    # one folder / file / -k expression
# - builds <DB> from the live schema (no data) and drops it afterwards;
# - runs the CURRENT source (backend/ mounted) in a one-off container from the
#   backend image, on the stack's network with the backend's settings — the live
#   backend container and live data are never touched.
set -euo pipefail
cd "$(dirname "$0")/.."
DB=${TEST_DB_NAME:-pob_suite_test}
PGU='${POSTGRES_USER:-pob_user}'

docker exec pob_postgres sh -c "dropdb --if-exists -U $PGU $DB; createdb -U $PGU $DB"
docker exec pob_postgres sh -c "pg_dump --schema-only -U $PGU \${POSTGRES_DB:-pob_system} | psql -q -U $PGU -d $DB >/dev/null 2>&1"
# A valid licence inside the throwaway DB only (schema-only = no licence row, and
# the licence middleware would answer every request with 402).
docker exec pob_postgres sh -c "psql -q -U $PGU -d $DB -c \"INSERT INTO sys_subscription (installation_id, org_name, tier, max_users, max_employees, max_devices, issue_date, expiry_date, is_active, created_by) VALUES ('TEST', 'Test suite', 'standard', 50, 500, 20, now(), now() + interval '1 year', TRUE, 'tests')\""
ENVF=$(mktemp)
cleanup() { rm -f "$ENVF"; docker exec pob_postgres sh -c "dropdb --if-exists -U $PGU $DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker exec pob_backend env | grep -v -E '^(PATH|HOSTNAME|HOME|PWD|SHLVL|_)=' > "$ENVF"
URL=$(docker exec pob_backend sh -c 'echo $DATABASE_URL' | sed -E "s#/[^/?]+(\?|\$)#/$DB\1#")
NET=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' pob_backend | awk '{print $1}')
IMG=$(docker inspect -f '{{.Config.Image}}' pob_backend)

docker run --rm --network "$NET" --env-file "$ENVF" -e TEST_DATABASE_URL="$URL" -e DATABASE_URL="$URL" \
  -v "$PWD/backend:/app" --tmpfs /app/logs --tmpfs /app/uploads --tmpfs /app/media -w /app "$IMG" python -m pytest -q -p no:warnings -p no:cacheprovider "${@:-tests}"
