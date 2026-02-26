from __future__ import annotations

from dataclasses import dataclass

import httpx

from typing import Any


def normalize_base_url(base_url: str) -> str:
  b = (base_url or "").strip().rstrip("/")
  if not b:
    raise ValueError("baseUrl is required")
  if not (b.startswith("http://") or b.startswith("https://")):
    b = "https://" + b
  return b


class JiraApiError(RuntimeError):
  def __init__(self, *, status_code: int, message: str, details: dict[str, Any] | None = None) -> None:
    super().__init__(message)
    self.status_code = status_code
    self.message = message
    self.details = details or {}


def _extract_jira_error(payload: Any) -> tuple[str, dict[str, Any]]:
  if isinstance(payload, dict):
    em = payload.get("errorMessages")
    errs = payload.get("errors")
    parts: list[str] = []
    if isinstance(em, list) and em:
      parts.extend([str(x) for x in em if x])
    if isinstance(errs, dict) and errs:
      parts.extend([f"{k}: {v}" for k, v in errs.items()])
    msg = "; ".join(parts).strip() or "Jira request failed"
    return msg, {"errorMessages": em or [], "errors": errs or {}}
  if isinstance(payload, str) and payload.strip():
    return payload.strip()[:500], {}
  return "Jira request failed", {}


async def _request_json(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> Any:
  r = await client.request(method, path, **kwargs)
  if r.status_code >= 400:
    try:
      payload = r.json()
    except Exception:
      payload = (r.text or "")[:800]
    msg, details = _extract_jira_error(payload)
    raise JiraApiError(status_code=r.status_code, message=msg, details=details)
  if r.status_code == 204:
    return None
  return r.json()


@dataclass
class JiraAuth:
  base_url: str
  email: str | None
  token: str
  user_agent: str

  def httpx_client(self) -> httpx.AsyncClient:
    headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
    if self.email:
      auth = (self.email, self.token)
      return httpx.AsyncClient(base_url=self.base_url, headers=headers, auth=auth, timeout=60)
    headers["Authorization"] = f"Bearer {self.token}"
    return httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=60)


DEFAULT_FIELDS = [
  "summary",
  "description",
  "assignee",
  "priority",
  "issuetype",
  "labels",
  "duedate",
  "status",
  "updated",
]


async def jira_search_jql(
  *,
  auth: JiraAuth,
  jql: str,
  fields: list[str] | None = None,
  max_results: int = 50,
  next_page_token: str | None = None,
) -> dict:
  async with auth.httpx_client() as client:
    params: dict[str, str | int] = {
      "jql": jql,
      "maxResults": max_results,
      "fields": ",".join(fields or DEFAULT_FIELDS),
    }
    if next_page_token:
      params["nextPageToken"] = next_page_token
    return await _request_json(client, "GET", "/rest/api/3/search/jql", params=params)


async def jira_search_legacy(
  *,
  auth: JiraAuth,
  jql: str,
  start_at: int = 0,
  max_results: int = 50,
  fields: list[str] | None = None,
) -> dict:
  async with auth.httpx_client() as client:
    return await _request_json(
      client,
      "GET",
      "/rest/api/3/search",
      params={"jql": jql, "startAt": start_at, "maxResults": max_results, "fields": ",".join(fields or DEFAULT_FIELDS)},
    )


async def jira_search(*, auth: JiraAuth, jql: str, start_at: int = 0, max_results: int = 50) -> dict:
  """
  Compatibility helper for existing code paths.
  Jira Cloud increasingly prefers /search/jql; some tenants return 410 for /search.
  Returns a dict containing at least: issues, total (optional), nextPageToken (optional), isLast (optional).
  """
  try:
    data = await jira_search_jql(auth=auth, jql=jql, max_results=max_results)
    if "issues" not in data:
      data["issues"] = []
    return data
  except JiraApiError as e:
    if e.status_code in (404, 410):
      return await jira_search_legacy(auth=auth, jql=jql, start_at=start_at, max_results=max_results)
    raise


def adf_from_plain_text(text: str) -> dict:
  safe = (text or "").replace("\r\n", "\n").strip()
  if not safe:
    return {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": []}]}
  safe = safe[:10000]
  lines = safe.split("\n")
  content = []
  for line in lines:
    para = {"type": "paragraph", "content": []}
    if line.strip():
      para["content"].append({"type": "text", "text": line[:1000]})
    content.append(para)
  return {"type": "doc", "version": 1, "content": content}


def plain_text_from_adf(adf: object) -> str:
  parts: list[str] = []

  def add_newline() -> None:
    if not parts:
      parts.append("\n")
      return
    if not parts[-1].endswith("\n"):
      parts.append("\n")

  def walk(node: object) -> None:
    if isinstance(node, dict):
      t = node.get("type")
      if t == "text" and isinstance(node.get("text"), str):
        parts.append(node["text"])
        return
      if t in ("paragraph", "heading", "blockquote"):
        for child in node.get("content") or []:
          walk(child)
        add_newline()
        return
      if t in ("hardBreak",):
        add_newline()
        return
      if t in ("bulletList", "orderedList"):
        for li in node.get("content") or []:
          walk(li)
        add_newline()
        return
      if t == "listItem":
        parts.append("- ")
        for child in node.get("content") or []:
          walk(child)
        add_newline()
        return
      for child in node.get("content") or []:
        walk(child)
      return
    if isinstance(node, list):
      for item in node:
        walk(item)
      return

  walk(adf)
  txt = "".join(parts).replace("\r\n", "\n").strip()
  while "\n\n\n" in txt:
    txt = txt.replace("\n\n\n", "\n\n")
  return txt


async def jira_list_comments(*, auth: JiraAuth, key: str, start_at: int = 0, max_results: int = 50) -> list[dict]:
  out: list[dict] = []
  cur = start_at
  while True:
    async with auth.httpx_client() as client:
      data = await _request_json(
        client,
        "GET",
        f"/rest/api/3/issue/{key}/comment",
        params={"startAt": cur, "maxResults": max_results, "orderBy": "created"},
      )
    if not isinstance(data, dict):
      return out
    values = data.get("comments") or []
    if not values:
      return out
    out.extend([c for c in values if isinstance(c, dict)])
    cur = int(data.get("startAt") or cur) + int(data.get("maxResults") or max_results)
    total = data.get("total")
    if isinstance(total, int) and cur >= total:
      return out


async def jira_create_issue(
  *,
  auth: JiraAuth,
  project_key: str,
  summary: str,
  description: str,
  issue_type: str = "Task",
  labels: list[str] | None = None,
  priority_name: str | None = None,
  assignee_account_id: str | None = None,
) -> dict:
  async with auth.httpx_client() as client:
    fields: dict = {
      "project": {"key": project_key},
      "summary": summary,
      "description": adf_from_plain_text(description or ""),
      "issuetype": {"name": issue_type},
      "labels": labels or [],
    }
    if priority_name:
      fields["priority"] = {"name": priority_name}
    if assignee_account_id:
      fields["assignee"] = {"accountId": assignee_account_id}
    return await _request_json(client, "POST", "/rest/api/3/issue", json={"fields": fields})


async def jira_get_issue(*, auth: JiraAuth, key: str, fields: list[str] | None = None) -> dict:
  async with auth.httpx_client() as client:
    return await _request_json(client, "GET", f"/rest/api/3/issue/{key}", params={"fields": ",".join(fields or DEFAULT_FIELDS)})


async def jira_update_issue(
  *,
  auth: JiraAuth,
  key: str,
  summary: str | None = None,
  description: str | None = None,
  labels: list[str] | None = None,
) -> None:
  fields_patch: dict = {}
  if summary is not None:
    fields_patch["summary"] = summary
  if description is not None:
    fields_patch["description"] = adf_from_plain_text(description)
  if labels is not None:
    fields_patch["labels"] = labels
  if not fields_patch:
    return
  async with auth.httpx_client() as client:
    await _request_json(client, "PUT", f"/rest/api/3/issue/{key}", json={"fields": fields_patch})


async def jira_search_users(*, auth: JiraAuth, query: str, max_results: int = 10) -> list[dict]:
  async with auth.httpx_client() as client:
    out = await _request_json(client, "GET", "/rest/api/3/user/search", params={"query": query, "maxResults": max_results})
    return out if isinstance(out, list) else []


async def jira_set_assignee(*, auth: JiraAuth, key: str, account_id: str | None) -> None:
  async with auth.httpx_client() as client:
    await _request_json(client, "PUT", f"/rest/api/3/issue/{key}/assignee", json={"accountId": account_id})


async def jira_add_comment(*, auth: JiraAuth, key: str, text: str) -> dict:
  body = adf_from_plain_text(text or "")
  async with auth.httpx_client() as client:
    return await _request_json(client, "POST", f"/rest/api/3/issue/{key}/comment", json={"body": body})
