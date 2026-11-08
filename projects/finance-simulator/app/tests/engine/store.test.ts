/**
 * Persistence tests. DatabaseSync against ':memory:' — no Electron, no files.
 * Uses synthetic data only.
 */
import { DatabaseSync } from 'node:sqlite';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { runMigrations, SCHEMA_VERSION } from '../../db/migrations';
import {
  deleteDebt,
  deleteIncomeSource,
  getDebt,
  listDebts,
  listIncomeSources,
  upsertDebt,
  upsertIncomeSource,
  withTransaction,
} from '../../db/records';

let db: DatabaseSync;

beforeEach(() => {
  db = new DatabaseSync(':memory:');
  runMigrations(db);
});

afterEach(() => {
  db.close();
});

describe('migrations', () => {
  it('records schema version 1', () => {
    expect(SCHEMA_VERSION).toBe(1);
    const rows = db.prepare('SELECT version FROM schema_version').all() as { version: number }[];
    expect(rows).toEqual([{ version: 1 }]);
  });

  it('is idempotent when run twice', () => {
    runMigrations(db);
    const rows = db.prepare('SELECT version FROM schema_version').all();
    expect(rows.length).toBe(1);
  });

  it('creates the debts and income_sources tables', () => {
    const names = db
      .prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
      .all() as { name: string }[];
    expect(names.map((n) => n.name)).toContain('debts');
    expect(names.map((n) => n.name)).toContain('income_sources');
  });
});

describe('debts', () => {
  it('creates a debt with a generated id and lists it', () => {
    const saved = upsertDebt(db, {
      name: 'Card',
      balanceCents: 500000,
      aprPercent: 19.99,
      minPaymentCents: 12500,
    });
    expect(saved.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(saved.name).toBe('Card');
    expect(saved.balanceCents).toBe(500000);
    expect(saved.aprPercent).toBe(19.99);
    expect(saved.minPaymentCents).toBe(12500);
    expect(typeof saved.createdAt).toBe('string');
    expect(listDebts(db).length).toBe(1);
  });

  it('updates a debt in place and preserves createdAt', () => {
    const created = upsertDebt(db, {
      name: 'Card',
      balanceCents: 500000,
      aprPercent: 19.99,
      minPaymentCents: 12500,
    });
    const updated = upsertDebt(db, {
      id: created.id,
      name: 'Card',
      balanceCents: 490000,
      aprPercent: 19.99,
      minPaymentCents: 12500,
    });
    expect(updated.id).toBe(created.id);
    expect(updated.balanceCents).toBe(490000);
    expect(updated.createdAt).toBe(created.createdAt);
    expect(listDebts(db).length).toBe(1);
  });

  it('getDebt returns null for an unknown id', () => {
    expect(getDebt(db, 'nope')).toBeNull();
  });

  it('deletes a debt and throws on unknown id', () => {
    const saved = upsertDebt(db, {
      name: 'Card',
      balanceCents: 500000,
      aprPercent: 19.99,
      minPaymentCents: 12500,
    });
    expect(deleteDebt(db, saved.id)).toEqual({ ok: true });
    expect(listDebts(db)).toEqual([]);
    expect(() => deleteDebt(db, saved.id)).toThrow(Error);
  });
});

describe('income sources', () => {
  it('creates, updates, lists and deletes income sources', () => {
    const created = upsertIncomeSource(db, {
      name: 'Paycheck',
      amountCents: 155751,
      frequency: 'biweekly',
    });
    expect(created.frequency).toBe('biweekly');
    const updated = upsertIncomeSource(db, {
      id: created.id,
      name: 'Paycheck',
      amountCents: 160000,
      frequency: 'biweekly',
    });
    expect(updated.amountCents).toBe(160000);
    expect(updated.createdAt).toBe(created.createdAt);
    expect(listIncomeSources(db).length).toBe(1);
    expect(deleteIncomeSource(db, created.id)).toEqual({ ok: true });
    expect(() => deleteIncomeSource(db, created.id)).toThrow(Error);
  });
});

describe('transactions', () => {
  it('rolls back the whole transaction when the callback throws', () => {
    expect(() =>
      withTransaction(db, () => {
        upsertDebt(db, {
          name: 'Card',
          balanceCents: 500000,
          aprPercent: 19.99,
          minPaymentCents: 12500,
        });
        throw new Error('boom');
      }),
    ).toThrow('boom');
    expect(listDebts(db)).toEqual([]);
  });
});
