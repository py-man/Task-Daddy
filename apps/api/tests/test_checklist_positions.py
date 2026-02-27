from __future__ import annotations

import secrets

import pytest
from httpx import AsyncClient

from conftest import login


@pytest.mark.anyio
async def test_checklist_create_uses_max_position_without_500(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": f"Checklist Pos {secrets.token_hex(4)}"})).json()
  board_id = b["id"]
  lanes = (await client.get(f"/boards/{board_id}/lanes")).json()
  lane_id = lanes[0]["id"]
  t = (await client.post(f"/boards/{board_id}/tasks", json={"laneId": lane_id, "title": "Task"})).json()
  task_id = t["id"]

  c1 = await client.post(f"/tasks/{task_id}/checklist", json={"text": "one"})
  assert c1.status_code == 200, c1.text
  c2 = await client.post(f"/tasks/{task_id}/checklist", json={"text": "two"})
  assert c2.status_code == 200, c2.text
  c3 = await client.post(f"/tasks/{task_id}/checklist", json={"text": "three"})
  assert c3.status_code == 200, c3.text

  items = (await client.get(f"/tasks/{task_id}/checklist")).json()
  assert [i["position"] for i in items] == [0, 1, 2]

