# Deployment notes (MVP)

Task-Daddy ships with Docker Compose for local runs. For production you typically run:

- Postgres (managed or self-hosted)
- API behind HTTPS (reverse proxy)
- Web behind HTTPS (reverse proxy)

## Reverse proxy (example)

Run both services behind TLS and map a single hostname (recommended):

- `https://taskdaddy.example.com` → web
- `https://taskdaddy.example.com/api` → API

In this mode, set:

- `COOKIE_SECURE=true`
- `COOKIE_DOMAIN=taskdaddy.example.com`
- `CORS_ORIGINS=https://taskdaddy.example.com`
- `NEXT_PUBLIC_API_URL=/api`

## Kubernetes (high level)

Suggested layout:

- `Deployment` + `Service` for `api`
- `Deployment` + `Service` for `web`
- `StatefulSet` for Postgres (or managed Postgres)
- `Ingress` for TLS + routing

Key env for the API:

- `DATABASE_URL` to your Postgres instance
- `APP_SECRET` (random, long)
- `FERNET_KEY` (random, base64 URL-safe)

## Backup retention

The API runs a daily backup loop when `BACKUP_AUTO_ENABLED=true` and purges backups older than `BACKUP_RETENTION_DAYS`.
