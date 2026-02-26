from __future__ import annotations

import pytest

from tests.conftest import login, seeded_user_id


@pytest.mark.anyio
async def test_notification_preferences_roundtrip(client):
  await login(client, "member@neonlanes.local", "member1234")

  get_res = await client.get("/notifications/preferences")
  assert get_res.status_code == 200, get_res.text
  body = get_res.json()
  assert body["mentions"] is True

  up_res = await client.patch(
    "/notifications/preferences",
    json={"mentions": False, "quietHoursEnabled": True, "quietHoursStart": "22:00", "quietHoursEnd": "07:00"},
  )
  assert up_res.status_code == 200, up_res.text
  updated = up_res.json()
  assert updated["mentions"] is False
  assert updated["quietHoursEnabled"] is True
  assert updated["quietHoursStart"] == "22:00"
  assert updated["quietHoursEnd"] == "07:00"


@pytest.mark.anyio
async def test_mentions_respect_user_preference(client):
  await login(client, "admin@neonlanes.local", "admin1234")

  board = (await client.post("/boards", json={"name": "Notif Prefs Board"})).json()
  lanes = (await client.get(f"/boards/{board['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  add = await client.post(f"/boards/{board['id']}/members", json={"email": "member@neonlanes.local", "role": "member"})
  assert add.status_code in (200, 409), add.text

  member_id = await seeded_user_id("member@neonlanes.local")
  created = await client.post(
    f"/boards/{board['id']}/tasks",
    json={"laneId": lane_id, "title": "Prefs mention test", "priority": "P2", "type": "Feature", "ownerId": member_id},
  )
  assert created.status_code == 200, created.text
  task = created.json()

  await login(client, "member@neonlanes.local", "member1234")
  pref = await client.patch("/notifications/preferences", json={"mentions": False, "quietHoursEnabled": False})
  assert pref.status_code == 200, pref.text

  await login(client, "admin@neonlanes.local", "admin1234")
  c = await client.post(f"/tasks/{task['id']}/comments", json={"body": "Ping @member please review"})
  assert c.status_code == 200, c.text

  await login(client, "member@neonlanes.local", "member1234")
  inbox = await client.get("/notifications/inapp", params={"unreadOnly": "true", "limit": "50"})
  assert inbox.status_code == 200, inbox.text
  titles = [n.get("title") for n in inbox.json()]
  assert "You were mentioned" not in titles
