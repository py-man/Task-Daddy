from __future__ import annotations

import pytest

from app.routers import github as github_router
from tests.conftest import enable_admin_mfa, login


@pytest.mark.anyio
async def test_github_connection_crud_and_test(client, monkeypatch):
  await login(client, "admin@taskdaddy.local", "admin1234")
  await enable_admin_mfa(client)

  async def _fake_ping(*, base_url: str, api_token: str):
    assert base_url.startswith("https://")
    assert api_token == "ghp_top_secret_token"
    return {"ok": True, "login": "taskdaddy-bot", "id": 42, "url": "https://github.com/taskdaddy-bot"}

  monkeypatch.setattr(github_router, "github_ping", _fake_ping)

  created = await client.post(
    "/github/connections",
    json={
      "name": "GitHub Prod",
      "baseUrl": "api.github.com",
      "apiToken": "ghp_top_secret_token",
      "defaultOwner": "task-daddy",
      "defaultRepo": "task-daddy",
      "enabled": True,
    },
  )
  assert created.status_code == 200, created.text
  conn = created.json()
  assert conn["name"] == "GitHub Prod"
  assert conn["baseUrl"] == "https://api.github.com"
  assert conn["defaultOwner"] == "task-daddy"
  assert conn["defaultRepo"] == "task-daddy"

  listed = await client.get("/github/connections")
  assert listed.status_code == 200, listed.text
  assert len(listed.json()) == 1

  tested = await client.post(f"/github/connections/{conn['id']}/test")
  assert tested.status_code == 200, tested.text
  assert tested.json()["ok"] is True
  assert tested.json()["result"]["login"] == "taskdaddy-bot"

  patched = await client.patch(
    f"/github/connections/{conn['id']}",
    json={"name": "GitHub OSS", "defaultOwner": "taskdaddy", "defaultRepo": "core", "enabled": False},
  )
  assert patched.status_code == 200, patched.text
  after = patched.json()
  assert after["name"] == "GitHub OSS"
  assert after["defaultOwner"] == "taskdaddy"
  assert after["defaultRepo"] == "core"
  assert after["enabled"] is False

  deleted = await client.delete(f"/github/connections/{conn['id']}")
  assert deleted.status_code == 200, deleted.text
  assert deleted.json()["ok"] is True

  listed2 = await client.get("/github/connections")
  assert listed2.status_code == 200, listed2.text
  assert listed2.json() == []

