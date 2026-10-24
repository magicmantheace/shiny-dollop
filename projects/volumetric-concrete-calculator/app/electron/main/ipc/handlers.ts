/**
 * IPC handlers — all inputs validated with zod before touching the engine or DB.
 * Calculation results always carry assumptions and estimate-only warnings;
 * nothing here asserts structural strength, code compliance, or legal payload.
 */
import { dialog, ipcMain } from 'electron';
import fs from 'node:fs';
import { z } from 'zod';
import { calculate, CalculationError } from '../../../engine/calculator.js';
import { calculationToCsv } from '../../../engine/csv.js';
import {
  envelopeToProfile,
  ExchangeError,
  exportEnvelope,
  validateEnvelope,
} from '../../../engine/exchange.js';
import { isMassUnit, isVolumeUnit } from '../../../engine/units.js';
import type { CalibrationProfile } from '../../../shared/types.js';
import { createProfile, deleteProfile, getProfile, listCalculations, listProfiles, recordCalculation, updateProfile } from '../db/profiles.js';

const unitsSchema = z.object({
  volume: z.string().refine(isVolumeUnit, 'volume must be one of m3|L|yd3'),
  mass: z.string().refine(isMassUnit, 'mass must be one of kg|t|lb'),
});

const materialSchema = z.object({
  materialId: z.string().min(1).max(100),
  kind: z.enum(['cement', 'sand', 'gravel', 'water', 'admixture', 'other']),
  description: z.string().max(500).optional(),
});

const calibrationSchema = z.object({
  materialId: z.string().min(1).max(100),
  gateSetting: z.number().finite().positive().max(1_000_000),
  measuredOutputPerUnit: z.number().finite().positive().max(1_000_000_000),
  measuredAt: z.string().max(100).optional(),
  source: z.string().max(500).optional(),
});

const mixComponentSchema = z.object({
  materialId: z.string().min(1).max(100),
  targetPerM3: z.number().finite().min(0).max(100_000),
});

const mixSchema = z.object({
  mixDesignId: z.string().min(1).max(100),
  note: z.string().max(500).optional(),
  nominalOnly: z.literal(true, {
    message: 'nominalOnly must be true — mix IDs are nominal identifiers only, never structural performance claims.',
  }),
  components: mixComponentSchema.array().min(1).max(100),
});

const profileSchema = z.object({
  profileName: z.string().trim().min(1).max(200),
  units: unitsSchema,
  materials: materialSchema.array().min(1).max(200),
  calibrations: calibrationSchema.array().max(1000),
  mixes: mixSchema.array().max(200),
});

const stockSchema = z.record(z.string().min(1).max(100), z.number().finite().min(0).max(1_000_000_000));

const calculateSchema = z.object({
  profileId: z.number().int().positive(),
  mixDesignId: z.string().min(1).max(100),
  volume: z.number().finite().positive().max(1_000_000),
  volumeUnit: z.string().refine(isVolumeUnit, 'volumeUnit must be one of m3|L|yd3'),
  wasteAllowancePct: z.number().finite().min(0).max(100),
  startingStock: stockSchema.optional(),
  lowStockThresholds: stockSchema.optional(),
  truckLimits: z
    .object({
      maxVolume: z.number().finite().positive().max(1_000_000).optional(),
      maxPayloadMass: z.number().finite().positive().max(10_000_000).optional(),
    })
    .optional(),
  measuredVolumeProducedM3: z.number().finite().min(0).max(1_000_000).optional(),
});

function toError(e: unknown): { code: string; message: string } {
  if (e instanceof CalculationError || e instanceof ExchangeError) {
    return { code: 'VALIDATION', message: e.message };
  }
  if (e instanceof z.ZodError) {
    return { code: 'VALIDATION', message: e.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ') };
  }
  return { code: 'INTERNAL', message: e instanceof Error ? e.message : String(e) };
}

async function pickSavePath(defaultName: string, filters: { name: string; extensions: string[] }[]): Promise<string | null> {
  const res = await dialog.showSaveDialog({ defaultPath: defaultName, filters });
  return res.canceled || !res.filePath ? null : res.filePath;
}

export function registerIpc(): void {
  ipcMain.handle('profiles.list', () => {
    try {
      return { ok: true, data: listProfiles() };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('profiles.get', (_e, rawId: unknown) => {
    try {
      const id = z.number().int().positive().parse(rawId);
      return { ok: true, data: getProfile(id) };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('profiles.create', (_e, raw: unknown) => {
    try {
      const parsed = profileSchema.parse(raw) as CalibrationProfile;
      return { ok: true, data: { id: createProfile(parsed) } };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('profiles.update', (_e, raw: unknown) => {
    try {
      const { id, profile } = z.object({ id: z.number().int().positive(), profile: profileSchema }).parse(raw);
      updateProfile(id, profile as CalibrationProfile);
      return { ok: true, data: { id } };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('profiles.delete', (_e, rawId: unknown) => {
    try {
      const id = z.number().int().positive().parse(rawId);
      deleteProfile(id);
      return { ok: true, data: { id } };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('calc.run', (_e, raw: unknown) => {
    try {
      const input = calculateSchema.parse(raw);
      const profile = getProfile(input.profileId);
      const result = calculate({
        profile,
        mixDesignId: input.mixDesignId,
        volume: input.volume,
        volumeUnit: input.volumeUnit as 'm3' | 'L' | 'yd3',
        wasteAllowancePct: input.wasteAllowancePct,
        ...(input.startingStock ? { startingStock: input.startingStock } : {}),
        ...(input.lowStockThresholds ? { lowStockThresholds: input.lowStockThresholds } : {}),
        ...(input.truckLimits ? { truckLimits: input.truckLimits } : {}),
        ...(input.measuredVolumeProducedM3 !== undefined ? { measuredVolumeProducedM3: input.measuredVolumeProducedM3 } : {}),
      });
      const id = recordCalculation({
        profileId: input.profileId,
        profileName: profile.profileName,
        mixDesignId: input.mixDesignId,
        volume: input.volume,
        volumeUnit: input.volumeUnit,
        wasteAllowancePct: input.wasteAllowancePct,
        resultJson: JSON.stringify(result),
      });
      return { ok: true, data: { id, result, massUnit: profile.units.mass } };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('history.list', () => {
    try {
      return { ok: true, data: listCalculations() };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('export.envelope', async (_e, rawId: unknown) => {
    try {
      const id = z.number().int().positive().parse(rawId);
      const profile = getProfile(id);
      const envelope = exportEnvelope(profile);
      // Re-validate what we export: our side of the contract must always
      // satisfy the documented v1.0.0 rules.
      validateEnvelope(envelope);
      const filePath = await pickSavePath(`${profile.profileName.replace(/[^\w\-]+/g, '_')}-calibration.json`, [
        { name: 'JSON', extensions: ['json'] },
      ]);
      if (!filePath) return { ok: true, data: { canceled: true } };
      fs.writeFileSync(filePath, JSON.stringify(envelope, null, 2), 'utf8');
      return { ok: true, data: { filePath } };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('export.csv', async (_e, raw: unknown) => {
    try {
      const { calculationId } = z.object({ calculationId: z.number().int().positive() }).parse(raw);
      const rec = listCalculations(1000).find((r) => r.id === calculationId);
      if (!rec) throw new Error(`Calculation ${calculationId} not found.`);
      const result = JSON.parse(rec.resultJson) as import('../../../shared/types.js').CalculationResult;
      const profile = getProfile(rec.profileId);
      const csv = calculationToCsv(result, profile.units.mass);
      const filePath = await pickSavePath(`calculation-${calculationId}.csv`, [{ name: 'CSV', extensions: ['csv'] }]);
      if (!filePath) return { ok: true, data: { canceled: true } };
      fs.writeFileSync(filePath, csv, 'utf8');
      return { ok: true, data: { filePath } };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });

  ipcMain.handle('import.envelope', async () => {
    try {
      const res = await dialog.showOpenDialog({
        properties: ['openFile'],
        filters: [{ name: 'JSON', extensions: ['json'] }],
      });
      if (res.canceled || res.filePaths.length === 0) return { ok: true, data: { canceled: true } };
      const raw = fs.readFileSync(res.filePaths[0], 'utf8');
      const envelope = validateEnvelope(raw);
      const profile = envelopeToProfile(envelope);
      const id = createProfile(profile);
      return { ok: true, data: { id, profileName: profile.profileName } };
    } catch (e) {
      return { ok: false, error: toError(e) };
    }
  });
}
