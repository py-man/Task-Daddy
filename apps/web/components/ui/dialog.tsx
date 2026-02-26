"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { motion } from "framer-motion";
import { cn } from "@/lib/cn";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[300]" />
      <DialogPrimitive.Content asChild>
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.99 }}
          transition={{ type: "spring", stiffness: 420, damping: 32 }}
          transformTemplate={({ x, y, scale }) => {
            const nx = typeof x === "number" ? x : 0;
            const ny = typeof y === "number" ? y : 0;
            const ns = typeof scale === "number" ? scale : 1;
            return `translate(-50%, -50%) translate3d(${nx}px, ${ny}px, 0) scale(${ns})`;
          }}
          className={cn(
            "fixed left-1/2 top-1/2 w-[94vw] max-w-lg rounded-2xl glass p-4 md:p-5 shadow-neon max-h-[88vh] overflow-auto z-[310]",
            "sm:w-[92vw] md:max-h-[85vh]",
            className
          )}
        >
          {children}
        </motion.div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
