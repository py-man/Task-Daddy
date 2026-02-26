"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "nl-button nl-button-3d inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium transition-all outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:opacity-50 disabled:pointer-events-none hover:-translate-y-0.5 hover:scale-[1.01] active:translate-y-[1px] active:scale-[0.985]",
  {
    variants: {
      variant: {
        primary:
          "text-text border border-accent/35 bg-[linear-gradient(180deg,rgba(115,255,209,0.22),rgba(115,255,209,0.08))] hover:bg-[linear-gradient(180deg,rgba(115,255,209,0.28),rgba(115,255,209,0.10))] shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_8px_18px_rgba(0,0,0,0.30),0_0_18px_rgba(115,255,209,0.16)]",
        ghost:
          "text-text/95 border border-white/20 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] hover:bg-[linear-gradient(180deg,rgba(255,255,255,0.10),rgba(255,255,255,0.04))] shadow-[inset_0_1px_0_rgba(255,255,255,0.14),0_6px_14px_rgba(0,0,0,0.22)]",
        warn:
          "text-text border border-warn/35 bg-[linear-gradient(180deg,rgba(255,202,74,0.18),rgba(255,202,74,0.07))] hover:bg-[linear-gradient(180deg,rgba(255,202,74,0.24),rgba(255,202,74,0.09))] shadow-[inset_0_1px_0_rgba(255,255,255,0.16),0_8px_18px_rgba(0,0,0,0.28)]",
        danger:
          "text-text border border-danger/38 bg-[linear-gradient(180deg,rgba(255,74,110,0.20),rgba(255,74,110,0.08))] hover:bg-[linear-gradient(180deg,rgba(255,74,110,0.27),rgba(255,74,110,0.10))] shadow-[inset_0_1px_0_rgba(255,255,255,0.14),0_8px_18px_rgba(0,0,0,0.30)]"
      },
      size: {
        sm: "h-8 px-3",
        md: "h-10 px-4",
        lg: "h-11 px-5"
      }
    },
    defaultVariants: {
      variant: "primary",
      size: "md"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
);
Button.displayName = "Button";
