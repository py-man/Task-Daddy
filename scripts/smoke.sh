#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Safety: always isolate smoke from live stacks by using a dedicated
# Compose project name unless explicitly overridden.
SMOKE_PROJECT_NAME="${SMOKE_PROJECT_NAME:-taskdaddy_smoke}"
export COMPOSE_PROJECT_NAME="$SMOKE_PROJECT_NAME"

dc() {
  docker-compose "$@"
}

log() {
  printf "%s %s\n" "[$(date -u +%Y-%m-%dT%H:%M:%SZ)]" "$*"
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local tries="${3:-120}"
  local delay="${4:-1}"
  local i
  for i in $(seq 1 "$tries"); do
    if curl -sf --max-time 2 "$url" >/dev/null; then
      log "ready $name url=$url"
      return 0
    fi
    sleep "$delay"
  done
  log "not_ready $name url=$url"
  dc ps || true
  dc logs --tail=200 api web || true
  return 1
}

totp_now() {
  local secret="$1"
  python3 - "$secret" <<'PY'
import base64, hashlib, hmac, struct, sys, time
secret = sys.argv[1].strip().upper().replace(" ", "")
key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
counter = int(time.time()) // 30
msg = struct.pack(">Q", counter)
digest = hmac.new(key, msg, hashlib.sha1).digest()
offset = digest[-1] & 0x0F
code = ((digest[offset] & 0x7F) << 24) | ((digest[offset+1] & 0xFF) << 16) | ((digest[offset+2] & 0xFF) << 8) | (digest[offset+3] & 0xFF)
print(f"{code % 1_000_000:06d}")
PY
}

SMOKE_EMAIL="${SMOKE_EMAIL:-}"
SMOKE_PASSWORD="${SMOKE_PASSWORD:-}"
SMOKE_API_PORT="${SMOKE_API_PORT:-28000}"
SMOKE_WEB_PORT="${SMOKE_WEB_PORT:-23105}"
SMOKE_DB_PORT="${SMOKE_DB_PORT:-25432}"
SMOKE_REDIS_PORT="${SMOKE_REDIS_PORT:-26379}"
SMOKE_POSTGRES_PASSWORD="${SMOKE_POSTGRES_PASSWORD:-change-me-local}"
export API_PORT="${API_PORT:-$SMOKE_API_PORT}"
export WEB_PORT="${WEB_PORT:-$SMOKE_WEB_PORT}"
export DB_PORT="${DB_PORT:-$SMOKE_DB_PORT}"
export REDIS_PORT="${REDIS_PORT:-$SMOKE_REDIS_PORT}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$SMOKE_POSTGRES_PASSWORD}"
API_BASE="${API_BASE:-http://127.0.0.1:$API_PORT}"
WEB_BASE="${WEB_BASE:-http://127.0.0.1:$WEB_PORT}"
SMOKE_RECREATE_STACK="${SMOKE_RECREATE_STACK:-1}"
SMOKE_EXPECT_MARKETING="${SMOKE_EXPECT_MARKETING:-0}"
SMOKE_EXPECT_3D_LAB="${SMOKE_EXPECT_3D_LAB:-0}"
SMOKE_BOOTSTRAP_ADMIN_EMAIL="${SMOKE_BOOTSTRAP_ADMIN_EMAIL:-smoke.admin@taskdaddy.local}"

SMOKE_RUN_ID="$(date +%s%N)-$RANDOM"

if [ -z "$SMOKE_EMAIL" ]; then
  SMOKE_EMAIL="$SMOKE_BOOTSTRAP_ADMIN_EMAIL"
fi
if [ -z "$SMOKE_PASSWORD" ]; then
  SMOKE_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(20))')"
fi

if [ "$SMOKE_RECREATE_STACK" = "1" ]; then
  # Full teardown keeps smoke DB credentials deterministic across runs.
  dc down -v --remove-orphans || true
  dc up --build -d
fi

wait_for_url "$API_BASE/health" "api" 120 1
wait_for_url "$API_BASE/version" "api_version" 60 1
wait_for_url "$WEB_BASE/version" "web" 120 1
wait_for_url "$WEB_BASE/api/health" "web_api_proxy" 60 1
if [ "$SMOKE_EXPECT_3D_LAB" = "1" ]; then
  log "check_3d_lab_route"
  wait_for_url "$WEB_BASE/lab/neon-3d" "web_lab_3d" 120 1
  curl -sf --max-time 8 "$WEB_BASE/lab/neon-3d" | grep -q "Task-Daddy 3D UX Lab"
fi
if [ "$SMOKE_EXPECT_MARKETING" = "1" ]; then
  log "check_marketing_route"
  wait_for_url "$WEB_BASE/marketing" "web_marketing" 120 1
  curl -sf --max-time 8 "$WEB_BASE/marketing" | grep -q "Move work at the speed of clarity"
fi
log "check_bg_layer"
curl -sf --max-time 5 "$WEB_BASE/login" | grep -q 'data-testid="bg-layer"'

log "bootstrap_ephemeral_admin email=$SMOKE_EMAIL"
dc exec -T api bash -lc "cd /app && SMOKE_ADMIN_EMAIL='$SMOKE_EMAIL' SMOKE_ADMIN_PASSWORD='$SMOKE_PASSWORD' python - <<'PY'
import asyncio, os
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User
from app.security import hash_password

EMAIL = os.environ['SMOKE_ADMIN_EMAIL'].strip().lower()
PASSWORD = os.environ['SMOKE_ADMIN_PASSWORD']

async def main():
    async with SessionLocal() as db:
        res = await db.execute(select(User).where(User.email == EMAIL))
        u = res.scalar_one_or_none()
        if u is None:
            u = User(
                email=EMAIL,
                name='Smoke Admin',
                role='admin',
                password_hash=hash_password(PASSWORD),
                avatar_url=None,
                timezone='UTC',
                jira_account_id=None,
                active=True,
                login_disabled=False,
                mfa_enabled=False,
                mfa_secret_encrypted=None,
                mfa_recovery_codes_encrypted=None,
            )
            db.add(u)
        else:
            u.name = 'Smoke Admin'
            u.role = 'admin'
            u.password_hash = hash_password(PASSWORD)
            u.active = True
            u.login_disabled = False
            u.mfa_enabled = False
            u.mfa_secret_encrypted = None
            u.mfa_recovery_codes_encrypted = None
        await db.commit()

asyncio.run(main())
PY"

COOKIE_JAR="/tmp/taskdaddy.cookies"
rm -f "$COOKIE_JAR"
COOKIE_HEADERS="/tmp/taskdaddy.cookies.headers"
AUTH_COOKIE_HEADER=""

extract_session_cookie() {
  local headers_file="$1"
  awk 'BEGIN{IGNORECASE=1} /^Set-Cookie:/{print}' "$headers_file" \
    | sed -n 's/^Set-Cookie:[[:space:]]*nl_session=\([^;]*\).*/\1/ip' \
    | tail -n1
}

log "login email=$SMOKE_EMAIL"
LOGIN_BODY="$(printf '{"email":"%s","password":"%s"}' "$SMOKE_EMAIL" "$SMOKE_PASSWORD")"
LOGIN_RESP="$(curl -sS --max-time 8 -D "$COOKIE_HEADERS" -c "$COOKIE_JAR" -X POST "$API_BASE/auth/login" -H "Content-Type: application/json" --data "$LOGIN_BODY" -w "\n%{http_code}")"
LOGIN_CODE="$(printf "%s" "$LOGIN_RESP" | tail -n 1)"
LOGIN_JSON="$(printf "%s" "$LOGIN_RESP" | sed '$d')"
if [ "$LOGIN_CODE" != "200" ]; then
  echo "login_failed status=$LOGIN_CODE body=$LOGIN_JSON" >&2
  exit 1
fi
SESSION_COOKIE="$(extract_session_cookie "$COOKIE_HEADERS")"
if [ -z "$SESSION_COOKIE" ]; then
  echo "login_cookie_missing body=$LOGIN_JSON" >&2
  exit 1
fi
AUTH_COOKIE_HEADER="Cookie: nl_session=$SESSION_COOKIE"

log "mfa_start"
MFA_START_RESP="$(curl -sS --max-time 8 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/auth/mfa/start" -H "Content-Type: application/json" --data "{\"password\":\"$SMOKE_PASSWORD\"}" -w "\n%{http_code}")"
MFA_START_CODE="$(printf "%s" "$MFA_START_RESP" | tail -n 1)"
MFA_START_JSON="$(printf "%s" "$MFA_START_RESP" | sed '$d')"
if [ "$MFA_START_CODE" != "200" ]; then
  echo "mfa_start_failed status=$MFA_START_CODE body=$MFA_START_JSON" >&2
  exit 1
fi
MFA_SECRET="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["secret"])' "$MFA_START_JSON")"
MFA_CODE="$(totp_now "$MFA_SECRET")"

log "mfa_confirm"
MFA_CONFIRM_RESP="$(curl -sS --max-time 8 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/auth/mfa/confirm" -H "Content-Type: application/json" --data "{\"totpCode\":\"$MFA_CODE\"}" -w "\n%{http_code}")"
MFA_CONFIRM_CODE="$(printf "%s" "$MFA_CONFIRM_RESP" | tail -n 1)"
if [ "$MFA_CONFIRM_CODE" != "200" ]; then
  echo "mfa_confirm_failed status=$MFA_CONFIRM_CODE body=$(printf "%s" "$MFA_CONFIRM_RESP" | sed '$d')" >&2
  exit 1
fi

# Re-login with TOTP to guarantee MFA-verified session for admin-only token operations.
MFA_CODE="$(totp_now "$MFA_SECRET")"
log "login_mfa_verified"
LOGIN_MFA_RESP="$(curl -sS --max-time 8 -D "$COOKIE_HEADERS" -c "$COOKIE_JAR" -X POST "$API_BASE/auth/login" -H "Content-Type: application/json" --data "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\",\"totpCode\":\"$MFA_CODE\"}" -w "\n%{http_code}")"
LOGIN_MFA_CODE="$(printf "%s" "$LOGIN_MFA_RESP" | tail -n 1)"
if [ "$LOGIN_MFA_CODE" != "200" ]; then
  echo "login_mfa_failed status=$LOGIN_MFA_CODE body=$(printf "%s" "$LOGIN_MFA_RESP" | sed '$d')" >&2
  exit 1
fi
SESSION_COOKIE="$(extract_session_cookie "$COOKIE_HEADERS")"
if [ -z "$SESSION_COOKIE" ]; then
  # Fallback to previous cookie in case API does not rotate session cookie on MFA login.
  SESSION_COOKIE="$(printf "%s" "$AUTH_COOKIE_HEADER" | sed 's/^Cookie: nl_session=//')"
fi
AUTH_COOKIE_HEADER="Cookie: nl_session=$SESSION_COOKIE"

log "whoami"
ME_JSON="$(curl -sf --max-time 5 -H "$AUTH_COOKIE_HEADER" "$API_BASE/auth/me")"
USER_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$ME_JSON")"
USER_ROLE="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("role",""))' "$ME_JSON")"
if [ "$USER_ROLE" != "admin" ]; then
  echo "smoke_user_not_admin role=$USER_ROLE" >&2
  exit 1
fi

SMOKE_BOARD_NAME="Smoke Board $SMOKE_RUN_ID"
log "create_board name=$SMOKE_BOARD_NAME"
BOARD_RESP="$(curl -sS --max-time 5 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/boards" -H "Content-Type: application/json" --data "{\"name\":\"$SMOKE_BOARD_NAME\"}" -w "\n%{http_code}")"
BOARD_CODE="$(printf "%s" "$BOARD_RESP" | tail -n 1)"
BOARD_JSON="$(printf "%s" "$BOARD_RESP" | sed '$d')"
if [ "$BOARD_CODE" != "200" ]; then
  echo "board_create_failed status=$BOARD_CODE body=$BOARD_JSON" >&2
  exit 1
fi
BOARD_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$BOARD_JSON")"

SMOKE_WEBHOOK_SOURCE="smoke-$SMOKE_RUN_ID"
cleanup() {
  if [ -n "${BOARD_ID:-}" ]; then
    curl -sS --max-time 5 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/boards/$BOARD_ID/delete" -H "Content-Type: application/json" --data '{"mode":"delete"}' >/dev/null || true
  fi
  if [ -n "${SMOKE_WEBHOOK_SOURCE:-}" ]; then
    curl -sS --max-time 5 -H "$AUTH_COOKIE_HEADER" -X DELETE "$API_BASE/webhooks/secrets/$SMOKE_WEBHOOK_SOURCE" >/dev/null || true
  fi
}
trap cleanup EXIT

log "list_lanes"
LANES_JSON="$(curl -sf --max-time 5 -H "$AUTH_COOKIE_HEADER" "$API_BASE/boards/$BOARD_ID/lanes")"
FIRST_LANE_ID="$(python3 -c 'import json,sys; a=json.loads(sys.argv[1]); print(a[0]["id"])' "$LANES_JSON")"
SECOND_LANE_ID="$(python3 -c 'import json,sys; a=json.loads(sys.argv[1]); print(a[1]["id"])' "$LANES_JSON")"

log "create_task"
TASK_JSON="$(curl -sf --max-time 5 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/boards/$BOARD_ID/tasks" -H "Content-Type: application/json" --data "{\"laneId\":\"$FIRST_LANE_ID\",\"title\":\"Smoke task\",\"priority\":\"P2\",\"type\":\"Feature\",\"ownerId\":\"$USER_ID\"}")"
TASK_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$TASK_JSON")"
TASK_VERSION="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["version"])' "$TASK_JSON")"

log "move_task"
curl -sf --max-time 5 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/tasks/$TASK_ID/move" -H "Content-Type: application/json" --data "{\"laneId\":\"$SECOND_LANE_ID\",\"toIndex\":0,\"version\":$TASK_VERSION}" >/dev/null

log "audit_list"
curl -sf --max-time 5 -H "$AUTH_COOKIE_HEADER" "$API_BASE/audit?boardId=$BOARD_ID" >/dev/null

log "ai_summarize"
curl -sf --max-time 10 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/ai/task/$TASK_ID/summarize" -H "Content-Type: application/json" --data '{}' >/dev/null

log "api_token_create"
TOKEN_RESP="$(curl -sS --max-time 8 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/auth/tokens" -H "Content-Type: application/json" --data "{\"name\":\"smoke-$SMOKE_RUN_ID\",\"password\":\"$SMOKE_PASSWORD\"}" -w "\n%{http_code}")"
TOKEN_CODE="$(printf "%s" "$TOKEN_RESP" | tail -n 1)"
TOKEN_JSON="$(printf "%s" "$TOKEN_RESP" | sed '$d')"
if [ "$TOKEN_CODE" != "200" ]; then
  echo "api_token_create_failed status=$TOKEN_CODE body=$TOKEN_JSON" >&2
  exit 1
fi
API_TOKEN="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["token"])' "$TOKEN_JSON")"
API_TOKEN_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["apiToken"]["id"])' "$TOKEN_JSON")"

log "api_token_me"
TOKEN_ME="$(curl -sS --max-time 5 -H "Authorization: Bearer $API_TOKEN" "$API_BASE/auth/me" -w "\n%{http_code}")"
TOKEN_ME_CODE="$(printf "%s" "$TOKEN_ME" | tail -n 1)"
if [ "$TOKEN_ME_CODE" != "200" ]; then
  echo "api_token_me_failed status=$TOKEN_ME_CODE body=$(printf "%s" "$TOKEN_ME" | sed '$d')" >&2
  exit 1
fi

log "api_token_revoke"
REVOKE_RESP="$(curl -sS --max-time 8 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/auth/tokens/$API_TOKEN_ID/revoke" -H "Content-Type: application/json" --data "{\"password\":\"$SMOKE_PASSWORD\"}" -w "\n%{http_code}")"
REVOKE_CODE="$(printf "%s" "$REVOKE_RESP" | tail -n 1)"
if [ "$REVOKE_CODE" != "200" ]; then
  echo "api_token_revoke_failed status=$REVOKE_CODE body=$(printf "%s" "$REVOKE_RESP" | sed '$d')" >&2
  exit 1
fi

log "api_token_denied_after_revoke"
TOKEN_DENIED="$(curl -sS --max-time 5 -H "Authorization: Bearer $API_TOKEN" "$API_BASE/auth/me" -w "\n%{http_code}")"
TOKEN_DENIED_CODE="$(printf "%s" "$TOKEN_DENIED" | tail -n 1)"
if [ "$TOKEN_DENIED_CODE" != "401" ]; then
  echo "api_token_revoke_not_effective status=$TOKEN_DENIED_CODE body=$(printf "%s" "$TOKEN_DENIED" | sed '$d')" >&2
  exit 1
fi

SMOKE_WEBHOOK_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
log "webhook_secret_upsert source=$SMOKE_WEBHOOK_SOURCE"
WHS_RESP="$(curl -sS --max-time 8 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/webhooks/secrets" -H "Content-Type: application/json" --data "{\"source\":\"$SMOKE_WEBHOOK_SOURCE\",\"enabled\":true,\"bearerToken\":\"$SMOKE_WEBHOOK_TOKEN\"}" -w "\n%{http_code}")"
WHS_CODE="$(printf "%s" "$WHS_RESP" | tail -n 1)"
if [ "$WHS_CODE" != "200" ]; then
  echo "webhook_secret_upsert_failed status=$WHS_CODE body=$(printf "%s" "$WHS_RESP" | sed '$d')" >&2
  exit 1
fi

log "webhook_inbound_create_task"
WH_IDEMP="smoke-webhook-$SMOKE_RUN_ID"
WH_BODY="$(printf '{"action":"create_task","boardName":"%s","title":"Webhook smoke %s","description":"created by smoke webhook"}' "$SMOKE_BOARD_NAME" "$SMOKE_RUN_ID")"
WH_RESP="$(curl -sS --max-time 10 -X POST "$API_BASE/webhooks/inbound/$SMOKE_WEBHOOK_SOURCE" -H "Content-Type: application/json" -H "Authorization: Bearer $SMOKE_WEBHOOK_TOKEN" -H "Idempotency-Key: $WH_IDEMP" --data "$WH_BODY" -w "\n%{http_code}")"
WH_CODE="$(printf "%s" "$WH_RESP" | tail -n 1)"
WH_JSON="$(printf "%s" "$WH_RESP" | sed '$d')"
if [ "$WH_CODE" != "200" ]; then
  echo "webhook_inbound_failed status=$WH_CODE body=$WH_JSON" >&2
  exit 1
fi
WH_TASK_ID="$(python3 -c 'import json,sys; j=json.loads(sys.argv[1]); print((j.get("result") or {}).get("taskId") or "")' "$WH_JSON")"
if [ -z "$WH_TASK_ID" ]; then
  echo "webhook_inbound_missing_task_id body=$WH_JSON" >&2
  exit 1
fi

log "webhook_events_list"
WHE_RESP="$(curl -sS --max-time 8 -H "$AUTH_COOKIE_HEADER" "$API_BASE/webhooks/events?source=$SMOKE_WEBHOOK_SOURCE&limit=5" -w "\n%{http_code}")"
WHE_CODE="$(printf "%s" "$WHE_RESP" | tail -n 1)"
WHE_JSON="$(printf "%s" "$WHE_RESP" | sed '$d')"
if [ "$WHE_CODE" != "200" ]; then
  echo "webhook_events_list_failed status=$WHE_CODE body=$WHE_JSON" >&2
  exit 1
fi
WHE_COUNT="$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1])))' "$WHE_JSON")"
if [ "$WHE_COUNT" -lt 1 ]; then
  echo "webhook_events_empty source=$SMOKE_WEBHOOK_SOURCE" >&2
  exit 1
fi

log "delete_board"
curl -sf --max-time 5 -H "$AUTH_COOKIE_HEADER" -X POST "$API_BASE/boards/$BOARD_ID/delete" -H "Content-Type: application/json" --data '{"mode":"delete"}' >/dev/null
BOARD_ID=""

log "webhook_secret_disable"
curl -sf --max-time 8 -H "$AUTH_COOKIE_HEADER" -X DELETE "$API_BASE/webhooks/secrets/$SMOKE_WEBHOOK_SOURCE" >/dev/null
SMOKE_WEBHOOK_SOURCE=""

echo "smoke_ok web=$WEB_BASE api=$API_BASE version=$(curl -sf "$API_BASE/version" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
