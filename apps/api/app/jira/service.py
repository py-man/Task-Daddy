from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dateutil import parser as dateparser
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.config import settings
from app.jira.client import (
  JiraApiError,
  JiraAuth,
  jira_create_issue,
  jira_get_issue,
  jira_add_comment,
  jira_list_comments,
  jira_search_jql,
  jira_search_users,
  jira_set_assignee,
  normalize_base_url,
  plain_text_from_adf,
)
from app.models import JiraConnection, JiraSyncProfile, Lane, SyncRun, Task
from app.security import decrypt_integration_secret


def _log(run: SyncRun, level: str, message: str) -> None:
  run.log = list(run.log or []) + [{"at": datetime.now(timezone.utc).isoformat(), "level": level, "message": message}]


def _error_text(exc: Exception) -> str:
  message = str(exc).strip()
  if message:
    return f"{exc.__class__.__name__}: {message}"
  return exc.__class__.__name__


def _jira_labelize(raw: str) -> str | None:
  s = (raw or "").strip().lower()
  if not s:
    return None
  # Jira label rules: no spaces, restricted charset; keep MVP simple.
  s = s.replace(" ", "-")
  out = []
  for ch in s:
    if ch.isalnum() or ch in ("-", "_", "."):
      out.append(ch)
  label = "".join(out).strip("-. _")
  if not label:
    return None
  return label[:50]


async def _get_or_create_jira_bot_user_id(db: AsyncSession) -> str:
  from app.models import User
  from app.security import hash_password

  email = "jira@taskdaddy.local"
  res = await db.execute(select(User).where(User.email == email))
  u = res.scalar_one_or_none()
  if u:
    return u.id
  u = User(email=email, name="Jira", password_hash=hash_password("disabled"), role="viewer", avatar_url=None)
  db.add(u)
  await db.flush()
  return u.id


async def _import_jira_comments(
  db: AsyncSession,
  *,
  task: Task,
  auth: JiraAuth,
  actor_id: str | None,
) -> int:
  from app.models import Comment

  jira_comments = await jira_list_comments(auth=auth, key=task.jira_key or "")
  if not jira_comments:
    return 0

  ids: list[str] = []
  for c in jira_comments:
    cid = c.get("id")
    if isinstance(cid, str) and cid.strip():
      ids.append(cid.strip())
  if not ids:
    return 0

  existing_res = await db.execute(
    select(Comment.source_id).where(and_(Comment.task_id == task.id, Comment.source == "jira", Comment.source_id.in_(ids)))
  )
  existing_ids = set([x for x in existing_res.scalars().all() if x])

  bot_id = await _get_or_create_jira_bot_user_id(db)
  inserted = 0
  for c in jira_comments:
    cid = c.get("id")
    if not isinstance(cid, str) or not cid.strip() or cid.strip() in existing_ids:
      continue
    author = c.get("author") or {}
    author_name = None
    if isinstance(author, dict):
      author_name = author.get("displayName") or author.get("emailAddress") or author.get("accountId")
    created = c.get("created")
    created_at: datetime | None = None
    try:
      created_at = dateparser.parse(created).astimezone(timezone.utc) if created else None
    except Exception:
      created_at = None

    body = c.get("body")
    body_text = ""
    if isinstance(body, (dict, list)):
      body_text = plain_text_from_adf(body)
    elif isinstance(body, str):
      body_text = body
    body_text = (body_text or "").replace("\r\n", "\n").strip()
    if not body_text:
      continue
    ts = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    author_disp = (str(author_name).strip() if isinstance(author_name, str) and author_name.strip() else "Unknown")
    body_text = f"JIRA:>> [{ts}] {author_disp}: {body_text}"

    db.add(
      Comment(
        task_id=task.id,
        author_id=bot_id,
        body=body_text[:20000],
        source="jira",
        source_id=cid.strip(),
        source_author=str(author_name).strip() if author_name else None,
        source_url=(f"{task.jira_url}?focusedCommentId={cid}" if task.jira_url else None),
        created_at=created_at or datetime.now(timezone.utc),
      )
    )
    existing_ids.add(cid.strip())
    inserted += 1

  if inserted:
    await write_audit(
      db,
      event_type="task.jira.comments.pulled",
      entity_type="Task",
      entity_id=task.id,
      board_id=task.board_id,
      task_id=task.id,
      actor_id=actor_id,
      payload={"jiraKey": task.jira_key, "inserted": inserted},
    )
  return inserted


async def _export_task_comments_to_jira(
  db: AsyncSession,
  *,
  task: Task,
  auth: JiraAuth,
  actor_id: str | None,
) -> int:
  from app.models import Comment, User

  if not task.jira_key:
    return 0
  # Export only app-authored comments not yet exported.
  res = await db.execute(
    select(Comment, User)
    .join(User, User.id == Comment.author_id)
    .where(and_(Comment.task_id == task.id, Comment.source == "app", Comment.jira_comment_id.is_(None)))
    .order_by(Comment.created_at.asc())
  )
  rows = res.all()
  comments = [c for c, _ in rows]
  if not comments:
    return 0

  exported = 0
  for (c, u) in rows:
    ts = (c.created_at or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    header = f"NEONLANES:>> [{ts}] {u.name}:"
    marker = f"Task-Daddy commentId={c.id}"
    body = f"{header}\n{marker}\n\n{(c.body or '').strip()}".strip()
    try:
      created = await jira_add_comment(auth=auth, key=task.jira_key, text=body)
      cid = created.get("id")
      if isinstance(cid, str) and cid.strip():
        c.jira_comment_id = cid.strip()
        c.jira_exported_at = datetime.now(timezone.utc)
        exported += 1
    except Exception:
      # Do not fail the whole sync for a single comment.
      continue

  if exported:
    await write_audit(
      db,
      event_type="task.jira.comments.pushed",
      entity_type="Task",
      entity_id=task.id,
      board_id=task.board_id,
      task_id=task.id,
      actor_id=actor_id,
      payload={"jiraKey": task.jira_key, "exported": exported},
    )
  return exported


async def create_connection(db: AsyncSession, *, base_url: str, email: str | None, token_encrypted: str) -> JiraConnection:
  conn = JiraConnection(base_url=normalize_base_url(base_url), email=email, token_encrypted=token_encrypted)
  db.add(conn)
  await db.flush()
  return conn


async def create_connection_named(
  db: AsyncSession,
  *,
  name: str | None,
  base_url: str,
  email: str | None,
  token_encrypted: str,
  default_assignee_account_id: str | None = None,
) -> JiraConnection:
  conn = JiraConnection(
    name=(name or "").strip() or None,
    base_url=normalize_base_url(base_url),
    email=email,
    token_encrypted=token_encrypted,
    default_assignee_account_id=(default_assignee_account_id or "").strip() or None,
  )
  db.add(conn)
  await db.flush()
  return conn


async def _get_auth(db: AsyncSession, *, connection_id: str) -> tuple[JiraConnection, JiraAuth]:
  res = await db.execute(select(JiraConnection).where(JiraConnection.id == connection_id))
  connection = res.scalar_one()
  token = decrypt_integration_secret(connection.token_encrypted)
  auth = JiraAuth(
    base_url=normalize_base_url(connection.base_url),
    email=connection.email,
    token=token,
    user_agent=settings.jira_user_agent,
  )
  return connection, auth


async def link_task_to_jira_issue(
  db: AsyncSession,
  *,
  task: Task,
  connection_id: str,
  jira_key: str,
  enable_sync: bool = True,
  actor_id: str | None,
) -> Task:
  connection, _ = await _get_auth(db, connection_id=connection_id)
  task.jira_connection_id = connection.id
  task.jira_key = jira_key
  task.jira_url = f"{connection.base_url.rstrip('/')}/browse/{jira_key}"
  task.jira_sync_enabled = bool(enable_sync)
  task.jira_last_sync_at = datetime.now(timezone.utc)
  task.version += 1
  await write_audit(
    db,
    event_type="task.jira.linked",
    entity_type="Task",
    entity_id=task.id,
    board_id=task.board_id,
    task_id=task.id,
    actor_id=actor_id,
    payload={"jiraKey": jira_key, "connectionId": connection_id, "enableSync": enable_sync},
  )
  return task


async def create_jira_issue_from_task(
  db: AsyncSession,
  *,
  task: Task,
  connection_id: str,
  project_key: str,
  issue_type: str | None,
  enable_sync: bool = True,
  assignee_mode: str = "taskOwner",
  actor_id: str | None,
) -> Task:
  # Idempotent: if already linked, do nothing.
  if task.jira_key:
    return task

  connection, auth = await _get_auth(db, connection_id=connection_id)

  labels = [x for x in (_jira_labelize(t) for t in (task.tags or [])) if x]
  # Stable label for traceability + a hard idempotency key.
  id_label = f"task-daddy-task-{task.id}"
  labels = list({*labels, "task-daddy", id_label})

  # Strong idempotency: if the task somehow lost its link but an issue exists, re-link.
  try:
    found = await jira_search_jql(auth=auth, jql=f'labels = "{id_label}"', max_results=2, fields=["summary", "status", "updated"])
    issues = found.get("issues") or []
    if issues:
      key = issues[0].get("key")
      if key:
        task.jira_connection_id = connection.id
        task.jira_key = str(key)
        task.jira_url = f"{connection.base_url.rstrip('/')}/browse/{task.jira_key}"
        task.jira_sync_enabled = bool(enable_sync)
        task.jira_project_key = project_key
        task.jira_issue_type = issue_type or "Task"
        task.jira_last_sync_at = datetime.now(timezone.utc)
        task.version += 1
        await write_audit(
          db,
          event_type="task.jira.relinked",
          entity_type="Task",
          entity_id=task.id,
          board_id=task.board_id,
          task_id=task.id,
          actor_id=actor_id,
          payload={"jiraKey": task.jira_key},
        )
        return task
  except Exception:
    # Non-fatal; proceed to create.
    pass

  priority_map = {"P0": "Highest", "P1": "High", "P2": "Medium", "P3": "Low"}
  jira_priority = priority_map.get(task.priority or "P2", "High")

  async def _resolve_assignee_account_id() -> str | None:
    if assignee_mode in ("unassigned", "projectDefault"):
      return None
    if assignee_mode == "connectionDefault":
      cid = (getattr(connection, "default_assignee_account_id", None) or "").strip()
      return cid or (settings.jira_default_assignee_account_id or "").strip() or None
    if assignee_mode != "taskOwner":
      return None
    if not task.owner_id:
      return None
    try:
      from app.models import User

      ures = await db.execute(select(User).where(User.id == task.owner_id))
      u = ures.scalar_one_or_none()
      if not u:
        return None
      # Prefer explicit Jira accountId stored in the user profile (email may be hidden in Jira Cloud).
      if getattr(u, "jira_account_id", None):
        return str(u.jira_account_id)
      if u.email:
        users = await jira_search_users(auth=auth, query=u.email, max_results=5)
        for cand in users:
          if isinstance(cand, dict) and cand.get("accountId"):
            return str(cand.get("accountId"))
    except Exception:
      return None
    return None

  assignee_account_id = await _resolve_assignee_account_id()

  try:
    created = await jira_create_issue(
      auth=auth,
      project_key=project_key,
      summary=task.title,
      description=task.description or "",
      issue_type=issue_type or "Task",
      labels=labels,
      priority_name=jira_priority,
      assignee_account_id=assignee_account_id,
    )
  except JiraApiError as e:
    # Some Jira instances restrict fields (priority/issuetype); retry with fewer fields.
    if e.status_code == 400:
      # Retry with fewer fields; if assignment caused the error, retry without assignee.
      try:
        created = await jira_create_issue(
          auth=auth,
          project_key=project_key,
          summary=task.title,
          description=task.description or "",
          issue_type=issue_type or "Task",
          labels=labels,
          priority_name=None,
          assignee_account_id=assignee_account_id,
        )
      except JiraApiError:
        created = await jira_create_issue(
          auth=auth,
          project_key=project_key,
          summary=task.title,
          description=task.description or "",
          issue_type=issue_type or "Task",
          labels=labels,
          priority_name=None,
          assignee_account_id=None,
        )
    else:
      raise
  jira_key = created.get("key")
  if not jira_key:
    # Jira returns {"id": "...", "key": "...", "self": "..."} on success.
    raise RuntimeError("Jira create issue succeeded but did not return key")

  task.jira_connection_id = connection.id
  task.jira_key = str(jira_key)
  task.jira_url = f"{connection.base_url.rstrip('/')}/browse/{jira_key}"
  task.jira_sync_enabled = bool(enable_sync)
  task.jira_project_key = project_key
  task.jira_issue_type = issue_type or "Task"
  task.jira_last_sync_at = datetime.now(timezone.utc)
  task.version += 1

  # Best-effort assignment fallback: in case the Jira instance ignores assignee on create.
  if assignee_mode == "unassigned":
    try:
      await jira_set_assignee(auth=auth, key=task.jira_key, account_id=None)
    except JiraApiError as e:
      await write_audit(
        db,
        event_type="task.jira.assign_failed",
        entity_type="Task",
        entity_id=task.id,
        board_id=task.board_id,
        task_id=task.id,
        actor_id=actor_id,
        payload={"jiraKey": task.jira_key, "assigneeMode": assignee_mode, "statusCode": e.status_code, "message": e.message},
      )
  elif assignee_account_id:
    try:
      await jira_set_assignee(auth=auth, key=task.jira_key, account_id=assignee_account_id)
    except JiraApiError as e:
      await write_audit(
        db,
        event_type="task.jira.assign_failed",
        entity_type="Task",
        entity_id=task.id,
        board_id=task.board_id,
        task_id=task.id,
        actor_id=actor_id,
        payload={
          "jiraKey": task.jira_key,
          "assigneeMode": assignee_mode,
          "assigneeAccountId": assignee_account_id,
          "statusCode": e.status_code,
          "message": e.message,
        },
      )

  await write_audit(
    db,
    event_type="task.jira.created",
    entity_type="Task",
    entity_id=task.id,
    board_id=task.board_id,
    task_id=task.id,
    actor_id=actor_id,
    payload={
      "jiraKey": task.jira_key,
      "projectKey": project_key,
      "issueType": task.jira_issue_type,
      "enableSync": enable_sync,
      "assigneeMode": assignee_mode,
      "assigneeAccountId": assignee_account_id,
    },
  )
  return task


async def get_task_jira_issue(db: AsyncSession, *, task: Task) -> dict:
  if not task.jira_connection_id or not task.jira_key:
    return {"linked": False}
  _, auth = await _get_auth(db, connection_id=task.jira_connection_id)
  issue = await jira_get_issue(auth=auth, key=task.jira_key)
  return {"linked": True, "issue": issue}


async def pull_task_from_jira(db: AsyncSession, *, task: Task, actor_id: str | None) -> Task:
  if not task.jira_connection_id or not task.jira_key:
    raise RuntimeError("Task is not linked to Jira")
  connection, auth = await _get_auth(db, connection_id=task.jira_connection_id)
  issue = await jira_get_issue(auth=auth, key=task.jira_key)
  fields: dict[str, Any] = issue.get("fields") or {}

  summary = fields.get("summary") or task.title
  description = fields.get("description")
  labels = fields.get("labels") or []
  due = fields.get("duedate")
  updated_at = fields.get("updated")

  task.title = str(summary)[:500]
  if isinstance(description, (dict, list)):
    task.description = plain_text_from_adf(description)
  elif isinstance(description, str):
    task.description = description

  task.tags = list(labels)
  task.due_date = dateparser.parse(due).astimezone(timezone.utc) if due else None
  task.jira_url = f"{connection.base_url.rstrip('/')}/browse/{task.jira_key}"
  task.jira_updated_at = dateparser.parse(updated_at).astimezone(timezone.utc) if updated_at else task.jira_updated_at
  task.jira_last_sync_at = datetime.now(timezone.utc)
  task.version += 1

  try:
    await _import_jira_comments(db, task=task, auth=auth, actor_id=actor_id)
  except Exception:
    # Non-fatal: issue sync is still useful even if comments fail.
    pass

  await write_audit(
    db,
    event_type="task.jira.pulled",
    entity_type="Task",
    entity_id=task.id,
    board_id=task.board_id,
    task_id=task.id,
    actor_id=actor_id,
    payload={"jiraKey": task.jira_key},
  )
  return task


async def sync_task_with_jira(db: AsyncSession, *, task: Task, actor_id: str | None) -> Task:
  if not task.jira_connection_id or not task.jira_key:
    raise RuntimeError("Task is not linked to Jira")
  _, auth = await _get_auth(db, connection_id=task.jira_connection_id)
  # Pull latest issue fields + import Jira comments.
  await pull_task_from_jira(db, task=task, actor_id=actor_id)
  # Push local comments to Jira (idempotent via jira_comment_id).
  await _export_task_comments_to_jira(db, task=task, auth=auth, actor_id=actor_id)
  task.jira_last_sync_at = datetime.now(timezone.utc)
  return task


async def import_issues_to_board(
  db: AsyncSession,
  *,
  board_id: str,
  connection: JiraConnection,
  jql: str,
  status_to_state_key: dict[str, str],
  priority_map: dict[str, str],
  type_map: dict[str, str],
  conflict_policy: str,
  actor_id: str | None,
) -> tuple[JiraSyncProfile, SyncRun]:
  profile = JiraSyncProfile(
    board_id=board_id,
    connection_id=connection.id,
    jql=jql,
    status_to_state_key=status_to_state_key,
    priority_map=priority_map,
    type_map=type_map,
    conflict_policy=conflict_policy,
  )
  db.add(profile)
  await db.flush()

  run = SyncRun(board_id=board_id, profile_id=profile.id, status="success", log=[])
  db.add(run)
  await db.flush()

  await write_audit(
    db,
    event_type="jira.import.started",
    entity_type="SyncRun",
    entity_id=run.id,
    board_id=board_id,
    actor_id=actor_id,
    payload={"jql": jql},
  )

  await _run_sync(db, profile=profile, connection=connection, run=run, actor_id=actor_id)
  return profile, run


async def sync_now(db: AsyncSession, *, profile: JiraSyncProfile, actor_id: str | None) -> SyncRun:
  cres = await db.execute(select(JiraConnection).where(JiraConnection.id == profile.connection_id))
  connection = cres.scalar_one()
  run = SyncRun(board_id=profile.board_id, profile_id=profile.id, status="success", log=[])
  db.add(run)
  await db.flush()
  await write_audit(
    db,
    event_type="jira.sync.started",
    entity_type="SyncRun",
    entity_id=run.id,
    board_id=profile.board_id,
    actor_id=actor_id,
    payload={"profileId": profile.id},
  )
  await _run_sync(db, profile=profile, connection=connection, run=run, actor_id=actor_id)
  return run


async def _run_sync(
  db: AsyncSession,
  *,
  profile: JiraSyncProfile,
  connection: JiraConnection,
  run: SyncRun,
  actor_id: str | None,
) -> None:
  started = datetime.now(timezone.utc)
  run.started_at = started

  try:
    token = decrypt_integration_secret(connection.token_encrypted)
    auth = JiraAuth(base_url=normalize_base_url(connection.base_url), email=connection.email, token=token, user_agent=settings.jira_user_agent)

    lanes_res = await db.execute(select(Lane).where(Lane.board_id == profile.board_id).order_by(Lane.position.asc()))
    lanes = lanes_res.scalars().all()
    lane_by_state = {l.state_key: l for l in lanes}
    backlog_lane = next((l for l in lanes if l.type == "backlog"), lanes[0] if lanes else None)
    if not backlog_lane:
      raise RuntimeError("Board has no lanes")

    imported = 0
    updated = 0
    conflicts = 0
    next_token: str | None = None
    while True:
      data = await jira_search_jql(auth=auth, jql=profile.jql, max_results=50, next_page_token=next_token)
      issues = data.get("issues") or []
      if not issues:
        break
      for issue in issues:
        key = issue.get("key")
        fields: dict[str, Any] = issue.get("fields") or {}
        summary = fields.get("summary") or key
        status_name = ((fields.get("status") or {}).get("name")) or ""
        state_key = (profile.status_to_state_key or {}).get(status_name) or ""
        lane = lane_by_state.get(state_key) if state_key else None
        if not lane:
          lane = backlog_lane
          state_key = lane.state_key

        priority_name = ((fields.get("priority") or {}).get("name")) or ""
        issue_type = ((fields.get("issuetype") or {}).get("name")) or ""
        labels = fields.get("labels") or []
        due = fields.get("duedate")
        updated_at = fields.get("updated")

        mapped_priority = (profile.priority_map or {}).get(priority_name) or "P2"
        mapped_type = (profile.type_map or {}).get(issue_type) or "Feature"
        due_dt = dateparser.parse(due).astimezone(timezone.utc) if due else None
        jira_updated_dt = dateparser.parse(updated_at).astimezone(timezone.utc) if updated_at else None

        jira_url = f"{connection.base_url.rstrip('/')}/browse/{key}" if key else None

        tres = await db.execute(
          select(Task)
          .where(and_(Task.board_id == profile.board_id, Task.jira_key == key))
          .order_by(Task.updated_at.desc(), Task.created_at.desc(), Task.id.desc())
        )
        matches = tres.scalars().all()
        existing = matches[0] if matches else None
        if len(matches) > 1:
          conflicts += 1
          _log(run, "warn", f"Duplicate Jira key mapping detected for {key}; using task {existing.id}")

        if existing is None:
          # naive ordering: append to lane
          ores = await db.execute(
            select(func.max(Task.order_index)).where(Task.board_id == profile.board_id, Task.lane_id == lane.id)
          )
          max_order = ores.scalar_one_or_none()
          new_order = (max_order + 1) if max_order is not None else 0
          t = Task(
            board_id=profile.board_id,
            lane_id=lane.id,
            state_key=state_key,
            title=summary,
            description="",
            owner_id=None,
            priority=mapped_priority,
            type=mapped_type,
            tags=list(labels),
            due_date=due_dt,
            blocked=False,
            blocked_reason=None,
            jira_key=key,
            jira_url=jira_url,
            jira_updated_at=jira_updated_dt,
            jira_last_sync_at=datetime.now(timezone.utc),
            order_index=new_order,
            version=0,
          )
          db.add(t)
          imported += 1
          _log(run, "info", f"Imported {key} -> {t.id} lane={lane.name}")
          await write_audit(
            db,
            event_type="task.imported",
            entity_type="Task",
            entity_id=t.id,
            board_id=profile.board_id,
            task_id=t.id,
            actor_id=actor_id,
            payload={"jiraKey": key, "status": status_name},
          )
          continue

        last_sync = existing.jira_last_sync_at
        app_changed = last_sync is not None and existing.updated_at and existing.updated_at > last_sync
        jira_changed = last_sync is not None and jira_updated_dt is not None and jira_updated_dt > last_sync
        if app_changed and jira_changed:
          conflicts += 1
          _log(run, "warn", f"Conflict on {key} (policy={profile.conflict_policy})")

        if profile.conflict_policy == "jiraWins":
          existing.title = summary
          existing.priority = mapped_priority
          existing.type = mapped_type
          existing.tags = list(labels)
          existing.due_date = due_dt
          existing.jira_url = jira_url
          existing.jira_updated_at = jira_updated_dt
          if existing.lane_id != lane.id:
            existing.lane_id = lane.id
            existing.state_key = state_key
          existing.jira_last_sync_at = datetime.now(timezone.utc)
          existing.version += 1
          updated += 1
          _log(run, "info", f"Updated {key} -> {existing.id}")

      next_token = data.get("nextPageToken")
      is_last = bool(data.get("isLast")) or not next_token
      if is_last:
        break

    run.status = "success"
    run.finished_at = datetime.now(timezone.utc)
    _log(run, "info", f"Done imported={imported} updated={updated} conflicts={conflicts}")
    await write_audit(
      db,
      event_type="jira.sync.completed",
      entity_type="SyncRun",
      entity_id=run.id,
      board_id=profile.board_id,
      actor_id=actor_id,
      payload={"imported": imported, "updated": updated, "conflicts": conflicts},
    )
  except Exception as e:
    err = _error_text(e)
    run.status = "error"
    run.error_message = err
    run.finished_at = datetime.now(timezone.utc)
    _log(run, "error", f"Sync error: {err}")
    await write_audit(
      db,
      event_type="jira.sync.error",
      entity_type="SyncRun",
      entity_id=run.id,
      board_id=profile.board_id,
      actor_id=actor_id,
      payload={"error": err},
    )
