from __future__ import annotations

import asyncio
import json
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Protocol

import httpx

from app.security import decrypt_secret


@dataclass(frozen=True)
class NotificationMessage:
  title: str
  message: str
  priority: int = 0


class NotificationProvider(Protocol):
  async def send(self, *, destination: dict[str, Any], msg: NotificationMessage) -> dict[str, Any]: ...


class LocalNotificationProvider:
  async def send(self, *, destination: dict[str, Any], msg: NotificationMessage) -> dict[str, Any]:
    return {
      "provider": "local",
      "status": "sent",
      "detail": {"title": msg.title, "message": msg.message, "priority": msg.priority, "destination": destination.get("name")},
    }


class PushoverProvider:
  async def send(self, *, destination: dict[str, Any], msg: NotificationMessage) -> dict[str, Any]:
    cfg = destination.get("config") or {}
    token = str(cfg.get("appToken") or "").strip()
    user = str(cfg.get("userKey") or "").strip()
    if not token or not user:
      raise ValueError("Pushover destination missing token/userKey")

    payload = {"token": token, "user": user, "title": msg.title, "message": msg.message, "priority": int(msg.priority or 0)}

    async with httpx.AsyncClient(timeout=15) as client:
      r = await client.post("https://api.pushover.net/1/messages.json", data=payload)
      r.raise_for_status()
      data = r.json()
    return {"provider": "pushover", "status": "sent", "detail": data}


class SmtpProvider:
  async def send(self, *, destination: dict[str, Any], msg: NotificationMessage) -> dict[str, Any]:
    cfg = destination.get("config") or {}
    host = str(cfg.get("host") or "").strip()
    port = int(cfg.get("port") or 587)
    username = str(cfg.get("username") or "").strip()
    password = str(cfg.get("password") or "").strip()
    from_addr = str(cfg.get("from") or "").strip()
    to_addr = str(cfg.get("to") or "").strip()
    starttls = bool(cfg.get("starttls", True))
    if not host or not from_addr or not to_addr:
      raise ValueError("SMTP destination missing host/from/to")

    def _send_sync() -> None:
      m = EmailMessage()
      m["Subject"] = msg.title
      m["From"] = from_addr
      m["To"] = to_addr
      m.set_content(msg.message)
      with smtplib.SMTP(host=host, port=port, timeout=15) as s:
        s.ehlo()
        if starttls:
          s.starttls()
          s.ehlo()
        if username and password:
          s.login(username, password)
        s.send_message(m)

    await asyncio.to_thread(_send_sync)
    return {"provider": "smtp", "status": "sent", "detail": {"to": to_addr, "host": host, "port": port}}


def destination_public(*, provider: str, name: str, enabled: bool, token_hint: str, created_at: Any, updated_at: Any, id: str) -> dict[str, Any]:
  return {
    "id": id,
    "provider": provider,
    "name": name,
    "enabled": bool(enabled),
    "tokenHint": token_hint or "",
    "createdAt": created_at,
    "updatedAt": updated_at,
  }


def decrypt_destination_config(config_encrypted: str) -> dict[str, Any]:
  raw = decrypt_secret(config_encrypted)
  try:
    obj = json.loads(raw)
    return obj if isinstance(obj, dict) else {}
  except Exception:
    return {}


def provider_for(provider: str) -> NotificationProvider:
  if provider == "pushover":
    return PushoverProvider()
  if provider == "smtp":
    return SmtpProvider()
  return LocalNotificationProvider()
