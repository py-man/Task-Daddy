from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db, require_admin_mfa_guard
from app.models import PasswordResetToken, Session as DbSession, Task, User
from app.schemas import UserCreateIn, UserCreateOut, UserDeleteIn, UserInviteIn, UserInviteOut, UserOut, UserUpdateIn
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _hash_token(token: str) -> str:
  return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _user_out(u: User) -> UserOut:
  return UserOut(
    id=u.id,
    email=u.email,
    name=u.name,
    role=u.role,
    avatarUrl=u.avatar_url,
    timezone=getattr(u, "timezone", None),
    jiraAccountId=getattr(u, "jira_account_id", None),
    mfaEnabled=bool(getattr(u, "mfa_enabled", False)),
    active=bool(getattr(u, "active", True)),
    loginDisabled=bool(getattr(u, "login_disabled", False)),
  )


async def _delete_user_impl(*, user_id: str, payload: UserDeleteIn, actor: User, db: AsyncSession) -> dict:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  if actor.id == user_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
  res = await db.execute(select(User).where(User.id == user_id))
  u = res.scalar_one_or_none()
  if not u:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

  # Idempotency: allow repeating delete against an already-deleted user.
  if (u.email or "").startswith("deleted+") and bool(getattr(u, "active", True)) is False:
    return {"ok": True}

  if payload.mode == "reassign":
    if not payload.reassignToUserId:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reassignToUserId is required")
    if payload.reassignToUserId == u.id:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reassignToUserId must be different")
    rres = await db.execute(select(User).where(User.id == payload.reassignToUserId))
    dest = rres.scalar_one_or_none()
    if not dest or not bool(getattr(dest, "active", True)):
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reassignTo user")
    await db.execute(update(Task).where(Task.owner_id == u.id).values(owner_id=dest.id))
  else:
    await db.execute(update(Task).where(Task.owner_id == u.id).values(owner_id=None))

  await db.execute(delete(DbSession).where(DbSession.user_id == u.id))
  await db.execute(update(User).where(User.id == u.id).values(active=False, email=f"deleted+{u.id}@taskdaddy.local", name="Deleted User"))
  await db.commit()
  return {"ok": True}


@router.get("", response_model=list[UserOut])
async def list_users(
  includeInactive: bool = False,
  includeDeleted: bool = False,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> list[UserOut]:
  q = select(User).order_by(User.created_at.asc())
  if not includeDeleted:
    q = q.where(~User.email.like("deleted+%"))
  if not (user.role == "admin" and includeInactive):
    q = q.where(User.active.is_(True))
  res = await db.execute(q)
  out = []
  for u in res.scalars().all():
    out.append(_user_out(u))
  return out


@router.post("", response_model=UserCreateOut)
async def create_user(
  payload: UserCreateIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> UserCreateOut:
  if actor.role != "admin":
    # MVP: global admins only; board-level admin creation can be added later.
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

  email = payload.email.strip().lower()
  if not email:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email is required")
  if "@" not in email or email.startswith("@") or email.endswith("@"):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
  name = payload.name.strip()
  if not name:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")

  res = await db.execute(select(User).where(User.email == email))
  existing = res.scalar_one_or_none()
  if existing:
    return UserCreateOut(user=_user_out(existing), tempPassword=None)

  temp_password: str | None = None
  password = payload.password
  if not password:
    temp_password = secrets.token_urlsafe(12)
    password = temp_password

  u = User(
    email=email,
    name=name,
    role=payload.role,
    password_hash=hash_password(password),
    avatar_url=payload.avatarUrl,
    timezone=None,
    jira_account_id=None,
    active=True,
  )
  db.add(u)
  await db.commit()
  return UserCreateOut(user=_user_out(u), tempPassword=temp_password)


@router.post("/invite", response_model=UserInviteOut)
async def invite_user(
  payload: UserInviteIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> UserInviteOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

  email = payload.email.strip().lower()
  if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
  name = payload.name.strip()
  if not name:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")

  created = False
  res = await db.execute(select(User).where(User.email == email))
  u = res.scalar_one_or_none()
  if u and str(u.email).startswith("deleted+"):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email cannot be reused (deleted user placeholder)")

  if not u:
    created = True
    u = User(
      email=email,
      name=name,
      role=payload.role,
      password_hash=hash_password(secrets.token_urlsafe(24)),
      avatar_url=None,
      timezone=None,
      jira_account_id=None,
      active=True,
    )
    db.add(u)
    await db.flush()
  else:
    u.name = name or u.name
    u.role = payload.role
    u.active = True
    await db.execute(delete(DbSession).where(DbSession.user_id == u.id))

  # Keep only the newest reset/invite token valid for this user.
  await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == u.id, PasswordResetToken.used_at.is_(None)))

  token = secrets.token_urlsafe(32)
  expires = datetime.now(timezone.utc) + timedelta(hours=24)
  prt = PasswordResetToken(
    user_id=u.id,
    token_hash=_hash_token(token),
    request_ip=None,
    expires_at=expires,
    created_at=datetime.now(timezone.utc),
  )
  db.add(prt)
  await db.commit()

  base = (payload.inviteBaseUrl or "").strip().rstrip("/")
  if not base:
    base = "http://localhost:3000"
  invite_url = f"{base}/login?mode=reset&token={token}"
  return UserInviteOut(
    user=_user_out(u),
    inviteToken=token,
    inviteUrl=invite_url,
    expiresAt=expires,
    created=created,
  )


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
  user_id: str,
  payload: UserUpdateIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> UserOut:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  res = await db.execute(select(User).where(User.id == user_id))
  u = res.scalar_one_or_none()
  if not u:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

  fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
  if "email" in fields_set and payload.email is not None:
    email = payload.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
    exists = await db.execute(select(User.id).where(User.email == email, User.id != u.id))
    if exists.scalar_one_or_none():
      raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    u.email = email
  if "name" in fields_set and payload.name is not None:
    u.name = payload.name.strip()
  if "role" in fields_set and payload.role is not None:
    u.role = payload.role
  if "avatarUrl" in fields_set:
    u.avatar_url = payload.avatarUrl
  if "timezone" in fields_set:
    u.timezone = payload.timezone
  if "jiraAccountId" in fields_set:
    u.jira_account_id = payload.jiraAccountId
  if "active" in fields_set and payload.active is not None:
    u.active = bool(payload.active)
    if not u.active:
      await db.execute(delete(DbSession).where(DbSession.user_id == u.id))
  if "loginDisabled" in fields_set and payload.loginDisabled is not None:
    u.login_disabled = bool(payload.loginDisabled)
    if u.login_disabled:
      await db.execute(delete(DbSession).where(DbSession.user_id == u.id))
  if "password" in fields_set and payload.password is not None and payload.password.strip():
    u.password_hash = hash_password(payload.password.strip())
    await db.execute(delete(DbSession).where(DbSession.user_id == u.id))

  await db.commit()
  return _user_out(u)


@router.delete("/{user_id}")
async def delete_user(
  user_id: str,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> dict:
  # Backward-compatible: default to unassign tasks.
  return await _delete_user_impl(user_id=user_id, payload=UserDeleteIn(mode="unassign"), actor=actor, db=db)


@router.post("/{user_id}/delete")
async def delete_user_v2(
  user_id: str,
  payload: UserDeleteIn,
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> dict:
  return await _delete_user_impl(user_id=user_id, payload=payload, actor=actor, db=db)


@router.get("/avatar/{filename}")
async def user_avatar_file(filename: str) -> FileResponse:
  safe = os.path.basename(filename)
  if not safe or safe != filename:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")
  path = os.path.join("data/uploads", safe)
  if not os.path.isfile(path):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
  return FileResponse(path)


@router.post("/{user_id}/avatar")
async def upload_user_avatar(
  user_id: str,
  file: UploadFile = File(...),
  actor: User = Depends(get_current_user),
  _: None = Depends(require_admin_mfa_guard),
  db: AsyncSession = Depends(get_db),
) -> dict:
  if actor.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

  res = await db.execute(select(User).where(User.id == user_id))
  u = res.scalar_one_or_none()
  if not u:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

  content_type = (file.content_type or "").lower()
  allowed_types = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
  ext = allowed_types.get(content_type)
  if not ext:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

  data = await file.read()
  if not data or len(data) > 2 * 1024 * 1024:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar must be 1B..2MB")

  os.makedirs("data/uploads", exist_ok=True)
  name = f"avatar_{u.id}_{uuid4().hex[:10]}{ext}"
  out_path = os.path.join("data/uploads", name)
  with open(out_path, "wb") as f:
    f.write(data)

  u.avatar_url = f"/users/avatar/{name}"
  await db.commit()
  return {"ok": True, "avatarPath": u.avatar_url}
