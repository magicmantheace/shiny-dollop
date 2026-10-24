# Product specification — AI Dungeon Master

**Intake status:** Approved project concept; implementation not started.
**Priority:** 16/17
**Audience/target platform:** Tabletop RPG desktop

## Problem and outcome

Support offline-capable tabletop campaigns with auditable rules, dice, memory, NPCs and optional local AI narration.

## MVP user workflow and acceptance contract

Create a campaign and characters, roll dice, run initiative/combat with logged state, save, and resume.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Campaign and session records** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Character sheets and stats** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Transparent dice engine** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Initiative and encounter state** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **NPC/location memory** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Inventory and session notes** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Optional local AI speech/narration** — implement with persisted, validated state and meaningful user feedback where relevant.
8. **Versioned ruleset packs and import** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Deterministic campaign-state engine + local UI; optional local-model narration adapter.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Can import approved character/world exports from Worldbuilding Manager and dungeon manifests from Procedural Dungeon Designer.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

No unlicensed proprietary rulebooks; AI flavor is never the authoritative rules engine.

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
