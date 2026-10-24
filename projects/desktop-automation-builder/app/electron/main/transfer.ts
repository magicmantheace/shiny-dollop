// Workflow export / import. Imports are validated and never auto-run:
// they create a brand-new workflow record with a fresh id.
import { DatabaseSync } from 'node:sqlite';
import { z } from 'zod';
import { DAB_ERROR_CODES, dabError } from '../../shared/errors.js';
import type { Workflow } from '../../shared/types.js';
import { importEnvelopeSchema } from './schemas.js';
import { insertWorkflowWithId, nowIso } from './store.js';

export const EXPORT_FORMAT_VERSION = '1.0.0';

export interface ExportEnvelope {
  formatVersion: string;
  exportedAt: string;
  workflow: {
    name: string;
    sandboxRoot: string;
    steps: Workflow['steps'];
    version: number;
  };
}

export function exportWorkflowJson(wf: Workflow): string {
  const envelope: ExportEnvelope = {
    formatVersion: EXPORT_FORMAT_VERSION,
    exportedAt: nowIso(),
    workflow: {
      name: wf.name,
      sandboxRoot: wf.sandboxRoot,
      steps: wf.steps,
      version: wf.version,
    },
  };
  return JSON.stringify(envelope, null, 2);
}

function majorOf(formatVersion: string): number | null {
  const major = formatVersion.split('.')[0];
  if (major === undefined || !/^\d+$/.test(major)) return null;
  return Number.parseInt(major, 10);
}

export function importWorkflowJson(db: DatabaseSync, json: string): Workflow {
  let raw: unknown;
  try {
    raw = JSON.parse(json);
  } catch {
    throw dabError(DAB_ERROR_CODES.IMPORT_INVALID, 'Import payload is not valid JSON.');
  }
  if (typeof raw !== 'object' || raw === null || typeof (raw as { formatVersion?: unknown }).formatVersion !== 'string') {
    throw dabError(DAB_ERROR_CODES.IMPORT_INVALID, 'Import payload is missing formatVersion.');
  }
  const declared = (raw as { formatVersion: string }).formatVersion;
  const major = majorOf(declared);
  if (major === null) {
    throw dabError(DAB_ERROR_CODES.IMPORT_INVALID, `Import payload has an unreadable formatVersion: "${declared}".`);
  }
  if (major !== 1) {
    throw dabError(
      DAB_ERROR_CODES.IMPORT_VERSION_UNSUPPORTED,
      `Unsupported import formatVersion "${declared}": only major version 1 is supported.`,
    );
  }
  const parsed = importEnvelopeSchema.safeParse(raw);
  if (!parsed.success) {
    throw dabError(DAB_ERROR_CODES.IMPORT_INVALID, `Import payload failed validation: ${parsed.error.message}`);
  }
  const w = parsed.data.workflow;
  return insertWorkflowWithId(db, {
    name: w.name,
    sandboxRoot: w.sandboxRoot,
    steps: w.steps,
    version: w.version ?? 1,
  });
}

export type ImportEnvelopeInput = z.infer<typeof importEnvelopeSchema>;
