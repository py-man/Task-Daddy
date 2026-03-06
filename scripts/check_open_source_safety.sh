#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[safety] checking tracked env files..."
git ls-files | rg -n '(^|/)\.env($|\.)' | rg -v '\.env\.(example|sample|template)$' >/tmp/task_daddy_env_hits.txt || true
if [[ -s /tmp/task_daddy_env_hits.txt ]]; then
  echo "[safety] FAIL: tracked .env files found:"
  cat /tmp/task_daddy_env_hits.txt
  exit 1
fi
echo "[safety] ok: no tracked .env files"

echo "[safety] scanning tracked files for secret-like patterns..."
tmp_hits="$(mktemp)"
trap 'rm -f "$tmp_hits" /tmp/task_daddy_env_hits.txt' EXIT

git ls-files | while IFS= read -r f; do
  rg -n \
    -e 'AKIA[0-9A-Z]{16}' \
    -e 'ASIA[0-9A-Z]{16}' \
    -e '-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----' \
    -e 'xox[baprs]-[A-Za-z0-9-]{20,}' \
    -e 'ghp_[A-Za-z0-9]{20,}' \
    -e 'github_pat_[A-Za-z0-9_]{20,}' \
    -e 'sk-[A-Za-z0-9]{20,}' \
    -- "$f" || true
done >"$tmp_hits"

if [[ -s "$tmp_hits" ]]; then
  echo "[safety] FAIL: possible secrets detected:"
  cat "$tmp_hits"
  exit 1
fi

echo "[safety] ok: no obvious secret signatures in tracked files"
echo "[safety] PASS"
