/**
 * MVP acceptance walkthrough — full end-to-end run against the real engine.
 * Restaurant site (exercises menu sections): create → fill profile →
 * validate → export → verify files, links, no external assets, determinism.
 * Synthetic fixture data only.
 */
import { createHash } from 'node:crypto';
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
  tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'bwg-accept-'));
  store = openDb(path.join(tmp, 'test.sqlite'));
});

afterEach(async () => {
  store.close();
  await fs.rm(tmp, { recursive: true, force: true });
});

function sha(b: string | Buffer): string {
  return createHash('sha256').update(b).digest('hex');
}

describe('MVP acceptance: restaurant site end-to-end', () => {
  it('choose type → fill profile → preview pages → export deployable folder', async () => {
    // 1. Choose a business type + theme.
    const created = store.create({ name: 'Hearth & Crumb', businessType: 'restaurant', themeId: 'restaurant' });
    expect(created.themeId).toBe('restaurant');

    // 2. Fill contact / services / menu / SEO.
    const site = store.updateProfile(
      created.id,
      makeProfile({
        name: 'Hearth & Crumb',
        tagline: 'Wood-fired comfort food.',
        contact: {
          phone: '555-019-2834',
          email: 'hello@hearthcrumb.example.com',
          address: '42 Oven Street, Testville',
          website: 'https://hearthcrumb.example.com',
        },
      }),
    );
    expect(site.profile.menuSections.length).toBeGreaterThan(0);

    // 3. Validation is clean.
    const validation = validateSiteExport({ store }, site.id);
    expect(validation.ok).toBe(true);
    expect(validation.issues).toEqual([]);

    // 4. Export a deployable static folder.
    const dest = path.join(tmp, 'site');
    const result = await runExport({ store }, site.id, dest);
    expect(result.ok).toBe(true);
    for (const f of ['index.html', 'menu.html', 'contact.html', 'style.css', 'sitemap.xml', 'robots.txt']) {
      expect(result.files).toContain(f);
      expect((await fs.stat(path.join(dest, f))).isFile()).toBe(true);
    }

    // 5. Every internal link resolves to an exported file.
    const pages = ['index.html', 'menu.html', 'contact.html'];
    const hrefs = new Set<string>();
    for (const p of pages) {
      const html = await fs.readFile(path.join(dest, p), 'utf8');
      for (const m of html.matchAll(/href="([^"#]+)"/g)) {
        const href = m[1];
        if (!/^(https?:|mailto:|tel:)/.test(href)) hrefs.add(href);
      }
      // SEO + accessibility markers present on every page.
      expect(html).toContain('<title>');
      expect(html).toContain('name="description"');
      expect(html).toContain('skip');
      expect(html).toContain('<main');
    }
    for (const href of hrefs) {
      expect(result.files, `broken link ${href}`).toContain(href);
    }

    // 6. No third-party hosted assets (no external scripts, styles, images, fonts).
    for (const p of [...pages, 'style.css']) {
      const body = await fs.readFile(path.join(dest, p), 'utf8');
      expect(body, `${p} references external script`).not.toMatch(/<script[^>]+src="https?:/);
      expect(body, `${p} references external asset`).not.toMatch(/(src|href)="https?:[^"]*\.(png|jpe?g|gif|svg|webp|woff2?|ttf)"/);
      expect(body, `${p} uses @import`).not.toContain('@import');
    }

    // 7. Determinism: second export is byte-identical.
    const dest2 = path.join(tmp, 'site2');
    const result2 = await runExport({ store }, site.id, dest2);
    expect(result2.ok).toBe(true);
    for (const f of result.files) {
      const a = await fs.readFile(path.join(dest, f));
      const b = await fs.readFile(path.join(dest2, f));
      expect(sha(a), `non-deterministic file ${f}`).toBe(sha(b));
    }

    // 8. Export is blocked when a required field goes missing — nothing written.
    store.updateProfile(site.id, { name: '' });
    const bad = validateSiteExport({ store }, site.id);
    expect(bad.ok).toBe(false);
    expect(bad.issues.some((i) => i.code.startsWith('FIELD_REQUIRED'))).toBe(true);
    const dest3 = path.join(tmp, 'site3');
    const blocked = await runExport({ store }, site.id, dest3);
    expect(blocked.ok).toBe(false);
    await expect(fs.stat(dest3)).rejects.toThrow();
  });
});
