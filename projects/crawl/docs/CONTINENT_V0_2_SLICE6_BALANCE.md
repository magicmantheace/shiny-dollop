# Continent v0.2 Slice 6B — Long-Run Balance Pass

## Purpose

The first 200-year benchmark proved that the simulation core can run centuries quickly and without structural corruption, but it exposed three historical-behavior failures:

1. statistical population grew from 100,000 to 1,946,164 (19.46x),
2. the persistent named-NPC cast reached zero by year 193,
3. no war emerged organically during the entire 200-year history despite contested frontier claims and religious tension.

Slice 6B corrects those problems without changing the benchmark seed or hiding instability.

## Baseline

The first committed 200-year baseline remains the comparison point:

- 200 years simulated,
- 548.98 seconds wall time,
- 2.743 seconds/year average,
- zero structural invariant failures,
- 54 stability warnings,
- 100,000 initial population,
- 1,946,164 final population,
- zero living persistent NPCs by year 193,
- zero organic wars,
- 24 frontier settlements founded,
- 20 contested frontier claims,
- 85 religious-tension events.

## 1. Statistical demography

### Aggregate sampling

Monthly births and deaths no longer perform one random draw per inhabitant. They use a deterministic normal approximation to a binomial process. Runtime cost is therefore approximately constant per settlement rather than proportional to total population.

Expected benefit:

- a one-million-person continent no longer requires millions of Python RNG calls every demographic month,
- long-horizon runtime should grow mainly with entity/system complexity rather than raw statistical population.

### Carrying-capacity pressure

Birth rates now respond to settlement housing density. As population approaches or exceeds housing capacity:

- fertility falls,
- mortality rises,
- prosperity and stability receive crowding pressure.

Food scarcity, war, siege, and occupation also suppress births and/or increase mortality.

Housing expansion remains possible, but it is now:

- quarterly rather than effectively continuous,
- wealth-funded,
- deliberately slower than unconstrained demographic expansion.

This allows prosperous settlements to grow without allowing housing construction to automatically erase every carrying-capacity limit.

### Ancestry accounting

Births and deaths are allocated proportionally across the settlement's ancestry distribution rather than assigning all net growth to the currently dominant ancestry.

## 2. Persistent named-NPC generations

### Dynamic cast target

The complete engine targets roughly 400–700 living persistent NPCs depending on statistical population:

- approximately 500 at a 100,000-person continent,
- capped at 700 as the statistical population grows.

Persistent NPCs are representative named people inside the statistical population and are not added to `WorldState.total_population`.

### Widow and widower recovery

If an NPC's recorded spouse is dead or missing, the surviving NPC's `spouse_id` is cleared before annual matchmaking. Historical relationship records remain, but the survivor can marry again.

This prevents a dead spouse ID from permanently shrinking the reproductive pool.

### Family births

Named-family birth pressure rises as the living cast falls below its target, while remaining low when the cast is healthy. Normal family births remain the preferred way named generations continue.

### Named-cast safety valve

If the living cast falls below 70% of its target, up to 30 statistical inhabitants per year can become persistent named adults (`NPC_ENTERED_RECORD`).

This represents people who were always part of the statistical population becoming historically relevant as merchants, craftspeople, soldiers, priests, rulers, or other notable actors.

It does not create additional statistical population.

## 3. Organic political escalation

Frontier and religious systems now feed the war system directly.

### Contested frontier claims

For every active contested territorial claim:

- both kingdoms gain a unique grievance tied to the claim,
- bilateral opinion deteriorates gradually,
- the claim contributes to a pairwise tension score.

### Pairwise tension

Tension combines:

- bilateral hostility,
- number of contested frontier claims,
- cultural militarism,
- kingdom expansion goals,
- military readiness,
- religious disputes.

A high-tension pair can enter a `DIPLOMATIC_CRISIS`. Severe tension deterministically declares war; moderate tension has a deterministic seeded probability of escalation over time.

### Safeguards

Political escalation will not automatically declare a new war when:

- the pair is already at war,
- either kingdom is already fighting another active war,
- an active truce still applies,
- one kingdom is the other's overlord,
- both kingdoms share the same overlord.

This keeps organic conflict meaningful without creating unrestricted multi-front war spam.

## Regression tests

`tests/test_long_term_balance.py` verifies:

1. a crowded settlement does not continue runaway annual growth,
2. a dead spouse no longer permanently blocks remarriage,
3. the persistent cast replenishes before extinction without changing statistical population,
4. severe contested-border tension can organically declare a war.

## Next benchmark

Run normal validation first:

```powershell
Set-Location D:\living
.\scripts\run-local-validation.ps1
```

Then rerun the exact baseline seed:

```powershell
.\scripts\run-long-horizon-benchmark.ps1 -Years 200 -SnapshotEvery 10
```

## v0.2 long-run acceptance targets

The next 200-year run should satisfy all of the following:

### Structural

- zero invariant failures,
- no negative population,
- ancestry totals match settlement populations,
- no broken settlement/kingdom/NPC/army/route references,
- no invalid occupation or siege state.

### Demography

- final population should remain below 5x the 100,000 baseline unless history contains a compelling reason for greater growth,
- no persistent exponential-growth warning trend,
- runtime should not degrade primarily because statistical population increased.

### Persistent NPCs

- living persistent NPC count never reaches zero,
- final living cast should normally remain between 300 and 800,
- multiple generations should be represented by births, coming-of-age events, marriages, deaths, and ruler successions.

### Politics and warfare

- at least one organic war should occur in a 200-year history when contested claims or severe diplomatic hostility exist,
- wars should end rather than remain permanently active,
- territorial changes and occupations must continue to satisfy structural invariants,
- war frequency should remain low enough that the continent is not in perpetual universal war.

### Performance

The baseline was 2.743 seconds/year average and 4.411 seconds/year P95. The balance pass may add some political work, but long-run performance should remain practical for repeated 200-year testing.

## Interpretation

The goal is not a perfectly static or perfectly peaceful world. The goal is a historically plausible world that can grow, decline, fight, recover, form families, lose rulers, found settlements, and redraw borders for centuries without numerical runaway or historical-system collapse.
