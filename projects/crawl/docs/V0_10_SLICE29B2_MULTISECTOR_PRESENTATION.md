# Underreach v0.10 Slice 29B.2 — Connected Multi-Sector Presentation

## Purpose

29B.2 turns the deterministic Stratum layout from 29B.1 into a reproducible multi-room presentation plan and proves that Unreal can instantiate the connected room/corridor structure headlessly.

The simulation and Ledger remain authoritative. This slice does not grant presentation code authority over traversal, combat, progression, or outcomes.

## New protocol

`underreach.multisector-presentation.v1`

The plan binds to the exact 29B.1 Stratum digest and contains:

- one room descriptor per Sector;
- one corridor descriptor per Stratum connection;
- opposed door/portal metadata for each corridor;
- deterministic entry-to-exit proof route;
- contiguous Sector-hold and transition timeline;
- deterministic camera-region handoff windows;
- stable digest.

The Unreal proof writes `underreach.multisector-unreal-debug.v1` diagnostics after spawning room floors, corridor floors/walls, role markers, and route markers using engine primitives.

## Invariants

1. Same Stratum manifest produces the same multi-Sector plan and digest.
2. The plan is always `authoritative: false`.
3. Every Stratum Sector has exactly one room descriptor.
4. Every Stratum connection has exactly one corridor descriptor.
5. Corridor endpoints are orthogonally adjacent Sectors.
6. Corridor portals face opposing room sides.
7. The proof route begins at Entry and ends at Exit.
8. Every proof-route hop is a real Stratum connection.
9. Timeline coverage is contiguous: no gap exists between Sector holds and transitions.
10. JSON round-trip preserves plan identity and digest.
11. Unreal writes fresh diagnostics from UE 5.8 and spawns at least four connected rooms.
12. Unreal corridor count equals connection count.
13. Camera handoff windows equal the number of route transitions.
14. Proof diagnostics report zero empty-camera and zero stale-target windows.
15. Existing repository Python tests remain green.

## Validation

```powershell
.\scripts\run-underreach-multisector-validation.ps1
```

The script performs focused deterministic tests, runs the UE 5.8 headless construction proof, validates the fresh JSON artifact, then runs the full Python regression suite. It does not use GitHub Actions.

## Acceptance boundary

This slice proves connected geometry and a deterministic traversal/camera-handoff schedule. It does **not yet** claim that the existing live Descender actor and production Feed camera physically traverse the generated rooms. That integration is the next environment sub-slice after this foundation passes.

## Deferred

- bind a live Descender actor to the proof route;
- production Feed Follow/Auto camera integration across Sector boundaries;
- door opening/closing animation;
- authored corridor/door art;
- room walls/ceilings generated from theme modules rather than proof primitives;
- canonical transition events and Stratum progression;
- monster/encounter population.
