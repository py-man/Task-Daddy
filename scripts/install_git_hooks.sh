#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p .git/hooks
cat > .git/hooks/pre-push <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
exec ./scripts/pre_push_guard.sh
HOOK
chmod +x .git/hooks/pre-push

echo "Installed pre-push hook -> .git/hooks/pre-push"
