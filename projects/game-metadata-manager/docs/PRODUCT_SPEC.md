# Product specification — Game Library Metadata Enricher

**Intake status:** Approved project concept; implementation not started.
**Priority:** 7/17
**Audience/target platform:** Windows gaming desktop

## Problem and outcome

Organize game artwork, descriptions, collections, tags, and missing-install metadata without altering games.

## MVP user workflow and acceptance contract

Import a fixture library, edit artwork/title/tags, detect a missing path, and export a reversible metadata bundle.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Game library importer and schema versioning** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Editable descriptions and original titles** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Artwork picker and cache provenance** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Custom tags, groups and filters** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Missing executable/install detection** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Conflict-safe metadata merges** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **JSON/CSV export and undoable edits** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Standalone Electron or equivalent Windows app with versioned import/export; keep existing game launcher untouched.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Optional future reviewed interoperability with `projects/universal-game-launcher/`.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

No modification of the existing Universal Game Launcher as part of this project; do not scrape copyrighted art without appropriate rights.

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
