/**
 * Calibration exchange envelope v1.0.0.
 *
 * Implements the contract documented by Concrete Operations Manager
 * (Project 2) in its docs/CALIBRATION_EXCHANGE.md. This module is an
 * independent implementation — no shared code or dependencies between the
 * two projects, format conformance only.
 *
 * Rules enforced here mirror the documented validation rules:
 *  1. formatVersion matches ^\d+\.\d+\.\d+$; unknown MAJOR versions rejected.
 *  2. units enums exact (volume: m3|L|yd3; mass: kg|t|lb; length: m|mm).
 *  3. materials non-empty; materialIds unique, 1–100 chars.
 *  4. calibrations[].materialId and mixes[].components[].materialId must
 *     reference declared materials.
 *  5. Numeric fields finite; measuredOutputPerUnit > 0; targetPerM3 >= 0.
 *  6. Payload size <= 5 MB (import guard).
 * Plus: mixes[].nominalOnly must be literally true (nominal-only mix IDs).
 */

import { isMassUnit, isVolumeUnit } from './units.js';
import type { CalibrationProfile, MaterialKind } from './types.js';

export const EXCHANGE_FORMAT_VERSION = '1.0.0';
const MAX_PAYLOAD_BYTES = 5 * 1024 * 1024;

type LengthUnit = 'm' | 'mm';

export interface ExchangeUnits {
  volume: 'm3' | 'L' | 'yd3';
  mass: 'kg' | 't' | 'lb';
  length: LengthUnit;
}

export interface ExchangeMaterial {
  materialId: string;
  kind: MaterialKind | string;
  description?: string;
}

export interface ExchangeCalibration {
  materialId: string;
  gateSetting: number;
  measuredOutputPerUnit: number;
  measuredAt?: string;
}

export interface ExchangeMixComponent {
  materialId: string;
  targetPerM3: number;
}

export interface ExchangeMix {
  mixDesignId: string;
  note?: string;
  nominalOnly: true;
  components: ExchangeMixComponent[];
}

export interface ExchangeEnvelope {
  formatVersion: string;
  profileName: string;
  exportedAt: string;
  exporter: string;
  units: ExchangeUnits;
  materials: ExchangeMaterial[];
  calibrations: ExchangeCalibration[];
  mixes?: ExchangeMix[];
}

export class ExchangeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ExchangeError';
  }
}

const APP_ID = 'Volumetric Mix Calculator 0.1.0';

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function checkFiniteNumber(v: unknown, label: string): number {
  if (typeof v !== 'number' || !Number.isFinite(v)) {
    throw new ExchangeError(`${label} must be a finite number.`);
  }
  return v;
}

/**
 * Validate an unknown payload against the v1.0.0 envelope contract.
 * Returns the typed envelope on success; throws ExchangeError otherwise.
 */
export function validateEnvelope(payload: unknown): ExchangeEnvelope {
  const json = typeof payload === 'string' ? payload : JSON.stringify(payload);
  if (Buffer.byteLength(json, 'utf8') > MAX_PAYLOAD_BYTES) {
    throw new ExchangeError(`Payload exceeds the 5 MB import guard.`);
  }
  const env: unknown = typeof payload === 'string' ? JSON.parse(payload) : payload;
  if (!isRecord(env)) throw new ExchangeError('Envelope must be a JSON object.');

  // formatVersion
  if (typeof env.formatVersion !== 'string' || !/^\d+\.\d+\.\d+$/.test(env.formatVersion)) {
    throw new ExchangeError('formatVersion must be a semver string like "1.0.0".');
  }
  const [major] = env.formatVersion.split('.').map(Number);
  if (major !== 1) {
    throw new ExchangeError(
      `Unsupported envelope major version ${major} (this reader implements 1.x).`,
    );
  }

  if (typeof env.profileName !== 'string' || env.profileName.length < 1 || env.profileName.length > 200) {
    throw new ExchangeError('profileName must be 1–200 characters.');
  }
  if (typeof env.exportedAt !== 'string' || Number.isNaN(Date.parse(env.exportedAt))) {
    throw new ExchangeError('exportedAt must be an RFC 3339 timestamp.');
  }
  if (typeof env.exporter !== 'string' || env.exporter.length < 1 || env.exporter.length > 200) {
    throw new ExchangeError('exporter must be 1–200 characters.');
  }

  // units
  if (!isRecord(env.units)) throw new ExchangeError('units must be an object.');
  const { volume, mass, length } = env.units;
  if (!isVolumeUnit(volume)) throw new ExchangeError(`units.volume must be one of m3|L|yd3 (got ${JSON.stringify(volume)}).`);
  if (!isMassUnit(mass)) throw new ExchangeError(`units.mass must be one of kg|t|lb (got ${JSON.stringify(mass)}).`);
  if (length !== 'm' && length !== 'mm') throw new ExchangeError(`units.length must be one of m|mm (got ${JSON.stringify(length)}).`);

  // materials
  if (!Array.isArray(env.materials) || env.materials.length === 0) {
    throw new ExchangeError('materials must be a non-empty array.');
  }
  const ids = new Set<string>();
  const kinds = new Map<string, string>();
  for (const m of env.materials) {
    if (!isRecord(m)) throw new ExchangeError('Each material must be an object.');
    if (typeof m.materialId !== 'string' || m.materialId.length < 1 || m.materialId.length > 100) {
      throw new ExchangeError('Each materialId must be 1–100 characters.');
    }
    if (ids.has(m.materialId)) throw new ExchangeError(`Duplicate materialId "${m.materialId}".`);
    ids.add(m.materialId);
    if (typeof m.kind !== 'string' || m.kind.length === 0) {
      throw new ExchangeError(`Material "${m.materialId}" must declare a kind.`);
    }
    kinds.set(m.materialId, m.kind);
    if (m.description !== undefined && typeof m.description !== 'string') {
      throw new ExchangeError(`Material "${m.materialId}" description must be a string.`);
    }
  }

  // calibrations
  if (!Array.isArray(env.calibrations)) throw new ExchangeError('calibrations must be an array.');
  for (const c of env.calibrations) {
    if (!isRecord(c)) throw new ExchangeError('Each calibration must be an object.');
    if (typeof c.materialId !== 'string' || !ids.has(c.materialId)) {
      throw new ExchangeError(`Calibration references undeclared materialId "${String(c.materialId)}".`);
    }
    const out = checkFiniteNumber(c.measuredOutputPerUnit, `measuredOutputPerUnit for "${c.materialId}"`);
    if (out <= 0) throw new ExchangeError(`measuredOutputPerUnit for "${c.materialId}" must be > 0.`);
    checkFiniteNumber(c.gateSetting, `gateSetting for "${c.materialId}"`);
    if (c.measuredAt !== undefined && typeof c.measuredAt !== 'string') {
      throw new ExchangeError(`measuredAt for "${c.materialId}" must be a string.`);
    }
  }

  // mixes (optional)
  let mixes: ExchangeMix[] | undefined;
  if (env.mixes !== undefined) {
    if (!Array.isArray(env.mixes)) throw new ExchangeError('mixes must be an array.');
    mixes = [];
    for (const mix of env.mixes) {
      if (!isRecord(mix)) throw new ExchangeError('Each mix must be an object.');
      if (typeof mix.mixDesignId !== 'string' || mix.mixDesignId.length === 0) {
        throw new ExchangeError('Each mix needs a non-empty mixDesignId.');
      }
      if (mix.nominalOnly !== true) {
        throw new ExchangeError(
          `Mix "${mix.mixDesignId}": nominalOnly must be literally true — mix IDs are nominal identifiers only, never structural performance claims.`,
        );
      }
      if (!Array.isArray(mix.components)) throw new ExchangeError(`Mix "${mix.mixDesignId}" components must be an array.`);
      const components: ExchangeMixComponent[] = [];
      for (const comp of mix.components) {
        if (!isRecord(comp)) throw new ExchangeError(`Mix "${mix.mixDesignId}" has a non-object component.`);
        if (typeof comp.materialId !== 'string' || !ids.has(comp.materialId)) {
          throw new ExchangeError(`Mix "${mix.mixDesignId}" references undeclared materialId "${String(comp.materialId)}".`);
        }
        const t = checkFiniteNumber(comp.targetPerM3, `targetPerM3 for "${comp.materialId}"`);
        if (t < 0) throw new ExchangeError(`targetPerM3 for "${comp.materialId}" must be >= 0.`);
        components.push({ materialId: comp.materialId, targetPerM3: t });
      }
      mixes.push({
        mixDesignId: mix.mixDesignId,
        ...(typeof mix.note === 'string' ? { note: mix.note } : {}),
        nominalOnly: true,
        components,
      });
    }
  }

  return {
    formatVersion: env.formatVersion,
    profileName: env.profileName,
    exportedAt: env.exportedAt,
    exporter: env.exporter,
    units: { volume, mass, length },
    materials: env.materials.map((m: Record<string, unknown>) => ({
      materialId: m.materialId as string,
      kind: m.kind as string,
      ...(typeof m.description === 'string' ? { description: m.description } : {}),
    })),
    calibrations: env.calibrations.map((c: Record<string, unknown>) => ({
      materialId: c.materialId as string,
      gateSetting: c.gateSetting as number,
      measuredOutputPerUnit: c.measuredOutputPerUnit as number,
      ...(typeof c.measuredAt === 'string' ? { measuredAt: c.measuredAt } : {}),
    })),
    ...(mixes ? { mixes } : {}),
  };
}

/**
 * Export a calibration profile to the v1.0.0 exchange envelope.
 * measuredOutputPerUnit is expressed in the envelope's mass unit for
 * mass-basis materials (cement/sand/gravel/other) and in the envelope's
 * volume unit for volume-basis materials (water/admixture) — the convention
 * documented alongside the contract.
 */
export function exportEnvelope(profile: CalibrationProfile): ExchangeEnvelope {
  const materials: ExchangeMaterial[] = profile.materials.map((m) => ({
    materialId: m.materialId,
    kind: m.kind,
    ...(m.description ? { description: m.description } : {}),
  }));
  const calibrations: ExchangeCalibration[] = profile.calibrations.map((c) => ({
    materialId: c.materialId,
    gateSetting: c.gateSetting,
    measuredOutputPerUnit: c.measuredOutputPerUnit,
    ...(c.measuredAt ? { measuredAt: c.measuredAt } : {}),
  }));
  const mixes: ExchangeMix[] = profileMixesToExchange(profile);
  return {
    formatVersion: EXCHANGE_FORMAT_VERSION,
    profileName: profile.profileName,
    exportedAt: new Date().toISOString(),
    exporter: APP_ID,
    units: { volume: profile.units.volume, mass: profile.units.mass, length: 'm' },
    materials,
    calibrations,
    mixes,
  };
}

/**
 * Convert a validated envelope back into an internal calibration profile.
 * Unknown material kinds are preserved as 'other' with the original kind
 * recorded in the description, so round-trips never lose data.
 */
export function envelopeToProfile(env: ExchangeEnvelope): CalibrationProfile {
  return {
    profileName: env.profileName,
    units: { volume: env.units.volume, mass: env.units.mass },
    materials: env.materials.map((m) => {
      const known = (['cement', 'sand', 'gravel', 'water', 'admixture', 'other'] as const).includes(
        m.kind as MaterialKind,
      );
      const kindNote = known ? undefined : `imported kind "${m.kind}"`;
      return {
        materialId: m.materialId,
        kind: known ? (m.kind as MaterialKind) : ('other' as MaterialKind),
        description: [m.description, kindNote].filter(Boolean).join('; ') || undefined,
      };
    }),
    calibrations: env.calibrations.map((c) => ({
      materialId: c.materialId,
      gateSetting: c.gateSetting,
      measuredOutputPerUnit: c.measuredOutputPerUnit,
      ...(c.measuredAt ? { measuredAt: c.measuredAt } : {}),
    })),
    mixes: (env.mixes ?? []).map((mix) => ({
      mixDesignId: mix.mixDesignId,
      ...(mix.note ? { note: mix.note } : {}),
      nominalOnly: true as const,
      components: mix.components.map((comp) => ({
        materialId: comp.materialId,
        targetPerM3: comp.targetPerM3,
      })),
    })),
  };
}

/** Map internal mix designs to exchange-format mixes (nominalOnly always true). */
export function profileMixesToExchange(profile: CalibrationProfile): ExchangeMix[] {
  return profile.mixes.map((mix) => ({
    mixDesignId: mix.mixDesignId,
    ...(mix.note ? { note: mix.note } : {}),
    nominalOnly: true as const,
    components: mix.components.map((c) => ({ materialId: c.materialId, targetPerM3: c.targetPerM3 })),
  }));
}
