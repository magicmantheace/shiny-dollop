# Underreach v0.10 — Slice 29B.2.1

## Live Multi-Sector Traversal & Feed Integration

### Purpose

Prove that the accepted deterministic Stratum and multi-Sector presentation layout can drive one live Descender presentation actor through multiple connected Sectors in Unreal while Follow and Auto Feed cameras remain attached across every Sector boundary.

This slice is still downstream presentation. It does **not** grant movement permission, resolve gameplay, change canonical outcomes, or make presentation state authoritative.

## Invariants

1. The accepted `underreach.stratum-environment.v1` manifest remains the spatial source.
2. The accepted `underreach.multisector-presentation.v1` plan remains the connected-room/corridor source.
3. Live traversal uses `underreach.live-multisector-traversal.v1` and is explicitly `authoritative: false`.
4. The Descender actor moves through the Entry→Exit proof route in generated Sector order.
5. Follow and Auto channels keep the same live Descender target on every frame.
6. No empty camera window is permitted during a Sector transition.
7. No stale target window is permitted during a Sector transition.
8. Checkpoint/resume preserves the exact Stratum digest, multi-Sector digest, Descender identity, current Sector, and presentation transform.
9. Resume reaches the same Exit Sector without regenerating a different layout.
10. Unreal validation uses artifact freshness and validation flags rather than trusting editor shutdown exit code.
11. Remote/headless validation uses NullRHI; this slice validates state, geometry traversal, camera transforms, and continuity rather than rendered pixels.

## Acceptance Gate

Run:

```powershell
.\scripts\run-underreach-live-multisector-validation.ps1
```

Acceptance requires all of the following:

- 29B.1, 29B.2, and 29B.2.1 focused deterministic tests pass.
- The Unreal 5.8 proof writes a fresh `live-multisector-unreal-debug.json`.
- One Descender presentation actor physically traverses at least two Sectors.
- Sector transition count equals route Sector count minus one.
- Follow Feed has zero empty and zero stale target windows.
- Auto Feed has zero empty and zero stale target windows.
- Descender and both camera actors remain within 0.01 cm of their deterministic presentation stream transforms.
- A checkpoint is written mid-route.
- Checkpoint preserves the same Stratum and multi-Sector digests.
- Checkpoint preserves the current Sector and Descender identity.
- Resume begins at the checkpoint frame and reaches the same Exit Sector.
- Full repository regression suite passes.

## Deferred

The following remain outside 29B.2.1:

- rendered visual-quality validation of camera transitions;
- authored locomotion and turn-in-place animation across corridors;
- NavMesh/pathfinding-driven canonical movement permissions;
- doors with gameplay state, locks, hazards, or secret routes;
- encounter/monster spawning by Sector;
- Stratum theme/material families;
- production streaming/deployment concerns.

Those belong to later 29B/29C slices. The core rule remains: **simulation truth is authoritative; live traversal, Feed cameras, and Unreal presentation can only visualize accepted state.**
