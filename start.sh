set -euo pipefail
cd "$(dirname "$0")"
if command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
elif docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  echo "Neither 'docker compose' nor 'docker-compose' is installed." >&2
  exit 1
fi
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" && "${ALLOW_NON_MAIN_START:-0}" != "1" ]]; then
  echo "Refusing start.sh on branch '$BRANCH' to protect production track." >&2
  echo "Use ./scripts/branch_up.sh for isolated non-main testing." >&2
  exit 1
fi
export DEPLOY_TRACK=production
export DEPLOY_BRANCH="$BRANCH"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-taskdaddy}"
./scripts/pre_restart_backup.sh || echo "Warning: pre-restart backup skipped/failed; continuing startup."
"${DC[@]}" stop api web db || true
"${DC[@]}" rm -f api web db || true
"${DC[@]}" up --build -d
