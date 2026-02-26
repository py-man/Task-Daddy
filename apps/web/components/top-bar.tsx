"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bell, BookOpen, ChevronDown, ExternalLink, Layers, LogOut, Mic, MicOff, Moon, Plus, RefreshCw, Settings, Shield, Sparkles, Sun } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { useBoard } from "@/components/board-context";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogTrigger, DialogContent } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { TaskDaddyLogo } from "@/components/brand/task-daddy-logo";
import { applyLightPaletteFromStorage } from "@/lib/light-palette";

function isoOrNull(d: string) {
  if (!d) return null;
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toISOString();
}

export function TopBar() {
  const router = useRouter();
  const { user, logout } = useSession();
  const { boards, board, lanes, users, tasks, taskTypes, priorities, selectBoard, createBoard, createTask, updateTask, refreshAll, search, setSearch } =
    useBoard();
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [newBoardName, setNewBoardName] = useState("New Board");
  const [syncBadge, setSyncBadge] = useState<{ text: string; variant: any }>({ text: "Idle", variant: "muted" });
  const [newTaskOpen, setNewTaskOpen] = useState(false);
  const [newTask, setNewTask] = useState<{
    title: string;
    laneId: string;
    priority: string;
    type: string;
    ownerId: string;
    dueDate: string;
  }>({
    title: "",
    laneId: "",
    priority: "",
    type: "",
    ownerId: "",
    dueDate: ""
  });
  const [aiOpen, setAiOpen] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiText, setAiText] = useState("");
  const [aiSuggestions, setAiSuggestions] = useState<any[]>([]);
  const [aiSelected, setAiSelected] = useState<Record<string, boolean>>({});
  const [aiCreates, setAiCreates] = useState<any[]>([]);
  const [aiCreateSelected, setAiCreateSelected] = useState<Record<string, boolean>>({});
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifs, setNotifs] = useState<any[]>([]);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [voiceListening, setVoiceListening] = useState(false);
  const voiceRef = useRef<any>(null);
  const unreadCount = useMemo(() => notifs.filter((n) => !n.readAt).length, [notifs]);

  const boardLabel = board?.name || "Select board";

  const enabledTaskTypes = useMemo(
    () => (taskTypes || []).filter((t) => t.enabled !== false).slice().sort((a, b) => a.position - b.position),
    [taskTypes]
  );
  const enabledPriorities = useMemo(
    () => (priorities || []).filter((p) => p.enabled !== false).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );
  const defaultTypeKey = useMemo(() => enabledTaskTypes.find((t) => t.key.toLowerCase() === "feature")?.key || enabledTaskTypes[0]?.key || "", [enabledTaskTypes]);
  const defaultPriorityKey = useMemo(
    () => enabledPriorities.find((p) => p.key.toLowerCase() === "p2")?.key || enabledPriorities[0]?.key || "",
    [enabledPriorities]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const active = document.activeElement as HTMLElement | null;
      if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable)) return;
      if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === "n" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        if (!board?.id) return;
        e.preventDefault();
        setNewTaskOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [board?.id]);

  useEffect(() => {
    if (!board?.id) return;
    api
      .jiraSyncRuns(board.id)
      .then((runs) => {
        const last = runs[0];
        if (!last) {
          setSyncBadge({ text: "No sync", variant: "muted" });
          return;
        }
        setSyncBadge({ text: last.status === "success" ? "Synced" : "Sync error", variant: last.status === "success" ? "ok" : "danger" });
      })
      .catch(() => setSyncBadge({ text: "Sync?", variant: "muted" }));
  }, [board?.id]);

  useEffect(() => {
    if (!board?.id) return;
    const sorted = [...lanes].sort((a, b) => a.position - b.position);
    const defaultLaneId =
      (newTask.laneId && sorted.some((l) => l.id === newTask.laneId) ? newTask.laneId : "") ||
      sorted.find((l) => l.type === "backlog")?.id ||
      sorted[0]?.id ||
      "";
    setNewTask((t: any) => ({
      ...t,
      laneId: defaultLaneId,
      priority: t.priority || defaultPriorityKey || t.priority,
      type: t.type || defaultTypeKey || t.type
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [board?.id, lanes.length, defaultPriorityKey, defaultTypeKey]);

  const refreshNotifs = async () => {
    setNotifLoading(true);
    try {
      const list = await api.inappNotifications({ limit: 50 });
      setNotifs(list);
    } catch {
      // ignore (session may be invalid during navigation)
    } finally {
      setNotifLoading(false);
    }
  };

  useEffect(() => {
    const saved = (typeof window !== "undefined" ? window.localStorage.getItem("nl-theme") : null) as "dark" | "light" | null;
    const mode = saved === "light" ? "light" : "dark";
    setTheme(mode);
    document.documentElement.setAttribute("data-theme", mode);
    applyLightPaletteFromStorage();
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    if (typeof window !== "undefined") window.localStorage.setItem("nl-theme", theme);
  }, [theme]);

  useEffect(() => {
    refreshNotifs();
    const t = window.setInterval(refreshNotifs, 15000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    rec.onresult = (event: any) => {
      let interim = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = String(event.results[i][0]?.transcript || "");
        if (event.results[i].isFinal) finalText += transcript;
        else interim += transcript;
      }
      const text = (finalText || interim).trim();
      if (!text) return;
      setNewTask((t) => ({ ...t, title: text }));
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
  }, []);

  const toggleVoiceCapture = () => {
    if (!voiceRef.current) return;
    try {
      if (voiceListening) voiceRef.current.stop();
      else voiceRef.current.start();
    } catch {
      toast.error("Voice input unavailable on this device.");
    }
  };

  const boardMenu = useMemo(
    () =>
      boards.map((b) => (
        <DropdownMenuItem key={b.id} onSelect={() => selectBoard(b.id)}>
          {b.name}
        </DropdownMenuItem>
      )),
    [boards, selectBoard]
  );

  return (
    <div data-testid="topbar" className="sticky top-0 z-[60]">
      <div className="px-3 py-2 md:h-14 flex flex-col md:flex-row md:items-center gap-2 md:gap-3 bg-bg/30 backdrop-blur-xl border-b border-white/10">
      <div className="flex items-center gap-2 min-w-0">
        <Link
          href="/app/home"
          className="hidden md:inline-flex h-10 w-10 rounded-2xl border border-accent/25 bg-accent/10 shadow-neon items-center justify-center hover:bg-white/5 transition"
          aria-label="Task-Daddy"
        >
          <TaskDaddyLogo size={26} />
        </Link>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              data-testid="board-menu-trigger"
              className="glass rounded-2xl px-3 h-10 flex items-center gap-2 border border-white/10 hover:bg-white/5 transition min-w-0"
            >
              <div className="text-sm font-medium truncate max-w-[46vw] md:max-w-[380px]">{boardLabel}</div>
              <ChevronDown size={16} className="text-muted" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {boardMenu}
            <DropdownMenuSeparator />
            <Dialog>
              <DialogTrigger asChild>
                <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                  <Plus size={16} /> Create board
                </DropdownMenuItem>
              </DialogTrigger>
              <DialogContent>
                <div className="text-lg font-semibold">Create board</div>
                <div className="mt-3 space-y-2">
                  <div className="text-xs text-muted">Name</div>
                  <Input value={newBoardName} onChange={(e) => setNewBoardName(e.target.value)} />
                  <div className="mt-3 flex gap-2 justify-end">
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setNewBoardName("New Board");
                      }}
                    >
                      Reset
                    </Button>
                    <Button
                      onClick={async () => {
                        await createBoard(newBoardName);
                      }}
                    >
                      Create
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </DropdownMenuContent>
        </DropdownMenu>

        <Badge variant={syncBadge.variant}>
          <RefreshCw size={12} /> {syncBadge.text}
        </Badge>
        <button
          aria-label="Toggle theme"
          className="glass rounded-2xl px-3 h-10 flex items-center gap-2 border border-white/10 hover:bg-white/5 transition"
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          <span className="hidden md:inline text-xs">{theme === "dark" ? "Light" : "Dark"}</span>
        </button>
        <Dialog open={notifOpen} onOpenChange={(v) => (setNotifOpen(v), v ? refreshNotifs() : null)}>
          <DialogTrigger asChild>
            <button className="relative glass rounded-2xl px-3 h-10 flex items-center gap-2 border border-white/10 hover:bg-white/5 transition">
              <Bell size={16} />
              {unreadCount ? (
                <span className="absolute -top-1 -right-1 h-5 min-w-5 px-1 rounded-full bg-accent text-black text-xs flex items-center justify-center">
                  {unreadCount}
                </span>
              ) : null}
            </button>
          </DialogTrigger>
          <DialogContent>
            <div className="flex items-center justify-between gap-3">
              <div className="text-lg font-semibold">Notifications</div>
              <Button
                size="sm"
                variant="ghost"
                disabled={notifLoading || unreadCount === 0}
                onClick={async () => {
                  try {
                    await api.markAllNotificationsRead();
                    await refreshNotifs();
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Mark all read
              </Button>
            </div>
            <div className="mt-3 max-h-[60vh] overflow-auto pr-1 scrollbar">
              {notifLoading ? (
                <div className="text-sm text-muted">Loading…</div>
              ) : notifs.length ? (
                <div className="space-y-2">
                  {notifs.map((n) => (
                    <button
                      key={n.id}
                      className="w-full text-left rounded-2xl border border-white/10 bg-white/5 hover:bg-white/10 transition p-3"
                      onClick={async () => {
                        if (!n.readAt) {
                          await api.markNotificationsRead([n.id]);
                          await refreshNotifs();
                        }
                        if (n.entityType === "Task" && n.entityId) {
                          router.push(`/app/board?task=${encodeURIComponent(n.entityId)}`);
                          setNotifOpen(false);
                        }
                      }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="text-sm font-medium">{n.title}</div>
                        <div className="flex items-center gap-1">
                          {n.taxonomy === "action_required" ? <Badge variant="warn">Action</Badge> : null}
                          {n.taxonomy === "system" ? <Badge variant="muted">System</Badge> : null}
                          {Number(n.burstCount || 1) > 1 ? <Badge variant="accent">x{Number(n.burstCount)}</Badge> : null}
                          {!n.readAt ? <Badge variant="accent">New</Badge> : <Badge variant="muted">Read</Badge>}
                        </div>
                      </div>
                      <div className="mt-1 text-sm text-muted whitespace-pre-wrap">{n.body}</div>
                      <div className="mt-2 text-xs text-muted">{n.createdAt}</div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted">No notifications.</div>
              )}
            </div>
          </DialogContent>
        </Dialog>
        <div className="flex-1" />
        <div className="md:hidden">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="glass rounded-2xl px-3 h-10 flex items-center gap-2 border border-white/10 hover:bg-white/5 transition">
                <div className="text-sm">{user?.name || "User"}</div>
                <ChevronDown size={16} className="text-muted" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onSelect={() => {
                  router.push("/app/settings");
                }}
              >
                <Settings size={16} /> Settings
              </DropdownMenuItem>
              {user?.role === "admin" ? (
                <DropdownMenuItem
                  onSelect={() => {
                    router.push("/app/settings/users");
                  }}
                >
                  <Shield size={16} /> Admin
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuItem
                onSelect={() => {
                  router.push("/app/integrations/jira");
                }}
              >
                <ExternalLink size={16} /> Jira
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => {
                  router.push("/app/reports");
                }}
              >
                <Layers size={16} /> Reports
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => {
                  router.push("/app/help");
                }}
              >
                <BookOpen size={16} /> Help
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => {
                  toast.message("Keyboard shortcuts", {
                    description: "/ search • n new task • esc close drawer"
                  });
                }}
              >
                <Sparkles size={16} /> Shortcuts
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={async () => {
                  await logout();
                }}
              >
                <LogOut size={16} /> Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="flex-1 min-w-0">
        <Input
          ref={searchRef}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tasks…  ( / )"
          className="glass border-white/10"
        />
      </div>

      {board?.id ? (
        <Dialog open={newTaskOpen} onOpenChange={setNewTaskOpen}>
          <DialogTrigger asChild>
            <Button variant="ghost">
              <Plus size={16} /> New (n)
            </Button>
          </DialogTrigger>
          <DialogContent>
            <div className="text-lg font-semibold">New task</div>
            <div className="mt-3 space-y-2">
              <div className="text-xs text-muted">Title</div>
              <div className="flex items-center gap-2">
                <Input
                  autoFocus
                  value={newTask.title}
                  onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                  placeholder="Ship motion UI improvements"
                />
                <Button
                  size="sm"
                  variant={voiceListening ? "danger" : "ghost"}
                  disabled={!voiceSupported}
                  onClick={toggleVoiceCapture}
                  aria-label="Dictate task title"
                >
                  {voiceListening ? <MicOff size={15} /> : <Mic size={15} />}
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-3 mt-3">
                <div>
                  <div className="text-xs text-muted">Lane</div>
                  <select
                    className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                    value={newTask.laneId}
                    onChange={(e) => setNewTask({ ...newTask, laneId: e.target.value })}
                  >
                    {[...lanes]
                      .sort((a, b) => a.position - b.position)
                      .map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.name}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <div className="text-xs text-muted">Owner</div>
                  <select
                    className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                    value={newTask.ownerId}
                    onChange={(e) => setNewTask({ ...newTask, ownerId: e.target.value })}
                  >
                    <option value="">Unassigned</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-xs text-muted">Priority</div>
                  <select
                    className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                    value={newTask.priority}
                    onChange={(e) => setNewTask({ ...newTask, priority: e.target.value })}
                  >
                    {enabledPriorities.map((p) => (
                      <option key={p.key} value={p.key}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="text-xs text-muted">Type</div>
                  <select
                    className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                    value={newTask.type}
                    onChange={(e) => setNewTask({ ...newTask, type: e.target.value })}
                  >
                    {enabledTaskTypes.map((t) => (
                      <option key={t.key} value={t.key}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <div className="text-xs text-muted">Due date</div>
                <Input type="date" value={newTask.dueDate} onChange={(e) => setNewTask({ ...newTask, dueDate: e.target.value })} placeholder="YYYY-MM-DD" />
              </div>

              <div className="flex justify-end mt-3 gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setNewTask({ title: "", laneId: newTask.laneId, priority: defaultPriorityKey || "", type: defaultTypeKey || "", ownerId: "", dueDate: "" });
                    setNewTaskOpen(false);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={async () => {
                    const sorted = [...lanes].sort((a, b) => a.position - b.position);
                    const safeLaneId =
                      (newTask.laneId && sorted.some((l) => l.id === newTask.laneId) ? newTask.laneId : "") ||
                      sorted.find((l) => l.type === "backlog")?.id ||
                      sorted[0]?.id ||
                      "";
                    if (!safeLaneId) {
                      toast.error("No valid lane available for this board");
                      return;
                    }
                    await createTask({
                      laneId: safeLaneId,
                      title: newTask.title || "New task",
                      priority: newTask.priority,
                      type: newTask.type,
                      ownerId: newTask.ownerId || null,
                      dueDate: isoOrNull(newTask.dueDate)
                    });
                    setNewTask({ title: "", laneId: safeLaneId, priority: defaultPriorityKey || "", type: defaultTypeKey || "", ownerId: "", dueDate: "" });
                    setNewTaskOpen(false);
                  }}
                >
                  Create
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      ) : null}

      {board?.id ? (
        <Dialog open={aiOpen} onOpenChange={setAiOpen}>
          <DialogTrigger asChild>
            <Button variant="ghost">
              <Sparkles size={16} /> AI
            </Button>
          </DialogTrigger>
          <DialogContent>
            <div className="text-lg font-semibold">Board AI</div>
            <div className="mt-1 text-xs text-muted">
              Runs suggestions against this board. Nothing changes until you click <span className="text-text">Apply</span>.
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                variant="ghost"
                disabled={aiLoading}
                onClick={async () => {
                  if (!board?.id) return;
                  setAiLoading(true);
                  try {
                    const res = await api.aiBoard(board.id, "triage-unassigned");
                    setAiText(res.text);
                    setAiSuggestions(res.suggestions || []);
                    setAiCreates(res.creates || []);
                    const selected: Record<string, boolean> = {};
                    for (const s of res.suggestions || []) selected[s.taskId] = true;
                    setAiSelected(selected);
                    setAiCreateSelected({});
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  } finally {
                    setAiLoading(false);
                  }
                }}
              >
                Triage unassigned
              </Button>
              <Button
                variant="ghost"
                disabled={aiLoading}
                onClick={async () => {
                  if (!board?.id) return;
                  setAiLoading(true);
                  try {
                    const res = await api.aiBoard(board.id, "prioritize");
                    setAiText(res.text);
                    setAiSuggestions(res.suggestions || []);
                    setAiCreates(res.creates || []);
                    const selected: Record<string, boolean> = {};
                    for (const s of res.suggestions || []) selected[s.taskId] = true;
                    setAiSelected(selected);
                    setAiCreateSelected({});
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  } finally {
                    setAiLoading(false);
                  }
                }}
              >
                Prioritize
              </Button>
              <Button
                variant="ghost"
                disabled={aiLoading}
                onClick={async () => {
                  if (!board?.id) return;
                    setAiLoading(true);
                  try {
                    const res = await api.aiBoard(board.id, "breakdown");
                    setAiText(res.text);
                    setAiSuggestions(res.suggestions || []);
                    setAiCreates(res.creates || []);
                    setAiSelected({});
                    const selected: Record<string, boolean> = {};
                    for (const g of res.creates || []) {
                      for (let i = 0; i < (g.tasks || []).length; i++) selected[`${g.parentTaskId}:${i}`] = true;
                    }
                    setAiCreateSelected(selected);
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  } finally {
                    setAiLoading(false);
                  }
                }}
              >
                Break down big tasks
              </Button>
            </div>
            <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3 text-sm whitespace-pre-wrap min-h-24">
              {aiLoading ? "Thinking…" : aiText || "Run an action."}
            </div>

            {aiSuggestions.length ? (
              <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold">Suggested changes</div>
                  <Button
                    size="sm"
                    disabled={aiLoading || !Object.values(aiSelected).some(Boolean)}
                    onClick={async () => {
                      if (!board?.id) return;
                      const toApply = aiSuggestions.filter((s) => aiSelected[s.taskId]);
                      if (!toApply.length) return;
                      const ok = confirm(`Apply ${toApply.length} change(s) to tasks?`);
                      if (!ok) return;
                      try {
                        for (const s of toApply) {
                          const t = tasks.find((x) => x.id === s.taskId);
                          const version = t?.version ?? 0;
                          await updateTask(s.taskId, { version, ...(s.patch || {}) });
                        }
                        toast.success("Applied");
                        await refreshAll();
                      } catch (e: any) {
                        toast.error(String(e?.message || e));
                      }
                    }}
                  >
                    Apply selected
                  </Button>
                </div>
                <div className="mt-3 space-y-2 max-h-56 overflow-auto pr-1 scrollbar">
                  {aiSuggestions.map((s) => {
                    const t = tasks.find((x) => x.id === s.taskId);
                    const patch = s.patch || {};
                    const ownerId = patch.ownerId as string | undefined;
                    const priority = patch.priority as string | undefined;
                    const ownerName = ownerId ? users.find((u) => u.id === ownerId)?.name || ownerId : null;
                    const label = ownerName
                      ? `Set owner → ${ownerName}`
                      : priority
                      ? `Set priority → ${priority}`
                      : `Update task`;
                    return (
                      <label key={`${s.taskId}:${label}`} className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={aiSelected[s.taskId] !== false}
                          onChange={(e) => setAiSelected((prev) => ({ ...prev, [s.taskId]: e.target.checked }))}
                        />
                        <div className="min-w-0">
                          <div className="font-medium truncate">{t?.title || s.taskId}</div>
                          <div className="text-xs text-muted">{label}{s.reason ? ` • ${s.reason}` : ""}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {aiCreates.length ? (
              <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold">Suggested new tasks</div>
                  <Button
                    size="sm"
                    disabled={aiLoading || !Object.values(aiCreateSelected).some(Boolean)}
                    onClick={async () => {
                      if (!board?.id) return;
                      const flat: Array<{ parentTaskId: string; idx: number; task: any }> = [];
                      for (const g of aiCreates) {
                        for (let i = 0; i < (g.tasks || []).length; i++) {
                          const key = `${g.parentTaskId}:${i}`;
                          if (!aiCreateSelected[key]) continue;
                          flat.push({ parentTaskId: g.parentTaskId, idx: i, task: g.tasks[i] });
                        }
                      }
                      if (!flat.length) return;
                      const ok = confirm(`Create ${flat.length} new task(s) in Backlog?`);
                      if (!ok) return;
                      try {
                        let created = 0;
                        for (const it of flat) {
                          const title = String(it.task?.title || "").trim();
                          if (!title) continue;
                          const laneId = String(it.task?.laneId || "").trim();
                          if (!laneId) continue;
                          const tags: string[] = Array.isArray(it.task?.tags) ? it.task.tags : [];
                          const exists = tasks.some((t) => t.title === title && (t.tags || []).some((x) => tags.includes(x)));
                          if (exists) continue;
                          const tNew = await api.createTask(board.id, {
                            laneId,
                            title,
                            description: String(it.task?.description || ""),
                            tags,
                            priority: defaultPriorityKey || "P2",
                            type: defaultTypeKey || "Feature",
                            ownerId: null,
                            dueDate: null
                          });
                          created++;
                          if (it.parentTaskId) {
                            try {
                              await api.addDependency(it.parentTaskId, tNew.id);
                            } catch {
                              // dependency is best-effort
                            }
                          }
                        }
                        toast.success(created ? `Created ${created} task(s)` : "No new tasks created");
                        await refreshAll();
                      } catch (e: any) {
                        toast.error(String(e?.message || e));
                      }
                    }}
                  >
                    Create selected
                  </Button>
                </div>
                <div className="mt-3 space-y-2 max-h-56 overflow-auto pr-1 scrollbar">
                  {aiCreates.flatMap((g: any) =>
                    (g.tasks || []).map((t: any, i: number) => {
                      const key = `${g.parentTaskId}:${i}`;
                      const parent = tasks.find((x) => x.id === g.parentTaskId);
                      return (
                        <label key={key} className="flex items-start gap-2 text-sm">
                          <input
                            type="checkbox"
                            className="mt-1"
                            checked={aiCreateSelected[key] !== false}
                            onChange={(e) => setAiCreateSelected((prev) => ({ ...prev, [key]: e.target.checked }))}
                          />
                          <div className="min-w-0">
                            <div className="font-medium truncate">{t?.title || "New task"}</div>
                            <div className="text-xs text-muted truncate">
                              From: {parent?.title || g.parentTaskId}
                              {g.reason ? ` • ${g.reason}` : ""}
                            </div>
                          </div>
                        </label>
                      );
                    })
                  )}
                </div>
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      ) : null}

      <div className="hidden md:block">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost">
              <Layers size={16} /> Reports
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onSelect={() => {
                router.push("/app/reports");
              }}
            >
              <Layers size={16} /> Dashboard
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => {
                router.push("/app/settings/diagnostics");
              }}
            >
              <RefreshCw size={16} /> Diagnostics
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="hidden md:block">
        <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="glass rounded-2xl px-3 h-10 flex items-center gap-2 border border-white/10 hover:bg-white/5 transition">
            <div className="text-sm">{user?.name || "User"}</div>
            <ChevronDown size={16} className="text-muted" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => {
              router.push("/app/settings");
            }}
          >
            <Settings size={16} /> Settings
          </DropdownMenuItem>
              {user?.role === "admin" ? (
                <DropdownMenuItem
                  onSelect={() => {
                    router.push("/app/settings/users");
                  }}
                >
                  <Shield size={16} /> Admin
                </DropdownMenuItem>
              ) : null}
          <DropdownMenuItem
            onSelect={() => {
              router.push("/app/integrations/jira");
            }}
          >
            <ExternalLink size={16} /> Jira
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              router.push("/app/reports");
            }}
          >
            <Layers size={16} /> Reports
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              router.push("/app/help");
            }}
          >
            <BookOpen size={16} /> Help
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => {
              toast.message("Keyboard shortcuts", {
                description: "/ search • n new task • esc close drawer"
              });
            }}
          >
            <Sparkles size={16} /> Shortcuts
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={async () => {
              await logout();
            }}
          >
            <LogOut size={16} /> Logout
          </DropdownMenuItem>
        </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
    </div>
  );
}
