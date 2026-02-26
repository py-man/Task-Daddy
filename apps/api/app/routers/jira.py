from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.deps import get_current_user, get_db, require_board_role
from app.jira.service import create_connection_named, import_issues_to_board, sync_now
from app.models import JiraConnection, JiraSyncProfile, SyncRun, Task, User
from app.schemas import (
  JiraConnectIn,
  JiraConnectionOut,
  JiraConnectionUpdateIn,
  JiraImportIn,
  JiraSyncNowIn,
  SyncRunOut,
)
from app.security import IntegrationSecretDecryptError, decrypt_integration_secret, encrypt_secret
from app.jira.client import normalize_base_url

router = APIRouter(prefix="/jira", tags=["jira"])


def _conn_out(c: JiraConnection) -> JiraConnectionOut:
  needs_reconnect = False
  reconnect_reason: str | None = None
  try:
    decrypt_integration_secret(c.token_encrypted)
  except IntegrationSecretDecryptError:
    needs_reconnect = True
    reconnect_reason = "Token cannot be decrypted with current key"
  return JiraConnectionOut(
    id=c.id,
    name=getattr(c, "name", None),
    baseUrl=c.base_url,
    email=c.email,
    defaultAssigneeAccountId=getattr(c, "default_assignee_account_id", None),
    needsReconnect=needs_reconnect,
    reconnectReason=reconnect_reason,
    createdAt=c.created_at,
  )


def _run_out(r: SyncRun) -> SyncRunOut:
  return SyncRunOut(
    id=r.id,
    boardId=r.board_id,
    profileId=r.profile_id,
    status=r.status,
    startedAt=r.started_at,
    finishedAt=r.finished_at,
    log=list(r.log or []),
    errorMessage=r.error_message,
  )


@router.get("/connections", response_model=list[JiraConnectionOut])
async def list_connections(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[JiraConnectionOut]:
  res = await db.execute(select(JiraConnection).order_by(JiraConnection.created_at.desc()))
  return [_conn_out(c) for c in res.scalars().all()]


@router.patch("/connections/{connection_id}", response_model=JiraConnectionOut)
async def update_connection(
  connection_id: str,
  payload: JiraConnectionUpdateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> JiraConnectionOut:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  res = await db.execute(select(JiraConnection).where(JiraConnection.id == connection_id))
  c = res.scalar_one_or_none()
  if not c:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
  fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
  if "name" in fields_set:
    c.name = (payload.name or "").strip() or None
  if "defaultAssigneeAccountId" in fields_set:
    c.default_assignee_account_id = (payload.defaultAssigneeAccountId or "").strip() or None
  await write_audit(
    db,
    event_type="jira.connection.updated",
    entity_type="JiraConnection",
    entity_id=c.id,
    actor_id=user.id,
    payload={"name": c.name, "baseUrl": c.base_url, "defaultAssigneeAccountId": c.default_assignee_account_id},
  )
  await db.commit()
  return _conn_out(c)


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  res = await db.execute(select(JiraConnection).where(JiraConnection.id == connection_id))
  c = res.scalar_one_or_none()
  if not c:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

  # Unlink tasks for MVP.
  await db.execute(
    update(Task)
    .where(Task.jira_connection_id == connection_id)
    .values(jira_connection_id=None, jira_sync_enabled=False)
  )
  # Delete profiles for this connection (sync runs remain for audit/history).
  await db.execute(delete(JiraSyncProfile).where(JiraSyncProfile.connection_id == connection_id))
  await db.execute(delete(JiraConnection).where(JiraConnection.id == connection_id))
  await write_audit(
    db,
    event_type="jira.connection.deleted",
    entity_type="JiraConnection",
    entity_id=connection_id,
    actor_id=user.id,
    payload={"baseUrl": c.base_url, "name": getattr(c, "name", None)},
  )
  await db.commit()
  return {"ok": True}


@router.post("/connect", response_model=JiraConnectionOut)
async def connect(payload: JiraConnectIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> JiraConnectionOut:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  try:
    base = normalize_base_url(payload.baseUrl)
  except Exception as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
  c = await create_connection_named(
    db,
    name=payload.name,
    base_url=base,
    email=payload.email,
    token_encrypted=encrypt_secret(payload.token),
    default_assignee_account_id=payload.defaultAssigneeAccountId,
  )
  await write_audit(
    db,
    event_type="jira.connected",
    entity_type="JiraConnection",
    entity_id=c.id,
    actor_id=user.id,
    payload={"baseUrl": c.base_url, "name": getattr(c, "name", None)},
  )
  await db.commit()
  return _conn_out(c)


@router.post("/connect-env", response_model=JiraConnectionOut)
async def connect_env(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> JiraConnectionOut:
  from app.config import settings

  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  if not settings.jira_base_url or not settings.jira_token:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set JIRA_BASE_URL and JIRA_TOKEN in apps/api/.env")

  base = normalize_base_url(settings.jira_base_url)
  email = settings.jira_email
  default_assignee = settings.jira_default_assignee_account_id

  existing = await db.execute(
    select(JiraConnection).where(JiraConnection.base_url == base, JiraConnection.email == email)
  )
  c = existing.scalar_one_or_none()
  if c:
    c.token_encrypted = encrypt_secret(settings.jira_token)
    if getattr(c, "name", None) in (None, ""):
      c.name = "Env Jira"
    if default_assignee:
      c.default_assignee_account_id = default_assignee
    await write_audit(
      db,
      event_type="jira.connected",
      entity_type="JiraConnection",
      entity_id=c.id,
      actor_id=user.id,
      payload={"baseUrl": c.base_url, "via": "env"},
    )
    await db.commit()
    return _conn_out(c)

  c2 = await create_connection_named(
    db,
    name="Env Jira",
    base_url=base,
    email=email,
    token_encrypted=encrypt_secret(settings.jira_token),
    default_assignee_account_id=default_assignee,
  )
  await write_audit(
    db,
    event_type="jira.connected",
    entity_type="JiraConnection",
    entity_id=c2.id,
    actor_id=user.id,
    payload={"baseUrl": c2.base_url, "via": "env"},
  )
  await db.commit()
  return _conn_out(c2)


@router.post("/import", response_model=SyncRunOut)
async def import_issues(payload: JiraImportIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> SyncRunOut:
  await require_board_role(payload.boardId, "member", user, db)
  cres = await db.execute(select(JiraConnection).where(JiraConnection.id == payload.connectionId))
  c = cres.scalar_one_or_none()
  if not c:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
  try:
    decrypt_integration_secret(c.token_encrypted)
  except IntegrationSecretDecryptError as exc:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
  _, run = await import_issues_to_board(
    db,
    board_id=payload.boardId,
    connection=c,
    jql=payload.jql,
    status_to_state_key=payload.statusToStateKey,
    priority_map=payload.priorityMap,
    type_map=payload.typeMap,
    conflict_policy=payload.conflictPolicy,
    actor_id=user.id,
  )
  await db.commit()
  return _run_out(run)


@router.post("/sync-now", response_model=SyncRunOut)
async def sync_now_route(payload: JiraSyncNowIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> SyncRunOut:
  pres = await db.execute(select(JiraSyncProfile).where(JiraSyncProfile.id == payload.profileId))
  p = pres.scalar_one_or_none()
  if not p:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
  await require_board_role(p.board_id, "member", user, db)
  cres = await db.execute(select(JiraConnection).where(JiraConnection.id == p.connection_id))
  c = cres.scalar_one_or_none()
  if not c:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
  try:
    decrypt_integration_secret(c.token_encrypted)
  except IntegrationSecretDecryptError as exc:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
  run = await sync_now(db, profile=p, actor_id=user.id)
  await db.commit()
  return _run_out(run)


@router.get("/profiles")
async def list_profiles(boardId: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
  await require_board_role(boardId, "viewer", user, db)
  res = await db.execute(select(JiraSyncProfile).where(JiraSyncProfile.board_id == boardId).order_by(JiraSyncProfile.created_at.desc()))
  out = []
  for p in res.scalars().all():
    out.append(
      {
        "id": p.id,
        "boardId": p.board_id,
        "connectionId": p.connection_id,
        "jql": p.jql,
        "conflictPolicy": p.conflict_policy,
        "createdAt": p.created_at,
      }
    )
  return out


@router.get("/sync-runs", response_model=list[SyncRunOut])
async def list_sync_runs(boardId: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[SyncRunOut]:
  await require_board_role(boardId, "viewer", user, db)
  res = await db.execute(select(SyncRun).where(SyncRun.board_id == boardId).order_by(SyncRun.started_at.desc()).limit(50))
  return [_run_out(r) for r in res.scalars().all()]


@router.delete("/sync-runs")
async def clear_sync_runs(boardId: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  await require_board_role(boardId, "admin", user, db)
  await db.execute(delete(SyncRun).where(SyncRun.board_id == boardId))
  await write_audit(
    db,
    event_type="jira.sync_runs.cleared",
    entity_type="Board",
    entity_id=boardId,
    board_id=boardId,
    actor_id=user.id,
    payload={},
  )
  await db.commit()
  return {"ok": True}
