# Product specification — Small Business Website Generator

**Intake status:** Approved project concept; implementation not started.
**Priority:** 10/17
**Audience/target platform:** Website authoring tool

## Problem and outcome

Produce complete static websites for tradespeople, authors, restaurants, and independent businesses.

## MVP user workflow and acceptance contract

Choose a business type, fill contact/services, preview a responsive website, and export a deployable static folder.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Trade/author/restaurant starter layouts** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Theme and business-profile forms** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Home/services/contact and optional menu/pages** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **SEO metadata and sitemap** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Accessible navigation and form alternatives** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Mobile preview and responsive layout** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Validated static package export** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Standalone local editor, original responsive HTML/CSS themes, static export; no hosting required.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Optional import of versioned templates from Digital Product Template Factory.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

One-time purchase model; no recurring paid upgrades; do not include copyrighted brand imagery or unlicensed templates.

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
