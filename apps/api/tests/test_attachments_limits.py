from __future__ import annotations

import secrets

import pytest
from httpx import AsyncClient

from app.config import settings

from conftest import login


@pytest.mark.anyio
async def test_attachment_upload_enforces_size_limit(client: AsyncClient) -> None:
  await login(client, "member@neonlanes.local", "member1234")

  board = (await client.post("/boards", json={"name": f"Upload {secrets.token_hex(4)}"})).json()
  lanes = (await client.get(f"/boards/{board['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  task = (await client.post(f"/boards/{board['id']}/tasks", json={"title": "Attachment test", "laneId": lane_id})).json()

  orig = settings.max_attachment_bytes
  settings.max_attachment_bytes = 10
  try:
    r = await client.post(
      f"/tasks/{task['id']}/attachments",
      files={"file": ("big.txt", b"a" * 11, "text/plain")},
    )
    assert r.status_code == 413, r.text
  finally:
    settings.max_attachment_bytes = orig
