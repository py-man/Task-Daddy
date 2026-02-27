from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db, require_admin_mfa_guard
from app.models import AuditEvent, GitHubConnection, JiraConnection, NotificationDestination, OpenProjectConnection, User, WebhookSecret
from app.schemas import IntegrationStatusItemOut, IntegrationsStatusOut
from app.security import IntegrationSecretDecryptError, decrypt_integration_secret

router = APIRouter(prefix="/integrations", tags=["integrations"])


async def _latest_audit_event(
  db: AsyncSession,
  *,
  event_types: tuple[str, ...],
  provider: str | None = None,
) -> AuditEvent | None:
  if not event_types:
    return None
  res = await db.execute(
    select(AuditEvent)
    .where(AuditEvent.event_type.in_(event_types))
    .order_by(AuditEvent.created_at.desc())
    .limit(50)
  )
  rows = res.scalars().all()
  if not provider:
    return rows[0] if rows else None
  for row in rows:
    payload = row.payload or {}
    if str(payload.get("provider") or "") == provider:
      return row
  return None


def _last_error_message(event: AuditEvent | None) -> str | None:
  if not event:
    return None
  payload = event.payload or {}
  return str(payload.get("error") or "").strip() or None


@router.get("/status", response_model=IntegrationsStatusOut)
async def integrations_status(
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> IntegrationsStatusOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

  out: list[IntegrationStatusItemOut] = []

  # Jira
  jres = await db.execute(select(JiraConnection).order_by(JiraConnection.updated_at.desc()))
  jira_connections = jres.scalars().all()
  jira_configured = len(jira_connections) > 0
  jira_enabled = False
  jira_updated_at = jira_connections[0].updated_at if jira_connections else None
  jira_reconnect_count = 0
  for c in jira_connections:
    try:
      decrypt_integration_secret(c.token_encrypted)
      jira_enabled = True
    except IntegrationSecretDecryptError:
      jira_reconnect_count += 1
  jira_ok = await _latest_audit_event(db, event_types=("jira.connection.test.ok",))
  jira_err = await _latest_audit_event(db, event_types=("jira.connection.test.error",))
  if not jira_configured:
    jira_state = "not_configured"
    jira_msg = "No Jira connection configured"
  elif jira_reconnect_count > 0 and not jira_enabled:
    jira_state = "error"
    jira_msg = "Token reconnect required"
  elif jira_ok and (not jira_err or jira_ok.created_at >= jira_err.created_at):
    jira_state = "ok"
    jira_msg = "Connection test passed"
  elif jira_err:
    jira_state = "error"
    jira_msg = _last_error_message(jira_err) or "Connection test failed"
  else:
    jira_state = "unknown"
    jira_msg = "Configured but not tested yet"
  out.append(
    IntegrationStatusItemOut(
      key="jira",
      label="Jira",
      configured=jira_configured,
      enabled=jira_enabled,
      state=jira_state,
      message=jira_msg,
      lastCheckedAt=(jira_ok.created_at if jira_state == "ok" and jira_ok else (jira_err.created_at if jira_err else None)),
      updatedAt=jira_updated_at,
    )
  )

  # OpenProject
  ores = await db.execute(select(OpenProjectConnection).order_by(OpenProjectConnection.updated_at.desc()))
  op_connections = ores.scalars().all()
  op_configured = len(op_connections) > 0
  op_enabled = any(bool(c.enabled) for c in op_connections)
  op_updated_at = op_connections[0].updated_at if op_connections else None
  op_ok = await _latest_audit_event(db, event_types=("openproject.connection.test.ok",))
  op_err = await _latest_audit_event(db, event_types=("openproject.connection.test.error",))
  if not op_configured:
    op_state = "not_configured"
    op_msg = "No OpenProject connection configured"
  elif not op_enabled:
    op_state = "error"
    op_msg = "All OpenProject connections are disabled"
  elif op_ok and (not op_err or op_ok.created_at >= op_err.created_at):
    op_state = "ok"
    op_msg = "Connection test passed"
  elif op_err:
    op_state = "error"
    op_msg = _last_error_message(op_err) or "Connection test failed"
  else:
    op_state = "unknown"
    op_msg = "Configured but not tested yet"
  out.append(
    IntegrationStatusItemOut(
      key="openproject",
      label="OpenProject",
      configured=op_configured,
      enabled=op_enabled,
      state=op_state,
      message=op_msg,
      lastCheckedAt=(op_ok.created_at if op_state == "ok" and op_ok else (op_err.created_at if op_err else None)),
      updatedAt=op_updated_at,
    )
  )

  # GitHub
  gres = await db.execute(select(GitHubConnection).order_by(GitHubConnection.updated_at.desc()))
  gh_connections = gres.scalars().all()
  gh_configured = len(gh_connections) > 0
  gh_enabled = any(bool(c.enabled) for c in gh_connections)
  gh_updated_at = gh_connections[0].updated_at if gh_connections else None
  gh_ok = await _latest_audit_event(db, event_types=("github.connection.test.ok",))
  gh_err = await _latest_audit_event(db, event_types=("github.connection.test.error",))
  if not gh_configured:
    gh_state = "not_configured"
    gh_msg = "No GitHub connection configured"
  elif not gh_enabled:
    gh_state = "error"
    gh_msg = "All GitHub connections are disabled"
  elif gh_ok and (not gh_err or gh_ok.created_at >= gh_err.created_at):
    gh_state = "ok"
    gh_msg = "Connection test passed"
  elif gh_err:
    gh_state = "error"
    gh_msg = _last_error_message(gh_err) or "Connection test failed"
  else:
    gh_state = "unknown"
    gh_msg = "Configured but not tested yet"
  out.append(
    IntegrationStatusItemOut(
      key="github",
      label="GitHub",
      configured=gh_configured,
      enabled=gh_enabled,
      state=gh_state,
      message=gh_msg,
      lastCheckedAt=(gh_ok.created_at if gh_state == "ok" and gh_ok else (gh_err.created_at if gh_err else None)),
      updatedAt=gh_updated_at,
    )
  )

  # SMTP
  dres = await db.execute(select(NotificationDestination).order_by(NotificationDestination.updated_at.desc()))
  destinations = dres.scalars().all()
  smtp_dest = [d for d in destinations if d.provider == "smtp"]
  smtp_configured = len(smtp_dest) > 0
  smtp_enabled = any(bool(d.enabled) for d in smtp_dest)
  smtp_updated_at = smtp_dest[0].updated_at if smtp_dest else None
  smtp_ok = await _latest_audit_event(db, event_types=("notifications.test.sent",), provider="smtp")
  smtp_err = await _latest_audit_event(db, event_types=("notifications.test.error",), provider="smtp")
  if not smtp_configured:
    smtp_state = "not_configured"
    smtp_msg = "No SMTP destination configured"
  elif not smtp_enabled:
    smtp_state = "error"
    smtp_msg = "SMTP destination is disabled"
  elif smtp_ok and (not smtp_err or smtp_ok.created_at >= smtp_err.created_at):
    smtp_state = "ok"
    smtp_msg = "Test notification delivered"
  elif smtp_err:
    smtp_state = "error"
    smtp_msg = _last_error_message(smtp_err) or "SMTP test failed"
  else:
    smtp_state = "unknown"
    smtp_msg = "Configured but not tested yet"
  out.append(
    IntegrationStatusItemOut(
      key="smtp",
      label="SMTP Email",
      configured=smtp_configured,
      enabled=smtp_enabled,
      state=smtp_state,
      message=smtp_msg,
      lastCheckedAt=(smtp_ok.created_at if smtp_state == "ok" and smtp_ok else (smtp_err.created_at if smtp_err else None)),
      updatedAt=smtp_updated_at,
    )
  )

  # Pushover
  push_dest = [d for d in destinations if d.provider == "pushover"]
  push_configured = len(push_dest) > 0
  push_enabled = any(bool(d.enabled) for d in push_dest)
  push_updated_at = push_dest[0].updated_at if push_dest else None
  push_ok = await _latest_audit_event(db, event_types=("notifications.test.sent",), provider="pushover")
  push_err = await _latest_audit_event(db, event_types=("notifications.test.error",), provider="pushover")
  if not push_configured:
    push_state = "not_configured"
    push_msg = "No Pushover destination configured"
  elif not push_enabled:
    push_state = "error"
    push_msg = "Pushover destination is disabled"
  elif push_ok and (not push_err or push_ok.created_at >= push_err.created_at):
    push_state = "ok"
    push_msg = "Test notification delivered"
  elif push_err:
    push_state = "error"
    push_msg = _last_error_message(push_err) or "Pushover test failed"
  else:
    push_state = "unknown"
    push_msg = "Configured but not tested yet"
  out.append(
    IntegrationStatusItemOut(
      key="pushover",
      label="Pushover",
      configured=push_configured,
      enabled=push_enabled,
      state=push_state,
      message=push_msg,
      lastCheckedAt=(push_ok.created_at if push_state == "ok" and push_ok else (push_err.created_at if push_err else None)),
      updatedAt=push_updated_at,
    )
  )

  # Slack
  slack_dest = [d for d in destinations if d.provider == "slack"]
  slack_configured = len(slack_dest) > 0
  slack_enabled = any(bool(d.enabled) for d in slack_dest)
  slack_updated_at = slack_dest[0].updated_at if slack_dest else None
  slack_ok = await _latest_audit_event(db, event_types=("notifications.test.sent",), provider="slack")
  slack_err = await _latest_audit_event(db, event_types=("notifications.test.error",), provider="slack")
  if not slack_configured:
    slack_state = "not_configured"
    slack_msg = "No Slack destination configured"
  elif not slack_enabled:
    slack_state = "error"
    slack_msg = "Slack destination is disabled"
  elif slack_ok and (not slack_err or slack_ok.created_at >= slack_err.created_at):
    slack_state = "ok"
    slack_msg = "Test notification delivered"
  elif slack_err:
    slack_state = "error"
    slack_msg = _last_error_message(slack_err) or "Slack test failed"
  else:
    slack_state = "unknown"
    slack_msg = "Configured but not tested yet"
  out.append(
    IntegrationStatusItemOut(
      key="slack",
      label="Slack",
      configured=slack_configured,
      enabled=slack_enabled,
      state=slack_state,
      message=slack_msg,
      lastCheckedAt=(slack_ok.created_at if slack_state == "ok" and slack_ok else (slack_err.created_at if slack_err else None)),
      updatedAt=slack_updated_at,
    )
  )

  # Microsoft Teams
  teams_dest = [d for d in destinations if d.provider == "teams"]
  teams_configured = len(teams_dest) > 0
  teams_enabled = any(bool(d.enabled) for d in teams_dest)
  teams_updated_at = teams_dest[0].updated_at if teams_dest else None
  teams_ok = await _latest_audit_event(db, event_types=("notifications.test.sent",), provider="teams")
  teams_err = await _latest_audit_event(db, event_types=("notifications.test.error",), provider="teams")
  if not teams_configured:
    teams_state = "not_configured"
    teams_msg = "No Teams destination configured"
  elif not teams_enabled:
    teams_state = "error"
    teams_msg = "Teams destination is disabled"
  elif teams_ok and (not teams_err or teams_ok.created_at >= teams_err.created_at):
    teams_state = "ok"
    teams_msg = "Test notification delivered"
  elif teams_err:
    teams_state = "error"
    teams_msg = _last_error_message(teams_err) or "Teams test failed"
  else:
    teams_state = "unknown"
    teams_msg = "Configured but not tested yet"
  out.append(
    IntegrationStatusItemOut(
      key="teams",
      label="Microsoft Teams",
      configured=teams_configured,
      enabled=teams_enabled,
      state=teams_state,
      message=teams_msg,
      lastCheckedAt=(teams_ok.created_at if teams_state == "ok" and teams_ok else (teams_err.created_at if teams_err else None)),
      updatedAt=teams_updated_at,
    )
  )

  # Webhooks
  wres = await db.execute(select(WebhookSecret).order_by(WebhookSecret.updated_at.desc()))
  webhook_secrets = wres.scalars().all()
  webhook_configured = len(webhook_secrets) > 0
  webhook_enabled = any(bool(s.enabled) for s in webhook_secrets)
  webhook_updated_at = webhook_secrets[0].updated_at if webhook_secrets else None
  if not webhook_configured:
    webhook_state = "not_configured"
    webhook_msg = "No webhook sources configured"
  elif not webhook_enabled:
    webhook_state = "error"
    webhook_msg = "All webhook sources are disabled"
  else:
    webhook_state = "ok"
    webhook_msg = "Webhook source configured"
  out.append(
    IntegrationStatusItemOut(
      key="webhooks",
      label="Webhooks",
      configured=webhook_configured,
      enabled=webhook_enabled,
      state=webhook_state,
      message=webhook_msg,
      lastCheckedAt=None,
      updatedAt=webhook_updated_at,
    )
  )

  return IntegrationsStatusOut(generatedAt=datetime.now(timezone.utc), items=out)
