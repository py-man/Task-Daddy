from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_current_user, get_db, require_admin_mfa_guard
from app.metrics import runtime_metrics
from app.models import AuditEvent, InAppNotification, SyncRun, TaskReminder, User
from app.schemas import SystemStatusOut, SystemStatusSectionOut

router = APIRouter(prefix="/admin/system-status", tags=["admin"])


def _as_state(ok: bool, warn: bool = False) -> str:
  if not ok:
    return "red"
  return "yellow" if warn else "green"


async def _redis_metrics() -> tuple[str, list[str]]:
  if not settings.redis_url:
    return ("yellow", ["provider: disabled", "hit ratio: n/a", "memory usage: n/a"])
  try:
    from redis.asyncio import from_url as redis_from_url
  except Exception:
    return ("yellow", ["provider: redis client missing", "hit ratio: n/a", "memory usage: n/a"])

  client = redis_from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
  try:
    info = await client.info()
    keyspace_hits = int(info.get("keyspace_hits", 0) or 0)
    keyspace_misses = int(info.get("keyspace_misses", 0) or 0)
    total = keyspace_hits + keyspace_misses
    hit_ratio = (keyspace_hits / total * 100.0) if total > 0 else 0.0
    memory_bytes = int(info.get("used_memory", 0) or 0)
    evictions = int(info.get("evicted_keys", 0) or 0)
    dbsize = 0
    try:
      dbsize = int(await client.dbsize())
    except Exception:
      dbsize = 0
    if total == 0:
      state = "yellow"
      ratio_line = "hit ratio: n/a (warming up, no cache traffic yet)"
    else:
      state = _as_state(evictions == 0 and hit_ratio >= 70, warn=hit_ratio < 90)
      ratio_line = f"hit ratio: {hit_ratio:.1f}%"
    return (
      state,
      [
        "provider: redis",
        ratio_line,
        f"ops: {total}",
        f"memory: {memory_bytes // (1024 * 1024)}MB",
        f"evictions: {evictions}",
        f"keyspace size: {dbsize}",
      ],
    )
  except Exception as e:
    return ("yellow", [f"provider: redis unreachable", f"detail: {str(e)[:120]}", "hit ratio: n/a", "memory usage: n/a"])
  finally:
    await client.close()


@router.get("", response_model=SystemStatusOut)
async def get_system_status(
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> SystemStatusOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

  now = datetime.now(timezone.utc)
  sections: list[SystemStatusSectionOut] = []
  runtime = runtime_metrics.snapshot()

  # API health
  sections.append(
    SystemStatusSectionOut(
      key="api",
      label="API health",
      state=_as_state(runtime["errorRate15m"] < 1.0 and runtime["p95LatencyMs24h"] < 1000, warn=runtime["errorRate15m"] > 0),
      details=[
        "health endpoint: ok",
        f"uptime: {runtime['uptimeSeconds']}s",
        f"error rate (15m): {runtime['errorRate15m']}%",
        f"error rate (24h): {runtime['errorRate24h']}%",
        f"p95 latency (24h): {runtime['p95LatencyMs24h']}ms",
        f"version: {settings.app_version}",
        f"build: {settings.build_sha}",
      ],
      updatedAt=now,
    )
  )

  # Postgres (pg_stat_activity and pg_settings)
  pg_details = ["pg_stat_activity unavailable"]
  pg_state = "yellow"
  try:
    pg_row = (
      await db.execute(
        text(
          """
          select
            count(*)::int as total,
            sum(case when state = 'active' then 1 else 0 end)::int as active,
            sum(case when wait_event_type = 'Lock' then 1 else 0 end)::int as waiting_lock,
            sum(
              case
                when state = 'active'
                  and query_start is not null
                  and now() - query_start > interval '30 seconds'
                then 1
                else 0
              end
            )::int as long_running
          from pg_stat_activity
          where datname = current_database()
          """
        )
      )
    ).mappings().first()
    max_conn = (await db.execute(text("select setting::int as max_connections from pg_settings where name='max_connections'"))).mappings().first()
    total = int(pg_row["total"] or 0) if pg_row else 0
    active = int(pg_row["active"] or 0) if pg_row else 0
    waiting_lock = int(pg_row["waiting_lock"] or 0) if pg_row else 0
    long_running = int(pg_row["long_running"] or 0) if pg_row else 0
    max_connections = int(max_conn["max_connections"] or 0) if max_conn else 0
    ratio = (total / max_connections) if max_connections > 0 else 0
    pg_state = _as_state(long_running == 0 and waiting_lock == 0 and ratio < 0.9, warn=ratio >= 0.7)
    pg_details = [
      f"connections: {total}/{max_connections or '?'}",
      f"active queries: {active}",
      f"long-running (>30s): {long_running}",
      f"waiting locks: {waiting_lock}",
    ]
    long_query_rows = (
      await db.execute(
        text(
          """
          select
            pid,
            now() - query_start as age,
            left(regexp_replace(query, E'\\s+', ' ', 'g'), 120) as query
          from pg_stat_activity
          where datname = current_database()
            and state = 'active'
            and query_start is not null
          order by age desc
          limit 3
          """
        )
      )
    ).mappings().all()
    if long_query_rows:
      pg_details.append("top long queries:")
      for row in long_query_rows:
        pg_details.append(f"- pid {row['pid']} age {row['age']}: {row['query']}")

    lock_rows = (
      await db.execute(
        text(
          """
          select
            blocked.pid as blocked_pid,
            blocker.pid as blocker_pid,
            left(regexp_replace(blocked.query, E'\\s+', ' ', 'g'), 80) as blocked_query
          from pg_catalog.pg_locks blocked_locks
          join pg_catalog.pg_stat_activity blocked on blocked.pid = blocked_locks.pid
          join pg_catalog.pg_locks blocker_locks
            on blocker_locks.locktype = blocked_locks.locktype
           and blocker_locks.database is not distinct from blocked_locks.database
           and blocker_locks.relation is not distinct from blocked_locks.relation
           and blocker_locks.page is not distinct from blocked_locks.page
           and blocker_locks.tuple is not distinct from blocked_locks.tuple
           and blocker_locks.virtualxid is not distinct from blocked_locks.virtualxid
           and blocker_locks.transactionid is not distinct from blocked_locks.transactionid
           and blocker_locks.classid is not distinct from blocked_locks.classid
           and blocker_locks.objid is not distinct from blocked_locks.objid
           and blocker_locks.objsubid is not distinct from blocked_locks.objsubid
           and blocker_locks.pid != blocked_locks.pid
          join pg_catalog.pg_stat_activity blocker on blocker.pid = blocker_locks.pid
          where not blocked_locks.granted
            and blocked.datname = current_database()
          limit 3
          """
        )
      )
    ).mappings().all()
    if lock_rows:
      pg_details.append("blocked lock pairs:")
      for row in lock_rows:
        pg_details.append(f"- blocked {row['blocked_pid']} by {row['blocker_pid']}: {row['blocked_query']}")
  except Exception as e:
    pg_state = "yellow"
    pg_details = [f"pg_stat unavailable: {str(e)[:120]}"]

  sections.append(
    SystemStatusSectionOut(
      key="postgres",
      label="Postgres",
      state=pg_state,
      details=pg_details,
      updatedAt=now,
    )
  )

  # Cache (Redis, if configured)
  cache_state, cache_details = await _redis_metrics()
  sections.append(
    SystemStatusSectionOut(
      key="cache",
      label="Cache",
      state=cache_state,
      details=cache_details,
      updatedAt=now,
    )
  )

  # Queue health (task reminders as queue proxy)
  pending_count = (
    await db.execute(select(func.count()).select_from(TaskReminder).where(TaskReminder.status.in_(["pending", "sending"])))
  ).scalar_one()
  error_count = (await db.execute(select(func.count()).select_from(TaskReminder).where(TaskReminder.status == "error"))).scalar_one()
  retry_sum = (
    await db.execute(select(func.coalesce(func.sum(TaskReminder.attempts), 0)).where(TaskReminder.status.in_(["pending", "sending", "error"])))
  ).scalar_one()
  oldest_row = (
    await db.execute(select(func.min(TaskReminder.scheduled_at)).where(TaskReminder.status.in_(["pending", "sending"])))
  ).scalar_one_or_none()
  oldest_seconds = 0
  if oldest_row:
    oldest_seconds = max(0, int((now - oldest_row).total_seconds()))
  queue_state = _as_state(error_count == 0 and pending_count < 500 and oldest_seconds < 3600, warn=pending_count > 50 or oldest_seconds > 300)
  sections.append(
    SystemStatusSectionOut(
      key="queue",
      label="Queue",
      state=queue_state,
      details=[
        f"depth: {int(pending_count)}",
        f"oldest pending: {oldest_seconds}s",
        f"retries: {int(retry_sum or 0)}",
        f"dlq/errors: {int(error_count)}",
      ],
      updatedAt=now,
    )
  )

  # Notifications (audit + inbox backlog)
  since_hour = now.replace(minute=0, second=0, microsecond=0)
  since_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
  notif_err = (
    await db.execute(
      select(func.count()).select_from(AuditEvent).where(
        AuditEvent.created_at >= since_hour,
        AuditEvent.event_type.in_(["notifications.test.error", "notifications.delivery.error", "reminder.dispatch.error"]),
      )
    )
  ).scalar_one()
  notif_sent = (
    await db.execute(
      select(func.count()).select_from(AuditEvent).where(
        AuditEvent.created_at >= since_hour,
        AuditEvent.event_type.in_(["notifications.test.sent", "notifications.delivery.sent", "reminder.dispatch.sent"]),
      )
    )
  ).scalar_one()
  notif_err_24h = (
    await db.execute(
      select(func.count()).select_from(AuditEvent).where(
        AuditEvent.created_at >= since_day,
        AuditEvent.event_type.in_(["notifications.test.error", "notifications.delivery.error", "reminder.dispatch.error"]),
      )
    )
  ).scalar_one()
  notif_sent_24h = (
    await db.execute(
      select(func.count()).select_from(AuditEvent).where(
        AuditEvent.created_at >= since_day,
        AuditEvent.event_type.in_(["notifications.test.sent", "notifications.delivery.sent", "reminder.dispatch.sent"]),
      )
    )
  ).scalar_one()
  receipt_pending = (
    await db.execute(
      select(func.count()).select_from(AuditEvent).where(
        AuditEvent.created_at >= since_day,
        AuditEvent.event_type.in_(["notifications.test.sent", "notifications.delivery.sent"]),
        text("coalesce(payload->'result'->>'receipt','') <> ''"),
      )
    )
  ).scalar_one()
  total_24h = int(notif_sent_24h) + int(notif_err_24h)
  success_rate_24h = (float(notif_sent_24h) / total_24h * 100.0) if total_24h > 0 else 100.0
  unread_count = (await db.execute(select(func.count()).select_from(InAppNotification).where(InAppNotification.read_at.is_(None)))).scalar_one()
  notif_state = _as_state(notif_err == 0 and success_rate_24h >= 95.0, warn=unread_count > 200 or success_rate_24h < 99.0)
  sections.append(
    SystemStatusSectionOut(
      key="notifications",
      label="Notifications",
      state=notif_state,
      details=[
        f"sent (hour): {int(notif_sent)}",
        f"errors (hour): {int(notif_err)}",
        f"success rate (24h): {success_rate_24h:.1f}%",
        f"emergency receipts pending (24h): {int(receipt_pending)}",
        f"in-app unread: {int(unread_count)}",
      ],
      updatedAt=now,
    )
  )

  # Background jobs (sync + backup)
  last_sync = (
    await db.execute(select(SyncRun.status, SyncRun.finished_at, SyncRun.started_at).order_by(SyncRun.started_at.desc()).limit(1))
  ).first()
  backup_dir = Path(settings.backup_dir)
  backup_files = sorted(backup_dir.glob("*.tar.gz"))
  last_backup = backup_files[-1].stat().st_mtime if backup_files else None
  backup_line = "last backup: none"
  if last_backup:
    backup_line = f"last backup: {datetime.fromtimestamp(last_backup, tz=timezone.utc).isoformat()}"
  job_state = "green"
  details = [backup_line]
  if last_sync:
    sync_status, finished_at, started_at = last_sync
    ts = (finished_at or started_at)
    details.append(f"last jira sync: {sync_status} at {ts.isoformat() if ts else 'n/a'}")
    if sync_status != "success":
      job_state = "yellow"
  else:
    details.append("last jira sync: none")
  details.append(f"pending reminders: {int(pending_count)}")
  sections.append(
    SystemStatusSectionOut(
      key="jobs",
      label="Background jobs",
      state=job_state,
      details=details,
      updatedAt=now,
    )
  )

  return SystemStatusOut(
    generatedAt=now,
    version=settings.app_version,
    buildSha=settings.build_sha,
    sections=sections,
  )
