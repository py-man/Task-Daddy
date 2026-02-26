"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import {
  getBackgroundOpacity,
  getBackgroundStyle,
  setBackgroundOpacity,
  setBackgroundStyle,
  type BackgroundStyle
} from "@/components/background-layer";
import { getApp3dEnabled, getApp3dMode, setApp3dEnabled, setApp3dMode, type App3dMode } from "@/components/app-3d-layer";
import { applyLightPaletteFromStorage, setLightPalette, type LightPalette } from "@/lib/light-palette";
import { applyUiDesignFromStorage, setUiDesign, type UiDesign } from "@/lib/ui-design";
import { useSession } from "@/components/session";

export default function AppearancePage() {
  const { user } = useSession();
  const [style, setStyle] = useState<BackgroundStyle>("grid");
  const [reducedMotion, setReducedMotion] = useState(false);
  const [opacity, setOpacity] = useState(0.28);
  const [app3d, setApp3d] = useState(true);
  const [app3dMode, setApp3dModeState] = useState<App3dMode>("scroll");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [lightPalette, setLightPaletteState] = useState<LightPalette>("aqua");
  const [uiDesign, setUiDesignState] = useState<UiDesign>("core");
  const isAdmin = String((user as any)?.role || "").toLowerCase() === "admin" || String((user as any)?.role || "").toLowerCase() === "owner";

  useEffect(() => {
    setStyle(getBackgroundStyle());
    setOpacity(getBackgroundOpacity());
    setApp3d(getApp3dEnabled());
    setApp3dModeState(getApp3dMode());
    const currentTheme = (document.documentElement.getAttribute("data-theme") || "dark") as "dark" | "light";
    setTheme(currentTheme === "light" ? "light" : "dark");
    setLightPaletteState(applyLightPaletteFromStorage());
    setUiDesignState(applyUiDesignFromStorage());
    const mql = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(Boolean(mql?.matches));
    update();
    mql?.addEventListener?.("change", update);
    return () => mql?.removeEventListener?.("change", update);
  }, []);

  const options: { value: BackgroundStyle; label: string; desc: string }[] = useMemo(
    () => [
      { value: "off", label: "Off", desc: "No animated layer." },
      { value: "grid", label: "Grid", desc: "Subtle parallax grid lines." },
      { value: "grain", label: "Grain", desc: "Soft noise overlay for depth." },
      { value: "ascii", label: "ASCII", desc: "Extra subtle textural pattern." },
      { value: "corridor", label: "Corridor", desc: "Perspective lane lines (Jesko-inspired)." },
      { value: "scanline", label: "Scanline", desc: "Static film-style line texture." }
    ],
    []
  );
  const palettes: { value: LightPalette; label: string; desc: string }[] = useMemo(
    () => [
      { value: "aqua", label: "Aqua", desc: "Clean cyan/blue default." },
      { value: "jira", label: "Jira Blue", desc: "Blue-on-white enterprise style." },
      { value: "sunrise", label: "Sunrise", desc: "Warm amber/orange light mode." },
      { value: "forest", label: "Forest", desc: "Green calm productivity tone." },
      { value: "graphite", label: "Graphite", desc: "Cool steel blue professional tone." }
    ],
    []
  );

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-lg font-semibold">Appearance</div>
          <div className="mt-1 text-sm text-muted">Premium, subtle motion layers behind the UI.</div>
        </div>
        {reducedMotion ? <Badge variant="muted">Reduced motion</Badge> : <Badge variant="accent">Motion</Badge>}
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold">UI design presets</div>
        <div className="mt-1 text-xs text-muted">Switch app layout behavior. Core remains unchanged; Focus, Command, and Jira provide alternate flows.</div>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { value: "core", label: "Core", desc: "Current Task-Daddy baseline layout and spacing." },
            { value: "focus", label: "Focus", desc: "Reduced noise, larger task cards, single-flow execution." },
            { value: "command", label: "Command", desc: "Operations center with extra context and dashboard strip." },
            { value: "jira", label: "Jira style", desc: "Dense blue-on-white enterprise board with compact controls." }
          ].filter((o) => isAdmin || o.value !== "command").map((o) => {
            const active = uiDesign === o.value;
            return (
              <button
                key={o.value}
                type="button"
                className={cn(
                  "text-left rounded-3xl border px-4 py-3 transition",
                  active ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 bg-white/5 hover:bg-white/7"
                )}
                onClick={() => {
                  const next = o.value as UiDesign;
                  setUiDesignState(next);
                  setUiDesign(next);
                  if (next === "jira") {
                    setLightPaletteState("jira");
                    setLightPalette("jira");
                  }
                  toast.success(`UI design: ${o.label}`);
                }}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold">{o.label}</div>
                  {active ? <Badge variant="accent">Active</Badge> : <Badge variant="muted">Select</Badge>}
                </div>
                <div className="mt-1 text-xs text-muted">{o.desc}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold">Light theme palettes</div>
        <div className="mt-1 text-xs text-muted">Pick from multiple light-mode palettes so light mode has distinct visual styles.</div>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          {palettes.map((p) => {
            const active = lightPalette === p.value;
            return (
              <button
                key={p.value}
                type="button"
                className={cn(
                  "text-left rounded-3xl border px-4 py-3 transition",
                  active ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 bg-white/5 hover:bg-white/7"
                )}
                onClick={() => {
                  setLightPaletteState(p.value);
                  setLightPalette(p.value);
                  toast.success(`Light palette: ${p.label}`);
                }}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold">{p.label}</div>
                  {active ? <Badge variant="accent">Active</Badge> : <Badge variant="muted">Select</Badge>}
                </div>
                <div className="mt-1 text-xs text-muted">{p.desc}</div>
              </button>
            );
          })}
        </div>
        {theme !== "light" ? <div className="mt-2 text-xs text-muted">Switch to Light mode from the top bar to preview palette changes.</div> : null}
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold">Background style</div>
        <div className="mt-1 text-xs text-muted">Slow movement, low opacity, pointer-events disabled. Auto-disables animation when Reduced Motion is enabled.</div>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          {options.map((o) => {
            const active = style === o.value;
            return (
              <button
                key={o.value}
                type="button"
                className={cn(
                  "text-left rounded-3xl border px-4 py-3 transition",
                  active ? "border-accent/30 bg-accent/10 shadow-neon" : "border-white/10 bg-white/5 hover:bg-white/7"
                )}
                onClick={() => {
                  setStyle(o.value);
                  setBackgroundStyle(o.value);
                  toast.success(`Background: ${o.label}`);
                }}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold">{o.label}</div>
                  {active ? <Badge variant="accent">Active</Badge> : <Badge variant="muted">Select</Badge>}
                </div>
                <div className="mt-1 text-xs text-muted">{o.desc}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold">3D app world</div>
        <div className="mt-1 text-xs text-muted">
          Toggle immersive 3D depth for login and app pages. Motion automatically softens with Reduced Motion.
        </div>
        <div className="mt-3 flex items-center gap-2">
          <Button
            size="sm"
            variant={app3d ? "primary" : "ghost"}
            onClick={() => {
              setApp3d(true);
              setApp3dEnabled(true);
              toast.success("3D layer enabled");
            }}
          >
            On
          </Button>
          <Button
            size="sm"
            variant={!app3d ? "primary" : "ghost"}
            onClick={() => {
              setApp3d(false);
              setApp3dEnabled(false);
              toast.success("3D layer disabled");
            }}
          >
            Off
          </Button>
          <Badge variant={app3d ? "accent" : "muted"}>{app3d ? "Enabled" : "Disabled"}</Badge>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {(["minimal", "scroll", "fixed", "cinematic"] as App3dMode[]).map((mode) => (
            <Button
              key={mode}
              size="sm"
              variant={app3dMode === mode ? "primary" : "ghost"}
              onClick={() => {
                setApp3dModeState(mode);
                setApp3dMode(mode);
                toast.success(`3D mode: ${mode}`);
              }}
            >
              {mode}
            </Button>
          ))}
        </div>
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold">Intensity</div>
        <div className="mt-1 text-xs text-muted">Make the background more visible without affecting readability.</div>
        <div className="mt-3 flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={95}
            step={1}
            value={Math.round(opacity * 100)}
            onChange={(e) => {
              const next = Math.max(0, Math.min(95, Number(e.target.value))) / 100;
              setOpacity(next);
              setBackgroundOpacity(next);
            }}
            className="flex-1 accent-[rgb(var(--accent))]"
          />
          <Badge variant="muted">{Math.round(opacity * 100)}%</Badge>
        </div>
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold">Preview</div>
        <div className="mt-1 text-xs text-muted">
          Background styles are intentionally subtle. Preview renders the active style at higher contrast so you can confirm it’s applied.
        </div>
        <div className="mt-3 rounded-3xl border border-white/10 bg-white/5 overflow-hidden relative h-28">
          <div
            aria-hidden="true"
            className={cn(
              "absolute -inset-6 pointer-events-none",
              style === "off"
                ? ""
                : style === "grid"
                  ? "nl-bg--grid"
                  : style === "grain"
                    ? "nl-bg--grain"
                    : style === "ascii"
                      ? "nl-bg--ascii"
                      : style === "corridor"
                        ? "nl-bg--corridor"
                        : "nl-bg--scanline",
              "opacity-100 mix-blend-screen"
            )}
          />
          <div className="relative z-10 h-full w-full p-4 flex items-end justify-between">
            <div>
              <div className="text-xs text-muted">Active</div>
              <div className="text-sm font-semibold">{options.find((x) => x.value === style)?.label || style}</div>
            </div>
            {reducedMotion ? <Badge variant="muted">Reduced motion</Badge> : <Badge variant="accent">Motion</Badge>}
          </div>
        </div>
      </div>

      <div className="mt-5 flex justify-end">
        <Button
          variant="ghost"
          onClick={() => {
            setStyle("grid");
            setBackgroundStyle("grid");
            toast.success("Background reset to Grid");
          }}
        >
          Reset
        </Button>
      </div>
    </div>
  );
}
