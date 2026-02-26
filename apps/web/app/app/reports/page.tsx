"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Gauge,
  ListChecks,
  ShieldAlert,
  Users,
  Workflow
} from "lucide-react";
import { useMemo } from "react";
import { EmptyState } from "@/components/empty-state";
import { useBoard } from "@/components/board-context";
import { cn } from "@/lib/cn";

function MiniBarChart({
  rows
}: {
  rows: Array<{ key: string; label: string; value: number; tone?: "accent" | "danger" | "warn" | "ok" }>;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  const toneTo = (tone?: string) => {
    if (tone === "danger") return "bg-danger/25";
    if (tone === "warn") return "bg-warn/25";
    if (tone === "ok") return "bg-ok/25";
    return "bg-accent/25";
  };
  const fillTo = (tone?: string) => {
    if (tone === "danger") return "bg-danger";
    if (tone === "warn") return "bg-warn";
    if (tone === "ok") return "bg-ok";
    return "bg-accent";
  };

  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center gap-3">
          <div className="w-28 text-xs text-muted truncate">{r.label}</div>
          <div className={cn("flex-1 h-2 rounded-full overflow-hidden", toneTo(r.tone))}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${Math.round((r.value / max) * 100)}%` }}
              transition={{ duration: 0.25 }}
              className={cn("h-full rounded-full", fillTo(r.tone))}
            />
          </div>
          <div className="w-12 text-right text-xs text-muted tabular-nums">{r.value}</div>
        </div>
      ))}
    </div>
  );
}

function parseTimeMs(s?: string | null) {
  if (!s) return null;
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return null;
  return d.getTime();
}

function startOfWeekMs(ts: number) {
  const d = new Date(ts);
  const day = d.getUTCDay();
  const delta = day === 0 ? 6 : day - 1;
  d.setUTCDate(d.getUTCDate() - delta);
  d.setUTCHours(0, 0, 0, 0);
  return d.getTime();
}

export default function ReportsPage() {
  const { board, lanes, tasks, users, loading } = useBoard();

  const metrics = useMemo(() => {
    const laneTypeById = new Map(lanes.map((l) => [l.id, l.type]));
    const laneNameById = new Map(lanes.map((l) => [l.id, l.name]));
    const userNameById = new Map(users.map((u) => [u.id, u.name]));

    const now = Date.now();
    const dayMs = 24 * 3600 * 1000;
    const weekAgo = now - 7 * dayMs;

    let overdue = 0;
    let dueSoon = 0;
    let blocked = 0;
    let inProgress = 0;
    let doneWeek = 0;
    let unassigned = 0;
    let stale7d = 0;
    let wipBreaches = 0;

    const blockedReasonCounts = new Map<string, number>();
    const typeCounts = new Map<string, number>();
    const priorityCounts = new Map<string, number>();
    const laneCounts = new Map<string, number>();
    const ageBuckets = { "0-2d": 0, "3-7d": 0, "8-14d": 0, "15d+": 0 };
    const dueBuckets = { overdue: 0, "0-2d": 0, "3-7d": 0, "8d+": 0, noDueDate: 0 };
    const ownerTaskCounts = new Map<string, number>();
    const ownerMinutesCounts = new Map<string, number>();
    const doneTrend = new Map<number, number>();

    for (const lane of lanes) {
      if (typeof lane.wipLimit === "number" && lane.wipLimit >= 0) {
        const laneTotal = tasks.filter((t) => t.laneId === lane.id && (laneTypeById.get(t.laneId) || "active") !== "done").length;
        if (laneTotal > lane.wipLimit) wipBreaches++;
      }
    }

    for (const t of tasks) {
      const laneType = laneTypeById.get(t.laneId) || "active";
      const dueMs = parseTimeMs(t.dueDate);
      const updatedMs = parseTimeMs(t.updatedAt);
      const isBlocked = Boolean(t.blocked) || laneType === "blocked";
      const isDone = laneType === "done";

      typeCounts.set(t.type, (typeCounts.get(t.type) || 0) + 1);
      priorityCounts.set(t.priority, (priorityCounts.get(t.priority) || 0) + 1);
      laneCounts.set(t.laneId, (laneCounts.get(t.laneId) || 0) + 1);

      if (!t.ownerId) unassigned++;
      if (t.ownerId) {
        ownerTaskCounts.set(t.ownerId, (ownerTaskCounts.get(t.ownerId) || 0) + 1);
        ownerMinutesCounts.set(t.ownerId, (ownerMinutesCounts.get(t.ownerId) || 0) + Number(t.estimateMinutes || 0));
      }

      if (!isDone) {
        if (isBlocked) {
          blocked++;
          const reason = String(t.blockedReason || "No reason").trim() || "No reason";
          blockedReasonCounts.set(reason, (blockedReasonCounts.get(reason) || 0) + 1);
        }
        if (laneType === "active") inProgress++;
        if (updatedMs !== null) {
          const ageDays = Math.floor((now - updatedMs) / dayMs);
          if (ageDays >= 7) stale7d++;
          if (ageDays <= 2) ageBuckets["0-2d"]++;
          else if (ageDays <= 7) ageBuckets["3-7d"]++;
          else if (ageDays <= 14) ageBuckets["8-14d"]++;
          else ageBuckets["15d+"]++;
        }

        if (dueMs === null) {
          dueBuckets.noDueDate++;
        } else {
          const delta = dueMs - now;
          if (delta < 0) {
            overdue++;
            dueBuckets.overdue++;
          } else if (delta <= 2 * dayMs) {
            dueSoon++;
            dueBuckets["0-2d"]++;
          } else if (delta <= 7 * dayMs) {
            dueBuckets["3-7d"]++;
          } else {
            dueBuckets["8d+"]++;
          }
        }
      } else if (updatedMs !== null) {
        if (updatedMs >= weekAgo) doneWeek++;
        const wk = startOfWeekMs(updatedMs);
        doneTrend.set(wk, (doneTrend.get(wk) || 0) + 1);
      }
    }

    const byLane = lanes
      .slice()
      .sort((a, b) => a.position - b.position)
      .map((l) => ({
        key: l.id,
        label: l.name,
        value: laneCounts.get(l.id) || 0,
        tone: l.type === "done" ? ("ok" as const) : l.type === "blocked" ? ("danger" as const) : ("accent" as const)
      }));

    const byUserTasks = users
      .map((u) => ({
        key: u.id,
        label: u.name.split(" ")[0] || u.name,
        value: ownerTaskCounts.get(u.id) || 0,
        tone: "accent" as const
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 12);

    const byUserMinutes = users
      .map((u) => ({
        key: u.id,
        label: u.name.split(" ")[0] || u.name,
        value: ownerMinutesCounts.get(u.id) || 0,
        tone: "warn" as const
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 12);

    const topBlockedReasons = Array.from(blockedReasonCounts.entries())
      .map(([label, value]) => ({ key: label, label, value, tone: "danger" as const }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);

    const byType = Array.from(typeCounts.entries())
      .map(([label, value]) => ({ key: label, label, value, tone: "accent" as const }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);

    const byPriority = Array.from(priorityCounts.entries())
      .map(([label, value]) => ({ key: label, label, value, tone: label === "P0" || label === "P1" ? ("warn" as const) : ("accent" as const) }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);

    const doneTrendRows = Array.from(doneTrend.entries())
      .sort((a, b) => a[0] - b[0])
      .slice(-6)
      .map(([wk, value]) => ({
        key: String(wk),
        label: new Date(wk).toISOString().slice(5, 10),
        value,
        tone: "ok" as const
      }));

    const ageRows = Object.entries(ageBuckets).map(([label, value]) => ({ key: label, label, value, tone: "accent" as const }));
    const dueRows = Object.entries(dueBuckets).map(([label, value]) => ({ key: label, label, value, tone: label === "overdue" ? ("danger" as const) : ("accent" as const) }));

    const riskTasks = tasks
      .map((t) => {
        const laneType = laneTypeById.get(t.laneId) || "active";
        if (laneType === "done") return null;
        const dueMs = parseTimeMs(t.dueDate);
        const updatedMs = parseTimeMs(t.updatedAt);
        let score = 0;
        if (Boolean(t.blocked) || laneType === "blocked") score += 5;
        if (!t.ownerId) score += 2;
        if (t.priority === "P0") score += 4;
        if (t.priority === "P1") score += 2;
        if (dueMs !== null && dueMs < now) score += 4;
        if (updatedMs !== null && now - updatedMs > 7 * dayMs) score += 2;
        return {
          id: t.id,
          title: t.title,
          laneName: laneNameById.get(t.laneId) || "Lane",
          owner: t.ownerId ? userNameById.get(t.ownerId) || "Unknown" : "Unassigned",
          priority: t.priority,
          score
        };
      })
      .filter((x): x is { id: string; title: string; laneName: string; owner: string; priority: string; score: number } => Boolean(x))
      .sort((a, b) => b.score - a.score)
      .slice(0, 8);

    const flowEfficiency = doneWeek + inProgress > 0 ? Math.round((doneWeek / (doneWeek + inProgress)) * 100) : 0;

    return {
      overdue,
      dueSoon,
      blocked,
      inProgress,
      doneWeek,
      unassigned,
      stale7d,
      wipBreaches,
      flowEfficiency,
      byLane,
      byUserTasks,
      byUserMinutes,
      topBlockedReasons,
      byType,
      byPriority,
      doneTrendRows,
      ageRows,
      dueRows,
      riskTasks
    };
  }, [lanes, tasks, users]);

  if (loading) return <div className="h-full p-6 text-muted">Loading…</div>;
  if (!board) {
    return (
      <div className="h-full p-4 md:p-6">
        <EmptyState title="Reports need a board" body="Select a board first, then come back here for health + workload insights." />
      </div>
    );
  }

  const chips = [
    { key: "overdue", label: "Overdue", value: metrics.overdue, icon: <AlertTriangle size={14} />, tone: "danger" },
    { key: "dueSoon", label: "Due soon", value: metrics.dueSoon, icon: <Clock size={14} />, tone: "warn" },
    { key: "blocked", label: "Blocked", value: metrics.blocked, icon: <ShieldAlert size={14} />, tone: "danger" },
    { key: "inProgress", label: "In progress", value: metrics.inProgress, icon: <Workflow size={14} />, tone: "accent" },
    { key: "doneWeek", label: "Done (7d)", value: metrics.doneWeek, icon: <CheckCircle2 size={14} />, tone: "ok" },
    { key: "unassigned", label: "Unassigned", value: metrics.unassigned, icon: <Users size={14} />, tone: "warn" },
    { key: "stale7d", label: "Stale (7d+)", value: metrics.stale7d, icon: <Clock size={14} />, tone: "warn" },
    { key: "wipBreaches", label: "WIP breaches", value: metrics.wipBreaches, icon: <Gauge size={14} />, tone: "danger" },
    { key: "flowEfficiency", label: "Flow efficiency %", value: metrics.flowEfficiency, icon: <ListChecks size={14} />, tone: "accent" }
  ] as const;

  const toneClass = (tone: string) => {
    if (tone === "danger") return "border-danger/25 bg-danger/5";
    if (tone === "warn") return "border-warn/25 bg-warn/5";
    if (tone === "ok") return "border-ok/25 bg-ok/5";
    return "border-accent/25 bg-accent/5";
  };

  return (
    <div data-testid="reports-page" className="h-full overflow-auto px-4 pb-24 md:pb-6 scrollbar">
      <div className="mt-4 glass rounded-3xl border border-white/10 shadow-neon p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-lg font-semibold flex items-center gap-2">
              <BarChart3 size={16} className="text-accent" /> Reports
            </div>
            <div className="text-sm text-muted">Expanded board analytics for “{board.name}”.</div>
          </div>
          <div className="h-10 w-10 rounded-2xl border border-white/10 bg-white/5 grid place-items-center text-muted">
            <BarChart3 size={18} />
          </div>
        </div>

        <div className="mt-4 grid gap-2 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {chips.map((it) => (
            <motion.div
              key={it.key}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}
              className={cn("rounded-2xl border px-3 py-2 flex items-center gap-2", toneClass(it.tone))}
            >
              <div className="h-9 w-9 rounded-2xl border border-white/10 bg-white/5 grid place-items-center text-muted">{it.icon}</div>
              <div className="min-w-0">
                <div className="text-xs text-muted">{it.label}</div>
                <div className="text-lg font-semibold leading-tight tabular-nums">{it.value}</div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold flex items-center gap-2"><BarChart3 size={14} className="text-accent" /> Tasks by lane</div>
          <div className="mt-4">{metrics.byLane.length ? <MiniBarChart rows={metrics.byLane} /> : <EmptyState title="No lanes yet" body="Create lanes to unlock lane flow reporting." className="p-4" />}</div>
        </div>

        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold flex items-center gap-2"><Users size={14} className="text-accent" /> Workload by tasks</div>
          <div className="mt-4">{metrics.byUserTasks.length ? <MiniBarChart rows={metrics.byUserTasks} /> : <EmptyState title="No members yet" body="Add board members to see workload distribution." className="p-4" />}</div>
        </div>

        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold flex items-center gap-2"><Clock size={14} className="text-warn" /> Workload by estimate (minutes)</div>
          <div className="mt-4">{metrics.byUserMinutes.length ? <MiniBarChart rows={metrics.byUserMinutes} /> : <EmptyState title="No estimates yet" body="Set estimate minutes on tasks to unlock capacity reports." className="p-4" />}</div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold">Open task age buckets</div>
          <div className="mt-4"><MiniBarChart rows={metrics.ageRows} /></div>
        </div>
        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold">Due-date buckets</div>
          <div className="mt-4"><MiniBarChart rows={metrics.dueRows} /></div>
        </div>
        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold">Throughput trend (done/week)</div>
          <div className="mt-4">{metrics.doneTrendRows.length ? <MiniBarChart rows={metrics.doneTrendRows} /> : <EmptyState title="No completed work" body="Move tasks to Done to build throughput history." className="p-4" />}</div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold">Task types</div>
          <div className="mt-4">{metrics.byType.length ? <MiniBarChart rows={metrics.byType} /> : <EmptyState title="No typed tasks" body="Set task types to unlock category reporting." className="p-4" />}</div>
        </div>
        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold">Priority distribution</div>
          <div className="mt-4">{metrics.byPriority.length ? <MiniBarChart rows={metrics.byPriority} /> : <EmptyState title="No priorities" body="Set priorities to unlock urgency reporting." className="p-4" />}</div>
        </div>
        <div className="glass rounded-3xl border border-white/10 shadow-neon p-5">
          <div className="text-sm font-semibold">Blocked reason hotspots</div>
          <div className="mt-4">{metrics.topBlockedReasons.length ? <MiniBarChart rows={metrics.topBlockedReasons} /> : <EmptyState title="No blocked tasks" body="Blocked tasks with reasons appear here." className="p-4" />}</div>
        </div>
      </div>

      <div className="mt-4 glass rounded-3xl border border-white/10 shadow-neon p-5">
        <div className="text-sm font-semibold">Top risk tasks (priority queue)</div>
        <div className="mt-3 overflow-x-auto">
          {metrics.riskTasks.length ? (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-white/10">
                  <th className="py-2 pr-3">Task</th>
                  <th className="py-2 pr-3">Lane</th>
                  <th className="py-2 pr-3">Owner</th>
                  <th className="py-2 pr-3">Priority</th>
                  <th className="py-2">Risk</th>
                </tr>
              </thead>
              <tbody>
                {metrics.riskTasks.map((t) => (
                  <tr key={t.id} className="border-b border-white/5">
                    <td className="py-2 pr-3 max-w-[360px] truncate">{t.title}</td>
                    <td className="py-2 pr-3 text-muted">{t.laneName}</td>
                    <td className="py-2 pr-3 text-muted">{t.owner}</td>
                    <td className="py-2 pr-3">{t.priority}</td>
                    <td className="py-2 tabular-nums font-semibold">{t.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title="No open tasks" body="Risk queue appears when a board has active tasks." className="p-4" />
          )}
        </div>
      </div>
    </div>
  );
}
