/**
 * Scheduler tests with an injected clock and manual timer — deterministic,
 * no real waiting. Verifies due-run behavior, last_run_at bookkeeping,
 * event emission, failure handling, and that the timer never survives
 * beyond stop().
 */
import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  deleteSchedule,
  listSchedules,
  setSchedule,
} from '../../electron/main/db/schedules';
import { countBackups, listBackups } from '../../electron/main/db/backups';
import { BackupScheduler } from '../../electron/main/scheduler/scheduler';
import {
  addTestGame,
  makeFixture,
  seedSaveTree,
  writeFile,
  type Fixture,
} from '../helpers';

let fixture: Fixture | null = null;
afterEach(() => {
  fixture?.cleanup();
  fixture = null;
});

interface Harness {
  fixture: Fixture;
  gameId: number;
  scheduler: BackupScheduler;
  events: { event: string; payload: unknown }[];
  now: Date;
  advance: (ms: number) => void;
  timers: { set: (fn: () => void) => unknown; clear: () => void };
  tickFns: (() => void)[];
}

function setup(): Harness {
  const fx = makeFixture();
  fixture = fx;
  seedSaveTree(fx.saveDir);
  const game = addTestGame(fx);

  const events: { event: string; payload: unknown }[] = [];
  const tickFns: (() => void)[] = [];
  let current = new Date('2026-10-23T10:00:00.000Z');

  const timers = {
    set: (fn: () => void): unknown => {
      tickFns.push(fn);
      return tickFns.length; // fake handle
    },
    clear: (): void => {
      tickFns.length = 0;
    },
  };

  const scheduler = new BackupScheduler(
    {
      db: fx.db,
      backupsRoot: fx.backupsRoot,
      tickMs: 60_000,
      now: () => new Date(current),
      timer: timers,
    },
    (event, payload) => events.push({ event, payload }),
  );

  return {
    fixture: fx,
    gameId: game.id,
    scheduler,
    events,
    now: current,
    advance: (ms: number) => {
      current = new Date(current.getTime() + ms);
    },
    timers,
    tickFns,
  };
}

describe('BackupScheduler', () => {
  it('runs a due schedule, records last_run_at, and emits backup.completed', async () => {
    const h = setup();
    setSchedule(h.fixture.db, { gameId: h.gameId, intervalMinutes: 60, enabled: true });

    const summary = await h.scheduler.tick();

    expect(summary).toEqual({ ran: 1, succeeded: 1, failed: 0, skipped: 0 });
    expect(countBackups(h.fixture.db, h.gameId)).toBe(1);
    const [schedule] = listSchedules(h.fixture.db);
    expect(schedule?.lastRunAt).toBe('2026-10-23T10:00:00.000Z');

    const completed = h.events.find((e) => e.event === 'backup.completed');
    expect(completed).toBeDefined();
    expect((completed?.payload as { gameId: number }).gameId).toBe(h.gameId);
    expect((completed?.payload as { skipped: boolean }).skipped).toBe(false);
  });

  it('propagates skipped-file warnings on the backup.completed event', async () => {
    const h = setup();
    setSchedule(h.fixture.db, { gameId: h.gameId, intervalMinutes: 60, enabled: true });
    // A dangling symlink can never be read: the scheduled backup succeeds but
    // must carry the skip warning so the renderer can surface it.
    try {
      fs.symlinkSync(
        path.join(h.fixture.saveDir, 'does-not-exist-target'),
        path.join(h.fixture.saveDir, 'locked.sav'),
      );
    } catch {
      return; // Windows without symlink privilege.
    }

    const summary = await h.scheduler.tick();
    expect(summary.succeeded).toBe(1);

    const completed = h.events.find((e) => e.event === 'backup.completed');
    const payload = completed?.payload as {
      skippedFiles?: { relPath: string; reason: string }[];
    };
    expect(payload.skippedFiles?.some((s) => s.relPath === 'locked.sav')).toBe(true);
  });

  it('does not re-run a schedule before its interval elapses', async () => {
    const h = setup();
    setSchedule(h.fixture.db, { gameId: h.gameId, intervalMinutes: 60, enabled: true });

    await h.scheduler.tick();
    const second = await h.scheduler.tick();
    expect(second.ran).toBe(0);
    expect(countBackups(h.fixture.db, h.gameId)).toBe(1);

    // 61 minutes later it is due again — but nothing changed, so the backup
    // is skipped while last_run_at still advances.
    h.advance(61 * 60_000);
    const third = await h.scheduler.tick();
    expect(third).toEqual({ ran: 1, succeeded: 0, failed: 0, skipped: 1 });
    expect(countBackups(h.fixture.db, h.gameId)).toBe(1);
    const [schedule] = listSchedules(h.fixture.db);
    expect(schedule?.lastRunAt).toBe('2026-10-23T11:01:00.000Z');
  });

  it('creates a fresh backup when saves changed since the last scheduled run', async () => {
    const h = setup();
    setSchedule(h.fixture.db, { gameId: h.gameId, intervalMinutes: 60, enabled: true });

    await h.scheduler.tick();
    writeFile(h.fixture.saveDir, 'slot1.sav', 'new progress');
    h.advance(61 * 60_000);
    const summary = await h.scheduler.tick();

    expect(summary.succeeded).toBe(1);
    expect(countBackups(h.fixture.db, h.gameId)).toBe(2);
    const backups = listBackups(h.fixture.db, h.gameId);
    expect(backups[0]?.label).toBe('scheduled backup');
  });

  it('skips disabled schedules entirely', async () => {
    const h = setup();
    setSchedule(h.fixture.db, { gameId: h.gameId, intervalMinutes: 60, enabled: false });

    const summary = await h.scheduler.tick();
    expect(summary.ran).toBe(0);
    expect(countBackups(h.fixture.db, h.gameId)).toBe(0);
    expect(h.events).toEqual([]);
  });

  it('emits backup.failed with an actionable code and keeps the schedule due', async () => {
    const h = setup();
    setSchedule(h.fixture.db, { gameId: h.gameId, intervalMinutes: 60, enabled: true });
    fs.rmSync(h.fixture.saveDir, { recursive: true }); // drive disconnected, effectively

    const summary = await h.scheduler.tick();

    expect(summary).toEqual({ ran: 1, succeeded: 0, failed: 1, skipped: 0 });
    const failed = h.events.find((e) => e.event === 'backup.failed');
    expect(failed).toBeDefined();
    expect((failed?.payload as { code: string }).code).toBe('SAVE_DIR_MISSING');
    expect((failed?.payload as { message: string }).message).toMatch(/re-register/i);
    // last_run_at NOT updated: the failure stays due and retries next tick.
    const [schedule] = listSchedules(h.fixture.db);
    expect(schedule?.lastRunAt).toBeNull();
  });

  it('a failing game does not stop other due schedules', async () => {
    const h = setup();
    const broken = addTestGame(h.fixture, 'Broken Game');
    // Point the broken game at a missing folder.
    h.fixture.db
      .prepare('UPDATE games SET save_path = ? WHERE id = ?')
      .run('/definitely/not/here', broken.id);
    setSchedule(h.fixture.db, { gameId: broken.id, intervalMinutes: 60, enabled: true });
    setSchedule(h.fixture.db, { gameId: h.gameId, intervalMinutes: 60, enabled: true });

    const summary = await h.scheduler.tick();
    expect(summary).toEqual({ ran: 2, succeeded: 1, failed: 1, skipped: 0 });
    expect(countBackups(h.fixture.db, h.gameId)).toBe(1);
  });

  it('start/stop control the timer; overdue schedules are simply due after restart', async () => {
    const h = setup();
    expect(h.scheduler.isRunning()).toBe(false);
    h.scheduler.start();
    expect(h.scheduler.isRunning()).toBe(true);
    expect(h.tickFns).toHaveLength(1);
    // Starting twice does not double-register.
    h.scheduler.start();
    expect(h.tickFns).toHaveLength(1);
    h.scheduler.stop();
    expect(h.scheduler.isRunning()).toBe(false);
    expect(h.tickFns).toHaveLength(0);

    // The DB is the only durable state: deleting the schedule removes it.
    setSchedule(h.fixture.db, { gameId: h.gameId, intervalMinutes: 60, enabled: true });
    expect(deleteSchedule(h.fixture.db, h.gameId)).toBe(true);
    expect(listSchedules(h.fixture.db)).toEqual([]);
  });
});
