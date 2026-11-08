/**
 * takeSnapshot — point-in-time resource observation persisted to the DB.
 * Every snapshot carries the exact note "approximate — point-in-time
 * estimate, not a benchmark".
 */

import { SNAPSHOT_NOTE, type ResourceSnapshot } from '../../../shared/gpp-types.js';
import { GppDatabase } from '../store/database.js';
import { OsLayer, OsLayerError } from '../os-layer/types.js';

export async function takeSnapshot(label: string, os: OsLayer, db: GppDatabase): Promise<ResourceSnapshot> {
  const { cpuPercent, memoryMb } = await os.takeSnapshot();
  // A failed collection must never be persisted as a measurement: reject
  // non-finite or negative values (e.g. sentinel placeholders from a layer
  // whose counters were unavailable) instead of storing them, where the
  // UI would display and compare them as ordinary data.
  if (!Number.isFinite(cpuPercent) || !Number.isFinite(memoryMb) || cpuPercent < 0 || memoryMb < 0) {
    throw new OsLayerError(
      'os-error',
      `Snapshot collection failed: the OS layer returned invalid measurements (cpuPercent=${cpuPercent}, memoryMb=${memoryMb}). No snapshot was recorded.`,
    );
  }
  return db.addSnapshot({ label, cpuPercent, memoryMb, note: SNAPSHOT_NOTE });
}
