"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function InboxPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<any[]>([]);

  const refresh = async () => {
    setLoading(true);
    try {
      const ns = await api.inappNotifications({ unreadOnly: false, limit: 100 });
      setItems(ns);
    } catch (e: any) {
      toast.error(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="h-full p-4 flex flex-col min-h-0">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">Inbox</div>
        <Button
          size="sm"
          variant="ghost"
          disabled={loading || items.every((x) => x.readAt)}
          onClick={async () => {
            try {
              await api.markAllNotificationsRead();
              await refresh();
            } catch (e: any) {
              toast.error(String(e?.message || e));
            }
          }}
        >
          Mark all read
        </Button>
      </div>

      <div className="mt-3 flex-1 min-h-0 overflow-y-auto scrollbar">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-sm text-muted mt-6">No notifications.</div>
        ) : (
          <div className="space-y-2 pb-6">
            {items.map((n) => (
              <button
                key={n.id}
                className="w-full text-left rounded-2xl border border-white/10 bg-white/5 hover:bg-white/10 transition p-3"
                onClick={async () => {
                  try {
                    if (!n.readAt) {
                      await api.markNotificationsRead([n.id]);
                      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, readAt: new Date().toISOString() } : x)));
                    }
                    if (n.entityType === "Task" && n.entityId) {
                      router.push(`/app/board?task=${encodeURIComponent(n.entityId)}`);
                    }
                  } catch (e: any) {
                    toast.error(String(e?.message || e));
                  }
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-sm font-medium">{n.title}</div>
                  {!n.readAt ? <Badge variant="accent">New</Badge> : <Badge variant="muted">Read</Badge>}
                </div>
                <div className="mt-1 text-sm text-muted whitespace-pre-wrap">{n.body}</div>
                <div className="mt-2 text-xs text-muted">{new Date(n.createdAt).toLocaleString()}</div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

