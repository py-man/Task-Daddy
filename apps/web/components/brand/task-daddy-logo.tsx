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
        <linearGradient id="td_g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="rgb(var(--accent) / 1)" />
          <stop offset="1" stopColor="rgb(50 210 200 / 1)" />
        </linearGradient>
        <filter id="td_glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.4" result="b" />
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

      <rect x="5" y="5" width="54" height="54" rx="16" fill="rgb(var(--panel) / 0.65)" stroke="rgb(255 255 255 / 0.10)" />

      <g filter="url(#td_glow)" stroke="url(#td_g)" strokeWidth="3.5" strokeLinecap="round" fill="none">
        <path d="M14 20h22" />
        <path d="M25 20v24" />
        <path d="M38 20h7c5 0 9 4 9 9v6c0 5-4 9-9 9h-7V20z" />
      </g>

      <g opacity="0.55">
        <circle cx="50" cy="18" r="1.6" fill="rgb(var(--accent) / 0.9)" />
        <circle cx="16" cy="48" r="1.2" fill="rgb(50 210 200 / 0.9)" />
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
