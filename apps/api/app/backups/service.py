from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
  Attachment,
  AuditEvent,
  Board,
  BoardMember,
  BackupPolicy,
  ChecklistItem,
  Comment,
  JiraConnection,
  JiraSyncProfile,
  Lane,
  NotificationDestination,
  SyncRun,
  Task,
  TaskDependency,
  User,
  WebhookSecret,
)


@dataclass
class BackupInfo:
  filename: str
  sizeBytes: int
  createdAt: str


@dataclass
class BackupPolicyInfo:
  retentionDays: int
  minIntervalMinutes: int
  maxBackups: int
  maxTotalSizeMb: int


def _now_utc() -> datetime:
  return datetime.now(timezone.utc).replace(microsecond=0)


def _ensure_backup_dir() -> Path:
  out = Path(settings.backup_dir)
  out.mkdir(parents=True, exist_ok=True)
  return out


def _uploads_dir() -> Path:
  # Matches docker-compose volume mount.
  return Path("data/uploads")


def _csv_bytes(rows: list[list[str]]) -> bytes:
  buf = io.StringIO(newline="")
  w = csv.writer(buf, lineterminator="\r\n")
  for r in rows:
    w.writerow(r)
  return buf.getvalue().encode("utf-8-sig")


def _safe_write_member(tar: tarfile.TarFile, arcname: str, data: bytes) -> None:
  info = tarfile.TarInfo(name=arcname)
  info.size = len(data)
  info.mtime = int(_now_utc().timestamp())
  tar.addfile(info, io.BytesIO(data))


async def _snapshot(db: AsyncSession) -> dict[str, Any]:
  # Snapshot is intentionally "safe": no passwords, no secrets, no encrypted tokens.
  users_res = await db.execute(select(User))
  users = []
  for u in users_res.scalars().all():
    users.append(
      {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "avatarUrl": u.avatar_url,
        "timezone": u.timezone,
        "jiraAccountId": u.jira_account_id,
        "active": bool(u.active),
        "loginDisabled": bool(getattr(u, "login_disabled", False)),
        "mfaEnabled": bool(u.mfa_enabled),
        "createdAt": u.created_at.isoformat(),
        "updatedAt": u.updated_at.isoformat(),
      }
    )

  boards_res = await db.execute(select(Board))
  boards = [
    {
      "id": b.id,
      "name": b.name,
      "nameKey": b.name_key,
      "ownerId": b.owner_id,
      "createdAt": b.created_at.isoformat(),
      "updatedAt": b.updated_at.isoformat(),
    }
    for b in boards_res.scalars().all()
  ]

  members_res = await db.execute(select(BoardMember))
  members = [
    {"id": m.id, "boardId": m.board_id, "userId": m.user_id, "role": m.role, "createdAt": m.created_at.isoformat()}
    for m in members_res.scalars().all()
  ]

  lanes_res = await db.execute(select(Lane))
  lanes = []
  for l in lanes_res.scalars().all():
    lanes.append(
      {
        "id": l.id,
        "boardId": l.board_id,
        "name": l.name,
        "stateKey": l.state_key,
        "type": l.type,
        "wipLimit": l.wip_limit,
        "position": l.position,
        "createdAt": l.created_at.isoformat(),
        "updatedAt": l.updated_at.isoformat(),
      }
    )

  tasks_res = await db.execute(select(Task))
  tasks = []
  for t in tasks_res.scalars().all():
    tasks.append(
      {
        "id": t.id,
        "boardId": t.board_id,
        "laneId": t.lane_id,
        "stateKey": t.state_key,
        "title": t.title,
        "description": t.description,
        "ownerId": t.owner_id,
        "priority": t.priority,
        "type": t.type,
        "tags": list(t.tags or []),
        "dueDate": t.due_date.isoformat() if t.due_date else None,
        "estimateMinutes": t.estimate_minutes,
        "blocked": bool(t.blocked),
        "blockedReason": t.blocked_reason,
        "orderIndex": t.order_index,
        "version": t.version,
        "jiraKey": t.jira_key,
        "jiraUrl": t.jira_url,
        "jiraSyncEnabled": bool(getattr(t, "jira_sync_enabled", False)),
        "jiraConnectionId": getattr(t, "jira_connection_id", None),
        "jiraProjectKey": getattr(t, "jira_project_key", None),
        "jiraIssueType": getattr(t, "jira_issue_type", None),
        "jiraUpdatedAt": t.jira_updated_at.isoformat() if t.jira_updated_at else None,
        "jiraLastSyncAt": t.jira_last_sync_at.isoformat() if t.jira_last_sync_at else None,
        "createdAt": t.created_at.isoformat(),
        "updatedAt": t.updated_at.isoformat(),
      }
    )

  comments_res = await db.execute(select(Comment))
  comments = []
  for c in comments_res.scalars().all():
    comments.append(
      {
        "id": c.id,
        "taskId": c.task_id,
        "authorId": c.author_id,
        "body": c.body,
        "source": c.source,
        "sourceId": c.source_id,
        "sourceAuthor": c.source_author,
        "sourceUrl": c.source_url,
        "jiraCommentId": c.jira_comment_id,
        "jiraExportedAt": c.jira_exported_at.isoformat() if c.jira_exported_at else None,
        "createdAt": c.created_at.isoformat(),
      }
    )

  checklist_res = await db.execute(select(ChecklistItem))
  checklist = [
    {
      "id": i.id,
      "taskId": i.task_id,
      "text": i.text,
      "done": bool(i.done),
      "position": i.position,
      "createdAt": i.created_at.isoformat(),
    }
    for i in checklist_res.scalars().all()
  ]

  deps_res = await db.execute(select(TaskDependency))
  deps = [
    {"id": d.id, "taskId": d.task_id, "dependsOnTaskId": d.depends_on_task_id, "createdAt": d.created_at.isoformat()}
    for d in deps_res.scalars().all()
  ]

  attachments_res = await db.execute(select(Attachment))
  attachments = []
  for a in attachments_res.scalars().all():
    attachments.append(
      {
        "id": a.id,
        "taskId": a.task_id,
        "filename": a.filename,
        "mime": a.mime,
        "sizeBytes": a.size_bytes,
        "path": a.path,
        "createdAt": a.created_at.isoformat(),
      }
    )

  audit_res = await db.execute(select(AuditEvent))
  audit = []
  for e in audit_res.scalars().all():
    audit.append(
      {
        "id": e.id,
        "boardId": e.board_id,
        "taskId": e.task_id,
        "actorId": e.actor_id,
        "eventType": e.event_type,
        "entityType": e.entity_type,
        "entityId": e.entity_id,
        "payload": e.payload,
        "createdAt": e.created_at.isoformat(),
      }
    )

  jira_connections_res = await db.execute(select(JiraConnection))
  jira_connections = []
  for jc in jira_connections_res.scalars().all():
    jira_connections.append(
      {
        "id": jc.id,
        "name": jc.name,
        "baseUrl": jc.base_url,
        "email": jc.email,
        "defaultAssigneeAccountId": jc.default_assignee_account_id,
        "createdAt": jc.created_at.isoformat(),
        "updatedAt": jc.updated_at.isoformat(),
      }
    )

  jira_profiles_res = await db.execute(select(JiraSyncProfile))
  jira_profiles = []
  for p in jira_profiles_res.scalars().all():
    jira_profiles.append(
      {
        "id": p.id,
        "boardId": p.board_id,
        "connectionId": p.connection_id,
        "jql": p.jql,
        "statusToStateKey": p.status_to_state_key,
        "priorityMap": p.priority_map,
        "typeMap": p.type_map,
        "conflictPolicy": p.conflict_policy,
        "createdAt": p.created_at.isoformat(),
        "updatedAt": p.updated_at.isoformat(),
      }
    )

  sync_runs_res = await db.execute(select(SyncRun))
  sync_runs = []
  for r in sync_runs_res.scalars().all():
    sync_runs.append(
      {
        "id": r.id,
        "boardId": r.board_id,
        "profileId": r.profile_id,
        "status": r.status,
        "startedAt": r.started_at.isoformat(),
        "finishedAt": r.finished_at.isoformat() if r.finished_at else None,
        "log": r.log,
        "errorMessage": r.error_message,
      }
    )

  webhook_secrets_res = await db.execute(select(WebhookSecret))
  webhook_sources = [{"id": w.id, "source": w.source, "enabled": bool(w.enabled)} for w in webhook_secrets_res.scalars().all()]

  notif_res = await db.execute(select(NotificationDestination))
  notifs = []
  for d in notif_res.scalars().all():
    notifs.append(
      {
        "id": d.id,
        "name": d.name,
        "provider": d.provider,
        "enabled": bool(d.enabled),
        "createdAt": d.created_at.isoformat(),
        "updatedAt": d.updated_at.isoformat(),
      }
    )

  return {
    "meta": {
      "appVersion": settings.app_version,
      "buildSha": settings.build_sha,
      "createdAt": _now_utc().isoformat().replace("+00:00", "Z"),
    },
    "users": users,
    "boards": boards,
    "boardMembers": members,
    "lanes": lanes,
    "tasks": tasks,
    "comments": comments,
    "checklistItems": checklist,
    "taskDependencies": deps,
    "attachments": attachments,
    "auditEvents": audit,
    "jiraConnections": jira_connections,
    "jiraSyncProfiles": jira_profiles,
    "syncRuns": sync_runs,
    "webhookSources": webhook_sources,
    "notificationDestinations": notifs,
  }


async def create_full_backup(db: AsyncSession) -> BackupInfo:
  backup_dir = _ensure_backup_dir()
  created = _now_utc()
  filename = f"neonlanes_backup_{created.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.tar.gz"
  out_path = backup_dir / filename

  snap = await _snapshot(db)

  # CSV exports (Excel-friendly, RFC4180, UTF-8 BOM, CRLF)
  exports: dict[str, bytes] = {}
  exports["exports/users.csv"] = _csv_bytes(
    [["id", "email", "name", "role", "timezone", "avatarUrl", "jiraAccountId", "active", "loginDisabled", "mfaEnabled"]]
    + [
      [
        u["id"],
        u["email"],
        u["name"],
        u["role"],
        u.get("timezone") or "",
        u.get("avatarUrl") or "",
        u.get("jiraAccountId") or "",
        "true" if u.get("active") else "false",
        "true" if u.get("loginDisabled") else "false",
        "true" if u.get("mfaEnabled") else "false",
      ]
      for u in snap["users"]
    ]
  )
  exports["exports/boards.csv"] = _csv_bytes([["id", "name", "nameKey", "ownerId"]] + [[b["id"], b["name"], b["nameKey"], b["ownerId"]] for b in snap["boards"]])
  exports["exports/board_members.csv"] = _csv_bytes(
    [["id", "boardId", "userId", "role", "createdAt"]] + [[m["id"], m["boardId"], m["userId"], m["role"], m["createdAt"]] for m in snap["boardMembers"]]
  )
  exports["exports/lanes.csv"] = _csv_bytes(
    [["id", "boardId", "name", "stateKey", "type", "wipLimit", "position"]]
    + [[l["id"], l["boardId"], l["name"], l["stateKey"], l["type"], str(l.get("wipLimit") or ""), str(l["position"])] for l in snap["lanes"]]
  )
  exports["exports/tasks.csv"] = _csv_bytes(
    [["id", "boardId", "laneId", "stateKey", "title", "description", "ownerId", "priority", "type", "tags", "dueDate", "estimateMinutes", "blocked", "blockedReason", "orderIndex", "version", "jiraKey", "jiraUrl", "jiraSyncEnabled", "jiraConnectionId", "jiraProjectKey", "jiraIssueType", "jiraUpdatedAt", "jiraLastSyncAt"]]
    + [
      [
        t["id"],
        t["boardId"],
        t["laneId"],
        t["stateKey"],
        t["title"],
        t.get("description") or "",
        t.get("ownerId") or "",
        t["priority"],
        t["type"],
        ",".join(t.get("tags") or []),
        t.get("dueDate") or "",
        str(t.get("estimateMinutes") or ""),
        "true" if t.get("blocked") else "false",
        t.get("blockedReason") or "",
        str(t.get("orderIndex") or 0),
        str(t.get("version") or 0),
        t.get("jiraKey") or "",
        t.get("jiraUrl") or "",
        "true" if t.get("jiraSyncEnabled") else "false",
        t.get("jiraConnectionId") or "",
        t.get("jiraProjectKey") or "",
        t.get("jiraIssueType") or "",
        t.get("jiraUpdatedAt") or "",
        t.get("jiraLastSyncAt") or "",
      ]
      for t in snap["tasks"]
    ]
  )
  exports["exports/comments.csv"] = _csv_bytes(
    [["id", "taskId", "authorId", "body", "source", "sourceId", "sourceAuthor", "sourceUrl", "jiraCommentId", "createdAt"]]
    + [
      [
        c["id"],
        c["taskId"],
        c["authorId"],
        c["body"],
        c.get("source") or "app",
        c.get("sourceId") or "",
        c.get("sourceAuthor") or "",
        c.get("sourceUrl") or "",
        c.get("jiraCommentId") or "",
        c.get("createdAt") or "",
      ]
      for c in snap["comments"]
    ]
  )
  exports["exports/checklist_items.csv"] = _csv_bytes(
    [["id", "taskId", "text", "done", "position", "createdAt"]]
    + [[i["id"], i["taskId"], i["text"], "true" if i["done"] else "false", str(i["position"]), i["createdAt"]] for i in snap["checklistItems"]]
  )
  exports["exports/task_dependencies.csv"] = _csv_bytes(
    [["id", "taskId", "dependsOnTaskId", "createdAt"]]
    + [[d["id"], d["taskId"], d["dependsOnTaskId"], d["createdAt"]] for d in snap["taskDependencies"]]
  )
  exports["exports/attachments.csv"] = _csv_bytes(
    [["id", "taskId", "filename", "mime", "sizeBytes", "path", "createdAt"]]
    + [[a["id"], a["taskId"], a["filename"], a["mime"], str(a["sizeBytes"]), a["path"], a["createdAt"]] for a in snap["attachments"]]
  )
  exports["exports/audit_events.csv"] = _csv_bytes(
    [["id", "boardId", "taskId", "actorId", "eventType", "entityType", "entityId", "payloadJson", "createdAt"]]
    + [
      [
        e["id"],
        e.get("boardId") or "",
        e.get("taskId") or "",
        e.get("actorId") or "",
        e["eventType"],
        e["entityType"],
        e.get("entityId") or "",
        json.dumps(e.get("payload") or {}, ensure_ascii=False),
        e["createdAt"],
      ]
      for e in snap["auditEvents"]
    ]
  )
  exports["exports/jira_connections.csv"] = _csv_bytes(
    [["id", "name", "baseUrl", "email", "defaultAssigneeAccountId", "createdAt", "updatedAt"]]
    + [[c["id"], c.get("name") or "", c["baseUrl"], c.get("email") or "", c.get("defaultAssigneeAccountId") or "", c["createdAt"], c["updatedAt"]] for c in snap["jiraConnections"]]
  )
  exports["exports/jira_sync_profiles.csv"] = _csv_bytes(
    [["id", "boardId", "connectionId", "jql", "statusToStateKeyJson", "priorityMapJson", "typeMapJson", "conflictPolicy", "createdAt", "updatedAt"]]
    + [
      [
        p["id"],
        p["boardId"],
        p["connectionId"],
        p["jql"],
        json.dumps(p.get("statusToStateKey") or {}, ensure_ascii=False),
        json.dumps(p.get("priorityMap") or {}, ensure_ascii=False),
        json.dumps(p.get("typeMap") or {}, ensure_ascii=False),
        p.get("conflictPolicy") or "jiraWins",
        p["createdAt"],
        p["updatedAt"],
      ]
      for p in snap["jiraSyncProfiles"]
    ]
  )
  exports["exports/sync_runs.csv"] = _csv_bytes(
    [["id", "boardId", "profileId", "status", "startedAt", "finishedAt", "errorMessage", "logJson"]]
    + [
      [
        r["id"],
        r["boardId"],
        r["profileId"],
        r.get("status") or "",
        r.get("startedAt") or "",
        r.get("finishedAt") or "",
        r.get("errorMessage") or "",
        json.dumps(r.get("log") or [], ensure_ascii=False),
      ]
      for r in snap["syncRuns"]
    ]
  )
  exports["exports/notification_destinations.csv"] = _csv_bytes(
    [["id", "name", "provider", "enabled", "createdAt", "updatedAt"]]
    + [[n["id"], n["name"], n["provider"], "true" if n["enabled"] else "false", n["createdAt"], n["updatedAt"]] for n in snap["notificationDestinations"]]
  )
  exports["exports/webhook_sources.csv"] = _csv_bytes([["id", "source", "enabled"]] + [[w["id"], w["source"], "true" if w["enabled"] else "false"] for w in snap["webhookSources"]])

  meta = {
    "createdAt": created.isoformat().replace("+00:00", "Z"),
    "filename": filename,
    "appVersion": settings.app_version,
    "buildSha": settings.build_sha,
  }

  uploads_dir = _uploads_dir()
  uploads_dir.mkdir(parents=True, exist_ok=True)

  with tarfile.open(out_path, mode="w:gz") as tar:
    _safe_write_member(tar, "metadata.json", json.dumps(meta, indent=2).encode("utf-8"))
    _safe_write_member(tar, "snapshot.json", json.dumps(snap, ensure_ascii=False, indent=2).encode("utf-8"))
    for path, data in exports.items():
      _safe_write_member(tar, path, data)
    # Attachments
    for f in uploads_dir.glob("*"):
      if not f.is_file():
        continue
      tar.add(f, arcname=f"uploads/{f.name}")

  st = out_path.stat()
  return BackupInfo(filename=filename, sizeBytes=st.st_size, createdAt=created.isoformat().replace("+00:00", "Z"))


def _parse_db_url_parts() -> tuple[str, int, str, str | None, str]:
  raw = str(settings.database_url or "").strip()
  # Supports e.g. postgresql+asyncpg://user:pass@db:5432/neonlanes
  normalized = raw.replace("postgresql+asyncpg://", "postgresql://", 1)
  p = urlparse(normalized)
  if p.scheme not in ("postgresql", "postgres"):
    raise ValueError("Unsupported database URL for pg_dump")
  host = p.hostname or "db"
  port = int(p.port or 5432)
  user = unquote(p.username or "")
  password = unquote(p.password) if p.password else None
  dbname = (p.path or "").lstrip("/")
  if not user or not dbname:
    raise ValueError("Invalid database URL for pg_dump")
  return host, port, user, password, dbname


async def create_machine_recovery_export(db: AsyncSession) -> BackupInfo:
  backup_dir = _ensure_backup_dir()
  created = _now_utc()
  export_name = f"neonlanes_full_export_{created.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.tar.gz"
  export_path = backup_dir / export_name

  # Build the existing logical+attachments backup first.
  app_backup = await create_full_backup(db)
  app_backup_path = backup_dir / app_backup.filename

  host, port, user, password, dbname = _parse_db_url_parts()

  with tempfile.TemporaryDirectory(prefix="neonlanes_full_export_") as td:
    td_path = Path(td)
    pg_dump_path = td_path / "pg_dump.custom"
    meta_path = td_path / "metadata.json"

    env = os.environ.copy()
    if password:
      env["PGPASSWORD"] = password
    cmd = [
      "pg_dump",
      "-h",
      host,
      "-p",
      str(port),
      "-U",
      user,
      "-d",
      dbname,
      "-Fc",
      "-f",
      str(pg_dump_path),
    ]

    def _run_dump() -> None:
      subprocess.run(cmd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    await asyncio.to_thread(_run_dump)

    meta = {
      "createdAt": created.isoformat().replace("+00:00", "Z"),
      "type": "machine-recovery-export",
      "appVersion": settings.app_version,
      "buildSha": settings.build_sha,
      "db": {"host": host, "port": port, "database": dbname, "user": user, "format": "pg_dump custom"},
      "contains": ["app backup tar.gz", "postgres pg_dump custom"],
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    with tarfile.open(export_path, mode="w:gz") as tar:
      tar.add(app_backup_path, arcname=f"app/{app_backup_path.name}")
      tar.add(pg_dump_path, arcname="postgres/pg_dump.custom")
      tar.add(meta_path, arcname="metadata.json")

  st = export_path.stat()
  return BackupInfo(filename=export_name, sizeBytes=st.st_size, createdAt=created.isoformat().replace("+00:00", "Z"))


def list_backups() -> list[BackupInfo]:
  backup_dir = _ensure_backup_dir()
  out: list[BackupInfo] = []
  archives = []
  archives.extend(backup_dir.glob("neonlanes_backup_*.tar.gz"))
  archives.extend(backup_dir.glob("neonlanes_full_export_*.tar.gz"))
  for p in sorted(archives, key=lambda x: x.stat().st_mtime, reverse=True):
    st = p.stat()
    created = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    out.append(BackupInfo(filename=p.name, sizeBytes=st.st_size, createdAt=created))
  return out


def _policy_from_settings() -> BackupPolicyInfo:
  return BackupPolicyInfo(
    retentionDays=max(1, int(settings.backup_retention_days)),
    minIntervalMinutes=max(0, int(settings.backup_min_interval_minutes)),
    maxBackups=max(1, int(settings.backup_max_count)),
    maxTotalSizeMb=max(1, int(settings.backup_max_total_size_mb)),
  )


def _normalize_policy_payload(payload: dict[str, Any], current: BackupPolicyInfo) -> BackupPolicyInfo:
  def _value(keys: list[str], fallback: int) -> int:
    for key in keys:
      if key in payload and payload[key] is not None:
        return int(payload[key])
    return fallback

  return BackupPolicyInfo(
    retentionDays=max(1, _value(["retentionDays", "retention_days"], current.retentionDays)),
    minIntervalMinutes=max(0, _value(["minIntervalMinutes", "min_interval_minutes"], current.minIntervalMinutes)),
    maxBackups=max(1, _value(["maxBackups", "max_backups"], current.maxBackups)),
    maxTotalSizeMb=max(1, _value(["maxTotalSizeMb", "max_total_size_mb"], current.maxTotalSizeMb)),
  )


async def get_backup_policy(db: AsyncSession) -> BackupPolicyInfo:
  current = _policy_from_settings()
  res = await db.execute(select(BackupPolicy).limit(1))
  row = res.scalar_one_or_none()
  if row is None:
    return current
  return BackupPolicyInfo(
    retentionDays=max(1, int(row.retention_days)),
    minIntervalMinutes=max(0, int(row.min_interval_minutes)),
    maxBackups=max(1, int(row.max_backups)),
    maxTotalSizeMb=max(1, int(row.max_total_size_mb)),
  )


async def update_backup_policy(db: AsyncSession, payload: dict[str, Any]) -> BackupPolicyInfo:
  current = await get_backup_policy(db)
  nxt = _normalize_policy_payload(payload, current)
  res = await db.execute(select(BackupPolicy).limit(1))
  row = res.scalar_one_or_none()
  if row is None:
    row = BackupPolicy(
      retention_days=nxt.retentionDays,
      min_interval_minutes=nxt.minIntervalMinutes,
      max_backups=nxt.maxBackups,
      max_total_size_mb=nxt.maxTotalSizeMb,
    )
    db.add(row)
  else:
    row.retention_days = nxt.retentionDays
    row.min_interval_minutes = nxt.minIntervalMinutes
    row.max_backups = nxt.maxBackups
    row.max_total_size_mb = nxt.maxTotalSizeMb
  await db.commit()
  return nxt


def _all_backup_archives() -> list[Path]:
  backup_dir = _ensure_backup_dir()
  out: list[Path] = []
  for p in backup_dir.glob("*.tar.gz"):
    if not p.is_file():
      continue
    try:
      _ = p.stat()
      out.append(p)
    except FileNotFoundError:
      continue
  return sorted(out, key=lambda x: x.stat().st_mtime, reverse=True)


def should_run_scheduled_backup(*, min_interval_minutes: int) -> tuple[bool, int]:
  if min_interval_minutes <= 0:
    return (True, 0)
  archives = _all_backup_archives()
  if not archives:
    return (True, 0)
  newest = archives[0]
  age_seconds = int(datetime.now(tz=timezone.utc).timestamp() - newest.stat().st_mtime)
  required = int(min_interval_minutes * 60)
  if age_seconds >= required:
    return (True, 0)
  return (False, max(0, required - age_seconds))


def purge_old_backups(*, retention_days: int, max_backups: int, max_total_size_mb: int) -> dict[str, int]:
  archives = _all_backup_archives()
  if not archives:
    return {"deletedByAge": 0, "deletedByCount": 0, "deletedBySize": 0, "deletedTotal": 0}

  deleted_age = 0
  deleted_count = 0
  deleted_size = 0

  if retention_days > 0:
    cutoff = datetime.now(tz=timezone.utc).timestamp() - retention_days * 24 * 3600
    for p in list(archives):
      try:
        if p.stat().st_mtime < cutoff:
          p.unlink(missing_ok=True)
          archives.remove(p)
          deleted_age += 1
      except FileNotFoundError:
        if p in archives:
          archives.remove(p)

  if max_backups > 0 and len(archives) > max_backups:
    to_delete = archives[max_backups:]
    for p in to_delete:
      try:
        p.unlink(missing_ok=True)
        deleted_count += 1
      except FileNotFoundError:
        pass
    archives = archives[:max_backups]

  if max_total_size_mb > 0:
    max_bytes = int(max_total_size_mb) * 1024 * 1024
    total_bytes = 0
    sizes: dict[Path, int] = {}
    for p in archives:
      try:
        st_size = p.stat().st_size
      except FileNotFoundError:
        st_size = 0
      sizes[p] = st_size
      total_bytes += st_size
    while archives and total_bytes > max_bytes:
      oldest = archives[-1]
      removed = sizes.get(oldest, 0)
      try:
        oldest.unlink(missing_ok=True)
        deleted_size += 1
      except FileNotFoundError:
        pass
      archives.pop()
      total_bytes = max(0, total_bytes - removed)

  deleted_total = deleted_age + deleted_count + deleted_size
  return {"deletedByAge": deleted_age, "deletedByCount": deleted_count, "deletedBySize": deleted_size, "deletedTotal": deleted_total}


def delete_backup(filename: str) -> dict[str, bool]:
  name = str(filename or "").strip()
  if not name:
    raise ValueError("Invalid filename")
  if "/" in name or "\\" in name or ".." in name:
    raise ValueError("Invalid filename")
  backup_dir = _ensure_backup_dir()
  p = backup_dir / name
  if not p.exists():
    return {"deleted": False}
  p.unlink()
  return {"deleted": True}


def _safe_extract_tar(tar_path: Path, dest_dir: Path) -> None:
  dest_dir.mkdir(parents=True, exist_ok=True)
  with tarfile.open(tar_path, mode="r:gz") as tar:
    for member in tar.getmembers():
      name = member.name
      if name.startswith("/") or ".." in Path(name).parts:
        raise ValueError("Invalid archive entry")
    tar.extractall(path=dest_dir)


async def restore_full_backup(db: AsyncSession, *, filename: str, mode: str, dry_run: bool) -> dict[str, Any]:
  if mode not in ("skip_existing", "overwrite", "merge_non_conflicting"):
    raise ValueError("Invalid restore mode")
  if "/" in filename or "\\" in filename or ".." in filename:
    raise ValueError("Invalid filename")
  backup_dir = _ensure_backup_dir()
  tar_path = backup_dir / filename
  if not tar_path.exists():
    raise FileNotFoundError("Backup not found")

  with tempfile.TemporaryDirectory(prefix="neonlanes_restore_") as td:
    td_path = Path(td)
    _safe_extract_tar(tar_path, td_path)
    snap_path = td_path / "snapshot.json"
    if not snap_path.exists():
      raise ValueError("Missing snapshot.json")
    snap = json.loads(snap_path.read_text(encoding="utf-8"))

    counts = {k: len(snap.get(k) or []) for k in ("users", "boards", "lanes", "tasks", "comments", "attachments", "auditEvents")}
    if dry_run:
      return {"ok": True, "dryRun": True, "counts": counts}

    # Build id maps for idempotency.
    user_id_map: dict[str, str] = {}
    board_id_map: dict[str, str] = {}
    lane_id_map: dict[str, str] = {}
    task_id_map: dict[str, str] = {}

    # Users: match by id, else by email
    existing_users = {}
    res = await db.execute(select(User))
    for u in res.scalars().all():
      existing_users[u.id] = u
    email_to_user = {u.email.lower(): u for u in existing_users.values()}

    for u in snap.get("users") or []:
      uid = str(u["id"])
      email = str(u["email"]).strip().lower()
      if uid in existing_users:
        user_id_map[uid] = uid
        if mode == "overwrite":
          existing = existing_users[uid]
          existing.email = email
          existing.name = str(u.get("name") or existing.name)
          existing.role = str(u.get("role") or existing.role)
          existing.avatar_url = u.get("avatarUrl")
          existing.timezone = u.get("timezone")
          existing.jira_account_id = u.get("jiraAccountId")
          existing.active = bool(u.get("active", True))
          existing.login_disabled = bool(u.get("loginDisabled", False))
        continue
      if email and email in email_to_user:
        user_id_map[uid] = email_to_user[email].id
        continue
      # Create user with a random password; secrets are never restored.
      from app.security import hash_password

      temp_pw = uuid.uuid4().hex
      nu = User(
        id=uid,
        email=email,
        name=str(u.get("name") or email),
        password_hash=hash_password(temp_pw),
        role=str(u.get("role") or "member"),
        avatar_url=u.get("avatarUrl"),
        timezone=u.get("timezone"),
        jira_account_id=u.get("jiraAccountId"),
        active=bool(u.get("active", True)),
        login_disabled=bool(u.get("loginDisabled", False)),
        mfa_enabled=False,
        mfa_secret_encrypted=None,
        mfa_recovery_codes_encrypted=None,
      )
      db.add(nu)
      user_id_map[uid] = uid

    # Boards: match by id, else by nameKey
    res = await db.execute(select(Board))
    existing_boards = {b.id: b for b in res.scalars().all()}
    namekey_to_board = {b.name_key: b for b in existing_boards.values()}
    for b in snap.get("boards") or []:
      bid = str(b["id"])
      name_key = str(b.get("nameKey") or "")
      if bid in existing_boards:
        board_id_map[bid] = bid
        if mode == "overwrite":
          eb = existing_boards[bid]
          eb.name = str(b.get("name") or eb.name)
          eb.name_key = name_key or eb.name_key
          eb.owner_id = user_id_map.get(str(b.get("ownerId")), eb.owner_id)
        continue
      if name_key and name_key in namekey_to_board:
        board_id_map[bid] = namekey_to_board[name_key].id
        continue
      owner_id = user_id_map.get(str(b.get("ownerId"))) or next(iter(user_id_map.values()), None)
      if not owner_id:
        raise ValueError("Cannot restore boards without at least one user")
      nb = Board(id=bid, name=str(b["name"]), name_key=name_key or str(b["name"]).strip().lower(), owner_id=owner_id)
      db.add(nb)
      board_id_map[bid] = bid

    # Board members: insert if not exists
    res = await db.execute(select(BoardMember))
    existing_members = {(m.board_id, m.user_id): m for m in res.scalars().all()}
    for m in snap.get("boardMembers") or []:
      board_id = board_id_map.get(str(m["boardId"])) or str(m["boardId"])
      user_id = user_id_map.get(str(m["userId"])) or str(m["userId"])
      key = (board_id, user_id)
      if key in existing_members:
        if mode == "overwrite":
          existing_members[key].role = str(m.get("role") or existing_members[key].role)
        continue
      db.add(BoardMember(id=str(m["id"]), board_id=board_id, user_id=user_id, role=str(m.get("role") or "viewer")))

    # Lanes: match by id, else by (boardId,stateKey)
    res = await db.execute(select(Lane))
    existing_lanes = {l.id: l for l in res.scalars().all()}
    lane_key_to_lane = {(l.board_id, l.state_key): l for l in existing_lanes.values()}
    for l in snap.get("lanes") or []:
      lid = str(l["id"])
      board_id = board_id_map.get(str(l["boardId"])) or str(l["boardId"])
      state_key = str(l.get("stateKey") or "")
      key = (board_id, state_key)
      if lid in existing_lanes:
        lane_id_map[lid] = lid
        if mode == "overwrite":
          el = existing_lanes[lid]
          el.name = str(l.get("name") or el.name)
          el.state_key = state_key or el.state_key
          el.type = str(l.get("type") or el.type)
          el.wip_limit = l.get("wipLimit")
          el.position = int(l.get("position") or el.position)
        continue
      if key in lane_key_to_lane:
        lane_id_map[lid] = lane_key_to_lane[key].id
        continue
      nl = Lane(
        id=lid,
        board_id=board_id,
        name=str(l["name"]),
        state_key=state_key or str(l["name"]).strip().lower(),
        type=str(l.get("type") or "active"),
        wip_limit=l.get("wipLimit"),
        position=int(l.get("position") or 0),
      )
      db.add(nl)
      lane_id_map[lid] = lid

    # Tasks: match by id, else by jiraKey (unique)
    res = await db.execute(select(Task))
    existing_tasks = {t.id: t for t in res.scalars().all()}
    jira_key_to_task = {t.jira_key: t for t in existing_tasks.values() if t.jira_key}
    for t in snap.get("tasks") or []:
      tid = str(t["id"])
      jira_key = (t.get("jiraKey") or "").strip() or None
      if tid in existing_tasks:
        task_id_map[tid] = tid
        if mode == "overwrite":
          et = existing_tasks[tid]
          et.title = str(t.get("title") or et.title)
          et.description = str(t.get("description") or "")
          et.priority = str(t.get("priority") or et.priority)
          et.type = str(t.get("type") or et.type)
          et.tags = list(t.get("tags") or [])
          et.due_date = datetime.fromisoformat(t["dueDate"].replace("Z", "+00:00")) if t.get("dueDate") else None
          et.estimate_minutes = t.get("estimateMinutes")
          et.blocked = bool(t.get("blocked", False))
          et.blocked_reason = t.get("blockedReason")
          et.order_index = int(t.get("orderIndex") or 0)
          et.version = int(t.get("version") or et.version)
        continue
      if jira_key and jira_key in jira_key_to_task:
        task_id_map[tid] = jira_key_to_task[jira_key].id
        continue
      board_id = board_id_map.get(str(t["boardId"])) or str(t["boardId"])
      lane_id = lane_id_map.get(str(t["laneId"])) or str(t["laneId"])
      owner_id = user_id_map.get(str(t.get("ownerId"))) if t.get("ownerId") else None
      nt = Task(
        id=tid,
        board_id=board_id,
        lane_id=lane_id,
        state_key=str(t.get("stateKey") or ""),
        title=str(t.get("title") or "Untitled"),
        description=str(t.get("description") or ""),
        owner_id=owner_id,
        priority=str(t.get("priority") or "P2"),
        type=str(t.get("type") or "Feature"),
        tags=list(t.get("tags") or []),
        due_date=datetime.fromisoformat(t["dueDate"].replace("Z", "+00:00")) if t.get("dueDate") else None,
        estimate_minutes=t.get("estimateMinutes"),
        blocked=bool(t.get("blocked", False)),
        blocked_reason=t.get("blockedReason"),
        order_index=int(t.get("orderIndex") or 0),
        version=int(t.get("version") or 0),
        jira_key=jira_key,
        jira_url=t.get("jiraUrl"),
        jira_sync_enabled=bool(t.get("jiraSyncEnabled", False)),
        jira_connection_id=t.get("jiraConnectionId"),
        jira_project_key=t.get("jiraProjectKey"),
        jira_issue_type=t.get("jiraIssueType"),
        jira_updated_at=datetime.fromisoformat(t["jiraUpdatedAt"].replace("Z", "+00:00")) if t.get("jiraUpdatedAt") else None,
        jira_last_sync_at=datetime.fromisoformat(t["jiraLastSyncAt"].replace("Z", "+00:00")) if t.get("jiraLastSyncAt") else None,
      )
      db.add(nt)
      task_id_map[tid] = tid

    # Comments
    res = await db.execute(select(Comment))
    existing_comments = {c.id: c for c in res.scalars().all()}
    for c in snap.get("comments") or []:
      cid = str(c["id"])
      if cid in existing_comments:
        if mode == "overwrite":
          ec = existing_comments[cid]
          ec.body = str(c.get("body") or ec.body)
        continue
      task_id = task_id_map.get(str(c["taskId"])) or str(c["taskId"])
      author_id = user_id_map.get(str(c["authorId"])) or str(c["authorId"])
      created_at = datetime.fromisoformat(str(c["createdAt"]).replace("Z", "+00:00"))
      nc = Comment(
        id=cid,
        task_id=task_id,
        author_id=author_id,
        body=str(c.get("body") or ""),
        source=str(c.get("source") or "app"),
        source_id=c.get("sourceId"),
        source_author=c.get("sourceAuthor"),
        source_url=c.get("sourceUrl"),
        jira_comment_id=c.get("jiraCommentId"),
        created_at=created_at,
      )
      db.add(nc)

    # Checklist items
    res = await db.execute(select(ChecklistItem))
    existing_items = {i.id: i for i in res.scalars().all()}
    for i in snap.get("checklistItems") or []:
      iid = str(i["id"])
      if iid in existing_items:
        if mode == "overwrite":
          ei = existing_items[iid]
          ei.text = str(i.get("text") or ei.text)
          ei.done = bool(i.get("done", False))
          ei.position = int(i.get("position") or ei.position)
        continue
      task_id = task_id_map.get(str(i["taskId"])) or str(i["taskId"])
      db.add(
        ChecklistItem(
          id=iid,
          task_id=task_id,
          text=str(i.get("text") or ""),
          done=bool(i.get("done", False)),
          position=int(i.get("position") or 0),
          created_at=datetime.fromisoformat(str(i["createdAt"]).replace("Z", "+00:00")),
        )
      )

    # Dependencies
    res = await db.execute(select(TaskDependency))
    existing_deps = {d.id: d for d in res.scalars().all()}
    for d in snap.get("taskDependencies") or []:
      did = str(d["id"])
      if did in existing_deps:
        continue
      task_id = task_id_map.get(str(d["taskId"])) or str(d["taskId"])
      depends_on = task_id_map.get(str(d["dependsOnTaskId"])) or str(d["dependsOnTaskId"])
      db.add(TaskDependency(id=did, task_id=task_id, depends_on_task_id=depends_on))

    # Attachments: restore file bytes and DB row.
    uploads_src = td_path / "uploads"
    uploads_dst = _uploads_dir()
    uploads_dst.mkdir(parents=True, exist_ok=True)

    res = await db.execute(select(Attachment))
    existing_att = {a.id: a for a in res.scalars().all()}
    for a in snap.get("attachments") or []:
      aid = str(a["id"])
      if aid in existing_att:
        continue
      src_path = uploads_src / Path(str(a.get("path") or "")).name
      if src_path.exists():
        dst_path = uploads_dst / src_path.name
        if not dst_path.exists():
          dst_path.write_bytes(src_path.read_bytes())
        out_path = str(Path("data/uploads") / src_path.name)
      else:
        out_path = str(a.get("path") or "")
      task_id = task_id_map.get(str(a["taskId"])) or str(a["taskId"])
      db.add(
        Attachment(
          id=aid,
          task_id=task_id,
          filename=str(a.get("filename") or src_path.name),
          mime=str(a.get("mime") or "application/octet-stream"),
          size_bytes=int(a.get("sizeBytes") or 0),
          path=out_path,
        )
      )

    # Audit events
    res = await db.execute(select(AuditEvent))
    existing_audit = {e.id: e for e in res.scalars().all()}
    for e in snap.get("auditEvents") or []:
      eid = str(e["id"])
      if eid in existing_audit:
        continue
      db.add(
        AuditEvent(
          id=eid,
          board_id=board_id_map.get(str(e.get("boardId"))) if e.get("boardId") else None,
          task_id=task_id_map.get(str(e.get("taskId"))) if e.get("taskId") else None,
          actor_id=user_id_map.get(str(e.get("actorId"))) if e.get("actorId") else None,
          event_type=str(e.get("eventType") or ""),
          entity_type=str(e.get("entityType") or ""),
          entity_id=e.get("entityId"),
          payload=e.get("payload") or {},
          created_at=datetime.fromisoformat(str(e["createdAt"]).replace("Z", "+00:00")),
        )
      )

    await db.commit()

    return {"ok": True, "dryRun": False, "counts": counts}
