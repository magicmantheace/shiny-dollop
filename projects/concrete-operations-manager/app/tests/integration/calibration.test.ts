import { afterEach, describe, expect, it } from 'vitest';
import { makeTestDb } from '../helpers';
import type { DatabaseSync } from 'node:sqlite';
import {
  importCalibrationProfile,
  listCalibrationProfiles,
  parseCalibrationEnvelope,
  removeCalibrationProfile,
} from '../../electron/main/db/calibration';
import { OpsError } from '../../electron/main/errors';

let db: DatabaseSync;
afterEach(() => {
  try {
    db?.close();
  } catch {
    // ignore
  }
});

const VALID_ENVELOPE = {
  formatVersion: '1.0.0',
  profileName: 'Synthetic Plant Profile',
  exportedAt: '2026-10-23T10:00:00.000Z',
  exporter: 'Volumetric Mix Calculator (synthetic fixture)',
  units: { volume: 'm3', mass: 'kg', length: 'm' },
  materials: [
    { materialId: 'cement-type10', kind: 'cement', description: 'Type 10 Portland' },
    { materialId: 'sand-washed', kind: 'sand' },
  ],
  calibrations: [
    { materialId: 'cement-type10', gateSetting: 42, measuredOutputPerUnit: 12.5 },
  ],
  mixes: [
    {
      mixDesignId: 'C25/30',
      nominalOnly: true,
      components: [{ materialId: 'cement-type10', targetPerM3: 320 }],
    },
  ],
};

describe('calibration exchange envelope', () => {
  it('accepts a valid envelope and stores it as a profile', () => {
    db = makeTestDb();
    const profile = importCalibrationProfile(db, VALID_ENVELOPE);
    expect(profile.name).toBe('Synthetic Plant Profile');
    expect(profile.formatVersion).toBe('1.0.0');
    const stored = JSON.parse(profile.payloadJson) as Record<string, unknown>;
    expect(stored['profileName']).toBe('Synthetic Plant Profile');
    expect(listCalibrationProfiles(db)).toHaveLength(1);
    expect(removeCalibrationProfile(db, profile.id)).toBe(true);
    expect(listCalibrationProfiles(db)).toHaveLength(0);
  });

  it('rejects envelopes with bad versions, unknown units, or dangling references', () => {
    expect(() => parseCalibrationEnvelope({ ...VALID_ENVELOPE, formatVersion: 'v1' })).toThrow(OpsError);
    expect(() =>
      parseCalibrationEnvelope({ ...VALID_ENVELOPE, units: { volume: 'gallons', mass: 'kg', length: 'm' } }),
    ).toThrow(OpsError);
    expect(() =>
      parseCalibrationEnvelope({
        ...VALID_ENVELOPE,
        calibrations: [{ materialId: 'undeclared-stuff', gateSetting: 1, measuredOutputPerUnit: 1 }],
      }),
    ).toThrow(/undeclared materialId/);
    expect(() =>
      parseCalibrationEnvelope({
        ...VALID_ENVELOPE,
        mixes: [{ mixDesignId: 'C25/30', nominalOnly: true, components: [{ materialId: 'nope', targetPerM3: 1 }] }],
      }),
    ).toThrow(/undeclared materialId/);
  });

  it('rejects non-object and non-JSON payloads at import', () => {
    db = makeTestDb();
    expect(() => importCalibrationProfile(db, null)).toThrow(OpsError);
    expect(() => importCalibrationProfile(db, 'not json')).toThrow(OpsError);
    expect(() => importCalibrationProfile(db, [])).toThrow(OpsError);
  });
});
