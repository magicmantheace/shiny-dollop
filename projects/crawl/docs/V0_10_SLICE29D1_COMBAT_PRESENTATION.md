# Underreach v0.10 — Slice 29D.1 Combat Presentation Foundation

## Purpose

29D.1 turns the accepted 29C.3 autonomous encounter stream into a deterministic, presentation-only combat schedule suitable for Unreal playback.

The governing rule remains:

> THE SIMULATION CREATES THE EVENTS. THE PRESENTATION SYSTEM ONLY STAGES THEM.

Simulation truth remains authoritative. Animation, camera timing, reaction timing, presentation offsets, and presentation duration may never change canonical movement, hit/miss, damage, death, retreat, encounter outcome, or Ledger identity.

## Inputs

The slice consumes an accepted `underreach.autonomous-encounter-flow.v1` proof from 29C.3.

Required source facts include:

- canonical digest,
- canonical frame sequence,
- actor positions,
- canonical action kinds,
- hit/miss and damage values,
- Descender state,
- monster alive/health state,
- Feed focus,
- encounter outcome.

## Output protocol

`underreach.combat-presentation.v1`

The manifest is explicitly:

- `authoritative: false`,
- `simulation_time_independent: true`,
- `canonical_state_mutation_allowed: false`,
- bound to the exact source canonical digest and source proof digest.

## Presentation schedule

Each canonical action can generate one or more presentation windows.

### Movement

Canonical movement produces a locomotion window with:

- canonical start/end position references,
- deterministic facing toward the canonical target,
- a bounded turn duration,
- a semantic locomotion slot,
- a Feed shot intent.

This does not introduce pathfinding or new movement.

### Attacks

Canonical attack actions are split only for presentation into:

1. wind-up,
2. contact,
3. recovery.

The canonical hit/miss and damage are copied into the presentation window. Animation timing cannot alter them.

Default semantic attack slots are:

- `humanoid.combat.attack.default`
- `enemy.biped.combat.attack.default`

These preserve compatibility with the existing validated attack-slot system. More authored animation selection can be layered later without changing this contract.

### Hit reactions

A hit reaction may only be created when the source canonical action says `hit: true`.

Misses cannot receive hit reactions.

The presentation can carry a small non-authoritative reaction-offset hint. The offset is visual only and must not be written back into canonical actor position.

### Death transitions

A death window may only appear when the source frame already marks the target dead after a canonical hit.

Death presentation is therefore downstream of simulation truth, never a cause of death.

Default semantic death slots are:

- `humanoid.death.default`
- `enemy.biped.death.default`

### Facing

Facing yaw is derived from canonical actor/target positions. It is presentation-only and does not affect attack resolution.

### Feed camera intent

29D.1 introduces simple action-aware shot categories:

- `follow_action`
- `combat_pair`
- `threat_reveal`
- `wide_context`
- `aftermath_hold`

The camera remains a consumer. It cannot select targets for the simulation or affect outcomes.

## Simulation time vs presentation time

29D.1 formalizes the distinction:

`SIMULATION TIME != ANIMATION TIME`

Canonical ticks remain untouched. The presentation schedule maps them into a separate timeline so an attack can have readable wind-up/contact/recovery timing without forcing the deterministic simulation to wait for an animation.

## Unreal proof

`build_underreach_combat_presentation_proof.py` runs headlessly under Unreal Engine 5.8 with `-NullRHI -NoSound`.

The proof:

- reads a pre-generated proof artifact,
- verifies source authority and presentation non-authority,
- spawns proxy Descender/monster actors,
- applies canonical positions,
- applies deterministic facing yaw,
- applies semantic action tags,
- drives an action-aware Feed camera,
- verifies no empty/stale Feed focus,
- verifies actor position and facing accuracy,
- hashes the source file before/after Unreal and requires it to remain unchanged.

The proof does **not** run combat inside Unreal.

## Acceptance criteria

29D.1 is accepted only if local validation proves all of the following:

1. Focused 29B → 29D.1 tests pass.
2. Identical generation reproduces the source canonical digest.
3. Identical generation reproduces the 29D.1 presentation digest.
4. Presentation remains non-authoritative.
5. Simulation and presentation clocks remain explicitly separate.
6. Every presentation window references a real canonical frame/action.
7. Every canonical hit receives one reaction window.
8. Canonical misses receive no hit-reaction window.
9. Death windows can only follow canonical death state.
10. Facing is deterministically derived and bounded.
11. Unreal consumes every presentation window.
12. Unreal actor position error is <= 0.01 cm.
13. Unreal facing error is <= 0.01 degrees.
14. Feed has zero empty focus windows.
15. Feed has zero stale focus windows.
16. Unreal applies attack and reaction semantic slots.
17. At least two action-aware camera shot categories are exercised by the proof.
18. Unreal does not modify the generated proof artifact.
19. Full repository regression suite passes.

## Deferred

29D.1 is a foundation slice. It does not claim final production combat visuals.

Deferred work includes:

- authored turn-in-place footwork,
- real skeletal attack animation playback for every monster family,
- animation montage blending,
- weapon-specific attack selection,
- IK/contact correction,
- authored hit reactions,
- physically convincing knockback,
- ragdoll or authored corpse settling,
- blood/VFX/audio impacts,
- motion warping,
- camera collision/occlusion polish,
- cinematic shot blending,
- production combat lighting,
- final animation quality.

Those layers must continue to consume the canonical action schedule rather than becoming gameplay authority.
