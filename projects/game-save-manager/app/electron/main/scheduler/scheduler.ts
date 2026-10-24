/**
 * Per-game backup scheduler. While the app runs, a timer fires every minute;
 * due schedules (enabled, and last_run_at older than interval_minutes — or
 * never run) trigger createBackup, update last_run_at, and emit IPC events.
 *
 * Durability note: the timer does NOT survive restarts — only the DB does.
 * On launch, any schedule whose last_run_at is older than its interval is
 * simply "due" at the next tick. Missed runs while the app was closed are
 * not backfilled; that is documented, not a bug.
 */
import type { DatabaseSync } from 'node:sqlite';
import { listSchedules, touchScheduleLastRun } from '../db/schedules';
import { createBackup, type EngineDeps, type ProgressCallback } from '../backup/engine';
import { BackupError } from '../backup/errors';
import { IpcEvents } from '../../../shared/ipc-channels';
import type {
  BackupCompletedEvent,
  BackupFailedEvent,
  BackupProgressEvent,
  Schedule,
} from '../../../shared/types';

export interface SchedulerDeps extends EngineDeps {
  /** Defaults to 60_000 ms. */
  tickMs?: number;
  /** Defaults to () => new Date(). Injected in tests. */
  now?: () => Date;
  /** Defaults to setInterval/clearInterval. Injected in tests. */
  timer?: {
    set: (fn: () => void, ms: number) => unknown;
    clear: (handle: unknown) => void;
  };
}

export type SchedulerEmit = (event: string, payload: unknown) => void;

export interface TickSummary {
  ran: number;
  succeeded: number;
  failed: number;
  skipped: number;
}

const DEFAULT_TICK_MS = 60_000;

export class BackupScheduler {
  private readonly db: DatabaseSync;
  private readonly engineDeps: EngineDeps;
  private readonly tickMs: number;
  private readonly now: () => Date;
  private readonly timer: NonNullable<SchedulerDeps['timer']>;
  private readonly emit: SchedulerEmit;
  private handle: unknown = null;
  private tickInFlight = false;

  constructor(deps: SchedulerDeps, emit: SchedulerEmit) {
    this.db = deps.db;
    this.engineDeps = { db: deps.db, backupsRoot: deps.backupsRoot };
    this.tickMs = deps.tickMs ?? DEFAULT_TICK_MS;
    this.now = deps.now ?? (() => new Date());
    this.timer = deps.timer ?? {
      set: (fn, ms) => setInterval(fn, ms),
      clear: (h) => clearInterval(h as NodeJS.Timeout),
    };
    this.emit = emit;
  }

  start(): void {
    if (this.handle !== null) return;
    this.handle = this.timer.set(() => {
      void this.tick();
    }, this.tickMs);
  }

  stop(): void {
    if (this.handle === null) return;
    this.timer.clear(this.handle);
    this.handle = null;
  }

  isRunning(): boolean {
    return this.handle !== null;
  }

  /** Schedules that are enabled and overdue as of `at`. */
  dueSchedules(at: Date = this.now()): Schedule[] {
    return listSchedules(this.db).filter((s) => {
      if (!s.enabled) return false;
      if (!s.lastRunAt) return true;
      const last = new Date(s.lastRunAt).getTime();
      if (Number.isNaN(last)) return true;
      return at.getTime() - last >= s.intervalMinutes * 60_000;
    });
  }

  /**
   * Run one scheduling pass. Public so tests can drive it deterministically
   * without waiting on real timers. Overlap-guarded: a slow pass never
   * stacks with the next tick.
   */
  async tick(onProgress?: ProgressCallback): Promise<TickSummary> {
    if (this.tickInFlight) return { ran: 0, succeeded: 0, failed: 0, skipped: 0 };
    this.tickInFlight = true;
    const summary: TickSummary = { ran: 0, succeeded: 0, failed: 0, skipped: 0 };
    try {
      const due = this.dueSchedules();
      for (const schedule of due) {
        summary.ran++;
        const progressForwarder: ProgressCallback = (p) => {
          const evt: BackupProgressEvent = { gameId: schedule.gameId, ...p };
          this.emit(IpcEvents.backupProgress, evt);
          onProgress?.(p);
        };
        try {
          const result = await createBackup(this.engineDeps, schedule.gameId, {
            label: 'scheduled backup',
            onProgress: progressForwarder,
          });
          const at = this.now().toISOString();
          touchScheduleLastRun(this.db, schedule.gameId, at);
          const evt: BackupCompletedEvent = {
            gameId: schedule.gameId,
            backupId: result.backup.id,
            label: result.backup.label,
            fileCount: result.backup.fileCount,
            totalBytes: result.backup.totalBytes,
            skipped: result.skipped,
            skippedFiles: result.skippedFiles,
          };
          this.emit(IpcEvents.backupCompleted, evt);
          if (result.skipped) summary.skipped++;
          else summary.succeeded++;
        } catch (err) {
          summary.failed++;
          const code = err instanceof BackupError ? err.code : 'BACKUP_FAILED';
          const evt: BackupFailedEvent = {
            gameId: schedule.gameId,
            code,
            message: err instanceof Error ? err.message : String(err),
          };
          this.emit(IpcEvents.backupFailed, evt);
          // last_run_at intentionally NOT updated: a failed schedule stays due
          // and retries on the next tick.
        }
      }
    } finally {
      this.tickInFlight = false;
    }
    return summary;
  }
}
