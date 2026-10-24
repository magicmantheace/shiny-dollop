import { describe, expect, it } from 'vitest';
import { replayRoll } from '../../shared/dice.js';
import type { RollOutcome } from '../../shared/types.js';
import { makeFixture, reopen } from './helpers.js';

async function setupCombat(fx: ReturnType<typeof makeFixture>) {
  const campaign = await fx.service.campaignsCreate({ name: 'Combat', seed: 'combat-seed' });
  const hero = await fx.service.charactersCreate(campaign.id, {
    kind: 'pc',
    name: 'Wren',
    stats: { agility: 3 },
    hpMax: 12,
  });
  const foe = await fx.service.charactersCreate(campaign.id, {
    kind: 'npc',
    name: 'Mire Hound',
    stats: { agility: 0 },
    hpMax: 8,
  });
  const slow = await fx.service.charactersCreate(campaign.id, {
    kind: 'npc',
    name: 'Old Gatekeeper',
    stats: { agility: -1 },
    hpMax: 6,
  });
  return { campaign, hero, foe, slow };
}

describe('encounters', () => {
  it('rolls logged initiative and orders the turn tracker', async () => {
    const fx = makeFixture();
    const { campaign, hero, foe, slow } = await setupCombat(fx);
    const encounter = await fx.service.encountersStart(campaign.id, {
      name: 'Ambush',
      characterIds: [foe.id, hero.id, slow.id],
    });
    expect(encounter.status).toBe('active');
    expect(encounter.round).toBe(1);
    expect(encounter.turnIndex).toBe(0);
    // Ordered by initiative total descending.
    const totals = encounter.combatants.map((c) => c.initiativeTotal);
    expect(totals).toEqual([...totals].sort((a, b) => b - a));
    // Every initiative roll is in the log with a replayable breakdown.
    const log = await fx.service.logList(campaign.id);
    const initRolls = log.filter(
      (e) => e.kind === 'roll' && (e.detail as { purpose?: string })?.purpose === 'initiative',
    );
    expect(initRolls).toHaveLength(3);
    for (const entry of initRolls) {
      expect(replayRoll((entry.detail as { outcome: RollOutcome }).outcome)).toBe(true);
    }
    expect(log.some((e) => e.kind === 'encounter' && e.text.includes('started'))).toBe(true);
  });

  it('advances turns and wraps into the next round', async () => {
    const fx = makeFixture();
    const { campaign, hero, foe } = await setupCombat(fx);
    const encounter = await fx.service.encountersStart(campaign.id, {
      name: 'Duel',
      characterIds: [hero.id, foe.id],
    });
    const t1 = await fx.service.encountersAdvanceTurn(encounter.id);
    expect(t1.turnIndex).toBe(1);
    expect(t1.round).toBe(1);
    const t2 = await fx.service.encountersAdvanceTurn(encounter.id);
    expect(t2.turnIndex).toBe(0);
    expect(t2.round).toBe(2);
  });

  it('applies damage and healing with HP clamping, all logged', async () => {
    const fx = makeFixture();
    const { campaign, hero, foe } = await setupCombat(fx);
    const encounter = await fx.service.encountersStart(campaign.id, {
      name: 'Brawl',
      characterIds: [hero.id, foe.id],
    });
    await fx.service.encountersApplyDamage(encounter.id, {
      characterId: foe.id,
      amount: 3,
      note: 'shortsword',
    });
    let chars = await fx.service.charactersList(campaign.id);
    expect(chars.find((c) => c.id === foe.id)?.hpCurrent).toBe(5);
    await fx.service.encountersApplyDamage(encounter.id, { characterId: foe.id, amount: 99 });
    chars = await fx.service.charactersList(campaign.id);
    expect(chars.find((c) => c.id === foe.id)?.hpCurrent).toBe(0);
    await fx.service.encountersApplyHeal(encounter.id, { characterId: foe.id, amount: 4 });
    chars = await fx.service.charactersList(campaign.id);
    expect(chars.find((c) => c.id === foe.id)?.hpCurrent).toBe(4);
    await fx.service.encountersApplyHeal(encounter.id, { characterId: foe.id, amount: 99 });
    chars = await fx.service.charactersList(campaign.id);
    expect(chars.find((c) => c.id === foe.id)?.hpCurrent).toBe(8); // clamped at max

    const log = await fx.service.logList(campaign.id);
    const damage = log.filter((e) => e.kind === 'damage');
    expect(damage).toHaveLength(2);
    expect(damage[0]?.text).toContain('HP 8 → 5');
    expect(log.filter((e) => e.kind === 'heal')).toHaveLength(2);
  });

  it('resumes an active encounter exactly after a restart', async () => {
    const fx = makeFixture();
    const { campaign, hero, foe } = await setupCombat(fx);
    const encounter = await fx.service.encountersStart(campaign.id, {
      name: 'Siege',
      characterIds: [hero.id, foe.id],
    });
    await fx.service.encountersAdvanceTurn(encounter.id);
    await fx.service.encountersApplyDamage(encounter.id, { characterId: hero.id, amount: 2 });

    const resumed = reopen(fx);
    const active = await resumed.encountersGetActive(campaign.id);
    expect(active?.id).toBe(encounter.id);
    expect(active?.turnIndex).toBe(1);
    expect(active?.round).toBe(1);
    expect(active?.combatants.map((c) => c.characterId)).toEqual(
      encounter.combatants.map((c) => c.characterId),
    );
    const heroAfter = (await resumed.charactersList(campaign.id)).find((c) => c.id === hero.id);
    expect(heroAfter?.hpCurrent).toBe(10);
  });

  it('refuses a second active encounter and actions on an ended one', async () => {
    const fx = makeFixture();
    const { campaign, hero, foe } = await setupCombat(fx);
    const encounter = await fx.service.encountersStart(campaign.id, {
      name: 'One',
      characterIds: [hero.id, foe.id],
    });
    await expect(
      fx.service.encountersStart(campaign.id, { name: 'Two', characterIds: [hero.id] }),
    ).rejects.toMatchObject({ code: 'INPUT_INVALID' });
    await fx.service.encountersEnd(encounter.id);
    await expect(fx.service.encountersAdvanceTurn(encounter.id)).rejects.toMatchObject({
      code: 'ENCOUNTER_NOT_ACTIVE',
    });
    await expect(
      fx.service.encountersApplyDamage(encounter.id, { characterId: foe.id, amount: 1 }),
    ).rejects.toMatchObject({ code: 'ENCOUNTER_NOT_ACTIVE' });
    expect(await fx.service.encountersGetActive(campaign.id)).toBeNull();
  });
});
