"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LayoutGrid, Bell, Settings } from "lucide-react";
import { cn } from "@/lib/cn";

const tabs = [
  { href: "/app/home", icon: Home, label: "Home" },
  { href: "/app/board", icon: LayoutGrid, label: "Board" },
  { href: "/app/inbox", icon: Bell, label: "Inbox" },
  { href: "/app/settings", icon: Settings, label: "Settings" }
] as const;

export function MobileBottomNav() {
  const pathname = usePathname();
  return (
    <div className="fixed left-0 right-0 z-40 px-2.5 bottom-[calc(max(8px,env(safe-area-inset-bottom))+var(--nl-vv-bottom,0px)+var(--nl-mobile-bottom-extra,0px))]">
      <div className="glass rounded-xl shadow-neon border border-white/10 px-1.5 py-1 flex items-center justify-around">
        {tabs.map((t) => {
          const active = pathname === t.href || pathname?.startsWith(`${t.href}/`);
          const Icon = t.icon;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={cn(
                "h-10 w-[23vw] max-w-[88px] rounded-lg grid place-items-center border transition",
                active ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 bg-white/0 hover:bg-white/5"
              )}
              aria-label={t.label}
            >
              <div className="flex items-center gap-1.5">
                <Icon size={16} className={active ? "text-text" : "text-muted"} />
                <div className={cn("text-[10px] leading-none", active ? "text-text" : "text-muted")}>{t.label}</div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
