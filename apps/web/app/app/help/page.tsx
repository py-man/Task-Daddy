"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";

const sections = [
  { id: "start-here", title: "Start Here" },
  { id: "smtp-setup", title: "SMTP Setup" },
  { id: "core-flow", title: "Core Flow" },
  { id: "calendar-reminders", title: "Calendar + Reminders" },
  { id: "integrations", title: "Integrations" },
  { id: "api-and-webhooks", title: "API + Webhooks" },
  { id: "mobile", title: "Mobile Quick Capture" },
  { id: "security", title: "Security" }
] as const;

export default function HelpPage() {
  return (
    <div className="h-full overflow-auto px-4 pb-10 scrollbar">
      <div className="mt-4 max-w-6xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="text-lg font-semibold">Task-Daddy Help</div>
          <Badge variant="muted">Small tasks. Big momentum.</Badge>
        </div>
        <div className="mt-2 text-sm text-muted max-w-3xl">
          Stop keeping your life in your head. This guide is designed for fast setup and fast recovery when something breaks.
        </div>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4 items-start">
          <aside className="rounded-3xl border border-white/10 bg-white/5 p-3 lg:sticky lg:top-4">
            <div className="text-xs uppercase tracking-wide text-muted">Jump to</div>
            <div className="mt-2 space-y-1">
              {sections.map((s) => (
                <a key={s.id} href={`#${s.id}`} className="block rounded-xl px-2.5 py-2 text-sm text-muted hover:text-text hover:bg-white/10 transition">
                  {s.title}
                </a>
              ))}
            </div>
          </aside>

          <div className="space-y-4">
            <Section id="start-here" title="Start Here">
              <ul className="list-disc pl-5 space-y-1 text-sm text-muted">
                <li>Create a board in <span className="text-text">Board</span> view.</li>
                <li>Add tasks with title first. Keep it short and outcome-focused.</li>
                <li>Open a task to edit details, owner, due date, comments, and AI enhancements.</li>
                <li>Use <span className="text-text">Home</span> for recent/today/week momentum tracking.</li>
              </ul>
            </Section>

            <Section id="smtp-setup" title="SMTP Setup (Password Reset + Reminder Emails)">
              <ol className="list-decimal pl-5 space-y-1 text-sm text-muted">
                <li>Go to <span className="text-text">Settings → Notifications</span>.</li>
                <li>In <span className="text-text">Email (SMTP)</span>, enter Host, Port, From, and To.</li>
                <li>Use <span className="text-text">Port 587 + StartTLS</span> unless your provider requires another mode.</li>
                <li>Click <span className="text-text">Save</span>, then <span className="text-text">Send test</span>.</li>
                <li>If test fails, verify provider credentials and sender policy (SPF/DKIM/domain rules).</li>
              </ol>
              <div className="mt-3 rounded-2xl border border-white/10 bg-black/25 p-3 text-xs overflow-auto">
                Required fields: host, from, to. Optional: username/password if auth is required.
              </div>
            </Section>

            <Section id="core-flow" title="Core Flow: Capture → Clarify → Complete">
              <ul className="list-disc pl-5 space-y-1 text-sm text-muted">
                <li>Capture quickly in board/list/mobile quick note.</li>
                <li>Clarify in task drawer: add description, priority, due date, owner, checklist.</li>
                <li>Complete by moving lanes and keeping blocked items visible.</li>
                <li>Task AI is preview-first: suggestions only apply when you explicitly click apply.</li>
              </ul>
            </Section>

            <Section id="calendar-reminders" title="Calendar + Reminders">
              <ul className="list-disc pl-5 space-y-1 text-sm text-muted">
                <li>Set due date on a task and click <span className="text-text">Export .ics</span> to download calendar invite.</li>
                <li>Click <span className="text-text">Email .ics</span> to send the same invite via SMTP.</li>
                <li>Use <span className="text-text">Remind me</span> to schedule in-app and optional external notifications.</li>
              </ul>
            </Section>

            <Section id="integrations" title="Integrations (Jira + OpenProject)">
              <ul className="list-disc pl-5 space-y-1 text-sm text-muted">
                <li>Jira/OpenProject are opt-in per task. Link once, sync many times.</li>
                <li>Create/sync actions are idempotent to avoid duplicate issue creation.</li>
                <li>If sync fails, check integration credentials and key mapping in task drawer Integration tab.</li>
              </ul>
              <div className="mt-2 text-xs">
                <Link href="/app/integrations/jira" className="underline text-muted hover:text-text">Open Jira settings</Link>
                <span className="mx-2 text-muted">•</span>
                <Link href="/app/integrations/openproject" className="underline text-muted hover:text-text">Open OpenProject settings</Link>
              </div>
            </Section>

            <Section id="api-and-webhooks" title="API + Webhooks">
              <div className="text-xs text-muted mb-2">Useful endpoints</div>
              <pre className="rounded-2xl border border-white/10 bg-black/30 p-3 text-xs overflow-auto">
{`Web app proxy: http://localhost:3005/api
Direct API:    http://localhost:8000

Inbound webhook:
POST /webhooks/inbound/{source}
Authorization: Bearer <TOKEN>`}
              </pre>
              <div className="mt-2 text-xs text-muted">Use idempotency keys for external create_task calls to prevent duplicates.</div>
            </Section>

            <Section id="mobile" title="Mobile Quick Capture">
              <ul className="list-disc pl-5 space-y-1 text-sm text-muted">
                <li>Use inline quick note on mobile board for fast capture.</li>
                <li>Use FAB quick add when you need owner/type/priority/due date at creation time.</li>
                <li>Then tidy up on desktop with full drawer editing and integrations.</li>
              </ul>
            </Section>

            <Section id="security" title="Security + Access">
              <ul className="list-disc pl-5 space-y-1 text-sm text-muted">
                <li>MFA: enable from <span className="text-text">Settings → Security</span>.</li>
                <li>Trusted devices: during MFA login, check remember device for 30 days.</li>
                <li>Admins can invite users, set/reset passwords, and block login without deleting ownership history.</li>
              </ul>
            </Section>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="rounded-3xl border border-white/10 bg-white/5 p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}
