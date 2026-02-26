"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { Board, BoardTaskPriority, BoardTaskType, Lane } from "@neonlanes/shared/schema";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/cn";

type ImportItem = { title: string; description?: string; tags?: string[]; idempotencyKey?: string };

function normalizeTitleForPreview(title: string) {
  return title.trim().replace(/^[-*•\s]+/, "").replace(/\s+/g, " ");
}

function dedupeByTitle(items: ImportItem[]) {
  const seen = new Set<string>();
  const out: ImportItem[] = [];
  for (const it of items) {
    const key = normalizeTitleForPreview(it.title).toLowerCase();
    if (!key) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ ...it, title: normalizeTitleForPreview(it.title) });
  }
  return out;
}

function normalizeTag(tag: string) {
  const t = tag.trim();
  if (!t) return "";
  // Keep tags readable but consistent.
  return t.replace(/\s+/g, " ").toUpperCase();
}

function parseList(text: string): ImportItem[] {
  const lines = text.split(/\r?\n/);
  let sectionTags: string[] = [];
  const items: ImportItem[] = [];
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    const isBullet = /^[-*•]\s+/.test(line.trim());
    if (!isBullet) {
      // Treat as a section header. Example: "POWERZAC / PCI / OPERATIONS"
      sectionTags = line
        .split("/")
        .map((x) => normalizeTag(x))
        .filter(Boolean);
      continue;
    }
    const title = line.replace(/^[-*•]\s+/, "").trim();
    if (!title) continue;
    const tags = sectionTags.length ? [...sectionTags] : [];
    const idempotencyKey = tags.length ? `${tags.join("/")}:${title}` : title;
    items.push({ title, tags, idempotencyKey });
  }
  // Fallback: if user pasted plain lines without bullets, keep old behavior.
  if (items.length === 0) {
    return dedupeByTitle(lines.map((l) => ({ title: l })));
  }
  return dedupeByTitle(items);
}

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      const next = line[i + 1];
      if (inQuotes && next === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      out.push(cur.trim());
      cur = "";
      continue;
    }
    cur += ch;
  }
  out.push(cur.trim());
  return out;
}

function parseCsv(text: string): ImportItem[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) return [];
  const first = splitCsvLine(lines[0]).map((x) => x.trim().toLowerCase());
  const hasHeader = first.includes("title");
  const titleIdx = hasHeader ? first.indexOf("title") : 0;
  const descIdx = hasHeader ? first.indexOf("description") : 1;
  const tagsIdx = hasHeader ? first.indexOf("tags") : -1;
  const keyIdx = hasHeader ? first.indexOf("idempotencykey") : -1;
  const start = hasHeader ? 1 : 0;

  const items: ImportItem[] = [];
  for (let i = start; i < lines.length; i++) {
    const cols = splitCsvLine(lines[i]);
    const title = cols[titleIdx] || "";
    const description = descIdx >= 0 ? cols[descIdx] || "" : "";
    const rawTags = tagsIdx >= 0 ? cols[tagsIdx] || "" : "";
    const idempotencyKey = keyIdx >= 0 ? cols[keyIdx] || "" : "";
    const tags =
      rawTags
        .split(/[;,]/)
        .map((t) => normalizeTag(t))
        .filter(Boolean) || [];
    if (!title.trim()) continue;
    items.push({ title, description, tags, idempotencyKey: idempotencyKey.trim() || undefined });
  }
  return dedupeByTitle(items);
}

export default function ImportsPage() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [boardId, setBoardId] = useState<string>("");
  const [lanes, setLanes] = useState<Lane[]>([]);
  const [defaultLaneId, setDefaultLaneId] = useState<string>("");
  const [skipIfTitleExists, setSkipIfTitleExists] = useState(true);
  const [members, setMembers] = useState<any[]>([]);
  const [allUsers, setAllUsers] = useState<any[]>([]);
  const [defaultOwnerId, setDefaultOwnerId] = useState<string>("");
  const [taskTypes, setTaskTypes] = useState<BoardTaskType[]>([]);
  const [priorities, setPriorities] = useState<BoardTaskPriority[]>([]);
  const [defaultType, setDefaultType] = useState<string>("");
  const [defaultPriority, setDefaultPriority] = useState<string>("");

  const [mode, setMode] = useState<"list" | "csv">("list");
  const [listText, setListText] = useState("");
  const [csvText, setCsvText] = useState("");
  const [csvFilename, setCsvFilename] = useState<string>("");

  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<any | null>(null);

  useEffect(() => {
    api
      .boards()
      .then((b) => {
        setBoards(b);
        if (!boardId && b.length) setBoardId(b[0].id);
      })
      .catch((e) => toast.error(String(e?.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!boardId) return;
    Promise.all([api.lanes(boardId), api.boardMembers(boardId), api.users(), api.taskTypes(boardId), api.priorities(boardId)])
      .then(([l, ms, us, tts, ps]) => {
        setLanes(l);
        setMembers(ms);
        setAllUsers(us);
        setTaskTypes(tts);
        setPriorities(ps);
        const backlog = l.find((x) => x.type === "backlog");
        setDefaultLaneId(backlog?.id || l[0]?.id || "");
        const memberIds = new Set(ms.map((m: any) => m.userId));
        const memberUsers = us.filter((u: any) => memberIds.has(u.id));
        // Prefer first active member in deterministic order.
        const prefer = memberUsers[0];
        setDefaultOwnerId(prefer?.id || "");

        const enabledTypes = (tts || []).filter((t: any) => t.enabled !== false).slice().sort((a: any, b: any) => a.position - b.position);
        const enabledPrio = (ps || []).filter((p: any) => p.enabled !== false).slice().sort((a: any, b: any) => a.rank - b.rank);
        setDefaultType(enabledTypes.find((t: any) => String(t.key).toLowerCase() === "ops")?.key || enabledTypes[0]?.key || "");
        setDefaultPriority(enabledPrio.find((p: any) => String(p.key).toLowerCase() === "p2")?.key || enabledPrio[0]?.key || "");
      })
      .catch((e) => toast.error(String(e?.message || e)));
  }, [boardId]);

  const items: ImportItem[] = useMemo(() => {
    try {
      return mode === "list" ? parseList(listText) : parseCsv(csvText);
    } catch {
      return [];
    }
  }, [mode, listText, csvText]);

  const preview = items.slice(0, 20);

  async function runImport() {
    if (!boardId) return toast.error("Pick a board first.");
    if (!defaultLaneId) return toast.error("Pick a default lane.");
    if (!defaultType) return toast.error("Pick a default type.");
    if (!defaultPriority) return toast.error("Pick a default priority.");
    if (items.length === 0) return toast.error("Add at least one task.");

    setImporting(true);
    setResults(null);
    try {
      const out = await api.bulkImportTasks(boardId, {
        defaultLaneId,
        skipIfTitleExists,
        items: items.map((it) => ({
          title: normalizeTitleForPreview(it.title),
          description: it.description || "",
          tags: it.tags || [],
          idempotencyKey: it.idempotencyKey || undefined,
          ownerId: defaultOwnerId || null,
          type: defaultType,
          priority: defaultPriority
        }))
      });
      setResults(out);
      toast.success(`Imported: ${out.createdCount} created, ${out.existingCount} existing`);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="text-lg font-semibold">Imports</div>
      <div className="mt-2 text-sm text-muted">Paste a list or upload CSV. Imports are idempotent (won’t re-create tasks on retry).</div>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-muted mb-1">Board</div>
          <select className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm" value={boardId} onChange={(e) => setBoardId(e.target.value)}>
            {boards.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="text-xs text-muted mb-1">Default lane</div>
          <select
            className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={defaultLaneId}
            onChange={(e) => setDefaultLaneId(e.target.value)}
          >
            {lanes.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-muted mb-1">Default owner</div>
          <select
            className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
            value={defaultOwnerId}
            onChange={(e) => setDefaultOwnerId(e.target.value)}
          >
            <option value="">Unassigned</option>
            {(() => {
              const memberIds = new Set((members || []).map((m: any) => m.userId));
              const memberUsers = (allUsers || []).filter((u: any) => memberIds.has(u.id));
              return memberUsers.map((u: any) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.email})
                </option>
              ));
            })()}
          </select>
          <div className="mt-1 text-xs text-muted">Only board members can be assigned.</div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-xs text-muted mb-1">Default type</div>
            <select
              className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
              value={defaultType}
              onChange={(e) => setDefaultType(e.target.value)}
            >
              {taskTypes
                .filter((t) => t.enabled !== false)
                .slice()
                .sort((a, b) => a.position - b.position)
                .map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <div className="text-xs text-muted mb-1">Default priority</div>
            <select
              className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
              value={defaultPriority}
              onChange={(e) => setDefaultPriority(e.target.value)}
            >
              {priorities
                .filter((p) => p.enabled !== false)
                .slice()
                .sort((a, b) => a.rank - b.rank)
                .map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.name}
                  </option>
                ))}
            </select>
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-sm">
        <input id="skip" type="checkbox" checked={skipIfTitleExists} onChange={(e) => setSkipIfTitleExists(e.target.checked)} />
        <label htmlFor="skip" className="text-muted">
          Skip if a task with the same title already exists in this board
        </label>
      </div>

      <div className="mt-5">
        <Tabs value={mode} onValueChange={(v) => setMode(v as any)}>
          <TabsList>
            <TabsTrigger value="list">Paste list</TabsTrigger>
            <TabsTrigger value="csv">Upload CSV</TabsTrigger>
          </TabsList>

          <TabsContent value="list" className="mt-3">
            <div className="text-xs text-muted mb-1">One task title per line</div>
            <textarea
              className="min-h-40 w-full rounded-2xl bg-white/5 border border-white/10 p-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
              placeholder={"- PowerZac risks - update doc\n- Follow up Dora can't be completed"}
              value={listText}
              onChange={(e) => setListText(e.target.value)}
            />
          </TabsContent>

          <TabsContent value="csv" className="mt-3">
            <div className="text-xs text-muted">CSV supports headers. Minimum column: title. Optional: description.</div>
            <div className="mt-3 flex items-center gap-3">
              <Input
                type="file"
                accept=".csv,text/csv"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  setCsvFilename(f.name);
                  const txt = await f.text();
                  setCsvText(txt);
                }}
              />
              {csvFilename ? <div className="text-xs text-muted">{csvFilename}</div> : null}
            </div>
            <div className="mt-3 text-xs text-muted">Or paste CSV</div>
            <textarea
              className="min-h-40 w-full rounded-2xl bg-white/5 border border-white/10 p-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              placeholder={"title,description\n\"Task A\",\"Do something\""}
            />
            <div className="mt-2 text-xs text-muted">Optional columns: tags (semicolon-separated), idempotencyKey.</div>
          </TabsContent>
        </Tabs>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm font-semibold">Preview</div>
          <div className="text-xs text-muted">{items.length} items</div>
        </div>
        {items.length === 0 ? (
          <div className="mt-2 text-xs text-muted">No items parsed yet.</div>
        ) : (
          <div className="mt-3 space-y-2">
            {preview.map((it, idx) => (
              <div key={`${idx}-${it.title}`} className={cn("rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm", idx % 2 ? "bg-black/10" : "")}>
                <div className="font-medium">{normalizeTitleForPreview(it.title)}</div>
                {it.description ? <div className="mt-1 text-xs text-muted line-clamp-2">{it.description}</div> : null}
                {it.tags && it.tags.length ? <div className="mt-1 text-[11px] text-muted">tags: {it.tags.join(", ")}</div> : null}
              </div>
            ))}
            {items.length > preview.length ? <div className="text-xs text-muted">…and {items.length - preview.length} more</div> : null}
          </div>
        )}
      </div>

      <div className="mt-5 flex items-center justify-end gap-3">
        <Button onClick={runImport} disabled={importing || items.length === 0}>
          {importing ? "Importing…" : "Import tasks"}
        </Button>
      </div>

      {results ? (
        <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">Result</div>
          <div className="mt-1 text-xs text-muted">
            Created {results.createdCount}, existing {results.existingCount}
          </div>
          <div className="mt-3 space-y-2">
            {(results.results || []).slice(0, 30).map((r: any) => (
              <div key={r.key} className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm">
                <div className="truncate">
                  <span className={cn("mr-2 text-xs", r.status === "created" ? "text-ok" : "text-muted")}>{r.status}</span>
                  {r.task?.title}
                </div>
                <div className="text-xs text-muted truncate">{r.key}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
