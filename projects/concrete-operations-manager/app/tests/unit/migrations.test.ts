import { describe, expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import { getAppliedVersions, runMigrations } from '../../electron/main/db/migrations';
import { getSetting } from '../../electron/main/db/settings';

describe('migrations', () => {
  it('applies exactly once and is idempotent', () => {
    const db = new DatabaseSync(':memory:');
    try {
      runMigrations(db);
      expect(getAppliedVersions(db)).toEqual([1]);
      runMigrations(db);
      runMigrations(db);
      expect(getAppliedVersions(db)).toEqual([1]);
    } finally {
      db.close();
    }
  });

  it('seeds tax rates, materials and settings', () => {
    const db = new DatabaseSync(':memory:');
    try {
      runMigrations(db);
      const taxes = db.prepare('SELECT * FROM tax_rates').all() as { name: string; rate_bps: number }[];
      expect(taxes).toHaveLength(1);
      expect(taxes[0]).toMatchObject({ name: 'GST', rate_bps: 500 });
      const materials = db.prepare('SELECT name FROM inventory_materials').all() as { name: string }[];
      expect(materials.map((m) => m.name).sort()).toEqual(['Gravel (20mm)', 'Portland cement', 'Sand']);
      expect(getSetting(db, 'default_concrete_rate_cents_per_m3')).toBe('18000');
      expect(getSetting(db, 'small_load_threshold_liters')).toBe('3000');
    } finally {
      db.close();
    }
  });

  it('enables foreign keys for the schema to work as designed', () => {
    const db = new DatabaseSync(':memory:');
    try {
      db.exec('PRAGMA foreign_keys = ON;');
      runMigrations(db);
      // A pour referencing a nonexistent job must fail.
      expect(() =>
        db.prepare("INSERT INTO pours (job_id, mix_design_id, quoted_liters, created_at) VALUES (9999, 'C25/30', 100, 'x')").run(),
      ).toThrow();
    } finally {
      db.close();
    }
  });
});
