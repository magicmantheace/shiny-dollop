# Underreach v0.10 — Slice 29E.2 Real Equipment Asset Integration

## Purpose

29E.2 proves that the accepted 29E.1 equipment presentation contract can be replaced by **real loadable Unreal StaticMesh assets** without changing simulation truth.

The slice deliberately separates two claims:

- the meshes are real imported Unreal assets and can replace the procedural proxy realization;
- the meshes are **production candidates**, not final production art.

No 29E.2 presentation artifact may change Character DNA, canonical inventory, combat timing, damage, death, movement truth, Ledger events, or any other simulation outcome.

## Source mesh pipeline

The repository contains a deterministic project-authored mesh generator in `livingworld.underreach_equipment_asset_integration`.

The generator emits three ASCII OBJ sources in Unreal-centimeter scale:

- `UR_Sword_01.obj`
- `UR_Helmet_01.obj`
- `UR_Breastplate_01.obj`

Each source receives a SHA-256 identity in `underreach.real-equipment-source-manifest.v1`. The sources are intentionally simple project-authored production candidates so the complete real-asset pipeline is reproducible and does not depend on an untracked marketplace/download asset.

The source manifest explicitly records:

- project-authored provenance;
- source hash and byte count;
- intended Unreal object path;
- material-instance path;
- `art_status = production_candidate`;
- `final_art_required = true`.

## Unreal asset targets

The fresh validation run imports the three sources into:

- `/Game/Underreach29E2/Equipment/SM_UR_Sword_01`
- `/Game/Underreach29E2/Equipment/SM_UR_Helmet_01`
- `/Game/Underreach29E2/Equipment/SM_UR_Breastplate_01`

It also creates three real `MaterialInstanceConstant` assets under `/Game/Underreach29E2/Materials` and binds each equipment directive to a deterministic material-instance path.

These generated `.uasset` files are local derived presentation artifacts. The canonical, reviewable source is the deterministic text mesh generator plus source manifest/hashes.

## Accepted contracts preserved from 29E.1

For every equipment directive 29E.2 preserves:

- Descender identity;
- visual ID;
- equipment slot;
- attachment socket (`hand_r`, `head`, or `spine_03`);
- attachment mode;
- full accepted source attachment record;
- Human/Dwarf presentation fit scale;
- Character renderer identity;
- material/wear presentation parameters;
- facial contract;
- actor/stride/foot-IK presentation values.

29E.2 changes only the equipment **visual realization** from `procedural_proxy` to `real_static_mesh_asset`.

## Protocols

Integration proof:

`underreach.real-equipment-asset-integration.v1`

Source manifest:

`underreach.real-equipment-source-manifest.v1`

Unreal diagnostics:

`underreach.real-equipment-asset-integration-unreal-debug.v1`

Generator version:

`29e2.1`

## Validation

Run:

```powershell
.\scripts\run-underreach-real-equipment-validation.ps1
```

The runner requires:

1. accepted 29A/29D/29E.1 regressions and focused 29E.2 tests;
2. deterministic source OBJ generation;
3. deterministic integration proof generation;
4. exact source SHA-256 stability across regeneration;
5. exactly three source equipment candidates;
6. fresh Unreal 5.8 headless import of all three OBJ sources as `StaticMesh` assets;
7. fresh creation/load of all three `MaterialInstanceConstant` assets;
8. every equipment directive resolving to its expected real mesh and material instance;
9. Human/Dwarf fit scale remaining within 0.70–1.20;
10. attachment bones remaining limited to `hand_r`, `head`, and `spine_03`;
11. production-candidate/non-final art status remaining truthful;
12. proof file remaining byte-identical after Unreal consumption;
13. full repository regression suite.

Acceptance requires the runner to finish with:

```text
[29E.2] PASS
```

## Non-goals

29E.2 is not the final equipment art pass. It does not claim sculpted/high-poly production quality, final textures, cloth simulation, damage decals, weapon trails, or final cinematic material polish. It establishes the real-asset replacement contract those later art upgrades will use.
