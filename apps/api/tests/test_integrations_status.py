from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditEvent, JiraConnection
from app.security import encrypt_secret, totp_code
from tests.conftest import enable_admin_mfa, login


def _by_key(items: list[dict]) -> dict[str, dict]:
  return {str(i["key"]): i for i in items}


@pytest.mark.anyio
async def test_integrations_status_reports_configuration_and_health(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  empty = await client.get("/integrations/status")
  assert empty.status_code == 200, empty.text
  base = _by_key(empty.json()["items"])
  assert base["jira"]["state"] == "not_configured"
  assert base["openproject"]["state"] == "not_configured"
  assert base["github"]["state"] == "not_configured"
  assert base["smtp"]["state"] in {"not_configured", "unknown"}
  assert base["pushover"]["state"] in {"not_configured", "unknown"}
  assert base["webhooks"]["state"] == "not_configured"

  # Configure integrations
  j = await client.post(
    "/jira/connect",
    json={"name": "Main", "baseUrl": "https://example.atlassian.net", "email": "admin@example.com", "token": "x-token"},
  )
  assert j.status_code == 200, j.text
  jira_id = str(j.json()["id"])

  op = await client.post(
    "/openproject/connections",
    json={"name": "OP", "baseUrl": "https://openproject.example.com", "apiToken": "op-token-123456", "enabled": True},
  )
  assert op.status_code == 200, op.text
  gh = await client.post(
    "/github/connections",
    json={"name": "GH", "baseUrl": "https://api.github.com", "apiToken": "ghp_test_token_123456", "enabled": True},
  )
  assert gh.status_code == 200, gh.text

  smtp = await client.post(
    "/notifications/destinations",
    json={"provider": "smtp", "name": "SMTP", "enabled": True, "smtpHost": "smtp.example.com", "smtpFrom": "a@b.com", "smtpTo": "c@d.com"},
  )
  assert smtp.status_code == 200, smtp.text

  push = await client.post(
    "/notifications/destinations",
    json={"provider": "pushover", "name": "Pushover", "enabled": True, "pushoverAppToken": "app_token_1234567890", "pushoverUserKey": "user_key_1234567890"},
  )
  assert push.status_code == 200, push.text

  wh = await client.post("/webhooks/secrets", json={"source": "demo", "enabled": True, "bearerToken": "super-secret-token-123"})
  assert wh.status_code == 200, wh.text

  # Mark successful tests in audit for Jira/SMTP.
  async with SessionLocal() as db:
    jres = await db.execute(select(JiraConnection).where(JiraConnection.id == jira_id))
    conn = jres.scalar_one()
    db.add(
      AuditEvent(
        event_type="jira.connection.test.ok",
        entity_type="JiraConnection",
        entity_id=conn.id,
        actor_id=None,
        payload={},
      )
    )
    db.add(
      AuditEvent(
        event_type="notifications.test.sent",
        entity_type="NotificationDestination",
        entity_id=None,
        actor_id=None,
        payload={"provider": "smtp"},
      )
    )
    await db.commit()

  out = await client.get("/integrations/status")
  assert out.status_code == 200, out.text
  items = _by_key(out.json()["items"])
  assert items["jira"]["configured"] is True
  assert items["jira"]["state"] == "ok"
  assert items["openproject"]["configured"] is True
  assert items["openproject"]["state"] == "unknown"
  assert items["github"]["configured"] is True
  assert items["github"]["state"] == "unknown"
  assert items["smtp"]["configured"] is True
  assert items["smtp"]["state"] == "ok"
  assert items["pushover"]["configured"] is True
  assert items["pushover"]["state"] == "unknown"
  assert items["webhooks"]["configured"] is True
  assert items["webhooks"]["state"] == "ok"


@pytest.mark.anyio
async def test_integrations_status_marks_jira_reconnect_as_error(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  # Insert intentionally undecryptable token to simulate key mismatch/reconnect required.
  async with SessionLocal() as db:
    db.add(
      JiraConnection(
        name="Broken",
        base_url="https://example.atlassian.net",
        email="admin@example.com",
        token_encrypted=encrypt_secret("bad-token"),
      )
    )
    await db.commit()

  # Corrupt encrypted token after creation.
  async with SessionLocal() as db:
    res = await db.execute(select(JiraConnection).order_by(JiraConnection.created_at.desc()).limit(1))
    c = res.scalar_one()
    c.token_encrypted = "corrupted"
    await db.commit()

  out = await client.get("/integrations/status")
  assert out.status_code == 200, out.text
  jira = _by_key(out.json()["items"])["jira"]
  assert jira["configured"] is True
  assert jira["state"] == "error"
