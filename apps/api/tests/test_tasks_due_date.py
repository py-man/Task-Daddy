from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import login


@pytest.mark.anyio
async def test_due_date_accepts_date_only_and_iso(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Due Date Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "T", "priority": "P2", "type": "Feature"},
    )
  ).json()

  r1 = await client.patch(f"/tasks/{t['id']}", json={"version": t["version"], "dueDate": "2026-02-22"})
  assert r1.status_code == 200, r1.text
  assert r1.json()["dueDate"].startswith("2026-02-22T")

  t2 = r1.json()
  r2 = await client.patch(f"/tasks/{t['id']}", json={"version": t2["version"], "dueDate": "2026-02-22T00:00:00Z"})
  assert r2.status_code == 200, r2.text
  assert r2.json()["dueDate"].endswith("+00:00") or r2.json()["dueDate"].endswith("Z")


@pytest.mark.anyio
async def test_due_date_empty_string_clears(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Due Date Clear Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "T", "priority": "P2", "type": "Feature", "dueDate": "2026-02-22"},
    )
  ).json()

  r = await client.patch(f"/tasks/{t['id']}", json={"version": t["version"], "dueDate": ""})
  assert r.status_code == 200, r.text
  assert r.json()["dueDate"] is None

