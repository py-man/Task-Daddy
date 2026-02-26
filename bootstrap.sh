set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
fi
if [ ! -f apps/api/.env ]; then
  cp apps/api/.env.example apps/api/.env
fi
if [ ! -f apps/web/.env ]; then
  cp apps/web/.env.example apps/web/.env
fi

./start.sh

