# LivingWorld v0.2 — Slice 2

## Continent observability, migration, and refugees

Slice 2 builds on the validated procedural continent foundation from Slice 1. It makes the continent visible through the API/dashboard and introduces the first population-movement system.

## Simulation changes

Migration runs once per simulated month after the existing demographic, political, and war systems.

A settlement develops outward migration pressure from:

- food insecurity
- low stability
- overcrowding
- participation in an active war

Potential destinations are scored from:

- food security
- stability
- health
- available housing
- local prosperity
- travel distance
- whether the destination is itself involved in war

War-driven movement is recorded as `REFUGEE_MOVEMENT`; other movement is recorded as `MIGRATION`.

Every flow records:

- origin and destination settlement
- origin and destination region
- origin and destination kingdom
- number of statistical inhabitants moved
- named persistent NPCs that relocated
- reason for movement
- whether the flow is refugee movement

Statistical population is conserved during migration. Births and deaths remain the only sources of net demographic change.

A small number of eligible persistent NPCs can move with each statistical flow. Rulers and active army commanders are excluded. Where practical, spouses and children are moved together with selected named NPCs.

## API changes

New endpoints:

- `GET /api/continent`
- `GET /api/regions`
- `GET /api/migrations`
- `POST /api/admin/world/generate-continent`

Updated endpoints:

- `GET /api/map` now returns continent bounds, continent metadata, region overlays, region IDs on settlements, and landmarks from all regions.
- `GET /api/regions/{region_id}` now resolves any generated region.
- `GET /api/settlements` accepts `region_id` as a filter.

The FastAPI application version is now `0.2.0`.

## Dashboard changes

The dashboard now:

- uses the world/continent bounds instead of a hard-coded `100 x 100` map
- draws region boundaries and labels
- displays all six continent regions
- shows region population and settlement counts
- polls migration/refugee events
- displays recent movement in a dedicated panel
- exposes monthly migrant and refugee metrics

## Local validation

No GitHub Actions are required or configured for validation.

From the feature branch:

```powershell
Set-Location D:\living
git pull
.\scripts\run-local-validation.ps1
```

The validation script runs:

1. Slice 2 continent/migration/API tests
2. the full backend regression suite
3. a deterministic continent + migration smoke test
4. the dashboard production build

It then writes and pushes `validation/LOCAL_VALIDATION.md` to the current branch for inspection.

## Slice 2 acceptance criteria

- continent map uses 200 x 300 world bounds
- all six regions are API-visible
- settlements expose region identity
- crisis conditions move population between settlements
- migration preserves total statistical population
- ancestry population totals remain consistent with settlement population
- active wars can generate refugee movement
- named NPCs can relocate with flows while rulers/commanders remain anchored
- migration/refugee history is queryable through the API
- dashboard displays regional and migration state
- all prior tests continue to pass
- dashboard production build succeeds

## Follow-up work

Later v0.2 slices should expand this foundation with:

- road/river-aware migration cost
- border policy and closed-border effects
- refugee acceptance/rejection diplomacy
- camps and temporary settlements
- disease and resource pressure caused by sudden arrivals
- cultural/religious mixing over generations
- colonization and settlement founding
- territorial control/frontiers
- sieges, supply lines, and occupation
- historical map snapshots by year
