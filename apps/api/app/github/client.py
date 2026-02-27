from __future__ import annotations

from typing import Any

import httpx


def normalize_base_url(base_url: str) -> str:
  b = (base_url or "").strip().rstrip("/")
  if not b:
    b = "https://api.github.com"
  if not (b.startswith("http://") or b.startswith("https://")):
    b = "https://" + b
  return b


async def github_ping(*, base_url: str, api_token: str) -> dict[str, Any]:
  token = (api_token or "").strip()
  if not token:
    raise ValueError("apiToken is required")
  async with httpx.AsyncClient(
    base_url=normalize_base_url(base_url),
    timeout=20,
    headers={
      "Accept": "application/vnd.github+json",
      "Authorization": f"Bearer {token}",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "Task-Daddy/1.0",
    },
  ) as client:
    res = await client.get("/user")
    res.raise_for_status()
    data = res.json() if res.content else {}
    if not isinstance(data, dict):
      return {"ok": True}
    out: dict[str, Any] = {"ok": True}
    if isinstance(data.get("login"), str):
      out["login"] = data["login"]
    if isinstance(data.get("id"), int):
      out["id"] = data["id"]
    if isinstance(data.get("html_url"), str):
      out["url"] = data["html_url"]
    return out
