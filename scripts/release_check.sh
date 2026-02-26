#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PHASE="${1:-pre}"
if [[ "$PHASE" != "pre" && "$PHASE" != "post" ]]; then
  echo "Usage: ./scripts/release_check.sh [pre|post]" >&2
  exit 1
fi

log() {
  printf "%s %s\n" "[$(date -u +%Y-%m-%dT%H:%M:%SZ)]" "$*"
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local tries="${3:-60}"
  local delay="${4:-1}"
  local i
  for i in $(seq 1 "$tries"); do
    if curl -sf --max-time 3 "$url" >/dev/null; then
      log "ready $name url=$url"
      return 0
    fi
    sleep "$delay"
  done
  log "not_ready $name url=$url"
  return 1
}

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" && "${ALLOW_NON_MAIN_PROD:-0}" != "1" ]]; then
  echo "Release gate failed: branch '$BRANCH' is not allowed for production deploy." >&2
  echo "Switch to main, or override only if intentional: ALLOW_NON_MAIN_PROD=1" >&2
  exit 1
fi

if [[ ! -f ".env.production" ]]; then
  echo "Release gate failed: missing .env.production" >&2
  exit 1
fi

if [[ "$PHASE" == "pre" ]]; then
  log "release_gate pre: running host backup + config export"
  ./scripts/pre_restart_backup.sh
fi

log "release_gate $PHASE: checking health endpoints"
./scripts/check_port_docs_sync.sh
wait_for_url "http://127.0.0.1:8000/health" "api_health" 90 1
wait_for_url "http://127.0.0.1:3000/version" "web_version" 90 1
wait_for_url "http://127.0.0.1:3000/api/health" "web_api_proxy" 90 1

log "release_gate $PHASE: running smoke (non-destructive)"
SMOKE_RECREATE_STACK=0 API_BASE="http://127.0.0.1:8000" WEB_BASE="http://127.0.0.1:3000" ./scripts/smoke.sh

log "release_gate_ok phase=$PHASE branch=$BRANCH"
