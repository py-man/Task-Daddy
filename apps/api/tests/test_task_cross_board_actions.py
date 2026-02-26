from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import login


async def _first_lane_id(client: AsyncClient, board_id: str) -> str:
  lres = await client.get(f"/boards/{board_id}/lanes")
  assert lres.status_code == 200, lres.text
  lanes = lres.json()
  assert lanes
  return lanes[0]["id"]


@pytest.mark.anyio
async def test_duplicate_task_to_another_board(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b1 = (await client.post("/boards", json={"name": "Cross Source"})).json()
  b2 = (await client.post("/boards", json={"name": "Cross Target"})).json()
  lane1 = await _first_lane_id(client, b1["id"])
  lane2 = await _first_lane_id(client, b2["id"])

  tres = await client.post(
    f"/boards/{b1['id']}/tasks",
    json={"laneId": lane1, "title": "Duplicate me", "priority": "P2", "type": "Feature"},
  )
  assert tres.status_code == 200, tres.text
  source_task = tres.json()

  dres = await client.post(
    f"/tasks/{source_task['id']}/duplicate-to-board",
    json={"targetBoardId": b2["id"], "targetLaneId": lane2, "includeChecklist": True, "includeDependencies": True},
  )
  assert dres.status_code == 200, dres.text
  dup = dres.json()
  assert dup["id"] != source_task["id"]
  assert dup["boardId"] == b2["id"]
  assert dup["laneId"] == lane2
  assert dup["title"] == source_task["title"]

  src_read = await client.get(f"/tasks/{source_task['id']}")
  assert src_read.status_code == 200, src_read.text
  assert src_read.json()["boardId"] == b1["id"]


@pytest.mark.anyio
async def test_transfer_task_to_another_board(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b1 = (await client.post("/boards", json={"name": "Move Source"})).json()
  b2 = (await client.post("/boards", json={"name": "Move Target"})).json()
  lane1 = await _first_lane_id(client, b1["id"])
  lane2 = await _first_lane_id(client, b2["id"])

  tres = await client.post(
    f"/boards/{b1['id']}/tasks",
    json={"laneId": lane1, "title": "Transfer me", "priority": "P2", "type": "Feature"},
  )
  assert tres.status_code == 200, tres.text
  source_task = tres.json()

  mres = await client.post(
    f"/tasks/{source_task['id']}/transfer-board",
    json={"targetBoardId": b2["id"], "targetLaneId": lane2},
  )
  assert mres.status_code == 200, mres.text
  moved = mres.json()
  assert moved["id"] == source_task["id"]
  assert moved["boardId"] == b2["id"]
  assert moved["laneId"] == lane2
  assert moved["jiraSyncEnabled"] is False
