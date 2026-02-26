from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.deps import get_current_user, get_db
from app.models import Board, BoardMember, Comment, InboundWebhookEvent, Lane, Task, User, WebhookSecret
from app.schemas import WebhookEventOut, WebhookInboundOut, WebhookSecretOut, WebhookSecretRevealOut, WebhookSecretUpsertIn
from app.security import decrypt_integration_secret, encrypt_secret

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _require_admin(user: User) -> None:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


def _token_hint(token: str) -> str:
  t = token.strip()
  if len(t) <= 8:
    return "****"
  return f"****{t[-4:]}"


async def _get_secret(db: AsyncSession, source: str) -> WebhookSecret | None:
  res = await db.execute(select(WebhookSecret).where(WebhookSecret.source == source))
  return res.scalar_one_or_none()


async def _verify_bearer(db: AsyncSession, *, source: str, auth_header: str | None) -> None:
  secret = await _get_secret(db, source)
  if not secret or not secret.enabled:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook not configured")
  if not auth_header or not auth_header.lower().startswith("bearer "):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
  provided = auth_header.split(" ", 1)[1].strip()
  expected = decrypt_integration_secret(secret.bearer_token_encrypted)
  if not secrets.compare_digest(provided, expected):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")


def _safe_headers(headers: dict[str, str]) -> dict[str, Any]:
  out: dict[str, Any] = {}
  for k, v in headers.items():
    lk = k.lower()
    if lk in ("authorization", "cookie", "set-cookie"):
      continue
    out[k] = v
  return out


def _parse_due_date(v: Any) -> datetime | None:
  if v is None:
    return None
  if isinstance(v, datetime):
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
  if isinstance(v, str):
    s = v.strip()
    if not s:
      return None
    try:
      dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
      return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
      return None
  return None


def _as_priority(v: Any) -> str:
  s = str(v or "P2").strip().upper()
  return s if s in ("P0", "P1", "P2", "P3") else "P2"


def _as_type(v: Any) -> str:
  s = str(v or "Feature").strip()
  allowed = {"Bug", "Feature", "Ops", "Risk", "Debt", "Spike", "Support"}
  return s if s in allowed else "Feature"


async def _find_board_by_name(db: AsyncSession, name: str) -> Board | None:
  norm = name.strip().lower()
  if not norm:
    return None
  res = await db.execute(select(Board).where(func.lower(func.btrim(Board.name)) == norm))
  return res.scalar_one_or_none()


async def _find_lane_by_name(db: AsyncSession, board_id: str, lane_name: str) -> Lane | None:
  norm = lane_name.strip().lower()
  if not norm:
    return None
  res = await db.execute(
    select(Lane).where(Lane.board_id == board_id, func.lower(func.btrim(Lane.name)) == norm).order_by(Lane.position.asc())
  )
  return res.scalar_one_or_none()


async def _default_lane(db: AsyncSession, board_id: str) -> Lane:
  res = await db.execute(select(Lane).where(Lane.board_id == board_id).order_by(Lane.position.asc()))
  lanes = res.scalars().all()
  if not lanes:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Board has no lanes")
  backlog = next((l for l in lanes if l.type == "backlog"), None)
  return backlog or lanes[0]


async def _board_member_user_ids(db: AsyncSession, board_id: str) -> set[str]:
  res = await db.execute(select(BoardMember.user_id).where(BoardMember.board_id == board_id))
  return set([x for x in res.scalars().all() if x])


async def _process_action(db: AsyncSession, *, source: str, payload: dict[str, Any], event_id: str) -> dict[str, Any]:
  action = (payload.get("action") or "").strip()
  if action not in ("create_task", "comment_task", "move_task"):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown action")

  if action == "create_task":
    title = (payload.get("title") or "").strip()
    board_name = (payload.get("boardName") or "").strip()
    if not title:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title is required")
    if not board_name:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="boardName is required")
    board = await _find_board_by_name(db, board_name)
    if not board:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="board not found")

    lane: Lane | None = None
    if payload.get("laneName"):
      lane = await _find_lane_by_name(db, board.id, str(payload.get("laneName")))
    if not lane:
      lane = await _default_lane(db, board.id)

    owner_id: str | None = None
    owner_email = (payload.get("ownerEmail") or "").strip().lower()
    if owner_email:
      ures = await db.execute(select(User).where(func.lower(User.email) == owner_email))
      u = ures.scalar_one_or_none()
      if u:
        member_ids = await _board_member_user_ids(db, board.id)
        if u.id in member_ids:
          owner_id = u.id

    # compute order at end of lane
    ores = await db.execute(select(func.max(Task.order_index)).where(Task.board_id == board.id, Task.lane_id == lane.id))
    max_order = ores.scalar_one()
    order_index = (max_order + 1) if max_order is not None else 0

    t = Task(
      board_id=board.id,
      lane_id=lane.id,
      state_key=lane.state_key,
      title=title,
      description=str(payload.get("description") or ""),
      owner_id=owner_id,
      priority=_as_priority(payload.get("priority")),
      type=_as_type(payload.get("type")),
      tags=list(payload.get("tags") or []),
      due_date=_parse_due_date(payload.get("dueDate")),
      estimate_minutes=payload.get("estimateMinutes"),
      blocked=bool(payload.get("blocked") or False),
      blocked_reason=payload.get("blockedReason"),
      order_index=order_index,
      version=0,
    )
    db.add(t)
    await write_audit(
      db,
      event_type="webhook.task.created",
      entity_type="Task",
      entity_id=t.id,
      board_id=board.id,
      task_id=t.id,
      actor_id=None,
      payload={"source": source, "eventId": event_id},
    )
    await db.flush()
    return {"taskId": t.id, "boardId": board.id, "laneId": lane.id, "ownerId": owner_id}

  if action == "comment_task":
    body = (payload.get("body") or "").strip()
    if not body:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="body is required")

    task_id = (payload.get("taskId") or "").strip()
    jira_key = (payload.get("jiraKey") or "").strip()
    if not task_id and not jira_key:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="taskId or jiraKey is required")

    if task_id:
      tres = await db.execute(select(Task).where(Task.id == task_id))
    else:
      tres = await db.execute(select(Task).where(Task.jira_key == jira_key))
    t = tres.scalar_one_or_none()
    if not t:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")

    # Attribute to board owner for now, but preserve original author in source_author.
    bres = await db.execute(select(Board).where(Board.id == t.board_id))
    b = bres.scalar_one()
    author_id = b.owner_id

    source_author = (payload.get("author") or payload.get("authorName") or "").strip() or None
    source_id = (payload.get("commentId") or payload.get("id") or payload.get("idempotencyKey") or event_id)
    src = f"webhook:{source}"
    src_id = str(source_id)
    # Idempotency: comment uniqueness is enforced by (task_id, source, source_id).
    # Pre-check to avoid surfacing 500s on duplicates.
    cres = await db.execute(select(Comment).where(Comment.task_id == t.id, Comment.source == src, Comment.source_id == src_id))
    existing = cres.scalar_one_or_none()
    if existing:
      return {"commentId": existing.id, "taskId": t.id, "idempotent": True}

    c = Comment(task_id=t.id, author_id=author_id, body=body, source=src, source_id=src_id, source_author=source_author)
    db.add(c)
    await write_audit(
      db,
      event_type="webhook.comment.created",
      entity_type="Comment",
      entity_id=c.id,
      board_id=t.board_id,
      task_id=t.id,
      actor_id=None,
      payload={"source": source, "eventId": event_id},
    )
    await db.flush()
    return {"commentId": c.id, "taskId": t.id}

  # move_task
  task_id = (payload.get("taskId") or "").strip()
  if not task_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="taskId is required")
  lane_name = (payload.get("laneName") or "").strip()
  if not lane_name:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="laneName is required")
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
  lane = await _find_lane_by_name(db, t.board_id, lane_name)
  if not lane:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lane not found")

  ores = await db.execute(select(func.max(Task.order_index)).where(Task.board_id == t.board_id, Task.lane_id == lane.id))
  max_order = ores.scalar_one()
  t.lane_id = lane.id
  t.state_key = lane.state_key
  t.order_index = (max_order + 1) if max_order is not None else 0
  t.version += 1
  await write_audit(
    db,
    event_type="webhook.task.moved",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=None,
    payload={"source": source, "eventId": event_id, "laneId": lane.id},
  )
  return {"taskId": t.id, "laneId": lane.id}


@router.post("/inbound/{source}", response_model=WebhookInboundOut)
async def inbound(source: str, request: Request, db: AsyncSession = Depends(get_db)) -> WebhookInboundOut:
  await _verify_bearer(db, source=source, auth_header=request.headers.get("authorization"))
  try:
    body = await request.json()
  except Exception:
    body = {}
  if not isinstance(body, dict):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON object body required")

  idempotency_key = request.headers.get("idempotency-key") or (body.get("idempotencyKey") if isinstance(body, dict) else None)
  idempotency_key = str(idempotency_key).strip() if idempotency_key else None

  existing: InboundWebhookEvent | None = None
  if idempotency_key:
    res = await db.execute(
      select(InboundWebhookEvent).where(InboundWebhookEvent.source == source, InboundWebhookEvent.idempotency_key == idempotency_key)
    )
    existing = res.scalar_one_or_none()
    if existing and existing.processed and existing.result is not None and existing.error is None:
      return WebhookInboundOut(eventId=existing.id, idempotentReplay=True, result=existing.result)

  ev = existing or InboundWebhookEvent(
    source=source,
    idempotency_key=idempotency_key,
    headers=_safe_headers(dict(request.headers)),
    body=body,
    received_at=datetime.now(timezone.utc),
    processed=False,
  )
  db.add(ev)
  await db.flush()

  try:
    result = await _process_action(db, source=source, payload=body, event_id=ev.id)
    ev.processed = True
    ev.processed_at = datetime.now(timezone.utc)
    ev.result = result
    ev.error = None
    await db.commit()
    return WebhookInboundOut(eventId=ev.id, idempotentReplay=False, result=result)
  except HTTPException as e:
    ev.processed = True
    ev.processed_at = datetime.now(timezone.utc)
    ev.error = str(e.detail)
    await db.commit()
    raise
  except Exception as e:
    ev.processed = True
    ev.processed_at = datetime.now(timezone.utc)
    ev.error = str(e)
    await db.commit()
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing failed")


@router.get("/secrets", response_model=list[WebhookSecretOut])
async def list_secrets(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[WebhookSecretOut]:
  _require_admin(user)
  res = await db.execute(select(WebhookSecret).order_by(WebhookSecret.source.asc()))
  out: list[WebhookSecretOut] = []
  for s in res.scalars().all():
    out.append(WebhookSecretOut(source=s.source, enabled=s.enabled, tokenHint=s.token_hint, createdAt=s.created_at, updatedAt=s.updated_at))
  return out


@router.post("/secrets", response_model=WebhookSecretRevealOut)
async def upsert_secret(payload: WebhookSecretUpsertIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> WebhookSecretRevealOut:
  _require_admin(user)
  source = payload.source.strip()
  if not source.replace("-", "").replace("_", "").isalnum():
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source")
  token = (payload.bearerToken or "").strip() or secrets.token_urlsafe(32)

  existing = await _get_secret(db, source)
  if existing:
    existing.enabled = bool(payload.enabled)
    existing.bearer_token_encrypted = encrypt_secret(token)
    existing.token_hint = _token_hint(token)
    await write_audit(db, event_type="webhook.secret.updated", entity_type="WebhookSecret", entity_id=existing.id, actor_id=user.id, payload={"source": source})
    await db.commit()
    return WebhookSecretRevealOut(
      secret=WebhookSecretOut(source=existing.source, enabled=existing.enabled, tokenHint=existing.token_hint, createdAt=existing.created_at, updatedAt=existing.updated_at),
      bearerToken=token,
    )

  s = WebhookSecret(
    source=source,
    enabled=bool(payload.enabled),
    bearer_token_encrypted=encrypt_secret(token),
    token_hint=_token_hint(token),
  )
  db.add(s)
  await write_audit(db, event_type="webhook.secret.created", entity_type="WebhookSecret", entity_id=s.id, actor_id=user.id, payload={"source": source})
  await db.commit()
  return WebhookSecretRevealOut(
    secret=WebhookSecretOut(source=s.source, enabled=s.enabled, tokenHint=s.token_hint, createdAt=s.created_at, updatedAt=s.updated_at),
    bearerToken=token,
  )


@router.post("/secrets/{source}/rotate", response_model=WebhookSecretRevealOut)
async def rotate_secret(source: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> WebhookSecretRevealOut:
  _require_admin(user)
  s = await _get_secret(db, source)
  if not s:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
  token = secrets.token_urlsafe(32)
  s.bearer_token_encrypted = encrypt_secret(token)
  s.token_hint = _token_hint(token)
  await write_audit(db, event_type="webhook.secret.rotated", entity_type="WebhookSecret", entity_id=s.id, actor_id=user.id, payload={"source": source})
  await db.commit()
  return WebhookSecretRevealOut(
    secret=WebhookSecretOut(source=s.source, enabled=s.enabled, tokenHint=s.token_hint, createdAt=s.created_at, updatedAt=s.updated_at),
    bearerToken=token,
  )


@router.delete("/secrets/{source}")
async def disable_secret(source: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  _require_admin(user)
  s = await _get_secret(db, source)
  if not s:
    return {"ok": True}
  s.enabled = False
  await write_audit(db, event_type="webhook.secret.disabled", entity_type="WebhookSecret", entity_id=s.id, actor_id=user.id, payload={"source": source})
  await db.commit()
  return {"ok": True}


@router.get("/events", response_model=list[WebhookEventOut])
async def list_events(source: str | None = None, limit: int = 50, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[WebhookEventOut]:
  _require_admin(user)
  lim = max(1, min(200, int(limit)))
  q = select(InboundWebhookEvent).order_by(InboundWebhookEvent.received_at.desc()).limit(lim)
  if source:
    q = q.where(InboundWebhookEvent.source == source)
  res = await db.execute(q)
  out: list[WebhookEventOut] = []
  for ev in res.scalars().all():
    out.append(
      WebhookEventOut(
        id=ev.id,
        source=ev.source,
        idempotencyKey=ev.idempotency_key,
        receivedAt=ev.received_at,
        processed=ev.processed,
        processedAt=ev.processed_at,
        result=ev.result,
        error=ev.error,
      )
    )
  return out


@router.post("/events/{event_id}/replay", response_model=WebhookInboundOut)
async def replay_event(event_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> WebhookInboundOut:
  _require_admin(user)
  res = await db.execute(select(InboundWebhookEvent).where(InboundWebhookEvent.id == event_id))
  ev = res.scalar_one_or_none()
  if not ev:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
  if not isinstance(ev.body, dict):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stored event body is not a JSON object")

  # Re-run processing. This is only safe if the original webhook used idempotency.
  try:
    result = await _process_action(db, source=ev.source, payload=dict(ev.body), event_id=ev.id)
    ev.processed = True
    ev.processed_at = datetime.now(timezone.utc)
    ev.result = result
    ev.error = None
    await write_audit(db, event_type="webhook.event.replayed", entity_type="InboundWebhookEvent", entity_id=ev.id, actor_id=user.id, payload={"source": ev.source})
    await db.commit()
    return WebhookInboundOut(eventId=ev.id, idempotentReplay=False, result=result)
  except HTTPException:
    raise
  except Exception:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Replay failed")
