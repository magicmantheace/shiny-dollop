# Crawl Live Spectator Desktop

**Status:** MVP FUNCTIONAL / REVIEW READY — working application implemented on branch `crawl-spectator-desktop/mvp` (see [implementation status](docs/IMPLEMENTATION_STATUS.md)).

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

## Implementation

Electron + React + TypeScript (strict) desktop client under `app/`, with a
typed, zod-validated read-only adapter for the public Feed API contract
(derived in [docs/FEED_API_CONTRACT.md](docs/FEED_API_CONTRACT.md)),
reconnect with backoff and tick-cursor resume, a bounded live Ledger
buffer, local-only follow preferences (SQLite), a replay browser, and
locally computed highlights. A deterministic demo mode with invented
fixture Descenders is built in and is always labeled DEMO in the UI —
it is never presented as live data.

### Run it

```bash
cd app
npm ci
npm run build
npx electron .        # or: npm run smoke  (headless acceptance walkthrough)
```

In the app: enter your local Feed API base URL and **Connect live**, or
**Start demo** to explore with fixture data. Development: `npm test`,
`npm run typecheck`, `npm run lint`.

## Dependencies and boundaries

Consumes `projects/crawl/` APIs only, without cross-project source coupling.

Strictly read-only: never alter canonical Crawl/Underreach data. Do not change `projects/crawl/` during this project.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
