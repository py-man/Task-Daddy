from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="Jira Mock", version="0.1.0")


def _now() -> str:
  return datetime.now(timezone.utc).isoformat()


@app.get("/rest/api/3/search")
async def search(
  request: Request,
  jql: str,
  startAt: int = 0,
  maxResults: int = 50,
  fields: str | None = None,
  authorization: str | None = Header(default=None),
) -> dict:
  # Accept any Authorization header (Bearer ...) OR basic auth. For smoke tests.
  if not authorization and not request.headers.get("authorization") and not request.headers.get("authorization"):
    # don't hard-fail; Jira client may use basic auth and won't send Authorization.
    pass

  issues = [
    {
      "id": "10001",
      "key": "DEMO-1",
      "fields": {
        "summary": "Fix login redirect loop",
        "description": "Users sometimes bounce between / and /login.",
        "assignee": {"displayName": "Admin"},
        "priority": {"name": "High"},
        "issuetype": {"name": "Bug"},
        "labels": ["auth", "frontend"],
        "duedate": datetime.now(timezone.utc).date().isoformat(),
        "status": {"name": "To Do"},
        "updated": _now(),
      },
    },
    {
      "id": "10002",
      "key": "DEMO-2",
      "fields": {
        "summary": "Add WIP limit indicator to lane headers",
        "description": "Show WIP count vs limit and warn when exceeded.",
        "assignee": None,
        "priority": {"name": "Medium"},
        "issuetype": {"name": "Task"},
        "labels": ["ui", "lanes"],
        "duedate": None,
        "status": {"name": "In Progress"},
        "updated": _now(),
      },
    },
    {
      "id": "10003",
      "key": "DEMO-3",
      "fields": {
        "summary": "Sync conflicts: log & apply jiraWins",
        "description": "Ensure conflicts are detected and logged in SyncRun.",
        "assignee": None,
        "priority": {"name": "Highest"},
        "issuetype": {"name": "Story"},
        "labels": ["jira", "sync"],
        "duedate": None,
        "status": {"name": "Done"},
        "updated": _now(),
      },
    },
  ]

  sliced = issues[startAt : startAt + maxResults]
  return {"startAt": startAt, "maxResults": maxResults, "total": len(issues), "issues": sliced}


@app.get("/health")
async def health() -> dict:
  return {"ok": True}

