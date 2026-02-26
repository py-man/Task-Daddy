# VPS Security Hardening (2026-02-26)

Executive summary:
- Baseline hardening is now added for production compose deployment.
- You still must apply host-level controls (TLS reverse proxy + firewall + secret management) before public launch.
- HTTPS automation is now available with Let's Encrypt via Caddy (`docker-compose.https.yml`).

## Critical findings addressed in repo

1) Public `db`/`redis` exposure risk
- Risk: default compose maps `5432` and `6379` publicly.
- Mitigation added:
  - `docker-compose.prod.yml` removes published ports for `db` and `redis`.

2) Weak internet-facing container posture
- Risk: default containers run with broad privileges and writable root FS.
- Mitigation added:
  - `docker-compose.prod.yml` sets `no-new-privileges`, drops Linux caps, enables read-only root filesystem for `api` and `web`, and uses `/tmp` tmpfs.

3) Host header abuse
- Risk: API previously accepted any Host.
- Mitigation added:
  - `TrustedHostMiddleware` enabled.
  - Configurable `TRUSTED_HOSTS` setting and env examples.

4) Missing baseline security headers
- Risk: absent basic hardening headers.
- Mitigation added:
  - `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` set by API middleware.

## Required host/VPS controls before go-live

1) TLS termination (required)
- Put Nginx/Caddy/Traefik in front of `127.0.0.1:3000`.
- Enforce HTTPS and redirect HTTP to HTTPS.

2) Firewall
- Allow inbound only: `22`, `80`, `443`.
- Deny direct inbound access to container-only ports (`3000`, `8000`, `5432`, `6379`).

3) Secrets
- Fill all `REPLACE_*` values in `.env.production` and `apps/api/.env`.
- Use strong random values for:
  - `POSTGRES_PASSWORD`
  - `APP_SECRET`
  - `FERNET_KEY`
  - seed account passwords

4) DNS and app policy
- Set:
  - `COOKIE_SECURE=true`
  - `COOKIE_DOMAIN=<your-domain>`
  - `CORS_ORIGINS=https://<your-domain>`
  - `CORS_ORIGIN_REGEX` for your domain only
  - `TRUSTED_HOSTS=<your-domain>`

5) Patching/operations
- Keep Ubuntu packages and Docker engine updated.
- Enable log rotation and backup restore drills.
- Rotate credentials if any environment file is copied/shared.

## Deployment command

```bash
set -a; source .env.production; set +a
docker-compose -f docker-compose.prod.yml -f docker-compose.https.yml up -d --build
```

## Database changes required?

- None. No DB migration/config table update is required to enable HTTPS.
- Activation is environment and compose based.

## Go-live gate (must all be true)

- [ ] `docker ps` shows only web exposed on loopback (`127.0.0.1:3000`), not public interfaces.
- [ ] Public internet can reach app only through HTTPS reverse proxy.
- [ ] `COOKIE_SECURE=true` and trusted hosts/CORS restricted to your domain.
- [ ] Randomized secrets/passwords are set (no defaults/placeholders).
- [ ] Smoke test passes after production deploy.
