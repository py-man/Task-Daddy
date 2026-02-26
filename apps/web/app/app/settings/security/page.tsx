"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { makeQrSvg } from "@/lib/qr";

export default function SettingsSecurityPage() {
  const { user } = useSession();
  const [mfaPassword, setMfaPassword] = useState("");
  const [mfaStart, setMfaStart] = useState<{ secret: string; otpauthUri: string } | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disableRecovery, setDisableRecovery] = useState("");

  const [sessions, setSessions] = useState<any[] | null>(null);
  const [trustedDevices, setTrustedDevices] = useState<any[] | null>(null);
  const [apiTokens, setApiTokens] = useState<any[] | null>(null);
  const [tokenName, setTokenName] = useState("CLI");
  const [tokenPassword, setTokenPassword] = useState("");
  const [tokenCreated, setTokenCreated] = useState<{ token: string; hint: string } | null>(null);

  const loadSessions = async () => {
    try {
      const ss = await api.sessions();
      setSessions(ss);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  const loadApiTokens = async () => {
    try {
      const ts = await api.apiTokens();
      setApiTokens(ts);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  const loadTrustedDevices = async () => {
    try {
      const ds = await api.mfaTrustedDevices();
      setTrustedDevices(ds);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  useEffect(() => {
    loadSessions();
    loadTrustedDevices();
    loadApiTokens();
  }, []);

  const qr = useMemo(() => {
    if (!mfaStart?.otpauthUri) return null;
    try {
      return makeQrSvg(mfaStart.otpauthUri, 180);
    } catch {
      return null;
    }
  }, [mfaStart?.otpauthUri]);

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-lg font-semibold">Security</div>
          <div className="mt-1 text-sm text-muted">MFA, sessions, and password reset.</div>
        </div>
        {user?.mfaEnabled ? <Badge variant="ok">MFA enabled</Badge> : <Badge variant="warn">MFA disabled</Badge>}
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">Multi-factor authentication (TOTP)</div>
          <div className="mt-1 text-xs text-muted">Use Google Authenticator / Microsoft Authenticator / 1Password.</div>

          {!user?.mfaEnabled ? (
            <div className="mt-4 space-y-3">
              <div>
                <div className="text-xs text-muted mb-1">Confirm your password</div>
                <Input type="password" value={mfaPassword} onChange={(e) => setMfaPassword(e.target.value)} placeholder="••••••••" />
              </div>
              <Button
                variant="ghost"
                onClick={async () => {
                  try {
                    const res = await api.mfaStart(mfaPassword);
                    setMfaStart(res);
                    setRecoveryCodes(null);
                    toast.success("MFA setup started");
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Start MFA setup
              </Button>

              {mfaStart ? (
                <div className="mt-4 rounded-3xl border border-white/10 bg-black/20 p-4">
                  <div className="text-sm font-semibold">Step 2: Add to authenticator</div>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4 items-start">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-2 grid place-items-center">
                      {qr ? <div dangerouslySetInnerHTML={{ __html: qr }} /> : <div className="text-xs text-muted p-6">QR unavailable. Use secret.</div>}
                    </div>
                    <div className="space-y-2 text-sm">
                      <div>
                        <div className="text-xs text-muted">Secret</div>
                        <div className="mt-1 font-mono text-xs break-all">{mfaStart.secret}</div>
                      </div>
                      <div>
                        <div className="text-xs text-muted">otpauth URI</div>
                        <div className="mt-1 font-mono text-xs break-all">{mfaStart.otpauthUri}</div>
                      </div>
                      <div className="text-xs text-muted">If scanning fails, add a new TOTP entry manually using the secret.</div>
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="text-xs text-muted mb-1">Enter a 6-digit code to confirm</div>
                    <Input value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} placeholder="123456" />
                  </div>
                  <div className="mt-3 flex justify-end">
                    <Button
                      variant="ghost"
                      onClick={async () => {
                        try {
                          const out = await api.mfaConfirm(mfaCode);
                          setRecoveryCodes(out.recoveryCodes);
                          toast.success("MFA enabled");
                          setMfaStart(null);
                          setMfaPassword("");
                          setMfaCode("");
                          await loadSessions();
                          window.location.reload();
                        } catch (e: any) {
                          toast.error(String(e?.message || e));
                        }
                      }}
                    >
                      Enable MFA
                    </Button>
                  </div>
                </div>
              ) : null}

              {recoveryCodes ? (
                <div className="mt-4 rounded-3xl border border-white/10 bg-black/20 p-4">
                  <div className="text-sm font-semibold">Recovery codes</div>
                  <div className="mt-1 text-xs text-muted">Store these somewhere safe. Each code can be used once.</div>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {recoveryCodes.map((c) => (
                      <div key={c} className="font-mono text-xs rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                        {c}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <div className="text-sm text-muted">MFA is enabled on your account.</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div>
                  <div className="text-xs text-muted mb-1">Confirm password</div>
                  <Input type="password" value={disablePassword} onChange={(e) => setDisablePassword(e.target.value)} />
                </div>
                <div>
                  <div className="text-xs text-muted mb-1">TOTP code</div>
                  <Input value={disableCode} onChange={(e) => setDisableCode(e.target.value)} placeholder="123456" />
                </div>
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Or recovery code</div>
                <Input value={disableRecovery} onChange={(e) => setDisableRecovery(e.target.value)} placeholder="ABCD1234-EFGH5678" />
              </div>
              <div className="flex justify-end">
                <Button
                  variant="danger"
                  onClick={async () => {
                    try {
                      await api.mfaDisable({
                        password: disablePassword,
                        totpCode: disableCode.trim() || null,
                        recoveryCode: disableRecovery.trim() || null,
                      });
                      toast.success("MFA disabled");
                      window.location.reload();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    }
                  }}
                >
                  Disable MFA
                </Button>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">Sessions</div>
          <div className="mt-1 text-xs text-muted">Review active sessions and revoke access.</div>

          {sessions === null ? (
            <div className="mt-3 text-sm text-muted">Loading…</div>
          ) : (
            <div className="mt-3 space-y-2">
              {sessions.map((s) => (
                <div key={s.id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs text-muted truncate">{s.userAgent || "Unknown agent"}</div>
                    {s.mfaVerified ? <Badge variant="ok">MFA</Badge> : <Badge variant="warn">No MFA</Badge>}
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {s.createdIp ? `IP ${s.createdIp} • ` : ""}
                    {new Date(s.createdAt).toLocaleString()} → {new Date(s.expiresAt).toLocaleString()}
                  </div>
                  <div className="mt-2 flex justify-end">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        try {
                          await api.revokeSession(s.id);
                          toast.success("Revoked");
                          await loadSessions();
                        } catch (e: any) {
                          toast.error(String(e?.message || e));
                        }
                      }}
                    >
                      Revoke
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap justify-end gap-2">
            {user?.role === "admin" ? (
              <Button
                variant="danger"
                onClick={async () => {
                  try {
                    await api.revokeAllSessionsGlobal();
                    toast.success("All sessions revoked globally");
                    window.location.href = "/login";
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                Revoke all sessions (global)
              </Button>
            ) : null}
            <Button
              variant="danger"
              onClick={async () => {
                try {
                  await api.revokeAllSessions();
                  toast.success("Logged out everywhere");
                  window.location.href = "/login";
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                }
              }}
            >
              Logout all devices
            </Button>
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="text-sm font-semibold">MFA trusted devices</div>
          <div className="mt-1 text-xs text-muted">Devices that can skip MFA for up to 30 days.</div>

          {trustedDevices === null ? (
            <div className="mt-3 text-sm text-muted">Loading…</div>
          ) : trustedDevices.length === 0 ? (
            <div className="mt-3 text-sm text-muted">No trusted devices.</div>
          ) : (
            <div className="mt-3 space-y-2">
              {trustedDevices.map((d) => (
                <div key={d.id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs text-muted truncate">{d.userAgent || "Unknown device"}</div>
                    {d.revokedAt ? <Badge variant="muted">Revoked</Badge> : <Badge variant="ok">Trusted</Badge>}
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {d.createdIp ? `IP ${d.createdIp} • ` : ""}
                    Added {new Date(d.createdAt).toLocaleString()}
                    {d.lastUsedAt ? ` • Last used ${new Date(d.lastUsedAt).toLocaleString()}` : ""}
                    {d.expiresAt ? ` • Expires ${new Date(d.expiresAt).toLocaleString()}` : ""}
                  </div>
                  <div className="mt-2 flex justify-end">
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={Boolean(d.revokedAt)}
                      onClick={async () => {
                        try {
                          await api.revokeMfaTrustedDevice(d.id);
                          toast.success("Trusted device revoked");
                          await loadTrustedDevices();
                        } catch (e: any) {
                          toast.error(String(e?.message || e));
                        }
                      }}
                    >
                      Revoke
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 flex justify-end">
            <Button
              variant="danger"
              onClick={async () => {
                try {
                  await api.revokeAllMfaTrustedDevices();
                  toast.success("All trusted devices revoked");
                  await loadTrustedDevices();
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                }
              }}
            >
              Revoke all trusted devices
            </Button>
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-sm font-semibold">API tokens</div>
              <div className="mt-1 text-xs text-muted">Personal access tokens for CLI tools and automations. Tokens are shown once.</div>
            </div>
            <Badge variant="muted">Bearer</Badge>
          </div>

          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
            <div>
              <div className="text-xs text-muted mb-1">Token name</div>
              <Input value={tokenName} onChange={(e) => setTokenName(e.target.value)} placeholder="e.g. Laptop CLI" />
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Confirm password</div>
              <Input type="password" value={tokenPassword} onChange={(e) => setTokenPassword(e.target.value)} placeholder="••••••••" />
            </div>
          </div>

          <div className="mt-3 flex justify-end">
            <Button
              variant="ghost"
              onClick={async () => {
                try {
                  const out = await api.createApiToken(tokenName, tokenPassword);
                  setTokenCreated({ token: out.token, hint: out.tokenHint });
                  toast.success("Token created");
                  await loadApiTokens();
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                }
              }}
            >
              Create token
            </Button>
          </div>

          {tokenCreated ? (
            <div className="mt-3 rounded-2xl border border-white/10 bg-black/20 p-3">
              <div className="text-xs text-muted">New token</div>
              <div className="mt-2 font-mono text-xs break-all">{tokenCreated.token}</div>
              <div className="mt-2 flex justify-end gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(tokenCreated.token);
                      toast.success("Copied");
                    } catch {
                      toast.error("Copy failed");
                    }
                  }}
                >
                  Copy
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setTokenCreated(null)}>
                  Done
                </Button>
              </div>
              <div className="mt-2 text-[11px] text-muted">Store this token now. You won’t be able to view it again.</div>
            </div>
          ) : null}

          <div className="mt-4">
            <div className="text-xs text-muted mb-2">Your tokens</div>
            {apiTokens === null ? (
              <div className="text-sm text-muted">Loading…</div>
            ) : apiTokens.length === 0 ? (
              <div className="text-sm text-muted">No tokens created yet.</div>
            ) : (
              <div className="space-y-2">
                {apiTokens.map((t) => (
                  <div key={t.id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium truncate">{t.name}</div>
                      {t.revokedAt ? <Badge variant="muted">Revoked</Badge> : <Badge variant="ok">{t.tokenHint}</Badge>}
                    </div>
                    <div className="mt-1 text-xs text-muted">
                      Created {new Date(t.createdAt).toLocaleString()}
                      {t.lastUsedAt ? ` • Last used ${new Date(t.lastUsedAt).toLocaleString()}` : ""}
                    </div>
                    <div className="mt-2 flex justify-end">
                      <Button
                        size="sm"
                        variant="danger"
                        disabled={Boolean(t.revokedAt)}
                        onClick={async () => {
                          const ok = confirm("Revoke this token? It will stop working immediately.");
                          if (!ok) return;
                          try {
                            await api.revokeApiToken(t.id, tokenPassword);
                            toast.success("Revoked");
                            await loadApiTokens();
                          } catch (e: any) {
                            toast.error(String(e?.message || e));
                          }
                        }}
                      >
                        Revoke
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">Password reset</div>
        <div className="mt-1 text-xs text-muted">If you forget your password, use the Login page “Forgot password” flow.</div>
      </div>
    </div>
  );
}
