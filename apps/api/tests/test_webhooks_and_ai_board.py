from __future__ import annotations

import secrets

import pytest
from httpx import AsyncClient

from conftest import login


@pytest.mark.anyio
async def test_board_ai_returns_actionable_suggestions_but_does_not_mutate(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  # Create board + task (unassigned)
  b = (await client.post("/boards", json={"name": f"AI Board {secrets.token_hex(4)}"})).json()
  board_id = b["id"]
  lanes = (await client.get(f"/boards/{board_id}/lanes")).json()
  lane_id = lanes[0]["id"]

  t = (await client.post(f"/boards/{board_id}/tasks", json={"laneId": lane_id, "title": "Unassigned task"})).json()
  task_id = t["id"]

  # AI triage should propose assigning to board owner (admin user)
  res = await client.post(f"/ai/board/{board_id}/triage-unassigned", json={})
  assert res.status_code == 200
  data = res.json()
  assert "text" in data
  assert "suggestions" in data
  assert any(s["taskId"] == task_id for s in data["suggestions"])

  # Ensure DB not mutated by AI endpoint
  t2 = (await client.get(f"/tasks/{task_id}")).json()
  assert t2["ownerId"] is None


@pytest.mark.anyio
async def test_board_ai_breakdown_returns_creates_but_does_not_mutate(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b = (await client.post("/boards", json={"name": f"AI Breakdown {secrets.token_hex(4)}"})).json()
  board_id = b["id"]
  lanes = (await client.get(f"/boards/{board_id}/lanes")).json()
  lane_id = lanes[0]["id"]

  long_desc = "x" * 800
  t = (await client.post(f"/boards/{board_id}/tasks", json={"laneId": lane_id, "title": "Big task", "description": long_desc})).json()
  task_id = t["id"]

  before = (await client.get(f"/boards/{board_id}/tasks")).json()
  res = await client.post(f"/ai/board/{board_id}/breakdown", json={})
  assert res.status_code == 200
  data = res.json()
  assert "text" in data
  assert "creates" in data
  assert any(g["parentTaskId"] == task_id for g in data["creates"])
  first_group = next(g for g in data["creates"] if g["parentTaskId"] == task_id)
  assert len(first_group["tasks"]) >= 1
  assert all("laneId" in x and "title" in x for x in first_group["tasks"])

  after = (await client.get(f"/boards/{board_id}/tasks")).json()
  assert len(after) == len(before)


@pytest.mark.anyio
async def test_webhook_inbound_create_task_is_idempotent_and_comment_dedupes(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b = (await client.post("/boards", json={"name": f"Webhook Board {secrets.token_hex(4)}"})).json()
  board_id = b["id"]
  lanes = (await client.get(f"/boards/{board_id}/lanes")).json()
  lane_name = lanes[0]["name"]

  token = "tok_" + secrets.token_urlsafe(16)
  res = await client.post("/webhooks/secrets", json={"source": "shortcuts", "enabled": True, "bearerToken": token})
  assert res.status_code == 200

  idem = "idem_" + secrets.token_hex(8)
  payload = {"action": "create_task", "title": "Shortcut created", "boardName": b["name"], "laneName": lane_name, "idempotencyKey": idem}
  r1 = await client.post("/webhooks/inbound/shortcuts", json=payload, headers={"Authorization": f"Bearer {token}"})
  assert r1.status_code == 200
  out1 = r1.json()
  assert out1["ok"] is True
  task_id = out1["result"]["taskId"]

  # Re-send with same idempotency key should not create a second task
  r2 = await client.post("/webhooks/inbound/shortcuts", json=payload, headers={"Authorization": f"Bearer {token}"})
  assert r2.status_code == 200
  out2 = r2.json()
  assert out2["idempotentReplay"] is True
  assert out2["result"]["taskId"] == task_id

  # Comment (dedupe by commentId)
  cpay = {"action": "comment_task", "taskId": task_id, "body": "Hello from Siri", "commentId": "c1", "author": "Siri"}
  c1 = await client.post("/webhooks/inbound/shortcuts", json=cpay, headers={"Authorization": f"Bearer {token}"})
  assert c1.status_code == 200
  c2 = await client.post("/webhooks/inbound/shortcuts", json=cpay, headers={"Authorization": f"Bearer {token}"})
  assert c2.status_code == 200

  comments = (await client.get(f"/tasks/{task_id}/comments")).json()
  assert sum(1 for c in comments if c["body"] == "Hello from Siri") == 1


@pytest.mark.anyio
async def test_webhook_create_task_can_create_multiple_without_order_index_error(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b = (await client.post("/boards", json={"name": f"Webhook Multi {secrets.token_hex(4)}"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_name = lanes[0]["name"]

  token = "tok_" + secrets.token_urlsafe(16)
  res = await client.post("/webhooks/secrets", json={"source": "shortcuts", "enabled": True, "bearerToken": token})
  assert res.status_code == 200

  for i in range(3):
    payload = {
      "action": "create_task",
      "title": f"Shortcut {i}",
      "boardName": b["name"],
      "laneName": lane_name,
      "idempotencyKey": f"k{i}",
    }
    r = await client.post("/webhooks/inbound/shortcuts", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text

  tasks = (await client.get(f"/boards/{b['id']}/tasks")).json()
  assert len(tasks) == 3
