set -euo pipefail

PUSHOVER_APP_TOKEN="${PUSHOVER_APP_TOKEN:-}"
PUSHOVER_USER_KEY="${PUSHOVER_USER_KEY:-}"
TITLE="${TITLE:-Task-Daddy}"
MESSAGE="${MESSAGE:-Task-Daddy is ready.}"

if [ -z "$PUSHOVER_APP_TOKEN" ] || [ -z "$PUSHOVER_USER_KEY" ]; then
  echo "missing PUSHOVER_APP_TOKEN or PUSHOVER_USER_KEY" >&2
  exit 2
fi

curl -sS https://api.pushover.net/1/messages.json \
  -d "token=$PUSHOVER_APP_TOKEN" \
  -d "user=$PUSHOVER_USER_KEY" \
  -d "title=$TITLE" \
  -d "message=$MESSAGE" >/dev/null

echo "ok"

