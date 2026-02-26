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

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-taskdaddy}"

if [ ! -f .env ]; then
  cp .env.example .env
fi
if [ ! -f apps/api/.env ]; then
  cp apps/api/.env.example apps/api/.env
fi
if [ ! -f apps/web/.env ]; then
  cp apps/web/.env.example apps/web/.env
fi

set_env_var() {
  local file="$1"
  local key="$2"
  local val="$3"
  python3 - "$file" "$key" "$val" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
val = sys.argv[3]
lines = path.read_text().splitlines() if path.exists() else []
prefix = key + "="
updated = False
out = []
for line in lines:
  if line.startswith(prefix):
    out.append(f"{key}={val}")
    updated = True
  else:
    out.append(line)
if not updated:
  out.append(f"{key}={val}")
path.write_text("\n".join(out) + "\n")
PY
}

# Local bootstrap must allow HTTP localhost sessions.
set_env_var apps/api/.env COOKIE_SECURE "false"

# Auto-generate strong local secrets if placeholders are still present.
if grep -Eq '^APP_SECRET=($|REPLACE_WITH_STRONG_RANDOM_SECRET)$' apps/api/.env || grep -Eq '^FERNET_KEY=($|REPLACE_WITH_FERNET_KEY)$' apps/api/.env; then
  echo "Generating local secrets for apps/api/.env ..."
  sec_out="$(./scripts/generate_prod_secrets.sh)"
  app_secret="$(printf '%s\n' "$sec_out" | awk -F= '/^APP_SECRET=/{print $2; exit}')"
  fernet_key="$(printf '%s\n' "$sec_out" | awk -F= '/^FERNET_KEY=/{print $2; exit}')"
  if [ -n "${app_secret}" ]; then
    set_env_var apps/api/.env APP_SECRET "${app_secret}"
  fi
  if [ -n "${fernet_key}" ]; then
    set_env_var apps/api/.env FERNET_KEY "${fernet_key}"
  fi
fi

./start.sh

echo
echo "Task-Daddy bootstrap complete."
echo "Web: http://localhost:${WEB_PORT:-3010}"
echo "Login credentials:"
for _ in $(seq 1 45); do
  if ! "${DC[@]}" ps api 2>/dev/null | tail -n +2 | grep -Eiq 'up|running'; then
    sleep 1
    continue
  fi
  if "${DC[@]}" exec -T api sh -lc 'test -f /app/data/backups/bootstrap_credentials.txt' >/dev/null 2>&1; then
    "${DC[@]}" exec -T api cat /app/data/backups/bootstrap_credentials.txt
    exit 0
  fi
  sleep 1
done
echo "Could not read bootstrap credentials yet." >&2
if ! "${DC[@]}" ps api 2>/dev/null | tail -n +2 | grep -Eiq 'up|running'; then
  echo "API service is not running. Recent API logs:" >&2
  "${DC[@]}" logs --tail=120 api || true
else
  echo "Run this to fetch credentials manually:" >&2
  echo "  ${DC[*]} exec api cat /app/data/backups/bootstrap_credentials.txt" >&2
fi
exit 1
