# LivingWorld v0.2 — Slice 3

## Borders, refugee policy, camps, and arrival pressure

Slice 3 turns migration from a purely geographic choice into a political and humanitarian system. Kingdom policy can now alter whether population crosses borders, whether displaced people are admitted, and whether refugee camps form outside host settlements.

## Kingdom policy

Every kingdom now persists two backward-compatible policy fields:

- `border_policy`: `open`, `controlled`, or `closed`
- `refugee_policy`: `welcome`, `limited`, or `reject`

Old saves that do not contain these fields load with safe defaults (`open` borders and `limited` refugee acceptance).

Authenticated external commands can change policy at runtime:

- `kingdom.set_border_policy`
- `kingdom.set_refugee_policy`

The offline natural-language parser also understands:

```text
set kingdom_0001 border closed
set kingdom_0001 refugees welcome
```

Policy changes become immutable historical events.

## Border-aware movement

Ordinary migration behaves as follows:

- open borders permit normal cross-border movement
- controlled borders reduce cross-border capacity
- closed borders block ordinary cross-border migration

Refugee movement uses both border and refugee policy. A welcoming open kingdom can admit the full flow when housing allows. Limited or closed/rejecting policies can leave part or all of the flow outside the destination settlement.

Existing active trade routes act as established travel corridors and reduce migration travel friction between directly connected settlements.

## Refugee camps

Population denied entry is not deleted. It is moved from the origin settlement into a persistent `RefugeeCamp` entity associated with a host settlement and kingdom.

A camp stores:

- host settlement and host kingdom
- origin kingdom
- statistical population
- ancestry distribution
- creation and latest-arrival dates
- food security
- health
- months active
- lifecycle state (`active`, `resettling`, `closed`)

Camp population counts toward `WorldState.total_population`, preserving the Slice 2 population-conservation invariant.

Repeated rejected flows from the same origin toward the same host expand the existing active camp rather than creating duplicate camps every month.

## Host pressure and disease

Once per simulated month, active camps:

- draw grain/aid from the host settlement
- lose food security if aid coverage is insufficient
- suffer health effects from scarcity and crowding
- reduce host food security
- can slightly reduce host health

Severely unhealthy camps can generate `CAMP_DISEASE_OUTBREAK` events, which also strain the host settlement.

This makes refugee acceptance materially affect the economy and population health instead of existing only as narrative text.

## Resettlement

If the host later opens its border and allows refugees, an active camp can gradually resettle into its host settlement when housing is available.

Resettlement:

- transfers statistical population and ancestry counts into the settlement
- keeps world population conserved
- applies arrival pressure to the settlement
- emits `REFUGEE_RESETTLED`
- closes the camp once no residents remain

## Diplomacy

Cross-border refugee handling affects kingdom relations.

Rejecting refugees can:

- lower the origin kingdom's opinion of the host
- create a durable `Refugees denied entry` grievance
- emit `BORDER_REJECTION`

Accepting refugees can modestly improve the origin kingdom's opinion of the host and emits `REFUGEE_ACCEPTED`.

## API changes

FastAPI version: `0.2.1`.

New endpoint:

- `GET /api/refugee-camps`

It can filter by:

- `host_kingdom_id`
- `origin_kingdom_id`
- active/all camps

Updated responses:

- `/api/map` includes kingdom border/refugee policies and active camps
- `/api/continent` includes camp count and camp population
- `/api/kingdoms/{id}` includes hosted camp count/population
- `/api/settlements/{id}` includes attached camp IDs/population

## Dashboard changes

The dashboard now shows:

- admitted refugees for the latest month
- camped/rejected refugees for the latest month
- active camp count
- camp population
- kingdom border policy
- kingdom refugee policy
- camp markers on the continent map
- camp population, food security, health, and lifecycle state
- policy command examples in the admin console

## Local validation

No GitHub Actions are configured or required.

Run from the Slice 3 branch:

```powershell
Set-Location D:\living
git pull
.\scripts\run-local-validation.ps1
```

The validator runs:

1. Slice 3 continent/border/refugee/API tests
2. the full backend regression suite
3. a deterministic closed-border rejection + camp-resettlement smoke test
4. the dashboard production build

It writes, commits, and pushes only `validation/LOCAL_VALIDATION.md`.

## Slice 3 acceptance criteria

- existing saves load without migration
- closed borders block ordinary cross-border migration
- refugee policy changes refugee acceptance
- rejected refugees form persistent camps rather than disappearing
- settlement + camp population remains conserved during movement/resettlement
- camp ancestry totals equal camp population
- camps consume host resources
- unhealthy camps can create disease pressure
- opening policy permits gradual resettlement
- refugee rejection creates diplomatic consequences
- policy can be changed through authenticated commands and offline natural commands
- camps and policy are API-visible
- camps and policy are dashboard-visible
- all prior backend tests continue to pass
- dashboard production build succeeds

## Follow-up: Slice 4

The next coherent v0.2 slice should move from displacement to **expansion and territory**:

- colonization pressure
- settlement founding
- frontier claims
- territorial control
- defensible borders and forts
- abandoned/ruined settlements
- integration of migration into new settlement formation

After that, warfare can be upgraded around the territorial model with sieges, supply lines, occupation, and postwar borders.
