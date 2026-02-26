#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/py-man/Task-Daddy}"
OUT_DIR="${2:-docs/launch}"
mkdir -p "$OUT_DIR"

cat >"${OUT_DIR}/x_post.txt" <<EOF
Task-Daddy is live: Small tasks. Big momentum.

Open-source task manager with:
- Kanban boards
- Jira + OpenProject integrations
- Voice quick-capture flow
- Reminders + ICS + webhooks
- MFA + backups + self-hosted Docker setup

${REPO_URL}
EOF

cat >"${OUT_DIR}/reddit_post.md" <<EOF
# Task-Daddy: open-source task manager for momentum, not overwhelm

I built and open-sourced **Task-Daddy** to keep task management fast and useful without bloated workflows.

## Highlights
- Board + lane workflow
- Jira and OpenProject integrations
- Voice capture for quick tasks
- Notifications/reminders + ICS export
- Admin MFA, backups, API tokens, webhooks
- Self-hosted Docker setup

Repo: ${REPO_URL}
EOF

cat >"${OUT_DIR}/hn_post.txt" <<EOF
Show HN: Task-Daddy – open-source task manager (Jira/OpenProject, voice capture, MFA, self-hosted)
${REPO_URL}
EOF

cat >"${OUT_DIR}/linkedin_post.txt" <<EOF
I just released Task-Daddy: an open-source task manager built for clarity and momentum.

It combines practical team workflows (boards, priorities, integrations) with personal productivity speed (quick capture, reminders, exports).

If you want a self-hosted, extensible stack with FastAPI + Next.js + Docker, check it out:
${REPO_URL}
EOF

cat >"${OUT_DIR}/tags.txt" <<EOF
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
EOF

echo "Launch pack generated in ${OUT_DIR}:"
ls -1 "${OUT_DIR}"
