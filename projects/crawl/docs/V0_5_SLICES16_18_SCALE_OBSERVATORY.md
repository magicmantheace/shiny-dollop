# Crawl v0.5 — Slices 16–18

This batch builds directly on the locally validated Slices 1–15 Headless Crawl MVP.

## Slice 16 — Simulation Detail Tiers

`livingworld.detail_tiers` introduces explicit deterministic tiers:

- **Tier A / Focused** — watched or explicitly selected crawlers; update cadence 1 tick.
- **Tier B / Active** — party-relevant or immediately at-risk crawlers; cadence 2 ticks.
- **Tier C / Remote** — authoritative but currently remote crawlers; cadence 4 ticks.
- **Tier D / Background** — inactive, waiting, or deterministically sampled background crawlers; cadence 8 ticks.

Tier state is stored under `crawl.modifiers._detail_tiers`, so no database migration is required. Tier transitions are scheduling metadata only. `set_tier` snapshots the complete `CrawlerParticipation` before and after every transition and raises if authoritative crawler state changes.

The deterministic scheduler exposes `due_crawlers()` and `scheduler_load()`. Batch 4 deliberately keeps the already validated Batch 3 gameplay loop as the compatibility execution path; the scheduler is the boundary later scaling work can consume without changing authoritative outcomes prematurely.

## Slice 17 — Multi-Seed Validation and Performance

`livingworld.crawl_scale_validation` runs a seed matrix and records:

- completion / structural validity,
- deterministic replay equivalence,
- survivors and eliminations,
- floors reached,
- party count,
- resolved/total encounters,
- owned-item concentration,
- progression range,
- Director intervention volume,
- notable semantic event volume,
- event-history size,
- serialized state bytes,
- wall-clock run time,
- detail-tier distribution,
- estimated scheduled-update ratio.

The default formal matrix is the roadmap's first target:

```text
20 seeds × 100 crawlers × 3 floors
```

Every seed is replayed by default. A run fails the matrix gate if it does not terminate, cannot re-validate its Pydantic model, or produces a different deterministic fingerprint/step count on replay.

The later 20 × 1,000 × 5 target is intentionally a stress target, not the first merge gate.

## Slice 18 — Crawl Observatory

`livingworld.crawl_observatory` builds a developer-first diagnostic snapshot containing:

- crawl and floor status,
- crawler population/status counts,
- A–D detail tiers and scheduler load,
- map/location occupancy,
- active/dormant encounters,
- active parties,
- crawler profile/state/build/inventory,
- relationships and recent memories,
- recent events,
- deaths/eliminations,
- semantic interesting-event ranking,
- Director interventions,
- performance telemetry,
- selected-crawler decision trace and causal parent IDs.

`livingworld.crawl_observatory_html` renders that snapshot as a self-contained local HTML dashboard with no external frontend dependency. `livingworld.crawl_observatory_demo` writes both JSON and HTML.

This is intentionally a debugging observatory, not the future public Spectator API. Hidden/internal state can be visible here because the acceptance criterion is developer diagnosis.

## Local validation

Formal Batch 4 validation:

```powershell
.\scripts\run-crawl-slices16-18-validation.ps1
```

This runs:

1. focused Slices 1–18 tests,
2. a Crawl Observatory report/dashboard smoke run,
3. 20-seed × 100-crawler × 3-floor deterministic matrix with replay,
4. the full inherited repository regression suite.

Quick checkpoint:

```powershell
.\scripts\run-crawl-slices16-18-validation.ps1 `
  -Seeds 3 `
  -Crawlers 25 `
  -Floors 2 `
  -MaxSteps 5000 `
  -SkipFullRegression
```

Large stress run after the formal gate:

```powershell
.\scripts\run-crawl-slices16-18-validation.ps1 `
  -Seeds 20 `
  -Crawlers 1000 `
  -Floors 5 `
  -MaxSteps 50000 `
  -SkipFullRegression
```

## Acceptance gates

Batch 4 is ready to merge only when:

- tier transitions preserve authoritative crawler state,
- tier assignment and due-update scheduling are deterministic,
- scheduler load is lower than full-frequency cognition for nontrivial populations,
- all formal matrix seeds terminate without structural invariant failure,
- deterministic replays match,
- the observatory exposes the required developer diagnostic views,
- a crawler's objective/state and recent causal history can be inspected without raw database queries,
- inherited Slices 1–15 behavior remains green.

## Deliberate deferrals

- actually replacing detailed C/D gameplay with abstract outcome models,
- 10,000+ crawler stress targets,
- public spectator filtering/security,
- live streaming/event transport,
- Unreal integration,
- automatic cameras/commentary/highlight production.

Those remain later roadmap work. The Batch 4 scheduler exists specifically so lower-detail execution can be introduced behind a tested deterministic boundary instead of rewriting the Headless MVP all at once.
