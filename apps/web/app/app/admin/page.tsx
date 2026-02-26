"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session";

export default function AdminPage() {
  const router = useRouter();
  const { user } = useSession();

  useEffect(() => {
    router.replace("/app/settings/users");
  }, [router]);

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="text-lg font-semibold">Admin moved</div>
      <div className="mt-2 text-sm text-muted">Admin tools are now under Settings → Users / Boards.</div>
      <div className="mt-3 text-sm text-muted">Signed in as {user?.email || "—"}.</div>
    </div>
  );
}

