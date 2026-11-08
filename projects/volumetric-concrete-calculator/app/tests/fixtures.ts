/**
 * Shared synthetic fixture: a volumetric truck calibration profile.
 * Entirely invented data — no real customer, plant, or mix information.
 */
import type { CalibrationProfile } from '../engine/types.js';

export function fixtureProfile(): CalibrationProfile {
  return {
    profileName: 'Test Truck 7',
    units: { volume: 'm3', mass: 'kg' },
    materials: [
      { materialId: 'cement', kind: 'cement', description: 'General purpose cement' },
      { materialId: 'sand', kind: 'sand', description: 'Washed concrete sand' },
      { materialId: 'stone', kind: 'gravel', description: '20mm crushed stone' },
      { materialId: 'water', kind: 'water', description: 'Batch water' },
      { materialId: 'admix', kind: 'admixture', description: 'Plasticiser' },
    ],
    calibrations: [
      // measuredOutputPerUnit: kg per gate unit (mass basis), L per gate unit (volume basis)
      { materialId: 'cement', gateSetting: 40, measuredOutputPerUnit: 8.0, measuredAt: '2026-10-01', source: 'scale ticket #1042' },
      { materialId: 'sand', gateSetting: 55, measuredOutputPerUnit: 22.5, measuredAt: '2026-10-01', source: 'scale ticket #1042' },
      { materialId: 'stone', gateSetting: 60, measuredOutputPerUnit: 25.0, measuredAt: '2026-10-01', source: 'scale ticket #1043' },
      { materialId: 'water', gateSetting: 30, measuredOutputPerUnit: 5.0, measuredAt: '2026-10-02', source: 'flow meter test' },
      { materialId: 'admix', gateSetting: 10, measuredOutputPerUnit: 0.5, measuredAt: '2026-10-02', source: 'dispenser calibration' },
    ],
    mixes: [
      {
        // Nominal ID only — never a structural performance claim.
        mixDesignId: 'NOM-25',
        note: 'Nominal 25 MPa-class test mix (nominal ID only)',
        nominalOnly: true,
        components: [
          { materialId: 'cement', targetPerM3: 320 },
          { materialId: 'sand', targetPerM3: 800 },
          { materialId: 'stone', targetPerM3: 1050 },
          { materialId: 'water', targetPerM3: 165 },
          { materialId: 'admix', targetPerM3: 1.2 },
        ],
      },
    ],
  };
}
