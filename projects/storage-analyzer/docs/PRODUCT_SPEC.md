# Product specification — PC Storage and Duplicate Finder

**Intake status:** Approved project concept; implementation not started.
**Priority:** 4/17
**Audience/target platform:** Windows utility

## Problem and outcome

Understand drive usage and duplicate files with non-destructive analysis and transparent evidence.

## MVP user workflow and acceptance contract

Choose a directory, view ranked file/folder sizes and verified duplicate groups, cancel scans, and export a report; no deletion.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Folder and drive-space treemap/list** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Large-file filtering** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Size-first and hash-confirmed duplicate groups** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Search and file-type summaries** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Exclusion rules and protected-path warnings** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Cancellable scans with progress** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **CSV/JSON results and rescan comparison** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Windows desktop UI plus cancellable background filesystem indexer and SHA-256 duplicate verification.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Standalone.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Initial MVP is read-only. Never follow reparse points into loops; no system-directory modifications; clearly label stale results.

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
