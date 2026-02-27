from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.anyio
async def test_task_types_and_priorities_defaults_and_validation(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

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


@pytest.mark.anyio
async def test_sync_task_fields_to_all_boards_copies_custom_and_updates_defaults(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  src = (await client.post("/boards", json={"name": "Source Board"})).json()
  dst = (await client.post("/boards", json={"name": "Target Board"})).json()
  src_board_id = src["id"]
  dst_board_id = dst["id"]

  # Add custom keys to source board.
  created_type = await client.post(
    f"/boards/{src_board_id}/task_types",
    json={"key": "FOLLOW_UP", "name": "Follow-Up", "color": "#22c55e"},
  )
  assert created_type.status_code == 200, created_type.text
  created_prio = await client.post(
    f"/boards/{src_board_id}/priorities",
    json={"key": "BLK", "name": "Blocker", "color": "#ef4444"},
  )
  assert created_prio.status_code == 200, created_prio.text

  # Update default labels on source to verify sync updates existing keys on target.
  upd_type = await client.patch(
    f"/boards/{src_board_id}/task_types/Feature",
    json={"name": "Feature Work", "color": "#2563eb"},
  )
  assert upd_type.status_code == 200, upd_type.text
  upd_prio = await client.patch(
    f"/boards/{src_board_id}/priorities/P2",
    json={"name": "Normal", "color": "#0ea5e9"},
  )
  assert upd_prio.status_code == 200, upd_prio.text

  sync = await client.post(f"/boards/{src_board_id}/task_fields/sync_all")
  assert sync.status_code == 200, sync.text
  payload = sync.json()
  assert payload["ok"] is True
  assert payload["boardsTouched"] >= 1
  assert payload["typesCreated"] >= 1
  assert payload["prioritiesCreated"] >= 1

  dst_types = {t["key"]: t for t in (await client.get(f"/boards/{dst_board_id}/task_types")).json()}
  dst_prios = {p["key"]: p for p in (await client.get(f"/boards/{dst_board_id}/priorities")).json()}

  assert dst_types["FOLLOW_UP"]["name"] == "Follow-Up"
  assert dst_types["Feature"]["name"] == "Feature Work"
  assert dst_types["Feature"]["color"] == "#2563eb"

  assert dst_prios["BLK"]["name"] == "Blocker"
  assert dst_prios["P2"]["name"] == "Normal"
  assert dst_prios["P2"]["color"] == "#0ea5e9"

  # Re-running sync should be idempotent.
  sync2 = await client.post(f"/boards/{src_board_id}/task_fields/sync_all")
  assert sync2.status_code == 200, sync2.text
  payload2 = sync2.json()
  assert payload2["typesCreated"] == 0
  assert payload2["typesUpdated"] == 0
  assert payload2["prioritiesCreated"] == 0
  assert payload2["prioritiesUpdated"] == 0
