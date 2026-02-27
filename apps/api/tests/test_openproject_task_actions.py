from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.db import SessionLocal
from app.models import OpenProjectConnection
from app.routers import tasks as tasks_router
from app.security import encrypt_secret
from tests.conftest import login


@pytest.mark.anyio
async def test_openproject_task_create_link_pull_sync(client: AsyncClient, monkeypatch) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "OpenProject Task Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "OP source title", "description": "OP source body", "priority": "P2", "type": "Feature"},
    )
  ).json()

  async with SessionLocal() as db:
    conn = OpenProjectConnection(
      name="OP",
      base_url="https://openproject.example.com",
      api_token_encrypted=encrypt_secret("tok"),
      project_identifier="platform",
      enabled=True,
      token_hint="…token",
    )
    db.add(conn)
    await db.flush()
    conn_id = conn.id
    await db.commit()

  async def _fake_create_work_package(**kwargs):
    return {"id": 321, "subject": "OP created", "description": "new", "url": "https://openproject.example.com/work_packages/321"}

  async def _fake_get_work_package(**kwargs):
    wp_id = int(kwargs["work_package_id"])
    return {
      "id": wp_id,
      "subject": f"OP pull {wp_id}",
      "description": "Pulled body",
      "url": f"https://openproject.example.com/work_packages/{wp_id}",
    }

  async def _fake_update_work_package(**kwargs):
    wp_id = int(kwargs["work_package_id"])
    return {
      "id": wp_id,
      "subject": kwargs.get("subject") or "",
      "description": kwargs.get("description") or "",
      "url": f"https://openproject.example.com/work_packages/{wp_id}",
    }

  monkeypatch.setattr(tasks_router, "openproject_create_work_package", _fake_create_work_package)
  monkeypatch.setattr(tasks_router, "openproject_get_work_package", _fake_get_work_package)
  monkeypatch.setattr(tasks_router, "openproject_update_work_package", _fake_update_work_package)

  created = await client.post(
    f"/tasks/{t['id']}/openproject/create",
    json={"connectionId": conn_id, "projectIdentifier": "platform", "enableSync": True},
  )
  assert created.status_code == 200, created.text
  created_task = created.json()
  assert created_task["openprojectWorkPackageId"] == 321
  assert created_task["openprojectConnectionId"] == conn_id
  assert created_task["openprojectSyncEnabled"] is True
  assert created_task["openprojectUrl"].endswith("/work_packages/321")

  pulled = await client.post(f"/tasks/{t['id']}/openproject/pull", json={})
  assert pulled.status_code == 200, pulled.text
  pulled_task = pulled.json()
  assert pulled_task["title"] == "OP pull 321"
  assert pulled_task["description"] == "Pulled body"

  synced = await client.post(f"/tasks/{t['id']}/openproject/sync", json={})
  assert synced.status_code == 200, synced.text
  assert synced.json()["openprojectWorkPackageId"] == 321

  wp = await client.get(f"/tasks/{t['id']}/openproject/work-package")
  assert wp.status_code == 200, wp.text
  assert wp.json()["id"] == 321

  linked = await client.post(
    f"/tasks/{t['id']}/openproject/link",
    json={"connectionId": conn_id, "workPackageId": 444, "enableSync": False},
  )
  assert linked.status_code == 200, linked.text
  linked_task = linked.json()
  assert linked_task["openprojectWorkPackageId"] == 444
  assert linked_task["openprojectSyncEnabled"] is False
  assert linked_task["openprojectUrl"].endswith("/work_packages/444")
