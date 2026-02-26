from __future__ import annotations

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

from conftest import enable_admin_mfa, login


@pytest.mark.anyio
async def test_api_token_can_authenticate_via_bearer(client: AsyncClient) -> None:
  await login(client, "member@neonlanes.local", "member1234")

  created = await client.post("/auth/tokens", json={"name": f"cli-{secrets.token_hex(4)}", "password": "member1234"})
  assert created.status_code == 200, created.text
  token = created.json()["token"]
  token_id = created.json()["apiToken"]["id"]

  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as c2:
    me = await c2.get("/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "member@neonlanes.local"

    # Token management requires a cookie session (defense in depth).
    denied = await c2.get("/auth/tokens")
    assert denied.status_code == 401

  revoked = await client.post(f"/auth/tokens/{token_id}/revoke", json={"password": "member1234"})
  assert revoked.status_code == 200, revoked.text

  async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as c3:
    me2 = await c3.get("/auth/me")
    assert me2.status_code == 401


@pytest.mark.anyio
async def test_api_token_does_not_satisfy_admin_mfa_guard(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")
  await enable_admin_mfa(client)

  created = await client.post("/auth/tokens", json={"name": "admin-cli", "password": "admin1234"})
  assert created.status_code == 200, created.text
  token = created.json()["token"]

  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as c2:
    # Admin-only routes protected by require_admin_mfa_guard should still require a cookie session.
    r = await c2.get("/notifications/destinations")
    assert r.status_code == 401
