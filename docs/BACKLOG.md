# NeonLanes Backlog (Owner: Admin)

This is the authoritative backlog for the next iterations. Every item must ship with tests.

Execution rule (hard):
- Execute backlog items in order.
- Complete one slice fully (code + tests + commit) before switching context.
- No status-report loops while a requested slice remains incomplete.

## Recent Ship (2026-02-26)

- `done (2026-02-27)` Integration health visibility:
  - added `/integrations/status` API for Jira, OpenProject, SMTP, Pushover, and Webhooks
  - added live state indicators in Settings → Integrations (green/red/unknown/not configured)
  - added audit-backed status messaging and regression tests

- `done` Post-login Home dashboard (`/app/home`) for web/mobile:
  - accordion buckets for recently viewed + date ranges
  - detail/list toggles
  - top-level reporting widgets (pie + bars)
- `done` Voice quick-capture expansion:
  - desktop/iPad TopBar new-task dictation
  - mobile FAB note/title dictation
- `done` Navigation/landing defaults:
  - login + root route default to Home
  - Home tab added to mobile and desktop nav
- `done` User auth governance:
  - `loginDisabled` (block authentication while keeping user active)
  - admin-set password from Users settings
  - automatic session revocation on password change / login block
- `done` Smoke hardening:
  - ephemeral admin auto-bootstrap per run
  - mandatory webhook smoke validation
  - admin MFA + API token lifecycle validation

## P0 — Reliability + Safety Gate (2026-02-27)

1) Branch/compose isolation hard-stop
   - Enforce non-overlapping compose project names and default ports by branch:
     - `main`: `neonlanes` on `3000`
     - `opensource-neon`: `taskdaddy` on `3010`
     - smoke: `*_smoke` high ports only
   - Add preflight checks that fail startup if target ports are already occupied by another project.
   - Add branch guard in startup scripts: refuse to run production start outside `main`.
2) Mandatory pre-change backup guard
   - Every restart/recreate path must produce host-level DB backup first (outside container volume).
   - Backup script must detect active project container dynamically (no hardcoded project prefix).
   - Fail deploy if backup creation fails and `ALLOW_NO_BACKUP!=1`.
3) Recoverability drill automation
   - Add weekly restore drill script:
     - backup -> fresh DB -> restore -> integrity checks (boards/tasks/comments counts)
   - Emit machine-readable report (`artifacts/recovery_drill.json`) and fail CI on regression.
4) Production protection tests
   - Add regression tests for:
     - wrong-branch deploy prevention
     - compose project mismatch detection
     - port collision detection
     - backup-required-on-restart policy

## P0 — Adversarial Security Testing Track

1) External attack surface validation
   - Add scripted checks from outside host perspective:
     - only `80/443` internet-exposed
     - no public `5432/6379/8000`
   - Store scan artifacts and compare deltas between releases.
2) Auth/session abuse tests
   - Add security tests for:
     - session fixation and stale-session reuse after restart
     - brute-force/rate-limit bypass attempts
     - MFA bypass/replay edge cases
     - API token abuse (scope + revocation timing)
3) Integration secret handling tests
   - Add decryption/key-rotation resilience tests for Jira/OpenProject/Webhooks.
   - Ensure failures return safe errors and never leak secret material.
4) Supply-chain and dependency gate
   - CI policy to fail on known critical vulnerabilities after grace window.
   - Track dependency exceptions with expiry date and owner.

## P1 — Integrations Expansion Roadmap (Next 2 sprints)

1) GitHub Issues/Projects integration
   - Two-way sync for task <-> issue state, assignee, labels, comments.
   - Task-level explicit link/create/import flow (idempotent; preview-first).
   - Optional project automation hooks (close issue on task done, etc).
2) NotebookLM / Knowledge context pack
   - Build board export pack for NotebookLM-friendly ingestion:
     - board summary, top risks, recent decisions, linked Jira/OpenProject context.
   - Add one-click “Generate research pack” from Reports.
3) Calendar/task ecosystem
   - Expand ICS delivery paths and add CalDAV-friendly export options.
   - Add Slack/Teams notification adapters for reminders + escalations.
4) OpenProject parity hardening
   - Task-level create/sync parity with Jira in drawer UX.
   - Ensure robust import/sync diagnostics and actionable error feedback.

## P1 — Integration Targets (Top 10 to Add)

1) Slack
   - `done (phase 1)` Webhook notification destination + test-send path.
   - Next: task alerts, mention notifications, and slash-command quick capture.
2) Microsoft Teams
   - `done (phase 1)` Webhook notification destination + test-send path.
   - Next: actionable task cards.
3) Google Calendar
   - Due-date/reminder sync and quick add from calendar context.
4) Outlook / Microsoft 365 Calendar
   - Enterprise calendar parity for reminders and schedule visibility.
5) GitHub Issues / Projects
   - Two-way task/issue state + assignee + comments linkage.
6) GitLab Issues
   - Two-way issue/task sync for self-hosted and cloud teams.
7) Linear
   - Issue lifecycle sync and cycle context.
8) Notion
   - Database sync for task knowledge + decision context.
9) Zapier / Make
   - No-code automation bridge for business workflows.
10) Telegram bot
   - Mobile-first quick capture, reminders, and approvals.

## P1 — Failure Scenarios to Simulate (Must test)

1) DB unavailable during startup, then recovers.
2) Redis unavailable while API remains online.
3) SMTP misconfigured but password reset/reporting continue gracefully.
4) Jira/OpenProject token invalidation mid-sync.
5) Disk nearing full during backup/export.
6) Docker daemon restart while users have active sessions.
7) SSL renewal failure path in reverse proxy.
8) Duplicate webhook delivery storms (idempotency + burst collapse).

## P0 — Open-Source Readiness (By 2026-02-26 Morning)

Status snapshot (2026-02-25 late):
- `done` parity merge from `main` into `opensource-neon`
- `done` smoke + targeted test verification
- `done (2026-02-26)` full-suite backend test logs + clean-clone verification + explicit go/no-go report

1) Branch parity + reconciliation
   - Bring `opensource-neon` to feature parity with `main` (including RC7+ deltas) using controlled merge/rebase.
   - Resolve divergences with explicit changelog notes and no behavior regressions.
2) Safety scrub + data hygiene
   - Verify no secrets/tokens/credentials in tracked files or history pointers.
   - Ensure open-source defaults only (demo users/tasks only, no private board/ticket data).
3) Release verification from clean clone
   - Validate documented bootstrap flow works exactly as written (`bootstrap.sh` / `docker-compose` / login).
   - Run smoke + API tests + web typecheck/lint and capture pass/fail artifact summary.
4) Open-source docs + operator onboarding
   - Update `README.md` and `docs/OPEN_SOURCE_RELEASE_CHECKLIST.md` with final exact steps and expected outputs.
   - Add “first 15 minutes” operator checklist (start, login, demo flow, recovery steps).
5) Go/No-Go gate
   - Produce explicit release decision with blockers list; only mark ready when all checks pass.

## P0 — RC7 Release-Candidate Gate

- `done (2026-02-26)` rc7 refreshed from main and validated:
  - web typecheck pass
  - smoke pass on `:3000`
  - full API test suite pass (`48 passed`) on `neonlanes_test`
  - report: `docs/RC7_READINESS_2026-02-26.md`

## P0 — Security + Admin Control Plane

- `done (2026-02-26)` VPS internet-facing docker hardening baseline:
  - added `docker-compose.prod.yml` with non-public db/redis/api and loopback-only web bind
  - added `docker-compose.https.yml` + `deploy/Caddyfile` for automatic Let's Encrypt certificates
  - added `scripts/generate_prod_secrets.sh` for strong secret/password generation
  - added API trusted-host + security-header middleware
  - added production env templates and deployment hardening runbook
- MFA/TOTP (QR enrollment, recovery codes, enforce for admins, audit events).
- Password reset (email token, expiring, rate-limited, audit events).
- Session management UI (list sessions, revoke, logout all devices).
- Rate limiting:
  - `/auth/login` and password reset endpoints.
- Unify `/app/settings` as the single control plane (single left-nav entry):
  - Index page lists: Boards, Users, Jira Connections, AI, Security, Webhooks, Backups, Diagnostics.
  - Make `/app/admin` redirect to Settings (or become `/app/settings/*` sections).
- User profile UX:
  - Per-user profile page (edit name/email/role/timezone/avatar/jiraAccountId).
  - User security page (enable/disable MFA + recovery codes + sessions list + logout all).
- Admin MFA enforcement UX:
  - Seeded admin can enroll MFA; admin-only actions require MFA verified session.
- “Help & docs” inside app:
  - Add end-user docs + developer docs + API examples + webhook examples.

## P0 — Backup/Restore

- `done (2026-02-26)` machine-recovery full export:
  - `POST /backups/full_export` creates a downloadable archive containing:
    - app backup tarball (snapshot + CSV exports + attachments)
    - PostgreSQL `pg_dump` (custom format)
  - Backups UI now exposes `Create full export`.
- Full backup `.tar.gz` (exports + attachments + config snapshot + build metadata).
- Restore (dry-run + merge modes + restore log + dedupe by ids/hashes).
- Backup retention policy hardening:
  - Prevent backup storms from filling filesystem.
  - Add min backup interval, max backups cap, and size-based pruning.
  - Keep manual backup always available.
  - Add admin controls for retention by days/count/size.

## P1 — AI (Board-level “does something”)

- Workload optimizer (suggest reassignment/priorities + Apply preview).
- Board health score widget + suggestions (never auto-mutate).
- Automation rule generator (produce deterministic rule JSON in StubAI).
- Add local LLM option (Ollama) behind `AI_PROVIDER=ollama` with per-action prompts; keep StubAI deterministic for tests.

## P1 — Integrations

- Apple Shortcuts endpoints:
  - Create task, add comment, move task, list tasks, mark done.
  - Bearer token auth; Settings UI to rotate tokens.
- Outbound webhooks for key events with retries + DLQ table.
- Notifications: Pushover + SMTP (config + user preferences + quiet hours).

## P1 — Integration Expansion (10 Targets)

Status: backlog sequencing for next iterations; each slice must ship with API tests + web typecheck + smoke touchpoint.

1) GitHub Issues/Projects task sync (connections + test + task link parity).
2) Slack channel actions:
   - create task from message
   - post task lifecycle updates
3) Microsoft Teams parity with Slack actions.
4) Apple Shortcuts mobile capture flows (quick task, comment, done).
5) Google Calendar connector (event-to-task and due-date push).
6) Outlook Calendar connector (enterprise parity with Google Calendar).
7) Notion task import/export bridge.
8) Linear issue sync (optional per-board profile).
9) Trello board/card import with idempotent re-sync keys.
10) Zapier/Make generic trigger-action pack for low-code automations.

## P0 — Task Data Lifecycle (Idempotent + Safe at Scale)

1) Soft-hide / archive model (no destructive delete by default)
   - Add `archivedAt`, `archivedBy`, `archiveReason` to tasks.
   - Hidden tasks excluded from normal board/list queries by default, with `showArchived=true` toggle.
   - Single-task hide/unhide + bulk hide/unhide endpoints and UI actions.
2) Idempotent behavior guarantees
   - Create/update/archive actions must be replay-safe using existing task `version` or idempotency keys.
   - Audit every lifecycle change (`task.archived`, `task.unarchived`, `task.purged`).
3) Retention + purge policy for old data
   - Configurable retention windows (for example: purge archived tasks older than N days).
   - Purge runs in dry-run mode first with counts and sample IDs.
   - Require explicit admin confirmation and backup snapshot before destructive purge.
4) Export before purge
   - One-click export of archived dataset (CSV + JSON) before final purge.
   - Track export artifact and checksum in audit log.
5) Query/index hardening for large datasets
   - Add indexes for `archivedAt`, `updatedAt`, `boardId`, `laneId`, `priority`, `ownerId`.
   - Ensure archived rows do not degrade active board query latency.
6) Board/list bulk-select hide workflow (requested)
   - Add multi-select in swimlane and list views for one-or-more tasks.
   - Bulk action: `Hide selected` (soft-hide/archive), no destructive delete.
   - Safety rule: default bulk-hide only for tasks in `backlog` or `done`; block/confirm for `in_progress` and `blocked`.
   - Add `show hidden` toggle + bulk unhide path for recovery.
   - Tests:
     - selection state consistency across lane/list filters,
     - bulk hide idempotency,
     - rule enforcement by lane/state,
     - hidden tasks excluded from default queries.

## P2 — UX Polish (Web3 motion)

- Replace “NL” with a real logo (ASCII + optional SVG).
- Confetti / delight when moving to Done (optional toggle).
- Visual signals: overdue, due soon, blocked reason tooltip, stale badge, WIP exceeded.
- Command palette (⌘K) for create task / switch board / sync.
- Light-mode theme packs with selectable color palettes (not just default light).
- Dark/light parity pass so 3D/background effects are visible and balanced in both modes.
- Board/List ordering controls parity:
  - Add explicit sort options in swimlane and list views (priority, due date, updated, title).
  - Persist per-user sort preferences by board/view.

## P2 — UI Lab (3D Landing Experiment)

- Create isolated route `/lab/neon-3d` (no regression for product UI).
- Implement scroll-driven camera narrative with neon lane landscape.
- Add adaptive quality and reduced-motion fallback.
- Validate route-level performance budgets and desktop non-regression snapshots.

## P0 — Active Bugfixes

- Light mode background visibility:
  - Ensure `grid/grain/ascii` styles remain visible in light theme (darker line/noise tokens).
- Copilot `Enhance ticket` 500:
  - Fix checklist position query to use deterministic max aggregation (no `MultipleResultsFound`).
  - Add regression test covering 3+ checklist inserts for a task.
- Self-improvement loop:
  - Maintain `docs/ERROR_LESSONS.md` and `docs/SELF_IMPROVEMENT_LOOP.md`.
  - Run `scripts/error_loop_check.sh` during bugfix iterations.

## P0 — Active Bugfixes

- Light mode background visibility:
  - Ensure `grid/grain/ascii` styles remain visible in light theme (darker line/noise tokens).
- Copilot `Enhance ticket` 500:
  - Fix checklist position query to use deterministic max aggregation (no `MultipleResultsFound`).
  - Add regression test covering 3+ checklist inserts for a task.
- Self-improvement loop:
  - Maintain `docs/ERROR_LESSONS.md` and `docs/SELF_IMPROVEMENT_LOOP.md`.
  - Run `scripts/error_loop_check.sh` during bugfix iterations.

## P2 — Competitor Gaps (top 5)

These are common “must have” features seen in Linear/Motion/ClickUp/Asana/Notion that NeonLanes does not fully support yet:

1) Cycles / Sprints (Linear)
   - Per-board or per-team cycles with cadence, planning, and reporting (scope vs completed).
   - MVP scope:
     - Create/edit/archive cycles (name, start/end, goal, capacity minutes optional).
     - Assign tasks to a cycle; cycle filter chips in Board/List.
     - Cycle report: planned vs done, carry-over, throughput (done count).
   - Tests (pytest + E2E):
     - Create cycle, assign task, report counts stable after refresh.
2) Rules / Automation builder (ClickUp)
   - Trigger → (optional conditions) → actions (set fields, notify, create follow-up, call webhook).
   - MVP scope:
     - Rules are per-board; stored in DB and versioned.
     - Triggers: task.created, task.moved, task.overdue, comment.created.
     - Conditions: laneId, priority, type, tag contains, blocked.
     - Actions: set priority/type/tags/owner, post outbound webhook, send notification.
     - Dry-run + audit log: every rule execution writes an audit event.
   - Tests:
     - Rule fires exactly once per event; rerun is idempotent.
3) Workload / Capacity planning (Asana)
   - Capacity per user over time, rebalance by drag, overload indicators and forecasts.
   - MVP scope:
     - Per-user weekly capacity (minutes) + per-task estimateMinutes rollup.
     - Workload view: assigned minutes per user (week) with overload indicator.
     - “Rebalance” suggestions (AI optional later): move tasks between owners.
   - Tests:
     - Capacity calculation matches estimates; overload threshold triggers UI badge.
4) Auto-scheduling / “Plan my day” (Motion)
   - Optional AI scheduling suggestions using due date + estimate minutes + availability windows (no calendar sync yet).
   - MVP scope:
     - “Plan My Day” panel for a user: ranked queue + suggested blocks (start/end).
     - Never auto-modifies tasks; “Apply plan” creates reminders + sets due times (optional).
     - Deterministic StubAI output for tests; optional external provider later.
   - Tests:
     - Plan generation returns stable suggestions; apply requires explicit user click.
5) Database-style “Views” + Timeline (Notion)
   - Saved views with filters/sorts + a timeline view with configurable fields/columns (mobile-friendly).
   - MVP scope:
     - Saved views: name + query JSON (filters, sort, columns).
     - Timeline view: due-date timeline (week/month) with lane/type filters.
   - Tests:
     - Saved view persists, loads fast, and produces identical API query results.

## P1 — AI Capability Expansion (competitive parity)

- Replace low-value generic actions (`Triage`, `Prioritize`, `Break down`) with contextual, actionable AI:
  - Task-aware priority reasoning with impact/confidence and one-click apply.
  - Contextual breakdown with dependency suggestions and checklist generation from task content/comments.
  - Risk detection (deadline risk, blocked-too-long, stale, overloaded assignee) with recommended actions.
  - Board weekly summary (“what changed”, “what’s at risk”, “what to do next”).
  - Scheduling assistant (“plan my day”) that proposes time blocks from due dates + estimates.
- Require “preview then apply” for all AI writes; never silently mutate.
- Add evaluation telemetry: accepted vs rejected suggestions, time saved proxy.

## P0 — AI Fit-for-Purpose Remediation (2026-02-26)

Problem statement:
- Current "enhance ticket" behavior is too generic and repeats boilerplate across unrelated intents.
- Example failure: access issue tickets receive the same generic acceptance/implementation text as non-access work.

Research baseline:
- Captured in `docs/AI_FUNCTIONS_PLAYBOOK_2026-02-26.md` using current Linear/Jira/ClickUp/Asana AI patterns.

Implementation items (in order):
1) Intent-aware enhancement pipeline
   - `done (2026-02-26)` Added `intent` classifier (access_issue, bug, outage, feature_request, integration, compliance, onboarding, data_fix, other).
   - `done (2026-02-26)` Output now includes confidence + evidence fields.
   - Tests:
     - `done (2026-02-26)` deterministic API tests added for access issue and feature request routing.
2) Intent-specific ticket templates
   - Replace one-template output with intent-specific sections for:
     - acceptance criteria
     - implementation notes
     - edge cases
     - observability/logging
     - definition of done
   - Hard gate:
     - `access_issue` must include identity scope, authn/authz checks, audit logging checks, and verification path.
3) Missing-information detector
   - Before final enhancement output, emit top missing facts/questions needed to raise confidence.
   - UI shows "ask before apply" prompts.
4) Structured output contract + quality score
   - `done (2026-02-26, slice 1)` Return stable JSON schema:
     - `intent`, `missingInfo`, `acceptanceCriteria`, `implementationNotes`, `edgeCases`, `observability`, `definitionOfDone`, `priorityRecommendation`, `suggestedActions`, `qualityScore`.
   - Block apply if `qualityScore` below threshold unless user explicitly overrides.
5) Preview/apply and audit hardening
   - `done (2026-02-26, web slice)` task drawer `Enhance ticket` no longer auto-mutates task description/checklist; outputs preview first.
   - Preserve "preview then apply" behavior.
   - `done (2026-02-26, backend preview slice)` AI preview audit fields added:
     - prompt class
     - context hash
     - output schema version
     - action/intent summary
   - Add user decision audit (accept/reject/apply) on explicit apply actions.
6) Linked system payload drafts
   - For Jira/OpenProject-linked tasks, generate explicit draft comment/field updates in preview mode only.
7) Regression + UX acceptance suite
   - Unit tests for intent routing and section population.
   - API contract tests for schema stability.
   - Web test for preview diff and section-level accept/reject.

Definition of done:
- Access issue and feature request produce materially different enhancement outputs.
- AI suggestions are evidence-backed and testable, not generic boilerplate.
- Deterministic snapshot tests pass for all canonical intent fixtures.

## P2 — Research Additions (2026-02-25, 10 items)

1) Portfolio roadmap view (Jira Advanced Roadmaps / Asana Portfolios style)
   - Cross-board initiative hierarchy with progress rollups and risk flags.
2) Goal/OKR linking (Linear initiatives + goals pattern)
   - Attach tasks/cycles to measurable goals and show confidence trend.
3) Intake forms to task templates (ClickUp/Asana forms parity)
   - Public/private forms that create tasks with mapped fields and defaults.
4) Dependency graph explorer (Notion/Jira dependency visibility)
   - Interactive graph for blockers/dependencies across boards with critical path highlight.
5) Scenario planning sandbox (capacity what-if)
   - Temporary plan mode to simulate owner/lane/date changes before applying.
6) SLA policy engine for work types
   - Define response/resolution windows by priority/type with breach alerts.
7) Release train center
   - Group tasks into releases, lock release scope, and auto-generate release notes.
8) Customer request portal + dedupe
   - Intake external feature requests, merge duplicates, tie votes to backlog priority.
9) Time tracking + cost rollups
   - Lightweight timers/manual logs, planned-vs-actual analytics per project/user.
10) Team operating metrics pack
   - DORA-lite, predictability ratio, escaped defects, and planning accuracy dashboard.

## P0 — Core Regression Test Expansion (mandatory)

Goal:
- Every core-function feature/fix must ship with tests proving no regression.

Required coverage per slice:
1) Reminders
   - creation validation (timezone-aware input required)
   - scheduler dispatch (pending -> sent/error transitions)
   - external delivery fail/retry behavior
2) Integrations (Jira/OpenProject/Webhooks/SMTP/Pushover)
   - connect/test endpoints
   - happy-path action (import/sync/create/link where applicable)
   - invalid config/error-path assertions
3) Auth/Security core
   - login/MFA/session persistence and revocation
   - password reset and admin password change flow
4) Task core lifecycle
   - create/edit/move/hide/bulk actions
   - board/lane invariants and assignment constraints

Merge gate:
- No merge to `main` without at least one new/updated automated test per changed core area.
- Smoke + targeted test suite for touched core area must pass in CI/local before commit.

## P1 — User-Requested Additions (2026-02-25)

1) Integrations into OpenProject
   - Build OpenProject connection profile, status mapping, task/work-package links, and two-way comments.
2) Expand integration strategy (open projects + dev tools)
   - Add GitHub Projects/GitHub Issues sync, Slack command hooks, and release orchestration workflows.
3) NotebookLM map pack
   - Produce curated knowledge pack (backlog, architecture, API, changelog, research docs) for fast context ingestion.
4) “Get-shit-done” MCP + GitHub flow
   - `done (2026-02-27, Codex skill enablement)` installed `yeet` as the closest Codex-native "get-shit-done" equivalent for branch/commit/push/PR automation.
   - Remaining: add project-specific runbook prompts for triage/release automation under `docs/ops/`.
5) UI/UX + GitHub AI expertise catalog
   - Research, catalog, and score reusable GitHub-hosted tooling for design QA, design-to-code, and UX regression checks.
6) Drag screen information density
   - Increase task card context (estimate, tags, recency, blocked reason, short description) without opening drawer.

## P1 — User-Requested Additions (2026-02-25, late)

1) Mobile MFA “remember this device”
   - `done (2026-02-26)` trusted-device option added on MFA login with 30-day TTL.
   - `done (2026-02-26)` trusted-device revocation list + revoke-all controls in Settings → Security.
   - `done (2026-02-26)` audit events added for trusted-device revocation actions.
2) Contextual help system refresh
   - `done (2026-02-26)` expanded `/app/help` for mobile quick capture + MFA trusted devices.
   - `done (2026-02-26)` added board-level contextual hints and refreshed `README.md` help highlights.
3) Skill-assisted delivery pipeline
   - Use newly installed API/microservices skills for architecture and implementation tasks; add a short operating guide in docs for when each skill should be triggered.
4) Mobile board UX density pass
   - `done (2026-02-25)` collapsed board controls by default on mobile, compacted top/bottom bars, increased lane/task viewport.
   - `done (2026-02-25)` added hide-on-scroll mobile chrome on board lane scroll (header/nav/FAB auto-hide, restore on upward scroll/top).
   - `done (2026-02-26)` mobile task-detail sheet flow:
     - mobile-first entry animation, simplified tab set, and top-right Save action.
     - expanded task sections by default on mobile to reduce tap depth.
5) Mobile quick-capture mode
   - `done (2026-02-25)` FAB now supports default quick-note capture + full-task mode.
   - `done (2026-02-26)` added inline non-modal one-field quick capture on mobile board screen.
6) Jira-style light palette
   - `done (2026-02-25)` added `Jira Blue` blue-on-white palette in Appearance.

## P2 — Mobile UX Research (2026-02-25)

- Created benchmark + implementation notes from current top-100 web traffic set and mobile UX standards:
  - `docs/MOBILE_WEB_UX_BENCHMARK_2026-02-25.md`

## P1 — MCP + Skills Enablement (2026-02-27)

1) “Second brain” enablement
   - `done (2026-02-27, Codex skill enablement)` installed:
     - `notion-knowledge-capture`
     - `notion-research-documentation`
     - `notion-spec-to-implementation`
   - Remaining: wire Notion MCP OAuth in operator environment and document per-project workspace mapping.
2) Delivery acceleration skills
   - `done (2026-02-27)` installed:
     - `speech` (voice workflows)
     - `gh-fix-ci` (CI remediation flow)
     - `gh-address-comments` (review follow-up flow)
     - `sentry` (error triage flow)
3) Ops guardrail
   - Require a short "skills used this slice" note in commit body or PR description for major backlog features.
