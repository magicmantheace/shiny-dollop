/**
 * Calibration data exchange with the Volumetric Mix Calculator (Project 3).
 * This app treats calibration payloads as opaque versioned JSON: it
 * validates the envelope (formatVersion + required sections) against the
 * contract in docs/CALIBRATION_EXCHANGE.md, stores the payload as a profile,
 * and can export it back out. No shared code, no shared dependencies.
 */
import type { DatabaseSync } from 'node:sqlite';
import { z } from 'zod';
import type { CalibrationProfile } from '../../../shared/types';
import { OpsError, OpsErrorCodes } from '../errors';
import { writeAudit } from './audit';

/** Envelope schema — must match docs/CALIBRATION_EXCHANGE.md. */
export const calibrationEnvelopeSchema = z.object({
  formatVersion: z.string().regex(/^\d+\.\d+\.\d+$/, 'formatVersion must be semver X.Y.Z'),
  profileName: z.string().trim().min(1).max(200),
  exportedAt: z.string().datetime({ offset: true }),
  exporter: z.string().trim().min(1).max(200),
  units: z.object({
    volume: z.enum(['m3', 'L', 'yd3']),
    mass: z.enum(['kg', 't', 'lb']),
    length: z.enum(['m', 'mm']),
  }),
  materials: z
    .array(
      z.object({
        materialId: z.string().trim().min(1).max(100),
        kind: z.enum(['cement', 'sand', 'gravel', 'water', 'admixture', 'other']),
        description: z.string().max(500).optional(),
      }),
    )
    .min(1),
  calibrations: z.array(
    z.object({
      materialId: z.string().trim().min(1).max(100),
      gateSetting: z.number().finite(),
      measuredOutputPerUnit: z.number().finite().positive(),
      measuredAt: z.string().datetime({ offset: true }).optional(),
    }),
  ),
  mixes: z
    .array(
      z.object({
        mixDesignId: z.string().trim().min(1).max(40),
        note: z.string().max(500).optional(),
        nominalOnly: z.literal(true),
        components: z
          .array(
            z.object({
              materialId: z.string().trim().min(1).max(100),
              targetPerM3: z.number().finite().nonnegative(),
            }),
          )
          .min(1),
      }),
    )
    .optional(),
});

export type CalibrationEnvelope = z.infer<typeof calibrationEnvelopeSchema>;

export function parseCalibrationEnvelope(payload: unknown): CalibrationEnvelope {
  const parsed = calibrationEnvelopeSchema.safeParse(payload);
  if (!parsed.success) {
    throw new OpsError(
      OpsErrorCodes.VALIDATION,
      `Calibration payload failed envelope validation: ${parsed.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ')}`,
    );
  }
  // Cross-check: every calibration/mix component must reference a declared material.
  const declared = new Set(parsed.data.materials.map((m) => m.materialId));
  const missing = new Set<string>();
  for (const c of parsed.data.calibrations) if (!declared.has(c.materialId)) missing.add(c.materialId);
  for (const mix of parsed.data.mixes ?? []) {
    for (const comp of mix.components) if (!declared.has(comp.materialId)) missing.add(comp.materialId);
  }
  if (missing.size > 0) {
    throw new OpsError(
      OpsErrorCodes.VALIDATION,
      `Calibration payload references undeclared materialId(s): ${[...missing].join(', ')}`,
    );
  }
  return parsed.data;
}

function mapProfile(row: Record<string, unknown>): CalibrationProfile {
  return {
    id: row['id'] as number,
    name: row['name'] as string,
    formatVersion: row['format_version'] as string,
    payloadJson: row['payload_json'] as string,
    importedAt: row['imported_at'] as string,
  };
}

export function listCalibrationProfiles(db: DatabaseSync): CalibrationProfile[] {
  const rows = db.prepare('SELECT * FROM calibration_profiles ORDER BY imported_at DESC').all() as Record<
    string,
    unknown
  >[];
  return rows.map(mapProfile);
}

export function importCalibrationProfile(db: DatabaseSync, payload: unknown): CalibrationProfile {
  const envelope = parseCalibrationEnvelope(payload);
  const now = new Date().toISOString();
  // Store the ORIGINAL validated payload, not the Zod-parsed result:
  // the schemas strip unknown keys, so serializing the parsed envelope
  // silently dropped additive optional fields from compatible minor
  // versions (extra top-level/nested fields). The payload is treated
  // as opaque — validation only checks the known envelope — so the
  // original JSON must round-trip through import → export intact.
  const originalJson = JSON.stringify(payload);
  const result = db
    .prepare(
      `INSERT INTO calibration_profiles (name, format_version, payload_json, imported_at)
       VALUES (?, ?, ?, ?)`,
    )
    .run(envelope.profileName, envelope.formatVersion, originalJson, now);
  const id = Number(result.lastInsertRowid);
  const row = db.prepare('SELECT * FROM calibration_profiles WHERE id = ?').get(id) as Record<string, unknown>;
  const profile = mapProfile(row);
  writeAudit(db, { entityType: 'calibration_profile', entityId: id, action: 'imported', after: { name: profile.name, formatVersion: profile.formatVersion } });
  return profile;
}

export function getCalibrationProfile(db: DatabaseSync, id: number): CalibrationProfile | null {
  const row = db.prepare('SELECT * FROM calibration_profiles WHERE id = ?').get(id) as
    | Record<string, unknown>
    | undefined;
  return row ? mapProfile(row) : null;
}

export function removeCalibrationProfile(db: DatabaseSync, id: number): boolean {
  const profile = getCalibrationProfile(db, id);
  if (!profile) return false;
  db.prepare('DELETE FROM calibration_profiles WHERE id = ?').run(id);
  writeAudit(db, { entityType: 'calibration_profile', entityId: id, action: 'deleted', before: { name: profile.name } });
  return true;
}
