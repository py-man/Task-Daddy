"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function IndexPage() {
  const router = useRouter();
  const version = process.env.NEXT_PUBLIC_APP_VERSION || "v2026-02-26+r3-hardening";

  useEffect(() => {
    (async () => {
      try {
        await api.me();
        router.replace("/app/home");
      } catch {
        router.replace("/login");
      }
    })();
  }, [router]);

  return (
    <div style={{ height: "100vh", display: "grid", placeItems: "center" }}>
      <div className="glass" style={{ padding: 16, borderRadius: 16, boxShadow: "0 20px 60px rgb(0 0 0 / 0.45)" }}>
        <div className="text-sm text-muted">Task-Daddy {version}</div>
        <div className="mt-1">Loading…</div>
      </div>
    </div>
  );
}
