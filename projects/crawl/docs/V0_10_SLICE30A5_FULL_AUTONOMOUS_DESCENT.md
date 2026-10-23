# v0.10 Slice 30A.5 — Full Autonomous Descent

## Status

Implementation branch only. This slice is not accepted until the local validator ends with explicit:

```text
[30A.5] PASS
```

## Canonical baseline

30A.5 starts from accepted 30A.4:

```text
87a5a81a61323b2166622b144183ba6dd5b652ca
```

It layers orchestration on top of the accepted canonical stack:

```text
30A.1 Descent Run State
  ↓
30A.2 Multi-Stratum Progression
  ↓
30A.3 Loot, Cache & Relic Foundation
  ↓
30A.4 Resources & Survival
  ↓
30A.5 Full Autonomous Descent
```

No accepted 30A.1-30A.4 implementation file is rewritten by this slice.

---

## Architectural rule

The deterministic simulation remains authoritative.

```text
Autonomous bounded policy
        ↓
Accepted canonical simulation services
        ↓
Authoritative Descent + Event Ledger
        ↓
Presentation manifests
        ↓
Unreal Engine / feed / replay / highlights
```

Unreal, animation, camera, rendering, commentary, presentation AI, or future spectators cannot choose movement, loot ownership, survival consumption, encounters, Stratum advancement, combat outcomes, or canonical state.

30A.5 is headless orchestration only.

---

## Why 30A.5 does not reuse GameplayCrawlSimulator directly

The older `GameplayCrawlSimulator` increments `crawl.current_tick` internally. 30A.4 introduced a stronger invariant:

```text
_resources_survival.last_processed_tick == descent.current_tick
```

Calling the old gameplay loop directly would allow canonical time to advance without applying the accepted survival clock.

30A.5 therefore coordinates the proven lower-level systems in this order:

1. advance one canonical survival tick through 30A.4;
2. evaluate survival needs and owned supplies;
3. run bounded deterministic crawler decisions;
4. perceive local topology;
5. commit one canonical adjacent movement;
6. resolve occupied encounters through the existing encounter/combat system;
7. open reached 30A.3 caches;
8. reveal, claim, and consume 30A.4 survival supplies;
9. collect canonical ground/cache loot;
10. recover in canonical safe areas when needed;
11. advance Strata through accepted 30A.2/30A.4 transition services;
12. complete the final Stratum through accepted canonical lifecycle services.

This keeps all source validators live during the run.

---

## New protocol

```text
underreach.full-autonomous-descent.v1
```

Implementation version:

```text
30a5.1
```

Metadata key:

```text
_full_autonomous_descent
```

---

## Bounded autonomous policy

30A.5 intentionally does **not** introduce an unrestricted LLM planner.

The current policy uses the existing deterministic crawler personality and navigation system, then applies limited survival/progression overrides.

Allowed action set:

```text
explore
seek_exit
seek_safety
recover
wait
```

The policy can never emit an arbitrary executable action.

### Personality remains relevant

The existing `choose_action()` scoring still considers crawler traits, danger, health, fatigue, curiosity, patience, and related agent state.

30A.5 only overrides it when an accepted canonical need requires stronger behavior.

Examples:

- critically depleted resources can prioritize escape or cache search;
- low canonical stamina can prioritize a known safe area;
- the first bounded part of a Stratum encourages exploration while its cache remains sealed;
- a crawler already waiting at an exit remains there once cache-search pressure is satisfied.

---

## No omniscient cache navigation

A cache's canonical Sector is **not** automatically injected into crawler navigation knowledge.

Descenders discover caches by physically reaching their Sector while exploring.

This preserves the distinction between:

```text
world truth
```

and:

```text
what an individual crawler knows
```

### Hidden traversal search

The existing perception system can fail to notice a hidden path. To prevent an autonomous run from permanently deadlocking on one missed edge, 30A.5 adds a bounded deliberate-search mechanic.

A stalled crawler may repeatedly search its current Sector. The search:

- considers only real adjacent canonical edges;
- uses deterministic seed/Descender/Sector/attempt inputs;
- is influenced by perception/navigation skill;
- increases its chance with repeated attempts;
- reveals only one legitimate traversal option;
- records `AUTONOMOUS_HIDDEN_PATH_DISCOVERED` in the Ledger.

It does not teleport a crawler or reveal the whole floor.

---

## Canonical time and survival

Every autonomous step advances time by exactly one tick through:

```text
ResourcesSurvivalService.advance_time(...)
```

This means hydration, nutrition, stamina coupling, threshold events, and deprivation pressure are applied before autonomous movement for the step.

Movement then applies the established movement-cost model to the already-canonical `participant.gameplay.stamina` field.

No duplicate stamina pool is introduced.

---

## Survival behavior

Before movement, an active Descender checks owned survival supplies.

When hydration or nutrition is sufficiently low, the deterministic runner may consume a matching owned supply through the accepted 30A.4 API:

```text
consume_supply_item(...)
```

The item is removed from canonical inventory, the resource pool changes, and the existing survival provenance event is recorded.

At a canonical safe area, sufficiently depleted stamina can trigger:

```text
recover_at_safe_area(...)
```

Again, this uses the accepted 30A.4 state rather than a parallel recovery mechanism.

---

## Cache and supply integration

After movement and encounter resolution, any active Descender physically occupying a sealed current-Stratum cache Sector can open it.

Opening the accepted 30A.3 cache automatically reveals its associated 30A.4 supply cache.

Ground items are then handled deterministically:

### Survival supplies

The co-located active Descender with the lowest matching canonical resource is selected first.

### Managed 30A.3 loot

The established item scoring system chooses the most appropriate co-located active Descender.

### Other canonical ground loot

This includes valid encounter/death drops that are not owned by 30A.3 or 30A.4. The existing item transfer/equipment functions are used and an `AUTONOMOUS_GROUND_LOOT_ACQUIRED` event records the transfer.

Every item still has exactly one authoritative holder:

```text
owner OR world location OR encounter
```

---

## Encounter integration

30A.5 seeds deterministic encounters across all configured Strata during Descent creation using the existing encounter system.

After autonomous movement, each occupied non-exit Sector may resolve its next dormant encounter through the existing:

```text
resolve_encounter(...)
```

Therefore combat outcomes, enemy state, injury/death, reward generation, item distribution, and encounter cleanup remain owned by previously proven canonical systems.

30A.5 does not invent combat outcomes.

---

## Elimination and extinction

Individual elimination/death is handled by the existing encounter/combat lifecycle.

If at least one active Descender remains, the autonomous run continues.

If no active Descenders remain before canonical Descent completion, 30A.5 records:

```text
FULL_AUTONOMOUS_DESCENT_EXTINGUISHED
```

The 30A.5 orchestration outcome becomes:

```text
extinguished
```

The underlying accepted 30A.2 run state is left structurally valid rather than fabricating skipped Stratum transitions or fake survivors.

The acceptance proof requires a successful completed run with at least one survivor; extinction support is a valid terminal orchestration state but does not satisfy 30A.5 acceptance by itself.

---

## Stratum advancement

Once every active current-Stratum survivor occupies a canonical exit:

- non-final Stratum → `ResourcesSurvivalService.advance(..., advance_ticks=0)`;
- final Stratum → `ResourcesSurvivalService.complete(..., advance_ticks=0)`.

The autonomous step already advanced survival time, so transitions do not silently add a second survival tick.

All accepted 30A.2 transition records and `STRATUM_ADVANCED` Ledger events remain authoritative.

---

## Autonomous trace

Each resolved autonomous step stores a compact deterministic record containing:

- step index;
- canonical tick;
- Stratum before/after;
- one bounded action record per acting Descender;
- origin/destination Sector;
- traversal cost;
- encounter IDs resolved;
- caches opened;
- loot/supply claim counts;
- supply-consumption count;
- transition/completion flags;
- surviving/eliminated counts;
- step digest;
- canonical Ledger event ID.

Every record is bound to:

```text
AUTONOMOUS_STEP_RESOLVED
```

The validator recomputes every step digest and verifies every step event exists in canonical history.

---

## Autonomous metrics

30A.5 tracks deterministic cumulative metrics for:

```text
moves
waits
safe_recoveries
cache_opens
loot_claims
supply_claims
supply_consumptions
encounters_resolved
strata_advanced
hidden_paths_discovered
```

These are observational summaries of canonical operations; they do not replace source state.

---

## Deterministic snapshot

`build_full_autonomous_snapshot()` binds together:

- current canonical Descent identity/status;
- current tick/Stratum;
- exact accepted 30A.4 snapshot digest;
- full autonomous step trace;
- step-trace digest;
- autonomous metrics;
- Stratum step counts;
- surviving/eliminated counts;
- encounter count;
- Event Ledger ID digest;
- canonical Descent fingerprint.

The snapshot itself receives a deterministic SHA-256 digest.

---

## Portable restore

30A.5 deliberately reuses the accepted 30A.4 portable serialization envelope because that envelope stores the **entire canonical Descent model**, including 30A.5 metadata.

After restore, 30A.5 runs its own validator and snapshot comparison.

Therefore the proof checks both:

```text
30A.4 canonical portable restore
+
30A.5 autonomous trace validation
```

without creating another competing serialization format.

---

## Durable checkpoint / resume requirement

The acceptance proof runs the same four-Stratum Descent three ways.

### Run A — uninterrupted baseline

A 12-Descender Descent runs autonomously from planned state through final completion.

### Run B — independent reproduction

The same seed and roster are supplied in reverse input order.

Acceptance requires exact equality of:

- final canonical model;
- final fingerprint;
- Event Ledger ID sequence;
- autonomous snapshot;
- run result.

### Run C — checkpoint resume

A third identical run advances until it first reaches Stratum 2.

At that exact live state:

1. 30A.4 portable serialization is round-tripped;
2. an `AlphaCheckpointStore` checkpoint is written;
3. the checkpoint is loaded;
4. 30A.5 validation is run on the restored state;
5. autonomous execution resumes to completion.

The resumed final state must be **identical** to Run A:

```text
same canonical model
same fingerprint
same Event Ledger IDs
same autonomous snapshot
```

This is the central determinism requirement for 30A.5.

---

## Acceptance proof must exercise real systems

A successful final status alone is insufficient.

The PowerShell validator also requires at least:

- one autonomous movement;
- one resolved encounter;
- all three transitions in a four-Stratum run;
- one autonomous cache opening;
- one autonomous loot acquisition;
- one survival-supply acquisition;
- one survival-supply consumption;
- exploration actions;
- exit-seeking actions;
- survival-time Ledger events;
- autonomous start/step/completion Ledger events.

This prevents a trivialized route from passing as a full autonomous Descent.

---

## Files

```text
src/livingworld/underreach_full_autonomous_descent.py
tests/test_underreach_30a5_full_autonomous_descent.py
scripts/generate-underreach-full-autonomous-descent-proof.py
scripts/run-underreach-full-autonomous-descent-validation.ps1
docs/V0_10_SLICE30A5_FULL_AUTONOMOUS_DESCENT.md
```

---

## Local validation

From the Crawl test checkout:

```powershell
cd D:\CrawlTesting
git fetch origin
git switch agent/underreach-v0.10-slice30a5-full-autonomous-descent
git pull --ff-only
.\scripts\run-underreach-full-autonomous-descent-validation.ps1
```

Do not accept the slice unless the final line includes:

```text
[30A.5] PASS
```

---

## Scope boundary after acceptance

30A.5 completes Phase 30A's deterministic autonomous-Descent foundation.

The next canonical phase is **30B — AI Brain**.

30B may improve planning, reasoning, memory use, tactical intent, and richer autonomous behavior, but it must consume the canonical systems established here rather than replacing their authority.

30A.5 does **not** permit an LLM, Unreal, animation, camera, commentary, or presentation layer to alter canonical gameplay truth.
