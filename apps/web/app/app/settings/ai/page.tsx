"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useBoard } from "@/components/board-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function SettingsAIPage() {
  const provider = useMemo(() => process.env.NEXT_PUBLIC_AI_PROVIDER || "local-stub", []);
  const { board, boards, selectBoard, tasks, users, updateTask, refreshAll, taskTypes, priorities } = useBoard();
  const [loading, setLoading] = useState(false);
  const [text, setText] = useState("");
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [creates, setCreates] = useState<any[]>([]);
  const [createSelected, setCreateSelected] = useState<Record<string, boolean>>({});

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

  const run = async (action: "triage-unassigned" | "prioritize" | "breakdown") => {
    if (!board?.id) {
      toast.error("Select a board first.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.aiBoard(board.id, action);
      setText(res.text || "");
      setSuggestions(res.suggestions || []);
      setCreates(res.creates || []);
      const sel: Record<string, boolean> = {};
      for (const s of res.suggestions || []) sel[s.taskId] = true;
      setSelected(sel);
      const csel: Record<string, boolean> = {};
      for (const g of res.creates || []) {
        for (let i = 0; i < (g.tasks || []).length; i++) csel[`${g.parentTaskId}:${i}`] = true;
      }
      setCreateSelected(csel);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!board?.id && boards.length > 0) {
      selectBoard(boards[0].id);
    }
  }, [board?.id, boards, selectBoard]);

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-semibold">AI</div>
          <div className="mt-2 text-sm text-muted">AI suggestions are always preview + apply. Task-Daddy never auto-mutates your data silently.</div>
        </div>
        <Badge variant="muted">Board AI</Badge>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4 text-sm">
        <div className="mb-2">
          <span className="text-muted mr-2">Board:</span>
          <select
            className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text outline-none"
            value={board?.id || ""}
            onChange={(e) => {
              if (!e.target.value) return;
              selectBoard(e.target.value);
              setText("");
              setSuggestions([]);
              setCreates([]);
            }}
          >
            {boards.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <span className="text-muted">Provider:</span> {provider}
        </div>
        <div className="mt-2">
          <span className="text-muted">Current board:</span> {board?.name || "—"}
        </div>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">Board actions</div>
        <div className="mt-1 text-xs text-muted">Nothing changes until you click Apply/Create.</div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="ghost" disabled={loading || !board?.id} onClick={() => run("triage-unassigned")}>
            Triage unassigned
          </Button>
          <Button size="sm" variant="ghost" disabled={loading || !board?.id} onClick={() => run("prioritize")}>
            Prioritize
          </Button>
          <Button size="sm" variant="ghost" disabled={loading || !board?.id} onClick={() => run("breakdown")}>
            Break down big tasks
          </Button>
        </div>

        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3 text-sm whitespace-pre-wrap min-h-24">
          {loading ? "Thinking…" : text || "Run an action."}
        </div>

        {suggestions.length ? (
          <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">Suggested changes</div>
              <Button
                size="sm"
                disabled={loading || !Object.values(selected).some(Boolean)}
                onClick={async () => {
                  if (!board?.id) return;
                  const toApply = suggestions.filter((s) => selected[s.taskId]);
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
            <div className="mt-3 space-y-2 max-h-72 overflow-auto pr-1 scrollbar">
              {suggestions.map((s) => {
                const t = tasks.find((x) => x.id === s.taskId);
                const patch = s.patch || {};
                const ownerId = patch.ownerId as string | undefined;
                const priority = patch.priority as string | undefined;
                const ownerName = ownerId ? users.find((u) => u.id === ownerId)?.name || ownerId : null;
                const label = ownerName ? `Set owner → ${ownerName}` : priority ? `Set priority → ${priority}` : `Update task`;
                return (
                  <label key={`${s.taskId}:${label}`} className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={selected[s.taskId] !== false}
                      onChange={(e) => setSelected((prev) => ({ ...prev, [s.taskId]: e.target.checked }))}
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

        {creates.length ? (
          <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">Suggested new tasks</div>
              <Button
                size="sm"
                disabled={loading || !Object.values(createSelected).some(Boolean)}
                onClick={async () => {
                  if (!board?.id) return;
                  const flat: Array<{ parentTaskId: string; idx: number; task: any }> = [];
                  for (const g of creates) {
                    for (let i = 0; i < (g.tasks || []).length; i++) {
                      const key = `${g.parentTaskId}:${i}`;
                      if (!createSelected[key]) continue;
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
                        priority: defaultPriorityKey,
                        type: defaultTypeKey,
                        ownerId: null,
                        dueDate: null
                      });
                      created++;
                      if (it.parentTaskId) {
                        try {
                          await api.addDependency(it.parentTaskId, tNew.id);
                        } catch {
                          // best-effort
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
            <div className="mt-3 space-y-2 max-h-72 overflow-auto pr-1 scrollbar">
              {creates.flatMap((g: any) =>
                (g.tasks || []).map((t: any, i: number) => {
                  const key = `${g.parentTaskId}:${i}`;
                  const parent = tasks.find((x) => x.id === g.parentTaskId);
                  return (
                    <label key={key} className="flex items-start gap-2 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={createSelected[key] !== false}
                        onChange={(e) => setCreateSelected((prev) => ({ ...prev, [key]: e.target.checked }))}
                      />
                      <div className="min-w-0">
                        <div className="font-medium truncate">{t?.title || "New task"}</div>
                        <div className="text-xs text-muted truncate">From: {parent?.title || g.parentTaskId}{g.reason ? ` • ${g.reason}` : ""}</div>
                      </div>
                    </label>
                  );
                })
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
