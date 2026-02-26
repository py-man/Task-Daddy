from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.deps import get_current_user, get_db, require_admin_mfa_guard
from app.models import OpenProjectConnection, User
from app.openproject.client import normalize_base_url, openproject_ping
from app.schemas import OpenProjectConnectIn, OpenProjectConnectionOut, OpenProjectConnectionUpdateIn
from app.security import decrypt_integration_secret, encrypt_secret

router = APIRouter(prefix="/openproject", tags=["openproject"])


def _hint(v: str) -> str:
  s = (v or "").strip()
  if not s:
    return ""
  if len(s) <= 6:
    return f"…{s}"
  return f"…{s[-6:]}"


def _out(c: OpenProjectConnection) -> OpenProjectConnectionOut:
  return OpenProjectConnectionOut(
    id=c.id,
    name=c.name,
    baseUrl=c.base_url,
    projectIdentifier=c.project_identifier,
    enabled=bool(c.enabled),
    tokenHint=c.token_hint or "",
    createdAt=c.created_at,
    updatedAt=c.updated_at,
  )


@router.get("/connections", response_model=list[OpenProjectConnectionOut])
async def list_connections(
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> list[OpenProjectConnectionOut]:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  res = await db.execute(select(OpenProjectConnection).order_by(OpenProjectConnection.created_at.desc()))
  return [_out(c) for c in res.scalars().all()]


@router.post("/connections", response_model=OpenProjectConnectionOut)
async def create_connection(
  payload: OpenProjectConnectIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> OpenProjectConnectionOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  try:
    base = normalize_base_url(payload.baseUrl)
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
  name = (payload.name or "").strip() or "OpenProject"
  project_id = (payload.projectIdentifier or "").strip() or None
  token = (payload.apiToken or "").strip()
  conn = OpenProjectConnection(
    name=name,
    base_url=base,
    api_token_encrypted=encrypt_secret(token),
    project_identifier=project_id,
    enabled=bool(payload.enabled),
    token_hint=_hint(token),
  )
  db.add(conn)
  await db.flush()
  await write_audit(
    db,
    event_type="openproject.connection.created",
    entity_type="OpenProjectConnection",
    entity_id=conn.id,
    actor_id=actor.id,
    payload={"name": conn.name, "baseUrl": conn.base_url, "enabled": conn.enabled, "projectIdentifier": conn.project_identifier},
  )
  await db.commit()
  return _out(conn)


@router.patch("/connections/{connection_id}", response_model=OpenProjectConnectionOut)
async def update_connection(
  connection_id: str,
  payload: OpenProjectConnectionUpdateIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> OpenProjectConnectionOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  res = await db.execute(select(OpenProjectConnection).where(OpenProjectConnection.id == connection_id))
  conn = res.scalar_one_or_none()
  if not conn:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
  fields_set = payload.model_fields_set
  if "name" in fields_set:
    conn.name = (payload.name or "").strip() or conn.name
  if "projectIdentifier" in fields_set:
    conn.project_identifier = (payload.projectIdentifier or "").strip() or None
  if "enabled" in fields_set and payload.enabled is not None:
    conn.enabled = bool(payload.enabled)
  if "apiToken" in fields_set and payload.apiToken:
    token = payload.apiToken.strip()
    conn.api_token_encrypted = encrypt_secret(token)
    conn.token_hint = _hint(token)
  await write_audit(
    db,
    event_type="openproject.connection.updated",
    entity_type="OpenProjectConnection",
    entity_id=conn.id,
    actor_id=actor.id,
    payload={"changed": sorted(list(fields_set))},
  )
  await db.commit()
  return _out(conn)


@router.delete("/connections/{connection_id}")
async def delete_connection(
  connection_id: str,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> dict:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  res = await db.execute(select(OpenProjectConnection).where(OpenProjectConnection.id == connection_id))
  conn = res.scalar_one_or_none()
  if not conn:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
  await db.execute(delete(OpenProjectConnection).where(OpenProjectConnection.id == connection_id))
  await write_audit(
    db,
    event_type="openproject.connection.deleted",
    entity_type="OpenProjectConnection",
    entity_id=connection_id,
    actor_id=actor.id,
    payload={"name": conn.name, "baseUrl": conn.base_url},
  )
  await db.commit()
  return {"ok": True}


@router.post("/connections/{connection_id}/test")
async def test_connection(
  connection_id: str,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> dict:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  res = await db.execute(select(OpenProjectConnection).where(OpenProjectConnection.id == connection_id))
  conn = res.scalar_one_or_none()
  if not conn:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
  token = decrypt_integration_secret(conn.api_token_encrypted)
  try:
    result = await openproject_ping(base_url=conn.base_url, api_token=token)
  except Exception as e:
    await write_audit(
      db,
      event_type="openproject.connection.test.error",
      entity_type="OpenProjectConnection",
      entity_id=conn.id,
      actor_id=actor.id,
      payload={"error": str(e)},
    )
    await db.commit()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OpenProject test failed: {e}") from e
  await write_audit(
    db,
    event_type="openproject.connection.test.ok",
    entity_type="OpenProjectConnection",
    entity_id=conn.id,
    actor_id=actor.id,
    payload={"result": result},
  )
  await db.commit()
  return {"ok": True, "result": result}
