import { describe, expect, it } from 'vitest';
import { snapshotResources, type OsLayer } from '../../electron/main/resources.js';

describe('resources', () => {
  it('fake OsLayer maps correctly, gpu unavailable, load 0 -> null', () => {
    const fake: OsLayer = {
      cpus: () => [{ model: 'Fake CPU 3000' }, { model: 'Fake CPU 3000' }],
      totalmem: () => 16000,
      freemem: () => 4000,
      loadavg: () => [0, 0, 0],
    };
    const snap = snapshotResources(fake);
    expect(snap.cpuCount).toBe(2);
    expect(snap.cpuModel).toBe('Fake CPU 3000');
    expect(snap.totalMemBytes).toBe(16000);
    expect(snap.freeMemBytes).toBe(4000);
    expect(snap.gpu.status).toBe('unavailable');
    expect(snap.gpu.reason.length).toBeGreaterThan(0);
    expect(snap.loadAvg1m).toBeNull();
  });
  it('non-zero load maps', () => {
    const fake: OsLayer = { cpus: () => [{ model: 'X' }], totalmem: () => 100, freemem: () => 50, loadavg: () => [1.5, 0, 0] };
    expect(snapshotResources(fake).loadAvg1m).toBe(1.5);
  });
});
