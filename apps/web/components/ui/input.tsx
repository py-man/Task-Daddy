"use client";

import * as React from "react";
import { cn } from "@/lib/cn";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, ...props }, ref) => {
  return (
    <input
      ref={ref}
      className={cn(
        "nl-input h-10 w-full rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-text placeholder:text-muted/70 outline-none focus:ring-2 focus:ring-accent/40",
        className
      )}
      {...props}
    />
  );
});
Input.displayName = "Input";
