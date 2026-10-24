/**
 * Tests for the calibration exchange envelope v1.0.0.
 *
 * These tests pin this calculator's implementation to the contract
 * documented by Concrete Operations Manager (Project 2) in its
 * docs/CALIBRATION_EXCHANGE.md — format conformance only, no shared code.
 * Every documented validation rule has a test here.
 */
import { describe, expect, it } from 'vitest';
import {
  EXCHANGE_FORMAT_VERSION,
  ExchangeEnvelope,
  ExchangeError,
  envelopeToProfile,
  exportEnvelope,
  validateEnvelope,
} from '../../engine/exchange.js';
import { calculate } from '../../engine/calculator.js';
import { fixtureProfile } from '../fixtures.js';

function validPayload(): Record<string, unknown> {
  return JSON.parse(
    JSON.stringify(exportEnvelope(fixtureProfile())),
  ) as Record<string, unknown>;
}

describe('exchange — export', () => {
  it('exports a v1.0.0 envelope with all required fields', () => {
    const env = exportEnvelope(fixtureProfile());
    expect(env.formatVersion).toBe('1.0.0');
    expect(EXCHANGE_FORMAT_VERSION).toBe('1.0.0');
    expect(env.profileName).toBe('Test Truck 7');
    expect(Number.isNaN(Date.parse(env.exportedAt))).toBe(false);
    expect(env.exporter).toContain('Volumetric Mix Calculator');
    expect(env.units).toEqual({ volume: 'm3', mass: 'kg', length: 'm' });
    expect(env.materials.length).toBe(5);
    expect(env.calibrations.length).toBe(5);
    expect(env.mixes!.length).toBe(1);
  });

  it('forces nominalOnly true on every exported mix', () => {
    const env = exportEnvelope(fixtureProfile());
    for (const mix of env.mixes!) {
      expect(mix.nominalOnly).toBe(true);
    }
  });

  it('exported envelope validates against the documented contract', () => {
    const env = exportEnvelope(fixtureProfile());
    expect(() => validateEnvelope(env)).not.toThrow();
  });

  it('round-trips: export → validate → import → calculate identically', () => {
    const env = exportEnvelope(fixtureProfile());
    const validated = validateEnvelope(JSON.parse(JSON.stringify(env)));
    const profile = envelopeToProfile(validated);
    const req = {
      profile,
      mixDesignId: 'NOM-25',
      volume: 8,
      volumeUnit: 'm3' as const,
      wasteAllowancePct: 5,
    };
    const fromRoundTrip = calculate(req);
    const fromOriginal = calculate({ ...req, profile: fixtureProfile() });
    // The v1.0.0 envelope carries measuredAt but not the free-text `source`
    // note (no such field in the contract), so strip `source` before comparing.
    const norm = (r: typeof fromOriginal) =>
      JSON.stringify({
        ...r,
        calculatedAt: 'x',
        materials: r.materials.map((m) => ({
          ...m,
          calibrationUsed: { ...m.calibrationUsed, source: undefined },
        })),
      });
    expect(norm(fromRoundTrip)).toBe(norm(fromOriginal));
  });
});

describe('exchange — validation rules (documented contract)', () => {
  it('rule 1: rejects malformed formatVersion', () => {
    const p = validPayload();
    p.formatVersion = '1.0';
    expect(() => validateEnvelope(p)).toThrowError(ExchangeError);
  });

  it('rule 1: rejects unknown major versions', () => {
    const p = validPayload();
    p.formatVersion = '2.0.0';
    expect(() => validateEnvelope(p)).toThrowError(/major version 2/);
  });

  it('rule 2: rejects unknown unit strings', () => {
    const p = validPayload();
    (p.units as Record<string, string>).volume = 'gallon';
    expect(() => validateEnvelope(p)).toThrowError(/units\.volume/);
    const p2 = validPayload();
    (p2.units as Record<string, string>).mass = 'oz';
    expect(() => validateEnvelope(p2)).toThrowError(/units\.mass/);
    const p3 = validPayload();
    (p3.units as Record<string, string>).length = 'ft';
    expect(() => validateEnvelope(p3)).toThrowError(/units\.length/);
  });

  it('rule 3: rejects empty materials and duplicate materialIds', () => {
    const p = validPayload();
    p.materials = [];
    expect(() => validateEnvelope(p)).toThrowError(/non-empty/);
    const p2 = validPayload();
    (p2.materials as unknown[]).push((p2.materials as unknown[])[0]);
    expect(() => validateEnvelope(p2)).toThrowError(/Duplicate materialId/);
  });

  it('rule 4: rejects calibrations referencing undeclared materials', () => {
    const p = validPayload();
    (p.calibrations as Record<string, unknown>[])[0].materialId = 'ghost';
    expect(() => validateEnvelope(p)).toThrowError(/undeclared materialId/);
  });

  it('rule 4: rejects mix components referencing undeclared materials', () => {
    const p = validPayload();
    const mixes = p.mixes as Record<string, unknown>[];
    (mixes[0].components as Record<string, unknown>[])[0].materialId = 'ghost';
    expect(() => validateEnvelope(p)).toThrowError(/undeclared materialId/);
  });

  it('rule 5: rejects non-finite and non-positive numerics', () => {
    const p = validPayload();
    (p.calibrations as Record<string, unknown>[])[0].measuredOutputPerUnit = 0;
    expect(() => validateEnvelope(p)).toThrowError(/must be > 0/);
    const p2 = validPayload();
    (p2.calibrations as Record<string, unknown>[])[1].gateSetting = NaN;
    expect(() => validateEnvelope(p2)).toThrowError(/finite/);
    const p3 = validPayload();
    const mixes = p3.mixes as Record<string, unknown>[];
    (mixes[0].components as Record<string, unknown>[])[0].targetPerM3 = -2;
    expect(() => validateEnvelope(p3)).toThrowError(/must be >= 0/);
  });

  it('rule 6: rejects payloads over 5 MB', () => {
    const p = validPayload();
    (p.materials as Record<string, unknown>[])[0].description = 'x'.repeat(6 * 1024 * 1024);
    expect(() => validateEnvelope(p)).toThrowError(/5 MB/);
  });

  it('nominalOnly must be literally true', () => {
    const p = validPayload();
    const mixes = p.mixes as Record<string, unknown>[];
    mixes[0].nominalOnly = false;
    expect(() => validateEnvelope(p)).toThrowError(/nominalOnly must be literally true/);
    const p2 = validPayload();
    const mixes2 = p2.mixes as Record<string, unknown>[];
    delete mixes2[0].nominalOnly;
    expect(() => validateEnvelope(p2)).toThrowError(/nominalOnly must be literally true/);
  });

  it('rejects over-long profileName and bad exportedAt', () => {
    const p = validPayload();
    p.profileName = 'x'.repeat(201);
    expect(() => validateEnvelope(p)).toThrowError(/profileName/);
    const p2 = validPayload();
    p2.exportedAt = 'not-a-date';
    expect(() => validateEnvelope(p2)).toThrowError(/exportedAt/);
  });

  it('accepts envelopes without the optional mixes array', () => {
    const p = validPayload();
    delete p.mixes;
    const env: ExchangeEnvelope = validateEnvelope(p);
    expect(env.mixes).toBeUndefined();
    expect(envelopeToProfile(env).mixes).toEqual([]);
  });

  it('accepts envelopes as JSON strings', () => {
    const env = validateEnvelope(JSON.stringify(validPayload()));
    expect(env.formatVersion).toBe('1.0.0');
  });
});

describe('exchange — import semantics', () => {
  it('preserves unknown material kinds as other with a note', () => {
    const p = validPayload();
    (p.materials as Record<string, unknown>[])[0].kind = 'flyash';
    const profile = envelopeToProfile(validateEnvelope(p));
    expect(profile.materials[0].kind).toBe('other');
    expect(profile.materials[0].description).toContain('flyash');
  });

  it('imported profile calculates the same as the original', () => {
    const profile = envelopeToProfile(validateEnvelope(validPayload()));
    const r = calculate({
      profile,
      mixDesignId: 'NOM-25',
      volume: 8,
      volumeUnit: 'm3',
      wasteAllowancePct: 5,
    });
    const cement = r.materials.find((m) => m.materialId === 'cement')!;
    expect(cement.requiredQty).toBeCloseTo(2688, 6);
  });
});
