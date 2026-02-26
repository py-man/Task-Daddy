"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useBoard } from "@/components/board-context";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function SettingsBackupsPage() {
  const { board } = useBoard();
  const { user } = useSession();
  const [loading, setLoading] = useState(false);
  const [backups, setBackups] = useState<any[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [policy, setPolicy] = useState({
    retentionDays: 5,
    minIntervalMinutes: 60,
    maxBackups: 30,
    maxTotalSizeMb: 2048
  });

  const refresh = async () => {
    if (user?.role !== "admin") return;
    try {
      const list = await api.backups();
      const p = await api.backupPolicy();
      setBackups(list);
      setPolicy({
        retentionDays: Number(p?.retentionDays || 5),
        minIntervalMinutes: Number(p?.minIntervalMinutes || 60),
        maxBackups: Number(p?.maxBackups || 30),
        maxTotalSizeMb: Number(p?.maxTotalSizeMb || 2048)
      });
      setSelected((prev) => {
        const next: Record<string, boolean> = {};
        for (const b of list) {
          if (prev[b.filename]) next[b.filename] = true;
        }
        return next;
      });
    } catch (e: any) {
      toast.error(String(e?.message || e));
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role]);

  let backupsSection: React.ReactNode = null;
  if (user?.role !== "admin") {
    backupsSection = <div className="mt-3 text-xs text-muted">Admin-only: sign in as an admin user to create/restore backups.</div>;
  } else if (backups.length) {
    const selectedNames = backups.filter((b) => selected[b.filename]).map((b) => b.filename);
    backupsSection = (
      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-semibold">Existing backups</div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled={loading || selectedNames.length === 0}
              onClick={async () => {
                const ok = confirm(`Delete ${selectedNames.length} backup(s)? This cannot be undone.`);
                if (!ok) return;
                setLoading(true);
                try {
                  for (const name of selectedNames) {
                    // eslint-disable-next-line no-await-in-loop
                    await api.deleteBackup(name);
                  }
                  toast.success(`Deleted ${selectedNames.length} backup(s)`);
                  setSelected({});
                  await refresh();
                } catch (e: any) {
                  toast.error(String(e?.message || e));
                } finally {
                  setLoading(false);
                }
              }}
            >
              Delete selected
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                const all: Record<string, boolean> = {};
                for (const b of backups) all[b.filename] = true;
                setSelected(all);
              }}
            >
              Select all
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSelected({})}>
              Clear
            </Button>
          </div>
        </div>
        <div className="mt-2 space-y-2">
          {backups.map((b) => (
            <div key={b.filename} className="flex flex-col gap-2 rounded-2xl border border-white/10 bg-white/5 p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={Boolean(selected[b.filename])}
                  onChange={(e) => setSelected((prev) => ({ ...prev, [b.filename]: e.target.checked }))}
                  className="mt-1"
                  aria-label={`Select ${b.filename}`}
                />
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{b.filename}</div>
                  <div className="mt-1 text-xs text-muted">
                    {b.createdAt} • {(Number(b.sizeBytes || 0) / (1024 * 1024)).toFixed(2)} MB
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {String(b.filename || "").startsWith("neonlanes_full_export_") || String(b.filename || "").startsWith("taskdaddy_full_export_")
                      ? "Type: Full export (DB dump + app backup)"
                      : "Type: App backup"}
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => window.open(`/api/backups/${encodeURIComponent(b.filename)}/download`, "_blank", "noopener,noreferrer")}
                >
                  Download
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={loading}
                  onClick={async () => {
                    const ok = confirm(`Delete ${b.filename}? This cannot be undone.`);
                    if (!ok) return;
                    setLoading(true);
                    try {
                      await api.deleteBackup(b.filename);
                      toast.success("Deleted");
                      await refresh();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  Delete
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={loading}
                  onClick={async () => {
                    const ok = confirm(`Dry-run restore preview for ${b.filename}?`);
                    if (!ok) return;
                    setLoading(true);
                    try {
                      const res = await api.restoreBackup({ filename: b.filename, mode: "skip_existing", dryRun: true });
                      toast.success(`Preview: ${JSON.stringify(res.counts || {})}`);
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  Preview restore
                </Button>
                <Button
                  size="sm"
                  disabled={loading}
                  onClick={async () => {
                    const ok = confirm(`Restore ${b.filename}? This will merge into the current database (idempotent).`);
                    if (!ok) return;
                    setLoading(true);
                    try {
                      await api.restoreBackup({ filename: b.filename, mode: "skip_existing" });
                      toast.success("Restore complete");
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  Restore
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  } else {
    backupsSection = <div className="mt-3 text-xs text-muted">No backups yet.</div>;
  }

  return (
    <div className="glass rounded-3xl shadow-neon border border-white/10 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-semibold">Backups</div>
          <div className="mt-2 text-sm text-muted">Exports and full backups for disaster recovery.</div>
        </div>
        <Badge variant="muted">Admin</Badge>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">CSV export (board)</div>
        <div className="mt-1 text-xs text-muted">Excel-friendly export for the current board.</div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant="ghost"
            disabled={!board?.id}
            onClick={() => {
              if (!board?.id) return;
              window.open(`/api/boards/${board.id}/export/tasks.csv`, "_blank", "noopener,noreferrer");
            }}
          >
            Download tasks.csv
          </Button>
        </div>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">Retention guardrails</div>
        <div className="mt-1 text-xs text-muted">Control backup lifecycle: minimum interval, max count, max size, and retention window.</div>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="text-xs text-muted">
            Retention days
            <input
              type="number"
              min={1}
              value={policy.retentionDays}
              onChange={(e) => setPolicy((p) => ({ ...p, retentionDays: Number(e.target.value || 1) }))}
              className="mt-1 w-full rounded-xl border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
            />
          </label>
          <label className="text-xs text-muted">
            Minimum interval (minutes)
            <input
              type="number"
              min={0}
              value={policy.minIntervalMinutes}
              onChange={(e) => setPolicy((p) => ({ ...p, minIntervalMinutes: Number(e.target.value || 0) }))}
              className="mt-1 w-full rounded-xl border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
            />
          </label>
          <label className="text-xs text-muted">
            Max backups
            <input
              type="number"
              min={1}
              value={policy.maxBackups}
              onChange={(e) => setPolicy((p) => ({ ...p, maxBackups: Number(e.target.value || 1) }))}
              className="mt-1 w-full rounded-xl border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
            />
          </label>
          <label className="text-xs text-muted">
            Max total size (MB)
            <input
              type="number"
              min={1}
              value={policy.maxTotalSizeMb}
              onChange={(e) => setPolicy((p) => ({ ...p, maxTotalSizeMb: Number(e.target.value || 1) }))}
              className="mt-1 w-full rounded-xl border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
            />
          </label>
        </div>
        <div className="mt-3 flex gap-2">
          <Button
            size="sm"
            disabled={loading || user?.role !== "admin"}
            onClick={async () => {
              setLoading(true);
              try {
                await api.updateBackupPolicy(policy);
                toast.success("Backup guardrails saved");
                await refresh();
              } catch (e: any) {
                toast.error(String(e?.message || e));
              } finally {
                setLoading(false);
              }
            }}
          >
            Save guardrails
          </Button>
          <Button size="sm" variant="ghost" disabled={loading || user?.role !== "admin"} onClick={refresh}>
            Reload
          </Button>
        </div>
      </div>

      <div className="mt-5 rounded-3xl border border-white/10 bg-white/5 p-4">
        <div className="text-sm font-semibold">Backups and full export</div>
        <div className="mt-1 text-xs text-muted">
          App backup includes CSV exports + attachments. Full export additionally includes a PostgreSQL `pg_dump` for machine-recovery scenarios.
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={loading || user?.role !== "admin"}
            onClick={async () => {
              setLoading(true);
              try {
                await api.createFullBackup();
                toast.success("Backup created");
                await refresh();
              } catch (e: any) {
                toast.error(String(e?.message || e));
              } finally {
                setLoading(false);
              }
            }}
          >
            Create app backup
          </Button>
          <Button
            size="sm"
            disabled={loading || user?.role !== "admin"}
            onClick={async () => {
              setLoading(true);
              try {
                await api.createMachineRecoveryExport();
                toast.success("Full export created");
                await refresh();
              } catch (e: any) {
                toast.error(String(e?.message || e));
              } finally {
                setLoading(false);
              }
            }}
          >
            Create full export
          </Button>
          <Button size="sm" variant="ghost" disabled={loading || user?.role !== "admin"} onClick={refresh}>
            Refresh list
          </Button>
        </div>

        {user?.role === "admin" ? (
          <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
            <div className="text-sm font-semibold">Restore from file</div>
            <div className="mt-1 text-xs text-muted">Upload a previously downloaded `.tar.gz` and restore it into this instance.</div>
            <div className="mt-3 flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
              <input
                type="file"
                accept=".tar.gz,application/gzip"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="text-sm"
              />
              <div className="flex gap-2 justify-end">
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={loading || !uploadFile}
                  onClick={async () => {
                    if (!uploadFile) return;
                    const ok = confirm(`Preview restore for ${uploadFile.name}?`);
                    if (!ok) return;
                    setLoading(true);
                    try {
                      const res = await api.uploadBackupAndRestore(uploadFile, { mode: "skip_existing", dryRun: true });
                      toast.success(`Preview: ${JSON.stringify(res.counts || {})}`);
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  Preview
                </Button>
                <Button
                  size="sm"
                  disabled={loading || !uploadFile}
                  onClick={async () => {
                    if (!uploadFile) return;
                    const ok = confirm(`Restore from ${uploadFile.name}? This will merge into the current database (idempotent).`);
                    if (!ok) return;
                    setLoading(true);
                    try {
                      await api.uploadBackupAndRestore(uploadFile, { mode: "skip_existing" });
                      toast.success("Restore complete");
                      setUploadFile(null);
                      await refresh();
                    } catch (e: any) {
                      toast.error(String(e?.message || e));
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  Restore
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {backupsSection}
      </div>
    </div>
  );
}
