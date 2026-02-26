"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export default function WebhooksPage() {
  const { user } = useSession();
  const isAdmin = user?.role === "admin";
  const [secrets, setSecrets] = useState<any[] | null>(null);
  const [events, setEvents] = useState<any[] | null>(null);
  const [form, setForm] = useState({ source: "shortcuts", enabled: true, bearerToken: "" });
  const [revealed, setRevealed] = useState<string | null>(null);
  const [publicApiBaseOverride, setPublicApiBaseOverride] = useState("");

  const load = async () => {
    if (!isAdmin) return;
    try {
      const [s, e] = await Promise.all([api.webhookSecrets(), api.webhookEvents(null, 50)]);
      setSecrets(s);
      setEvents(e);
    } catch (err: any) {
      toast.error(String(err?.message || err));
    }
  };

  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem("nl-public-api-base") : "";
    if (saved) setPublicApiBaseOverride(saved);
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("nl-public-api-base", publicApiBaseOverride.trim());
    }
  }, [publicApiBaseOverride]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  const publicWebBase = useMemo(() => {
    const configured = String(process.env.NEXT_PUBLIC_PUBLIC_WEB_URL || "").trim();
    if (configured) return configured.replace(/\/+$/, "");
    if (typeof window !== "undefined" && window.location?.origin) return window.location.origin;
    return "http://localhost:3000";
  }, []);
  const publicApiBase = useMemo(() => {
    if (publicApiBaseOverride.trim()) return publicApiBaseOverride.trim().replace(/\/+$/, "");
    const configured = String(process.env.NEXT_PUBLIC_PUBLIC_API_URL || "").trim();
    if (!configured) return "";
    return configured.replace(/\/+$/, "");
  }, [publicApiBaseOverride]);
  const endpoint = useMemo(() => `${publicWebBase}/api/webhooks/inbound/shortcuts`, [publicWebBase]);
  const endpointDirectApi = useMemo(() => (publicApiBase ? `${publicApiBase}/webhooks/inbound/shortcuts` : ""), [publicApiBase]);

  if (!isAdmin) {
    return <div className="h-full p-6 text-muted">Admin only.</div>;
  }

  return (
    <div className="h-full overflow-auto px-4 pb-10 scrollbar">
      <div className="mt-4 max-w-5xl">
        <div className="flex items-center gap-2">
          <div className="text-lg font-semibold">Webhooks</div>
          <Badge variant="muted">Inbox</Badge>
        </div>
        <div className="mt-2 text-sm text-muted">
          Configure inbound webhooks for automations (Apple Shortcuts/Siri, other systems). Tokens are stored encrypted.
        </div>

        <div className="mt-4 grid md:grid-cols-2 gap-3">
          <div className="glass rounded-3xl shadow-neon border border-white/10 p-4">
            <div className="text-sm font-semibold">Create / update secret</div>
            <div className="mt-2 text-xs text-muted">Inbound endpoint (Shortcuts)</div>
            <div className="mt-1 rounded-2xl border border-white/10 bg-black/30 p-2 text-xs overflow-auto">{endpoint}</div>
            <div className="mt-2 flex justify-end">
              <Button size="sm" variant="ghost" onClick={async () => { await navigator.clipboard.writeText(endpoint); toast.success("Copied"); }}>
                Copy URL
              </Button>
            </div>
            <div className="mt-3 text-xs text-muted mb-1">Public API base override (for reverse proxy / external IP)</div>
            <Input
              value={publicApiBaseOverride}
              onChange={(e) => setPublicApiBaseOverride(e.target.value)}
              placeholder="https://your.domain/api or https://your.domain"
            />
            {endpointDirectApi ? (
              <>
                <div className="mt-3 text-xs text-muted">Direct API endpoint (optional)</div>
                <div className="mt-1 rounded-2xl border border-white/10 bg-black/30 p-2 text-xs overflow-auto">{endpointDirectApi}</div>
                <div className="mt-2 flex justify-end">
                  <Button size="sm" variant="ghost" onClick={async () => { await navigator.clipboard.writeText(endpointDirectApi); toast.success("Copied"); }}>
                    Copy API URL
                  </Button>
                </div>
              </>
            ) : (
              <div className="mt-2 text-xs text-muted">
                Set <span className="font-mono">NEXT_PUBLIC_PUBLIC_WEB_URL</span> (and optionally <span className="font-mono">NEXT_PUBLIC_PUBLIC_API_URL</span>) for a copy/paste URL
                when deployed.
              </div>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <div className="text-xs text-muted mb-1">Source</div>
                <Input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} placeholder="shortcuts" />
              </div>
              <div className="col-span-2">
                <div className="text-xs text-muted mb-1">Bearer token</div>
                <Input value={form.bearerToken} onChange={(e) => setForm({ ...form, bearerToken: e.target.value })} placeholder="paste or leave blank to generate" />
                {form.bearerToken.trim() && form.bearerToken.trim().length < 12 ? (
                  <div className="mt-1 text-xs text-warn">Token must be at least 12 characters (or leave blank to auto-generate).</div>
                ) : null}
              </div>
              <label className="col-span-2 flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
                Enabled
              </label>
            </div>

            <div className="mt-3 flex justify-end gap-2">
              <Button variant="ghost" onClick={load}>
                Refresh
              </Button>
              <Button
                variant="ghost"
                onClick={async () => {
                  try {
                    const src = form.source.trim();
                    if (!src) return;
                    const res = await api.webhookUpsertSecret({
                      source: src,
                      enabled: true,
                      bearerToken: null
                    });
                    setRevealed(res?.bearerToken || null);
                    setForm((f) => ({ ...f, enabled: true, bearerToken: "" }));
                    await load();
                    toast.success("Generated");
                  } catch (err: any) {
                    toast.error(String(err?.message || err));
                  }
                }}
              >
                Generate token
              </Button>
              <Button
                onClick={async () => {
                  try {
                    const res = await api.webhookUpsertSecret({
                      source: form.source.trim(),
                      enabled: form.enabled,
                      bearerToken: form.bearerToken.trim() || null
                    });
                    setRevealed(res?.bearerToken || null);
                    setForm((f) => ({ ...f, bearerToken: "" }));
                    await load();
                    toast.success("Saved");
                  } catch (err: any) {
                    toast.error(String(err?.message || err));
                  }
                }}
              >
                Save
              </Button>
            </div>

            {revealed ? (
              <div className="mt-4 rounded-2xl border border-accent/30 bg-accent/10 p-3">
                <div className="text-sm font-semibold">Token (copy now)</div>
                <div className="mt-1 text-xs text-muted">This is shown once. Store it in Apple Shortcuts / your system config.</div>
                <div className="mt-2 rounded-2xl border border-white/10 bg-black/30 p-2 text-xs overflow-auto">{revealed}</div>
                <div className="mt-2 flex justify-end">
                  <Button size="sm" variant="ghost" onClick={async () => { await navigator.clipboard.writeText(revealed); toast.success("Copied"); }}>
                    Copy token
                  </Button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="glass rounded-3xl shadow-neon border border-white/10 p-4">
            <div className="text-sm font-semibold">Configured sources</div>
            <div className="mt-2 text-xs text-muted">Rotate to generate a new token; old token stops working immediately.</div>

            {secrets === null ? (
              <Skeleton className="h-24 w-full mt-3" />
            ) : secrets.length === 0 ? (
              <div className="mt-3 text-sm text-muted">No secrets yet.</div>
            ) : (
              <div className="mt-3 space-y-2">
                {secrets.map((s) => (
                  <div key={s.source} className="rounded-2xl border border-white/10 bg-white/5 p-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{s.source}</div>
                      <div className="text-xs text-muted truncate">{s.tokenHint}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={s.enabled ? "ok" : "muted"}>{s.enabled ? "enabled" : "disabled"}</Badge>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={async () => {
                          try {
                            const res = await api.webhookRotateSecret(s.source);
                            setRevealed(res?.bearerToken || null);
                            await load();
                            toast.success("Rotated");
                          } catch (err: any) {
                            toast.error(String(err?.message || err));
                          }
                        }}
                      >
                        Rotate
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={async () => {
                          if (!confirm(`Disable webhook source “${s.source}”?`)) return;
                          try {
                            await api.webhookDisableSecret(s.source);
                            await load();
                            toast.success("Disabled");
                          } catch (err: any) {
                            toast.error(String(err?.message || err));
                          }
                        }}
                      >
                        Disable
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mt-3 glass rounded-3xl shadow-neon border border-white/10 p-4">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-sm font-semibold">Inbound webhook inbox</div>
              <div className="text-xs text-muted">Recent events, payload processing result, and replay for debugging.</div>
            </div>
            <Button variant="ghost" onClick={load}>
              Refresh
            </Button>
          </div>

          {events === null ? (
            <Skeleton className="h-24 w-full mt-3" />
          ) : events.length === 0 ? (
            <div className="mt-3 text-sm text-muted">No events yet.</div>
          ) : (
            <div className="mt-3 space-y-2">
              {events.map((ev) => (
                <div key={ev.id} className="rounded-2xl border border-white/10 bg-white/5 p-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">
                      {ev.source} <span className="text-xs text-muted">• {new Date(ev.receivedAt).toLocaleString()}</span>
                    </div>
                    <div className="text-xs text-muted truncate">
                      {ev.error ? `Error: ${ev.error}` : ev.result ? `Result: ${JSON.stringify(ev.result)}` : "—"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={ev.error ? "danger" : "ok"}>{ev.error ? "error" : "ok"}</Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        if (!confirm("Replay this event? (Safe only if idempotencyKey was used.)")) return;
                        try {
                          const res = await api.webhookReplay(ev.id);
                          toast.success(`Replayed: ${JSON.stringify(res?.result || {})}`);
                          await load();
                        } catch (err: any) {
                          toast.error(String(err?.message || err));
                        }
                      }}
                    >
                      Replay
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
