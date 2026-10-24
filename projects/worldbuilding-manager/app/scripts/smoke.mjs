/**
 * Backend smoke test: exercises the compiled engine (dist/) end-to-end —
 * the MVP acceptance workflow — against a real on-disk SQLite database.
 * Run `npm run build` first, then `npm run smoke`. No Electron window.
 */
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { WorldStore } from '../dist/db/world.js';

function assert(cond, label) {
  if (!cond) {
    console.error(`SMOKE FAIL: ${label}`);
    process.exit(1);
  }
  console.log(`smoke ok: ${label}`);
}

const dir = mkdtempSync(join(tmpdir(), 'wbm-smoke-'));
try {
  const store = new WorldStore(join(dir, 'world.sqlite'));
  const hero = store.createEntity({
    type: 'character', name: 'Sera Vane', role: 'protagonist',
    description: 'A tide-cartographer.', bornOrder: 10, diedOrder: 90, tags: ['hero'],
  });
  const city = store.createEntity({ type: 'location', name: 'Port Sorrow', description: 'A drowned harbour city.' });
  const event = store.createEntity({ type: 'event', name: 'Arrival at Port Sorrow', orderKey: 40, storyDate: 'Year 3, First Tide' });
  store.createEntity({ type: 'note', name: 'Chapter 4 outline', body: 'Sera confronts the Lantern Court at Port Sorrow.' });
  store.addLink(hero.id, city.id, 'lives-in');
  store.addLink(event.id, hero.id, 'features');
  assert(store.linksForEntity(city.id).length === 1, 'character linked to location, visible from both sides');
  assert(store.timeline().map((e) => e.name).join() === 'Arrival at Port Sorrow', 'timeline event ordered');
  assert(store.search('Lantern Court').length === 1, 'search finds the note by body text');
  assert(store.continuityWarnings().length === 0, 'no continuity warning for an in-lifetime event');
  const json = store.exportBundle();
  store.close();

  const restored = new WorldStore(join(dir, 'restored.sqlite'));
  const result = restored.importBundle(json);
  assert(result.entities === 4 && result.links === 2, 'backup import restores entities and links');
  assert(restored.exportBundle() === json, 'restored project re-exports byte-identically');
  assert(restored.exportMarkdown().includes('Port Sorrow'), 'markdown export covers the project');
  restored.close();
  console.log('SMOKE PASS: MVP acceptance workflow green');
} finally {
  rmSync(dir, { recursive: true, force: true });
}
