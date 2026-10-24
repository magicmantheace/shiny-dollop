/**
 * Type declarations for the renderer: the `window.gpp` API exposed by the
 * preload script, plus re-exports of every shared contract type.
 *
 * Worker B: import types from here (or from ../shared/gpp-types) and call
 * window.gpp — the twelve channel names and shapes are stable.
 */

import type {
  ActivateProfileInput,
  ActivateResponse,
  ActivationProgress,
  ActivationResult,
  CapabilitiesResponse,
  Capability,
  ChangeKind,
  ChangeSpec,
  CreateProfileInput,
  DeleteProfileInput,
  ErrorResponse,
  GppApi,
  JournalEntry,
  JournalListResponse,
  OkResponse,
  PlannedChange,
  PreviewProfileInput,
  PreviewResponse,
  Profile,
  ProfileResponse,
  ProfilesListResponse,
  ResourceSnapshot,
  RestoreAllResponse,
  RollbackProfileInput,
  RollbackResponse,
  RollbackResult,
  RestoreAllResult,
  SkippedChange,
  SnapshotResponse,
  SnapshotsListResponse,
  TakeSnapshotInput,
  UpdateProfileInput,
} from '../shared/gpp-types.js';

export type {
  ActivateProfileInput,
  ActivateResponse,
  ActivationProgress,
  ActivationResult,
  CapabilitiesResponse,
  Capability,
  ChangeKind,
  ChangeSpec,
  CreateProfileInput,
  DeleteProfileInput,
  ErrorResponse,
  GppApi,
  JournalEntry,
  JournalListResponse,
  OkResponse,
  PlannedChange,
  PreviewProfileInput,
  PreviewResponse,
  Profile,
  ProfileResponse,
  ProfilesListResponse,
  ResourceSnapshot,
  RestoreAllResponse,
  RollbackProfileInput,
  RollbackResponse,
  RollbackResult,
  RestoreAllResult,
  SkippedChange,
  SnapshotResponse,
  SnapshotsListResponse,
  TakeSnapshotInput,
  UpdateProfileInput,
};

declare global {
  interface Window {
    gpp: GppApi;
  }
}
