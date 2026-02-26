from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import login


@pytest.mark.anyio
async def test_create_multiple_tasks_in_same_lane_assigns_order_index(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Order Index Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  created = []
  for i in range(3):
    res = await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": f"T{i}", "priority": "P2", "type": "Feature"},
    )
    assert res.status_code == 200, res.text
    created.append(res.json())

  assert [t["orderIndex"] for t in created] == [0, 1, 2]

