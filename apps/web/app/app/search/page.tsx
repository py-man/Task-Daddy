"use client";

import { useMemo, useState } from "react";
import { useBoard } from "@/components/board-context";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { TaskDrawer } from "@/components/task-drawer";
import { EmptyState } from "@/components/empty-state";
import { cn } from "@/lib/cn";

export default function SearchPage() {
  const { board, tasks, loading, priorities } = useBoard();
  const [q, setQ] = useState("");
  const [drawerTaskId, setDrawerTaskId] = useState<string | null>(null);
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

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    return tasks.filter((t) => {
      const hay = `${t.title}\n${t.description}\n${(t.tags || []).join(" ")}\n${t.jiraKey || ""}`.toLowerCase();
      return hay.includes(s);
    });
  }, [q, tasks]);

  if (loading) return <div className="h-full p-4 text-sm text-muted">Loading…</div>;

  if (!board) {
    return (
      <div className="h-full p-4">
        <EmptyState title="Select a board" body="Pick a board from the header to search." />
      </div>
    );
  }

  return (
    <div className="h-full p-4 flex flex-col min-h-0">
      <div className="text-sm font-semibold">Search</div>
      <div className="mt-3">
        <Input data-testid="mobile-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, description, tags, Jira key…" />
      </div>

      <div className="mt-3 flex-1 min-h-0 overflow-y-auto scrollbar">
        {!q.trim() ? (
          <div className="text-sm text-muted mt-6">Type to search this board.</div>
        ) : results.length === 0 ? (
          <div className="text-sm text-muted mt-6">No matches.</div>
        ) : (
          <div className="space-y-2 pb-6">
            {results.slice(0, 50).map((t) => (
              <button
                key={t.id}
                className={cn("w-full text-left rounded-2xl border border-white/10 bg-white/5 hover:bg-white/10 transition p-3")}
                onClick={() => setDrawerTaskId(t.id)}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-sm font-medium leading-snug">{t.title}</div>
                  <Badge variant={priorityVariant(t.priority)}>{t.priority}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {t.jiraKey ? <Badge variant="accent">{t.jiraKey}</Badge> : null}
                  {t.blocked ? <Badge variant="danger">Blocked</Badge> : null}
                  {t.tags?.slice(0, 3).map((tag) => (
                    <Badge key={tag} variant="muted">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <TaskDrawer taskId={drawerTaskId} onClose={() => setDrawerTaskId(null)} />
    </div>
  );
}
