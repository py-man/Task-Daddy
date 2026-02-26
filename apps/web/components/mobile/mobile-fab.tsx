"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Mic, MicOff, Plus } from "lucide-react";
import { toast } from "sonner";
import { useBoard } from "@/components/board-context";
import { useSession } from "@/components/session";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function isoOrNull(d: string) {
  if (!d) return null;
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toISOString();
}

export function MobileFab() {
  const { board, lanes, createTask, taskTypes, priorities } = useBoard();
  const { user } = useSession();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"task" | "note">("note");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [laneId, setLaneId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [priority, setPriority] = useState("");
  const [type, setType] = useState("");
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [voiceListening, setVoiceListening] = useState(false);
  const voiceRef = useRef<any>(null);

  const sortedLanes = useMemo(() => [...lanes].sort((a, b) => a.position - b.position), [lanes]);
  const enabledTaskTypes = useMemo(
    () => (taskTypes || []).filter((t) => t.enabled !== false).slice().sort((a, b) => a.position - b.position),
    [taskTypes]
  );
  const enabledPriorities = useMemo(
    () => (priorities || []).filter((p) => p.enabled !== false).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );
  const defaultTypeKey = useMemo(() => enabledTaskTypes.find((t) => t.key.toLowerCase() === "ops")?.key || enabledTaskTypes[0]?.key || "", [enabledTaskTypes]);
  const defaultPriorityKey = useMemo(
    () => enabledPriorities.find((p) => p.key.toLowerCase() === "p2")?.key || enabledPriorities[0]?.key || "",
    [enabledPriorities]
  );
  const defaultNoteTypeKey = useMemo(
    () => enabledTaskTypes.find((t) => t.key.toLowerCase() === "note")?.key || enabledTaskTypes.find((t) => t.key.toLowerCase() === "ops")?.key || defaultTypeKey,
    [enabledTaskTypes, defaultTypeKey]
  );

  const canCreateTask = Boolean(board?.id) && Boolean(user?.id) && Boolean(title.trim()) && Boolean(laneId);
  const canCreateNote = Boolean(board?.id) && Boolean(user?.id) && Boolean(note.trim()) && Boolean(laneId);

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
      if (mode === "note") setNote(text);
      else setTitle(text);
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
  }, [mode]);

  const toggleVoiceCapture = () => {
    if (!voiceRef.current) return;
    try {
      if (voiceListening) voiceRef.current.stop();
      else voiceRef.current.start();
    } catch {
      toast.error("Voice input unavailable on this device.");
    }
  };

  const onOpenChange = (v: boolean) => {
    setOpen(v);
    if (v) {
      setMode("note");
      setTitle("");
      setNote("");
      setDueDate("");
      setPriority(defaultPriorityKey);
      setType(defaultTypeKey);
      setLaneId(sortedLanes[0]?.id || "");
    }
  };

  if (!board) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <button
          className="fixed z-[45] right-4 bottom-[84px] h-12 w-12 rounded-xl bg-accent text-black shadow-neon border border-accent/40 grid place-items-center active:scale-[0.98] transition"
          aria-label="Create task"
        >
          <Plus size={20} />
        </button>
      </DialogTrigger>
      <DialogContent>
        <div className="text-lg font-semibold">Quick add</div>
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            className={mode === "note" ? "h-8 px-3 rounded-xl border border-accent/30 bg-accent/10 text-sm" : "h-8 px-3 rounded-xl border border-white/10 text-sm"}
            onClick={() => setMode("note")}
          >
            Quick note
          </button>
          <button
            type="button"
            className={mode === "task" ? "h-8 px-3 rounded-xl border border-accent/30 bg-accent/10 text-sm" : "h-8 px-3 rounded-xl border border-white/10 text-sm"}
            onClick={() => setMode("task")}
          >
            Full task
          </button>
        </div>
        <div className="mt-3 space-y-3">
          {mode === "note" ? (
            <div>
              <div className="text-xs text-muted mb-1">Note</div>
              <textarea
                data-testid="mobile-quickadd-note"
                className="min-h-24 w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Capture it fast..."
              />
              <div className="mt-2">
                <Button size="sm" variant={voiceListening ? "danger" : "ghost"} disabled={!voiceSupported} onClick={toggleVoiceCapture}>
                  {voiceListening ? <MicOff size={15} /> : <Mic size={15} />} Voice
                </Button>
              </div>
            </div>
          ) : (
            <div>
              <div className="text-xs text-muted mb-1">Title</div>
              <div className="flex items-center gap-2">
                <Input
                  data-testid="mobile-quickadd-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="What needs doing?"
                />
                <Button size="sm" variant={voiceListening ? "danger" : "ghost"} disabled={!voiceSupported} onClick={toggleVoiceCapture}>
                  {voiceListening ? <MicOff size={15} /> : <Mic size={15} />}
                </Button>
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-muted mb-1">Lane</div>
              <select
                data-testid="mobile-quickadd-lane"
                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                value={laneId}
                onChange={(e) => setLaneId(e.target.value)}
              >
                {sortedLanes.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Priority</div>
              <select
                data-testid="mobile-quickadd-priority"
                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                {enabledPriorities.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            {mode === "task" ? (
              <>
                <div className="col-span-2">
                  <div className="text-xs text-muted mb-1">Type</div>
                  <select
                    data-testid="mobile-quickadd-type"
                    className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                    value={type}
                    onChange={(e) => setType(e.target.value)}
                  >
                    {enabledTaskTypes.map((t) => (
                      <option key={t.key} value={t.key}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="col-span-2">
                  <div className="text-xs text-muted mb-1">Due date (optional)</div>
                  <Input data-testid="mobile-quickadd-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
                </div>
              </>
            ) : null}
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={mode === "note" ? !canCreateNote : !canCreateTask}
              onClick={async () => {
                try {
                  if (mode === "note") {
                    await createTask({
                      laneId,
                      title: note.trim().slice(0, 96),
                      description: note.trim(),
                      ownerId: user?.id || null,
                      priority: defaultPriorityKey || priority,
                      type: defaultNoteTypeKey
                    });
                  } else {
                    await createTask({
                      laneId,
                      title: title.trim(),
                      ownerId: user?.id || null,
                      priority,
                      type,
                      dueDate: isoOrNull(dueDate)
                    });
                  }
                  setOpen(false);
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                }
              }}
            >
              {mode === "note" ? "Save note" : "Create"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
