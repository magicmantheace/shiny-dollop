# Stylized 3D art direction v1

## Visual identity

Warm, readable, expressive 3D animated-series look. Distinctive silhouettes, broad facial readability, modest texture complexity, appealing non-realistic materials. Avoid dependence on proprietary character libraries or trademarked visual identities.

- Silhouette: readable at 720p; slightly exaggerated head/hands/eyes; age/size differences via bounded proportions.
- Surface: coherent roughness/metalness palette; simple material slots; reusable palette swatches.
- Face: 8 core emotions plus intensity; eyebrows/eyes/mouth read under low lighting.
- Lighting: one key, fill, ambient, limited shadow cascades; avoid expensive transparency and hair strands.
- Hair: geometry clumps, not strand simulation.
- Wardrobe: fitting layers with collision-safe defaults; cloth simulation is optional.
- Camera: wide, two-shot, close-left, close-right; no violent camera jumps without transitions.
- Characters: avoid mixing incompatible visual languages in the same scene unless tagged intentionally.

## Initial modular sets (planned)

Bodies: adult slim/average/broad and small character; heads: 3; eyes: 3; hair: 6; outfits: 5 sets; skin/hair/clothing palettes. One hero skeleton, shared shader contract, variants through shape keys and accessories.

## Style validation

Turntable render from 8 angles, shoulder/hip/hand joints in 5 poses, prop grips, facial closeups, silhouette at 720p and a low-light preview. Review clipping, texture resolution, alpha overdraw and visible rig errors before promoting.

**Current art assets:** none bundled. Godot demo creates colored capsule stand-ins.
