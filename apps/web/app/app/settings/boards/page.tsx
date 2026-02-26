"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useBoard } from "@/components/board-context";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function SettingsBoardsPage() {
  const { user } = useSession();
  const { boards, board, refreshAll, selectBoard, createBoard } = useBoard();
  const isAdmin = user?.role === "admin";
  const [newName, setNewName] = useState("");

  const sorted = useMemo(() => [...boards].sort((a, b) => a.name.localeCompare(b.name)), [boards]);

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-lg font-semibold">Boards</div>
          <div className="mt-1 text-sm text-muted">Create, rename, and safely delete boards.</div>
        </div>
        <Button
          variant="ghost"
          onClick={async () => {
            await refreshAll();
            toast.success("Refreshed");
          }}
        >
          Refresh
        </Button>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">Create board</div>
        <div className="mt-2 flex gap-2 items-end">
          <div className="flex-1">
            <div className="text-xs text-muted mb-1">Name</div>
            <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Infra Swimlanes" />
          </div>
          <Button
            variant="ghost"
            onClick={async () => {
              try {
                const n = (newName || "").trim();
                if (!n) return;
                await createBoard(n);
                setNewName("");
                toast.success("Board created");
                await refreshAll();
              } catch (e: any) {
                toast.error(String(e?.message || e));
              }
            }}
          >
            Create
          </Button>
        </div>
        <div className="mt-2 text-xs text-muted">Board names are unique (case-insensitive).</div>
      </div>

      <div className="mt-5 space-y-2">
        {sorted.map((b) => (
          <BoardRow
            key={b.id}
            board={b}
            currentBoardId={board?.id || null}
            boards={sorted}
            onSelect={() => selectBoard(b.id)}
            onChanged={refreshAll}
            canAdmin={isAdmin}
          />
        ))}
      </div>
    </div>
  );
}

function BoardRow({
  board,
  currentBoardId,
  boards,
  onSelect,
  onChanged,
  canAdmin,
}: {
  board: any;
  currentBoardId: string | null;
  boards: any[];
  onSelect: () => void;
  onChanged: () => Promise<void>;
  canAdmin: boolean;
}) {
  const [rename, setRename] = useState(board.name);
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [membersOpen, setMembersOpen] = useState(false);

  const [deleteMode, setDeleteMode] = useState<"transfer" | "exportThenDelete" | "deleteAll">("transfer");
  const [transferTo, setTransferTo] = useState<string>("");
  const [confirmName, setConfirmName] = useState("");
  const transferOptions = boards.filter((b) => b.id !== board.id);

  const isCurrent = currentBoardId === board.id;

  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="text-sm font-semibold truncate">{board.name}</div>
          {isCurrent ? <Badge variant="ok">Current</Badge> : <Badge variant="muted">Board</Badge>}
        </div>
        <div className="text-xs text-muted truncate">{board.id}</div>
      </div>

      <div className="flex flex-wrap gap-2 justify-end">
        <Button size="sm" variant="ghost" onClick={onSelect}>
          Open
        </Button>

        {canAdmin ? (
          <Dialog open={membersOpen} onOpenChange={setMembersOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost">
                Members
              </Button>
            </DialogTrigger>
            <DialogContent>
              <BoardMembersDialog boardId={board.id} boardName={board.name} onChanged={onChanged} />
            </DialogContent>
          </Dialog>
        ) : null}

        {canAdmin ? (
          <Dialog>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost">
                Rename
              </Button>
            </DialogTrigger>
            <DialogContent>
              <div className="text-lg font-semibold">Rename board</div>
              <div className="mt-3">
                <div className="text-xs text-muted mb-1">Name</div>
                <Input value={rename} onChange={(e) => setRename(e.target.value)} />
              </div>
              <div className="mt-5 flex justify-end gap-2">
                <Button
                  variant="ghost"
                  disabled={saving}
                  onClick={async () => {
                    setSaving(true);
                    try {
                      await api.updateBoard(board.id, rename);
                      toast.success("Renamed");
                      await onChanged();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setSaving(false);
                    }
                  }}
                >
                  Save
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        ) : null}

        {canAdmin ? (
          <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="danger">
                Delete
              </Button>
            </DialogTrigger>
            <DialogContent>
              <div className="text-lg font-semibold">Delete board</div>
              <div className="mt-1 text-sm text-muted">Destructive actions require explicit confirmation.</div>

              <div className="mt-4 space-y-3 text-sm">
                <label className="flex items-center gap-2">
                  <input type="radio" checked={deleteMode === "transfer"} onChange={() => setDeleteMode("transfer")} />
                  <span>Transfer tasks to another board, then delete board</span>
                </label>
                {deleteMode === "transfer" ? (
                  <div className="pl-6">
                    <div className="text-xs text-muted mb-1">Transfer to</div>
                    <select
                      className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
                      value={transferTo}
                      onChange={(e) => setTransferTo(e.target.value)}
                    >
                      <option value="">Select board…</option>
                      {transferOptions.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </select>
                    <div className="mt-1 text-xs text-muted">Tasks map by stateKey when possible, otherwise backlog lane.</div>
                  </div>
                ) : null}

                <label className="flex items-center gap-2">
                  <input type="radio" checked={deleteMode === "exportThenDelete"} onChange={() => setDeleteMode("exportThenDelete")} />
                  <span>Export tasks (CSV), then delete board + tasks</span>
                </label>
                {deleteMode === "exportThenDelete" ? (
                  <div className="pl-6 text-xs text-muted">Downloads a CSV export for tasks, then deletes the board and all tasks.</div>
                ) : null}

                <label className="flex items-center gap-2">
                  <input type="radio" checked={deleteMode === "deleteAll"} onChange={() => setDeleteMode("deleteAll")} />
                  <span>Delete everything (board + tasks)</span>
                </label>
                {deleteMode === "deleteAll" ? (
                  <div className="pl-6">
                    <div className="text-xs text-muted mb-1">Type board name to confirm</div>
                    <Input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} placeholder={board.name} />
                  </div>
                ) : null}
              </div>

              <div className="mt-5 flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setDeleteOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  disabled={(deleteMode === "transfer" && !transferTo) || (deleteMode === "deleteAll" && confirmName.trim() !== board.name)}
                  onClick={async () => {
                    try {
                      if (deleteMode === "exportThenDelete") {
                        window.open(`/api/boards/${board.id}/export/tasks.csv`, "_blank", "noopener,noreferrer");
                        await new Promise((r) => setTimeout(r, 300));
                        await api.deleteBoard(board.id, "delete", null);
                      } else if (deleteMode === "deleteAll") {
                        await api.deleteBoard(board.id, "delete", null);
                      } else {
                        await api.deleteBoard(board.id, "transfer", transferTo);
                      }
                      toast.success("Deleted");
                      setDeleteOpen(false);
                      await onChanged();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    }
                  }}
                >
                  Delete board
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        ) : null}
      </div>
    </div>
  );
}

function BoardMembersDialog({
  boardId,
  boardName,
  onChanged,
}: {
  boardId: string;
  boardName: string;
  onChanged: () => Promise<void>;
}) {
  const [loading, setLoading] = useState(true);
  const [members, setMembers] = useState<any[]>([]);
  const [allUsers, setAllUsers] = useState<any[]>([]);
  const [pickUserId, setPickUserId] = useState("");
  const [pickRole, setPickRole] = useState<"viewer" | "member" | "admin">("member");

  const load = async () => {
    setLoading(true);
    try {
      const [ms, us] = await Promise.all([api.boardMembers(boardId), api.users()]);
      setMembers(ms);
      setAllUsers(us);
      const memberIds = new Set(ms.map((m: any) => m.userId));
      const firstCandidate = us.find((u: any) => !memberIds.has(u.id));
      setPickUserId(firstCandidate?.id || "");
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boardId]);

  const memberIds = useMemo(() => new Set(members.map((m: any) => m.userId)), [members]);
  const candidates = useMemo(() => allUsers.filter((u: any) => !memberIds.has(u.id)), [allUsers, memberIds]);

  return (
    <div>
      <div className="text-lg font-semibold">Board members</div>
      <div className="mt-1 text-sm text-muted">Manage who can be assigned tasks in “{boardName}”.</div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
        <div className="text-sm font-semibold">Add existing user</div>
        <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 items-end">
          <div className="md:col-span-2">
            <div className="text-xs text-muted mb-1">User</div>
            <select
              data-testid="settings-board-add-member-user"
              className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
              value={pickUserId}
              onChange={(e) => setPickUserId(e.target.value)}
              disabled={loading}
            >
              {candidates.length === 0 ? <option value="">No available users</option> : <option value="">Select user…</option>}
              {candidates.map((u: any) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.email})
                </option>
              ))}
            </select>
          </div>
          <div>
            <div className="text-xs text-muted mb-1">Role</div>
            <select
              data-testid="settings-board-add-member-role"
              className="h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm"
              value={pickRole}
              onChange={(e) => setPickRole(e.target.value as any)}
              disabled={loading}
            >
              {["viewer", "member", "admin"].map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-3 flex justify-end">
            <Button
              data-testid="settings-board-add-member-submit"
              variant="ghost"
              disabled={loading || !pickUserId}
              onClick={async () => {
                try {
                  const u = allUsers.find((x: any) => x.id === pickUserId);
                  if (!u) return;
                  await api.addBoardMember(boardId, { email: u.email, role: pickRole });
                  toast.success("Member added");
                  await load();
                  await onChanged();
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                }
              }}
            >
              Add
            </Button>
          </div>
        </div>
      </div>

      <div className="mt-4">
        <div className="text-sm font-semibold">Current members</div>
        {loading ? (
          <div className="text-sm text-muted mt-2">Loading…</div>
        ) : members.length === 0 ? (
          <div className="text-sm text-muted mt-2">No members.</div>
        ) : (
          <div className="mt-2 space-y-2">
            {members.map((m: any) => (
              <div key={m.userId} className="rounded-2xl border border-white/10 bg-white/5 p-3 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{m.name}</div>
                  <div className="text-xs text-muted truncate">{m.email}</div>
                </div>
                <Badge variant="muted">{m.role}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 text-xs text-muted">
        Task assignment only allows users who are members of the board. Add them here to make them selectable in the task drawer.
      </div>
    </div>
  );
}
