# Test plan — Crawl Live Spectator Desktop

**Current test status:** RUN — 45/45 automated tests pass plus packaged-main smoke `SMOKE_OK` (see verification record below). Live-server and Windows checks remain **implemented but unverified**.

## Required automated and integration scenarios

- Typed read-only API contract fixtures — ✅ `tests/backend/contract.test.ts`, `tests/backend/client.test.ts`
- Disconnect/reconnect/backpressure — ✅ `tests/backend/engine.test.ts` (server kill/restart, cursor resume), `tests/backend/feedStore.test.ts` (1,000 events into a 10-cap buffer)
- Distinguish live truth from fixture/demo mode — ✅ `tests/renderer/App.test.tsx` (DEMO vs LIVE banner), engine status messages
- No simulation write endpoint usage — ✅ `tests/backend/client.test.ts` records every fixture-server request: all GET, no `/live/follow`, `/live/release`, or write paths
- Event ordering, IDs and replay cursor handling — ✅ `tests/backend/feedStore.test.ts`, `tests/backend/fixture.test.ts`, `tests/backend/engine.test.ts`

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs. — ✅ malformed contract payloads rejected (`FEED_CONTRACT_INVALID`); oversized responses rejected (`FEED_RESPONSE_TOO_LARGE`); timeouts (`FEED_TIMEOUT`); unreachable (`FEED_UNREACHABLE`); credential-bearing URLs rejected (`BASE_URL_INVALID`); blank search rejected.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant. — ✅ prefs persist across DB reopen; export/import round-trip; unknown format major rejected.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior. — ✅ reconnect/backoff recovery after server death; request timeout path.
- Confirm tests use temporary fixtures and do not read owner's private or production data. — ✅ all data is the invented fixture set; DBs live in tmpdirs.
- Verify deterministic calculations and no accidental state changes in read-only actions. — ✅ fixture determinism test (two instances byte-identical); read-only request recording.

## End-to-end MVP verification

Connect to a running local Underreach Feed API, display real Descenders, select one and inspect authentic state/history plus live updates.

**Status:** verified end-to-end in **demo/fixture mode** (in-process fixture feed in tests; real HTTP against the fixture Feed server in the packaged-main smoke). The same flow against an owner-run live Feed API is **implemented but unverified** — no live Underreach server exists in this environment.

## Verification record

Environment: Linux VM, Node 24, Electron 45 under Xvfb for smoke. Branch `crawl-spectator-desktop/mvp`.

| Command | Result |
| --- | --- |
| `npm test` | **45 passed / 0 failed** (8 files: 39 backend + 6 renderer) |
| `npm run typecheck` | clean |
| `npm run lint` | clean (`--max-warnings 0`) |
| `npm run build` | green (Vite renderer + `tsc` main) |
| `npm run smoke` | **SMOKE_OK** — packaged main connected in LIVE mode to the fixture server, listed 8 Descenders, loaded a profile with relationships + history, searched, listed parties, verified feed ordering/dedupe, follows + highlights, replay `after_tick` semantics, GET-only wire log, prefs persistence across DB reopen, and demo-mode connect |

Per-suite counts: contract 5, feedStore 5, fixture 7, prefs 4, client 11, engine 4, preload 3, renderer App 6.

## Remaining gaps

- Real owner-run Feed API connection — unverified (needs the owner's server).
- Windows 11 run/packaging — unverified (no Wine on this VM).
