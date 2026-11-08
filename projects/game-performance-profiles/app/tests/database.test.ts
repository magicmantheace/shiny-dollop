/**
 * SQLite store tests: schema versioning, profile CRUD, journal lifecycle,
 * snapshots, and explicit transaction atomicity. All against :memory: DBs.
 */
import { describe, expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import { GppDatabase, SCHEMA_VERSION } from '../electron/main/store/database.js';

function memDb(): GppDatabase {
  return new GppDatabase(':memory:');
}

describe('schema', () => {
  it('records schema_version 1 in the database file', async () => {
    const { mkdtempSync } = await import('node:fs');
    const { join } = await import('node:path');
    const { tmpdir } = await import('node:os');
    const file = join(mkdtempSync(join(tmpdir(), 'gpp-test-')), 'test.sqlite');
    const db = new GppDatabase(file);
    db.close();
    const raw = new DatabaseSync(file);
    const row = raw.prepare('SELECT version FROM schema_version').get() as unknown as { version: number };
    expect(row.version).toBe(SCHEMA_VERSION);
    const tables = raw
      .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
      .all() as Array<{ name: string }>;
    for (const t of ['profiles', 'journal', 'snapshots', 'schema_version']) {
      expect(tables.map((r) => r.name)).toContain(t);
    }
    raw.close();
  });

  it('persists tables across close/reopen of a file database', async () => {
    const { mkdtempSync } = await import('node:fs');
    const { join } = await import('node:path');
    const { tmpdir } = await import('node:os');
    const dir = mkdtempSync(join(tmpdir(), 'gpp-test-'));
    const file = join(dir, 'test.sqlite');
    const db1 = new GppDatabase(file);
    db1.createProfile('Persist', [{ kind: 'game-mode', params: { enabled: 'true' } }]);
    db1.close();
    const db2 = new GppDatabase(file);
    expect(db2.listProfiles()).toHaveLength(1);
    expect(db2.listProfiles()[0]!.name).toBe('Persist');
    db2.close();
  });
});

describe('profiles', () => {
  it('CRUD round-trips with JSON changes', () => {
    const db = memDb();
    const created = db.createProfile('A', [
      { kind: 'game-mode', params: { enabled: 'true' } },
      { kind: 'power-plan', params: { guid: '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c' } },
    ]);
    expect(created.id).toBeTruthy();
    expect(db.getProfile(created.id)).toEqual(created);

    const updated = db.updateProfile(created.id, { name: 'B' })!;
    expect(updated.name).toBe('B');
    expect(updated.changes).toHaveLength(2);
    expect(new Date(updated.updatedAt).getTime()).toBeGreaterThanOrEqual(
      new Date(created.updatedAt).getTime(),
    );

    const updated2 = db.updateProfile(created.id, {
      changes: [{ kind: 'game-mode', params: { enabled: 'false' } }],
    })!;
    expect(updated2.changes).toHaveLength(1);

    expect(db.updateProfile('missing', { name: 'x' })).toBeUndefined();
    expect(db.deleteProfile(created.id)).toBe(true);
    expect(db.deleteProfile(created.id)).toBe(false);
    expect(db.listProfiles()).toHaveLength(0);
    db.close();
  });
});

describe('journal', () => {
  it('add → listUnrolledBack (newest-first) → markRolledBack', () => {
    const db = memDb();
    const e1 = db.addJournalEntry({
      profileId: 'p',
      profileName: 'P',
      changeKind: 'game-mode',
      target: 't',
      before: 'disabled',
      after: 'enabled',
    });
    const e2 = db.addJournalEntry({
      profileId: 'p',
      profileName: 'P',
      changeKind: 'power-plan',
      target: 't2',
      before: 'a',
      after: 'b',
    });
    const pending = db.listUnrolledBack('p');
    expect(pending).toHaveLength(2);
    // newest first — e2 was added after e1
    expect(pending[0]!.id).toBe(e2.id);
    expect(pending[1]!.id).toBe(e1.id);

    db.markRolledBack(e2.id);
    expect(db.listUnrolledBack('p').map((e) => e.id)).toEqual([e1.id]);
    expect(db.listJournal()).toHaveLength(2);
    db.close();
  });

  it('listUnrolledBack without a profile id covers all profiles', () => {
    const db = memDb();
    db.addJournalEntry({
      profileId: 'p1', profileName: 'P1', changeKind: 'game-mode',
      target: 't', before: 'a', after: 'b',
    });
    db.addJournalEntry({
      profileId: 'p2', profileName: 'P2', changeKind: 'game-mode',
      target: 't', before: 'a', after: 'b',
    });
    expect(db.listUnrolledBack()).toHaveLength(2);
    expect(db.listUnrolledBack('p1')).toHaveLength(1);
    db.close();
  });
});

describe('transactions', () => {
  it('a throwing transaction rolls back and leaves the DB usable', () => {
    const db = memDb();
    expect(() =>
      db.transaction(() => {
        throw new Error('boom');
      }),
    ).toThrow('boom');
    // The failed BEGIN/ROLLBACK must not poison the connection: later writes work.
    const ok = db.createProfile('Fine', []);
    expect(db.getProfile(ok.id)!.name).toBe('Fine');
    db.close();
  });
});

describe('snapshots', () => {
  it('add → list round-trips all fields', () => {
    const db = memDb();
    const s = db.addSnapshot({
      label: 'after',
      cpuPercent: 42.5,
      memoryMb: 9000,
      note: 'approximate — point-in-time estimate, not a benchmark',
    });
    expect(s.id).toBeTruthy();
    expect(s.takenAt).toBeTruthy();
    const listed = db.listSnapshots();
    expect(listed).toHaveLength(1);
    expect(listed[0]).toEqual(s);
    db.close();
  });
});
