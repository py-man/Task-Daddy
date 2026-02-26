"use client";

import { useSession } from "@/components/session";
import { useBoard } from "@/components/board-context";
import Link from "next/link";

export default function SettingsPage() {
  const { user } = useSession();
  const { board } = useBoard();

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="text-lg font-semibold">Settings</div>
      <div className="mt-2 text-sm text-muted">Task-Daddy control plane for boards, users, integrations, security, and diagnostics.</div>

      <div className="mt-4 space-y-2 text-sm">
        <div>
          <span className="text-muted">Signed in:</span> {user?.email} ({user?.role})
        </div>
        <div>
          <span className="text-muted">Current board:</span> {board?.name || "—"}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3">
        <CardLink title="Appearance" desc="Background layer styles (off/grid/grain/ascii) and motion-safe defaults." href="/app/settings/appearance" />
        <CardLink title="Boards" desc="Create/rename/delete boards, manage members, and safe deletion (transfer or delete)." href="/app/settings/boards" />
        <CardLink title="Users" desc="Directory, roles, disable/delete, and profile fields (admin)." href="/app/settings/users" />
        <CardLink title="Fields" desc="Customize task types and priorities per board." href="/app/settings/fields" />
        <CardLink title="Integrations" desc="Jira connections and Webhooks (Shortcuts-ready)." href="/app/settings/integrations" />
        <CardLink title="Notifications" desc="Pushover (MVP), email/webhooks next. Includes a test-send button." href="/app/settings/notifications" />
        <CardLink title="Imports" desc="Paste a list or upload CSV to create tasks idempotently in a selected board." href="/app/settings/imports" />
        <CardLink title="Security" desc="MFA (TOTP), sessions, password reset flows." href="/app/settings/security" />
        <CardLink title="Backups" desc="Exports + full backups + restore (coming next)." href="/app/settings/backups" />
        <CardLink title="Diagnostics" desc="Health, versions, last sync runs, last errors." href="/app/settings/diagnostics" />
      </div>

      <div className="mt-6 flex flex-wrap gap-3 text-sm">
        <Link href="/app/help" className="text-muted hover:text-text underline">
          Help & docs
        </Link>
        <Link href="/app/integrations/jira" className="text-muted hover:text-text underline">
          Jira
        </Link>
        <Link href="/app/integrations/webhooks" className="text-muted hover:text-text underline">
          Webhooks
        </Link>
      </div>
    </div>
  );
}

function CardLink({ title, desc, href }: { title: string; desc: string; href: string }) {
  return (
    <Link href={href} className="rounded-3xl border border-white/10 bg-white/5 hover:bg-white/7 transition p-4 block">
      <div className="text-sm font-semibold">{title}</div>
      <div className="mt-1 text-xs text-muted">{desc}</div>
    </Link>
  );
}
