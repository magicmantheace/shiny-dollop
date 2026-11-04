import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { exportPrefs, getPrefs, importPrefs, openPrefsDatabase, savePrefs } from '../../electron/main/prefs';

let dir: string;
beforeAll(async () => {
  dir = await mkdtemp(join(tmpdir(), 'spectator-prefs-test-'));
});
afterAll(async () => {
  await rm(dir, { recursive: true, force: true });
});

describe('prefs store', () => {
  it('returns defaults on a fresh database', () => {
    const db = openPrefsDatabase(join(dir, 'a.sqlite'));
    expect(getPrefs(db)).toEqual({ baseUrl: 'http://127.0.0.1:8000', followedDescenderIds: [] });
    db.close();
  });

  it('persists base URL and follows across a reopen, deduped and sorted', () => {
    const path = join(dir, 'b.sqlite');
    const db = openPrefsDatabase(path);
    savePrefs(db, { baseUrl: 'http://127.0.0.1:9001', followedDescenderIds: ['selka-morrow', 'mira-vane', 'mira-vane'] });
    db.close();
    const reopened = openPrefsDatabase(path);
    expect(getPrefs(reopened)).toEqual({
      baseUrl: 'http://127.0.0.1:9001',
      followedDescenderIds: ['mira-vane', 'selka-morrow'],
    });
    reopened.close();
  });

  it('export/import round-trips into a fresh database', () => {
    const source = openPrefsDatabase(join(dir, 'c.sqlite'));
    savePrefs(source, { baseUrl: 'http://localhost:8123', followedDescenderIds: ['issa-quill'] });
    const envelope = exportPrefs(source);
    expect(envelope.formatVersion).toBe('1.0.0');
    source.close();
    const target = openPrefsDatabase(join(dir, 'd.sqlite'));
    const imported = importPrefs(target, envelope);
    expect(imported).toEqual({ baseUrl: 'http://localhost:8123', followedDescenderIds: ['issa-quill'] });
    target.close();
  });

  it('rejects unknown major versions and garbage envelopes', () => {
    const db = openPrefsDatabase(join(dir, 'e.sqlite'));
    expect(() => importPrefs(db, { formatVersion: '2.0.0', prefs: { baseUrl: 'x', followedDescenderIds: [] } }))
      .toThrowError(expect.objectContaining({ code: 'PREFS_VERSION_UNSUPPORTED' }));
    expect(() => importPrefs(db, { nope: true })).toThrowError(expect.objectContaining({ code: 'PREFS_INVALID' }));
    expect(() => importPrefs(db, 'a string')).toThrowError(expect.objectContaining({ code: 'PREFS_INVALID' }));
    db.close();
  });
});
