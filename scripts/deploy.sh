#!/usr/bin/env bash
# Build and (re)start ApexPOB services, then VERIFY the result.
#   ./scripts/deploy.sh                      # backend, celery-worker, celery-beat, frontend
#   ./scripts/deploy.sh backend frontend     # just these
# Docker Desktop sometimes recreates a container on only ONE of its networks. The
# backend then can't reach postgres/redis (sign-in fails) and the Celery worker
# can't reach the internet (no email / WhatsApp alerts) — silently. This script
# re-attaches any missing network and checks reachability before calling it done.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)
SERVICES=("$@")
[ ${#SERVICES[@]} -eq 0 ] && SERVICES=(backend celery-worker celery-beat frontend)

# Never ship a backend that doesn't even compile (a syntax error crash-loops it
# and takes sign-in down with it).
if printf '%s\n' "${SERVICES[@]}" | grep -qE '^(backend|celery-worker|celery-beat)$'; then
  echo "▶ compiling backend"
  # services/mustering_ai_analytics.py is dead code (never imported) that has not
  # compiled since the first commit — excluded until it is removed.
  if ! out=$(python3 -m compileall -q -x 'mustering_ai_analytics\.py' backend/app 2>&1); then
    echo "✗ backend has a syntax error — not deploying"; echo "$out" | grep -A4 "Error compiling" | head -20; exit 1
  fi
fi
echo "▶ building: ${SERVICES[*]}"
"${COMPOSE[@]}" build "${SERVICES[@]}" | grep -E "naming to|ERROR|Failed to compile" || true
echo "▶ starting"
"${COMPOSE[@]}" up -d --no-deps "${SERVICES[@]}" 2>&1 | tail -n 3

echo "▶ checking networks"
for svc in "${SERVICES[@]}"; do
  cname=$("${COMPOSE[@]}" ps -q "$svc" | head -1)
  [ -z "$cname" ] && { echo "  ✗ $svc is not running"; exit 1; }
  want=$("${COMPOSE[@]}" config --format json | python3 -c "
import json,sys; c=json.load(sys.stdin); n=c['services']['$svc'].get('networks') or {}
print(' '.join(sorted((c['networks'][k].get('name') or k) for k in n)))")
  have=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$cname")
  restart=0
  for net in $want; do
    if [[ " $have " != *" $net "* ]]; then
      echo "  ↻ $svc was missing $net — attaching"
      docker network connect "$net" "$cname"; restart=1
    fi
  done
  [ $restart -eq 1 ] && docker restart "$cname" >/dev/null
  echo "  ✓ $svc: $want"
done

echo "▶ checking reachability"
sleep 10
docker exec pob_backend python -c "
import socket
for h in ('postgres', 'redis'): socket.getaddrinfo(h, 0)
print('  ✓ backend → postgres, redis')"
docker exec pob_celery_worker python -c "
import socket
for h in ('postgres', 'redis'): socket.getaddrinfo(h, 0)
socket.create_connection(('graph.facebook.com', 443), timeout=8)
print('  ✓ celery worker → postgres, redis, internet (email / WhatsApp)')"
# The backend takes a while to boot after a restart — wait for it, then insist on 200.
for _ in $(seq 1 60); do
  code=$(curl -sk -o /dev/null -w '%{http_code}' https://localhost/health || true)
  [ "$code" = "200" ] && break
  sleep 3
done
if [ "$code" != "200" ]; then
  echo "  ✗ https://localhost/health → $code after 3 minutes"; docker logs --tail 20 pob_backend; exit 1
fi
echo "  ✓ https://localhost/health → 200"
echo "✅ deployed"
