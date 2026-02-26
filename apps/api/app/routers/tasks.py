from __future__ import annotations

import asyncio
import hashlib
import os
import re
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.config import settings
from app.deps import get_current_user, get_db, require_board_role
from app.models import (
  Attachment,
  BoardMember,
  BoardTaskPriority,
  BoardTaskType,
  ChecklistItem,
  Comment,
  Lane,
  OpenProjectConnection,
  Task,
  NotificationDestination,
  TaskDependency,
  TaskImportKey,
  TaskReminder,
  User,
)
from app.notifications.events import dispatch_to_materialized, materialize_enabled_destinations, notify_board_members_inapp, notify_inapp
from app.notifications.service import NotificationMessage, decrypt_destination_config
from app.schemas import (
  AttachmentOut,
  BulkUpdateIn,
  ChecklistCreateIn,
  ChecklistOut,
  ChecklistUpdateIn,
  CommentCreateIn,
  CommentOut,
  TaskJiraCreateIn,
  TaskJiraLinkIn,
  TaskOpenProjectCreateIn,
  TaskOpenProjectLinkIn,
  TaskBulkImportIn,
  TaskBulkImportOut,
  TaskBulkImportResultOut,
  TaskBoardDuplicateIn,
  TaskBoardMoveIn,
  TaskCreateIn,
  TaskMoveIn,
  TaskOut,
  TaskIcsEmailIn,
  TaskIcsEmailOut,
  TaskReminderCreateIn,
  TaskReminderOut,
  TaskUpdateIn,
)
from app.jira.service import get_task_jira_issue, link_task_to_jira_issue, create_jira_issue_from_task, pull_task_from_jira, sync_task_with_jira
from app.openproject.client import (
  openproject_create_work_package,
  openproject_get_work_package,
  openproject_update_work_package,
)
from app.security import decrypt_integration_secret

router = APIRouter(tags=["tasks"])


async def _validate_owner(board_id: str, owner_id: str | None, db: AsyncSession) -> None:
  if not owner_id:
    return
  res = await db.execute(
    select(User.id)
    .join(BoardMember, BoardMember.user_id == User.id)
    .where(User.id == owner_id, BoardMember.board_id == board_id)
  )
  ok = res.scalar_one_or_none()
  if not ok:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ownerId (must be a board member)")


async def _validate_type_and_priority(board_id: str, *, task_type: str | None, priority: str | None, db: AsyncSession) -> None:
  if task_type is not None:
    key = str(task_type).strip()
    if not key:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid type")
    res = await db.execute(
      select(BoardTaskType.key).where(BoardTaskType.board_id == board_id, BoardTaskType.key == key, BoardTaskType.enabled.is_(True))
    )
    if not res.scalar_one_or_none():
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid type (not enabled for this board)")
  if priority is not None:
    key = str(priority).strip()
    if not key:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid priority")
    res = await db.execute(
      select(BoardTaskPriority.key).where(
        BoardTaskPriority.board_id == board_id, BoardTaskPriority.key == key, BoardTaskPriority.enabled.is_(True)
      )
    )
    if not res.scalar_one_or_none():
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid priority (not enabled for this board)")


def _task_out(t: Task) -> TaskOut:
  return TaskOut(
    id=t.id,
    boardId=t.board_id,
    laneId=t.lane_id,
    stateKey=t.state_key,
    title=t.title,
    description=t.description,
    ownerId=t.owner_id,
    priority=t.priority,
    type=t.type,
    tags=list(t.tags or []),
    dueDate=t.due_date,
    estimateMinutes=t.estimate_minutes,
    blocked=t.blocked,
    blockedReason=t.blocked_reason,
    jiraKey=t.jira_key,
    jiraUrl=t.jira_url,
    jiraConnectionId=t.jira_connection_id,
    jiraSyncEnabled=bool(t.jira_sync_enabled),
    jiraProjectKey=t.jira_project_key,
    jiraIssueType=t.jira_issue_type,
    openprojectWorkPackageId=t.openproject_work_package_id,
    openprojectUrl=t.openproject_url,
    openprojectConnectionId=t.openproject_connection_id,
    openprojectSyncEnabled=bool(t.openproject_sync_enabled),
    orderIndex=t.order_index,
    version=t.version,
    createdAt=t.created_at,
    updatedAt=t.updated_at,
  )


def _reminder_out(r: TaskReminder) -> TaskReminderOut:
  return TaskReminderOut(
    id=r.id,
    taskId=r.task_id,
    recipientUserId=r.recipient_user_id,
    scheduledAt=r.scheduled_at,
    note=r.note,
    channels=list(r.channels or []),
    status=r.status,
    attempts=int(r.attempts or 0),
    lastError=r.last_error,
    sentAt=r.sent_at,
    canceledAt=r.canceled_at,
    createdAt=r.created_at,
  )


def _ics_escape(s: str) -> str:
  return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _build_task_ics(t: Task) -> bytes:
  # Always export as all-day event on the due date to avoid timezone surprises.
  start = t.due_date.date()
  end = start + timedelta(days=1)

  def _dt_date(d) -> str:
    return f"{d.year:04d}{d.month:02d}{d.day:02d}"

  summary = (t.title or "Task-Daddy task").replace("\n", " ").strip()
  desc = (t.description or "").replace("\r\n", "\n").strip()
  uid = f"{t.id}@taskdaddy.local"
  dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
  lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Task-Daddy//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    f"UID:{_ics_escape(uid)}",
    f"DTSTAMP:{dtstamp}",
    f"SUMMARY:{_ics_escape(summary)}",
    f"DTSTART;VALUE=DATE:{_dt_date(start)}",
    f"DTEND;VALUE=DATE:{_dt_date(end)}",
    f"DESCRIPTION:{_ics_escape(desc)}" if desc else "DESCRIPTION:",
    "END:VEVENT",
    "END:VCALENDAR",
    "",
  ]
  return "\r\n".join(lines).encode("utf-8")


async def _send_ics_over_smtp(
  *,
  cfg: dict,
  to_addr: str,
  subject: str,
  body_text: str,
  ics_bytes: bytes,
  filename: str,
) -> dict:
  host = str(cfg.get("host") or "").strip()
  port = int(cfg.get("port") or 587)
  username = str(cfg.get("username") or "").strip()
  password = str(cfg.get("password") or "").strip()
  from_addr = str(cfg.get("from") or "").strip()
  starttls = bool(cfg.get("starttls", True))
  if not host or not from_addr:
    raise ValueError("SMTP destination missing host/from")

  def _send_sync() -> None:
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = from_addr
    m["To"] = to_addr
    m.set_content(body_text)
    m.add_attachment(ics_bytes, maintype="text", subtype="calendar", filename=filename)
    with smtplib.SMTP(host=host, port=port, timeout=15) as s:
      s.ehlo()
      if starttls:
        s.starttls()
        s.ehlo()
      if username and password:
        s.login(username, password)
      s.send_message(m)

  await asyncio.to_thread(_send_sync)
  return {"to": to_addr, "from": from_addr, "host": host, "port": port}


async def _get_openproject_connection_or_400(*, db: AsyncSession, connection_id: str) -> OpenProjectConnection:
  cres = await db.execute(select(OpenProjectConnection).where(OpenProjectConnection.id == connection_id))
  conn = cres.scalar_one_or_none()
  if not conn or not conn.enabled:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OpenProject connection not found or disabled")
  return conn


def _normalize_import_title(title: str) -> str:
  t = title.strip()
  t = re.sub(r"^[-*•\\s]+", "", t)
  t = re.sub(r"\\s+", " ", t).strip().lower()
  return t


def _import_key_for_item(title: str, idempotency_key: str | None) -> str:
  raw = (idempotency_key or "").strip()
  if raw:
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"custom:{h}"
  norm = _normalize_import_title(title)
  h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
  return f"title:{h}"


def _mention_tokens_for_user(*, name: str | None, email: str | None) -> set[str]:
  tokens: set[str] = set()
  if name:
    nm = str(name).strip().lower()
    if nm:
      tokens.add("@" + nm)
      tokens.add("@" + nm.replace(" ", ""))
  if email:
    em = str(email).strip().lower()
    if em:
      tokens.add("@" + em)
      local = em.split("@", 1)[0]
      if local:
        tokens.add("@" + local)
  return tokens


def _burst_bucket_utc(*, minutes: int = 10) -> str:
  now = datetime.now(timezone.utc)
  minute_bucket = (now.minute // max(1, minutes)) * max(1, minutes)
  return f"{now.strftime('%Y%m%d%H')}{minute_bucket:02d}"


async def _pick_target_lane(board_id: str, lane_id: str | None, db: AsyncSession) -> Lane:
  if lane_id:
    lres = await db.execute(select(Lane).where(Lane.id == lane_id))
    lane = lres.scalar_one_or_none()
    if not lane or lane.board_id != board_id:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid targetLaneId")
    return lane
  res = await db.execute(select(Lane).where(Lane.board_id == board_id).order_by(Lane.position.asc()))
  lanes = res.scalars().all()
  if not lanes:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target board has no lanes")
  return next((l for l in lanes if l.type == "backlog"), lanes[0])


async def _normalize_type_priority_for_board(
  *,
  board_id: str,
  current_type: str,
  current_priority: str,
  db: AsyncSession,
) -> tuple[str, str]:
  t_res = await db.execute(
    select(BoardTaskType.key, BoardTaskType.position)
    .where(BoardTaskType.board_id == board_id, BoardTaskType.enabled.is_(True))
    .order_by(BoardTaskType.position.asc())
  )
  p_res = await db.execute(
    select(BoardTaskPriority.key, BoardTaskPriority.rank)
    .where(BoardTaskPriority.board_id == board_id, BoardTaskPriority.enabled.is_(True))
    .order_by(BoardTaskPriority.rank.asc())
  )
  type_keys = [row.key for row in t_res.all() if row.key]
  prio_keys = [row.key for row in p_res.all() if row.key]
  if not type_keys or not prio_keys:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target board task fields are not configured")
  out_type = current_type if current_type in type_keys else type_keys[0]
  out_priority = current_priority if current_priority in prio_keys else prio_keys[min(2, len(prio_keys) - 1)]
  return out_type, out_priority


@router.get("/boards/{board_id}/tasks", response_model=list[TaskOut])
async def list_tasks(
  board_id: str,
  search: str | None = None,
  ownerId: str | None = None,
  priority: str | None = None,
  type: str | None = None,
  tag: str | None = None,
  dueFrom: datetime | None = None,
  dueTo: datetime | None = None,
  blocked: bool | None = None,
  unassigned: bool | None = None,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> list[TaskOut]:
  await require_board_role(board_id, "viewer", user, db)
  # Best-effort overdue reminders for the current user (in-app only, deduped).
  lanes_res = await db.execute(select(Lane.id, Lane.type).where(Lane.board_id == board_id))
  lane_type_by_id = {row.id: row.type for row in lanes_res.all()}
  q = select(Task).where(Task.board_id == board_id)

  if search:
    like = f"%{search}%"
    q = q.where(or_(Task.title.ilike(like), Task.description.ilike(like), func.array_to_string(Task.tags, ",").ilike(like), Task.jira_key.ilike(like)))
  if ownerId:
    q = q.where(Task.owner_id == ownerId)
  if unassigned:
    q = q.where(Task.owner_id.is_(None))
  if priority:
    q = q.where(Task.priority == priority)
  if type:
    q = q.where(Task.type == type)
  if tag:
    q = q.where(Task.tags.any(tag))
  if blocked is not None:
    q = q.where(Task.blocked == blocked)
  if dueFrom:
    q = q.where(Task.due_date >= dueFrom)
  if dueTo:
    q = q.where(Task.due_date <= dueTo)

  q = q.order_by(Task.lane_id.asc(), Task.order_index.asc())
  res = await db.execute(q)
  tasks = res.scalars().all()

  now = datetime.now(timezone.utc)
  for t in tasks:
    if t.owner_id != user.id:
      continue
    if not t.due_date:
      continue
    if lane_type_by_id.get(t.lane_id) == "done":
      continue
    if t.due_date < now:
      await notify_inapp(
        db,
        user_id=user.id,
        level="warn",
        title="Task overdue",
        body=f"{t.title}",
        event_type="task.overdue",
        entity_type="Task",
        entity_id=t.id,
        dedupe_key=f"task.overdue:{t.id}:{now.date().isoformat()}",
      )
  await db.commit()
  return [_task_out(t) for t in tasks]


@router.post("/boards/{board_id}/tasks", response_model=TaskOut)
async def create_task(
  board_id: str,
  payload: TaskCreateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> TaskOut:
  await require_board_role(board_id, "member", user, db)
  lres = await db.execute(select(Lane).where(Lane.id == payload.laneId))
  lane = lres.scalar_one_or_none()
  if not lane or lane.board_id != board_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid laneId")

  await _validate_owner(board_id, payload.ownerId, db)
  await _validate_type_and_priority(board_id, task_type=payload.type, priority=payload.priority, db=db)

  ores = await db.execute(select(func.max(Task.order_index)).where(Task.board_id == board_id, Task.lane_id == lane.id))
  max_order = ores.scalar_one()
  new_order = (max_order + 1) if max_order is not None else 0
  t = Task(
    board_id=board_id,
    lane_id=lane.id,
    state_key=lane.state_key,
    title=payload.title,
    description=payload.description or "",
    owner_id=payload.ownerId,
    priority=payload.priority,
    type=payload.type,
    tags=list(payload.tags or []),
    due_date=payload.dueDate,
    estimate_minutes=payload.estimateMinutes,
    blocked=payload.blocked,
    blocked_reason=payload.blockedReason,
    order_index=new_order,
    version=0,
  )
  db.add(t)
  await write_audit(
    db,
    event_type="task.created",
    entity_type="Task",
    entity_id=t.id,
    board_id=board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"title": t.title, "laneId": t.lane_id},
  )

  # In-app notifications: task created + assignment.
  external_messages: list[NotificationMessage] = []
  if payload.ownerId and payload.ownerId != user.id:
    await notify_inapp(
      db,
      user_id=payload.ownerId,
      level="info",
      title="New task assigned",
      body=f"{t.title}",
      event_type="task.assigned",
      entity_type="Task",
      entity_id=t.id,
      dedupe_key=f"task.assigned:{t.id}:{payload.ownerId}",
    )
    external_messages.append(NotificationMessage(title="Task-Daddy: task assigned", message=f"{t.title}", priority=0))
  else:
    await notify_board_members_inapp(
      db,
      board_id=board_id,
      exclude_user_id=user.id,
      level="info",
      title="New task created",
      body=f"{t.title}",
      event_type="task.created",
      entity_type="Task",
      entity_id=t.id,
      dedupe_key=f"task.created:{t.id}",
    )

  # Overdue signal: if due date is already in the past and task isn't done.
  if payload.dueDate and payload.dueDate < datetime.now(timezone.utc) and payload.ownerId:
    await notify_inapp(
      db,
      user_id=payload.ownerId,
      level="warn",
      title="Task overdue",
      body=f"{t.title}",
      event_type="task.overdue",
      entity_type="Task",
      entity_id=t.id,
      dedupe_key=f"task.overdue:{t.id}:{payload.dueDate.date().isoformat()}:{payload.ownerId}",
    )
    external_messages.append(NotificationMessage(title="Task-Daddy: task overdue", message=f"{t.title}", priority=1))

  external_dests = await materialize_enabled_destinations(db) if external_messages else []
  await db.commit()

  # External notifications should never block the request.
  for msg in external_messages:
    if external_dests:
      asyncio.create_task(dispatch_to_materialized(external_dests, msg=msg))
  return _task_out(t)


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  return _task_out(t)


@router.get("/tasks/{task_id}/ics")
async def task_ics(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Response:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  if not t.due_date:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task has no dueDate")
  body = _build_task_ics(t)
  return Response(
    content=body,
    media_type="text/calendar; charset=utf-8",
    headers={"Content-Disposition": f'attachment; filename="task_daddy_task_{t.id}.ics"'},
  )


@router.post("/tasks/{task_id}/ics/email", response_model=TaskIcsEmailOut)
async def task_ics_email(
  task_id: str,
  payload: TaskIcsEmailIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> TaskIcsEmailOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  if not t.due_date:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task has no dueDate")

  sres = await db.execute(
    select(NotificationDestination)
    .where(NotificationDestination.provider == "smtp", NotificationDestination.enabled.is_(True))
    .order_by(NotificationDestination.updated_at.desc(), NotificationDestination.created_at.desc())
  )
  smtp_destination = sres.scalars().first()
  if not smtp_destination:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No enabled SMTP destination configured")

  cfg = decrypt_destination_config(smtp_destination.config_encrypted)
  to_addr = str((payload.to or cfg.get("to") or "")).strip()
  if not to_addr:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recipient email is required")

  ics_filename = f"task_daddy_task_{t.id}.ics"
  body = _build_task_ics(t)
  due_str = t.due_date.date().isoformat()
  subject = (payload.subject or f"Task-Daddy task due: {t.title} ({due_str})").strip()
  note = (payload.note or "").strip()
  body_text = f"Task: {t.title}\nDue: {due_str}\nBoard: {t.board_id}\n"
  if note:
    body_text = f"{body_text}\n{note}"
  detail = await _send_ics_over_smtp(
    cfg=cfg,
    to_addr=to_addr,
    subject=subject,
    body_text=body_text,
    ics_bytes=body,
    filename=ics_filename,
  )
  await write_audit(
    db,
    event_type="task.ics.emailed",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"to": to_addr, "destinationId": smtp_destination.id},
  )
  await db.commit()
  return TaskIcsEmailOut(ok=True, to=to_addr, provider="smtp", filename=ics_filename, detail=detail)


@router.get("/tasks/{task_id}/reminders", response_model=list[TaskReminderOut])
async def list_task_reminders(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[TaskReminderOut]:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  res = await db.execute(select(TaskReminder).where(TaskReminder.task_id == task_id).order_by(TaskReminder.scheduled_at.asc()))
  return [_reminder_out(r) for r in res.scalars().all()]


@router.post("/tasks/{task_id}/reminders", response_model=TaskReminderOut)
async def create_task_reminder(
  task_id: str,
  payload: TaskReminderCreateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> TaskReminderOut:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)

  recipient_user_id = user.id
  if payload.recipient == "owner":
    if not t.owner_id:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task has no owner to remind")
    recipient_user_id = t.owner_id

  r = TaskReminder(
    task_id=t.id,
    board_id=t.board_id,
    created_by_user_id=user.id,
    recipient_user_id=recipient_user_id,
    scheduled_at=payload.scheduledAt,
    note=(payload.note or "").strip(),
    channels=list(payload.channels or ["inapp"]),
    status="pending",
    attempts=0,
    last_error=None,
    last_attempt_at=None,
    sent_at=None,
    canceled_at=None,
  )
  db.add(r)
  await db.flush()
  await write_audit(
    db,
    event_type="reminder.created",
    entity_type="TaskReminder",
    entity_id=r.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"scheduledAt": r.scheduled_at.isoformat(), "recipientUserId": recipient_user_id, "channels": list(r.channels or [])},
  )
  await db.commit()
  return _reminder_out(r)


@router.delete("/reminders/{reminder_id}")
async def cancel_task_reminder(
  reminder_id: str,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  rres = await db.execute(select(TaskReminder).where(TaskReminder.id == reminder_id))
  r = rres.scalar_one_or_none()
  if not r:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
  tres = await db.execute(select(Task).where(Task.id == r.task_id))
  t = tres.scalar_one()
  await require_board_role(t.board_id, "member", user, db)
  # Only creator, recipient, or board admin can cancel.
  if user.id not in (r.created_by_user_id, r.recipient_user_id):
    await require_board_role(t.board_id, "admin", user, db)
  now = datetime.now(timezone.utc)
  r.canceled_at = now
  r.status = "canceled"
  await write_audit(
    db,
    event_type="reminder.canceled",
    entity_type="TaskReminder",
    entity_id=r.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={},
  )
  await db.commit()
  return {"ok": True}


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(task_id: str, payload: TaskUpdateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  if t.version != payload.version:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Version conflict")

  old_owner_id = t.owner_id
  old_due = t.due_date
  external_messages: list[NotificationMessage] = []

  fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
  if "ownerId" in fields_set:
    await _validate_owner(t.board_id, payload.ownerId, db)
  if "type" in fields_set or "priority" in fields_set:
    await _validate_type_and_priority(t.board_id, task_type=(payload.type if "type" in fields_set else None), priority=(payload.priority if "priority" in fields_set else None), db=db)

  changed: dict = {}
  mapping = [
    ("title", "title"),
    ("description", "description"),
    ("owner_id", "ownerId"),
    ("priority", "priority"),
    ("type", "type"),
    ("tags", "tags"),
    ("due_date", "dueDate"),
    ("estimate_minutes", "estimateMinutes"),
    ("blocked", "blocked"),
    ("blocked_reason", "blockedReason"),
  ]
  for model_attr, field_name in mapping:
    if field_name in fields_set:
      val = getattr(payload, field_name)
      setattr(t, model_attr, val)
      if field_name == "description" and isinstance(val, str):
        changed[field_name] = val[:500]
      else:
        changed[field_name] = val

  t.version += 1
  await write_audit(
    db,
    event_type="task.updated",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"version": t.version, "changed": list(changed.keys()), "fields": changed},
  )

  # Assignment notification
  if "ownerId" in fields_set and t.owner_id and t.owner_id != old_owner_id and t.owner_id != user.id:
    await notify_inapp(
      db,
      user_id=t.owner_id,
      level="info",
      title="Task assigned",
      body=f"{t.title}",
      event_type="task.assigned",
      entity_type="Task",
      entity_id=t.id,
      dedupe_key=f"task.assigned:{t.id}:{t.owner_id}",
    )
    external_messages.append(NotificationMessage(title="Task-Daddy: task assigned", message=f"{t.title}", priority=0))

  # Due date notifications (warn on overdue)
  if "dueDate" in fields_set and t.due_date and t.due_date != old_due and t.owner_id:
    lres = await db.execute(select(Lane).where(Lane.id == t.lane_id))
    lane = lres.scalar_one_or_none()
    if (not lane) or lane.type != "done":
      if t.due_date < datetime.now(timezone.utc):
        await notify_inapp(
          db,
          user_id=t.owner_id,
          level="warn",
          title="Task overdue",
          body=f"{t.title}",
          event_type="task.overdue",
          entity_type="Task",
          entity_id=t.id,
          dedupe_key=f"task.overdue:{t.id}:{t.due_date.date().isoformat()}:{t.owner_id}",
        )
        external_messages.append(NotificationMessage(title="Task-Daddy: task overdue", message=f"{t.title}", priority=1))

  external_dests = await materialize_enabled_destinations(db) if external_messages else []
  await db.commit()

  for msg in external_messages:
    if external_dests:
      asyncio.create_task(dispatch_to_materialized(external_dests, msg=msg))
  return _task_out(t)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  await db.execute(delete(Task).where(Task.id == task_id))
  await write_audit(
    db,
    event_type="task.deleted",
    entity_type="Task",
    entity_id=task_id,
    board_id=t.board_id,
    actor_id=user.id,
    payload={"title": t.title},
  )
  await db.commit()
  return {"ok": True}


@router.post("/tasks/{task_id}/move", response_model=TaskOut)
async def move_task(task_id: str, payload: TaskMoveIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  if t.version != payload.version:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Version conflict")

  lres = await db.execute(select(Lane).where(Lane.id == payload.laneId))
  lane = lres.scalar_one_or_none()
  if not lane or lane.board_id != t.board_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid laneId")

  from_lane = t.lane_id
  to_lane = lane.id
  to_idx = max(payload.toIndex, 0)

  # Robust reindexing (MVP): compute ordering in memory, then write sequential indices.
  if from_lane == to_lane:
    res = await db.execute(select(Task).where(Task.board_id == t.board_id, Task.lane_id == from_lane).order_by(Task.order_index.asc()))
    arr = res.scalars().all()
    arr = [x for x in arr if x.id != t.id]
    to_idx = min(to_idx, len(arr))
    arr.insert(to_idx, t)
    for idx, x in enumerate(arr):
      x.order_index = idx
    t.lane_id = to_lane
    t.state_key = lane.state_key
  else:
    f_res = await db.execute(select(Task).where(Task.board_id == t.board_id, Task.lane_id == from_lane).order_by(Task.order_index.asc()))
    t_res = await db.execute(select(Task).where(Task.board_id == t.board_id, Task.lane_id == to_lane).order_by(Task.order_index.asc()))
    from_arr = [x for x in f_res.scalars().all() if x.id != t.id]
    to_arr = t_res.scalars().all()
    to_idx = min(to_idx, len(to_arr))
    to_arr.insert(to_idx, t)
    for idx, x in enumerate(from_arr):
      x.order_index = idx
    for idx, x in enumerate(to_arr):
      x.order_index = idx
    t.lane_id = to_lane
    t.state_key = lane.state_key

  t.version += 1
  if t.owner_id and t.owner_id != user.id and from_lane != to_lane:
    burst = _burst_bucket_utc(minutes=10)
    await notify_inapp(
      db,
      user_id=t.owner_id,
      level="info",
      title="Task moved",
      body=f"{t.title} → {lane.name}",
      event_type="task.moved",
      entity_type="Task",
      entity_id=t.id,
      dedupe_key=f"task.moved:{t.id}:{t.owner_id}:{burst}",
    )
  await write_audit(
    db,
    event_type="task.moved",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"fromLaneId": from_lane, "toLaneId": lane.id, "toIndex": to_idx},
  )
  await db.commit()
  return _task_out(t)


@router.post("/tasks/{task_id}/transfer-board", response_model=TaskOut)
async def transfer_task_to_board(
  task_id: str,
  payload: TaskBoardMoveIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  task = res.scalar_one_or_none()
  if not task:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(task.board_id, "member", user, db)
  await require_board_role(payload.targetBoardId, "member", user, db)

  lane = await _pick_target_lane(payload.targetBoardId, payload.targetLaneId, db)
  next_order_res = await db.execute(select(func.max(Task.order_index)).where(Task.board_id == payload.targetBoardId, Task.lane_id == lane.id))
  max_order = next_order_res.scalar_one()
  target_order = (max_order + 1) if max_order is not None else 0

  member_res = await db.execute(select(BoardMember.user_id).where(BoardMember.board_id == payload.targetBoardId, BoardMember.user_id == task.owner_id))
  owner_is_member = bool(member_res.scalar_one_or_none()) if task.owner_id else False
  new_owner = task.owner_id if (payload.keepOwnerIfMember and owner_is_member) else None
  new_type, new_priority = await _normalize_type_priority_for_board(
    board_id=payload.targetBoardId,
    current_type=task.type,
    current_priority=task.priority,
    db=db,
  )

  old_board_id = task.board_id
  old_lane_id = task.lane_id
  task.board_id = payload.targetBoardId
  task.lane_id = lane.id
  task.state_key = lane.state_key
  task.order_index = target_order
  task.owner_id = new_owner
  task.type = new_type
  task.priority = new_priority
  task.version += 1
  # Board-linked Jira profile is no longer valid across board transfer.
  task.jira_sync_enabled = False

  await write_audit(
    db,
    event_type="task.transferred_board",
    entity_type="Task",
    entity_id=task.id,
    board_id=payload.targetBoardId,
    task_id=task.id,
    actor_id=user.id,
    payload={
      "fromBoardId": old_board_id,
      "toBoardId": payload.targetBoardId,
      "fromLaneId": old_lane_id,
      "toLaneId": lane.id,
      "ownerRetained": bool(new_owner),
    },
  )
  await db.commit()
  return _task_out(task)


@router.post("/tasks/{task_id}/duplicate-to-board", response_model=TaskOut)
async def duplicate_task_to_board(
  task_id: str,
  payload: TaskBoardDuplicateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  task = res.scalar_one_or_none()
  if not task:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(task.board_id, "member", user, db)
  await require_board_role(payload.targetBoardId, "member", user, db)

  lane = await _pick_target_lane(payload.targetBoardId, payload.targetLaneId, db)
  next_order_res = await db.execute(select(func.max(Task.order_index)).where(Task.board_id == payload.targetBoardId, Task.lane_id == lane.id))
  max_order = next_order_res.scalar_one()
  target_order = (max_order + 1) if max_order is not None else 0

  member_res = await db.execute(select(BoardMember.user_id).where(BoardMember.board_id == payload.targetBoardId, BoardMember.user_id == task.owner_id))
  owner_is_member = bool(member_res.scalar_one_or_none()) if task.owner_id else False
  new_owner = task.owner_id if (payload.keepOwnerIfMember and owner_is_member) else None
  new_type, new_priority = await _normalize_type_priority_for_board(
    board_id=payload.targetBoardId,
    current_type=task.type,
    current_priority=task.priority,
    db=db,
  )

  clone = Task(
    board_id=payload.targetBoardId,
    lane_id=lane.id,
    state_key=lane.state_key,
    title=task.title,
    description=task.description,
    owner_id=new_owner,
    priority=new_priority,
    type=new_type,
    tags=list(task.tags or []),
    due_date=task.due_date,
    estimate_minutes=task.estimate_minutes,
    blocked=task.blocked,
    blocked_reason=task.blocked_reason,
    order_index=target_order,
    version=0,
  )
  db.add(clone)
  await db.flush()

  if payload.includeChecklist:
    cres = await db.execute(select(ChecklistItem).where(ChecklistItem.task_id == task.id).order_by(ChecklistItem.position.asc()))
    for item in cres.scalars().all():
      db.add(ChecklistItem(task_id=clone.id, text=item.text, done=item.done, position=item.position))

  if payload.includeComments:
    com_res = await db.execute(select(Comment).where(Comment.task_id == task.id).order_by(Comment.created_at.asc()))
    for c in com_res.scalars().all():
      db.add(Comment(task_id=clone.id, author_id=c.author_id, body=c.body))

  if payload.includeDependencies:
    dep_res = await db.execute(select(TaskDependency).where(TaskDependency.task_id == task.id))
    for dep in dep_res.scalars().all():
      db.add(TaskDependency(task_id=clone.id, depends_on_task_id=dep.depends_on_task_id))

  await write_audit(
    db,
    event_type="task.duplicated_board",
    entity_type="Task",
    entity_id=clone.id,
    board_id=payload.targetBoardId,
    task_id=clone.id,
    actor_id=user.id,
    payload={"sourceTaskId": task.id, "sourceBoardId": task.board_id, "toBoardId": payload.targetBoardId, "toLaneId": lane.id},
  )
  await db.commit()
  return _task_out(clone)


@router.post("/boards/{board_id}/tasks/bulk_import", response_model=TaskBulkImportOut)
async def bulk_import_tasks(
  board_id: str,
  payload: TaskBulkImportIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> TaskBulkImportOut:
  await require_board_role(board_id, "member", user, db)

  lanes_res = await db.execute(select(Lane).where(Lane.board_id == board_id))
  lanes = lanes_res.scalars().all()
  if not lanes:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Board has no lanes")
  lanes_by_id = {l.id: l for l in lanes}

  default_lane: Lane | None = None
  if payload.defaultLaneId:
    default_lane = lanes_by_id.get(payload.defaultLaneId)
    if not default_lane:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid defaultLaneId")
  if not default_lane:
    default_lane = next((l for l in lanes if l.type == "backlog"), lanes[0])

  existing_by_title_key: dict[str, Task] = {}
  if payload.skipIfTitleExists:
    query_keys = sorted({i.title.strip().lower() for i in payload.items if i.title.strip()})
    if query_keys:
      res = await db.execute(
        select(Task).where(Task.board_id == board_id, func.lower(func.trim(Task.title)).in_(query_keys))
      )
      for t in res.scalars().all():
        existing_by_title_key[_normalize_import_title(t.title)] = t

  results: list[TaskBulkImportResultOut] = []
  created_count = 0
  existing_count = 0

  for item in payload.items:
    title = item.title.strip()
    if not title:
      continue

    key = _import_key_for_item(title, item.idempotencyKey)

    kres = await db.execute(select(TaskImportKey).where(TaskImportKey.board_id == board_id, TaskImportKey.key == key))
    km = kres.scalar_one_or_none()
    if km:
      tres = await db.execute(select(Task).where(Task.id == km.task_id))
      t = tres.scalar_one_or_none()
      if t:
        existing_count += 1
        results.append(TaskBulkImportResultOut(status="existing", key=key, task=_task_out(t)))
        continue

    if payload.skipIfTitleExists:
      existing = existing_by_title_key.get(_normalize_import_title(title))
      if existing:
        try:
          async with db.begin_nested():
            db.add(TaskImportKey(board_id=board_id, key=key, task_id=existing.id))
            await db.flush()
        except IntegrityError:
          pass
        existing_count += 1
        results.append(TaskBulkImportResultOut(status="existing", key=key, task=_task_out(existing)))
        continue

    lane = default_lane
    if item.laneId:
      lane = lanes_by_id.get(item.laneId)
      if not lane:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid laneId in items")

    await _validate_owner(board_id, item.ownerId, db)
    await _validate_type_and_priority(board_id, task_type=item.type, priority=item.priority, db=db)

    try:
      async with db.begin_nested():
        ores = await db.execute(select(func.max(Task.order_index)).where(Task.board_id == board_id, Task.lane_id == lane.id))
        max_order = ores.scalar_one()
        new_order = (max_order + 1) if max_order is not None else 0

        t = Task(
          board_id=board_id,
          lane_id=lane.id,
          state_key=lane.state_key,
          title=title,
          description=item.description or "",
          owner_id=item.ownerId,
          priority=item.priority,
          type=item.type,
          tags=list(item.tags or []),
          due_date=item.dueDate,
          estimate_minutes=item.estimateMinutes,
          blocked=item.blocked,
          blocked_reason=item.blockedReason,
          order_index=new_order,
          version=0,
        )
        db.add(t)
        await db.flush()
        db.add(TaskImportKey(board_id=board_id, key=key, task_id=t.id))
        await db.flush()
        await write_audit(
          db,
          event_type="task.imported",
          entity_type="Task",
          entity_id=t.id,
          board_id=board_id,
          task_id=t.id,
          actor_id=user.id,
          payload={"title": t.title, "laneId": t.lane_id, "importKey": key},
        )
      created_count += 1
      results.append(TaskBulkImportResultOut(status="created", key=key, task=_task_out(t)))
    except IntegrityError:
      kres = await db.execute(select(TaskImportKey).where(TaskImportKey.board_id == board_id, TaskImportKey.key == key))
      km = kres.scalar_one_or_none()
      if not km:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency conflict")
      tres = await db.execute(select(Task).where(Task.id == km.task_id))
      t = tres.scalar_one()
      existing_count += 1
      results.append(TaskBulkImportResultOut(status="existing", key=key, task=_task_out(t)))

  await db.commit()
  return TaskBulkImportOut(createdCount=created_count, existingCount=existing_count, results=results)


@router.post("/tasks/{task_id}/jira/link", response_model=TaskOut)
async def jira_link_task(task_id: str, payload: TaskJiraLinkIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  t2 = await link_task_to_jira_issue(db, task=t, connection_id=payload.connectionId, jira_key=payload.jiraKey, enable_sync=payload.enableSync, actor_id=user.id)
  await db.commit()
  return _task_out(t2)


@router.post("/tasks/{task_id}/jira/create", response_model=TaskOut)
async def jira_create_for_task(task_id: str, payload: TaskJiraCreateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  t2 = await create_jira_issue_from_task(
    db,
    task=t,
    connection_id=payload.connectionId,
    project_key=payload.projectKey,
    issue_type=payload.issueType,
    enable_sync=payload.enableSync,
    assignee_mode=payload.assigneeMode,
    actor_id=user.id,
  )
  await db.commit()
  return _task_out(t2)


@router.post("/tasks/{task_id}/jira/pull", response_model=TaskOut)
async def jira_pull_for_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  t2 = await pull_task_from_jira(db, task=t, actor_id=user.id)
  await db.commit()
  return _task_out(t2)


@router.post("/tasks/{task_id}/jira/sync", response_model=TaskOut)
async def jira_sync_for_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  t2 = await sync_task_with_jira(db, task=t, actor_id=user.id)
  await db.commit()
  return _task_out(t2)


@router.get("/tasks/{task_id}/jira/issue")
async def jira_get_issue(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  return await get_task_jira_issue(db, task=t)


@router.post("/tasks/{task_id}/openproject/link", response_model=TaskOut)
async def openproject_link_task(
  task_id: str,
  payload: TaskOpenProjectLinkIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  conn = await _get_openproject_connection_or_400(db=db, connection_id=payload.connectionId)
  token = decrypt_integration_secret(conn.api_token_encrypted)
  wp = await openproject_get_work_package(base_url=conn.base_url, api_token=token, work_package_id=payload.workPackageId)
  t.openproject_work_package_id = int(wp["id"])
  t.openproject_url = str(wp["url"])
  t.openproject_connection_id = conn.id
  t.openproject_sync_enabled = bool(payload.enableSync)
  t.openproject_updated_at = datetime.now(timezone.utc)
  await write_audit(
    db,
    event_type="task.openproject.linked",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"connectionId": conn.id, "workPackageId": t.openproject_work_package_id, "enableSync": bool(payload.enableSync)},
  )
  await db.commit()
  return _task_out(t)


@router.post("/tasks/{task_id}/openproject/create", response_model=TaskOut)
async def openproject_create_for_task(
  task_id: str,
  payload: TaskOpenProjectCreateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  conn = await _get_openproject_connection_or_400(db=db, connection_id=payload.connectionId)
  token = decrypt_integration_secret(conn.api_token_encrypted)
  project_identifier = (payload.projectIdentifier or conn.project_identifier or "").strip()
  if not project_identifier:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="projectIdentifier required on task or connection")
  wp = await openproject_create_work_package(
    base_url=conn.base_url,
    api_token=token,
    project_identifier=project_identifier,
    subject=t.title,
    description=t.description or "",
  )
  t.openproject_work_package_id = int(wp["id"])
  t.openproject_url = str(wp["url"])
  t.openproject_connection_id = conn.id
  t.openproject_sync_enabled = bool(payload.enableSync)
  t.openproject_updated_at = datetime.now(timezone.utc)
  await write_audit(
    db,
    event_type="task.openproject.created",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"connectionId": conn.id, "workPackageId": t.openproject_work_package_id, "projectIdentifier": project_identifier},
  )
  await db.commit()
  return _task_out(t)


@router.post("/tasks/{task_id}/openproject/pull", response_model=TaskOut)
async def openproject_pull_for_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  if not t.openproject_connection_id or not t.openproject_work_package_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task not linked to OpenProject")
  conn = await _get_openproject_connection_or_400(db=db, connection_id=t.openproject_connection_id)
  token = decrypt_integration_secret(conn.api_token_encrypted)
  wp = await openproject_get_work_package(
    base_url=conn.base_url,
    api_token=token,
    work_package_id=int(t.openproject_work_package_id),
  )
  t.title = str(wp["subject"] or t.title)
  t.description = str(wp["description"] or t.description)
  t.openproject_url = str(wp["url"])
  t.openproject_updated_at = datetime.now(timezone.utc)
  t.openproject_last_sync_at = datetime.now(timezone.utc)
  await write_audit(
    db,
    event_type="task.openproject.pulled",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"connectionId": conn.id, "workPackageId": int(t.openproject_work_package_id)},
  )
  await db.commit()
  return _task_out(t)


@router.post("/tasks/{task_id}/openproject/sync", response_model=TaskOut)
async def openproject_sync_for_task(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TaskOut:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  if not t.openproject_connection_id or not t.openproject_work_package_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task not linked to OpenProject")
  conn = await _get_openproject_connection_or_400(db=db, connection_id=t.openproject_connection_id)
  token = decrypt_integration_secret(conn.api_token_encrypted)
  wp = await openproject_update_work_package(
    base_url=conn.base_url,
    api_token=token,
    work_package_id=int(t.openproject_work_package_id),
    subject=t.title,
    description=t.description or "",
  )
  t.openproject_url = str(wp["url"])
  t.openproject_updated_at = datetime.now(timezone.utc)
  t.openproject_last_sync_at = datetime.now(timezone.utc)
  await write_audit(
    db,
    event_type="task.openproject.synced",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"connectionId": conn.id, "workPackageId": int(t.openproject_work_package_id)},
  )
  await db.commit()
  return _task_out(t)


@router.get("/tasks/{task_id}/openproject/work-package")
async def openproject_get_issue(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  res = await db.execute(select(Task).where(Task.id == task_id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  if not t.openproject_connection_id or not t.openproject_work_package_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task not linked to OpenProject")
  conn = await _get_openproject_connection_or_400(db=db, connection_id=t.openproject_connection_id)
  token = decrypt_integration_secret(conn.api_token_encrypted)
  return await openproject_get_work_package(
    base_url=conn.base_url,
    api_token=token,
    work_package_id=int(t.openproject_work_package_id),
  )


@router.post("/boards/{board_id}/tasks/bulk")
async def bulk_update(board_id: str, payload: BulkUpdateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  await require_board_role(board_id, "member", user, db)
  allowed = {"ownerId": "owner_id", "priority": "priority", "type": "type", "blocked": "blocked"}
  patch = {}
  for k, v in payload.patch.items():
    if k in allowed:
      patch[allowed[k]] = v
  if "owner_id" in patch:
    await _validate_owner(board_id, patch["owner_id"], db)
  if "type" in patch or "priority" in patch:
    await _validate_type_and_priority(board_id, task_type=patch.get("type"), priority=patch.get("priority"), db=db)
  if not patch:
    return {"ok": True, "updated": 0}
  res = await db.execute(update(Task).where(Task.board_id == board_id, Task.id.in_(payload.taskIds)).values(**patch))
  await write_audit(
    db,
    event_type="tasks.bulk_updated",
    entity_type="Board",
    entity_id=board_id,
    board_id=board_id,
    actor_id=user.id,
    payload={"count": len(payload.taskIds), "patch": payload.patch},
  )
  await db.commit()
  return {"ok": True, "updated": res.rowcount or 0}


@router.get("/tasks/{task_id}/comments", response_model=list[CommentOut])
async def list_comments(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[CommentOut]:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  res = await db.execute(
    select(Comment, User)
    .join(User, User.id == Comment.author_id)
    .where(Comment.task_id == task_id)
    .order_by(Comment.created_at.asc())
  )
  out: list[CommentOut] = []
  for c, u in res.all():
    out.append(
      CommentOut(
        id=c.id,
        taskId=c.task_id,
        authorId=c.author_id,
        authorName=u.name,
        body=c.body,
        source=getattr(c, "source", "app"),
        sourceId=getattr(c, "source_id", None),
        sourceAuthor=getattr(c, "source_author", None),
        sourceUrl=getattr(c, "source_url", None),
        createdAt=c.created_at,
      )
    )
  return out


@router.post("/tasks/{task_id}/comments", response_model=CommentOut)
async def create_comment(
  task_id: str,
  payload: CommentCreateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> CommentOut:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  c = Comment(task_id=task_id, author_id=user.id, body=payload.body)
  db.add(c)
  body_l = payload.body.lower()

  # Mention notifications for board members (e.g. @name, @namewithoutspace, @email, @localpart).
  mres = await db.execute(
    select(User.id, User.name, User.email)
    .join(BoardMember, BoardMember.user_id == User.id)
    .where(BoardMember.board_id == t.board_id, User.active.is_(True))
  )
  for uid, uname, uemail in mres.all():
    if uid == user.id:
      continue
    tokens = _mention_tokens_for_user(name=uname, email=uemail)
    if not tokens:
      continue
    if not any(tok in body_l for tok in tokens):
      continue
    burst = _burst_bucket_utc(minutes=10)
    await notify_inapp(
      db,
      user_id=uid,
      level="info",
      title="You were mentioned",
      body=f"{t.title}",
      event_type="comment.mentioned",
      entity_type="Task",
      entity_id=t.id,
      dedupe_key=f"comment.mentioned:{t.id}:{uid}:{burst}",
    )

  # Notify task owner on new comments by others.
  if t.owner_id and t.owner_id != user.id:
    burst = _burst_bucket_utc(minutes=10)
    await notify_inapp(
      db,
      user_id=t.owner_id,
      level="info",
      title="New comment on your task",
      body=f"{t.title}",
      event_type="comment.created",
      entity_type="Task",
      entity_id=t.id,
      dedupe_key=f"comment.created:{t.id}:{t.owner_id}:{burst}",
    )

  await write_audit(
    db,
    event_type="comment.created",
    entity_type="Comment",
    entity_id=c.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"body": payload.body[:500]},
  )
  await db.commit()
  return CommentOut(
    id=c.id,
    taskId=c.task_id,
    authorId=c.author_id,
    authorName=user.name,
    body=c.body,
    source=getattr(c, "source", "app"),
    sourceId=getattr(c, "source_id", None),
    sourceAuthor=getattr(c, "source_author", None),
    sourceUrl=getattr(c, "source_url", None),
    createdAt=c.created_at,
  )


@router.patch("/comments/{comment_id}", response_model=CommentOut)
async def update_comment(comment_id: str, payload: CommentCreateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentOut:
  cres = await db.execute(select(Comment).where(Comment.id == comment_id))
  c = cres.scalar_one_or_none()
  if not c:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
  tres = await db.execute(select(Task).where(Task.id == c.task_id))
  t = tres.scalar_one()
  await require_board_role(t.board_id, "member", user, db)
  c.body = payload.body
  await write_audit(
    db,
    event_type="comment.updated",
    entity_type="Comment",
    entity_id=c.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"body": payload.body[:500]},
  )
  await db.commit()
  # author is unchanged; lookup is cheap enough for MVP.
  ures = await db.execute(select(User).where(User.id == c.author_id))
  au = ures.scalar_one()
  return CommentOut(
    id=c.id,
    taskId=c.task_id,
    authorId=c.author_id,
    authorName=au.name,
    body=c.body,
    source=getattr(c, "source", "app"),
    sourceId=getattr(c, "source_id", None),
    sourceAuthor=getattr(c, "source_author", None),
    sourceUrl=getattr(c, "source_url", None),
    createdAt=c.created_at,
  )


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  cres = await db.execute(select(Comment).where(Comment.id == comment_id))
  c = cres.scalar_one_or_none()
  if not c:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
  tres = await db.execute(select(Task).where(Task.id == c.task_id))
  t = tres.scalar_one()
  await require_board_role(t.board_id, "member", user, db)
  await db.execute(delete(Comment).where(Comment.id == comment_id))
  await write_audit(
    db,
    event_type="comment.deleted",
    entity_type="Comment",
    entity_id=comment_id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"commentId": comment_id},
  )
  await db.commit()
  return {"ok": True}


@router.get("/tasks/{task_id}/dependencies")
async def list_dependencies(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  dres = await db.execute(select(TaskDependency).where(TaskDependency.task_id == task_id).order_by(TaskDependency.created_at.asc()))
  deps = dres.scalars().all()
  return [{"id": d.id, "taskId": d.task_id, "dependsOnTaskId": d.depends_on_task_id, "createdAt": d.created_at} for d in deps]


@router.post("/tasks/{task_id}/dependencies")
async def add_dependency(task_id: str, payload: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  depends_on = payload.get("dependsOnTaskId")
  if not depends_on:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="dependsOnTaskId is required")
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  other = await db.execute(select(Task).where(Task.id == depends_on))
  ot = other.scalar_one_or_none()
  if not ot or ot.board_id != t.board_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid dependency task id")
  d = TaskDependency(task_id=task_id, depends_on_task_id=depends_on)
  db.add(d)
  await write_audit(
    db,
    event_type="dependency.added",
    entity_type="TaskDependency",
    entity_id=d.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"dependsOnTaskId": depends_on},
  )
  await db.commit()
  return {"ok": True, "dependencyId": d.id}


@router.delete("/dependencies/{dep_id}")
async def delete_dependency(dep_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  dres = await db.execute(select(TaskDependency).where(TaskDependency.id == dep_id))
  d = dres.scalar_one_or_none()
  if not d:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
  tres = await db.execute(select(Task).where(Task.id == d.task_id))
  t = tres.scalar_one()
  await require_board_role(t.board_id, "member", user, db)
  await db.execute(delete(TaskDependency).where(TaskDependency.id == dep_id))
  await write_audit(
    db,
    event_type="dependency.deleted",
    entity_type="TaskDependency",
    entity_id=dep_id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"dependencyId": dep_id},
  )
  await db.commit()
  return {"ok": True}


@router.get("/tasks/{task_id}/checklist", response_model=list[ChecklistOut])
async def list_checklist(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[ChecklistOut]:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  res = await db.execute(select(ChecklistItem).where(ChecklistItem.task_id == task_id).order_by(ChecklistItem.position.asc()))
  return [ChecklistOut(id=i.id, taskId=i.task_id, text=i.text, done=i.done, position=i.position) for i in res.scalars().all()]


@router.post("/tasks/{task_id}/checklist", response_model=ChecklistOut)
async def create_checklist_item(
  task_id: str,
  payload: ChecklistCreateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> ChecklistOut:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)
  res = await db.execute(select(func.max(ChecklistItem.position)).where(ChecklistItem.task_id == task_id))
  max_pos = res.scalar_one()
  pos = (max_pos + 1) if max_pos is not None else 0
  i = ChecklistItem(task_id=task_id, text=payload.text, done=False, position=pos)
  db.add(i)
  await write_audit(
    db, event_type="checklist.created", entity_type="ChecklistItem", entity_id=i.id, board_id=t.board_id, task_id=t.id, actor_id=user.id, payload={}
  )
  await db.commit()
  return ChecklistOut(id=i.id, taskId=i.task_id, text=i.text, done=i.done, position=i.position)


@router.patch("/checklist/{item_id}", response_model=ChecklistOut)
async def update_checklist_item(item_id: str, payload: ChecklistUpdateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ChecklistOut:
  ires = await db.execute(select(ChecklistItem).where(ChecklistItem.id == item_id))
  i = ires.scalar_one_or_none()
  if not i:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist item not found")
  tres = await db.execute(select(Task).where(Task.id == i.task_id))
  t = tres.scalar_one()
  await require_board_role(t.board_id, "member", user, db)

  if payload.text is not None:
    i.text = payload.text
  if payload.done is not None:
    i.done = payload.done
  await write_audit(
    db,
    event_type="checklist.updated",
    entity_type="ChecklistItem",
    entity_id=i.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"text": i.text[:200], "done": i.done},
  )
  await db.commit()
  return ChecklistOut(id=i.id, taskId=i.task_id, text=i.text, done=i.done, position=i.position)


@router.delete("/checklist/{item_id}")
async def delete_checklist_item(item_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  ires = await db.execute(select(ChecklistItem).where(ChecklistItem.id == item_id))
  i = ires.scalar_one_or_none()
  if not i:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist item not found")
  tres = await db.execute(select(Task).where(Task.id == i.task_id))
  t = tres.scalar_one()
  await require_board_role(t.board_id, "member", user, db)
  await db.execute(delete(ChecklistItem).where(ChecklistItem.id == item_id))
  await write_audit(
    db,
    event_type="checklist.deleted",
    entity_type="ChecklistItem",
    entity_id=item_id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={"checklistItemId": item_id},
  )
  await db.commit()
  return {"ok": True}


@router.get("/tasks/{task_id}/attachments", response_model=list[AttachmentOut])
async def list_attachments(task_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[AttachmentOut]:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  res = await db.execute(select(Attachment).where(Attachment.task_id == task_id).order_by(Attachment.created_at.asc()))
  out: list[AttachmentOut] = []
  for a in res.scalars().all():
    out.append(
      AttachmentOut(
        id=a.id,
        taskId=a.task_id,
        filename=a.filename,
        mime=a.mime,
        sizeBytes=a.size_bytes,
        url=f"/attachments/{a.id}",
        createdAt=a.created_at,
      )
    )
  return out


@router.get("/attachments/{attachment_id}")
async def get_attachment(attachment_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> FileResponse:
  ares = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
  a = ares.scalar_one_or_none()
  if not a:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
  tres = await db.execute(select(Task).where(Task.id == a.task_id))
  t = tres.scalar_one()
  await require_board_role(t.board_id, "viewer", user, db)
  return FileResponse(path=a.path, media_type=a.mime, filename=a.filename)


@router.post("/tasks/{task_id}/attachments")
async def upload_attachment(
  task_id: str,
  file: UploadFile = File(...),
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "member", user, db)

  os.makedirs("data/uploads", exist_ok=True)
  ext = os.path.splitext(file.filename or "")[1]
  out_name = f"{uuid.uuid4().hex}{ext}"
  out_path = os.path.join("data/uploads", out_name)
  data = await file.read(int(settings.max_attachment_bytes) + 1)
  if len(data) > int(settings.max_attachment_bytes):
    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Attachment too large")
  with open(out_path, "wb") as f:
    f.write(data)
  a = Attachment(
    task_id=task_id,
    filename=file.filename or out_name,
    mime=file.content_type or "application/octet-stream",
    size_bytes=len(data),
    path=out_path,
  )
  db.add(a)
  await write_audit(
    db, event_type="attachment.added", entity_type="Attachment", entity_id=a.id, board_id=t.board_id, task_id=t.id, actor_id=user.id, payload={"filename": a.filename}
  )
  await db.commit()
  return {"ok": True, "attachmentId": a.id}
