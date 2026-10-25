// Local spectator preferences (node:sqlite).
//
// Local-only state: the last-used Feed base URL and the viewer's followed
// Descenders. Following is a preference of THIS client only — it is never
// sent to the Feed server (the server's session follow endpoints are not
// used). Schema is versioned (PRAGMA user_version); the export/import
// envelope carries formatVersion '1.0.0' and unknown majors are rejected.

import { DatabaseSync } from 'node:sqlite';
import { z } from 'zod';
import { SpectatorError } from '../../shared/errors.js';
import { PREFS_FORMAT_VERSION, type Prefs, type PrefsEnvelope } from '../../shared/types.js';

export const PREFS_SCHEMA_VERSION = 1;
export const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';

const PrefsSchema = z.object({
  baseUrl: z.string(),
  followedDescenderIds: z.array(z.string()),
});

const PrefsEnvelopeSchema = z.object({
  formatVersion: z.string(),
  prefs: PrefsSchema,
});

const DEFAULT_PREFS: Prefs = { baseUrl: DEFAULT_BASE_URL, followedDescenderIds: [] };

export function openPrefsDatabase(dbPath: string): DatabaseSync {
  const db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('CREATE TABLE IF NOT EXISTS prefs (id INTEGER PRIMARY KEY CHECK (id = 1), json TEXT NOT NULL);');
  db.exec(`PRAGMA user_version = ${PREFS_SCHEMA_VERSION};`);
  return db;
}

export function getPrefs(db: DatabaseSync): Prefs {
  const row = db.prepare('SELECT json FROM prefs WHERE id = 1').get() as unknown as { json: string } | undefined;
  if (!row) return { ...DEFAULT_PREFS, followedDescenderIds: [] };
  const parsed = PrefsSchema.safeParse(JSON.parse(row.json) as unknown);
  if (!parsed.success) {
    throw new SpectatorError('PREFS_INVALID', 'Stored spectator preferences are corrupt and were not applied.');
  }
  return parsed.data;
}

export function savePrefs(db: DatabaseSync, prefs: Prefs): Prefs {
  const clean: Prefs = {
    baseUrl: prefs.baseUrl,
    followedDescenderIds: [...new Set(prefs.followedDescenderIds)].sort(),
  };
  db.prepare('INSERT INTO prefs (id, json) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET json = excluded.json').run(JSON.stringify(clean));
  return clean;
}

export function exportPrefs(db: DatabaseSync): PrefsEnvelope {
  return { formatVersion: PREFS_FORMAT_VERSION, prefs: getPrefs(db) };
}

export function importPrefs(db: DatabaseSync, envelope: unknown): Prefs {
  const parsed = PrefsEnvelopeSchema.safeParse(envelope);
  if (!parsed.success) {
    throw new SpectatorError('PREFS_INVALID', 'The preferences file does not match the expected format and was not imported.');
  }
  const major = parsed.data.formatVersion.split('.')[0];
  if (major !== PREFS_FORMAT_VERSION.split('.')[0]) {
    throw new SpectatorError(
      'PREFS_VERSION_UNSUPPORTED',
      `Preferences format ${parsed.data.formatVersion} is not supported by this version (expected ${PREFS_FORMAT_VERSION}).`,
    );
  }
  return savePrefs(db, parsed.data.prefs);
}
