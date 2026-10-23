# Product specification — Volumetric Concrete Mix Calculator

**Intake status:** Approved project concept; implementation not started.
**Priority:** 3/17
**Audience/target platform:** Engineering support / Windows desktop

## Problem and outcome

Calculate calibrated volumetric-truck material needs, stock use, and estimated production yield without claiming unverified strength results.

## MVP user workflow and acceptance contract

Enter a calibrated mix and desired cubic metres and obtain reproducible cement, sand, stone, water and estimated remaining-stock quantities.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Versioned mix/calibration profiles** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Cement, sand, stone, water, and admixture quantities** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Adjustable target volume and waste allowance** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Onboard inventory and silo balance estimate** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Payload and capacity warning inputs** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Measured-versus-theoretical yield comparison** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Unit-aware CSV and JSON exports** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Offline calculation engine with typed units and a simple desktop UI; portable JSON/CSV calibration exchange.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Export format usable by Concrete Operations Manager; applications must compile and run independently.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Do not assert structural concrete strength, code compliance, legal truck payload, or tested mix adequacy from estimates. Mark assumptions and measurement sources.

- Prefer offline operation and no paid API dependency.
- Optimize for a Windows 11 desktop (i5-10400F, RTX 3060 12 GB, 32 GB RAM), where relevant.
- Avoid destructive defaults, unapproved network calls, or hidden data collection.
- Make errors actionable; provide accessible keyboard navigation and recovery paths.
- Use original/licensed assets and scrub private example data.

## Completion criteria

1. Runnable build and reproducible install or launch instructions.
2. End-to-end MVP workflow exercised with recorded evidence.
3. Focused automated tests and relevant platform manual tests executed.
4. Clear distinction between implemented, verified, planned and blocked features.
5. Scoped pull request left unmerged for review.
