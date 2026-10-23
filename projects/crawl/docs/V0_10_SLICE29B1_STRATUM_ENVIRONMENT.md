# Underreach v0.10 Slice 29B.1 — Stratum Environment Foundation

## Purpose

29B.1 replaces the assumption that presentation happens in one fixed QA room with a deterministic, data-driven spatial plan for a Stratum containing multiple Sectors.

This slice does **not** make environment presentation authoritative. Simulation truth, traversal legality, combat outcomes, death, inventory, and progression remain owned by the deterministic core and Ledger.

The existing `crawl.presentation-environment.v1` room protocol is intentionally preserved. 29B.1 adds `underreach.stratum-environment.v1` above it so later Unreal work can instantiate a legacy-compatible presentation room for each generated Sector without a risky protocol migration.

## Manifest contract

A generated Stratum contains:

- stable Stratum seed and generator version;
- deterministic Sector IDs;
- unique grid cells and world origins;
- explicit entry and exit Sectors;
- an optional mid-route Refuge;
- combat/transit roles;
- deterministic undirected connectivity;
- room and combat-clearance dimensions;
- a presentation-room seed for each Sector;
- a stable SHA-256 digest.

## Invariants

1. Same inputs produce byte-equivalent logical manifests and the same digest.
2. Different Descent seeds produce different manifests/digests.
3. Every Sector is reachable from the entry Sector.
4. No two Sectors occupy the same grid cell/world origin.
5. Entry and exit are distinct.
6. Marker IDs and Sector roles agree.
7. Combat clearance never exceeds the Sector room envelope.
8. JSON checkpoint/save/restore does not alter identity or digest.
9. The manifest is always `authoritative: false`.
10. Generation supports at least 250 Sectors deterministically for stress validation.

## Local validation

```powershell
.\scripts\run-underreach-stratum-validation.ps1
```

The runner executes the focused 29B.1 tests, writes a proof manifest under `validation/underreach-29b1/`, then runs the full Python regression suite. It does not use GitHub Actions.

## Acceptance gate

29B.1 is accepted only after the local runner reports:

- focused tests PASS;
- proof manifest generated;
- full repository Python suite PASS;
- rerunning with the same seed reproduces the same digest;
- no pre-existing Underreach regression.

## Deferred to 29B.2+

- Unreal instantiation of several connected Sectors at once;
- corridor/door geometry between Sector origins;
- canonical movement across Sector transitions;
- encounter placement and monster population;
- theme/material families beyond the initial manifest field;
- hazards, traps, vertical traversal, locked routes, secret routes;
- procedural Stratum progression rules.
