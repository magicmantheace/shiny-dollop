# Product specification — Crawl Live Spectator Desktop

**Intake status:** Approved project concept; implementation not started.
**Priority:** 17/17
**Audience/target platform:** Underreach spectator client

## Problem and outcome

Read-only desktop viewer for real Descender state, live events, relationships, stories and replays.

## MVP user workflow and acceptance contract

Connect to a running local Underreach Feed API, display real Descenders, select one and inspect authentic state/history plus live updates.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Connection setup and runtime status** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Descender search and profiles** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Current stratum/sector and status** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Relationships, parties and history** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Live Ledger event feed** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Follow/favorites local preferences** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Replay browser and highlights** — implement with persisted, validated state and meaningful user feedback where relevant.
8. **Archived Descent navigation** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Desktop client with typed, versioned read-only API adapter and reconnect handling; use existing Underreach Feed contracts.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Consumes `projects/crawl/` APIs only, without cross-project source coupling.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Strictly read-only: never alter canonical Crawl/Underreach data. Do not change `projects/crawl/` during this project.

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
