"use client";

export type UiDesign = "core" | "focus" | "command" | "jira";
type UserRole = string | null | undefined;

const KEY = "nl-ui-design";
const ATTR = "data-ui-design";

function defaultDesignForRole(role: UserRole): UiDesign {
  const normalized = String(role || "").toLowerCase();
  if (normalized === "admin" || normalized === "owner") return "command";
  return "jira";
}

export function getUiDesign(): UiDesign {
  if (typeof window === "undefined") return "core";
  const saved = window.localStorage.getItem(KEY);
  if (saved === "focus" || saved === "command" || saved === "jira" || saved === "core") return saved;
  return "core";
}

export function setUiDesign(design: UiDesign): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, design);
  document.documentElement.setAttribute(ATTR, design);
  window.dispatchEvent(new CustomEvent("nl:uiDesignChanged", { detail: { design } }));
}

export function applyUiDesignFromStorage(): UiDesign {
  const design = getUiDesign();
  if (typeof window !== "undefined") {
    document.documentElement.setAttribute(ATTR, design);
  }
  return design;
}

export function ensureUiDesignForRole(role: UserRole): UiDesign {
  if (typeof window === "undefined") return defaultDesignForRole(role);
  const normalized = String(role || "").toLowerCase();
  const isAdmin = normalized === "admin" || normalized === "owner";
  const saved = window.localStorage.getItem(KEY);
  if (saved === "focus" || saved === "command" || saved === "jira" || saved === "core") {
    const allowed = !isAdmin && saved === "command" ? defaultDesignForRole(role) : saved;
    if (allowed !== saved) window.localStorage.setItem(KEY, allowed);
    document.documentElement.setAttribute(ATTR, allowed);
    return allowed;
  }
  const next = defaultDesignForRole(role);
  window.localStorage.setItem(KEY, next);
  document.documentElement.setAttribute(ATTR, next);
  window.dispatchEvent(new CustomEvent("nl:uiDesignChanged", { detail: { design: next, source: "role-default" } }));
  return next;
}
