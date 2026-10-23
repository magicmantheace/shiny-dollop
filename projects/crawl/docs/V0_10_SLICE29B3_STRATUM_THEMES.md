# Underreach v0.10 — Slice 29B.3: Stratum Themes & Material Variation

## Purpose

29B.3 adds a deterministic presentation-only theme layer on top of the accepted 29B.1/29B.2/29B.2.1 environment stack.

The simulation and Ledger remain authoritative. Theme choice may alter only visual presentation metadata. It must never change Sector identity, connectivity, world origin, Entry, Exit, Refuge, traversal legality, or the live Entry-to-Exit route.

## Protocol

`underreach.stratum-theme.v1`

Generator version: `29b3.1`

## Initial themes

- `ancient_stoneworks`
- `flooded_catacombs`
- `ember_foundry`

Each theme defines deterministic palettes for:

- floor material identity
- wall material identity
- ceiling material identity
- trim material identity
- prop identities
- lighting identity

The current slice deliberately stores stable presentation asset identities rather than requiring final production art. Those identities can later map to real Unreal materials, meshes, decals, Niagara effects, lights, and prop blueprints without changing the deterministic contract.

## Determinism

Each Sector uses its accepted `presentation_room_seed` to select palette entries through stable SHA-256 selection. Equal environment + equal theme must produce byte-equivalent semantic content and the same theme digest.

Changing the theme should produce a different visual digest while retaining the same topology fingerprint.

## Topology firewall

Every theme manifest records and validates:

- ordered Sector IDs
- ordered Stratum connections
- Sector world origins
- Entry Sector
- Exit Sector
- Refuge Sector
- source Stratum environment digest

Theme validation rejects any modification to those values.

## Unreal proof

The UE 5.8 proof constructs all three initial themes from one deterministic Stratum. Each theme copy is spatially offset only inside the proof scene so the three variants can coexist for inspection.

For every themed Sector the proof creates a room-floor proxy actor and writes the deterministic theme assignments into Unreal actor tags. The proof validates that:

- all three themes bind to the same Stratum environment digest
- all theme topology fingerprints are identical
- all three theme digests are distinct
- Entry, Exit, and Refuge are unchanged
- every expected themed Sector actor exists
- Unreal actors contain their deterministic theme metadata

`NullRHI` is used for remote/headless validation. Therefore this slice proves deterministic Unreal theme application metadata and topology preservation; it does not claim final rendered material quality.

## Acceptance criteria

29B.3 is accepted only when all of the following pass locally:

1. 29B.1, 29B.2, 29B.2.1, and 29B.3 focused deterministic tests.
2. Same environment/theme produces the same theme digest.
3. Different theme produces a different visual digest.
4. Different theme does not change topology, origins, Entry, Exit, or Refuge.
5. Every registered material/prop/light assignment is inside its declared theme palette.
6. UE 5.8 headless proof creates all themed Sector proxy actors.
7. Unreal actors receive deterministic theme metadata.
8. Full repository regression suite passes.

## Deferred

29B.3 does not yet require:

- final production material assets
- texture blending or vertex painting
- decals and grime passes
- Niagara atmosphere/VFX
- authored prop meshes
- animated environmental machinery
- dynamic water simulation
- final light fixtures or baked lighting
- Stratum-specific monsters

These can replace the proxy asset identities later while preserving the `underreach.stratum-theme.v1` deterministic manifest boundary.
