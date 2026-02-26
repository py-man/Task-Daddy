from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_current_user, get_db, require_admin_mfa
from app.models import ApiToken, MfaTrustedDevice, NotificationDestination, PasswordResetToken, Session as DbSession, User
from app.notifications.service import NotificationMessage, decrypt_destination_config, provider_for
from app.rate_limit import limiter
from app.schemas import (
  ApiTokenCreateIn,
  ApiTokenCreateOut,
  ApiTokenOut,
  ApiTokenRevokeIn,
  LoginIn,
  MfaTrustedDeviceOut,
  MfaTrustedDeviceRevokeIn,
  MfaConfirmIn,
  MfaConfirmOut,
  MfaDisableIn,
  MfaStartIn,
  MfaStartOut,
  PasswordResetConfirmIn,
  PasswordResetRequestIn,
  SessionOut,
  SessionRevokeIn,
  UserOut,
)
from app.security import (
  SESSION_COOKIE_NAME,
  SESSION_TTL_DAYS,
  MFA_TRUST_COOKIE_NAME,
  decrypt_secret,
  encrypt_secret,
  api_token_hash,
  mfa_trusted_token_hash,
  mfa_trusted_token_new,
  new_session_expires_at,
  recovery_code_hash,
  recovery_codes_generate,
  totp_code,
  totp_new_secret,
  totp_verify,
  verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _audit(db: AsyncSession, *, event_type: str, entity_type: str, entity_id: str | None, actor_id: str | None, payload: dict) -> None:
  from app.audit import write_audit

  await write_audit(db, event_type=event_type, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, payload=payload)


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


def _rate_limit_or_429(*, key: str, limit: int, window_seconds: int) -> None:
  allowed, retry_after = limiter.hit(key, limit=limit, window_seconds=window_seconds)
  if allowed:
    return
  raise HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail={"code": "rate_limited", "message": "Too many requests", "retryAfterSeconds": retry_after},
    headers={"Retry-After": str(retry_after)},
  )


def _trusted_device_out(d: MfaTrustedDevice) -> MfaTrustedDeviceOut:
  return MfaTrustedDeviceOut(
    id=d.id,
    userId=d.user_id,
    createdIp=d.created_ip,
    userAgent=d.user_agent,
    createdAt=d.created_at,
    lastUsedAt=d.last_used_at,
    expiresAt=d.expires_at,
    revokedAt=d.revoked_at,
  )


@router.post("/login", response_model=UserOut)
async def login(payload: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> UserOut:
  ip = request.client.host if request.client else "unknown"
  email_key = (payload.email or "").strip().lower()
  _rate_limit_or_429(key=f"auth:login:ip:{ip}", limit=int(settings.rate_limit_login_ip_per_minute), window_seconds=60)
  if email_key:
    _rate_limit_or_429(key=f"auth:login:email:{email_key}", limit=int(settings.rate_limit_login_email_per_minute), window_seconds=60)

  normalized_email = (payload.email or "").strip().lower()
  res = await db.execute(select(User).where(User.email == normalized_email))
  u = res.scalar_one_or_none()
  if not u or not verify_password(payload.password, u.password_hash):
    await _audit(db, event_type="auth.login.failed", entity_type="Auth", entity_id=None, actor_id=None, payload={"email": normalized_email, "ip": ip})
    await db.commit()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
  if hasattr(u, "active") and not bool(getattr(u, "active")):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
  if bool(getattr(u, "login_disabled", False)):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Login disabled")

  mfa_enabled = bool(getattr(u, "mfa_enabled", False))
  mfa_verified = False
  trusted_raw = request.cookies.get(MFA_TRUST_COOKIE_NAME)
  remember_raw: str | None = None
  trusted_device_id: str | None = None
  if mfa_enabled:
    if trusted_raw:
      tr = await db.execute(
        select(MfaTrustedDevice).where(
          MfaTrustedDevice.user_id == u.id,
          MfaTrustedDevice.token_hash == mfa_trusted_token_hash(trusted_raw),
          MfaTrustedDevice.revoked_at.is_(None),
        )
      )
      td = tr.scalar_one_or_none()
      if td and td.expires_at > datetime.now(timezone.utc):
        td.last_used_at = datetime.now(timezone.utc)
        mfa_verified = True
        trusted_device_id = td.id
      elif td and td.expires_at <= datetime.now(timezone.utc):
        td.revoked_at = datetime.now(timezone.utc)

    if (not mfa_verified) and payload.totpCode:
      if not u.mfa_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA misconfigured")
      secret = decrypt_secret(u.mfa_secret_encrypted)
      if not totp_verify(secret, payload.totpCode):
        await _audit(db, event_type="auth.mfa.failed", entity_type="User", entity_id=u.id, actor_id=u.id, payload={})
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
      mfa_verified = True
    elif (not mfa_verified) and payload.recoveryCode:
      if not u.mfa_recovery_codes_encrypted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA required")
      hashes: list[str] = []
      try:
        hashes = list(__import__("json").loads(decrypt_secret(u.mfa_recovery_codes_encrypted)))
      except Exception:
        hashes = []
      h = recovery_code_hash(payload.recoveryCode)
      if h not in hashes:
        await _audit(db, event_type="auth.mfa.failed", entity_type="User", entity_id=u.id, actor_id=u.id, payload={"mode": "recovery"})
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code")
      hashes = [x for x in hashes if x != h]
      u.mfa_recovery_codes_encrypted = encrypt_secret(__import__("json").dumps(hashes))
      mfa_verified = True
    elif not mfa_verified:
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA required")

    if mfa_verified and payload.rememberDevice and (payload.totpCode or payload.recoveryCode):
      remember_raw = mfa_trusted_token_new()
      td = MfaTrustedDevice(
        user_id=u.id,
        token_hash=mfa_trusted_token_hash(remember_raw),
        created_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=max(1, int(settings.mfa_trusted_device_ttl_days))),
      )
      db.add(td)
      await db.flush()
      trusted_device_id = td.id

  s = DbSession(
    user_id=u.id,
    expires_at=new_session_expires_at(),
    mfa_verified=mfa_verified,
    created_ip=request.client.host if request.client else None,
    user_agent=request.headers.get("user-agent"),
  )
  db.add(s)
  await _audit(
    db,
    event_type="auth.login.success",
    entity_type="User",
    entity_id=u.id,
    actor_id=u.id,
    payload={"mfa": mfa_verified, "trustedDeviceId": trusted_device_id},
  )
  await db.commit()

  response.set_cookie(
    key=SESSION_COOKIE_NAME,
    value=s.id,
    httponly=True,
    secure=settings.cookie_secure,
    samesite="lax",
    domain=settings.cookie_domain or None,
    max_age=int(SESSION_TTL_DAYS * 86400),
    expires=s.expires_at,
    path="/",
  )
  if remember_raw:
    response.set_cookie(
      key=MFA_TRUST_COOKIE_NAME,
      value=remember_raw,
      httponly=True,
      secure=settings.cookie_secure,
      samesite="lax",
      domain=settings.cookie_domain or None,
      max_age=int(max(1, int(settings.mfa_trusted_device_ttl_days)) * 86400),
      expires=datetime.now(timezone.utc) + timedelta(days=max(1, int(settings.mfa_trusted_device_ttl_days))),
      path="/",
    )
  elif mfa_enabled and mfa_verified and trusted_device_id and not payload.rememberDevice:
    # Keep existing trusted cookie if present; only clear when explicitly revoking or logging out.
    pass
  elif mfa_enabled and trusted_raw and not trusted_device_id:
    response.delete_cookie(key=MFA_TRUST_COOKIE_NAME, path="/")
  return _user_out(u)


@router.post("/logout")
async def logout(
  response: Response,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  # best-effort: delete all sessions for user
  await db.execute(delete(DbSession).where(DbSession.user_id == user.id))
  await db.execute(delete(MfaTrustedDevice).where(MfaTrustedDevice.user_id == user.id))
  response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
  response.delete_cookie(key=MFA_TRUST_COOKIE_NAME, path="/")
  await db.commit()
  return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
  return _user_out(user)


@router.post("/mfa/start", response_model=MfaStartOut)
async def mfa_start(payload: MfaStartIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> MfaStartOut:
  # Require password confirmation
  if not verify_password(payload.password, user.password_hash):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

  secret = totp_new_secret()
  user.mfa_secret_encrypted = encrypt_secret(secret)
  user.mfa_enabled = False
  user.mfa_recovery_codes_encrypted = None
  await _audit(db, event_type="mfa.start", entity_type="User", entity_id=user.id, actor_id=user.id, payload={})
  await db.commit()

  issuer = "Task-Daddy"
  label = f"{issuer}:{user.email}"
  otpauth = f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&digits=6&period=30"
  return MfaStartOut(otpauthUri=otpauth, secret=secret)


@router.post("/mfa/confirm", response_model=MfaConfirmOut)
async def mfa_confirm(
  payload: MfaConfirmIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> MfaConfirmOut:
  if not user.mfa_secret_encrypted:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA not started")
  secret = decrypt_secret(user.mfa_secret_encrypted)
  if not totp_verify(secret, payload.totpCode):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

  codes = recovery_codes_generate(10)
  hashes = [recovery_code_hash(c) for c in codes]
  user.mfa_recovery_codes_encrypted = encrypt_secret(__import__("json").dumps(hashes))
  user.mfa_enabled = True

  # Convenience: once the user has proven possession of TOTP during enrollment,
  # mark the current session as MFA-verified so admin actions work immediately
  # without forcing a logout/login loop.
  if session_id:
    sres = await db.execute(select(DbSession).where(DbSession.id == session_id, DbSession.user_id == user.id))
    s = sres.scalar_one_or_none()
    if s is not None:
      s.mfa_verified = True

  await _audit(db, event_type="mfa.enabled", entity_type="User", entity_id=user.id, actor_id=user.id, payload={})
  await db.commit()
  return MfaConfirmOut(recoveryCodes=codes)


@router.post("/mfa/disable")
async def mfa_disable(payload: MfaDisableIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  if not verify_password(payload.password, user.password_hash):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
  if not user.mfa_secret_encrypted:
    user.mfa_enabled = False
    user.mfa_recovery_codes_encrypted = None
    await db.commit()
    return {"ok": True}
  secret = decrypt_secret(user.mfa_secret_encrypted)

  ok = False
  if payload.totpCode and totp_verify(secret, payload.totpCode):
    ok = True
  if (not ok) and payload.recoveryCode and user.mfa_recovery_codes_encrypted:
    try:
      hashes = list(__import__("json").loads(decrypt_secret(user.mfa_recovery_codes_encrypted)))
    except Exception:
      hashes = []
    if recovery_code_hash(payload.recoveryCode) in hashes:
      ok = True
  if not ok:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")

  user.mfa_enabled = False
  user.mfa_secret_encrypted = None
  user.mfa_recovery_codes_encrypted = None
  await _audit(db, event_type="mfa.disabled", entity_type="User", entity_id=user.id, actor_id=user.id, payload={})
  await db.commit()
  return {"ok": True}


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[SessionOut]:
  res = await db.execute(select(DbSession).where(DbSession.user_id == user.id).order_by(DbSession.created_at.desc()))
  out: list[SessionOut] = []
  for s in res.scalars().all():
    out.append(
      SessionOut(
        id=s.id,
        userId=s.user_id,
        mfaVerified=bool(getattr(s, "mfa_verified", False)),
        createdIp=getattr(s, "created_ip", None),
        userAgent=getattr(s, "user_agent", None),
        createdAt=s.created_at,
        expiresAt=s.expires_at,
      )
    )
  return out


@router.get("/mfa/trusted_devices", response_model=list[MfaTrustedDeviceOut])
async def list_mfa_trusted_devices(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[MfaTrustedDeviceOut]:
  res = await db.execute(
    select(MfaTrustedDevice)
    .where(MfaTrustedDevice.user_id == user.id)
    .order_by(MfaTrustedDevice.created_at.desc())
  )
  return [_trusted_device_out(d) for d in res.scalars().all()]


@router.post("/mfa/trusted_devices/revoke")
async def revoke_mfa_trusted_device(
  payload: MfaTrustedDeviceRevokeIn,
  response: Response,
  request: Request,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  res = await db.execute(select(MfaTrustedDevice).where(MfaTrustedDevice.id == payload.deviceId, MfaTrustedDevice.user_id == user.id))
  d = res.scalar_one_or_none()
  if not d:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trusted device not found")
  d.revoked_at = datetime.now(timezone.utc)
  await _audit(
    db,
    event_type="auth.mfa.trusted_device.revoked",
    entity_type="MfaTrustedDevice",
    entity_id=d.id,
    actor_id=user.id,
    payload={"ip": request.client.host if request.client else None},
  )
  await db.commit()
  response.delete_cookie(key=MFA_TRUST_COOKIE_NAME, path="/")
  return {"ok": True}


@router.post("/mfa/trusted_devices/revoke_all")
async def revoke_all_mfa_trusted_devices(
  response: Response,
  request: Request,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  now = datetime.now(timezone.utc)
  res = await db.execute(select(MfaTrustedDevice).where(MfaTrustedDevice.user_id == user.id, MfaTrustedDevice.revoked_at.is_(None)))
  devices = res.scalars().all()
  for d in devices:
    d.revoked_at = now
  await _audit(
    db,
    event_type="auth.mfa.trusted_device.revoked_all",
    entity_type="User",
    entity_id=user.id,
    actor_id=user.id,
    payload={"count": len(devices), "ip": request.client.host if request.client else None},
  )
  await db.commit()
  response.delete_cookie(key=MFA_TRUST_COOKIE_NAME, path="/")
  return {"ok": True}


@router.post("/sessions/revoke")
async def revoke_session(payload: SessionRevokeIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  await db.execute(delete(DbSession).where(DbSession.user_id == user.id, DbSession.id == payload.sessionId))
  await _audit(db, event_type="auth.session.revoked", entity_type="Session", entity_id=payload.sessionId, actor_id=user.id, payload={})
  await db.commit()
  return {"ok": True}


@router.post("/sessions/revoke_all")
async def revoke_all_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  await db.execute(delete(DbSession).where(DbSession.user_id == user.id))
  await _audit(db, event_type="auth.session.revoked_all", entity_type="User", entity_id=user.id, actor_id=user.id, payload={})
  await db.commit()
  return {"ok": True}


@router.post("/sessions/revoke_all_global")
async def revoke_all_sessions_global(
  request: Request,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
  if not session_id:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session required")
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
  await require_admin_mfa(request, user, db, session_id)
  await db.execute(delete(DbSession))
  await _audit(
    db,
    event_type="auth.session.revoked_all_global",
    entity_type="Session",
    entity_id=None,
    actor_id=user.id,
    payload={"ip": request.client.host if request.client else None},
  )
  await db.commit()
  return {"ok": True}


def _hash_token(token: str) -> str:
  return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_hint(token: str) -> str:
  t = (token or "").strip()
  if not t:
    return ""
  if len(t) <= 6:
    return f"…{t}"
  return f"…{t[-6:]}"


def _api_token_out(t: ApiToken) -> ApiTokenOut:
  return ApiTokenOut(
    id=t.id,
    userId=t.user_id,
    name=t.name,
    tokenHint=t.token_hint,
    createdAt=t.created_at,
    lastUsedAt=t.last_used_at,
    revokedAt=t.revoked_at,
  )


@router.get("/tokens", response_model=list[ApiTokenOut])
async def list_api_tokens(
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> list[ApiTokenOut]:
  if not session_id:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session required")
  res = await db.execute(select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc()))
  return [_api_token_out(t) for t in res.scalars().all()]


@router.post("/tokens", response_model=ApiTokenCreateOut)
async def create_api_token(
  payload: ApiTokenCreateIn,
  request: Request,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> ApiTokenCreateOut:
  if not session_id:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session required")
  if not verify_password(payload.password, user.password_hash):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

  # Creating a long-lived token is a privileged action for admins: require MFA-verified session.
  if user.role == "admin":
    await require_admin_mfa(request, user, db, session_id)

  res = await db.execute(select(ApiToken).where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None)))
  active = res.scalars().all()
  if len(active) >= 25:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many active tokens")

  raw = "nlpat_" + secrets.token_urlsafe(32)
  h = api_token_hash(raw)
  t = ApiToken(user_id=user.id, name=payload.name.strip(), token_hash=h, token_hint=_token_hint(raw))
  db.add(t)
  await db.flush()
  await _audit(db, event_type="auth.api_token.created", entity_type="ApiToken", entity_id=t.id, actor_id=user.id, payload={"name": t.name})
  await db.commit()
  return ApiTokenCreateOut(token=raw, tokenHint=t.token_hint, apiToken=_api_token_out(t))


@router.post("/tokens/{token_id}/revoke")
async def revoke_api_token(
  token_id: str,
  payload: ApiTokenRevokeIn,
  request: Request,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
  if not session_id:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session required")
  if not verify_password(payload.password, user.password_hash):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
  if user.role == "admin":
    await require_admin_mfa(request, user, db, session_id)

  res = await db.execute(select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user.id))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
  if t.revoked_at is None:
    t.revoked_at = datetime.now(timezone.utc)
    await _audit(db, event_type="auth.api_token.revoked", entity_type="ApiToken", entity_id=t.id, actor_id=user.id, payload={})
    await db.commit()
  return {"ok": True}


@router.post("/password/reset/request")
async def password_reset_request(payload: PasswordResetRequestIn, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
  ip = request.client.host if request.client else "unknown"
  email_key = (payload.email or "").strip().lower()
  _rate_limit_or_429(key=f"auth:pwreset:req:ip:{ip}", limit=int(settings.rate_limit_password_reset_ip_per_minute), window_seconds=60)
  if email_key:
    _rate_limit_or_429(key=f"auth:pwreset:req:email:{email_key}", limit=int(settings.rate_limit_password_reset_email_per_minute), window_seconds=60)

  # Always return ok to avoid account enumeration.
  normalized_email = (payload.email or "").strip().lower()
  res = await db.execute(select(User).where(User.email == normalized_email))
  u = res.scalar_one_or_none()
  if not u:
    return {"ok": True}

  token = secrets.token_urlsafe(32)
  expires = datetime.now(timezone.utc) + timedelta(hours=1)
  prt = PasswordResetToken(
    user_id=u.id,
    token_hash=_hash_token(token),
    request_ip=request.client.host if request.client else None,
    expires_at=expires,
    created_at=datetime.now(timezone.utc),
  )
  db.add(prt)
  await _audit(db, event_type="auth.password_reset.requested", entity_type="User", entity_id=u.id, actor_id=None, payload={"ip": prt.request_ip})
  await db.commit()

  # If SMTP notification destination is configured, send reset link email.
  email_sent = False
  dres = await db.execute(
    select(NotificationDestination)
    .where(NotificationDestination.provider == "smtp", NotificationDestination.enabled.is_(True))
    .order_by(NotificationDestination.updated_at.desc())
  )
  smtp_destination = dres.scalars().first()
  if smtp_destination:
    try:
      cfg = decrypt_destination_config(smtp_destination.config_encrypted)
      to_addr = normalized_email or str(cfg.get("to") or "").strip()
      if to_addr:
        base = (payload.resetBaseUrl or "").strip().rstrip("/")
        if not base:
          base = "http://localhost:3000"
        reset_url = f"{base}/login?mode=reset&token={token}"
        provider = provider_for("smtp")
        await provider.send(
          destination={"config": {**cfg, "to": to_addr}},
          msg=NotificationMessage(
            title="Task-Daddy password reset",
            message=(
              "A password reset was requested for your account.\n\n"
              f"Reset link: {reset_url}\n\n"
              "If you did not request this, you can ignore this email."
            ),
          ),
        )
        email_sent = True
    except Exception:
      email_sent = False

  # Dev fallback: return token in response when explicitly enabled.
  if os.getenv("DEV_EMAIL_CAPTURE", "").strip().lower() in ("1", "true", "yes", "y"):
    return {"ok": True, "token": token, "emailSent": email_sent}
  return {"ok": True, "emailSent": email_sent}


@router.post("/password/reset/confirm")
async def password_reset_confirm(payload: PasswordResetConfirmIn, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
  ip = request.client.host if request.client else "unknown"
  _rate_limit_or_429(key=f"auth:pwreset:confirm:ip:{ip}", limit=int(settings.rate_limit_password_reset_ip_per_minute), window_seconds=60)

  h = _hash_token(payload.token)
  res = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == h))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
  if t.used_at is not None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token already used")
  if t.expires_at < datetime.now(timezone.utc):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expired")

  ures = await db.execute(select(User).where(User.id == t.user_id))
  u = ures.scalar_one_or_none()
  if not u:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

  from app.security import hash_password

  u.password_hash = hash_password(payload.newPassword)
  t.used_at = datetime.now(timezone.utc)
  # Security: invalidate sessions after password reset.
  await db.execute(delete(DbSession).where(DbSession.user_id == u.id))
  await _audit(db, event_type="auth.password_reset.completed", entity_type="User", entity_id=u.id, actor_id=u.id, payload={})
  await db.commit()
  return {"ok": True}
