/**
 * Unit-aware CSV export of a calculation result.
 *
 * Every quantity column header names its unit explicitly, e.g.
 * "requiredQty (kg)". The profile's mass unit is passed in by the caller
 * (the main process knows it); volume quantities use the request's volume
 * unit. A trailing disclaimer block states the estimate-only nature of the
 * numbers and the nominal-only status of mix IDs.
 */

import { roundDisplay } from './units.js';
import type { CalculationResult } from './types.js';

function csvCell(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function csvRow(cells: (string | number)[]): string {
  return cells.map((c) => csvCell(String(c))).join(',');
}

/**
 * @param result  the calculation result
 * @param massUnit the profile's mass unit (e.g. 'kg'), used for mass-basis rows
 */
export function calculationToCsv(result: CalculationResult, massUnit: string): string {
  const lines: string[] = [];
  lines.push(csvRow(['Volumetric Concrete Mix Calculator — calculation export']));
  lines.push(csvRow(['profile', result.profileName]));
  lines.push(csvRow(['mixDesignId (nominal only — not a structural performance claim)', result.mixDesignId]));
  lines.push(csvRow([`target volume (${result.volumeUnit})`, result.volume]));
  lines.push(csvRow(['waste allowance (%)', result.wasteAllowancePct]));
  lines.push(csvRow(['total volume incl. waste (m3)', roundDisplay(result.totalVolumeM3, 3)]));
  lines.push(csvRow(['total material mass, mass-basis materials (kg)', roundDisplay(result.totalMassKg, 2)]));
  lines.push(csvRow(['calculated at (UTC)', result.calculatedAt]));
  lines.push('');

  lines.push(
    csvRow([
      'materialId',
      'kind',
      'basis',
      'theoreticalQty',
      'requiredQty (incl. waste)',
      'qtyUnit',
      'gateSettingNeeded (gate units)',
      'measuredOutputPerUnit',
      'remainingStock',
      'stockUnit',
      'shortfall',
      'lowStock',
    ]),
  );
  for (const m of result.materials) {
    const qtyUnit = m.basis === 'mass' ? massUnit : result.volumeUnit;
    lines.push(
      csvRow([
        m.materialId,
        m.kind,
        m.basis,
        roundDisplay(m.theoreticalQty, 3),
        roundDisplay(m.requiredQty, 3),
        qtyUnit,
        Number.isFinite(m.gateSettingNeeded) ? roundDisplay(m.gateSettingNeeded, 3) : 'n/a (no calibration)',
        Number.isFinite(m.calibrationUsed.measuredOutputPerUnit)
          ? roundDisplay(m.calibrationUsed.measuredOutputPerUnit, 4)
          : 'n/a',
        m.remainingStock === undefined
          ? 'n/a (no starting stock)'
          : roundDisplay(m.remainingStock, 3),
        qtyUnit,
        m.shortfall ? 'YES' : 'no',
        m.lowStock ? 'YES' : 'no',
      ]),
    );
  }
  lines.push('');

  lines.push(csvRow(['warnings']));
  if (result.warnings.length === 0) {
    lines.push(csvRow(['none']));
  } else {
    lines.push(csvRow(['code', 'message', 'estimateOnly']));
    for (const w of result.warnings) {
      lines.push(csvRow([w.code, w.message, w.estimateOnly ? 'yes' : 'no']));
    }
  }
  lines.push('');

  if (result.yieldComparison) {
    lines.push(csvRow(['yield comparison']));
    lines.push(csvRow(['theoretical volume (m3)', roundDisplay(result.yieldComparison.theoreticalVolumeM3, 3)]));
    lines.push(csvRow(['measured volume (m3)', roundDisplay(result.yieldComparison.measuredVolumeM3, 3)]));
    lines.push(csvRow(['variance (%)', roundDisplay(result.yieldComparison.varianceFraction * 100, 2)]));
    lines.push('');
  }

  lines.push(csvRow(['assumptions / disclaimers']));
  for (const a of result.assumptions) {
    lines.push(csvRow([a]));
  }
  lines.push(
    csvRow([
      'DISCLAIMER: All quantities are estimates. Mix design IDs are nominal identifiers only and are never verified structural performance claims. Truck capacity/payload comparisons are estimates against operator-entered values — never a legal payload determination or code-compliance claim.',
    ]),
  );

  return lines.join('\r\n') + '\r\n';
}
