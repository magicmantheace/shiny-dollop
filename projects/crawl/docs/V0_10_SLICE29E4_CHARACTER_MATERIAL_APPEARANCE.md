# Underreach v0.10 Slice 29E.4 — Character Material & Appearance Realization

## Purpose

29E.4 turns the deterministic Descender appearance identity already accepted in 29A/29E.1 into real Unreal material assets for the existing Human and Dwarf skeletal characters.

The slice remains presentation-only. It does not change Character DNA, canonical inventory, combat timing, animation bindings, skeletal-mesh identity, equipment bindings, or Ledger truth.

## Source chain

- 29A.2 supplies deterministic Human/Dwarf Character DNA, skin/eye variants, hair/facial-hair identity, clothing identity, body variant, body scale, facial contract, and renderer identity.
- 29E.1 supplies accepted style-driven cloth roughness, cloth wear, dirt, saturation, and accent index.
- 29E.3 remains the exact accepted equipment material/wear source and provides the current accepted visual baseline/provenance chain.
- 29E.4 realizes character surfaces without modifying any of those inputs.

## Reusable material hierarchy

```text
M_UR_Character_Master
        ↓
MI_UR_Skin_Template
MI_UR_Hair_Template
MI_UR_Eye_Template
MI_UR_Clothing_Template
        ↓
per-Descender MaterialInstanceConstant
```

The master material lives under `/Game/Underreach29E4/Materials`. Reusable category templates live under `/Game/Underreach29E4/Materials/Templates`. Deterministic per-Descender instances live under `/Game/Underreach29E4/Materials/Descenders`.

For the accepted 24-Descender proof this creates 96 deterministic character material directives: four per Descender.

## Realized appearance domains

### Skin

- deterministic `skin_variant` from Character DNA selects a bounded skin-tone family;
- stable per-Descender value variation prevents same-variant clones;
- accepted dirt contributes a reduced presentation-only skin dirt amount;
- roughness/specular receive bounded individual variation.

### Hair and facial hair

- existing deterministic hair/facial-hair asset identity is preserved;
- stable material variation supplies hair tone, roughness, and specular differences;
- facial hair shares the character's hair material family instead of creating a second identity system.

### Eyes

- deterministic Character DNA `eye_variant` selects the eye color family;
- eyes use lower roughness and higher specular response than hair/cloth;
- eye identity remains tied to the existing DNA digest.

### Clothing

- existing clothing asset identity is unchanged;
- style profile selects the bounded clothing color family;
- accepted 29E.1 `cloth_roughness`, `cloth_wear`, `dirt_amount`, `saturation`, and `accent_index` are consumed directly;
- clothing color/accent variation remains deterministic per Descender.

## Unreal realization

The Unreal proof creates the real master material, four reusable MaterialInstanceConstant templates, and all per-Descender MaterialInstanceConstants. Every vector/scalar parameter is read back through Unreal and compared against the deterministic proof.

The proof loads the exact accepted 29A Human/Dwarf SkeletalMesh variants and applies generated materials as temporary `SkeletalMeshComponent` material overrides. Shared SkeletalMesh assets are not modified.

Material slots are classified from their imported slot/material identity into skin, hair/facial-hair, eye, or clothing categories. The acceptance proof must observe and bind all four categories across both Human and Dwarf Descenders.

## Preserved skeletal variants

29E.4 keeps the existing six accepted presentation mappings available:

- `human_average`
- `human_short_heavy`
- `human_tall_thin`
- `dwarf_average`
- `dwarf_heavy`
- `dwarf_alt`

It preserves the renderer-manifest body mesh selection, actor scale, stride scale, foot IK offset, visual identity digest, renderer manifest digest, and facial contract.

## Authority boundary

All of the following remain explicitly false:

- `character_dna_mutation_allowed`
- `canonical_inventory_mutation_allowed`
- `combat_timing_mutation_allowed`
- `animation_binding_mutation_allowed`
- `skeletal_mesh_binding_mutation_allowed`
- `equipment_binding_mutation_allowed`

29E.4 cannot change simulation truth or gameplay outcomes.

## Local acceptance

29E.4 is accepted only when:

```powershell
.\scripts\run-underreach-character-material-appearance-validation.ps1
```

ends with:

```text
[29E.4] PASS
```

The runner verifies focused 29E regressions, exact accepted 29E.3 provenance, deterministic proof reproduction, 24 Descenders / 96 character material directives, the real Unreal material hierarchy, parameter round-trip, Human/Dwarf skeletal meshes, multiple body variants, all four surface categories, non-authoritative component overrides, proof-file immutability, and the full repository regression suite.

## Non-goals

29E.4 does not yet prove weapon-hand alignment, armor/helmet behavior during attack/reaction/death animation, or no-floating/no-sliding combat equipment. Those belong to **29E.5 — Equipment/Character Combat Integration**.
