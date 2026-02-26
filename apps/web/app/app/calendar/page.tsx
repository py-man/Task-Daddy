"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useBoard } from "@/components/board-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TaskDrawer } from "@/components/task-drawer";

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function addMonths(d: Date, n: number) {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

export default function CalendarPage() {
  const { board, tasks, loading, search } = useBoard();
  const [cursor, setCursor] = useState(() => startOfMonth(new Date()));
  const [drawerTaskId, setDrawerTaskId] = useState<string | null>(null);

  const tasksWithDue = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tasks
      .filter((t) => t.dueDate)
      .filter((t) => {
        if (!q) return true;
        const hay = `${t.title}\n${t.description}\n${(t.tags || []).join(" ")}\n${t.jiraKey || ""}`.toLowerCase();
        return hay.includes(q);
      });
  }, [tasks, search]);

  const grid = useMemo(() => {
    const first = startOfMonth(cursor);
    const offset = (first.getDay() + 6) % 7; // monday=0
    const start = new Date(first);
    start.setDate(first.getDate() - offset);
    const days: Date[] = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      days.push(d);
    }
    return days;
  }, [cursor]);

  const byDay = useMemo(() => {
    const map = new Map<string, any[]>();
    for (const t of tasksWithDue) {
      const key = t.dueDate!.slice(0, 10);
      map.set(key, [...(map.get(key) || []), t]);
    }
    return map;
  }, [tasksWithDue]);

  if (loading || !board) return <div className="h-full p-6 text-muted">Loading…</div>;

  const title = cursor.toLocaleString(undefined, { month: "long", year: "numeric" });
  const todayKey = new Date().toISOString().slice(0, 10);

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="px-4 pb-3 flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => setCursor((d) => addMonths(d, -1))}>
          <ChevronLeft size={16} /> Prev
        </Button>
        <div className="text-sm font-semibold">{title}</div>
        <Button variant="ghost" size="sm" onClick={() => setCursor((d) => addMonths(d, 1))}>
          Next <ChevronRight size={16} />
        </Button>
      </div>

      <div className="flex-1 overflow-auto px-4 pb-6 scrollbar">
        <div className="glass rounded-3xl shadow-neon border border-white/10 overflow-hidden">
          <div className="grid" style={{ gridTemplateColumns: "repeat(7, 1fr)" }}>
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
              <div key={d} className="p-3 text-xs text-muted border-b border-white/10">
                {d}
              </div>
            ))}
            {grid.map((d) => {
              const key = d.toISOString().slice(0, 10);
              const inMonth = d.getMonth() === cursor.getMonth();
              const items = byDay.get(key) || [];
              return (
                <div key={key} className="min-h-28 p-2 border-b border-white/10 border-r border-white/10">
                  <div className="flex items-center justify-between">
                    <div className={`text-xs ${inMonth ? "text-text" : "text-muted"}`}>{d.getDate()}</div>
                    {key === todayKey ? <Badge variant="accent">Today</Badge> : null}
                  </div>
                  <div className="mt-2 space-y-1">
                    {items.slice(0, 4).map((t: any) => (
                      <button
                        key={t.id}
                        onClick={() => setDrawerTaskId(t.id)}
                        className="w-full text-left rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 px-2 py-1 text-xs"
                      >
                        {t.title}
                      </button>
                    ))}
                    {items.length > 4 ? <div className="text-[11px] text-muted">+{items.length - 4} more</div> : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <TaskDrawer taskId={drawerTaskId} onClose={() => setDrawerTaskId(null)} />
    </div>
  );
}
