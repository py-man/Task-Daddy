"use client";

import { useEffect, useMemo, useState } from "react";
import { useBoard } from "@/components/board-context";
import { useSession } from "@/components/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TaskDrawer } from "@/components/task-drawer";
import { EmptyState } from "@/components/empty-state";
import { cn } from "@/lib/cn";
import type { Task } from "@neonlanes/shared/schema";

function dueMeta(dueDate?: string | null) {
  if (!dueDate) return { has: false as const, overdue: false, dueSoon: false, label: "" };
  const d = new Date(dueDate);
  if (Number.isNaN(d.getTime())) return { has: false as const, overdue: false, dueSoon: false, label: "" };
  const deltaMs = d.getTime() - Date.now();
  const overdue = deltaMs < 0;
  const dueSoon = !overdue && deltaMs <= 48 * 3600 * 1000;
  if (overdue) {
    const daysLate = Math.max(1, Math.ceil(Math.abs(deltaMs) / (24 * 3600 * 1000)));
    return { has: true as const, overdue: true, dueSoon: false, label: `OVERDUE • ${daysLate}d` };
  }
  if (dueSoon) {
    const hoursLeft = Math.max(1, Math.ceil(deltaMs / (3600 * 1000)));
    return { has: true as const, overdue: false, dueSoon: true, label: `DUE SOON • ${hoursLeft}h` };
  }
  return { has: true as const, overdue: false, dueSoon: false, label: "DUE" };
}

export default function MyTasksPage() {
  const { board, lanes, tasks, loading, priorities } = useBoard();
  const { user } = useSession();
  const [drawerTaskId, setDrawerTaskId] = useState<string | null>(null);
  const [preset, setPreset] = useState<"mine" | "overdue" | "dueSoon" | "blocked" | "high">("mine");

  useEffect(() => {
    setDrawerTaskId(null);
  }, [board?.id]);

  const laneTypeById = useMemo(() => new Map(lanes.map((l) => [l.id, l.type])), [lanes]);
  const enabledPriorities = useMemo(
    () => (priorities || []).filter((p) => p.enabled !== false).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );
  const priorityRank = useMemo(() => new Map(enabledPriorities.map((p) => [p.key, p.rank])), [enabledPriorities]);
  const priorityTone = (key: string) => {
    const r = priorityRank.get(key) ?? 99;
    if (r <= 0) return "danger";
    if (r === 1) return "warn";
    if (r === 2) return "accent";
    return "muted";
  };

  const mine = useMemo(() => {
    const base = tasks.filter((t) => t.ownerId && t.ownerId === user?.id);
    if (preset === "blocked") {
      return base.filter((t) => (t.blocked || laneTypeById.get(t.laneId) === "blocked") && laneTypeById.get(t.laneId) !== "done");
    }
    if (preset === "high") return base.filter((t) => (priorityRank.get(t.priority) ?? 99) <= 1 && laneTypeById.get(t.laneId) !== "done");
    if (preset === "overdue") {
      return base.filter((t) => {
        if (!t.dueDate) return false;
        if (laneTypeById.get(t.laneId) === "done") return false;
        const d = new Date(t.dueDate);
        if (Number.isNaN(d.getTime())) return false;
        return d.getTime() < Date.now();
      });
    }
    if (preset === "dueSoon") {
      return base.filter((t) => {
        if (!t.dueDate) return false;
        if (laneTypeById.get(t.laneId) === "done") return false;
        const d = new Date(t.dueDate);
        if (Number.isNaN(d.getTime())) return false;
        const delta = d.getTime() - Date.now();
        return delta >= 0 && delta <= 48 * 3600 * 1000;
      });
    }
    return base;
  }, [tasks, user?.id, preset, laneTypeById]);

  const ordered = useMemo(() => {
    const out = [...mine];
    out.sort((a, b) => {
      const ap = priorityRank.get(a.priority) ?? 99;
      const bp = priorityRank.get(b.priority) ?? 99;
      if (ap !== bp) return ap - bp;
      const ad = a.dueDate ? new Date(a.dueDate).getTime() : Number.POSITIVE_INFINITY;
      const bd = b.dueDate ? new Date(b.dueDate).getTime() : Number.POSITIVE_INFINITY;
      return ad - bd;
    });
    return out;
  }, [mine, priorityRank]);

  if (loading) return <div className="h-full p-4 text-sm text-muted">Loading…</div>;

  if (!board) {
    return (
      <div className="h-full p-4">
        <EmptyState title="Select a board" body="Pick a board from the header." />
      </div>
    );
  }

  return (
    <div className="h-full p-4 flex flex-col min-h-0">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={preset === "mine" ? "primary" : "ghost"} onClick={() => setPreset("mine")}>
          Mine
        </Button>
        <Button size="sm" variant={preset === "overdue" ? "danger" : "ghost"} onClick={() => setPreset("overdue")}>
          Overdue
        </Button>
        <Button size="sm" variant={preset === "dueSoon" ? "warn" : "ghost"} onClick={() => setPreset("dueSoon")}>
          Due soon
        </Button>
        <Button size="sm" variant={preset === "blocked" ? "danger" : "ghost"} onClick={() => setPreset("blocked")}>
          Blocked
        </Button>
        <Button size="sm" variant={preset === "high" ? "primary" : "ghost"} onClick={() => setPreset("high")}>
          High
        </Button>
      </div>

      <div className="mt-3 flex-1 min-h-0 overflow-y-auto scrollbar">
        {ordered.length === 0 ? (
          <div className="text-sm text-muted mt-6">No tasks.</div>
        ) : (
          <div className="space-y-2 pb-6">
            {ordered.map((t: Task) => {
              const dm = dueMeta(t.dueDate);
              return (
                <button
                  key={t.id}
                  className={cn(
                    "w-full text-left rounded-2xl border bg-white/5 p-3 transition",
                    dm.overdue ? "border-danger/40" : dm.dueSoon ? "border-warn/30" : "border-white/10 hover:bg-white/10"
                  )}
                  onClick={() => setDrawerTaskId(t.id)}
                >
                    <div className="flex items-start justify-between gap-2">
                      <div className="text-sm font-medium leading-snug">{t.title}</div>
                    <Badge variant={priorityTone(t.priority)}>{t.priority}</Badge>
                    </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {dm.has ? <Badge variant={dm.overdue ? "danger" : dm.dueSoon ? "warn" : "muted"}>{dm.label}</Badge> : null}
                    {t.blocked ? <Badge variant="danger">Blocked</Badge> : null}
                    {t.jiraKey ? <Badge variant="accent">{t.jiraKey}</Badge> : null}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <TaskDrawer taskId={drawerTaskId} onClose={() => setDrawerTaskId(null)} />
    </div>
  );
}
