# Underreach Character DNA

Character DNA is persistent Descender identity, not an Unreal actor or a baked
mesh. The v1 protocol is `underreach.character-dna.v1`, schema `1`,
implementation `29a1.1`.

## Invariants

- The same DNA, schema, Character Factory, and asset registry produce the same
  canonical renderer manifest and digest.
- Loading never rerolls an appearance.
- Unreal object paths, actor IDs, components, LOD state, and current animation
  state are excluded.
- Simulation-persistent appearance overlays (hair, scars, injuries, clothing,
  equipment, dirt, blood, missing features, transformations) are separate from
  the mostly stable biological identity.
- Render instances are disposable and can retain terminal state without
  changing DNA.

## Supported traits

Species, style, age, height, mass, body fat, muscularity, shoulders, hips,
torso/leg/arm length, head scale, jaw, chin, cheeks, nose, brow, eyes, facial
fullness, face seed, skin, eyes, hair, facial hair, clothing, equipment,
persistent marks, injuries, tattoos, missing features, dirt, blood, and magical
transformation hooks.

`CharacterDNAGenerator` uses stable SHA-256-derived samples and constrained,
correlated Human/Dwarf profiles. `CharacterDNAStore` writes atomically,
revalidates the temporary file, and supports explicit migration hooks.

The reference population command generates 100 Humans and 100 Dwarves and
writes deterministic examples, reconstruction data, and a population digest to
`unreal/CrawlPresentation/Generated/29a1`.
