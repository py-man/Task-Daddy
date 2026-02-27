#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${SKIP_TASKDADDY_PREPUSH:-0}" == "1" ]]; then
  echo "pre-push guard skipped (SKIP_TASKDADDY_PREPUSH=1)"
  exit 0
fi

if command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
elif docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  echo "pre-push guard failed: docker-compose/docker compose not found" >&2
  exit 1
fi

./scripts/pre_push_security_gate.sh

echo "pre-push: isolated smoke stack (never touches live containers)"
SMOKE_PROJECT_NAME="${SMOKE_PROJECT_NAME:-taskdaddy_smoke_prepush}" \
SMOKE_RECREATE_STACK=1 \
SMOKE_WEB_PORT="${SMOKE_WEB_PORT:-33110}" \
SMOKE_API_PORT="${SMOKE_API_PORT:-38010}" \
SMOKE_DB_PORT="${SMOKE_DB_PORT:-35432}" \
SMOKE_REDIS_PORT="${SMOKE_REDIS_PORT:-36379}" \
./scripts/smoke.sh

echo "pre-push guard passed"
