"use client";

import * as React from "react";
import { cn } from "@/lib/cn";
import { motion } from "framer-motion";

export function EmptyState({
  title,
  body,
  actions,
  className
}: {
  title: string;
  body?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("glass rounded-3xl border border-white/10 shadow-neon p-6", className)}>
      <div className="flex items-start gap-4">
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
          className="h-12 w-12 rounded-3xl border border-accent/25 bg-accent/10 grid place-items-center"
          aria-hidden="true"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" className="text-accent">
            <path
              d="M6 16V7a2 2 0 0 1 2-2h9"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
            <path
              d="M18 8v9a2 2 0 0 1-2 2H7"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
            <path d="M8.5 11.5h7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M8.5 14.5h4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </motion.div>
        <div className="min-w-0">
          <div className="text-lg font-semibold">{title}</div>
          {body ? <div className="mt-1 text-sm text-muted whitespace-pre-wrap">{body}</div> : null}
          {actions ? <div className="mt-4 flex flex-wrap gap-2">{actions}</div> : null}
        </div>
      </div>
    </div>
  );
}

