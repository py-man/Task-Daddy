"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function SettingsNotificationsPage() {
  const { user } = useSession();
  const isAdmin = user?.role === "admin";
  const [loading, setLoading] = useState(true);
  const [prefLoading, setPrefLoading] = useState(true);
  const [destinations, setDestinations] = useState<any[]>([]);
  const [prefs, setPrefs] = useState<any>({
    mentions: true,
    comments: true,
    moves: true,
    assignments: true,
    overdue: true,
    quietHoursEnabled: false,
    quietHoursStart: "22:00",
    quietHoursEnd: "07:00",
    timezone: user?.timezone || "UTC"
  });
  const [form, setForm] = useState({
    name: "Pushover",
    enabled: true,
    appToken: "",
    userKey: ""
  });
  const [smtpForm, setSmtpForm] = useState({
    name: "SMTP",
    enabled: false,
    host: "",
    port: "587",
    username: "",
    password: "",
    from: "",
    to: "",
    starttls: true
  });
  const existingPushover = useMemo(() => destinations.find((d) => d.provider === "pushover") || null, [destinations]);
  const existingSmtp = useMemo(() => destinations.find((d) => d.provider === "smtp") || null, [destinations]);

  const load = async () => {
    setPrefLoading(true);
    if (isAdmin) setLoading(true);
    try {
      const pref = await api.notificationPreferences();
      setPrefs(pref);
      if (isAdmin) {
        const ds = await api.notificationDestinations();
        setDestinations(ds);
        const pushover = ds.find((d: any) => d.provider === "pushover") || null;
        const smtp = ds.find((d: any) => d.provider === "smtp") || null;
        if (pushover) setForm((f) => ({ ...f, name: pushover.name || "Pushover", enabled: Boolean(pushover.enabled) }));
        if (smtp) setSmtpForm((f) => ({ ...f, name: smtp.name || "SMTP", enabled: Boolean(smtp.enabled) }));
      }
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setPrefLoading(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-semibold">Notifications</div>
          <div className="mt-1 text-sm text-muted">Configure your alert preferences and, for admins, outbound channels. Secrets are encrypted.</div>
        </div>
        <Badge variant="muted">{isAdmin ? "User + Admin" : "User"}</Badge>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">My preferences</div>
        <div className="mt-1 text-xs text-muted">Choose which in-app notifications you receive and set quiet hours.</div>
        {prefLoading ? (
          <Skeleton className="h-24 w-full mt-4" />
        ) : (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              ["mentions", "Mentions"],
              ["comments", "Comments on my tasks"],
              ["moves", "Task moved"],
              ["assignments", "Task assigned"],
              ["overdue", "Overdue alerts"]
            ].map(([k, label]) => (
              <label key={k} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={Boolean((prefs as any)[k])}
                  onChange={(e) => setPrefs((p: any) => ({ ...p, [k]: e.target.checked }))}
                />
                <span>{label}</span>
              </label>
            ))}
            <label className="md:col-span-2 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={Boolean(prefs.quietHoursEnabled)}
                onChange={(e) => setPrefs((p: any) => ({ ...p, quietHoursEnabled: e.target.checked }))}
              />
              <span>Enable quiet hours</span>
            </label>
            <div>
              <div className="text-xs text-muted mb-1">Quiet start (HH:MM)</div>
              <Input value={prefs.quietHoursStart || ""} onChange={(e) => setPrefs((p: any) => ({ ...p, quietHoursStart: e.target.value }))} />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Quiet end (HH:MM)</div>
              <Input value={prefs.quietHoursEnd || ""} onChange={(e) => setPrefs((p: any) => ({ ...p, quietHoursEnd: e.target.value }))} />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <Button
                onClick={async () => {
                  try {
                    const out = await api.notificationUpdatePreferences({
                      mentions: Boolean(prefs.mentions),
                      comments: Boolean(prefs.comments),
                      moves: Boolean(prefs.moves),
                      assignments: Boolean(prefs.assignments),
                      overdue: Boolean(prefs.overdue),
                      quietHoursEnabled: Boolean(prefs.quietHoursEnabled),
                      quietHoursStart: prefs.quietHoursStart || null,
                      quietHoursEnd: prefs.quietHoursEnd || null
                    });
                    setPrefs(out);
                    toast.success("Preferences saved");
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Save preferences
              </Button>
            </div>
          </div>
        )}
      </div>

      {!isAdmin ? null : (
        <>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm font-semibold">Pushover</div>
          <div className="flex items-center gap-2">
            {existingPushover ? <Badge variant="ok">Saved</Badge> : <Badge variant="warn">Not configured</Badge>}
            {existingPushover?.tokenHint ? <Badge variant="muted">User {existingPushover.tokenHint}</Badge> : null}
          </div>
        </div>
        <div className="mt-1 text-xs text-muted">Use this to send instant push notifications to your device (test send supported).</div>

        {loading ? (
          <Skeleton className="h-24 w-full mt-4" />
        ) : (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 items-end">
            <div className="md:col-span-2">
              <div className="text-xs text-muted mb-1">Name</div>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Pushover" />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">App token</div>
              <Input value={form.appToken} onChange={(e) => setForm({ ...form, appToken: e.target.value })} placeholder="(stored encrypted)" />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">User key</div>
              <Input value={form.userKey} onChange={(e) => setForm({ ...form, userKey: e.target.value })} placeholder="(stored encrypted)" />
            </div>
            <label className="md:col-span-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              <span>Enabled</span>
            </label>

            <div className="md:col-span-2 flex flex-wrap justify-end gap-2">
              {existingPushover ? (
                <Button
                  variant="danger"
                  onClick={async () => {
                    const ok = confirm("Delete this Pushover destination?");
                    if (!ok) return;
                    try {
                      await api.notificationDeleteDestination(existingPushover.id);
                      toast.success("Deleted");
                      setForm({ name: "Pushover", enabled: true, appToken: "", userKey: "" });
                      await load();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    }
                  }}
                >
                  Delete
                </Button>
              ) : null}
              <Button
                variant="ghost"
                onClick={async () => {
                  try {
                    if (existingPushover) {
                      await api.notificationUpdateDestination(existingPushover.id, {
                        provider: "pushover",
                        name: form.name,
                        enabled: form.enabled,
                        pushoverAppToken: form.appToken || undefined,
                        pushoverUserKey: form.userKey || undefined
                      });
                      toast.success("Saved");
                    } else {
                      await api.notificationCreateDestination({
                        provider: "pushover",
                        name: form.name,
                        enabled: form.enabled,
                        pushoverAppToken: form.appToken,
                        pushoverUserKey: form.userKey
                      });
                      toast.success("Saved");
                    }
                    setForm((f) => ({ ...f, appToken: "", userKey: "" }));
                    await load();
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Save
              </Button>
              <Button
                disabled={!existingPushover}
                onClick={async () => {
                  if (!existingPushover) return;
                  try {
                    const res = await api.notificationTestDestination(existingPushover.id, {
                      title: "Task-Daddy",
                      message: "Test notification",
                      priority: 0
                    });
                    toast.success(`Sent (${res.provider})`);
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Send test
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm font-semibold">Email (SMTP)</div>
          <div className="flex items-center gap-2">
            {existingSmtp ? <Badge variant="ok">Saved</Badge> : <Badge variant="muted">Optional</Badge>}
            {existingSmtp?.tokenHint ? <Badge variant="muted">To {existingSmtp.tokenHint}</Badge> : null}
          </div>
        </div>
        <div className="mt-1 text-xs text-muted">Send notifications via SMTP. Credentials are stored encrypted and never shown back.</div>

        {loading ? (
          <Skeleton className="h-24 w-full mt-4" />
        ) : (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 items-end">
            <div className="md:col-span-2">
              <div className="text-xs text-muted mb-1">Name</div>
              <Input value={smtpForm.name} onChange={(e) => setSmtpForm({ ...smtpForm, name: e.target.value })} placeholder="SMTP" />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Host</div>
              <Input value={smtpForm.host} onChange={(e) => setSmtpForm({ ...smtpForm, host: e.target.value })} placeholder="smtp.example.com" />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Port</div>
              <Input value={smtpForm.port} onChange={(e) => setSmtpForm({ ...smtpForm, port: e.target.value })} placeholder="587" />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Username</div>
              <Input value={smtpForm.username} onChange={(e) => setSmtpForm({ ...smtpForm, username: e.target.value })} placeholder="(optional)" />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Password</div>
              <Input
                type="password"
                value={smtpForm.password}
                onChange={(e) => setSmtpForm({ ...smtpForm, password: e.target.value })}
                placeholder="(stored encrypted)"
              />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">From</div>
              <Input value={smtpForm.from} onChange={(e) => setSmtpForm({ ...smtpForm, from: e.target.value })} placeholder="hello@yourdomain.com" />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">To</div>
              <Input value={smtpForm.to} onChange={(e) => setSmtpForm({ ...smtpForm, to: e.target.value })} placeholder="you@company.com" />
            </div>
            <label className="md:col-span-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={smtpForm.starttls} onChange={(e) => setSmtpForm({ ...smtpForm, starttls: e.target.checked })} />
              <span>StartTLS</span>
            </label>
            <label className="md:col-span-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={smtpForm.enabled} onChange={(e) => setSmtpForm({ ...smtpForm, enabled: e.target.checked })} />
              <span>Enabled</span>
            </label>
            <div className="md:col-span-2 flex flex-wrap justify-end gap-2">
              {existingSmtp ? (
                <Button
                  variant="danger"
                  onClick={async () => {
                    const ok = confirm("Delete this SMTP destination?");
                    if (!ok) return;
                    try {
                      await api.notificationDeleteDestination(existingSmtp.id);
                      toast.success("Deleted");
                      setSmtpForm({ name: "SMTP", enabled: false, host: "", port: "587", username: "", password: "", from: "", to: "", starttls: true });
                      await load();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    }
                  }}
                >
                  Delete
                </Button>
              ) : null}
              <Button
                variant="ghost"
                onClick={async () => {
                  try {
                    const payload = {
                      provider: "smtp",
                      name: smtpForm.name,
                      enabled: smtpForm.enabled,
                      smtpHost: smtpForm.host || undefined,
                      smtpPort: smtpForm.port ? Number(smtpForm.port) : undefined,
                      smtpUsername: smtpForm.username || undefined,
                      smtpPassword: smtpForm.password || undefined,
                      smtpFrom: smtpForm.from || undefined,
                      smtpTo: smtpForm.to || undefined,
                      smtpStarttls: smtpForm.starttls
                    };
                    if (existingSmtp) {
                      await api.notificationUpdateDestination(existingSmtp.id, payload);
                      toast.success("Saved");
                    } else {
                      await api.notificationCreateDestination(payload);
                      toast.success("Saved");
                    }
                    setSmtpForm((f) => ({ ...f, password: "" }));
                    await load();
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Save
              </Button>
              <Button
                disabled={!existingSmtp}
                onClick={async () => {
                  if (!existingSmtp) return;
                  try {
                    const res = await api.notificationTestDestination(existingSmtp.id, {
                      title: "Task-Daddy",
                      message: "Test email notification",
                      priority: 0
                    });
                    toast.success(`Sent (${res.provider})`);
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Send test
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm">
        <div className="font-semibold">SMTP setup quick guide</div>
        <ol className="mt-2 list-decimal pl-5 text-xs text-muted space-y-1">
          <li>Host + Port: use your mail provider values (most providers use port 587 with StartTLS on).</li>
          <li>From: the sender address your SMTP account is allowed to send from.</li>
          <li>To: default recipient for reminders/password reset test messages.</li>
          <li>Save, then click <span className="text-text">Send test</span> to verify delivery.</li>
        </ol>
        <div className="mt-2 text-xs">
          <Link href="/app/help#smtp-setup" className="underline text-muted hover:text-text">
            Open full SMTP help and troubleshooting
          </Link>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm">
        <div className="font-semibold">What’s next</div>
        <div className="mt-1 text-xs text-muted">
          MVP includes in-app notifications (bell) + task create/assign/overdue triggers. Next iteration: per-user preferences, quiet hours, and more channels (Slack/webhooks).
        </div>
      </div>
        </>
      )}
    </div>
  );
}
