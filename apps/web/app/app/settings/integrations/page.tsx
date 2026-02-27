"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function SettingsIntegrationsPage() {
  const { user } = useSession();
  const isAdmin = user?.role === "admin";
  const [statusItems, setStatusItems] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [testingKey, setTestingKey] = useState<string | null>(null);

  const live = useMemo(() => ([
    {
      key: "jira",
      title: "Jira",
      href: "/app/integrations/jira",
      desc: "Connections, sync profiles, sync runs, and per-task linking.",
    },
    {
      key: "openproject",
      title: "OpenProject",
      href: "/app/integrations/openproject",
      desc: "Connection management and task-level linkage/sync controls.",
    },
    {
      key: "github",
      title: "GitHub",
      href: "/app/integrations/github",
      desc: "Connection management for upcoming GitHub Issues and Projects sync.",
    },
    {
      key: "webhooks",
      title: "Webhooks",
      href: "/app/integrations/webhooks",
      desc: "Inbound webhook secrets, event inbox, replay, and idempotent processing.",
    },
    {
      key: "smtp",
      title: "SMTP Email",
      href: "/app/settings/notifications",
      desc: "Password reset, reminder delivery, and task invite emails.",
    },
    {
      key: "pushover",
      title: "Pushover",
      href: "/app/settings/notifications",
      desc: "Push notifications for reminders, overdue events, and test sends.",
    },
    {
      key: "slack",
      title: "Slack",
      href: "/app/settings/notifications",
      desc: "Channel alerts via incoming webhook destination.",
    },
    {
      key: "teams",
      title: "Microsoft Teams",
      href: "/app/settings/notifications",
      desc: "Enterprise channel alerts via Teams webhook destination.",
    },
  ]), []);

  const refreshStatus = async () => {
    setLoading(true);
    try {
      const out = await api.integrationStatus();
      setStatusItems(out.items || []);
    } catch (e: any) {
      setStatusItems([]);
      toast.error(String(e?.message || e || "Failed to load integration status"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  const supportsQuickTest = (key: string) =>
    ["jira", "openproject", "github", "smtp", "pushover", "slack", "teams"].includes(key);

  const runQuickTest = async (key: string, title: string) => {
    try {
      setTestingKey(key);
      if (key === "jira") {
        const cs = await api.jiraConnections();
        const c = (cs || []).find((x: any) => !x.needsReconnect) || cs?.[0];
        if (!c) throw new Error("No Jira connection configured.");
        if (c.needsReconnect) throw new Error("Jira connection needs reconnect. Re-save token first.");
        await api.jiraTestConnection(c.id);
      } else if (key === "openproject") {
        const cs = await api.openprojectConnections();
        const c = (cs || []).find((x: any) => x.enabled) || cs?.[0];
        if (!c) throw new Error("No OpenProject connection configured.");
        if (!c.enabled) throw new Error("OpenProject connection is disabled.");
        await api.openprojectTestConnection(c.id);
      } else if (key === "github") {
        const cs = await api.githubConnections();
        const c = (cs || []).find((x: any) => x.enabled) || cs?.[0];
        if (!c) throw new Error("No GitHub connection configured.");
        if (!c.enabled) throw new Error("GitHub connection is disabled.");
        await api.githubTestConnection(c.id);
      } else {
        const provider = key;
        const ds = await api.notificationDestinations();
        const d = (ds || []).find((x: any) => x.provider === provider && x.enabled) || (ds || []).find((x: any) => x.provider === provider);
        if (!d) throw new Error(`${title} is not configured.`);
        if (!d.enabled) throw new Error(`${title} destination is disabled.`);
        await api.notificationTestDestination(d.id, {
          title: "Integration health check",
          message: `${title} test from Settings > Integrations`,
          priority: 0,
        });
      }
      toast.success(`${title} test passed`);
      await refreshStatus();
    } catch (e: any) {
      toast.error(String(e?.message || e || "Integration test failed"));
      await refreshStatus();
    } finally {
      setTestingKey(null);
    }
  };

  const planned = [
    {
      title: "NotebookLM Research Pack",
      eta: "Next",
      desc: "One-click board context export for research synthesis and planning workflows."
    },
    {
      title: "Slack + Teams Notifications",
      eta: "Planned",
      desc: "Action-required alerts, reminders, and escalation paths to chat platforms."
    },
    {
      title: "CalDAV + Calendar Connectors",
      eta: "Planned",
      desc: "Calendar sync expansion beyond ICS download/email for two-way scheduling context."
    }
  ];

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="text-lg font-semibold">Integrations</div>
      <div className="mt-2 text-sm text-muted">
        Manage external systems and track upcoming connector roadmap. Status dots show live configured/test state.
      </div>

      <div className="mt-6 text-sm font-semibold">Live now</div>
      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        {live.map((it) => (
          <Link key={it.title} href={it.href} className="rounded-3xl border border-white/10 bg-white/5 hover:bg-white/7 transition p-4 block">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">{it.title}</div>
              <div className="flex items-center gap-2">
                {(() => {
                  const s = (statusItems || []).find((x) => x.key === it.key);
                  const state = s?.state || "unknown";
                  const dot =
                    state === "ok"
                      ? "bg-emerald-400"
                      : state === "error"
                        ? "bg-rose-400"
                        : state === "not_configured"
                          ? "bg-slate-500"
                          : "bg-amber-400";
                  const pill =
                    state === "ok"
                      ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                      : state === "error"
                        ? "border-rose-400/30 bg-rose-400/10 text-rose-200"
                        : state === "not_configured"
                          ? "border-white/15 bg-white/5 text-muted"
                          : "border-amber-400/30 bg-amber-400/10 text-amber-200";
                  const label =
                    state === "ok"
                      ? "Connected"
                      : state === "error"
                        ? "Error"
                        : state === "not_configured"
                          ? "Not configured"
                          : "Needs test";
                  return (
                    <span className={`inline-flex items-center gap-1.5 text-[11px] rounded-full border px-2 py-0.5 ${pill}`} title={s?.message || "No status yet"}>
                      <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />
                      {label}
                    </span>
                  );
                })()}
                {supportsQuickTest(it.key) && isAdmin ? (
                  <button
                    className="text-[11px] rounded-full border border-white/15 bg-white/5 px-2 py-0.5 hover:bg-white/10 transition"
                    disabled={testingKey !== null}
                    onClick={async (e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      await runQuickTest(it.key, it.title);
                    }}
                  >
                    {testingKey === it.key ? "Testing…" : "Test"}
                  </button>
                ) : null}
              </div>
            </div>
            <div className="mt-1 text-xs text-muted">{it.desc}</div>
            {(() => {
              const s = (statusItems || []).find((x) => x.key === it.key);
              if (!s) return <div className="mt-2 text-[11px] text-muted">{loading ? "Loading status…" : "No status yet"}</div>;
              return <div className="mt-2 text-[11px] text-muted">{s.message || "No details."}</div>;
            })()}
          </Link>
        ))}
      </div>

      <div className="mt-6 text-sm font-semibold">Planned connectors</div>
      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        {planned.map((it) => (
          <div key={it.title} className="rounded-3xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">{it.title}</div>
              <span className="text-[11px] rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-muted">{it.eta}</span>
            </div>
            <div className="mt-1 text-xs text-muted">{it.desc}</div>
          </div>
        ))}
      </div>

      {!isAdmin ? <div className="mt-6 text-sm text-muted">Some integration settings require Admin + MFA session.</div> : null}
    </div>
  );
}
