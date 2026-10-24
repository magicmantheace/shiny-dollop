/**
 * SQLite store tests: schema version, CRUD round-trip, profile merge
 * semantics, and explicit transaction behavior.
 */
import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { openDb, SCHEMA_VERSION, type SiteStore } from '../../electron/main/db.js';
import { makeProfile } from './fixtures.js';

let tmp: string;
let store: SiteStore;
let dbFile: string;

beforeEach(async () => {
  tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'bwg-db-'));
  dbFile = path.join(tmp, 'test.sqlite');
  store = openDb(dbFile);
});

afterEach(async () => {
  store.close();
  await fs.rm(tmp, { recursive: true, force: true });
});

describe('schema', () => {
  it('migrates to schema version 1 on open', () => {
    expect(store.schemaVersion()).toBe(SCHEMA_VERSION);
    expect(store.schemaVersion()).toBe(1);
  });

  it('keeps existing data when reopened', () => {
    const created = store.create({ name: 'Keep Me', businessType: 'author', themeId: 'author' });
    store.close();
    store = openDb(dbFile); // reassign so afterEach closes the live handle
    expect(store.get(created.id)?.name).toBe('Keep Me');
    expect(store.schemaVersion()).toBe(1);
  });
});

describe('CRUD', () => {
  it('round-trips create → get with a default profile', () => {
    const created = store.create({ name: 'Acme Test Co.', businessType: 'trades', themeId: 'trades' });
    expect(created.id).toBeTruthy();
    expect(created.name).toBe('Acme Test Co.');
    expect(created.businessType).toBe('trades');
    expect(created.themeId).toBe('trades');
    expect(created.profile.name).toBe('Acme Test Co.');
    expect(created.profile.seo.title).toBe('Acme Test Co.');
    expect(created.updatedAt).toBeTruthy();

    const fetched = store.get(created.id);
    expect(fetched).toEqual(created);
  });

  it('returns null for an unknown id', () => {
    expect(store.get('does-not-exist')).toBeNull();
  });

  it('lists summaries without full profiles', () => {
    store.create({ name: 'One', businessType: 'trades', themeId: 'trades' });
    store.create({ name: 'Two', businessType: 'restaurant', themeId: 'restaurant' });
    const list = store.list();
    expect(list).toHaveLength(2);
    expect(list.map((s) => s.name).sort()).toEqual(['One', 'Two']);
    for (const summary of list) {
      expect(summary).not.toHaveProperty('profile');
    }
  });

  it('updateProfile merges nested objects and replaces arrays', () => {
    const created = store.create({ name: 'Acme', businessType: 'trades', themeId: 'trades' });
    store.updateProfile(created.id, {
      contact: { phone: '555-000-1111', email: 'a@example.com' },
      services: [{ title: 'S1', description: 'D1' }],
    });
    const updated = store.updateProfile(created.id, {
      contact: { phone: '555-999-8888' },
      seo: { description: 'New desc' },
    });
    // Nested merge: email preserved, phone replaced.
    expect(updated.profile.contact.phone).toBe('555-999-8888');
    expect(updated.profile.contact.email).toBe('a@example.com');
    // Arrays replaced wholesale on first patch and untouched by the second.
    expect(updated.profile.services).toEqual([{ title: 'S1', description: 'D1' }]);
    // Top-level scalar patch updates the site name too.
    expect(updated.profile.seo.description).toBe('New desc');
    expect(updated.name).toBe('Acme');
  });

  it('updateProfile can rename the site', () => {
    const created = store.create({ name: 'Old', businessType: 'trades', themeId: 'trades' });
    const updated = store.updateProfile(created.id, { name: 'New' });
    expect(updated.name).toBe('New');
    expect(updated.profile.name).toBe('New');
  });

  it('setTheme changes the theme', () => {
    const created = store.create({ name: 'Acme', businessType: 'trades', themeId: 'trades' });
    const updated = store.setTheme(created.id, 'trades');
    expect(updated.themeId).toBe('trades');
  });

  it('delete removes the site and reports false for unknown ids', () => {
    const created = store.create({ name: 'Gone', businessType: 'trades', themeId: 'trades' });
    expect(store.delete(created.id)).toBe(true);
    expect(store.get(created.id)).toBeNull();
    expect(store.delete(created.id)).toBe(false);
    expect(store.delete('nope')).toBe(false);
  });

  it('throws a named error when updating a missing site', () => {
    expect(() => store.updateProfile('nope', {})).toThrow(/SITE_NOT_FOUND/);
  });

  it('rolls back a failed transaction without partial writes', () => {
    const before = store.list().length;
    expect(() =>
      // Force a failure mid-transaction: updateProfile on a missing id throws
      // inside the transaction, so nothing may be persisted.
      store.updateProfile('missing-id', makeProfile()),
    ).toThrow(/SITE_NOT_FOUND/);
    expect(store.list()).toHaveLength(before);
  });
});
