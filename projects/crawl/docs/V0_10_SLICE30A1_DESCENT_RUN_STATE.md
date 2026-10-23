# Underreach v0.10 — Slice 30A.1 Descent Run State

## Status

Implementation branch only. This slice is **not accepted** until local validation ends with:

```text
[30A.1] PASS
```

Accepted baseline: `3a49f6e106e314457d5db589d2136e30d58e0a6f` (29E.6).

## Purpose

30A.1 begins Phase 30: **Make it an Actual Descent**.

The slice establishes a canonical deterministic run-state contract for one Underreach Descent:

- deterministic Descent identity,
- planned → active → completed lifecycle,
- an ordered participating Descender roster,
- canonical current Stratum and Sector positions,
- monotonic simulation tick,
- deterministic state snapshots and digests,
- exact portable serialization/restore,
- compatibility with the existing atomic `AlphaCheckpointStore`,
- explicit separation between simulation authority and presentation.

This is an authoritative simulation slice. Unreal is not involved in deciding or validating gameplay truth.

## Reuse instead of duplication

The repository already has a mature authoritative `Crawl` domain, persistence tables, event Ledger, and atomic checkpoint system.

`src/livingworld/underreach_domain.py` intentionally aliases:

```text
Descent = Crawl
Stratum = CrawlFloor
Sector = CrawlLocation
DescenderParticipation = CrawlerParticipation
```

30A.1 preserves that compatibility. It does **not** introduce a second mutable Descent object or a second database.

The mutable source of truth remains the established `Descent`/`Crawl` model.

The new `DescentRunStateService` is a lifecycle facade around that model.

## Canonical protocol

```text
underreach.descent-run-state.v1
```

Implementation:

```text
30a1.1
```

Portable serialization protocol:

```text
underreach.descent-run-serialization.v1
```

## Initial-Stratum scope

30A.1 initializes **exactly one Stratum**.

The persisted Crawl-era field remains one-based for backward compatibility:

```text
current_floor = 1
```

The Underreach-facing run snapshot exposes:

```text
current_stratum_index = 0
current_stratum_number = 1
```

Run metadata explicitly records:

```text
multi_stratum_progression_enabled = false
multi_stratum_owner_slice = 30A.2
```

30A.1 validation rejects a second Stratum. Actual generation/activation/advancement across multiple Strata belongs to **30A.2 — Multi-Stratum Progression**.

## Deterministic Descent identity

The run ID is derived from:

- Descent seed,
- ruleset ID,
- ruleset version,
- sorted Descender roster digest.

Caller roster order therefore cannot change canonical identity.

The roster digest contains only canonical Descender IDs. It deliberately does **not** depend on Unreal assets, renderer manifests, material identity, or other presentation data.

## Lifecycle

### Planned

`DescentRunStateService.create(...)`

Creates:

- one deterministic initial Stratum,
- all participants at its entrance Sector,
- stable run metadata,
- `DESCENT_RUN_STATE_INITIALIZED` in the canonical Ledger.

### Active

`DescentRunStateService.start(...)`

Uses the existing authoritative lifecycle service to:

- set the start tick,
- activate the initial Stratum,
- record normal lifecycle Ledger events.

Ticks can only move forward.

### Position state

`commit_descender_position(...)` records a position already chosen by an authoritative simulation system.

The function itself does not decide routes or outcomes. It requires:

- active Descent,
- active participating Descender,
- current Stratum,
- existing target Sector,
- an adjacent graph edge from the current Sector.

Successful changes produce a structured `DESCENDER_POSITION_CHANGED` Ledger event.

### Elimination

Elimination delegates to the established canonical `CrawlLifecycleService`, preserving existing count, health, event, persistence, and invariant behavior.

### Completion

For the one-Stratum 30A.1 proof, all still-active Descenders must be at an exit before completion.

Completion uses the established lifecycle transition and ends the Descent without creating or advancing to a second Stratum.

## Run snapshot

`build_descent_run_snapshot(...)` creates a deterministic canonical view containing:

- Descent ID / seed,
- ruleset identity,
- lifecycle state,
- current tick/start tick,
- Stratum index/number/seed/theme/status,
- exact participant Stratum/Sector positions,
- participation status counts,
- starting/surviving/eliminated counts,
- ordered roster and digest,
- Ledger event IDs and digest,
- canonical `Descent.fingerprint()`,
- snapshot SHA-256 digest.

A snapshot is validated against the live canonical `Descent`; it cannot replace or mutate it.

## Portable serialization

`serialize_descent_run(...)` uses the same canonical JSON and SHA-256 helpers as the existing runtime checkpoint system.

It contains:

- full canonical Descent state,
- canonical fingerprint,
- run-state snapshot digest,
- Ledger ID digest,
- envelope digest.

`restore_descent_run(...)` refuses:

- wrong protocol,
- envelope tampering,
- invalid canonical model state,
- fingerprint mismatch,
- run-state digest mismatch,
- Ledger ID digest mismatch.

## Durable checkpoint compatibility

30A.1 does not replace `AlphaCheckpointStore`.

The proof writes the active 30A.1 state through the existing store with the exact durable Ledger prefix, reloads it, and verifies exact model equality and canonical fingerprint equality.

This preserves the existing architecture:

```text
Canonical Descent
      ↓
Structured Ledger
      ↓
Atomic checkpoint + Ledger-prefix digest
```

## Authority boundary

Required metadata and proof flags:

```text
authoritative = true
canonical_owner = deterministic_simulation
presentation_feedback_allowed = false

simulation_decides_truth = true
unreal_can_mutate = false
presentation_can_mutate = false
```

Unreal remains a consumer downstream of canonical truth.

## Validation proof

The generator executes one deterministic eight-Descender lifecycle:

```text
create
  ↓
planned snapshot
  ↓
start at tick 5
  ↓
active snapshot
  ↓
commit one adjacent Sector position
  ↓
tick 6
  ↓
portable serialize/restore
  ↓
AlphaCheckpointStore write/load with exact Ledger prefix
  ↓
all active Descenders traverse valid graph edges to the exit
  ↓
tick 7
  ↓
complete
  ↓
completed snapshot
```

The proof is generated twice and the full proof digest must match.

## Files

```text
src/livingworld/underreach_descent_run_state.py
tests/test_underreach_30a1_descent_run_state.py
scripts/generate-underreach-descent-run-state-proof.py
scripts/run-underreach-descent-run-state-validation.ps1
docs/V0_10_SLICE30A1_DESCENT_RUN_STATE.md
```

Generated local proof:

```text
validation/underreach-30a1/descent-run-state-proof.json
```

## Validation command

From `D:\CrawlTesting`:

```powershell
.\scripts\run-underreach-descent-run-state-validation.ps1
```

The runner performs:

1. focused 30A.1 deterministic tests,
2. proof generation twice,
3. exact proof digest/identity comparison,
4. authority and 30A.2 scope checks,
5. portable restore/checkpoint restore agreement,
6. full repository regression suite,
7. explicit final `[30A.1] PASS`.

## Acceptance boundary

Do not accept 30A.1 unless local validation ends with:

```text
[30A.1] PASS
```

After acceptance, the next canonical slice is:

**30A.2 — Multi-Stratum Progression**

That slice may enable the currently forbidden multi-Stratum progression flag and introduce deterministic creation/activation/advancement across Strata.
