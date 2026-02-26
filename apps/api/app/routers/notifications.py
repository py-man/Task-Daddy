from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.deps import get_current_user, get_db, require_admin_mfa_guard
from app.models import InAppNotification, NotificationDestination, User
from app.notifications.events import notification_taxonomy_for_event
from app.notifications.service import NotificationMessage, decrypt_destination_config, destination_public, provider_for
from app.schemas import (
  NotificationDestinationOut,
  NotificationPreferencesIn,
  NotificationPreferencesOut,
  NotificationDestinationTestIn,
  NotificationDestinationUpsertIn,
  NotificationSendOut,
)
from app.security import encrypt_secret

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _hint(v: str) -> str:
  s = (v or "").strip()
  if not s:
    return ""
  if len(s) <= 6:
    return f"…{s}"
  return f"…{s[-6:]}"


def _default_prefs() -> dict:
  return {"mentions": True, "comments": True, "moves": True, "assignments": True, "overdue": True}


def _normalize_hhmm(v: str | None) -> str | None:
  s = (v or "").strip()
  if not s:
    return None
  if len(s) != 5 or s[2] != ":":
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Time must be HH:MM")
  hh, mm = s[:2], s[3:]
  if not (hh.isdigit() and mm.isdigit()):
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Time must be HH:MM")
  hhi, mmi = int(hh), int(mm)
  if hhi < 0 or hhi > 23 or mmi < 0 or mmi > 59:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Time must be HH:MM")
  return f"{hhi:02d}:{mmi:02d}"


@router.get("/preferences", response_model=NotificationPreferencesOut)
async def get_notification_preferences(
  actor: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesOut:
  res = await db.execute(select(User).where(User.id == actor.id))
  u = res.scalar_one()
  prefs = _default_prefs()
  prefs.update((getattr(u, "notification_prefs", None) or {}))
  return NotificationPreferencesOut(
    mentions=bool(prefs.get("mentions", True)),
    comments=bool(prefs.get("comments", True)),
    moves=bool(prefs.get("moves", True)),
    assignments=bool(prefs.get("assignments", True)),
    overdue=bool(prefs.get("overdue", True)),
    quietHoursEnabled=bool(getattr(u, "quiet_hours_enabled", False)),
    quietHoursStart=getattr(u, "quiet_hours_start", None),
    quietHoursEnd=getattr(u, "quiet_hours_end", None),
    timezone=getattr(u, "timezone", None),
  )


@router.patch("/preferences", response_model=NotificationPreferencesOut)
async def update_notification_preferences(
  payload: NotificationPreferencesIn,
  actor: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesOut:
  res = await db.execute(select(User).where(User.id == actor.id))
  u = res.scalar_one()

  prefs = _default_prefs()
  prefs.update((getattr(u, "notification_prefs", None) or {}))

  fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
  for key in ("mentions", "comments", "moves", "assignments", "overdue"):
    if key in fields_set:
      val = getattr(payload, key)
      if val is not None:
        prefs[key] = bool(val)

  if "quietHoursEnabled" in fields_set and payload.quietHoursEnabled is not None:
    u.quiet_hours_enabled = bool(payload.quietHoursEnabled)
  if "quietHoursStart" in fields_set:
    u.quiet_hours_start = _normalize_hhmm(payload.quietHoursStart)
  if "quietHoursEnd" in fields_set:
    u.quiet_hours_end = _normalize_hhmm(payload.quietHoursEnd)
  u.notification_prefs = prefs

  await write_audit(
    db,
    event_type="notifications.preferences.updated",
    entity_type="User",
    entity_id=u.id,
    actor_id=actor.id,
    payload={"changed": sorted(list(fields_set))},
  )
  await db.commit()
  return await get_notification_preferences(actor=actor, db=db)


@router.get("/destinations", response_model=list[NotificationDestinationOut])
async def list_destinations(
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> list[NotificationDestinationOut]:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  res = await db.execute(select(NotificationDestination).order_by(NotificationDestination.created_at.desc()))
  out = []
  for d in res.scalars().all():
    out.append(NotificationDestinationOut(**destination_public(id=d.id, provider=d.provider, name=d.name, enabled=d.enabled, token_hint=d.token_hint, created_at=d.created_at, updated_at=d.updated_at)))
  return out


@router.post("/destinations", response_model=NotificationDestinationOut)
async def create_destination(
  request: Request,
  payload: NotificationDestinationUpsertIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> NotificationDestinationOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

  provider = payload.provider
  cfg: dict = {}
  token_hint = ""
  if provider == "pushover":
    if not payload.pushoverAppToken or not payload.pushoverUserKey:
      raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pushover token + user key required")
    cfg = {"appToken": payload.pushoverAppToken.strip(), "userKey": payload.pushoverUserKey.strip()}
    token_hint = _hint(cfg["userKey"])
  elif provider == "smtp":
    if not payload.smtpHost or not payload.smtpFrom or not payload.smtpTo:
      raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SMTP host/from/to required")
    cfg = {
      "host": payload.smtpHost.strip(),
      "port": int(payload.smtpPort or 587),
      "username": (payload.smtpUsername or "").strip(),
      "password": (payload.smtpPassword or "").strip(),
      "from": payload.smtpFrom.strip(),
      "to": payload.smtpTo.strip(),
      "starttls": bool(payload.smtpStarttls if payload.smtpStarttls is not None else True),
    }
    token_hint = _hint(cfg["to"])
  else:
    cfg = {"note": "local sink"}

  d = NotificationDestination(
    provider=provider,
    name=payload.name.strip(),
    enabled=payload.enabled,
    config_encrypted=encrypt_secret(json.dumps(cfg)),
    token_hint=token_hint,
  )
  db.add(d)
  await db.flush()

  await write_audit(
    db,
    event_type="notifications.destination.created",
    entity_type="NotificationDestination",
    entity_id=d.id,
    actor_id=actor.id,
    payload={"provider": d.provider, "name": d.name, "enabled": d.enabled},
  )
  await db.commit()
  return NotificationDestinationOut(**destination_public(id=d.id, provider=d.provider, name=d.name, enabled=d.enabled, token_hint=d.token_hint, created_at=d.created_at, updated_at=d.updated_at))


@router.patch("/destinations/{destination_id}", response_model=NotificationDestinationOut)
async def update_destination(
  destination_id: str,
  payload: NotificationDestinationUpsertIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> NotificationDestinationOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

  res = await db.execute(select(NotificationDestination).where(NotificationDestination.id == destination_id))
  d = res.scalar_one_or_none()
  if not d:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")

  changed: dict = {}
  if payload.name and payload.name.strip() != d.name:
    d.name = payload.name.strip()
    changed["name"] = d.name
  if payload.enabled != d.enabled:
    d.enabled = payload.enabled
    changed["enabled"] = d.enabled

  # Provider + secrets update
  if payload.provider != d.provider:
    d.provider = payload.provider
    changed["provider"] = d.provider

  cfg = {} if "provider" in changed else decrypt_destination_config(d.config_encrypted)
  token_hint = d.token_hint
  if d.provider == "pushover":
    if payload.pushoverAppToken:
      cfg["appToken"] = payload.pushoverAppToken.strip()
      changed["appToken"] = "updated"
    if payload.pushoverUserKey:
      cfg["userKey"] = payload.pushoverUserKey.strip()
      token_hint = _hint(cfg.get("userKey") or "")
      changed["userKey"] = "updated"
    if not cfg.get("appToken") or not cfg.get("userKey"):
      raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pushover destination requires token + user key")
  elif d.provider == "smtp":
    if payload.smtpHost:
      cfg["host"] = payload.smtpHost.strip()
      changed["host"] = "updated"
    if payload.smtpPort is not None:
      cfg["port"] = int(payload.smtpPort)
      changed["port"] = "updated"
    if payload.smtpUsername is not None:
      cfg["username"] = (payload.smtpUsername or "").strip()
      changed["username"] = "updated"
    if payload.smtpPassword:
      cfg["password"] = (payload.smtpPassword or "").strip()
      changed["password"] = "updated"
    if payload.smtpFrom:
      cfg["from"] = payload.smtpFrom.strip()
      changed["from"] = "updated"
    if payload.smtpTo:
      cfg["to"] = payload.smtpTo.strip()
      token_hint = _hint(cfg.get("to") or "")
      changed["to"] = "updated"
    if payload.smtpStarttls is not None:
      cfg["starttls"] = bool(payload.smtpStarttls)
      changed["starttls"] = "updated"
    if not cfg.get("host") or not cfg.get("from") or not cfg.get("to"):
      raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SMTP destination requires host/from/to")
  else:
    cfg = {"note": "local sink"}
    token_hint = ""

  d.config_encrypted = encrypt_secret(json.dumps(cfg))
  d.token_hint = token_hint

  await write_audit(
    db,
    event_type="notifications.destination.updated",
    entity_type="NotificationDestination",
    entity_id=d.id,
    actor_id=actor.id,
    payload={"changed": list(changed.keys())},
  )
  await db.commit()
  return NotificationDestinationOut(**destination_public(id=d.id, provider=d.provider, name=d.name, enabled=d.enabled, token_hint=d.token_hint, created_at=d.created_at, updated_at=d.updated_at))


@router.delete("/destinations/{destination_id}")
async def delete_destination(
  destination_id: str,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> dict:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  res = await db.execute(select(NotificationDestination).where(NotificationDestination.id == destination_id))
  d = res.scalar_one_or_none()
  if not d:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")
  await db.execute(delete(NotificationDestination).where(NotificationDestination.id == destination_id))
  await write_audit(
    db,
    event_type="notifications.destination.deleted",
    entity_type="NotificationDestination",
    entity_id=destination_id,
    actor_id=actor.id,
    payload={"provider": d.provider, "name": d.name},
  )
  await db.commit()
  return {"ok": True}


@router.post("/destinations/{destination_id}/test", response_model=NotificationSendOut)
async def test_destination(
  destination_id: str,
  payload: NotificationDestinationTestIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> NotificationSendOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

  res = await db.execute(select(NotificationDestination).where(NotificationDestination.id == destination_id))
  d = res.scalar_one_or_none()
  if not d:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")
  if not d.enabled:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Destination disabled")

  cfg = decrypt_destination_config(d.config_encrypted)
  provider = provider_for(d.provider)
  msg = NotificationMessage(title=payload.title, message=payload.message, priority=payload.priority)
  try:
    result = await provider.send(destination={"id": d.id, "provider": d.provider, "name": d.name, "config": cfg}, msg=msg)
  except Exception as e:
    await write_audit(
      db,
      event_type="notifications.test.error",
      entity_type="NotificationDestination",
      entity_id=d.id,
      actor_id=actor.id,
      payload={"error": str(e), "provider": d.provider},
    )
    await db.commit()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Notification send failed: {e}")

  await write_audit(
    db,
    event_type="notifications.test.sent",
    entity_type="NotificationDestination",
    entity_id=d.id,
    actor_id=actor.id,
    payload={"provider": d.provider, "result": result.get("detail") or {}, "title": payload.title},
  )
  await db.commit()
  return NotificationSendOut(ok=True, provider=result.get("provider") or d.provider, status=result.get("status") or "sent", detail=result.get("detail"))


@router.get("/inapp")
async def list_inapp_notifications(
  unreadOnly: bool = False,
  limit: int = 50,
  actor: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> list[dict]:
  limit = max(1, min(int(limit), 200))
  stmt = select(InAppNotification).where(InAppNotification.user_id == actor.id)
  if unreadOnly:
    stmt = stmt.where(InAppNotification.read_at.is_(None))
  stmt = stmt.order_by(InAppNotification.created_at.desc()).limit(limit)
  res = await db.execute(stmt)
  out: list[dict] = []
  for n in res.scalars().all():
    out.append(
      {
        "id": n.id,
        "level": n.level,
        "title": n.title,
        "body": n.body,
        "eventType": n.event_type,
        "taxonomy": (n.taxonomy or notification_taxonomy_for_event(n.event_type, level=n.level)),
        "burstCount": int(getattr(n, "burst_count", 1) or 1),
        "lastOccurrenceAt": getattr(n, "last_occurrence_at", None),
        "entityType": n.entity_type,
        "entityId": n.entity_id,
        "dedupeKey": n.dedupe_key,
        "readAt": n.read_at,
        "createdAt": n.created_at,
      }
    )
  return out


@router.post("/inapp/mark-read")
async def mark_inapp_read(
  payload: dict,
  actor: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  ids = payload.get("ids")
  if not isinstance(ids, list) or not ids:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids is required")
  now = datetime.now(timezone.utc)
  await db.execute(update(InAppNotification).where(InAppNotification.user_id == actor.id, InAppNotification.id.in_(ids)).values(read_at=now))
  await write_audit(db, event_type="notifications.inapp.read", entity_type="InAppNotification", entity_id=None, actor_id=actor.id, payload={"count": len(ids)})
  await db.commit()
  return {"ok": True}


@router.post("/inapp/mark-all-read")
async def mark_inapp_all_read(
  actor: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  now = datetime.now(timezone.utc)
  await db.execute(update(InAppNotification).where(InAppNotification.user_id == actor.id, InAppNotification.read_at.is_(None)).values(read_at=now))
  await write_audit(db, event_type="notifications.inapp.read_all", entity_type="InAppNotification", entity_id=None, actor_id=actor.id, payload={})
  await db.commit()
  return {"ok": True}
