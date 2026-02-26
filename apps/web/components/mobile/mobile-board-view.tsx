"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRightLeft, CheckCircle2, ShieldAlert } from "lucide-react";
import type { BoardTaskPriority, Lane, Task, User } from "@neonlanes/shared/schema";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";

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
  const daysLeft = Math.max(1, Math.ceil(deltaMs / (24 * 3600 * 1000)));
  return { has: true as const, overdue: false, dueSoon: false, label: `DUE • ${daysLeft}d` };
}

export function MobileBoardView({
  lanes,
  tasksByLane,
  users,
  priorities,
  activeLaneId,
  setActiveLaneId,
  onOpenTask,
  onMoveTask
}: {
  lanes: Lane[];
  tasksByLane: Map<string, Task[]>;
  users: User[];
  priorities: BoardTaskPriority[];
  activeLaneId: string;
  setActiveLaneId: (id: string) => void;
  onOpenTask: (id: string) => void;
  onMoveTask: (taskId: string, payload: { laneId: string; toIndex: number; version: number }) => Promise<void>;
}) {
  const sortedLanes = useMemo(() => [...lanes].sort((a, b) => a.position - b.position), [lanes]);
  const activeLane = sortedLanes.find((l) => l.id === activeLaneId) || sortedLanes[0] || null;
  const laneTasks = (activeLane ? tasksByLane.get(activeLane.id) : []) || [];
  const doneLane = useMemo(() => sortedLanes.find((l) => l.type === "done") || null, [sortedLanes]);

  const userById = useMemo(() => new Map(users.map((u) => [u.id, u])), [users]);
  const enabledPriorities = useMemo(
    () => (priorities || []).filter((p) => p.enabled !== false).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );
  const priorityRank = useMemo(() => new Map(enabledPriorities.map((p) => [p.key, p.rank])), [enabledPriorities]);
  const priorityVariant = (key: string) => {
    const r = priorityRank.get(key) ?? 99;
    if (r <= 0) return "danger";
    if (r === 1) return "warn";
    if (r === 2) return "accent";
    return "muted";
  };
  const [moveFor, setMoveFor] = useState<Task | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const lastScrollTopRef = useRef(0);
  const hiddenRef = useRef(false);

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("nl:mobile-chrome", { detail: { hidden: false, source: "board" } }));
      }
    };
  }, []);

  const setChromeHidden = (hidden: boolean) => {
    if (hiddenRef.current === hidden) return;
    hiddenRef.current = hidden;
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nl:mobile-chrome", { detail: { hidden, source: "board" } }));
    }
  };

  const onScrollList = () => {
    const el = scrollRef.current;
    if (!el) return;
    const top = el.scrollTop;
    const delta = top - lastScrollTopRef.current;
    lastScrollTopRef.current = top;
    if (top < 16) {
      setChromeHidden(false);
      return;
    }
    if (delta > 8) setChromeHidden(true);
    if (delta < -8) setChromeHidden(false);
  };

  return (
    <div className="h-full min-h-0 flex flex-col">
      <div className="mt-2 flex gap-2 overflow-x-auto scrollbar pb-2">
        {sortedLanes.map((l) => (
          <button
            key={l.id}
            data-testid={`mobile-lane-chip-${l.id}`}
            className={cn(
              "shrink-0 rounded-2xl px-3 py-2 text-sm border transition",
              activeLane?.id === l.id ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 hover:bg-white/5"
            )}
            onClick={() => setActiveLaneId(l.id)}
          >
            {l.name}
            <span className="ml-2 text-xs text-muted tabular-nums">{(tasksByLane.get(l.id) || []).length}</span>
          </button>
        ))}
      </div>

      <div ref={scrollRef} onScroll={onScrollList} className="flex-1 min-h-0 overflow-y-auto scrollbar">
        {!activeLane ? (
          <div className="p-4 text-sm text-muted">No lanes yet.</div>
        ) : laneTasks.length === 0 ? (
          <div className="p-4 text-sm text-muted">No tasks in {activeLane.name}.</div>
        ) : (
          <div className="space-y-2 pb-6">
            {laneTasks.map((t) => {
              const owner = t.ownerId ? userById.get(t.ownerId) : null;
              const dm = dueMeta(t.dueDate);
              return (
                <div
                  key={t.id}
                  data-testid={`mobile-task-${t.id}`}
                  className={cn(
                    "nl-mobile-task-card rounded-2xl border bg-white/5 p-3 transition",
                    dm.overdue ? "border-danger/40 shadow-[0_0_0_1px_rgba(255,80,80,0.15)]" : dm.dueSoon ? "border-warn/30" : "border-white/10"
                  )}
                >
                  <button
                    className="w-full text-left"
                    onClick={() => {
                      setChromeHidden(false);
                      onOpenTask(t.id);
                    }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="nl-mobile-task-title text-sm font-medium leading-snug">{t.title}</div>
                      <Badge variant={priorityVariant(t.priority)}>{t.priority}</Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {owner ? <Badge variant="muted">{owner.name.split(" ")[0]}</Badge> : <Badge variant="muted">Unassigned</Badge>}
                      {t.blocked ? (
                        <Badge variant="danger" className="inline-flex items-center gap-1">
                          <ShieldAlert size={12} /> Blocked
                        </Badge>
                      ) : null}
                      {dm.has ? <Badge variant={dm.overdue ? "danger" : dm.dueSoon ? "warn" : "muted"}>{dm.label}</Badge> : null}
                      {t.jiraKey ? <Badge variant="accent">{t.jiraKey}</Badge> : null}
                    </div>
                  </button>

                  <div className="mt-3 flex items-center justify-end gap-2">
                    {doneLane && activeLane.type !== "done" ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={async () => {
                          const toIndex = (tasksByLane.get(doneLane.id) || []).length;
                          await onMoveTask(t.id, { laneId: doneLane.id, toIndex, version: t.version });
                        }}
                      >
                        <CheckCircle2 size={16} /> Done
                      </Button>
                    ) : null}

                    <Dialog open={moveFor?.id === t.id} onOpenChange={(v) => (!v ? setMoveFor(null) : setMoveFor(t))}>
                      <DialogTrigger asChild>
                        <Button size="sm" variant="ghost" onClick={() => setMoveFor(t)}>
                          <ArrowRightLeft size={16} /> Move
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <div className="text-lg font-semibold">Move task</div>
                        <div className="mt-2 text-sm text-muted">{t.title}</div>
                        <div className="mt-4 space-y-2">
                          {sortedLanes.map((l) => (
                            <button
                              key={l.id}
                              className={cn(
                                "w-full text-left rounded-2xl border p-3 transition",
                                l.id === t.laneId ? "border-accent/30 bg-accent/10" : "border-white/10 bg-white/5 hover:bg-white/10"
                              )}
                              onClick={async () => {
                                const toIndex = (tasksByLane.get(l.id) || []).length;
                                await onMoveTask(t.id, { laneId: l.id, toIndex, version: t.version });
                                setActiveLaneId(l.id);
                                setMoveFor(null);
                              }}
                            >
                              <div className="text-sm font-medium">{l.name}</div>
                              <div className="text-xs text-muted">{l.type}</div>
                            </button>
                          ))}
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
