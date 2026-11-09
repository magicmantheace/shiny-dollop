/**
 * Backup/restore and persistence across restart, using real on-disk
 * databases in a temp directory (synthetic data only).
 */
import { describe, expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { makeFileDb, cleanupDir, addTestCustomer, addTestJob, addTestPour } from '../helpers';
import { backupDatabase, restoreDatabase, validateRestoreCandidate } from '../../electron/main/backup';
import { getAppliedVersions, runMigrations } from '../../electron/main/db/migrations';
import { listCustomers } from '../../electron/main/db/customers';
import { OpsError } from '../../electron/main/errors';

describe('backup and restore', () => {
  it('backs up to a file and restores it with validation', () => {
    const { db, dbPath, dir } = makeFileDb();
    try {
      const customer = addTestCustomer(db, 'Backup Test Customer');
      const backupPath = path.join(dir, 'backup.db');
      expect(backupDatabase(db, dbPath, backupPath)).toBe(backupPath);
      expect(fs.existsSync(backupPath)).toBe(true);

      // Validation passes on the real backup.
      expect(validateRestoreCandidate(backupPath).version).toBe(1);

      db.close();
      const { rollbackPath } = restoreDatabase(dbPath, backupPath, path.join(dir, 'rollbacks'));
      expect(fs.existsSync(rollbackPath)).toBe(true);

      const reopened = new DatabaseSync(dbPath);
      try {
        expect(listCustomers(reopened).some((c) => c.id === customer.id)).toBe(true);
      } finally {
        reopened.close();
      }
    } finally {
      cleanupDir(dir);
    }
  });

  it('rejects a tampered/non-database restore candidate', () => {
    const { db, dir } = makeFileDb();
    try {
      const bad = path.join(dir, 'not-a-db.db');
      fs.writeFileSync(bad, 'this is not sqlite data');
      expect(() => validateRestoreCandidate(bad)).toThrow(OpsError);

      const empty = path.join(dir, 'empty.db');
      fs.writeFileSync(empty, '');
      expect(() => validateRestoreCandidate(empty)).toThrow(OpsError);

      expect(() => validateRestoreCandidate(path.join(dir, 'missing.db'))).toThrow(OpsError);
    } finally {
      try {
        db.close();
      } catch {
        // ignore
      }
      cleanupDir(dir);
    }
  });

  it('rejects a candidate whose schema is intact but whose data pages are damaged', () => {
    const { db, dbPath, dir } = makeFileDb();
    try {
      addTestCustomer(db, 'Corruption Test Customer');
      db.close();

      // Zero the customers table's root page. sqlite_master still lists
      // every table and schema_migrations still reports version 1, so
      // name/version checks alone would accept this file — but the
      // customer data is gone and querying it fails. Only the integrity
      // check catches this before the live DB is replaced.
      const probe = new DatabaseSync(dbPath, { readOnly: true });
      const { rootpage } = probe.prepare("SELECT rootpage FROM sqlite_master WHERE name = 'customers'").get() as {
        rootpage: number;
      };
      probe.close();
      expect(rootpage).toBeGreaterThan(1);

      const buf = fs.readFileSync(dbPath);
      const rawPageSize = buf.readUInt16BE(16);
      const pageSize = rawPageSize === 1 ? 65536 : rawPageSize;
      buf.fill(0, (rootpage - 1) * pageSize, rootpage * pageSize);
      fs.writeFileSync(dbPath, buf);

      // Sanity: the schema metadata really does survive the damage.
      const schemaProbe = new DatabaseSync(dbPath, { readOnly: true });
      const names = (
        schemaProbe.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all() as { name: string }[]
      ).map((t) => t.name);
      schemaProbe.close();
      expect(names).toContain('customers');

      let caught: unknown;
      try {
        validateRestoreCandidate(dbPath);
      } catch (err) {
        caught = err;
      }
      expect(caught).toBeInstanceOf(OpsError);
      expect((caught as OpsError).code).toBe('RESTORE_INVALID');
      expect((caught as OpsError).message).toMatch(/integrity check/);

      // And restore refuses to replace the live database with it.
      expect(() => restoreDatabase(dbPath, dbPath, path.join(dir, 'rollbacks'))).toThrow(/integrity check/);
    } finally {
      cleanupDir(dir);
    }
  });

  it('rejects a SQLite file that is not a ConcreteOps database', () => {
    const { db, dir } = makeFileDb();
    try {
      const other = path.join(dir, 'other.db');
      const o = new DatabaseSync(other);
      o.exec('CREATE TABLE things (id INTEGER PRIMARY KEY);');
      o.close();
      expect(() => validateRestoreCandidate(other)).toThrow(/missing tables/);
    } finally {
      try {
        db.close();
      } catch {
        // ignore
      }
      cleanupDir(dir);
    }
  });
});

describe('persistence across restart', () => {
  it('keeps customers, jobs and pours after close and reopen', () => {
    const { db, dbPath, dir } = makeFileDb();
    const customer = addTestCustomer(db, 'Persistence Test Customer');
    const job = addTestJob(db, customer.id);
    const pour = addTestPour(db, job.id, 3200);
    db.close();

    // Reopen the same file and re-run migrations (idempotent) the way the
    // production openDatabase() path does after Electron resolves userData.
    const reopened = new DatabaseSync(dbPath);
    try {
      runMigrations(reopened);
      expect(getAppliedVersions(reopened)).toEqual([1]);
      const customers = listCustomers(reopened);
      expect(customers.some((c) => c.name === 'Persistence Test Customer')).toBe(true);
      const jobs = reopened.prepare('SELECT * FROM jobs').all() as { id: number }[];
      expect(jobs.some((j) => j.id === job.id)).toBe(true);
      const pours = reopened.prepare('SELECT quoted_liters FROM pours WHERE id = ?').get(pour.id) as { quoted_liters: number };
      expect(pours.quoted_liters).toBe(3200);
    } finally {
      reopened.close();
      cleanupDir(dir);
    }
  });
});
