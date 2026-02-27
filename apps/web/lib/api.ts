import type { AuditEvent, Board, BoardTaskPriority, BoardTaskType, Lane, SyncRun, Task, TaskReminder, User } from "@neonlanes/shared/schema";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    credentials: "include"
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: "POST", body: form, credentials: "include" });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  async login(email: string, password: string) {
    return request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
  },
  async loginMfa(email: string, password: string, payload: { totpCode?: string; recoveryCode?: string; rememberDevice?: boolean }) {
    return request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password, ...payload }) });
  },
  async logout() {
    return request<{ ok: boolean }>("/auth/logout", { method: "POST" });
  },
  async me() {
    return request<User>("/auth/me");
  },
  async mfaStart(password: string) {
    return request<{ secret: string; otpauthUri: string }>("/auth/mfa/start", { method: "POST", body: JSON.stringify({ password }) });
  },
  async mfaConfirm(totpCode: string) {
    return request<{ recoveryCodes: string[] }>("/auth/mfa/confirm", { method: "POST", body: JSON.stringify({ totpCode }) });
  },
  async mfaDisable(payload: { password: string; totpCode?: string | null; recoveryCode?: string | null }) {
    return request<{ ok: boolean }>("/auth/mfa/disable", { method: "POST", body: JSON.stringify(payload) });
  },
  async sessions() {
    return request<any[]>("/auth/sessions");
  },
  async mfaTrustedDevices() {
    return request<any[]>("/auth/mfa/trusted_devices");
  },
  async revokeMfaTrustedDevice(deviceId: string) {
    return request<{ ok: boolean }>("/auth/mfa/trusted_devices/revoke", { method: "POST", body: JSON.stringify({ deviceId }) });
  },
  async revokeAllMfaTrustedDevices() {
    return request<{ ok: boolean }>("/auth/mfa/trusted_devices/revoke_all", { method: "POST" });
  },
  async revokeSession(sessionId: string) {
    return request<{ ok: boolean }>("/auth/sessions/revoke", { method: "POST", body: JSON.stringify({ sessionId }) });
  },
  async revokeAllSessions() {
    return request<{ ok: boolean }>("/auth/sessions/revoke_all", { method: "POST" });
  },
  async revokeAllSessionsGlobal() {
    return request<{ ok: boolean }>("/auth/sessions/revoke_all_global", { method: "POST" });
  },
  async apiTokens() {
    return request<any[]>("/auth/tokens");
  },
  async createApiToken(name: string, password: string) {
    return request<any>("/auth/tokens", { method: "POST", body: JSON.stringify({ name, password }) });
  },
  async revokeApiToken(tokenId: string, password: string) {
    return request<{ ok: boolean }>(`/auth/tokens/${tokenId}/revoke`, { method: "POST", body: JSON.stringify({ password }) });
  },
  async passwordResetRequest(email: string, resetBaseUrl?: string) {
    return request<{ ok: boolean; token?: string; emailSent?: boolean }>("/auth/password/reset/request", {
      method: "POST",
      body: JSON.stringify({ email, resetBaseUrl: resetBaseUrl || null })
    });
  },
  async passwordResetConfirm(token: string, newPassword: string) {
    return request<{ ok: boolean }>("/auth/password/reset/confirm", { method: "POST", body: JSON.stringify({ token, newPassword }) });
  },

  async boards() {
    return request<Board[]>("/boards");
  },
  async createBoard(name: string) {
    return request<Board>("/boards", { method: "POST", body: JSON.stringify({ name }) });
  },
  async updateBoard(boardId: string, name: string) {
    return request<Board>(`/boards/${boardId}`, { method: "PATCH", body: JSON.stringify({ name }) });
  },
  async deleteBoard(boardId: string, mode: "delete" | "transfer", transferToBoardId?: string | null) {
    return request<any>(`/boards/${boardId}/delete`, {
      method: "POST",
      body: JSON.stringify({ mode, transferToBoardId: transferToBoardId || null })
    });
  },
  async boardMembers(boardId: string) {
    return request<any[]>(`/boards/${boardId}/members`);
  },
  async addBoardMember(boardId: string, payload: { email: string; role: string }) {
    return request<any>(`/boards/${boardId}/members`, { method: "POST", body: JSON.stringify(payload) });
  },

  async lanes(boardId: string) {
    return request<Lane[]>(`/boards/${boardId}/lanes`);
  },
  async createLane(boardId: string, payload: { name: string; stateKey: string; type: string; wipLimit?: number | null }) {
    return request<Lane>(`/boards/${boardId}/lanes`, { method: "POST", body: JSON.stringify(payload) });
  },
  async updateLane(laneId: string, payload: any) {
    return request<Lane>(`/lanes/${laneId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async deleteLane(laneId: string) {
    return request<{ ok: boolean }>(`/lanes/${laneId}`, { method: "DELETE" });
  },
  async reorderLanes(boardId: string, laneIds: string[]) {
    return request<{ ok: boolean }>(`/boards/${boardId}/lanes/reorder`, {
      method: "POST",
      body: JSON.stringify({ laneIds })
    });
  },

  async tasks(boardId: string, params?: Record<string, string>) {
    const qs = params ? `?${new URLSearchParams(params)}` : "";
    return request<Task[]>(`/boards/${boardId}/tasks${qs}`);
  },
  async createTask(boardId: string, payload: any) {
    return request<Task>(`/boards/${boardId}/tasks`, { method: "POST", body: JSON.stringify(payload) });
  },
  async bulkImportTasks(boardId: string, payload: { defaultLaneId?: string | null; skipIfTitleExists?: boolean; items: any[] }) {
    return request<any>(`/boards/${boardId}/tasks/bulk_import`, { method: "POST", body: JSON.stringify(payload) });
  },
  async updateTask(taskId: string, payload: any) {
    return request<Task>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async moveTask(taskId: string, payload: any) {
    return request<Task>(`/tasks/${taskId}/move`, { method: "POST", body: JSON.stringify(payload) });
  },
  async transferTaskToBoard(
    taskId: string,
    payload: { targetBoardId: string; targetLaneId?: string | null; keepOwnerIfMember?: boolean }
  ) {
    return request<Task>(`/tasks/${taskId}/transfer-board`, { method: "POST", body: JSON.stringify(payload) });
  },
  async duplicateTaskToBoard(
    taskId: string,
    payload: {
      targetBoardId: string;
      targetLaneId?: string | null;
      includeChecklist?: boolean;
      includeComments?: boolean;
      includeDependencies?: boolean;
      keepOwnerIfMember?: boolean;
    }
  ) {
    return request<Task>(`/tasks/${taskId}/duplicate-to-board`, { method: "POST", body: JSON.stringify(payload) });
  },
  async task(taskId: string) {
    return request<Task>(`/tasks/${taskId}`);
  },
  async taskTypes(boardId: string) {
    return request<BoardTaskType[]>(`/boards/${boardId}/task_types`);
  },
  async createTaskType(boardId: string, payload: { key: string; name: string; color?: string | null }) {
    return request<BoardTaskType>(`/boards/${boardId}/task_types`, { method: "POST", body: JSON.stringify(payload) });
  },
  async updateTaskType(boardId: string, key: string, payload: { name?: string | null; color?: string | null; enabled?: boolean | null }) {
    return request<BoardTaskType>(`/boards/${boardId}/task_types/${encodeURIComponent(key)}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async reorderTaskTypes(boardId: string, keys: string[]) {
    return request<{ ok: boolean }>(`/boards/${boardId}/task_types/reorder`, { method: "POST", body: JSON.stringify({ keys }) });
  },
  async deleteTaskType(boardId: string, key: string) {
    return request<{ ok: boolean }>(`/boards/${boardId}/task_types/${encodeURIComponent(key)}`, { method: "DELETE" });
  },
  async priorities(boardId: string) {
    return request<BoardTaskPriority[]>(`/boards/${boardId}/priorities`);
  },
  async createPriority(boardId: string, payload: { key: string; name: string; color?: string | null; rank?: number | null }) {
    return request<BoardTaskPriority>(`/boards/${boardId}/priorities`, { method: "POST", body: JSON.stringify(payload) });
  },
  async updatePriority(boardId: string, key: string, payload: { name?: string | null; color?: string | null; enabled?: boolean | null }) {
    return request<BoardTaskPriority>(`/boards/${boardId}/priorities/${encodeURIComponent(key)}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async reorderPriorities(boardId: string, keys: string[]) {
    return request<{ ok: boolean }>(`/boards/${boardId}/priorities/reorder`, { method: "POST", body: JSON.stringify({ keys }) });
  },
  async deletePriority(boardId: string, key: string) {
    return request<{ ok: boolean }>(`/boards/${boardId}/priorities/${encodeURIComponent(key)}`, { method: "DELETE" });
  },
  async syncTaskFieldsToAllBoards(boardId: string) {
    return request<{
      ok: boolean;
      boardsTouched: number;
      typesCreated: number;
      typesUpdated: number;
      prioritiesCreated: number;
      prioritiesUpdated: number;
    }>(`/boards/${boardId}/task_fields/sync_all`, { method: "POST" });
  },
  async taskReminders(taskId: string) {
    return request<TaskReminder[]>(`/tasks/${taskId}/reminders`);
  },
  async taskIcsEmail(taskId: string, payload?: { to?: string; subject?: string; note?: string }) {
    return request<{ ok: boolean; to: string; provider: string; filename: string; detail?: any }>(`/tasks/${taskId}/ics/email`, {
      method: "POST",
      body: JSON.stringify(payload || {})
    });
  },
  async createTaskReminder(
    taskId: string,
    payload: { scheduledAt: string; recipient?: "me" | "owner"; channels?: ("inapp" | "external")[]; note?: string }
  ) {
    return request<TaskReminder>(`/tasks/${taskId}/reminders`, { method: "POST", body: JSON.stringify(payload) });
  },
  async cancelTaskReminder(reminderId: string) {
    return request<{ ok: boolean }>(`/reminders/${reminderId}`, { method: "DELETE" });
  },

  async checklist(taskId: string) {
    return request<any[]>(`/tasks/${taskId}/checklist`);
  },
  async addChecklist(taskId: string, text: string) {
    return request<any>(`/tasks/${taskId}/checklist`, { method: "POST", body: JSON.stringify({ text }) });
  },
  async updateChecklist(itemId: string, payload: any) {
    return request<any>(`/checklist/${itemId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async deleteChecklist(itemId: string) {
    return request<{ ok: boolean }>(`/checklist/${itemId}`, { method: "DELETE" });
  },

  async comments(taskId: string) {
    return request<any[]>(`/tasks/${taskId}/comments`);
  },
  async addComment(taskId: string, body: string) {
    return request<any>(`/tasks/${taskId}/comments`, { method: "POST", body: JSON.stringify({ body }) });
  },
  async updateComment(commentId: string, body: string) {
    return request<any>(`/comments/${commentId}`, { method: "PATCH", body: JSON.stringify({ body }) });
  },
  async deleteComment(commentId: string) {
    return request<{ ok: boolean }>(`/comments/${commentId}`, { method: "DELETE" });
  },

  async dependencies(taskId: string) {
    return request<any[]>(`/tasks/${taskId}/dependencies`);
  },
  async addDependency(taskId: string, dependsOnTaskId: string) {
    return request<any>(`/tasks/${taskId}/dependencies`, {
      method: "POST",
      body: JSON.stringify({ dependsOnTaskId })
    });
  },
  async deleteDependency(depId: string) {
    return request<{ ok: boolean }>(`/dependencies/${depId}`, { method: "DELETE" });
  },

  async uploadAttachment(taskId: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    return requestForm<any>(`/tasks/${taskId}/attachments`, form);
  },
  async attachments(taskId: string) {
    return request<any[]>(`/tasks/${taskId}/attachments`);
  },

  async audit(boardId?: string, taskId?: string) {
    const params: Record<string, string> = {};
    if (boardId) params.boardId = boardId;
    if (taskId) params.taskId = taskId;
    const qs = `?${new URLSearchParams(params)}`;
    return request<AuditEvent[]>(`/audit${qs}`);
  },

  async users(arg?: boolean | { includeInactive?: boolean; includeDeleted?: boolean }) {
    let includeInactive = false;
    let includeDeleted = false;
    if (typeof arg === "boolean") {
      includeInactive = arg;
    } else if (arg) {
      includeInactive = Boolean(arg.includeInactive);
      includeDeleted = Boolean(arg.includeDeleted);
    }
    const params = new URLSearchParams();
    if (includeInactive) params.set("includeInactive", "true");
    if (includeDeleted) params.set("includeDeleted", "true");
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<User[]>(`/users${qs}`);
  },
  async createUser(payload: { email: string; name: string; role: string; password?: string | null }) {
    return request<{ user: User; tempPassword?: string | null }>("/users", { method: "POST", body: JSON.stringify(payload) });
  },
  async inviteUser(payload: { email: string; name: string; role: string; inviteBaseUrl?: string | null }) {
    return request<{ user: User; inviteToken: string; inviteUrl: string; expiresAt: string; created: boolean }>("/users/invite", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  async updateUser(userId: string, payload: any) {
    return request<User>(`/users/${userId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async uploadUserAvatar(userId: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    return requestForm<{ ok: boolean; avatarPath: string }>(`/users/${userId}/avatar`, form);
  },
  async deleteUser(userId: string) {
    return request<{ ok: boolean }>(`/users/${userId}`, { method: "DELETE" });
  },
  async deleteUserV2(userId: string, payload: { mode: "unassign" } | { mode: "reassign"; reassignToUserId: string }) {
    return request<{ ok: boolean }>(`/users/${userId}/delete`, { method: "POST", body: JSON.stringify(payload) });
  },

  async aiTask(taskId: string, action: string) {
    return request<{
      text: string;
      suggestions?: any[];
      retrievalContext?: { similarTasks?: any[]; linkedRecords?: string[]; boardSignals?: string[] };
      intent?: { type: string; confidence: number; evidence?: string[] };
      missingInfo?: string[];
      acceptanceCriteria?: string[];
      implementationNotes?: string[];
      edgeCases?: string[];
      observability?: string[];
      definitionOfDone?: string[];
      priorityRecommendation?: { value: string; rationale: string; confidence: number };
      qualityScore?: { overall: number; dimensions?: Record<string, number>; reasonCodes?: string[] };
    }>(`/ai/task/${taskId}/${action}`, { method: "POST", body: JSON.stringify({}) });
  },
  async aiBoard(boardId: string, action: string) {
    return request<{ text: string; suggestions?: any[]; creates?: any[] }>(`/ai/board/${boardId}/${action}`, { method: "POST", body: JSON.stringify({}) });
  },

  async jiraConnections() {
    return request<any[]>("/jira/connections");
  },
  async jiraConnect(payload: any) {
    return request<any>("/jira/connect", { method: "POST", body: JSON.stringify(payload) });
  },
  async jiraConnectEnv() {
    return request<any>("/jira/connect-env", { method: "POST", body: JSON.stringify({}) });
  },
  async jiraImport(payload: any) {
    return request<SyncRun>("/jira/import", { method: "POST", body: JSON.stringify(payload) });
  },
  async jiraProfiles(boardId: string) {
    return request<any[]>(`/jira/profiles?${new URLSearchParams({ boardId })}`);
  },
  async jiraSyncNow(profileId: string) {
    return request<SyncRun>("/jira/sync-now", { method: "POST", body: JSON.stringify({ profileId }) });
  },
  async jiraSyncRuns(boardId: string) {
    return request<SyncRun[]>(`/jira/sync-runs?${new URLSearchParams({ boardId })}`);
  },
  async jiraUpdateConnection(connectionId: string, payload: { name?: string | null; defaultAssigneeAccountId?: string | null }) {
    return request<any>(`/jira/connections/${connectionId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async jiraDeleteConnection(connectionId: string) {
    return request<{ ok: boolean }>(`/jira/connections/${connectionId}`, { method: "DELETE" });
  },
  async jiraTestConnection(connectionId: string) {
    return request<{ ok: boolean; issuesSampled: number }>(`/jira/connections/${connectionId}/test`, { method: "POST", body: JSON.stringify({}) });
  },
  async openprojectConnections() {
    return request<any[]>("/openproject/connections");
  },
  async openprojectConnect(payload: { name?: string | null; baseUrl: string; apiToken: string; projectIdentifier?: string | null; enabled?: boolean }) {
    return request<any>("/openproject/connections", { method: "POST", body: JSON.stringify(payload) });
  },
  async openprojectUpdateConnection(connectionId: string, payload: { name?: string | null; apiToken?: string | null; projectIdentifier?: string | null; enabled?: boolean | null }) {
    return request<any>(`/openproject/connections/${connectionId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async openprojectDeleteConnection(connectionId: string) {
    return request<{ ok: boolean }>(`/openproject/connections/${connectionId}`, { method: "DELETE" });
  },
  async openprojectTestConnection(connectionId: string) {
    return request<{ ok: boolean; result: any }>(`/openproject/connections/${connectionId}/test`, { method: "POST", body: JSON.stringify({}) });
  },
  async githubConnections() {
    return request<any[]>("/github/connections");
  },
  async githubConnect(payload: { name?: string | null; baseUrl?: string | null; apiToken: string; defaultOwner?: string | null; defaultRepo?: string | null; enabled?: boolean }) {
    return request<any>("/github/connections", { method: "POST", body: JSON.stringify(payload) });
  },
  async githubUpdateConnection(connectionId: string, payload: { name?: string | null; apiToken?: string | null; defaultOwner?: string | null; defaultRepo?: string | null; enabled?: boolean | null }) {
    return request<any>(`/github/connections/${connectionId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async githubDeleteConnection(connectionId: string) {
    return request<{ ok: boolean }>(`/github/connections/${connectionId}`, { method: "DELETE" });
  },
  async githubTestConnection(connectionId: string) {
    return request<{ ok: boolean; result: any }>(`/github/connections/${connectionId}/test`, { method: "POST", body: JSON.stringify({}) });
  },
  async integrationStatus() {
    return request<{
      generatedAt: string;
      items: Array<{
        key: string;
        label: string;
        configured: boolean;
        enabled: boolean;
        state: "ok" | "error" | "unknown" | "not_configured";
        message?: string | null;
        lastCheckedAt?: string | null;
        updatedAt?: string | null;
      }>;
    }>("/integrations/status");
  },
  async jiraClearSyncRuns(boardId: string) {
    return request<{ ok: boolean }>(`/jira/sync-runs?${new URLSearchParams({ boardId })}`, { method: "DELETE" });
  },

  async taskJiraLink(taskId: string, payload: { connectionId: string; jiraKey: string; enableSync: boolean }) {
    return request<Task>(`/tasks/${taskId}/jira/link`, { method: "POST", body: JSON.stringify(payload) });
  },
  async taskJiraCreate(
    taskId: string,
    payload: {
      connectionId: string;
      projectKey: string;
      issueType: string;
      enableSync: boolean;
      assigneeMode: "projectDefault" | "taskOwner" | "unassigned" | "connectionDefault";
    }
  ) {
    return request<Task>(`/tasks/${taskId}/jira/create`, { method: "POST", body: JSON.stringify(payload) });
  },
  async taskJiraPull(taskId: string) {
    return request<Task>(`/tasks/${taskId}/jira/pull`, { method: "POST", body: JSON.stringify({}) });
  },
  async taskJiraSync(taskId: string) {
    return request<Task>(`/tasks/${taskId}/jira/sync`, { method: "POST", body: JSON.stringify({}) });
  },
  async taskJiraIssue(taskId: string) {
    return request<any>(`/tasks/${taskId}/jira/issue`);
  },
  async taskOpenProjectLink(taskId: string, payload: { connectionId: string; workPackageId: number; enableSync: boolean }) {
    return request<Task>(`/tasks/${taskId}/openproject/link`, { method: "POST", body: JSON.stringify(payload) });
  },
  async taskOpenProjectCreate(taskId: string, payload: { connectionId: string; projectIdentifier?: string | null; enableSync: boolean }) {
    return request<Task>(`/tasks/${taskId}/openproject/create`, { method: "POST", body: JSON.stringify(payload) });
  },
  async taskOpenProjectPull(taskId: string) {
    return request<Task>(`/tasks/${taskId}/openproject/pull`, { method: "POST", body: JSON.stringify({}) });
  },
  async taskOpenProjectSync(taskId: string) {
    return request<Task>(`/tasks/${taskId}/openproject/sync`, { method: "POST", body: JSON.stringify({}) });
  },
  async taskOpenProjectWorkPackage(taskId: string) {
    return request<any>(`/tasks/${taskId}/openproject/work-package`);
  },

  async webhookSecrets() {
    return request<any[]>("/webhooks/secrets");
  },
  async webhookUpsertSecret(payload: { source: string; enabled: boolean; bearerToken?: string | null }) {
    return request<any>("/webhooks/secrets", { method: "POST", body: JSON.stringify(payload) });
  },
  async webhookRotateSecret(source: string) {
    return request<any>(`/webhooks/secrets/${encodeURIComponent(source)}/rotate`, { method: "POST", body: JSON.stringify({}) });
  },
  async webhookDisableSecret(source: string) {
    return request<{ ok: boolean }>(`/webhooks/secrets/${encodeURIComponent(source)}`, { method: "DELETE" });
  },
  async webhookEvents(source?: string | null, limit: number = 50) {
    const params: Record<string, string> = { limit: String(limit) };
    if (source) params.source = source;
    return request<any[]>(`/webhooks/events?${new URLSearchParams(params)}`);
  },
  async webhookReplay(eventId: string) {
    return request<any>(`/webhooks/events/${eventId}/replay`, { method: "POST", body: JSON.stringify({}) });
  },

  async notificationDestinations() {
    return request<any[]>("/notifications/destinations");
  },
  async notificationCreateDestination(payload: any) {
    return request<any>("/notifications/destinations", { method: "POST", body: JSON.stringify(payload) });
  },
  async notificationUpdateDestination(destinationId: string, payload: any) {
    return request<any>(`/notifications/destinations/${destinationId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  async notificationDeleteDestination(destinationId: string) {
    return request<{ ok: boolean }>(`/notifications/destinations/${destinationId}`, { method: "DELETE" });
  },
  async notificationPreferences() {
    return request<any>("/notifications/preferences");
  },
  async notificationUpdatePreferences(payload: {
    mentions?: boolean;
    comments?: boolean;
    moves?: boolean;
    assignments?: boolean;
    overdue?: boolean;
    quietHoursEnabled?: boolean;
    quietHoursStart?: string | null;
    quietHoursEnd?: string | null;
  }) {
    return request<any>("/notifications/preferences", { method: "PATCH", body: JSON.stringify(payload) });
  },
  async notificationTestDestination(destinationId: string, payload: { title: string; message: string; priority?: number }) {
    return request<any>(`/notifications/destinations/${destinationId}/test`, { method: "POST", body: JSON.stringify(payload) });
  },

  async backups() {
    return request<any[]>("/backups");
  },
  async backupPolicy() {
    return request<any>("/backups/policy");
  },
  async updateBackupPolicy(payload: {
    retentionDays?: number;
    minIntervalMinutes?: number;
    maxBackups?: number;
    maxTotalSizeMb?: number;
  }) {
    return request<any>("/backups/policy", { method: "PATCH", body: JSON.stringify(payload) });
  },
  async createFullBackup() {
    return request<any>("/backups/full", { method: "POST", body: JSON.stringify({}) });
  },
  async createMachineRecoveryExport() {
    return request<any>("/backups/full_export", { method: "POST", body: JSON.stringify({}) });
  },
  async deleteBackup(filename: string) {
    return request<any>(`/backups/${encodeURIComponent(filename)}`, { method: "DELETE" });
  },
  async restoreBackup(payload: { filename: string; mode: "skip_existing" | "overwrite" | "merge_non_conflicting"; dryRun?: boolean }) {
    return request<any>("/backups/restore", { method: "POST", body: JSON.stringify(payload) });
  },
  async uploadBackupAndRestore(file: File, payload: { mode: "skip_existing" | "overwrite" | "merge_non_conflicting"; dryRun?: boolean }) {
    const form = new FormData();
    form.append("file", file);
    const qs = new URLSearchParams({ mode: payload.mode, dryRun: payload.dryRun ? "true" : "false" });
    const res = await fetch(`${API_URL}/backups/upload?${qs.toString()}`, { method: "POST", body: form, credentials: "include" });
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const j = await res.json();
        detail = j.detail || JSON.stringify(j);
      } catch {
        // ignore
      }
      throw new Error(detail);
    }
    return (await res.json()) as any;
  },

  async inappNotifications(params?: { unreadOnly?: boolean; limit?: number }) {
    const p = new URLSearchParams();
    if (params?.unreadOnly) p.set("unreadOnly", "true");
    if (params?.limit) p.set("limit", String(params.limit));
    const qs = p.toString() ? `?${p.toString()}` : "";
    return request<any[]>(`/notifications/inapp${qs}`);
  },
  async markNotificationsRead(ids: string[]) {
    return request<{ ok: boolean }>("/notifications/inapp/mark-read", { method: "POST", body: JSON.stringify({ ids }) });
  },
  async markAllNotificationsRead() {
    return request<{ ok: boolean }>("/notifications/inapp/mark-all-read", { method: "POST" });
  },

  async systemStatus() {
    return request<{
      generatedAt: string;
      version: string;
      buildSha: string;
      sections: Array<{
        key: string;
        label: string;
        state: "green" | "yellow" | "red";
        details: string[];
        updatedAt: string;
      }>;
    }>("/admin/system-status");
  }
};
