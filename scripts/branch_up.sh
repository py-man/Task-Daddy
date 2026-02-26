#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${branch}" == "main" ]]; then
  echo "Refusing branch_up on 'main'. Use ./start.sh or ./scripts/prod_up.sh for production track." >&2
  exit 1
fi

slug="$(echo "${branch}" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-24)"
if [[ -z "${slug}" ]]; then
  echo "Failed to derive branch slug from '${branch}'" >&2
  exit 1
fi

# Stable-ish offset from branch slug to avoid collisions.
sum="$(echo -n "${slug}" | cksum | awk '{print $1}')"
offset="$(( sum % 200 ))"

export COMPOSE_PROJECT_NAME="neonlanes_${slug}"
export DEPLOY_TRACK="branch-test"
export DEPLOY_BRANCH="${branch}"
export WEB_PORT="$(( 3200 + offset ))"
export API_PORT="$(( 8200 + offset ))"
export DB_PORT="$(( 5500 + offset ))"
export REDIS_PORT="$(( 6600 + offset ))"

echo "Starting isolated branch stack:"
echo "  branch=${branch}"
echo "  project=${COMPOSE_PROJECT_NAME}"
echo "  web=http://localhost:${WEB_PORT}"
echo "  api=http://localhost:${API_PORT}"
echo "  db_port=${DB_PORT}"
echo "  redis_port=${REDIS_PORT}"

docker-compose up -d --build
