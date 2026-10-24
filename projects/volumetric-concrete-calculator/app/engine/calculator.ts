/**
 * Core calculation engine: calibrated volumetric material quantities.
 *
 * Pure functions, no I/O. All math in base units (m³, kg); inputs in the
 * profile/request units are converted on entry and converted back on exit.
 * Nothing here asserts structural strength, code compliance, legal payload,
 * or tested mix adequacy — truck-limit outputs are warnings labelled
 * estimate-only, and mix IDs are nominal only.
 */

import {
  MASS_TO_KG,
  VOLUME_TO_M3,
  isMassUnit,
  isVolumeUnit,
  massFromKg,
  massToKg,
  volumeFromM3,
  volumeToM3,
} from './units.js';
import { materialBasis, MATERIAL_KINDS } from './types.js';
import type {
  CalculationRequest,
  CalculationResult,
  CalculationWarning,
  CalibrationProfile,
  CalibrationRow,
  Material,
  MaterialResult,
} from './types.js';

export class CalculationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CalculationError';
  }
}

function fail(message: string): never {
  throw new CalculationError(message);
}

function requireFinite(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    fail(`${label} must be a finite number.`);
  }
  return value;
}

function materialLabel(m: Material): string {
  return m.description ? `${m.materialId} (${m.description})` : m.materialId;
}

/** Validate a calibration profile's shape before any calculation. */
export function validateProfile(profile: CalibrationProfile): void {
  if (!profile || typeof profile !== 'object') fail('Profile must be an object.');
  if (typeof profile.profileName !== 'string' || profile.profileName.trim().length === 0) {
    fail('Profile must have a non-empty profileName.');
  }
  const units = profile.units;
  if (!units || !isVolumeUnit(units.volume) || !isMassUnit(units.mass)) {
    fail('Profile units must declare a valid volume unit (m3|L|yd3) and mass unit (kg|t|lb).');
  }
  if (!Array.isArray(profile.materials) || profile.materials.length === 0) {
    fail('Profile must declare at least one material.');
  }
  const seen = new Set<string>();
  for (const m of profile.materials) {
    if (typeof m.materialId !== 'string' || m.materialId.length === 0 || m.materialId.length > 100) {
      fail('Each material needs a materialId of 1–100 characters.');
    }
    if (seen.has(m.materialId)) fail(`Duplicate materialId "${m.materialId}".`);
    seen.add(m.materialId);
    if (!(MATERIAL_KINDS as readonly string[]).includes(m.kind)) {
      fail(`Material "${m.materialId}" has unknown kind "${String(m.kind)}".`);
    }
  }
  const byId = new Map(profile.materials.map((m) => [m.materialId, m]));
  if (!Array.isArray(profile.calibrations)) fail('Profile calibrations must be an array.');
  for (const c of profile.calibrations) {
    if (!byId.has(c.materialId)) {
      fail(`Calibration references undeclared materialId "${c.materialId}".`);
    }
    requireFinite(c.gateSetting, `Gate setting for "${c.materialId}"`);
    if (c.gateSetting <= 0) fail(`Gate setting for "${c.materialId}" must be > 0.`);
    requireFinite(c.measuredOutputPerUnit, `Measured output per unit for "${c.materialId}"`);
    if (c.measuredOutputPerUnit <= 0) {
      fail(`Measured output per unit for "${c.materialId}" must be > 0 (got ${c.measuredOutputPerUnit}).`);
    }
  }
  if (!Array.isArray(profile.mixes)) fail('Profile mixes must be an array.');
  for (const mix of profile.mixes) {
    if (typeof mix.mixDesignId !== 'string' || mix.mixDesignId.length === 0) {
      fail('Each mix design needs a non-empty mixDesignId.');
    }
    if (mix.nominalOnly !== true) {
      fail(`Mix "${mix.mixDesignId}": nominalOnly must be true — mix IDs are nominal identifiers only, never structural performance claims.`);
    }
    if (!Array.isArray(mix.components) || mix.components.length === 0) {
      fail(`Mix "${mix.mixDesignId}" must have at least one component.`);
    }
    for (const comp of mix.components) {
      if (!byId.has(comp.materialId)) {
        fail(`Mix "${mix.mixDesignId}" references undeclared materialId "${comp.materialId}".`);
      }
      requireFinite(comp.targetPerM3, `targetPerM3 for "${comp.materialId}"`);
      if (comp.targetPerM3 < 0) {
        fail(`targetPerM3 for "${comp.materialId}" must be >= 0.`);
      }
    }
  }
}

export function calculate(req: CalculationRequest): CalculationResult {
  validateProfile(req.profile);
  const { profile } = req;
  const units = profile.units;

  const volume = requireFinite(req.volume, 'Target volume');
  if (volume <= 0) fail('Target volume must be > 0.');
  if (volumeToM3(volume, req.volumeUnit) > 1_000_000) {
    fail('Target volume is implausibly large (> 1,000,000 m³). Check the volume unit.');
  }
  const waste = requireFinite(req.wasteAllowancePct, 'Waste allowance');
  if (waste < 0 || waste > 100) fail('Waste allowance must be between 0 and 100 percent.');

  const mix = profile.mixes.find((m) => m.mixDesignId === req.mixDesignId);
  if (!mix) fail(`Mix design "${req.mixDesignId}" not found in profile "${profile.profileName}".`);

  const volumeM3 = volumeToM3(volume, req.volumeUnit);
  const wasteFactor = 1 + waste / 100;

  const materialById = new Map(profile.materials.map((m) => [m.materialId, m]));
  // Latest calibration row per material wins (array order = entry order).
  const calibrationById = new Map<string, CalibrationRow>();
  for (const c of profile.calibrations) calibrationById.set(c.materialId, c);

  const warnings: CalculationWarning[] = [];
  const assumptions: string[] = [
    `Quantities are estimates derived from gate calibrations in profile "${profile.profileName}".`,
    'Mix design IDs are nominal identifiers only — never a verified structural performance claim.',
    'Gate calibration assumes linear output per gate unit across the operating range.',
  ];
  if (waste > 0) assumptions.push(`A ${waste}% waste/overage allowance is included in required quantities.`);

  const materials: MaterialResult[] = [];
  let totalMassKg = 0;

  for (const comp of mix.components) {
    const material = materialById.get(comp.materialId)!;
    const basis = materialBasis(material.kind);
    const calibration = calibrationById.get(comp.materialId);
    if (!calibration) {
      warnings.push({
        code: 'NO_CALIBRATION',
        message: `${materialLabel(material)} has no gate calibration — it is listed with required quantity but no gate setting could be computed.`,
        estimateOnly: true,
      });
    }

    // targetPerM3 is per cubic metre of concrete, in profile mass/volume units.
    const targetPerM3 = comp.targetPerM3;
    const theoreticalQty = targetPerM3 * volumeM3;
    const requiredQty = theoreticalQty * wasteFactor;
    const gateSettingNeeded =
      calibration && calibration.measuredOutputPerUnit > 0
        ? requiredQty / calibration.measuredOutputPerUnit
        : NaN;

    if (basis === 'mass') {
      totalMassKg += massToKg(requiredQty, units.mass);
    }

    let remainingStock: number | undefined;
    let shortfall = false;
    let lowStock = false;
    if (req.startingStock && req.startingStock[comp.materialId] !== undefined) {
      const stock = requireFinite(req.startingStock[comp.materialId], `Starting stock for "${comp.materialId}"`);
      if (stock < 0) fail(`Starting stock for "${comp.materialId}" must be >= 0.`);
      remainingStock = stock - requiredQty;
      shortfall = requiredQty > stock;
      if (shortfall) {
        warnings.push({
          code: 'STOCK_SHORTFALL',
          message: `${materialLabel(material)}: required ${requiredQty.toFixed(2)} ${units[basis]} exceeds starting stock ${stock.toFixed(2)} ${units[basis]} (shortfall ${(requiredQty - stock).toFixed(2)} ${units[basis]}). Estimate — verify stock before loading.`,
          estimateOnly: true,
        });
      }
      const threshold = req.lowStockThresholds?.[comp.materialId];
      if (threshold !== undefined) {
        requireFinite(threshold, `Low-stock threshold for "${comp.materialId}"`);
        if (remainingStock < threshold && !shortfall) {
          lowStock = true;
          warnings.push({
            code: 'LOW_STOCK',
            message: `${materialLabel(material)}: remaining stock ${remainingStock.toFixed(2)} ${units[basis]} is below the ${threshold.toFixed(2)} ${units[basis]} threshold.`,
            estimateOnly: true,
          });
        }
      }
    }

    materials.push({
      materialId: comp.materialId,
      kind: material.kind,
      description: material.description,
      basis,
      theoreticalQty,
      requiredQty,
      gateSettingNeeded,
      calibrationUsed: calibration ?? {
        materialId: comp.materialId,
        gateSetting: NaN,
        measuredOutputPerUnit: NaN,
      },
      remainingStock,
      shortfall,
      lowStock,
    });
  }

  // Truck constraint warnings — estimates only, never compliance claims.
  const totalVolumeM3 = volumeM3 * wasteFactor;
  if (req.truckLimits?.maxVolume !== undefined) {
    const maxV = requireFinite(req.truckLimits.maxVolume, 'Truck max volume');
    if (maxV <= 0) fail('Truck max volume must be > 0.');
    const maxVM3 = volumeToM3(maxV, units.volume);
    if (totalVolumeM3 > maxVM3) {
      warnings.push({
        code: 'VOLUME_CAPACITY',
        message: `Requested ${volumeFromM3(totalVolumeM3, units.volume).toFixed(2)} ${units.volume} (incl. waste) exceeds the entered truck capacity of ${maxV.toFixed(2)} ${units.volume}. Estimate only — verify against the truck's rated capacity.`,
        estimateOnly: true,
      });
    }
    assumptions.push('Truck capacity comparison is an estimate against an operator-entered value, not a rated-capacity claim.');
  }
  if (req.truckLimits?.maxPayloadMass !== undefined) {
    const maxP = requireFinite(req.truckLimits.maxPayloadMass, 'Truck max payload');
    if (maxP <= 0) fail('Truck max payload must be > 0.');
    const maxPKg = massToKg(maxP, units.mass);
    if (totalMassKg > maxPKg) {
      warnings.push({
        code: 'PAYLOAD_MASS',
        message: `Estimated material mass ${massFromKg(totalMassKg, units.mass).toFixed(2)} ${units.mass} exceeds the entered payload limit of ${maxP.toFixed(2)} ${units.mass}. Estimate only — never a legal payload determination; verify against regulations and the truck's certification.`,
        estimateOnly: true,
      });
    }
    assumptions.push('Payload comparison is an estimate against an operator-entered value, never a legal payload determination.');
  }

  // Theoretical vs measured yield.
  let yieldComparison: CalculationResult['yieldComparison'];
  if (req.measuredVolumeProducedM3 !== undefined) {
    const measured = requireFinite(req.measuredVolumeProducedM3, 'Measured volume produced');
    if (measured < 0) fail('Measured volume produced must be >= 0.');
    yieldComparison = {
      theoreticalVolumeM3: volumeM3,
      measuredVolumeM3: measured,
      varianceFraction: volumeM3 === 0 ? 0 : (measured - volumeM3) / volumeM3,
    };
    assumptions.push('Yield variance compares operator-recorded produced volume against the theoretical target; it reflects measurement and process variation, not material quality.');
  }

  return {
    mixDesignId: mix.mixDesignId,
    profileName: profile.profileName,
    volume,
    volumeUnit: req.volumeUnit,
    wasteAllowancePct: waste,
    totalVolumeM3,
    totalMassKg,
    materials,
    warnings,
    yieldComparison,
    assumptions,
    calculatedAt: new Date().toISOString(),
  };
}

/** Re-export unit helpers used by the exchange/CSV modules. */
export { MASS_TO_KG, VOLUME_TO_M3 };
