from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.anyio
async def test_task_types_and_priorities_defaults_and_validation(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Fields Board"})).json()
  board_id = b["id"]
  lanes = (await client.get(f"/boards/{board_id}/lanes")).json()
  lane_id = lanes[0]["id"]

  types = (await client.get(f"/boards/{board_id}/task_types")).json()
  assert any(t["key"] == "Feature" and t["enabled"] is True for t in types)

  prios = (await client.get(f"/boards/{board_id}/priorities")).json()
  assert any(p["key"] == "P2" and p["enabled"] is True for p in prios)

  # Disable a type and ensure it can't be used.
  r = await client.patch(f"/boards/{board_id}/task_types/Feature", json={"enabled": False})
  assert r.status_code == 200, r.text
  created = await client.post(
    f"/boards/{board_id}/tasks",
    json={"laneId": lane_id, "title": "T", "priority": "P2", "type": "Feature"},
  )
  assert created.status_code == 400
  assert "Invalid type" in created.text

  # Create a custom type, use it.
  ct = await client.post(f"/boards/{board_id}/task_types", json={"key": "Meeting", "name": "Meeting", "color": "#22c55e"})
  assert ct.status_code == 200, ct.text
  created2 = await client.post(
    f"/boards/{board_id}/tasks",
    json={"laneId": lane_id, "title": "T2", "priority": "P2", "type": "Meeting"},
  )
  assert created2.status_code == 200, created2.text

  # Disable a priority and ensure it can't be used.
  rp = await client.patch(f"/boards/{board_id}/priorities/P2", json={"enabled": False})
  assert rp.status_code == 200, rp.text
  created3 = await client.post(
    f"/boards/{board_id}/tasks",
    json={"laneId": lane_id, "title": "T3", "priority": "P2", "type": "Meeting"},
  )
  assert created3.status_code == 400
  assert "Invalid priority" in created3.text

