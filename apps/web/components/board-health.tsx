"use client";

import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Clock, ShieldAlert } from "lucide-react";
import type { Lane, Task } from "@neonlanes/shared/schema";
import { cn } from "@/lib/cn";

function parseTimeMs(s?: string | null) {
  if (!s) return null;
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return null;
  return d.getTime();
}

export function BoardHealthBar({ lanes, tasks }: { lanes: Lane[]; tasks: Task[] }) {
  const laneTypeById = new Map(lanes.map((l) => [l.id, l.type]));
  const now = Date.now();
  const weekAgo = now - 7 * 24 * 3600 * 1000;

  let overdue = 0;
  let dueSoon = 0;
  let blocked = 0;
  let inProgress = 0;
  let doneWeek = 0;

  for (const t of tasks) {
    const laneType = laneTypeById.get(t.laneId) || "active";
    const isBlocked = Boolean(t.blocked) || laneType === "blocked";
    const dueMs = parseTimeMs(t.dueDate);
    const updatedMs = parseTimeMs(t.updatedAt);
    if (laneType !== "done") {
      if (isBlocked) blocked++;
      if (laneType === "active") inProgress++;
      if (dueMs !== null) {
        const delta = dueMs - now;
        if (delta < 0) overdue++;
        else if (delta <= 48 * 3600 * 1000) dueSoon++;
      }
    } else {
      if (updatedMs !== null && updatedMs >= weekAgo) doneWeek++;
    }
  }

  const items = [
    { key: "overdue", label: "Overdue", value: overdue, icon: <AlertTriangle size={14} />, tone: "danger" },
    { key: "dueSoon", label: "Due soon", value: dueSoon, icon: <Clock size={14} />, tone: "warn" },
    { key: "blocked", label: "Blocked", value: blocked, icon: <ShieldAlert size={14} />, tone: "danger" },
    { key: "inProgress", label: "In progress", value: inProgress, icon: <Clock size={14} />, tone: "accent" },
    { key: "doneWeek", label: "Done (7d)", value: doneWeek, icon: <CheckCircle2 size={14} />, tone: "ok" }
  ] as const;

  const toneClass = (tone: string) => {
    if (tone === "danger") return "border-danger/25 bg-danger/5";
    if (tone === "warn") return "border-warn/25 bg-warn/5";
    if (tone === "ok") return "border-ok/25 bg-ok/5";
    return "border-accent/25 bg-accent/5";
  };

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-3 md:p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">Board health</div>
        <div className="text-xs text-muted">Live signals (no noise)</div>
      </div>

      <div className="mt-3 flex gap-2 overflow-x-auto scrollbar pb-1">
        {items.map((it) => (
          <motion.div
            key={it.key}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18 }}
            className={cn(
              "min-w-[160px] rounded-2xl border px-3 py-2 flex items-center gap-2",
              toneClass(it.tone),
              it.key === "overdue" && it.value > 0 ? "shadow-[0_0_18px_rgba(255,64,120,0.08)]" : ""
            )}
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
  );
}
