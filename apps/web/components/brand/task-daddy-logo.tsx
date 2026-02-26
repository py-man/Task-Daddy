"use client";

import * as React from "react";
import { cn } from "@/lib/cn";

export function TaskDaddyLogo({
  size = 28,
  className,
  label = "Task-Daddy"
}: {
  size?: number;
  className?: string;
  label?: string;
}) {
  return (
    <svg
      data-testid="td-logo"
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={label}
      className={cn("text-accent", className)}
    >
      <defs>
        <linearGradient id="td_lane" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="rgb(var(--accent) / 1)" />
          <stop offset="0.55" stopColor="rgb(64 196 255 / 1)" />
          <stop offset="1" stopColor="rgb(56 239 192 / 1)" />
        </linearGradient>
        <radialGradient id="td_bg" cx="18%" cy="16%" r="95%">
          <stop offset="0" stopColor="rgb(18 30 52 / 1)" />
          <stop offset="1" stopColor="rgb(7 12 24 / 1)" />
        </radialGradient>
        <filter id="td_glow" x="-50%" y="-50%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="2.8" result="b" />
          <feColorMatrix
            in="b"
            type="matrix"
            values="
              1 0 0 0 0
              0 1 0 0 0
              0 0 1 0 0
              0 0 0 0.7 0"
            result="c"
          />
          <feMerge>
            <feMergeNode in="c" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <rect x="4.5" y="4.5" width="55" height="55" rx="16" fill="url(#td_bg)" stroke="rgb(255 255 255 / 0.12)" />

      <g opacity="0.16" stroke="rgb(255 255 255 / 0.36)" strokeWidth="1">
        <line x1="12" y1="16" x2="52" y2="16" />
        <line x1="12" y1="48" x2="52" y2="48" />
      </g>

      <g filter="url(#td_glow)" stroke="url(#td_lane)" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" fill="none">
        <path d="M15 18h16v28" />
        <path d="M31 18h10c7 0 12 5 12 12v2c0 7-5 12-12 12h-10" />
        <path d="M17 45h31" />
      </g>

      <g opacity="0.9">
        <circle cx="31" cy="46" r="2.8" fill="rgb(125 246 226 / 1)" />
        <circle cx="46" cy="18" r="1.5" fill="rgb(102 223 255 / 0.9)" />
        <circle cx="16" cy="28" r="1.3" fill="rgb(var(--accent) / 0.9)" />
      </g>
    </svg>
  );
}

export function TaskDaddyLockup({ className }: { className?: string }) {
  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <TaskDaddyLogo size={28} />
      <div className="leading-tight">
        <div className="text-sm font-semibold">Task-Daddy</div>
        <div className="text-[11px] text-muted">Small tasks. Big momentum.</div>
      </div>
    </div>
  );
}
