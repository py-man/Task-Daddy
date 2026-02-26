set -euo pipefail
cd "$(dirname "$0")"
docker-compose ps
curl -sf http://localhost:8000/health
echo
curl -sf http://localhost:8000/version
echo
curl -sI http://localhost:3005 | head -n 1
