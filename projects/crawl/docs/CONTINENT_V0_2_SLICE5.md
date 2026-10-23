# LivingWorld v0.2 — Slice 5

## Territorial warfare, supply, sieges, occupation, and peace

Slice 5 replaces the v0.1/v0.2 aggregate war roll with a deterministic territorial warfare layer built on the frontier and claim systems introduced in Slice 4.

The authoritative simulation remains non-LLM and server-side.

## Backward-compatible warfare state

Existing saves load without a schema migration. New fields all have defaults.

### Army

Each army now persists:

- `supply_efficiency`
- `supply_source_settlement_id`

### Settlement

Settlements can now persist:

- `occupied_by_kingdom_id`
- `occupation_months`
- `besieged_by_kingdom_id`
- `siege_progress`

### Kingdom

Kingdoms can now persist:

- `overlord_kingdom_id`

This is used for postwar vassalization.

### War

Wars now persist:

- front settlement IDs
- per-settlement siege progress
- occupation ownership
- attacker exhaustion
- defender exhaustion
- months active
- peace terms

The existing casualty, score, and occupied-settlement fields remain supported.

## Front lines

Each active war identifies a small deterministic set of frontier settlements.

The system prefers settlements that:

- are geographically close to enemy territory
- are frontier settlements
- are forts
- sit near disputed regional seams

If no settlements are within the normal front distance, the nearest opposing settlement pair becomes the initial front.

The number of active front settlements is intentionally bounded so a continent-scale war does not turn every settlement into a tactical simulation object.

## Army movement

Attacking armies are routed toward enemy settlements on the current front.

Defending armies are routed toward friendly settlements on the current front.

The existing strategic hourly movement system remains responsible for travel time.

## Supply lines

Supply is evaluated from the kingdom's controlled settlement and active trade-route network.

A well-supplied army benefits from:

- being stationed at a friendly settlement with food
- an active route chain back to viable supply settlements
- short supply distance

An army deep in hostile territory without a connected supply network receives low supply efficiency.

Low supply efficiency reduces:

- morale
- readiness
- siege effectiveness

Friendly settlements provide grain to replenish army supply days when the connection is strong enough.

## Front battles

Monthly front battles only occur when both sides have forces at active front settlements.

Battle power uses:

- troop count
- readiness
- morale
- supply efficiency

Losses update the existing casualty and war-score records.

This replaces the previous system where every active army contributed to one continent-wide abstract battle regardless of location.

## Sieges

An army begins a siege when it occupies an enemy settlement location.

Siege progress depends on:

- attacking troop power
- attacker readiness and morale
- attacker supply efficiency
- defending army power
- settlement population
- infrastructure defenses
- settlement stability
- settlement type

Forts receive the largest defensive bonus.

Poorly supplied attackers progress much more slowly.

Sieges reduce settlement food security and emit structured `SIEGE_PROGRESS` events.

## Occupation

When siege progress reaches 100%, the settlement becomes occupied rather than immediately changing legal ownership.

Occupation persists:

- occupier kingdom
- occupation duration
- war occupation map
- occupied settlement list

A frontier territorial claim attached to the settlement becomes `occupied` and records the occupying kingdom.

Occupation reduces local stability and food security.

If an occupier withdraws all garrison forces for long enough, occupation can collapse before the peace settlement.

## War exhaustion

Both sides accumulate exhaustion from:

- war duration
- casualties
- supply shortages
- enemy occupation of their settlements

Exhaustion ranges from 0 to 1.

War can end because of:

- military collapse
- strong territorial/military score
- one side reaching extreme exhaustion
- mutual exhaustion after a prolonged conflict

## Peace settlements

Legal borders change at peace, not at initial occupation.

A victorious kingdom can receive up to three occupied non-capital settlements.

If no settlement is currently occupied but the victory is decisive, one strategically close non-capital settlement can still be ceded.

When a settlement is ceded:

- `settlement.kingdom_id` changes
- old/new kingdom settlement lists are updated
- living NPC allegiance is updated
- attached territory claims change owner
- the old kingdom loses the claim reference
- the new kingdom receives the claim reference
- occupation state is cleared
- `BORDER_CHANGED` is emitted

Population is not created or deleted by territorial transfer.

## Vassalization

A small losing kingdom can become a vassal when defeat is decisive.

The losing kingdom receives:

`overlord_kingdom_id = <winner>`

Vassalization is favored when:

- war score is decisive, or
- loser exhaustion is extreme
- the losing kingdom has five or fewer remaining settlements

A `KINGDOM_VASSALIZED` event is emitted.

The vassal remains a kingdom entity. Slice 5 does not yet implement taxes, levies, or rebellion against an overlord.

## Peace terms

Completed wars retain structured `peace_terms` containing:

- winner
- reason
- ceded settlement IDs
- vassalized kingdom ID, if any

This makes historical border changes reconstructable later.

## API compatibility

No duplicate warfare API was added.

The existing endpoints automatically expose the new state:

- `GET /api/wars`
- `GET /api/armies`
- `GET /api/settlements`
- `GET /api/settlements/{id}`
- `GET /api/kingdoms`
- `GET /api/kingdoms/{id}`
- `GET /api/world/state`

The dashboard TypeScript models now understand supply, fronts, sieges, occupations, exhaustion, peace terms, and vassal ownership without breaking the existing dashboard build.

## Metrics

After the normal engine metrics refresh, Slice 5 restores:

- `active_fronts`
- `active_sieges`
- `occupied_settlements`
- `avg_war_exhaustion`

## Local validation

No GitHub Actions are configured or required.

Run:

```powershell
Set-Location D:\living
git fetch origin
git switch agent/continent-v0.2-slice5
git pull
.\scripts\run-local-validation.ps1
```

The validator runs:

1. Slice 5 continent/migration/border/frontier/warfare/API tests
2. the complete backend regression suite
3. a deterministic front + supply + siege + occupation + peace smoke test
4. the dashboard production build

The validator commits and pushes only `validation/LOCAL_VALIDATION.md`.

## Slice 5 acceptance criteria

- old saves load using default warfare fields
- wars produce bounded geographic fronts
- armies receive deterministic supply efficiency
- isolated armies lose morale/readiness
- forts resist sieges more strongly than weak settlements
- poorly supplied attackers siege more slowly
- completed sieges create occupation, not immediate legal annexation
- occupied frontier claims reflect occupying kingdoms
- abandoned occupations can collapse when ungarrisoned
- both sides accumulate war exhaustion
- peace can transfer occupied non-capital settlements
- attached claims follow ceded settlements
- NPC allegiance follows permanent border transfer
- decisive peace can create vassal kingdoms
- war peace terms remain in history/state
- territorial transfer preserves total population
- warfare state is visible through existing APIs
- all previous backend tests remain green
- dashboard production build remains green

## Follow-up: Slice 6

Slice 6 should be the **v0.2 stability and history pass** before Unreal integration:

- 200-year deterministic stability runs
- save/load continuity across long runs
- inactive-region simulation scaling
- historical territory snapshots
- map timeline playback data
- kingdom rise/fall/rebellion stress testing
- performance profiling on the 100,000-population continent
- final API boundary cleanup for Unreal

After Slice 6 is green, the first Unreal milestone should load one settlement from the authoritative API and prove a player action creates a durable backend state change.
