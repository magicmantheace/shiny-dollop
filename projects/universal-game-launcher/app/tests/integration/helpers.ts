/** Drive IPC handlers directly (no Electron ipcMain) for integration tests. */
import type { DatabaseSync } from 'node:sqlite';
import { EventEmitter } from 'node:events';
import { openDatabase } from '../../electron/main/data/database';
import { createHandlers, type HandlerDeps } from '../../electron/main/ipc/handlers';
import { GameLauncher, type OpenExternalFn, type SpawnFn } from '../../electron/main/launch/launcher';
import type { SteamOs } from '../../electron/main/sources/steam/os';
import type { EpicOs } from '../../electron/main/sources/epic/os';
import type { BattleNetOs } from '../../electron/main/sources/battlenet/os';

export interface SpawnCall {
  exe: string;
  args: readonly string[];
  opts: Record<string, unknown>;
}

export interface SpawnStub {
  calls: SpawnCall[];
  procs: EventEmitter[];
  spawnImpl: SpawnFn;
  /**
   * When true (default), each spawned proc emits 'spawn' on the next tick,
   * mirroring Node: a successful spawn always emits 'spawn'; a failed spawn
   * emits only 'error'. Set false to simulate failures deterministically.
   */
  autoSpawn: boolean;
  /** Emit 'close' on the most recent spawned process. */
  closeLast: (code?: number) => void;
  /** Emit 'error' on the most recent spawned process. */
  errorLast: (message: string, code?: string) => void;
}

export function makeSpawnStub(): SpawnStub {
  const calls: SpawnCall[] = [];
  const procs: EventEmitter[] = [];
  const stub: SpawnStub = {
    calls,
    procs,
    autoSpawn: true,
    spawnImpl: undefined as unknown as SpawnFn,
    closeLast: (code = 0) => {
      const last = procs[procs.length - 1];
      if (last) last.emit('close', code);
    },
    errorLast: (message: string, code?: string) => {
      const last = procs[procs.length - 1];
      if (last) {
        const err = new Error(message) as NodeJS.ErrnoException;
        if (code) err.code = code;
        last.emit('error', err);
      }
    },
  };
  stub.spawnImpl = ((exe, args, opts) => {
    calls.push({ exe, args, opts: { ...(opts as object) } });
    const proc = new EventEmitter() as EventEmitter & { kill: () => void };
    proc.kill = () => undefined;
    procs.push(proc);
    if (stub.autoSpawn) setImmediate(() => proc.emit('spawn'));
    return proc as unknown as ReturnType<SpawnFn>;
  }) as SpawnFn;
  return stub;
}

export interface TestContext {
  db: DatabaseSync;
  launcher: GameLauncher;
  stub: SpawnStub;
  deps: HandlerDeps;
  /** Invoke a channel the way ipcMain.handle would (schema-validated). */
  call: (channel: string, payload?: unknown) => Promise<{ ok: boolean; data?: unknown; error?: { code: string; message: string } }>;
  close: () => void;
}

export function createTestContext(overrides?: {
  steamOs?: SteamOs;
  epicOs?: EpicOs;
  battleNetOs?: BattleNetOs;
  openExternalImpl?: OpenExternalFn;
}): TestContext {
  const db = openDatabase(':memory:');
  const stub = makeSpawnStub();
  const launcher = new GameLauncher({
    db,
    spawnImpl: stub.spawnImpl,
    openExternalImpl: overrides?.openExternalImpl,
    battleNetOs: overrides?.battleNetOs,
  });
  const handlers = createHandlers();
  const deps: HandlerDeps = {
    db,
    launcher,
    chooseExecutable: async () => ({ canceled: true }),
    chooseCover: async () => ({ canceled: true }),
    getCoversDir: () => '/tmp/ugl-test-covers',
    getMainWindow: () => null,
    steamOs: overrides?.steamOs,
    epicOs: overrides?.epicOs,
    battleNetOs: overrides?.battleNetOs,
  };
  const call = async (channel: string, payload?: unknown) => {
    const def = handlers.find((h) => h.channel === channel);
    if (!def) throw new Error(`No handler for ${channel}`);
    try {
      const parsed = def.schema.parse(payload);
      const data = await def.run(parsed as never, deps);
      return { ok: true as const, data };
    } catch (err) {
      // Mirror registerIpcHandlers' sanitization for the common cases.
      const e = err as { code?: string; message?: string; issues?: unknown[] };
      if (e.issues) return { ok: false as const, error: { code: 'VALIDATION_ERROR', message: 'Invalid request.' } };
      return {
        ok: false as const,
        error: { code: e.code ?? 'INTERNAL', message: e.message ?? 'error' },
      };
    }
  };
  return {
    db,
    launcher,
    stub,
    deps,
    call,
    close: () => {
      launcher.shutdown();
      db.close();
    },
  };
}
