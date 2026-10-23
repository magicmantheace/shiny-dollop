# Crawl v0.10 — Slice 30C.2 Social Memory & Relationship Evolution

## Status

**Canonical slice:** 30C.2 — Social Memory & Relationship Evolution

**Exact accepted baseline:** 30C.1 at `d1e34b9170aa237582a8643cdcbb2832cbb75130`.

**Protocol:** `underreach.social-memory-evolution.v1`

**Implementation:** `30c2.1`

This slice extends the accepted 30C.1 directed relationship state. It does not replace it and does not create a second social truth tree.

---

## Purpose

30C.1 established deterministic directed relationship dimensions. 30C.2 makes those dimensions evolve because of real canonical events and adds structured social memories that remain traceable to the authoritative Ledger.

The authority flow is:

```text
Canonical simulation event
        ↓
Structured social fact extraction
        ↓
Deterministic memory rule
        ↓
30C.1 relationship mutation service
        ↓
Structured social-memory record
        ↓
Canonical Ledger provenance
```

No LLM, dialogue system, Unreal presentation, commentator, recap system, or generated narrative may create canonical social memory or relationship truth.

---

## Canonical storage

30C.2 stores its metadata under:

`Descent.modifiers["_social_memory_evolution"]`

30C.1 remains under:

`Descent.modifiers["_social_state"]`

Both are part of the same authoritative `Descent` / `Crawl` object, so accepted SQLite persistence and alpha checkpoints automatically carry them together.

---

## Social memory identity

A memory is a deterministic thread keyed by:

- Descent ID,
- observer Descender ID,
- subject Descender ID,
- canonical memory type.

Repeated events of the same social meaning reinforce that same memory thread instead of producing an unrelated second truth.

Each memory stores:

- deterministic memory ID,
- observer Descender ID,
- subject Descender ID,
- memory type,
- every real source Ledger event ID,
- importance,
- confidence,
- bounded decay rate,
- creation tick,
- last reinforcement tick,
- last decay tick,
- reinforcement count.

A memory with no real canonical source event is invalid.

---

## Canonical social fact vocabulary

Initial 30C.2 memory types are:

- `rescued`
- `shared_resource`
- `healed`
- `protected`
- `abandoned`
- `betrayed`
- `stole_loot`
- `fought_beside`
- `caused_injury`
- `prevented_injury`
- `accepted_aid`
- `refused_aid`
- `kept_promise`
- `violated_promise`
- `witnessed_bravery`
- `witnessed_retreat`
- `witnessed_sacrifice`
- `witnessed_selfishness`

Each type maps to a fixed deterministic set of 30C.1 relationship deltas plus default memory importance, confidence, and decay rate.

The mapping is code-owned simulation policy, not model-generated prose.

---

## Source event extraction

### Direct event types

Events with unambiguous actor/affected roles can map directly. Examples include:

- `RESCUE`
- `SHARED_RESOURCE`
- `HEALED`
- `PROTECTED`
- `ABANDONED`
- `BETRAYAL`
- `LOOT_STOLEN`
- `INJURY_CAUSED`
- `INJURY_PREVENTED`
- `AID_ACCEPTED`
- `AID_REFUSED`
- `PROMISE_KEPT`
- `PROMISE_VIOLATED`

For these events the first actor is the acting Descender and the second actor is the affected Descender. The affected Descender forms the directed memory about the actor.

`FOUGHT_BESIDE` creates one directed memory in each direction when exactly two actors are supplied.

### Explicit structured social facts

Ambiguous gameplay events may carry:

```json
{
  "social_facts": [
    {
      "observer_descender_id": "descender_b",
      "subject_descender_id": "descender_a",
      "memory_type": "witnessed_bravery"
    }
  ]
}
```

This is structured simulation data, not narrative interpretation. Unknown memory types, non-participants, self-memories, and duplicate facts are rejected before mutation.

Explicit `social_facts` take precedence over event-type inference.

---

## Duplicate and order protection

Only qualifying source events are added to the processed source-event trace.

A qualifying source event:

- may be processed at most once,
- must already exist in canonical `history_event_ids`,
- must belong to the same Descent,
- cannot come from the future,
- must be processed in canonical Ledger order.

Reprocessing an already processed event is side-effect free.

Attempting to process an earlier qualifying event after a later one is rejected rather than silently creating order-dependent social truth.

---

## Relationship evolution

Every qualifying social fact applies its fixed relationship deltas through the accepted `SocialStateService.adjust_dimension()` authority boundary.

Therefore every actual relationship change remains:

- bounded by 30C.1 dimension limits,
- directed,
- deterministic,
- Ledger bound,
- linked back to the real source gameplay event ID.

Repeated behavior can reinforce relationship values until existing 30C.1 clamps are reached.

No relationship mutation occurs merely because a piece of prose says something happened.

---

## Memory reinforcement

When another canonical event produces the same observer / subject / memory-type thread:

1. memory decay is first applied internally up to that source event tick,
2. the new source event ID is appended,
3. importance and confidence receive bounded reinforcement,
4. reinforcement count increases,
5. the normal fixed relationship deltas apply again,
6. a `SOCIAL_MEMORY_REINFORCED` event is written.

The complete source-event list remains preserved.

---

## Bounded memory decay

30C.2 supports explicit deterministic decay of memory salience:

- confidence decays linearly by the memory's fixed decay rate,
- importance decays at half that rate,
- both clamp to `[0, 1]`,
- decay can only advance to a tick already reached by canonical Descent time,
- decay never advances simulation time itself.

Most importantly:

**30C.2 does not automatically decay relationship dimensions.**

That is intentional. Time passing is not a new social fact. Relationship truth changes only from canonical events unless a later explicitly defined simulation rule says otherwise.

Decay writes `SOCIAL_MEMORY_DECAY_APPLIED` and records that relationship state was not changed.

---

## Ledger events

30C.2 adds:

- `SOCIAL_MEMORY_EVOLUTION_INITIALIZED`
- `SOCIAL_MEMORY_RECORDED`
- `SOCIAL_MEMORY_REINFORCED`
- `SOCIAL_MEMORY_DECAY_APPLIED`

30C.1 continues to own:

- `SOCIAL_RELATIONSHIP_CREATED`
- `SOCIAL_RELATIONSHIP_CHANGED`

Every relationship mutation caused by a memory references the original gameplay source event ID.

---

## Persistence and checkpoint behavior

The memory state is embedded in canonical Descent state, so existing:

- SQLite `CrawlPersistence`,
- `AlphaCheckpointStore`,
- fingerprinting,
- canonical JSON,
- replay history

carry 30C.2 state automatically.

Acceptance requires exact save/load and checkpoint equality.

---

## Deterministic replay expectation

Two identical Descent stacks receiving the same canonical source-event history must produce identical:

- processed source IDs,
- memory IDs,
- memory source-event histories,
- reinforcement counts,
- relationship dimensions,
- memory-state digest,
- relationship-state digest,
- Ledger event sequence,
- checkpoint-restored state.

Earlier social events must remain visible in social state after real multi-Stratum progression.

---

## Explicit exclusions

30C.2 does **not** add:

- social action proposals,
- recruitment,
- item-sharing execution,
- party creation,
- alliance state,
- leadership,
- rivalry/betrayal action eligibility,
- free-form dialogue,
- interviews,
- commentator narration,
- cinematic storytelling,
- presentation feedback into canonical state.

Those belong to later slices.

---

## Local validation

Run:

```powershell
.\scripts\run-underreach-social-memory-evolution-validation.ps1
```

Validation runs:

1. accepted 30A.1 through 30C.1 focused regressions,
2. focused 30C.2 tests,
3. deterministic social-memory proof twice,
4. replay / reinforcement / decay / Stratum-persistence invariants,
5. checkpoint round-trip proof,
6. full repository regression suite.

Acceptance requires the explicit terminal line:

```text
[30C.2] PASS
```

---

## Next canonical slice

After acceptance, the next slice is:

**30C.3 — Social Intent & Interaction Execution**

30C.3 may observe the structured state established here, but social proposals must still pass through deterministic validation and simulation-owned execution before any canonical state changes.
