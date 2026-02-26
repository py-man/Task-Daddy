#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import secrets
from cryptography.fernet import Fernet

def strong(n=48):
  return secrets.token_urlsafe(n)

print("APP_SECRET=" + strong(48))
print("FERNET_KEY=" + Fernet.generate_key().decode())
print("POSTGRES_PASSWORD=" + strong(32))
print("SEED_ADMIN_PASSWORD=" + strong(20))
print("SEED_MEMBER_PASSWORD=" + strong(20))
PY
