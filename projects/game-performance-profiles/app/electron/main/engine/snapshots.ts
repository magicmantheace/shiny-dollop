/**
 * takeSnapshot — point-in-time resource observation persisted to the DB.
 * Every snapshot carries the exact note "approximate — point-in-time
 * estimate, not a benchmark".
 */

import { SNAPSHOT_NOTE, type ResourceSnapshot } from '../../../shared/gpp-types.js';
import { GppDatabase } from '../store/database.js';
import { OsLayer } from '../os-layer/types.js';

export async function takeSnapshot(label: string, os: OsLayer, db: GppDatabase): Promise<ResourceSnapshot> {
  const { cpuPercent, memoryMb } = await os.takeSnapshot();
  return db.addSnapshot({ label, cpuPercent, memoryMb, note: SNAPSHOT_NOTE });
}
