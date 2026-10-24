# Feed API contract — as consumed by this client

Derived **read-only** from the public Underreach Feed API implementation on
the `crawl/roadmap-completion` lineage (PR #2 head commit `c7d809c`;
note: the remote branch ref itself was later reset to the rewritten-main
base `6088340`, so the PR head ref is the surviving pointer to that code):

- `projects/crawl/src/livingworld/feed_api.py` — routes (FastAPI, API version `0.8.0`)
- `projects/crawl/src/livingworld/feed_state.py` — public payload projections
- `projects/crawl/src/livingworld/underreach_terminology.py` — vocabulary mapping
- `projects/crawl/src/livingworld/spectator_state.py` — profile/social fields

No Crawl source is imported, copied, or modified by this project. Only the
public wire shapes below are re-declared (as zod schemas in
`app/shared/contract.ts`).

## Routes used (all GET)

| Route | Returns | Notes |
| --- | --- | --- |
| `GET /health` | `{status, world, service, descent_id, tick}` | liveness + current tick |
| `GET /api/feed/descent` | descent summary object | status, current_tick/stratum, counts, ruleset |
| `GET /api/feed/descenders?status&stratum_number&limit` | `Descender[]` | sorted by id; limit 1–500 (default 100) |
| `GET /api/feed/descenders/{id}` | `Descender` + `relationships`, `public_profile` | 404 when unknown |
| `GET /api/feed/descenders/{id}/ledger?limit` | `LedgerEvent[]` | that Descender's events; limit 1–1000 |
| `GET /api/feed/parties?active_only` | `Party[]` | `{id, active, leader_descender_id, member_descender_ids, cohesion, loot_policy}` |
| `GET /api/feed/ledger/events?limit&event_type&after_tick` | `LedgerEvent[]` | see cursor semantics |
| `GET /api/feed/search?q&limit` | `{query, descenders, events}` | q: 1–120 chars, non-whitespace (else 422) |

`Descender`: `{descender_id, status (active|fallen|eliminated|advanced),
health, current_stratum, current_sector_id, current_party_id,
current_objective, level, experience, specialization, abilities[], kills,
encounters_survived, injuries[], inventory[{id,name,category,rarity,stats}],
equipment{slot:item_id}}` (+ optional `public_profile`, `relationships[]`
`{target_id, trust, respect, rivalry, familiarity}` on the profile route).

`LedgerEvent`: `{id, descent_id, stratum_number, tick, event_type, summary,
actor_ids[], sector_id, semantic{importance_score, rarity_score,
danger_level, reversal, relationship_impact, audience_interest_tags[],
causal_parent_ids[]}, canonical: true}`.

## Cursor semantics (live + replay)

`ledger/events` returns events with `tick > after_tick`, sorted by
`(tick, id)`, keeping the **last** `limit`. The cursor is therefore
tick-granular: resuming with `after_tick = lastTick` could skip events that
share `lastTick`. This client resumes with `after_tick = max(0, lastTick - 1)`
and dedupes by canonical event ID, which yields no gaps and no duplicates.

## Event vocabulary

The Ledger stores legacy types; the Feed projects prefixes
`CRAWLER_ → DESCENDER_`, `FLOOR_ → STRATUM_`, `CRAWL_ → DESCENT_`. All
payloads this client receives already use public names. The
`event_type` filter on `ledger/events` accepts public names (the server
maps them back to stored names itself).

## Highlights definition

The server's session-scoped `GET /api/feed/notifications` returns notable
events for the one Descender a viewer session follows, using a canonical
notable-type set. This client computes highlights **locally** with the
public projection of exactly that set (13 types, listed in
`app/shared/contract.ts`): a highlight is a Ledger event whose `actor_ids`
include a locally followed Descender AND whose public `event_type` is in
the notable set.

## Explicitly NOT used (read-only guarantee)

The API also exposes `POST /api/feed/live/follow` and
`POST /api/feed/live/release` (presentation-session control). This client
never calls them — following is a local-only preference — and it never
issues any non-GET request. An integration test records every request
against the fixture server and asserts this.
