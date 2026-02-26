set -euo pipefail
cd "$(dirname "$0")"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" && "${ALLOW_NON_MAIN_RESET:-0}" != "1" ]]; then
  echo "Refusing reset.sh on branch '$BRANCH' to protect production track." >&2
  echo "Use ./scripts/branch_down.sh then ./scripts/branch_up.sh for isolated non-main testing." >&2
  exit 1
fi
export DEPLOY_TRACK=production
export DEPLOY_BRANCH="$BRANCH"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-neonlanes}"
./scripts/pre_restart_backup.sh
docker-compose down -v --remove-orphans
docker-compose up --build -d
