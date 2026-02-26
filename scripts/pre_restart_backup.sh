#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/backups/host-db"
mkdir -p "${BACKUP_DIR}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"

# Prefer running Task-Daddy DB container if present.
db_container="$(
  docker ps --format '{{.Names}} {{.Image}}' \
    | awk '/postgres:16/ && /neonlanes/ && /db/ { print $1; exit }'
)"

if [[ -z "${db_container}" ]]; then
  echo "No running Task-Daddy postgres container found; backup skipped." >&2
  exit 1
fi

pg_user="$(docker inspect "${db_container}" --format '{{range .Config.Env}}{{println .}}{{end}}' | awk -F= '/^POSTGRES_USER=/{print $2; exit}')"
pg_pass="$(docker inspect "${db_container}" --format '{{range .Config.Env}}{{println .}}{{end}}' | awk -F= '/^POSTGRES_PASSWORD=/{print $2; exit}')"
pg_db="$(docker inspect "${db_container}" --format '{{range .Config.Env}}{{println .}}{{end}}' | awk -F= '/^POSTGRES_DB=/{print $2; exit}')"

if [[ -z "${pg_user}" || -z "${pg_pass}" || -z "${pg_db}" ]]; then
  echo "Unable to read postgres env from ${db_container}; aborting backup." >&2
  exit 1
fi

out="${BACKUP_DIR}/neonlanes_db_${ts}.dump"
meta="${BACKUP_DIR}/neonlanes_db_${ts}.meta.txt"

docker exec "${db_container}" sh -lc "PGPASSWORD='${pg_pass}' pg_dump -U '${pg_user}' -d '${pg_db}' -Fc" > "${out}"
sha256sum "${out}" > "${out}.sha256"

{
  echo "timestamp_utc=${ts}"
  echo "container=${db_container}"
  echo "db=${pg_db}"
  echo "user=${pg_user}"
  ls -lh "${out}"
} > "${meta}"

echo "Host backup created:"
echo "  ${out}"
echo "  ${out}.sha256"
echo "  ${meta}"

"${ROOT_DIR}/scripts/backup_config_integrations.sh"
