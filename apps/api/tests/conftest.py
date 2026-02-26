from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import SessionLocal, engine
from app.main import app
from app.security import totp_code
from app.rate_limit import limiter
from app.models import (
  AuditEvent,
  Attachment,
  Board,
  BoardMember,
  BoardTaskPriority,
  BoardTaskType,
  ChecklistItem,
  Comment,
  InboundWebhookEvent,
  InAppNotification,
  ApiToken,
  MfaTrustedDevice,
  BackupPolicy,
  JiraConnection,
  OpenProjectConnection,
  JiraSyncProfile,
  Lane,
  PasswordResetToken,
  Session,
  SyncRun,
  Task,
  TaskDependency,
  TaskImportKey,
  TaskReminder,
  User,
  WebhookSecret,
)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
  return "asyncio"


async def _reset_db() -> None:
  limiter.reset_prefix("auth:")
  async with SessionLocal() as db:
    # Keep seeded users; wipe everything else for deterministic tests.
    await db.execute(delete(AuditEvent))
    await db.execute(delete(SyncRun))
    await db.execute(delete(JiraSyncProfile))
    await db.execute(delete(Comment))
    await db.execute(delete(ChecklistItem))
    await db.execute(delete(TaskDependency))
    await db.execute(delete(TaskImportKey))
    await db.execute(delete(TaskReminder))
    await db.execute(delete(Attachment))
    await db.execute(delete(Task))
    await db.execute(delete(Lane))
    await db.execute(delete(BoardMember))
    await db.execute(delete(BoardTaskType))
    await db.execute(delete(BoardTaskPriority))
    await db.execute(delete(Board))
    await db.execute(delete(JiraConnection))
    await db.execute(delete(OpenProjectConnection))
    await db.execute(delete(InboundWebhookEvent))
    await db.execute(delete(WebhookSecret))
    await db.execute(delete(InAppNotification))
    await db.execute(delete(PasswordResetToken))
    await db.execute(delete(Session))
    await db.execute(delete(ApiToken))
    await db.execute(delete(MfaTrustedDevice))
    await db.execute(delete(BackupPolicy))

    keep = ["admin@neonlanes.local", "member@neonlanes.local"]
    await db.execute(delete(User).where(User.email.notin_(keep)))
    # Reset seeded users to known state for each test.
    await db.execute(
      update(User)
      .where(User.email.in_(keep))
      .values(
        mfa_enabled=False,
        mfa_secret_encrypted=None,
        mfa_recovery_codes_encrypted=None,
        notification_prefs={"mentions": True, "comments": True, "moves": True, "assignments": True, "overdue": True},
        quiet_hours_enabled=False,
        quiet_hours_start=None,
        quiet_hours_end=None,
        active=True,
        login_disabled=False,
      )
    )
    await db.commit()
  await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_between_tests() -> None:
  db_name = settings.database_url.rsplit("/", 1)[-1]
  if "test" not in db_name:
    raise RuntimeError(
      "Refusing to run destructive tests against non-test DB. "
      "Set DATABASE_URL to a *_test database (e.g. neonlanes_test)."
    )
  await _reset_db()
  yield
  await _reset_db()


@pytest.fixture
async def client() -> AsyncClient:
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://localhost") as c:
    yield c


async def login(
  client: AsyncClient,
  email: str,
  password: str,
  *,
  totpCode: str | None = None,
  recoveryCode: str | None = None,
  rememberDevice: bool | None = None,
) -> dict[str, str]:
  payload: dict = {"email": email, "password": password}
  if totpCode:
    payload["totpCode"] = totpCode
  if recoveryCode:
    payload["recoveryCode"] = recoveryCode
  if rememberDevice is not None:
    payload["rememberDevice"] = rememberDevice
  res = await client.post("/auth/login", json=payload)
  assert res.status_code == 200, res.text
  cookie = res.headers.get("set-cookie")
  assert cookie and "nl_session=" in cookie
  # httpx will store cookies automatically, but return a dict for clarity
  return {"ok": "true"}


async def seeded_user_id(email: str) -> str:
  async with SessionLocal() as db:
    res = await db.execute(select(User).where(User.email == email))
    u = res.scalar_one()
    return u.id


async def enable_admin_mfa(client: AsyncClient) -> dict:
  # Assumes caller is already logged in as admin (password-only).
  start = await client.post("/auth/mfa/start", json={"password": "admin1234"})
  assert start.status_code == 200, start.text
  secret = start.json()["secret"]
  confirm = await client.post("/auth/mfa/confirm", json={"totpCode": totp_code(secret)})
  assert confirm.status_code == 200, confirm.text
  return {"secret": secret, "recoveryCodes": confirm.json()["recoveryCodes"]}
