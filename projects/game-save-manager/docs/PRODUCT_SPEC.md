# Product specification — Universal Game Save Manager

**Intake status:** Approved project concept; implementation not started.
**Priority:** 1/17
**Audience/target platform:** Windows desktop

## Problem and outcome

Safely discover, back up, version, verify, and restore PC game saves across manual locations and common storefront layouts.

## MVP user workflow and acceptance contract

Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Manual game/save-folder registration** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Steam, Epic, and Battle.net location discovery where reliable** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Versioned timestamped backups and per-file checksums** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Safe restoration with pre-restore backup** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Change detection and backup retention settings** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Scheduled backups while running** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **History, searchable game list, and exportable manifest** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Electron + React + TypeScript + SQLite; filesystem operations through a validated main-process API.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Standalone; optional future interoperability with the existing Universal PC Game Launcher only by separate approval.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Do not assume storefront installation paths equal game save locations. Do not delete game data, bypass cloud sync, or silently overwrite saves.

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
