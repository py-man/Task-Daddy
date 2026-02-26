#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/backups/host-db"
mkdir -p "${OUT_DIR}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="${OUT_DIR}/neonlanes_config_integrations_${ts}.json"

db_container="$(
  docker ps --format '{{.Names}} {{.Image}}' \
    | awk '/postgres:16/ && /neonlanes/ && /db/ { print $1; exit }'
)"

if [[ -z "${db_container}" ]]; then
  echo "No running Task-Daddy postgres container found; config export skipped." >&2
  exit 1
fi

docker exec "${db_container}" psql -U neonlanes -d neonlanes -t -A -c "
select json_build_object(
  'generatedAt', now(),
  'boards', (
    select coalesce(json_agg(json_build_object(
      'id', b.id,
      'name', b.name,
      'ownerId', b.owner_id,
      'createdAt', b.created_at
    ) order by b.created_at), '[]'::json)
    from boards b
  ),
  'jiraConnections', (
    select coalesce(json_agg(json_build_object(
      'id', c.id,
      'name', c.name,
      'baseUrl', c.base_url,
      'email', c.email,
      'defaultAssigneeAccountId', c.default_assignee_account_id,
      'createdAt', c.created_at,
      'updatedAt', c.updated_at
    ) order by c.created_at), '[]'::json)
    from jira_connections c
  ),
  'openprojectConnections', (
    select coalesce(json_agg(json_build_object(
      'id', c.id,
      'name', c.name,
      'baseUrl', c.base_url,
      'projectIdentifier', c.project_identifier,
      'enabled', c.enabled,
      'tokenHint', c.token_hint,
      'createdAt', c.created_at,
      'updatedAt', c.updated_at
    ) order by c.created_at), '[]'::json)
    from openproject_connections c
  ),
  'webhookSecrets', (
    select coalesce(json_agg(json_build_object(
      'id', w.id,
      'source', w.source,
      'enabled', w.enabled,
      'tokenHint', w.token_hint,
      'createdAt', w.created_at,
      'updatedAt', w.updated_at
    ) order by w.created_at), '[]'::json)
    from webhook_secrets w
  ),
  'notificationDestinations', (
    select coalesce(json_agg(json_build_object(
      'id', n.id,
      'provider', n.provider,
      'enabled', n.enabled,
      'name', n.name,
      'tokenHint', n.token_hint,
      'updatedAt', n.updated_at
    ) order by n.updated_at desc), '[]'::json)
    from notification_destinations n
  )
)::text;
" > "${out}"

sha256sum "${out}" > "${out}.sha256"
echo "Config/integration export created:"
echo "  ${out}"
echo "  ${out}.sha256"
