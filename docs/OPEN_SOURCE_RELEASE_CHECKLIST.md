# Open Source Release Checklist

Use this before publishing an image/repo to public users.

## Secrets and credentials

- Remove all real Jira/SMTP/webhook credentials from `.env` and docs.
- Ensure `.env` is gitignored and never committed.
- Set strong values:
  - `APP_SECRET`
  - `FERNET_KEY`
- Set explicit seed passwords (`SEED_ADMIN_PASSWORD`, `SEED_MEMBER_PASSWORD`) or capture generated values from bootstrap output and rotate immediately.

## Auth and session hardening

- Set `COOKIE_SECURE=true` behind HTTPS.
- Set `COOKIE_DOMAIN` for your production domain.
- Restrict CORS to trusted origins.
- Verify admin MFA is enabled and required.
- Verify password reset and session revocation flows work.

## API and webhook safety

- Review webhook secrets/tokens and rotate before release.
- Confirm no debug endpoints expose sensitive internals.
- Validate rate limiting on auth and reset endpoints.
- Confirm API token flows require password confirmation and tokens are shown once only.

## Data and backups

- Remove private production data from seed/demo content.
- Verify backups run and retention policy is configured.
- Test restore in dry-run first, then full restore in non-prod.

## Build and verification

1. Checkout branch:
   - `git checkout opensource-neon`
2. Start clean:
   - `docker-compose down --remove-orphans`
   - `docker-compose up --build -d`
3. Verify health:
   - `curl -sf http://127.0.0.1:8000/health` -> `{"ok":true}`
   - `curl -sf http://127.0.0.1:8000/version` -> includes version string
   - `curl -sf http://127.0.0.1:3005/version` -> returns web version payload
4. Smoke (open-source web port):
   - `WEB_BASE=http://127.0.0.1:3005 ./scripts/smoke.sh`
   - expected tail: `smoke_ok web=http://127.0.0.1:3005 api=http://127.0.0.1:8000 ...`
5. Backend tests (minimum targeted set for shipped integrations):
   - `docker-compose run --rm api bash -lc "cd /app && pytest -q tests/test_task_reminders_and_ics.py tests/test_openproject_integrations.py tests/test_openproject_task_actions.py"`
6. Web checks:
   - `npm -w @neonlanes/web run -s typecheck`
7. Secret scan (tracked files):
   - `git grep -nE "(AKIA|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|xox[baprs]-|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z-_]{35})"`
   - expected: no matches

## Release hygiene

- Update `CHANGELOG.md`.
- Bump version/build metadata.
- Confirm README quickstart commands work from a clean clone.
- Run dependency and container image scans in CI.
- Publish `docs/OPEN_SOURCE_READINESS_YYYY-MM-DD.md` with explicit Go/No-Go.
