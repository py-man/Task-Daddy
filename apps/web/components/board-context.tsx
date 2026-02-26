"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Board, BoardTaskPriority, BoardTaskType, Lane, Task, User } from "@neonlanes/shared/schema";
import { api } from "@/lib/api";
import { toast } from "sonner";

type BoardState = {
  boards: Board[];
  board: Board | null;
  lanes: Lane[];
  tasks: Task[];
  users: User[];
  taskTypes: BoardTaskType[];
  priorities: BoardTaskPriority[];
  loading: boolean;
  search: string;
  setSearch: (s: string) => void;
  refreshAll: () => Promise<void>;
  selectBoard: (boardId: string) => void;
  createBoard: (name: string) => Promise<void>;
  createLane: (payload: { name: string; stateKey: string; type: string; wipLimit?: number | null }) => Promise<void>;
  reorderLanes: (laneIds: string[]) => Promise<void>;
  createTask: (payload: any) => Promise<Task>;
  updateTask: (taskId: string, payload: any) => Promise<Task>;
  moveTask: (taskId: string, payload: any) => Promise<Task>;
};

const BoardCtx = createContext<BoardState | null>(null);

export function BoardProvider({ children }: { children: React.ReactNode }) {
  const [boards, setBoards] = useState<Board[]>([]);
  const [boardId, setBoardId] = useState<string | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [lanes, setLanes] = useState<Lane[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [taskTypes, setTaskTypes] = useState<BoardTaskType[]>([]);
  const [priorities, setPriorities] = useState<BoardTaskPriority[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const selectBoard = useCallback((id: string) => {
    setBoardId(id);
    localStorage.setItem("nl:lastBoardId", id);
  }, []);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    try {
      const [b, us] = await Promise.all([api.boards(), api.users()]);
      setBoards(b);
      const preferredCandidate = boardId || localStorage.getItem("nl:lastBoardId") || null;
      const current = (preferredCandidate ? b.find((x) => x.id === preferredCandidate) : null) || b[0] || null;
      const resolvedId = current?.id || null;
      setBoardId(resolvedId);
      if (resolvedId) localStorage.setItem("nl:lastBoardId", resolvedId);
      setBoard(current);
      if (current) {
        const [ls, ts, ms, tts, ps] = await Promise.all([
          api.lanes(current.id),
          api.tasks(current.id),
          api.boardMembers(current.id),
          api.taskTypes(current.id),
          api.priorities(current.id)
        ]);
        setLanes(ls);
        setTasks(ts);
        const memberIds = new Set(ms.map((m: any) => m.userId));
        setUsers(us.filter((u) => memberIds.has(u.id)));
        setTaskTypes(tts);
        setPriorities(ps);
      } else {
        setLanes([]);
        setTasks([]);
        setUsers([]);
        setTaskTypes([]);
        setPriorities([]);
      }
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [boardId]);

  const createBoard = useCallback(async (name: string) => {
    try {
      const b = await api.createBoard(name);
      toast.success("Board created");
      setBoards((prev) => [b, ...prev]);
      selectBoard(b.id);
      await refreshAll();
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  }, [refreshAll, selectBoard]);

  const createLane = useCallback(async (payload: { name: string; stateKey: string; type: string; wipLimit?: number | null }) => {
    if (!boardId) return;
    try {
      await api.createLane(boardId, payload);
      toast.success("Lane created");
      await refreshAll();
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  }, [boardId, refreshAll]);

  const reorderLanes = useCallback(async (laneIds: string[]) => {
    if (!boardId) return;
    try {
      await api.reorderLanes(boardId, laneIds);
      setLanes((prev) => {
        const map = new Map(prev.map((l) => [l.id, l]));
        return laneIds.map((id, idx) => ({ ...map.get(id)!, position: idx }));
      });
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  }, [boardId]);

  const createTask = useCallback(async (payload: any): Promise<Task> => {
    const activeBoardId = board?.id || boardId;
    if (!activeBoardId) throw new Error("No active board selected");
    try {
      const t = await api.createTask(activeBoardId, payload);
      toast.success("Task created", {
        description: `ID: ${t.id}`,
        action: {
          label: "Open task",
          onClick: () => {
            if (typeof window !== "undefined") window.location.assign(`/app/board?task=${t.id}`);
          }
        }
      });
      setTasks((prev) => [...prev, t]);
      return t;
    } catch (e: any) {
      toast.error(String(e?.message || e));
      throw e;
    }
  }, [board?.id, boardId]);

  const updateTask = useCallback(async (taskId: string, payload: any) => {
    const t = await api.updateTask(taskId, payload);
    setTasks((prev) => prev.map((x) => (x.id === t.id ? t : x)));
    return t;
  }, []);

  const moveTask = useCallback(async (taskId: string, payload: any) => {
    const t = await api.moveTask(taskId, payload);
    setTasks((prev) => prev.map((x) => (x.id === t.id ? t : x)));
    return t;
  }, []);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!boardId) return;
    const b = boards.find((x) => x.id === boardId) || null;
    setBoard(b);
    if (b) {
      Promise.all([api.lanes(b.id), api.tasks(b.id), api.boardMembers(b.id), api.users(), api.taskTypes(b.id), api.priorities(b.id)])
        .then(([ls, ts, ms, us, tts, ps]) => {
          setLanes(ls);
          setTasks(ts);
          const memberIds = new Set(ms.map((m: any) => m.userId));
          setUsers(us.filter((u) => memberIds.has(u.id)));
          setTaskTypes(tts);
          setPriorities(ps);
        })
        .catch((e) => toast.error(String(e?.message || e)));
    }
  }, [boardId, boards]);

  const value = useMemo(
    () => ({
      boards,
      board,
      lanes,
      tasks,
      users,
      taskTypes,
      priorities,
      loading,
      search,
      setSearch,
      refreshAll,
      selectBoard,
      createBoard,
      createLane,
      reorderLanes,
      createTask,
      updateTask,
      moveTask
    }),
    [boards, board, lanes, tasks, users, taskTypes, priorities, loading, search, refreshAll, createBoard, createLane, reorderLanes, createTask, updateTask, moveTask, selectBoard]
  );

  return <BoardCtx.Provider value={value}>{children}</BoardCtx.Provider>;
}

export function useBoard() {
  const v = useContext(BoardCtx);
  if (!v) throw new Error("useBoard must be used within BoardProvider");
  return v;
}
