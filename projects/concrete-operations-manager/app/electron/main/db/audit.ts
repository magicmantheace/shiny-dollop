/**
 * Audit trail. Every override/adjustment and every state transition writes
 * a row recording who did what, when, and before → after.
 */
import type { DatabaseSync } from 'node:sqlite';
import type { AuditEntry } from '../../../shared/types';

export const ACTOR_LOCAL = 'local-user';

export function writeAudit(
  db: DatabaseSync,
  entry: {
    entityType: string;
    entityId: number;
    action: string;
    before?: unknown;
    after?: unknown;
    actor?: string;
  },
): AuditEntry {
  const createdAt = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO audit_trail (entity_type, entity_id, action, actor, before_json, after_json, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
    )
    .run(
      entry.entityType,
      entry.entityId,
      entry.action,
      entry.actor ?? ACTOR_LOCAL,
      entry.before === undefined ? null : JSON.stringify(entry.before),
      entry.after === undefined ? null : JSON.stringify(entry.after),
      createdAt,
    );
  return getAuditEntry(db, Number(result.lastInsertRowid)) as AuditEntry;
}

export function getAuditEntry(db: DatabaseSync, id: number): AuditEntry | null {
  const row = db.prepare('SELECT * FROM audit_trail WHERE id = ?').get(id) as Record<string, unknown> | undefined;
  return row ? mapAudit(row) : null;
}

export function listAudit(
  db: DatabaseSync,
  opts: { entityType?: string | undefined; entityId?: number | undefined; limit?: number | undefined } = {},
): AuditEntry[] {
  const limit = Math.min(Math.max(opts.limit ?? 100, 1), 500);
  const clauses: string[] = [];
  const params: (string | number)[] = [];
  if (opts.entityType !== undefined) {
    clauses.push('entity_type = ?');
    params.push(opts.entityType);
  }
  if (opts.entityId !== undefined) {
    clauses.push('entity_id = ?');
    params.push(opts.entityId);
  }
  const where = clauses.length > 0 ? `WHERE ${clauses.join(' AND ')}` : '';
  const rows = db
    .prepare(`SELECT * FROM audit_trail ${where} ORDER BY id DESC LIMIT ${limit}`)
    .all(...params) as Record<string, unknown>[];
  return rows.map(mapAudit);
}

function mapAudit(row: Record<string, unknown>): AuditEntry {
  return {
    id: row['id'] as number,
    entityType: row['entity_type'] as string,
    entityId: row['entity_id'] as number,
    action: row['action'] as string,
    actor: row['actor'] as string,
    beforeJson: row['before_json'] as string | null,
    afterJson: row['after_json'] as string | null,
    createdAt: row['created_at'] as string,
  };
}
