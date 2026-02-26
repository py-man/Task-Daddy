# Changelog

## v2026-02-26+r3-hardening

- Safety: enforced host-level DB backup before restart/recreate flows (`start.sh`, `reset.sh`, `scripts/prod_up.sh`).
- Safety: added integration/config export backup (`scripts/backup_config_integrations.sh`) with checksum output.
- Safety: added branch-isolated stack scripts (`scripts/branch_up.sh`, `scripts/branch_down.sh`) to prevent non-main branch changes from touching production containers.
- Compose: added deploy marker labels (`track`, `branch`) and parameterized local ports for branch-isolated runs.
- Data hygiene: normalized recovered task metadata; owner assignment + OCR cleanup + Jira key relink completed.
- Tag policy: removed `recovered`/`ocr` tags; standardized task tags to `TaskManager` (personal boards) and `TaskManager,shared` (non-personal boards).

## v2026-02-25+b61

- Integrations/OpenProject: added secure backend connection profiles (`openproject_connections`) with admin+MFA CRUD/test endpoints.
- Integrations/OpenProject: added API client (`/api/v3` ping using API key auth) and regression test coverage.
- UI: upgraded `/app/integrations/openproject` from static scaffold to working connection management.
- Help docs: added OpenProject API endpoints section.

## v2026-02-25+b60

- UX: increased board drag-card information density (estimate, tags, recency, blocked reason, short description preview).
- Integrations UI: added OpenProject integration scaffold page and surfaced it in Settings → Integrations.
- Backlog/strategy: added user-requested integration and enablement tracks (OpenProject, GitHub MCP execution flow, NotebookLM map pack, UI/UX GitHub AI catalog).
- Docs: added `docs/INTEGRATIONS_OPEN_PROJECTS_2026.md`, `docs/UI_UX_GITHUB_AI_CATALOG_2026.md`, and `docs/NOTEBOOKLM_MAP.md`.

## v2026-02-25+b59

- Notifications: added in-app taxonomy classification (`action_required`, `informational`, `system`) and surfaced it in `/notifications/inapp`.
- Notifications: implemented burst collapse via dedupe upsert (`burstCount`, `lastOccurrenceAt`) to reduce comment/move storm noise.
- Tasks: switched move/comment/mention dedupe keys to time-bucketed keys for practical burst grouping.
- UI: notification center now shows taxonomy badges and burst counts.
- Tests: expanded in-app notification coverage for taxonomy and burst collapse behavior.

## v2026-02-25+b58

- Backups: added DB-backed lifecycle policy (`retentionDays`, `minIntervalMinutes`, `maxBackups`, `maxTotalSizeMb`) and admin API endpoints (`GET/PATCH /backups/policy`).
- Backups: scheduler now enforces minimum interval for automatic snapshots and pruning now applies age + count + size caps.
- Backups UI: added retention guardrail controls in Settings → Backups.
- Reports: expanded `/app/reports` with additional operational analytics (age/due buckets, throughput trend, workload by tasks and estimate minutes, blocked-reason hotspots, risk queue table).
- Docs: updated backlog, product backlog, memory, and error lessons with resume-ready context.

## v2026-02-25+b57

- System Status: expanded Postgres diagnostics with top long-query snippets and blocked-lock pairs.
- System Status: notifications widget now includes 24h success rate and emergency receipt counts.
- System Status UI: added one-click JSON export for support snapshots.
- Nightly pipeline: added CodeQL SAST job and consolidated nightly summary generation from collected artifacts.
- Nightly artifacts: improved authenticated status snapshot and concrete DB `pg_stat` report extraction from Postgres container.

## v2026-02-25+RC6

- Platform: expanded nightly quality/security pipeline with concrete scans, Lighthouse artifacts, and security gate wiring.
- Admin: System Status expanded and enabled by default, with runtime API metrics and improved cache warm-up status handling.
- UX/Productivity: board swimlane ordering controls added (`manual`, `due`, `priority`, `updated`, `title`) with persisted sort direction.
- Docs/Research: added competitor and market research matrix plus updated product backlog linkage for next-wave features.

## v2026-02-24+b32

- Notifications: added per-user notification preferences (`mentions/comments/moves/assignments/overdue`) and quiet hours (`HH:MM`) APIs + UI.
- Notifications: in-app delivery now respects per-user preferences and quiet hours.
- Notifications: mention parsing + owner move/comment alert coverage expanded.
- Webhooks UX: added configurable public API base override + copy actions for URLs and generated tokens.
- AI: task-level context is now richer (recent comments/checklist/dependencies/owner/priority) and supports `enhance` action for more actionable ticket improvements.
- DB: added migration for user notification preferences and quiet-hour fields.
- Tests: added notification preferences regression tests.

## v2026-02-24+b31

- Notifications: added in-app mention detection from comments (`@name`, `@email`, `@localpart`) and owner alerts for new comments.
- Notifications: added owner lane-enter alert on task move across lanes.
- Mobile UX: tightened dialog sizing/padding to reduce overflow on small screens.
- AI Settings: added explicit board selector + guardrails when no board is selected.
- Tests: added regression coverage for mention + move notification flow.

## v2026-02-24+b30

- Security/Open-source hardening: removed hardcoded seed credentials from docs and seed logic; seed passwords now come from env or one-time generated bootstrap credentials file.
- Security docs: added `docs/OPEN_SOURCE_RELEASE_CHECKLIST.md` and updated env examples with strong-secret placeholders.
- Tasks: added cross-board actions (transfer or duplicate task to another board/lane) with API + UI + regression tests.
- AI UX: added one-click “Enhance ticket” in task Copilot to rewrite description + generate checklist using current task context.
- UX: added dark/light theme toggle in top bar and theme token support in global styles.
- Fix: reminder scheduling now uses isolated saving state to avoid clobbering unsaved task edit state.

## v2026-02-23+b28

- Integrations: Webhooks page now shows a usable inbound URL by default (your current web origin) and optionally a direct API URL when `NEXT_PUBLIC_PUBLIC_API_URL` is configured.

## v2026-02-23+b27

- Fields: per-board configurable task types + priorities (API + DB + Settings → Fields).
- UI: task create/edit, list filters/sorts, command palette, mobile quick-add now use per-board types/priorities.
- AI: board-level “Prioritize” now respects per-board priority keys (no hard-coded P0–P3).
- Integrations: Webhooks endpoint now uses configurable public API base (`NEXT_PUBLIC_PUBLIC_API_URL`) and supports “Generate token”.
- Security: remove seeded credential display from `/login`.

## v2026-02-23+b26

- Mobile: replace scaled-down desktop with a dedicated bottom-tab experience (Boards/My Tasks/Inbox/Search/Settings) and a floating Quick Add button.
- Board (mobile/tablet): single-lane view with lane chips and explicit Move/Done actions (no drag required).
- Backups: add delete + multi-select delete in Settings → Backups.
- List view: add sort controls (due/priority/updated/title).

## v2026-02-23+b25

- Tasks: add scheduled “Remind me” reminders (in-app + optional external notifications) in the task drawer.
- Tasks: add “Export .ics” download to import a task due date into your calendar.
- API: add task reminder endpoints + reminder dispatch loop, with regression tests.

## v2026-02-23+b24

- UX: make background styles visually distinct (grid nodes, ASCII wallpaper) and add an intensity slider in Settings → Appearance.

## v2026-02-23+b23

- UX: increase background visibility slightly (still subtle) and boost Settings → Appearance preview contrast.

## v2026-02-23+b22

- Fix: background style toggle now updates immediately in the same tab.
- UX: add high-contrast preview panel in Settings → Appearance so “Grain/ASCII” changes are visible.

## v2026-02-23+b21

- Fix: swimlane columns can scroll to the bottom again (nested flex `min-h-0`).

## v2026-02-23+b20

- Mobile: task drawer now supports moving tasks between lanes (Lane selector + save).

## v2026-02-23+b19

- Branding: add Task-Daddy SVG logo to TopBar, LeftRail, and login.
- Mobile: board view switches to lane tabs + single-lane focus layout on small screens.
- Reports: add `/app/reports` with lane + workload mini charts and a Reports dropdown in TopBar.
- Backups: add automatic daily backups + retention purge (`BACKUP_RETENTION_DAYS`, default 5).

## v2026-02-23+b18

- Fix: TopBar is always accessible (no longer renders behind board content).
- UI: unify z-index layering for Radix dropdown/popover/tooltip/dialog and task drawer.

## v2026-02-23+b17

- UX: add subtle background layer behind all content with Reduced Motion support and Settings → Appearance toggle.
- Imports: allow selecting default owner and parse sectioned bullet lists into tagged tasks.
- Fix: webhook create/move task no longer errors when lane has multiple tasks (order index query).

## v2026-02-23+b16

- Fix: creating the 3rd+ task in a lane no longer 500s (order index computation).
- Add: idempotent task bulk import API + Settings → Imports UI (paste list or upload CSV).

## v2026-02-23+b15

- Backups: implement full `.tar.gz` backups (safe snapshot + CSV exports + attachments) with list/download/restore + upload-restore in Settings → Backups.
- Notifications: add in-app notification center (bell) + task create/assign/overdue triggers; add SMTP destination (optional) alongside Pushover.
- UI: fix board selection persistence when the last board was deleted (prevents Settings → AI actions from failing due to stale `lastBoardId`).
- DB: add `in_app_notifications` table + migration.
- Tests: add backup/restore and in-app notification coverage.

## v2026-02-23+b14

- Settings: add Notifications section with Pushover destination CRUD + “Send test” (secrets stored encrypted).
- API: add `/notifications/*` endpoints + audit events and a `local` provider for deterministic tests.
- DB: add `notification_destinations` table and migration.

## v2026-02-23+b11

- Boards: add Members management UI in Settings → Boards so admins can add existing users to a board (required for task assignment).
- Task drawer: add “Add to board” from the Owner field (board admins only) to quickly make a user assignable.
- DB: enforce `board_members(board_id,user_id)` uniqueness + API add-member idempotency.

## v2026-02-23+b10

- Users: soft-deleted users are hidden by default (toggle “Show deleted” in Settings → Users); server supports `includeDeleted=true`.
- Smoke: add EXIT cleanup trap to reduce leftover smoke boards on failures.

## v2026-02-23+b09

- Fix MFA login UX: when password login returns “MFA required”, `/login` now prompts for TOTP or recovery code and completes sign-in.

## v2026-02-23+b08

- Docs: refresh `docs/CODEX_MEMORY.md` to match current shipped behavior.

## v2026-02-23+b07

- Fix MFA enrollment loop: confirming TOTP now marks the current session as MFA-verified (admin actions work immediately).
- Harden `scripts/smoke.sh`: more diagnostics, configurable creds, avoids admin-MFA coupling.

## v2026-02-23+b06

- Settings control plane: `/app/settings/*` sections (Boards, Users, Integrations, AI, Security, Backups, Diagnostics).
- MFA UX: TOTP setup with locally generated QR + sessions list/revoke/logout-all.
- Security hardening: login + password-reset rate limiting (in-memory) with tests.
- Boards: DB-enforced name uniqueness (case-insensitive, trimmed) + CSV export endpoint.
- Users: delete flow supports reassign/unassign owned tasks with tests.

## v2026-02-22+b05

- Fix task `dueDate` save (audit payload encoding + robust datetime parsing).
- Stop auto-filling credentials on `/login`.
- Make demo board seeding optional (`SEED_DEMO_BOARD=false` by default).
- Improve Jira issue creation assignment (supports default Jira accountId).
- Add webhook inbox + replay + admin token management (MVP).
- Add Admin UI for Users and Boards (MVP delete/transfer flow).
- Smoke test now cleans up its temporary board.
