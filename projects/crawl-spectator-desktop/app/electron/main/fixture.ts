// Deterministic synthetic Feed fixture — DEMO MODE data.
//
// Invented Descenders and events for the spectator's demo mode and tests.
// This is NOT real Underreach data and is never presented as such: the UI
// labels demo mode persistently. The shapes match the public Feed API
// contract exactly (see shared/contract.ts), and the same dataset backs the
// local fixture HTTP server (fixtureServer.ts) used by integration tests.
//
// Implements the same FeedSource surface as HttpFeedClient, mirroring the
// real server's filtering/ordering semantics:
// - descenders: sorted by id, optional status/stratum filters, limit slice
// - ledger/events: (tick, id) order, after_tick is exclusive, last `limit`
// - search: case-insensitive substring over descender ids and event
//   type/summary/actor ids

import { legacyEventType } from '../../shared/contract.js';
import type { DescentSummary, Descender, FeedHealth, LedgerEvent, Party, SearchResult } from '../../shared/contract.js';
import { SpectatorError } from '../../shared/errors.js';
import type { ReplayQuery } from '../../shared/types.js';
import type { FeedSource } from './feedClient.js';

export const FIXTURE_DESCENT_ID = 'descent-fixture-001';
export const FIXTURE_BASE_URL_LABEL = 'demo://fixture';

function sem(importance = 0.3, extra: Partial<LedgerEvent['semantic']> = {}): LedgerEvent['semantic'] {
  return {
    importance_score: importance,
    rarity_score: 0.1,
    danger_level: 0.2,
    reversal: false,
    relationship_impact: 0,
    audience_interest_tags: [],
    causal_parent_ids: [],
    ...extra,
  };
}

type DescenderSeed = Descender & { relationships: NonNullable<Descender['relationships']> };

const DESCENDERS: DescenderSeed[] = [
  {
    descender_id: 'mira-vane', status: 'active', health: 82, current_stratum: 3, current_sector_id: 'sector-ash-gate',
    current_party_id: 'party-ember-pact', current_objective: 'Reach the Stratum 3 exit', level: 6, experience: 1840,
    specialization: 'pathfinder', abilities: ['survey', 'steady-step'], kills: 4, encounters_survived: 11,
    injuries: [], inventory: [{ id: 'item-lantern-oil', name: 'Lantern Oil', category: 'consumable', rarity: 'common', stats: { uses: 2 } }],
    equipment: { main_hand: 'item-iron-pick' }, public_profile: { current_goal: 'Map the ash warrens', last_action: 'survey', decision_count: 57 },
    relationships: [
      { target_id: 'ossian-rell', trust: 0.8, respect: 0.7, rivalry: 0.1, familiarity: 0.9 },
      { target_id: 'selka-morrow', trust: 0.3, respect: 0.5, rivalry: 0.6, familiarity: 0.4 },
    ],
  },
  {
    descender_id: 'ossian-rell', status: 'active', health: 64, current_stratum: 3, current_sector_id: 'sector-ash-gate',
    current_party_id: 'party-ember-pact', current_objective: 'Guard the party flank', level: 6, experience: 1710,
    specialization: 'warden', abilities: ['shield-wall'], kills: 7, encounters_survived: 13,
    injuries: [{ kind: 'laceration', severity: 2 }], inventory: [], equipment: { main_hand: 'item-tower-shield' },
    public_profile: { current_goal: 'Keep Mira alive', last_action: 'shield-wall', decision_count: 49 },
    relationships: [{ target_id: 'mira-vane', trust: 0.9, respect: 0.8, rivalry: 0, familiarity: 0.9 }],
  },
  {
    descender_id: 'tamsin-okafor', status: 'active', health: 91, current_stratum: 3, current_sector_id: 'sector-bell-shrine',
    current_party_id: 'party-ember-pact', current_objective: 'Decipher the shrine inscription', level: 5, experience: 1425,
    specialization: 'runekeeper', abilities: ['read-runes', 'ward'], kills: 1, encounters_survived: 9,
    injuries: [], inventory: [{ id: 'item-chalk-bundle', name: 'Chalk Bundle', category: 'tool', rarity: 'common', stats: {} }],
    equipment: {}, public_profile: { current_goal: 'Decipher the shrine', last_action: 'read-runes', decision_count: 38 },
    relationships: [{ target_id: 'mira-vane', trust: 0.6, respect: 0.7, rivalry: 0.1, familiarity: 0.6 }],
  },
  {
    descender_id: 'brenn-ikar', status: 'active', health: 47, current_stratum: 2, current_sector_id: 'sector-flooded-steps',
    current_party_id: 'party-low-choir', current_objective: 'Find a refuge', level: 4, experience: 980,
    specialization: 'delver', abilities: ['swim'], kills: 2, encounters_survived: 8,
    injuries: [{ kind: 'sprain', severity: 1 }], inventory: [], equipment: {},
    public_profile: { current_goal: 'Dry ground', last_action: 'swim', decision_count: 31 },
    relationships: [{ target_id: 'issa-quill', trust: 0.5, respect: 0.4, rivalry: 0.2, familiarity: 0.5 }],
  },
  {
    descender_id: 'issa-quill', status: 'active', health: 73, current_stratum: 2, current_sector_id: 'sector-flooded-steps',
    current_party_id: 'party-low-choir', current_objective: 'Chart the flooded steps', level: 4, experience: 1010,
    specialization: 'cartographer', abilities: ['chart'], kills: 0, encounters_survived: 7,
    injuries: [], inventory: [], equipment: {},
    public_profile: { current_goal: 'Finish the chart', last_action: 'chart', decision_count: 27 },
    relationships: [{ target_id: 'brenn-ikar', trust: 0.6, respect: 0.5, rivalry: 0, familiarity: 0.6 }],
  },
  {
    descender_id: 'selka-morrow', status: 'active', health: 88, current_stratum: 4, current_sector_id: 'sector-glass-descent',
    current_party_id: null, current_objective: 'Descend alone', level: 7, experience: 2210,
    specialization: 'duelist', abilities: ['riposte', 'lunge'], kills: 9, encounters_survived: 15,
    injuries: [], inventory: [], equipment: { main_hand: 'item-glass-rapier' },
    public_profile: { current_goal: 'Reach Stratum 5 first', last_action: 'lunge', decision_count: 63 },
    relationships: [{ target_id: 'mira-vane', trust: 0.2, respect: 0.6, rivalry: 0.8, familiarity: 0.4 }],
  },
  {
    descender_id: 'dovran-pell', status: 'fallen', health: 0, current_stratum: 2, current_sector_id: 'sector-flooded-steps',
    current_party_id: null, current_objective: null, level: 3, experience: 640,
    specialization: 'delver', abilities: [], kills: 1, encounters_survived: 5,
    injuries: [{ kind: 'fatal', severity: 5 }], inventory: [], equipment: {},
    public_profile: { current_goal: null, last_action: null, decision_count: 19 },
    relationships: [],
  },
  {
    descender_id: 'ren-vasquez', status: 'eliminated', health: 12, current_stratum: 1, current_sector_id: 'sector-entry-hall',
    current_party_id: null, current_objective: null, level: 2, experience: 310,
    specialization: 'scavenger', abilities: [], kills: 0, encounters_survived: 2,
    injuries: [], inventory: [], equipment: {},
    public_profile: { current_goal: null, last_action: null, decision_count: 11 },
    relationships: [],
  },
];

const PARTIES: Party[] = [
  { id: 'party-ember-pact', active: true, leader_descender_id: 'mira-vane', member_descender_ids: ['mira-vane', 'ossian-rell', 'tamsin-okafor'], cohesion: 0.82, loot_policy: 'need_before_greed' },
  { id: 'party-low-choir', active: true, leader_descender_id: 'brenn-ikar', member_descender_ids: ['brenn-ikar', 'issa-quill'], cohesion: 0.64, loot_policy: 'round_robin' },
];

// [tick, event_type, actor_ids, sector_id, summary]
const HISTORY_SCRIPT: ReadonlyArray<readonly [number, string, string[], string | null, string]> = [
  [1180, 'DESCENT_STARTED', [], 'sector-entry-hall', 'The Descent began with 8 Descenders.'],
  [1184, 'PARTY_FORMED', ['mira-vane', 'ossian-rell', 'tamsin-okafor'], 'sector-entry-hall', 'Mira Vane formed the Ember Pact.'],
  [1189, 'PARTY_FORMED', ['brenn-ikar', 'issa-quill'], 'sector-entry-hall', 'Brenn Ikar formed the Low Choir.'],
  [1193, 'ENCOUNTER_TRIGGERED', ['mira-vane', 'ossian-rell'], 'sector-ash-gate', 'An ash wraith ambushed the Ember Pact.'],
  [1196, 'DESCENDER_DAMAGED', ['ossian-rell'], 'sector-ash-gate', 'Ossian Rell was damaged by an ash wraith.'],
  [1199, 'ENCOUNTER_RESOLVED', ['mira-vane', 'ossian-rell', 'tamsin-okafor'], 'sector-ash-gate', 'The Ember Pact drove off the ash wraith.'],
  [1202, 'DESCENDER_ADVANCED', ['selka-morrow'], 'sector-glass-descent', 'Selka Morrow advanced to Stratum 4.'],
  [1205, 'SOCIAL_RELATIONSHIP_CHANGED', ['selka-morrow', 'mira-vane'], null, 'Selka Morrow\'s rivalry with Mira Vane deepened.'],
  [1208, 'ENCOUNTER_TRIGGERED', ['brenn-ikar', 'issa-quill'], 'sector-flooded-steps', 'Something stirred beneath the flooded steps.'],
  [1211, 'DESCENDER_INJURED', ['brenn-ikar'], 'sector-flooded-steps', 'Brenn Ikar was injured in a collapse.'],
  [1214, 'DESCENDER_DIED', ['dovran-pell'], 'sector-flooded-steps', 'Dovran Pell fell in the flooded steps.'],
  [1217, 'DESCENDER_ELIMINATED', ['ren-vasquez'], 'sector-entry-hall', 'Ren Vasquez was eliminated at the Stratum 1 deadline.'],
  [1221, 'DESCENDER_ADVANCED', ['mira-vane', 'ossian-rell', 'tamsin-okafor'], 'sector-ash-gate', 'The Ember Pact advanced to Stratum 3.'],
  [1226, 'ENCOUNTER_TRIGGERED', ['tamsin-okafor'], 'sector-bell-shrine', 'The bell shrine tolled on its own.'],
  [1231, 'DESCENDER_DAMAGED', ['mira-vane'], 'sector-bell-shrine', 'Mira Vane was damaged by a falling bell clapper.'],
  [1236, 'ENCOUNTER_RESOLVED', ['tamsin-okafor'], 'sector-bell-shrine', 'Tamsin Okafor silenced the bell shrine.'],
  [1240, 'DESCENDER_ADVANCED', ['brenn-ikar', 'issa-quill'], 'sector-flooded-steps', 'The Low Choir reached Stratum 2\'s refuge.'],
];

// [event_type, actor_ids, sector_id, summary]
const LIVE_SCRIPT: ReadonlyArray<readonly [string, string[], string | null, string]> = [
  ['DESCENDER_DAMAGED', ['ossian-rell'], 'sector-ash-gate', 'Ossian Rell was damaged by falling ash.'],
  ['ENCOUNTER_TRIGGERED', ['mira-vane', 'ossian-rell'], 'sector-ash-gate', 'A cinder hound stalked the Ember Pact.'],
  ['ENCOUNTER_RESOLVED', ['mira-vane', 'ossian-rell', 'tamsin-okafor'], 'sector-ash-gate', 'The Ember Pact scattered the cinder hound.'],
  ['SOCIAL_RELATIONSHIP_CHANGED', ['mira-vane', 'selka-morrow'], null, 'Mira Vane sent a challenge marker to Selka Morrow.'],
  ['DESCENDER_INJURED', ['issa-quill'], 'sector-flooded-steps', 'Issa Quill was injured by a submerged trap.'],
  ['DESCENDER_ADVANCED', ['selka-morrow'], 'sector-glass-descent', 'Selka Morrow pushed deeper into the glass descent.'],
];

function makeEvent(seq: number, tick: number, type: string, actors: string[], sector: string | null, summary: string): LedgerEvent {
  return {
    id: `evt-${String(seq).padStart(6, '0')}`,
    descent_id: FIXTURE_DESCENT_ID,
    stratum_number: 3,
    tick,
    event_type: type,
    summary,
    actor_ids: [...actors],
    sector_id: sector,
    semantic: sem(0.4),
    canonical: true,
  };
}

function stripSocial(d: DescenderSeed): Descender {
  const copy: Descender = {
    ...d,
    inventory: d.inventory.map((i) => ({ ...i, stats: { ...i.stats } })),
    abilities: [...d.abilities],
    injuries: d.injuries.map((i) => ({ ...i })),
    equipment: { ...d.equipment },
  };
  delete copy.relationships;
  return copy;
}

export class FixtureFeed implements FeedSource {
  private readonly descenderSeeds: DescenderSeed[] = DESCENDERS.map((d) => ({ ...d, relationships: d.relationships.map((r) => ({ ...r })) }));
  private readonly partiesData: Party[] = PARTIES.map((p) => ({ ...p, member_descender_ids: [...p.member_descender_ids] }));
  private events: LedgerEvent[] = HISTORY_SCRIPT.map(([tick, type, actors, sector, summary], i) => makeEvent(i + 1, tick, type, actors, sector, summary));
  private nextSeq = HISTORY_SCRIPT.length + 1;
  private liveIndex = 0;
  private currentTick = 1240;

  /** Advance the fixture's live edge by one scripted event (demo liveness).
   *  Deterministic: depends only on how many times it has been called. */
  advance(): LedgerEvent {
    const [type, actors, sector, summary] = LIVE_SCRIPT[this.liveIndex % LIVE_SCRIPT.length]!;
    this.liveIndex += 1;
    this.currentTick += 1;
    const event = makeEvent(this.nextSeq, this.currentTick, type, actors, sector, summary);
    this.nextSeq += 1;
    this.events.push(event);
    return event;
  }

  async health(): Promise<FeedHealth> {
    return { status: 'ok', world: 'The Underreach', service: 'The Feed', descent_id: FIXTURE_DESCENT_ID, tick: this.currentTick };
  }

  async descent(): Promise<DescentSummary> {
    return {
      id: FIXTURE_DESCENT_ID, world: 'The Underreach', competition: 'The Descent', broadcast: 'The Feed',
      record: 'The Ledger', status: 'active', current_tick: this.currentTick, current_stratum: 3, stratum_count: 5,
      starting_descender_count: 8, surviving_descender_count: 6, eliminated_descender_count: 2,
      ruleset_id: 'underreach-alpha', ruleset_version: '1.0.0',
    };
  }

  async descenders(params: { status?: string; stratumNumber?: number; limit?: number } = {}): Promise<Descender[]> {
    let rows = [...this.descenderSeeds].sort((a, b) => a.descender_id.localeCompare(b.descender_id));
    if (params.status !== undefined) rows = rows.filter((d) => d.status === params.status!.toLowerCase());
    if (params.stratumNumber !== undefined) rows = rows.filter((d) => d.current_stratum === params.stratumNumber);
    return rows.slice(0, params.limit ?? 100).map(stripSocial);
  }

  async descender(descenderId: string): Promise<Descender> {
    const found = this.descenderSeeds.find((d) => d.descender_id === descenderId);
    if (!found) throw new SpectatorError('FEED_NOT_FOUND', `Descender "${descenderId}" was not found in the fixture feed.`);
    return { ...stripSocial(found), relationships: found.relationships.map((r) => ({ ...r })) };
  }

  async descenderLedger(descenderId: string, limit = 200): Promise<LedgerEvent[]> {
    if (!this.descenderSeeds.some((d) => d.descender_id === descenderId)) {
      throw new SpectatorError('FEED_NOT_FOUND', `Descender "${descenderId}" was not found in the fixture feed.`);
    }
    return this.events.filter((e) => e.actor_ids.includes(descenderId)).slice(0, limit).map((e) => ({ ...e }));
  }

  async parties(activeOnly = true): Promise<Party[]> {
    return this.partiesData.filter((p) => !activeOnly || p.active).map((p) => ({ ...p, member_descender_ids: [...p.member_descender_ids] }));
  }

  async ledgerEvents(query: ReplayQuery = {}): Promise<LedgerEvent[]> {
    const limit = query.limit ?? 100;
    let rows = [...this.events];
    if (query.eventType) {
      const wanted = legacyEventType(query.eventType);
      rows = rows.filter((e) => legacyEventType(e.event_type) === wanted);
    }
    if (query.afterTick !== undefined && query.afterTick !== null) {
      rows = rows.filter((e) => e.tick > query.afterTick!);
    }
    rows.sort((a, b) => a.tick - b.tick || a.id.localeCompare(b.id));
    return rows.slice(-limit).map((e) => ({ ...e, actor_ids: [...e.actor_ids] }));
  }

  async search(query: string, limit = 25): Promise<SearchResult> {
    const needle = query.trim().toLowerCase();
    if (!needle) throw new SpectatorError('INPUT_INVALID', 'Search query must contain non-whitespace characters.');
    const descenders = [...this.descenderSeeds]
      .sort((a, b) => a.descender_id.localeCompare(b.descender_id))
      .filter((d) => d.descender_id.toLowerCase().includes(needle))
      .slice(0, limit)
      .map(stripSocial);
    const events = this.events
      .filter((e) => e.event_type.toLowerCase().includes(needle) || e.summary.toLowerCase().includes(needle) || e.actor_ids.some((a) => a.toLowerCase().includes(needle)))
      .sort((a, b) => a.tick - b.tick || a.id.localeCompare(b.id))
      .slice(0, limit)
      .map((e) => ({ ...e }));
    return { query, descenders, events };
  }

  /** All events, for tests/server bookkeeping. */
  allEvents(): LedgerEvent[] {
    return this.events.map((e) => ({ ...e }));
  }
}
