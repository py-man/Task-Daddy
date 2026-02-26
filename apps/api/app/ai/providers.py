from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.config import settings


class AIProvider(Protocol):
  async def generate(self, *, prompt: str, context: dict[str, Any]) -> str: ...


@dataclass
class LocalDeterministicProvider:
  async def generate(self, *, prompt: str, context: dict[str, Any]) -> str:
    # Deterministic, offline-friendly behavior suitable for acceptance tests.
    kind = context.get("kind", "generic")
    title = context.get("title") or "Untitled"
    lane_type = context.get("laneType") or "active"
    due = context.get("dueDate") or "none"
    tags = ", ".join(context.get("tags") or [])
    owner = context.get("ownerId") or "unassigned"
    priority = context.get("priority") or "P2"
    task_type = context.get("type") or "Feature"
    blocked = bool(context.get("blocked"))
    blocked_reason = context.get("blockedReason") or "—"
    dep_count = int(context.get("dependencyCount") or 0)
    comments = context.get("comments") or []
    checklist = context.get("checklist") or []
    hay = f"{title}\n{context.get('description') or ''}\n{' '.join(context.get('tags') or [])}".lower()
    is_access = any(w in hay for w in ("access", "permission", "unauthorized", "forbidden", "login", "mfa", "sso", "401", "403"))
    if kind == "summarize":
      return (
        f"Summary: {title}\n"
        f"- Owner: {owner}\n"
        f"- Priority/Type: {priority} / {task_type}\n"
        f"- Lane: {lane_type}\n"
        f"- Due: {due}\n"
        f"- Tags: {tags or '—'}\n"
        f"- Dependencies: {dep_count}\n"
        f"- Checklist: {len(checklist)} item(s), Comments: {len(comments)}\n"
        f"- Key risks: missing owner, unclear acceptance criteria, hidden dependencies."
      )
    if kind == "checklist":
      from_comments = ""
      if comments:
        snippet = str(comments[0].get("body") or "").strip()
        if snippet:
          from_comments = f"- Confirm latest comment ask: {snippet[:120]}"
      return "\n".join(
        [
          "Checklist:",
          "- Confirm scope + acceptance criteria",
          "- Identify dependencies / blocked reason",
          f"- Validate owner ({owner}) and due date ({due})",
          "- Implement smallest shippable slice",
          "- Add tests / QA notes",
          "- Update docs / rollout plan",
          from_comments,
        ]
      )
    if kind == "rewrite":
      if is_access:
        return (
          "Acceptance Criteria:\n"
          f"- Access issue for '{title}' has impacted users/scope and environment documented\n"
          "- Authentication path validated (login/SSO/MFA) with before/after evidence\n"
          "- Authorization checks confirmed (role/group/policy) with least-privilege preserved\n"
          "- Audit events/logging expectations defined for auth decisions\n"
          "- Definition of done includes user confirmation and support/runbook update\n\n"
          "Implementation Notes:\n"
          f"- Priority: {priority}\n"
          f"- Dependencies to verify: {dep_count}\n"
          f"- Blocked: {'yes' if blocked else 'no'} ({blocked_reason})"
        )
      if "report" in hay or "dashboard" in hay or "metrics" in hay:
        return (
          "Acceptance Criteria:\n"
          f"- Reporting outcome for '{title}' is explicit (who uses it, what decision it enables)\n"
          "- Data source and refresh expectations are documented\n"
          "- Filters/date range and empty-state behavior are specified\n"
          "- Error/timeout behavior is defined with fallback messaging\n"
          "- Definition of done includes validation against known sample data\n\n"
          "Implementation Notes:\n"
          f"- Priority: {priority}\n"
          f"- Dependencies to verify: {dep_count}\n"
          f"- Blocked: {'yes' if blocked else 'no'} ({blocked_reason})"
        )
      return (
        "Acceptance Criteria:\n"
        f"- Task outcome for '{title}' is explicit and testable\n"
        "- Clear user-facing outcome described\n"
        "- Edge cases listed\n"
        "- Observability / logging expectations\n"
        "- Definition of done\n\n"
        "Implementation Notes:\n"
        f"- Priority: {priority}\n"
        f"- Dependencies to verify: {dep_count}\n"
        f"- Blocked: {'yes' if blocked else 'no'} ({blocked_reason})"
      )
    if kind == "next_actions":
      return (
        f"Next actions (lane={lane_type}):\n"
        "- Confirm owner and assign backup reviewer\n"
        "- Break into 1–3 subtasks with explicit outcomes\n"
        "- Verify due date realism\n"
        "- Move forward when unblocked"
      )
    if kind == "risk":
      return (
        "Risk scan:\n"
        f"- Owner missing? {'yes' if owner == 'unassigned' else 'no'}\n"
        f"- Overdue? {'check due date' if due == 'none' else due}\n"
        f"- Blocked? {'yes' if blocked else 'no'} ({blocked_reason})\n"
        f"- Scope too large? {'possible' if len(str(context.get('description') or '')) > 900 else 'low'}"
      )
    if kind == "enhance":
      top_comment = (comments[0].get("body") if comments else "") or ""
      description = str(context.get("description") or "").strip()
      desc_preview = description[:260] + ("..." if len(description) > 260 else "")
      focus = "Operational hardening"
      if is_access:
        focus = "Access incident resolution"
      elif "report" in hay or "dashboard" in hay or "metrics" in hay:
        focus = "Reporting/data quality"
      elif "mobile" in hay or "ios" in hay or "iphone" in hay or "ipad" in hay:
        focus = "Mobile UX and ergonomics"
      elif "sync" in hay or "jira" in hay or "openproject" in hay or "integration" in hay:
        focus = "Integration reliability"
      return (
        f"Enhancement Plan: {title}\n\n"
        f"Focus Area: {focus}\n\n"
        "0) Current Context\n"
        f"- Title signal: {title}\n"
        f"- Description signal: {desc_preview or '—'}\n"
        f"- Latest comment signal: {top_comment[:180] if top_comment else '—'}\n\n"
        "1) Improved Description\n"
        f"- Clarify expected outcome, owner ({owner}), and due date ({due}).\n"
        f"- Include dependency checks ({dep_count}) and completion evidence.\n"
        f"- Add explicit non-goals to avoid scope drift.\n\n"
        "2) Suggested Checklist\n"
        "- Define acceptance criteria tied to user outcome\n"
        "- Implement smallest viable slice first\n"
        "- Validate edge cases and permission paths\n"
        "- Add monitoring + rollback note\n"
        "- Attach proof in comments (before/after)\n\n"
        "3) Context Signals\n"
        f"- Priority: {priority} | Type: {task_type}\n"
        f"- Blocked: {'yes' if blocked else 'no'} ({blocked_reason})\n"
        f"- Latest comment: {top_comment[:140] if top_comment else '—'}\n\n"
        "4) Example Ticket Rewrite\n"
        f"- Problem: {title}\n"
        f"- Goal: User can complete intended flow without manual intervention.\n"
        f"- Validation: Reproduce issue, apply fix, verify success, and record evidence."
      )
    if kind == "triage_unassigned":
      return (
        "Triage suggestion:\n"
        "- Assign Ops tasks to on-call / platform\n"
        "- Assign Bugs to area owner\n"
        "- Assign Support to triage rotation"
      )
    if kind == "prioritize":
      return (
        "Priority suggestion:\n"
        "- P0: outage / data loss / security\n"
        "- P1: customer-impacting regression\n"
        "- P2: planned feature work\n"
        "- P3: cleanup / nice-to-have"
      )
    if kind == "breakdown":
      return (
        "Breakdown:\n"
        "- Add discovery notes\n"
        "- Implement core flow\n"
        "- Add edge cases\n"
        "- QA + rollout"
      )
    return json.dumps({"echo": prompt, "context": context}, indent=2)


@dataclass
class OpenAICompatibleProvider:
  api_key: str
  base_url: str

  async def generate(self, *, prompt: str, context: dict[str, Any]) -> str:
    headers = {"Authorization": f"Bearer {self.api_key}"}
    async with httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=60) as client:
      # OpenAI-compatible chat completions API.
      r = await client.post(
        "/chat/completions",
        json={
          "model": "gpt-4o-mini",
          "messages": [
            {"role": "system", "content": "You are an embedded product copilot for a task manager."},
            {"role": "user", "content": f"Context:\n{json.dumps(context)}\n\nPrompt:\n{prompt}"},
          ],
          "temperature": 0.3,
        },
      )
      r.raise_for_status()
      data = r.json()
      return data["choices"][0]["message"]["content"]


def get_ai_provider() -> AIProvider:
  if settings.ai_provider.lower() == "openai":
    if not settings.openai_api_key:
      raise RuntimeError("AI_PROVIDER=openai requires OPENAI_API_KEY")
    return OpenAICompatibleProvider(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
  return LocalDeterministicProvider()
