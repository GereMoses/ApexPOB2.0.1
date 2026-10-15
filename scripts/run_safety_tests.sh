#!/usr/bin/env bash
# Go-live safety regression suite (POB, zones, attendance, transport, land journeys).
# Same isolation as run_tests.sh: throwaway database + throwaway container.
set -euo pipefail
cd "$(dirname "$0")/.."
TEST_DB_NAME=pob_safety_test exec ./scripts/run_tests.sh tests/safety "$@"
