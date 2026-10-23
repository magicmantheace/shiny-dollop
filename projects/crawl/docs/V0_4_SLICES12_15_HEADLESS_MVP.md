# Crawl v0.4 — Batch 3: Slices 12–15 Headless MVP

This batch stacks on top of `agent/crawl-v0.4-slices7-11` and completes the first major headless Crawl milestone.

It intentionally does **not** start Unreal, rendering, streaming, or viewer-facing work. The purpose of this batch is to prove that the authoritative simulation can run a complete multi-floor crawl with pacing, deadlines, Director intervention, and structured story-ready history before any visual layer is trusted.

## Stack position

```text
roadmap/autonomous-crawl-pivot
  -> Slice 1 domain model
  -> Batch 1: Slices 2-6 autonomous crawlers
  -> Batch 2: Slices 7-11 gameplay
  -> Batch 3: Slices 12-15 headless MVP
```

Fixes discovered in lower batches should still be applied to the branch where the defect originated and then propagated upward.

---

## Slice 12 — Floor deadlines, advancement, and intermission

Implemented in `floor_lifecycle.py` with staged support added to `crawl_service.py`.

The new floor rhythm is:

```text
active
  -> deadline warnings
  -> closure
  -> advancement resolution
  -> intermission
  -> next floor activation
```

### Deadline behavior

Each active floor has an authoritative `deadline_tick`.

The floor lifecycle emits deterministic warning events as the deadline approaches. At closure:

- crawlers at an advancement exit remain eligible,
- active crawlers who failed to reach an exit are eliminated,
- authoritative survivor/elimination counts are updated,
- party state is re-evaluated,
- parties that cannot remain valid dissolve,
- the completed floor is closed,
- the next floor remains pending during intermission.

### Intermission

Intermission is an explicit simulation phase stored in the crawl's persisted control metadata.

During intermission survivors may:

- receive bounded recovery,
- regain stamina,
- reduce stress,
- clear temporary incapacitation,
- re-evaluate equipment,
- spend available progression choices,
- preserve all memories, relationships, inventory, party history, and crawler identity.

Only after the intermission timer expires is the next floor activated and given its own deadline.

### Compatibility

`CrawlLifecycleService.complete_current_floor()` now accepts `activate_next=False`.

The default remains `True`, preserving Batch 2 behavior. Batch 3 uses the staged path so intermission can exist without rewriting earlier gameplay code.

---

## Slice 13 — Crawl Director

Implemented in `crawl_director.py`.

The Director is deterministic, budgeted, and non-authoritative with respect to outcomes.

It may create legal opportunities or pressure, but it may not directly:

- kill crawlers,
- alter combat outcomes,
- teleport crawlers,
- invent ownership outside the item system,
- bypass encounter state,
- exceed a floor's Director budget.

### Current Director metrics

The first Director reads:

- active crawler count,
- average health,
- average stamina,
- location concentration,
- resolved encounter ratio,
- stagnation ratio,
- floor danger.

### Current intervention types

#### Announcement

Low-cost pacing/status intervention. It changes no authoritative crawler state.

#### Reveal route

Makes an already-valid adjacent path known to a bounded number of crawlers. It does not create a new physical connection.

#### Resource opportunity

Creates a normal `RESOURCE_DILEMMA` encounter at an existing location. Its reward is created through the existing item-generation path and remains encounter-owned until normal encounter resolution transfers it.

#### Scheduled hazard

Creates a normal hazard encounter at an existing occupied location. Damage still resolves through the existing encounter/hazard rules.

### Budget rules

Every intervention has an explicit cost. Spend is tracked per floor and persisted in `crawl.modifiers['_crawl_director']`.

At least one legal Director intervention is scheduled per floor so the MVP gate can verify that the Director layer is operational. Stronger interventions remain conditional on simulation metrics.

---

## Slice 14 — Semantic event ledger

Implemented in `semantic_event_ledger.py` and connected centrally through `CrawlLifecycleService._record()`.

This is deliberately downstream of authoritative state changes. The semantic layer describes what occurred; it never decides the authoritative outcome.

Every newly recorded Crawl event now receives deterministic metadata inside:

```text
event.data["semantic"]
```

### Metadata

Current fields include:

- `importance_score`
- `rarity_score`
- `danger_level`
- `reversal`
- `relationship_impact`
- `audience_interest_tags`
- `causal_parent_ids`
- `state_changes`
- `replay_checkpoint_ref`

Scores are deterministic and recalculable from structured state/event information. No LLM is required.

### Causality

The ledger remembers the most recent event involving each crawler.

When a new event involves that crawler, the previous event can become a causal parent. This produces the first machine-readable chains for later questions such as:

- what happened immediately before this death,
- why this rescue matters,
- which earlier event preceded a party split,
- what sequence led to an advancement failure.

This is intentionally conservative. It records real event relationships rather than inventing narrative causality.

### Notable-event index

High-scoring events are added to a persisted notable-event index in crawl control metadata.

This is the first bridge toward later highlight selection and story-arc analysis.

---

## Slice 15 — Headless Crawl MVP gate

Implemented by:

- `headless_mvp_simulation.py`
- `crawl_mvp_demo.py`
- `tests/test_crawl_slices12_15.py`
- `scripts/run-crawl-slices12-15-validation.ps1`

`HeadlessCrawlMVP` composes:

```text
crawler cognition / perception
        -> gameplay movement
        -> parties
        -> encounters
        -> combat / injury / death
        -> items / progression
        -> Director evaluation
        -> floor deadline evaluation
        -> advancement / intermission
        -> next floor
        -> semantic event ledger throughout
```

The Batch 3 layer disables Batch 2's automatic floor completion so the new floor lifecycle is the only system deciding when advancement occurs.

---

## Required local MVP demonstration

Default validation runs:

- 100 crawlers,
- 3 generated floors,
- up to 25,000 orchestration steps,
- deterministic crawler autonomy,
- exploration,
- encounters,
- combat,
- injuries/deaths,
- loot,
- progression,
- parties,
- Director interventions,
- floor advancement,
- intermission,
- structured semantic event history.

The report is written to:

```text
validation/crawl-v0.4-slices12-15-mvp.json
```

A temporary crawl database is written beside the report so the structured event stream can be inspected after the run.

### Gate checks

The report explicitly checks:

- at least 100 starting crawlers,
- at least 3 floors,
- terminal crawl state reached,
- encounters were generated,
- structured event history exists,
- semantic metadata exists,
- the Director actually intervened,
- survivor + elimination counts still equal the original roster.

The default 100-crawler / 3-floor command exits non-zero if any MVP gate check fails.

---

## Focused tests

`tests/test_crawl_slices12_15.py` covers:

1. semantic event scoring and causal actor links,
2. deadline elimination and staged intermission,
3. budgeted Director resource opportunities and item ownership,
4. persistence of Director/semantic control state,
5. integrated multi-floor Batch 3 composition.

The Batch 3 validator also reruns all focused tests from Slices 1–11 before the MVP demonstration.

---

## Local validation

Default:

```powershell
.\scripts\run-crawl-slices12-15-validation.ps1
```

Quick smoke test:

```powershell
.\scripts\run-crawl-slices12-15-validation.ps1 `
  -Crawlers 25 `
  -Floors 2 `
  -MaxSteps 5000 `
  -SkipFullRegression
```

The quick configuration is useful for debugging but does **not** satisfy the formal 100-crawler / 3-floor MVP gate.

Stress example:

```powershell
.\scripts\run-crawl-slices12-15-validation.ps1 `
  -Crawlers 250 `
  -Floors 5 `
  -MaxSteps 50000
```

No GitHub Actions are required or used.

---

## What this batch deliberately does not do

The following remain later work:

- simulation detail tiers,
- 1,000+ crawler scale validation,
- observatory/dashboard conversion,
- deterministic replay checkpoints/state hashes,
- spectator API,
- Unreal integration,
- automated cameras,
- video rendering,
- commentary/TTS,
- highlight clip generation,
- viewer follows/notifications.

Those should begin only after the headless MVP stack has passed local validation and lower-batch fixes have been propagated upward.

---

## Exit condition

Batch 3 should be considered ready only when:

1. Batch 1 is locally validated and its fixes are propagated upward.
2. Batch 2 is locally validated and its fixes are propagated upward.
3. Slices 1–15 focused tests pass on this branch.
4. The 100-crawler / 3-floor MVP report says `mvp_gate.overall = true`.
5. The inherited regression suite passes.
6. Generated history contains real, structured events that can be inspected as potential emergent contestant stories.

Passing that gate marks the end of the first **headless autonomous Crawl** phase and makes the project ready to move into v0.5 scaling and observability work.
