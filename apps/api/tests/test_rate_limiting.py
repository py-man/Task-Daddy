from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.anyio
async def test_login_rate_limited(client: AsyncClient) -> None:
  orig_ip = settings.rate_limit_login_ip_per_minute
  orig_email = settings.rate_limit_login_email_per_minute
  settings.rate_limit_login_ip_per_minute = 3
  settings.rate_limit_login_email_per_minute = 3
  try:
    for _ in range(3):
      r = await client.post("/auth/login", json={"email": "nobody@example.com", "password": "bad"})
      assert r.status_code == 401, r.text
    r = await client.post("/auth/login", json={"email": "nobody@example.com", "password": "bad"})
    assert r.status_code == 429, r.text
    assert r.headers.get("retry-after")
  finally:
    settings.rate_limit_login_ip_per_minute = orig_ip
    settings.rate_limit_login_email_per_minute = orig_email


@pytest.mark.anyio
async def test_password_reset_request_rate_limited(client: AsyncClient) -> None:
  orig_ip = settings.rate_limit_password_reset_ip_per_minute
  orig_email = settings.rate_limit_password_reset_email_per_minute
  settings.rate_limit_password_reset_ip_per_minute = 2
  settings.rate_limit_password_reset_email_per_minute = 2
  try:
    for _ in range(2):
      r = await client.post("/auth/password/reset/request", json={"email": "nobody@example.com"})
      assert r.status_code == 200, r.text
    r = await client.post("/auth/password/reset/request", json={"email": "nobody@example.com"})
    assert r.status_code == 429, r.text
  finally:
    settings.rate_limit_password_reset_ip_per_minute = orig_ip
    settings.rate_limit_password_reset_email_per_minute = orig_email

