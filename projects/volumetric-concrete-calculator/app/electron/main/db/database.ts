import { DatabaseSync } from 'node:sqlite';
import { app } from 'electron';
import path from 'node:path';
import fs from 'node:fs';

const SCHEMA_VERSION = 1;

const MIGRATIONS: string[] = [
  /* v1 */ `
  CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL,
    volume_unit TEXT NOT NULL CHECK (volume_unit IN ('m3','L','yd3')),
    mass_unit TEXT NOT NULL CHECK (mass_unit IN ('kg','t','lb')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    material_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    description TEXT,
    UNIQUE (profile_id, material_id)
  );
  CREATE TABLE IF NOT EXISTS calibrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    material_id TEXT NOT NULL,
    gate_setting REAL NOT NULL CHECK (gate_setting > 0),
    measured_output_per_unit REAL NOT NULL CHECK (measured_output_per_unit > 0),
    measured_at TEXT,
    source TEXT
  );
  CREATE TABLE IF NOT EXISTS mixes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mix_design_id TEXT NOT NULL,
    note TEXT,
    UNIQUE (profile_id, mix_design_id)
  );
  CREATE TABLE IF NOT EXISTS mix_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mix_id INTEGER NOT NULL REFERENCES mixes(id) ON DELETE CASCADE,
    material_id TEXT NOT NULL,
    target_per_m3 REAL NOT NULL CHECK (target_per_m3 >= 0)
  );
  CREATE TABLE IF NOT EXISTS calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    profile_name TEXT NOT NULL,
    mix_design_id TEXT NOT NULL,
    volume REAL NOT NULL,
    volume_unit TEXT NOT NULL,
    waste_allowance_pct REAL NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
  );
  `,
];

let db: DatabaseSync | null = null;

export function dbPath(): string {
  const dir = path.join(app.getPath('userData'), 'volumetric-concrete-calculator');
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, 'calculator.db');
}

export function getDb(): DatabaseSync {
  if (db) return db;
  db = new DatabaseSync(dbPath());
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  const row = db.prepare('SELECT name FROM sqlite_master WHERE type = ? AND name = ?').get('table', 'schema_version') as
    | { name: string }
    | undefined;
  let version = 0;
  if (row) {
    const v = db.prepare('SELECT version AS v FROM schema_version ORDER BY version DESC LIMIT 1').get() as
      | { v: number }
      | undefined;
    version = v?.v ?? 0;
  }
  for (let v = version; v < SCHEMA_VERSION; v++) {
    db.exec(MIGRATIONS[v]);
    db.prepare('INSERT OR REPLACE INTO schema_version (version) VALUES (?)').run(v + 1);
  }
  return db;
}

export function closeDb(): void {
  db?.close();
  db = null;
}
