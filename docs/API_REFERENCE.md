# Task-Daddy API Reference (MVP)

Base URL (default):

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Auth:

- Browser/UI: session cookie `nl_session`
- CLI/tools: Personal Access Token (PAT) `Authorization: Bearer nlpat_...`

Examples below use:

```bash
TD_API=http://localhost:8000
```

## Auth

### POST `/auth/login`

```bash
curl -sS -X POST "$TD_API/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"member@taskdaddy.local","password":"<MEMBER_PASSWORD>"}' \
  -c /tmp/nl.cookies
```

MFA (TOTP):

```bash
curl -sS -X POST "$TD_API/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"admin@taskdaddy.local","password":"<ADMIN_PASSWORD>","totpCode":"123456"}' \
  -c /tmp/nl.cookies
```

### POST `/auth/logout`

```bash
curl -sS -X POST "$TD_API/auth/logout" -b /tmp/nl.cookies
```

### GET `/auth/me`

Cookie:

```bash
curl -sS "$TD_API/auth/me" -b /tmp/nl.cookies
```

PAT:

```bash
curl -sS "$TD_API/auth/me" -H "Authorization: Bearer $NL_TOKEN"
```

### MFA (TOTP)

- `POST /auth/mfa/start` `{password}`
- `POST /auth/mfa/confirm` `{totpCode}`
- `POST /auth/mfa/disable` `{password, totpCode? | recoveryCode?}`

### Sessions

- `GET /auth/sessions`
- `POST /auth/sessions/revoke` `{sessionId}`
- `POST /auth/sessions/revoke_all`
- `POST /auth/sessions/revoke_all_global` (admin + MFA session required)

### Password reset

- `POST /auth/password/reset/request` `{email}`
- `POST /auth/password/reset/confirm` `{token,newPassword}`

### API tokens (PAT)

Note: token management requires a cookie session (defense in depth). The token itself can be used without cookies.

- `GET /auth/tokens`
- `POST /auth/tokens` `{name,password}` → returns the token **once**
- `POST /auth/tokens/{tokenId}/revoke` `{password}`

## Boards

- `GET /boards`
- `POST /boards` `{name}`
- `PATCH /boards/{boardId}` `{name}`
- `POST /boards/{boardId}/delete` `{mode:"delete"|"transfer",transferToBoardId?}`
- `GET /boards/{boardId}/members`
- `POST /boards/{boardId}/members` `{email,role}`

## Lanes

- `GET /boards/{boardId}/lanes`
- `POST /boards/{boardId}/lanes` `{name,stateKey,type,wipLimit?}`
- `PATCH /lanes/{laneId}` `{name?,stateKey?,type?,wipLimit?}`
- `DELETE /lanes/{laneId}`
- `POST /boards/{boardId}/lanes/reorder` `{laneIds:[...]}`

## Tasks

- `GET /boards/{boardId}/tasks` query:
  - `q`, `ownerId`, `priority`, `type`, `tag`, `blocked`, `dueFrom`, `dueTo`, `unassigned`
- `POST /boards/{boardId}/tasks` create
- `GET /tasks/{taskId}`
- `PATCH /tasks/{taskId}` update (optimistic `version`)
- `DELETE /tasks/{taskId}`
- `POST /tasks/{taskId}/move` `{laneId,toIndex,version}`
- `POST /boards/{boardId}/tasks/bulk_import` (idempotent by `importKey`)
- `POST /boards/{boardId}/tasks/bulk` bulk patch

### Comments

- `GET /tasks/{taskId}/comments`
- `POST /tasks/{taskId}/comments` `{body}`
- `PATCH /comments/{commentId}` `{body}`
- `DELETE /comments/{commentId}`

### Checklist

- `GET /tasks/{taskId}/checklist`
- `POST /tasks/{taskId}/checklist` `{text}`
- `PATCH /checklist/{itemId}` `{text?,done?,position?}`
- `DELETE /checklist/{itemId}`

### Dependencies

- `GET /tasks/{taskId}/dependencies`
- `POST /tasks/{taskId}/dependencies` `{dependsOnTaskId}`
- `DELETE /dependencies/{depId}`

### Attachments

- `GET /tasks/{taskId}/attachments`
- `POST /tasks/{taskId}/attachments` multipart file upload
- `GET /attachments/{attachmentId}` download

## Task fields (per-board Types/Priorities)

- `GET /boards/{boardId}/task_types`
- `POST /boards/{boardId}/task_types` `{key,name,color?}`
- `PATCH /boards/{boardId}/task_types/{key}`
- `POST /boards/{boardId}/task_types/reorder` `{keys:[...]}`
- `DELETE /boards/{boardId}/task_types/{key}`

- `GET /boards/{boardId}/priorities`
- `POST /boards/{boardId}/priorities` `{key,name,color?,rank?}`
- `PATCH /boards/{boardId}/priorities/{key}`
- `POST /boards/{boardId}/priorities/reorder` `{keys:[...]}`
- `DELETE /boards/{boardId}/priorities/{key}`

## AI

- Task actions: `POST /ai/task/{taskId}/{action}`
  - `summarize`, `rewrite`, `checklist`, `next_actions`, `risk_flags`
- Board actions: `POST /ai/board/{boardId}/{action}`
  - `triage_unassigned`, `prioritize`, `breakdown_big_tasks`

## Jira

- Connections:
  - `GET /jira/connections`
  - `POST /jira/connect`
  - `POST /jira/connect-env`
  - `PATCH /jira/connections/{id}`
  - `DELETE /jira/connections/{id}`
- Import/sync:
  - `POST /jira/import`
  - `POST /jira/sync-now`
  - `GET /jira/sync-runs?boardId=...`
  - `DELETE /jira/sync-runs?boardId=...`
- Task-level:
  - `POST /tasks/{taskId}/jira/create`
  - `POST /tasks/{taskId}/jira/link`
  - `POST /tasks/{taskId}/jira/pull`
  - `POST /tasks/{taskId}/jira/sync`
  - `GET /tasks/{taskId}/jira/issue`

## Webhooks (Apple Shortcuts style)

Admin config:

- `GET /webhooks/secrets`
- `POST /webhooks/secrets` `{source,enabled,bearerToken?}`
- `POST /webhooks/secrets/{source}/rotate`
- `DELETE /webhooks/secrets/{source}`
- `GET /webhooks/events?source=...&limit=...`
- `POST /webhooks/events/{eventId}/replay`

Inbound endpoint:

- `POST /webhooks/inbound/{source}` with header `Authorization: Bearer <configured token>`

Actions:

- `create_task` `{action,title,boardName,laneName?,ownerEmail?,priority?,type?,tags?,dueDate?,blocked?,blockedReason?,description?,idempotencyKey?}`
- `comment_task` `{action,taskId? | jiraKey?,body,author?,commentId?}`
- `move_task` `{action,taskId,laneName}`

## Notifications

Admin destinations:

- `GET /notifications/destinations`
- `POST /notifications/destinations`
- `PATCH /notifications/destinations/{id}`
- `DELETE /notifications/destinations/{id}`
- `POST /notifications/destinations/{id}/test`

In-app notifications (user):

- `GET /notifications/inapp?unreadOnly=true&limit=...`
- `POST /notifications/inapp/mark-read` `{ids:[...]}`
- `POST /notifications/inapp/mark-all-read`

## Backups

- `GET /backups`
- `POST /backups/full`
- `DELETE /backups/{filename}`
- `POST /backups/restore` `{filename,mode,dryRun?}`
- `POST /backups/upload?mode=...&dryRun=...` multipart

## Audit

- `GET /audit?boardId=...&taskId=...`

## Pushover quick notify (out-of-band)

If you want a one-off Pushover message from your shell (without storing credentials in the app), use:

```bash
PUSHOVER_APP_TOKEN="..." PUSHOVER_USER_KEY="..." \
TITLE="Task-Daddy" MESSAGE="Open-source build ready: http://localhost:3005" \
./scripts/pushover_notify.sh
```
