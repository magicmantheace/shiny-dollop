# Underreach v0.10 — Slice 29D.2: Real Animation Binding & Contact Quality

## Purpose

29D.2 connects the accepted 29D.1 combat-presentation windows to **real Unreal animation source assets** without giving presentation any authority over simulation truth.

The authority chain remains:

`canonical encounter → 29D.1 presentation timing → 29D.2 animation binding/contact plan → Unreal consumer`

Simulation decides whether an attack happened, whether it hit, damage, death, outcome, participants, and event order. 29D.2 only decides which already-measured animation source should visually represent an accepted attack and what bounded presentation-only contact correction may be requested.

## Real attack assets

The acceptance proof requires all four existing Manny attack sources to be found and freshly measured by Unreal 5.8:

- `MM_Attack_01`
- `MM_Attack_02`
- `MM_Attack_03`
- `MM_ChargedAttack`

The existing `profile_mannequin_attacks.py` path evaluates these assets through Unreal's deterministic `AnimPose` component-space evaluator. The 29D.2 runner does not trust a stale checked-in measurement: it regenerates `attack_profiles_measured.json` locally before building the binding proof.

Each real attack binding records the asset path, source duration, contact phase/time, strike effector, measured forward reach, contact height, pose variation, accepted 29D.1 facing, Feed camera intent, and a bounded motion-warp/IK alignment request.

## Contact and motion policy

29D.2 does **not** move canonical actors to make a visual strike land. Canonical positions remain unchanged. If animation reach and canonical pair separation differ, the binding computes a presentation-only alignment request capped at 180 cm. That request is a future motion-warp/IK instruction, not simulation movement.

Unreal then independently reloads the real source asset and evaluates the bound contact time. Acceptance requires the evaluated strike reach to reproduce the freshly measured profile within 1 cm and requires multiple sampled poses to show meaningful movement rather than a frozen/held pose.

## Reaction and death assets

29D.2 does not claim that real reaction or death animation assets have been validated. Existing 29D.1 hit-reaction and death windows are carried forward with:

`binding_status = semantic_fallback`

and no real asset path. This is intentional. A later slice may promote reaction/death slots only after their source assets and contact/transition behavior receive equivalent validation.

## Feed and facing

29D.2 preserves accepted 29D.1 facing values and camera-shot intent exactly. Animation binding may not choose a different target, alter facing data, or replace the Feed shot schedule in order to hide a poor contact solution.

## Headless Unreal proof

`build_underreach_animation_binding_proof.py` runs under Unreal 5.8 with `-NullRHI -NoSound` and:

1. loads the real Manny reference skeletal mesh;
2. loads every bound real attack asset;
3. evaluates every bound attack at its measured contact time with `AnimPose`;
4. measures root-relative strike reach for the declared hand/foot effector;
5. samples multiple points in each clip to reject frozen animation data;
6. confirms all four required real attack assets were exercised;
7. confirms alignment requests remain bounded;
8. confirms 29D.1 facing and Feed camera intent were preserved;
9. confirms reaction/death bindings remain truthful semantic fallbacks; and
10. hashes the proof before and after consumption to prove Unreal did not mutate it.

This is a real animation-source/contact proof, not a final cinematic render. It deliberately avoids unattended live-component or temporary-Sequencer playback paths that previously produced held/frozen poses. Final custom-Descender retarget quality, authored reaction/death clips, weapon-specific IK, foot planting, and rendered combat polish remain later work.

## Acceptance command

```powershell
.\scripts\run-underreach-animation-contact-validation.ps1
```

Acceptance requires the runner to finish with:

```text
[29D.2] PASS
```

The runner performs focused deterministic tests, fresh Unreal attack profiling, duplicate binding-proof generation, headless Unreal contact validation, and the full repository regression suite.
