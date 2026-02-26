from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models import ApiToken, BoardMember, Session as DbSession, User
from app.security import SESSION_COOKIE_NAME, api_token_hash


async def get_db() -> AsyncSession:
  async with SessionLocal() as session:
    yield session


async def get_current_user(
  request: Request,
  db: AsyncSession = Depends(get_db),
  session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> User:
  if not session_id:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
      token = auth.split(" ", 1)[1].strip()
      if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
      h = api_token_hash(token)
      tres = await db.execute(select(ApiToken).where(ApiToken.token_hash == h, ApiToken.revoked_at.is_(None)))
      t = tres.scalar_one_or_none()
      if not t:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
      ures = await db.execute(select(User).where(User.id == t.user_id))
      u = ures.scalar_one_or_none()
      if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
      if hasattr(u, "active") and not bool(getattr(u, "active")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
      if bool(getattr(u, "login_disabled", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Login disabled")
      return u

  if not session_id:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

  res = await db.execute(select(DbSession).where(DbSession.id == session_id))
  s = res.scalar_one_or_none()
  if not s:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
  if s.expires_at < datetime.now(timezone.utc):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

  ures = await db.execute(select(User).where(User.id == s.user_id))
  u = ures.scalar_one_or_none()
  if not u:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
  if hasattr(u, "active") and not bool(getattr(u, "active")):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
  if bool(getattr(u, "login_disabled", False)):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Login disabled")
  return u


async def require_admin_mfa_guard(
  request: Request,
  db: AsyncSession = Depends(get_db),
  user: User = Depends(get_current_user),
  session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> None:
  await require_admin_mfa(request, user, db, session_id)


async def require_board_role(
  board_id: str,
  min_role: str,
  user: User,
  db: AsyncSession,
) -> str:
  # role order: viewer < member < admin
  order = {"viewer": 0, "member": 1, "admin": 2}
  res = await db.execute(
    select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == user.id)
  )
  m = res.scalar_one_or_none()
  if not m:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No board access")
  if order.get(m.role, -1) < order.get(min_role, 0):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
  return m.role


async def require_admin_mfa(
  request: Request,
  user: User,
  db: AsyncSession,
  session_id: str | None,
) -> None:
  # Enforce MFA for admin-only operations.
  if user.role != "admin":
    return
  if not getattr(user, "mfa_enabled", False):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFA setup required for admin")
  if not session_id:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
  res = await db.execute(select(DbSession).where(DbSession.id == session_id))
  s = res.scalar_one_or_none()
  if not s:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
  if not bool(getattr(s, "mfa_verified", False)):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA required")


def client_ip(request: Request) -> str | None:
  return request.client.host if request.client else None
