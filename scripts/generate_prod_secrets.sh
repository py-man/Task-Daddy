#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import base64
import os
import secrets

def strong(n=48):
  return secrets.token_urlsafe(n)

def fernet_key():
  # Fernet key = urlsafe-base64 encoded 32 random bytes
  return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

print("APP_SECRET=" + strong(48))
print("FERNET_KEY=" + fernet_key())
print("POSTGRES_PASSWORD=" + strong(32))
print("SEED_ADMIN_PASSWORD=" + strong(20))
print("SEED_MEMBER_PASSWORD=" + strong(20))
PY
