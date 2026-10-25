/**
 * Schema migrations. Each migration is a versioned, idempotent step;
 * the schema_migrations table records what has already been applied.
 */
import type { DatabaseSync } from 'node:sqlite';

interface Migration {
  version: number;
  description: string;
  sql: string;
}

const MIGRATIONS: Migration[] = [
  {
    version: 1,
    description: 'initial schema: customers, jobs, pours, quotes, invoices, tax, inventory, audit, settings',
    sql: `
      CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        tax_exempt INTEGER NOT NULL DEFAULT 0,
        concrete_rate_cents_per_m3 INTEGER,
        small_load_charge_cents INTEGER,
        delivery_fee_mode TEXT CHECK (delivery_fee_mode IN ('flat','mileage')),
        delivery_flat_cents INTEGER,
        delivery_per_km_cents INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
        job_date TEXT NOT NULL,
        delivery_location TEXT NOT NULL,
        po_number TEXT,
        distance_tenths_km INTEGER,
        status TEXT NOT NULL DEFAULT 'scheduled'
          CHECK (status IN ('scheduled','in_progress','completed','cancelled')),
        notes TEXT,
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS pours (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        mix_design_id TEXT NOT NULL,
        quoted_liters INTEGER NOT NULL CHECK (quoted_liters > 0),
        delivered_liters INTEGER CHECK (delivered_liters IS NULL OR delivered_liters > 0),
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft'
          CHECK (status IN ('draft','issued','superseded')),
        lines_json TEXT NOT NULL,
        subtotal_cents INTEGER NOT NULL,
        tax_lines_json TEXT NOT NULL,
        total_cents INTEGER NOT NULL,
        tax_exempt_applied INTEGER NOT NULL DEFAULT 0,
        params_json TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL,
        issued_at TEXT,
        UNIQUE (job_id, version)
      );
      CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id INTEGER NOT NULL UNIQUE REFERENCES quotes(id) ON DELETE RESTRICT,
        invoice_number TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'issued'
          CHECK (status IN ('issued','paid','voided')),
        lines_json TEXT NOT NULL,
        subtotal_cents INTEGER NOT NULL,
        tax_lines_json TEXT NOT NULL,
        total_cents INTEGER NOT NULL,
        tax_exempt_applied INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        paid_at TEXT,
        voided_at TEXT
      );
      CREATE TABLE IF NOT EXISTS tax_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        rate_bps INTEGER NOT NULL CHECK (rate_bps >= 0),
        enabled INTEGER NOT NULL DEFAULT 1
      );
      CREATE TABLE IF NOT EXISTS inventory_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        unit TEXT NOT NULL DEFAULT 'kg'
      );
      CREATE TABLE IF NOT EXISTS inventory_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id INTEGER NOT NULL REFERENCES inventory_materials(id) ON DELETE RESTRICT,
        supplier TEXT NOT NULL,
        received_date TEXT NOT NULL,
        qty_kg INTEGER NOT NULL CHECK (qty_kg > 0),
        cost_cents INTEGER NOT NULL CHECK (cost_cents >= 0),
        notes TEXT,
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS inventory_consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pour_id INTEGER NOT NULL REFERENCES pours(id) ON DELETE CASCADE,
        material_id INTEGER NOT NULL REFERENCES inventory_materials(id) ON DELETE RESTRICT,
        qty_kg INTEGER NOT NULL CHECK (qty_kg > 0),
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS audit_trail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        actor TEXT NOT NULL,
        before_json TEXT,
        after_json TEXT,
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS calibration_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        format_version TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        imported_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_jobs_customer ON jobs(customer_id);
      CREATE INDEX IF NOT EXISTS idx_pours_job ON pours(job_id);
      CREATE INDEX IF NOT EXISTS idx_quotes_job ON quotes(job_id);
      CREATE INDEX IF NOT EXISTS idx_receipts_material ON inventory_receipts(material_id);
      CREATE INDEX IF NOT EXISTS idx_consumption_material ON inventory_consumption(material_id);
      CREATE INDEX IF NOT EXISTS idx_consumption_pour ON inventory_consumption(pour_id);
      CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_trail(entity_type, entity_id);
      CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_trail(created_at);
    `,
  },
];

/** Seed rows applied exactly once (guarded by INSERT OR IGNORE semantics). */
const SEED_SQL = `
  INSERT OR IGNORE INTO tax_rates (name, rate_bps, enabled) VALUES ('GST', 500, 1);
  INSERT OR IGNORE INTO inventory_materials (name, unit) VALUES
    ('Portland cement', 'kg'),
    ('Sand', 'kg'),
    ('Gravel (20mm)', 'kg');
  INSERT OR IGNORE INTO app_settings (key, value) VALUES
    ('company_name', 'Concrete Operations'),
    ('company_address', ''),
    ('default_concrete_rate_cents_per_m3', '18000'),
    ('default_small_load_charge_cents', '15000'),
    ('small_load_threshold_liters', '3000'),
    ('default_delivery_mode', 'flat'),
    ('default_delivery_flat_cents', '7500'),
    ('default_delivery_per_km_cents', '350');
`;

function ensureMigrationsTable(db: DatabaseSync): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version INTEGER PRIMARY KEY,
      applied_at TEXT NOT NULL
    );
  `);
}

export function getAppliedVersions(db: DatabaseSync): number[] {
  ensureMigrationsTable(db);
  const rows = db.prepare('SELECT version FROM schema_migrations ORDER BY version').all() as {
    version: number;
  }[];
  return rows.map((r) => r.version);
}

/** Apply every migration that has not been applied yet. Idempotent. */
export function runMigrations(db: DatabaseSync): void {
  ensureMigrationsTable(db);
  const applied = new Set(getAppliedVersions(db));
  for (const m of MIGRATIONS) {
    if (applied.has(m.version)) continue;
    db.exec(m.sql);
    db.exec(SEED_SQL);
    db.prepare('INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)').run(
      m.version,
      new Date().toISOString(),
    );
  }
}

/** Highest migration version the code knows about. */
export function latestMigrationVersion(): number {
  return MIGRATIONS[MIGRATIONS.length - 1]?.version ?? 0;
}
