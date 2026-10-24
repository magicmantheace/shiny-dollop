# Novel and Worldbuilding Manager

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 14 of 17 in the approved intake queue.
**Category:** Creative writing desktop
**Repository workspace:** `projects/worldbuilding-manager/`

## Purpose

Organize stories, characters, lore, timelines, locations and relationship continuity offline.

## First usable release (MVP)

Create characters, locations and a timeline event, link them, search notes, and export a complete project backup.

## Full intended capabilities

- Character and location sheets
- Factions and relationship map
- Timeline events and dates
- Notes, chapters, outlines and tags
- Cross-references and continuity warnings
- Snapshots and version history
- Markdown/JSON exports

## Proposed implementation direction

Local desktop editor, SQLite, markdown-friendly notes, entity links and export bundles. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Optional export of settings and characters to AI Dungeon Master.

Author retains control and copyright; no external sync by default.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
