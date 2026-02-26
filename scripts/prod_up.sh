#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" && "${ALLOW_NON_MAIN_PROD:-0}" != "1" ]]; then
  echo "Refusing production deploy from branch '$BRANCH'. Switch to 'main' first." >&2
  echo "Override only if intentional: ALLOW_NON_MAIN_PROD=1 ./scripts/prod_up.sh" >&2
  exit 1
fi

if [[ ! -f ".env.production" ]]; then
  echo "Missing .env.production" >&2
  exit 1
fi

export DEPLOY_TRACK=production
export DEPLOY_BRANCH="$BRANCH"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-neonlanes}"

./scripts/release_check.sh pre

set -a
source .env.production
set +a

COMPOSE_IGNORE_ORPHANS=1 docker-compose -f docker-compose.prod.yml -f docker-compose.https.yml up -d --build

echo "Production stack deploy requested from branch: $BRANCH"
curl -fsS -m 8 http://127.0.0.1:3000/version >/dev/null
echo "Local web check passed: http://127.0.0.1:3000/version"
./scripts/release_check.sh post
