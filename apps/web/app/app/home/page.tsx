"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { BarChart3, CalendarDays, CheckCircle2, Clock3, LayoutList, PieChart, Rows3, TriangleAlert } from "lucide-react";
import type { Task } from "@neonlanes/shared/schema";
import { useBoard } from "@/components/board-context";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { getRecentTaskIds } from "@/lib/recent-tasks";

function parseMs(v?: string | null) {
  if (!v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  return d.getTime();
}

function fmt(v?: string | null) {
  const ms = parseMs(v);
  if (ms === null) return "No due";
  return new Date(ms).toLocaleDateString();
}

function dayStart(ms: number) {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function weekStart(ms: number) {
  const d = new Date(ms);
  const day = d.getDay();
  const delta = day === 0 ? 6 : day - 1;
  d.setDate(d.getDate() - delta);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function monthStart(ms: number) {
  const d = new Date(ms);
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function MiniBars({ rows }: { rows: Array<{ key: string; label: string; value: number }> }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center gap-2">
          <div className="w-24 text-xs text-muted truncate">{r.label}</div>
          <div className="h-2 flex-1 rounded-full bg-white/10 overflow-hidden">
            <div className="h-2 rounded-full bg-accent" style={{ width: `${Math.round((r.value / max) * 100)}%` }} />
          </div>
          <div className="text-xs text-muted w-8 text-right">{r.value}</div>
        </div>
      ))}
    </div>
  );
}

function TaskDetail({ task, laneName, ownerName, onOpen }: { task: Task; laneName: string; ownerName: string; onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="nl-surface-item w-full text-left rounded-2xl p-3 hover:bg-white/10 transition">
      <div className="font-medium">{task.title}</div>
      <div className="mt-1 text-xs text-muted line-clamp-2">{task.description || "No description"}</div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <Badge variant="muted">{laneName}</Badge>
        <Badge variant="muted">{task.priority}</Badge>
        <span className="text-muted">{ownerName}</span>
        <span className="text-muted">{fmt(task.dueDate)}</span>
      </div>
    </button>
  );
}

function TaskListRow({ task, laneName, ownerName, onOpen }: { task: Task; laneName: string; ownerName: string; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="nl-surface-item w-full grid grid-cols-[minmax(0,1fr)_72px_96px] gap-2 text-left rounded-xl p-2.5 hover:bg-white/10 transition"
    >
      <div className="min-w-0">
        <div className="text-sm font-medium truncate">{task.title}</div>
        <div className="text-xs text-muted truncate">{laneName} • {ownerName}</div>
      </div>
      <div className="text-xs text-muted self-center">{task.priority}</div>
      <div className="text-xs text-muted self-center">{fmt(task.dueDate)}</div>
    </button>
  );
}

export default function HomePage() {
  const router = useRouter();
  const { user } = useSession();
  const { board, lanes, users, tasks, loading } = useBoard();
  const [view, setView] = useState<"detail" | "list">("detail");

  const laneById = useMemo(() => new Map(lanes.map((l) => [l.id, l])), [lanes]);
  const userById = useMemo(() => new Map(users.map((u) => [u.id, u.name])), [users]);
  const now = Date.now();
  const today = dayStart(now);
  const yesterday = today - 24 * 3600 * 1000;
  const thisWeek = weekStart(now);
  const lastWeek = thisWeek - 7 * 24 * 3600 * 1000;
  const thisMonth = monthStart(now);

  const openTask = (id: string) => router.push(`/app/board?task=${encodeURIComponent(id)}`);

  const sections = useMemo(() => {
    const dueInRange = (start: number, endExclusive?: number) =>
      tasks.filter((t) => {
        const ms = parseMs(t.dueDate);
        if (ms === null) return false;
        return ms >= start && (endExclusive ? ms < endExclusive : true);
      });

    const recentIds = getRecentTaskIds();
    const taskById = new Map(tasks.map((t) => [t.id, t]));
    const recent = recentIds.map((id) => taskById.get(id)).filter(Boolean) as Task[];

    return [
      { key: "recent", title: "Recently viewed", items: recent.slice(0, 12) },
      { key: "today", title: "Today tasks", items: dueInRange(today, today + 24 * 3600 * 1000) },
      { key: "yesterday", title: "Yesterday tasks", items: dueInRange(yesterday, today) },
      { key: "this-week", title: "This week tasks", items: dueInRange(thisWeek, thisWeek + 7 * 24 * 3600 * 1000) },
      { key: "last-week", title: "Last week tasks", items: dueInRange(lastWeek, thisWeek) },
      { key: "this-month", title: "This month tasks", items: dueInRange(thisMonth) }
    ];
  }, [tasks, today, yesterday, thisWeek, lastWeek, thisMonth]);

  const stats = useMemo(() => {
    const laneTypeById = new Map(lanes.map((l) => [l.id, l.type]));
    const total = tasks.length;
    let done = 0;
    let blocked = 0;
    let overdue = 0;
    for (const t of tasks) {
      const type = laneTypeById.get(t.laneId) || "active";
      if (type === "done") done++;
      if (type === "blocked" || t.blocked) blocked++;
      const due = parseMs(t.dueDate);
      if (due !== null && due < Date.now() && type !== "done") overdue++;
    }
    const open = Math.max(0, total - done);
    return { total, open, done, blocked, overdue };
  }, [tasks, lanes]);

  const pieStyle = useMemo(() => {
    const total = Math.max(1, stats.total);
    const doneP = (stats.done / total) * 100;
    const blockedP = (stats.blocked / total) * 100;
    const overdueP = (stats.overdue / total) * 100;
    const openP = Math.max(0, 100 - doneP - blockedP - overdueP);
    return {
      background: `conic-gradient(
        rgba(33, 208, 122, 0.92) 0 ${doneP}%,
        rgba(255, 95, 95, 0.92) ${doneP}% ${doneP + blockedP}%,
        rgba(255, 184, 90, 0.92) ${doneP + blockedP}% ${doneP + blockedP + overdueP}%,
        rgba(87, 179, 255, 0.95) ${doneP + blockedP + overdueP}% ${doneP + blockedP + overdueP + openP}%
      )`
    };
  }, [stats]);

  const laneRows = useMemo(
    () =>
      lanes
        .slice()
        .sort((a, b) => a.position - b.position)
        .map((lane) => ({ key: lane.id, label: lane.name, value: tasks.filter((t) => t.laneId === lane.id).length })),
    [lanes, tasks]
  );

  const priorityRows = useMemo(() => {
    const counts = new Map<string, number>();
    for (const t of tasks) counts.set(t.priority, (counts.get(t.priority) || 0) + 1);
    return Array.from(counts.entries())
      .map(([label, value]) => ({ key: label, label, value }))
      .sort((a, b) => b.value - a.value);
  }, [tasks]);

  if (loading) return <div className="h-full p-6 text-muted">Loading home…</div>;

  return (
    <div className="h-full overflow-y-auto p-3 md:p-5 pb-24 md:pb-6">
      <div className="nl-surface-panel rounded-2xl p-3 md:p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-lg font-semibold">{board?.name || "Board"} Dashboard</div>
            <div className="text-sm text-muted">Welcome back{user?.name ? `, ${user.name.split(" ")[0]}` : ""}. Snapshot of work and recent activity.</div>
          </div>
          <div className="nl-surface-item inline-flex rounded-xl p-1">
            <button className={cn("h-8 px-3 rounded-lg text-sm", view === "detail" ? "bg-accent/15 text-text" : "text-muted")} onClick={() => setView("detail")}>
              <Rows3 size={14} className="inline mr-1" /> Detail
            </button>
            <button className={cn("h-8 px-3 rounded-lg text-sm", view === "list" ? "bg-accent/15 text-text" : "text-muted")} onClick={() => setView("list")}>
              <LayoutList size={14} className="inline mr-1" /> List
            </button>
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 xl:grid-cols-3 gap-3">
        <div className="nl-surface-panel rounded-2xl p-4">
          <div className="flex items-center gap-2 text-sm font-semibold"><PieChart size={16} /> Overall status</div>
          <div className="mt-3 flex items-center gap-4">
            <div className="h-24 w-24 rounded-full border border-white/15" style={pieStyle} />
            <div className="text-xs space-y-1">
              <div><span className="text-ok">Done</span>: {stats.done}</div>
              <div><span className="text-danger">Blocked</span>: {stats.blocked}</div>
              <div><span className="text-warn">Overdue</span>: {stats.overdue}</div>
              <div><span className="text-accent">Open</span>: {stats.open}</div>
              <div className="text-muted">Total: {stats.total}</div>
            </div>
          </div>
        </div>
        <div className="nl-surface-panel rounded-2xl p-4">
          <div className="flex items-center gap-2 text-sm font-semibold"><BarChart3 size={16} /> By lane</div>
          <div className="mt-3"><MiniBars rows={laneRows.slice(0, 8)} /></div>
        </div>
        <div className="nl-surface-panel rounded-2xl p-4">
          <div className="flex items-center gap-2 text-sm font-semibold"><CalendarDays size={16} /> Priority load</div>
          <div className="mt-3"><MiniBars rows={priorityRows.slice(0, 6)} /></div>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {sections.map((section, index) => (
          <details key={section.key} className="nl-surface-panel rounded-2xl" open={index < 2}>
            <summary className="cursor-pointer list-none p-3 md:p-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 font-medium">
                {section.key === "recent" ? <Clock3 size={16} /> : section.key.includes("week") ? <CalendarDays size={16} /> : <CheckCircle2 size={16} />}
                {section.title}
              </div>
              <Badge variant="muted">{section.items.length}</Badge>
            </summary>
            <div className="px-3 md:px-4 pb-4">
              {section.items.length === 0 ? (
                <div className="nl-surface-item rounded-xl p-3 text-sm text-muted">No tasks in this bucket.</div>
              ) : view === "detail" ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {section.items.map((task) => (
                    <TaskDetail
                      key={task.id}
                      task={task}
                      laneName={laneById.get(task.laneId)?.name || "Lane"}
                      ownerName={task.ownerId ? userById.get(task.ownerId) || "Unassigned" : "Unassigned"}
                      onOpen={() => openTask(task.id)}
                    />
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {section.items.map((task) => (
                    <TaskListRow
                      key={task.id}
                      task={task}
                      laneName={laneById.get(task.laneId)?.name || "Lane"}
                      ownerName={task.ownerId ? userById.get(task.ownerId) || "Unassigned" : "Unassigned"}
                      onOpen={() => openTask(task.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </details>
        ))}
      </div>

      <div className="nl-surface-panel mt-4 rounded-2xl p-3 text-xs text-muted flex flex-wrap gap-4">
        <div className="inline-flex items-center gap-1"><TriangleAlert size={13} /> Due buckets are based on task due date.</div>
        <button className="inline-flex items-center gap-1 text-accent hover:underline" onClick={() => router.push("/app/reports")}>
          <BarChart3 size={13} /> Open full reports
        </button>
      </div>
    </div>
  );
}
