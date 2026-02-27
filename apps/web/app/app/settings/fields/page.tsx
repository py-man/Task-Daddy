"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useBoard } from "@/components/board-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";

function toKey(name: string) {
  const raw = String(name || "").trim();
  if (!raw) return "";
  if (/^[A-Za-z0-9_-]+$/.test(raw)) return raw;
  return raw
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
}

export default function SettingsFieldsPage() {
  const { board, boards, taskTypes, priorities, refreshAll, loading } = useBoard();
  const [typeName, setTypeName] = useState("");
  const [typeKey, setTypeKey] = useState("");
  const [prioName, setPrioName] = useState("");
  const [prioKey, setPrioKey] = useState("");
  const [applyAllBoards, setApplyAllBoards] = useState(true);
  const [busy, setBusy] = useState(false);

  const enabledTaskTypes = useMemo(
    () => (taskTypes || []).slice().sort((a, b) => a.position - b.position),
    [taskTypes]
  );
  const enabledPriorities = useMemo(
    () => (priorities || []).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );

  if (loading) return <div className="glass rounded-3xl shadow-neon border border-white/10 p-5 text-sm text-muted">Loading…</div>;

  if (!board) {
    return (
      <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
        <EmptyState title="Select a board" body="Pick a board first; task fields are configured per board." />
      </div>
    );
  }

  const reorderTypes = async (from: number, to: number) => {
    const list = enabledTaskTypes.map((t) => t.key);
    const [m] = list.splice(from, 1);
    list.splice(to, 0, m);
    await api.reorderTaskTypes(board.id, list);
    await refreshAll();
  };

  const reorderPriorities = async (from: number, to: number) => {
    const list = enabledPriorities.map((p) => p.key);
    const [m] = list.splice(from, 1);
    list.splice(to, 0, m);
    await api.reorderPriorities(board.id, list);
    await refreshAll();
  };

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-semibold">Fields</div>
          <div className="mt-2 text-sm text-muted">Customize task types and priorities per board. Keys are what tasks store; names can change later.</div>
          <div className="mt-1 text-xs text-muted">Current board: {board.name}</div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            className="h-9 px-4 shadow-[0_0_0_1px_rgba(115,255,209,0.35),0_8px_20px_rgba(16,185,129,0.28)]"
            disabled={busy}
            onClick={async () => {
              if (!board?.id) return;
              setBusy(true);
              try {
                const res = await api.syncTaskFieldsToAllBoards(board.id);
                toast.success(
                  `Synced fields: ${res.boardsTouched} board(s), +${res.typesCreated} type(s), +${res.prioritiesCreated} priority(s)`
                );
                await refreshAll();
              } catch (e: any) {
                toast.error(String(e?.message || e));
              } finally {
                setBusy(false);
              }
            }}
          >
            Save + Sync All Boards
          </Button>
          <label className="text-xs text-muted flex items-center gap-2">
            <input type="checkbox" checked={applyAllBoards} onChange={(e) => setApplyAllBoards(e.target.checked)} />
            Add to all boards
          </label>
          <Badge variant="muted">{applyAllBoards ? "All boards" : "Current board"}</Badge>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">Task types</div>
          <div className="mt-1 text-xs text-muted">Examples: Ops, Feature, Risk. Disable to hide from UI; delete only if unused.</div>

          <div className="mt-4 grid grid-cols-2 gap-3 items-end">
            <div className="col-span-2">
              <div className="text-xs text-muted mb-1">Name</div>
              <Input
                value={typeName}
                onChange={(e) => {
                  const v = e.target.value;
                  setTypeName(v);
                  if (!typeKey.trim()) setTypeKey(toKey(v));
                }}
                placeholder="e.g. Security"
              />
            </div>
            <div className="col-span-2">
              <div className="text-xs text-muted mb-1">Key</div>
              <Input value={typeKey} onChange={(e) => setTypeKey(e.target.value)} placeholder="e.g. SECURITY" />
            </div>
            <div className="col-span-2 flex justify-end">
              <Button
                disabled={busy || !typeName.trim() || !typeKey.trim()}
                onClick={async () => {
                  if (!board?.id) return;
                  setBusy(true);
                  try {
                    const targetBoards = applyAllBoards ? boards.map((b) => b.id) : [board.id];
                    let created = 0;
                    for (const bid of targetBoards) {
                      try {
                        await api.createTaskType(bid, { key: typeKey.trim(), name: typeName.trim() });
                        created++;
                      } catch (e: any) {
                        const msg = String(e?.message || e);
                        if (!msg.includes("409")) throw e;
                      }
                    }
                    toast.success(created > 0 ? `Created on ${created} board${created === 1 ? "" : "s"}` : "Already exists on selected boards");
                    setTypeName("");
                    setTypeKey("");
                    await refreshAll();
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Add type
              </Button>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {enabledTaskTypes.length === 0 ? (
              <div className="text-sm text-muted">No types yet.</div>
            ) : (
              enabledTaskTypes.map((t, idx) => (
                <div key={t.key} className="rounded-2xl border border-white/10 bg-black/20 p-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{t.name}</div>
                    <div className="text-xs text-muted truncate">{t.key}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-muted flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={t.enabled !== false}
                        onChange={async (e) => {
                          try {
                            await api.updateTaskType(board.id, t.key, { enabled: e.target.checked });
                            await refreshAll();
                          } catch (err: any) {
                            toast.error(String(err?.message || err));
                          }
                        }}
                      />
                      Enabled
                    </label>
                    <Button size="sm" variant="ghost" disabled={idx === 0} onClick={() => reorderTypes(idx, idx - 1)}>
                      Up
                    </Button>
                    <Button size="sm" variant="ghost" disabled={idx === enabledTaskTypes.length - 1} onClick={() => reorderTypes(idx, idx + 1)}>
                      Down
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={async () => {
                        if (!confirm(`Delete task type “${t.name}”? This is only allowed if no tasks use it.`)) return;
                        try {
                          await api.deleteTaskType(board.id, t.key);
                          toast.success("Deleted");
                          await refreshAll();
                        } catch (err: any) {
                          toast.error(String(err?.message || err));
                        }
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">Priorities</div>
          <div className="mt-1 text-xs text-muted">Lower rank = higher priority. Disable to hide from UI; delete only if unused.</div>

          <div className="mt-4 grid grid-cols-2 gap-3 items-end">
            <div className="col-span-2">
              <div className="text-xs text-muted mb-1">Name</div>
              <Input
                value={prioName}
                onChange={(e) => {
                  const v = e.target.value;
                  setPrioName(v);
                  if (!prioKey.trim()) setPrioKey(toKey(v));
                }}
                placeholder="e.g. P0"
              />
            </div>
            <div className="col-span-2">
              <div className="text-xs text-muted mb-1">Key</div>
              <Input value={prioKey} onChange={(e) => setPrioKey(e.target.value)} placeholder="e.g. P0" />
            </div>
            <div className="col-span-2 flex justify-end">
              <Button
                disabled={busy || !prioName.trim() || !prioKey.trim()}
                onClick={async () => {
                  if (!board?.id) return;
                  setBusy(true);
                  try {
                    const targetBoards = applyAllBoards ? boards.map((b) => b.id) : [board.id];
                    let created = 0;
                    for (const bid of targetBoards) {
                      try {
                        await api.createPriority(bid, { key: prioKey.trim(), name: prioName.trim() });
                        created++;
                      } catch (e: any) {
                        const msg = String(e?.message || e);
                        if (!msg.includes("409")) throw e;
                      }
                    }
                    toast.success(created > 0 ? `Created on ${created} board${created === 1 ? "" : "s"}` : "Already exists on selected boards");
                    setPrioName("");
                    setPrioKey("");
                    await refreshAll();
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Add priority
              </Button>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {enabledPriorities.length === 0 ? (
              <div className="text-sm text-muted">No priorities yet.</div>
            ) : (
              enabledPriorities.map((p, idx) => (
                <div key={p.key} className="rounded-2xl border border-white/10 bg-black/20 p-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{p.name}</div>
                    <div className="text-xs text-muted truncate">
                      {p.key} • rank {p.rank}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-muted flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={p.enabled !== false}
                        onChange={async (e) => {
                          try {
                            await api.updatePriority(board.id, p.key, { enabled: e.target.checked });
                            await refreshAll();
                          } catch (err: any) {
                            toast.error(String(err?.message || err));
                          }
                        }}
                      />
                      Enabled
                    </label>
                    <Button size="sm" variant="ghost" disabled={idx === 0} onClick={() => reorderPriorities(idx, idx - 1)}>
                      Up
                    </Button>
                    <Button size="sm" variant="ghost" disabled={idx === enabledPriorities.length - 1} onClick={() => reorderPriorities(idx, idx + 1)}>
                      Down
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={async () => {
                        if (!confirm(`Delete priority “${p.name}”? This is only allowed if no tasks use it.`)) return;
                        try {
                          await api.deletePriority(board.id, p.key);
                          toast.success("Deleted");
                          await refreshAll();
                        } catch (err: any) {
                          toast.error(String(err?.message || err));
                        }
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
