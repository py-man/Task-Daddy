"use client";

import { useEffect, useRef } from "react";
import { useState } from "react";

type App3DLayerProps = {
  mode: "board" | "list" | "calendar" | "settings" | "reports" | "general";
  blockedCount: number;
  overdueCount: number;
  respectSettings?: boolean;
};

const APP_3D_KEY = "nl:app3dEnabled";
const APP_3D_EVENT = "nl:app3dChanged";
const APP_3D_MODE_KEY = "nl:app3dMode";
const APP_3D_MODE_EVENT = "nl:app3dModeChanged";

export type App3dMode = "minimal" | "scroll" | "fixed" | "cinematic";

function readApp3dEnabled(): boolean {
  if (typeof window === "undefined") return true;
  const raw = (window.localStorage.getItem(APP_3D_KEY) || "1").trim().toLowerCase();
  return raw !== "0" && raw !== "false" && raw !== "off";
}

export function getApp3dEnabled(): boolean {
  return readApp3dEnabled();
}

export function setApp3dEnabled(enabled: boolean) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(APP_3D_KEY, enabled ? "1" : "0");
  window.dispatchEvent(new CustomEvent(APP_3D_EVENT, { detail: enabled ? "1" : "0" }));
}

function readApp3dMode(): App3dMode {
  if (typeof window === "undefined") return "scroll";
  const raw = (window.localStorage.getItem(APP_3D_MODE_KEY) || "scroll").trim().toLowerCase();
  if (raw === "minimal" || raw === "scroll" || raw === "fixed" || raw === "cinematic") return raw;
  return "scroll";
}

export function getApp3dMode(): App3dMode {
  return readApp3dMode();
}

export function setApp3dMode(mode: App3dMode) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(APP_3D_MODE_KEY, mode);
  window.dispatchEvent(new CustomEvent(APP_3D_MODE_EVENT, { detail: mode }));
}

export function App3DLayer({ mode, blockedCount, overdueCount, respectSettings = true }: App3DLayerProps) {
  const [enabled, setEnabled] = useState(true);
  const [app3dMode, setApp3dModeState] = useState<App3dMode>("scroll");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const modeRef = useRef(mode);
  const blockedRef = useRef(blockedCount);
  const overdueRef = useRef(overdueCount);
  const pointerRef = useRef({ x: 0, y: 0, tx: 0, ty: 0 });
  const energyRef = useRef(0);
  const burstsRef = useRef<Array<{ x: number; y: number; life: number; r: number }>>([]);

  useEffect(() => {
    setEnabled(readApp3dEnabled());
    setApp3dModeState(readApp3dMode());
    const onStorage = (event: StorageEvent) => {
      if (event.key === APP_3D_KEY) setEnabled(readApp3dEnabled());
      if (event.key === APP_3D_MODE_KEY) setApp3dModeState(readApp3dMode());
    };
    const onCustom = () => setEnabled(readApp3dEnabled());
    const onMode = () => setApp3dModeState(readApp3dMode());
    window.addEventListener("storage", onStorage);
    window.addEventListener(APP_3D_EVENT, onCustom as EventListener);
    window.addEventListener(APP_3D_MODE_EVENT, onMode as EventListener);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(APP_3D_EVENT, onCustom as EventListener);
      window.removeEventListener(APP_3D_MODE_EVENT, onMode as EventListener);
    };
  }, []);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    blockedRef.current = blockedCount;
  }, [blockedCount]);

  useEffect(() => {
    overdueRef.current = overdueCount;
  }, [overdueCount]);

  useEffect(() => {
    if (respectSettings && !enabled) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const motionFactor = app3dMode === "minimal" ? 0.42 : app3dMode === "fixed" ? 0.06 : app3dMode === "cinematic" ? 1.45 : 1;
    let animation = 0;
    let active = true;

    const setSize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const dpr = Math.min(1.5, window.devicePixelRatio || 1);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (time: number) => {
      if (!active) return;
      const width = window.innerWidth;
      const height = window.innerHeight;
      const t = time * (reducedMotion ? 0 : 0.00008 * motionFactor);
      const scrollNorm = Math.max(0, Math.min(1, window.scrollY / Math.max(1, window.innerHeight * 3)));
      const p = pointerRef.current;
      p.x += (p.tx - p.x) * 0.06;
      p.y += (p.ty - p.y) * 0.06;
      const energy = energyRef.current;
      energyRef.current = Math.max(0, energy * 0.96);
      const routeMode = modeRef.current;
      const blocked = Math.max(0, blockedRef.current);
      const overdue = Math.max(0, overdueRef.current);
      const stress = Math.min(1, (blocked + overdue) / 10);
      const pointerStrength = app3dMode === "fixed" ? 0 : app3dMode === "minimal" ? 0.35 : app3dMode === "cinematic" ? 1.65 : 1;
      const scrollOffset = app3dMode === "fixed" ? 0 : app3dMode === "cinematic" ? scrollNorm * 0.14 : scrollNorm * 0.08;
      const horizonY = height * (0.26 + scrollOffset + p.y * 0.02 * pointerStrength);
      const centerX = width * (0.5 + p.x * 0.03 * pointerStrength + (app3dMode === "cinematic" ? Math.sin(t * 0.7) * 0.01 : 0));

      const modeTone =
        routeMode === "calendar"
          ? { c1: "98,186,255", c2: "152,108,255" }
          : routeMode === "settings"
            ? { c1: "122,142,174", c2: "116,134,160" }
            : routeMode === "reports"
              ? { c1: "120,255,206", c2: "198,103,255" }
              : routeMode === "list"
                ? { c1: "102,220,255", c2: "176,120,255" }
                : routeMode === "board"
                  ? { c1: "95,255,221", c2: "217,70,239" }
                  : { c1: "105,242,224", c2: "209,95,255" };

      context.clearRect(0, 0, width, height);

      const bg = context.createLinearGradient(0, 0, 0, height);
      const topAlpha = app3dMode === "minimal" ? 0.54 : app3dMode === "fixed" ? 0.62 : app3dMode === "cinematic" ? 0.48 : 0.65;
      const bottomAlpha = app3dMode === "cinematic" ? 0.78 : 0.84;
      bg.addColorStop(0, `rgba(6,8,16,${topAlpha + stress * 0.05})`);
      bg.addColorStop(1, `rgba(4,6,12,${bottomAlpha})`);
      context.fillStyle = bg;
      context.fillRect(0, 0, width, height);

      const glow = context.createRadialGradient(centerX, horizonY - 40, 0, centerX, horizonY, width * 0.82);
      const glowBoost = app3dMode === "minimal" ? 0.65 : app3dMode === "fixed" ? 0.9 : app3dMode === "cinematic" ? 1.62 : 1;
      glow.addColorStop(0, `rgba(${modeTone.c1},${(0.28 + stress * 0.16 + energy * 0.08) * glowBoost})`);
      glow.addColorStop(0.45, `rgba(${modeTone.c2},${(0.18 + stress * 0.1 + energy * 0.06) * glowBoost})`);
      glow.addColorStop(1, "rgba(5,8,15,0)");
      context.fillStyle = glow;
      context.fillRect(0, 0, width, height);

      context.save();
      context.translate(centerX, horizonY);

      const horizonLines = app3dMode === "minimal" ? 12 : app3dMode === "fixed" ? 18 : app3dMode === "cinematic" ? 34 : 24;
      for (let i = 0; i < horizonLines; i++) {
        const depth = ((i / horizonLines + t * (app3dMode === "cinematic" ? 1.9 : 1)) % 1) + 0.0001;
        const y = depth * depth * height * 1.36;
        const alpha = (1 - depth) * (0.26 + stress * 0.11 + energy * 0.08);
        context.strokeStyle = `rgba(${modeTone.c1},${alpha.toFixed(3)})`;
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(-width, y);
        context.lineTo(width, y);
        context.stroke();
      }

      const railCount = app3dMode === "minimal" ? 5 : app3dMode === "fixed" ? 7 : app3dMode === "cinematic" ? 11 : 8;
      for (let i = -railCount; i <= railCount; i++) {
        const x = (i / railCount) * width * 0.5;
        const alpha = 0.08 + (1 - Math.abs(i) / railCount) * (0.18 + stress * 0.08 + energy * 0.04);
        context.strokeStyle =
          i % 2 === 0 ? `rgba(${modeTone.c1},${alpha.toFixed(3)})` : `rgba(${modeTone.c2},${(alpha * 0.88).toFixed(3)})`;
        context.beginPath();
        context.moveTo(x, 0);
        context.lineTo(x * 2.5, height);
        context.stroke();
      }

      context.restore();

      const laneCount = app3dMode === "minimal" ? 2 : app3dMode === "cinematic" ? 4 : 3;
      for (let i = 0; i < laneCount; i++) {
        const laneX = width * (0.26 + i * 0.24) + p.x * 24;
        const laneGlow = context.createLinearGradient(0, horizonY, 0, height);
        laneGlow.addColorStop(0, `rgba(${i % 2 ? modeTone.c2 : modeTone.c1},${0.24 + energy * 0.1})`);
        laneGlow.addColorStop(1, "rgba(0,0,0,0)");
        context.strokeStyle = laneGlow;
        context.lineWidth = 1.6 + i * 0.3;
        context.beginPath();
        context.moveTo(laneX, horizonY + 4);
        context.lineTo(laneX + (i - 1) * 20, height);
        context.stroke();
      }

      const dustCount = app3dMode === "minimal" ? 6 : app3dMode === "fixed" ? 10 : app3dMode === "cinematic" ? 30 : 16;
      for (let i = 0; i < dustCount; i++) {
        const px = ((i * 193) % width) + Math.sin(t * 3 + i) * 36;
        const py = ((i * 157) % height) + Math.cos(t * 2.3 + i * 1.2) * 24;
        context.fillStyle =
          i % 3
            ? `rgba(${modeTone.c1},${(0.14 + stress * 0.1).toFixed(3)})`
            : `rgba(${modeTone.c2},${(0.16 + stress * 0.1).toFixed(3)})`;
        context.beginPath();
        context.arc(px, py, 1.2, 0, Math.PI * 2);
        context.fill();
      }

      if (app3dMode === "cinematic") {
        const sweep = (Math.sin(t * 3) + 1) / 2;
        const beamX = width * (0.08 + sweep * 0.84);
        const beam = context.createLinearGradient(beamX - 120, 0, beamX + 120, 0);
        beam.addColorStop(0, "rgba(0,0,0,0)");
        beam.addColorStop(0.5, `rgba(${modeTone.c2},0.11)`);
        beam.addColorStop(1, "rgba(0,0,0,0)");
        context.fillStyle = beam;
        context.fillRect(0, 0, width, height);
      }

      if (app3dMode === "fixed") {
        context.fillStyle = "rgba(0,0,0,0.22)";
        context.fillRect(0, 0, width, height);
      }

      if (!reducedMotion) {
        burstsRef.current = burstsRef.current
          .map((burst) => ({ ...burst, life: burst.life - 0.02, r: burst.r + 2.3 * motionFactor }))
          .filter((burst) => burst.life > 0);
        for (const burst of burstsRef.current) {
          context.strokeStyle = `rgba(${modeTone.c1},${(burst.life * 0.35).toFixed(3)})`;
          context.lineWidth = 1.5;
          context.beginPath();
          context.arc(burst.x, burst.y, burst.r, 0, Math.PI * 2);
          context.stroke();
        }
      }

      if (stress > 0.01 && routeMode === "board") {
        const warnWidth = Math.min(width * 0.78, width * (0.14 + stress * 0.32));
        context.fillStyle = `rgba(255,74,110,${(0.08 + stress * 0.2).toFixed(3)})`;
        context.fillRect(width - warnWidth, 0, warnWidth, 3);
      }

      animation = window.requestAnimationFrame(draw);
    };

    setSize();
    const onPointerMove = (event: PointerEvent) => {
      if (reducedMotion || app3dMode === "fixed") return;
      const x = event.clientX / Math.max(1, window.innerWidth);
      const y = event.clientY / Math.max(1, window.innerHeight);
      pointerRef.current.tx = (x - 0.5) * 2;
      pointerRef.current.ty = (y - 0.5) * 2;
    };
    const addBurst = (x: number, y: number, boost = 0.25) => {
      burstsRef.current.push({ x, y, life: 1, r: 8 });
      energyRef.current = Math.min(1, energyRef.current + boost);
    };
    const onPointerDown = (event: PointerEvent) => {
      if (reducedMotion || app3dMode === "fixed") return;
      addBurst(event.clientX, event.clientY, 0.24);
    };
    const onWheel = () => {
      if (reducedMotion || app3dMode === "fixed") return;
      energyRef.current = Math.min(1, energyRef.current + (app3dMode === "cinematic" ? 0.14 : 0.08));
    };
    const onTaskMoved = () => {
      if (reducedMotion || app3dMode === "fixed") return;
      addBurst(window.innerWidth * 0.6, window.innerHeight * 0.45, 0.35);
    };

    window.addEventListener("resize", setSize);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("wheel", onWheel, { passive: true });
    window.addEventListener("nl:task-moved", onTaskMoved as EventListener);
    animation = window.requestAnimationFrame(draw);

    return () => {
      active = false;
      window.removeEventListener("resize", setSize);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("nl:task-moved", onTaskMoved as EventListener);
      window.cancelAnimationFrame(animation);
    };
  }, [enabled, app3dMode, respectSettings]);

  if (respectSettings && !enabled) return null;
  return <canvas ref={canvasRef} className="nl-app3d-layer" aria-hidden />;
}
