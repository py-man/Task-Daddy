from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.db import SessionLocal
from app.models import JiraConnection, OpenProjectConnection, WebhookSecret
from tests.conftest import login


@pytest.mark.anyio
async def test_jira_task_create_returns_400_when_connection_token_cannot_be_decrypted(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Jira Key Mismatch Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  t = (await client.post(f"/boards/{b['id']}/tasks", json={"laneId": lane_id, "title": "Broken Jira Token"})).json()

  async with SessionLocal() as db:
    conn = JiraConnection(
      name="Broken Jira",
      base_url="https://jira.example.com",
      email="jira@example.com",
      token_encrypted="not-a-valid-fernet-token",
    )
    db.add(conn)
    await db.flush()
    conn_id = conn.id
    await db.commit()

  res = await client.post(
    f"/tasks/{t['id']}/jira/create",
    json={"connectionId": conn_id, "projectKey": "OPS", "issueType": "Task", "enableSync": True, "assigneeMode": "unassigned"},
  )
  assert res.status_code == 400, res.text
  assert "cannot be decrypted" in str(res.json().get("detail", "")).lower()


@pytest.mark.anyio
async def test_openproject_task_create_returns_400_when_connection_token_cannot_be_decrypted(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "OpenProject Key Mismatch Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  t = (await client.post(f"/boards/{b['id']}/tasks", json={"laneId": lane_id, "title": "Broken OP Token"})).json()

  async with SessionLocal() as db:
    conn = OpenProjectConnection(
      name="Broken OP",
      base_url="https://openproject.example.com",
      api_token_encrypted="not-a-valid-fernet-token",
      project_identifier="ops",
      enabled=True,
      token_hint="****",
    )
    db.add(conn)
    await db.flush()
    conn_id = conn.id
    await db.commit()

  res = await client.post(
    f"/tasks/{t['id']}/openproject/create",
    json={"connectionId": conn_id, "projectIdentifier": "ops", "enableSync": True},
  )
  assert res.status_code == 400, res.text
  assert "cannot be decrypted" in str(res.json().get("detail", "")).lower()


@pytest.mark.anyio
async def test_webhook_inbound_returns_400_when_secret_cannot_be_decrypted(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  async with SessionLocal() as db:
    secret = WebhookSecret(
      source="shortcuts",
      enabled=True,
      bearer_token_encrypted="not-a-valid-fernet-token",
      token_hint="****",
    )
    db.add(secret)
    await db.commit()

  res = await client.post(
    "/webhooks/inbound/shortcuts",
    json={"action": "create_task", "title": "t", "boardName": "missing"},
    headers={"Authorization": "Bearer some-token"},
  )
  assert res.status_code == 400, res.text
  assert "cannot be decrypted" in str(res.json().get("detail", "")).lower()
