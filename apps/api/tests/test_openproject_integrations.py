from __future__ import annotations

import pytest

from app.routers import openproject as openproject_router
from tests.conftest import enable_admin_mfa, login


@pytest.mark.anyio
async def test_openproject_connection_crud_and_test(client, monkeypatch):
  await login(client, "admin@neonlanes.local", "admin1234")
  await enable_admin_mfa(client)

  async def _fake_ping(*, base_url: str, api_token: str):
    assert base_url.startswith("https://")
    assert api_token == "top-secret-token"
    return {"ok": True, "instanceName": "Demo OpenProject", "coreVersion": "14.0.0"}

  monkeypatch.setattr(openproject_router, "openproject_ping", _fake_ping)

  created = await client.post(
    "/openproject/connections",
    json={
      "name": "OpenProject Prod",
      "baseUrl": "openproject.example.com",
      "apiToken": "top-secret-token",
      "projectIdentifier": "ops",
      "enabled": True,
    },
  )
  assert created.status_code == 200, created.text
  conn = created.json()
  assert conn["name"] == "OpenProject Prod"
  assert conn["baseUrl"] == "https://openproject.example.com"
  assert conn["projectIdentifier"] == "ops"

  listed = await client.get("/openproject/connections")
  assert listed.status_code == 200, listed.text
  assert len(listed.json()) == 1

  tested = await client.post(f"/openproject/connections/{conn['id']}/test")
  assert tested.status_code == 200, tested.text
  assert tested.json()["ok"] is True
  assert tested.json()["result"]["instanceName"] == "Demo OpenProject"

  patched = await client.patch(
    f"/openproject/connections/{conn['id']}",
    json={"name": "OpenProject Ops", "projectIdentifier": "platform", "enabled": False},
  )
  assert patched.status_code == 200, patched.text
  after = patched.json()
  assert after["name"] == "OpenProject Ops"
  assert after["projectIdentifier"] == "platform"
  assert after["enabled"] is False

  deleted = await client.delete(f"/openproject/connections/{conn['id']}")
  assert deleted.status_code == 200, deleted.text
  assert deleted.json()["ok"] is True

  listed2 = await client.get("/openproject/connections")
  assert listed2.status_code == 200, listed2.text
  assert listed2.json() == []
