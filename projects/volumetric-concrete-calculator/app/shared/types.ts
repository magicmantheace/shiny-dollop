/**
 * Shared types between the Electron main process and the renderer.
 * The calculation engine types are re-exported for the UI.
 */
export type {
  CalibrationProfile,
  CalibrationRow,
  CalculationRequest,
  CalculationResult,
  CalculationWarning,
  Material,
  MaterialKind,
  MaterialResult,
  MixComponent,
  MixDesign,
  ProfileUnits,
  StockLevels,
  TruckLimits,
} from '../engine/types.js';
export type { MassUnit, VolumeUnit } from '../engine/units.js';
export type { ExchangeEnvelope } from '../engine/exchange.js';

export interface ProfileSummary {
  id: number;
  profileName: string;
  volumeUnit: string;
  massUnit: string;
  materialCount: number;
  mixCount: number;
  updatedAt: string;
}

export interface CalculationRecord {
  id: number;
  profileId: number;
  profileName: string;
  mixDesignId: string;
  volume: number;
  volumeUnit: string;
  wasteAllowancePct: number;
  resultJson: string;
  createdAt: string;
}

export interface ApiError {
  code: string;
  message: string;
}
