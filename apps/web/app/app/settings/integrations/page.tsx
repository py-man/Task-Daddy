"use client";

import Link from "next/link";
import { useSession } from "@/components/session";

export default function SettingsIntegrationsPage() {
  const { user } = useSession();
  const isAdmin = user?.role === "admin";

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="text-lg font-semibold">Integrations</div>
      <div className="mt-2 text-sm text-muted">Manage external systems: Jira, inbound webhooks (Shortcuts), and outbound automations.</div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3">
        <Link href="/app/integrations/jira" className="rounded-3xl border border-white/10 bg-white/5 hover:bg-white/7 transition p-4 block">
          <div className="text-sm font-semibold">Jira</div>
          <div className="mt-1 text-xs text-muted">Connections, sync profiles, sync runs, and per-task linking.</div>
        </Link>
        <Link href="/app/integrations/webhooks" className="rounded-3xl border border-white/10 bg-white/5 hover:bg-white/7 transition p-4 block">
          <div className="text-sm font-semibold">Webhooks</div>
          <div className="mt-1 text-xs text-muted">Inbound webhook secrets + event inbox + replay.</div>
        </Link>
        <Link href="/app/integrations/openproject" className="rounded-3xl border border-white/10 bg-white/5 hover:bg-white/7 transition p-4 block">
          <div className="text-sm font-semibold">OpenProject</div>
          <div className="mt-1 text-xs text-muted">Connection management is live: add, test, enable/disable, delete.</div>
        </Link>
      </div>

      {!isAdmin ? <div className="mt-6 text-sm text-muted">Some integration settings require Admin + MFA session.</div> : null}
    </div>
  );
}
