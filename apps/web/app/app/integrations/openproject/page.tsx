"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";

export default function OpenProjectIntegrationPage() {
  const { user } = useSession();
  const isAdmin = user?.role === "admin";
  const [loading, setLoading] = useState(false);
  const [connections, setConnections] = useState<any[]>([]);
  const [form, setForm] = useState({
    name: "OpenProject Prod",
    baseUrl: "",
    apiToken: "",
    projectIdentifier: ""
  });

  const refresh = async () => {
    if (!isAdmin) return;
    try {
      const list = await api.openprojectConnections();
      setConnections(list);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-semibold">OpenProject Integration</div>
          <div className="mt-2 text-sm text-muted">
            Connect OpenProject and verify access. Next slice will add work-package sync and two-way comments.
          </div>
        </div>
        <Badge variant="warn">MVP Baseline</Badge>
      </div>

      {!isAdmin ? <div className="mt-6 text-sm text-muted">Admin + MFA session required.</div> : null}

      {isAdmin ? (
        <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">Add connection</div>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-muted">Name</div>
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <div className="text-xs text-muted">Project identifier (optional)</div>
              <Input value={form.projectIdentifier} onChange={(e) => setForm((f) => ({ ...f, projectIdentifier: e.target.value }))} placeholder="e.g. platform" />
            </div>
            <div>
              <div className="text-xs text-muted">Base URL</div>
              <Input value={form.baseUrl} onChange={(e) => setForm((f) => ({ ...f, baseUrl: e.target.value }))} placeholder="https://openproject.example.com" />
            </div>
            <div>
              <div className="text-xs text-muted">API token</div>
              <Input type="password" value={form.apiToken} onChange={(e) => setForm((f) => ({ ...f, apiToken: e.target.value }))} placeholder="••••••••" />
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <Button
              size="sm"
              disabled={loading || !form.baseUrl.trim() || !form.apiToken.trim()}
              onClick={async () => {
                setLoading(true);
                try {
                  await api.openprojectConnect({
                    name: form.name.trim() || "OpenProject",
                    baseUrl: form.baseUrl.trim(),
                    apiToken: form.apiToken.trim(),
                    projectIdentifier: form.projectIdentifier.trim() || null,
                    enabled: true
                  });
                  toast.success("OpenProject connection saved");
                  setForm({ name: "OpenProject Prod", baseUrl: "", apiToken: "", projectIdentifier: "" });
                  await refresh();
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                } finally {
                  setLoading(false);
                }
              }}
            >
              Save connection
            </Button>
            <Button size="sm" variant="ghost" onClick={refresh} disabled={loading}>
              Refresh
            </Button>
          </div>
        </div>
      ) : null}

      {isAdmin ? (
        <div className="mt-4 space-y-3">
          {connections.length === 0 ? <div className="text-sm text-muted">No OpenProject connections yet.</div> : null}
          {connections.map((c) => (
            <div key={c.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center gap-2">
                <Badge variant={c.enabled ? "ok" : "muted"}>{c.enabled ? "Enabled" : "Disabled"}</Badge>
                <div className="text-sm font-semibold">{c.name}</div>
                <div className="text-xs text-muted">{c.tokenHint || ""}</div>
              </div>
              <div className="mt-1 text-xs text-muted">{c.baseUrl}</div>
              <div className="mt-1 text-xs text-muted">project: {c.projectIdentifier || "(none)"}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={loading}
                  onClick={async () => {
                    setLoading(true);
                    try {
                      const out = await api.openprojectTestConnection(c.id);
                      toast.success(`Connected: ${out?.result?.instanceName || "OpenProject"}`);
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  Test
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={loading}
                  onClick={async () => {
                    setLoading(true);
                    try {
                      await api.openprojectUpdateConnection(c.id, { enabled: !c.enabled });
                      await refresh();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  {c.enabled ? "Disable" : "Enable"}
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  disabled={loading}
                  onClick={async () => {
                    if (!confirm(`Delete ${c.name}?`)) return;
                    setLoading(true);
                    try {
                      await api.openprojectDeleteConnection(c.id);
                      toast.success("Connection deleted");
                      await refresh();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
