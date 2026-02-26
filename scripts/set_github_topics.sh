#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-py-man/Task-Daddy}"

TOPICS=(
  task-manager
  productivity
  open-source
  jira
  openproject
  voice
  kanban
  life-management
  todo
  project-management
  nextjs
  fastapi
  docker
  webhooks
  task-tracking
  mfa
  automation
  self-hosted
)

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install GitHub CLI first." >&2
  exit 1
fi

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "gh auth missing. Run: gh auth login" >&2
  exit 1
fi

args=()
for t in "${TOPICS[@]}"; do
  args+=(--add-topic "$t")
done

set +e
out="$(gh repo edit "$REPO" "${args[@]}" 2>&1)"
code=$?
set -e

if [[ $code -ne 0 ]]; then
  echo "$out" >&2
  echo
  echo "If you see 403 'Resource not accessible by personal access token':" >&2
  echo "1) Run: gh auth refresh -h github.com -s repo" >&2
  echo "2) Retry this script." >&2
  exit $code
fi

echo "Topics updated for $REPO"
gh repo view "$REPO" --json repositoryTopics -q '.repositoryTopics[].name'
