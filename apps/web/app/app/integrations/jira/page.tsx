"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useSession } from "@/components/session";
import { useBoard } from "@/components/board-context";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export default function JiraPage() {
  const { user } = useSession();
  const { board } = useBoard();
  const [connections, setConnections] = useState<any[] | null>(null);
  const [profiles, setProfiles] = useState<any[] | null>(null);
  const [runs, setRuns] = useState<any[] | null>(null);
  const [connectForm, setConnectForm] = useState({ name: "Primary Jira", baseUrl: "", email: "", token: "", defaultAssigneeAccountId: "" });
  const [importForm, setImportForm] = useState({
    connectionId: "",
    jql: "project = DEMO ORDER BY updated DESC",
    statusToStateKey: `{\n  "To Do": "backlog",\n  "In Progress": "in_progress",\n  "Done": "done"\n}`,
    priorityMap: `{\n  "Highest": "P0",\n  "High": "P1",\n  "Medium": "P2",\n  "Low": "P3"\n}`,
    typeMap: `{\n  "Bug": "Bug",\n  "Task": "Feature",\n  "Story": "Feature"\n}`,
    conflictPolicy: "jiraWins"
  });
  const [importing, setImporting] = useState(false);
  const [syncingNow, setSyncingNow] = useState(false);

  const refresh = async () => {
    try {
      const [cs, ps, rs] = await Promise.all([
        api.jiraConnections(),
        board?.id ? api.jiraProfiles(board.id) : Promise.resolve([]),
        board?.id ? api.jiraSyncRuns(board.id) : Promise.resolve([])
      ]);
      setConnections(cs);
      setProfiles(ps);
      setRuns(rs);
      if (!importForm.connectionId) {
        const preferred = cs.find((c: any) => !c.needsReconnect) || cs[0];
        if (preferred) setImportForm((f) => ({ ...f, connectionId: preferred.id }));
      }
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [board?.id]);

  const canConnect = user?.role === "admin";

  const lastRun = runs?.[0] || null;
  const selectedConnection = useMemo(
    () => (connections || []).find((c: any) => c.id === importForm.connectionId) || null,
    [connections, importForm.connectionId]
  );
  const firstProfile = (profiles || [])[0] || null;
  const firstProfileConnection = useMemo(
    () => (connections || []).find((c: any) => c.id === firstProfile?.connectionId) || null,
    [connections, firstProfile?.connectionId]
  );

  if (!board) return <div className="h-full p-6 text-muted">Select a board first.</div>;

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="px-4 pb-3 flex items-center gap-2">
        <div className="text-sm font-semibold">Jira</div>
        {lastRun ? (
          <Badge variant={lastRun.status === "success" ? "ok" : "danger"}>
            Last: {lastRun.status} • {new Date(lastRun.startedAt).toLocaleString()}
          </Badge>
        ) : (
          <Badge variant="muted">No sync runs</Badge>
        )}
        <div className="flex-1" />
        <Button variant="ghost" onClick={refresh}>
          Refresh
        </Button>
      </div>

      <div className="flex-1 overflow-auto px-4 pb-6 scrollbar">
        <div className="grid grid-cols-2 gap-4">
          <div className="glass rounded-3xl shadow-neon border border-white/10 p-4">
            <div className="text-sm font-semibold">Connect</div>
            <div className="text-xs text-muted mt-1">Admin only for MVP.</div>
            {!canConnect ? <div className="mt-3 text-sm text-muted">You are `{user?.role}`.</div> : null}

            <div className="mt-4 space-y-2">
              <div className="text-xs text-muted">Name</div>
              <Input value={connectForm.name} onChange={(e) => setConnectForm({ ...connectForm, name: e.target.value })} placeholder="e.g. Primary Jira" />
              <div className="text-xs text-muted">Base URL</div>
              <Input
                data-testid="jira-base-url"
                value={connectForm.baseUrl}
                onChange={(e) => setConnectForm({ ...connectForm, baseUrl: e.target.value })}
                placeholder="https://your-domain.atlassian.net"
              />
              <Button
                size="sm"
                variant="ghost"
                disabled={!canConnect}
                onClick={async () => {
                  try {
                    await api.jiraConnectEnv();
                    toast.success("Connected via server env");
                    await refresh();
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Use server env Jira
              </Button>
              <div className="text-xs text-muted">Email (Cloud) or leave blank (PAT)</div>
              <Input
                data-testid="jira-email"
                value={connectForm.email}
                onChange={(e) => setConnectForm({ ...connectForm, email: e.target.value })}
                placeholder="you@company.com"
              />
              <div className="text-xs text-muted">API token / PAT</div>
              <Input
                data-testid="jira-token"
                type="password"
                value={connectForm.token}
                onChange={(e) => setConnectForm({ ...connectForm, token: e.target.value })}
                placeholder="••••••••"
              />
              <div className="text-xs text-muted">Default assignee accountId (optional)</div>
              <Input
                data-testid="jira-default-assignee"
                value={connectForm.defaultAssigneeAccountId}
                onChange={(e) => setConnectForm({ ...connectForm, defaultAssigneeAccountId: e.target.value })}
                placeholder="e.g. 712020:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />
              <Button
                data-testid="jira-save-connection"
                className="mt-2"
                disabled={!canConnect}
                onClick={async () => {
                  try {
                    await api.jiraConnect({
                      name: connectForm.name,
                      baseUrl: connectForm.baseUrl,
                      email: connectForm.email || null,
                      token: connectForm.token,
                      defaultAssigneeAccountId: connectForm.defaultAssigneeAccountId.trim() || null
                    });
                    toast.success("Connected");
                    setConnectForm({ name: "Primary Jira", baseUrl: "", email: "", token: "", defaultAssigneeAccountId: "" });
                    await refresh();
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Save connection
              </Button>
            </div>

            <div className="mt-5 text-sm font-semibold">Connections</div>
            {connections === null ? (
              <Skeleton className="h-20 w-full mt-2" />
            ) : connections.length === 0 ? (
              <div className="text-xs text-muted mt-2">No connections.</div>
            ) : (
              <div className="mt-2 space-y-2">
                {connections.map((c) => (
                  <div key={c.id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <div className="flex items-center gap-2">
                      <Input
                        className="glass border-white/10"
                        value={c.name || ""}
                        onChange={(e) => setConnections((prev) => (prev ? prev.map((x) => (x.id === c.id ? { ...x, name: e.target.value } : x)) : prev))}
                        placeholder="Connection name"
                      />
                      <Input
                        className="glass border-white/10"
                        value={c.defaultAssigneeAccountId || ""}
                        onChange={(e) =>
                          setConnections((prev) =>
                            prev ? prev.map((x) => (x.id === c.id ? { ...x, defaultAssigneeAccountId: e.target.value } : x)) : prev
                          )
                        }
                        placeholder="Default assignee accountId"
                      />
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={!canConnect}
                        onClick={async () => {
                          try {
                            await api.jiraUpdateConnection(c.id, {
                              name: (c.name || "").trim() || null,
                              defaultAssigneeAccountId: (c.defaultAssigneeAccountId || "").trim() || null
                            });
                            toast.success("Saved");
                            await refresh();
                          } catch (e: any) {
                            toast.error(String(e?.message || e));
                          }
                        }}
                      >
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        disabled={!canConnect}
                        onClick={async () => {
                          if (!confirm("Delete this Jira connection? Linked tasks will be unlinked.")) return;
                          try {
                            await api.jiraDeleteConnection(c.id);
                            toast.success("Deleted");
                            await refresh();
                          } catch (e: any) {
                            toast.error(String(e?.message || e));
                          }
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                    <div className="text-xs text-muted">{c.baseUrl}</div>
                    <div className="text-xs text-muted">{c.email || "Bearer token"}</div>
                    {c.needsReconnect ? <div className="text-xs text-danger mt-1">Needs reconnect: {c.reconnectReason || "Token invalid for current key"}</div> : null}
                    {c.defaultAssigneeAccountId ? <div className="text-xs text-muted">Default assignee: {c.defaultAssigneeAccountId}</div> : null}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="glass rounded-3xl shadow-neon border border-white/10 p-4">
            <div className="text-sm font-semibold">Import / Sync</div>
            <div className="text-xs text-muted mt-1">Import issues by JQL into this board, mapping Jira status → lane `stateKey`.</div>

            <div className="mt-4 space-y-2">
              <div className="text-xs text-muted">Connection</div>
              <select
                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
                value={importForm.connectionId}
                onChange={(e) => setImportForm({ ...importForm, connectionId: e.target.value })}
              >
                <option value="">Select…</option>
                {(connections || []).map((c) => (
                  <option key={c.id} value={c.id} disabled={Boolean(c.needsReconnect)}>
                    {c.name ? `${c.name} • ` : ""}
                    {c.baseUrl}
                    {c.needsReconnect ? " (Needs reconnect)" : ""}
                  </option>
                ))}
              </select>
              {selectedConnection?.needsReconnect ? (
                <div className="text-xs text-danger">Selected connection needs reconnect. Re-save token in Connect first.</div>
              ) : null}

              <div className="text-xs text-muted">JQL</div>
              <Input value={importForm.jql} onChange={(e) => setImportForm({ ...importForm, jql: e.target.value })} />

              <div className="text-xs text-muted">statusToStateKey (JSON)</div>
              <textarea
                className="min-h-24 w-full rounded-2xl bg-white/5 border border-white/10 p-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                value={importForm.statusToStateKey}
                onChange={(e) => setImportForm({ ...importForm, statusToStateKey: e.target.value })}
              />

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-xs text-muted">priorityMap (JSON)</div>
                  <textarea
                    className="min-h-24 w-full rounded-2xl bg-white/5 border border-white/10 p-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                    value={importForm.priorityMap}
                    onChange={(e) => setImportForm({ ...importForm, priorityMap: e.target.value })}
                  />
                </div>
                <div>
                  <div className="text-xs text-muted">typeMap (JSON)</div>
                  <textarea
                    className="min-h-24 w-full rounded-2xl bg-white/5 border border-white/10 p-3 text-sm text-text outline-none focus:ring-2 focus:ring-accent/40"
                    value={importForm.typeMap}
                    onChange={(e) => setImportForm({ ...importForm, typeMap: e.target.value })}
                  />
                </div>
              </div>

              <div className="text-xs text-muted">Conflict policy</div>
              <select
                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
                value={importForm.conflictPolicy}
                onChange={(e) => setImportForm({ ...importForm, conflictPolicy: e.target.value })}
              >
                <option value="jiraWins">jiraWins</option>
                <option value="appWins">appWins (not implemented)</option>
                <option value="manual">manual (not implemented)</option>
              </select>

              <div className="flex gap-2">
                <Button
                  disabled={importing || syncingNow}
                  onClick={async () => {
                    if (!importForm.connectionId) {
                      toast.error("Select a Jira connection first.");
                      return;
                    }
                    if (selectedConnection?.needsReconnect) {
                      toast.error("Selected connection needs reconnect. Re-save token in Connect first.");
                      return;
                    }
                    try {
                      setImporting(true);
                      let statusToStateKey: Record<string, string>;
                      let priorityMap: Record<string, string>;
                      let typeMap: Record<string, string>;
                      try {
                        statusToStateKey = JSON.parse(importForm.statusToStateKey);
                        priorityMap = JSON.parse(importForm.priorityMap);
                        typeMap = JSON.parse(importForm.typeMap);
                      } catch {
                        toast.error("Invalid JSON mapping. Check status/priority/type map fields.");
                        return;
                      }
                      const run = await api.jiraImport({
                        boardId: board.id,
                        connectionId: importForm.connectionId,
                        jql: importForm.jql,
                        statusToStateKey,
                        priorityMap,
                        typeMap,
                        conflictPolicy: importForm.conflictPolicy
                      });
                      toast.success("Import started");
                      setRuns((prev) => [run, ...(prev || [])]);
                      await refresh();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setImporting(false);
                    }
                  }}
                >
                  {importing ? "Importing…" : "Import by JQL"}
                </Button>
                <Button
                  variant="ghost"
                  disabled={importing || syncingNow}
                  onClick={async () => {
                    if (firstProfileConnection?.needsReconnect) {
                      toast.error("Profile connection needs reconnect. Re-save token in Connect first.");
                      return;
                    }
                    try {
                      setSyncingNow(true);
                      const ps = profiles || [];
                      const p = ps[0];
                      if (!p) {
                        toast.error("No sync profile yet. Run an import first.");
                        return;
                      }
                      const run = await api.jiraSyncNow(p.id);
                      toast.success("Sync started");
                      setRuns((prev) => [run, ...(prev || [])]);
                      await refresh();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setSyncingNow(false);
                    }
                  }}
                >
                  {syncingNow ? "Syncing…" : "Sync Now"}
                </Button>
                <Button
                  variant="ghost"
                  disabled={!board?.id}
                  onClick={async () => {
                    if (!board?.id) return;
                    if (!confirm("Clear Jira sync run logs for this board?")) return;
                    try {
                      await api.jiraClearSyncRuns(board.id);
                      toast.success("Cleared");
                      await refresh();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    }
                  }}
                >
                  Clear logs
                </Button>
              </div>
              {!importForm.connectionId ? <div className="text-xs text-warn">Import disabled: select a Jira connection.</div> : null}
              {selectedConnection?.needsReconnect ? (
                <div className="text-xs text-danger">Import blocked: selected connection needs reconnect.</div>
              ) : null}
              {!(profiles || []).length ? <div className="text-xs text-muted">Sync Now needs a profile created by Import.</div> : null}
            </div>

            <div className="mt-5 text-sm font-semibold">Sync runs</div>
            {runs === null ? (
              <Skeleton className="h-28 w-full mt-2" />
            ) : runs.length === 0 ? (
              <div className="text-xs text-muted mt-2">No runs.</div>
            ) : (
              <div className="mt-2 space-y-2">
                {runs.slice(0, 8).map((r) => (
                  <details key={r.id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <summary className="cursor-pointer text-sm">
                      <span className={r.status === "success" ? "text-ok" : "text-danger"}>{r.status}</span>{" "}
                      <span className="text-muted">•</span> {new Date(r.startedAt).toLocaleString()}
                    </summary>
                    <pre className="mt-2 text-xs text-muted whitespace-pre-wrap">{JSON.stringify(r.log, null, 2)}</pre>
                    {r.errorMessage ? <div className="mt-2 text-xs text-danger">{r.errorMessage}</div> : null}
                  </details>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
