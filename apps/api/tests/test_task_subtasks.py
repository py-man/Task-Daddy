from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import login


@pytest.mark.anyio
async def test_task_subtasks_create_and_list(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Subtask Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  parent = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Parent", "priority": "P2", "type": "Feature"},
    )
  ).json()

  res = await client.post(f"/tasks/{parent['id']}/subtasks", json={"title": "Child task"})
  assert res.status_code == 200, res.text
  sub = res.json()
  assert sub["parentTaskId"] == parent["id"]

  listed = (await client.get(f"/tasks/{parent['id']}/subtasks")).json()
  assert len(listed) == 1
  assert listed[0]["id"] == sub["id"]


@pytest.mark.anyio
async def test_task_parent_cycle_rejected(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Cycle Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  parent = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Parent", "priority": "P2", "type": "Feature"},
    )
  ).json()
  child = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Child", "priority": "P2", "type": "Feature", "parentTaskId": parent["id"]},
    )
  ).json()

  res = await client.patch(
    f"/tasks/{parent['id']}",
    json={"version": parent["version"], "parentTaskId": child["id"]},
  )
  assert res.status_code == 400, res.text
  assert "cycle" in res.text.lower()


@pytest.mark.anyio
async def test_delete_parent_detaches_subtasks(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Delete Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  parent = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Parent", "priority": "P2", "type": "Feature"},
    )
  ).json()
  child = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Child", "priority": "P2", "type": "Feature", "parentTaskId": parent["id"]},
    )
  ).json()

  deleted = await client.delete(f"/tasks/{parent['id']}")
  assert deleted.status_code == 200, deleted.text

  child_after = (await client.get(f"/tasks/{child['id']}")).json()
  assert child_after["parentTaskId"] is None
