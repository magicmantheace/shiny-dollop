/**
 * Export pipeline tests: happy path writes, validation blocking, and
 * destination-directory guards.
 */
import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { openDb, type SiteStore } from '../../electron/main/db.js';
import { runExport, validateSiteExport } from '../../electron/main/exporter.js';
import { makeProfile } from './fixtures.js';

let tmp: string;
let store: SiteStore;

beforeEach(async () => {
  tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'bwg-export-'));
  store = openDb(path.join(tmp, 'test.sqlite'));
});

afterEach(async () => {
  store.close();
  await fs.rm(tmp, { recursive: true, force: true });
});

function createValidSite(themeId = 'trades', businessType: 'trades' | 'author' | 'restaurant' | 'localbiz' = 'trades') {
  const site = store.create({ name: 'Acme Test Co.', businessType, themeId });
  return store.updateProfile(site.id, makeProfile());
}

describe('runExport', () => {
  it('writes all files for a valid site and reports ok:true', async () => {
    const site = createValidSite();
    const dest = path.join(tmp, 'out');
    const result = await runExport({ store }, site.id, dest);

    expect(result.ok).toBe(true);
    expect(result.destDir).toBe(path.resolve(dest));
    expect(result.files).toEqual(
      expect.arrayContaining(['index.html', 'services.html', 'contact.html', 'style.css', 'sitemap.xml', 'robots.txt']),
    );
    expect(result.issues).toEqual([]);

    const index = await fs.readFile(path.join(dest, 'index.html'), 'utf8');
    expect(index).toContain('Acme Test Co.');
    const sitemap = await fs.readFile(path.join(dest, 'sitemap.xml'), 'utf8');
    expect(sitemap).toContain('<loc>');
    const robots = await fs.readFile(path.join(dest, 'robots.txt'), 'utf8');
    expect(robots).toContain('Sitemap:');
  });

  it('creates a non-existent destination directory', async () => {
    const site = createValidSite();
    const dest = path.join(tmp, 'nested', 'deep', 'out');
    const result = await runExport({ store }, site.id, dest);
    expect(result.ok).toBe(true);
    expect((await fs.stat(dest)).isDirectory()).toBe(true);
  });

  it('blocks export (ok:false, nothing written) when the profile is invalid', async () => {
    const site = store.create({ name: '', businessType: 'trades', themeId: 'trades' });
    const dest = path.join(tmp, 'blocked-out');
    const result = await runExport({ store }, site.id, dest);

    expect(result.ok).toBe(false);
    expect(result.files).toEqual([]);
    expect(result.issues.map((i) => i.code)).toContain('FIELD_REQUIRED:name');
    await expect(fs.stat(dest)).rejects.toThrow();
  });

  it('refuses a non-empty destination directory with a named error', async () => {
    const site = createValidSite();
    const dest = path.join(tmp, 'dirty');
    await fs.mkdir(dest, { recursive: true });
    await fs.writeFile(path.join(dest, 'existing.txt'), 'x');
    await expect(runExport({ store }, site.id, dest)).rejects.toThrow(/EXPORT_DEST_NOT_EMPTY/);
  });

  it('refuses a destination path that is an existing file', async () => {
    const site = createValidSite();
    const dest = path.join(tmp, 'afile.txt');
    await fs.writeFile(dest, 'x');
    await expect(runExport({ store }, site.id, dest)).rejects.toThrow(/EXPORT_DEST_NOT_DIR/);
  });

  it('throws SITE_NOT_FOUND for an unknown id', async () => {
    await expect(runExport({ store }, 'nope', path.join(tmp, 'out'))).rejects.toThrow(/SITE_NOT_FOUND/);
  });

  it('exports the restaurant theme with menu.html', async () => {
    const site = createValidSite('restaurant', 'restaurant');
    const dest = path.join(tmp, 'rest-out');
    const result = await runExport({ store }, site.id, dest);
    expect(result.ok).toBe(true);
    expect(result.files).toContain('menu.html');
    expect(result.files).not.toContain('services.html');
  });
});

describe('validateSiteExport', () => {
  it('returns ok:true with no issues for a valid site (dry run, writes nothing)', async () => {
    const site = createValidSite();
    const result = validateSiteExport({ store }, site.id);
    expect(result.ok).toBe(true);
    expect(result.issues).toEqual([]);
    expect(await fs.readdir(tmp)).not.toContain('out');
  });

  it('returns ok:false with issues for an invalid site', async () => {
    const site = store.create({ name: 'No Contact Co.', businessType: 'trades', themeId: 'trades' });
    const result = validateSiteExport({ store }, site.id);
    expect(result.ok).toBe(false);
    expect(result.issues.length).toBeGreaterThan(0);
  });
});
