from __future__ import annotations

import pytest

from tests.conftest import login, seeded_user_id


@pytest.mark.anyio
async def test_inapp_notifications_task_assigned_and_mark_read(client):
  await login(client, "admin@taskdaddy.local", "admin1234")

  board = (await client.post("/boards", json={"name": "Notif Board"})).json()
  lanes = (await client.get(f"/boards/{board['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  member_id = await seeded_user_id("member@taskdaddy.local")
  add = await client.post(f"/boards/{board['id']}/members", json={"email": "member@taskdaddy.local", "role": "member"})
  assert add.status_code in (200, 409), add.text

  created = await client.post(
    f"/boards/{board['id']}/tasks",
    json={"laneId": lane_id, "title": "Assigned task", "priority": "P2", "type": "Feature", "ownerId": member_id},
  )
  assert created.status_code == 200, created.text

  await login(client, "member@taskdaddy.local", "member1234")
  inbox = await client.get("/notifications/inapp", params={"unreadOnly": "true", "limit": "50"})
  assert inbox.status_code == 200, inbox.text
  items = inbox.json()
  assigned = next((n for n in items if n["title"] == "New task assigned"), None)
  assert assigned is not None
  assert assigned.get("taxonomy") == "action_required"
  assert int(assigned.get("burstCount") or 1) == 1

  # Mark all as read
  mark = await client.post("/notifications/inapp/mark-all-read")
  assert mark.status_code == 200, mark.text
  inbox2 = await client.get("/notifications/inapp", params={"unreadOnly": "true", "limit": "50"})
  assert inbox2.status_code == 200
  assert inbox2.json() == []


@pytest.mark.anyio
async def test_inapp_notifications_mentions_and_task_moved(client):
  await login(client, "admin@taskdaddy.local", "admin1234")

  board = (await client.post("/boards", json={"name": "Notif Mention Board"})).json()
  lanes = (await client.get(f"/boards/{board['id']}/lanes")).json()
  backlog_lane = lanes[0]["id"]
  target_lane = lanes[1]["id"] if len(lanes) > 1 else lanes[0]["id"]

  member_id = await seeded_user_id("member@taskdaddy.local")
  add = await client.post(f"/boards/{board['id']}/members", json={"email": "member@taskdaddy.local", "role": "member"})
  assert add.status_code in (200, 409), add.text

  created = await client.post(
    f"/boards/{board['id']}/tasks",
    json={"laneId": backlog_lane, "title": "Mention me task", "priority": "P2", "type": "Feature", "ownerId": member_id},
  )
  assert created.status_code == 200, created.text
  task = created.json()

  await client.post(f"/tasks/{task['id']}/comments", json={"body": "Please review this @member and @member@taskdaddy.local"})
  moved = await client.post(f"/tasks/{task['id']}/move", json={"laneId": target_lane, "toIndex": 0, "version": task["version"]})
  assert moved.status_code == 200, moved.text

  await login(client, "member@taskdaddy.local", "member1234")
  inbox = await client.get("/notifications/inapp", params={"unreadOnly": "true", "limit": "100"})
  assert inbox.status_code == 200, inbox.text
  items = inbox.json()
  titles = [n.get("title") for n in items]
  assert "You were mentioned" in titles
  assert "Task moved" in titles
  mentioned = next((n for n in items if n.get("title") == "You were mentioned"), None)
  moved_note = next((n for n in items if n.get("title") == "Task moved"), None)
  assert mentioned and mentioned.get("taxonomy") == "action_required"
  assert moved_note and moved_note.get("taxonomy") == "informational"


@pytest.mark.anyio
async def test_inapp_notifications_burst_collapse_for_comment_and_move(client):
  await login(client, "admin@taskdaddy.local", "admin1234")

  board = (await client.post("/boards", json={"name": "Notif Burst Board"})).json()
  lanes = (await client.get(f"/boards/{board['id']}/lanes")).json()
  backlog_lane = lanes[0]["id"]
  target_lane = lanes[1]["id"] if len(lanes) > 1 else lanes[0]["id"]

  member_id = await seeded_user_id("member@taskdaddy.local")
  add = await client.post(f"/boards/{board['id']}/members", json={"email": "member@taskdaddy.local", "role": "member"})
  assert add.status_code in (200, 409), add.text

  created = await client.post(
    f"/boards/{board['id']}/tasks",
    json={"laneId": backlog_lane, "title": "Burst me task", "priority": "P2", "type": "Feature", "ownerId": member_id},
  )
  assert created.status_code == 200, created.text
  task = created.json()

  for i in range(3):
    c = await client.post(f"/tasks/{task['id']}/comments", json={"body": f"storm comment {i}"})
    assert c.status_code == 200, c.text

  move1 = await client.post(f"/tasks/{task['id']}/move", json={"laneId": target_lane, "toIndex": 0, "version": task["version"]})
  assert move1.status_code == 200, move1.text
  moved = move1.json()
  move2 = await client.post(f"/tasks/{task['id']}/move", json={"laneId": backlog_lane, "toIndex": 0, "version": moved["version"]})
  assert move2.status_code == 200, move2.text

  await login(client, "member@taskdaddy.local", "member1234")
  inbox = await client.get("/notifications/inapp", params={"unreadOnly": "true", "limit": "100"})
  assert inbox.status_code == 200, inbox.text
  items = inbox.json()

  comment_note = next((n for n in items if n.get("title") == "New comment on your task"), None)
  moved_note = next((n for n in items if n.get("title") == "Task moved"), None)
  assert comment_note is not None
  assert int(comment_note.get("burstCount") or 1) >= 3
  assert moved_note is not None
  assert int(moved_note.get("burstCount") or 1) >= 2
