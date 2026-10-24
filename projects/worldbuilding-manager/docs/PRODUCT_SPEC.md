# Product specification — Novel and Worldbuilding Manager

**Intake status:** Approved project concept; implementation not started.
**Priority:** 14/17
**Audience/target platform:** Creative writing desktop

## Problem and outcome

Organize stories, characters, lore, timelines, locations and relationship continuity offline.

## MVP user workflow and acceptance contract

Create characters, locations and a timeline event, link them, search notes, and export a complete project backup.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Character and location sheets** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Factions and relationship map** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Timeline events and dates** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Notes, chapters, outlines and tags** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Cross-references and continuity warnings** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Snapshots and version history** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Markdown/JSON exports** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Local desktop editor, SQLite, markdown-friendly notes, entity links and export bundles.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Optional export of settings and characters to AI Dungeon Master.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Author retains control and copyright; no external sync by default.

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
