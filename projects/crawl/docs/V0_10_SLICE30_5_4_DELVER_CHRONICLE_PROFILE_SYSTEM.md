# Underreach v0.10 — Phase 30.5 Slice 4

## Delver Chronicle & Profile System

Status: implementation candidate; local validation required before acceptance.

Protocol: `underreach.delver-chronicle-profile.v1`

Implementation version: `30.5.4`

Accepted baseline: 30.5.3 — Highlight & Story-Arc Detection.

Next canonical slice on acceptance: **30.5.5 — Narrative Claim Manifest & Fact Verification**.

---

## Purpose

30.5.4 turns accepted presentation-safe canonical history into durable Delver profile and Chronicle structures.

This slice does **not** generate public prose. It establishes the persistent biography substrate that later narrative workers may consume only after 30.5.5 provides claim-manifest and fact-verification controls.

The governing flow is:

```text
Deterministic Crawl Simulation
        ↓
Canonical Ledger / state
        ↓
30.5.1 MediaEnvelope
        ↓
30.5.2 Media SQLite
        ↓
30.5.3 MediaHighlight + MediaStoryArc
        ↓
30.5.4 DelverProfile + ChronicleChapter
```

Everything below the MediaEnvelope remains presentation-only.

---

## Authority boundary

The following are frozen:

- the deterministic simulation remains the only authority for gameplay truth;
- 30.5.4 opens and writes only the separate media database;
- canonical Crawl persistence is never mutated by profile/Chronicle processing;
- no profile field may write back to canonical identity, health, inventory, equipment, position, progression, party, alliance, relationship, memory, combat, or Ledger history;
- no generated prose is accepted in 30.5.4;
- no provider is invoked;
- no Unreal process is invoked;
- no cloud or paid API is required;
- reprocessing identical inputs is idempotent;
- restart/reopen of the media SQLite file cannot duplicate profiles or chapters.

Snapshot contract:

```text
authoritative = false
canonical_owner = deterministic_simulation
presentation_can_mutate_simulation = false
generated_prose_used = false
claim_verification_required_before_prose = true
unreal_dependency = false
provider_invocation_used = false
```

---

## Durable media records

30.5.4 adds two media-owned tables:

```text
media_delver_profiles
media_chronicle_chapters
```

They are created through separate 30.5.4 SQLAlchemy metadata and live on the same non-authoritative media engine established by 30.5.2.

No 30.5.4 table exists in the canonical Crawl database.

---

## DelverProfile

One deterministic profile exists per:

```text
crawl_id + delver_id
```

Profile identity is stable and does not depend on processing order.

The profile stores only presentation-safe information supported by MediaEnvelope context:

- stable Crawl and Delver IDs;
- public/display name only when one is actually present in accepted context;
- current status: `ACTIVE`, `RETREATED`, or `DEAD`;
- current Stratum;
- current Sector;
- current party ID;
- active alliance IDs visible through accepted party context;
- bounded known allies derived from directed canonical relationship values;
- bounded known rivals derived from directed canonical relationship values;
- notable equipped or important owned items visible in MediaEnvelope context;
- optional presentation-identity reference when one exists;
- latest canonical media tick/envelope represented by the current-state fields;
- cumulative envelope/event provenance;
- deterministic Chronicle chapter IDs;
- pending quiet-history envelope IDs;
- terminal Chronicle closure state;
- policy digest.

If accepted canonical data does not include a public name or presentation identity, the profile leaves those fields empty. 30.5.4 never invents them.

---

## Directed ally and rival derivation

Relationship summaries are deterministic and read only from `MediaEnvelope.social_context.relationships`.

For the profile owner as the directed source:

- ally strength may come from positive trust, respect, affection, or gratitude;
- rival strength may come from resentment, rivalry, fear, or negative trust;
- configurable thresholds decide whether a relationship is surfaced;
- ties are resolved by stable Delver ID;
- output is bounded by policy.

The profile does not create or mutate a canonical relationship edge.

---

## Current party and alliance context

Current party identity comes from the accepted participant context in the newest represented envelope.

Alliance IDs are surfaced only when the accepted 30.5.1 party context contains an active alliance record containing that party.

No inferred or generated alliance is permitted.

---

## Notable equipment

30.5.4 surfaces only items present in MediaEnvelope item/equipment context.

The initial bounded rule includes:

- equipped item IDs;
- important items owned by the Delver;
- accepted presentation-safe item name/category/rarity/slot metadata when present.

Unknown metadata remains unknown. The profile never fabricates equipment detail.

---

## ChronicleChapter

A Chronicle chapter is an immutable structured biography record. It is not final narrative prose.

Every chapter contains:

- deterministic chapter ID;
- profile/Crawl/Delver identity;
- chapter kind;
- deterministic title code;
- canonical tick;
- source MediaEnvelope IDs;
- source canonical event IDs;
- supporting allowed-fact IDs;
- optional persisted highlight ID;
- story-arc IDs;
- deterministic trigger codes;
- terminal flag;
- `structured_only = true`;
- `claim_verification_required = true`;
- `generated_prose_used = false`;
- `presentation_can_mutate_simulation = false`.

The same immutable chapter identity resolving to a different payload is a hard failure.

---

## Chapter kinds

### `highlight`

Created when an envelope already has an accepted persisted 30.5.3 `MediaHighlight`.

One structured chapter is created for each participating Delver profile.

The chapter inherits:

- highlight ID;
- highlight reason codes;
- output tier trigger;
- relevant story arcs;
- event/fact provenance.

### `quiet_recap`

Archive-only events can still be meaningful canonical history.

If an archive-only envelope participates in a 30.5.3 story arc, the Delver profile may accumulate it as pending quiet history.

Once `quiet_recap_min_envelopes` is reached, those pending envelopes are collapsed into one deterministic structured quiet-recap chapter and the pending set is cleared.

This threshold is policy-controlled and deterministic.

A highlight or terminal event clears pending quiet history so a later quiet recap does not silently span across a major chapter boundary.

### `terminal`

A terminal death/elimination or accepted retreated status creates a terminal chapter.

Terminal chapters close the Chronicle permanently:

```text
DEAD      -> chronicle_closed = true
RETREATED -> chronicle_closed = true
```

A closed profile cannot return to `ACTIVE` merely because an older or duplicate envelope is reprocessed.

---

## Current-state update ordering

Profile current-state fields are updated only by the latest represented `(export_tick, envelope_id)`.

Processing older envelopes later may add missing provenance or immutable chapters, but it cannot roll back current profile state.

Once the Chronicle is terminally closed, later/non-terminal presentation inputs cannot reopen it or replace terminal status.

---

## Idempotency and deterministic identity

Profile ID:

```text
stable(crawl_id, delver_id)
```

Chapter ID:

```text
stable(profile_id, chapter_kind, highlight_id-or-none, normalized source envelope IDs)
```

Consequences:

- repeated processing does not duplicate a profile;
- repeated highlight processing does not duplicate a chapter;
- SQLite restart/reopen retains exact identities;
- input order is normalized by `(export_tick, envelope_id)` in batch processing;
- equivalent independent runs produce equivalent semantic snapshots.

---

## Generated prose boundary

30.5.4 intentionally stops at structured biography data.

It does **not** create:

- Chronicle paragraphs;
- profile biographies;
- dialogue;
- captions;
- interviews;
- narration;
- promotional copy.

The structured chapter already contains the allowed-fact provenance required by the next slice.

30.5.5 must establish claim manifests and deterministic verification before generated prose may be treated as review-ready narrative.

---

## Local-first / paid API rule

30.5.4 invokes no provider at all.

Therefore:

```text
local model required = false
cloud model required = false
paid provider required = false
provider execution records created = false
```

Later local narrative generation may use the 30.5.2 provider router, but that does not belong to this slice.

---

## Focused validation

The focused suite must prove:

1. a persisted high-signal highlight creates one structured Chronicle chapter for every participating Delver;
2. profile state surfaces accepted party/alliance and directed ally/rival context;
3. terminal death closes the Chronicle and creates a terminal chapter;
4. configurable quiet-history batching creates one deterministic quiet recap;
5. repeat processing is idempotent;
6. `process_many` normalizes input order;
7. Chronicle tables exist only in the media database and canonical state/Ledger remain unchanged;
8. file-backed SQLite reopen preserves exact profiles/chapters and duplicate processing remains stable.

---

## Deterministic proof

The acceptance proof must include all three biography paths:

```text
high-signal highlight -> structured highlight chapters
archive-only Stratum history -> quiet recap chapter
death -> terminal chapter + closed Chronicle
```

It must also prove:

- public-safe party/alliance context;
- directed ally and rival surfacing;
- supporting allowed-fact provenance on every chapter;
- no generated prose;
- no media jobs;
- no provider invocation;
- exact media snapshot after SQLite reopen;
- exact media snapshot after duplicate reprocessing;
- unchanged canonical state/fingerprint/history/Ledger rows;
- deterministic proof reproduction across two independent runs.

---

## Acceptance gate

Local acceptance requires the PowerShell validator to finish with exactly:

```text
[30.5.4] PASS
```

Until that line is observed, 30.5.4 is not accepted.

---

## On acceptance

Accepted 30.5.4 means Crawl has a durable, restart-safe, deterministic living-biography substrate without giving generated narrative authority over canonical truth.

The next frozen development slice is:

**30.5.5 — Narrative Claim Manifest & Fact Verification**

That slice may introduce structured prose claims and verification, but it must preserve the same one-way authority boundary.
