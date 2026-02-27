"use client";

import { useMemo, useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Clock, GripVertical, Layers, ShieldAlert, Sparkles } from "lucide-react";
import type { Lane, Task, User } from "@neonlanes/shared/schema";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useBoard } from "@/components/board-context";

function laneIcon(type: string) {
  if (type === "done") return <CheckCircle2 size={14} className="text-ok" />;
  if (type === "blocked") return <ShieldAlert size={14} className="text-danger" />;
  if (type === "backlog") return <Layers size={14} className="text-muted" />;
  return <Clock size={14} className="text-accent" />;
}

function isOverdue(dueDate?: string | null) {
  if (!dueDate) return false;
  const d = new Date(dueDate);
  if (Number.isNaN(d.getTime())) return false;
  return d.getTime() < Date.now();
}

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

function relativeUpdatedLabel(updatedAt?: string | null) {
  if (!updatedAt) return "";
  const d = new Date(updatedAt);
  if (Number.isNaN(d.getTime())) return "";
  const deltaMs = Date.now() - d.getTime();
  if (deltaMs < 60 * 1000) return "updated now";
  if (deltaMs < 3600 * 1000) return `updated ${Math.max(1, Math.floor(deltaMs / (60 * 1000)))}m ago`;
  if (deltaMs < 24 * 3600 * 1000) return `updated ${Math.max(1, Math.floor(deltaMs / (3600 * 1000)))}h ago`;
  return `updated ${Math.max(1, Math.floor(deltaMs / (24 * 3600 * 1000)))}d ago`;
}

export function LaneColumn({
  lane,
  tasks,
  users,
  onOpenTask,
  selectedTaskIds = new Set<string>(),
  onToggleTaskSelection = () => {},
  laneSortable = true,
  className
}: {
  lane: Lane;
  tasks: Task[];
  users: User[];
  onOpenTask: (taskId: string) => void;
  selectedTaskIds?: Set<string>;
  onToggleTaskSelection?: (taskId: string, selected: boolean) => void;
  laneSortable?: boolean;
  className?: string;
}) {
  const { reorderLanes, lanes, refreshAll, priorities } = useBoard();
  const { setNodeRef: dropRef, isOver } = useDroppable({ id: `lane-drop:${lane.id}` });
  const {
    attributes,
    listeners,
    setNodeRef: sortRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: `lane:${lane.id}`, disabled: !laneSortable });

  const style = { transform: CSS.Transform.toString(transform), transition };
  const count = tasks.length;
  const wip = lane.wipLimit ?? null;
  const overWip = wip !== null && count > wip;
  const overdueCount = useMemo(() => {
    if (lane.type === "done") return 0;
    return tasks.filter((t) => isOverdue(t.dueDate)).length;
  }, [lane.type, tasks]);
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
  const [laneSettings, setLaneSettings] = useState<{
    name: string;
    stateKey: string;
    type: "backlog" | "active" | "blocked" | "done";
    wipLimit: string | number;
  }>({
    name: lane.name,
    stateKey: lane.stateKey,
    type: lane.type,
    wipLimit: lane.wipLimit ?? ""
  });

  return (
    <div
      ref={sortRef}
      style={style}
      className={cn("w-[86vw] sm:w-[320px] h-full min-h-0 flex flex-col snap-start", isDragging && "opacity-70", className)}
    >
      <div className="nl-lane-card glass rounded-2xl p-3 shadow-neon min-h-[90px]">
        <div className="grid grid-cols-[32px_minmax(0,1fr)_auto] items-start gap-2">
          <div
            className="h-8 w-8 rounded-2xl border border-white/10 bg-white/5 grid place-items-center"
            {...(laneSortable ? attributes : {})}
            {...(laneSortable ? listeners : {})}
            title="Drag to reorder lane"
          >
            <GripVertical size={16} className="text-muted" />
          </div>
          <div className="min-w-0 space-y-1">
            <div className="h-5 flex items-center gap-2 min-w-0">
              {laneIcon(lane.type)}
              <div className="nl-lane-title font-semibold text-sm truncate">{lane.name}</div>
              {overWip ? <AlertTriangle size={14} className="text-warn" /> : null}
            </div>
            <div className="h-5 flex items-center gap-2 min-w-0">
              <div className="nl-lane-meta text-xs text-muted truncate whitespace-nowrap">
                {count} tasks{wip !== null ? ` • WIP ${count}/${wip}` : ""} • {lane.stateKey}
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0 pt-[1px]">
            <Badge variant={lane.type === "done" ? "ok" : lane.type === "blocked" ? "danger" : "muted"} className="shrink-0 uppercase">
              {lane.type}
            </Badge>
            {overdueCount ? (
              <Badge variant="danger" className="shrink-0">
                OVERDUE {overdueCount}
              </Badge>
            ) : null}
            <Popover>
              <PopoverTrigger asChild>
                <button
                  className="h-9 w-9 shrink-0 rounded-2xl border border-white/10 bg-white/0 hover:bg-white/5 transition grid place-items-center"
                  onClick={(e) => e.stopPropagation()}
                  title="Lane settings"
                >
                  <span className="text-muted text-base leading-none">•••</span>
                </button>
              </PopoverTrigger>
            <PopoverContent
              onOpenAutoFocus={(e) => e.preventDefault()}
              onClick={(e) => e.stopPropagation()}
              className="w-80"
            >
              <div className="text-sm font-semibold">Lane settings</div>
              <div className="mt-2 space-y-2">
                <div className="text-xs text-muted">Name</div>
                <Input value={laneSettings.name} onChange={(e) => setLaneSettings({ ...laneSettings, name: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-muted">stateKey</div>
                    <Input value={laneSettings.stateKey} onChange={(e) => setLaneSettings({ ...laneSettings, stateKey: e.target.value })} />
                  </div>
                  <div>
                    <div className="text-xs text-muted">Type</div>
                    <select
                      className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                      value={laneSettings.type}
                      onChange={(e) =>
                        setLaneSettings({
                          ...laneSettings,
                          type: e.target.value as "backlog" | "active" | "blocked" | "done"
                        })
                      }
                    >
                      {["backlog", "active", "blocked", "done"].map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="text-xs text-muted">WIP limit</div>
                <Input
                  value={String(laneSettings.wipLimit)}
                  onChange={(e) => setLaneSettings({ ...laneSettings, wipLimit: e.target.value })}
                  placeholder="(empty for none)"
                />
                <div className="flex gap-2 justify-end pt-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={async () => {
                      try {
                        const ordered = [...lanes].sort((a, b) => a.position - b.position).map((l) => l.id);
                        const idx = ordered.indexOf(lane.id);
                        if (idx > 0) {
                          const moved = arrayMove(ordered, idx, idx - 1);
                          await reorderLanes(moved);
                        }
                      } catch (e: any) {
                        toast.error(String(e?.message || e));
                      }
                    }}
                  >
                    Move left
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={async () => {
                      try {
                        const ordered = [...lanes].sort((a, b) => a.position - b.position).map((l) => l.id);
                        const idx = ordered.indexOf(lane.id);
                        if (idx < ordered.length - 1) {
                          const moved = arrayMove(ordered, idx, idx + 1);
                          await reorderLanes(moved);
                        }
                      } catch (e: any) {
                        toast.error(String(e?.message || e));
                      }
                    }}
                  >
                    Move right
                  </Button>
                </div>
                <div className="flex gap-2 justify-end">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={async () => {
                      try {
                        await api.updateLane(lane.id, {
                          name: laneSettings.name,
                          stateKey: laneSettings.stateKey,
                          type: laneSettings.type,
                          wipLimit: laneSettings.wipLimit === "" ? null : Number(laneSettings.wipLimit)
                        });
                        toast.success("Lane updated");
                        await refreshAll();
                      } catch (e: any) {
                        toast.error(String(e?.message || e));
                      }
                    }}
                  >
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={async () => {
                      try {
                        await api.deleteLane(lane.id);
                        toast.success("Lane deleted");
                        await refreshAll();
                      } catch (e: any) {
                        toast.error(String(e?.message || e));
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>

      <div
        ref={dropRef}
        className={cn(
          "nl-lane-dropzone mt-3 glass rounded-2xl p-2 flex-1 min-h-0 overflow-y-auto scrollbar border transition",
          isOver ? "border-accent/40 bg-accent/5" : "border-white/10"
        )}
      >
        <SortableContext items={tasks.map((t) => `task:${t.id}`)} strategy={verticalListSortingStrategy}>
          <div className="nl-task-stack flex flex-col gap-2">
            {tasks.map((t) => (
              <TaskCard
                key={t.id}
                task={t}
                laneType={lane.type}
                users={users}
                selected={selectedTaskIds.has(t.id)}
                onSelect={(selected) => onToggleTaskSelection(t.id, selected)}
                onOpen={() => onOpenTask(t.id)}
              />
            ))}
          </div>
        </SortableContext>

        {tasks.length === 0 ? (
          <div className="p-6 text-xs text-muted text-center">
            <div className="mx-auto h-10 w-10 rounded-3xl border border-white/10 bg-white/5 grid place-items-center">
              <Layers size={16} className="text-muted" />
            </div>
            <div className="mt-2">No tasks yet</div>
            <div className="mt-0.5 text-[11px] text-muted/80">Drop a task here or press n</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TaskCard({
  task,
  laneType,
  users,
  selected,
  onSelect,
  onOpen
}: {
  task: Task;
  laneType: string;
  users: User[];
  selected: boolean;
  onSelect: (selected: boolean) => void;
  onOpen: () => void;
}) {
  const { priorities } = useBoard();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: `task:${task.id}` });
  const style = { transform: CSS.Transform.toString(transform), transition };

  const owner = useMemo(() => users.find((u) => u.id === task.ownerId) || null, [users, task.ownerId]);
  const due = dueMeta(task.dueDate);
  const showDue = due.has && laneType !== "done";
  const overdue = showDue && due.overdue;
  const dueSoon = showDue && due.dueSoon;
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

  return (
    <motion.button
      ref={setNodeRef}
      style={style}
      onClick={onOpen}
      {...attributes}
      {...listeners}
      className={cn(
        "nl-task-card text-left w-full glass rounded-2xl p-3 border border-white/18 hover:border-accent/45 hover:bg-white/7 transition relative",
        overdue &&
          "border-danger/40 shadow-[0_0_0_1px_rgba(255,64,120,0.25),0_0_24px_rgba(255,64,120,0.14)]",
        dueSoon && "border-warn/40 shadow-[0_0_0_1px_rgba(255,196,0,0.18),0_0_18px_rgba(255,196,0,0.10)]",
        isDragging && "opacity-60"
      )}
      whileHover={{
        y: -3,
        scale: 1.01,
        boxShadow: "0 14px 28px rgba(0,0,0,0.3), 0 0 0 1px rgba(115,255,209,0.16)"
      }}
      whileTap={{ scale: 0.985, y: 0 }}
    >
      <div className="absolute right-2 top-2 z-10">
        <input
          type="checkbox"
          className="h-4 w-4 accent-emerald-400"
          checked={selected}
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
          onChange={(e) => onSelect(e.target.checked)}
          aria-label={`Select task ${task.title}`}
        />
      </div>
      <div
        className={cn(
          "absolute -left-0.5 top-3 bottom-3 w-0.5 rounded-full",
          task.blocked ? "bg-danger/60" : overdue ? "bg-danger/50" : dueSoon ? "bg-warn/60" : "bg-accent/40"
        )}
      />

      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="nl-task-title text-sm font-medium truncate">{task.title}</div>
          <div className="mt-1 flex flex-wrap gap-1.5 items-center content-center">
            <Badge variant={priorityVariant(task.priority)}>{task.priority}</Badge>
            {task.blocked ? <Badge variant="danger">Blocked</Badge> : null}
            {showDue ? <Badge variant={overdue ? "danger" : dueSoon ? "warn" : "muted"}>{due.label}</Badge> : null}
            {task.estimateMinutes ? <Badge variant="muted">{task.estimateMinutes}m</Badge> : null}
            {task.tags?.length ? <Badge variant="muted">tags {task.tags.length}</Badge> : null}
            {task.jiraKey ? (
              <a
                href={task.jiraUrl || "#"}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
                onPointerDown={(e) => e.stopPropagation()}
                className="inline-flex"
              >
                <Badge variant="accent" className="max-w-[120px] truncate">
                  {task.jiraKey}
                </Badge>
              </a>
            ) : null}
          </div>
          {task.blocked && task.blockedReason ? (
            <div className="mt-1 text-[11px] text-danger/90 line-clamp-1">Reason: {task.blockedReason}</div>
          ) : null}
          {task.description?.trim() ? (
            <div className="nl-task-desc mt-1 text-[11px] text-muted/90 line-clamp-2">{task.description.trim()}</div>
          ) : null}
        </div>

        <Popover>
          <PopoverTrigger asChild>
            <button
              className="h-8 w-8 grid place-items-center rounded-xl border border-white/10 bg-white/0 hover:bg-white/5 transition"
              onClick={(e) => {
                e.stopPropagation();
              }}
              onPointerDown={(e) => e.stopPropagation()}
              title="AI quick actions"
            >
              <Sparkles size={16} className="text-accent" />
            </button>
          </PopoverTrigger>
          <PopoverContent
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            <div className="text-sm font-semibold">AI quick actions</div>
            <div className="mt-2 flex flex-col gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  const text = (await api.aiTask(task.id, "summarize")).text;
                  toast.message("AI Summary", { description: text });
                }}
              >
                Summarize
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  const text = (await api.aiTask(task.id, "next-actions")).text;
                  toast.message("AI Next actions", { description: text });
                }}
              >
                Next actions
              </Button>
            </div>
          </PopoverContent>
        </Popover>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <div className="nl-task-meta text-xs text-muted">
          {task.type}
          {task.tags?.length ? ` • ${task.tags.slice(0, 2).join(", ")}${task.tags.length > 2 ? " +" : ""}` : ""}
        </div>
        <div className="flex items-center gap-2">
          {owner ? (
            <Avatar>
              <AvatarImage src={owner.avatarUrl || undefined} />
              <AvatarFallback>{owner.name.slice(0, 2).toUpperCase()}</AvatarFallback>
            </Avatar>
          ) : (
            <div className="text-[11px] text-muted border border-white/10 bg-white/5 rounded-full px-2 py-0.5">
              Unassigned
            </div>
          )}
        </div>
      </div>
      <div className="nl-task-updated mt-1 text-[11px] text-muted">{relativeUpdatedLabel(task.updatedAt)}</div>
    </motion.button>
  );
}
