import { describe, expect, it } from 'vitest';
import { replayRoll } from '../../shared/dice.js';
import type { RollOutcome } from '../../shared/types.js';
import { makeFixture, reopen } from './helpers.js';

async function seedCampaign(fx: ReturnType<typeof makeFixture>) {
  const campaign = await fx.service.campaignsCreate({
    name: 'The Mire Campaign',
    setting: 'A flooded borderland.',
    seed: 'mire-seed',
  });
  const session = await fx.service.sessionsCreate(campaign.id, { title: 'Session 1' });
  const hero = await fx.service.charactersCreate(campaign.id, {
    kind: 'pc',
    name: 'Wren',
    archetype: 'Scout',
    stats: { agility: 2, wits: 1 },
    hpMax: 12,
    inventory: ['lantern', 'rope'],
  });
  const foe = await fx.service.charactersCreate(campaign.id, {
    kind: 'npc',
    name: 'Mire Hound',
    archetype: 'Beast',
    hpMax: 8,
  });
  return { campaign, session, hero, foe };
}

describe('campaigns, sessions, characters', () => {
  it('creates and lists campaigns, sessions and characters', async () => {
    const fx = makeFixture();
    const { campaign, session, hero } = await seedCampaign(fx);
    expect((await fx.service.campaignsList()).map((c) => c.id)).toContain(campaign.id);
    expect((await fx.service.sessionsList(campaign.id))[0]?.id).toBe(session.id);
    const chars = await fx.service.charactersList(campaign.id);
    expect(chars.map((c) => c.name)).toEqual(['Wren', 'Mire Hound']);
    expect(chars.find((c) => c.id === hero.id)?.inventory).toEqual(['lantern', 'rope']);
    const noted = await fx.service.sessionsUpdateNotes(session.id, 'The ferry is late.');
    expect(noted.notes).toBe('The ferry is late.');
    const ended = await fx.service.sessionsEnd(session.id);
    expect(ended.endedAt).not.toBeNull();
  });

  it('rejects invalid input with named errors', async () => {
    const fx = makeFixture();
    const { campaign } = await seedCampaign(fx);
    await expect(fx.service.campaignsCreate({ name: '' })).rejects.toMatchObject({
      code: 'INPUT_INVALID',
    });
    await expect(
      fx.service.charactersCreate(campaign.id, {
        kind: 'pc',
        name: 'Bad Stats',
        stats: { might: 99 },
      }),
    ).rejects.toMatchObject({ code: 'INPUT_INVALID' });
    await expect(
      fx.service.charactersCreate(campaign.id, { kind: 'pc', name: 'Zero', hpMax: 0 }),
    ).rejects.toMatchObject({ code: 'INPUT_INVALID' });
    await expect(fx.service.charactersList('nope')).rejects.toMatchObject({
      code: 'CAMPAIGN_NOT_FOUND',
    });
  });

  it('persists across a database reopen (save / resume)', async () => {
    const fx = makeFixture();
    const { campaign, hero } = await seedCampaign(fx);
    await fx.service.diceRoll(campaign.id, { notation: '2d6', label: 'before restart' });
    const stateBefore = (await fx.service.campaignsGet(campaign.id)).diceState;
    const resumed = reopen(fx);
    const after = await resumed.campaignsGet(campaign.id);
    expect(after.diceState).toBe(stateBefore);
    expect((await resumed.charactersList(campaign.id)).map((c) => c.id)).toContain(hero.id);
    const log = await resumed.logList(campaign.id);
    expect(log.some((e) => e.kind === 'roll')).toBe(true);
    // The dice stream continues seamlessly after the restart.
    const next = await resumed.diceRoll(campaign.id, { notation: '2d6' });
    expect(next.outcome.stateBefore).toBe(stateBefore);
  });
});

describe('dice and checks through the service', () => {
  it('logs every roll with a replayable breakdown and advances the stream', async () => {
    const fx = makeFixture();
    const { campaign, session } = await seedCampaign(fx);
    const first = await fx.service.diceRoll(campaign.id, {
      notation: '2d6+1',
      sessionId: session.id,
    });
    const second = await fx.service.diceRoll(campaign.id, { notation: '1d20' });
    expect(second.outcome.stateBefore).toBe(first.outcome.stateAfter);
    expect(replayRoll(first.outcome)).toBe(true);
    expect(replayRoll(second.outcome)).toBe(true);
    const log = await fx.service.logList(campaign.id);
    const rolls = log.filter((e) => e.kind === 'roll');
    expect(rolls).toHaveLength(2);
    const detail = rolls[0]?.detail as { outcome: RollOutcome };
    expect(detail.outcome.dice).toEqual(first.outcome.dice);
    // Log sequence is monotonic and append-only ordered.
    const seqs = log.map((e) => e.seq);
    expect(seqs).toEqual([...seqs].sort((a, b) => a - b));
    expect(new Set(seqs).size).toBe(seqs.length);
  });

  it('resolves attribute checks against the house difficulty table', async () => {
    const fx = makeFixture();
    const { campaign, hero } = await seedCampaign(fx);
    const res = await fx.service.checkRoll(campaign.id, {
      characterId: hero.id,
      attribute: 'agility',
      difficulty: 'standard',
    });
    expect(res.target).toBe(9);
    expect(res.outcome.modifier).toBe(2);
    expect(res.succeeded).toBe(res.outcome.total >= 9);
    const entry = (await fx.service.logList(campaign.id)).find((e) => e.kind === 'check');
    expect(entry?.text).toContain(res.succeeded ? 'SUCCESS' : 'FAILURE');
  });

  it('rejects bad dice notation through the service', async () => {
    const fx = makeFixture();
    const { campaign } = await seedCampaign(fx);
    await expect(
      fx.service.diceRoll(campaign.id, { notation: 'roll it' }),
    ).rejects.toMatchObject({ code: 'DICE_NOTATION_INVALID' });
  });

  it('two campaigns with the same seed roll identical sequences', async () => {
    const fx = makeFixture();
    const a = await fx.service.campaignsCreate({ name: 'A', seed: 'twin-seed' });
    const b = await fx.service.campaignsCreate({ name: 'B', seed: 'twin-seed' });
    const totalsA: number[] = [];
    const totalsB: number[] = [];
    for (let i = 0; i < 5; i++) {
      totalsA.push((await fx.service.diceRoll(a.id, { notation: '2d6' })).outcome.total);
      totalsB.push((await fx.service.diceRoll(b.id, { notation: '2d6' })).outcome.total);
    }
    expect(totalsA).toEqual(totalsB);
  });
});
