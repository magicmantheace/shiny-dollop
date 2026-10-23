# Underreach v0.10 — Slice 29E.6 Character Visual Polish & Render Proof

## Status

Implementation branch only. This slice is **not accepted** until the local validation script ends with an explicit:

```text
[29E.6] PASS
```

Accepted baseline: `c8519750144912bb6963791b748596e12c136592` (29E.5).

## Purpose

29E.6 is the final Phase-29 character/equipment slice. It proves that the accepted procedural Descenders, character materials, real equipment, and combat-fit attachment contracts can be presented as usable full-body Unreal renders rather than existing only as manifests and component bindings.

The simulation remains authoritative. 29E.6 is presentation-only and cannot change Character DNA, canonical inventory, combat timing/outcomes, animation identity, skeletal bindings, or material identity.

## Accepted source chain consumed

- 29E.2 real equipment digest: `f5fc053be8f23b788321096e6141b88caaaa3f653868e3b0ecd244a62dc8d2f6`
- 29E.3 equipment material/wear digest: `a8ab58180e51a6ae6245daaff75d7cf625c5cfa1e44dd07e49cde00cb9bcaa79`
- 29E.4 character material/appearance digest: `3614cedb01758a635e945bd506267d659aea120aad52fcf470f48937f0ad3b54`
- 29E.5 equipment/character combat integration digest: `88d194996aecc56076c136eb493e5d2ce4ca602f77b34e95c2f351bcfc44b4bb`

The local validator rebuilds and verifies this chain before 29E.6 may render anything.

## Deterministic render plan

Resolution: **1280 × 720**.

Camera bands:

- Near: **700 cm**
- Mid: **1300 cm**
- Far: **2400 cm**

Required shots:

1. `human_hero_near` — full-body Human material/equipment evaluation, 38° horizontal FOV.
2. `dwarf_hero_near` — full-body Dwarf material/equipment evaluation, 38° horizontal FOV.
3. `mixed_pair_mid` — Human/Dwarf mid-distance readability, 46° FOV.
4. `crowd_far` — crowd silhouette/material/equipment diversity at distance, 58° FOV.

The near/mid/far distances are deliberately inside the existing Crawl camera-planning envelope while leaving enough vertical room for the accepted full-body visual profile.

## Deterministic lighting rig

The offscreen proof constructs a disposable three-light studio rig:

- Key: 7000 intensity, 5000 K.
- Fill: 3800 intensity, 6500 K.
- Rim: 5200 intensity, 4200 K.

A floor and backdrop are also staged from engine basic geometry so the render target has a controlled, lit presentation environment.

## Character material proof

For each rendered Descender the Unreal proof loads the exact accepted 29E.4 per-Descender material instances for:

- skin
- hair
- eyes
- clothing

The accepted MPFB slot classifier is reused in the same order:

1. hair
2. eye
3. clothing
4. skin

Every assigned material is read back from the real `SkeletalMeshComponent`. Missing categories or wrong material paths are failures.

## Equipment proof

The proof uses the exact 29E.5 bindings:

- sword → `hand_r`
- helmet → `head`
- breastplate → `spine_03`

Each spawned equipment component is made `Movable`, attached directly to the skeletal component, and verified for:

- attachment success
- correct parent component
- correct socket/bone
- correct real StaticMesh
- correct 29E.3 per-Descender material instance
- accepted presentation scale
- sword grip alignment tolerance ≤ 0.05 cm

No floating/sliding substitute is accepted.

## Crowd diversity contract

The far shot contains 12 deterministically selected Descenders and must retain at least:

- 10 rendered Descenders
- both Human and Dwarf species
- 4 body variants
- 4 style profiles
- 8 distinct character-material fingerprints
- sword, helmet, and breastplate visual coverage

Selection is deterministic and favors new species, body variants, styles, equipment coverage, and material fingerprints.

## Real render proof

29E.6 does **not** use `-NullRHI` for its final step.

Prerequisite asset/material realization continues to use NullRHI, but the final proof starts Unreal with `-RenderOffScreen` and a real RHI. It uses `SceneCapture2D` + `TextureRenderTarget2D` to capture each required shot and exports actual PNG files through Unreal's rendering library.

Each render must:

- exist on disk
- be at least 4096 bytes
- contain non-black sampled pixels
- contain multiple sampled color bins / luminance variation
- satisfy the deterministic camera safe-frame calculation
- contain successfully bound character materials and equipment

Expected output directory:

```text
unreal/CrawlPresentation/Generated/underreach-29e6/renders/
```

Expected PNGs:

```text
human_hero_near.png
dwarf_hero_near.png
mixed_pair_mid.png
crowd_far.png
```

## Unreal validation flags

The Unreal diagnostics require all of the following:

- `all_six_body_mesh_assets_load`
- `character_materials_bound`
- `real_equipment_bound`
- `all_equipment_visuals_rendered`
- `human_dwarf_hero_rendered`
- `near_mid_far_rendered`
- `camera_distance_safe_frames`
- `lighting_rig_realized`
- `render_files_exported`
- `render_pixels_nonblank`
- `crowd_diversity_preserved`
- `presentation_non_authoritative`
- `proof_file_unchanged`
- `no_errors`
- `all_shots_valid`
- `all_pass`

## Validation command

From `D:\CrawlTesting`:

```powershell
.\scripts\run-underreach-character-visual-polish-render-validation.ps1
```

The script performs focused deterministic tests, rebuilds the accepted E2→E5 prerequisites, creates the four real GPU-backed renders, validates diagnostics and render artifacts, then runs the full repository regression suite.

## Phase boundary

A successful local `[29E.6] PASS` completes the canonical Phase-29 character/equipment visual foundation.

Only after that pass is accepted does development move to **30A.1 — Descent Run State**.
