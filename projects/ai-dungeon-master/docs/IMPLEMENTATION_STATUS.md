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
