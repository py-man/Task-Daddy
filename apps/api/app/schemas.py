from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic import field_validator


_DATE_ONLY_RE = re.compile(r"^\\d{4}-\\d{2}-\\d{2}$")
_TZ_SUFFIX_RE = re.compile(r"(Z|[+-]\\d{2}:\\d{2})$")


def _parse_dt_utc(value: object) -> object:
  if value is None:
    return None
  if isinstance(value, datetime):
    dt = value
  elif isinstance(value, str):
    s = value.strip()
    if not s:
      return None
    if _DATE_ONLY_RE.fullmatch(s):
      dt = datetime.fromisoformat(s)
    else:
      dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
  else:
    return value

  if dt.tzinfo is None:
    return dt.replace(tzinfo=timezone.utc)
  return dt.astimezone(timezone.utc)


def _parse_dt_utc_require_tz(value: object) -> object:
  if value is None:
    return None
  if isinstance(value, datetime):
    dt = value
    if dt.tzinfo is None:
      raise ValueError("datetime must include timezone")
    return dt.astimezone(timezone.utc)
  if isinstance(value, str):
    s = value.strip()
    if not s:
      return None
    if _DATE_ONLY_RE.fullmatch(s):
      raise ValueError("datetime must include time and timezone")
    if not _TZ_SUFFIX_RE.search(s):
      raise ValueError("datetime must include timezone")
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
      raise ValueError("datetime must include timezone")
    return dt.astimezone(timezone.utc)
  return value


class UserOut(BaseModel):
  id: str
  email: str
  name: str
  role: Literal["admin", "member", "viewer"]
  avatarUrl: str | None = None
  timezone: str | None = None
  jiraAccountId: str | None = None
  mfaEnabled: bool = False
  active: bool = True
  loginDisabled: bool = False


class UserUpdateIn(BaseModel):
  email: str | None = Field(default=None, min_length=3, max_length=320)
  name: str | None = Field(default=None, min_length=1, max_length=120)
  role: Literal["admin", "member", "viewer"] | None = None
  avatarUrl: str | None = None
  timezone: str | None = Field(default=None, min_length=1, max_length=64)
  jiraAccountId: str | None = Field(default=None, min_length=1, max_length=128)
  active: bool | None = None
  loginDisabled: bool | None = None
  password: str | None = Field(default=None, min_length=8, max_length=200)


class UserCreateIn(BaseModel):
  email: str = Field(min_length=3, max_length=320)
  name: str = Field(min_length=1, max_length=120)
  role: Literal["admin", "member", "viewer"] = "member"
  password: str | None = Field(default=None, min_length=8, max_length=200)
  avatarUrl: str | None = None


class UserCreateOut(BaseModel):
  user: UserOut
  tempPassword: str | None = None


class UserInviteIn(BaseModel):
  email: str = Field(min_length=3, max_length=320)
  name: str = Field(min_length=1, max_length=120)
  role: Literal["admin", "member", "viewer"] = "member"
  inviteBaseUrl: str | None = Field(default=None, max_length=500)


class UserInviteOut(BaseModel):
  user: UserOut
  inviteToken: str
  inviteUrl: str
  expiresAt: datetime
  created: bool = False


class UserDeleteIn(BaseModel):
  mode: Literal["unassign", "reassign"] = "unassign"
  reassignToUserId: str | None = None


class LoginIn(BaseModel):
  email: str
  password: str
  totpCode: str | None = None
  recoveryCode: str | None = None
  rememberDevice: bool = False


class MfaStartIn(BaseModel):
  password: str


class MfaStartOut(BaseModel):
  otpauthUri: str
  secret: str


class MfaConfirmIn(BaseModel):
  totpCode: str


class MfaConfirmOut(BaseModel):
  recoveryCodes: list[str]


class MfaDisableIn(BaseModel):
  password: str
  totpCode: str | None = None
  recoveryCode: str | None = None


class SessionOut(BaseModel):
  id: str
  userId: str
  mfaVerified: bool
  createdIp: str | None = None
  userAgent: str | None = None
  createdAt: datetime
  expiresAt: datetime


class SessionRevokeIn(BaseModel):
  sessionId: str


class MfaTrustedDeviceOut(BaseModel):
  id: str
  userId: str
  createdIp: str | None = None
  userAgent: str | None = None
  createdAt: datetime
  lastUsedAt: datetime | None = None
  expiresAt: datetime
  revokedAt: datetime | None = None


class MfaTrustedDeviceRevokeIn(BaseModel):
  deviceId: str


class ApiTokenOut(BaseModel):
  id: str
  userId: str
  name: str
  tokenHint: str
  createdAt: datetime
  lastUsedAt: datetime | None = None
  revokedAt: datetime | None = None


class ApiTokenCreateIn(BaseModel):
  name: str = Field(min_length=1, max_length=200)
  password: str = Field(min_length=1, max_length=200)


class ApiTokenCreateOut(BaseModel):
  token: str
  tokenHint: str
  apiToken: ApiTokenOut


class ApiTokenRevokeIn(BaseModel):
  password: str = Field(min_length=1, max_length=200)


class PasswordResetRequestIn(BaseModel):
  email: str
  resetBaseUrl: str | None = Field(default=None, max_length=500)


class PasswordResetConfirmIn(BaseModel):
  token: str
  newPassword: str = Field(min_length=8, max_length=200)


class BoardCreateIn(BaseModel):
  name: str = Field(min_length=1, max_length=120)


class BoardOut(BaseModel):
  id: str
  name: str
  ownerId: str
  createdAt: datetime
  updatedAt: datetime


class BoardDeleteIn(BaseModel):
  mode: Literal["delete", "transfer"]
  transferToBoardId: str | None = None


class LaneCreateIn(BaseModel):
  name: str
  stateKey: str
  type: Literal["backlog", "active", "blocked", "done"] = "active"
  wipLimit: int | None = None


class LaneUpdateIn(BaseModel):
  name: str | None = None
  type: Literal["backlog", "active", "blocked", "done"] | None = None
  stateKey: str | None = None
  wipLimit: int | None = None


class LaneOut(BaseModel):
  id: str
  boardId: str
  name: str
  stateKey: str
  type: str
  wipLimit: int | None
  position: int


class LaneReorderIn(BaseModel):
  laneIds: list[str]


class TaskCreateIn(BaseModel):
  laneId: str
  title: str
  description: str = ""
  ownerId: str | None = None
  priority: str = Field(default="P2", min_length=1, max_length=64)
  type: str = Field(default="Feature", min_length=1, max_length=64)
  tags: list[str] = []
  dueDate: datetime | None = None
  estimateMinutes: int | None = None
  blocked: bool = False
  blockedReason: str | None = None

  @field_validator("dueDate", mode="before")
  @classmethod
  def _due_date_to_utc(cls, v: object) -> object:
    return _parse_dt_utc(v)


class TaskUpdateIn(BaseModel):
  version: int
  title: str | None = None
  description: str | None = None
  ownerId: str | None = None
  priority: str | None = Field(default=None, min_length=1, max_length=64)
  type: str | None = Field(default=None, min_length=1, max_length=64)
  tags: list[str] | None = None
  dueDate: datetime | None = None
  estimateMinutes: int | None = None
  blocked: bool | None = None
  blockedReason: str | None = None

  @field_validator("dueDate", mode="before")
  @classmethod
  def _due_date_to_utc(cls, v: object) -> object:
    return _parse_dt_utc(v)


class TaskMoveIn(BaseModel):
  laneId: str
  toIndex: int = 0
  version: int


class TaskBoardMoveIn(BaseModel):
  targetBoardId: str
  targetLaneId: str | None = None
  keepOwnerIfMember: bool = True


class TaskBoardDuplicateIn(BaseModel):
  targetBoardId: str
  targetLaneId: str | None = None
  includeChecklist: bool = True
  includeComments: bool = False
  includeDependencies: bool = True
  keepOwnerIfMember: bool = True


class TaskOut(BaseModel):
  id: str
  boardId: str
  laneId: str
  stateKey: str
  title: str
  description: str
  ownerId: str | None
  priority: str
  type: str
  tags: list[str]
  dueDate: datetime | None
  estimateMinutes: int | None
  blocked: bool
  blockedReason: str | None
  jiraKey: str | None
  jiraUrl: str | None
  jiraConnectionId: str | None = None
  jiraSyncEnabled: bool = False
  jiraProjectKey: str | None = None
  jiraIssueType: str | None = None
  openprojectWorkPackageId: int | None = None
  openprojectUrl: str | None = None
  openprojectConnectionId: str | None = None
  openprojectSyncEnabled: bool = False
  orderIndex: int
  version: int
  createdAt: datetime
  updatedAt: datetime


class TaskJiraLinkIn(BaseModel):
  connectionId: str
  jiraKey: str
  enableSync: bool = True


class TaskJiraCreateIn(BaseModel):
  connectionId: str
  projectKey: str
  issueType: str = "Task"
  enableSync: bool = True
  assigneeMode: Literal["projectDefault", "taskOwner", "unassigned", "connectionDefault"] = "taskOwner"


class TaskOpenProjectLinkIn(BaseModel):
  connectionId: str
  workPackageId: int = Field(ge=1)
  enableSync: bool = True


class TaskOpenProjectCreateIn(BaseModel):
  connectionId: str
  projectIdentifier: str | None = Field(default=None, max_length=200)
  enableSync: bool = True


class TaskIcsEmailIn(BaseModel):
  to: str | None = Field(default=None, max_length=200)
  subject: str | None = Field(default=None, min_length=1, max_length=200)
  note: str | None = Field(default=None, max_length=2000)


class TaskIcsEmailOut(BaseModel):
  ok: bool = True
  to: str
  provider: str
  filename: str
  detail: dict[str, Any] | None = None


class TaskReminderCreateIn(BaseModel):
  scheduledAt: datetime
  recipient: Literal["me", "owner"] = "me"
  channels: list[Literal["inapp", "external"]] = ["inapp"]
  note: str = Field(default="", max_length=1000)

  @field_validator("scheduledAt", mode="before")
  @classmethod
  def _scheduled_to_utc(cls, v: object) -> object:
    return _parse_dt_utc_require_tz(v)

  @field_validator("channels")
  @classmethod
  def _channels_non_empty(cls, v: list[str]) -> list[str]:
    out = []
    for c in v or []:
      s = str(c).strip()
      if s and s not in out:
        out.append(s)
    return out or ["inapp"]


class TaskReminderOut(BaseModel):
  id: str
  taskId: str
  recipientUserId: str
  scheduledAt: datetime
  note: str
  channels: list[str]
  status: str
  attempts: int
  lastError: str | None = None
  sentAt: datetime | None = None
  canceledAt: datetime | None = None
  createdAt: datetime



class BulkUpdateIn(BaseModel):
  taskIds: list[str]
  patch: dict[str, Any]


class TaskBulkImportItemIn(BaseModel):
  title: str = Field(min_length=1, max_length=220)
  description: str = Field(default="", max_length=20000)
  laneId: str | None = None
  ownerId: str | None = None
  priority: str = Field(default="P2", min_length=1, max_length=64)
  type: str = Field(default="Feature", min_length=1, max_length=64)
  tags: list[str] = []
  dueDate: datetime | None = None
  estimateMinutes: int | None = None
  blocked: bool = False
  blockedReason: str | None = None
  idempotencyKey: str | None = Field(default=None, max_length=500)

  @field_validator("dueDate", mode="before")
  @classmethod
  def _due_date_to_utc(cls, v: object) -> object:
    return _parse_dt_utc(v)


class TaskBulkImportIn(BaseModel):
  defaultLaneId: str | None = None
  skipIfTitleExists: bool = True
  items: list[TaskBulkImportItemIn] = Field(min_length=1, max_length=1000)


class TaskBulkImportResultOut(BaseModel):
  status: Literal["created", "existing"]
  key: str
  task: TaskOut


class TaskBulkImportOut(BaseModel):
  createdCount: int
  existingCount: int
  results: list[TaskBulkImportResultOut] = []


class CommentCreateIn(BaseModel):
  body: str = Field(min_length=1, max_length=20000)


class CommentOut(BaseModel):
  id: str
  taskId: str
  authorId: str
  authorName: str
  body: str
  source: str
  sourceId: str | None = None
  sourceAuthor: str | None = None
  sourceUrl: str | None = None
  createdAt: datetime


class BoardTaskTypeOut(BaseModel):
  key: str
  name: str
  color: str | None = None
  enabled: bool = True
  position: int


class BoardTaskTypeCreateIn(BaseModel):
  key: str = Field(min_length=1, max_length=64)
  name: str = Field(min_length=1, max_length=120)
  color: str | None = Field(default=None, max_length=32)


class BoardTaskTypeUpdateIn(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=120)
  color: str | None = Field(default=None, max_length=32)
  enabled: bool | None = None


class BoardTaskTypeReorderIn(BaseModel):
  keys: list[str] = Field(min_length=1, max_length=200)


class BoardTaskPriorityOut(BaseModel):
  key: str
  name: str
  color: str | None = None
  enabled: bool = True
  rank: int


class BoardTaskPriorityCreateIn(BaseModel):
  key: str = Field(min_length=1, max_length=64)
  name: str = Field(min_length=1, max_length=120)
  color: str | None = Field(default=None, max_length=32)
  rank: int | None = None


class BoardTaskPriorityUpdateIn(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=120)
  color: str | None = Field(default=None, max_length=32)
  enabled: bool | None = None


class BoardTaskPriorityReorderIn(BaseModel):
  keys: list[str] = Field(min_length=1, max_length=200)


class AttachmentOut(BaseModel):
  id: str
  taskId: str
  filename: str
  mime: str
  sizeBytes: int
  url: str
  createdAt: datetime


class ChecklistCreateIn(BaseModel):
  text: str


class ChecklistUpdateIn(BaseModel):
  text: str | None = None
  done: bool | None = None


class ChecklistOut(BaseModel):
  id: str
  taskId: str
  text: str
  done: bool
  position: int


class AuditOut(BaseModel):
  id: str
  boardId: str | None
  taskId: str | None
  actorId: str | None
  eventType: str
  entityType: str
  entityId: str | None
  payload: dict[str, Any]
  createdAt: datetime


class JiraConnectIn(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=80)
  baseUrl: str
  email: str | None = None
  token: str
  defaultAssigneeAccountId: str | None = None


class JiraConnectionUpdateIn(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=80)
  defaultAssigneeAccountId: str | None = None


class JiraConnectionOut(BaseModel):
  id: str
  name: str | None = None
  baseUrl: str
  email: str | None
  defaultAssigneeAccountId: str | None = None
  needsReconnect: bool = False
  reconnectReason: str | None = None
  createdAt: datetime


class OpenProjectConnectIn(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=80)
  baseUrl: str
  apiToken: str = Field(min_length=6, max_length=400)
  projectIdentifier: str | None = Field(default=None, max_length=80)
  enabled: bool = True


class OpenProjectConnectionUpdateIn(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=80)
  apiToken: str | None = Field(default=None, min_length=6, max_length=400)
  projectIdentifier: str | None = Field(default=None, max_length=80)
  enabled: bool | None = None


class OpenProjectConnectionOut(BaseModel):
  id: str
  name: str
  baseUrl: str
  projectIdentifier: str | None = None
  enabled: bool = True
  tokenHint: str = ""
  createdAt: datetime
  updatedAt: datetime


class WebhookSecretOut(BaseModel):
  source: str
  enabled: bool
  tokenHint: str
  createdAt: datetime
  updatedAt: datetime


class WebhookSecretUpsertIn(BaseModel):
  source: str = Field(min_length=2, max_length=64)
  enabled: bool = True
  bearerToken: str | None = Field(default=None, min_length=12, max_length=400)


class WebhookSecretRevealOut(BaseModel):
  secret: WebhookSecretOut
  bearerToken: str


class WebhookEventOut(BaseModel):
  id: str
  source: str
  idempotencyKey: str | None
  receivedAt: datetime
  processed: bool
  processedAt: datetime | None
  result: dict[str, Any] | None
  error: str | None


class WebhookInboundOut(BaseModel):
  ok: bool = True
  eventId: str
  idempotentReplay: bool = False
  result: dict[str, Any] | None = None


class NotificationDestinationOut(BaseModel):
  id: str
  provider: str
  name: str
  enabled: bool
  tokenHint: str
  createdAt: datetime
  updatedAt: datetime


class NotificationDestinationUpsertIn(BaseModel):
  provider: Literal["local", "pushover", "smtp"]
  name: str = Field(default="Default", min_length=1, max_length=80)
  enabled: bool = True
  pushoverAppToken: str | None = Field(default=None, min_length=10, max_length=128)
  pushoverUserKey: str | None = Field(default=None, min_length=10, max_length=128)
  smtpHost: str | None = Field(default=None, min_length=2, max_length=200)
  smtpPort: int | None = Field(default=None, ge=1, le=65535)
  smtpUsername: str | None = Field(default=None, max_length=200)
  smtpPassword: str | None = Field(default=None, max_length=400)
  smtpFrom: str | None = Field(default=None, max_length=200)
  smtpTo: str | None = Field(default=None, max_length=200)
  smtpStarttls: bool | None = Field(default=True)


class NotificationDestinationTestIn(BaseModel):
  title: str = Field(default="Task-Daddy test", min_length=1, max_length=60)
  message: str = Field(min_length=1, max_length=500)
  priority: int = Field(default=0, ge=-2, le=2)


class NotificationSendOut(BaseModel):
  ok: bool = True
  provider: str
  status: str
  detail: dict[str, Any] | None = None


class NotificationPreferencesOut(BaseModel):
  mentions: bool = True
  comments: bool = True
  moves: bool = True
  assignments: bool = True
  overdue: bool = True
  quietHoursEnabled: bool = False
  quietHoursStart: str | None = None
  quietHoursEnd: str | None = None
  timezone: str | None = None


class NotificationPreferencesIn(BaseModel):
  mentions: bool | None = None
  comments: bool | None = None
  moves: bool | None = None
  assignments: bool | None = None
  overdue: bool | None = None
  quietHoursEnabled: bool | None = None
  quietHoursStart: str | None = Field(default=None, max_length=5)
  quietHoursEnd: str | None = Field(default=None, max_length=5)


class JiraImportIn(BaseModel):
  boardId: str
  connectionId: str
  jql: str
  statusToStateKey: dict[str, str] = {}
  priorityMap: dict[str, str] = {}
  typeMap: dict[str, str] = {}
  conflictPolicy: Literal["jiraWins", "appWins", "manual"] = "jiraWins"


class JiraSyncNowIn(BaseModel):
  profileId: str


class SyncRunOut(BaseModel):
  id: str
  boardId: str
  profileId: str
  status: str
  startedAt: datetime
  finishedAt: datetime | None
  log: list[dict[str, Any]]
  errorMessage: str | None


class AIActionIn(BaseModel):
  input: str | None = None


class AIPatchSuggestion(BaseModel):
  taskId: str
  patch: dict[str, Any]
  reason: str | None = None
  reasonCodes: list[str] = []
  preview: str | None = None


class AICreateTaskSuggestion(BaseModel):
  title: str = Field(min_length=1, max_length=220)
  description: str = Field(default="", max_length=20000)
  laneId: str
  tags: list[str] = []


class AICreateTasksSuggestion(BaseModel):
  parentTaskId: str
  tasks: list[AICreateTaskSuggestion] = []
  reason: str | None = None


class AIIntentOut(BaseModel):
  type: str
  confidence: float = Field(ge=0.0, le=1.0)
  evidence: list[str] = []


class AIPriorityRecommendationOut(BaseModel):
  value: str
  rationale: str
  confidence: float = Field(ge=0.0, le=1.0)


class AIQualityDimensionsOut(BaseModel):
  completeness: float = Field(ge=0.0, le=1.0)
  clarity: float = Field(ge=0.0, le=1.0)
  testability: float = Field(ge=0.0, le=1.0)
  operationalSafety: float = Field(ge=0.0, le=1.0)


class AIQualityScoreOut(BaseModel):
  overall: float = Field(ge=0.0, le=1.0)
  dimensions: AIQualityDimensionsOut
  reasonCodes: list[str] = []


class AIRelatedTaskOut(BaseModel):
  taskId: str
  title: str
  laneType: str | None = None
  priority: str | None = None
  similarity: float = Field(ge=0.0, le=1.0)
  jiraKey: str | None = None
  openprojectWorkPackageId: int | None = None
  updatedAt: datetime | None = None


class AIRetrievalContextOut(BaseModel):
  similarTasks: list[AIRelatedTaskOut] = []
  linkedRecords: list[str] = []
  boardSignals: list[str] = []


class AIActionOut(BaseModel):
  text: str
  suggestions: list[AIPatchSuggestion] = []
  creates: list[AICreateTasksSuggestion] = []
  retrievalContext: AIRetrievalContextOut | None = None
  intent: AIIntentOut | None = None
  missingInfo: list[str] = []
  acceptanceCriteria: list[str] = []
  implementationNotes: list[str] = []
  edgeCases: list[str] = []
  observability: list[str] = []
  definitionOfDone: list[str] = []
  priorityRecommendation: AIPriorityRecommendationOut | None = None
  qualityScore: AIQualityScoreOut | None = None


class SystemStatusSectionOut(BaseModel):
  key: str
  label: str
  state: Literal["green", "yellow", "red"]
  details: list[str] = []
  updatedAt: datetime


class SystemStatusOut(BaseModel):
  generatedAt: datetime
  version: str
  buildSha: str
  sections: list[SystemStatusSectionOut]
