"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { DndContext, DragEndEvent, DragOverlay, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { motion } from "framer-motion";
import { CircleHelp, Mic, MicOff, Plus } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useBoard } from "@/components/board-context";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { LaneColumn } from "@/components/swimlane";
import { TaskDrawer } from "@/components/task-drawer";
import { BoardHealthBar } from "@/components/board-health";
import { useSession } from "@/components/session";
import type { Lane, Task } from "@neonlanes/shared/schema";
import { toast } from "sonner";
import { EmptyState } from "@/components/empty-state";
import { MobileBoardView } from "@/components/mobile/mobile-board-view";
import { applyUiDesignFromStorage, getUiDesign, type UiDesign } from "@/lib/ui-design";
import { cn } from "@/lib/cn";

export default function BoardPage() {
  const { board, boards, lanes, tasks, users, priorities, taskTypes, loading, search, createLane, reorderLanes, moveTask, createBoard, createTask } = useBoard();
  const { user: sessionUser } = useSession();
  const searchParams = useSearchParams();
  const [drawerTaskId, setDrawerTaskId] = useState<string | null>(null);
  const [laneModal, setLaneModal] = useState({ name: "New lane", stateKey: "new_lane", type: "active", wipLimit: "" });
  const [activeDragTask, setActiveDragTask] = useState<Task | null>(null);
  const [preset, setPreset] = useState<"all" | "mine" | "overdue" | "blocked" | "high" | "dueSoon">("all");
  const [mobileLaneId, setMobileLaneId] = useState<string>("");
  const [mobileControlsOpen, setMobileControlsOpen] = useState(false);
  const [desktopMoreOpen, setDesktopMoreOpen] = useState(false);
  const [laneSort, setLaneSort] = useState<"manual" | "due" | "priority" | "updated" | "title">("manual");
  const [laneSortDir, setLaneSortDir] = useState<"asc" | "desc">("asc");
  const [quickNote, setQuickNote] = useState("");
  const [quickSaving, setQuickSaving] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [voiceListening, setVoiceListening] = useState(false);
  const [uiDesign, setUiDesign] = useState<UiDesign>("core");
  const voiceRef = useRef<any>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const sortedLanes = useMemo(() => [...lanes].sort((a, b) => a.position - b.position), [lanes]);
  const laneTypeById = useMemo(() => new Map(sortedLanes.map((l) => [l.id, l.type])), [sortedLanes]);
  useEffect(() => {
    if (!mobileLaneId && sortedLanes[0]?.id) setMobileLaneId(sortedLanes[0].id);
    if (mobileLaneId && !sortedLanes.some((l) => l.id === mobileLaneId) && sortedLanes[0]?.id) setMobileLaneId(sortedLanes[0].id);
  }, [sortedLanes, mobileLaneId]);

  useEffect(() => {
    try {
      const v = (localStorage.getItem("nl:boardPreset") || "all") as any;
      if (["all", "mine", "overdue", "blocked", "high", "dueSoon"].includes(v)) setPreset(v);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("nl:boardPreset", preset);
    } catch {
      // ignore
    }
  }, [preset]);

  useEffect(() => {
    try {
      const v = (localStorage.getItem("nl:boardLaneSort") || "manual") as any;
      if (["manual", "due", "priority", "updated", "title"].includes(v)) setLaneSort(v);
      const d = (localStorage.getItem("nl:boardLaneSortDir") || "asc") as any;
      if (["asc", "desc"].includes(d)) setLaneSortDir(d);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("nl:boardLaneSort", laneSort);
      localStorage.setItem("nl:boardLaneSortDir", laneSortDir);
    } catch {
      // ignore
    }
  }, [laneSort, laneSortDir]);

  const enabledPriorities = useMemo(
    () => (priorities || []).filter((p) => p.enabled !== false).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );
  const enabledTaskTypes = useMemo(
    () => (taskTypes || []).filter((t) => t.enabled !== false).slice().sort((a, b) => a.position - b.position),
    [taskTypes]
  );
  const priorityRank = useMemo(() => new Map(enabledPriorities.map((p) => [p.key, p.rank])), [enabledPriorities]);
  const quickPriority = useMemo(
    () => enabledPriorities.find((p) => p.key.toLowerCase() === "p2")?.key || enabledPriorities[0]?.key || "P2",
    [enabledPriorities]
  );
  const quickType = useMemo(
    () =>
      enabledTaskTypes.find((t) => t.key.toLowerCase() === "note")?.key ||
      enabledTaskTypes.find((t) => t.key.toLowerCase() === "ops")?.key ||
      enabledTaskTypes.find((t) => t.key.toLowerCase() === "feature")?.key ||
      enabledTaskTypes[0]?.key ||
      "Feature",
    [enabledTaskTypes]
  );

  const filteredTasks = useMemo(() => {
    const q = search.trim().toLowerCase();
    let base = tasks;
    if (preset === "mine" && sessionUser?.id) base = base.filter((t) => t.ownerId === sessionUser.id);
    if (preset === "blocked") {
      base = base.filter((t) => (t.blocked || laneTypeById.get(t.laneId) === "blocked") && laneTypeById.get(t.laneId) !== "done");
    }
    if (preset === "high") base = base.filter((t) => (t.priority === "P0" || t.priority === "P1") && laneTypeById.get(t.laneId) !== "done");
    if (preset === "overdue") {
      base = base.filter((t) => {
        const laneType = laneTypeById.get(t.laneId);
        if (laneType === "done") return false;
        if (!t.dueDate) return false;
        const d = new Date(t.dueDate);
        if (Number.isNaN(d.getTime())) return false;
        return d.getTime() < Date.now();
      });
    }
    if (preset === "dueSoon") {
      base = base.filter((t) => {
        const laneType = laneTypeById.get(t.laneId);
        if (laneType === "done") return false;
        if (!t.dueDate) return false;
        const d = new Date(t.dueDate);
        if (Number.isNaN(d.getTime())) return false;
        const delta = d.getTime() - Date.now();
        return delta >= 0 && delta <= 48 * 3600 * 1000;
      });
    }

    if (!q) return base;
    return base.filter((t) => {
      const hay = `${t.title}\n${t.description}\n${(t.tags || []).join(" ")}\n${t.jiraKey || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [tasks, search, preset, sessionUser?.id, laneTypeById]);

  const tasksByLane = useMemo(() => {
    const map = new Map<string, Task[]>();
    for (const l of sortedLanes) map.set(l.id, []);
    for (const t of filteredTasks) {
      const arr = map.get(t.laneId) || [];
      arr.push(t);
      map.set(t.laneId, arr);
    }
    for (const [k, arr] of map) {
      arr.sort((a, b) => {
        let out = 0;
        if (laneSort === "priority") {
          out = (priorityRank.get(a.priority) ?? 99) - (priorityRank.get(b.priority) ?? 99);
        } else if (laneSort === "updated") {
          out = String(a.updatedAt || "").localeCompare(String(b.updatedAt || ""));
        } else if (laneSort === "title") {
          out = String(a.title || "").localeCompare(String(b.title || ""));
        } else if (laneSort === "due") {
          out = String(a.dueDate || "").localeCompare(String(b.dueDate || ""));
        } else {
          out = a.orderIndex - b.orderIndex;
        }
        if (out === 0) out = a.orderIndex - b.orderIndex;
        return laneSortDir === "asc" ? out : -out;
      });
      map.set(k, arr);
    }
    return map;
  }, [filteredTasks, sortedLanes, laneSort, laneSortDir, priorityRank]);

  useEffect(() => {
    const id = searchParams?.get("task");
    if (id) setDrawerTaskId(id);
  }, [searchParams]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const active = document.activeElement as HTMLElement | null;
      if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable)) return;
      if (e.key === "Escape") setDrawerTaskId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new CustomEvent("nl:mobile-chrome", { detail: { hidden: false, source: "board" } }));
    return () => {
      window.dispatchEvent(new CustomEvent("nl:mobile-chrome", { detail: { hidden: false, source: "board" } }));
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setUiDesign(applyUiDesignFromStorage());
    const onStorage = (event: StorageEvent) => {
      if (event.key === "nl-ui-design") setUiDesign(getUiDesign());
    };
    const onCustom = () => setUiDesign(getUiDesign());
    window.addEventListener("storage", onStorage);
    window.addEventListener("nl:uiDesignChanged", onCustom as EventListener);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("nl:uiDesignChanged", onCustom as EventListener);
    };
  }, []);

  const onDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveDragTask(null);
    if (!over) return;
    const activeId = String(active.id);
    const overId = String(over.id);

    // Lane reorder
    if (activeId.startsWith("lane:") && overId.startsWith("lane:")) {
      const ids = sortedLanes.map((l) => `lane:${l.id}`);
      const oldIndex = ids.indexOf(activeId);
      const newIndex = ids.indexOf(overId);
      if (oldIndex === -1 || newIndex === -1 || oldIndex === newIndex) return;
      const moved = arrayMove(sortedLanes, oldIndex, newIndex).map((l) => l.id);
      await reorderLanes(moved);
      window.dispatchEvent(new CustomEvent("nl:task-moved", { detail: { type: "lane-reorder" } }));
      return;
    }

    // Task move
    if (activeId.startsWith("task:")) {
      const taskId = activeId.replace("task:", "");
      const t = tasks.find((x) => x.id === taskId);
      if (!t) return;

      let targetLaneId = t.laneId;
      let toIndex = 0;

      if (overId.startsWith("lane-drop:")) {
        targetLaneId = overId.replace("lane-drop:", "");
        toIndex = tasksByLane.get(targetLaneId)?.length || 0;
      } else if (overId.startsWith("task:")) {
        const overTaskId = overId.replace("task:", "");
        const overTask = tasks.find((x) => x.id === overTaskId);
        if (overTask) {
          targetLaneId = overTask.laneId;
          const laneTasks = tasksByLane.get(targetLaneId) || [];
          toIndex = laneTasks.findIndex((x) => x.id === overTask.id);
          if (toIndex < 0) toIndex = laneTasks.length;
        }
      }

      if (targetLaneId === t.laneId && toIndex === t.orderIndex) return;
      try {
        await moveTask(taskId, { laneId: targetLaneId, toIndex, version: t.version });
        window.dispatchEvent(new CustomEvent("nl:task-moved", { detail: { type: "task-move", taskId, laneId: targetLaneId } }));
      } catch (e: any) {
        toast.error(String(e?.message || e));
      }
    }
  };

  const onDragStart = (id: string) => {
    if (id.startsWith("task:")) {
      const t = tasks.find((x) => x.id === id.replace("task:", ""));
      if (t) setActiveDragTask(t);
    }
  };

  const boardOverdue = tasks.filter((t) => {
    const laneType = laneTypeById.get(t.laneId);
    if (laneType === "done") return false;
    if (!t.dueDate) return false;
    const d = new Date(t.dueDate);
    return !Number.isNaN(d.getTime()) && d.getTime() < Date.now();
  }).length;
  const boardBlocked = tasks.filter((t) => (t.blocked || laneTypeById.get(t.laneId) === "blocked") && laneTypeById.get(t.laneId) !== "done").length;
  const boardDueSoon = tasks.filter((t) => {
    const laneType = laneTypeById.get(t.laneId);
    if (laneType === "done") return false;
    if (!t.dueDate) return false;
    const d = new Date(t.dueDate);
    if (Number.isNaN(d.getTime())) return false;
    const delta = d.getTime() - Date.now();
    return delta >= 0 && delta <= 48 * 3600 * 1000;
  }).length;

  const submitQuickNote = async (raw: string) => {
    const body = (raw || "").trim();
    if (!body || !sessionUser?.id) return;
    const laneId = mobileLaneId || sortedLanes[0]?.id;
    if (!laneId) return;
    try {
      setQuickSaving(true);
      await createTask({
        laneId,
        title: body.slice(0, 96),
        description: body,
        ownerId: sessionUser.id,
        priority: quickPriority,
        type: quickType
      });
      setQuickNote("");
    } catch (err: any) {
      toast.error(String(err?.message || err));
    } finally {
      setQuickSaving(false);
    }
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    const W = window as any;
    const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
    if (!SR) {
      setVoiceSupported(false);
      return;
    }
    setVoiceSupported(true);
    const rec = new SR();
    rec.lang = "en-US";
    rec.continuous = false;
    rec.interimResults = true;
    rec.onstart = () => setVoiceListening(true);
    rec.onend = () => setVoiceListening(false);
    rec.onerror = () => {
      setVoiceListening(false);
      toast.error("Voice input failed. Try again.");
    };
    rec.onresult = async (event: any) => {
      let interim = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = String(event.results[i][0]?.transcript || "");
        if (event.results[i].isFinal) finalText += transcript;
        else interim += transcript;
      }
      const text = (finalText || interim).trim();
      if (!text) return;
      setQuickNote(text);
      if (finalText.trim()) await submitQuickNote(finalText.trim());
    };
    voiceRef.current = rec;
    return () => {
      try {
        rec.stop();
      } catch {
        // ignore
      }
      voiceRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mobileLaneId, sortedLanes, sessionUser?.id, quickPriority, quickType]);

  const toggleVoiceCapture = () => {
    if (!voiceRef.current || quickSaving) return;
    try {
      if (voiceListening) voiceRef.current.stop();
      else voiceRef.current.start();
    } catch {
      toast.error("Voice input unavailable on this device.");
    }
  };

  if (loading) {
    return <div className="h-full p-6 text-muted">Loading board…</div>;
  }

  if (!board) {
    return (
      <div className="h-full p-4 md:p-6">
        <EmptyState
          title={boards.length ? "Select a board" : "Create your first board"}
          body={
            boards.length
              ? "Pick a board from the top bar.\nIf you don’t see it, you may not be a member yet."
              : "Boards hold lanes, tasks, and integrations.\nCreate one to get started."
          }
          actions={
            <Button
              variant="primary"
              onClick={async () => {
                await createBoard(`New Board ${new Date().toISOString().slice(0, 10)}`);
              }}
            >
              Create board
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "h-full flex flex-col min-h-0",
        uiDesign === "core" && "nl-board-core",
        uiDesign === "focus" && "nl-board-focus",
        uiDesign === "command" && "nl-board-command",
        uiDesign === "jira" && "nl-board-jira"
      )}
    >
      <div className="hidden lg:block px-4 pt-4">
        <BoardHealthBar lanes={sortedLanes} tasks={tasks} />
      </div>

      <div className="lg:hidden px-3 pt-2 pb-2">
        <TooltipProvider>
          <div className="flex items-center gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="sm" variant={mobileControlsOpen ? "primary" : "ghost"} onClick={() => setMobileControlsOpen((v) => !v)}>
                  {mobileControlsOpen ? "Hide controls" : "Show controls"}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Open filters and sorting for this board.</TooltipContent>
            </Tooltip>
            <a href="/app/help#mobile-quick-capture" className="h-8 px-2 rounded-xl border border-white/10 bg-white/5 inline-flex items-center gap-1 text-xs text-muted">
              <CircleHelp size={14} /> Help
            </a>
          </div>
        </TooltipProvider>
      </div>

      <div className="lg:hidden px-3 pb-2">
        <div className={cn("glass rounded-2xl border border-white/10 p-2", uiDesign === "focus" && "rounded-3xl p-3", uiDesign === "jira" && "rounded-xl")}>
          <div className={cn("flex items-center gap-2", uiDesign === "focus" && "gap-3")}>
            <Input
              data-testid="mobile-inline-quick-note"
              value={quickNote}
              onChange={(e) => setQuickNote(e.target.value)}
              placeholder={uiDesign === "jira" ? "Quick capture" : "Quick note... capture now, tidy later"}
              autoCapitalize="sentences"
              autoCorrect="on"
              enterKeyHint="done"
              onKeyDown={async (e) => {
                if (e.key !== "Enter") return;
                e.preventDefault();
                await submitQuickNote(quickNote);
              }}
            />
            <Button size="sm" variant={voiceListening ? "danger" : "ghost"} disabled={!voiceSupported || quickSaving} onClick={toggleVoiceCapture}>
              {voiceListening ? <MicOff size={15} /> : <Mic size={15} />}
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={quickSaving || !quickNote.trim() || !sessionUser?.id || !(mobileLaneId || sortedLanes[0]?.id)}
              onClick={async () => {
                await submitQuickNote(quickNote);
              }}
            >
              Add
            </Button>
          </div>
          <div className="mt-1 text-[11px] text-muted">
            {uiDesign === "command"
              ? "Instant capture for triage. Add detail later in task drawer."
              : "Saves to current lane using your default note settings."}
          </div>
        </div>
      </div>

      <div className="hidden lg:flex px-4 pb-3 pt-3 flex-col gap-2">
        <div className="nl-board-toolbar-primary flex flex-wrap items-center gap-2">
          <Button size="sm" variant={preset === "all" ? "primary" : "ghost"} onClick={() => setPreset("all")}>
            All
          </Button>
          <Button size="sm" variant={preset === "mine" ? "primary" : "ghost"} onClick={() => setPreset("mine")}>
            My tasks
          </Button>
          <Button size="sm" variant={preset === "overdue" ? "danger" : "ghost"} onClick={() => setPreset("overdue")}>
            Overdue
          </Button>
          <Button size="sm" variant={preset === "dueSoon" ? "warn" : "ghost"} onClick={() => setPreset("dueSoon")}>
            Due soon
          </Button>
          <Button size="sm" variant={desktopMoreOpen ? "primary" : "ghost"} onClick={() => setDesktopMoreOpen((v) => !v)}>
            {desktopMoreOpen ? "Hide more" : "More"}
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="ghost">
                <Plus size={16} /> Add lane
              </Button>
            </DialogTrigger>
            <DialogContent>
              <div className="text-lg font-semibold">New lane</div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <div className="text-xs text-muted mb-1">Name</div>
                  <Input value={laneModal.name} onChange={(e) => setLaneModal({ ...laneModal, name: e.target.value })} />
                </div>
                <div>
                  <div className="text-xs text-muted mb-1">stateKey</div>
                  <Input value={laneModal.stateKey} onChange={(e) => setLaneModal({ ...laneModal, stateKey: e.target.value })} />
                </div>
                <div>
                  <div className="text-xs text-muted mb-1">Type</div>
                  <select
                    className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                    value={laneModal.type}
                    onChange={(e) => setLaneModal({ ...laneModal, type: e.target.value })}
                  >
                    {["backlog", "active", "blocked", "done"].map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="col-span-2">
                  <div className="text-xs text-muted mb-1">WIP limit (optional)</div>
                  <Input
                    value={laneModal.wipLimit}
                    onChange={(e) => setLaneModal({ ...laneModal, wipLimit: e.target.value })}
                    placeholder="e.g. 5"
                  />
                </div>
                <div className="col-span-2 flex justify-end gap-2 mt-2">
                  <Button
                    onClick={async () => {
                      const wip = laneModal.wipLimit.trim() ? Number(laneModal.wipLimit) : null;
                      await createLane({
                        name: laneModal.name,
                        stateKey: laneModal.stateKey,
                        type: laneModal.type,
                        wipLimit: wip !== null && Number.isFinite(wip) ? wip : null
                      });
                    }}
                  >
                    Create
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
        {desktopMoreOpen ? (
          <div className="nl-board-toolbar-secondary flex flex-wrap items-center gap-2">
            <Button size="sm" variant={preset === "blocked" ? "danger" : "ghost"} onClick={() => setPreset("blocked")}>
              Blocked
            </Button>
            <Button size="sm" variant={preset === "high" ? "primary" : "ghost"} onClick={() => setPreset("high")}>
              High priority
            </Button>
            <label className="text-xs text-muted px-2">Order</label>
            <select
              className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
              value={laneSort}
              onChange={(e) => setLaneSort(e.target.value as "manual" | "due" | "priority" | "updated" | "title")}
            >
              <option value="manual">Manual</option>
              <option value="due">Due date</option>
              <option value="priority">Priority</option>
              <option value="updated">Updated</option>
              <option value="title">Title</option>
            </select>
            <select
              className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
              value={laneSortDir}
              onChange={(e) => setLaneSortDir(e.target.value as "asc" | "desc")}
            >
              <option value="asc">Asc</option>
              <option value="desc">Desc</option>
            </select>
          </div>
        ) : null}
      </div>

      {mobileControlsOpen ? (
        <div className="lg:hidden px-3 pb-2">
          <div className="glass rounded-2xl p-3 border border-white/10 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant={preset === "all" ? "primary" : "ghost"} onClick={() => setPreset("all")}>
                All
              </Button>
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
            <div className="grid grid-cols-2 gap-2">
              <select
                className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
                value={laneSort}
                onChange={(e) => setLaneSort(e.target.value as "manual" | "due" | "priority" | "updated" | "title")}
              >
                <option value="manual">Manual</option>
                <option value="due">Due date</option>
                <option value="priority">Priority</option>
                <option value="updated">Updated</option>
                <option value="title">Title</option>
              </select>
              <select
                className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
                value={laneSortDir}
                onChange={(e) => setLaneSortDir(e.target.value as "asc" | "desc")}
              >
                <option value="asc">Asc</option>
                <option value="desc">Desc</option>
              </select>
            </div>
          </div>
        </div>
      ) : null}

      <div className="flex-1 min-h-0 px-3 lg:px-4 pb-4 lg:pb-6">
        <div className="lg:hidden h-full min-h-0">
          <MobileBoardView
            lanes={sortedLanes}
            tasksByLane={tasksByLane}
            users={users}
            priorities={priorities}
            activeLaneId={mobileLaneId}
            setActiveLaneId={setMobileLaneId}
            onOpenTask={(id) => setDrawerTaskId(id)}
            onMoveTask={async (taskId, payload) => {
              try {
                await moveTask(taskId, payload);
              } catch (e: any) {
                toast.error(String(e?.message || e));
              }
            }}
          />
        </div>

        <div className="hidden lg:block h-full min-h-0">
          <div className={cn("h-full min-h-0", uiDesign === "command" ? "grid grid-cols-[minmax(0,1fr)_280px] gap-3" : "block")}>
            <div className="h-full min-h-0 overflow-x-auto overflow-y-hidden scrollbar scroll-smooth snap-x snap-mandatory">
              <DndContext sensors={sensors} onDragStart={(e) => onDragStart(String(e.active.id))} onDragEnd={onDragEnd}>
                <SortableContext items={sortedLanes.map((l) => `lane:${l.id}`)} strategy={horizontalListSortingStrategy}>
                  <div className={cn("h-full flex min-w-max", uiDesign === "focus" ? "gap-6 px-2" : uiDesign === "jira" ? "gap-2" : "gap-4")}>
                    {sortedLanes.map((lane) => (
                      <LaneColumn
                        key={lane.id}
                        lane={lane as Lane}
                        tasks={tasksByLane.get(lane.id) || []}
                        users={users}
                        onOpenTask={(id) => setDrawerTaskId(id)}
                        className={uiDesign === "focus" ? "sm:w-[360px]" : uiDesign === "jira" ? "sm:w-[300px]" : ""}
                      />
                    ))}
                  </div>
                </SortableContext>
                <DragOverlay>
                  {activeDragTask ? (
                    <motion.div className="glass rounded-2xl p-3 w-72 shadow-neon">
                      <div className="text-sm font-medium">{activeDragTask.title}</div>
                    </motion.div>
                  ) : null}
                </DragOverlay>
              </DndContext>
            </div>
            {uiDesign === "command" ? (
              <aside className="glass rounded-2xl border border-white/10 p-3 overflow-auto">
                <div className="text-sm font-semibold">Command Center</div>
                <div className="mt-3 grid grid-cols-1 gap-2">
                  <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                    <div className="text-xs text-muted">Total tasks</div>
                    <div className="text-xl font-semibold">{tasks.length}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                    <div className="text-xs text-muted">Blocked</div>
                    <div className="text-xl font-semibold">{boardBlocked}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                    <div className="text-xs text-muted">Overdue</div>
                    <div className="text-xl font-semibold">{boardOverdue}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-2">
                    <div className="text-xs text-muted">Due soon (48h)</div>
                    <div className="text-xl font-semibold">{boardDueSoon}</div>
                  </div>
                </div>
                <div className="mt-3 text-xs text-muted">Use this mode for triage, incident days, and deadline sweeps.</div>
              </aside>
            ) : null}
          </div>
        </div>
      </div>

      <TaskDrawer taskId={drawerTaskId} onClose={() => setDrawerTaskId(null)} />
    </div>
  );
}
