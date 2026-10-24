/** Epic Games source adapter — public surface. */
export { EpicAdapter, EPIC_LAUNCHER_URI, createEpicScanController } from './adapter';
export type {
  DiscoveredGame,
  LaunchValidation,
  ProbeResult,
  ScanController,
  ScanResult,
  ScanStatus,
} from './adapter';
export { EpicFsError, RealEpicOs, joinFor, manifestDirFor } from './os';
export type { EpicOs } from './os';
export { lastScan, recordScan, syncEpicGames } from './sync';
export type { EpicSyncResult } from './sync';
