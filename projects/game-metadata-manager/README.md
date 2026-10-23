# Game Library Metadata Enricher

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 7 of 17 in the approved intake queue.
**Category:** Windows gaming desktop
**Repository workspace:** `projects/game-metadata-manager/`

## Purpose

Organize game artwork, descriptions, collections, tags, and missing-install metadata without altering games.

## First usable release (MVP)

Import a fixture library, edit artwork/title/tags, detect a missing path, and export a reversible metadata bundle.

## Full intended capabilities

- Game library importer and schema versioning
- Editable descriptions and original titles
- Artwork picker and cache provenance
- Custom tags, groups and filters
- Missing executable/install detection
- Conflict-safe metadata merges
- JSON/CSV export and undoable edits

## Proposed implementation direction

Standalone Electron or equivalent Windows app with versioned import/export; keep existing game launcher untouched. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Optional future reviewed interoperability with `projects/universal-game-launcher/`.

No modification of the existing Universal Game Launcher as part of this project; do not scrape copyrighted art without appropriate rights.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
