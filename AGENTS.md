# Task-Daddy AGENTS.md

## Repo Role
- `task-daddy` is the open-source stripped distribution.
- Do not place private environment details, production identifiers, or internal-only tooling code here.

## Commit + Restart Safety
- Create a code backup point (git tag) before every commit.
- Before any restart/deploy touching runtime services, create and verify backup artifacts.
- Never run destructive Docker volume removal on production-like environments.

## Health Verification
- After restart/deploy, run and report:
  - API health: `http://127.0.0.1:8000/health`
  - Web health: `http://127.0.0.1:3010/`
- If checks fail, stop rollout and fix before continuing.

## Release Hygiene
- Keep docs and API reference aligned with shipped behavior.
- Keep secrets and personal data out of commits.
