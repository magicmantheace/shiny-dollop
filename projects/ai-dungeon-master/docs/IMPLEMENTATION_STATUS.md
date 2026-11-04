# Implementation status — AI Dungeon Master

- **Overall status:** MVP FUNCTIONAL — implemented and verified on Linux (Node 24, Electron 45 under xvfb); Windows 11 behavior is **implemented but not verified on target OS**.
- **Priority:** 16/17
- **Branch:** `ai-dungeon-master/mvp`
- **Build validated:** Yes — `npm run build` green (Vite renderer + tsc main/preload).
- **Automated tests executed:** Yes — 40/40 passing (see TEST_PLAN.md verification record).
- **End-to-end MVP verified:** Yes — smoke mode (`npm run smoke`) runs the packaged Electron main under xvfb and executes the full acceptance workflow against a real SQLite file, including close/reopen resume; prints `SMOKE_OK`.
- **Owner review:** Pending (PR to be opened by the parent agent).

## What is implemented

- **Campaigns & sessions** — create/select/delete campaigns; per-campaign sessions with editable notes and end timestamps, persisted in SQLite (`node:sqlite`).
- **Character sheets** — PCs and NPCs with the original AIDM house ruleset (attributes Might/Agility/Wits/Spirit, −2..+4; HP; inventory; notes), validated CRUD.
- **Transparent dice engine** (`app/shared/dice.ts`) — notation `NdM±K`; each campaign owns a seeded PRNG stream whose 32-bit state is persisted on the campaign row. Every roll records dice, modifier, total, and stream state before/after, and can be replayed exactly (`replayRoll`). Rolls are append-only log entries and can never be edited or silently rerolled.
- **Attribute checks** — 2d6 + attribute vs the house difficulty table (Easy 7 / Standard 9 / Hard 11 / Heroic 13), outcome decided only by the engine, logged with breakdown.
- **Initiative & encounters** — initiative rolled per combatant from the campaign stream (each roll logged), turn order sorted by total (ties: Agility, then name), turn/round tracker, damage/healing with HP clamping and before/after log entries, encounter end. Closing and reopening the app mid-encounter resumes exactly (tested at the DB level and in smoke).
- **NPC/location memory** — per-campaign memory entries (npc/location/fact) with tags and substring search.
- **Narration (flavor only)** — adapter interface with a deterministic offline mock narrator (default) and an optional loopback-only HTTP narrator (Ollama-style `/api/generate`). Narration is attached to a log entry's narration fields via the store's single-purpose `attachNarration`; narrators receive a read-only view and have no access to rules state. Endpoint failure falls back to mock text (`mock-fallback`). Cloud endpoints are rejected in settings.
- **Imports (contract-level, fixtures only)**
  - Worldbuilding Manager backup (`worldbuilding-manager.project`, formatVersion 1.0.0) → character/location/other entities become npc/location/fact memory entries.
  - Procedural Dungeon Designer manifest (`procedural-dungeon-designer/map`, formatVersion 1.0.0) → one location memory entry summarizing rooms and placements.
  - Both reject unknown major versions with `IMPORT_VERSION_UNSUPPORTED` and wrong formats with `IMPORT_INVALID`.
- **Campaign export/backup** — versioned JSON bundle (`ai-dungeon-master/campaign`, 1.0.0), byte-deterministic (stable key-sorted stringify, no timestamps in the envelope); import into a fresh DB reproduces the campaign byte-identically; id collisions remap consistently.
- **Preload hygiene** — sandboxed preload is self-contained at runtime (type-only shared imports, literal channel strings), guarded by `tests/backend/preload-hygiene.test.ts`.

## House ruleset

Original and documented in `app/shared/ruleset.ts`: four attributes, 2d6 checks, initiative 2d6 + Agility. No published rulebook content is used anywhere — no D&D stat blocks, spells, or monsters.

## Not in MVP (planned / backlog)

- Versioned ruleset packs beyond the built-in house ruleset.
- Speech synthesis for narration (narration is text-only).
- Multi-campaign encounter history views; undo beyond "corrections are new log entries" (the log is append-only by design).

## Verification record (2026-10-23, Linux VM, Node 24)

| Command | Result |
| --- | --- |
| `npm test` | 40/40 tests pass, 8 files (36 backend + 4 renderer) |
| `npm run typecheck` | clean |
| `npm run lint` | clean (`--max-warnings 0`) |
| `npm run build` | green (renderer + main) |
| `npm run smoke` | SMOKE PASS — packaged main printed `SMOKE_OK` under xvfb |

## Platform labels

- Linux (this VM): implemented **and verified**.
- Windows 11 click-through, NSIS packaging on Windows: **implemented but not verified on target OS** (no Wine/Windows here). No code signing.
- A real local model endpoint on the owner's machine: the HTTP narrator is verified against a loopback test server; a real Ollama instance is **implemented but unverified**.

## Codex-review fixes, cycle 4 (2026-10-24, PR #21, FINAL)

All three findings from the cycle-3 re-review verified against the code before fixing:

- **Reject redirects from the loopback narration endpoint (P1, `narrator.ts`):** `HttpNarrator` used fetch's default redirect handling, so a 307/308 from the configured loopback endpoint would forward the POST body (session event text) to a non-loopback destination. The fetch now uses `redirect: 'manual'` and any 3xx response is rejected as `NARRATION_UNAVAILABLE` (the service then falls back to mock narration) — no redirect is ever followed and no data is sent to a redirect target.
- **Make campaign imports transactional (P2, `service.ts` / `store.ts`):** `importCampaign` inserted the campaign and its rows one by one with no transaction, so a bundle with a new campaign id but a reused session/character id left a partially restored campaign behind when a later insert hit the uniqueness constraint. The store now exposes `transact(...)` and the whole import runs inside it — any failure rolls back every insert.
- **Expose campaign import without an active campaign (P2, `App.tsx`):** the Campaign data section (including whole-campaign import) sat inside the `campaign &&` conditional, so a fresh installation had to create a dummy campaign before restoring a backup. The section now renders unconditionally; only the campaign-scoped actions (export, worldbuilding/dungeon imports into the active campaign) remain conditional.

- **Verification:** `npm test` — **55/55 pass** (52 before; +3 regression tests: redirect never followed / target receives nothing, transactional import rollback on a colliding later insert, campaign import visible and usable with no active campaign); `npm run typecheck`, `npm run lint`, `npm run build` clean.

## Codex-review fixes, cycle 5 (2026-11-04, PR #21)

Ground truth: the latest Codex review (id 5641531410, on head `542c1c0e4`) carried exactly two findings. The other 11 inline comments belong to earlier rounds on superseded commits and had already been answered by the cycle 1–4 fix commits; the summary block's unresolved flag tracks those historical threads.

Both current-head findings were verified against the code and reproduced with regression tests before fixing:

- **Return structured IPC failures instead of throwing plain objects (P2, `electron/main/ipc.ts` / `electron/preload/preload.ts`):** handlers previously threw the plain `{ code, message }` AidmError across Electron IPC, where the invoke dispatcher serializes a thrown plain object as `[object Object]`, losing the actionable error. Handlers now resolve an `AidmIpcResult` envelope — `{ ok: true, value }` or `{ ok: false, error }` — and the preload unwraps it, returning successful values and rejecting with the preserved AidmError. Malformed IPC responses produce an `INPUT_INVALID` AidmError rather than leaking an unshaped value.
- **Guard direct encounter updates against campaign switches (P2, `src/components/App.tsx`):** encounter start and advance-turn responses previously called `setEncounter` directly, bypassing `refreshAll`'s campaign/generation guard, so a response for campaign A could be installed after switching to campaign B. Both paths now apply the result through `applyEncounterIfSelected`, which compares the returned encounter's `campaignId` with the currently selected campaign and discards stale results.

- **Verification:** `npm test` — **59/59 pass** (55 before; +2 preload-envelope tests and +2 stale-encounter renderer tests, with the 2 existing IPC tests updated to envelope expectations). Negative check: with the source fixes stashed, exactly those 6 regression tests fail and the other 14 tests in the targeted files pass. `npm run typecheck`, `npm run lint`, and `npm run build` are clean; `npm run smoke` prints `SMOKE_OK`.
