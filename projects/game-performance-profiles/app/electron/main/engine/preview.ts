/**
 * previewProfile — resolve each change spec into a PlannedChange without
 * touching the OS for anything unsupported.
 *
 * For every change: read the current value (`from`), derive the desired value
 * (`to`), mark reversibility, and surface capability support + reason.
 * Unsupported changes are reported, never attempted.
 */

import type { Capability, ChangeKind, PlannedChange, Profile } from '../../../shared/gpp-types.js';
import { CHANGE_KINDS } from '../../../shared/gpp-types.js';
import {
  describeDesired,
  describeTarget,
  isValidGuid,
  OsLayer,
  processImageNameProblem,
} from '../os-layer/types.js';

let changeSeq = 0;

/** Deterministic per-preview change ids (unique within a process run). */
export function nextChangeId(): string {
  changeSeq += 1;
  return `chg-${changeSeq}`;
}

export async function previewProfile(profile: Profile, os: OsLayer): Promise<PlannedChange[]> {
  const capabilities = new Map<string, Capability>();
  for (const c of await os.probeCapabilities()) {
    capabilities.set(c.id, c);
  }

  const planned: PlannedChange[] = [];
  for (const change of profile.changes) {
    planned.push(await previewOne(change.kind, change.params, capabilities, os));
  }
  return planned;
}

async function previewOne(
  kind: string,
  params: Record<string, string>,
  capabilities: Map<string, Capability>,
  os: OsLayer,
): Promise<PlannedChange> {
  const changeId = nextChangeId();

  if (!CHANGE_KINDS.includes(kind as ChangeKind)) {
    return {
      changeId,
      kind: kind as ChangeKind,
      target: '(unknown change)',
      from: '',
      to: '',
      reversible: false,
      supported: false,
      unsupportedReason: `Unknown change kind "${kind}".`,
    };
  }
  const k = kind as ChangeKind;
  const target = describeTarget(k, params);

  // Parameter validation that must hold before anything is attempted.
  const paramProblem = validateParams(k, params);
  if (paramProblem) {
    return { changeId, kind: k, target, from: '', to: '', reversible: true, supported: false, unsupportedReason: paramProblem };
  }

  const cap = capabilities.get(k);
  if (!cap?.supported) {
    return {
      changeId,
      kind: k,
      target,
      from: '',
      to: '',
      reversible: true,
      supported: false,
      unsupportedReason: cap?.reason ?? `Capability "${k}" is not supported on this machine.`,
    };
  }

  const from = await os.readCurrent(k, params);
  const to = describeDesired(k, params);
  return { changeId, kind: k, target, from, to, reversible: true, supported: true };
}

/**
 * Static parameter problems surfaced in preview AND enforced again at
 * activation time (defense in depth). Returns a human-readable reason or
 * undefined when the params are acceptable.
 */
export function validateParams(kind: ChangeKind, params: Record<string, string>): string | undefined {
  switch (kind) {
    case 'game-mode':
      return undefined;
    case 'power-plan': {
      const guid = (params['guid'] ?? '').trim();
      if (!guid) {
        return 'No power-plan GUID selected — pick a power plan in the UI before activation.';
      }
      if (!isValidGuid(guid)) {
        return `Malformed power-plan GUID "${params['guid']}".`;
      }
      return undefined;
    }
    case 'process-priority': {
      // Rejects empty names, wildcard patterns (which Get-Process -Name
      // would expand onto protected processes) and denylisted processes.
      const nameProblem = processImageNameProblem(params['imageName'] ?? '');
      if (nameProblem) return nameProblem;
      const p = (params['priority'] ?? '').trim().toLowerCase();
      if (p !== 'above-normal' && p !== 'high' && p !== 'abovenormal' && p !== 'above_normal') {
        return `Unsupported priority "${params['priority']}" — only above-normal and high are allowed.`;
      }
      return undefined;
    }
    case 'fullscreen-optimizations':
      if (!(params['childKey'] ?? '').trim()) return 'fullscreen-optimizations requires params.childKey.';
      return undefined;
  }
}
