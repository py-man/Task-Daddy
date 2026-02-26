from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.config import settings
from app.db import SessionLocal
from app.models import Attachment, AuditEvent, Board, BoardMember, BoardTaskPriority, BoardTaskType, ChecklistItem, Comment, Lane, Task, TaskDependency
from app.backups.service import purge_old_backups, should_run_scheduled_backup
from tests.conftest import enable_admin_mfa, login


@pytest.mark.anyio
async def test_full_backup_create_list_restore_idempotent(client):
  await login(client, "admin@neonlanes.local", "admin1234")
  await enable_admin_mfa(client)

  b = (await client.post("/boards", json={"name": "Backup Test"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  t = (await client.post(f"/boards/{b['id']}/tasks", json={"laneId": lane_id, "title": "Backup task", "priority": "P2", "type": "Feature", "ownerId": None})).json()

  # Upload an attachment so the backup includes uploads/.
  up = await client.post(f"/tasks/{t['id']}/attachments", files={"file": ("hello.txt", b"hello world", "text/plain")})
  assert up.status_code == 200, up.text

  created = await client.post("/backups/full", json={})
  assert created.status_code == 200, created.text
  filename = created.json()["filename"]
  assert filename.endswith(".tar.gz")

  listed = await client.get("/backups")
  assert listed.status_code == 200, listed.text
  assert any(x["filename"] == filename for x in listed.json())

  # Deleting removes from list and blocks download.
  deleted = await client.delete(f"/backups/{filename}")
  assert deleted.status_code == 200, deleted.text
  assert deleted.json()["deleted"] is True

  listed2 = await client.get("/backups")
  assert listed2.status_code == 200, listed2.text
  assert not any(x["filename"] == filename for x in listed2.json())

  dl_missing = await client.get(f"/backups/{filename}/download")
  assert dl_missing.status_code == 404, dl_missing.text

  # Create again for remaining restore validations.
  created2 = await client.post("/backups/full", json={})
  assert created2.status_code == 200, created2.text
  filename2 = created2.json()["filename"]

  preview = await client.post("/backups/restore", json={"filename": filename2, "mode": "skip_existing", "dryRun": True})
  assert preview.status_code == 200, preview.text
  assert preview.json()["dryRun"] is True
  assert "counts" in preview.json()

  # Wipe board data, then restore; ensure things come back.
  async with SessionLocal() as db:
    await db.execute(delete(AuditEvent))
    await db.execute(delete(Comment))
    await db.execute(delete(ChecklistItem))
    await db.execute(delete(TaskDependency))
    await db.execute(delete(Attachment))
    await db.execute(delete(Task))
    await db.execute(delete(Lane))
    await db.execute(delete(BoardMember))
    await db.execute(delete(BoardTaskType))
    await db.execute(delete(BoardTaskPriority))
    await db.execute(delete(Board))
    await db.commit()

  restored = await client.post("/backups/restore", json={"filename": filename2, "mode": "skip_existing"})
  assert restored.status_code == 200, restored.text
  assert restored.json()["ok"] is True

  boards_after = await client.get("/boards")
  assert boards_after.status_code == 200, boards_after.text
  assert any(x["name"] == "Backup Test" for x in boards_after.json())

  # Restore again should be idempotent (no duplicates, no errors).
  restored2 = await client.post("/backups/restore", json={"filename": filename2, "mode": "skip_existing"})
  assert restored2.status_code == 200, restored2.text

  # Download endpoint returns a gzip stream.
  dl = await client.get(f"/backups/{filename2}/download")
  assert dl.status_code == 200, dl.text
  assert dl.headers.get("content-type", "").startswith("application/gzip")


def test_purge_old_backups_deletes_files(tmp_path: Path):
  old = tmp_path / "neonlanes_backup_20000101_000000_deadbeef.tar.gz"
  keep = tmp_path / "neonlanes_backup_20990101_000000_deadbeef.tar.gz"
  old.write_bytes(b"x")
  keep.write_bytes(b"x")

  # Set mtime: old => 10 days ago, keep => now.
  now = time.time()
  os.utime(old, (now - 10 * 24 * 3600, now - 10 * 24 * 3600))
  os.utime(keep, (now, now))

  prev = settings.backup_dir
  try:
    settings.backup_dir = str(tmp_path)
    res = purge_old_backups(retention_days=5, max_backups=20, max_total_size_mb=512)
    assert res["deletedTotal"] == 1
    assert not old.exists()
    assert keep.exists()
  finally:
    settings.backup_dir = prev


def test_should_run_scheduled_backup_respects_min_interval(tmp_path: Path):
  prev = settings.backup_dir
  try:
    settings.backup_dir = str(tmp_path)
    assert should_run_scheduled_backup(min_interval_minutes=60)[0] is True

    recent = tmp_path / "neonlanes_backup_recent.tar.gz"
    recent.write_bytes(b"x")
    run_now, wait_seconds = should_run_scheduled_backup(min_interval_minutes=60)
    assert run_now is False
    assert wait_seconds > 0
  finally:
    settings.backup_dir = prev


@pytest.mark.anyio
async def test_backup_policy_get_and_patch(client):
  await login(client, "admin@neonlanes.local", "admin1234")
  await enable_admin_mfa(client)

  got = await client.get("/backups/policy")
  assert got.status_code == 200, got.text
  body = got.json()
  assert body["retentionDays"] >= 1
  assert body["maxBackups"] >= 1

  patched = await client.patch(
    "/backups/policy",
    json={"retentionDays": 9, "minIntervalMinutes": 15, "maxBackups": 11, "maxTotalSizeMb": 1024},
  )
  assert patched.status_code == 200, patched.text
  after = patched.json()
  assert after["retentionDays"] == 9
  assert after["minIntervalMinutes"] == 15
  assert after["maxBackups"] == 11
  assert after["maxTotalSizeMb"] == 1024
