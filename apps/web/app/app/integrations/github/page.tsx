"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";

export default function GitHubIntegrationPage() {
  const { user } = useSession();
  const isAdmin = user?.role === "admin";
  const [loading, setLoading] = useState(false);
  const [connections, setConnections] = useState<any[]>([]);
  const [form, setForm] = useState({
    name: "GitHub Prod",
    baseUrl: "https://api.github.com",
    apiToken: "",
    defaultOwner: "",
    defaultRepo: ""
  });
  const [showApiToken, setShowApiToken] = useState(false);

  const refresh = async () => {
    if (!isAdmin) return;
    try {
      const list = await api.githubConnections();
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
          <div className="text-lg font-semibold">GitHub Integration</div>
          <div className="mt-2 text-sm text-muted">
            Connect GitHub and verify API access. Next slice adds issue/project sync at task level.
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
              <div className="text-xs text-muted">Base URL</div>
              <Input value={form.baseUrl} onChange={(e) => setForm((f) => ({ ...f, baseUrl: e.target.value }))} placeholder="https://api.github.com" />
            </div>
            <div>
              <div className="text-xs text-muted">Default owner (optional)</div>
              <Input value={form.defaultOwner} onChange={(e) => setForm((f) => ({ ...f, defaultOwner: e.target.value }))} placeholder="task-daddy" />
            </div>
            <div>
              <div className="text-xs text-muted">Default repo (optional)</div>
              <Input value={form.defaultRepo} onChange={(e) => setForm((f) => ({ ...f, defaultRepo: e.target.value }))} placeholder="task-daddy" />
            </div>
            <div className="md:col-span-2">
              <div className="text-xs text-muted">API token</div>
              <Input type={showApiToken ? "text" : "password"} value={form.apiToken} onChange={(e) => setForm((f) => ({ ...f, apiToken: e.target.value }))} placeholder="ghp_..." />
              <label className="mt-1 flex items-center gap-2 text-xs text-muted">
                <input type="checkbox" checked={showApiToken} onChange={(e) => setShowApiToken(e.target.checked)} />
                <span>Show token</span>
              </label>
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <Button
              size="sm"
              disabled={loading || !form.apiToken.trim()}
              onClick={async () => {
                setLoading(true);
                try {
                  await api.githubConnect({
                    name: form.name.trim() || "GitHub",
                    baseUrl: form.baseUrl.trim() || "https://api.github.com",
                    apiToken: form.apiToken.trim(),
                    defaultOwner: form.defaultOwner.trim() || null,
                    defaultRepo: form.defaultRepo.trim() || null,
                    enabled: true
                  });
                  toast.success("GitHub connection saved");
                  setForm({ name: "GitHub Prod", baseUrl: "https://api.github.com", apiToken: "", defaultOwner: "", defaultRepo: "" });
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
          {connections.length === 0 ? <div className="text-sm text-muted">No GitHub connections yet.</div> : null}
          {connections.map((c) => (
            <div key={c.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center gap-2">
                <Badge variant={c.enabled ? "ok" : "muted"}>{c.enabled ? "Enabled" : "Disabled"}</Badge>
                <div className="text-sm font-semibold">{c.name}</div>
                <div className="text-xs text-muted">{c.tokenHint || ""}</div>
              </div>
              <div className="mt-1 text-xs text-muted">{c.baseUrl}</div>
              <div className="mt-1 text-xs text-muted">
                default repo: {(c.defaultOwner || "-") + "/" + (c.defaultRepo || "-")}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={loading}
                  onClick={async () => {
                    setLoading(true);
                    try {
                      const out = await api.githubTestConnection(c.id);
                      toast.success(`Connected: ${out?.result?.login || "GitHub"}`);
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
                      await api.githubUpdateConnection(c.id, { enabled: !c.enabled });
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
                      await api.githubDeleteConnection(c.id);
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

