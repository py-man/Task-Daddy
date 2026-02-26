from __future__ import annotations

import secrets

import pytest
from httpx import AsyncClient

from app.security import totp_code
from conftest import enable_admin_mfa, login


@pytest.mark.anyio
async def test_notifications_destinations_crud_and_test_send_local(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")
  mfa = await enable_admin_mfa(client)
  await login(client, "admin@neonlanes.local", "admin1234", totpCode=totp_code(mfa["secret"]))

  # Create local destination (no external network required)
  name = f"Local {secrets.token_hex(4)}"
  create = await client.post("/notifications/destinations", json={"provider": "local", "name": name, "enabled": True})
  assert create.status_code == 200, create.text
  dest_id = create.json()["id"]

  listed = await client.get("/notifications/destinations")
  assert listed.status_code == 200, listed.text
  assert any(d["id"] == dest_id for d in listed.json())

  upd = await client.patch(f"/notifications/destinations/{dest_id}", json={"provider": "local", "name": name + "2", "enabled": False})
  assert upd.status_code == 200, upd.text
  assert upd.json()["enabled"] is False

  # Disabled destination cannot send
  test_disabled = await client.post(f"/notifications/destinations/{dest_id}/test", json={"title": "t", "message": "m"})
  assert test_disabled.status_code == 400, test_disabled.text

  # Enable and send test
  upd2 = await client.patch(f"/notifications/destinations/{dest_id}", json={"provider": "local", "name": name + "2", "enabled": True})
  assert upd2.status_code == 200, upd2.text

  test = await client.post(f"/notifications/destinations/{dest_id}/test", json={"title": "Task-Daddy test", "message": "Hello", "priority": 0})
  assert test.status_code == 200, test.text
  assert test.json()["ok"] is True
  assert test.json()["provider"] == "local"

  # Delete
  d = await client.delete(f"/notifications/destinations/{dest_id}")
  assert d.status_code == 200, d.text
  listed2 = await client.get("/notifications/destinations")
  assert listed2.status_code == 200, listed2.text
  assert not any(x["id"] == dest_id for x in listed2.json())

