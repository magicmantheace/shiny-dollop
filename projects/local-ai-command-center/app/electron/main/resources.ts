import * as os from 'node:os';
import type { ResourceSnapshot } from '../../shared/types.js';

export interface OsLayer {
  cpus(): { model: string }[];
  totalmem(): number;
  freemem(): number;
  loadavg(): number[];
}
export class NodeOsLayer implements OsLayer {
  cpus(): { model: string }[] { return os.cpus(); }
  totalmem(): number { return os.totalmem(); }
  freemem(): number { return os.freemem(); }
  loadavg(): number[] { return os.loadavg(); }
}
export function snapshotResources(osLayer: OsLayer = new NodeOsLayer()): ResourceSnapshot {
  const cpus = osLayer.cpus();
  const load = osLayer.loadavg();
  const raw = load.length > 0 ? load[0] : undefined;
  const loadAvg1m = raw === undefined || raw === 0 ? null : raw;
  return {
    cpuCount: cpus.length,
    cpuModel: cpus[0]?.model ?? 'Unknown',
    loadAvg1m,
    totalMemBytes: osLayer.totalmem(),
    freeMemBytes: osLayer.freemem(),
    gpu: { status: 'unavailable', reason: 'GPU detection is not implemented in the MVP; no GPU figures are reported rather than estimated.' },
    sampledAt: new Date().toISOString(),
  };
}
