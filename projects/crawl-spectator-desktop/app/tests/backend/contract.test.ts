import { describe, expect, it } from 'vitest';
import {
  DescenderSchema,
  LedgerEventSchema,
  NOTABLE_PUBLIC_EVENT_TYPES,
  isHighlight,
  legacyEventType,
  parseContract,
  publicEventType,
} from '../../shared/contract';
import type { LedgerEvent } from '../../shared/contract';
import { SpectatorError } from '../../shared/errors';

const validDescender = {
  descender_id: 'mira-vane',
  status: 'active',
  health: 82,
  current_stratum: 3,
  current_sector_id: 'sector-ash-gate',
  current_party_id: null,
  current_objective: 'Reach the exit',
  level: 6,
  experience: 1840,
  specialization: 'pathfinder',
  abilities: ['survey'],
  kills: 4,
  encounters_survived: 11,
  injuries: [],
  inventory: [],
  equipment: {},
};

const validEvent: LedgerEvent = {
  id: 'evt-000001',
  descent_id: 'descent-1',
  stratum_number: 3,
  tick: 1200,
  event_type: 'DESCENDER_ADVANCED',
  summary: 'Advanced.',
  actor_ids: ['mira-vane'],
  sector_id: null,
  semantic: {
    importance_score: 0.5, rarity_score: 0.1, danger_level: 0.2, reversal: false,
    relationship_impact: 0, audience_interest_tags: [], causal_parent_ids: [],
  },
  canonical: true,
};

describe('contract schemas', () => {
  it('parses a valid descender and ledger event', () => {
    expect(parseContract(DescenderSchema, validDescender, 'descender').descender_id).toBe('mira-vane');
    expect(parseContract(LedgerEventSchema, validEvent, 'event').id).toBe('evt-000001');
  });

  it('rejects malformed payloads with FEED_CONTRACT_INVALID', () => {
    const badDescenders: unknown[] = [
      { ...validDescender, descender_id: undefined },
      { ...validDescender, health: 'high' },
      { ...validDescender, abilities: 'survey' },
      null,
    ];
    const badEvents: unknown[] = [
      { ...validEvent, id: '' },
      { ...validEvent, actor_ids: 'mira-vane' },
      { ...validEvent, semantic: undefined },
      'a string',
    ];
    for (const payload of badDescenders) {
      try {
        parseContract(DescenderSchema, payload, 'test');
        expect.unreachable('malformed descender was accepted');
      } catch (err) {
        expect(err).toBeInstanceOf(SpectatorError);
        expect((err as SpectatorError).code).toBe('FEED_CONTRACT_INVALID');
      }
    }
    for (const payload of badEvents) {
      try {
        parseContract(LedgerEventSchema, payload, 'test');
        expect.unreachable('malformed event was accepted');
      } catch (err) {
        expect(err).toBeInstanceOf(SpectatorError);
        expect((err as SpectatorError).code).toBe('FEED_CONTRACT_INVALID');
      }
    }
  });
});

describe('event vocabulary mapping', () => {
  it('maps stored legacy names to public names and back', () => {
    expect(publicEventType('CRAWLER_INJURED')).toBe('DESCENDER_INJURED');
    expect(publicEventType('FLOOR_DEADLINE_ELIMINATION')).toBe('STRATUM_DEADLINE_ELIMINATION');
    expect(publicEventType('CRAWL_STARTED')).toBe('DESCENT_STARTED');
    expect(publicEventType('ENCOUNTER_TRIGGERED')).toBe('ENCOUNTER_TRIGGERED');
    expect(legacyEventType('DESCENDER_DIED')).toBe('CRAWLER_DIED');
    expect(legacyEventType('STRATUM_DEADLINE_ELIMINATION')).toBe('FLOOR_DEADLINE_ELIMINATION');
    expect(legacyEventType(publicEventType('CRAWLER_ADVANCED'))).toBe('CRAWLER_ADVANCED');
  });

  it('the notable set is exactly the public projection of the server canonical set', () => {
    // Server-side canonical (stored) names from feed_api.py NOTABLE_FOLLOW_EVENT_TYPES.
    const canonicalStored = [
      'CRAWLER_DIED', 'CRAWLER_ELIMINATED', 'FLOOR_DEADLINE_ELIMINATION', 'CRAWLER_INJURED',
      'CRAWLER_DAMAGED', 'CRAWLER_ADVANCED', 'ENCOUNTER_TRIGGERED', 'ENCOUNTER_RESOLVED',
      'PARTY_FORMED', 'PARTY_DISSOLVED', 'ALLIANCE_FORMED', 'ALLIANCE_BETRAYAL',
      'SOCIAL_RELATIONSHIP_CHANGED',
    ];
    expect(new Set(canonicalStored.map(publicEventType))).toEqual(NOTABLE_PUBLIC_EVENT_TYPES);
  });
});

describe('isHighlight', () => {
  const followed = new Set(['mira-vane']);
  it('requires both a notable type and a followed actor', () => {
    expect(isHighlight(validEvent, followed)).toBe(true);
    expect(isHighlight({ ...validEvent, event_type: 'DESCENDER_MOVED' }, followed)).toBe(false);
    expect(isHighlight({ ...validEvent, actor_ids: ['someone-else'] }, followed)).toBe(false);
    expect(isHighlight(validEvent, new Set())).toBe(false);
  });
});
