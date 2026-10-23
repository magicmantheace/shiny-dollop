# Underreach v0.10 — Slice 29C.1 Monster & Encounter Foundation

## Purpose

Slice 29C.1 establishes deterministic monster content definitions and deterministic Sector encounter plans on top of the accepted 29B Stratum stack.

This slice does **not** make monster placement or combat canonical simulation truth yet. The encounter plan is explicitly non-authoritative scaffolding. A later simulation-integration slice must validate/promote encounter intent into deterministic simulation state before any monster can affect damage, death, inventory, progression, Arbiter enforcement, or the Ledger.

## Protocols

- Monster definition: `underreach.monster-definition.v1`
- Encounter plan: `underreach.encounter-plan.v1`
- Unreal proof diagnostics: `underreach.monster-encounter-unreal-debug.v1`
- Generator version: `29c1.1`

## Initial monster catalog

The first content catalog contains five placeholder gameplay/presentation archetypes:

- Stone Maw — burrower, threat 2
- Vault Stalker — stalker, threat 3
- Drowned Thrall — thrall, threat 1
- Ember Hound — hound, threat 2
- Forge Brute — construct, threat 4

Each definition carries a stable ID, family, threat value, compatible Stratum themes, proxy dimensions, and presentation tags. These are data definitions, not final art assets or final balance values.

## Deterministic encounter generation

`build_encounter_plan(environment, theme_manifest)`:

- binds to the accepted Stratum environment digest;
- preserves Sector IDs, connections, origins, Entry, Exit, and Refuge;
- never places encounters in Entry or Refuge Sectors;
- selects theme-compatible monster definitions deterministically from each Sector's `presentation_room_seed`;
- produces stable member IDs;
- keeps presentation spawn offsets inside the accepted combat-clearance region;
- produces stable total-threat values;
- produces a stable SHA-256 plan digest;
- states `promotion_required_for_canonical_combat: true`.

## Authority boundary

The simulation remains authoritative.

29C.1 may decide what a presentation/content encounter *would contain*. It cannot:

- deal damage;
- kill a Descender;
- award or remove inventory;
- alter progression;
- alter Stratum topology;
- create canonical Ledger outcomes;
- override Arbiter rules.

Future simulation integration must convert a validated encounter intent into deterministic simulation entities/events. Unreal only visualizes the resulting state.

## Unreal proof

`build_underreach_monster_encounter_proof.py` runs in UE 5.8 under `-NullRHI` and:

1. builds a deterministic 12-Sector Stratum;
2. applies the accepted 29B.3 theme layer;
3. generates a 29C.1 encounter plan;
4. spawns one proxy Unreal actor for every generated monster member;
5. tags every actor with monster, Sector, encounter, and theme identity;
6. measures actor placement error;
7. verifies no Entry/Refuge monster spawns;
8. verifies every spawn remains within combat clearance;
9. verifies the Stratum topology fingerprint is unchanged;
10. writes fresh JSON diagnostics.

The proxy cubes are deliberately temporary. This slice proves deterministic encounter data and Unreal binding, not production monster models or animation.

## Acceptance runner

Run:

```powershell
.\scripts\run-underreach-monster-encounter-validation.ps1
```

Acceptance requires:

- 29B.1, 29B.2, 29B.2.1, 29B.3, and 29C.1 focused deterministic tests pass;
- deterministic 250-Sector stress generation passes;
- Unreal creates fresh 29C.1 diagnostics;
- at least one meaningful encounter and monster spawn exists;
- Entry/Refuge spawn count is zero;
- maximum Unreal actor placement error is <= 0.01 cm;
- every spawn is inside combat clearance;
- Stratum topology remains identical;
- the canonical-combat promotion boundary remains explicit;
- full repository regression suite passes.

## Deferred to later 29C slices

- canonical simulation monster entities;
- deterministic monster AI/tactical behavior;
- combat resolution against Descenders;
- health/damage/death integration;
- Ledger encounter/combat events;
- live Feed combat coverage across encounters;
- checkpoint/resume of active encounters;
- real monster meshes, rigs, animation, VFX, audio, materials;
- encounter pacing, elite/boss logic, rewards, and balance.

## Intended next slice

29C.2 should promote encounter plans into deterministic simulation entities and prove one complete live encounter from spawn through combat outcome, Ledger recording, Unreal presentation, and checkpoint/resume without allowing presentation code to influence canonical truth.
