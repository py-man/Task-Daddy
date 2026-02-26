"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function SettingsUsersPage() {
  const { user } = useSession();
  const [users, setUsers] = useState<any[] | null>(null);
  const [creating, setCreating] = useState({ email: "", name: "", role: "member" as "admin" | "member" | "viewer" });
  const [inviting, setInviting] = useState({ email: "", name: "", role: "member" as "admin" | "member" | "viewer" });
  const [inviteResult, setInviteResult] = useState<{ inviteUrl: string; inviteToken: string; expiresAt: string } | null>(null);
  const [showDeleted, setShowDeleted] = useState(false);

  const isAdmin = user?.role === "admin";

  const load = async () => {
    try {
      const us = await api.users({ includeInactive: true, includeDeleted: showDeleted });
      setUsers(us);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  useEffect(() => {
    if (!isAdmin) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin, showDeleted]);

  const activeUsers = useMemo(() => (users || []).filter((u) => u.active !== false), [users]);
  const inactiveUsers = useMemo(() => (users || []).filter((u) => u.active === false), [users]);

  if (!isAdmin) {
    return <div className="glass rounded-3xl shadow-neon border border-white/10 p-5 text-sm text-muted">Admin only.</div>;
  }

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-lg font-semibold">Users</div>
          <div className="mt-1 text-sm text-muted">Create, edit, disable, or delete users. Admin actions require MFA.</div>
        </div>
        <Button
          variant="ghost"
          onClick={async () => {
            await load();
            toast.success("Refreshed");
          }}
        >
          Refresh
        </Button>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">Create user</div>
        <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 items-end">
          <div className="md:col-span-2">
            <div className="text-xs text-muted mb-1">Email</div>
            <Input
              data-testid="settings-create-user-email"
              value={creating.email}
              onChange={(e) => setCreating({ ...creating, email: e.target.value })}
              placeholder="new.user@company.com"
            />
          </div>
          <div>
            <div className="text-xs text-muted mb-1">Role</div>
            <select
              data-testid="settings-create-user-role"
              className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
              value={creating.role}
              onChange={(e) => setCreating({ ...creating, role: e.target.value as any })}
            >
              {["viewer", "member", "admin"].map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-3">
            <div className="text-xs text-muted mb-1">Display name</div>
            <Input
              data-testid="settings-create-user-name"
              value={creating.name}
              onChange={(e) => setCreating({ ...creating, name: e.target.value })}
              placeholder="New User"
            />
          </div>
          <div className="md:col-span-3 flex justify-end">
            <Button
              data-testid="settings-create-user-submit"
              variant="ghost"
              onClick={async () => {
                try {
                  const res = await api.createUser({ email: creating.email, name: creating.name, role: creating.role });
                  toast.success(res.tempPassword ? `User created. Temp password: ${res.tempPassword}` : "User already exists");
                  setCreating({ email: "", name: "", role: "member" });
                  await load();
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                }
              }}
            >
              Create
            </Button>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm">
        <span className="text-muted">Admin actions require MFA. </span>
        <Link href="/app/settings/security" className="underline text-text">
          Open Security settings
        </Link>
      </div>

      <div className="mt-4 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">Invite user</div>
        <div className="mt-1 text-xs text-muted">Creates or reactivates an account and generates a 24-hour password setup link.</div>
        <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 items-end">
          <div className="md:col-span-2">
            <div className="text-xs text-muted mb-1">Email</div>
            <Input value={inviting.email} onChange={(e) => setInviting({ ...inviting, email: e.target.value })} placeholder="new.user@company.com" />
          </div>
          <div>
            <div className="text-xs text-muted mb-1">Role</div>
            <select className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm" value={inviting.role} onChange={(e) => setInviting({ ...inviting, role: e.target.value as any })}>
              {["viewer", "member", "admin"].map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-3">
            <div className="text-xs text-muted mb-1">Display name</div>
            <Input value={inviting.name} onChange={(e) => setInviting({ ...inviting, name: e.target.value })} placeholder="New User" />
          </div>
          <div className="md:col-span-3 flex justify-end">
            <Button
              variant="ghost"
              onClick={async () => {
                try {
                  const base = typeof window !== "undefined" ? window.location.origin : undefined;
                  const res = await api.inviteUser({ email: inviting.email, name: inviting.name, role: inviting.role, inviteBaseUrl: base });
                  setInviteResult({ inviteUrl: res.inviteUrl, inviteToken: res.inviteToken, expiresAt: res.expiresAt });
                  toast.success(res.created ? "Invite created" : "Invite refreshed");
                  setInviting({ email: "", name: "", role: "member" });
                  await load();
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                }
              }}
            >
              Invite
            </Button>
          </div>
        </div>

        {inviteResult ? (
          <div className="mt-3 rounded-2xl border border-white/10 bg-black/20 p-3 text-xs">
            <div className="text-muted">Invite URL (expires {new Date(inviteResult.expiresAt).toLocaleString()})</div>
            <div className="mt-1 break-all font-mono">{inviteResult.inviteUrl}</div>
            <div className="mt-2 text-muted">Invite token</div>
            <div className="mt-1 break-all font-mono">{inviteResult.inviteToken}</div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  await navigator.clipboard.writeText(inviteResult.inviteUrl);
                  toast.success("Invite URL copied");
                }}
              >
                Copy URL
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  await navigator.clipboard.writeText(inviteResult.inviteToken);
                  toast.success("Invite token copied");
                }}
              >
                Copy token
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
        <div>
          <div className="text-sm font-semibold">Visibility</div>
          <div className="text-xs text-muted">Deleted users are hidden by default (soft-delete).</div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showDeleted} onChange={(e) => setShowDeleted(e.target.checked)} />
          <span>Show deleted</span>
        </label>
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold">Active users</div>
        {users === null ? (
          <Skeleton className="h-24 w-full mt-3" />
        ) : (
          <div className="mt-3 space-y-2">
            {activeUsers.map((u) => (
              <UserRow key={u.id} user={u} allUsers={activeUsers} onChanged={load} />
            ))}
          </div>
        )}
      </div>

      <div className="mt-6">
        <div className="text-sm font-semibold">Disabled users</div>
        {users === null ? (
          <Skeleton className="h-20 w-full mt-3" />
        ) : inactiveUsers.length === 0 ? (
          <div className="text-sm text-muted mt-2">No disabled users.</div>
        ) : (
          <div className="mt-3 space-y-2">
            {inactiveUsers.map((u) => (
              <UserRow key={u.id} user={u} allUsers={activeUsers} onChanged={load} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function UserRow({ user, allUsers, onChanged }: { user: any; allUsers: any[]; onChanged: () => Promise<void> }) {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteMode, setDeleteMode] = useState<"unassign" | "reassign">("unassign");
  const [reassignTo, setReassignTo] = useState<string>("");
  const reassignOptions = allUsers.filter((u) => u.id !== user.id);
  const isDeleted = String(user.email || "").startsWith("deleted+");

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-3 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="text-sm font-medium truncate">
          {user.name} {user.active === false ? <span className="text-danger">(disabled)</span> : null}
        </div>
        <div className="text-xs text-muted truncate">{user.email}</div>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="muted">{user.role}</Badge>
        {isDeleted ? <Badge variant="muted">Deleted</Badge> : null}
        {user.mfaEnabled ? <Badge variant="ok">MFA</Badge> : <Badge variant="warn">No MFA</Badge>}
        {user.loginDisabled ? <Badge variant="danger">Login blocked</Badge> : <Badge variant="ok">Login allowed</Badge>}
        <Dialog>
          <DialogTrigger asChild>
            <Button size="sm" variant="ghost">
              Edit
            </Button>
          </DialogTrigger>
          <DialogContent>
            <EditUserDialog user={user} onSaved={onChanged} />
          </DialogContent>
        </Dialog>

        <Button
          size="sm"
          variant="ghost"
          disabled={isDeleted}
          onClick={async () => {
            try {
              await api.updateUser(user.id, { active: user.active === false ? true : false });
              toast.success(user.active === false ? "Enabled" : "Disabled");
              await onChanged();
            } catch (e: any) {
              toast.error(String(e?.message || e));
            }
          }}
        >
          {user.active === false ? "Enable" : "Disable"}
        </Button>
        <Button
          size="sm"
          variant={user.loginDisabled ? "warn" : "ghost"}
          disabled={isDeleted || user.active === false}
          onClick={async () => {
            try {
              await api.updateUser(user.id, { loginDisabled: user.loginDisabled ? false : true });
              toast.success(user.loginDisabled ? "Login enabled" : "Login blocked");
              await onChanged();
            } catch (e: any) {
              toast.error(String(e?.message || e));
            }
          }}
        >
          {user.loginDisabled ? "Allow login" : "Block login"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={isDeleted}
          onClick={async () => {
            try {
              const base = typeof window !== "undefined" ? window.location.origin : undefined;
              const out = await api.passwordResetRequest(String(user.email || ""), base);
              if (out?.emailSent) toast.success("Reset email sent");
              else toast.message("Reset requested", { description: "No SMTP destination is active yet. Configure Settings → Notifications." });
            } catch (e: any) {
              const msg = String(e?.message || e);
              if (msg.includes("MFA setup required")) {
                toast.message("MFA required", { description: "Enable MFA in Settings → Security, then retry." });
              } else {
                toast.error(msg);
              }
            }
          }}
        >
          Send reset
        </Button>

        <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
          <DialogTrigger asChild>
            <Button size="sm" variant="danger" disabled={isDeleted}>
              Delete
            </Button>
          </DialogTrigger>
          <DialogContent>
            <div className="text-lg font-semibold">Delete user</div>
            <div className="mt-1 text-sm text-muted">
              Deleting disables the user and invalidates all sessions. You must choose what happens to owned tasks.
            </div>

            <div className="mt-4 space-y-3 text-sm">
              <label className="flex items-center gap-2">
                <input type="radio" checked={deleteMode === "unassign"} onChange={() => setDeleteMode("unassign")} />
                <span>Unassign their tasks</span>
              </label>
              <label className="flex items-center gap-2">
                <input type="radio" checked={deleteMode === "reassign"} onChange={() => setDeleteMode("reassign")} />
                <span>Reassign tasks to another user</span>
              </label>

              {deleteMode === "reassign" ? (
                <div>
                  <div className="text-xs text-muted mb-1">Reassign to</div>
                  <select className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm" value={reassignTo} onChange={(e) => setReassignTo(e.target.value)}>
                    <option value="">Select user…</option>
                    {reassignOptions.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name} ({u.email})
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDeleteOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                disabled={deleteMode === "reassign" && !reassignTo}
                onClick={async () => {
                  try {
                    await api.deleteUserV2(
                      user.id,
                      deleteMode === "reassign" ? { mode: "reassign", reassignToUserId: reassignTo } : { mode: "unassign" }
                    );
                    toast.success("Deleted");
                    setDeleteOpen(false);
                    await onChanged();
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Delete user
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}

function EditUserDialog({ user, onSaved }: { user: any; onSaved: () => Promise<void> }) {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const [form, setForm] = useState<any>({
    name: user.name || "",
    email: user.email || "",
    role: user.role || "member",
    timezone: user.timezone || "",
    jiraAccountId: user.jiraAccountId || "",
    avatarUrl: user.avatarUrl || "",
    loginDisabled: Boolean(user.loginDisabled),
    password: "",
  });
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [saving, setSaving] = useState(false);
  const timezoneOptions = useMemo(() => {
    const fallback = ["UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Europe/London"];
    const supported: string[] =
      typeof Intl !== "undefined" && (Intl as any).supportedValuesOf ? ((Intl as any).supportedValuesOf("timeZone") as string[]) : fallback;
    return Array.from(new Set(supported)).sort();
  }, []);
  const avatarPreview = form.avatarUrl
    ? String(form.avatarUrl).startsWith("/")
      ? `${apiBase}${form.avatarUrl}`
      : String(form.avatarUrl)
    : null;

  return (
    <div>
      <div className="text-lg font-semibold">Edit user</div>
      <div className="mt-3 space-y-2">
        <div className="text-xs text-muted">Name</div>
        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <div className="text-xs text-muted">Email</div>
        <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <div className="text-xs text-muted">Role</div>
        <select className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          {["viewer", "member", "admin"].map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-xs text-muted">Timezone</div>
            <select className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm" value={form.timezone || ""} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
              <option value="">Unset</option>
              {timezoneOptions.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div className="text-xs text-muted">Jira accountId</div>
            <Input value={form.jiraAccountId} onChange={(e) => setForm({ ...form, jiraAccountId: e.target.value })} placeholder="712020:..." />
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={Boolean(form.loginDisabled)}
              onChange={(e) => setForm({ ...form, loginDisabled: e.target.checked })}
            />
            <span>Block this user from login (keep account active for ownership/integrations)</span>
          </label>
        </div>
        <div>
          <div className="text-xs text-muted">Set password (optional)</div>
          <Input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Leave blank to keep existing password"
          />
        </div>
        <div>
          <div className="text-xs text-muted">Avatar logo</div>
          <div className="mt-1 flex items-center gap-3">
            <div className="h-12 w-12 rounded-xl border border-white/10 bg-white/5 overflow-hidden grid place-items-center text-xs text-muted">
              {avatarPreview ? <img src={avatarPreview} alt="Avatar" className="h-full w-full object-cover" /> : "No logo"}
            </div>
            <label className="text-sm underline cursor-pointer">
              Upload image
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                className="hidden"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  setUploadingAvatar(true);
                  try {
                    const out = await api.uploadUserAvatar(user.id, f);
                    setForm((prev: any) => ({ ...prev, avatarUrl: out.avatarPath }));
                    toast.success("Avatar uploaded");
                  } catch (err: any) {
                    toast.error(String(err?.message || err));
                  } finally {
                    setUploadingAvatar(false);
                    e.currentTarget.value = "";
                  }
                }}
              />
            </label>
            <Button size="sm" variant="ghost" disabled={uploadingAvatar} onClick={() => setForm({ ...form, avatarUrl: "" })}>
              Clear
            </Button>
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-3">
          <Button
            variant="ghost"
            disabled={saving || uploadingAvatar}
            onClick={async () => {
              setSaving(true);
              try {
                await api.updateUser(user.id, {
                  name: form.name,
                  email: form.email,
                  role: form.role,
                  timezone: form.timezone.trim() || null,
                  jiraAccountId: form.jiraAccountId.trim() || null,
                  avatarUrl: form.avatarUrl.trim() || null,
                  loginDisabled: Boolean(form.loginDisabled),
                  password: form.password.trim() ? form.password.trim() : null,
                });
                toast.success("Saved");
                await onSaved();
              } catch (e: any) {
                toast.error(String(e?.message || e));
              } finally {
                setSaving(false);
              }
            }}
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}
