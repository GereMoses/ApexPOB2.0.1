#!/usr/bin/env bash
# Go-live safety regression suite (POB, zones, attendance, transport, land journeys).
# Builds a THROWAWAY database from the live schema (no data), runs
# backend/tests/safety against it inside the backend container, then drops it.
# Real data is never touched.
set -euo pipefail
cd "$(dirname "$0")/.."
DB=pob_safety_test
PG="psql -q -U \${POSTGRES_USER:-pob_user}"

docker exec pob_postgres sh -c "dropdb --if-exists -U \${POSTGRES_USER:-pob_user} $DB; createdb -U \${POSTGRES_USER:-pob_user} $DB"
docker exec pob_postgres sh -c "pg_dump --schema-only -U \${POSTGRES_USER:-pob_user} \${POSTGRES_DB:-pob_system} | $PG -d $DB >/dev/null 2>&1"
trap 'docker exec pob_postgres sh -c "dropdb --if-exists -U \${POSTGRES_USER:-pob_user} '"$DB"'"' EXIT

docker cp backend/tests/safety pob_backend:/app/tests/
URL=$(docker exec pob_backend sh -c 'echo $DATABASE_URL' | sed -E "s#/[^/]+\$#/$DB#")
docker exec -e TEST_DATABASE_URL="$URL" pob_backend sh -c 'cd /app && python -m pytest -q -p no:warnings tests/safety "$@"' -- "$@"
