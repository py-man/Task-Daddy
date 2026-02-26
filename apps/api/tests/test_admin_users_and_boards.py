from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.security import totp_code
from conftest import enable_admin_mfa, login


@pytest.mark.anyio
async def test_board_name_unique_case_insensitive(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  res1 = await client.post("/boards", json={"name": "  Unique Board  "})
  assert res1.status_code == 200, res1.text

  res2 = await client.post("/boards", json={"name": "unique board"})
  assert res2.status_code == 409, res2.text


@pytest.mark.anyio
async def test_admin_can_disable_user_and_sessions_invalidated(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@neonlanes.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  cres = await client.post("/users", json={"email": "disable.me@neonlanes.local", "name": "Disable Me", "role": "member", "password": "password123"})
  assert cres.status_code == 200, cres.text
  uid = cres.json()["user"]["id"]

  # Login as that user
  res_login = await client.post("/auth/login", json={"email": "disable.me@neonlanes.local", "password": "password123"})
  assert res_login.status_code == 200, res_login.text
  cookie = res_login.headers.get("set-cookie") or ""
  assert "nl_session=" in cookie
  user_session = cookie.split("nl_session=", 1)[1].split(";", 1)[0]

  # Disable from admin session (re-login admin)
  await login(client, "admin@neonlanes.local", "admin1234", totpCode=totp_code(mfa["secret"]))
  dis = await client.patch(f"/users/{uid}", json={"active": False})
  assert dis.status_code == 200, dis.text
  assert dis.json()["active"] is False

  # Old user session should no longer work.
  client.cookies.set("nl_session", user_session)
  me = await client.get("/auth/me")
  assert me.status_code in (401, 403), me.text


@pytest.mark.anyio
async def test_board_delete_with_transfer_moves_tasks(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  a = await client.post("/boards", json={"name": "Transfer From"})
  b = await client.post("/boards", json={"name": "Transfer To"})
  assert a.status_code == 200 and b.status_code == 200
  a_id = a.json()["id"]
  b_id = b.json()["id"]

  lanes_a = await client.get(f"/boards/{a_id}/lanes")
  assert lanes_a.status_code == 200
  lane_id = lanes_a.json()[0]["id"]

  t = await client.post(f"/boards/{a_id}/tasks", json={"laneId": lane_id, "title": "Move me", "priority": "P2", "type": "Feature"})
  assert t.status_code == 200, t.text

  delres = await client.post(f"/boards/{a_id}/delete", json={"mode": "transfer", "transferToBoardId": b_id})
  assert delres.status_code == 200, delres.text

  # Source board gone
  g = await client.get(f"/boards/{a_id}")
  assert g.status_code == 403 or g.status_code == 404

  tasks_b = await client.get(f"/boards/{b_id}/tasks")
  assert tasks_b.status_code == 200, tasks_b.text
  titles = [x["title"] for x in tasks_b.json()]
  assert "Move me" in titles


@pytest.mark.anyio
async def test_delete_user_reassigns_or_unassigns_tasks(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@neonlanes.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  u1 = await client.post("/users", json={"email": "u1@neonlanes.local", "name": "U1", "role": "member", "password": "password123"})
  u2 = await client.post("/users", json={"email": "u2@neonlanes.local", "name": "U2", "role": "member", "password": "password123"})
  assert u1.status_code == 200 and u2.status_code == 200
  u1_id = u1.json()["user"]["id"]
  u2_id = u2.json()["user"]["id"]

  b = await client.post("/boards", json={"name": "User Delete Reassign"})
  assert b.status_code == 200, b.text
  board_id = b.json()["id"]
  lanes = await client.get(f"/boards/{board_id}/lanes")
  lane_id = lanes.json()[0]["id"]

  add1 = await client.post(f"/boards/{board_id}/members", json={"email": "u1@neonlanes.local", "role": "member"})
  add2 = await client.post(f"/boards/{board_id}/members", json={"email": "u2@neonlanes.local", "role": "member"})
  assert add1.status_code == 200 and add2.status_code == 200

  t1 = await client.post(
    f"/boards/{board_id}/tasks",
    json={"laneId": lane_id, "title": "Owned by u1", "priority": "P2", "type": "Feature", "ownerId": u1_id},
  )
  assert t1.status_code == 200, t1.text
  task_id = t1.json()["id"]

  del_reassign = await client.post(f"/users/{u1_id}/delete", json={"mode": "reassign", "reassignToUserId": u2_id})
  assert del_reassign.status_code == 200, del_reassign.text

  got = await client.get(f"/tasks/{task_id}")
  assert got.status_code == 200, got.text
  assert got.json()["ownerId"] == u2_id

  # Unassign mode
  t2 = await client.post(
    f"/boards/{board_id}/tasks",
    json={"laneId": lane_id, "title": "Owned by u2", "priority": "P2", "type": "Feature", "ownerId": u2_id},
  )
  assert t2.status_code == 200, t2.text
  task2_id = t2.json()["id"]

  del_unassign = await client.post(f"/users/{u2_id}/delete", json={"mode": "unassign"})
  assert del_unassign.status_code == 200, del_unassign.text
  got2 = await client.get(f"/tasks/{task2_id}")
  assert got2.status_code == 200, got2.text
  assert got2.json()["ownerId"] is None

  # Deleted users are soft-deleted (email rewritten) but hidden unless includeDeleted=true.
  listed = await client.get("/users?includeInactive=true")
  assert listed.status_code == 200, listed.text
  assert not any((u.get("email") or "").startswith("deleted+") for u in listed.json())

  listed_all = await client.get("/users?includeInactive=true&includeDeleted=true")
  assert listed_all.status_code == 200, listed_all.text
  assert any((u.get("email") or "").startswith("deleted+") for u in listed_all.json())
