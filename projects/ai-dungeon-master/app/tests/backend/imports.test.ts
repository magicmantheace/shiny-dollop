import { describe, expect, it } from 'vitest';
import { MAX_IMPORT_CHARS } from '../../shared/export.js';
import { importCampaignSchema } from '../../electron/main/schemas.js';
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

  it('rejects a bundle whose character has stats: null and writes nothing', async () => {
    const fx = makeFixture();
    const { campaign } = await setupCampaign(fx);
    const text = await fx.service.exportCampaign(campaign.id);
    const bundle = JSON.parse(text) as { characters: Array<Record<string, unknown>> };
    bundle.characters[0]!.stats = null;
    const fx2 = makeFixture();
    await expect(fx2.service.importCampaign(JSON.stringify(bundle))).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });
    // Validation happens before any write: the target DB stays empty.
    expect(await fx2.service.campaignsList()).toHaveLength(0);
  });

  it('rejects bundles with dangling references or out-of-range fields', async () => {
    const fx = makeFixture();
    const { campaign } = await setupCampaign(fx);
    const text = await fx.service.exportCampaign(campaign.id);

    // Encounter combatant pointing at a character that is not in the bundle.
    const dangling = JSON.parse(text) as {
      encounters: Array<Record<string, unknown>>;
      characters: Array<{ id: string }>;
    };
    // Build an encounter by hand referencing a ghost character.
    dangling.encounters = [
      {
        id: 'enc-ghost',
        campaignId: campaign.id,
        sessionId: null,
        name: 'Ghost fight',
        status: 'active',
        combatants: [
          {
            characterId: 'char-does-not-exist',
            name: 'Ghost',
            initiative: {
              notation: '2d6',
              spec: { count: 2, sides: 6, modifier: 0 },
              dice: [3, 4],
              modifier: 0,
              total: 7,
              stateBefore: 1,
              stateAfter: 2,
            },
            initiativeTotal: 7,
          },
        ],
        turnIndex: 0,
        round: 1,
        createdAt: '2026-10-23T00:00:00.000Z',
        endedAt: null,
      },
    ];
    await expect(fx.service.importCampaign(JSON.stringify(dangling))).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });

    // Stat outside the ruleset range (-2..+4).
    const badStat = JSON.parse(text) as { characters: Array<{ stats: Record<string, number> }> };
    badStat.characters[0]!.stats.might = 99;
    await expect(fx.service.importCampaign(JSON.stringify(badStat))).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });

    // Session belonging to a different campaign id.
    const foreign = JSON.parse(text) as { sessions: Array<{ campaignId: string }> };
    if (foreign.sessions[0]) foreign.sessions[0].campaignId = 'camp-other';
    await expect(fx.service.importCampaign(JSON.stringify(foreign))).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });

    // None of the rejected imports created a second copy of the campaign.
    expect(await fx.service.campaignsList()).toHaveLength(1);
  });

  it('round-trips an ended encounter whose combatant was deleted after it ended', async () => {
    const fx = makeFixture();
    const campaign = await fx.service.campaignsCreate({ name: 'Hist', seed: 'hist-seed' });
    const hero = await fx.service.charactersCreate(campaign.id, {
      kind: 'pc',
      name: 'Wren',
      hpMax: 12,
    });
    const foe = await fx.service.charactersCreate(campaign.id, {
      kind: 'npc',
      name: 'Mire Hound',
      hpMax: 8,
    });
    const encounter = await fx.service.encountersStart(campaign.id, {
      name: 'Ambush',
      characterIds: [hero.id, foe.id],
    });
    await fx.service.encountersEnd(encounter.id);
    // Deleting a former combatant is allowed once the encounter has ended.
    await fx.service.charactersDelete(foe.id);

    // The campaign's own export must remain importable: the ended
    // encounter is historical and may reference the deleted character.
    const text = await fx.service.exportCampaign(campaign.id);
    const fx2 = makeFixture();
    const imported = await fx2.service.importCampaign(text);
    expect((await fx2.service.charactersList(imported.id)).map((c) => c.name)).toEqual(['Wren']);
    // Re-exporting the imported campaign reproduces the bundle exactly.
    expect(await fx2.service.exportCampaign(imported.id)).toBe(text);
  });

  it('allows a hand-crafted ended encounter to reference a missing character, but not an active one', async () => {
    const fx = makeFixture();
    const { campaign } = await setupCampaign(fx);
    const text = await fx.service.exportCampaign(campaign.id);
    const ghostCombatant = {
      characterId: 'char-does-not-exist',
      name: 'Ghost',
      initiative: {
        notation: '2d6',
        spec: { count: 2, sides: 6, modifier: 0 },
        dice: [3, 4],
        modifier: 0,
        total: 7,
        stateBefore: 1,
        stateAfter: 2,
      },
      initiativeTotal: 7,
    };
    const ended = JSON.parse(text) as { encounters: Array<Record<string, unknown>> };
    ended.encounters = [
      {
        id: 'enc-ended-ghost',
        campaignId: campaign.id,
        sessionId: null,
        name: 'Old fight',
        status: 'ended',
        combatants: [ghostCombatant],
        turnIndex: 0,
        round: 1,
        createdAt: '2026-10-23T00:00:00.000Z',
        endedAt: '2026-10-23T01:00:00.000Z',
      },
    ];
    const fx2 = makeFixture();
    await expect(fx2.service.importCampaign(JSON.stringify(ended))).resolves.toMatchObject({
      id: campaign.id,
    });

    const active = JSON.parse(text) as { encounters: Array<Record<string, unknown>> };
    active.encounters = [
      {
        id: 'enc-active-ghost',
        campaignId: campaign.id,
        sessionId: null,
        name: 'Live fight',
        status: 'active',
        combatants: [ghostCombatant],
        turnIndex: 0,
        round: 1,
        createdAt: '2026-10-23T00:00:00.000Z',
        endedAt: null,
      },
    ];
    await expect(fx.service.importCampaign(JSON.stringify(active))).rejects.toMatchObject({
      code: 'IMPORT_INVALID',
    });
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
    await expect(fx.service.importCampaign('x'.repeat(MAX_IMPORT_CHARS + 1))).rejects.toMatchObject({
      code: 'INPUT_TOO_LARGE',
    });
  });

  it('restores a valid accumulated export larger than the old 2,000,000-char cap', async () => {
    const fx = makeFixture();
    const campaign = await fx.service.campaignsCreate({ name: 'Big', seed: 'big-seed' });
    // 21 memory entries with max-size (100,000-char) bodies — all data
    // produced by supported operations. Their export is 2,100,000+ chars
    // and was previously rejected as INPUT_TOO_LARGE by both the parser
    // and the IPC schema, leaving the backup unrestorable.
    const bigBody = 'x'.repeat(100_000);
    for (let i = 0; i < 21; i += 1) {
      await fx.service.memoryCreate(campaign.id, {
        kind: 'fact',
        title: `Accumulated note ${i + 1}`,
        body: bigBody,
      });
    }
    const text = await fx.service.exportCampaign(campaign.id);
    expect(text.length).toBeGreaterThan(2_000_000);
    // The IPC boundary must accept the same text the parser accepts.
    expect(importCampaignSchema.parse([text])[0]).toBe(text);

    const fx2 = makeFixture();
    const imported = await fx2.service.importCampaign(text);
    expect(await fx2.service.memoryList(imported.id)).toHaveLength(21);
    expect(await fx2.service.exportCampaign(imported.id)).toBe(text);
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
