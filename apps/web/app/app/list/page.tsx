"use client";

import { useMemo, useState } from "react";
import { useBoard } from "@/components/board-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TaskDrawer } from "@/components/task-drawer";

export default function ListPage() {
  const { board, lanes, tasks, users, loading, search, taskTypes, priorities } = useBoard();
  const [drawerTaskId, setDrawerTaskId] = useState<string | null>(null);
  const [filters, setFilters] = useState({ ownerId: "", priority: "", type: "", blocked: "", completion: "" });
  const [sort, setSort] = useState<"due" | "priority" | "updated" | "title">("due");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [cols, setCols] = useState({
    lane: true,
    owner: true,
    priority: true,
    type: true,
    due: true,
    blocked: true,
    jira: true
  });

  const laneById = useMemo(() => new Map(lanes.map((l) => [l.id, l])), [lanes]);
  const userById = useMemo(() => new Map(users.map((u) => [u.id, u])), [users]);
  const enabledTaskTypes = useMemo(
    () => (taskTypes || []).filter((t) => t.enabled !== false).slice().sort((a, b) => a.position - b.position),
    [taskTypes]
  );
  const enabledPriorities = useMemo(
    () => (priorities || []).filter((p) => p.enabled !== false).slice().sort((a, b) => a.rank - b.rank),
    [priorities]
  );
  const priorityRank = useMemo(() => new Map(enabledPriorities.map((p) => [p.key, p.rank])), [enabledPriorities]);
  const priorityTone = (key: string) => {
    const r = priorityRank.get(key) ?? 99;
    if (r <= 0) return "danger";
    if (r === 1) return "warn";
    if (r === 2) return "accent";
    return "muted";
  };

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = tasks
      .filter((t) => {
        const hay = `${t.title}\n${t.description}\n${(t.tags || []).join(" ")}\n${t.jiraKey || ""}`.toLowerCase();
        if (q && !hay.includes(q)) return false;
        if (filters.ownerId === "__unassigned" && t.ownerId) return false;
        if (filters.ownerId && filters.ownerId !== "__unassigned" && (t.ownerId || "") !== filters.ownerId) return false;
        if (filters.priority && t.priority !== filters.priority) return false;
        if (filters.type && t.type !== filters.type) return false;
        const laneType = laneById.get(t.laneId)?.type || "active";
        const isBlocked = Boolean(t.blocked) || laneType === "blocked";
        if (filters.blocked === "true" && !isBlocked) return false;
        if (filters.blocked === "false" && isBlocked) return false;
        if (filters.completion === "done" && laneType !== "done") return false;
        if (filters.completion === "open" && laneType === "done") return false;
        return true;
      })
      .slice();

    const cmp = (a: any, b: any) => {
      if (sort === "priority") return (priorityRank.get(a.priority) ?? 99) - (priorityRank.get(b.priority) ?? 99);
      if (sort === "updated") return String(a.updatedAt || "").localeCompare(String(b.updatedAt || ""));
      if (sort === "title") return String(a.title || "").localeCompare(String(b.title || ""));
      // due
      return String(a.dueDate || "").localeCompare(String(b.dueDate || ""));
    };

    filtered.sort((a, b) => {
      const v = cmp(a, b);
      return sortDir === "asc" ? v : -v;
    });
    return filtered;
  }, [tasks, search, filters, sort, sortDir, priorityRank, laneById]);

  if (loading || !board) return <div className="h-full p-6 text-muted">Loading…</div>;

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="px-4 pb-3 flex flex-wrap items-center gap-2">
        <div className="glass nl-surface-panel rounded-2xl p-2 flex flex-wrap gap-2 items-center">
          <select
            className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={filters.ownerId}
            onChange={(e) => setFilters({ ...filters, ownerId: e.target.value })}
          >
            <option value="">Owner: Any</option>
            <option value="__unassigned">Unassigned</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={filters.priority}
            onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
          >
            <option value="">Priority: Any</option>
            {enabledPriorities.map((p) => (
              <option key={p.key} value={p.key}>
                {p.name}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={filters.type}
            onChange={(e) => setFilters({ ...filters, type: e.target.value })}
          >
            <option value="">Type: Any</option>
            {enabledTaskTypes.map((t) => (
              <option key={t.key} value={t.key}>
                {t.name}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={filters.blocked}
            onChange={(e) => setFilters({ ...filters, blocked: e.target.value })}
          >
            <option value="">Blocked: Any</option>
            <option value="true">Blocked</option>
            <option value="false">Not blocked</option>
          </select>
          <select
            className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={filters.completion}
            onChange={(e) => setFilters({ ...filters, completion: e.target.value })}
          >
            <option value="">Status: Any</option>
            <option value="open">Open</option>
            <option value="done">Done</option>
          </select>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setFilters({ ownerId: "", priority: "", type: "", blocked: "", completion: "" })}
          >
            Clear
          </Button>
        </div>

        <div className="glass nl-surface-panel rounded-2xl p-2 flex gap-2 items-center">
          <label className="text-xs text-muted px-2">Sort</label>
          <select
            className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={sort}
            onChange={(e) => setSort(e.target.value as any)}
          >
            <option value="due">Due date</option>
            <option value="priority">Priority</option>
            <option value="updated">Updated</option>
            <option value="title">Title</option>
          </select>
          <select
            className="h-9 rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={sortDir}
            onChange={(e) => setSortDir(e.target.value as any)}
          >
            <option value="asc">Asc</option>
            <option value="desc">Desc</option>
          </select>
        </div>

        <div className="glass nl-surface-panel rounded-2xl p-2 flex gap-2 items-center">
          <label className="text-xs text-muted px-2">Columns</label>
          {Object.entries(cols).map(([k, v]) => (
            <label key={k} className="text-xs text-muted flex items-center gap-1 px-2">
              <input checked={v} onChange={(e) => setCols({ ...cols, [k]: e.target.checked })} type="checkbox" />
              {k}
            </label>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto px-4 pb-6 scrollbar">
        <div className="glass nl-surface-panel rounded-3xl shadow-neon overflow-hidden">
          <table className="w-full text-sm table-fixed">
            <colgroup>
              <col className="w-[40%]" />
              {cols.lane ? <col className="w-[11%]" /> : null}
              {cols.owner ? <col className="w-[12%]" /> : null}
              {cols.priority ? <col className="w-[9%]" /> : null}
              {cols.type ? <col className="w-[9%]" /> : null}
              {cols.due ? <col className="w-[10%]" /> : null}
              {cols.blocked ? <col className="w-[9%]" /> : null}
              {cols.jira ? <col className="w-[11%]" /> : null}
            </colgroup>
            <thead className="bg-white/10">
              <tr className="text-left text-muted">
                <th className="p-3">Title</th>
                {cols.lane ? <th className="p-3">Lane</th> : null}
                {cols.owner ? <th className="p-3">Owner</th> : null}
                {cols.priority ? <th className="p-3">Priority</th> : null}
                {cols.type ? <th className="p-3">Type</th> : null}
                {cols.due ? <th className="p-3">Due</th> : null}
                {cols.blocked ? <th className="p-3">Blocked</th> : null}
                {cols.jira ? <th className="p-3">Jira</th> : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => {
                const lane = laneById.get(t.laneId);
                const laneType = lane?.type || "active";
                const isBlocked = Boolean(t.blocked) || laneType === "blocked";
                const owner = t.ownerId ? userById.get(t.ownerId) : null;
                return (
                  <tr
                    key={t.id}
                    className="border-t border-white/10 hover:bg-white/10 cursor-pointer"
                    onClick={() => setDrawerTaskId(t.id)}
                  >
                    <td className="p-3">
                      <div className="font-medium truncate">{t.title}</div>
                      <div className="text-xs text-muted line-clamp-1">{t.description || "No description"}</div>
                      <div className="text-[11px] text-muted/80 truncate mt-0.5">{(t.tags || []).slice(0, 3).join(", ")}</div>
                    </td>
                    {cols.lane ? <td className="p-3 text-muted truncate">{lane?.name || "—"}</td> : null}
                    {cols.owner ? <td className="p-3 text-muted truncate">{owner?.name || "Unassigned"}</td> : null}
                    {cols.priority ? (
                      <td className="p-3">
                        <Badge variant={priorityTone(t.priority)}>{t.priority}</Badge>
                      </td>
                    ) : null}
                    {cols.type ? <td className="p-3 text-muted truncate">{t.type}</td> : null}
                    {cols.due ? <td className="p-3 text-muted">{t.dueDate ? t.dueDate.slice(0, 10) : "—"}</td> : null}
                    {cols.blocked ? (
                      <td className="p-3">{isBlocked ? <Badge variant="danger">Yes</Badge> : <Badge variant="muted">No</Badge>}</td>
                    ) : null}
                    {cols.jira ? <td className="p-3 text-muted truncate">{t.jiraKey || "—"}</td> : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {rows.length === 0 ? <div className="p-6 text-sm text-muted">No tasks match.</div> : null}
        </div>
      </div>

      <TaskDrawer taskId={drawerTaskId} onClose={() => setDrawerTaskId(null)} />
    </div>
  );
}
