# Implementation status — Novel and Worldbuilding Manager

- **Overall status:** MVP FUNCTIONAL / REVIEW READY (branch `worldbuilding-manager/mvp`, unmerged)
- **Priority:** 14/17
- **Source/code implemented:** Yes — `app/` (Electron 45 + React 19 + TypeScript strict + Vite, `node:sqlite`, zod-validated IPC)
- **Build validated:** Yes — Linux VM, Node 24: `npm run build` green (typecheck + main + preload + renderer)
- **Automated tests executed:** Yes — **27/27 pass** (23 backend engine tests against real SQLite + 4 renderer UI tests), `npm run lint` clean
- **End-to-end MVP verified:** Yes — `npm run smoke` PASS against the compiled build on a real on-disk database: create character/location/timeline event/note → link them → search notes → continuity check → export JSON backup → import into a fresh database → byte-identical re-export → Markdown export
- **Owner review:** Pending

## Implemented and verified (Linux)

- Entity CRUD for characters, locations, factions, timeline events and notes, with validated persisted state and per-type fields (role, story date, order keys, birth/death order, tags)
- Bidirectional links/relationships with labels; deletion cascades links (no dangling references — tested)
- Timeline ordering by order key (custom calendars via free-text story dates + numeric keys)
- FTS5 full-text search across names/descriptions/bodies with type filters
- Deterministic continuity warnings (`EVENT_AFTER_DEATH`, `EVENT_BEFORE_BIRTH`) with positive and negative tests
- Append-only revision history per entity
- Versioned JSON backup (`formatVersion 1.0.0`) with byte-identical round-trip; named-error rejection for corrupt/dangling/unknown-major/oversized backups; single-document Markdown export
- Persistence across database reopen (tested)

## Codex review fixes (2026-10-24, PR #19 fix cycle 1)

- Backup size policy unified: one shared 64 MiB cap (`MAX_BACKUP_BYTES` in `shared/types.ts`) enforced by both `exportBundle()` (new `EXPORT_TOO_LARGE` — an unrestorable backup is never produced) and `importBundle()`; the IPC import schema limit was aligned to the same constant. Regression tests round-trip a >10 MiB revision-grown backup and cover the over-cap export refusal.
- Renderer: unsaved entity edits are no longer discarded when adding/removing a relationship refreshes the entity list — edit drafts initialize only when the selected entity id changes (regression test in `tests/ui/App.test.tsx`; the fake API now returns fresh objects per list call, matching IPC cloning).
- Main process (macOS): the `WorldStore` now closes on `before-quit` instead of `window-all-closed`, so close-window → reactivate keeps the database usable; `WorldStore.close()` is idempotent. Regression test with mocked Electron lifecycle + real store/IPC in `tests/backend/main-lifecycle.test.ts`.
- Verified: 31/31 tests pass (was 27), typecheck and lint clean. All four new tests fail against the pre-fix code.

## Implemented but not verified on target OS

- Windows 11 desktop behavior (window, packaged app, real user-data paths) — no Windows execution has taken place
- `npm run package:win` (electron-builder/NSIS) — configured, not run (no Wine on this VM); no code signing

## Planned / not in MVP

- Full relationship graph visualization (MVP lists relationships per entity)
- Revision rollback UI, multi-project/library management, triggers or AI assistance of any kind
- Optional character export toward AI Dungeon Master (backlog item 16; no integration built)

## Acceptance notes

Synthetic fictional fixtures only (e.g. "Sera Vane", "Port Sorrow") — no owner writing or personal data was used. Commands and results are recorded in `docs/TEST_PLAN.md`.
