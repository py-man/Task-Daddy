from __future__ import annotations

import secrets

import pytest
from httpx import AsyncClient

from conftest import login


@pytest.mark.anyio
async def test_bulk_import_is_idempotent_and_skips_existing_titles(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": f"Import {secrets.token_hex(4)}"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  items = [
    {"title": "A", "priority": "P2", "type": "Feature"},
    {"title": "B", "priority": "P2", "type": "Feature"},
    {"title": "C", "priority": "P2", "type": "Feature"},
  ]

  r1 = await client.post(f"/boards/{b['id']}/tasks/bulk_import", json={"defaultLaneId": lane_id, "items": items})
  assert r1.status_code == 200, r1.text
  out1 = r1.json()
  assert out1["createdCount"] == 3
  assert out1["existingCount"] == 0
  ids1 = [x["task"]["id"] for x in out1["results"]]

  # Replay with same payload: should not create duplicates.
  r2 = await client.post(f"/boards/{b['id']}/tasks/bulk_import", json={"defaultLaneId": lane_id, "items": items})
  assert r2.status_code == 200, r2.text
  out2 = r2.json()
  assert out2["createdCount"] == 0
  assert out2["existingCount"] == 3
  ids2 = [x["task"]["id"] for x in out2["results"]]
  assert set(ids1) == set(ids2)

  tasks = (await client.get(f"/boards/{b['id']}/tasks")).json()
  assert len(tasks) == 3


@pytest.mark.anyio
async def test_bulk_import_can_attach_idempotency_key_to_existing_manual_task(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": f"Import Existing {secrets.token_hex(4)}"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  manual = (await client.post(f"/boards/{b['id']}/tasks", json={"laneId": lane_id, "title": "Manual"})).json()

  r = await client.post(
    f"/boards/{b['id']}/tasks/bulk_import",
    json={"defaultLaneId": lane_id, "items": [{"title": "Manual", "idempotencyKey": "k1"}]},
  )
  assert r.status_code == 200, r.text
  out = r.json()
  assert out["createdCount"] == 0
  assert out["existingCount"] == 1
  assert out["results"][0]["task"]["id"] == manual["id"]

