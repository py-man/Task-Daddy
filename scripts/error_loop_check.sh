#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[loop] typecheck"
npm -w @neonlanes/web run typecheck

echo "[loop] smoke"
./scripts/smoke.sh

echo "[loop] quick error scan (api/web logs)"
docker-compose logs --tail=300 api web | rg -n "500 Internal Server Error|Traceback|ERROR|Unhandled Runtime Error|Sync error" || true

echo "[loop] done"
