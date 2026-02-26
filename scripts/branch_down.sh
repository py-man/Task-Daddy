#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

branch="$(git rev-parse --abbrev-ref HEAD)"
slug="$(echo "${branch}" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-24)"
if [[ -z "${slug}" ]]; then
  echo "Failed to derive branch slug from '${branch}'" >&2
  exit 1
fi

export COMPOSE_PROJECT_NAME="neonlanes_${slug}"
echo "Stopping isolated branch stack: ${COMPOSE_PROJECT_NAME}"
docker-compose down --remove-orphans
