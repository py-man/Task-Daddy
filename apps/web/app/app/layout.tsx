"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { SessionProvider, useSession } from "@/components/session";
import { BoardProvider } from "@/components/board-context";
import { AppShell } from "@/components/shell";

function Gate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading } = useSession();
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);
  if (!user) return null;
  return <>{children}</>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <BoardProvider>
        <Gate>
          <AppShell>{children}</AppShell>
        </Gate>
      </BoardProvider>
    </SessionProvider>
  );
}

