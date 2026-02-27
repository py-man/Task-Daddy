from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.security import totp_code
from conftest import login


@pytest.mark.anyio
async def test_admin_mfa_enrollment_and_admin_guard(client: AsyncClient) -> None:
  # Login without MFA first (allowed) to enroll.
  await login(client, "admin@taskdaddy.local", "admin1234")

  start = await client.post("/auth/mfa/start", json={"password": "admin1234"})
  assert start.status_code == 200, start.text
  secret = start.json()["secret"]

  code = totp_code(secret, now=int(time.time()))
  confirm = await client.post("/auth/mfa/confirm", json={"totpCode": code})
  assert confirm.status_code == 200, confirm.text
  recovery = confirm.json()["recoveryCodes"]
  assert isinstance(recovery, list) and len(recovery) >= 5

  # Admin endpoints require MFA verified session: login again with TOTP.
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(secret, now=int(time.time())))

  res = await client.post("/users", json={"email": "mfa.user@taskdaddy.local", "name": "MFA User", "role": "member"})
  assert res.status_code == 200, res.text


@pytest.mark.anyio
async def test_mfa_confirm_marks_current_session_verified_for_admin_actions(client: AsyncClient) -> None:
  # Login password-only, enroll MFA, then perform admin action without re-login.
  await login(client, "admin@taskdaddy.local", "admin1234")

  start = await client.post("/auth/mfa/start", json={"password": "admin1234"})
  assert start.status_code == 200, start.text
  secret = start.json()["secret"]

  confirm = await client.post("/auth/mfa/confirm", json={"totpCode": totp_code(secret, now=int(time.time()))})
  assert confirm.status_code == 200, confirm.text

  created = await client.post("/users", json={"email": "post.confirm@taskdaddy.local", "name": "Post Confirm", "role": "member"})
  assert created.status_code == 200, created.text


@pytest.mark.anyio
async def test_recovery_code_is_one_time_use(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  start = await client.post("/auth/mfa/start", json={"password": "admin1234"})
  secret = start.json()["secret"]
  confirm = await client.post("/auth/mfa/confirm", json={"totpCode": totp_code(secret, now=int(time.time()))})
  codes = confirm.json()["recoveryCodes"]
  first = codes[0]

  await login(client, "admin@taskdaddy.local", "admin1234", recoveryCode=first)
  # Reusing should fail.
  res = await client.post("/auth/login", json={"email": "admin@taskdaddy.local", "password": "admin1234", "recoveryCode": first})
  assert res.status_code == 401


@pytest.mark.anyio
async def test_sessions_list_and_revoke(client: AsyncClient) -> None:
  await login(client, "member@taskdaddy.local", "member1234")
  sessions = await client.get("/auth/sessions")
  assert sessions.status_code == 200
  sid = sessions.json()[0]["id"]

  revoke = await client.post("/auth/sessions/revoke", json={"sessionId": sid})
  assert revoke.status_code == 200


@pytest.mark.anyio
async def test_trusted_device_skips_mfa_and_can_be_revoked(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")
  start = await client.post("/auth/mfa/start", json={"password": "admin1234"})
  assert start.status_code == 200, start.text
  secret = start.json()["secret"]
  code = totp_code(secret, now=int(time.time()))

  confirm = await client.post("/auth/mfa/confirm", json={"totpCode": code})
  assert confirm.status_code == 200, confirm.text

  # Login with MFA and remember this device.
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(secret, now=int(time.time())), rememberDevice=True)
  trusted = await client.get("/auth/mfa/trusted_devices")
  assert trusted.status_code == 200, trusted.text
  trusted_items = trusted.json()
  assert len(trusted_items) >= 1

  # Drop session cookie but keep trusted-device cookie; login should skip MFA.
  client.cookies.delete("nl_session")
  no_mfa = await client.post("/auth/login", json={"email": "admin@taskdaddy.local", "password": "admin1234"})
  assert no_mfa.status_code == 200, no_mfa.text

  # Revoke all trusted devices and verify MFA is required again.
  revoked = await client.post("/auth/mfa/trusted_devices/revoke_all")
  assert revoked.status_code == 200, revoked.text
  client.cookies.delete("nl_session")
  must_mfa = await client.post("/auth/login", json={"email": "admin@taskdaddy.local", "password": "admin1234"})
  assert must_mfa.status_code == 401
  assert "MFA required" in must_mfa.text


@pytest.mark.anyio
async def test_global_session_revoke_requires_admin_mfa_and_clears_other_sessions(client: AsyncClient) -> None:
  # Member cannot invoke global revoke.
  await login(client, "member@taskdaddy.local", "member1234")
  denied = await client.post("/auth/sessions/revoke_all_global")
  assert denied.status_code == 403

  # Admin enrolls MFA and creates two independent sessions.
  await login(client, "admin@taskdaddy.local", "admin1234")
  start = await client.post("/auth/mfa/start", json={"password": "admin1234"})
  assert start.status_code == 200, start.text
  secret = start.json()["secret"]
  confirm = await client.post("/auth/mfa/confirm", json={"totpCode": totp_code(secret, now=int(time.time()))})
  assert confirm.status_code == 200, confirm.text

  primary = AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")
  secondary = AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")
  try:
    await login(primary, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(secret, now=int(time.time())))
    await login(secondary, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(secret, now=int(time.time())))

    ok = await primary.post("/auth/sessions/revoke_all_global")
    assert ok.status_code == 200, ok.text

    # Secondary session should be invalidated.
    me = await secondary.get("/auth/me")
    assert me.status_code == 401
  finally:
    await primary.aclose()
    await secondary.aclose()
