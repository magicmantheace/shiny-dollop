# Underreach v0.10 — Slice 29E.5 Equipment/Character Combat Integration

## Purpose

29E.5 integrates the accepted real equipment and character presentation layers with real animated Human/Dwarf combat presentation.

The slice proves that:

- real sword, helmet, and breastplate meshes remain attached to accepted character skeletons;
- swords align their authored grip region to `hand_r`;
- helmets remain attached to `head` through hit reactions and deaths;
- breastplates remain attached to `spine_03` through hit reactions and deaths;
- Human and Dwarf body variants use their own accepted native Attack/Reaction/Death animation assets;
- equipment follows animated bones rather than remaining in world space;
- no presentation binding can change canonical inventory, combat timing, damage, death, Character DNA, or Ledger truth.

## Accepted source chain

29E.5 starts from accepted 29E.4 commit:

`02e6640c1fdb14148e8498f68423a447d5555749`

Accepted deterministic source digests:

- 29E.2 real equipment: `f5fc053be8f23b788321096e6141b88caaaa3f653868e3b0ecd244a62dc8d2f6`
- 29E.3 equipment material/wear: `a8ab58180e51a6ae6245daaff75d7cf625c5cfa1e44dd07e49cde00cb9bcaa79`
- 29E.4 character material/appearance: `3614cedb01758a635e945bd506267d659aea120aad52fcf470f48937f0ad3b54`

Default proof seed remains:

`underreach-29e2-real-equipment-proof`

The accepted population contains 24 Descenders and 52 equipment integration directives.

## Presentation authority boundary

The 29E.5 manifest explicitly keeps all of these false:

- `canonical_inventory_mutation_allowed`
- `character_dna_mutation_allowed`
- `combat_timing_mutation_allowed`
- `combat_outcome_mutation_allowed`
- `animation_asset_mutation_allowed`
- `skeletal_mesh_binding_mutation_allowed`

The deterministic simulation and authoritative Ledger continue to decide what happened. 29E.5 only decides how already-canonical combat is presented.

## Equipment bindings

| Equipment | Slot | Accepted bone |
| --- | --- | --- |
| Sword | `right_hand` | `hand_r` |
| Helmet | `head_armor` | `head` |
| Breastplate | `chest_armor` | `spine_03` |

The real mesh and per-Descender material instance paths are inherited exactly from accepted 29E.3.

## Variant-native combat assets

29E.5 uses the existing native Underreach combat clips for each MPFB body variant rather than forcing Manny assets directly onto a different skeleton.

Families validated:

- Human average — `A_UnderreachHuman_Attack`, `Reaction`, `Death`
- Human short/heavy — `A_UnderreachHumanShortHeavy_Attack`, `Reaction`, `Death`
- Human tall/thin — `A_UnderreachHumanTallThin_Attack`, `Reaction`, `Death`
- Dwarf average — `A_UnderreachDwarf_Attack`, `Reaction`, `Death`
- Dwarf heavy — `A_UnderreachDwarfHeavy_Attack`, `Reaction`, `Death`
- Dwarf alternate — `A_UnderreachDwarfAlt_Attack`, `Reaction`, `Death`

The accepted 24-person proof does not necessarily contain every body variant, so the Unreal proof independently loads and verifies all six variant asset families.

## Weapon-hand alignment

The generated sword mesh has an authored grip region centered approximately 8.5 cm below its object origin on local Z.

29E.5 applies the inverse, presentation-scale-aware local offset after attachment so the grip center—not merely the sword object origin—lands on `hand_r`.

Maximum accepted grip-center alignment error:

`0.05 cm`

The weapon is attached to the skeletal component at `hand_r`, so the relative attachment relationship remains constant while the hand moves through the attack animation.

## Armor persistence

Helmet and breastplate bindings are not detached or replaced during reaction/death presentation.

The Unreal proof samples their target bones through variant-native hit-reaction and death clips with `AnimPose`. The sampled target bone must demonstrate real animation motion while the equipment retains a skeletal-bone-follow attachment contract.

This proves the equipment is following the animated character rather than being left behind as world-space geometry.

## Unreal proof

The proof runs headlessly with `-NullRHI -NoSound` and does not require viewport playback.

It validates:

- all six variant mesh/Attack/Reaction/Death families load;
- both Human and Dwarf families are represented;
- real StaticMesh equipment loads;
- accepted 29E.3 material instances load;
- live spawned equipment components attach to the exact accepted bones;
- attached component parent/socket/mesh/material readback is correct;
- sword grip-center alignment is within tolerance;
- `hand_r` moves through attack poses;
- `head` / `spine_03` move through reaction/death poses;
- no attachment errors occur;
- proof JSON remains unchanged;
- authority remains presentation-only.

## Clean prerequisite reconstruction

The 29E.5 validation runner does not rely on generated Unreal assets left behind by previous validation sessions.

It first rebuilds exact accepted 29E.2 source/meshes, then realizes exact accepted 29E.3 per-Descender equipment material instances, then executes 29E.5.

## Local validation

From `D:\CrawlTesting`:

```powershell
git fetch origin
git switch agent/underreach-v0.10-slice29e5-equipment-character-combat-integration
git pull --ff-only
.\scripts\run-underreach-equipment-character-combat-integration-validation.ps1
```

Acceptance requires the final explicit line:

```text
[29E.5] PASS
```

A successful deterministic or Unreal sub-proof alone is not sufficient for slice acceptance; the full repository regression suite must also pass.

## Outputs

Primary proof:

`unreal/CrawlPresentation/Generated/underreach-29e5/equipment-character-combat-integration-proof.json`

Unreal diagnostics:

`unreal/CrawlPresentation/Generated/underreach-29e5/equipment-character-combat-unreal-debug.json`

Unreal log:

`unreal/CrawlPresentation/Generated/underreach-29e5/unreal-equipment-character-combat-integration.log`

## Next canonical slice after acceptance

**29E.6 — Character Visual Polish & Render Proof**

29E.6 will provide full-body rendered proof, lighting/material evaluation, camera-distance quality checks, crowd visual diversity, and final Phase-29 character/equipment acceptance.
