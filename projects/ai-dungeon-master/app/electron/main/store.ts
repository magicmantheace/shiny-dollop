// SQLite persistence (node:sqlite) for the AI Dungeon Master.
// Each entity is stored as JSON in `json` with id/campaign columns
// denormalized for cheap listings. The session log is append-only at the
// service layer: there is deliberately no update/delete helper for log
// rows other than attachNarration, which may only fill the narration
// fields of an entry.
import { DatabaseSync } from 'node:sqlite';
import type {
  Campaign,
  Character,
  Encounter,
  LogEntry,
  MemoryEntry,
  NarrationSettings,
  Session,
} from '../../shared/types.js';

export const SCHEMA_VERSION = 1;

export function nowIso(): string {
  return new Date().toISOString();
}

const MIGRATIONS = `
CREATE TABLE IF NOT EXISTS campaigns (
  id TEXT PRIMARY KEY,
  name TEXT,
  json TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  campaign_id TEXT,
  json TEXT,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_campaign ON sessions(campaign_id, created_at);
CREATE TABLE IF NOT EXISTS characters (
  id TEXT PRIMARY KEY,
  campaign_id TEXT,
  json TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_characters_campaign ON characters(campaign_id);
CREATE TABLE IF NOT EXISTS encounters (
  id TEXT PRIMARY KEY,
  campaign_id TEXT,
  status TEXT,
  json TEXT,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_encounters_campaign ON encounters(campaign_id, status);
CREATE TABLE IF NOT EXISTS memory_entries (
  id TEXT PRIMARY KEY,
  campaign_id TEXT,
  json TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_memory_campaign ON memory_entries(campaign_id);
CREATE TABLE IF NOT EXISTS log_entries (
  id TEXT PRIMARY KEY,
  campaign_id TEXT,
  seq INTEGER,
  json TEXT,
  created_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_log_campaign_seq ON log_entries(campaign_id, seq);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
`;

export function openDatabase(dbPath: string): DatabaseSync {
  const db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec(MIGRATIONS);
  db.exec(`PRAGMA user_version = ${SCHEMA_VERSION};`);
  return db;
}

interface JsonRow {
  json: string;
}

function parse<T>(row: JsonRow): T {
  return JSON.parse(row.json) as T;
}

// ---------- campaigns ----------

export function insertCampaign(db: DatabaseSync, c: Campaign): Campaign {
  db.prepare('INSERT INTO campaigns (id, name, json, created_at, updated_at) VALUES (?,?,?,?,?)')
    .run(c.id, c.name, JSON.stringify(c), c.createdAt, c.updatedAt);
  return c;
}

export function getCampaign(db: DatabaseSync, id: string): Campaign | null {
  const row = db.prepare('SELECT json FROM campaigns WHERE id = ?').get(id) as unknown as
    | JsonRow
    | undefined;
  return row ? parse<Campaign>(row) : null;
}

export function listCampaigns(db: DatabaseSync): Campaign[] {
  const rows = db
    .prepare('SELECT json FROM campaigns ORDER BY updated_at DESC, rowid DESC')
    .all() as unknown as JsonRow[];
  return rows.map((r) => parse<Campaign>(r));
}

export function updateCampaign(db: DatabaseSync, c: Campaign): void {
  db.prepare('UPDATE campaigns SET name = ?, json = ?, updated_at = ? WHERE id = ?')
    .run(c.name, JSON.stringify(c), c.updatedAt, c.id);
}

export function deleteCampaign(db: DatabaseSync, id: string): boolean {
  db.exec('BEGIN');
  try {
    for (const table of ['sessions', 'characters', 'encounters', 'memory_entries', 'log_entries']) {
      db.prepare(`DELETE FROM ${table} WHERE campaign_id = ?`).run(id);
    }
    const res = db.prepare('DELETE FROM campaigns WHERE id = ?').run(id);
    db.exec('COMMIT');
    return Number(res.changes) > 0;
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
}

// ---------- generic per-campaign entity helpers ----------

function insertEntity(
  db: DatabaseSync,
  table: string,
  id: string,
  campaignId: string,
  value: unknown,
  createdAt: string,
  updatedAt: string | null,
  extra: Record<string, string> = {},
): void {
  const cols = ['id', 'campaign_id', 'json', 'created_at', ...Object.keys(extra)];
  if (updatedAt !== null) cols.push('updated_at');
  const placeholders = cols.map(() => '?').join(',');
  const values = [id, campaignId, JSON.stringify(value), createdAt, ...Object.values(extra)];
  if (updatedAt !== null) values.push(updatedAt);
  db.prepare(`INSERT INTO ${table} (${cols.join(',')}) VALUES (${placeholders})`).run(...values);
}

function getEntity<T>(db: DatabaseSync, table: string, id: string): T | null {
  const row = db.prepare(`SELECT json FROM ${table} WHERE id = ?`).get(id) as unknown as
    | JsonRow
    | undefined;
  return row ? parse<T>(row) : null;
}

function listEntities<T>(
  db: DatabaseSync,
  table: string,
  campaignId: string,
  order: string,
): T[] {
  const rows = db
    .prepare(`SELECT json FROM ${table} WHERE campaign_id = ? ORDER BY ${order}`)
    .all(campaignId) as unknown as JsonRow[];
  return rows.map((r) => parse<T>(r));
}

function updateEntity(
  db: DatabaseSync,
  table: string,
  id: string,
  value: unknown,
  updatedAt: string | null,
  extra: Record<string, string> = {},
): void {
  const sets = ['json = ?', ...Object.keys(extra).map((k) => `${k} = ?`)];
  const values = [JSON.stringify(value), ...Object.values(extra)];
  if (updatedAt !== null) sets.push('updated_at = ?');
  if (updatedAt !== null) values.push(updatedAt);
  values.push(id);
  db.prepare(`UPDATE ${table} SET ${sets.join(',')} WHERE id = ?`).run(...values);
}

function deleteEntity(db: DatabaseSync, table: string, id: string): boolean {
  const res = db.prepare(`DELETE FROM ${table} WHERE id = ?`).run(id);
  return Number(res.changes) > 0;
}

// ---------- sessions ----------

export function insertSession(db: DatabaseSync, s: Session): Session {
  insertEntity(db, 'sessions', s.id, s.campaignId, s, s.startedAt, null);
  return s;
}
export function getSession(db: DatabaseSync, id: string): Session | null {
  return getEntity<Session>(db, 'sessions', id);
}
export function listSessions(db: DatabaseSync, campaignId: string): Session[] {
  return listEntities<Session>(db, 'sessions', campaignId, 'created_at ASC, rowid ASC');
}
export function updateSession(db: DatabaseSync, s: Session): void {
  updateEntity(db, 'sessions', s.id, s, null);
}

// ---------- characters ----------

export function insertCharacter(db: DatabaseSync, c: Character): Character {
  insertEntity(db, 'characters', c.id, c.campaignId, c, c.createdAt, c.updatedAt);
  return c;
}
export function getCharacter(db: DatabaseSync, id: string): Character | null {
  return getEntity<Character>(db, 'characters', id);
}
export function listCharacters(db: DatabaseSync, campaignId: string): Character[] {
  return listEntities<Character>(db, 'characters', campaignId, 'created_at ASC, rowid ASC');
}
export function updateCharacter(db: DatabaseSync, c: Character): void {
  updateEntity(db, 'characters', c.id, c, c.updatedAt);
}
export function deleteCharacter(db: DatabaseSync, id: string): boolean {
  return deleteEntity(db, 'characters', id);
}

// ---------- encounters ----------

export function insertEncounter(db: DatabaseSync, e: Encounter): Encounter {
  insertEntity(db, 'encounters', e.id, e.campaignId, e, e.createdAt, null, { status: e.status });
  return e;
}
export function getEncounter(db: DatabaseSync, id: string): Encounter | null {
  return getEntity<Encounter>(db, 'encounters', id);
}
export function listEncounters(db: DatabaseSync, campaignId: string): Encounter[] {
  return listEntities<Encounter>(db, 'encounters', campaignId, 'created_at ASC, rowid ASC');
}
export function updateEncounter(db: DatabaseSync, e: Encounter): void {
  updateEntity(db, 'encounters', e.id, e, null, { status: e.status });
}

// ---------- memory ----------

export function insertMemory(db: DatabaseSync, m: MemoryEntry): MemoryEntry {
  insertEntity(db, 'memory_entries', m.id, m.campaignId, m, m.createdAt, m.updatedAt);
  return m;
}
export function getMemory(db: DatabaseSync, id: string): MemoryEntry | null {
  return getEntity<MemoryEntry>(db, 'memory_entries', id);
}
export function listMemory(db: DatabaseSync, campaignId: string): MemoryEntry[] {
  return listEntities<MemoryEntry>(db, 'memory_entries', campaignId, 'created_at ASC, rowid ASC');
}
export function updateMemory(db: DatabaseSync, m: MemoryEntry): void {
  updateEntity(db, 'memory_entries', m.id, m, m.updatedAt);
}
export function deleteMemory(db: DatabaseSync, id: string): boolean {
  return deleteEntity(db, 'memory_entries', id);
}

// ---------- log (append-only) ----------

export function nextLogSeq(db: DatabaseSync, campaignId: string): number {
  const row = db
    .prepare('SELECT COALESCE(MAX(seq), 0) AS maxSeq FROM log_entries WHERE campaign_id = ?')
    .get(campaignId) as unknown as { maxSeq: number };
  return Number(row.maxSeq) + 1;
}

export function insertLogEntry(db: DatabaseSync, entry: LogEntry): LogEntry {
  db.prepare('INSERT INTO log_entries (id, campaign_id, seq, json, created_at) VALUES (?,?,?,?,?)')
    .run(entry.id, entry.campaignId, entry.seq, JSON.stringify(entry), entry.createdAt);
  return entry;
}

export function getLogEntry(db: DatabaseSync, id: string): LogEntry | null {
  const row = db.prepare('SELECT json FROM log_entries WHERE id = ?').get(id) as unknown as
    | JsonRow
    | undefined;
  return row ? parse<LogEntry>(row) : null;
}

export function listLogEntries(
  db: DatabaseSync,
  campaignId: string,
  sessionId?: string | null,
): LogEntry[] {
  const all = listEntities<LogEntry>(db, 'log_entries', campaignId, 'seq ASC');
  if (sessionId === undefined || sessionId === null) return all;
  return all.filter((e) => e.sessionId === sessionId);
}

/**
 * The ONLY mutation ever applied to a log row: fill in its narration
 * flavor fields. Rules data (text/detail/seq) is immutable by design.
 */
export function attachNarration(
  db: DatabaseSync,
  entry: LogEntry,
  narration: string,
  source: string,
): LogEntry {
  const updated: LogEntry = { ...entry, narration, narrationSource: source };
  db.prepare('UPDATE log_entries SET json = ? WHERE id = ?')
    .run(JSON.stringify(updated), entry.id);
  return updated;
}

// ---------- settings ----------

const SETTINGS_KEY = 'narration';

export function getSettings(db: DatabaseSync): NarrationSettings {
  const row = db.prepare('SELECT value FROM settings WHERE key = ?').get(SETTINGS_KEY) as
    | { value: string }
    | undefined;
  if (!row) return { narrator: 'mock', endpoint: 'http://127.0.0.1:11434', model: '' };
  return JSON.parse(row.value) as NarrationSettings;
}

export function saveSettings(db: DatabaseSync, settings: NarrationSettings): NarrationSettings {
  db.prepare(
    'INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
  ).run(SETTINGS_KEY, JSON.stringify(settings));
  return settings;
}
