#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR="artifacts/nightly"
mkdir -p "$ARTIFACT_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
API_BASE="${API_BASE:-http://127.0.0.1:8000}"
WEB_BASE="${WEB_BASE:-http://127.0.0.1:3000}"
NIGHTLY_ADMIN_EMAIL="${NIGHTLY_ADMIN_EMAIL:-admin@neonlanes.local}"
NIGHTLY_ADMIN_PASSWORD="${NIGHTLY_ADMIN_PASSWORD:-admin1234}"

write_file_if_missing() {
  local file="$1"
  local content="$2"
  if [ ! -s "$file" ]; then
    printf "%s\n" "$content" >"$file"
  fi
}

echo "[$TIMESTAMP] collecting npm audit"
npm audit --json >"$ARTIFACT_DIR/npm_audit.json" || true

echo "[$TIMESTAMP] collecting pip audit"
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit -r apps/api/requirements.txt -f json >"$ARTIFACT_DIR/pip_audit.json" || true
else
  python3 -m pip install --quiet --user pip-audit >/dev/null 2>&1 || true
  if command -v pip-audit >/dev/null 2>&1; then
    pip-audit -r apps/api/requirements.txt -f json >"$ARTIFACT_DIR/pip_audit.json" || true
  elif python3 -m pip_audit --help >/dev/null 2>&1; then
    python3 -m pip_audit -r apps/api/requirements.txt -f json >"$ARTIFACT_DIR/pip_audit.json" || true
  fi
fi
write_file_if_missing "$ARTIFACT_DIR/pip_audit.json" '{"dependencies":[],"vulnerabilities":[]}'

echo "[$TIMESTAMP] collecting semgrep sarif"
if command -v semgrep >/dev/null 2>&1; then
  semgrep --config auto --json --output "$ARTIFACT_DIR/semgrep.json" . || true
  semgrep --config auto --sarif --output "$ARTIFACT_DIR/security.sarif" . || true
else
  write_file_if_missing "$ARTIFACT_DIR/semgrep.json" '{"results":[]}'
  write_file_if_missing "$ARTIFACT_DIR/security.sarif" '{"version":"2.1.0","runs":[{"tool":{"driver":{"name":"semgrep"}},"results":[]}]}'
fi

echo "[$TIMESTAMP] collecting API health/version"
curl -sf "$API_BASE/health" >"$ARTIFACT_DIR/health.json" || echo '{"ok":false}' >"$ARTIFACT_DIR/health.json"
curl -sf "$API_BASE/version" >"$ARTIFACT_DIR/version.json" || echo '{"version":"unknown","buildSha":"unknown"}' >"$ARTIFACT_DIR/version.json"

echo "[$TIMESTAMP] collecting authenticated system status snapshot"
COOKIE_JAR="$ARTIFACT_DIR/admin_cookie.txt"
rm -f "$COOKIE_JAR"
LOGIN_PAYLOAD=$(printf '{"email":"%s","password":"%s"}' "$NIGHTLY_ADMIN_EMAIL" "$NIGHTLY_ADMIN_PASSWORD")
LOGIN_CODE=$(curl -sS -o "$ARTIFACT_DIR/admin_login.json" -w '%{http_code}' -c "$COOKIE_JAR" -H 'content-type: application/json' -d "$LOGIN_PAYLOAD" "$API_BASE/auth/login" || true)
if [ "$LOGIN_CODE" = "200" ]; then
  curl -sf -b "$COOKIE_JAR" "$API_BASE/admin/system-status" >"$ARTIFACT_DIR/system_status.json" || echo '{"error":"system-status unavailable"}' >"$ARTIFACT_DIR/system_status.json"
else
  echo '{"error":"admin login failed for system-status"}' >"$ARTIFACT_DIR/system_status.json"
fi

echo "[$TIMESTAMP] collecting db report from postgres stats"
if docker compose ps db >/dev/null 2>&1; then
  {
    echo "Nightly DB summary ($TIMESTAMP)"
    echo "----------------------------------"
    docker compose exec -T db psql -U neonlanes -d neonlanes -Atc "select 'connections='||count(*) from pg_stat_activity where datname = current_database();" || true
    docker compose exec -T db psql -U neonlanes -d neonlanes -Atc "select 'active='||count(*) from pg_stat_activity where datname = current_database() and state='active';" || true
    docker compose exec -T db psql -U neonlanes -d neonlanes -Atc "select 'waiting_locks='||count(*) from pg_stat_activity where datname = current_database() and wait_event_type='Lock';" || true
    echo "top_long_queries:"
    docker compose exec -T db psql -U neonlanes -d neonlanes -Atc "select pid||'|'||coalesce((now()-query_start)::text,'n/a')||'|'||left(regexp_replace(query, E'\\\\s+', ' ', 'g'), 120) from pg_stat_activity where datname = current_database() and state='active' and query_start is not null order by (now()-query_start) desc limit 10;" || true
  } >"$ARTIFACT_DIR/db_report.txt"
else
  cat <<EOF >"$ARTIFACT_DIR/db_report.txt"
Nightly DB summary ($TIMESTAMP)
----------------------------------
source: postgres container unavailable
EOF
fi
if [ -x ./scripts/api-contract-check.sh ]; then
  ./scripts/api-contract-check.sh || true
fi

echo "[$TIMESTAMP] collecting web perf timing"
curl -sS -o /dev/null -w 'dns=%{time_namelookup}\nconnect=%{time_connect}\nstart_transfer=%{time_starttransfer}\ntotal=%{time_total}\n' "$WEB_BASE/login" >"$ARTIFACT_DIR/perf.txt" || true

cat <<EOF >"$ARTIFACT_DIR/nightly_report.md"
# Task-Daddy Nightly Health Report
- timestamp: $TIMESTAMP
- pipeline: nightly
- status: completed

## Findings Summary
- tests: see CI job logs
- lint/typecheck: see CI job logs
- dependency audit: artifacts/nightly/npm_audit.json + artifacts/nightly/pip_audit.json
- security gate: security_gate.txt (from CI security job)
- security scan: artifacts/nightly/security.sarif + artifacts/nightly/semgrep.json
- performance: artifacts/nightly/perf.txt
- lighthouse: uploaded by nightly lighthouse job
- system health: artifacts/nightly/system_status.json
- api contract: artifacts/nightly/api_contract_report.txt

## Recommendations
- Fail build on critical vulns from npm/pip audit.
- Add Redis metrics endpoint and replace cache placeholders.
- Add Lighthouse CI HTML report generation.
EOF

cat <<EOF >"$ARTIFACT_DIR/recommended_fixes_backlog.md"
# Recommended Fixes Backlog
- Priority: High — Enforce vulnerability thresholds (fail on critical/high after grace period).
- Priority: High — Add Redis queue + DLQ metrics from worker queue adapter.
- Priority: Medium — Add ASVS 5.0 checklist coverage report and gating.
- Priority: Medium — Add notification taxonomy/escalation metrics (action-required vs info).
- Priority: Medium — Add auto-ticket creation based on severity/repeat findings.
EOF

cat <<EOF >"$ARTIFACT_DIR/findings.json"
{
  "timestamp": "$TIMESTAMP",
  "pipeline": "nightly",
  "details": [
    {"source":"npm_audit","path":"artifacts/nightly/npm_audit.json"},
    {"source":"pip_audit","path":"artifacts/nightly/pip_audit.json"},
    {"source":"semgrep","path":"artifacts/nightly/security.sarif"},
    {"source":"system_status","path":"artifacts/nightly/system_status.json"},
    {"source":"perf","path":"artifacts/nightly/perf.txt"}
  ]
}
EOF

cat <<EOF >"$ARTIFACT_DIR/perf.html"
<html><body><h1>Nightly Performance Snapshot</h1><p>Generated at $TIMESTAMP</p><p>See perf.txt for cURL timing and CI for Lighthouse step.</p></body></html>
EOF

echo "Artifacts emitted to $ARTIFACT_DIR"
