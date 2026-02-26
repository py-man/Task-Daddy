#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

web_port="$(rg -o '\$\{WEB_PORT:-[0-9]+\}' docker-compose.yml | head -n1 | sed -E 's/.*:-([0-9]+)\}.*/\1/')"
if [[ -z "${web_port}" ]]; then
  echo "port_sync_check_failed: could not determine WEB_PORT default from docker-compose.yml" >&2
  exit 1
fi

must_files=(
  "README.md"
  "docs/OPEN_SOURCE_RELEASE_CHECKLIST.md"
  "docs/API_REFERENCE.md"
  "apps/web/app/app/help/page.tsx"
)

for f in "${must_files[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "port_sync_check_failed: missing required file $f" >&2
    exit 1
  fi
done

if rg -n '3005' "${must_files[@]}" >/dev/null; then
  echo "port_sync_check_failed: stale port 3005 reference found in required docs/help files" >&2
  rg -n '3005' "${must_files[@]}" >&2
  exit 1
fi

if ! rg -n "localhost:${web_port}|127\\.0\\.0\\.1:${web_port}" "${must_files[@]}" >/dev/null; then
  echo "port_sync_check_failed: required docs/help files do not reference expected web port ${web_port}" >&2
  exit 1
fi

echo "port_sync_check_ok web_port=${web_port}"
