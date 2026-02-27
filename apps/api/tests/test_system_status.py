from __future__ import annotations

import pytest

from app.security import totp_code
from conftest import enable_admin_mfa, login

pytestmark = pytest.mark.anyio


async def test_system_status_requires_admin(client):
  await login(client, "member@taskdaddy.local", "member1234")
  res = await client.get("/admin/system-status")
  assert res.status_code == 403


async def test_system_status_returns_sections_for_admin_with_mfa(client):
  await login(client, "admin@taskdaddy.local", "admin1234")
  setup = await enable_admin_mfa(client)
  await login(client, "admin@taskdaddy.local", "admin1234", totpCode=totp_code(setup["secret"]))
  res = await client.get("/admin/system-status")
  assert res.status_code == 200, res.text
  body = res.json()
  assert body["version"]
  sections = body["sections"]
  keys = {section["key"] for section in sections}
  assert {"api", "postgres", "cache", "queue", "notifications", "jobs"}.issubset(keys)
  api_section = next(s for s in sections if s["key"] == "api")
  details = "\n".join(api_section["details"])
  assert "uptime:" in details
  assert "p95 latency" in details
  notif_section = next(s for s in sections if s["key"] == "notifications")
  notif_details = "\n".join(notif_section["details"])
  assert "success rate (24h):" in notif_details
