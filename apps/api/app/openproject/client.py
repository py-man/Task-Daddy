from __future__ import annotations

from typing import Any

import httpx


def normalize_base_url(base_url: str) -> str:
  b = (base_url or "").strip().rstrip("/")
  if not b:
    raise ValueError("baseUrl is required")
  if not (b.startswith("http://") or b.startswith("https://")):
    b = "https://" + b
  return b


async def openproject_ping(*, base_url: str, api_token: str) -> dict[str, Any]:
  token = (api_token or "").strip()
  if not token:
    raise ValueError("apiToken is required")
  async with httpx.AsyncClient(
    base_url=normalize_base_url(base_url),
    timeout=20,
    headers={"Accept": "application/json"},
    auth=httpx.BasicAuth("apikey", token),
  ) as client:
    res = await client.get("/api/v3")
    res.raise_for_status()
    data = res.json() if res.content else {}
    if not isinstance(data, dict):
      return {"ok": True}
    out: dict[str, Any] = {"ok": True}
    if isinstance(data.get("instanceName"), str):
      out["instanceName"] = data["instanceName"]
    if isinstance(data.get("coreVersion"), str):
      out["coreVersion"] = data["coreVersion"]
    if isinstance(data.get("_links"), dict):
      out["links"] = list(data["_links"].keys())[:12]
    return out


def openproject_work_package_url(*, base_url: str, work_package_id: int | str) -> str:
  return f"{normalize_base_url(base_url)}/work_packages/{int(work_package_id)}"


def _description_raw(desc: Any) -> str:
  if isinstance(desc, dict):
    raw = desc.get("raw")
    if isinstance(raw, str):
      return raw
  if isinstance(desc, str):
    return desc
  return ""


def _normalize_work_package(*, base_url: str, data: dict[str, Any]) -> dict[str, Any]:
  wp_id = data.get("id")
  if wp_id is None:
    raise ValueError("OpenProject response missing work package id")
  subject = str(data.get("subject") or "").strip()
  desc = _description_raw(data.get("description"))
  return {
    "id": int(wp_id),
    "subject": subject,
    "description": desc,
    "url": openproject_work_package_url(base_url=base_url, work_package_id=int(wp_id)),
    "raw": data,
  }


async def openproject_get_work_package(*, base_url: str, api_token: str, work_package_id: int | str) -> dict[str, Any]:
  async with httpx.AsyncClient(
    base_url=normalize_base_url(base_url),
    timeout=20,
    headers={"Accept": "application/json"},
    auth=httpx.BasicAuth("apikey", (api_token or "").strip()),
  ) as client:
    res = await client.get(f"/api/v3/work_packages/{int(work_package_id)}")
    res.raise_for_status()
    data = res.json() if res.content else {}
    if not isinstance(data, dict):
      raise ValueError("Unexpected OpenProject response")
    return _normalize_work_package(base_url=base_url, data=data)


async def openproject_create_work_package(
  *,
  base_url: str,
  api_token: str,
  project_identifier: str,
  subject: str,
  description: str = "",
) -> dict[str, Any]:
  pid = str(project_identifier or "").strip()
  if not pid:
    raise ValueError("projectIdentifier is required")
  payload: dict[str, Any] = {
    "subject": str(subject or "").strip() or "Task-Daddy task",
    "_links": {"project": {"href": f"/api/v3/projects/{pid}"}},
  }
  desc = str(description or "").strip()
  if desc:
    payload["description"] = {"format": "markdown", "raw": desc}

  async with httpx.AsyncClient(
    base_url=normalize_base_url(base_url),
    timeout=20,
    headers={"Accept": "application/json", "Content-Type": "application/json"},
    auth=httpx.BasicAuth("apikey", (api_token or "").strip()),
  ) as client:
    res = await client.post("/api/v3/work_packages", json=payload)
    res.raise_for_status()
    data = res.json() if res.content else {}
    if not isinstance(data, dict):
      raise ValueError("Unexpected OpenProject response")
    return _normalize_work_package(base_url=base_url, data=data)


async def openproject_update_work_package(
  *,
  base_url: str,
  api_token: str,
  work_package_id: int | str,
  subject: str,
  description: str,
) -> dict[str, Any]:
  async with httpx.AsyncClient(
    base_url=normalize_base_url(base_url),
    timeout=20,
    headers={"Accept": "application/json", "Content-Type": "application/json"},
    auth=httpx.BasicAuth("apikey", (api_token or "").strip()),
  ) as client:
    current = await client.get(f"/api/v3/work_packages/{int(work_package_id)}")
    current.raise_for_status()
    lock_version = (current.json() if current.content else {}).get("lockVersion")
    payload = {
      "lockVersion": int(lock_version or 0),
      "subject": str(subject or "").strip() or "Task-Daddy task",
      "description": {"format": "markdown", "raw": str(description or "").strip()},
    }
    res = await client.patch(f"/api/v3/work_packages/{int(work_package_id)}", json=payload)
    res.raise_for_status()
    data = res.json() if res.content else {}
    if not isinstance(data, dict):
      raise ValueError("Unexpected OpenProject response")
    return _normalize_work_package(base_url=base_url, data=data)
