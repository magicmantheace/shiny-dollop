# LivingWorld v0.2 — Slice 4

## Colonization, frontier settlements, territorial claims, forts, and ruins

Slice 4 moves the continent from passive migration into persistent expansion. Kingdoms can now develop colonization pressure, found new settlements by transferring existing population, project explicit frontier claims, fortify contested borders, and abandon failed settlements into durable ruins.

## Design rules

The Slice 4 systems preserve the existing authoritative simulation invariants:

- population is transferred rather than created by colonization
- ancestry totals move with statistical population
- named NPCs can relocate with founding groups
- refugee camps can contribute settlers to frontier foundations
- frontier claims are deterministic and persisted in world state
- abandoned settlements relocate survivors before becoming ruins
- existing v0.1/v0.2 saves load with safe defaults because all new fields are optional/defaulted
- no LLM is required for any territorial decision

## Colonization pressure

Each kingdom receives a deterministic colonization-pressure score derived from:

- cultural expansionism
- kingdom expansion priority
- kingdom stability
- settlement prosperity
- treasury capacity
- overcrowding
- active-war penalty

The score is bounded from 0 to 1. Automatic expansion only attempts to found a frontier when pressure is sufficiently high.

Automatic colonization is intentionally throttled. A kingdom can maintain at most six active frontier settlements through the autonomous cycle, preventing 200-year simulations from producing unbounded settlement growth.

## Frontier site selection

Candidate sites are sampled deterministically inside:

- regions where the kingdom already has population
- immediately reachable neighboring regions near existing settlements

Sites are rejected when they are too close to an existing settlement or too far from a viable source settlement.

Candidate scoring considers:

- local settlement sparsity
- practical distance back to an origin settlement
- defensibility
- strategic border value
- proximity to rival settlements

## Founding a settlement

`found_frontier_settlement()` creates a new settlement by transferring people from an existing source settlement.

A portion of settlers can also come from an active refugee camp hosted by the kingdom. This ties Slice 3 displacement directly into Slice 4 settlement formation.

New frontier settlements can be:

- `hamlet`
- `trade_post`
- `fort`

The automatic type selection prefers forts at contested/highly defensible sites, trade posts at longer-distance corridors, and hamlets for ordinary expansion.

Founding creates:

- a persistent settlement
- resource stocks
- initial buildings and defenses
- a trade/supply route back to the origin settlement
- a persistent territorial claim
- named NPC relocation when eligible
- a `SETTLEMENT_FOUNDED` history event

## Territorial claims

Each frontier foundation creates a record in `WorldState.territory_claims`.

A claim stores:

- claim ID
- claimant kingdom
- region
- linked settlement
- position
- control radius
- control strength
- defensibility
- lifecycle status
- neighboring kingdoms contesting the claim
- creation date

Claim status can be:

- `active`
- `contested`
- `abandoned`

Existing settlements continue to imply core territorial control. Frontier claims represent explicit projected control beyond those cores.

`territory_summary()` computes a comparable control estimate for each kingdom from core settlement influence plus active frontier-claim influence. This is an influence estimate, not a final terrain polygon system.

## Contested borders and forts

Every month, frontier claims are reevaluated against nearby settlements controlled by other kingdoms.

When foreign settlement influence approaches a frontier claim:

- the claim becomes contested
- the competing kingdom IDs are persisted
- `FRONTIER_CLAIM_CONTESTED` can be emitted
- the owning kingdom can invest treasury into defenses
- sufficiently fortified frontier settlements become `fort` settlements
- `FRONTIER_FORTIFIED` is emitted on the transition

This creates the territorial foundation required for the later siege/supply/occupation system.

## Frontier collapse and ruins

Frontier settlements accumulate stress when they suffer severe conditions such as:

- very low population
- food collapse
- low stability
- poor health

Three consecutive months of severe frontier stress trigger abandonment when another settlement in the same kingdom can receive the survivors.

Abandonment:

- moves all statistical population to the nearest viable same-kingdom settlement
- transfers ancestry counts
- relocates living named NPCs
- deactivates trade routes connected to the failed settlement
- removes the failed settlement from the kingdom's active settlement list
- keeps the location in the world as a `ruin`
- marks the territorial claim `abandoned`
- records the abandoned year
- emits `SETTLEMENT_ABANDONED`

The ruin remains available for future history, archaeology, reclamation, or player-world content rather than disappearing from the map.

## Persistence and API visibility

Backward-compatible fields added to `Settlement`:

- `frontier`
- `origin_settlement_id`
- `frontier_stress_months`
- `abandoned_year`

Backward-compatible field added to `WorldState`:

- `territory_claims`

The existing APIs already expose the Slice 4 state without requiring a new API contract:

- `GET /api/world/state` exposes all territorial claims
- `GET /api/settlements` exposes frontier and abandonment metadata
- `GET /api/kingdoms` exposes each kingdom's claim IDs

A dedicated territory/frontline API is intentionally deferred until the siege/occupation system stabilizes the final control semantics.

## Simulation cadence

Frontier maintenance runs monthly after migration and refugee-camp updates.

Monthly work includes:

- claim contest reevaluation
- defensive investment
- fortification
- frontier stress tracking
- abandonment when necessary

Automatic colonization is attempted at the beginning of a simulated year.

After the base engine refreshes world metrics, Slice 4 restores:

- active frontier claims
- frontier settlements
- frontier forts
- frontier ruins
- contested frontier claims

## Local validation

No GitHub Actions are configured or required.

From the Slice 4 branch:

```powershell
Set-Location D:\living
git pull
.\scripts\run-local-validation.ps1
```

The validator runs:

1. Slice 4 continent/migration/border/frontier/API tests
2. the complete backend regression suite
3. a deterministic frontier founding + territory + abandonment smoke test
4. the dashboard production build regression

It writes, commits, and pushes only `validation/LOCAL_VALIDATION.md`.

## Slice 4 acceptance criteria

- old saves load without a schema migration
- founding a frontier preserves total population
- ancestry totals equal settlement population after founding
- named NPCs can relocate with settlers
- frontier settlements create persistent claims
- new settlements receive a connection to an origin settlement
- frontier claims can become contested
- contested frontier settlements can become forts
- refugee-camp population can participate in settlement formation
- sustained frontier failure creates a ruin
- abandonment preserves total population
- abandoned claims stop projecting territorial strength
- territory summaries are deterministic and comparable
- frontier state is visible through existing API state responses
- all prior backend tests continue to pass
- dashboard production build still succeeds

## Follow-up: Slice 5

The next coherent v0.2 slice should upgrade warfare to use the territorial model:

- front lines
- army supply lines
- siege state
- settlement occupation
- fort defensive effects
- claim capture and contested control
- war exhaustion
- peace terms that alter borders
- vassalization and postwar territorial settlement

After that, the v0.2 continent should be ready for a dedicated long-duration stability pass and historical map snapshots before the first Unreal integration milestone.
