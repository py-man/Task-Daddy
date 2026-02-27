"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Calendar, CircleHelp, ExternalLink, Loader2, Plus, Save, X } from "lucide-react";
import { toast } from "sonner";
import { useBoard } from "@/components/board-context";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { getUiDesign } from "@/lib/ui-design";
import { recordRecentTask } from "@/lib/recent-tasks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

function isoOrNull(d: string) {
  if (!d) return null;
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toISOString();
}

function localDateTimeToIsoOrNull(v: string) {
  const s = String(v || "").trim();
  if (!s) return null;
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/);
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const h = Number(m[4]);
  const mi = Number(m[5]);
  const dt = new Date(y, mo - 1, d, h, mi, 0, 0);
  // Guard invalid rollovers (e.g., 2026-02-31T10:00).
  if (
    Number.isNaN(dt.getTime()) ||
    dt.getFullYear() !== y ||
    dt.getMonth() !== mo - 1 ||
    dt.getDate() !== d ||
    dt.getHours() !== h ||
    dt.getMinutes() !== mi
  ) {
    return null;
  }
  return dt.toISOString();
}

function defaultReminderLocalValue(minutesFromNow: number) {
  const dt = new Date(Date.now() + minutesFromNow * 60_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  // datetime-local expects YYYY-MM-DDTHH:MM
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
}

function Hint({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" className="inline-flex items-center text-muted hover:text-text" aria-label="Help">
          <CircleHelp size={13} />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">{text}</TooltipContent>
    </Tooltip>
  );
}

export function TaskDrawer({ taskId, onClose }: { taskId: string | null; onClose: () => void }) {
  const { board, boards, lanes, tasks, users, taskTypes, priorities, updateTask, moveTask, refreshAll } = useBoard();
  const { user: sessionUser } = useSession();
  const task = useMemo(() => tasks.find((t) => t.id === taskId) || null, [tasks, taskId]);
  const lane = useMemo(() => (task ? lanes.find((l) => l.id === task.laneId) || null : null), [lanes, task]);

  const [tab, setTab] = useState("details");
  const [saving, setSaving] = useState(false);
  const [reminderSaving, setReminderSaving] = useState(false);
  const [form, setForm] = useState<any>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiText, setAiText] = useState<string>("");
  const [aiStructured, setAiStructured] = useState<any | null>(null);
  const [aiAction, setAiAction] = useState<string>("summarize");
  const [checklist, setChecklist] = useState<any[] | null>(null);
  const [comments, setComments] = useState<any[] | null>(null);
  const [deps, setDeps] = useState<any[] | null>(null);
  const [depPick, setDepPick] = useState<string>("");
  const [activity, setActivity] = useState<any[] | null>(null);
  const [attachments, setAttachments] = useState<any[] | null>(null);
  const [reminders, setReminders] = useState<any[] | null>(null);
  const [reminderForm, setReminderForm] = useState<{
    scheduledLocal: string;
    recipient: "me" | "owner";
    external: boolean;
    note: string;
  }>({ scheduledLocal: defaultReminderLocalValue(60), recipient: "me", external: false, note: "" });
  const [members, setMembers] = useState<any[] | null>(null);
  const [allUsers, setAllUsers] = useState<any[] | null>(null);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [addMemberUserId, setAddMemberUserId] = useState("");
  const [addMemberRole, setAddMemberRole] = useState<"viewer" | "member" | "admin">("member");
  const [jiraConnections, setJiraConnections] = useState<any[] | null>(null);
  const [openprojectConnections, setOpenprojectConnections] = useState<any[] | null>(null);
  const [xBoardAction, setXBoardAction] = useState<"transfer" | "duplicate">("transfer");
  const [xBoardTargetBoardId, setXBoardTargetBoardId] = useState("");
  const [xBoardTargetLaneId, setXBoardTargetLaneId] = useState("");
  const [xBoardTargetLanes, setXBoardTargetLanes] = useState<any[]>([]);
  const [jiraForm, setJiraForm] = useState<{
    connectionId: string;
    projectKey: string;
    issueType: string;
    enableSync: boolean;
    assigneeMode: "projectDefault" | "taskOwner" | "unassigned" | "connectionDefault";
  }>({
    connectionId: "",
    projectKey: "INFRA",
    issueType: "Task",
    enableSync: true,
    assigneeMode: "connectionDefault"
  });
  const [openprojectForm, setOpenprojectForm] = useState<{
    connectionId: string;
    workPackageId: string;
    projectIdentifier: string;
    enableSync: boolean;
  }>({
    connectionId: "",
    workPackageId: "",
    projectIdentifier: "",
    enableSync: true
  });
  const [detailsLayout, setDetailsLayout] = useState<"core" | "focus" | "compact">("core");
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [isTabletLikely, setIsTabletLikely] = useState(false);
  const pencilCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const pencilDrawingRef = useRef(false);
  const pencilPointRef = useRef<{ x: number; y: number } | null>(null);
  const [pencilInkUsed, setPencilInkUsed] = useState(false);
  const [pencilCardInput, setPencilCardInput] = useState("");
  const [pencilCards, setPencilCards] = useState<Array<{ id: string; text: string; x: number; y: number }>>([]);
  const pencilDragRef = useRef<{ id: string; pointerId: number; offsetX: number; offsetY: number } | null>(null);

  const enabledTaskTypes = useMemo(
    () => (taskTypes || []).filter((t) => t.enabled !== false).slice().sort((a, b) => a.position - b.position),
    [taskTypes]
  );
  const enabledPriorities = useMemo(
    () => (priorities || []).filter((p) => p.enabled !== false).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );

  const priorityTone = (key: string) => {
    const r = enabledPriorities.find((p) => p.key === key)?.rank ?? 99;
    if (r <= 0) return "danger";
    if (r === 1) return "warn";
    if (r === 2) return "accent";
    return "muted";
  };
  const jiraProjects = ["INFRA", "PSS", "CRQ", "PROBMAN", "OPS_GOV", "OG"];

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem("nl-task-details-layout");
    if (saved === "focus" || saved === "compact" || saved === "core") {
      setDetailsLayout(saved);
      return;
    }
    const design = getUiDesign();
    if (design === "focus") setDetailsLayout("focus");
    else if (design === "command" || design === "jira") setDetailsLayout("compact");
    else setDetailsLayout("core");
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("nl-task-details-layout", detailsLayout);
  }, [detailsLayout]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const update = () => setIsMobileViewport(window.innerWidth < 1024);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    if (typeof navigator === "undefined") return;
    const platform = String((navigator as any).platform || "").toLowerCase();
    const touch = Number((navigator as any).maxTouchPoints || 0);
    const ua = String((navigator as any).userAgent || "").toLowerCase();
    const likelyIpad = platform.includes("ipad") || (platform.includes("mac") && touch > 1) || ua.includes("ipad");
    setIsTabletLikely(likelyIpad || (touch >= 2 && !isMobileViewport));
  }, [isMobileViewport]);

  useEffect(() => {
    setTab("details");
    setAiText("");
    setChecklist(null);
    setComments(null);
    setDeps(null);
    setActivity(null);
    setAttachments(null);
    setReminders(null);
    setReminderForm({ scheduledLocal: defaultReminderLocalValue(60), recipient: "me", external: false, note: "" });
    if (task) {
      setForm({
        laneId: task.laneId,
        title: task.title,
        description: task.description,
        ownerId: task.ownerId || "",
        priority: task.priority,
        type: task.type,
        tags: (task.tags || []).join(", "),
        dueDate: task.dueDate ? task.dueDate.slice(0, 10) : "",
        estimateMinutes: task.estimateMinutes ?? "",
        blocked: task.blocked,
        blockedReason: task.blockedReason || ""
      });
    } else {
      setForm(null);
    }
  }, [taskId]); // intentionally not depending on task snapshot

  useEffect(() => {
    if (isMobileViewport && tab === "copilot") {
      setTab("details");
    }
  }, [isMobileViewport, tab]);

  useEffect(() => {
    if (!task?.id) return;
    recordRecentTask(task.id);
  }, [task?.id]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const canvas = pencilCanvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    const dpr = Math.max(1, Math.floor(window.devicePixelRatio || 1));
    canvas.width = Math.floor(rect.width * dpr);
    canvas.height = Math.floor(220 * dpr);
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = "220px";
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, 220);
    ctx.fillStyle = "rgba(255,255,255,0.02)";
    ctx.fillRect(0, 0, rect.width, 220);
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    for (let y = 20; y < 220; y += 20) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(rect.width, y);
      ctx.stroke();
    }
  }, [taskId, tab, detailsLayout]);

  const drawAt = (x: number, y: number, pressure: number) => {
    const canvas = pencilCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const px = Math.max(0, Math.min(rect.width, x - rect.left));
    const py = Math.max(0, Math.min(220, y - rect.top));
    const prev = pencilPointRef.current;
    ctx.strokeStyle = "rgba(120, 196, 255, 0.95)";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = Math.max(1.2, Math.min(4.4, 1.2 + pressure * 2.8));
    if (prev) {
      ctx.beginPath();
      ctx.moveTo(prev.x, prev.y);
      ctx.lineTo(px, py);
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(px + 0.01, py + 0.01);
      ctx.stroke();
    }
    pencilPointRef.current = { x: px, y: py };
  };

  const clearPencilInk = () => {
    const canvas = pencilCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, 220);
    ctx.fillStyle = "rgba(255,255,255,0.02)";
    ctx.fillRect(0, 0, rect.width, 220);
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    for (let y = 20; y < 220; y += 20) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(rect.width, y);
      ctx.stroke();
    }
    setPencilInkUsed(false);
  };

  const addPencilCard = () => {
    const text = pencilCardInput.trim();
    if (!text) return;
    const next = {
      id: `pc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      text,
      x: 12 + (pencilCards.length % 3) * 115,
      y: 12 + Math.floor(pencilCards.length / 3) * 80,
    };
    setPencilCards((prev) => [...prev, next]);
    setPencilCardInput("");
  };

  const appendPencilToDescription = async () => {
    if (!task || !form) return;
    const stamp = new Date().toISOString();
    const lines = [
      "",
      "## Pencil Notes",
      `- Captured at: ${stamp}`,
      `- Ink captured: ${pencilInkUsed ? "yes" : "no"}`,
      ...pencilCards.map((c) => `- ${c.text}`),
    ];
    const nextDescription = `${form.description || ""}\n${lines.join("\n")}`.trim();
    setSaving(true);
    try {
      const latest = await api.task(task.id);
      const t = await updateTask(task.id, { version: latest.version, description: nextDescription });
      setForm({ ...form, description: t.description });
      toast.success("Pencil notes appended to description");
      setTab("details");
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setSaving(false);
    }
  };

  const open = Boolean(taskId);

  const loadDetailsSidecars = async () => {
    if (!taskId) return;
    try {
      const [cl, cm, dp, at, rm] = await Promise.all([
        api.checklist(taskId),
        api.comments(taskId),
        api.dependencies(taskId),
        api.attachments(taskId),
        api.taskReminders(taskId)
      ]);
      setChecklist(cl);
      setComments(cm);
      setDeps(dp);
      setAttachments(at);
      setReminders(rm);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  const loadMembersAndUsers = async () => {
    if (!board?.id) return;
    try {
      const [ms, us] = await Promise.all([api.boardMembers(board.id), api.users()]);
      setMembers(ms);
      setAllUsers(us);
      const memberIds = new Set(ms.map((m: any) => m.userId));
      const firstCandidate = us.find((u: any) => !memberIds.has(u.id));
      setAddMemberUserId(firstCandidate?.id || "");
    } catch (e: any) {
      // don't toast here; it is called in background during drawer open
    }
  };

  const loadActivity = async () => {
    if (!board?.id || !taskId) return;
    try {
      const ev = await api.audit(board.id, taskId);
      setActivity(ev);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  useEffect(() => {
    if (open) {
      loadDetailsSidecars();
      loadMembersAndUsers();
      const fallbackBoard = boards.find((b) => b.id !== board?.id);
      setXBoardTargetBoardId(fallbackBoard?.id || "");
      setXBoardTargetLaneId("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, taskId, board?.id, boards.length]);

  useEffect(() => {
    if (!xBoardTargetBoardId) {
      setXBoardTargetLanes([]);
      setXBoardTargetLaneId("");
      return;
    }
    api
      .lanes(xBoardTargetBoardId)
      .then((ls) => {
        const sorted = [...ls].sort((a, b) => a.position - b.position);
        setXBoardTargetLanes(sorted);
        if (sorted.length > 0) {
          const backlog = sorted.find((l) => l.type === "backlog");
          setXBoardTargetLaneId(backlog?.id || sorted[0].id);
        } else {
          setXBoardTargetLaneId("");
        }
      })
      .catch(() => {
        setXBoardTargetLanes([]);
        setXBoardTargetLaneId("");
      });
  }, [xBoardTargetBoardId]);

  useEffect(() => {
    if (tab === "activity") loadActivity();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  useEffect(() => {
    if (tab !== "jira") return;
    api
      .jiraConnections()
      .then((cs) => {
        setJiraConnections(cs);
        if (cs[0] && !jiraForm.connectionId) setJiraForm((f) => ({ ...f, connectionId: cs[0].id }));
      })
      .catch((e: any) => toast.error(String(e?.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  useEffect(() => {
    if (tab !== "openproject") return;
    api
      .openprojectConnections()
      .then((cs) => {
        setOpenprojectConnections(cs);
        if (cs[0] && !openprojectForm.connectionId) {
          setOpenprojectForm((f) => ({
            ...f,
            connectionId: cs[0].id,
            projectIdentifier: f.projectIdentifier || cs[0].projectIdentifier || ""
          }));
        }
      })
      .catch((e: any) => toast.error(String(e?.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const save = async () => {
    if (!task || !form) return;
    const est = form.estimateMinutes === "" ? null : Number(form.estimateMinutes);
    if (est !== null && Number.isNaN(est)) {
      toast.error("Estimate must be a number (minutes).");
      return;
    }
    setSaving(true);
    try {
      const latest = await api.task(task.id);
      let v = latest.version;
      if (form.laneId && form.laneId !== latest.laneId) {
        const toIndex = tasks.filter((t) => t.laneId === form.laneId).length;
        const moved = await moveTask(task.id, { laneId: form.laneId, toIndex, version: v });
        v = moved.version;
      }
      const updated = await updateTask(task.id, {
        version: v,
        title: form.title,
        description: form.description,
        ownerId: form.ownerId || null,
        priority: form.priority,
        type: form.type,
        tags: String(form.tags || "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        dueDate: isoOrNull(form.dueDate),
        estimateMinutes: est,
        blocked: Boolean(form.blocked),
        blockedReason: form.blocked ? form.blockedReason || "" : null
      });
      setForm((prev: any) =>
        prev
          ? {
              ...prev,
              title: updated.title,
              description: updated.description,
              ownerId: updated.ownerId || "",
              priority: updated.priority,
              type: updated.type,
              tags: (updated.tags || []).join(", "),
              dueDate: updated.dueDate ? String(updated.dueDate).slice(0, 10) : "",
              estimateMinutes: updated.estimateMinutes ?? "",
              blocked: updated.blocked,
              blockedReason: updated.blockedReason || ""
            }
          : prev
      );
      toast.success("Saved");
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setSaving(false);
    }
  };

  const applyAiToDescriptionAndSave = async () => {
    if (!task || !form || !aiText) return;
    setSaving(true);
    try {
      const latest = await api.task(task.id);
      const t = await updateTask(task.id, { version: latest.version, description: aiText });
      setForm({ ...form, description: t.description });
      toast.success("Applied to description");
      setTab("details");
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setSaving(false);
    }
  };

  const addAiAsComment = async () => {
    if (!taskId || !aiText) return;
    try {
      await api.addComment(taskId, aiText);
      toast.success("Added comment");
      await loadDetailsSidecars();
      setTab("details");
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  const runAI = async (action: string) => {
    if (!taskId) return;
    if (!isMobileViewport) setTab("copilot");
    setAiLoading(true);
    setAiAction(action);
    setAiStructured(null);
    try {
      const out = await api.aiTask(taskId, action);
      setAiText(out.text);
      if (out.intent || out.qualityScore) setAiStructured(out);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setAiLoading(false);
    }
  };

  const enhanceTicket = async () => {
    if (!taskId) return;
    if (!isMobileViewport) setTab("copilot");
    setAiLoading(true);
    setAiAction("enhance");
    try {
      const [enhance, rewrite, checklistOut, risk] = await Promise.all([
        api.aiTask(taskId, "enhance"),
        api.aiTask(taskId, "rewrite"),
        api.aiTask(taskId, "checklist"),
        api.aiTask(taskId, "risk"),
      ]);
      const checklistLines = String(checklistOut.text || "")
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.startsWith("- "))
        .map((line) => line.replace(/^- /, ""));
      setAiStructured(enhance.intent || enhance.qualityScore ? enhance : null);
      setAiText([enhance.text, "", rewrite.text, "", "Checklist suggestions:", ...checklistLines.map((l) => `- ${l}`), "", risk.text].join("\n"));
      toast.success("AI enhancement ready for preview. Nothing was applied yet.");
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setAiLoading(false);
    }
  };

  const applyChecklistFromText = async () => {
    if (!taskId || !aiText) return;
    const lines = aiText
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.startsWith("- "));
    if (lines.length === 0) {
      toast.error("No checklist items found in AI output");
      return;
    }
    for (const l of lines) {
      // eslint-disable-next-line no-await-in-loop
      await api.addChecklist(taskId, l.replace(/^- /, ""));
    }
    toast.success(`Added ${lines.length} checklist items`);
    await loadDetailsSidecars();
    setTab("details");
  };

  const myBoardRole = useMemo(() => {
    if (!members || !sessionUser?.id) return null;
    const m = members.find((x: any) => x.userId === sessionUser.id);
    return m?.role || null;
  }, [members, sessionUser?.id]);

  const canManageMembers = myBoardRole === "admin";

  const addMemberCandidates = useMemo(() => {
    if (!allUsers) return [];
    const memberIds = new Set((members || []).map((m: any) => m.userId));
    return allUsers.filter((u: any) => !memberIds.has(u.id));
  }, [allUsers, members]);

  const ownerOptions = (allUsers && allUsers.length ? allUsers : users).map((u: any) => (
    <option key={u.id} value={u.id}>
      {u.name} ({u.role})
    </option>
  ));
  const isFocusLayout = detailsLayout === "focus";
  const isCompactLayout = detailsLayout === "compact";
  const topFormGridClass = isCompactLayout ? "grid grid-cols-2 gap-2" : "grid grid-cols-2 gap-3";
  const splitGridClass =
    isFocusLayout ? "grid grid-cols-1 gap-3" : isCompactLayout ? "grid grid-cols-2 gap-2" : "grid grid-cols-2 gap-3";
  const drawerClass = isMobileViewport
    ? "nl-task-drawer fixed inset-0 glass shadow-neon border border-white/10 overflow-hidden flex flex-col z-[310]"
    : isFocusLayout
      ? "nl-task-drawer fixed inset-0 md:inset-0 md:left-[7vw] md:right-[7vw] md:top-4 md:bottom-4 glass md:rounded-3xl shadow-neon border border-white/10 overflow-hidden flex flex-col z-[310]"
      : isCompactLayout
        ? "nl-task-drawer fixed inset-0 md:right-3 md:top-3 md:bottom-3 md:left-auto md:w-[440px] md:max-w-[90vw] glass md:rounded-3xl shadow-neon border border-white/10 overflow-hidden flex flex-col z-[310]"
        : "nl-task-drawer fixed inset-0 md:right-3 md:top-3 md:bottom-3 md:left-auto md:w-[520px] md:max-w-[92vw] glass md:rounded-3xl shadow-neon border border-white/10 overflow-hidden flex flex-col z-[310]";

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 bg-black/55 backdrop-blur-sm z-[300]" />
        <DialogPrimitive.Content asChild>
          <motion.div
            initial={isMobileViewport ? { y: 56, opacity: 0, scale: 0.995 } : { x: 64, opacity: 0, rotateY: 7, scale: 0.985 }}
            animate={isMobileViewport ? { y: 0, opacity: 1, scale: 1 } : { x: 0, opacity: 1, rotateY: 0, scale: 1 }}
            exit={isMobileViewport ? { y: 48, opacity: 0, scale: 0.996 } : { x: 52, opacity: 0, rotateY: 6, scale: 0.992 }}
            transition={{ type: "spring", stiffness: 360, damping: 30, mass: 0.82 }}
            className={drawerClass}
            style={{ transformPerspective: 1200 }}
          >
            {!task ? (
              <div className="p-5">
                <Skeleton className="h-6 w-2/3" />
                <Skeleton className="h-4 w-1/2 mt-3" />
                <Skeleton className="h-28 w-full mt-5" />
              </div>
            ) : (
              <>
                <div className="p-4 border-b border-white/10 flex items-start gap-2">
                  <div className="flex-1">
                    <div className="text-sm text-muted">
                      {lane ? (
                        <>
                          <span>{lane.name}</span> <span className="text-muted/60">•</span>{" "}
                          <span className="text-muted">{lane.type}</span>
                        </>
                      ) : (
                        "—"
                      )}
                    </div>
                    <div className="mt-1 text-lg font-semibold leading-tight">{task.title}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge variant="muted">{task.type}</Badge>
                      <Badge variant={priorityTone(task.priority)}>{task.priority}</Badge>
                      {task.blocked ? <Badge variant="danger">Blocked</Badge> : null}
                      {task.jiraKey ? <Badge variant="accent">{task.jiraKey}</Badge> : null}
                      {task.jiraKey && task.jiraUrl ? (
                        <a href={task.jiraUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-muted hover:text-text">
                          <ExternalLink size={14} /> Open in Jira
                        </a>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
                      <X size={16} />
                    </Button>
                    {tab === "details" && form ? (
                      <Button
                        variant="primary"
                        size="sm"
                        className="border-emerald-400/60 bg-[linear-gradient(180deg,rgba(52,211,153,0.26),rgba(16,185,129,0.14))] text-emerald-50 hover:bg-[linear-gradient(180deg,rgba(52,211,153,0.34),rgba(16,185,129,0.18))]"
                        onClick={save}
                        disabled={saving}
                      >
                        {saving ? <Loader2 className="animate-spin" size={14} /> : <Save size={14} />} Save
                      </Button>
                    ) : null}
                  </div>
                </div>

                <div className={cn("flex-1 overflow-y-auto scrollbar", isMobileViewport ? "p-3 pb-[max(14px,env(safe-area-inset-bottom))]" : "p-4")}>
                  <TooltipProvider>
                  <Tabs value={tab} onValueChange={setTab}>
                    <TabsList className={cn(isMobileViewport ? "grid grid-cols-5 gap-1" : "")}>
                      <TabsTrigger value="details">Details</TabsTrigger>
                      <TabsTrigger value="pencil">Pencil</TabsTrigger>
                      {!isMobileViewport ? <TabsTrigger value="copilot">Copilot</TabsTrigger> : null}
                      <TabsTrigger value="jira">Jira</TabsTrigger>
                      <TabsTrigger value="openproject">OpenProject</TabsTrigger>
                      <TabsTrigger value="activity">Activity</TabsTrigger>
                    </TabsList>
                    <div className="mt-2 text-[11px] text-muted flex items-center gap-2">
                      <Hint text="Details is local task data. Jira/OpenProject tabs are explicit sync actions." />
                      Preview and apply actions explicitly. Nothing auto-syncs without your click.
                    </div>

                    <TabsContent value="details" className="mt-4">
                      {!form ? null : (
                        <div className="space-y-4">
                          <div className={topFormGridClass}>
                            {!isMobileViewport ? (
                              <div className="col-span-2 flex justify-end">
                                <div className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-2 py-1">
                                  <span className="text-xs text-muted">Layout</span>
                                  <select
                                    className="h-8 rounded-lg bg-transparent border border-white/10 px-2 text-xs text-text outline-none"
                                    value={detailsLayout}
                                    onChange={(e) => setDetailsLayout(e.target.value as "core" | "focus" | "compact")}
                                  >
                                    <option value="core">Core</option>
                                    <option value="focus">Focus</option>
                                    <option value="compact">Compact</option>
                                  </select>
                                </div>
                              </div>
                            ) : null}
                            {isFocusLayout ? (
                              <div className="col-span-2 rounded-2xl border border-accent/25 bg-accent/10 p-2 text-xs text-muted">
                                Focus mode: centered editor + reduced visual noise. Collaboration blocks are collapsed below.
                              </div>
                            ) : null}
                            <div className="col-span-2 rounded-2xl border border-white/10 bg-white/5 p-2">
                              <div className="text-xs text-muted mb-2">Quick actions</div>
                              <div className="flex items-center gap-2">
                                <div className="flex flex-wrap items-center gap-2 min-w-0">
                                  {!isMobileViewport ? (
                                  <Button size="sm" variant="ghost" onClick={enhanceTicket} disabled={aiLoading || saving || !taskId}>
                                    Enhance
                                  </Button>
                                  ) : null}
                                  {task?.jiraKey ? (
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      disabled={saving}
                                      onClick={async () => {
                                        if (!taskId) return;
                                        try {
                                          setSaving(true);
                                          await api.taskJiraSync(taskId);
                                          await refreshAll();
                                          toast.success("Jira synced");
                                        } catch (e: any) {
                                          toast.error(String(e?.message || e));
                                        } finally {
                                          setSaving(false);
                                        }
                                      }}
                                    >
                                      Sync Jira
                                    </Button>
                                  ) : null}
                                  {task?.openprojectWorkPackageId ? (
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      disabled={saving}
                                      onClick={async () => {
                                        if (!taskId) return;
                                        try {
                                          setSaving(true);
                                          await api.taskOpenProjectSync(taskId);
                                          await refreshAll();
                                          toast.success("OpenProject synced");
                                        } catch (e: any) {
                                          toast.error(String(e?.message || e));
                                        } finally {
                                          setSaving(false);
                                        }
                                      }}
                                    >
                                      Sync OpenProject
                                    </Button>
                                  ) : null}
                                </div>
                              </div>
                              {!isMobileViewport && aiText ? (
                                <div className="mt-2 rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs flex items-center justify-between gap-2">
                                  <span>AI preview ready.</span>
                                  <Button size="sm" variant="ghost" onClick={() => setTab("copilot")}>
                                    Open Copilot
                                  </Button>
                                </div>
                              ) : null}
                            </div>
                            <div className="col-span-2">
                              <div className="text-xs text-muted mb-1 flex items-center gap-1">
                                Title <Hint text="Short actionable summary. Keep this outcome-oriented." />
                              </div>
                              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                            </div>
                            <div className="col-span-2">
                              <div className="text-xs text-muted mb-1 flex items-center gap-1">
                                Lane <Hint text="Changes workflow stage and board ordering context." />
                              </div>
                              <select
                                data-testid="task-lane"
                                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                value={form.laneId}
                                onChange={(e) => setForm({ ...form, laneId: e.target.value })}
                              >
                                {[...lanes]
                                  .slice()
                                  .sort((a, b) => a.position - b.position)
                                  .map((l) => (
                                    <option key={l.id} value={l.id}>
                                      {l.name}
                                    </option>
                                  ))}
                              </select>
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1 flex items-center justify-between gap-2">
                                <span>Owner</span>
                                {canManageMembers ? (
                                  <Dialog open={addMemberOpen} onOpenChange={setAddMemberOpen}>
                                    <DialogTrigger asChild>
                                      <button
                                        type="button"
                                        className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent/90"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <Plus size={12} />
                                        Add to board
                                      </button>
                                    </DialogTrigger>
                                    <DialogContent>
                                      <div className="text-lg font-semibold">Add board member</div>
                                      <div className="mt-1 text-sm text-muted">Members can be assigned tasks in this board.</div>
                                      <div className="mt-4 space-y-3">
                                        <div>
                                          <div className="text-xs text-muted mb-1">User</div>
                                          <select
                                            data-testid="task-add-member-user"
                                            className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text"
                                            value={addMemberUserId}
                                            onChange={(e) => setAddMemberUserId(e.target.value)}
                                          >
                                            {addMemberCandidates.length === 0 ? <option value="">No available users</option> : <option value="">Select user…</option>}
                                            {addMemberCandidates.map((u: any) => (
                                              <option key={u.id} value={u.id}>
                                                {u.name} ({u.email})
                                              </option>
                                            ))}
                                          </select>
                                        </div>
                                        <div>
                                          <div className="text-xs text-muted mb-1">Role</div>
                                          <select
                                            data-testid="task-add-member-role"
                                            className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text"
                                            value={addMemberRole}
                                            onChange={(e) => setAddMemberRole(e.target.value as any)}
                                          >
                                            {["viewer", "member", "admin"].map((r) => (
                                              <option key={r} value={r}>
                                                {r}
                                              </option>
                                            ))}
                                          </select>
                                        </div>
                                      </div>
                                      <div className="mt-5 flex justify-end gap-2">
                                        <Button variant="ghost" onClick={() => setAddMemberOpen(false)}>
                                          Cancel
                                        </Button>
                                        <Button
                                          variant="primary"
                                          disabled={!addMemberUserId || !board?.id}
                                          onClick={async () => {
                                            try {
                                              const u = (allUsers || []).find((x: any) => x.id === addMemberUserId);
                                              if (!u) return;
                                              await api.addBoardMember(board!.id, { email: u.email, role: addMemberRole });
                                              toast.success("Added to board");
                                              await refreshAll();
                                              setForm((f: any) => ({ ...f, ownerId: u.id }));
                                              setAddMemberOpen(false);
                                            } catch (e: any) {
                                              toast.error(String(e?.message || e));
                                            }
                                          }}
                                        >
                                          Add member
                                        </Button>
                                      </div>
                                    </DialogContent>
                                  </Dialog>
                                ) : null}
                              </div>
                              <select
                                className={cn(
                                  "h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                )}
                                value={form.ownerId}
                                onChange={(e) => setForm({ ...form, ownerId: e.target.value })}
                              >
                                <option value="">Unassigned</option>
                                {ownerOptions}
                              </select>
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1">Priority</div>
                              <select
                                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                value={form.priority}
                                onChange={(e) => setForm({ ...form, priority: e.target.value })}
                              >
                                {enabledPriorities.map((p) => (
                                  <option key={p.key} value={p.key}>
                                    {p.name}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1">Type</div>
                              <select
                                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                value={form.type}
                                onChange={(e) => setForm({ ...form, type: e.target.value })}
                              >
                                {enabledTaskTypes.map((t) => (
                                  <option key={t.key} value={t.key}>
                                    {t.name}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="col-span-2">
                              <div className="text-xs text-muted mb-1">Tags (comma separated)</div>
                              <Input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1 flex items-center justify-between gap-2">
                                <span className="inline-flex items-center gap-2">
                                  <Calendar size={14} /> Due date
                                  <Hint text="Required for ICS export/email and overdue calculations." />
                                </span>
                                <div className="inline-flex items-center gap-2">
                                  <button
                                    type="button"
                                    className="text-xs text-accent hover:underline"
                                    onClick={async () => {
                                      if (!taskId) return;
                                      if (!task?.dueDate) {
                                        toast.error("Save a due date first to export an .ics file.");
                                        return;
                                      }
                                      const to = (window.prompt("Email address for .ics (blank = use SMTP default recipient):", "") || "").trim();
                                      try {
                                        const out = await api.taskIcsEmail(taskId, { to: to || undefined });
                                        toast.success(`Sent .ics to ${out.to}`);
                                      } catch (e: any) {
                                        toast.error(String(e?.message || e));
                                      }
                                    }}
                                  >
                                    Email .ics
                                  </button>
                                  <button
                                    type="button"
                                    className="text-xs text-accent hover:underline"
                                    onClick={() => {
                                      if (!taskId) return;
                                      if (!task?.dueDate) {
                                        toast.error("Save a due date first to export an .ics file.");
                                        return;
                                      }
                                      window.location.href = `/api/tasks/${taskId}/ics`;
                                    }}
                                  >
                                    Export .ics
                                  </button>
                                </div>
                              </div>
                              <Input type="date" value={form.dueDate} onChange={(e) => setForm({ ...form, dueDate: e.target.value })} />
                            </div>
                            <div>
                              <div className="text-xs text-muted mb-1">Estimate (minutes)</div>
                              <Input
                                value={String(form.estimateMinutes)}
                                onChange={(e) => setForm({ ...form, estimateMinutes: e.target.value })}
                                placeholder="e.g. 90"
                              />
                            </div>
                            <div className="col-span-2 flex items-center gap-2">
                              <input
                                id="blocked"
                                type="checkbox"
                                checked={Boolean(form.blocked)}
                                onChange={(e) => setForm({ ...form, blocked: e.target.checked })}
                              />
                              <label htmlFor="blocked" className="text-sm">
                                Blocked
                              </label>
                            </div>
                            {form.blocked ? (
                              <div className="col-span-2">
                                <div className="text-xs text-muted mb-1">Blocked reason</div>
                                <Input value={form.blockedReason} onChange={(e) => setForm({ ...form, blockedReason: e.target.value })} />
                              </div>
                            ) : null}
                          </div>

                          <div>
                            <div className="text-xs text-muted mb-1">Description (Markdown)</div>
                            <textarea
                              className="min-h-28 w-full rounded-2xl bg-white/5 border border-white/10 p-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                              value={form.description}
                              onChange={(e) => setForm({ ...form, description: e.target.value })}
                            />
                            {detailsLayout === "compact" ? (
                              <div className="mt-2 text-xs text-muted">Preview hidden in compact mode.</div>
                            ) : (
                              <>
                                <div className="mt-2 text-xs text-muted">Preview</div>
                                <div className="mt-2 rounded-2xl border border-white/10 bg-white/5 p-3 text-sm">
                                  <ReactMarkdown>{form.description || "_No description_"}</ReactMarkdown>
                                </div>
                              </>
                            )}
                          </div>

                            <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                              <div className="text-sm font-semibold inline-flex items-center gap-1">
                                Cross-board actions <Hint text="Transfer moves this task. Duplicate copies it and keeps this task." />
                              </div>
                              <div className="mt-1 text-xs text-muted">Transfer this task or duplicate it into another board.</div>
                            <div className="mt-3 grid grid-cols-2 gap-3">
                              <div>
                                <div className="text-xs text-muted mb-1">Action</div>
                                <select
                                  className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                  value={xBoardAction}
                                  onChange={(e) => setXBoardAction(e.target.value as any)}
                                >
                                  <option value="transfer">Transfer</option>
                                  <option value="duplicate">Duplicate</option>
                                </select>
                              </div>
                              <div>
                                <div className="text-xs text-muted mb-1">Target board</div>
                                <select
                                  data-testid="task-cross-board-target"
                                  className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                  value={xBoardTargetBoardId}
                                  onChange={(e) => setXBoardTargetBoardId(e.target.value)}
                                >
                                  <option value="">Select board…</option>
                                  {boards
                                    .filter((b) => b.id !== board?.id)
                                    .map((b) => (
                                      <option key={b.id} value={b.id}>
                                        {b.name}
                                      </option>
                                    ))}
                                </select>
                              </div>
                              <div className="col-span-2">
                                <div className="text-xs text-muted mb-1">Target lane</div>
                                <select
                                  data-testid="task-cross-board-lane"
                                  className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                  value={xBoardTargetLaneId}
                                  onChange={(e) => setXBoardTargetLaneId(e.target.value)}
                                >
                                  <option value="">Select lane…</option>
                                  {xBoardTargetLanes.map((l: any) => (
                                    <option key={l.id} value={l.id}>
                                      {l.name}
                                    </option>
                                  ))}
                                </select>
                              </div>
                              <div className="col-span-2 flex justify-end">
                                <Button
                                  data-testid="task-cross-board-apply"
                                  variant="ghost"
                                  disabled={!xBoardTargetBoardId || !xBoardTargetLaneId || saving}
                                  onClick={async () => {
                                    if (!taskId || !xBoardTargetBoardId || !xBoardTargetLaneId) return;
                                    try {
                                      setSaving(true);
                                      if (xBoardAction === "transfer") {
                                        await api.transferTaskToBoard(taskId, {
                                          targetBoardId: xBoardTargetBoardId,
                                          targetLaneId: xBoardTargetLaneId,
                                          keepOwnerIfMember: true
                                        });
                                        toast.success("Task transferred");
                                        await refreshAll();
                                        onClose();
                                      } else {
                                        await api.duplicateTaskToBoard(taskId, {
                                          targetBoardId: xBoardTargetBoardId,
                                          targetLaneId: xBoardTargetLaneId,
                                          includeChecklist: true,
                                          includeComments: false,
                                          includeDependencies: true,
                                          keepOwnerIfMember: true
                                        });
                                        toast.success("Task duplicated");
                                        await refreshAll();
                                      }
                                    } catch (e: any) {
                                      toast.error(String(e?.message || e));
                                    } finally {
                                      setSaving(false);
                                    }
                                  }}
                                >
                                  {xBoardAction === "transfer" ? "Transfer task" : "Duplicate task"}
                                </Button>
                              </div>
                            </div>
                          </div>

                          <details className="rounded-2xl border border-white/10 bg-white/5 p-3" open={isMobileViewport || (!isFocusLayout && !isCompactLayout)}>
                            <summary className="cursor-pointer list-none flex items-center justify-between gap-2">
                              <div className="text-sm font-semibold">Remind me</div>
                              <div className="text-xs text-muted">In-app always • external uses Settings → Notifications</div>
                            </summary>
                            <div className="flex items-center justify-between gap-2">
                              <div />
                            </div>
                            <div className="mt-3 grid grid-cols-2 gap-3">
                              <div className="col-span-2">
                                <div className="text-xs text-muted mb-1">Time</div>
                                <Input
                                  data-testid="reminder-datetime"
                                  type="datetime-local"
                                  value={reminderForm.scheduledLocal}
                                  onChange={(e) => setReminderForm((f) => ({ ...f, scheduledLocal: e.target.value }))}
                                />
                              </div>
                              <div>
                                <div className="text-xs text-muted mb-1">Recipient</div>
                                <select
                                  data-testid="reminder-recipient"
                                  className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                  value={reminderForm.recipient}
                                  onChange={(e) => setReminderForm((f) => ({ ...f, recipient: e.target.value as any }))}
                                >
                                  <option value="me">Me</option>
                                  <option value="owner" disabled={!task?.ownerId}>
                                    Owner
                                  </option>
                                </select>
                              </div>
                              <div className="flex items-end gap-2">
                                <label className="flex items-center gap-2 text-sm">
                                  <input
                                    data-testid="reminder-external"
                                    type="checkbox"
                                    checked={reminderForm.external}
                                    onChange={(e) => setReminderForm((f) => ({ ...f, external: e.target.checked }))}
                                  />
                                  Also send external (email/pushover)
                                </label>
                              </div>
                              <div className="col-span-2">
                                <div className="text-xs text-muted mb-1">Note (optional)</div>
                                <Input value={reminderForm.note} onChange={(e) => setReminderForm((f) => ({ ...f, note: e.target.value }))} />
                              </div>
                              <div className="col-span-2 flex items-center justify-end gap-2">
                                <Button
                                  data-testid="reminder-create"
                                  variant="ghost"
                                  onClick={() => setReminderForm({ scheduledLocal: defaultReminderLocalValue(15), recipient: "me", external: false, note: "" })}
                                >
                                  +15m
                                </Button>
                                <Button
                                  data-testid="reminder-create-submit"
                                  disabled={reminderSaving || !taskId}
                                  onClick={async () => {
                                    if (!taskId) return;
                                    const scheduledAt = localDateTimeToIsoOrNull(reminderForm.scheduledLocal);
                                    if (!scheduledAt) {
                                      toast.error("Choose a valid reminder time.");
                                      return;
                                    }
                                    try {
                                      setReminderSaving(true);
                                      await api.createTaskReminder(taskId, {
                                        scheduledAt,
                                        recipient: reminderForm.recipient,
                                        channels: reminderForm.external ? ["inapp", "external"] : ["inapp"],
                                        note: reminderForm.note
                                      });
                                      toast.success("Reminder scheduled");
                                      await loadDetailsSidecars();
                                    } catch (e: any) {
                                      toast.error(String(e?.message || e));
                                    } finally {
                                      setReminderSaving(false);
                                    }
                                  }}
                                >
                                  Schedule
                                </Button>
                              </div>
                            </div>

                            <div className="mt-3">
                              {reminders === null ? (
                                <Skeleton className="h-12 w-full" />
                              ) : reminders.length === 0 ? (
                                <div className="text-xs text-muted">No reminders.</div>
                              ) : (
                                <div className="space-y-2">
                                  {reminders.slice(0, 10).map((r) => (
                                    <div key={r.id} className="rounded-2xl border border-white/10 bg-white/5 p-2 flex items-start justify-between gap-2">
                                      <div>
                                        <div className="text-sm">
                                          {new Date(r.scheduledAt).toLocaleString()}{" "}
                                          <span className="text-xs text-muted">• {String(r.status || "pending")}</span>
                                        </div>
                                        {r.note ? <div className="text-xs text-muted whitespace-pre-wrap">{r.note}</div> : null}
                                        <div className="mt-1 flex flex-wrap gap-1">
                                          {(r.channels || []).map((c: string) => (
                                            <Badge key={c} variant="muted">
                                              {c}
                                            </Badge>
                                          ))}
                                        </div>
                                      </div>
                                      <div className="flex items-center gap-2">
                                        {String(r.status) === "pending" ? (
                                          <Button
                                            data-testid={`reminder-cancel-${r.id}`}
                                            variant="ghost"
                                            size="sm"
                                            disabled={reminderSaving}
                                            onClick={async () => {
                                              try {
                                                setReminderSaving(true);
                                                await api.cancelTaskReminder(r.id);
                                                toast.success("Canceled");
                                                await loadDetailsSidecars();
                                              } catch (e: any) {
                                                toast.error(String(e?.message || e));
                                              } finally {
                                                setReminderSaving(false);
                                              }
                                            }}
                                          >
                                            Cancel
                                          </Button>
                                        ) : null}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </details>

                          <details className="rounded-2xl border border-white/10 bg-white/5 p-3" open={isMobileViewport || (!isFocusLayout && !isCompactLayout)}>
                            <summary className="cursor-pointer list-none flex items-center justify-between gap-2">
                              <div className="text-sm font-semibold">Checklist + Comments</div>
                              <div className="text-xs text-muted">Expand to view and edit</div>
                            </summary>
                          <div className={`${splitGridClass} mt-3`}>
                            <div>
                              <div className="text-sm font-semibold">Checklist</div>
                              {checklist === null ? (
                                <Skeleton className="h-20 w-full mt-2" />
                              ) : checklist.length === 0 ? (
                                <div className="text-xs text-muted mt-2">No checklist items.</div>
                              ) : (
                                <div className="mt-2 space-y-2">
                                  {checklist.map((i) => (
                                    <label key={i.id} className="flex items-start gap-2 text-sm">
                                      <input
                                        type="checkbox"
                                        checked={Boolean(i.done)}
                                        onChange={async (e) => {
                                          await api.updateChecklist(i.id, { done: e.target.checked });
                                          await loadDetailsSidecars();
                                        }}
                                      />
                                      <span className={cn(i.done ? "line-through text-muted" : "")}>{i.text}</span>
                                    </label>
                                  ))}
                                </div>
                              )}
                            </div>
                            <div>
                              <div className="text-sm font-semibold">Comments</div>
                              {comments === null ? (
                                <Skeleton className="h-20 w-full mt-2" />
                              ) : comments.length === 0 ? (
                                <div className="text-xs text-muted mt-2">No comments.</div>
                              ) : (
                                <div className="mt-2 space-y-2">
                                  {comments.slice(-6).map((c) => (
                                    <div key={c.id} className="rounded-2xl border border-white/10 bg-white/5 p-2">
                                      <div className="flex items-center justify-between gap-2">
                                        <div className="text-[11px] text-muted">{c.authorName || c.authorId}</div>
                                        {c.source === "jira" ? (
                                          <a className="text-[11px] text-accent hover:underline" href={c.sourceUrl || task?.jiraUrl || "#"} target="_blank" rel="noreferrer">
                                            Jira
                                          </a>
                                        ) : null}
                                      </div>
                                      <div className="text-sm whitespace-pre-wrap">{c.body}</div>
                                    </div>
                                  ))}
                                </div>
                              )}
                              <div className="mt-2 flex gap-2">
                                <Input
                                  placeholder="Add a comment…"
                                  onKeyDown={async (e) => {
                                    if (e.key === "Enter") {
                                      const body = (e.target as HTMLInputElement).value.trim();
                                      if (!body || !taskId) return;
                                      (e.target as HTMLInputElement).value = "";
                                      await api.addComment(taskId, body);
                                      await loadDetailsSidecars();
                                    }
                                  }}
                                />
                              </div>
                            </div>
                          </div>
                          </details>

                          <details className="rounded-2xl border border-white/10 bg-white/5 p-3" open={isMobileViewport || (!isFocusLayout && !isCompactLayout)}>
                            <summary className="cursor-pointer list-none flex items-center justify-between gap-2">
                              <div className="text-sm font-semibold">Dependencies + Attachments</div>
                              <div className="text-xs text-muted">Expand to view and edit</div>
                            </summary>
                          <div className={`${splitGridClass} mt-3`}>
                            <div>
                              <div className="text-sm font-semibold">Dependencies</div>
                              {deps === null ? (
                                <Skeleton className="h-20 w-full mt-2" />
                              ) : deps.length === 0 ? (
                                <div className="text-xs text-muted mt-2">No dependencies.</div>
                              ) : (
                                <div className="mt-2 space-y-2">
                                  {deps.map((d) => (
                                    <div key={d.id} className="rounded-2xl border border-white/10 bg-white/5 p-2 flex items-center justify-between gap-2">
                                      <div className="text-xs text-muted">
                                        Depends on:{" "}
                                        {(() => {
                                          const dt = tasks.find((x) => x.id === d.dependsOnTaskId);
                                          return dt ? dt.title : d.dependsOnTaskId;
                                        })()}
                                      </div>
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={async () => {
                                          await api.deleteDependency(d.id);
                                          await loadDetailsSidecars();
                                        }}
                                      >
                                        Remove
                                      </Button>
                                    </div>
                                  ))}
                                </div>
                              )}
                              <div className="mt-2 space-y-2">
                                <div className="text-xs text-muted">Add dependency</div>
                                <div className="flex gap-2">
                                  <select
                                    className="h-10 flex-1 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                    value={depPick}
                                    onChange={(e) => setDepPick(e.target.value)}
                                  >
                                    <option value="">Select a task…</option>
                                    {tasks
                                      .filter((t) => t.id !== taskId)
                                      .slice(0, 200)
                                      .map((t) => (
                                        <option key={t.id} value={t.id}>
                                          {t.title}
                                        </option>
                                      ))}
                                  </select>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    disabled={!depPick || !taskId}
                                    onClick={async () => {
                                      if (!taskId || !depPick) return;
                                      await api.addDependency(taskId, depPick);
                                      setDepPick("");
                                      await loadDetailsSidecars();
                                    }}
                                  >
                                    Add
                                  </Button>
                                </div>
                                <Input
                                  placeholder="Or paste dependency task id and press Enter…"
                                  onKeyDown={async (e) => {
                                    if (e.key === "Enter") {
                                      const id = (e.target as HTMLInputElement).value.trim();
                                      if (!id || !taskId) return;
                                      (e.target as HTMLInputElement).value = "";
                                      await api.addDependency(taskId, id);
                                      await loadDetailsSidecars();
                                    }
                                  }}
                                />
                              </div>
                            </div>
                            <div>
                              <div className="text-sm font-semibold">Attachments</div>
                              <div className="text-xs text-muted mt-2">MVP stores files in API volume.</div>
                              {attachments === null ? (
                                <div className="text-xs text-muted mt-2">Loading…</div>
                              ) : attachments.length === 0 ? (
                                <div className="text-xs text-muted mt-2">No attachments.</div>
                              ) : (
                                <div className="mt-2 space-y-2">
                                  {attachments.map((a) => {
                                    const url = `/api${a.url}`;
                                    const isImage = String(a.mime || "").startsWith("image/");
                                    return (
                                      <div key={a.id} className="rounded-2xl border border-white/10 bg-white/5 p-2">
                                        <div className="flex items-center justify-between gap-2">
                                          <div className="text-xs text-muted truncate">{a.filename}</div>
                                          <a className="text-xs text-accent hover:underline" href={url} target="_blank" rel="noreferrer">
                                            Open
                                          </a>
                                        </div>
                                        {isImage ? (
                                          // eslint-disable-next-line @next/next/no-img-element
                                          <img src={url} alt={a.filename} className="mt-2 rounded-xl max-h-40 object-contain w-full bg-black/20" />
                                        ) : null}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                              <div className="mt-2">
                                <input
                                  type="file"
                                  onChange={async (e) => {
                                    const f = e.target.files?.[0];
                                    if (!f || !taskId) return;
                                    try {
                                      await api.uploadAttachment(taskId, f);
                                      toast.success("Uploaded");
                                      await loadDetailsSidecars();
                                    } catch (err: any) {
                                      toast.error(String(err?.message || err));
                                    } finally {
                                      e.currentTarget.value = "";
                                    }
                                  }}
                                />
                              </div>
                            </div>
                          </div>
                          </details>
                        </div>
                      )}
                    </TabsContent>

                    <TabsContent value="pencil" className="mt-4">
                      <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <div className="text-sm font-semibold">Pencil Pad</div>
                            <div className="text-xs text-muted">
                              Best on iPad + Apple Pencil. Draw quick context, drop note cards, then append to description.
                            </div>
                          </div>
                          {isTabletLikely ? <Badge variant="accent">iPad mode</Badge> : <Badge variant="muted">Works with touch/mouse/pen</Badge>}
                        </div>

                        <div
                          className="mt-3 relative rounded-2xl border border-white/10 bg-black/20 overflow-hidden"
                          onPointerMove={(e) => {
                            const drag = pencilDragRef.current;
                            if (!drag) return;
                            setPencilCards((prev) =>
                              prev.map((c) =>
                                c.id === drag.id
                                  ? { ...c, x: Math.max(0, Math.min(360, e.clientX - drag.offsetX)), y: Math.max(0, Math.min(180, e.clientY - drag.offsetY)) }
                                  : c
                              )
                            );
                          }}
                          onPointerUp={() => {
                            pencilDragRef.current = null;
                          }}
                        >
                          <canvas
                            ref={pencilCanvasRef}
                            className="block w-full h-[220px] touch-none"
                            onPointerDown={(e) => {
                              if (e.button !== 0) return;
                              pencilDrawingRef.current = true;
                              pencilPointRef.current = null;
                              drawAt(e.clientX, e.clientY, e.pressure || 0.4);
                              setPencilInkUsed(true);
                            }}
                            onPointerMove={(e) => {
                              if (!pencilDrawingRef.current) return;
                              drawAt(e.clientX, e.clientY, e.pressure || 0.4);
                            }}
                            onPointerUp={() => {
                              pencilDrawingRef.current = false;
                              pencilPointRef.current = null;
                            }}
                            onPointerLeave={() => {
                              pencilDrawingRef.current = false;
                              pencilPointRef.current = null;
                            }}
                          />
                          {pencilCards.map((c) => (
                            <div
                              key={c.id}
                              className="absolute w-[110px] rounded-xl border border-white/20 bg-sky-400/20 backdrop-blur px-2 py-1 text-xs text-sky-50 cursor-grab"
                              style={{ left: c.x, top: c.y }}
                              onPointerDown={(e) => {
                                const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
                                pencilDragRef.current = {
                                  id: c.id,
                                  pointerId: e.pointerId,
                                  offsetX: e.clientX - rect.left,
                                  offsetY: e.clientY - rect.top,
                                };
                                (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
                              }}
                            >
                              {c.text}
                            </div>
                          ))}
                        </div>

                        <div className="mt-3 grid grid-cols-1 md:grid-cols-[1fr_auto_auto_auto] gap-2">
                          <Input
                            placeholder="Add a draggable note card (example: confirm access group mapping)"
                            value={pencilCardInput}
                            onChange={(e) => setPencilCardInput(e.target.value)}
                          />
                          <Button variant="ghost" onClick={addPencilCard} disabled={!pencilCardInput.trim()}>
                            Add card
                          </Button>
                          <Button variant="ghost" onClick={clearPencilInk}>
                            Clear ink
                          </Button>
                          <Button variant="primary" onClick={appendPencilToDescription} disabled={saving || (!pencilInkUsed && pencilCards.length === 0)}>
                            Append to task
                          </Button>
                        </div>
                      </div>
                    </TabsContent>

                    {!isMobileViewport ? <TabsContent value="copilot" className="mt-4">
                      <div className="grid grid-cols-2 gap-2">
                        <Button variant="primary" onClick={enhanceTicket} disabled={aiLoading || saving || !taskId}>
                          Enhance ticket
                        </Button>
                        <Button variant="ghost" onClick={() => runAI("summarize")} disabled={aiLoading}>
                          Summarize
                        </Button>
                        <Button variant="ghost" onClick={() => runAI("rewrite")} disabled={aiLoading}>
                          Rewrite
                        </Button>
                        <Button variant="ghost" onClick={() => runAI("checklist")} disabled={aiLoading}>
                          Generate checklist
                        </Button>
                        <Button variant="ghost" onClick={() => runAI("next-actions")} disabled={aiLoading}>
                          Next actions
                        </Button>
                        <Button variant="ghost" onClick={() => runAI("risk")} disabled={aiLoading}>
                          Risk scan
                        </Button>
                        <Button variant="primary" onClick={applyAiToDescriptionAndSave} disabled={!aiText || aiLoading || saving}>
                          Apply → Description
                        </Button>
                        <Button variant="primary" onClick={addAiAsComment} disabled={!aiText || aiLoading}>
                          Save as comment
                        </Button>
                        <Button variant="primary" onClick={applyChecklistFromText} disabled={!aiText || aiLoading}>
                          Apply checklist
                        </Button>
                      </div>

                      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3 min-h-40">
                        {aiLoading ? (
                          <div className="flex items-center gap-2 text-muted">
                            <Loader2 className="animate-spin" size={16} /> Thinking…
                          </div>
                        ) : aiText ? (
                          <div>
                            <div className="text-[11px] text-muted">Last action: {aiAction}</div>
                            {aiStructured?.intent ? (
                              <div className="mt-2 rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-2 text-xs">
                                <div className="font-semibold text-emerald-200">
                                  Intent: {aiStructured.intent.type}
                                  <span className="ml-2 text-emerald-100/80">
                                    ({Math.round(Number(aiStructured.intent.confidence || 0) * 100)}%)
                                  </span>
                                </div>
                                {Array.isArray(aiStructured.intent.evidence) && aiStructured.intent.evidence.length > 0 ? (
                                  <div className="mt-1 text-emerald-100/80">Evidence: {aiStructured.intent.evidence.join(", ")}</div>
                                ) : null}
                                {aiStructured?.qualityScore ? (
                                  <div className="mt-1 text-emerald-100/80">
                                    Quality score: {Math.round(Number(aiStructured.qualityScore.overall || 0) * 100)}%
                                  </div>
                                ) : null}
                                {Array.isArray(aiStructured?.qualityScore?.reasonCodes) && aiStructured.qualityScore.reasonCodes.length > 0 ? (
                                  <div className="mt-1 text-emerald-100/80">Reason codes: {aiStructured.qualityScore.reasonCodes.join(", ")}</div>
                                ) : null}
                                {Array.isArray(aiStructured?.retrievalContext?.linkedRecords) && aiStructured.retrievalContext.linkedRecords.length > 0 ? (
                                  <div className="mt-1 text-emerald-100/80">Linked: {aiStructured.retrievalContext.linkedRecords.join(" | ")}</div>
                                ) : null}
                              </div>
                            ) : null}
                            {Array.isArray(aiStructured?.suggestions) && aiStructured.suggestions.length > 0 ? (
                              <div className="mt-2 rounded-xl border border-white/10 bg-white/5 p-2 text-xs">
                                <div className="font-semibold">Patch previews</div>
                                {aiStructured.suggestions.slice(0, 2).map((s: any, i: number) => (
                                  <div key={`ai-prev-${i}`} className="mt-2">
                                    <div className="text-muted">{s.reason || "Suggested patch"}</div>
                                    {s.preview ? <pre className="mt-1 whitespace-pre-wrap text-[11px]">{s.preview}</pre> : null}
                                  </div>
                                ))}
                              </div>
                            ) : null}
                            <pre className="mt-2 whitespace-pre-wrap text-sm">{aiText}</pre>
                          </div>
                        ) : (
                          <div className="text-sm text-muted">
                            Copilot is embedded here (Local provider by default). Use actions above.
                          </div>
                        )}
                      </div>
                    </TabsContent> : null}

                    <TabsContent value="jira" className="mt-4">
                      <div className="space-y-3">
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <div className="text-sm font-semibold">Create Jira from this task</div>
                          <div className="text-xs text-muted mt-1">
                            Manual + idempotent. Once linked, this task won’t create duplicates. Use “Sync this Jira (pull)” to bring updates into NeonLanes.
                          </div>

                          <div className="mt-3 space-y-2">
                            <div className="text-xs text-muted">Connection</div>
                            <select
                              data-testid="task-jira-connection"
                              className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                              value={jiraForm.connectionId}
                              onChange={(e) => setJiraForm({ ...jiraForm, connectionId: e.target.value })}
                            >
                              <option value="">Select…</option>
                              {(jiraConnections || []).map((c) => (
                                <option key={c.id} value={c.id} disabled={Boolean(c.needsReconnect)}>
                                  {c.name ? `${c.name} • ` : ""}
                                  {c.baseUrl}
                                  {c.needsReconnect ? " (Needs reconnect)" : ""}
                                </option>
                              ))}
                            </select>
                            {(() => {
                              const selected = (jiraConnections || []).find((c: any) => c.id === jiraForm.connectionId);
                              if (!selected?.needsReconnect) return null;
                              return <div className="text-xs text-danger">This connection needs reconnect before use.</div>;
                            })()}

                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <div className="text-xs text-muted">Project</div>
                                <select
                                  data-testid="task-jira-project"
                                  className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                  value={jiraForm.projectKey}
                                  onChange={(e) => setJiraForm({ ...jiraForm, projectKey: e.target.value })}
                                >
                                  {jiraProjects.map((p) => (
                                    <option key={p} value={p}>
                                      {p}
                                    </option>
                                  ))}
                                </select>
                              </div>
                              <div>
                                <div className="text-xs text-muted">Issue type</div>
                                <Input
                                  data-testid="task-jira-issuetype"
                                  value={jiraForm.issueType}
                                  onChange={(e) => setJiraForm({ ...jiraForm, issueType: e.target.value })}
                                  placeholder="Task"
                                  className="glass border-white/10"
                                />
                              </div>
                            </div>

                            <label className="flex items-center gap-2 text-sm">
                              <input
                                data-testid="task-jira-enable-sync"
                                type="checkbox"
                                checked={jiraForm.enableSync}
                                onChange={(e) => setJiraForm({ ...jiraForm, enableSync: e.target.checked })}
                              />
                              <span className="text-muted">Enable periodic sync for this task</span>
                            </label>

                            <div>
                              <div className="text-xs text-muted">Assignee</div>
                              <select
                                data-testid="task-jira-assignee"
                                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                                value={jiraForm.assigneeMode}
                                onChange={(e) => setJiraForm({ ...jiraForm, assigneeMode: e.target.value as any })}
                              >
                                <option value="connectionDefault">Connection default</option>
                                <option value="taskOwner">Task owner</option>
                                <option value="projectDefault">Project default</option>
                                <option value="unassigned">Unassigned</option>
                              </select>
                            </div>

                            <div className="flex flex-wrap gap-2">
                              <Button
                                data-testid="task-jira-create"
                                disabled={
                                  !task ||
                                  !jiraForm.connectionId ||
                                  saving ||
                                  Boolean(task?.jiraKey) ||
                                  Boolean((jiraConnections || []).find((c: any) => c.id === jiraForm.connectionId)?.needsReconnect)
                                }
                                onClick={async () => {
                                  if (!task) return;
                                  try {
                                    setSaving(true);
                                    const t = await api.taskJiraCreate(task.id, {
                                      connectionId: jiraForm.connectionId,
                                      projectKey: jiraForm.projectKey,
                                      issueType: jiraForm.issueType || "Task",
                                      enableSync: jiraForm.enableSync,
                                      assigneeMode: jiraForm.assigneeMode
                                    });
                                    setForm((f: any) => (f ? { ...f, title: t.title, description: t.description, tags: (t.tags || []).join(", ") } : f));
                                    await refreshAll();
                                    toast.success(t.jiraKey ? `Created ${t.jiraKey}` : "Created");
                                  } catch (e: any) {
                                    toast.error(String(e?.message || e));
                                  } finally {
                                    setSaving(false);
                                  }
                                }}
                              >
                                {task?.jiraKey ? "Already linked" : "Create Jira"}
                              </Button>

                              <Button
                                data-testid="task-jira-pull"
                                variant="ghost"
                                disabled={!task?.jiraKey || saving}
                                onClick={async () => {
                                  if (!task) return;
                                  try {
                                    setSaving(true);
                                    const t = await api.taskJiraSync(task.id);
                                    setForm((f: any) =>
                                      f
                                        ? {
                                            ...f,
                                            title: t.title,
                                            description: t.description,
                                            tags: (t.tags || []).join(", "),
                                            dueDate: t.dueDate ? t.dueDate.slice(0, 10) : ""
                                          }
                                        : f
                                    );
                                    await refreshAll();
                                    toast.success("Synced with Jira");
                                  } catch (e: any) {
                                    toast.error(String(e?.message || e));
                                  } finally {
                                    setSaving(false);
                                  }
                                }}
                              >
                                Sync this Jira
                              </Button>
                            </div>
                          </div>
                        </div>

                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <div className="text-sm font-semibold">Linked issue</div>
                          <div className="mt-2 text-sm">
                            {task?.jiraKey ? (
                              <div className="flex items-center gap-2">
                                <Badge variant="accent">{task.jiraKey}</Badge>
                                {task.jiraUrl ? (
                                  <a
                                    href={task.jiraUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"
                                  >
                                    <ExternalLink size={14} /> Open
                                  </a>
                                ) : null}
                              </div>
                            ) : (
                              <div className="text-xs text-muted">Not linked.</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </TabsContent>

                    <TabsContent value="openproject" className="mt-4">
                      <div className="space-y-3">
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <div className="text-sm font-semibold">OpenProject for this task</div>
                          <div className="text-xs text-muted mt-1">
                            Create or link a work package, then pull/sync updates.
                          </div>

                          <div className="mt-3 space-y-2">
                            <div className="text-xs text-muted">Connection</div>
                            <select
                              className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                              value={openprojectForm.connectionId}
                              onChange={(e) => {
                                const picked = (openprojectConnections || []).find((c) => c.id === e.target.value);
                                setOpenprojectForm((f) => ({
                                  ...f,
                                  connectionId: e.target.value,
                                  projectIdentifier: picked?.projectIdentifier || f.projectIdentifier
                                }));
                              }}
                            >
                              <option value="">Select…</option>
                              {(openprojectConnections || []).map((c) => (
                                <option key={c.id} value={c.id}>
                                  {c.name ? `${c.name} • ` : ""}
                                  {c.baseUrl}
                                </option>
                              ))}
                            </select>

                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <div className="text-xs text-muted">Project identifier</div>
                                <Input
                                  value={openprojectForm.projectIdentifier}
                                  onChange={(e) => setOpenprojectForm((f) => ({ ...f, projectIdentifier: e.target.value }))}
                                  placeholder="e.g. platform"
                                  className="glass border-white/10"
                                />
                              </div>
                              <div>
                                <div className="text-xs text-muted">Work package id (for link)</div>
                                <Input
                                  value={openprojectForm.workPackageId}
                                  onChange={(e) => setOpenprojectForm((f) => ({ ...f, workPackageId: e.target.value }))}
                                  placeholder="e.g. 1234"
                                  className="glass border-white/10"
                                />
                              </div>
                            </div>

                            <label className="flex items-center gap-2 text-sm">
                              <input
                                type="checkbox"
                                checked={openprojectForm.enableSync}
                                onChange={(e) => setOpenprojectForm((f) => ({ ...f, enableSync: e.target.checked }))}
                              />
                              <span className="text-muted">Enable sync for this task</span>
                            </label>

                            <div className="flex flex-wrap gap-2">
                              <Button
                                disabled={!task || !openprojectForm.connectionId || saving || Boolean(task?.openprojectWorkPackageId)}
                                onClick={async () => {
                                  if (!task) return;
                                  try {
                                    setSaving(true);
                                    const t = await api.taskOpenProjectCreate(task.id, {
                                      connectionId: openprojectForm.connectionId,
                                      projectIdentifier: openprojectForm.projectIdentifier || undefined,
                                      enableSync: openprojectForm.enableSync
                                    });
                                    await refreshAll();
                                    toast.success(t.openprojectWorkPackageId ? `Created #${t.openprojectWorkPackageId}` : "Created");
                                  } catch (e: any) {
                                    toast.error(String(e?.message || e));
                                  } finally {
                                    setSaving(false);
                                  }
                                }}
                              >
                                {task?.openprojectWorkPackageId ? "Already linked" : "Create OpenProject"}
                              </Button>
                              <Button
                                variant="ghost"
                                disabled={!task || !openprojectForm.connectionId || !openprojectForm.workPackageId || saving}
                                onClick={async () => {
                                  if (!task) return;
                                  const workPackageId = Number(openprojectForm.workPackageId);
                                  if (!workPackageId || Number.isNaN(workPackageId)) {
                                    toast.error("Enter a valid work package id.");
                                    return;
                                  }
                                  try {
                                    setSaving(true);
                                    await api.taskOpenProjectLink(task.id, {
                                      connectionId: openprojectForm.connectionId,
                                      workPackageId,
                                      enableSync: openprojectForm.enableSync
                                    });
                                    await refreshAll();
                                    toast.success(`Linked #${workPackageId}`);
                                  } catch (e: any) {
                                    toast.error(String(e?.message || e));
                                  } finally {
                                    setSaving(false);
                                  }
                                }}
                              >
                                Link existing
                              </Button>
                              <Button
                                variant="ghost"
                                disabled={!task?.openprojectWorkPackageId || saving}
                                onClick={async () => {
                                  if (!task) return;
                                  try {
                                    setSaving(true);
                                    await api.taskOpenProjectPull(task.id);
                                    await refreshAll();
                                    toast.success("Pulled from OpenProject");
                                  } catch (e: any) {
                                    toast.error(String(e?.message || e));
                                  } finally {
                                    setSaving(false);
                                  }
                                }}
                              >
                                Pull
                              </Button>
                              <Button
                                variant="ghost"
                                disabled={!task?.openprojectWorkPackageId || saving}
                                onClick={async () => {
                                  if (!task) return;
                                  try {
                                    setSaving(true);
                                    await api.taskOpenProjectSync(task.id);
                                    await refreshAll();
                                    toast.success("Synced with OpenProject");
                                  } catch (e: any) {
                                    toast.error(String(e?.message || e));
                                  } finally {
                                    setSaving(false);
                                  }
                                }}
                              >
                                Sync
                              </Button>
                              {task?.openprojectUrl ? (
                                <a
                                  href={task.openprojectUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 rounded-xl border border-white/10 px-3 h-10 text-sm hover:bg-white/5"
                                >
                                  <ExternalLink size={14} /> Open
                                </a>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      </div>
                    </TabsContent>

                    <TabsContent value="activity" className="mt-4">
                      {activity === null ? (
                        <Skeleton className="h-28 w-full" />
                      ) : activity.length === 0 ? (
                        <div className="text-sm text-muted">No activity yet.</div>
                      ) : (
                        <div className="space-y-2">
                          {activity.map((ev) => (
                            <div key={ev.id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                              <div className="text-xs text-muted">
                                {new Date(ev.createdAt).toLocaleString()} • {ev.eventType}
                              </div>
                              <div className="text-sm">{ev.entityType}</div>
                              <pre className="mt-2 text-xs text-muted whitespace-pre-wrap">{JSON.stringify(ev.payload, null, 2)}</pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </TabsContent>
                  </Tabs>
                  </TooltipProvider>
                </div>
              </>
            )}
          </motion.div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
