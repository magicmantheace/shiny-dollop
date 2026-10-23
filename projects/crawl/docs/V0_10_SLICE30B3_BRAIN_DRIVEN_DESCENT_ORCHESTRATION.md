# Underreach v0.10 Slice 30B.3 — Brain-Driven Descent Orchestration

## Status

Implementation slice awaiting local acceptance validation.

Protocol:

`underreach.brain-driven-descent.v1`

Implementation version:

`30b3.1`

Exact source baseline:

30B.2 — Intent Validation & Execution Bridge

Accepted source SHA at branch creation:

`14122b2e4ab53d9d07963c944b3bd631fd244384`

---

## Purpose

30B.1 established a read-only brain observation and advisory `BrainIntent` contract.

30B.2 established the deterministic simulation-owned authority membrane that validates and executes an accepted intent.

30B.3 connects those two contracts to the accepted unattended Descent runtime.

The result is the first complete brain-driven crawl loop:

```text
Canonical Descent state
        ↓
30A.4 simulation clock advances
        ↓
30B.1 bounded brain observation
        ↓
Brain provider proposes intent
        ↓
30B.2 deterministic validation/execution membrane
        ↓
Canonical movement/resource action OR deterministic rejection
        ↓
30A.5 deterministic liveness fallback when required
        ↓
Accepted encounter/cache/loot/survival systems
        ↓
Accepted Stratum progression/completion
        ↓
Canonical Ledger + checkpoints
```

The brain influences behavior.

The brain does **not** become authoritative.

---

## Non-negotiable authority boundary

The deterministic simulation remains the only owner of canonical truth.

The brain provider may:

- receive a bounded observation,
- return a typed proposal.

The brain provider may not directly:

- move a Descender,
- change health,
- change stamina,
- change hydration or nutrition,
- open a cache,
- grant or remove an item,
- resolve combat,
- eliminate a Descender,
- advance a Stratum,
- change the simulation clock,
- append canonical Ledger events,
- mutate Unreal or presentation state into simulation truth.

Every accepted brain mutation still passes through 30B.2 and accepted simulation services.

---

## Why 30A.5 is preserved

30B.3 does not replace or edit the accepted 30A.5 implementation.

Instead it composes `FullAutonomousDescentService` and maintains its accepted trace and invariants while adding a separate brain-driven trace.

This provides two important properties:

1. all accepted 30A.1–30A.5 invariants remain live,
2. checkpoints created during 30B.3 still contain the complete canonical state required by the previous stack.

The 30A.5 trace remains the generic authoritative unattended-step trace.

The 30B.3 trace explains how brain proposals and deterministic fallbacks produced those actions.

---

## Brain cadence

30B.3 uses a deterministic cadence of:

`1 brain proposal opportunity per active Descender per simulation step`

The cadence is persisted in metadata as:

`brain_cadence_steps = 1`

The simulation advances the 30A.4 survival clock **before** requesting proposals for the step.

Therefore every brain observation is based on the current authoritative tick/resource state.

Proposals are generated and executed one Descender at a time in stable Descender-ID order.

The implementation does not generate one stale batch and then execute it after other Descenders have already changed canonical state.

---

## Proposal execution

For each active Descender:

1. capture canonical digest/fingerprint/Ledger state,
2. request a 30B.1 proposal,
3. verify provider code did not mutate canonical state,
4. pass the proposal to the 30B.2 executor,
5. allow 30B.2 to rebuild the current observation and validate legality,
6. execute only through accepted canonical services,
7. bind accepted execution to `BRAIN_INTENT_EXECUTED`,
8. record the result in the 30B.3 decision trace.

Brain actions remain the accepted 30B.1 vocabulary:

- `explore`
- `seek_cache`
- `seek_exit`
- `seek_safety`
- `recover`
- `consume_supply`
- `wait`

---

## Deterministic fallback

An AI/model provider must never become a runtime availability dependency.

30B.3 therefore retains the accepted 30A.5 bounded policy as a liveness fallback.

Fallback is used when:

- the provider raises an exception without canonical mutation,
- 30B.2 rejects the proposal,
- execution fails before any canonical mutation,
- a navigation proposal executes but produces no movement,
- a `wait` proposal is executed outside an exit.

The fallback may:

- use the existing deterministic personality/navigation decision logic,
- perform the existing deterministic deliberate hidden-path search,
- move through an adjacent canonical edge,
- recover at an accepted safe area.

The fallback cannot bypass accepted simulation rules.

### Provider mutation during failure

If a provider raises an exception **after** changing canonical state, 30B.3 refuses to hide the problem with fallback.

The orchestrator raises an authority error instead.

Likewise, if 30B.2 unexpectedly fails after a partial canonical mutation, fallback is refused.

This prevents a model/provider bug from being disguised as normal deterministic behavior.

---

## Hidden-path liveness

30B.2 intentionally does not grant omniscient routing.

A brain can therefore propose exploration or exit seeking while the crawler still lacks a known route.

If the validated navigation execution makes no progress, 30B.3 invokes the accepted 30A.5 policy.

That policy owns deterministic deliberate hidden-path discovery.

Therefore:

- the brain does not receive hidden map truth,
- the executor does not teleport,
- the crawl can still converge when a hidden traversal edge is required.

---

## Simulation-owned systems after brain actions

After all current Descenders receive a brain/fallback action opportunity, 30B.3 delegates the rest of the step to accepted deterministic systems.

### Encounters

Occupied encounters are resolved through the accepted encounter/combat system.

The brain does not select combat outcomes.

### Caches

A cache opens only when an active Descender physically reaches its canonical Sector.

### Loot

Ground/cache loot ownership continues through accepted deterministic item scoring/claim rules.

### Survival supplies

The brain may explicitly propose `consume_supply` through 30B.2.

The accepted 30A.5 survival safety net is also retained after actions so a weak/custom provider cannot intentionally or accidentally deadlock survival management.

### Recovery

The brain may propose `recover` only at an accepted safe area.

The accepted deterministic post-action safe-area recovery guard is retained for liveness/survival safety.

### Time

Only 30A.4 advances the canonical survival clock.

30B.3 advances it exactly once per brain-driven simulation step.

### Stratum progression

30A.2 remains the owner of multi-Stratum advancement.

All surviving active Descenders must satisfy the accepted exit condition before transition.

### Completion

Final completion remains owned by accepted Descent progression/lifecycle services.

### Extinction

Encounter/combat systems continue to own individual elimination.

If no active Descenders remain, 30B.3 records terminal extinction without inventing skipped Strata or fake survivors.

---

## Canonical Ledger events

30B.3 adds:

- `BRAIN_DRIVEN_DESCENT_INITIALIZED`
- `BRAIN_DRIVEN_DESCENT_STARTED`
- `BRAIN_DRIVEN_STEP_RESOLVED`
- `BRAIN_DRIVEN_DESCENT_COMPLETED`
- `BRAIN_DRIVEN_DESCENT_EXTINGUISHED`

30B.2 continues to emit:

- `BRAIN_INTENT_EXECUTED`

Accepted lower-level events remain unchanged, including:

- survival clock events,
- position changes,
- cache/loot/supply events,
- encounter/combat events,
- `STRATUM_ADVANCED`,
- `AUTONOMOUS_STEP_RESOLVED`,
- final completion/extinction events.

A 30B.3 step record references its matching accepted 30A.5 `AUTONOMOUS_STEP_RESOLVED` event.

This creates a traceable chain from:

```text
brain proposal
→ validated brain execution
→ canonical lower-level events
→ accepted autonomous step
→ brain-driven step
```

---

## Metadata

30B.3 metadata is stored under:

`_brain_driven_descent`

It records:

- protocol/version,
- authority boundary,
- provider identity,
- brain cadence,
- deterministic fallback identity,
- run outcome,
- brain-driven step count,
- detailed step records,
- lifecycle Ledger IDs,
- runtime metrics.

Metrics include:

- brain proposals,
- brain executions,
- brain rejections,
- provider errors,
- brain-produced moves,
- non-progress brain navigation,
- fallback invocations,
- fallback-produced moves.

The existing `_full_autonomous_descent` metadata remains authoritative and valid in parallel.

---

## Snapshot and determinism

`build_brain_driven_snapshot()` includes:

- protocol/version,
- Descent identity and seed,
- canonical run status/outcome,
- provider identity,
- brain cadence,
- full 30B.3 step trace,
- trace digest,
- brain metrics,
- accepted 30A.5 snapshot digest,
- survivor/elimination counts,
- Ledger-ID digest,
- canonical Descent fingerprint,
- deterministic snapshot digest.

For the deterministic reference provider, the same seed + roster + canonical state must reproduce exactly:

- proposals,
- executions,
- fallbacks,
- events,
- canonical model,
- history IDs,
- final snapshot.

---

## Checkpoint/resume

30B.3 adds no hidden mutable brain-runtime state for the deterministic reference provider.

The complete brain-driven trace lives in canonical Descent metadata.

Acceptance therefore requires:

1. start an identical brain-driven run,
2. reach Stratum 2,
3. write an `AlphaCheckpointStore` checkpoint,
4. restore the checkpoint,
5. validate both accepted 30A.5 and 30B.3 state,
6. resume with the same provider identity,
7. complete the remaining Strata,
8. compare the final state to the uninterrupted run.

The resumed final result must match exactly:

- canonical model JSON,
- Ledger event-ID sequence,
- canonical fingerprint,
- 30B.3 snapshot,
- 30A.5 source snapshot embedded in it.

---

## Acceptance proof

The deterministic proof uses:

- 12 Descenders,
- 4 Strata,
- the deterministic reference brain,
- the complete accepted 30A.1–30B.2 stack.

It performs:

1. uninterrupted brain-driven completion,
2. independent reproduction with reversed roster input order,
3. exact model/history/snapshot comparison,
4. checkpoint capture after entering Stratum 2,
5. exact checkpoint restore validation,
6. checkpoint-resumed completion,
7. exact final comparison to uninterrupted execution,
8. a synthetic provider-outage step proving deterministic fallback and clock progress.

The validator additionally requires real integration evidence:

- brain proposals > 0,
- brain executions > 0,
- brain-produced moves > 0,
- canonical encounter resolution > 0,
- three Stratum transitions,
- cache opening > 0,
- loot claims > 0,
- supply claims > 0,
- survival supply consumption > 0,
- cache-seeking brain intent exercised,
- brain execution Ledger counts match metrics,
- provider outage invokes fallback.

---

## Files

30B.3 adds only:

- `src/livingworld/underreach_brain_driven_descent.py`
- `tests/test_underreach_30b3_brain_driven_descent_orchestration.py`
- `scripts/generate-underreach-brain-driven-descent-proof.py`
- `scripts/run-underreach-brain-driven-descent-validation.ps1`
- `docs/V0_10_SLICE30B3_BRAIN_DRIVEN_DESCENT_ORCHESTRATION.md`

No accepted 30A or earlier 30B implementation file is modified.

No Unreal file is modified.

No GitHub Actions workflow is added or required.

---

## Local validation

Run:

```powershell
.\scripts\run-underreach-brain-driven-descent-validation.ps1
```

The validator runs:

1. accepted 30A.1–30B.2 focused regressions,
2. focused 30B.3 orchestration/fallback/determinism tests,
3. the deterministic four-Stratum proof twice,
4. proof/authority/checkpoint invariants,
5. the full repository regression suite.

Acceptance requires the explicit terminal line:

```text
[30B.3] PASS
```

---

## Phase boundary

30B.1 established the brain proposal contract.

30B.2 established deterministic intent validation/execution.

30B.3 establishes complete unattended brain-driven Descent orchestration.

If this slice passes acceptance, **Phase 30B — AI Brain is complete.**

The next known canonical phase is:

**30C — Social Intelligence**

That phase can build cooperation, trust, alliance, rivalry, betrayal, group decisions, and other multi-character reasoning on top of this now-functional individual brain execution loop.

30C must preserve the same authority rule:

> social reasoning may propose or influence decisions through bounded contracts, but deterministic simulation remains the owner of canonical truth.
