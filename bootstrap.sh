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

# Auto-generate strong local secrets if placeholders are still present.
if grep -Eq '^APP_SECRET=(|REPLACE_WITH_STRONG_RANDOM_SECRET)$' apps/api/.env || grep -Eq '^FERNET_KEY=(|REPLACE_WITH_FERNET_KEY)$' apps/api/.env; then
  echo "Generating local secrets for apps/api/.env ..."
  sec_out="$(./scripts/generate_prod_secrets.sh)"
  app_secret="$(printf '%s\n' "$sec_out" | awk -F= '/^APP_SECRET=/{print $2; exit}')"
  fernet_key="$(printf '%s\n' "$sec_out" | awk -F= '/^FERNET_KEY=/{print $2; exit}')"
  if [ -n "${app_secret}" ]; then
    sed -i "s|^APP_SECRET=.*|APP_SECRET=${app_secret}|" apps/api/.env
  fi
  if [ -n "${fernet_key}" ]; then
    sed -i "s|^FERNET_KEY=.*|FERNET_KEY=${fernet_key}|" apps/api/.env
  fi
fi

./start.sh

echo
echo "Task-Daddy bootstrap complete."
echo "Web: http://localhost:${WEB_PORT:-3010}"
echo "Login credentials:"
for _ in $(seq 1 30); do
  if docker compose exec -T api sh -lc 'test -f /app/data/backups/bootstrap_credentials.txt' >/dev/null 2>&1; then
    docker compose exec -T api cat /app/data/backups/bootstrap_credentials.txt
    exit 0
  fi
  sleep 1
done
echo "Could not read bootstrap credentials yet. Run:"
echo "  docker compose exec api cat /app/data/backups/bootstrap_credentials.txt"
