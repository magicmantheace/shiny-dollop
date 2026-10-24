/**
 * Database record access. All writes go through explicit transactions
 * (BEGIN IMMEDIATE / COMMIT / ROLLBACK). This module takes an already-open
 * DatabaseSync handle and never imports 'electron', so backend tests can
 * drive it against an in-memory database.
 */
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type {
  DebtRecord,
  IncomeFrequency,
  IncomeRecord,
} from '../shared/types';
import type { DebtUpsertInput, IncomeUpsertInput } from '../shared/schemas';

/**
 * Nesting depth per database handle. Outer level uses explicit
 * BEGIN IMMEDIATE / COMMIT / ROLLBACK; nested levels use SAVEPOINT so
 * composable helpers (upsert/delete call withTransaction internally) can be
 * wrapped in a larger transaction safely.
 */
const txDepth = new WeakMap<DatabaseSync, number>();

/** Run fn inside an explicit transaction; roll back on any error. */
export function withTransaction<T>(db: DatabaseSync, fn: () => T): T {
  const depth = txDepth.get(db) ?? 0;
  const savepoint = `fs_tx_${depth}`;
  if (depth === 0) {
    db.exec('BEGIN IMMEDIATE;');
  } else {
    db.exec(`SAVEPOINT ${savepoint};`);
  }
  txDepth.set(db, depth + 1);
  try {
    const result = fn();
    if (depth === 0) {
      db.exec('COMMIT;');
    } else {
      db.exec(`RELEASE ${savepoint};`);
    }
    txDepth.set(db, depth);
    return result;
  } catch (err) {
    try {
      if (depth === 0) {
        db.exec('ROLLBACK;');
      } else {
        db.exec(`ROLLBACK TO ${savepoint};`);
      }
    } catch {
      // rollback itself failing leaves nothing more we can do here
    }
    txDepth.set(db, depth);
    throw err;
  }
}

interface DebtRow {
  id: string;
  name: string;
  balance_cents: number;
  apr_percent: number;
  min_payment_cents: number;
  created_at: string;
}

interface IncomeRow {
  id: string;
  name: string;
  amount_cents: number;
  frequency: IncomeFrequency;
  created_at: string;
}

function toDebtRecord(row: DebtRow): DebtRecord {
  return {
    id: row.id,
    name: row.name,
    balanceCents: row.balance_cents,
    aprPercent: row.apr_percent,
    minPaymentCents: row.min_payment_cents,
    createdAt: row.created_at,
  };
}

function toIncomeRecord(row: IncomeRow): IncomeRecord {
  return {
    id: row.id,
    name: row.name,
    amountCents: row.amount_cents,
    frequency: row.frequency,
    createdAt: row.created_at,
  };
}

export function listDebts(db: DatabaseSync): DebtRecord[] {
  const rows = db
    .prepare('SELECT id, name, balance_cents, apr_percent, min_payment_cents, created_at FROM debts ORDER BY created_at ASC, id ASC')
    .all() as unknown as DebtRow[];
  return rows.map(toDebtRecord);
}

export function getDebt(db: DatabaseSync, id: string): DebtRecord | null {
  const row = db
    .prepare('SELECT id, name, balance_cents, apr_percent, min_payment_cents, created_at FROM debts WHERE id = ?')
    .get(id) as DebtRow | undefined;
  return row ? toDebtRecord(row) : null;
}

/** Create (no id) or replace (with id) a debt. Preserves created_at on update. */
export function upsertDebt(db: DatabaseSync, input: DebtUpsertInput): DebtRecord {
  return withTransaction(db, () => {
    const id = input.id ?? randomUUID();
    const now = new Date().toISOString();
    const existing = getDebt(db, id);
    db.prepare(
      `INSERT INTO debts (id, name, balance_cents, apr_percent, min_payment_cents, created_at)
       VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         name = excluded.name,
         balance_cents = excluded.balance_cents,
         apr_percent = excluded.apr_percent,
         min_payment_cents = excluded.min_payment_cents`,
    ).run(id, input.name, input.balanceCents, input.aprPercent, input.minPaymentCents, existing?.createdAt ?? now);
    const saved = getDebt(db, id);
    if (!saved) throw new Error(`Failed to persist debt ${id}.`);
    return saved;
  });
}

/** Delete a debt; throws if the id does not exist. */
export function deleteDebt(db: DatabaseSync, id: string): { ok: true } {
  return withTransaction(db, () => {
    const result = db.prepare('DELETE FROM debts WHERE id = ?').run(id);
    if (result.changes === 0) {
      throw new Error(`No debt with id ${id}.`);
    }
    return { ok: true };
  });
}

export function listIncomeSources(db: DatabaseSync): IncomeRecord[] {
  const rows = db
    .prepare('SELECT id, name, amount_cents, frequency, created_at FROM income_sources ORDER BY created_at ASC, id ASC')
    .all() as unknown as IncomeRow[];
  return rows.map(toIncomeRecord);
}

export function getIncomeSource(db: DatabaseSync, id: string): IncomeRecord | null {
  const row = db
    .prepare('SELECT id, name, amount_cents, frequency, created_at FROM income_sources WHERE id = ?')
    .get(id) as IncomeRow | undefined;
  return row ? toIncomeRecord(row) : null;
}

export function upsertIncomeSource(db: DatabaseSync, input: IncomeUpsertInput): IncomeRecord {
  return withTransaction(db, () => {
    const id = input.id ?? randomUUID();
    const now = new Date().toISOString();
    const existing = getIncomeSource(db, id);
    db.prepare(
      `INSERT INTO income_sources (id, name, amount_cents, frequency, created_at)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         name = excluded.name,
         amount_cents = excluded.amount_cents,
         frequency = excluded.frequency`,
    ).run(id, input.name, input.amountCents, input.frequency, existing?.createdAt ?? now);
    const saved = getIncomeSource(db, id);
    if (!saved) throw new Error(`Failed to persist income source ${id}.`);
    return saved;
  });
}

/** Delete an income source; throws if the id does not exist. */
export function deleteIncomeSource(db: DatabaseSync, id: string): { ok: true } {
  return withTransaction(db, () => {
    const result = db.prepare('DELETE FROM income_sources WHERE id = ?').run(id);
    if (result.changes === 0) {
      throw new Error(`No income source with id ${id}.`);
    }
    return { ok: true };
  });
}
