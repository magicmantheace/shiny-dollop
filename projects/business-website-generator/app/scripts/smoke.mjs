#!/usr/bin/env node
/**
 * Backend smoke test: builds on dist/, then exercises the real pipeline —
 * open DB → create site → fill profile → validate → export → verify files.
 * Run with: npm run smoke
 */
import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';

const { openDb } = await import('../dist/electron/main/db.js');
const { runExport, validateSiteExport } = await import('../dist/electron/main/exporter.js');
const { listThemes } = await import('../dist/electron/main/themes/index.js');

const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'bwg-smoke-'));
const store = openDb(path.join(tmp, 'smoke.sqlite'));

try {
  console.log('themes:', listThemes().map((t) => t.id).join(', '));

  const site = store.create({ name: 'Smoke Test Plumbing', businessType: 'trades', themeId: 'trades' });
  store.updateProfile(site.id, {
    tagline: 'We fix leaks fast.',
    about: 'A synthetic smoke-test business.',
    contact: { phone: '555-010-0000', email: 'smoke@example.com', address: '1 Smoke Way' },
    hours: { label: 'Hours', lines: ['Mon–Fri: 8am–6pm'] },
    services: [{ title: 'Leak repair', description: 'We find and fix leaks.' }],
    seo: { title: 'Smoke Test Plumbing', description: 'Synthetic smoke-test site.' },
  });

  const check = validateSiteExport({ store }, site.id);
  console.log('validate ok:', check.ok, '| issues:', check.issues.length);
  if (!check.ok) throw new Error('smoke validation failed: ' + JSON.stringify(check.issues));

  const dest = path.join(tmp, 'site');
  const result = await runExport({ store }, site.id, dest);
  console.log('export ok:', result.ok, '| files:', result.files.length);
  if (!result.ok) throw new Error('smoke export failed');

  for (const rel of ['index.html', 'services.html', 'contact.html', 'style.css', 'sitemap.xml', 'robots.txt']) {
    await fs.access(path.join(dest, rel));
  }
  const index = await fs.readFile(path.join(dest, 'index.html'), 'utf8');
  if (!index.includes('Smoke Test Plumbing')) throw new Error('business name missing from index.html');

  console.log('SMOKE PASS:', dest);
} finally {
  store.close();
  await fs.rm(tmp, { recursive: true, force: true });
}
