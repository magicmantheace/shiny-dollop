/**
 * Internal domain types for the Volumetric Concrete Mix Calculator.
 *
 * A calibration profile describes one truck (or plant): the materials it
 * carries, each material's gate calibration (measured output per gate unit),
 * and the mix designs built on top of them.
 *
 * Mix design IDs are NOMINAL ONLY (e.g. "C25/30"). A mix ID is never a
 * verified structural performance claim — see the calibration exchange
 * contract (docs/CALIBRATION_EXCHANGE_FORMAT.md).
 */

import type { MassUnit, VolumeUnit } from './units.js';

export type MaterialKind =
  | 'cement'
  | 'sand'
  | 'gravel'
  | 'water'
  | 'admixture'
  | 'other';

export const MATERIAL_KINDS: readonly MaterialKind[] = [
  'cement',
  'sand',
  'gravel',
  'water',
  'admixture',
  'other',
];

/**
 * Whether a material is measured by mass or by volume.
 * Convention (documented, owned by this calculator):
 * water and admixture are volume-basis; everything else is mass-basis.
 * This determines which envelope unit (mass vs volume) a calibration's
 * measuredOutputPerUnit is expressed in when exporting the v1.0.0
 * calibration exchange envelope.
 */
export function materialBasis(kind: MaterialKind): 'mass' | 'volume' {
  return kind === 'water' || kind === 'admixture' ? 'volume' : 'mass';
}

export interface Material {
  materialId: string;
  kind: MaterialKind;
  description?: string;
}

export interface CalibrationRow {
  materialId: string;
  /** Calculator's own dial/position unit (opaque number), must be > 0. */
  gateSetting: number;
  /**
   * Measured output per gate unit, in the profile's mass unit (mass-basis
   * materials) or volume unit (volume-basis materials). Must be > 0.
   */
  measuredOutputPerUnit: number;
  /** ISO date or free-text note describing when/how the measurement was taken. */
  measuredAt?: string;
  /** Free-text note recording the measurement source (scale ticket, test pour, …). */
  source?: string;
}

export interface MixComponent {
  materialId: string;
  /**
   * Target quantity of this material per cubic metre of concrete,
   * in the profile's mass unit (mass-basis) or volume unit (volume-basis).
   * Must be >= 0.
   */
  targetPerM3: number;
}

export interface MixDesign {
  mixDesignId: string;
  note?: string;
  /** Always true: mix IDs are nominal identifiers, never performance claims. */
  nominalOnly: true;
  components: MixComponent[];
}

export interface ProfileUnits {
  volume: VolumeUnit;
  mass: MassUnit;
}

export interface CalibrationProfile {
  profileName: string;
  units: ProfileUnits;
  materials: Material[];
  calibrations: CalibrationRow[];
  mixes: MixDesign[];
}

/** Per-material stock on the truck / in the silo, in profile units. */
export interface StockLevels {
  [materialId: string]: number;
}

export interface TruckLimits {
  /** Maximum concrete volume the truck can carry/produce, in profile volume units. */
  maxVolume?: number;
  /** Maximum payload mass, in profile mass units. Estimate only — never a legal claim. */
  maxPayloadMass?: number;
}

export interface CalculationRequest {
  profile: CalibrationProfile;
  mixDesignId: string;
  /** Target concrete volume, in the request's volume unit. */
  volume: number;
  volumeUnit: VolumeUnit;
  /** Waste/overage allowance, percent, 0–100. */
  wasteAllowancePct: number;
  /** Optional starting stock per material, in profile units. */
  startingStock?: StockLevels;
  /** Optional low-stock warning threshold per material, in profile units. */
  lowStockThresholds?: StockLevels;
  /** Optional truck constraint inputs. Warnings only. */
  truckLimits?: TruckLimits;
  /**
   * Optional measured concrete volume actually produced (m³), recorded after
   * the pour. Used for theoretical-vs-measured yield comparison.
   */
  measuredVolumeProducedM3?: number;
}

export interface MaterialResult {
  materialId: string;
  kind: MaterialKind;
  description?: string;
  basis: 'mass' | 'volume';
  /** Theoretical quantity for the target volume (no waste), profile units. */
  theoreticalQty: number;
  /** Required quantity incl. waste allowance, profile units. */
  requiredQty: number;
  /** Gate setting needed to deliver requiredQty, in gate units. */
  gateSettingNeeded: number;
  /** The calibration row used, for traceability. */
  calibrationUsed: CalibrationRow;
  /** Remaining stock after this batch, if starting stock was given. */
  remainingStock?: number;
  /** True when requiredQty exceeds the given starting stock. */
  shortfall: boolean;
  /** True when remaining stock is below the low-stock threshold. */
  lowStock: boolean;
}

export interface CalculationWarning {
  code:
    | 'STOCK_SHORTFALL'
    | 'LOW_STOCK'
    | 'VOLUME_CAPACITY'
    | 'PAYLOAD_MASS'
    | 'NO_CALIBRATION'
    | 'IMPLAUSIBLE_INPUT';
  message: string;
  /** Always true for truck-limit warnings: estimates, not compliance claims. */
  estimateOnly: boolean;
}

export interface CalculationResult {
  mixDesignId: string;
  profileName: string;
  /** Target volume echoed back, in the request's volume unit. */
  volume: number;
  volumeUnit: VolumeUnit;
  wasteAllowancePct: number;
  /** Total concrete volume incl. waste, m³. */
  totalVolumeM3: number;
  /** Total material mass (mass-basis materials only), kg. */
  totalMassKg: number;
  materials: MaterialResult[];
  warnings: CalculationWarning[];
  /** Theoretical vs measured yield comparison, when measured volume was given. */
  yieldComparison?: {
    theoreticalVolumeM3: number;
    measuredVolumeM3: number;
    /** (measured - theoretical) / theoretical, as a fraction. */
    varianceFraction: number;
  };
  /** Assumptions baked into this result — always surfaced to the user. */
  assumptions: string[];
  calculatedAt: string;
}
