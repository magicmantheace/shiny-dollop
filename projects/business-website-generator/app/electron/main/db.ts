/**
 * SQLite site store (node:sqlite).
 *
 * The database file lives under Electron's userData directory; main.ts passes
 * the path in. This module takes an explicit path so it stays unit-testable
 * without Electron.
 *
 * Schema v1:
 *   sites(id TEXT PRIMARY KEY, name TEXT NOT NULL, businessType TEXT NOT NULL,
 *         themeId TEXT NOT NULL, profile TEXT NOT NULL /* JSON *\/, updated_at TEXT NOT NULL)
 *   schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)  -- key 'version'
 */
import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type {
  BusinessProfile,
  BusinessProfilePatch,
  BusinessType,
  NewSiteInput,
  Site,
  SiteSummary,
} from '../../shared/types.js';

export const SCHEMA_VERSION = 1;

export interface SiteStore {
  list(): SiteSummary[];
  create(input: NewSiteInput): Site;
  get(id: string): Site | null;
  updateProfile(id: string, patch: BusinessProfilePatch): Site;
  delete(id: string): boolean;
  setTheme(id: string, themeId: string): Site;
  /** Current schema version recorded in schema_meta. */
  schemaVersion(): number;
  close(): void;
}

export function defaultProfile(name: string, _businessType: BusinessType): BusinessProfile {
  return {
    name,
    tagline: '',
    about: '',
    contact: { phone: '', email: '', address: '', website: '' },
    hours: { label: 'Hours', lines: [] },
    services: [],
    menuSections: [],
    social: [],
    seo: { title: name, description: '' },
  };
}

function mergeProfile(base: BusinessProfile, patch: BusinessProfilePatch): BusinessProfile {
  return {
    ...base,
    ...patch,
    contact: { ...base.contact, ...(patch.contact ?? {}) },
    hours: { ...base.hours, ...(patch.hours ?? {}) },
    seo: { ...base.seo, ...(patch.seo ?? {}) },
  };
}

interface SiteRow {
  id: string;
  name: string;
  businessType: string;
  themeId: string;
  profile: string;
  updated_at: string;
}

function rowToSite(row: SiteRow): Site {
  return {
    id: row.id,
    name: row.name,
    businessType: row.businessType as BusinessType,
    themeId: row.themeId,
    updatedAt: row.updated_at,
    profile: JSON.parse(row.profile) as BusinessProfile,
  };
}

function rowToSummary(row: SiteRow): SiteSummary {
  return {
    id: row.id,
    name: row.name,
    businessType: row.businessType as BusinessType,
    themeId: row.themeId,
    updatedAt: row.updated_at,
  };
}

const MIGRATION_V1 = `
CREATE TABLE IF NOT EXISTS sites (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  businessType TEXT NOT NULL,
  themeId TEXT NOT NULL,
  profile TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
`;

export function openDb(dbPath: string): SiteStore {
  const db = new DatabaseSync(dbPath);

  // Explicit migration transaction: v1 baseline.
  db.exec('BEGIN');
  try {
    db.exec(MIGRATION_V1);
    const row = db
      .prepare("SELECT value FROM schema_meta WHERE key = 'version'")
      .get() as unknown as { value: string } | undefined;
    if (!row) {
      db.prepare("INSERT INTO schema_meta (key, value) VALUES ('version', ?)").run(String(SCHEMA_VERSION));
    }
    db.exec('COMMIT');
  } catch (e) {
    db.exec('ROLLBACK');
    throw e;
  }

  function transaction<T>(fn: () => T): T {
    db.exec('BEGIN');
    try {
      const out = fn();
      db.exec('COMMIT');
      return out;
    } catch (e) {
      db.exec('ROLLBACK');
      throw e;
    }
  }

  const getStmt = () => db.prepare('SELECT * FROM sites WHERE id = ?');

  return {
    list(): SiteSummary[] {
      const rows = db.prepare('SELECT * FROM sites ORDER BY updated_at DESC, id ASC').all() as unknown as SiteRow[];
      return rows.map(rowToSummary);
    },

    create(input: NewSiteInput): Site {
      return transaction(() => {
        const id = randomUUID();
        const updatedAt = new Date().toISOString();
        const profile = defaultProfile(input.name, input.businessType);
        db.prepare(
          'INSERT INTO sites (id, name, businessType, themeId, profile, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
        ).run(id, input.name, input.businessType, input.themeId, JSON.stringify(profile), updatedAt);
        const row = getStmt().get(id) as unknown as SiteRow;
        return rowToSite(row);
      });
    },

    get(id: string): Site | null {
      const row = getStmt().get(id) as unknown as SiteRow | undefined;
      return row ? rowToSite(row) : null;
    },

    updateProfile(id: string, patch: BusinessProfilePatch): Site {
      return transaction(() => {
        const row = getStmt().get(id) as unknown as SiteRow | undefined;
        if (!row) throw new Error(`SITE_NOT_FOUND: No site with id "${id}".`);
        const merged = mergeProfile(JSON.parse(row.profile) as BusinessProfile, patch);
        const updatedAt = new Date().toISOString();
        db.prepare('UPDATE sites SET profile = ?, name = ?, updated_at = ? WHERE id = ?').run(
          JSON.stringify(merged),
          merged.name,
          updatedAt,
          id,
        );
        return rowToSite(getStmt().get(id) as unknown as SiteRow);
      });
    },

    delete(id: string): boolean {
      return transaction(() => {
        const res = db.prepare('DELETE FROM sites WHERE id = ?').run(id);
        return Number(res.changes) > 0;
      });
    },

    setTheme(id: string, themeId: string): Site {
      return transaction(() => {
        const row = getStmt().get(id) as unknown as SiteRow | undefined;
        if (!row) throw new Error(`SITE_NOT_FOUND: No site with id "${id}".`);
        const updatedAt = new Date().toISOString();
        db.prepare('UPDATE sites SET themeId = ?, updated_at = ? WHERE id = ?').run(themeId, updatedAt, id);
        return rowToSite(getStmt().get(id) as unknown as SiteRow);
      });
    },

    schemaVersion(): number {
      const row = db
        .prepare("SELECT value FROM schema_meta WHERE key = 'version'")
        .get() as unknown as { value: string } | undefined;
      return row ? Number(row.value) : 0;
    },

    close(): void {
      db.close();
    },
  };
}
