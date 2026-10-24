# Implementation status — Crawl Live Spectator Desktop

- **Overall status:** MVP FUNCTIONAL / REVIEW READY (branch `crawl-spectator-desktop/mvp`)
- **Priority:** 17/17
- **Source/code implemented:** Yes — Electron app under `app/` (Electron 45 + React 19 + TypeScript strict + Vite, `node:sqlite` preferences, zod-validated IPC and Feed payloads)
- **Build validated:** Yes — `npm run build` green (renderer + main), Linux VM
- **Automated tests executed:** Yes — 59/59 pass (50 backend + 9 renderer; Codex-review fix cycle 3, 2026-10-24), typecheck + lint clean, build green, plus smoke `SMOKE_OK` (previous cycle)
- **End-to-end MVP verified:** In DEMO/fixture terms, yes (see below). Against a real owner-run Underreach Feed API: **implemented but not verified** (no live server exists in this environment)
- **Owner review:** Pending (PR to be opened by the parent agent after independent verification)

## Contract source

The typed adapter is built against the real public Feed API contract,
derived read-only from the `crawl/roadmap-completion` lineage (PR #2 head
`c7d809c`): `feed_api.py`, `feed_state.py`, `underreach_terminology.py`.
Full derived contract: [FEED_API_CONTRACT.md](FEED_API_CONTRACT.md).
`projects/crawl/` was not modified and is not imported anywhere.

## Implemented and verified here (demo/fixture path)

- **Connection lifecycle:** persisted + validated base URL (http/https only,
  no embedded credentials), live connect, disconnect, status states
  (disconnected/connecting/connected/error) with actionable messages,
  automatic reconnect with exponential backoff (500 ms → 8 s cap), and
  cursor resume after reconnect with no duplicate or missed events
  (integration-tested by killing and restarting the fixture server).
- **Demo/fixture mode:** deterministic in-process fixture feed (8 invented
  Descenders, 2 parties, 17 scripted history events + a scripted live
  edge) and a GET-only fixture HTTP server speaking the real contract.
  The UI labels demo mode with a persistent amber banner; live mode shows
  a green LIVE banner naming the base URL. The two are never ambiguous.
- **Descenders:** directory list (status/stratum filters available in the
  adapter), API search, profile view (stratum/sector, status, health,
  level, objective, party, abilities, relationships) and per-Descender
  Ledger history.
- **Live Ledger feed:** polled via `ledger/events` with the contract's
  tick cursor (resume from cursor−1 + ID dedupe), deterministic
  (tick, id) order, and a hard-bounded buffer (500 events; oldest dropped
  and counted — backpressure-tested with 1,000 events).
- **Follow/favorites:** local-only preferences in SQLite (base URL +
  followed ids), persisted across restarts; followed-only feed filter.
  Follows are NEVER sent to the server.
- **Highlights (precisely defined):** Ledger events whose actors include a
  followed Descender AND whose public event type is in the contract's
  notable set (the public projection of the server's
  `NOTABLE_FOLLOW_EVENT_TYPES`). Computed locally; tested.
- **Replay browser:** direct Ledger queries by `after_tick` and
  `event_type` (public names; the server maps them to stored names).
- **Strictly read-only enforcement:** `HttpFeedClient` exposes only GET
  operations; an integration test records all requests against the
  fixture server and asserts every one is a GET and none touches the
  server's POST session endpoints (`/live/follow`, `/live/release`) or
  any simulation/write path. Oversized (>2 MB), malformed, timed-out,
  and unreachable responses all map to named, actionable errors.
- **Codex-review fixes (2026-10-24):** switching sources clears all
  source-specific buffered state (engine store/descent/status AND
  renderer profile/history/search/replay) before the new source is
  contacted, never-established reconnects do a full initial sync instead
  of resuming a previous source's cursor, and stale renderer responses
  are rejected by a connection-generation guard; the HTTP timeout now
  covers body consumption (stalled bodies produce `FEED_TIMEOUT`);
  polling catch-up widens 300 → 1000 when a batch fills its limit and,
  when even the widened window fills, reports the truncated window
  explicitly (`truncatedCatchUps` in the feed snapshot + status warning)
  instead of silently advancing past possible loss — a complete fix for
  >1000-event windows needs a contract change (no backward paging).
- **Codex-review fixes, cycle 2 (2026-10-24):** a Descent identity
  change at the same Feed URL is now detected from the health response
  before any catch-up request is issued — in both the poll loop and
  automatic reconnection the engine discards the old Descent's
  buffer/cursor and fresh-syncs the new Descent instead of resuming
  `after_tick=<old cursor>` against it; renderer profile/history
  responses are additionally guarded by a selection-specific request
  token (plus a response-ID check), so a slow response for a superseded
  Descender selection can no longer overwrite the current selection.
- **Codex-review fixes, cycle 3 (2026-10-24):** on macOS, closing the
  window left the process running with no way to get a window back —
  `window-all-closed` correctly skipped `app.quit()` on darwin and
  `mainWindow` was nulled on close, but `createWindow()` was only called
  at boot and no `activate` handler existed. The window lifecycle now
  lives in `electron/main/windowLifecycle.ts` (`registerWindowLifecycle`,
  wired into `main.ts` boot): an `activate` event (e.g. a Dock click)
  recreates the window when none exists and is a no-op when one does;
  `window-all-closed` still quits on non-macOS platforms only. Covered
  by 5 new regression tests in `tests/backend/windowLifecycle.test.ts`
  (fake App: activate-after-close recreates, activate-with-window does
  not duplicate, darwin does not quit, win32/linux quit, plus a wiring
  check on `main.ts`). macOS itself is not available in this environment,
  so the handler is unit-verified, not exercised on a real Mac.
- **Preferences export/import:** versioned envelope (`formatVersion
  1.0.0`); unknown majors rejected (`PREFS_VERSION_UNSUPPORTED`).
- **Preload hygiene:** sandboxed preload is self-contained (type-only
  shared imports, literal channel strings, lockstep-tested against the
  main channel table); the compiled preload requires only `electron`
  (verified on the build artifact).

## Implemented but not verified on target

- Connection to a **real owner-run Underreach Feed API** (the adapter is
  contract-faithful and integration-tested against the fixture server,
  but no live server was available here).
- Windows 11 click-through and NSIS packaging (no Wine on this VM);
  no code signing.

## Planned / not in MVP

- Archived Descent navigation (spec item 8) — replay covers past events
  of the current Descent only.
- Server-side notification stream (would require the server's session
  endpoints, which this read-only client deliberately does not use).
- Stratum/sector map view; standings/trending/echoes panels (contract
  routes exist; not consumed by the MVP).

## Acceptance walkthrough (demo mode, as run by smoke + tests)

Start demo → 8 fixture Descenders listed → select Mira Vane → profile
with relationships and history renders → live events append in order
without duplicates → follow Mira → highlights populate → replay after
tick 1220 returns only later events → disconnect. The packaged-main
smoke run performs the equivalent flow over real HTTP against the
fixture server and prints `SMOKE_OK`.
