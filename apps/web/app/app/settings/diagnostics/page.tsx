"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useBoard } from "@/components/board-context";

export default function SettingsDiagnosticsPage() {
  const { board } = useBoard();
  const [health, setHealth] = useState<any | null>(null);
  const [version, setVersion] = useState<any | null>(null);
  const [syncRuns, setSyncRuns] = useState<any[] | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const h = await fetch("/api/health", { credentials: "include" }).then((r) => r.json());
        setHealth(h);
      } catch (e: any) {
        toast.error(String(e?.message || e));
      }
      try {
        const v = await fetch("/api/version", { credentials: "include" }).then((r) => r.json());
        setVersion(v);
      } catch (e: any) {
        toast.error(String(e?.message || e));
      }
    })();
  }, []);

  useEffect(() => {
    if (!board?.id) return;
    (async () => {
      try {
        const r = await fetch(`/api/jira/sync-runs?${new URLSearchParams({ boardId: board.id })}`, { credentials: "include" });
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        const runs = await r.json();
        setSyncRuns(runs);
      } catch {
        setSyncRuns([]);
      }
    })();
  }, [board?.id]);

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="text-lg font-semibold">Diagnostics</div>
      <div className="mt-2 text-sm text-muted">Service health, versions, and sync status.</div>

      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">API Health</div>
          <pre className="mt-2 text-xs text-muted whitespace-pre-wrap">{health ? JSON.stringify(health, null, 2) : "Loading…"}</pre>
        </div>
        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">Version</div>
          <pre className="mt-2 text-xs text-muted whitespace-pre-wrap">{version ? JSON.stringify(version, null, 2) : "Loading…"}</pre>
        </div>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">Jira sync</div>
        <div className="mt-1 text-xs text-muted">Last sync runs for the current board.</div>
        <pre className="mt-3 text-xs text-muted whitespace-pre-wrap">{syncRuns === null ? "Loading…" : JSON.stringify(syncRuns.slice(0, 3), null, 2)}</pre>
      </div>
    </div>
  );
}

