/**
 * Game launching and session tracking.
 *
 * Security invariants:
 * - The game is always looked up by UUID from our own database. The renderer
 *   never supplies a raw path to execute.
 * - Processes are spawned with shell:false and a structured argv array.
 * - No shell string concatenation anywhere on this path.
 * - Store launches hand a validated URI to the OS (openExternal). The app
 *   never claims the game is "running" from a URI handoff.
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
import { buildRunGameUri, isValidAppId } from '../sources/steam/adapter';
import { EPIC_LAUNCHER_URI } from '../sources/epic/adapter';
import { BattleNetAdapter } from '../sources/battlenet/adapter';
import { RealBattleNetOs, type BattleNetOs } from '../sources/battlenet/os';
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

export type OpenExternalFn = (uri: string) => Promise<void>;

interface RunningEntry {
  child: ChildProcess;
  sessionId: string | null;
  gameId: string;
}

export interface LauncherDeps {
  db: DatabaseSync;
  /** Override for tests. Defaults to child_process.spawn. */
  spawnImpl?: SpawnFn;
  /** Override for tests. Defaults to Electron's shell.openExternal. */
  openExternalImpl?: OpenExternalFn;
  /** Override for tests. Defaults to the real Battle.net OS layer. */
  battleNetOs?: BattleNetOs;
  /** Called after a successful spawn (e.g. to minimize the window). */
  onLaunched?: (gameId: string) => void;
}

const CHECKPOINT_INTERVAL_MS = 30_000;

export class GameLauncher {
  private readonly db: DatabaseSync;
  private readonly spawnImpl: SpawnFn;
  private readonly openExternalImpl: OpenExternalFn | undefined;
  private readonly battleNetOs: BattleNetOs;
  private readonly onLaunched: ((gameId: string) => void) | undefined;
  private readonly running = new Map<string, RunningEntry>();
  private checkpointTimer: NodeJS.Timeout | null = null;

  constructor(deps: LauncherDeps) {
    this.db = deps.db;
    this.spawnImpl = deps.spawnImpl ?? spawn;
    this.openExternalImpl = deps.openExternalImpl;
    this.battleNetOs = deps.battleNetOs ?? new RealBattleNetOs();
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
    if (game.source === 'steam') {
      return this.launchSteam(gameId);
    }
    if (game.source === 'epic') {
      return this.launchEpic(gameId);
    }
    if (game.source !== 'manual') {
      throw new ValidationError(
        'NOT_IMPLEMENTED',
        `Launching from ${game.source} is not implemented yet.`,
      );
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
      // Read the CURRENT session id from the entry: it may have been
      // re-keyed by onPlayHistoryCleared() while this game was running.
      const sid = entry.sessionId;
      if (sid) {
        const endedAt = new Date().toISOString();
        const session = finalizeSession(this.db, sid, { state, notes });
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

  /**
   * Shared OS URI handoff for store sources (Steam per-game URIs, Epic's
   * launcher URI). The handoff is reported as "launch requested" — never as
   * "running", because the OS gives us no handle on the resulting process.
   * A session row with trackingMethod 'unavailable' records the request
   * honestly; no playtime is invented (last_played_at / total_play_ms are
   * untouched).
   */
  private async handoffStoreUri(
    gameId: string,
    expectedSource: 'steam' | 'epic',
    uri: string,
    sessionNotes: string,
  ): Promise<{ sessionId: string | null; alreadyRunning: boolean }> {
    const game = getGame(this.db, gameId);
    if (!game || game.source !== expectedSource) {
      throw new ValidationError('NOT_FOUND', 'Game not found in the library.');
    }
    if (!this.openExternalImpl) {
      throw new ValidationError(
        'NO_OS_HANDOFF',
        'OS URI handoff is unavailable in this environment.',
      );
    }
    try {
      await this.openExternalImpl(uri);
    } catch (err) {
      throw new ValidationError(
        'LAUNCH_REQUEST_FAILED',
        `Could not hand "${game.title}" to the ${expectedSource === 'steam' ? 'Steam' : 'Epic Games'} client: ${(err as Error).message}`,
      );
    }
    let sessionId: string | null = null;
    if (getSettings(this.db).trackingEnabled) {
      const session = createSession(this.db, gameId, 'unavailable');
      finalizeSession(this.db, session.id, { state: 'completed', notes: sessionNotes });
      sessionId = session.id;
    }
    this.onLaunched?.(gameId);
    return { sessionId, alreadyRunning: false };
  }

  /**
   * Steam launch: hand a validated steam:// URI to the OS.
   */
  private async launchSteam(
    gameId: string,
  ): Promise<{ sessionId: string | null; alreadyRunning: boolean }> {
    const game = getGame(this.db, gameId);
    if (!game || game.source !== 'steam') {
      throw new ValidationError('NOT_FOUND', 'Game not found in the library.');
    }
    if (!isValidAppId(game.externalId)) {
      throw new ValidationError(
        'INVALID_APPID',
        `"${game.title}" has no valid Steam AppID; refusing to build a launch URI.`,
      );
    }
    return this.handoffStoreUri(
      gameId,
      'steam',
      buildRunGameUri(game.externalId),
      'Launch requested — handed to the Steam client. Playtime cannot be tracked for store launches.',
    );
  }

  /**
   * Epic launch: per-game deep links are unverified, so hand the documented
   * Epic Games Launcher URI to the OS. The stored launch URI must be exactly
   * the known launcher scheme — never anything derived from a manifest.
   */
  private async launchEpic(
    gameId: string,
  ): Promise<{ sessionId: string | null; alreadyRunning: boolean }> {
    const game = getGame(this.db, gameId);
    if (!game || game.source !== 'epic') {
      throw new ValidationError('NOT_FOUND', 'Game not found in the library.');
    }
    if (game.launchUri !== EPIC_LAUNCHER_URI) {
      throw new ValidationError(
        'INVALID_LAUNCH_URI',
        `"${game.title}" does not carry the verified Epic launcher URI; refusing to hand off.`,
      );
    }
    return this.handoffStoreUri(
      gameId,
      'epic',
      EPIC_LAUNCHER_URI,
      'Launch requested — Epic Games Launcher is opening. Playtime cannot be tracked for store launches.',
    );
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
   * Open a store client itself (not a game). Used for sources without
   * verified per-game launching — currently Epic (documented launcher URI)
   * and Battle.net (validated client executable). Reports success/failure
   * honestly; never claims a game is running. No session is recorded: the
   * client is not a game.
   */
  async openClient(source: 'epic' | 'battlenet'): Promise<void> {
    if (source === 'epic') {
      if (!this.openExternalImpl) {
        throw new ValidationError(
          'NO_OS_HANDOFF',
          'OS URI handoff is unavailable in this environment.',
        );
      }
      try {
        await this.openExternalImpl(EPIC_LAUNCHER_URI);
      } catch (err) {
        throw new ValidationError(
          'LAUNCH_REQUEST_FAILED',
          `Could not open the Epic Games Launcher: ${(err as Error).message}`,
        );
      }
      return;
    }
    const probe = new BattleNetAdapter(this.battleNetOs).probe();
    if (probe.status !== 'installed' || !probe.clientExe) {
      throw new ValidationError('CLIENT_NOT_FOUND', probe.reason);
    }
    // Defense in depth: the path came from our own probe, but re-validate
    // the shape before spawning anything.
    const exe = probe.clientExe;
    if (!/Battle\.net\.exe$/i.test(exe)) {
      throw new ValidationError(
        'INVALID_CLIENT_PATH',
        'Refusing to open an unexpected Battle.net client path.',
      );
    }
    try {
      this.spawnImpl(exe, [], { shell: false, windowsHide: true, detached: false });
    } catch (err) {
      throw new ValidationError(
        'LAUNCH_REQUEST_FAILED',
        `Could not open Battle.net: ${(err as Error).message}`,
      );
    }
  }

  /**
   * React to play history being cleared while games are running.
   *
   * Semantics (documented choice): a live game keeps running and its
   * tracking continues — but from the clear moment forward. The old
   * session row was deleted by the clear, so each still-running entry
   * gets a FRESH session row starting now. Nothing is backfilled: the
   * minutes between the old session's start and the clear are gone,
   * which is exactly what "clear history" means. When the process
   * exits, only the post-clear duration is recorded.
   *
   * Must be called synchronously right after the history-clearing
   * transaction commits, with no awaits in between — 'close' event
   * handlers cannot interleave with synchronous code, so no exit can
   * slip in while an entry has a stale session id.
   */
  onPlayHistoryCleared(): void {
    for (const entry of this.running.values()) {
      if (!entry.sessionId) continue; // tracking disabled; nothing recorded
      entry.sessionId = createSession(this.db, entry.gameId, 'observed').id;
    }
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
