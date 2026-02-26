"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronDown, Bell, Search, Moon, Sun } from "lucide-react";
import { useBoard } from "@/components/board-context";
import { TaskDaddyLogo } from "@/components/brand/task-daddy-logo";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

function titleForPath(pathname: string | null) {
  const p = pathname || "";
  if (p.startsWith("/app/boards")) return "Boards";
  if (p.startsWith("/app/home")) return "Home";
  if (p.startsWith("/app/tasks")) return "My Tasks";
  if (p.startsWith("/app/inbox")) return "Inbox";
  if (p.startsWith("/app/search")) return "Search";
  if (p.startsWith("/app/settings")) return "Settings";
  if (p.startsWith("/app/board")) return "Board";
  return "Task-Daddy";
}

export function MobileHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { boards, board, selectBoard, createBoard } = useBoard();
  const [newBoardName, setNewBoardName] = useState("New Board");
  const [unreadCount, setUnreadCount] = useState(0);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const canPickBoard = useMemo(
    () =>
      (pathname || "").startsWith("/app/home") ||
      (pathname || "").startsWith("/app/board") ||
      (pathname || "").startsWith("/app/tasks") ||
      (pathname || "").startsWith("/app/search"),
    [pathname]
  );

  const refreshUnread = async () => {
    try {
      const ns = await api.inappNotifications({ unreadOnly: true, limit: 50 });
      setUnreadCount(ns.length);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    refreshUnread();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const saved = (typeof window !== "undefined" ? window.localStorage.getItem("nl-theme") : null) as "dark" | "light" | null;
    const mode = saved === "light" ? "light" : "dark";
    setTheme(mode);
    document.documentElement.setAttribute("data-theme", mode);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    if (typeof window !== "undefined") window.localStorage.setItem("nl-theme", next);
  };

  const title = titleForPath(pathname);

  return (
    <div className="sticky top-0 z-[60]">
      <div className="px-2.5 py-1.5 min-h-11 flex items-center gap-2 bg-bg/26 backdrop-blur-xl border-b border-white/10">
        <Link
          href="/app/home"
          className="inline-flex h-8.5 w-8.5 rounded-xl border border-accent/25 bg-accent/10 shadow-neon items-center justify-center hover:bg-white/5 transition"
          aria-label="Task-Daddy"
        >
          <TaskDaddyLogo size={22} />
        </Link>

        {canPickBoard ? (
          <Dialog>
            <DialogTrigger asChild>
              <button className="glass rounded-xl px-2.5 h-8.5 flex items-center gap-1.5 border border-white/10 hover:bg-white/5 transition min-w-0">
                <div className="text-[13px] font-medium truncate max-w-[54vw]">{board?.name || "Select board"}</div>
                <ChevronDown size={16} className="text-muted" />
              </button>
            </DialogTrigger>
            <DialogContent>
              <div className="text-lg font-semibold">Boards</div>
              <div className="mt-3 space-y-2">
                {boards.map((b) => (
                  <button
                    key={b.id}
                    className="w-full text-left rounded-2xl border border-white/10 bg-white/5 hover:bg-white/10 transition p-3"
                    onClick={() => {
                      selectBoard(b.id);
                      router.push("/app/board");
                    }}
                  >
                    <div className="text-sm font-medium">{b.name}</div>
                    {b.id === board?.id ? <Badge variant="accent" className="mt-2">Current</Badge> : null}
                  </button>
                ))}
              </div>

              <div className="mt-4 border-t border-white/10 pt-4">
                <div className="text-sm font-semibold">Create board</div>
                <div className="mt-2 space-y-2">
                  <Input value={newBoardName} onChange={(e) => setNewBoardName(e.target.value)} />
                  <Button
                    className="w-full"
                    onClick={async () => {
                      await createBoard(newBoardName);
                      router.push("/app/board");
                    }}
                  >
                    Create
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        ) : (
          <div className="text-[13px] font-semibold">{title}</div>
        )}

        <div className="flex-1" />

        <button
          className="h-8.5 w-8.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition grid place-items-center"
          onClick={() => router.push("/app/search")}
          aria-label="Search"
        >
          <Search size={17} className="text-muted" />
        </button>

        <button
          className="h-8.5 w-8.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition grid place-items-center"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun size={17} className="text-muted" /> : <Moon size={17} className="text-muted" />}
        </button>

        <button
          className="relative h-8.5 w-8.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition grid place-items-center"
          onClick={() => router.push("/app/inbox")}
          aria-label="Inbox"
        >
          <Bell size={17} className="text-muted" />
          {unreadCount ? (
            <span className="absolute -top-1 -right-1 h-5 min-w-5 px-1 rounded-full bg-accent text-black text-xs flex items-center justify-center">
              {unreadCount}
            </span>
          ) : null}
        </button>
      </div>
    </div>
  );
}
