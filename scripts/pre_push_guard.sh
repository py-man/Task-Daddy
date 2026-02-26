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

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-taskdaddy}"
export WEB_PORT="${WEB_PORT:-3010}"
export API_PORT="${API_PORT:-8000}"
export DB_PORT="${DB_PORT:-5432}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export WEB_BIND_HOST="${WEB_BIND_HOST:-127.0.0.1}"
export API_BIND_HOST="${API_BIND_HOST:-127.0.0.1}"
export DB_BIND_HOST="${DB_BIND_HOST:-127.0.0.1}"
export REDIS_BIND_HOST="${REDIS_BIND_HOST:-127.0.0.1}"

./scripts/pre_push_security_gate.sh

echo "pre-push: ensuring taskdaddy stack is up on web=${WEB_PORT} api=${API_PORT}"
"${DC[@]}" up -d

echo "pre-push: smoke on 3010/8000 (non-destructive)"
SMOKE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" SMOKE_RECREATE_STACK=0 SMOKE_WEB_PORT="${WEB_PORT}" SMOKE_API_PORT="${API_PORT}" ./scripts/smoke.sh

echo "pre-push guard passed"
