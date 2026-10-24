/**
 * SQLite persistence via node:sqlite (Node 22.5+ built-in).
 *
 * Tables: schema_version, profiles, journal, snapshots.
 * Every write runs inside an explicit BEGIN/COMMIT/ROLLBACK so a partial
 * multi-statement write can never land half-applied.
 */

import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import type {
  ChangeSpec,
  JournalEntry,
  Profile,
  ResourceSnapshot,
} from '../../../shared/gpp-types.js';

export const SCHEMA_VERSION = 1;

export class GppDatabase {
  private db: DatabaseSync;

  constructor(path: string) {
    this.db = new DatabaseSync(path);
    this.migrate();
  }

  close(): void {
    this.db.close();
  }

  private migrate(): void {
    this.transaction(() => {
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS schema_version (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profiles (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          changes_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS journal (
          id TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          profile_name TEXT NOT NULL,
          change_kind TEXT NOT NULL,
          target TEXT NOT NULL,
          before_value TEXT NOT NULL,
          after_value TEXT NOT NULL,
          applied_at TEXT NOT NULL,
          rolled_back_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_journal_profile ON journal(profile_id, applied_at);
        CREATE TABLE IF NOT EXISTS snapshots (
          id TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          taken_at TEXT NOT NULL,
          cpu_percent REAL NOT NULL,
          memory_mb REAL NOT NULL,
          note TEXT NOT NULL
        );
      `);
      const row = this.db.prepare('SELECT version FROM schema_version ORDER BY version DESC LIMIT 1').get() as
        | { version: number }
        | undefined;
      if (!row) {
        this.db
          .prepare('INSERT INTO schema_version (version, applied_at) VALUES (?, ?)')
          .run(SCHEMA_VERSION, new Date().toISOString());
      } else if (row.version !== SCHEMA_VERSION) {
        throw new Error(`Unsupported schema version ${row.version} (expected ${SCHEMA_VERSION}).`);
      }
    });
  }

  /** Run fn inside BEGIN/COMMIT; ROLLBACK + rethrow on error. */
  transaction<T>(fn: () => T): T {
    this.db.exec('BEGIN');
    try {
      const result = fn();
      this.db.exec('COMMIT');
      return result;
    } catch (e) {
      try {
        this.db.exec('ROLLBACK');
      } catch {
        /* rollback of a failed rollback: nothing to do */
      }
      throw e;
    }
  }

  // -- profiles ------------------------------------------------------------

  listProfiles(): Profile[] {
    const rows = this.db.prepare('SELECT * FROM profiles ORDER BY created_at ASC').all() as unknown as ProfileRow[];
    return rows.map(rowToProfile);
  }

  getProfile(id: string): Profile | undefined {
    const row = this.db.prepare('SELECT * FROM profiles WHERE id = ?').get(id) as ProfileRow | undefined;
    return row ? rowToProfile(row) : undefined;
  }

  createProfile(name: string, changes: ChangeSpec[]): Profile {
    const now = new Date().toISOString();
    const profile: Profile = { id: randomUUID(), name, changes, createdAt: now, updatedAt: now };
    this.transaction(() => {
      this.db
        .prepare('INSERT INTO profiles (id, name, changes_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)')
        .run(profile.id, profile.name, JSON.stringify(profile.changes), profile.createdAt, profile.updatedAt);
    });
    return profile;
  }

  updateProfile(id: string, patch: { name?: string; changes?: ChangeSpec[] }): Profile | undefined {
    const existing = this.getProfile(id);
    if (!existing) return undefined;
    const updated: Profile = {
      ...existing,
      name: patch.name ?? existing.name,
      changes: patch.changes ?? existing.changes,
      updatedAt: new Date().toISOString(),
    };
    this.transaction(() => {
      this.db
        .prepare('UPDATE profiles SET name = ?, changes_json = ?, updated_at = ? WHERE id = ?')
        .run(updated.name, JSON.stringify(updated.changes), updated.updatedAt, updated.id);
    });
    return updated;
  }

  deleteProfile(id: string): boolean {
    return this.transaction(() => {
      const res = this.db.prepare('DELETE FROM profiles WHERE id = ?').run(id);
      return res.changes > 0;
    });
  }

  // -- journal ---------------------------------------------------------------

  addJournalEntry(entry: Omit<JournalEntry, 'id' | 'appliedAt' | 'rolledBackAt'>): JournalEntry {
    const full: JournalEntry = {
      ...entry,
      id: randomUUID(),
      appliedAt: new Date().toISOString(),
      rolledBackAt: undefined,
    };
    this.transaction(() => {
      this.db
        .prepare(
          `INSERT INTO journal
             (id, profile_id, profile_name, change_kind, target, before_value, after_value, applied_at, rolled_back_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)`,
        )
        .run(
          full.id,
          full.profileId,
          full.profileName,
          full.changeKind,
          full.target,
          full.before,
          full.after,
          full.appliedAt,
        );
    });
    return full;
  }

  listJournal(): JournalEntry[] {
    const rows = this.db.prepare('SELECT * FROM journal ORDER BY applied_at ASC').all() as unknown as JournalRow[];
    return rows.map(rowToJournal);
  }

  /** Un-rolled-back journal entries for a profile, newest first (rollback order). */
  listUnrolledBack(profileId?: string): JournalEntry[] {
    // rowid DESC breaks ties when two entries share a millisecond timestamp.
    const orderBy = 'ORDER BY applied_at DESC, rowid DESC';
    const rows = (
      profileId
        ? this.db
            .prepare(`SELECT * FROM journal WHERE profile_id = ? AND rolled_back_at IS NULL ${orderBy}`)
            .all(profileId)
        : this.db.prepare(`SELECT * FROM journal WHERE rolled_back_at IS NULL ${orderBy}`).all()
    ) as unknown as JournalRow[];
    return rows.map(rowToJournal);
  }

  markRolledBack(id: string): void {
    this.transaction(() => {
      this.db.prepare('UPDATE journal SET rolled_back_at = ? WHERE id = ?').run(new Date().toISOString(), id);
    });
  }

  // -- snapshots -------------------------------------------------------------

  addSnapshot(s: Omit<ResourceSnapshot, 'id' | 'takenAt'>): ResourceSnapshot {
    const full: ResourceSnapshot = { ...s, id: randomUUID(), takenAt: new Date().toISOString() };
    this.transaction(() => {
      this.db
        .prepare('INSERT INTO snapshots (id, label, taken_at, cpu_percent, memory_mb, note) VALUES (?, ?, ?, ?, ?, ?)')
        .run(full.id, full.label, full.takenAt, full.cpuPercent, full.memoryMb, full.note);
    });
    return full;
  }

  listSnapshots(): ResourceSnapshot[] {
    const rows = this.db.prepare('SELECT * FROM snapshots ORDER BY taken_at ASC').all() as unknown as SnapshotRow[];
    return rows.map((r) => ({
      id: r.id,
      label: r.label,
      takenAt: r.taken_at,
      cpuPercent: r.cpu_percent,
      memoryMb: r.memory_mb,
      note: r.note,
    }));
  }
}

interface ProfileRow {
  id: string;
  name: string;
  changes_json: string;
  created_at: string;
  updated_at: string;
}

interface JournalRow {
  id: string;
  profile_id: string;
  profile_name: string;
  change_kind: string;
  target: string;
  before_value: string;
  after_value: string;
  applied_at: string;
  rolled_back_at: string | null;
}

interface SnapshotRow {
  id: string;
  label: string;
  taken_at: string;
  cpu_percent: number;
  memory_mb: number;
  note: string;
}

function rowToProfile(r: ProfileRow): Profile {
  return {
    id: r.id,
    name: r.name,
    changes: JSON.parse(r.changes_json) as ChangeSpec[],
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  };
}

function rowToJournal(r: JournalRow): JournalEntry {
  return {
    id: r.id,
    profileId: r.profile_id,
    profileName: r.profile_name,
    changeKind: r.change_kind as JournalEntry['changeKind'],
    target: r.target,
    before: r.before_value,
    after: r.after_value,
    appliedAt: r.applied_at,
    rolledBackAt: r.rolled_back_at ?? undefined,
  };
}
