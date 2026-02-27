from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import InAppNotification, NotificationDestination, TaskReminder
from app.routers import tasks as tasks_router
from app.reminders import service as reminder_service
from app.reminders.service import dispatch_due_reminders_once
from app.security import encrypt_secret

from tests.conftest import login


@pytest.mark.anyio
async def test_task_ics_download(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

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
  await login(client, "admin@taskdaddy.local", "admin1234")

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
  await login(client, "admin@taskdaddy.local", "admin1234")

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


@pytest.mark.anyio
async def test_task_reminder_rejects_naive_datetime(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": "Reminder TZ Validation Board"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Reminder naive datetime", "priority": "P2", "type": "Feature"},
    )
  ).json()

  created = await client.post(
    f"/tasks/{t['id']}/reminders",
    json={"scheduledAt": "2026-02-22T10:00:00", "recipient": "me", "channels": ["inapp"], "note": "naive"},
  )
  assert created.status_code == 422, created.text
  assert "timezone" in created.text.lower()


@pytest.mark.anyio
async def test_task_reminder_external_failure_sets_error_and_retries(client: AsyncClient, monkeypatch) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  board_name = f"Reminder External Fail Board {secrets.token_hex(4)}"
  b_res = await client.post("/boards", json={"name": board_name})
  assert b_res.status_code == 200, b_res.text
  b = b_res.json()
  lanes_res = await client.get(f"/boards/{b['id']}/lanes")
  assert lanes_res.status_code == 200, lanes_res.text
  lane_id = lanes_res.json()[0]["id"]
  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={"laneId": lane_id, "title": "Reminder external fail", "priority": "P2", "type": "Feature"},
    )
  ).json()

  created = await client.post(
    f"/tasks/{t['id']}/reminders",
    json={"scheduledAt": "2026-02-22T10:00:00Z", "recipient": "me", "channels": ["inapp", "external"], "note": "retry me"},
  )
  assert created.status_code == 200, created.text
  rid = created.json()["id"]

  async def _fake_materialized(_db):
    return [{"id": "dest-1", "provider": "smtp", "name": "smtp", "config": {}}]

  async def _fake_dispatch(_dests, *, msg):
    assert "reminder" in msg.title.lower()
    return [{"provider": "smtp", "status": "error", "detail": {"error": "smtp failed"}}]

  monkeypatch.setattr(reminder_service, "materialize_enabled_destinations", _fake_materialized)
  monkeypatch.setattr(reminder_service, "dispatch_to_materialized", _fake_dispatch)

  async with SessionLocal() as db:
    now = datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc)
    sent = await dispatch_due_reminders_once(db, now=now)
    assert sent == 0
    r = await db.get(TaskReminder, rid)
    assert r is not None
    assert r.status == "error"
    assert r.sent_at is None
    assert "smtp failed" in str(r.last_error or "")

  async def _fake_dispatch_ok(_dests, *, msg):
    return [{"provider": "smtp", "status": "sent", "detail": {"ok": True}}]

  monkeypatch.setattr(reminder_service, "dispatch_to_materialized", _fake_dispatch_ok)
  async with SessionLocal() as db:
    now = datetime(2026, 2, 22, 12, 1, 0, tzinfo=timezone.utc)
    sent = await dispatch_due_reminders_once(db, now=now)
    assert sent == 1
    r = await db.get(TaskReminder, rid)
    assert r is not None
    assert r.status == "sent"
    assert r.sent_at is not None
    assert r.last_error in (None, "")
