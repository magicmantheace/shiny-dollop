import { describe, expect, it } from 'vitest';
import { DUNGEON_FIXTURE, WORLDBUILDING_FIXTURE, makeFixture } from './helpers.js';

async function setupCampaign(fx: ReturnType<typeof makeFixture>) {
  const campaign = await fx.service.campaignsCreate({
    name: 'Round Trip',
    setting: 'Bells and floodwater.',
    seed: 'rt-seed',
  });
  const session = await fx.service.sessionsCreate(campaign.id, { title: 'Session 1' });
  await fx.service.sessionsUpdateNotes(session.id, 'They rang the bell twice.');
  const hero = await fx.service.charactersCreate(campaign.id, {
    kind: 'pc',
    name: 'Wren',
    archetype: 'Scout',
    stats: { agility: 2 },
    hpMax: 12,
    inventory: ['lantern'],
  });
  await fx.service.diceRoll(campaign.id, { notation: '2d6+1', sessionId: session.id });
  await fx.service.memoryCreate(campaign.id, {
    kind: 'location',
    title: 'The Tollhouse',
    body: 'Sunk to its eaves.',
    tags: ['mire'],
  });
  return { campaign, session, hero };
}

describe('campaign export / import', () => {
  it('exports byte-identical bundles and round-trips into a fresh DB identically', async () => {
    const fx = makeFixture();
    const { campaign } = await setupCampaign(fx);
    const first = await fx.service.exportCampaign(campaign.id);
    const second = await fx.service.exportCampaign(campaign.id);
    expect(first).toBe(second);
    expect(JSON.parse(first).format).toBe('ai-dungeon-master/campaign');
    expect(JSON.parse(first).formatVersion).toBe('1.0.0');

    const fx2 = makeFixture();
    const imported = await fx2.service.importCampaign(first);
    expect(imported.id).toBe(campaign.id); // fresh DB: no collision, ids preserved
    const reexported = await fx2.service.exportCampaign(imported.id);
    expect(reexported).toBe(first);
  });

  it('remaps ids when importing into a DB that already holds the campaign', async () => {
    const fx = makeFixture();
    const { campaign } = await setupCampaign(fx);
    const text = await fx.service.exportCampaign(campaign.id);
    const copy = await fx.service.importCampaign(text);
    expect(copy.id).not.toBe(campaign.id);
    const copyLog = await fx.service.logList(copy.id);
    const origLog = await fx.service.logList(campaign.id);
    expect(copyLog.map((e) => e.text)).toEqual(origLog.map((e) => e.text));
    expect((await fx.service.charactersList(copy.id)).map((c) => c.name)).toEqual(['Wren']);
  });

  it('rejects corrupt and unknown-major campaign bundles with named errors', async () => {
    const fx = makeFixture();
    await expect(fx.service.importCampaign('not json')).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });
    await expect(
      fx.service.importCampaign(JSON.stringify({ format: 'other/format', formatVersion: '1.0.0' })),
    ).rejects.toMatchObject({ code: 'IMPORT_INVALID' });
    await expect(
      fx.service.importCampaign(
        JSON.stringify({
          format: 'ai-dungeon-master/campaign',
          formatVersion: '2.0.0',
          campaign: { id: 'x', name: 'X' },
          sessions: [],
          characters: [],
          encounters: [],
          memory: [],
          log: [],
        }),
      ),
    ).rejects.toMatchObject({ code: 'IMPORT_VERSION_UNSUPPORTED' });
    await expect(fx.service.importCampaign('x'.repeat(2_000_001))).rejects.toMatchObject({
      code: 'INPUT_TOO_LARGE',
    });
  });
});

describe('memory', () => {
  it('creates, updates, searches and deletes memory entries', async () => {
    const fx = makeFixture();
    const campaign = await fx.service.campaignsCreate({ name: 'Mem', seed: 'mem-seed' });
    const entry = await fx.service.memoryCreate(campaign.id, {
      kind: 'npc',
      title: 'Sella the Ferryman',
      body: 'Rows travelers across the Mire.',
      tags: ['mire', 'ferry'],
    });
    await fx.service.memoryCreate(campaign.id, {
      kind: 'fact',
      title: 'Bell Toll',
      body: 'The toll is one memory per crossing.',
    });
    expect((await fx.service.memorySearch(campaign.id, 'ferry')).map((m) => m.id)).toEqual([
      entry.id,
    ]);
    expect((await fx.service.memorySearch(campaign.id, 'MIRE')).map((m) => m.id)).toEqual([
      entry.id,
    ]);
    const updated = await fx.service.memoryUpdate(entry.id, { body: 'Retired last winter.' });
    expect(updated.body).toBe('Retired last winter.');
    await fx.service.memoryDelete(entry.id);
    expect(await fx.service.memoryList(campaign.id)).toHaveLength(1);
  });
});

describe('sibling contract imports', () => {
  it('imports a worldbuilding backup as NPC/location/fact memory entries', async () => {
    const fx = makeFixture();
    const campaign = await fx.service.campaignsCreate({ name: 'WB', seed: 'wb-seed' });
    const summary = await fx.service.importWorldbuilding(campaign.id, WORLDBUILDING_FIXTURE);
    expect(summary.createdMemoryEntries).toBe(3);
    const memory = await fx.service.memoryList(campaign.id);
    const byTitle = new Map(memory.map((m) => [m.title, m]));
    expect(byTitle.get('Sella the Ferryman')?.kind).toBe('npc');
    expect(byTitle.get('Sella the Ferryman')?.source).toBe('worldbuilding-import');
    expect(byTitle.get('Sella the Ferryman')?.body).toContain('guide');
    expect(byTitle.get('The Drowned Tollhouse')?.kind).toBe('location');
    expect(byTitle.get('The Lantern Court')?.kind).toBe('fact');
    const log = await fx.service.logList(campaign.id);
    expect(log.some((e) => e.kind === 'import')).toBe(true);
  });

  it('imports a dungeon manifest as a session location reference', async () => {
    const fx = makeFixture();
    const campaign = await fx.service.campaignsCreate({ name: 'DG', seed: 'dg-seed' });
    const summary = await fx.service.importDungeonManifest(campaign.id, DUNGEON_FIXTURE);
    expect(summary.createdMemoryEntries).toBe(1);
    const memory = await fx.service.memoryList(campaign.id);
    expect(memory).toHaveLength(1);
    expect(memory[0]?.kind).toBe('location');
    expect(memory[0]?.title).toBe('Sunken Crypt of Bells');
    expect(memory[0]?.body).toContain('Flooded Vault');
    expect(memory[0]?.body).toContain('Pale Warden');
    expect(memory[0]?.source).toBe('dungeon-import');
  });

  it('rejects unknown majors and wrong formats for both contract imports', async () => {
    const fx = makeFixture();
    const campaign = await fx.service.campaignsCreate({ name: 'Rej', seed: 'rej-seed' });
    const wb2 = JSON.stringify({
      format: 'worldbuilding-manager.project',
      formatVersion: '2.0.0',
      entities: [],
      links: [],
      revisions: [],
    });
    await expect(fx.service.importWorldbuilding(campaign.id, wb2)).rejects.toMatchObject({
      code: 'IMPORT_VERSION_UNSUPPORTED',
    });
    const dg2 = JSON.stringify({
      format: 'procedural-dungeon-designer/map',
      formatVersion: '9.1.0',
      name: 'X',
      map: { rooms: [] },
    });
    await expect(fx.service.importDungeonManifest(campaign.id, dg2)).rejects.toMatchObject({
      code: 'IMPORT_VERSION_UNSUPPORTED',
    });
    // Swapping the two formats must fail as IMPORT_INVALID.
    await expect(fx.service.importWorldbuilding(campaign.id, DUNGEON_FIXTURE)).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });
    await expect(
      fx.service.importDungeonManifest(campaign.id, WORLDBUILDING_FIXTURE),
    ).rejects.toMatchObject({ code: 'IMPORT_INVALID' });
    // Nothing was created by the rejected imports.
    expect(await fx.service.memoryList(campaign.id)).toHaveLength(0);
  });
});
