/**
 * Game launching and session tracking.
 *
 * Security invariants:
 * - The game is always looked up by UUID from our own database. The renderer
 *   never supplies a raw path to execute.
 * - Processes are spawned with shell:false and a structured argv array.
 * - No shell string concatenation anywhere on this path.
 */
import { spawn, type ChildProcess, type SpawnOptions } from 'node:child_process';
import type { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import { getGame, recordPlaytime } from '../data/games';
import {
  checkpointSession,
  createSession,
  finalizeSession,
  recoverInterruptedSessions,
} from '../data/sessions';
import { getSettings } from '../data/settings';
import {
  ValidationError,
  assertDirectoryUsable,
  assertExecutableUsable,
  canonicalizePath,
  validateArgsArray,
} from './validation';

export type SpawnFn = (
  exe: string,
  args: readonly string[],
  opts: SpawnOptions,
) => ChildProcess;

interface RunningEntry {
  child: ChildProcess;
  sessionId: string | null;
  gameId: string;
}

export interface LauncherDeps {
  db: DatabaseSync;
  /** Override for tests. Defaults to child_process.spawn. */
  spawnImpl?: SpawnFn;
  /** Called after a successful spawn (e.g. to minimize the window). */
  onLaunched?: (gameId: string) => void;
}

const CHECKPOINT_INTERVAL_MS = 30_000;

export class GameLauncher {
  private readonly db: DatabaseSync;
  private readonly spawnImpl: SpawnFn;
  private readonly onLaunched: ((gameId: string) => void) | undefined;
  private readonly running = new Map<string, RunningEntry>();
  private checkpointTimer: NodeJS.Timeout | null = null;

  constructor(deps: LauncherDeps) {
    this.db = deps.db;
    this.spawnImpl = deps.spawnImpl ?? spawn;
    this.onLaunched = deps.onLaunched;
  }

  /** Number of currently tracked child processes (useful for tests/diagnostics). */
  runningCount(): number {
    return this.running.size;
  }

  /**
   * Launch a library game by id. Returns the new (or already-running) session.
   * Throws ValidationError with an actionable message on any pre-flight failure.
   */
  async launch(gameId: string): Promise<{ sessionId: string | null; alreadyRunning: boolean }> {
    const game = getGame(this.db, gameId);
    if (!game) {
      throw new ValidationError('NOT_FOUND', 'Game not found in the library.');
    }
    if (!game.exePath) {
      throw new ValidationError(
        'NO_LAUNCH_TARGET',
        `"${game.title}" has no executable target to launch.`,
      );
    }
    const existing = this.running.get(gameId);
    if (existing) {
      return { sessionId: existing.sessionId, alreadyRunning: true };
    }

    // Revalidate at use time: the file may have moved since it was added.
    const exePath = canonicalizePath(game.exePath);
    await assertExecutableUsable(exePath);
    const args = validateArgsArray(game.args);
    let cwd = path.dirname(exePath);
    if (game.workingDir) {
      await assertDirectoryUsable(game.workingDir);
      cwd = canonicalizePath(game.workingDir);
    }

    const settings = getSettings(this.db);
    const sessionId = settings.trackingEnabled
      ? createSession(this.db, gameId, 'observed').id
      : null;

    let child: ChildProcess;
    try {
      child = this.spawnImpl(exePath, args, {
        cwd,
        shell: false,
        windowsHide: true,
        detached: false,
      });
    } catch (err) {
      if (sessionId) {
        finalizeSession(this.db, sessionId, {
          state: 'interrupted',
          notes: `Spawn threw before the process started: ${(err as Error).message}`,
        });
      }
      throw new ValidationError(
        'SPAWN_FAILED',
        `Could not start "${game.title}": ${(err as Error).message}`,
      );
    }

    const entry: RunningEntry = { child, sessionId, gameId };
    const finalize = (state: 'completed' | 'interrupted', notes: string | null = null) => {
      if (!this.running.has(gameId)) return; // already finalized
      this.running.delete(gameId);
      if (sessionId) {
        const endedAt = new Date().toISOString();
        const session = finalizeSession(this.db, sessionId, { state, notes });
        recordPlaytime(this.db, gameId, endedAt, session.durationMs ?? 0);
      }
    };

    child.on('error', (err: Error) => {
      finalize('interrupted', `Process failed to start: ${err.message}`);
    });
    child.on('close', () => {
      finalize('completed');
    });

    this.running.set(gameId, entry);
    this.ensureCheckpointTimer();
    this.onLaunched?.(gameId);
    return { sessionId, alreadyRunning: false };
  }

  private ensureCheckpointTimer(): void {
    if (this.checkpointTimer) return;
    this.checkpointTimer = setInterval(() => {
      for (const entry of this.running.values()) {
        if (entry.sessionId) {
          try {
            checkpointSession(this.db, entry.sessionId);
          } catch {
            // A failed checkpoint must never kill the timer or the game.
          }
        }
      }
    }, CHECKPOINT_INTERVAL_MS);
    this.checkpointTimer.unref?.();
  }

  /**
   * Finalize any in-memory running sessions conservatively (at last
   * checkpoint, never "now"). Called on app shutdown; also safe to call when
   * idle. Child processes themselves are left alone — we never kill games.
   */
  shutdown(): void {
    if (this.checkpointTimer) {
      clearInterval(this.checkpointTimer);
      this.checkpointTimer = null;
    }
    recoverInterruptedSessions(this.db);
    this.running.clear();
  }
}
