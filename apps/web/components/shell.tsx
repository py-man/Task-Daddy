"use client";

import { motion } from "framer-motion";
import { LeftRail } from "@/components/left-rail";
import { TopBar } from "@/components/top-bar";
import { CommandPalette } from "@/components/command-palette";
import { MobileBottomNav } from "@/components/mobile/mobile-bottom-nav";
import { MobileHeader } from "@/components/mobile/mobile-header";
import { MobileFab } from "@/components/mobile/mobile-fab";
import { App3DLayer } from "@/components/app-3d-layer";
import { getApp3dEnabled } from "@/components/app-3d-layer";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useBoard } from "@/components/board-context";
import { motionTokens } from "@/lib/motion";
import { applyUiDesignFromStorage, ensureUiDesignForRole, getUiDesign, type UiDesign } from "@/lib/ui-design";
import { useSession } from "@/components/session";

export function AppShell({ children }: { children: React.ReactNode }) {
  const version = process.env.NEXT_PUBLIC_APP_VERSION || "v2026-02-26+r3-hardening";
  const pathname = usePathname();
  const { lanes, tasks } = useBoard();
  const laneTypeById = useMemo(() => new Map(lanes.map((lane) => [lane.id, lane.type])), [lanes]);

  const blockedCount = useMemo(
    () => tasks.filter((task) => task.blocked || laneTypeById.get(task.laneId) === "blocked").length,
    [laneTypeById, tasks]
  );
  const overdueCount = useMemo(() => {
    const now = Date.now();
    return tasks.filter((task) => {
      const due = task.dueDate ? new Date(task.dueDate).getTime() : NaN;
      const laneType = laneTypeById.get(task.laneId) || "active";
      return !Number.isNaN(due) && due < now && laneType !== "done";
    }).length;
  }, [laneTypeById, tasks]);

  const mode: "board" | "list" | "calendar" | "settings" | "reports" | "general" = pathname.includes("/calendar")
    ? "calendar"
    : pathname.includes("/list")
      ? "list"
      : pathname.includes("/settings")
        ? "settings"
        : pathname.includes("/reports")
          ? "reports"
          : pathname.includes("/board")
            ? "board"
            : "general";
  const [app3dEnabled, setApp3dEnabled] = useState(true);
  const [mobileChromeHidden, setMobileChromeHidden] = useState(false);
  const [uiDesign, setUiDesign] = useState<UiDesign>("core");
  const { user } = useSession();

  useEffect(() => {
    setApp3dEnabled(getApp3dEnabled());
    setUiDesign(applyUiDesignFromStorage());
    const onStorage = (event: StorageEvent) => {
      if (event.key === "nl:app3dEnabled") setApp3dEnabled(getApp3dEnabled());
      if (event.key === "nl-ui-design") setUiDesign(getUiDesign());
    };
    const onCustom = () => setApp3dEnabled(getApp3dEnabled());
    const onDesign = () => setUiDesign(getUiDesign());
    window.addEventListener("storage", onStorage);
    window.addEventListener("nl:app3dChanged", onCustom as EventListener);
    window.addEventListener("nl:uiDesignChanged", onDesign as EventListener);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("nl:app3dChanged", onCustom as EventListener);
      window.removeEventListener("nl:uiDesignChanged", onDesign as EventListener);
    };
  }, []);

  useEffect(() => {
    if (!user) return;
    setUiDesign(ensureUiDesignForRole((user as any).role));
  }, [user]);

  useEffect(() => {
    const onMobileChrome = (evt: Event) => {
      const detail = (evt as CustomEvent<{ hidden?: boolean; source?: string }>).detail || {};
      if (detail.source !== "board") return;
      setMobileChromeHidden(Boolean(detail.hidden));
    };
    window.addEventListener("nl:mobile-chrome", onMobileChrome as EventListener);
    return () => window.removeEventListener("nl:mobile-chrome", onMobileChrome as EventListener);
  }, []);

  useEffect(() => {
    // Reset chrome visibility when route changes to avoid stale hidden state.
    setMobileChromeHidden(false);
  }, [pathname]);

  useEffect(() => {
    const root = document.documentElement;
    const nav = window.navigator as Navigator & { standalone?: boolean };
    const isIOS = /iPhone|iPad|iPod/i.test(nav.userAgent) || (nav.platform === "MacIntel" && nav.maxTouchPoints > 1);
    const standalone = window.matchMedia("(display-mode: standalone)").matches || Boolean(nav.standalone);
    root.style.setProperty("--nl-mobile-bottom-extra", isIOS && !standalone ? "28px" : "0px");
    const updateVisualViewportBottomInset = () => {
      const vv = window.visualViewport;
      if (!vv) {
        root.style.setProperty("--nl-vv-bottom", "0px");
        return;
      }
      const bottomInset = Math.max(0, Math.round(window.innerHeight - (vv.height + vv.offsetTop)));
      root.style.setProperty("--nl-vv-bottom", `${bottomInset}px`);
    };

    updateVisualViewportBottomInset();
    window.addEventListener("resize", updateVisualViewportBottomInset);
    window.visualViewport?.addEventListener("resize", updateVisualViewportBottomInset);
    window.visualViewport?.addEventListener("scroll", updateVisualViewportBottomInset);
    return () => {
      window.removeEventListener("resize", updateVisualViewportBottomInset);
      window.visualViewport?.removeEventListener("resize", updateVisualViewportBottomInset);
      window.visualViewport?.removeEventListener("scroll", updateVisualViewportBottomInset);
      root.style.setProperty("--nl-vv-bottom", "0px");
      root.style.setProperty("--nl-mobile-bottom-extra", "0px");
    };
  }, []);

  return (
    <div className="h-screen w-screen relative">
      <App3DLayer mode={mode} blockedCount={blockedCount} overdueCount={overdueCount} />
      <CommandPalette />
      <div
        className={`hidden lg:grid h-full relative z-10 ${uiDesign === "focus" ? "nl-layout-focus" : uiDesign === "command" ? "nl-layout-command" : uiDesign === "jira" ? "nl-layout-jira" : ""}`}
        style={{ gridTemplateColumns: uiDesign === "focus" ? "76px 1fr" : uiDesign === "command" ? "96px 1fr" : "84px 1fr" }}
      >
        <div className="nl-shell-rail">
          <LeftRail variant="rail" />
        </div>
        <div
          className={`h-screen flex flex-col nl-shell-glass ${app3dEnabled ? "" : "nl-shell-glass-flat"} ${
            uiDesign === "jira" ? "nl-shell-jira" : uiDesign === "focus" ? "nl-shell-focus" : uiDesign === "command" ? "nl-shell-command" : ""
          }`}
        >
          <TopBar />
          <motion.main
            key="main"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: motionTokens.duration.base, ease: motionTokens.ease.standard }}
            className="flex-1 overflow-hidden"
          >
            {children}
          </motion.main>
          <div className="h-10 px-4 flex items-center justify-between text-xs text-muted">
            <div>Task-Daddy</div>
            <div>{version}</div>
          </div>
        </div>
      </div>

      <div
        className={`lg:hidden h-full flex flex-col relative z-10 nl-shell-glass-mobile ${app3dEnabled ? "" : "nl-shell-glass-mobile-flat"} ${
          uiDesign === "focus" ? "nl-mobile-focus" : uiDesign === "command" ? "nl-mobile-command" : uiDesign === "jira" ? "nl-mobile-jira" : ""
        }`}
      >
        <div className={`transition-all duration-200 ${mobileChromeHidden ? "max-h-0 opacity-0 pointer-events-none overflow-hidden" : "max-h-40 opacity-100"}`}>
          <MobileHeader />
        </div>
        <motion.main
          key="main-mobile"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: motionTokens.duration.base, ease: motionTokens.ease.standard }}
          className={`flex-1 overflow-hidden ${mobileChromeHidden ? "pb-2" : "pb-[calc(104px+env(safe-area-inset-bottom)+var(--nl-vv-bottom,0px)+var(--nl-mobile-bottom-extra,0px))]"}`}
        >
          {children}
        </motion.main>
        <div className={`transition-opacity duration-200 ${mobileChromeHidden ? "opacity-0 pointer-events-none" : "opacity-100"}`}>
          <MobileFab />
          <MobileBottomNav />
        </div>
      </div>
    </div>
  );
}
