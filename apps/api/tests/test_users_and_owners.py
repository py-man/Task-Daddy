from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from conftest import SessionLocal, enable_admin_mfa, login
from app.models import PasswordResetToken, User
from app.security import totp_code


@pytest.mark.anyio
async def test_admin_can_create_user(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  res = await client.post(
    "/users",
    json={"email": "new.user@taskdaddy.local", "name": "New User", "role": "member"},
  )
  assert res.status_code == 200, res.text
  body = res.json()
  assert body["user"]["email"] == "new.user@taskdaddy.local"
  assert body["tempPassword"]

  res2 = await client.get("/users")
  assert res2.status_code == 200
  emails = [u["email"] for u in res2.json()]
  assert "new.user@taskdaddy.local" in emails


@pytest.mark.anyio
async def test_member_cannot_create_user(client: AsyncClient) -> None:
  await login(client, "member@taskdaddy.local", "member1234")
  res = await client.post(
    "/users",
    json={"email": "x@taskdaddy.local", "name": "X", "role": "member"},
  )
  assert res.status_code == 403


@pytest.mark.anyio
async def test_admin_can_invite_user_and_create_reset_token(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  invited_email = "invite.user@taskdaddy.local"
  res = await client.post(
    "/users/invite",
    json={"email": invited_email, "name": "Invite User", "role": "member", "inviteBaseUrl": "http://localhost:3000"},
  )
  assert res.status_code == 200, res.text
  body = res.json()
  assert body["created"] is True
  assert body["user"]["email"] == invited_email
  assert "/login?mode=reset&token=" in body["inviteUrl"]
  assert body["inviteToken"]

  async with SessionLocal() as db:
    u = (await db.execute(select(User).where(User.email == invited_email))).scalar_one()
    tokens = (
      await db.execute(
        select(PasswordResetToken).where(
          PasswordResetToken.user_id == u.id,
          PasswordResetToken.used_at.is_(None),
        )
      )
    ).scalars().all()
    assert len(tokens) == 1


@pytest.mark.anyio
async def test_invite_existing_user_rotates_unexpired_token(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  invited_email = "rotate.invite@taskdaddy.local"
  first = await client.post(
    "/users/invite",
    json={"email": invited_email, "name": "Rotate First", "role": "member", "inviteBaseUrl": "http://localhost:3000"},
  )
  assert first.status_code == 200, first.text
  token_one = first.json()["inviteToken"]

  second = await client.post(
    "/users/invite",
    json={"email": invited_email, "name": "Rotate Second", "role": "member", "inviteBaseUrl": "http://localhost:3000"},
  )
  assert second.status_code == 200, second.text
  body = second.json()
  assert body["created"] is False
  assert body["inviteToken"] != token_one

  async with SessionLocal() as db:
    u = (await db.execute(select(User).where(User.email == invited_email))).scalar_one()
    tokens = (
      await db.execute(
        select(PasswordResetToken).where(
          PasswordResetToken.user_id == u.id,
          PasswordResetToken.used_at.is_(None),
        )
      )
    ).scalars().all()
    assert len(tokens) == 1


@pytest.mark.anyio
async def test_member_cannot_invite_user(client: AsyncClient) -> None:
  await login(client, "member@taskdaddy.local", "member1234")
  res = await client.post(
    "/users/invite",
    json={"email": "blocked.invite@taskdaddy.local", "name": "Blocked", "role": "member"},
  )
  assert res.status_code == 403


@pytest.mark.anyio
async def test_task_owner_must_be_board_member(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  # Create an extra user (not board member).
  ures = await client.post("/users", json={"email": "outsider@taskdaddy.local", "name": "Outsider", "role": "member"})
  assert ures.status_code == 200
  outsider_id = ures.json()["user"]["id"]

  bres = await client.post("/boards", json={"name": "Owner Validation"})
  assert bres.status_code == 200
  board_id = bres.json()["id"]

  lres = await client.get(f"/boards/{board_id}/lanes")
  assert lres.status_code == 200
  lane_id = lres.json()[0]["id"]

  # Cannot assign owner not in board.
  tres = await client.post(
    f"/boards/{board_id}/tasks",
    json={"laneId": lane_id, "title": "T1", "priority": "P2", "type": "Feature", "ownerId": outsider_id},
  )
  assert tres.status_code == 400

  # Add outsider to board then assign works.
  add = await client.post(f"/boards/{board_id}/members", json={"email": "outsider@taskdaddy.local", "role": "member"})
  assert add.status_code == 200, add.text

  tres2 = await client.post(
    f"/boards/{board_id}/tasks",
    json={"laneId": lane_id, "title": "T2", "priority": "P2", "type": "Feature", "ownerId": outsider_id},
  )
  assert tres2.status_code == 200, tres2.text
  assert tres2.json()["ownerId"] == outsider_id


@pytest.mark.anyio
async def test_unassign_owner_with_null_ownerId(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  bres = await client.post("/boards", json={"name": "Unassign"})
  board_id = bres.json()["id"]
  lres = await client.get(f"/boards/{board_id}/lanes")
  lane_id = lres.json()[0]["id"]

  # Assign seeded member.
  users = await client.get("/users")
  member_id = next(u["id"] for u in users.json() if u["email"] == "member@taskdaddy.local")
  add = await client.post(f"/boards/{board_id}/members", json={"email": "member@taskdaddy.local", "role": "member"})
  assert add.status_code == 200, add.text

  tres = await client.post(
    f"/boards/{board_id}/tasks",
    json={"laneId": lane_id, "title": "T", "priority": "P2", "type": "Feature", "ownerId": member_id},
  )
  assert tres.status_code == 200, tres.text
  task = tres.json()
  assert task["ownerId"] == member_id

  up = await client.patch(f"/tasks/{task['id']}", json={"version": task["version"], "ownerId": None})
  assert up.status_code == 200, up.text
  assert up.json()["ownerId"] is None


@pytest.mark.anyio
async def test_admin_can_block_login_and_set_password(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  created = await client.post(
    "/users",
    json={"email": "lockable@taskdaddy.local", "name": "Lockable User", "role": "member", "password": "InitialPass123!"},
  )
  assert created.status_code == 200, created.text
  uid = created.json()["user"]["id"]

  blocked = await client.patch(f"/users/{uid}", json={"loginDisabled": True})
  assert blocked.status_code == 200, blocked.text
  assert blocked.json()["loginDisabled"] is True

  denied = await client.post("/auth/login", json={"email": "lockable@taskdaddy.local", "password": "InitialPass123!"})
  assert denied.status_code == 403
  assert "Login disabled" in denied.text

  unblocked = await client.patch(f"/users/{uid}", json={"loginDisabled": False, "password": "NewPass456!"})
  assert unblocked.status_code == 200, unblocked.text
  assert unblocked.json()["loginDisabled"] is False

  old_fail = await client.post("/auth/login", json={"email": "lockable@taskdaddy.local", "password": "InitialPass123!"})
  assert old_fail.status_code == 401

  new_ok = await client.post("/auth/login", json={"email": "lockable@taskdaddy.local", "password": "NewPass456!"})
  assert new_ok.status_code == 200, new_ok.text
