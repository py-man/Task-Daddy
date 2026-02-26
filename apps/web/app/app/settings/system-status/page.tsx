"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { FEATURES } from "@/lib/features";
import { api } from "@/lib/api";

type StatusTone = "green" | "yellow" | "red";
type StatusSection = {
  key: string;
  label: string;
  state: StatusTone;
  details: string[];
  updatedAt: string;
};

const stateMap: Record<StatusTone, { label: string; tone: "muted" | "accent" | "danger" | "warn" | "ok" }> = {
  green: { label: "Healthy", tone: "ok" },
  yellow: { label: "Degraded", tone: "warn" },
  red: { label: "Attention", tone: "danger" }
};

export default function SystemStatusPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string>("");
  const [versionLabel, setVersionLabel] = useState<string>("");
  const [sections, setSections] = useState<StatusSection[]>([]);

  const load = useCallback(async () => {
    try {
      const result = await api.systemStatus();
      setError(null);
      setGeneratedAt(result.generatedAt);
      setVersionLabel(`${result.version} (${result.buildSha})`);
      setSections(result.sections || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load system status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  const downloadSnapshot = useCallback(() => {
    const blob = new Blob(
      [
        JSON.stringify(
          {
            generatedAt,
            version: versionLabel,
            sections
          },
          null,
          2
        )
      ],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `task_daddy_system_status_${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [generatedAt, versionLabel, sections]);

  if (!FEATURES.systemStatus) {
    return (
      <div className="glass rounded-3xl shadow-neon border border-white/10 p-6">
        <div className="text-lg font-semibold">System Status</div>
        <div className="mt-2 text-sm text-muted">
          The System Status dashboard is disabled. Enable `NEXT_PUBLIC_FEATURE_SYSTEM_STATUS=1` to view it.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="text-2xl font-semibold">System Status</div>
        <div className="text-sm text-muted">Single pane to monitor API, Postgres, Cache, Queue, notifications, and jobs.</div>
        <div className="text-xs text-muted">
          {loading ? "Loading…" : error ? `Last error: ${error}` : `Snapshot: ${new Date(generatedAt).toLocaleString()} • ${versionLabel}`}
        </div>
        <div>
          <button
            type="button"
            onClick={downloadSnapshot}
            className="h-8 rounded-xl border border-white/15 bg-white/5 px-3 text-xs text-text hover:bg-white/10"
          >
            Export snapshot JSON
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {sections.map((item) => (
          <div
            key={item.key}
            className="glass rounded-3xl border border-white/10 shadow-neon p-5 flex flex-col gap-2 min-h-[160px]"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">{item.label}</div>
              <Badge variant={stateMap[item.state].tone}>{stateMap[item.state].label}</Badge>
            </div>
            <ul className="text-xs text-muted space-y-1 list-disc pl-4">
              {item.details.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <div className="text-[11px] text-muted">Updated: {new Date(item.updatedAt).toLocaleTimeString()}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Link
          href="/app/settings/diagnostics"
          className="glass rounded-3xl border border-white/10 shadow-neon p-4 hover:border-accent/30 flex flex-col gap-1"
        >
          <div className="text-sm font-semibold">View raw metrics</div>
          <div className="text-xs text-muted">pg_stat, cache stats, and queue diagnostics.</div>
        </Link>
        <Link
          href="/app/settings/diagnostics"
          className="glass rounded-3xl border border-white/10 shadow-neon p-4 hover:border-accent/30 flex flex-col gap-1"
        >
          <div className="text-sm font-semibold">Audit logs</div>
          <div className="text-xs text-muted">Notification delivery, AI prompts, and system events.</div>
        </Link>
        <Link
          href="/app/settings/backups"
          className="glass rounded-3xl border border-white/10 shadow-neon p-4 hover:border-accent/30 flex flex-col gap-1"
        >
          <div className="text-sm font-semibold">Export status</div>
          <div className="text-xs text-muted">Download nightly artifacts and DB snapshots.</div>
        </Link>
      </div>
    </div>
  );
}
