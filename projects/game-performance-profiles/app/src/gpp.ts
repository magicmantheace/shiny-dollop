/**
 * Thin typed wrapper around the `window.gpp` preload bridge.
 *
 * Every call goes through `bridge()` so a missing preload produces one clear,
 * actionable error instead of a cryptic `undefined` crash. Responses that
 * carry `{ error }` are converted into thrown Errors so callers deal with a
 * single failure shape.
 */
import type {
  ActivationProgress,
  ActivationResult,
  Capability,
  ChangeSpec,
  ErrorResponse,
  GppApi,
  JournalEntry,
  PlannedChange,
  Profile,
  ResourceSnapshot,
  RollbackResult,
  RestoreAllResult,
} from '../shared/gpp-types';

export function bridge(): GppApi {
  const api = window.gpp;
  if (!api) {
    throw new Error(
      'Game Performance Profiles bridge (window.gpp) is not available. ' +
        'Run this UI inside the Electron app with its preload script loaded.',
    );
  }
  return api;
}

/** Throws when the response is an `{ error }` payload; otherwise narrows it away. */
function assertNoError<T>(resp: T | ErrorResponse, action: string): asserts resp is T {
  if (
    resp !== null &&
    typeof resp === 'object' &&
    'error' in resp &&
    typeof (resp as ErrorResponse).error === 'string' &&
    (resp as ErrorResponse).error.length > 0
  ) {
    throw new Error(`${action} failed: ${(resp as ErrorResponse).error}`);
  }
}

export async function listCapabilities(): Promise<Capability[]> {
  const { capabilities } = await bridge().getCapabilities();
  return capabilities;
}

export async function listProfiles(): Promise<Profile[]> {
  const { profiles } = await bridge().listProfiles();
  return profiles;
}

export async function createProfile(input: {
  name: string;
  changes: ChangeSpec[];
}): Promise<Profile> {
  const resp = await bridge().createProfile(input);
  assertNoError(resp, 'Create profile');
  return resp.profile;
}

export async function updateProfile(input: {
  id: string;
  name?: string;
  changes?: ChangeSpec[];
}): Promise<Profile> {
  const resp = await bridge().updateProfile(input);
  assertNoError(resp, 'Update profile');
  return resp.profile;
}

export async function deleteProfile(id: string): Promise<void> {
  const resp = await bridge().deleteProfile({ id });
  assertNoError(resp, 'Delete profile');
}

export async function previewProfile(profileId: string): Promise<PlannedChange[]> {
  const resp = await bridge().previewProfile({ profileId });
  assertNoError(resp, 'Preview');
  return resp.planned;
}

export async function activateProfile(
  profileId: string,
  approved: true,
): Promise<ActivationResult> {
  const resp = await bridge().activateProfile({ profileId, approved });
  assertNoError(resp, 'Activate');
  return resp.result;
}

export async function rollbackProfile(profileId: string): Promise<RollbackResult> {
  const resp = await bridge().rollbackProfile({ profileId });
  assertNoError(resp, 'Roll back');
  return resp.result;
}

export async function restoreAll(): Promise<RestoreAllResult> {
  const { result } = await bridge().restoreAll();
  return result;
}

export async function listJournal(): Promise<JournalEntry[]> {
  const { entries } = await bridge().listJournal();
  return entries;
}

export async function takeSnapshot(label: string): Promise<ResourceSnapshot> {
  const resp = await bridge().takeSnapshot({ label });
  assertNoError(resp, 'Take snapshot');
  return resp.snapshot;
}

export async function listSnapshots(): Promise<ResourceSnapshot[]> {
  const { snapshots } = await bridge().listSnapshots();
  return snapshots;
}

/** Subscribe to activation progress events; returns an unsubscribe function. */
export function onActivationProgress(
  cb: (p: ActivationProgress) => void,
): () => void {
  return bridge().onActivationProgress(cb);
}
