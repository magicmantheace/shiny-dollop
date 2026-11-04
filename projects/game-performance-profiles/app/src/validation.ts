/**
 * Client-side validation for profile names and change specs.
 *
 * Pure functions — no DOM, no IPC — so they are unit-tested directly.
 * The backend re-validates everything; this layer exists to give the user
 * immediate, actionable feedback before any IPC call.
 */
import type { ChangeKind, ChangeSpec } from '../shared/gpp-types';

/** Canonical Windows power-plan GUID shape: 8-4-4-4-12 hex digits. */
export const GUID_RE =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

/** `name.exe` — letters, digits, spaces and a few safe punctuators. */
export const PROCESS_NAME_RE = /^[A-Za-z0-9][A-Za-z0-9 _.\-]*\.exe$/i;

/** `C:\...` or `\\server\...` absolute path ending in `.exe`. */
export const ABS_EXE_PATH_RE =
  /^(?:[A-Za-z]:\\|\\\\)[^<>:"|?*\r\n]+\.exe$/i;

export const MAX_NAME_LENGTH = 80;

export interface ChangeKindMeta {
  kind: ChangeKind;
  label: string;
  description: string;
}

export const CHANGE_KIND_META: ChangeKindMeta[] = [
  {
    kind: 'game-mode',
    label: 'Game Mode',
    description: 'Turn Windows Game Mode on or off.',
  },
  {
    kind: 'power-plan',
    label: 'Power plan',
    description:
      'Switch the active power plan to a specific plan GUID. You must pick your own plan — paste the GUID from `powercfg /list`.',
  },
  {
    kind: 'process-priority',
    label: 'Process priority',
    description:
      'Raise the CPU priority of a running game process. Only above-normal and high are allowed — never realtime.',
  },
  {
    kind: 'fullscreen-optimizations',
    label: 'Fullscreen optimizations',
    description: 'Enable or disable fullscreen optimizations for one .exe.',
  },
];

export const PRIORITY_OPTIONS = ['above-normal', 'high'] as const;

export function validateProfileName(name: string): string | null {
  const trimmed = name.trim();
  if (trimmed.length === 0) return 'Profile name is required.';
  if (trimmed.length > MAX_NAME_LENGTH)
    return `Profile name must be ${MAX_NAME_LENGTH} characters or fewer.`;
  return null;
}

/** Default params for a freshly added change of the given kind. */
export function defaultParams(kind: ChangeKind): Record<string, string> {
  switch (kind) {
    case 'game-mode':
      return { enabled: 'true' };
    case 'power-plan':
      return { guid: '' };
    case 'process-priority':
      return { process: '', priority: 'above-normal' };
    case 'fullscreen-optimizations':
      return { exePath: '', enabled: 'false' };
  }
}

/** Returns a list of human-readable validation errors; empty means valid. */
export function validateChangeParams(
  kind: ChangeKind,
  params: Record<string, string>,
): string[] {
  const errors: string[] = [];
  switch (kind) {
    case 'game-mode': {
      if (params['enabled'] !== 'true' && params['enabled'] !== 'false') {
        errors.push('Game Mode must be set to on or off.');
      }
      break;
    }
    case 'power-plan': {
      const guid = (params['guid'] ?? '').trim();
      if (!guid) {
        errors.push('A power-plan GUID is required — paste it from `powercfg /list`.');
      } else if (!GUID_RE.test(guid)) {
        errors.push(
          'That is not a valid power-plan GUID. Expected format: 8-4-4-4-12 hex digits, e.g. 381b4222-f694-41f0-9685-ff5bb260df2e.',
        );
      }
      break;
    }
    case 'process-priority': {
      const process = (params['process'] ?? '').trim();
      if (!process) {
        errors.push('A process name is required, e.g. game.exe.');
      } else if (!PROCESS_NAME_RE.test(process)) {
        errors.push(
          'Process name must look like a Windows executable, e.g. game.exe (letters, digits, spaces, dots, dashes, underscores).',
        );
      }
      if (!PRIORITY_OPTIONS.includes(params['priority'] as (typeof PRIORITY_OPTIONS)[number])) {
        errors.push('Priority must be above-normal or high. Realtime is never allowed.');
      }
      break;
    }
    case 'fullscreen-optimizations': {
      const exePath = (params['exePath'] ?? '').trim();
      if (!exePath) {
        errors.push('The full path to the game .exe is required.');
      } else if (!ABS_EXE_PATH_RE.test(exePath)) {
        errors.push(
          'Enter an absolute Windows path to an .exe, e.g. C:\\Games\\MyGame\\game.exe.',
        );
      }
      if (params['enabled'] !== 'true' && params['enabled'] !== 'false') {
        errors.push('Fullscreen optimizations must be set to on or off.');
      }
      break;
    }
  }
  return errors;
}

export function validateChange(spec: ChangeSpec): string[] {
  return validateChangeParams(spec.kind, spec.params);
}

/** Short human-readable summary of a change, e.g. `Power plan → 381b4222-…`. */
export function changeSummary(spec: ChangeSpec): string {
  const label = CHANGE_KIND_META.find((m) => m.kind === spec.kind)?.label ?? spec.kind;
  switch (spec.kind) {
    case 'game-mode':
      return `${label}: ${spec.params['enabled'] === 'true' ? 'on' : 'off'}`;
    case 'power-plan':
      return `${label}: ${(spec.params['guid'] ?? '').trim() || '(no GUID set)'}`;
    case 'process-priority':
      return `${label}: ${(spec.params['process'] ?? '').trim() || '(no process)'} → ${spec.params['priority'] ?? ''}`;
    case 'fullscreen-optimizations':
      return `${label}: ${(spec.params['exePath'] ?? '').trim() || '(no path)'} → ${
        spec.params['enabled'] === 'true' ? 'on' : 'off'
      }`;
  }
}

/** The concrete OS target a change applies to (used for display). */
export function changeTarget(spec: ChangeSpec): string {
  switch (spec.kind) {
    case 'game-mode':
      return 'Windows Game Mode';
    case 'power-plan':
      return `Power plan ${(spec.params['guid'] ?? '').trim() || '(unset)'}`;
    case 'process-priority':
      return (spec.params['process'] ?? '').trim() || '(no process)';
    case 'fullscreen-optimizations':
      return (spec.params['exePath'] ?? '').trim() || '(no path)';
  }
}
