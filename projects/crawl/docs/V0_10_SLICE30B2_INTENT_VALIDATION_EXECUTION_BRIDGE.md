# Underreach v0.10 Slice 30B.2 — Intent Validation & Execution Bridge

## Status

Implementation branch:

`agent/underreach-v0.10-slice30b2-intent-validation-execution-bridge`

Exact accepted baseline:

`0427fb3c7e02d4cbf978a45e1871ad1f7a2ce638`

30B.1 established a read-only AI-brain contract:

```text
canonical Descent state
        ↓
BrainObservation
        ↓
BrainProvider
        ↓
BrainIntent (advisory only)
```

30B.2 adds the missing authority membrane between that advisory proposal and canonical gameplay truth.

---

## Core rule

A brain still does **not** mutate the simulation.

The new pipeline is:

```text
canonical Descent state
        ↓
30B.1 read-only BrainObservation
        ↓
BrainProvider proposes BrainIntent
        ↓
30B.2 rebuilds CURRENT observation
        ↓
side-effect-free deterministic validation
        ↓
accepted? ── no ──> reject with reason; NO canonical mutation
        │
       yes
        ↓
preview execution on cloned Descent
        ↓
canonical simulation service executes operation
        ↓
accepted 30A.x mutation/event(s)
        ↓
BRAIN_INTENT_EXECUTED Ledger event
```

The provider never receives a mutable `Descent` reference through this API.

---

## Protocols

Slice protocol:

`underreach.brain-intent-execution.v1`

Implementation:

`30b2.1`

Decision protocol:

`underreach.brain-intent-execution-decision.v1`

Result protocol:

`underreach.brain-intent-execution-result.v1`

---

## Side-effect-free validation

`validate_intent_for_execution()` and `BrainIntentExecutionService.validate()` do not change:

- position,
- health,
- stamina,
- hydration,
- nutrition,
- inventory,
- item ownership,
- agent knowledge,
- cache state,
- current tick,
- Ledger history,
- canonical fingerprint.

Navigation preview occurs only on a cloned `Descent`.

The preview is important because normal perception/navigation updates crawler knowledge. Validation must not accidentally make a proposal true simply by checking it.

---

## Stale observation rejection

Every 30B.1 intent remains bound to the observation digest that produced it.

Before execution, 30B.2 rebuilds the current observation from canonical state.

If the digest changed, the intent is rejected with:

`stale_observation`

A stale rejection does not append an event and does not mutate canonical state.

This prevents a delayed model response from executing against a newer world state.

---

## Execution semantics

30B.2 tightens the broad 30B.1 proposal shape into action-specific simulation legality.

### `explore`

May optionally target a currently known neighboring Sector.

Without a target, deterministic accepted navigation chooses the next exploration step.

### `seek_exit`

An explicit target must be a Sector the Descender currently knows/believes is an exit.

Without a target, accepted navigation uses known exit/path state and the existing deterministic navigation rules.

### `seek_safety`

An explicit target must be a currently known safe area.

Without a target, accepted navigation uses the existing deterministic safe-area rules.

### `seek_cache`

30B.1 intentionally does not expose a cache Sector ID.

Therefore a brain may not target a Sector ID for `seek_cache` in 30B.2.

If the cache Sector is already part of canonical crawler knowledge, the simulation can route toward it. Otherwise `seek_cache` becomes deterministic exploration; the simulation does not grant omniscient cache location knowledge.

### `consume_supply`

The target item must still exist and must still be canonically owned by the proposing Descender.

Execution uses the accepted 30A.4 `consume_supply_item()` operation.

### `recover`

The Descender must currently occupy an accepted canonical safe area.

Execution uses the accepted 30A.4 `recover_at_safe_area()` operation.

### `wait`

No movement/resource mutation occurs.

The accepted decision is still recorded as a canonical `BRAIN_INTENT_EXECUTED` event because the simulation actually chose to honor that brain proposal.

---

## Canonical execution

Accepted movement uses:

- 30A.1/30A.2/30A.3/30A.4 position validation through `ResourcesSurvivalService.commit_descender_position()`,
- the accepted 30A.5 deterministic movement-cost logic,
- accepted canonical Ledger recording.

Accepted resource actions use 30A.4 services directly.

30B.2 does not create parallel gameplay state.

---

## Ledger provenance

Every accepted execution ends in:

`BRAIN_INTENT_EXECUTED`

The event contains:

- proposal ID,
- provider ID,
- source observation digest,
- deterministic execution-decision digest,
- action,
- origin Sector,
- resolved Sector,
- target item where relevant,
- IDs of lower-level canonical events caused by execution.

A rejected proposal creates no canonical event in this slice.

That distinction keeps "the brain proposed something invalid" outside canonical gameplay history unless a future orchestration slice intentionally chooses to track provider diagnostics separately.

---

## Determinism

For identical canonical state and the same 30B.1 proposal:

- validation decision must match,
- resolved action/Sector must match,
- lower-level event IDs must match,
- execution event ID must match,
- final canonical model must match.

Checkpoint restore must also reproduce the same **next** proposal and execution result.

---

## Acceptance proof

The deterministic proof uses:

- 8 Descenders,
- 3 Strata,
- the complete accepted 30A.1–30A.5 + 30B.1 stack.

It proves:

1. 30B.1 proposal generation does not mutate canonical state,
2. 30B.2 validation accepts a legal reference proposal without mutation,
3. accepted execution changes canonical state and is Ledger-bound,
4. an independent identical run produces the exact same intent, validation decision, execution result, and canonical state,
5. changing the authoritative survival clock makes an earlier proposal stale,
6. stale rejection changes neither state nor Ledger,
7. a checkpoint after canonical brain execution restores exactly,
8. the restored checkpoint produces the same next 30B.1 proposal,
9. original and restored states produce the same next 30B.2 execution result and final canonical state.

Focused tests additionally cover:

- action-semantic target rejection,
- accepted navigation,
- `wait`,
- owned survival-supply consumption,
- deterministic duplicate runs,
- `propose_and_execute()` authority behavior.

---

## Files

- `src/livingworld/underreach_brain_intent_execution.py`
- `tests/test_underreach_30b2_intent_validation_execution_bridge.py`
- `scripts/generate-underreach-brain-intent-execution-proof.py`
- `scripts/run-underreach-brain-intent-execution-validation.ps1`
- `docs/V0_10_SLICE30B2_INTENT_VALIDATION_EXECUTION_BRIDGE.md`

No accepted 30A.x or 30B.1 implementation file is modified.

No Unreal file is modified.

No GitHub Actions workflow is added or required.

---

## Scope boundary

30B.2 does **not**:

- own simulation tick cadence,
- ask a provider for every Descender each tick,
- replace the accepted 30A.5 full-run policy,
- resolve encounters,
- open caches,
- distribute ordinary loot,
- coordinate parties/social behavior,
- add network/model provider dependencies,
- allow presentation/Unreal feedback to affect gameplay.

It provides the trusted deterministic membrane those later systems must use.

---

## Next canonical slice

**30B.3 — Brain-Driven Descent Orchestration**

30B.3 should integrate the accepted 30B.1 proposal contract and 30B.2 execution membrane into unattended Descent cadence. The orchestrator may request proposals, validate/execute them, apply deterministic fallbacks for rejected/unavailable provider output, advance the accepted survival clock, and continue using accepted encounter/cache/loot/Stratum systems.

The brain must remain a proposer. The deterministic simulation remains the authority that decides which proposed actions actually happen.

---

## Local validation

Run:

```powershell
.\scripts\run-underreach-brain-intent-execution-validation.ps1
```

Acceptance requires the explicit terminal line:

```text
[30B.2] PASS
```
