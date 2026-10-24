import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { WorldStore } from '../../db/world';
import { AppError } from '../../shared/errors';

let store: WorldStore;

beforeEach(() => {
  store = new WorldStore(':memory:');
});
afterEach(() => store.close());

function seed() {
  const hero = store.createEntity({
    type: 'character', name: 'Sera Vane', role: 'protagonist',
    description: 'A tide-cartographer of the Salt Reaches.',
    body: 'Sera charts drowned roads and owes the Lantern Court a favour.',
    tags: ['hero'], bornOrder: 10, diedOrder: 90,
  });
  const city = store.createEntity({
    type: 'location', name: 'Port Sorrow', description: 'A harbour city built on a drowned cathedral.',
    tags: ['harbour'],
  });
  const faction = store.createEntity({ type: 'faction', name: 'Lantern Court', description: 'Keepers of the harbour lights.' });
  const arrival = store.createEntity({
    type: 'event', name: 'Arrival at Port Sorrow', storyDate: 'Year 3, First Tide', orderKey: 40,
    description: 'Sera reaches the city.',
  });
  const note = store.createEntity({
    type: 'note', name: 'Chapter 4 outline', body: 'Sera confronts the Lantern Court at the drowned cathedral.',
    tags: ['outline'],
  });
  return { hero, city, faction, arrival, note };
}

describe('entity CRUD per type', () => {
  it('creates and reads back every entity type with persisted fields', () => {
    const { hero, city, faction, arrival, note } = seed();
    expect(store.getEntity(hero.id)?.role).toBe('protagonist');
    expect(store.getEntity(city.id)?.tags).toEqual(['harbour']);
    expect(store.getEntity(faction.id)?.type).toBe('faction');
    expect(store.getEntity(arrival.id)?.storyDate).toBe('Year 3, First Tide');
    expect(store.getEntity(note.id)?.body).toContain('Lantern Court');
    expect(store.listEntities()).toHaveLength(5);
    expect(store.listEntities('character')).toHaveLength(1);
  });

  it('updates fields and persists the change', () => {
    const { hero } = seed();
    const updated = store.updateEntity(hero.id, { name: 'Sera Vane the Younger', description: 'Renamed.' });
    expect(updated.name).toBe('Sera Vane the Younger');
    expect(store.getEntity(hero.id)?.description).toBe('Renamed.');
  });

  it('rejects empty names and unknown types as VALIDATION_ERROR', () => {
    expect(() => store.createEntity({ type: 'character', name: '  ' })).toThrowError(
      expect.objectContaining({ code: 'VALIDATION_ERROR' }),
    );
    expect(() => store.createEntity({ type: 'dragon' as never, name: 'X' })).toThrowError(
      expect.objectContaining({ code: 'VALIDATION_ERROR' }),
    );
  });

  it('rejects oversized input', () => {
    expect(() => store.createEntity({ type: 'note', name: 'Big', body: 'x'.repeat(200_001) })).toThrowError(
      expect.objectContaining({ code: 'VALIDATION_ERROR' }),
    );
    expect(() => store.createEntity({ type: 'note', name: 'Big', tags: Array(21).fill('t') })).toThrowError(
      expect.objectContaining({ code: 'VALIDATION_ERROR' }),
    );
  });

  it('updating a missing entity is ENTITY_NOT_FOUND', () => {
    expect(() => store.updateEntity('nope', { name: 'X' })).toThrowError(
      expect.objectContaining({ code: 'ENTITY_NOT_FOUND' }),
    );
  });

  it('persists across a database reopen', () => {
    const dir = mkdtempSync(join(tmpdir(), 'wbm-'));
    const path = join(dir, 'world.sqlite');
    try {
      const a = new WorldStore(path);
      const c = a.createEntity({ type: 'character', name: 'Persistent Pia' });
      a.close();
      const b = new WorldStore(path);
      expect(b.getEntity(c.id)?.name).toBe('Persistent Pia');
      b.close();
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('links and relationships', () => {
  it('links are bidirectional in views and survive a rename', () => {
    const { hero, city } = seed();
    store.addLink(hero.id, city.id, 'lives-in');
    const fromHero = store.linksForEntity(hero.id);
    const fromCity = store.linksForEntity(city.id);
    expect(fromHero).toHaveLength(1);
    expect(fromHero[0]?.entity.name).toBe('Port Sorrow');
    expect(fromHero[0]?.direction).toBe('outgoing');
    expect(fromCity).toHaveLength(1);
    expect(fromCity[0]?.entity.name).toBe('Sera Vane');
    expect(fromCity[0]?.direction).toBe('incoming');
    store.updateEntity(city.id, { name: 'Port Sorrow Renamed' });
    expect(store.linksForEntity(hero.id)[0]?.entity.name).toBe('Port Sorrow Renamed');
  });

  it('character relationships carry their label on both sheets', () => {
    const rival = store.createEntity({ type: 'character', name: 'Captain Morvain' });
    const { hero } = seed();
    store.addLink(hero.id, rival.id, 'rival');
    expect(store.linksForEntity(rival.id)[0]?.label).toBe('rival');
    expect(store.linksForEntity(hero.id).some((l) => l.label === 'rival')).toBe(true);
  });

  it('deleting an entity cleans up its links — no dangling references', () => {
    const { hero, city, arrival } = seed();
    store.addLink(hero.id, city.id, 'lives-in');
    store.addLink(arrival.id, hero.id, 'features');
    store.deleteEntity(hero.id);
    expect(store.listLinks()).toHaveLength(0);
    expect(store.linksForEntity(city.id)).toHaveLength(0);
    expect(store.linksForEntity(arrival.id)).toHaveLength(0);
  });

  it('removeLink deletes exactly one link', () => {
    const { hero, city } = seed();
    const link = store.addLink(hero.id, city.id, 'lives-in');
    expect(store.removeLink(link.id)).toBe(true);
    expect(store.listLinks()).toHaveLength(0);
    expect(store.removeLink(link.id)).toBe(false);
  });

  it('rejects self-links and links to missing entities', () => {
    const { hero } = seed();
    expect(() => store.addLink(hero.id, hero.id)).toThrowError(expect.objectContaining({ code: 'SELF_LINK' }));
    expect(() => store.addLink(hero.id, 'ghost')).toThrowError(expect.objectContaining({ code: 'ENTITY_NOT_FOUND' }));
  });
});

describe('timeline and continuity', () => {
  it('orders events by order key, keyless events last', () => {
    store.createEntity({ type: 'event', name: 'Late', orderKey: 50 });
    store.createEntity({ type: 'event', name: 'Early', orderKey: 5 });
    store.createEntity({ type: 'event', name: 'Keyless' });
    store.createEntity({ type: 'event', name: 'Middle', orderKey: 20 });
    expect(store.timeline().map((e) => e.name)).toEqual(['Early', 'Middle', 'Late', 'Keyless']);
  });

  it('warns when a linked event happens after a character death', () => {
    const { hero } = seed(); // diedOrder 90
    const ghost = store.createEntity({ type: 'event', name: 'Sera at the Siege', orderKey: 120 });
    store.addLink(ghost.id, hero.id, 'features');
    const warnings = store.continuityWarnings();
    expect(warnings).toHaveLength(1);
    expect(warnings[0]?.code).toBe('EVENT_AFTER_DEATH');
    expect(warnings[0]?.characterName).toBe('Sera Vane');
  });

  it('warns when a linked event happens before a character birth', () => {
    const { hero } = seed(); // bornOrder 10
    const early = store.createEntity({ type: 'event', name: 'Sera as a Child', orderKey: 2 });
    store.addLink(early.id, hero.id, 'features');
    const warnings = store.continuityWarnings();
    expect(warnings.map((w) => w.code)).toEqual(['EVENT_BEFORE_BIRTH']);
  });

  it('no warning for in-lifetime events or unlinked events', () => {
    const { hero, arrival } = seed(); // arrival orderKey 40, hero alive 10..90
    store.addLink(arrival.id, hero.id, 'features');
    const orphan = store.createEntity({ type: 'event', name: 'Unlinked Late Event', orderKey: 500 });
    expect(orphan.orderKey).toBe(500);
    expect(store.continuityWarnings()).toHaveLength(0);
  });
});

describe('search', () => {
  it('finds text across names, descriptions and bodies', () => {
    seed();
    expect(store.search('cartographer').map((e) => e.name)).toEqual(['Sera Vane']);
    expect(store.search('cathedral').map((e) => e.name).sort()).toEqual(['Chapter 4 outline', 'Port Sorrow']);
    expect(store.search('nonexistentword')).toHaveLength(0);
    expect(store.search('   ')).toHaveLength(0);
  });

  it('respects the type filter', () => {
    seed();
    expect(store.search('Lantern', 'faction').map((e) => e.name)).toEqual(['Lantern Court']);
    expect(store.search('Lantern', 'location')).toHaveLength(0);
  });
});

describe('revisions', () => {
  it('records an append-only revision per create and update', () => {
    const { hero } = seed();
    expect(store.listRevisions(hero.id)).toHaveLength(1);
    store.updateEntity(hero.id, { description: 'Second version.' });
    store.updateEntity(hero.id, { description: 'Third version.' });
    const revs = store.listRevisions(hero.id);
    expect(revs.map((r) => r.revNo)).toEqual([1, 2, 3]);
    expect(revs[1]?.snapshot.description).toBe('Second version.');
    expect(revs[2]?.snapshot.description).toBe('Third version.');
  });
});

describe('backup export / import', () => {
  it('round-trips a full project into a fresh database, byte-identical', () => {
    const { hero, city, arrival } = seed();
    store.addLink(hero.id, city.id, 'lives-in');
    store.addLink(arrival.id, hero.id, 'features');
    store.updateEntity(hero.id, { description: 'Revised before export.' });
    const json = store.exportBundle();
    const fresh = new WorldStore(':memory:');
    try {
      const result = fresh.importBundle(json);
      expect(result.entities).toBe(5);
      expect(result.links).toBe(2);
      expect(result.revisions).toBeGreaterThanOrEqual(5);
      expect(fresh.exportBundle()).toBe(json);
      expect(fresh.linksForEntity(hero.id).map((l) => l.entity.name)).toEqual(['Arrival at Port Sorrow', 'Port Sorrow']);
    } finally {
      fresh.close();
    }
  });

  it('exports a human-readable Markdown document', () => {
    const { hero, city } = seed();
    store.addLink(hero.id, city.id, 'lives-in');
    const md = store.exportMarkdown();
    expect(md).toContain('# Worldbuilding project export');
    expect(md).toContain('### Sera Vane');
    expect(md).toContain('Port Sorrow');
    expect(md).toContain('lives-in');
  });

  it('rejects corrupt, wrong-format and unknown-major backups with named errors', () => {
    expect(() => store.importBundle('{not json')).toThrowError(expect.objectContaining({ code: 'IMPORT_INVALID' }));
    expect(() => store.importBundle(JSON.stringify({ format: 'other.app', formatVersion: '1.0.0', entities: [], links: [], revisions: [] })))
      .toThrowError(expect.objectContaining({ code: 'IMPORT_INVALID' }));
    expect(() => store.importBundle(JSON.stringify({
      format: 'worldbuilding-manager.project', formatVersion: '2.0.0', entities: [], links: [], revisions: [],
    }))).toThrowError(expect.objectContaining({ code: 'IMPORT_VERSION_UNSUPPORTED' }));
    expect(() => store.importBundle('x'.repeat(10 * 1024 * 1024 + 1))).toThrowError(
      expect.objectContaining({ code: 'IMPORT_TOO_LARGE' }),
    );
  });

  it('rejects a backup whose links dangle', () => {
    const { hero } = seed();
    const bundle = JSON.parse(store.exportBundle()) as Record<string, unknown>;
    bundle.links = [{ id: 'l1', sourceId: hero.id, targetId: 'ghost', label: '', createdAt: '2026-01-01T00:00:00.000Z' }];
    expect(() => store.importBundle(JSON.stringify(bundle))).toThrowError(
      expect.objectContaining({ code: 'IMPORT_INVALID' }),
    );
    // Failed import must not have wiped the existing project.
    expect(store.listEntities()).toHaveLength(5);
  });

  it('AppError is the thrown type for engine failures', () => {
    try {
      store.createEntity({ type: 'character', name: '' });
      expect.unreachable();
    } catch (err) {
      expect(err).toBeInstanceOf(AppError);
    }
  });
});
