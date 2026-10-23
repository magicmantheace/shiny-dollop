# Underreach v0.10 Slice 29E.3 — Equipment Material & Wear Realization

## Purpose

29E.3 turns the deterministic visual identity values accepted in 29E.1 into real Unreal material assets layered over the real equipment meshes accepted in 29E.2.

The slice remains presentation-only. It does not change Character DNA, canonical inventory, combat timing, attachment sockets, equipment fit, mesh identity, or Ledger truth.

## Source chain

- 29E.1 supplies deterministic material identity: metal/leather roughness, saturation, metal wear, dirt, and accent selection.
- 29E.2 supplies the three accepted real StaticMesh equipment candidates and their attachment/fit contract.
- 29E.3 converts those inputs into deterministic Unreal material parameters without changing either source contract.

## Reusable material hierarchy

29E.3 uses a shared hierarchy instead of unrelated one-off materials:

```text
M_UR_Equipment_Master
        ↓
MI_UR_Sword_01
MI_UR_Helmet_01
MI_UR_Breastplate_01
        ↓
per-Descender MaterialInstanceConstant
```

The master material lives under `/Game/Underreach29E3/Materials`. The three reusable item templates live under `/Game/Underreach29E3/Materials/Items`, and deterministic per-Descender instances live under `/Game/Underreach29E3/Materials/Descenders`.

The shared 29E.2 StaticMesh assets remain immutable. 29E.3 applies per-Descender material identity through a `StaticMeshComponent` material override.

## Realized parameters

The master material exposes and consumes:

- `MetalTint`
- `LeatherTint`
- `AccentTint`
- `Roughness`
- `Metallic`
- `WearAmount`
- `DirtAmount`
- `EdgeWear`
- `LeatherMix`
- `AccentMix`
- `Saturation`
- `ValueVariation`
- `MaterialVariationSeed`

Style profile selects bounded metal and leather tone families. The accepted 29E.1 accent index and saturation drive the accent tint. The accepted metal wear and dirt values become explicit Unreal parameters. Deterministic per-item variation supplies bounded value variation, edge wear, and a stable material variation seed.

The material graph makes these values visible rather than storing them only as metadata:

- dirt darkens/tints the equipment surface;
- wear shifts the surface toward a worn-metal tone;
- `EdgeWear` drives a Fresnel-based edge highlight suitable for the current production-candidate geometry;
- roughness and metallic remain real material inputs;
- leather and accent mixes tint the single-material 29E.2 candidates without pretending those simple meshes contain final authored material masks;
- value/seed variation gives same-style Descenders bounded individual variation.

The current three project-authored meshes remain production candidates, not final art. Future replacement meshes can add proper authored masks and textures without changing the deterministic parameter contract.

## Preservation guarantees

29E.3 copies and validates the accepted 29E.2 mesh path, attachment bone, attachment mode, and presentation scale for every equipment directive.

Accepted bones remain exactly:

- sword → `hand_r`
- helmet → `head`
- breastplate → `spine_03`

The 29E.2 digest, 29E.1 digest, population digest, visual identity digest, renderer manifest digest, and asset registry digest are retained as provenance. The material layer has no API for mutating canonical Character DNA, inventory, combat timing, or simulation state.

## Local acceptance

29E.3 is accepted only when `scripts/run-underreach-equipment-material-wear-validation.ps1` ends in `[29E.3] PASS`.

The runner verifies:

1. same seed reproduces identical material parameters and digest;
2. different seeds produce bounded deterministic variation;
3. 29E.1, 29E.2, and 29D.4 focused regressions pass;
4. the accepted 29E.2 real meshes are rebuilt and load successfully;
5. the reusable master material and all three item MaterialInstanceConstant templates load successfully;
6. every Descender equipment directive receives a unique MaterialInstanceConstant;
7. all vector/scalar parameters round-trip through Unreal within tolerance;
8. wear, dirt, edge wear, style tones, color, and roughness variation do not collapse;
9. real 29E.2 meshes accept the generated per-Descender material overrides on proof StaticMeshComponents;
10. Human/Dwarf fit and accepted attachment bones remain unchanged;
11. authority flags remain presentation-only;
12. Unreal does not modify the deterministic proof file;
13. the full repository regression suite passes.

The Unreal proof runs with `-NullRHI -NoSound` and writes concise diagnostics to:

`unreal/CrawlPresentation/Generated/underreach-29e3/equipment-material-unreal-debug.json`

## Non-goals

29E.3 does not change gameplay outcomes, canonical inventory, equipment statistics, damage, animation timing, Character DNA, or simulation truth. It does not claim final production-quality textures or masks. It establishes the deterministic material/wear realization pipeline that later production art can consume.
