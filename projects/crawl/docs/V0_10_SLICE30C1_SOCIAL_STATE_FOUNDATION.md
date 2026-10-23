# Crawl v0.10 — Slice 30C.1 Social State Foundation

## Status

**Phase:** 30C — Social Intelligence

**Slice:** 30C.1 — Social State Foundation

**Baseline:** `df62d4be0e67485dbc82c2d6c7d7e1b540bf8c78`

This slice establishes canonical social relationship state between Descenders without adding dialogue, social action execution, parties, betrayal logic, or free-form narrative generation.

The authority rule is unchanged:

> Social reasoning may observe or propose bounded decisions, but deterministic simulation services alone own canonical Crawl truth.

## Scope

30C.1 must provide:

- deterministic directed relationship state between Descenders,
- bounded canonical relationship dimensions,
- canonical read/create/update helpers,
- deterministic serialization and validation,
- event-ledger provenance for mutations,
- checkpoint/save/load compatibility through Crawl-owned state,
- stable fingerprints/digests suitable for later brain observations,
- focused regression tests and a deterministic proof.

## Canonical relationship dimensions

Each directed relationship edge supports:

- trust,
- respect,
- affection,
- fear,
- resentment,
- gratitude,
- rivalry,
- familiarity.

Relationship state is directed. A Descender may trust another Descender more than the reverse.

All dimensions use the closed interval `[-1.0, 1.0]` except familiarity, which uses `[0.0, 1.0]`.

Initial values are neutral (`0.0`). Sparse storage is required: an absent directed edge reads as neutral state and does not allocate canonical state until a deterministic social-state operation creates or changes it.

## Canonical identity

A relationship edge is uniquely identified by:

- source Descender ID,
- target Descender ID.

Self-relationships are invalid.

The same pair may therefore have two independent directed edges: `A -> B` and `B -> A`.

## Mutation contract

Relationship state may only change through the deterministic social-state service.

Every accepted canonical mutation must:

1. validate source and target participants,
2. validate dimension and bounded delta/value,
3. apply deterministic clamping,
4. emit a structured canonical event,
5. retain enough provenance to reconstruct why the relationship changed,
6. leave no presentation or LLM-generated prose as canonical truth.

30C.1 does not decide *when* relationship changes should occur. Later slices derive social evolution from authoritative gameplay events and bounded social intents.

## Event contract

Relationship mutation events identify at minimum:

- source Descender,
- target Descender,
- changed dimension,
- previous value,
- requested delta or replacement value,
- resulting value,
- whether the sparse edge was created by the operation,
- deterministic reason code,
- optional authoritative source event ID.

Reason codes are structured identifiers, not narrative prose.

## Persistence

30C.1 state lives inside Crawl-owned canonical metadata already included by accepted save/checkpoint serialization. No second authoritative social database or parallel truth tree may be introduced.

## Determinism

Given identical Crawl state and identical ordered social mutations, serialized relationship state, emitted event IDs, fingerprints, and proof digests must be identical.

## Explicit non-goals

Deferred to later 30C slices:

- 30C.2: event-derived social memory and relationship evolution,
- 30C.3: social intent validation/execution,
- 30C.4: parties, alliances, leadership,
- 30C.5: rivalry escalation, betrayal, social conflict,
- 30C.6: autonomous multi-character social orchestration.

Deferred to Phase 31:

- generated dialogue,
- conversation text,
- interviews,
- commentator voices,
- cinematic narration,
- free-form social storytelling.

## Acceptance gate

30C.1 is accepted only when local validation proves:

1. directed relationship edges are created deterministically,
2. absent edges read as neutral without mutation,
3. all canonical dimensions enforce their bounds,
4. self-relationships and unknown participants reject without mutation,
5. relationship changes emit structured canonical ledger provenance,
6. repeated identical runs produce identical state/event digests,
7. save/checkpoint/restore preserves social state exactly,
8. no accepted 30A/30B regression is introduced,
9. the full repository regression suite passes,
10. validation ends with explicit `[30C.1] PASS`.

## Next slice

After acceptance, the canonical next slice is:

**30C.2 — Social Memory & Relationship Evolution**
