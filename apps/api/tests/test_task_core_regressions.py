from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import login


@pytest.mark.anyio
async def test_login_is_case_insensitive_for_email(client: AsyncClient) -> None:
  res = await client.post("/auth/login", json={"email": "ADMIN@TASKDADDY.LOCAL", "password": "admin1234"})
  assert res.status_code == 200, res.text


@pytest.mark.anyio
async def test_create_task_in_backlog_lane_and_edit_title(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Core Flow Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  assert lanes
  backlog = next((l for l in lanes if l.get("type") == "backlog"), lanes[0])

  created = await client.post(
    f"/boards/{b['id']}/tasks",
    json={"laneId": backlog["id"], "title": "Morning report", "priority": "P2", "type": "Feature"},
  )
  assert created.status_code == 200, created.text
  task = created.json()
  assert task["boardId"] == b["id"]
  assert task["laneId"] == backlog["id"]
  assert task["title"] == "Morning report"

  updated = await client.patch(
    f"/tasks/{task['id']}",
    json={"version": task["version"], "title": "Morning report v2"},
  )
  assert updated.status_code == 200, updated.text
  assert updated.json()["title"] == "Morning report v2"
