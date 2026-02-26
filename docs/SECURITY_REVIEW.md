# Security review (open-source build)

This is a practical security checklist for Task-Daddy. It is not a formal penetration test.

## Secrets

- Secrets must only live in runtime env (`apps/api/.env`) or encrypted-at-rest DB fields.
- Never commit `.env`, Jira tokens, GitHub PATs, SMTP passwords, Pushover tokens.
- Encryption at rest:
  - Jira tokens, webhook bearer tokens, notification destination configs are stored encrypted with `FERNET_KEY`.

## Auth

Supported auth modes:

- Session cookie (`nl_session`) for the web UI.
- Personal Access Tokens (PAT) for CLI/tools: `Authorization: Bearer nlpat_...`.

Protections:

- Password hashing: `bcrypt` via Passlib.
- Rate limiting on login + password reset endpoints.
- Admin-only actions require an **MFA-verified session** (TOTP + recovery codes).

Notes:

- PAT creation/revocation requires a cookie session + password confirmation, and for admins also requires MFA verification.
- PATs intentionally do not bypass admin MFA guard (defense in depth).

## Cookie + CORS recommendations (production)

For public internet deployments, run behind HTTPS and set:

- `COOKIE_SECURE=true`
- `COOKIE_DOMAIN=your.domain`
- `CORS_ORIGINS=https://your.domain`
- `CORS_ORIGIN_REGEX=` (tighten or disable regex)

## Common hardening tasks (recommended)

- Put API behind a reverse proxy (TLS termination).
- Add security headers at the edge (or in app):
  - `Strict-Transport-Security`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
- Restrict upload types if needed; the API enforces a max upload size (`MAX_ATTACHMENT_BYTES`).

## Data safety

- Optimistic concurrency for tasks: `version` increments on update/move and conflicts return `409`.
- Board deletion is guarded: transfer-or-delete choice required.
- Audit events exist for auth and admin changes.

## Known limitations (MVP)

- CSRF: Session auth uses `SameSite=Lax`; for strict enterprise setups you may want CSRF tokens for state-changing endpoints.
- MFA “device trust” is not implemented.
- No MFA “enforce per board”; only role-based admin guard exists.

