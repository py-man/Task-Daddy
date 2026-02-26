"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { TaskDaddyLogo } from "@/components/brand/task-daddy-logo";
import { App3DLayer } from "@/components/app-3d-layer";

export default function LoginPage() {
  const router = useRouter();
  const version = process.env.NEXT_PUBLIC_APP_VERSION || "v2026-02-26+r3-hardening";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaMode, setMfaMode] = useState<"totp" | "recovery">("totp");
  const [rememberDevice, setRememberDevice] = useState(true);
  const [totpCode, setTotpCode] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [resetNewPassword, setResetNewPassword] = useState("");
  const [resetOpen, setResetOpen] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const nextRaw = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("next") || "/app/home" : "/app/home";
  const nextPath = nextRaw.startsWith("/") && !nextRaw.startsWith("//") ? nextRaw : "/app/home";

  useEffect(() => {
    if (typeof window === "undefined") return;
    const p = new URLSearchParams(window.location.search);
    if ((p.get("mode") || "").toLowerCase() === "reset") {
      setResetMode(true);
      const tok = (p.get("token") || "").trim();
      if (tok) setResetToken(tok);
    }
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const normalizedEmail = email.trim().toLowerCase();
      setMfaRequired(false);
      await api.login(normalizedEmail, password);
      toast.success("Welcome back");
      router.replace(nextPath);
    } catch (err: any) {
      const msg = String(err?.message || err);
      if (msg.includes("MFA required")) {
        setMfaRequired(true);
        toast.message("MFA required", { description: "Enter your authenticator code (or use a recovery code) to finish signing in." });
      } else {
        toast.error(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const onSubmitMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const normalizedEmail = email.trim().toLowerCase();
      if (mfaMode === "totp") {
        await api.loginMfa(normalizedEmail, password, { totpCode: totpCode.trim(), rememberDevice });
      } else {
        await api.loginMfa(normalizedEmail, password, { recoveryCode: recoveryCode.trim(), rememberDevice });
      }
      toast.success("Signed in");
      router.replace(nextPath);
    } catch (err: any) {
      toast.error(String(err?.message || err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen w-screen grid place-items-center px-6 relative overflow-hidden">
      <App3DLayer mode="general" blockedCount={0} overdueCount={0} respectSettings={false} />
      <div className="glass nl-login-card w-full max-w-md rounded-3xl p-6 shadow-neon relative z-10">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xl font-semibold">Task-Daddy</div>
            <div className="text-sm text-muted">{resetMode ? "Set a new password." : "Small tasks. Big momentum."}</div>
          </div>
          <div className="h-10 w-10 rounded-2xl border border-accent/30 bg-accent/10 shadow-neon grid place-items-center">
            <TaskDaddyLogo size={30} />
          </div>
        </div>
        {resetMode ? (
          <div className="mt-5 space-y-3">
            <div className="space-y-1">
              <div className="text-xs text-muted">Reset token</div>
              <Input value={resetToken} onChange={(e) => setResetToken(e.target.value)} placeholder="paste token here" />
            </div>
            <div className="space-y-1">
              <div className="text-xs text-muted">New password</div>
              <Input type="password" value={resetNewPassword} onChange={(e) => setResetNewPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <Button
              className="w-full"
              disabled={loading || !resetToken.trim() || resetNewPassword.length < 8}
              onClick={async () => {
                setLoading(true);
                try {
                  await api.passwordResetConfirm(resetToken, resetNewPassword);
                  if (typeof window !== "undefined") {
                    const u = new URL(window.location.href);
                    u.searchParams.delete("mode");
                    u.searchParams.delete("token");
                    window.history.replaceState({}, "", `${u.pathname}${u.search}`);
                  }
                  toast.success("Password updated. You can sign in now.");
                  setResetMode(false);
                  setResetToken("");
                  setResetNewPassword("");
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                } finally {
                  setLoading(false);
                }
              }}
            >
              Set new password
            </Button>
            <Button
              variant="ghost"
              className="w-full"
              onClick={() => {
                if (typeof window !== "undefined") {
                  const u = new URL(window.location.href);
                  u.searchParams.delete("mode");
                  u.searchParams.delete("token");
                  window.history.replaceState({}, "", `${u.pathname}${u.search}`);
                }
                setResetMode(false);
              }}
            >
              Back to sign in
            </Button>
          </div>
        ) : (
          <>
            <form onSubmit={mfaRequired ? onSubmitMfa : onSubmit} className="mt-5 space-y-3" autoComplete="off">
              <div className="space-y-1">
                <div className="text-xs text-muted">Email</div>
                <Input
                  data-testid="login-email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="off"
                  placeholder="you@company.com"
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted">Password</div>
                <Input
                  data-testid="login-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type="password"
                  autoComplete="off"
                  placeholder="••••••••"
                />
              </div>

              {mfaRequired ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-3 space-y-2">
                  <div className="text-sm font-semibold">MFA verification</div>
                  <div className="text-xs text-muted">Use your authenticator app, or enter a recovery code.</div>

                  <div className="flex gap-2">
                    <Button type="button" variant={mfaMode === "totp" ? "primary" : "ghost"} disabled={loading} onClick={() => setMfaMode("totp")}>
                      Authenticator
                    </Button>
                    <Button
                      type="button"
                      variant={mfaMode === "recovery" ? "primary" : "ghost"}
                      disabled={loading}
                      onClick={() => setMfaMode("recovery")}
                    >
                      Recovery
                    </Button>
                  </div>

                  {mfaMode === "totp" ? (
                    <div className="space-y-1">
                      <div className="text-xs text-muted">Authenticator code</div>
                      <Input
                        data-testid="login-mfa-totp"
                        value={totpCode}
                        onChange={(e) => setTotpCode(e.target.value)}
                        placeholder="123456"
                        inputMode="numeric"
                        autoComplete="one-time-code"
                      />
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <div className="text-xs text-muted">Recovery code</div>
                      <Input
                        data-testid="login-mfa-recovery"
                        value={recoveryCode}
                        onChange={(e) => setRecoveryCode(e.target.value)}
                        placeholder="NL-XXXX-XXXX"
                        autoComplete="off"
                      />
                    </div>
                  )}

                  <div className="flex items-center justify-between gap-2 pt-1">
                    <label className="flex items-center gap-2 text-xs text-muted">
                      <input type="checkbox" checked={rememberDevice} onChange={(e) => setRememberDevice(e.target.checked)} />
                      Remember this device for 30 days
                    </label>
                  </div>
                  <div className="flex items-center justify-between gap-2 pt-1">
                    <Button
                      type="button"
                      variant="ghost"
                      disabled={loading}
                      onClick={() => {
                        setMfaRequired(false);
                        setTotpCode("");
                        setRecoveryCode("");
                      }}
                    >
                      Back
                    </Button>
                    <Button data-testid="login-mfa-submit" type="submit" disabled={loading || (mfaMode === "totp" ? !totpCode.trim() : !recoveryCode.trim())}>
                      Verify
                    </Button>
                  </div>
                </div>
              ) : null}

              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Signing in…" : mfaRequired ? "Verify" : "Sign in"}
              </Button>
            </form>

            <div className="mt-3 flex justify-end">
              <Dialog open={resetOpen} onOpenChange={setResetOpen}>
                <DialogTrigger asChild>
                  <button className="text-xs text-muted hover:text-text underline">Forgot password?</button>
                </DialogTrigger>
                <DialogContent>
                  <div className="text-lg font-semibold">Reset password</div>
                  <div className="mt-1 text-sm text-muted">
                    Request a reset token. In local dev, the API can be configured to return the token (no email yet).
                  </div>

                  <div className="mt-4 space-y-2">
                    <div className="text-xs text-muted">Email</div>
                    <Input value={resetEmail} onChange={(e) => setResetEmail(e.target.value)} placeholder="you@company.com" />
                    <div className="flex justify-end">
                      <Button
                        variant="ghost"
                        onClick={async () => {
                          try {
                            const base = typeof window !== "undefined" ? window.location.origin : undefined;
                            const res = await api.passwordResetRequest(resetEmail.trim().toLowerCase(), base);
                            if (res?.token) {
                              setResetToken(res.token);
                              toast.success("Token generated (dev mode)");
                            } else if (res?.emailSent) {
                              toast.success("Reset email sent");
                            } else {
                              toast.success("If the account exists, a reset email will be sent");
                            }
                          } catch (e: any) {
                            toast.error(String(e?.message || e));
                          }
                        }}
                      >
                        Request token
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </>
        )}

        <div className="mt-4 text-xs text-muted">
          Use your organization account credentials. If you don’t have access, ask an admin.
        </div>
        <div className="mt-2 text-xs text-muted">{version}</div>
      </div>
    </div>
  );
}
