from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_COOKIE_NAME = "nl_session"
SESSION_TTL_DAYS = 14
MFA_TRUST_COOKIE_NAME = "nl_mfa_trust"


class IntegrationSecretDecryptError(RuntimeError):
  pass


def hash_password(password: str) -> str:
  return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
  return pwd_context.verify(password, password_hash)


def _fernet() -> Fernet:
  key = settings.fernet_key
  # accept raw bytes/base64 for ergonomics
  try:
    base64.urlsafe_b64decode(key.encode("utf-8"))
    return Fernet(key.encode("utf-8"))
  except Exception:
    b = base64.urlsafe_b64encode(key.encode("utf-8").ljust(32, b"\0")[:32])
    return Fernet(b)


def encrypt_secret(value: str) -> str:
  return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
  return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_integration_secret(value: str) -> str:
  try:
    return decrypt_secret(value)
  except InvalidToken as exc:
    raise IntegrationSecretDecryptError(
      "Integration token cannot be decrypted with the current key; reconnect and save this integration again."
    ) from exc


def new_session_expires_at() -> datetime:
  return datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)


def make_csrf_token() -> str:
  return secrets.token_urlsafe(32)


def totp_new_secret() -> str:
  # RFC 3548 base32 without padding
  return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").replace("=", "")


def _totp_counter(now: int | None = None, step_seconds: int = 30) -> int:
  ts = int(now if now is not None else time.time())
  return ts // step_seconds


def totp_code(secret_b32: str, *, now: int | None = None, digits: int = 6, step_seconds: int = 30) -> str:
  # RFC 6238 (HMAC-SHA1)
  s = secret_b32.strip().upper()
  pad = "=" * ((8 - (len(s) % 8)) % 8)
  key = base64.b32decode((s + pad).encode("utf-8"))
  counter = _totp_counter(now, step_seconds)
  msg = struct.pack(">Q", counter)
  digest = hmac.new(key, msg, hashlib.sha1).digest()
  offset = digest[-1] & 0x0F
  binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
  return str(binary % (10**digits)).zfill(digits)


def totp_verify(secret_b32: str, code: str, *, window: int = 1, now: int | None = None) -> bool:
  c = (code or "").strip().replace(" ", "")
  if not c.isdigit():
    return False
  ts = int(now if now is not None else time.time())
  for w in range(-window, window + 1):
    if secrets.compare_digest(totp_code(secret_b32, now=ts + w * 30), c):
      return True
  return False


def recovery_codes_generate(n: int = 10) -> list[str]:
  # user-friendly codes
  out: list[str] = []
  for _ in range(n):
    a = secrets.token_hex(4).upper()
    b = secrets.token_hex(4).upper()
    out.append(f"{a}-{b}")
  return out


def recovery_code_hash(code: str) -> str:
  return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def api_token_hash(token: str) -> str:
  # Keyed hash so DB leaks don't allow offline token matching.
  key = (settings.app_secret or "").encode("utf-8")
  msg = (token or "").strip().encode("utf-8")
  return hmac.new(key, msg, hashlib.sha256).hexdigest()


def mfa_trusted_token_new() -> str:
  return "nltd_" + secrets.token_urlsafe(32)


def mfa_trusted_token_hash(token: str) -> str:
  key = (settings.app_secret or "").encode("utf-8")
  msg = (token or "").strip().encode("utf-8")
  return hmac.new(key, msg, hashlib.sha256).hexdigest()
