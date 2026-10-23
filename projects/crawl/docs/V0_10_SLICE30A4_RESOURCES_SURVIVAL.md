# Underreach v0.10 — Slice 30A.4: Resources & Survival

## Status

Implementation branch only. This slice is not accepted until the local validator ends with explicit `[30A.4] PASS`.

## Base

Exact accepted 30A.3 base:

`7da3e7d2605ef607d7f9c8c99df8a9bf0e2fd73f`

## Purpose

30A.4 adds deterministic survival pressure to the same authoritative Descent state established by 30A.1–30A.3.

Canonical ownership remains:

```text
Deterministic Crawl Simulation
        ↓
Authoritative Descent / Ledger
        ↓
Presentation manifests
        ↓
Unreal Engine 5.8
```

Unreal, cameras, animation, UI, commentary, and future AI presentation systems cannot change hydration, nutrition, stamina, health, supply ownership, or resource-consumption truth.

## Core design decision: no duplicate stamina

The existing canonical gameplay state already contains:

`participant.gameplay.stamina`

30A.4 does not create another stamina/fatigue meter.

New survival resources are:

- hydration
- nutrition

Low hydration/nutrition affect the already-authoritative stamina value and can apply health pressure.

This prevents two competing stamina truths from emerging later.

## Canonical survival state

30A.4 stores its state under:

`descent.modifiers["_resources_survival"]`

Protocol:

`underreach.resources-survival.v1`

Implementation version:

`30a4.1`

Each Descender has deterministic:

- hydration, 0.0–1.0
- nutrition, 0.0–1.0
- risk band: stable / warning / critical
- warning Ledger event IDs
- critical Ledger event IDs
- resource-consumption Ledger event IDs
- safe-recovery Ledger event IDs
- accumulated survival health damage
- total survival ticks processed

Initial hydration/nutrition are deterministic from Descent seed + Descender ID.

## Survival clock

30A.4 owns an explicit survival clock synchronized with canonical `descent.current_tick`.

`advance_time(descent, to_tick)`:

1. rejects backwards time,
2. processes every elapsed canonical tick,
3. drains hydration and nutrition,
4. applies Stratum-danger multipliers,
5. couples resource state to canonical stamina,
6. applies health pressure at critical deprivation,
7. advances the canonical simulation tick,
8. records deterministic Ledger events,
9. validates the resulting state.

### Baseline drain rates

- hydration: 0.018 per tick
- nutrition: 0.010 per tick

Current Stratum danger deterministically increases both rates.

## Risk bands

Thresholds:

- stable recovery threshold: 0.70
- warning: <= 0.45
- critical: <= 0.18

The risk band is determined by the lower of hydration and nutrition.

### Stable

When both hydration and nutrition are at least 0.70, existing gameplay stamina can recover slowly.

### Warning

Warning pressure drains existing gameplay stamina.

### Critical

Critical pressure drains stamina more aggressively.

Critical hydration and/or nutrition also applies deterministic health pressure.

## Health-pressure scope guard

30A.4 does not create a competing autonomous death policy.

Survival health damage is clamped to a minimum survival-health floor of 0.05 in this slice.

This proves that deprivation can materially threaten a Descender while leaving the final autonomous decision/death orchestration to 30A.5.

30A.5 can then combine:

- survival pressure,
- encounters,
- injuries,
- pathfinding,
- supplies,
- risk tolerance,
- progression,
- and existing canonical elimination rules

without 30A.4 independently killing actors through a second path.

## Survival supplies

30A.4 binds one survival-supply cache to every deterministic 30A.3 loot cache.

The survival supply cache is a separate metadata layer. It does not modify the accepted 30A.3 cache blueprint or digest.

Each supply cache contains exactly:

- one hydration supply — `Sealed Water Flask`
- one nutrition supply — `Dense Field Ration`

Both are deterministic blueprints while sealed.

No `CrawlItem` exists until the underlying real 30A.3 cache is opened.

This prevents existing ground-loot logic from collecting survival supplies through a sealed cache.

## Supply revelation

The 30A.4 `open_cache()` wrapper first executes the accepted 30A.3 cache-open operation.

Only after the real cache is open does 30A.4 materialize its survival supplies at the same canonical Sector.

Ledger event:

`SURVIVAL_SUPPLIES_REVEALED`

The two supplies become real canonical `CrawlItem` records with:

- category `resource`
- rarity `common`
- exactly one authoritative location
- reveal-event provenance

## Supply acquisition

A Descender can acquire a revealed survival supply only when:

- the Descent is running,
- the Descender is active,
- the Descender is in the current Stratum,
- the supply exists as ground loot,
- the Descender occupies the same canonical Sector.

Acquisition uses the established `transfer_item_to_crawler()` function from the existing item system.

Ledger event:

`SURVIVAL_SUPPLY_ACQUIRED`

The normal `CrawlItem` one-holder invariant therefore remains authoritative.

## Supply consumption

Consumption requires canonical ownership.

Hydration supply increases hydration.

Nutrition supply increases nutrition.

The value is capped at 1.0.

Consumed supply is removed from:

- the Descender inventory,
- equipment mappings if somehow referenced,
- `descent.items`.

The supply blueprint and consumption provenance remain in 30A.4 metadata.

Ledger event:

`SURVIVAL_RESOURCE_CONSUMED`

A survival supply cache becomes depleted only when all of its materialized supplies have been consumed.

## Safe-area recovery

A currently active Descender occupying a canonical Stratum safe area can recover existing gameplay stamina.

Recovery amount:

`+0.25 stamina`, capped at 1.0.

Safe-area recovery does not magically create food or water.

Hydration and nutrition are unchanged.

Ledger event:

`SURVIVAL_SAFE_RECOVERY`

## Stratum progression

30A.4 wraps accepted 30A.3 / 30A.2 progression.

When `advance_ticks > 0`:

1. survival pressure is processed on the current Stratum,
2. canonical time advances,
3. the accepted progression system advances survivors to the next Stratum using `advance_ticks=0`,
4. hydration/nutrition persist unchanged except for the elapsed-time drain,
5. owned supplies remain in canonical inventory,
6. a carry-forward event is recorded.

Ledger event:

`SURVIVAL_STRATUM_CARRIED_FORWARD`

No automatic refill occurs between Strata.

## Final completion

Final Descent completion uses the same rule:

- optional final survival time is processed first,
- accepted 30A.3 / 30A.2 completion resolves the final Stratum,
- survival state remains part of the canonical completed Descent snapshot.

## Serialization

Portable serialization protocol:

`underreach.resources-survival-serialization.v1`

The envelope includes:

- complete canonical Descent state,
- canonical Descent fingerprint,
- survival snapshot digest,
- survival-state digest,
- Ledger event-ID digest,
- outer SHA-256 digest.

Restore rejects tampering before accepting the state.

## Durable checkpoint compatibility

30A.4 continues to use the existing `AlphaCheckpointStore` for unattended durable recovery.

The acceptance proof checkpoints after Stratum 1→2 while an unconsumed ration remains owned by a Descender.

The restored state must preserve exactly:

- current Stratum,
- canonical participant positions,
- hydration/nutrition state,
- stamina/health state,
- loot/cache/relic state,
- survival supply ownership,
- consumed supply records,
- Ledger prefix,
- survival metadata.

## Deterministic acceptance proof

Default proof configuration:

- 8 Descenders
- 4 Strata
- 4 30A.3 loot caches
- 4 associated survival supply caches
- 2 survival supplies per cache

Proof flow:

1. Create deterministic four-Stratum Descent.
2. Start at tick 5.
3. Advance survival time to create meaningful pressure.
4. Open Stratum 1 loot cache.
5. Reveal water + ration supplies.
6. Descender 000 claims/consumes water.
7. Descender 001 claims but does not consume ration.
8. Descender 000 reaches a safe area and recovers canonical stamina.
9. All active Descenders reach Stratum 1 exit.
10. Apply transition survival ticks.
11. Advance to Stratum 2.
12. Verify Descender 001 still owns the ration.
13. Portable-serialize the entire canonical state.
14. Write and reload an `AlphaCheckpointStore` checkpoint.
15. Verify checkpoint and portable restore agree.
16. Descender 001 consumes the carried ration on Stratum 2.
17. Open Stratum 2 loot cache and reveal its survival supplies.
18. Descender 002 claims the Stratum 2 water but leaves it unconsumed.
19. Apply another pressure window sufficient to reach critical deprivation for at least one Descender.
20. Verify deterministic health pressure.
21. Advance through remaining Strata.
22. Complete the Descent.
23. Generate the proof a second time.
24. Require identical proof digest and Descent ID.
25. Run the full repository regression suite.

## Acceptance assertions

The PowerShell validator requires:

- exact proof protocol,
- two proof generations with identical digest,
- deterministic Descent identity,
- 8 Descenders,
- 4 Strata,
- 4 survival supply caches,
- survival pressure after the first time window,
- critical pressure after the second window,
- canonical health pressure,
- water increases hydration,
- ration increases nutrition,
- safe rest increases existing gameplay stamina,
- post-transition checkpoint on Stratum index 1,
- checkpoint Ledger prefix of meaningful size,
- portable/checkpoint restore agreement,
- final supply-cache state:
  - 2 revealed,
  - 1 depleted,
  - 4 materialized supplies,
  - 3 claimed supplies,
  - 2 consumed supplies,
- final completed Descent on Stratum index 3,
- required Ledger event types,
- full repository regression pass,
- final explicit `[30A.4] PASS`.

## Required Ledger events

Acceptance requires at least these event types:

- `RESOURCES_SURVIVAL_INITIALIZED`
- `SURVIVAL_TIME_APPLIED`
- `SURVIVAL_SUPPLIES_REVEALED`
- `SURVIVAL_SUPPLY_ACQUIRED`
- `SURVIVAL_RESOURCE_CONSUMED`
- `SURVIVAL_SAFE_RECOVERY`
- `SURVIVAL_STRATUM_CARRIED_FORWARD`

Threshold crossings additionally create:

- `SURVIVAL_THRESHOLD_REACHED`

## Authority contract

The proof states explicitly:

```text
simulation_decides_truth = true
unreal_can_mutate = false
presentation_can_mutate = false
hydration_nutrition_are_canonical = true
stamina_reuses_existing_gameplay_state = true
autonomous_survival_choices_owned_by = 30A.5
```

## Out of scope

30A.4 does not decide:

- when autonomous Descenders should seek food/water,
- whether a Descender should abandon a route for supplies,
- how parties share/ration survival supplies,
- when a character should rest versus push onward,
- survival-aware tactical AI,
- autonomous full-run orchestration,
- new death/elimination policy,
- Unreal/UI presentation of resource bars.

Those orchestration decisions belong to **30A.5 — Full Autonomous Descent**.

## Files

- `src/livingworld/underreach_resources_survival.py`
- `tests/test_underreach_30a4_resources_survival.py`
- `scripts/generate-underreach-resources-survival-proof.py`
- `scripts/run-underreach-resources-survival-validation.ps1`
- `docs/V0_10_SLICE30A4_RESOURCES_SURVIVAL.md`
