"use client";

export type LightPalette = "aqua" | "sunrise" | "forest" | "graphite" | "jira";

const KEY = "nl-light-palette";
const ATTR = "data-light-palette";

export function getLightPalette(): LightPalette {
  if (typeof window === "undefined") return "aqua";
  const saved = window.localStorage.getItem(KEY);
  if (saved === "sunrise" || saved === "forest" || saved === "graphite" || saved === "jira" || saved === "aqua") return saved;
  return "aqua";
}

export function setLightPalette(palette: LightPalette): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, palette);
  document.documentElement.setAttribute(ATTR, palette);
}

export function applyLightPaletteFromStorage(): LightPalette {
  const palette = getLightPalette();
  if (typeof window !== "undefined") {
    document.documentElement.setAttribute(ATTR, palette);
  }
  return palette;
}
