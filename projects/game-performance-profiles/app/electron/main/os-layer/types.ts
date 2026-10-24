/**
 * OsLayer — narrow interface between the engine and the operating system.
 *
 * The engine (preview/activate/rollback) is written against this interface,
 * so all OS interaction is funnelled through four operations per change kind.
 * `MockOsLayer` implements it in memory for tests on any platform;
 * `WindowsOsLayer` implements it against documented Windows APIs.
 *
 * Change kinds:
 * - game-mode:               HKCU\Software\Microsoft\GameBar\AllowAutoGameMode (DWORD)
 * - power-plan:              powercfg /getactivescheme + /setactive <GUID>
 * - process-priority:        per-process priority class (ABOVE_NORMAL or HIGH only)
 * - fullscreen-optimizations: per-game values under HKCU\System\GameConfigStore\Children\
 */

import type {
  ActivationProgress,
  Capability,
  ChangeKind,
} from '../../../shared/gpp-types.js';

/** Error thrown when an OsLayer refuses an operation for safety or support reasons. */
export class OsLayerError extends Error {
  readonly code: 'unsupported' | 'refused' | 'not-found' | 'os-error';
  constructor(code: OsLayerError['code'], message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = 'OsLayerError';
    this.code = code;
  }
}

/**
 * Describe the desired end state of a change as an opaque string, in the same
 * format `readCurrent` returns. Pure — never touches the OS. Used by the
 * engine for previews and journal `after` values.
 */
export function describeDesired(kind: ChangeKind, params: Record<string, string>): string {
  switch (kind) {
    case 'game-mode':
      return normalizeEnabled(params['enabled']) ? 'enabled' : 'disabled';
    case 'power-plan':
      return normalizeGuid(params['guid'] ?? '');
    case 'process-priority':
      return normalizePriority(params['priority'] ?? '');
    case 'fullscreen-optimizations':
      return normalizeEnabled(params['disableFse']) ? 'disabled' : 'enabled';
    default: {
      const _exhaustive: never = kind;
      throw new OsLayerError('refused', `Unknown change kind "${_exhaustive}".`);
    }
  }
}

/** Human-readable target for a change, for previews and the journal. */
export function describeTarget(kind: ChangeKind, params: Record<string, string>): string {
  switch (kind) {
    case 'game-mode':
      return 'Windows Game Mode (Auto Game Mode)';
    case 'power-plan':
      return `power plan ${params['guid'] ?? '(not set)'}`;
    case 'process-priority':
      return `${params['imageName'] ?? '(no process)'} → ${params['priority'] ?? '(no priority)'}`;
    case 'fullscreen-optimizations':
      return `fullscreen optimizations for ${params['childKey'] ?? '(no game key)'}`;
    default: {
      const _exhaustive: never = kind;
      throw new OsLayerError('refused', `Unknown change kind "${_exhaustive}".`);
    }
  }
}

export function normalizeEnabled(raw: string | undefined): boolean {
  return raw === 'true' || raw === '1' || raw === 'yes';
}

export const GUID_RE = /^\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?$/;

/** True when the string is a well-formed GUID (braces optional). */
export function isValidGuid(raw: string): boolean {
  return GUID_RE.test(raw.trim());
}

/** Canonical GUID form: lowercase, no braces. Throws on malformed input. */
export function normalizeGuid(raw: string): string {
  const trimmed = raw.trim().toLowerCase();
  if (!isValidGuid(trimmed)) {
    throw new OsLayerError('refused', `Malformed power-plan GUID: "${raw}"`);
  }
  return trimmed.replace(/^\{/, '').replace(/\}$/, '');
}

/**
 * Only these priority classes may ever be set. Realtime is deliberately
 * absent: setting realtime priority can starve input and the OS itself.
 */
export type AllowedPriority = 'above-normal' | 'high';

export function normalizePriority(raw: string): AllowedPriority {
  const v = raw.trim().toLowerCase();
  if (v === 'above-normal' || v === 'abovenormal' || v === 'above_normal') return 'above-normal';
  if (v === 'high') return 'high';
  throw new OsLayerError(
    'refused',
    `Unsupported priority "${raw}" — only above-normal and high are allowed (never realtime).`,
  );
}

/**
 * System processes the app must NEVER reprioritize. Compared
 * case-insensitively, with and without a trailing `.exe`.
 */
export const SYSTEM_PROCESS_DENYLIST: readonly string[] = [
  'system',
  'registry',
  'smss.exe',
  'csrss.exe',
  'wininit.exe',
  'services.exe',
  'lsass.exe',
  'lsaiso.exe',
  'svchost.exe',
  'winlogon.exe',
  'dwm.exe',
  'explorer.exe',
  'spoolsv.exe',
  'conhost.exe',
  'taskhostw.exe',
];

/** True when the image name is on the system-process denylist. */
export function isDeniedSystemProcess(imageName: string): boolean {
  const v = imageName.trim().toLowerCase();
  return SYSTEM_PROCESS_DENYLIST.some((d) => v === d || v === `${d}.exe` || `${v}.exe` === d);
}

export interface OsLayer {
  /** 'win32' for the real implementation, 'mock' for the in-memory one. */
  readonly platform: 'win32' | 'mock';

  /**
   * Probe each capability. The Windows layer must never attempt a change
   * whose capability reports unsupported; the engine skips those changes
   * before calling apply().
   */
  probeCapabilities(): Promise<Capability[]>;

  /**
   * Read the current value for a change, as an opaque string in the same
   * format describeDesired() produces. Used for preview `from` and journaling.
   */
  readCurrent(kind: ChangeKind, params: Record<string, string>): Promise<string>;

  /**
   * Apply the change described by (kind, params). The caller must have
   * verified capability support first. Must refuse denylisted processes and
   * invalid parameters by throwing OsLayerError.
   */
  apply(kind: ChangeKind, params: Record<string, string>): Promise<void>;

  /**
   * Restore a previously recorded value (the journal `before`), reversing an
   * earlier apply(). Same refusal rules as apply().
   */
  restore(kind: ChangeKind, params: Record<string, string>, value: string): Promise<void>;

  /** Point-in-time resource observation. */
  takeSnapshot(): Promise<{ cpuPercent: number; memoryMb: number }>;
}

export type ProgressCallback = (p: ActivationProgress) => void;
