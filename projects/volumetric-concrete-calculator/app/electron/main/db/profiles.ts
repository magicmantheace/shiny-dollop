/**
 * Profile persistence: CRUD for calibration profiles, materials,
 * calibrations and mix designs. All writes validated through the engine's
 * validateProfile before commit.
 */
import { validateProfile } from '../../../engine/calculator.js';
import type { CalibrationProfile, ProfileSummary } from '../../../shared/types.js';
import { getDb } from './database.js';

function nowIso(): string {
  return new Date().toISOString();
}

/** node:sqlite has no transaction() helper — wrap explicitly. */
function inTransaction<T>(fn: () => T): T {
  const db = getDb();
  db.exec('BEGIN IMMEDIATE');
  try {
    const result = fn();
    db.exec('COMMIT');
    return result;
  } catch (e) {
    try {
      db.exec('ROLLBACK');
    } catch {
      /* already rolled back */
    }
    throw e;
  }
}

export function listProfiles(): ProfileSummary[] {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT p.id, p.profile_name AS profileName, p.volume_unit AS volumeUnit,
              p.mass_unit AS massUnit, p.updated_at AS updatedAt,
              (SELECT COUNT(*) FROM materials m WHERE m.profile_id = p.id) AS materialCount,
              (SELECT COUNT(*) FROM mixes x WHERE x.profile_id = p.id) AS mixCount
       FROM profiles p ORDER BY p.updated_at DESC`,
    )
    .all() as unknown as ProfileSummary[];
  return rows;
}

export function getProfile(id: number): CalibrationProfile & { id: number } {
  const db = getDb();
  const prow = db
    .prepare('SELECT id, profile_name AS profileName, volume_unit AS volumeUnit, mass_unit AS massUnit FROM profiles WHERE id = ?')
    .get(id) as unknown as { id: number; profileName: string; volumeUnit: 'm3' | 'L' | 'yd3'; massUnit: 'kg' | 't' | 'lb' } | undefined;
  if (!prow) throw new Error(`Profile ${id} not found.`);
  const materials = db
    .prepare('SELECT material_id AS materialId, kind, description FROM materials WHERE profile_id = ? ORDER BY id')
    .all(id) as unknown as { materialId: string; kind: string; description: string | null }[];
  const calibrations = db
    .prepare(
      'SELECT material_id AS materialId, gate_setting AS gateSetting, measured_output_per_unit AS measuredOutputPerUnit, measured_at AS measuredAt, source FROM calibrations WHERE profile_id = ? ORDER BY id',
    )
    .all(id) as unknown as { materialId: string; gateSetting: number; measuredOutputPerUnit: number; measuredAt: string | null; source: string | null }[];
  const mixRows = db
    .prepare('SELECT id, mix_design_id AS mixDesignId, note FROM mixes WHERE profile_id = ? ORDER BY id')
    .all(id) as unknown as { id: number; mixDesignId: string; note: string | null }[];
  const mixes = mixRows.map((mix) => ({
    mixDesignId: mix.mixDesignId,
    ...(mix.note ? { note: mix.note } : {}),
    nominalOnly: true as const,
    components: (
      db
        .prepare('SELECT material_id AS materialId, target_per_m3 AS targetPerM3 FROM mix_components WHERE mix_id = ? ORDER BY id')
        .all(mix.id) as unknown as { materialId: string; targetPerM3: number }[]
    ).map((c) => ({ materialId: c.materialId, targetPerM3: c.targetPerM3 })),
  }));
  return {
    id: prow.id,
    profileName: prow.profileName,
    units: { volume: prow.volumeUnit, mass: prow.massUnit },
    materials: materials.map((m) => ({
      materialId: m.materialId,
      kind: m.kind as CalibrationProfile['materials'][number]['kind'],
      ...(m.description ? { description: m.description } : {}),
    })),
    calibrations: calibrations.map((c) => ({
      materialId: c.materialId,
      gateSetting: c.gateSetting,
      measuredOutputPerUnit: c.measuredOutputPerUnit,
      ...(c.measuredAt ? { measuredAt: c.measuredAt } : {}),
      ...(c.source ? { source: c.source } : {}),
    })),
    mixes,
  };
}

function insertProfileTx(profile: CalibrationProfile): number {
  const db = getDb();
  validateProfile(profile);
  const now = nowIso();
  const info = db
    .prepare('INSERT INTO profiles (profile_name, volume_unit, mass_unit, created_at, updated_at) VALUES (?,?,?, ?,?)')
    .run(profile.profileName, profile.units.volume, profile.units.mass, now, now);
  const profileId = Number(info.lastInsertRowid);
  const matStmt = db.prepare('INSERT INTO materials (profile_id, material_id, kind, description) VALUES (?,?,?,?)');
  for (const m of profile.materials) matStmt.run(profileId, m.materialId, m.kind, m.description ?? null);
  const calStmt = db.prepare(
    'INSERT INTO calibrations (profile_id, material_id, gate_setting, measured_output_per_unit, measured_at, source) VALUES (?,?,?,?,?,?)',
  );
  for (const c of profile.calibrations) {
    calStmt.run(profileId, c.materialId, c.gateSetting, c.measuredOutputPerUnit, c.measuredAt ?? null, c.source ?? null);
  }
  const mixStmt = db.prepare('INSERT INTO mixes (profile_id, mix_design_id, note) VALUES (?,?,?)');
  const compStmt = db.prepare('INSERT INTO mix_components (mix_id, material_id, target_per_m3) VALUES (?,?,?)');
  for (const mix of profile.mixes) {
    const mi = mixStmt.run(profileId, mix.mixDesignId, mix.note ?? null);
    const mixId = Number(mi.lastInsertRowid);
    for (const comp of mix.components) compStmt.run(mixId, comp.materialId, comp.targetPerM3);
  }
  return profileId;
}

export function createProfile(profile: CalibrationProfile): number {
  return inTransaction(() => insertProfileTx(profile));
}

export function updateProfile(id: number, profile: CalibrationProfile): void {
  // Ensure it exists first for an actionable error.
  getProfile(id);
  validateProfile(profile);
  const db = getDb();
  inTransaction(() => {
    db.prepare('DELETE FROM mix_components WHERE mix_id IN (SELECT id FROM mixes WHERE profile_id = ?)').run(id);
    db.prepare('DELETE FROM mixes WHERE profile_id = ?').run(id);
    db.prepare('DELETE FROM calibrations WHERE profile_id = ?').run(id);
    db.prepare('DELETE FROM materials WHERE profile_id = ?').run(id);
    db.prepare('UPDATE profiles SET profile_name = ?, volume_unit = ?, mass_unit = ?, updated_at = ? WHERE id = ?').run(
      profile.profileName,
      profile.units.volume,
      profile.units.mass,
      nowIso(),
      id,
    );
    const matStmt = db.prepare('INSERT INTO materials (profile_id, material_id, kind, description) VALUES (?,?,?,?)');
    for (const m of profile.materials) matStmt.run(id, m.materialId, m.kind, m.description ?? null);
    const calStmt = db.prepare(
      'INSERT INTO calibrations (profile_id, material_id, gate_setting, measured_output_per_unit, measured_at, source) VALUES (?,?,?,?,?,?)',
    );
    for (const c of profile.calibrations) {
      calStmt.run(id, c.materialId, c.gateSetting, c.measuredOutputPerUnit, c.measuredAt ?? null, c.source ?? null);
    }
    const mixStmt = db.prepare('INSERT INTO mixes (profile_id, mix_design_id, note) VALUES (?,?,?)');
    const compStmt = db.prepare('INSERT INTO mix_components (mix_id, material_id, target_per_m3) VALUES (?,?,?)');
    for (const mix of profile.mixes) {
      const mi = mixStmt.run(id, mix.mixDesignId, mix.note ?? null);
      const mixId = Number(mi.lastInsertRowid);
      for (const comp of mix.components) compStmt.run(mixId, comp.materialId, comp.targetPerM3);
    }
  });
}

export function deleteProfile(id: number): void {
  const db = getDb();
  const info = db.prepare('DELETE FROM profiles WHERE id = ?').run(id);
  if (info.changes === 0) throw new Error(`Profile ${id} not found.`);
}

export function recordCalculation(input: {
  profileId: number;
  profileName: string;
  mixDesignId: string;
  volume: number;
  volumeUnit: string;
  wasteAllowancePct: number;
  resultJson: string;
}): number {
  const db = getDb();
  const info = db
    .prepare(
      'INSERT INTO calculations (profile_id, profile_name, mix_design_id, volume, volume_unit, waste_allowance_pct, result_json, created_at) VALUES (?,?,?,?,?,?,?,?)',
    )
    .run(
      input.profileId,
      input.profileName,
      input.mixDesignId,
      input.volume,
      input.volumeUnit,
      input.wasteAllowancePct,
      input.resultJson,
      nowIso(),
    );
  return Number(info.lastInsertRowid);
}

export function listCalculations(limit = 50): import('../../../shared/types.js').CalculationRecord[] {
  const db = getDb();
  return db
    .prepare(
      `SELECT id, profile_id AS profileId, profile_name AS profileName, mix_design_id AS mixDesignId,
              volume, volume_unit AS volumeUnit, waste_allowance_pct AS wasteAllowancePct,
              result_json AS resultJson, created_at AS createdAt
       FROM calculations ORDER BY id DESC LIMIT ?`,
    )
    .all(limit) as unknown as import('../../../shared/types.js').CalculationRecord[];
}
