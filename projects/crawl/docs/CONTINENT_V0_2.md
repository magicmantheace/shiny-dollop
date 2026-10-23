# LivingWorld v0.2 — Procedural Continent Slice 1

This slice moves LivingWorld from one strategic region toward a continent-scale authoritative simulation without breaking v0.1 saves or the existing simulation engine.

## Implemented target

`generate_continent_world()` creates one deterministic continent with:

- 1 continent envelope
- 6 strategic regions
- 6 autonomous kingdoms
- 30 towns
- 120 villages
- 100,000 statistical inhabitants
- 500 persistent NPCs
- 6 cultures and 6 religions
- 6 standing armies
- region-local and cross-region trade routes
- continent-wide diplomatic relationships
- globally unique entity IDs and readable entity names
- persistence through the existing SQLAlchemy world-state storage
- compatibility with the existing `FinalWorldEngine`

The generator uses the v0.1 two-kingdom generator as a deterministic building block, then remaps every ID and reference into a continent-wide namespace. This deliberately reuses systems that are already covered by v0.1 tests instead of duplicating economy, NPC, army, culture, religion, and settlement-generation logic.

## Geometry

The first continent representation is strategic rather than final Unreal terrain. It uses a 200 x 300 logical coordinate envelope divided into six 100 x 100 regions. The regions are arranged as two columns across three climate bands:

1. Frostmere Reach — cool temperate
2. The Verdant Crown — cool temperate
3. Aster Lowlands — temperate
4. Ironspine March — temperate
5. Sunward Basin — warm temperate
6. Ember Coast — warm temperate

Each region starts under one kingdom. This is an initial political state, not a permanent rule; the existing war, conquest, rebellion, and kingdom-destruction systems may change ownership over time.

## Compatibility

`WorldState` now contains optional `continent` metadata and a `regions` dictionary. Existing v0.1 worlds remain valid because both are backward-compatible additions. When an older single-region state is loaded, the world-state validator automatically exposes its existing `region` through `regions`.

The legacy `region` field remains the aggregate strategic envelope because existing API/dashboard and simulation code currently reads it. For continent worlds it represents the whole continent; `regions` carries the six detailed strategic subdivisions.

## New runtime capability

`LivingWorldRuntime.regenerate_continent()` can replace the current world with the v0.2 continent target and persist it using the same authoritative engine and database layer.

API/dashboard exposure for choosing continent generation is intentionally kept as the next integration slice after this generator passes local validation.

## Validation added

`tests/test_continent_generation.py` checks:

- exact v0.2 target counts
- deterministic same-seed generation
- unique kingdom and settlement names
- kingdom, settlement, NPC, army, route, culture, religion, region and relationship references
- SQLite round-trip persistence
- one month of `FinalWorldEngine` simulation after loading from persistence

No GitHub Actions workflow is added. Validation remains local-only.

## Next slice after validation

1. Expose continent generation and region queries through the FastAPI admin/read API.
2. Update the operations dashboard to display six regions and continent metadata.
3. Add migration/refugee flows between regions.
4. Add settlement founding from population pressure.
5. Add region-aware strategic AI and border pressure.
6. Run 10-, 100-, and 200-year continent resilience tests and tune systemic collapse/recovery behavior.
