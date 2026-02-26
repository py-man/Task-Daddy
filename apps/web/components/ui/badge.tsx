"use client";

import { cn } from "@/lib/cn";

export function Badge({
  children,
  className,
  variant = "muted"
}: {
  children: React.ReactNode;
  className?: string;
  variant?: "muted" | "accent" | "danger" | "warn" | "ok";
}) {
  const base = "nl-badge inline-flex shrink-0 whitespace-nowrap items-center rounded-full border px-2 py-0.5 text-[11px] leading-4";
  const map = {
    muted: "border-white/10 bg-white/5 text-muted",
    accent: "border-accent/30 bg-accent/10 text-text",
    danger: "border-danger/40 bg-danger/10 text-text",
    warn: "border-warn/40 bg-warn/10 text-text",
    ok: "border-ok/40 bg-ok/10 text-text"
  } as const;
  return <span className={cn(base, map[variant], className)}>{children}</span>;
}
