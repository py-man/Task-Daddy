from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BoardMember, InAppNotification, NotificationDestination, User
from app.notifications.service import NotificationMessage, decrypt_destination_config, provider_for


def _now() -> datetime:
  return datetime.now(timezone.utc)


def _minutes(hhmm: str | None) -> int | None:
  s = (hhmm or "").strip()
  if not s or len(s) != 5 or s[2] != ":":
    return None
  hh, mm = s[:2], s[3:]
  if not (hh.isdigit() and mm.isdigit()):
    return None
  hhi, mmi = int(hh), int(mm)
  if hhi < 0 or hhi > 23 or mmi < 0 or mmi > 59:
    return None
  return hhi * 60 + mmi


def _event_pref_key(event_type: str | None) -> str | None:
  et = str(event_type or "").strip().lower()
  if et == "comment.mentioned":
    return "mentions"
  if et == "comment.created":
    return "comments"
  if et == "task.moved":
    return "moves"
  if et == "task.assigned":
    return "assignments"
  if et == "task.overdue":
    return "overdue"
  return None


def notification_taxonomy_for_event(event_type: str | None, *, level: str | None = None) -> str:
  et = str(event_type or "").strip().lower()
  lvl = str(level or "").strip().lower()
  if et.startswith("system.") or et.startswith("notifications.") or lvl == "error":
    return "system"
  if et in {"task.overdue", "task.assigned", "comment.mentioned"} or lvl in {"warn"}:
    return "action_required"
  return "informational"


async def _should_deliver(
  db: AsyncSession,
  *,
  user_id: str,
  event_type: str | None,
) -> bool:
  ures = await db.execute(select(User).where(User.id == user_id))
  user = ures.scalar_one_or_none()
  if not user or not bool(getattr(user, "active", True)):
    return False

  prefs = {"mentions": True, "comments": True, "moves": True, "assignments": True, "overdue": True}
  prefs.update((getattr(user, "notification_prefs", None) or {}))
  key = _event_pref_key(event_type)
  if key and not bool(prefs.get(key, True)):
    return False

  if bool(getattr(user, "quiet_hours_enabled", False)):
    start = _minutes(getattr(user, "quiet_hours_start", None))
    end = _minutes(getattr(user, "quiet_hours_end", None))
    if start is not None and end is not None:
      tz_name = getattr(user, "timezone", None) or "UTC"
      try:
        now_local = _now().astimezone(ZoneInfo(tz_name))
      except Exception:
        now_local = _now()
      minute = now_local.hour * 60 + now_local.minute
      in_qh = (start <= minute < end) if start < end else (minute >= start or minute < end)
      if in_qh:
        return False
  return True


async def notify_inapp(
  db: AsyncSession,
  *,
  user_id: str,
  level: str,
  title: str,
  body: str,
  event_type: str | None = None,
  entity_type: str | None = None,
  entity_id: str | None = None,
  dedupe_key: str | None = None,
) -> None:
  if not await _should_deliver(db, user_id=user_id, event_type=event_type):
    return
  now = _now()
  taxonomy = notification_taxonomy_for_event(event_type, level=level)
  stmt = (
    insert(InAppNotification)
    .values(
      user_id=user_id,
      level=level,
      title=title,
      body=body,
      event_type=event_type,
      taxonomy=taxonomy,
      entity_type=entity_type,
      entity_id=entity_id,
      dedupe_key=dedupe_key,
      burst_count=1,
      last_occurrence_at=now,
      created_at=now,
    )
    .on_conflict_do_update(
      index_elements=["user_id", "dedupe_key"],
      index_where=InAppNotification.dedupe_key.isnot(None),
      set_={
        "level": level,
        "title": title,
        "body": body,
        "event_type": event_type,
        "taxonomy": taxonomy,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "burst_count": InAppNotification.burst_count + 1,
        "last_occurrence_at": now,
        "read_at": None,
      },
    )
  )
  await db.execute(stmt)


async def notify_board_members_inapp(
  db: AsyncSession,
  *,
  board_id: str,
  exclude_user_id: str | None,
  level: str,
  title: str,
  body: str,
  event_type: str | None = None,
  entity_type: str | None = None,
  entity_id: str | None = None,
  dedupe_key: str | None = None,
) -> int:
  res = await db.execute(select(BoardMember.user_id).where(BoardMember.board_id == board_id))
  user_ids = [row.user_id for row in res.all()]
  n = 0
  for uid in user_ids:
    if exclude_user_id and uid == exclude_user_id:
      continue
    await notify_inapp(
      db,
      user_id=uid,
      level=level,
      title=title,
      body=body,
      event_type=event_type,
      entity_type=entity_type,
      entity_id=entity_id,
      dedupe_key=(f"{dedupe_key}:{uid}" if dedupe_key else None),
    )
    n += 1
  return n


async def dispatch_to_destinations(
  db: AsyncSession,
  *,
  msg: NotificationMessage,
) -> list[dict[str, Any]]:
  dests = await materialize_enabled_destinations(db)
  return await dispatch_to_materialized(dests, msg=msg)


async def materialize_enabled_destinations(db: AsyncSession) -> list[dict[str, Any]]:
  res = await db.execute(select(NotificationDestination).where(NotificationDestination.enabled.is_(True)).order_by(NotificationDestination.created_at.desc()))
  out: list[dict[str, Any]] = []
  for d in res.scalars().all():
    out.append({"id": d.id, "provider": d.provider, "name": d.name, "config": decrypt_destination_config(d.config_encrypted)})
  return out


async def dispatch_to_materialized(dests: list[dict[str, Any]], *, msg: NotificationMessage) -> list[dict[str, Any]]:
  results: list[dict[str, Any]] = []
  for d in dests:
    provider = provider_for(str(d.get("provider") or "local"))
    try:
      results.append(await provider.send(destination=d, msg=msg))
    except Exception as e:
      results.append({"provider": d.get("provider") or "unknown", "status": "error", "detail": {"error": str(e), "destination": d.get("name")}})
  return results
