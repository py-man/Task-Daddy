from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import InAppNotification, NotificationDestination, TaskReminder
from app.routers import tasks as tasks_router
from app.reminders.service import dispatch_due_reminders_once
from app.security import encrypt_secret

from tests.conftest import login


@pytest.mark.anyio
async def test_task_ics_download(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b = (await client.post("/boards", json={"name": "ICS Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Calendar task", "priority": "P2", "type": "Feature", "dueDate": "2026-02-22"},
    )
  ).json()

  res = await client.get(f"/tasks/{t['id']}/ics")
  assert res.status_code == 200, res.text
  ct = res.headers.get("content-type", "")
  assert "text/calendar" in ct
  body = res.content.decode("utf-8")
  assert "BEGIN:VCALENDAR" in body
  assert "BEGIN:VEVENT" in body
  assert "SUMMARY:Calendar task" in body
  assert "DTSTART;VALUE=DATE:20260222" in body
  assert "DTEND;VALUE=DATE:20260223" in body


@pytest.mark.anyio
async def test_task_ics_email_uses_enabled_smtp_destination(client: AsyncClient, monkeypatch) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b = (await client.post("/boards", json={"name": "ICS Mail Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Calendar mail task", "priority": "P2", "type": "Feature", "dueDate": "2026-02-22"},
    )
  ).json()

  async with SessionLocal() as db:
    d = NotificationDestination(
      provider="smtp",
      name="SMTP",
      enabled=True,
      config_encrypted=encrypt_secret(
        json.dumps(
          {
            "host": "smtp.example.com",
            "port": 587,
            "username": "u",
            "password": "p",
            "from": "neonlanes@example.com",
            "to": "fallback@example.com",
            "starttls": True,
          }
        )
      ),
      token_hint="...ample.com",
    )
    db.add(d)
    await db.commit()

  sent: dict = {}

  async def _fake_send(**kwargs):
    sent.update(kwargs)
    return {"to": kwargs["to_addr"], "host": kwargs["cfg"].get("host")}

  monkeypatch.setattr(tasks_router, "_send_ics_over_smtp", _fake_send)

  res = await client.post(f"/tasks/{t['id']}/ics/email", json={})
  assert res.status_code == 200, res.text
  out = res.json()
  assert out["ok"] is True
  assert out["to"] == "fallback@example.com"
  assert out["provider"] == "smtp"
  assert out["filename"].endswith(".ics")
  assert sent.get("to_addr") == "fallback@example.com"
  assert b"BEGIN:VCALENDAR" in sent.get("ics_bytes", b"")

  res2 = await client.post(f"/tasks/{t['id']}/ics/email", json={"to": "override@example.com", "note": "please accept"})
  assert res2.status_code == 200, res2.text
  assert res2.json()["to"] == "override@example.com"


@pytest.mark.anyio
async def test_task_reminders_create_list_cancel_and_dispatch(client: AsyncClient) -> None:
  await login(client, "admin@neonlanes.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Reminder Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]

  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Reminder task", "priority": "P2", "type": "Feature"},
    )
  ).json()

  # Create a due reminder for the current user ("me").
  scheduled_at = "2026-02-22T10:00:00Z"
  created = await client.post(
    f"/tasks/{t['id']}/reminders",
    json={"scheduledAt": scheduled_at, "recipient": "me", "channels": ["inapp"], "note": "Follow up"},
  )
  assert created.status_code == 200, created.text
  rid = created.json()["id"]

  listed = await client.get(f"/tasks/{t['id']}/reminders")
  assert listed.status_code == 200, listed.text
  assert any(r["id"] == rid for r in listed.json())

  # Cancel then verify it won't dispatch.
  canceled = await client.delete(f"/reminders/{rid}")
  assert canceled.status_code == 200, canceled.text

  async with SessionLocal() as db:
    now = datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc)
    sent = await dispatch_due_reminders_once(db, now=now)
    assert sent == 0

  # Create a new reminder and dispatch it once.
  created2 = await client.post(
    f"/tasks/{t['id']}/reminders",
    json={"scheduledAt": scheduled_at, "recipient": "me", "channels": ["inapp"], "note": "Ping"},
  )
  assert created2.status_code == 200, created2.text
  rid2 = created2.json()["id"]

  async with SessionLocal() as db:
    now = datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc)
    sent = await dispatch_due_reminders_once(db, now=now)
    assert sent == 1
    # Calling it again should be idempotent (no re-send).
    sent2 = await dispatch_due_reminders_once(db, now=now)
    assert sent2 == 0

    r = await db.get(TaskReminder, rid2)
    assert r is not None
    assert r.status == "sent"
    assert r.sent_at is not None

    # In-app notification created (deduped).
    notif = (
      await db.execute(select(InAppNotification).where(InAppNotification.dedupe_key == f"reminder.due:{rid2}"))
    ).scalar_one_or_none()
    assert notif is not None
    n = (await db.execute(select(func.count()).select_from(InAppNotification))).scalar_one()
    assert n >= 1
