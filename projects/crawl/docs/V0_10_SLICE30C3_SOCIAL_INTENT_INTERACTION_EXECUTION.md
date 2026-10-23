# Crawl v0.10 - Slice 30C.3 Social Intent & Interaction Execution

## Status

**Canonical slice:** 30C.3 - Social Intent & Interaction Execution

**Exact accepted baseline:** `75d222c269befb81af65acb165638005193dfa49` (30C.2 accepted)

**Protocol:** `underreach.social-intent-execution.v1`

**Implementation version:** `30c3.1`

## Purpose

30C.1 established authoritative directed social relationship state.

30C.2 established event-linked social memory and deterministic relationship evolution.

30C.3 adds the authority membrane that allows a brain, future model provider, or other bounded social proposer to suggest an interaction without allowing that proposer to mutate canonical Crawl truth.

The authority flow is:

```text
Canonical Descent state
    |
    v
Bounded SocialObservation
    |
    v
Advisory SocialIntent
    |
    v
Deterministic validation
    |
    v
Simulation-owned execution
    |
    v
Canonical Ledger event(s)
    |
    v
30C.2 memory/relationship consequences where applicable
```

The proposer is advisory only.

## Authority boundary

The following remain true:

- the deterministic simulation owns canonical mutation;
- a social proposal cannot mutate state;
- a model/provider cannot mutate state;
- stale or impossible proposals are rejected without mutation;
- Unreal and presentation systems cannot mutate social truth;
- social interactions are Ledger bound;
- generated prose is not canonical social state;
- persistent parties, alliances, and leadership are not owned by this slice;
- rivalry/betrayal conflict execution is not owned by this slice;
- free-form dialogue remains Phase 31 work.

## Bounded social observation

A `SocialObservation` exposes only bounded canonical information needed for a later social proposer:

- Descender identity;
- current tick, Stratum, and Sector;
- active co-located Descenders;
- transferable ordinary item IDs;
- transferable survival-supply IDs;
- known Sector IDs;
- pending recruitment offers addressed to the Descender;
- current directed relationship values for co-located Descenders;
- social relationship-state digest;
- social memory-state digest;
- canonical state digest.

The observation receives its own deterministic digest.

A proposal is stale when its observation digest no longer matches the current canonical observation.

## SocialIntent contract

A `SocialIntent` is immutable and includes:

- deterministic proposal ID;
- provider ID;
- proposing Descender ID;
- observation digest;
- bounded action;
- action-specific target identifiers.

The proposal ID is derived from the proposal fields and is validated before execution.

## Bounded action vocabulary

30C.3 owns these initial actions:

### `share_item`

Transfer one owned non-survival item to a co-located active Descender.

The canonical item owner changes through the accepted item system.

The source interaction is recorded as `SHARED_RESOURCE`, which lets accepted 30C.2 create a real `shared_resource` memory and relationship consequences.

### `share_supply`

Transfer one owned 30A.4 survival supply to a co-located active Descender.

Supply identity and lifecycle remain owned by 30A.4. 30C.3 changes only the live canonical owner.

The resulting `SHARED_RESOURCE` event feeds 30C.2 memory just like other real resource sharing.

### `warn`

Share bounded canonical Sector knowledge with a co-located Descender.

A warning may only target a Sector actually known by the source Descender.

Second-hand knowledge is deterministic and confidence-bounded. It may merge:

- known neighbors;
- tags;
- hazard tags;
- believed-safe state;
- believed-exit state.

The receiver does not gain a fabricated visit count.

### `recruit`

Create a structured pending recruitment offer between co-located active Descenders.

This does **not** create a party.

### `accept_recruitment`

Resolve a pending recruitment offer as accepted.

This records canonical social agreement only.

It does **not** create a party or mutate `current_party_id`.

30C.4 owns persistent group formation.

### `refuse_recruitment`

Resolve a pending recruitment offer as refused.

No party mutation occurs.

### `challenge`

Create a structured, Ledger-bound challenge signal.

30C.3 deliberately does not start combat or mutate rivalry from the challenge alone.

30C.5 owns rivalry, betrayal, and social conflict behavior.

## Why generic help/protect actions are not fake events

The Phase 30C plan lists help/protect as candidate social actions, but 30C.3 does not record a `HEALED` or `PROTECTED` event unless a real canonical mechanic actually performs that outcome.

Concrete help in this slice is represented by real item/supply sharing and real warning/knowledge transfer.

This prevents a proposer from creating a false social memory merely by choosing an action label.

Later integration may add additional help/protect verbs once the deterministic gameplay operation they invoke is explicit.

## Recruitment offer state

Recruitment offers are stored inside the canonical 30C.3 metadata root.

Each offer includes:

- stable offer ID;
- source Descender;
- target Descender;
- status: `pending`, `accepted`, or `refused`;
- offered tick;
- resolved tick when applicable;
- offered Ledger event ID;
- resolved Ledger event ID when applicable;
- deterministic digest.

Only the addressed target may accept or refuse an offer.

A second pending offer from the same source to the same target is rejected.

## Validation membrane

Before execution the simulation independently rebuilds the current `SocialObservation`.

A proposal is rejected when, among other reasons:

- the Descent is not running;
- source is not active/current-Stratum;
- target is missing or inactive;
- source and target are not co-located;
- the observation is stale;
- a shared item is missing or no longer owned;
- an item/supply category does not match the action;
- a warning references unknown source knowledge;
- a recruitment offer is missing, resolved, or addressed to another Descender;
- a duplicate pending recruitment offer already exists.

Rejected proposals must not change:

- canonical state;
- canonical fingerprint;
- item ownership;
- knowledge;
- relationship state;
- memory state;
- recruitment state;
- Ledger history.

## Ledger events

30C.3 introduces or uses:

- `SOCIAL_INTENT_EXECUTION_INITIALIZED`
- `SOCIAL_INTENT_EXECUTED`
- `SOCIAL_WARNING_ISSUED`
- `SOCIAL_RECRUITMENT_OFFERED`
- `SOCIAL_RECRUITMENT_ACCEPTED`
- `SOCIAL_RECRUITMENT_REFUSED`
- `SOCIAL_CHALLENGE_ISSUED`
- `SHARED_RESOURCE` for real item/supply sharing

Every accepted interaction has one canonical interaction/source event plus one `SOCIAL_INTENT_EXECUTED` membrane event.

## 30C.2 integration

Real `SHARED_RESOURCE` interactions are immediately processed through the accepted 30C.2 social-memory service.

This means a successful share can create:

- a `shared_resource` memory in the receiver about the giver;
- increased trust;
- increased affection;
- increased gratitude;
- increased familiarity;
- canonical relationship/memory Ledger provenance.

Recruitment, warnings, and challenges do not fabricate a 30C.2 memory type when no accepted 30C.2 semantic rule exists for that fact.

## Persistence and checkpoint behavior

30C.3 state lives inside canonical `Descent.modifiers`, so existing persistence and alpha checkpoints carry:

- recruitment offers;
- interaction records;
- interaction event IDs;
- execution event IDs;
- execution count.

Restoring a checkpoint must reproduce the exact social-intent snapshot.

## Determinism expectations

Equivalent initial canonical state and the same proposal sequence must produce identical:

- proposal IDs;
- decisions;
- offer IDs;
- interaction event IDs;
- execution event IDs;
- ownership changes;
- shared knowledge;
- social-memory effects;
- relationship effects;
- final snapshot digests.

## Acceptance gate

30C.3 is accepted only when local validation proves:

1. all accepted 30A.1 through 30C.2 regressions pass;
2. proposal construction is side-effect free;
3. stale proposals reject without mutation;
4. impossible/non-colocated interactions reject without mutation;
5. ordinary item sharing changes real canonical ownership;
6. survival-supply sharing changes real canonical ownership without breaking 30A.4 validation;
7. sharing feeds accepted 30C.2 social memory and relationship evolution;
8. warnings transfer only bounded known canonical Sector information;
9. recruitment offers deterministically open and resolve;
10. accepted recruitment does not create a party;
11. challenges do not silently start combat or mutate rivalry;
12. persistence/checkpoint round trips are exact;
13. independent deterministic runs match;
14. the full repository regression suite passes;
15. the validator ends with explicit `[30C.3] PASS`.

## Next canonical slice

After 30C.3 acceptance, the next canonical slice is:

**30C.4 - Parties, Alliances & Leadership**

30C.4 may consume accepted recruitment/social state to create real persistent group structures, membership, leadership, and coordinated group behavior.
