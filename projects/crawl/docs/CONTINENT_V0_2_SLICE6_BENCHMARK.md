# Continent v0.2 Slice 6A — Long-Horizon Benchmark Harness

Slice 6A prepares LivingWorld for measured 200+ year stability runs before the first Unreal Engine integration milestone.

The goal is not to make the simulation skip logic. The benchmark runs the same authoritative `FinalWorldEngine` and still processes every simulated hour, daily system, monthly system, seasonal system, and yearly system. It simply removes the live server's intentional five-second tick sleep and avoids database persistence on every runtime tick so we can measure the simulation core itself.

## Why this slice exists

At the current live defaults, one world year contains 8,640 simulated hours. The live runtime advances one simulated hour every five real seconds at 1x, making the nominal clock 12 real hours per world year.

At high multipliers, the limiting factor stops being the configured clock and becomes how quickly the full continent simulation can actually process those 8,640 hours. Slice 6A gives us a reproducible way to measure that ceiling on the target PC.

## New benchmark module

`src/livingworld/benchmark.py` provides a deterministic long-horizon runner.

It:

- generates a full v0.2 continent from a supplied seed
- runs `FinalWorldEngine` directly in memory
- advances exact 360-day world years
- times every simulated year separately
- prints a rolling ETA during long runs
- records total and per-year wall time
- calculates simulated hours per real second
- reports an equivalent unthrottled speed multiplier relative to the current 1x clock
- projects the measured wall time for a 200-year run
- collects event counts without database-write overhead
- retains a bounded set of major historical events
- checks world invariants after every year
- writes compact historical political-map snapshots
- writes a full checkpoint world at snapshot intervals
- writes JSON telemetry and a human-readable Markdown summary

The benchmark intentionally does **not** sleep between ticks.

## What the timing means

The primary number is **core simulation throughput**.

For example, if one simulated year completes in 20 real seconds, the engine processed:

- 8,640 simulated hours
- in 20 seconds
- or 432 simulated hours/second

Because the current live 1x clock represents 0.2 simulated hours/second, that would be an equivalent core capacity of about 2,160x.

This is a ceiling for the simulation core, not a promise that the live API server can sustain exactly that multiplier. The live runtime also has:

- the configured five-second scheduler sleep
- state persistence
- API/dashboard traffic
- WebSocket/event delivery

Those can be benchmarked separately after the core stability run.

## Structural invariants checked every year

The runner treats structural corruption as a hard failure.

Checks include:

- no negative settlement population
- settlement ancestry totals equal settlement population
- no negative ancestry counts
- world population equals settlements plus active refugee camps
- active settlements have valid owning kingdoms
- owning kingdoms list their active settlements
- refugee camps reference valid settlements and kingdoms
- NPCs reference valid settlements and kingdoms
- trade routes reference valid endpoints
- armies reference valid kingdoms, locations, destinations, and supply sources
- army troop counts and supply efficiency stay valid
- wars reference valid belligerents
- war fronts, sieges, and occupations reference valid settlements
- siege progress remains within 0..1
- war exhaustion remains within 0..1
- ended wars have an end date
- territorial claims reference valid settlements and kingdoms
- settlement occupation and siege kingdom references remain valid
- no NaN/infinite values in checked simulation fields
- total world population remains above zero
- at least one active settlement remains

## Stability warnings

Some outcomes are not automatically treated as bugs because the point of the long run is to discover whether the simulation naturally tends toward them.

The report currently warns when:

- world population falls below 10% of its starting value
- world population grows above 10x its starting value
- the persistent named-NPC population reaches zero

These warnings remain visible in the annual telemetry and final report even when structural invariants still pass.

## Historical map snapshots

Every N years, the benchmark writes a compact map snapshot containing:

- world date
- total population
- settlement positions
- settlement legal owner
- current occupier
- settlement type
- frontier status
- abandonment year
- kingdom capitals
- kingdom settlement lists
- vassal/overlord relationships
- territorial claims

This creates the data foundation for a later historical-map viewer without storing full world-state copies for every year.

## Checkpointing

At each configured snapshot interval, the benchmark overwrites:

`validation/long-horizon/checkpoint_world.json`

Only the latest full checkpoint is retained so disk usage remains bounded.

The checkpoint is primarily for debugging a failed long run. Resume-from-checkpoint automation is intentionally deferred until we know whether 200-year runs are long enough to justify it.

## Git safety

Large benchmark artifacts are ignored:

- `benchmark.json`
- `checkpoint_world.json`
- historical map JSON files

The small human-readable summary remains reviewable:

`validation/long-horizon/BENCHMARK.md`

This lets a local validation agent commit only the summary when we want to review benchmark results in GitHub without committing large generated state files.

## PYTHONPATH isolation

The Slice 5 validation exposed a local environment hazard where another project's venv was injected through `PYTHONPATH`.

Both the long-horizon runner and the standard local validator now clear `PYTHONPATH` only around child-process execution and restore the caller's original value afterward.

This ensures LivingWorld uses:

`D:\living\.venv\Scripts\python.exe`

and its own installed packages.

## Commands

### First: normal branch validation

```powershell
Set-Location D:\living
git fetch origin
git switch agent/continent-v0.2-slice6-benchmark
git pull
.\scripts\run-local-validation.ps1
```

Do not run the long benchmark until this is green.

### One-year calibration

This answers the immediate question: how long does one fully simulated continent year take on this PC when the engine is allowed to run as fast as it can?

```powershell
.\scripts\run-long-horizon-benchmark.ps1 -Years 1 -SnapshotEvery 1
```

Review:

```text
validation\long-horizon\BENCHMARK.md
```

### Ten-year calibration

A ten-year run gives a much better estimate because it captures annual systems, changing population, wars, frontiers, and entity growth.

```powershell
.\scripts\run-long-horizon-benchmark.ps1 -Years 10 -SnapshotEvery 5
```

### Full v0.2 stability run

```powershell
.\scripts\run-long-horizon-benchmark.ps1 -Years 200 -SnapshotEvery 10
```

The console prints each year's elapsed time and a rolling ETA.

## Benchmark outputs

`validation/long-horizon/BENCHMARK.md`
- small reviewable summary
- annual timings
- population and entity counts
- warfare activity
- warnings
- event counts

`validation/long-horizon/benchmark.json`
- full machine-readable telemetry
- annual records
- major historical events
- summary statistics

`validation/long-horizon/checkpoint_world.json`
- latest complete world state at a checkpoint

`validation/long-horizon/maps/year_XXXX.json`
- compact historical political maps

## Slice 6A acceptance criteria

Before merging this preparation slice:

- standard local validation passes
- benchmark invariant tests pass
- existing Slice 1–5 regressions remain green
- dashboard build remains green
- `PYTHONPATH` contamination no longer breaks local validation
- long-horizon output files stay out of git except `BENCHMARK.md`
- a one-year calibration can run from a single PowerShell command
- benchmark reports real seconds/year and a 200-year projection

After merging Slice 6A, the next validation stage is empirical rather than another feature slice:

1. run one year and record real throughput
2. run ten years and check whether seconds/year is stable
3. run 200 years
4. inspect structural failures, population drift, kingdom/territory history, NPC survival, and timing degradation
5. fix any long-duration failures found
6. repeat until 200 years is clean

Once that passes, v0.2 is ready for the first Unreal integration milestone: load one LivingWorld settlement into Unreal and prove a player action changes persistent authoritative backend state.
