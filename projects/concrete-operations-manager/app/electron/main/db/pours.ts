/**
 * Pours. quotedLiters is the ESTIMATE; deliveredLiters is the
 * calibrated/measured volume set when the pour is finalized. They are
 * separate fields and are never conflated.
 */
import type { DatabaseSync } from 'node:sqlite';
import type { Pour } from '../../../shared/types';
import type { PourAddInput } from '../../../shared/schemas';
import { getJob } from './jobs';
import { OpsError, OpsErrorCodes } from '../errors';
import { writeAudit } from './audit';

function mapPour(row: Record<string, unknown>): Pour {
  return {
    id: row['id'] as number,
    jobId: row['job_id'] as number,
    mixDesignId: row['mix_design_id'] as string,
    quotedLiters: row['quoted_liters'] as number,
    deliveredLiters: row['delivered_liters'] as number | null,
    createdAt: row['created_at'] as string,
  };
}

export function listPoursByJob(db: DatabaseSync, jobId: number): Pour[] {
  const rows = db.prepare('SELECT * FROM pours WHERE job_id = ? ORDER BY id').all(jobId) as Record<
    string,
    unknown
  >[];
  return rows.map(mapPour);
}

export function getPour(db: DatabaseSync, id: number): Pour | null {
  const row = db.prepare('SELECT * FROM pours WHERE id = ?').get(id) as
    | Record<string, unknown>
    | undefined;
  return row ? mapPour(row) : null;
}

export function addPour(db: DatabaseSync, input: PourAddInput): Pour {
  if (!getJob(db, input.jobId)) {
    throw new OpsError(OpsErrorCodes.NOT_FOUND, `Job #${input.jobId} does not exist.`);
  }
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO pours (job_id, mix_design_id, quoted_liters, delivered_liters, created_at)
       VALUES (?, ?, ?, NULL, ?)`,
    )
    .run(input.jobId, input.mixDesignId, input.quotedLiters, now);
  const id = Number(result.lastInsertRowid);
  const pour = getPour(db, id) as Pour;
  writeAudit(db, { entityType: 'pour', entityId: id, action: 'created', after: pour });
  return pour;
}

export function updatePour(
  db: DatabaseSync,
  id: number,
  patch: { mixDesignId?: string; quotedLiters?: number },
): Pour | null {
  const before = getPour(db, id);
  if (!before) return null;
  db.prepare(
    `UPDATE pours SET
       mix_design_id = COALESCE(?, mix_design_id),
       quoted_liters = COALESCE(?, quoted_liters)
     WHERE id = ?`,
  ).run(patch.mixDesignId ?? null, patch.quotedLiters ?? null, id);
  const after = getPour(db, id) as Pour;
  writeAudit(db, { entityType: 'pour', entityId: id, action: 'estimate_updated', before, after });
  return after;
}

/** Record the measured volume for a pour. Audited; revision writes a new row. */
export function setDeliveredLiters(db: DatabaseSync, id: number, deliveredLiters: number): Pour | null {
  const before = getPour(db, id);
  if (!before) return null;
  db.prepare('UPDATE pours SET delivered_liters = ? WHERE id = ?').run(deliveredLiters, id);
  const after = getPour(db, id) as Pour;
  writeAudit(db, {
    entityType: 'pour',
    entityId: id,
    action: before.deliveredLiters === null ? 'delivered_finalized' : 'delivered_revised',
    before: { deliveredLiters: before.deliveredLiters },
    after: { deliveredLiters: after.deliveredLiters },
  });
  return after;
}

export function removePour(db: DatabaseSync, id: number): boolean {
  const pour = getPour(db, id);
  if (!pour) return false;
  db.prepare('DELETE FROM pours WHERE id = ?').run(id);
  writeAudit(db, { entityType: 'pour', entityId: id, action: 'deleted', before: pour });
  return true;
}
