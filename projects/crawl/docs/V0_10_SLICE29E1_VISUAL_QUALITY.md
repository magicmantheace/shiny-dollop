# Underreach v0.10 Slice 29E.1 — Character & Equipment Visual Quality Foundation

## Purpose

Add a deterministic presentation-only quality layer above the accepted 29A Descender population and 29D combat presentation stack.

This slice improves variation, equipment fit, material/wear parameters, and visual provenance without allowing art or presentation code to change Character DNA, canonical inventory, combat timing, damage, death, or Ledger truth.

## Important art-status rule

The existing helmet, breastplate, and sword remain project-authored 29A proxy meshes. 29E.1 intentionally labels them `polished_proxy` and sets `production_art_required=true`. This slice must not misrepresent them as final production assets.

## Added protocol

`underreach.character-equipment-visual-quality.v1`

Generator version: `29e1.1`

## Deterministic visual directives

Each proof Descender receives deterministic style-driven material parameters for cloth, leather, and metal roughness; cloth/metal wear; dirt; saturation; and accent index.

Equipment fit is species/body aware:

- Dwarf swords use a shorter visual length scale.
- Dwarf helmets receive a larger head-fit scale.
- Breastplate X/Y/Z presentation fit is derived from shoulder width, mass, and species.
- Every scale axis is bounded to 0.70–1.20.

All equipment continues to consume the accepted 29A.1.1 skeletal-skin attachment sockets (`head`, `spine_03`, `hand_r`). No new canonical equipment is created.

## Unreal proof

The headless Unreal 5.8 consumer runs under `-NullRHI -NoSound` and verifies:

- every referenced equipment mesh loads;
- material variation did not collapse;
- presentation fit remains bounded;
- only accepted equipment attachment bones are used;
- all current equipment remains truthfully labelled as proxy art;
- the presentation authority boundary remains intact;
- the input proof file is byte-for-byte unchanged after Unreal consumes it.

## Acceptance command

```powershell
.\scripts\run-underreach-visual-quality-validation.ps1
```

Acceptance requires the runner to end with `[29E.1] PASS` after focused tests, deterministic proof reproduction, Unreal consumer validation, and the full repository regression suite.

## What this slice does not claim

29E.1 does **not** claim that the current proxy helmet, breastplate, or sword are final production-quality art. It creates the deterministic visual-quality and fit contract that future real asset replacements must satisfy. A later 29E slice can replace those proxy meshes without changing canonical simulation or Descender identity.
