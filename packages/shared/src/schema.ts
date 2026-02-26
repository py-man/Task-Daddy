import { z } from "zod";

export const RoleSchema = z.enum(["admin", "member", "viewer"]);
export type Role = z.infer<typeof RoleSchema>;

export const LaneTypeSchema = z.enum(["backlog", "active", "blocked", "done"]);
export type LaneType = z.infer<typeof LaneTypeSchema>;

export const PrioritySchema = z.string().min(1).max(64);
export type Priority = z.infer<typeof PrioritySchema>;

export const TaskTypeSchema = z.string().min(1).max(64);
export type TaskType = z.infer<typeof TaskTypeSchema>;

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string(),
  role: RoleSchema,
  avatarUrl: z.string().url().nullable(),
  timezone: z.string().nullable().optional(),
  jiraAccountId: z.string().nullable().optional(),
  mfaEnabled: z.boolean().optional(),
  active: z.boolean().optional(),
  loginDisabled: z.boolean().optional()
});
export type User = z.infer<typeof UserSchema>;

export const BoardSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  ownerId: z.string().uuid(),
  createdAt: z.string(),
  updatedAt: z.string()
});
export type Board = z.infer<typeof BoardSchema>;

export const LaneSchema = z.object({
  id: z.string().uuid(),
  boardId: z.string().uuid(),
  name: z.string(),
  stateKey: z.string(),
  type: LaneTypeSchema,
  wipLimit: z.number().int().min(0).nullable(),
  position: z.number().int().min(0)
});
export type Lane = z.infer<typeof LaneSchema>;

export const ChecklistItemSchema = z.object({
  id: z.string().uuid(),
  taskId: z.string().uuid(),
  text: z.string(),
  done: z.boolean(),
  position: z.number().int().min(0)
});
export type ChecklistItem = z.infer<typeof ChecklistItemSchema>;

export const CommentSchema = z.object({
  id: z.string().uuid(),
  taskId: z.string().uuid(),
  authorId: z.string().uuid(),
  body: z.string(),
  createdAt: z.string()
});
export type Comment = z.infer<typeof CommentSchema>;

export const TaskSchema = z.object({
  id: z.string().uuid(),
  boardId: z.string().uuid(),
  laneId: z.string().uuid(),
  stateKey: z.string(),
  title: z.string(),
  description: z.string(),
  ownerId: z.string().uuid().nullable(),
  priority: PrioritySchema,
  type: TaskTypeSchema,
  tags: z.array(z.string()),
  dueDate: z.string().nullable(),
  estimateMinutes: z.number().int().min(0).nullable(),
  blocked: z.boolean(),
  blockedReason: z.string().nullable(),
  jiraKey: z.string().nullable(),
  jiraUrl: z.string().nullable(),
  jiraConnectionId: z.string().uuid().nullable().optional(),
  jiraSyncEnabled: z.boolean().optional(),
  jiraProjectKey: z.string().nullable().optional(),
  jiraIssueType: z.string().nullable().optional(),
  openprojectWorkPackageId: z.number().int().nullable().optional(),
  openprojectUrl: z.string().nullable().optional(),
  openprojectConnectionId: z.string().uuid().nullable().optional(),
  openprojectSyncEnabled: z.boolean().optional(),
  orderIndex: z.number().int().min(0),
  version: z.number().int().min(0),
  createdAt: z.string(),
  updatedAt: z.string()
});
export type Task = z.infer<typeof TaskSchema>;

export const AuditEventSchema = z.object({
  id: z.string().uuid(),
  boardId: z.string().uuid().nullable(),
  taskId: z.string().uuid().nullable(),
  actorId: z.string().uuid().nullable(),
  eventType: z.string(),
  entityType: z.string(),
  entityId: z.string().nullable(),
  payload: z.record(z.any()),
  createdAt: z.string()
});
export type AuditEvent = z.infer<typeof AuditEventSchema>;

export const JiraConnectionSchema = z.object({
  id: z.string().uuid(),
  name: z.string().nullable().optional(),
  baseUrl: z.string(),
  email: z.string().nullable(),
  createdAt: z.string()
});
export type JiraConnection = z.infer<typeof JiraConnectionSchema>;

export const SyncRunSchema = z.object({
  id: z.string().uuid(),
  boardId: z.string().uuid(),
  status: z.enum(["success", "error"]),
  startedAt: z.string(),
  finishedAt: z.string().nullable(),
  log: z.array(z.object({ at: z.string(), level: z.enum(["info", "warn", "error"]), message: z.string() }))
});
export type SyncRun = z.infer<typeof SyncRunSchema>;

export const BoardTaskTypeSchema = z.object({
  key: z.string(),
  name: z.string(),
  color: z.string().nullable().optional(),
  enabled: z.boolean().optional(),
  position: z.number().int().min(0)
});
export type BoardTaskType = z.infer<typeof BoardTaskTypeSchema>;

export const BoardTaskPrioritySchema = z.object({
  key: z.string(),
  name: z.string(),
  color: z.string().nullable().optional(),
  enabled: z.boolean().optional(),
  rank: z.number().int().min(0)
});
export type BoardTaskPriority = z.infer<typeof BoardTaskPrioritySchema>;

export const TaskReminderSchema = z.object({
  id: z.string().uuid(),
  taskId: z.string().uuid(),
  recipientUserId: z.string().uuid(),
  scheduledAt: z.string(),
  note: z.string(),
  channels: z.array(z.string()),
  status: z.string(),
  attempts: z.number().int().min(0),
  lastError: z.string().nullable().optional(),
  sentAt: z.string().nullable().optional(),
  canceledAt: z.string().nullable().optional(),
  createdAt: z.string()
});
export type TaskReminder = z.infer<typeof TaskReminderSchema>;
