// Typed contract for the public Underreach Feed API.
//
// Derived read-only from the Feed API implementation on the
// `crawl/roadmap-completion` lineage (PR #2 head `c7d809c`,
// `projects/crawl/src/livingworld/feed_api.py` + `feed_state.py` +
// `underreach_terminology.py`). No crawl source is imported or copied;
// only the public wire shapes are re-declared here as zod schemas.
//
// Routes used by this client (all GET — the client is strictly read-only):
//   GET /health
//   GET /api/feed/descent
//   GET /api/feed/descenders?status&stratum_number&limit
//   GET /api/feed/descenders/{id}
//   GET /api/feed/descenders/{id}/ledger?limit
//   GET /api/feed/parties?active_only
//   GET /api/feed/ledger/events?limit&event_type&after_tick
//   GET /api/feed/search?q&limit
//
// The server also exposes POST /api/feed/live/follow and
// POST /api/feed/live/release (presentation-session control). This client
// NEVER calls them: following is a local-only preference here.
//
// Event vocabulary: the Ledger stores legacy types (`CRAWLER_*`, `FLOOR_*`,
// `CRAWL_*`); the Feed projects them to public names (`DESCENDER_*`,
// `STRATUM_*`, `DESCENT_*`). Everything this client receives already uses
// public names. When filtering `ledger/events?event_type=`, the server maps
// the public name back to the stored name itself.

import { z } from 'zod';
import { SpectatorError } from './errors.js';

export const FEED_API_VERSION = '0.8.0';
export const MAX_RESPONSE_BYTES = 2_000_000;

// ---------------------------------------------------------------------------
// Vocabulary mapping (mirrors underreach_terminology.py prefix rules)
// ---------------------------------------------------------------------------

const PUBLIC_PREFIXES: ReadonlyArray<readonly [string, string]> = [
  ['CRAWLER_', 'DESCENDER_'],
  ['FLOOR_', 'STRATUM_'],
  ['CRAWL_', 'DESCENT_'],
];

/** Stored (legacy) event type -> public Feed name. */
export function publicEventType(eventType: string): string {
  const value = String(eventType).toUpperCase();
  for (const [legacy, pub] of PUBLIC_PREFIXES) {
    if (value.startsWith(legacy)) return pub + value.slice(legacy.length);
  }
  return value;
}

/** Public Feed name -> stored (legacy) event type. */
export function legacyEventType(eventType: string): string {
  const value = String(eventType).toUpperCase();
  for (const [legacy, pub] of PUBLIC_PREFIXES) {
    if (value.startsWith(pub)) return legacy + value.slice(pub.length);
  }
  return value;
}

/**
 * Canonical event types considered notable for a followed Descender.
 * This is the public-name projection of the server's
 * NOTABLE_FOLLOW_EVENT_TYPES set (feed_api.py), which the server applies
 * to its session-scoped /api/feed/notifications endpoint. This client
 * computes highlights locally from the Ledger with exactly this set:
 * a highlight is an event whose `actor_ids` include a followed Descender
 * AND whose public `event_type` is in this set.
 */
export const NOTABLE_PUBLIC_EVENT_TYPES: ReadonlySet<string> = new Set([
  'DESCENDER_DIED',
  'DESCENDER_ELIMINATED',
  'STRATUM_DEADLINE_ELIMINATION',
  'DESCENDER_INJURED',
  'DESCENDER_DAMAGED',
  'DESCENDER_ADVANCED',
  'ENCOUNTER_TRIGGERED',
  'ENCOUNTER_RESOLVED',
  'PARTY_FORMED',
  'PARTY_DISSOLVED',
  'ALLIANCE_FORMED',
  'ALLIANCE_BETRAYAL',
  'SOCIAL_RELATIONSHIP_CHANGED',
]);

// ---------------------------------------------------------------------------
// Wire schemas (feed_state.py projections)
// ---------------------------------------------------------------------------

const SemanticSchema = z.looseObject({
  importance_score: z.number(),
  rarity_score: z.number(),
  danger_level: z.number(),
  reversal: z.boolean(),
  relationship_impact: z.number(),
  audience_interest_tags: z.array(z.string()),
  causal_parent_ids: z.array(z.string()),
});

export const LedgerEventSchema = z.looseObject({
  id: z.string().min(1),
  descent_id: z.string(),
  stratum_number: z.number(),
  tick: z.number(),
  event_type: z.string().min(1),
  summary: z.string(),
  actor_ids: z.array(z.string()),
  sector_id: z.string().nullable(),
  semantic: SemanticSchema,
  canonical: z.boolean(),
});
export type LedgerEvent = z.infer<typeof LedgerEventSchema>;

const InventoryItemSchema = z.looseObject({
  id: z.string(),
  name: z.string(),
  category: z.string(),
  rarity: z.string(),
  stats: z.record(z.string(), z.unknown()),
});

const RelationshipSchema = z.looseObject({
  target_id: z.string(),
  trust: z.number(),
  respect: z.number(),
  rivalry: z.number(),
  familiarity: z.number(),
});
export type Relationship = z.infer<typeof RelationshipSchema>;

export const DescenderSchema = z.looseObject({
  descender_id: z.string().min(1),
  status: z.string().min(1),
  health: z.number(),
  current_stratum: z.number(),
  current_sector_id: z.string().nullable(),
  current_party_id: z.string().nullable(),
  current_objective: z.string().nullable(),
  level: z.number(),
  experience: z.number(),
  specialization: z.string().nullable(),
  abilities: z.array(z.string()),
  kills: z.number(),
  encounters_survived: z.number(),
  injuries: z.array(z.record(z.string(), z.unknown())),
  inventory: z.array(InventoryItemSchema),
  equipment: z.record(z.string(), z.string()),
  public_profile: z
    .looseObject({
      current_goal: z.string().nullable(),
      last_action: z.string().nullable(),
      decision_count: z.number(),
    })
    .optional(),
  relationships: z.array(RelationshipSchema).optional(),
});
export type Descender = z.infer<typeof DescenderSchema>;

export const HealthSchema = z.looseObject({
  status: z.string(),
  world: z.string(),
  service: z.string(),
  descent_id: z.string(),
  tick: z.number(),
});
export type FeedHealth = z.infer<typeof HealthSchema>;

export const DescentSchema = z.looseObject({
  id: z.string(),
  world: z.string(),
  competition: z.string(),
  broadcast: z.string(),
  record: z.string(),
  status: z.string(),
  current_tick: z.number(),
  current_stratum: z.number(),
  stratum_count: z.number(),
  starting_descender_count: z.number(),
  surviving_descender_count: z.number(),
  eliminated_descender_count: z.number(),
  ruleset_id: z.string(),
  ruleset_version: z.string(),
});
export type DescentSummary = z.infer<typeof DescentSchema>;

export const PartySchema = z.looseObject({
  id: z.string(),
  active: z.boolean(),
  leader_descender_id: z.string().nullable(),
  member_descender_ids: z.array(z.string()),
  cohesion: z.number(),
  loot_policy: z.string(),
});
export type Party = z.infer<typeof PartySchema>;

export const SearchResultSchema = z.looseObject({
  query: z.string(),
  descenders: z.array(DescenderSchema),
  events: z.array(LedgerEventSchema),
});
export type SearchResult = z.infer<typeof SearchResultSchema>;

export const DescenderListSchema = z.array(DescenderSchema);
export const LedgerEventListSchema = z.array(LedgerEventSchema);
export const PartyListSchema = z.array(PartySchema);

// ---------------------------------------------------------------------------
// Validation helper — one place that turns zod failures into a named error.
// ---------------------------------------------------------------------------

export function parseContract<T>(schema: z.ZodType<T>, payload: unknown, what: string): T {
  const result = schema.safeParse(payload);
  if (!result.success) {
    const first = result.error.issues[0];
    const where = first ? `${first.path.join('.') || '(root)'}: ${first.message}` : 'unknown issue';
    throw new SpectatorError(
      'FEED_CONTRACT_INVALID',
      `The Feed API returned a ${what} payload that does not match the expected contract (${where}). ` +
        'The server version may have changed; no data was accepted.',
    );
  }
  return result.data;
}

/** True when an event is a highlight for the given followed-id set. */
export function isHighlight(event: LedgerEvent, followed: ReadonlySet<string>): boolean {
  if (!NOTABLE_PUBLIC_EVENT_TYPES.has(event.event_type)) return false;
  return event.actor_ids.some((id) => followed.has(id));
}
