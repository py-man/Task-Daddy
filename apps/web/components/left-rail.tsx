"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, CalendarDays, Home, LayoutGrid, List, Plug, Settings, Webhook } from "lucide-react";
import { cn } from "@/lib/cn";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { TaskDaddyLogo } from "@/components/brand/task-daddy-logo";

const items = [
  { href: "/app/home", icon: Home, label: "Home" },
  { href: "/app/board", icon: LayoutGrid, label: "Board" },
  { href: "/app/list", icon: List, label: "List" },
  { href: "/app/calendar", icon: CalendarDays, label: "Calendar" },
  { href: "/app/integrations/jira", icon: Plug, label: "Jira" },
  { href: "/app/integrations/webhooks", icon: Webhook, label: "Webhooks" },
  { href: "/app/help", icon: BookOpen, label: "Help" }
] as const;

export function LeftRail({ variant = "rail" }: { variant?: "rail" | "bottom" }) {
  const pathname = usePathname();
  if (variant === "bottom") {
    return (
      <div className="fixed bottom-0 left-0 right-0 z-40 p-3 pt-0">
        <div className="glass rounded-2xl shadow-neon border border-white/10 px-2 py-2 flex items-center justify-around">
          {items.map((it) => {
            const active = pathname?.startsWith(it.href);
            const Icon = it.icon;
            return (
              <Link
                key={it.href}
                href={it.href}
                className={cn(
                  "h-11 w-14 rounded-2xl grid place-items-center border transition",
                  active ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 bg-white/0 hover:bg-white/5"
                )}
              >
                <Icon size={18} className={active ? "text-text" : "text-muted"} />
              </Link>
            );
          })}
          <Link
            href="/app/settings"
            className={cn(
              "h-11 w-14 rounded-2xl grid place-items-center border transition",
              pathname?.startsWith("/app/settings")
                ? "border-accent/30 bg-accent/10 shadow-neon"
                : "border-white/10 bg-white/0 hover:bg-white/5"
            )}
          >
            <Settings size={18} className={pathname?.startsWith("/app/settings") ? "text-text" : "text-muted"} />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen p-3 flex flex-col gap-3">
      <div className="glass rounded-2xl p-3 shadow-neon">
        <div className="h-9 w-9 rounded-2xl border border-accent/30 bg-accent/10 grid place-items-center">
          <TaskDaddyLogo size={28} />
        </div>
      </div>

      <TooltipProvider>
        <div className="glass rounded-2xl p-2 flex flex-col gap-2 shadow-neon">
          {items.map((it) => {
            const active = pathname?.startsWith(it.href);
            const Icon = it.icon;
            return (
              <Tooltip key={it.href}>
                <TooltipTrigger asChild>
                  <Link
                    href={it.href}
                    className={cn(
                      "h-11 w-11 rounded-2xl grid place-items-center border transition",
                      active ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 bg-white/0 hover:bg-white/5"
                    )}
                  >
                    <Icon size={18} className={active ? "text-text" : "text-muted"} />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right">{it.label}</TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </TooltipProvider>

      <div className="flex-1" />

      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="glass rounded-2xl p-2 shadow-neon">
              <Link
                href="/app/settings"
                className="h-11 w-11 rounded-2xl grid place-items-center border border-white/10 hover:bg-white/5 transition"
              >
                <Settings size={18} className="text-muted" />
              </Link>
            </div>
          </TooltipTrigger>
          <TooltipContent side="right">Settings</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
