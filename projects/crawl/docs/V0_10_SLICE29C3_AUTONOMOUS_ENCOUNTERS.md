# Underreach v0.10 — Slice 29C.3 Autonomous Monster Behavior & Encounter Flow

## Purpose

29C.3 turns the bounded 29C.2 combat proof into a deterministic encounter that unfolds across simulation ticks. Monsters are no longer presentation-only proxies waiting for a single all-at-once combat resolution. They acquire targets, pursue Descenders, attack, take damage, die, and drive an action-aware Feed schedule from canonical simulation truth.

The governing invariant remains:

> **THE SIMULATION CREATES THE EVENTS. PRESENTATION ONLY REPLAYS THEM.**

Unreal, the Feed camera, animation, audio, and future AI dialogue are not allowed to create a hit, miss, movement result, target choice, retreat, death, victory, or defeat.

## Authority chain

```text
29C.1 deterministic encounter plan
        ↓ explicit 29C.2 promotion
Canonical EncounterState
        ↓
29C.3 deterministic tick loop
        ↓
Canonical positions / targets / attacks / health / outcome
        ↓
Authoritative Ledger
        ↓
Read-only presentation frames + Feed focus schedule
        ↓
Unreal replay
```

## Protocols

Canonical flow:

```text
underreach.autonomous-encounter-flow.v1
```

Presentation projection:

```text
underreach.autonomous-encounter-presentation.v1
```

Unreal diagnostics:

```text
underreach.autonomous-encounter-unreal-debug.v1
```

Generator version:

```text
29c3.1
```

## Canonical behavior

`src/livingworld/underreach_autonomous_encounters.py` runs one promoted encounter over bounded simulation ticks.

Each tick may contain:

- Descender entry into the encounter.
- Descender movement toward a living monster.
- Descender attacks with deterministic hit/damage rolls.
- Monster target acquisition using canonical Descender state.
- Monster pursuit movement.
- Monster attacks with deterministic hit/damage rolls.
- Descender retreat when health pressure and deterministic retreat roll allow it.
- Descender death through the existing lifecycle service.
- Monster defeat.
- Explicit encounter termination as `victory`, `defeat_or_retreat`, or `timeout`.

All randomness is derived from stable SHA-256 input consisting of the Descent seed, simulation tick, actor, target, and action channel.

## Spatial rules

29C.3 uses the selected 29B Sector's accepted combat-clearance area as its local canonical encounter arena. Actor positions are represented in Sector-local centimeters and are replayed directly by Unreal.

This does **not** yet migrate the complete 29B Stratum graph into the authoritative Crawl navigation model. The same boundary established by 29C.2 remains: the promoted encounter owns a valid canonical CrawlLocation while source Sector identity is retained as binding metadata.

That larger graph migration belongs in a later Descent/progression slice rather than being hidden inside combat work.

## Ledger events

29C.3 introduces bounded Underreach event types including:

- `UNDERREACH_AUTONOMOUS_ENCOUNTER_STARTED`
- `UNDERREACH_DESCENDER_ENTERED_ENCOUNTER`
- `UNDERREACH_DESCENDER_MOVED_IN_ENCOUNTER`
- `UNDERREACH_DESCENDER_ATTACKED_MONSTER`
- `UNDERREACH_MONSTER_TARGET_ACQUIRED`
- `UNDERREACH_MONSTER_MOVED`
- `UNDERREACH_MONSTER_ATTACKED`
- `UNDERREACH_MONSTER_DEFEATED`
- `UNDERREACH_DESCENDER_RETREATED_FROM_ENCOUNTER`
- `UNDERREACH_LIVE_ENCOUNTER_ENDED`

Existing lifecycle death events remain authoritative when a Descender dies.

## Feed behavior

Every canonical simulation frame receives a deterministic `feed_focus_actor_id` derived from the most important action in that frame.

Priority favors attacks, then target acquisition, movement, and entry. The presentation contract copies the canonical frames exactly and exposes a `feed_focus_schedule` containing only canonical actor IDs.

Acceptance requires:

- zero empty Feed focus windows;
- zero stale actor references;
- exact frame count;
- exact Ledger identity/order;
- exact canonical outcome;
- presentation frames byte-for-byte semantically equal to canonical frames.

The camera schedule is still a presentation decision. It cannot modify the encounter.

## Unreal proof

`build_underreach_autonomous_encounter_proof.py` runs in Unreal 5.8 with `-NullRHI -NoSound`.

It:

1. reads the canonical JSON generated outside Unreal;
2. records its SHA-256 before replay;
3. spawns Descender and monster proxy actors;
4. replays every canonical actor transform;
5. moves a Feed camera relative to the canonical focus actor on every frame;
6. verifies attack and target-acquisition frames exist;
7. verifies actor placement error is <= 0.01 cm;
8. verifies Feed focus never becomes empty or stale;
9. verifies Ledger identity and outcome remain exact;
10. hashes the canonical JSON again and requires it to be unchanged.

The proof does not run combat inside Unreal.

## Validation

Run:

```powershell
.\scripts\run-underreach-autonomous-encounter-validation.ps1
```

The runner performs:

1. focused tests for 29B.1 through 29C.3;
2. autonomous encounter stress coverage;
3. two independent canonical proof generations with identical inputs;
4. exact canonical/proof digest reproduction;
5. bounded multi-tick flow checks;
6. required Ledger event checks;
7. headless Unreal 5.8 replay and Feed-camera proof;
8. canonical-file immutability check across Unreal;
9. full repository `pytest -q` regression suite.

## Acceptance criteria

29C.3 is accepted only if local validation proves all of the following:

- identical inputs reproduce identical canonical and proof digests;
- encounter unfolds over multiple bounded simulation ticks;
- Descenders enter and act through canonical state;
- monsters acquire canonical live targets;
- movement and attack activity are represented in the Ledger;
- health and monster-alive state are simulation-owned;
- encounter terminates with an explicit canonical outcome;
- presentation is non-authoritative and bound to the canonical digest;
- presentation tampering is rejected;
- every Feed frame references a real actor;
- Unreal replays all canonical frames with <= 0.01 cm actor-position error;
- Unreal Feed tracking has zero empty/stale windows;
- Unreal does not modify the canonical artifact;
- focused tests pass;
- full repository regression suite passes.

## Explicitly deferred

29C.3 is behavior/flow infrastructure, not final combat presentation. It does not claim:

- authored monster skeletal meshes or animation sets;
- pathfinding/NavMesh around complex room obstacles;
- attack windups, hit reactions, dodges, blocks, knockback, or turn-in-place animation;
- animation timing synchronized to weapons and hit frames;
- advanced formation/group monster tactics;
- boss phase logic;
- ranged projectile presentation;
- production VFX/SFX;
- canonical whole-Stratum traversal graph migration;
- final Feed cinematography.

Those are downstream work, with 29D focused on combat presentation quality.
