"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarDays, CornerDownLeft, LayoutGrid, List, Plus, Search, Settings, Sparkles, X } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useBoard } from "@/components/board-context";
import { cn } from "@/lib/cn";

type Mode = "commands" | "create";

export function CommandPalette() {
  const router = useRouter();
  const { board, lanes, tasks, createTask, refreshAll, taskTypes, priorities } = useBoard();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("commands");
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
        setMode("commands");
        return;
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => inputRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setMode("commands");
  }, [open]);

  const sortedLanes = useMemo(() => [...lanes].sort((a, b) => a.position - b.position), [lanes]);
  const defaultLaneId = useMemo(() => {
    const backlog = sortedLanes.find((l) => l.type === "backlog");
    return backlog?.id || sortedLanes[0]?.id || "";
  }, [sortedLanes]);

  const enabledTaskTypes = useMemo(
    () => (taskTypes || []).filter((t) => t.enabled !== false).slice().sort((a, b) => a.position - b.position),
    [taskTypes]
  );
  const enabledPriorities = useMemo(
    () => (priorities || []).filter((p) => p.enabled !== false).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );
  const defaultTypeKey = useMemo(
    () => enabledTaskTypes.find((t) => t.key.toLowerCase() === "feature")?.key || enabledTaskTypes[0]?.key || "Feature",
    [enabledTaskTypes]
  );
  const defaultPriorityKey = useMemo(
    () => enabledPriorities.find((p) => p.key.toLowerCase() === "p2")?.key || enabledPriorities[0]?.key || "P2",
    [enabledPriorities]
  );

  const taskMatches = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return [];
    return tasks
      .filter((t) => t.title.toLowerCase().includes(needle) || (t.jiraKey || "").toLowerCase().includes(needle))
      .slice(0, 6);
  }, [q, tasks]);

  const commands = useMemo(
    () => [
      {
        id: "create",
        title: "Create task…",
        icon: <Plus size={16} />,
        desc: board ? `In ${board.name}` : "Select a board first",
        disabled: !board?.id || !defaultLaneId,
        run: () => setMode("create")
      },
      {
        id: "board",
        title: "Go to Board",
        icon: <LayoutGrid size={16} />,
        desc: "Swimlanes view",
        run: () => router.push("/app/board")
      },
      {
        id: "list",
        title: "Go to List",
        icon: <List size={16} />,
        desc: "Table view",
        run: () => router.push("/app/list")
      },
      {
        id: "calendar",
        title: "Go to Calendar",
        icon: <CalendarDays size={16} />,
        desc: "Due dates",
        run: () => router.push("/app/calendar")
      },
      {
        id: "settings",
        title: "Open Settings",
        icon: <Settings size={16} />,
        desc: "Control plane",
        run: () => router.push("/app/settings")
      }
    ],
    [board, defaultLaneId, router]
  );

  const filteredCommands = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((c) => `${c.title}\n${c.desc}`.toLowerCase().includes(needle));
  }, [commands, q]);

  const submitQuickCreate = async () => {
    if (!board?.id || !defaultLaneId) return;
    const title = q.trim();
    if (!title) return;
    setCreating(true);
    try {
      await createTask({
        laneId: defaultLaneId,
        title,
        priority: defaultPriorityKey,
        type: defaultTypeKey,
        ownerId: null,
        dueDate: null
      });
      setOpen(false);
      await refreshAll();
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-lg font-semibold">Command palette</div>
            <div className="mt-1 text-xs text-muted">⌘K / Ctrl+K • Type to search • Enter to create a task</div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setOpen(false)} aria-label="Close">
            <X size={16} />
          </Button>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <div className="h-10 w-10 rounded-2xl border border-white/10 bg-white/5 grid place-items-center">
            <Search size={16} className="text-muted" />
          </div>
          <Input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={
              board?.id ? "Search commands or tasks… (Enter opens first match / creates task)" : "Search commands… (select a board to create tasks)"
            }
            className="glass border-white/10"
            onKeyDown={async (e) => {
              if (e.key === "Enter" && mode === "commands") {
                e.preventDefault();
                if (taskMatches.length) {
                  router.push(`/app/board?task=${taskMatches[0].id}`);
                  setOpen(false);
                  return;
                }
                await submitQuickCreate();
              }
            }}
          />
          <Badge variant="muted">{board?.name || "No board"}</Badge>
        </div>

        {mode === "create" ? (
          <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">Create task</div>
              <Button size="sm" variant="ghost" onClick={() => setMode("commands")}>
                Back
              </Button>
            </div>
            <div className="mt-3 text-xs text-muted">Title</div>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ship command palette" className="mt-1 glass border-white/10" />
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="col-span-2 sm:col-span-1">
                <div className="text-xs text-muted">Lane</div>
                <select
                  className="mt-1 h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                  defaultValue={defaultLaneId}
                  onChange={(e) => {
                    // Keep simple: lane selection is stored as a data attribute on the select and read at submit time.
                    (e.currentTarget as HTMLSelectElement).dataset.selectedLaneId = e.currentTarget.value;
                  }}
                >
                  {sortedLanes.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-2 sm:col-span-1 flex items-end justify-end">
                <Button
                  disabled={creating || !q.trim()}
                  onClick={async (e) => {
                    const select = (e.currentTarget.closest("div")?.parentElement?.querySelector("select") as HTMLSelectElement | null) || null;
                    const laneId = (select?.dataset.selectedLaneId || select?.value || defaultLaneId).trim();
                    if (!laneId) return;
                    setCreating(true);
                    try {
                      await createTask({
                        laneId,
                        title: q.trim(),
                        priority: defaultPriorityKey,
                        type: defaultTypeKey,
                        ownerId: null,
                        dueDate: null
                      });
                      setOpen(false);
                      await refreshAll();
                    } catch (err: any) {
                      toast.error(String(err?.message || err));
                    } finally {
                      setCreating(false);
                    }
                  }}
                >
                  <CornerDownLeft size={16} /> Create
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-2">
              <div className="px-2 pt-2 pb-1 text-xs text-muted flex items-center gap-2">
                <Sparkles size={14} className="text-accent" /> Commands
              </div>
              <div className="space-y-1">
                {filteredCommands.map((c) => (
                  <button
                    key={c.id}
                    disabled={Boolean((c as any).disabled)}
                    onClick={() => {
                      if ((c as any).disabled) return;
                      (c as any).run?.();
                      setOpen(false);
                    }}
                    className={cn(
                      "w-full text-left rounded-2xl border px-3 py-2 flex items-center gap-3 transition",
                      (c as any).disabled
                        ? "border-white/5 bg-white/0 opacity-50 cursor-not-allowed"
                        : "border-white/10 hover:bg-white/5 hover:border-accent/25"
                    )}
                  >
                    <div className="h-9 w-9 rounded-2xl border border-white/10 bg-white/5 grid place-items-center text-muted">{(c as any).icon}</div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium truncate">{(c as any).title}</div>
                      <div className="text-xs text-muted truncate">{(c as any).desc}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {taskMatches.length ? (
              <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-2">
                <div className="px-2 pt-2 pb-1 text-xs text-muted flex items-center gap-2">
                  <Search size={14} /> Tasks
                </div>
                <div className="space-y-1">
                  {taskMatches.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => {
                        router.push(`/app/board?task=${t.id}`);
                        setOpen(false);
                      }}
                      className="w-full text-left rounded-2xl border border-white/10 hover:bg-white/5 hover:border-accent/25 px-3 py-2 flex items-center gap-3 transition"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium truncate">{t.title}</div>
                        <div className="text-xs text-muted truncate">{t.jiraKey ? `${t.jiraKey} • ` : ""}{t.priority} • {t.type}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
