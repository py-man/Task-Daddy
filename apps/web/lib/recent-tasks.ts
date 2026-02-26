"use client";

const KEY = "nl:recentTasks";
const MAX = 30;

function readRaw(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.map((v) => String(v || "")).filter(Boolean);
  } catch {
    return [];
  }
}

export function recordRecentTask(taskId: string) {
  if (typeof window === "undefined" || !taskId) return;
  const list = readRaw().filter((id) => id !== taskId);
  list.unshift(taskId);
  window.localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX)));
}

export function getRecentTaskIds() {
  return readRaw();
}

