"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { FEATURES } from "@/lib/features";

type NavItem = { href: string; label: string };

const baseItems: NavItem[] = [
  { href: "/app/settings", label: "Overview" },
  { href: "/app/settings/appearance", label: "Appearance" },
  { href: "/app/settings/boards", label: "Boards" },
  { href: "/app/settings/users", label: "Users" },
  { href: "/app/settings/fields", label: "Fields" },
  { href: "/app/settings/integrations", label: "Integrations" },
  { href: "/app/settings/notifications", label: "Notifications" },
  { href: "/app/settings/imports", label: "Imports" },
  { href: "/app/settings/ai", label: "AI" },
  { href: "/app/settings/security", label: "Security" },
  { href: "/app/settings/backups", label: "Backups" },
  { href: "/app/settings/diagnostics", label: "Diagnostics" }
];

const systemStatusItem: NavItem = { href: "/app/settings/system-status", label: "System Status" };

export function SettingsNav() {
  const pathname = usePathname();
  const navItems = useMemo(() => {
    if (!FEATURES.systemStatus) {
      return baseItems;
    }
    const list = [...baseItems];
    list.splice(2, 0, systemStatusItem);
    return list;
  }, []);
  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-3">
      <div className="flex items-center justify-between gap-2 px-2 pt-1">
        <div className="text-sm font-semibold">Settings</div>
        <Badge variant="muted">Control plane</Badge>
      </div>
      <div className="mt-3 flex md:block gap-2 md:space-y-1 overflow-x-auto scrollbar pb-1">
        {navItems.map((it) => {
          const active = pathname === it.href || (it.href !== "/app/settings" && pathname?.startsWith(it.href));
          return (
            <Link
              key={it.href}
              href={it.href}
              className={cn(
                "shrink-0 md:block rounded-2xl px-3 py-2 text-sm border transition",
                active ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 hover:bg-white/5"
              )}
            >
              {it.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
