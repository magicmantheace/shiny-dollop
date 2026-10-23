# Crawl Live Spectator Desktop

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 17 of 17 in the approved intake queue.
**Category:** Underreach spectator client
**Repository workspace:** `projects/crawl-spectator-desktop/`

## Purpose

Read-only desktop viewer for real Descender state, live events, relationships, stories and replays.

## First usable release (MVP)

Connect to a running local Underreach Feed API, display real Descenders, select one and inspect authentic state/history plus live updates.

## Full intended capabilities

- Connection setup and runtime status
- Descender search and profiles
- Current stratum/sector and status
- Relationships, parties and history
- Live Ledger event feed
- Follow/favorites local preferences
- Replay browser and highlights
- Archived Descent navigation

## Proposed implementation direction

Desktop client with typed, versioned read-only API adapter and reconnect handling; use existing Underreach Feed contracts. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Consumes `projects/crawl/` APIs only, without cross-project source coupling.

Strictly read-only: never alter canonical Crawl/Underreach data. Do not change `projects/crawl/` during this project.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
