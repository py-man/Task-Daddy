from __future__ import annotations

import difflib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import get_ai_provider
from app.audit import write_audit
from app.deps import get_current_user, get_db, require_board_role
from app.models import Board, BoardTaskPriority, ChecklistItem, Comment, Lane, Task, TaskDependency, User
from app.schemas import (
  AICreateTaskSuggestion,
  AICreateTasksSuggestion,
  AIIntentOut,
  AIPatchSuggestion,
  AIPriorityRecommendationOut,
  AIQualityDimensionsOut,
  AIQualityScoreOut,
  AIActionIn,
  AIActionOut,
  AIRelatedTaskOut,
  AIRetrievalContextOut,
)

router = APIRouter(prefix="/ai", tags=["ai"])

INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
  "access_issue": (
    "access",
    "permission",
    "permissions",
    "cannot login",
    "can't login",
    "unable to login",
    "forbidden",
    "unauthorized",
    "auth",
    "sso",
    "mfa",
    "role",
    "rbac",
    "403",
    "401",
  ),
  "outage": ("outage", "down", "incident", "sev1", "sev2", "major incident", "unavailable"),
  "bug": ("bug", "error", "fails", "failure", "broken", "exception", "traceback", "regression"),
  "integration": ("jira", "openproject", "webhook", "api", "sync", "integration"),
  "compliance": ("gdpr", "sox", "compliance", "audit", "policy"),
  "onboarding": ("onboarding", "new user", "first login", "provision"),
  "data_fix": ("data fix", "backfill", "migration", "repair data", "data mismatch"),
  "feature_request": ("feature", "enhancement", "improve", "add", "new capability"),
}


def _tokenize(value: str) -> set[str]:
  return {x for x in "".join(ch.lower() if ch.isalnum() else " " for ch in (value or "")).split() if len(x) >= 3}


def _similarity(a: str, b: str) -> float:
  ta = _tokenize(a)
  tb = _tokenize(b)
  if not ta or not tb:
    return 0.0
  overlap = len(ta.intersection(tb))
  return round(overlap / max(1, len(ta.union(tb))), 2)


def _diff_preview(*, before: str, after: str, path: str) -> str:
  if before == after:
    return ""
  lines = list(
    difflib.unified_diff(
      (before or "").splitlines(),
      (after or "").splitlines(),
      fromfile=f"a/{path}",
      tofile=f"b/{path}",
      lineterm="",
      n=1,
    )
  )
  return "\n".join(lines[:40])


def _intent_prompt_policy(intent: AIIntentOut) -> tuple[str, list[str]]:
  if intent.type == "access_issue":
    return (
      "identity-and-access",
      [
        "Prioritize user impact, auth path verification, and least-privilege controls.",
        "Require explicit impacted-user scope and verifiable before/after evidence.",
        "Include observability signals for 401/403 and policy decisions.",
      ],
    )
  if intent.type == "integration":
    return (
      "integration-reliability",
      [
        "Prioritize idempotency, retry boundaries, and connection health diagnostics.",
        "Call out source-of-truth rules for sync conflict handling.",
        "Require failure-mode logging and operator recovery steps.",
      ],
    )
  if intent.type in ("outage", "bug"):
    return (
      "incident-stability",
      [
        "Prioritize fast containment, clear rollback criteria, and regression proof.",
        "Require timeline notes and blast-radius boundaries.",
      ],
    )
  return (
    "delivery-quality",
    [
      "Prioritize testable outcomes and small shippable slices.",
      "Require explicit dependencies and monitoring hooks.",
    ],
  )


def _quality_reason_codes(*, t: Task, intent: AIIntentOut, missing_info: list[str], dep_count: int) -> list[str]:
  codes: list[str] = []
  if not t.owner_id:
    codes.append("MISSING_OWNER")
  if not t.due_date:
    codes.append("MISSING_DUE_DATE")
  if not (t.description or "").strip():
    codes.append("MISSING_DESCRIPTION")
  if dep_count == 0:
    codes.append("NO_TRACKED_DEPENDENCIES")
  if intent.type in ("access_issue", "outage", "integration", "compliance"):
    codes.append("HIGH_OPERATIONAL_RISK_INTENT")
  if len(missing_info) >= 3:
    codes.append("LOW_REQUIREMENTS_COMPLETENESS")
  return codes


async def _retrieve_task_context(*, db: AsyncSession, t: Task, lane_type: str) -> AIRetrievalContextOut:
  lanes_res = await db.execute(select(Lane).where(Lane.board_id == t.board_id))
  lane_by_id = {l.id: l for l in lanes_res.scalars().all()}

  recent_res = await db.execute(select(Task).where(Task.board_id == t.board_id).order_by(Task.updated_at.desc()).limit(80))
  recent = recent_res.scalars().all()

  base_text = f"{t.title}\n{t.description or ''}\n{' '.join(t.tags or [])}"
  similar: list[AIRelatedTaskOut] = []
  blocked = 0
  overdue = 0
  unassigned = 0
  now = datetime.now(timezone.utc)
  for other in recent:
    if other.blocked:
      blocked += 1
    if other.owner_id is None:
      unassigned += 1
    if other.due_date and other.due_date < now:
      overdue += 1
    if other.id == t.id:
      continue
    score = _similarity(base_text, f"{other.title}\n{other.description or ''}\n{' '.join(other.tags or [])}")
    if score < 0.12:
      continue
    similar.append(
      AIRelatedTaskOut(
        taskId=other.id,
        title=other.title,
        laneType=(lane_by_id.get(other.lane_id).type if lane_by_id.get(other.lane_id) else None),
        priority=other.priority,
        similarity=score,
        jiraKey=other.jira_key,
        openprojectWorkPackageId=other.openproject_work_package_id,
        updatedAt=other.updated_at,
      )
    )
  similar = sorted(similar, key=lambda x: x.similarity, reverse=True)[:5]

  linked_records: list[str] = []
  if t.jira_key:
    linked_records.append(f"Jira:{t.jira_key}")
  if t.openproject_work_package_id:
    linked_records.append(f"OpenProject:WP-{t.openproject_work_package_id}")
  if t.jira_sync_enabled:
    linked_records.append("JiraSync:enabled")
  if t.openproject_sync_enabled:
    linked_records.append("OpenProjectSync:enabled")
  if not linked_records:
    linked_records.append("No linked external records on this task")

  board_signals = [
    f"Board workload snapshot: {len(recent)} recent tasks scanned",
    f"Unassigned tasks: {unassigned}",
    f"Blocked tasks: {blocked}",
    f"Overdue tasks: {overdue}",
    f"Current lane type: {lane_type}",
  ]
  if similar:
    board_signals.append("Similar tasks found; reuse prior remediation pattern where applicable.")

  return AIRetrievalContextOut(similarTasks=similar, linkedRecords=linked_records, boardSignals=board_signals)


def _classify_intent(*, title: str, description: str, task_type: str | None, tags: list[str], comments: list[dict[str, Any]]) -> AIIntentOut:
  parts = [title or "", description or "", " ".join(tags or []), task_type or ""]
  parts.extend([str(c.get("body") or "") for c in comments[:4]])
  hay = "\n".join(parts).lower()

  scores: dict[str, int] = {}
  evidence: dict[str, list[str]] = {}
  for intent, words in INTENT_KEYWORDS.items():
    hits = [w for w in words if w in hay]
    if hits:
      scores[intent] = len(hits)
      evidence[intent] = hits[:4]

  if not scores:
    return AIIntentOut(type="other", confidence=0.45, evidence=["No strong intent keywords found"])

  best_intent = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[0][0]
  top = float(scores[best_intent])
  total = float(sum(scores.values()))
  confidence = min(0.95, max(0.55, top / max(1.0, total) + 0.35))
  ev = [f"keyword:{w}" for w in evidence.get(best_intent, [])]
  return AIIntentOut(type=best_intent, confidence=round(confidence, 2), evidence=ev)


def _priority_recommendation(*, t: Task, intent: AIIntentOut, now: datetime) -> AIPriorityRecommendationOut:
  due_secs = (t.due_date - now).total_seconds() if t.due_date else None
  due_soon = bool(due_secs is not None and 0 <= due_secs <= 48 * 3600)
  overdue = bool(due_secs is not None and due_secs < 0)
  high_intent = intent.type in ("outage", "access_issue", "compliance")
  if high_intent:
    return AIPriorityRecommendationOut(value="P1", rationale="High operational/security user impact intent detected.", confidence=0.82)
  if overdue or t.blocked:
    return AIPriorityRecommendationOut(value="P1", rationale="Task is blocked or overdue and needs immediate triage.", confidence=0.78)
  if due_soon:
    return AIPriorityRecommendationOut(value="P2", rationale="Due soon; schedule within current execution window.", confidence=0.72)
  return AIPriorityRecommendationOut(value="P2", rationale="Planned work with no immediate breach signal.", confidence=0.66)


def _missing_info(*, t: Task, intent: AIIntentOut, comments: list[dict[str, Any]], dep_count: int) -> list[str]:
  out: list[str] = []
  if not t.owner_id:
    out.append("Who is the primary owner accountable for completion?")
  if not t.due_date:
    out.append("What is the target due date/time and timezone?")
  if dep_count == 0:
    out.append("Are there upstream dependencies or approvals to track explicitly?")
  if not comments:
    out.append("Is there a reproduction or stakeholder context comment to anchor triage?")
  if intent.type == "access_issue":
    out.extend(
      [
        "Which exact users/groups are impacted and in which environment (prod/staging)?",
        "What is the precise failure mode (401/403/timeout/SSO callback issue)?",
      ]
    )
  return out[:5]


def _sections_for_intent(*, t: Task, intent: AIIntentOut, dep_count: int) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
  if intent.type == "access_issue":
    acceptance = [
      "Impacted user/account scope is explicitly listed (who, where, when).",
      "Authentication flow check passes (login/SSO/MFA path verified end-to-end).",
      "Authorization/role mapping is validated and least-privilege remains intact.",
      "Fix is validated by reproducing failure before and confirming success after.",
    ]
    notes = [
      f"Trace identity path for task '{t.title}' (user -> IdP/session -> policy -> app authorization).",
      "Confirm role/group membership propagation and token/session freshness.",
      "Document support escalation and fallback procedure if identity provider is degraded.",
    ]
    edges = [
      "User succeeds on one tenant/project but fails on another.",
      "Stale session tokens keep failing after role update until refresh/logout.",
      "MFA policy conflict for device trust state.",
    ]
    observability = [
      "Audit events include user identifier, auth result, policy decision, and correlation id.",
      "Track 401/403 rate by route and tenant; alert on spikes above baseline.",
      "Log role-evaluation outcome (without sensitive token contents).",
    ]
    dod = [
      "At least one impacted user confirms restored access.",
      "Security/audit logs show expected decisions with no policy bypass.",
      "Runbook updated for future access incidents.",
    ]
    return acceptance, notes, edges, observability, dod

  if intent.type in ("feature_request", "bug", "integration", "outage", "compliance", "onboarding", "data_fix"):
    acceptance = [
      f"Outcome for '{t.title}' is explicit and testable in user-facing behavior.",
      "Acceptance checks include happy path and at least one failure/edge path.",
      "Dependencies and rollout constraints are listed before implementation.",
    ]
    notes = [
      "Define smallest shippable slice and rollback criteria before coding.",
      f"Dependency review count: {dep_count}. Convert hidden dependencies to tracked items.",
      "Capture API/logging changes in implementation notes.",
    ]
    edges = [
      "Permission mismatch between environments.",
      "Partial rollout causes inconsistent behavior across clients.",
      "Stale cached data masks fixes until refresh.",
    ]
    observability = [
      "Add structured logs for primary state transitions.",
      "Track error rate and latency on affected endpoint/flow.",
      "Create one alert threshold tied to this ticket's failure mode.",
    ]
    dod = [
      "Automated test covers primary scenario and regression case.",
      "Monitoring confirms no increase in post-release error budget burn.",
      "Change note/comment documents validation evidence.",
    ]
    return acceptance, notes, edges, observability, dod

  acceptance = [
    f"Task outcome for '{t.title}' is explicit and testable.",
    "User-facing outcome and verification steps are documented.",
    "Edge cases and rollback criteria are listed.",
  ]
  notes = [
    "Clarify owner, priority, and due date before execution.",
    "Break work into small verifiable steps.",
    "Record dependencies and approval gates.",
  ]
  edges = ["Concurrent edits", "Environment mismatch", "Incomplete rollout communication"]
  observability = ["Structured logging for key actions", "Error-rate signal defined", "Audit trail present where applicable"]
  dod = ["Acceptance criteria validated", "Tests pass", "Stakeholder update posted"]
  return acceptance, notes, edges, observability, dod


def _quality_score(*, t: Task, intent: AIIntentOut, missing_info: list[str], reason_codes: list[str]) -> AIQualityScoreOut:
  completeness = 1.0 - min(1.0, len(missing_info) / 5.0)
  clarity = 0.85 if len((t.description or "").strip()) >= 30 else 0.62
  testability = 0.88 if intent.type == "access_issue" else 0.8
  operational = 0.9 if intent.type in ("access_issue", "outage", "compliance") else 0.78
  overall = round((completeness + clarity + testability + operational) / 4.0, 2)
  return AIQualityScoreOut(
    overall=overall,
    dimensions=AIQualityDimensionsOut(
      completeness=round(completeness, 2),
      clarity=round(clarity, 2),
      testability=round(testability, 2),
      operationalSafety=round(operational, 2),
    ),
    reasonCodes=reason_codes,
  )


def _render_enhance_text(
  *,
  intent: AIIntentOut,
  policy_name: str,
  policy_rules: list[str],
  retrieval: AIRetrievalContextOut,
  acceptance: list[str],
  notes: list[str],
  edges: list[str],
  observability: list[str],
  dod: list[str],
  priority: AIPriorityRecommendationOut,
  missing: list[str],
) -> str:
  lines = [
    f"Intent: {intent.type} (confidence {intent.confidence:.2f})",
    f"Policy: {policy_name}",
    "",
    "Prompt Policy Rules:",
  ]
  lines.extend([f"- {x}" for x in policy_rules])
  lines.extend(
    [
      "",
      "Retrieved Context:",
      "- Linked records: " + ", ".join(retrieval.linkedRecords),
    ]
  )
  lines.extend([f"- {x}" for x in retrieval.boardSignals])
  if retrieval.similarTasks:
    lines.extend(["- Similar tasks:"])
    lines.extend([f"  - {x.title} [{x.taskId}] sim={x.similarity:.2f}" for x in retrieval.similarTasks[:3]])
  lines.extend(
    [
      "",
    "Acceptance Criteria:",
    ]
  )
  lines.extend([f"- {x}" for x in acceptance])
  lines.extend(["", "Implementation Notes:"])
  lines.extend([f"- {x}" for x in notes])
  lines.extend(["", "Edge Cases:"])
  lines.extend([f"- {x}" for x in edges])
  lines.extend(["", "Observability / Logging:"])
  lines.extend([f"- {x}" for x in observability])
  lines.extend(["", "Definition of Done:"])
  lines.extend([f"- {x}" for x in dod])
  lines.extend(["", "Priority Recommendation:"])
  lines.append(f"- {priority.value}: {priority.rationale} (confidence {priority.confidence:.2f})")
  if missing:
    lines.extend(["", "Missing Information:"])
    lines.extend([f"- {x}" for x in missing])
  return "\n".join(lines)


@router.post("/task/{task_id}/{action}", response_model=AIActionOut)
async def task_ai(
  task_id: str,
  action: str,
  payload: AIActionIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> AIActionOut:
  tres = await db.execute(select(Task).where(Task.id == task_id))
  t = tres.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
  await require_board_role(t.board_id, "viewer", user, db)
  lres = await db.execute(select(Lane).where(Lane.id == t.lane_id))
  lane = lres.scalar_one_or_none()
  lane_type = lane.type if lane else "active"

  kind_map = {
    "summarize": "summarize",
    "rewrite": "rewrite",
    "checklist": "checklist",
    "next-actions": "next_actions",
    "risk": "risk",
    "enhance": "enhance",
  }
  kind = kind_map.get(action)
  if not kind:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown action")

  prompt = payload.input or ""
  comments_res = await db.execute(select(Comment).where(Comment.task_id == t.id).order_by(Comment.created_at.desc()).limit(8))
  checklist_res = await db.execute(select(ChecklistItem).where(ChecklistItem.task_id == t.id).order_by(ChecklistItem.position.asc()).limit(20))
  deps_res = await db.execute(select(TaskDependency).where(TaskDependency.task_id == t.id))
  comments = [{"authorId": c.author_id, "body": c.body} for c in comments_res.scalars().all()]
  checklist = [{"text": c.text, "done": bool(c.done)} for c in checklist_res.scalars().all()]
  dep_count = len(deps_res.scalars().all())
  context = {
    "kind": kind,
    "taskId": t.id,
    "title": t.title,
    "description": t.description,
    "ownerId": t.owner_id,
    "priority": t.priority,
    "type": t.type,
    "laneType": lane_type,
    "dueDate": t.due_date.isoformat() if t.due_date else None,
    "tags": list(t.tags or []),
    "blocked": t.blocked,
    "blockedReason": t.blocked_reason,
    "estimateMinutes": t.estimate_minutes,
    "comments": comments,
    "checklist": checklist,
    "dependencyCount": dep_count,
  }

  if kind == "enhance":
    retrieval = await _retrieve_task_context(db=db, t=t, lane_type=lane_type)
    intent = _classify_intent(
      title=t.title or "",
      description=t.description or "",
      task_type=t.type,
      tags=list(t.tags or []),
      comments=comments,
    )
    policy_name, policy_rules = _intent_prompt_policy(intent)
    missing_info = _missing_info(t=t, intent=intent, comments=comments, dep_count=dep_count)
    acceptance, notes, edge_cases, observability, dod = _sections_for_intent(t=t, intent=intent, dep_count=dep_count)
    if retrieval.similarTasks:
      notes.append(f"Use prior similar task patterns for validation: {', '.join(x.taskId for x in retrieval.similarTasks[:3])}.")
    prio = _priority_recommendation(t=t, intent=intent, now=datetime.now(timezone.utc))
    reason_codes = _quality_reason_codes(t=t, intent=intent, missing_info=missing_info, dep_count=dep_count)
    q = _quality_score(t=t, intent=intent, missing_info=missing_info, reason_codes=reason_codes)
    text = _render_enhance_text(
      intent=intent,
      policy_name=policy_name,
      policy_rules=policy_rules,
      retrieval=retrieval,
      acceptance=acceptance,
      notes=notes,
      edges=edge_cases,
      observability=observability,
      dod=dod,
      priority=prio,
      missing=missing_info,
    )
    suggestions: list[AIPatchSuggestion] = []
    structured_description = "\n".join(
      [
        "Outcome",
        f"- {acceptance[0]}",
        "",
        "Acceptance Criteria",
        *[f"- {x}" for x in acceptance],
        "",
        "Edge Cases",
        *[f"- {x}" for x in edge_cases],
        "",
        "Definition of Done",
        *[f"- {x}" for x in dod],
      ]
    )
    desc_preview = _diff_preview(before=t.description or "", after=structured_description, path=f"tasks/{t.id}/description.md")
    suggestions.append(
      AIPatchSuggestion(
        taskId=t.id,
        patch={"description": structured_description},
        reason="Apply structured acceptance criteria and execution notes to task description.",
        reasonCodes=["DESCRIPTION_STRUCTURED", "ACCEPTANCE_CRITERIA_ADDED"],
        preview=desc_preview or None,
      )
    )
    if t.priority != prio.value:
      suggestions.append(
        AIPatchSuggestion(
          taskId=t.id,
          patch={"priority": prio.value},
          reason=f"Priority recommendation based on intent={intent.type} and execution risk.",
          reasonCodes=["PRIORITY_ALIGNMENT"],
          preview=_diff_preview(before=t.priority or "", after=prio.value, path=f"tasks/{t.id}/priority.txt") or None,
        )
      )
    await write_audit(
      db,
      event_type="ai.task.preview",
      entity_type="Task",
      entity_id=t.id,
      board_id=t.board_id,
      task_id=t.id,
      actor_id=user.id,
      payload={
        "action": "enhance",
        "promptClass": "task_enhance_intent",
        "contextHash": f"{t.id}:{t.version}:{kind}",
        "schemaVersion": "ai.task.enhance.v2",
        "intent": intent.type,
        "qualityScore": q.overall,
        "reasonCodes": q.reasonCodes,
        "similarTasks": len(retrieval.similarTasks),
        "linkedRecords": retrieval.linkedRecords,
      },
    )
    await db.commit()
    return AIActionOut(
      text=text,
      suggestions=suggestions,
      retrievalContext=retrieval,
      intent=intent,
      missingInfo=missing_info,
      acceptanceCriteria=acceptance,
      implementationNotes=notes,
      edgeCases=edge_cases,
      observability=observability,
      definitionOfDone=dod,
      priorityRecommendation=prio,
      qualityScore=q,
    )

  provider = get_ai_provider()
  text = await provider.generate(prompt=prompt, context=context)
  await write_audit(
    db,
    event_type="ai.task.preview",
    entity_type="Task",
    entity_id=t.id,
    board_id=t.board_id,
    task_id=t.id,
    actor_id=user.id,
    payload={
      "action": action,
      "promptClass": f"task_{kind}",
      "contextHash": f"{t.id}:{t.version}:{kind}",
      "schemaVersion": "ai.task.preview.v1",
    },
  )
  await db.commit()
  return AIActionOut(text=text)


@router.post("/board/{board_id}/{action}", response_model=AIActionOut)
async def board_ai(
  board_id: str,
  action: str,
  payload: AIActionIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> AIActionOut:
  await require_board_role(board_id, "viewer", user, db)
  kind_map = {"triage-unassigned": "triage_unassigned", "prioritize": "prioritize", "breakdown": "breakdown"}
  kind = kind_map.get(action)
  if not kind:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown action")
  provider = get_ai_provider()
  text = await provider.generate(prompt=payload.input or "", context={"kind": kind, "boardId": board_id})

  # Provide actionable, deterministic suggestions so the UI can offer an explicit "Apply" action.
  # AI never mutates server state directly.
  suggestions: list[AIPatchSuggestion] = []
  creates: list[AICreateTasksSuggestion] = []
  bres = await db.execute(select(Board).where(Board.id == board_id))
  board = bres.scalar_one_or_none()
  owner_id = board.owner_id if board else None

  pres = await db.execute(
    select(BoardTaskPriority.key, BoardTaskPriority.rank)
    .where(BoardTaskPriority.board_id == board_id, BoardTaskPriority.enabled.is_(True))
    .order_by(BoardTaskPriority.rank.asc())
  )
  prio_keys = [row.key for row in pres.all() if row.key]
  if not prio_keys:
    prio_keys = ["P0", "P1", "P2", "P3"]
  p_high = prio_keys[0]
  p_medium = prio_keys[1] if len(prio_keys) > 1 else prio_keys[0]
  p_default = prio_keys[2] if len(prio_keys) > 2 else (prio_keys[1] if len(prio_keys) > 1 else prio_keys[0])

  lres = await db.execute(select(Lane).where(Lane.board_id == board_id))
  board_lanes = list(lres.scalars().all())
  lane_by_id = {l.id: l for l in board_lanes}
  backlog_lane = next((l for l in board_lanes if l.type == "backlog"), None) or next((l for l in board_lanes if l.type == "active"), None)
  backlog_lane_id = backlog_lane.id if backlog_lane else None

  tres = await db.execute(select(Task).where(Task.board_id == board_id))
  tasks = tres.scalars().all()

  now = datetime.now(timezone.utc)

  if kind == "triage_unassigned" and owner_id:
    for t in tasks:
      if t.owner_id is None:
        suggestions.append(
          AIPatchSuggestion(
            taskId=t.id,
            patch={"ownerId": owner_id},
            reason="Unassigned task → assign to board owner (explicit apply required).",
            reasonCodes=["OWNER_UNASSIGNED", "BOARD_DEFAULT_OWNER"],
            preview=_diff_preview(before="", after=str(owner_id), path=f"tasks/{t.id}/owner.txt") or None,
          )
        )

  if kind == "prioritize":
    urgent_words = ("outage", "sev", "security", "incident", "breach", "p0", "sev1", "sev2")
    for t in tasks:
      lane = lane_by_id.get(t.lane_id)
      if lane and lane.type == "done":
        continue
      hay = f"{t.title}\n{t.description or ''}".lower()
      due_soon = bool(t.due_date and (t.due_date - now).total_seconds() <= 48 * 3600 and (t.due_date - now).total_seconds() >= 0)
      overdue = bool(t.due_date and (t.due_date - now).total_seconds() < 0)
      has_urgent = any(w in hay for w in urgent_words)

      suggested = p_default
      reason = "Default planned work."
      if has_urgent:
        suggested = p_high
        reason = "Urgency keywords detected (incident/outage/security)."
      elif overdue or t.blocked:
        suggested = p_medium
        reason = "Overdue or blocked."
      elif due_soon:
        suggested = p_medium
        reason = "Due within 48h."

      if t.priority != suggested:
        suggestions.append(
          AIPatchSuggestion(
            taskId=t.id,
            patch={"priority": suggested},
            reason=reason,
            reasonCodes=["BOARD_PRIORITY_REBALANCE"],
            preview=_diff_preview(before=t.priority or "", after=suggested, path=f"tasks/{t.id}/priority.txt") or None,
          )
        )

  if kind == "breakdown" and backlog_lane_id:
    for t in tasks:
      lane = lane_by_id.get(t.lane_id)
      if lane and lane.type == "done":
        continue
      # Heuristic: "big" tasks are long descriptions or large estimates.
      desc_len = len((t.description or "").strip())
      est = t.estimate_minutes or 0
      if desc_len < 600 and est < 8 * 60:
        continue

      base = (t.title or "Task").strip()
      # Deterministic, test-friendly breakdown suggestions (AI text remains separate).
      subtasks = [
        ("Scope & acceptance criteria", f"Define scope and acceptance criteria for: {base}"),
        ("Implementation plan", f"Outline an implementation plan for: {base}"),
        ("Execution + tests", f"Implement the work and add regression tests for: {base}"),
      ]
      creates.append(
        AICreateTasksSuggestion(
          parentTaskId=t.id,
          reason="Task appears large (long description or large estimate). Create smaller work items in Backlog (explicit apply required).",
          tasks=[
            AICreateTaskSuggestion(
              title=f"{base}: {title}",
              description=desc,
              laneId=backlog_lane_id,
              tags=[f"breakdown:{t.id}", "ai-breakdown"],
            )
            for (title, desc) in subtasks
          ],
        )
      )

  await write_audit(
    db,
    event_type="ai.board.preview",
    entity_type="Board",
    entity_id=board_id,
    board_id=board_id,
    actor_id=user.id,
    payload={
      "action": action,
      "promptClass": f"board_{kind}",
      "schemaVersion": "ai.board.preview.v1",
      "suggestions": len(suggestions),
      "creates": len(creates),
    },
  )
  await db.commit()

  return AIActionOut(text=text, suggestions=suggestions, creates=creates)
