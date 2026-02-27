from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import monotonic

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import delete, select

from app.config import settings
from app.jira.client import JiraApiError
from app.security import IntegrationSecretDecryptError
from app.routers.ai import router as ai_router
from app.routers.audit import router as audit_router
from app.routers.auth import router as auth_router
from app.routers.boards import router as boards_router
from app.routers.backups import router as backups_router
from app.routers.github import router as github_router
from app.routers.integrations import router as integrations_router
from app.routers.jira import router as jira_router
from app.routers.lanes import router as lanes_router
from app.routers.notifications import router as notifications_router
from app.routers.openproject import router as openproject_router
from app.routers.system_status import router as system_status_router
from app.routers.tasks import router as tasks_router
from app.routers.task_fields import router as task_fields_router
from app.routers.users import router as users_router
from app.routers.webhooks import router as webhooks_router
from app.db import SessionLocal
from app.jira.service import sync_now
from app.models import JiraSyncProfile, Session as DbSession
from app.backups.service import create_full_backup, get_backup_policy, purge_old_backups, should_run_scheduled_backup
from app.reminders.service import dispatch_due_reminders_once
from app.metrics import runtime_metrics

app = FastAPI(
  title="Task-Daddy API",
  version="0.1.0",
  docs_url="/docs" if settings.api_docs_enabled else None,
  redoc_url="/redoc" if settings.api_docs_enabled else None,
  openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)


@app.exception_handler(JiraApiError)
async def _jira_api_error_handler(_, exc: JiraApiError) -> JSONResponse:
  return JSONResponse(
    status_code=400,
    content={"detail": {"message": exc.message, "statusCode": exc.status_code, "jira": exc.details}},
  )


@app.exception_handler(IntegrationSecretDecryptError)
async def _integration_secret_error_handler(_, exc: IntegrationSecretDecryptError) -> JSONResponse:
  return JSONResponse(status_code=400, content={"detail": str(exc)})

app.add_middleware(
  CORSMiddleware,
  allow_origins=settings.cors_origin_list(),
  allow_origin_regex=settings.cors_origin_regex,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list())

app.include_router(auth_router)
app.include_router(boards_router)
app.include_router(lanes_router)
app.include_router(tasks_router)
app.include_router(task_fields_router)
app.include_router(audit_router)
app.include_router(ai_router)
app.include_router(jira_router)
app.include_router(github_router)
app.include_router(integrations_router)
app.include_router(backups_router)
app.include_router(users_router)
app.include_router(webhooks_router)
app.include_router(notifications_router)
app.include_router(openproject_router)
app.include_router(system_status_router)


@app.middleware("http")
async def _request_metrics_middleware(request, call_next):
  start = monotonic()
  response = await call_next(request)
  elapsed_ms = (monotonic() - start) * 1000.0
  runtime_metrics.observe_request(response.status_code, elapsed_ms)
  response.headers.setdefault("X-Content-Type-Options", "nosniff")
  response.headers.setdefault("X-Frame-Options", "DENY")
  response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
  response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
  return response


@app.get("/health")
async def health() -> dict:
  return {"ok": True}


@app.get("/version")
async def version() -> dict:
  return {"version": settings.app_version, "buildSha": settings.build_sha}


_jira_loop_task: asyncio.Task | None = None
_backup_loop_task: asyncio.Task | None = None
_reminder_loop_task: asyncio.Task | None = None


def _is_test_db() -> bool:
  try:
    db_name = settings.database_url.rsplit("/", 1)[-1]
    return "test" in db_name
  except Exception:
    return False


async def _jira_auto_sync_loop() -> None:
  while True:
    await asyncio.sleep(max(10, int(settings.jira_auto_sync_interval_seconds)))
    async with SessionLocal() as db:
      res = await db.execute(select(JiraSyncProfile).order_by(JiraSyncProfile.created_at.desc()).limit(50))
      profiles = res.scalars().all()
      if not profiles:
        continue
      for p in profiles:
        run = await sync_now(db, profile=p, actor_id=None)
        db.add(run)
      await db.commit()


def _parse_hhmm_utc(s: str) -> tuple[int, int]:
  txt = (s or "").strip()
  if not txt:
    return (3, 0)
  parts = txt.split(":")
  if len(parts) != 2:
    return (3, 0)
  try:
    hh = int(parts[0])
    mm = int(parts[1])
    hh = max(0, min(23, hh))
    mm = max(0, min(59, mm))
    return (hh, mm)
  except Exception:
    return (3, 0)


def _seconds_until_next_utc(hh: int, mm: int) -> float:
  # Avoid adding datetime dependency; compute using asyncio loop time + UTC now via time.time()
  import time
  from datetime import datetime, timedelta, timezone

  now = datetime.now(tz=timezone.utc)
  target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
  if target <= now:
    target = target + timedelta(days=1)
  return max(1.0, (target - now).total_seconds())


async def _backup_daily_loop() -> None:
  hh, mm = _parse_hhmm_utc(settings.backup_auto_time_utc)
  while True:
    async with SessionLocal() as db:
      try:
        policy = await get_backup_policy(db)
      except Exception:
        policy = None
      try:
        if policy is not None:
          purge_old_backups(
            retention_days=policy.retentionDays,
            max_backups=policy.maxBackups,
            max_total_size_mb=policy.maxTotalSizeMb,
          )
      except Exception:
        pass

    await asyncio.sleep(_seconds_until_next_utc(hh, mm))
    async with SessionLocal() as db:
      try:
        policy = await get_backup_policy(db)
      except Exception:
        policy = None
      try:
        if policy is None:
          await create_full_backup(db)
        else:
          run_now, _wait_seconds = should_run_scheduled_backup(min_interval_minutes=policy.minIntervalMinutes)
          if run_now:
            await create_full_backup(db)
      except Exception:
        # Do not crash the app due to backup failures.
        pass
      try:
        if policy is not None:
          purge_old_backups(
            retention_days=policy.retentionDays,
            max_backups=policy.maxBackups,
            max_total_size_mb=policy.maxTotalSizeMb,
          )
      except Exception:
        pass


async def _reminder_dispatch_loop() -> None:
  # Simple poller (MVP): checks for due reminders and dispatches in-app + optional external.
  while True:
    await asyncio.sleep(20)
    async with SessionLocal() as db:
      try:
        await dispatch_due_reminders_once(db)
      except Exception:
        # Never crash the app due to reminder failures.
        pass


async def _force_logout_on_startup() -> None:
  async with SessionLocal() as db:
    await db.execute(delete(DbSession))
    await db.commit()


@app.on_event("startup")
async def _startup() -> None:
  global _jira_loop_task, _backup_loop_task, _reminder_loop_task
  if _is_test_db():
    return
  if not settings.app_secret or settings.app_secret.strip().lower() in {"dev-secret-change-me", "replace_with_strong_random_secret"}:
    raise RuntimeError("APP_SECRET is required and must not be a placeholder")
  if not settings.fernet_key or settings.fernet_key.strip() in {"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "REPLACE_WITH_FERNET_KEY"}:
    raise RuntimeError("FERNET_KEY is required and must not be a placeholder")
  if settings.force_logout_on_start:
    await _force_logout_on_startup()
  if settings.jira_auto_sync_enabled and _jira_loop_task is None:
    _jira_loop_task = asyncio.create_task(_jira_auto_sync_loop())
  if settings.backup_auto_enabled and _backup_loop_task is None:
    _backup_loop_task = asyncio.create_task(_backup_daily_loop())
  if _reminder_loop_task is None:
    _reminder_loop_task = asyncio.create_task(_reminder_dispatch_loop())
