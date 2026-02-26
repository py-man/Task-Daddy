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
"${DC[@]}" ps
curl -sf http://localhost:8000/health
echo
curl -sf http://localhost:8000/version
echo
curl -sI "http://localhost:${WEB_PORT:-3010}" | head -n 1
