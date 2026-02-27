from __future__ import annotations

import asyncio

import app.jira.service as jira_service
from app.jira.client import JiraApiError, JiraAuth


def test_bounded_jql_preserves_order_clause() -> None:
  bounded = jira_service._bounded_jql("project = DEMO ORDER BY updated DESC")
  assert bounded == "(project = DEMO) AND updated >= -30d ORDER BY updated DESC"


def test_search_retries_with_bounded_jql_on_unbounded_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
  calls: list[str] = []

  async def _fake_search(*, auth, jql, max_results, next_page_token=None):  # type: ignore[no-untyped-def]
    calls.append(jql)
    if len(calls) == 1:
      raise JiraApiError(
        status_code=400,
        message="Unbounded JQL queries are not allowed here. Please add a search restriction to your query.",
        details={},
      )
    return {"issues": [], "isLast": True}

  monkeypatch.setattr(jira_service, "jira_search_jql", _fake_search)
  auth = JiraAuth(base_url="https://example.atlassian.net", email="admin@example.com", token="x", user_agent="test")
  data, used_bounded, effective_jql = asyncio.run(
    jira_service._jira_search_with_bound_fallback(
      auth=auth,
      jql="project = DEMO ORDER BY updated DESC",
      max_results=50,
      next_page_token=None,
    )
  )
  assert data["issues"] == []
  assert used_bounded is True
  assert effective_jql == "(project = DEMO) AND updated >= -30d ORDER BY updated DESC"
  assert calls == ["project = DEMO ORDER BY updated DESC", "(project = DEMO) AND updated >= -30d ORDER BY updated DESC"]
