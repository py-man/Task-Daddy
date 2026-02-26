#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "pre-push security: scanning tracked content"

# 1) Block committed runtime secrets/config dumps/backups.
blocked_paths=(
  ".env"
  "apps/api/.env"
  "apps/web/.env"
  "data/"
  "backups/"
  "*.dump"
  "*.sqlite"
  "*.sqlite3"
  "*.pem"
  "*.key"
)

for p in "${blocked_paths[@]}"; do
  if git ls-files -- "$p" | grep -q .; then
    echo "BLOCKED: tracked sensitive/runtime file pattern matched: $p" >&2
    git ls-files -- "$p" >&2 || true
    exit 1
  fi
done

# 2) Block obvious private keys/tokens in tracked files.
secret_pattern='BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{20,}'
if git grep -nE "$secret_pattern" -- . ':(exclude)*.md' >/tmp/taskdaddy_secret_hits.txt; then
  echo "BLOCKED: possible hardcoded secret material found:" >&2
  cat /tmp/taskdaddy_secret_hits.txt >&2
  exit 1
fi

# 3) Block known private identifiers from this project context.
identifier_pattern='kevin\.brannigan|technosludge|heli-pay|gpecom|globalpay|globalpayments'
if git grep -nEi "$identifier_pattern" -- . ':(exclude)docs/*' ':(exclude)README.md' >/tmp/taskdaddy_identifier_hits.txt; then
  echo "BLOCKED: private/project-specific identifiers found in tracked source:" >&2
  cat /tmp/taskdaddy_identifier_hits.txt >&2
  exit 1
fi

# 4) Optional deep history scan for outgoing commits with gitleaks.
if command -v gitleaks >/dev/null 2>&1; then
  if git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' >/dev/null 2>&1; then
    upstream_ref="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}')"
    echo "pre-push security: gitleaks on outgoing commits ${upstream_ref}..HEAD"
    gitleaks git --log-opts "${upstream_ref}..HEAD" --redact --verbose
  else
    echo "pre-push security: no upstream configured; skipping outgoing-commit gitleaks scan"
  fi
else
  echo "pre-push security: gitleaks not installed, regex gate only"
fi

echo "pre-push security: passed"
