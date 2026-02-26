"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { useBoard } from "@/components/board-context";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";

export default function BoardsPage() {
  const router = useRouter();
  const { boards, board, selectBoard, createBoard, loading } = useBoard();

  const sorted = useMemo(() => [...boards].sort((a, b) => a.name.localeCompare(b.name)), [boards]);

  if (loading) return <div className="h-full p-4 text-sm text-muted">Loading…</div>;

  if (!sorted.length) {
    return (
      <div className="h-full p-4">
        <EmptyState
          title="Create your first board"
          body="Boards hold lanes, tasks, and integrations."
          actions={
            <Button
              variant="primary"
              onClick={async () => {
                await createBoard(`New Board ${new Date().toISOString().slice(0, 10)}`);
                router.push("/app/board");
              }}
            >
              Create board
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="h-full p-4">
      <div className="text-sm font-semibold">Boards</div>
      <div className="mt-3 space-y-2">
        {sorted.map((b) => {
          const active = b.id === board?.id;
          return (
            <button
              key={b.id}
              className={`w-full text-left rounded-2xl border p-3 transition ${active ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 bg-white/5 hover:bg-white/10"}`}
              onClick={() => {
                selectBoard(b.id);
                router.push("/app/board");
              }}
            >
              <div className="text-sm font-medium">{b.name}</div>
              <div className="mt-1 text-xs text-muted">{active ? "Current board" : "Tap to open"}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

