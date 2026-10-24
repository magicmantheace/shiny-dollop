/**
 * IPC handlers for the twelve gpp:* channels.
 *
 * createHandlers(ctx) returns a plain map of channel -> async handler so the
 * logic is unit-testable without Electron. registerIpcHandlers() wires the map
 * to ipcMain.handle(). Every handler validates its payload with zod and
 * returns either the documented response shape or { error: string }.
 */

import { ipcMain } from 'electron';
import type {
  ChangeSpec,
  Profile,
} from '../../../shared/gpp-types.js';
import { ACTIVATION_PROGRESS_EVENT, IPC_CHANNELS } from '../../../shared/gpp-types.js';
import { GppDatabase } from '../store/database.js';
import { MockOsLayer } from '../os-layer/mock.js';
import { OsLayer, ProgressCallback } from '../os-layer/types.js';
import { activateProfile, previewProfile, restoreAll, rollbackProfile, takeSnapshot } from '../engine/index.js';
import {
  activateProfileSchema,
  createProfileSchema,
  deleteProfileSchema,
  emptySchema,
  formatZodError,
  previewProfileSchema,
  rollbackProfileSchema,
  takeSnapshotSchema,
  updateProfileSchema,
} from './schemas.js';

export interface HandlerContext {
  db: GppDatabase;
  os: OsLayer;
  /** Forward activation progress events to the renderer. */
  emit: (event: string, payload: unknown) => void;
  /** Seed the built-in profile on first run. Returns the seeded profile if created. */
  seed?: () => Profile | undefined;
}

type Handler = (payload: unknown) => Promise<unknown>;

import { z } from 'zod';

function parse<T>(schema: z.ZodType<T>, payload: unknown): { data?: T; error?: string } {
  const r = schema.safeParse(payload);
  if (!r.success) return { error: formatZodError(r.error) };
  return { data: r.data };
}

function asChangeSpecs(changes: Array<{ kind: string; params: Record<string, string> }>): ChangeSpec[] {
  return changes.map((c) => ({ kind: c.kind as ChangeSpec['kind'], params: c.params }));
}

export function createHandlers(ctx: HandlerContext): Record<string, Handler> {
  const { db, os } = ctx;
  const onProgress: ProgressCallback = (p) => ctx.emit(ACTIVATION_PROGRESS_EVENT, p);

  // Shared mutation lock: activation, rollback and restore-all all mutate
  // OS state and append/retire journal entries. If two of them ran
  // concurrently (e.g. the renderer closes the activation dialog while an
  // activation is still running and starts another one), their OS
  // mutations and journal inserts could interleave, so a journal entry's
  // recorded `before` would no longer be the value the previous entry
  // left behind and the rollback chain would be corrupt. Queue every
  // mutating operation through one promise chain so operations run
  // strictly in invocation order and journal order always matches OS
  // mutation order. The chain itself never rejects, so one failed
  // operation cannot wedge the operations queued behind it.
  let mutationQueue: Promise<void> = Promise.resolve();
  function withMutationLock<T>(fn: () => Promise<T>): Promise<T> {
    const result = mutationQueue.then(() => fn());
    mutationQueue = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  }

  return {
    [IPC_CHANNELS.capabilities]: async () => {
      const capabilities = await os.probeCapabilities();
      return { capabilities };
    },

    [IPC_CHANNELS.profilesList]: async () => {
      return { profiles: db.listProfiles() };
    },

    [IPC_CHANNELS.profilesCreate]: async (payload) => {
      const { data, error } = parse(createProfileSchema, payload);
      if (error || !data) return { error: error ?? 'Invalid input.' };
      const profile = db.createProfile(data.name, asChangeSpecs(data.changes));
      return { profile };
    },

    [IPC_CHANNELS.profilesUpdate]: async (payload) => {
      const { data, error } = parse(updateProfileSchema, payload);
      if (error || !data) return { error: error ?? 'Invalid input.' };
      const profile = db.updateProfile(data.id, {
        ...(data.name !== undefined ? { name: data.name } : {}),
        ...(data.changes !== undefined ? { changes: asChangeSpecs(data.changes) } : {}),
      });
      if (!profile) return { error: `Profile "${data.id}" not found.` };
      return { profile };
    },

    [IPC_CHANNELS.profilesDelete]: async (payload) => {
      const { data, error } = parse(deleteProfileSchema, payload);
      if (error || !data) return { error: error ?? 'Invalid input.' };
      const deleted = db.deleteProfile(data.id);
      if (!deleted) return { error: `Profile "${data.id}" not found.` };
      return { ok: true as const };
    },

    [IPC_CHANNELS.profilesPreview]: async (payload) => {
      const { data, error } = parse(previewProfileSchema, payload);
      if (error || !data) return { error: error ?? 'Invalid input.' };
      const profile = db.getProfile(data.profileId);
      if (!profile) return { error: `Profile "${data.profileId}" not found.` };
      const planned = await previewProfile(profile, os);
      return { planned };
    },

    [IPC_CHANNELS.profilesActivate]: async (payload) => {
      const { data, error } = parse(activateProfileSchema, payload);
      if (error || !data) return { error: error ?? 'Invalid input.' };
      // Explicit-consent gate: the renderer must pass approved === true from a
      // real user confirmation. Anything else is rejected before touching the OS.
      if (data.approved !== true) {
        return { error: 'Activation requires explicit approval (approved === true).' };
      }
      return withMutationLock(async () => {
        // Re-read the profile inside the lock so a queued activation sees
        // the state the previous mutation left behind.
        const profile = db.getProfile(data.profileId);
        if (!profile) return { error: `Profile "${data.profileId}" not found.` };
        const result = await activateProfile(profile, os, { db, onProgress });
        return { result };
      });
    },

    [IPC_CHANNELS.profilesRollback]: async (payload) => {
      const { data, error } = parse(rollbackProfileSchema, payload);
      if (error || !data) return { error: error ?? 'Invalid input.' };
      return withMutationLock(async () => {
        const result = await rollbackProfile(data.profileId, os, db, (id) => db.getProfile(id));
        return { result };
      });
    },

    [IPC_CHANNELS.restoreAll]: async (payload) => {
      const { error } = parse(emptySchema, payload ?? {});
      if (error) return { error };
      return withMutationLock(async () => {
        const result = await restoreAll(os, db, (id) => db.getProfile(id));
        return { result };
      });
    },

    [IPC_CHANNELS.journalList]: async () => {
      return { entries: db.listJournal() };
    },

    [IPC_CHANNELS.snapshotsTake]: async (payload) => {
      const { data, error } = parse(takeSnapshotSchema, payload);
      if (error || !data) return { error: error ?? 'Invalid input.' };
      const snapshot = await takeSnapshot(data.label, os, db);
      return { snapshot };
    },

    [IPC_CHANNELS.snapshotsList]: async () => {
      return { snapshots: db.listSnapshots() };
    },
  };
}

export function registerIpcHandlers(ctx: HandlerContext): void {
  const handlers = createHandlers(ctx);
  for (const [channel, handler] of Object.entries(handlers)) {
    ipcMain.handle(channel, async (_event, payload) => {
      try {
        return await handler(payload);
      } catch (e) {
        return { error: e instanceof Error ? e.message : String(e) };
      }
    });
  }
}

/** Re-exported for main.ts convenience. */
export { MockOsLayer };
