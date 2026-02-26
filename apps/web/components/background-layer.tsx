"use client";

import { useEffect, useMemo, useState } from "react";

export type BackgroundStyle = "off" | "grid" | "grain" | "ascii" | "corridor" | "scanline";

const STORAGE_KEY = "nl:bgStyle";
const OPACITY_KEY = "nl:bgOpacity";
const EVENT_NAME = "nl:bgStyleChanged";
const OPACITY_EVENT = "nl:bgOpacityChanged";

function readStored(): BackgroundStyle {
  if (typeof window === "undefined") return "grid";
  const v = (localStorage.getItem(STORAGE_KEY) || "").trim().toLowerCase();
  if (v === "off" || v === "grid" || v === "grain" || v === "ascii" || v === "corridor" || v === "scanline") return v;
  return "grid";
}

function readOpacity(): number {
  if (typeof window === "undefined") return 0.28;
  const raw = (localStorage.getItem(OPACITY_KEY) || "").trim();
  const n = Number(raw);
  if (!Number.isFinite(n)) return 0.28;
  return Math.max(0, Math.min(0.95, n));
}

export function BackgroundLayer() {
  const [style, setStyle] = useState<BackgroundStyle>("grid");
  const [opacity, setOpacity] = useState<number>(0.28);

  useEffect(() => {
    setStyle(readStored());
    setOpacity(readOpacity());
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setStyle(readStored());
      if (e.key === OPACITY_KEY) setOpacity(readOpacity());
    };
    const onCustom = (e: Event) => {
      const ce = e as CustomEvent;
      const next = String(ce.detail || "").trim().toLowerCase();
      if (next === "off" || next === "grid" || next === "grain" || next === "ascii" || next === "corridor" || next === "scanline")
        setStyle(next as BackgroundStyle);
      else setStyle(readStored());
    };
    const onOpacity = () => setOpacity(readOpacity());
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        setStyle(readStored());
        setOpacity(readOpacity());
      }
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener(EVENT_NAME, onCustom as any);
    window.addEventListener(OPACITY_EVENT, onOpacity as any);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(EVENT_NAME, onCustom as any);
      window.removeEventListener(OPACITY_EVENT, onOpacity as any);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const className = useMemo(() => {
    if (style === "off") return "nl-bg nl-bg--off";
    if (style === "grid") return "nl-bg nl-bg--grid";
    if (style === "grain") return "nl-bg nl-bg--grain";
    if (style === "ascii") return "nl-bg nl-bg--ascii";
    if (style === "corridor") return "nl-bg nl-bg--corridor";
    return "nl-bg nl-bg--scanline";
  }, [style]);

  return (
    <div
      data-testid="bg-layer"
      data-style={style}
      className={className}
      aria-hidden="true"
      style={{ ["--nl-bg-opacity" as any]: opacity }}
    />
  );
}

export function setBackgroundStyle(style: BackgroundStyle) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, style);
  // Trigger same-tab updates (storage events don't reliably fire in the same tab).
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: style }));
}

export function getBackgroundStyle(): BackgroundStyle {
  return readStored();
}

export function setBackgroundOpacity(opacity: number) {
  if (typeof window === "undefined") return;
  const clamped = Math.max(0, Math.min(0.95, opacity));
  localStorage.setItem(OPACITY_KEY, String(clamped));
  window.dispatchEvent(new Event(OPACITY_EVENT));
}

export function getBackgroundOpacity(): number {
  return readOpacity();
}
