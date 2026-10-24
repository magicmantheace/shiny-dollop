# Universal Game Save Manager

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 1 of 17 in the approved intake queue.
**Category:** Windows desktop
**Repository workspace:** `projects/game-save-manager/`

## Purpose

Safely discover, back up, version, verify, and restore PC game saves across manual locations and common storefront layouts.

## First usable release (MVP)

Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation.

## Full intended capabilities

- Manual game/save-folder registration
- Steam, Epic, and Battle.net location discovery where reliable
- Versioned timestamped backups and per-file checksums
- Safe restoration with pre-restore backup
- Change detection and backup retention settings
- Scheduled backups while running
- History, searchable game list, and exportable manifest

## Proposed implementation direction

Electron + React + TypeScript + SQLite; filesystem operations through a validated main-process API. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Standalone; optional future interoperability with the existing Universal PC Game Launcher only by separate approval.

Do not assume storefront installation paths equal game save locations. Do not delete game data, bypass cloud sync, or silently overwrite saves.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
