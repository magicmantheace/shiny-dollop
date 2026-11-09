# Test plan — Novel and Worldbuilding Manager

## Verification record — MVP run (2026-10-23)

- **Environment:** Linux VM, Node v24.22.1, npm 10.9.4; branch `worldbuilding-manager/mvp` based on `origin/main` @ `5f85320`
- **Commands and results:**
  - `npm install` — 456 packages, clean
  - `npm test` — **27/27 pass** (2 files: 23 backend + 4 UI)
  - `npm run typecheck` — clean (main, preload, renderer configs)
  - `npm run lint` — clean
  - `npm run build` — green (main + preload + renderer bundles)
  - `npm run smoke` — **SMOKE PASS** (compiled engine, real on-disk SQLite, full acceptance workflow)
- **Platform gaps:** Windows 11 execution and NSIS packaging are **implemented but not verified on target OS** (no Windows/Wine on this VM).

## Automated scenarios (all passing)

- Entity CRUD per type (character/location/faction/event/note), update persistence, persistence across DB reopen
- Linked entities survive rename; links bidirectional in views; relationship labels on both character sheets
- Deleting an entity removes all its links (no dangling references); removeLink removes exactly one
- Self-links and links to missing entities rejected (`SELF_LINK`, `ENTITY_NOT_FOUND`)
- Timeline sorting by numeric order key with keyless events last (custom-calendar story dates are display labels)
- Continuity warnings: after-death and before-birth positive cases; in-lifetime and unlinked events produce none
- FTS5 search hits across names/descriptions/bodies; type filter respected; blank queries return nothing
- Revision history appends on create and each update, snapshots in order
- Backup export → fresh-database import round-trip reproduces the project **byte-identically**; Markdown export covers entities and links
- Import rejection with named errors: malformed JSON / wrong format (`IMPORT_INVALID`), dangling links (`IMPORT_INVALID`, existing project untouched), unknown major version (`IMPORT_VERSION_UNSUPPORTED`), oversized backup (`IMPORT_TOO_LARGE`)
- Malformed/oversized entity input rejected (`VALIDATION_ERROR`): empty name, unknown type, >200k body, >20 tags

## End-to-end MVP verification

Workflow from the spec — create characters, locations and a timeline event, link them, search notes, export a complete project backup — is exercised end-to-end by `scripts/smoke.mjs` against the compiled build and a real database file, and equivalently in the backend test suite. The renderer flow (create via form, search narrowing, timeline order, warning display, backup export) is covered by the UI tests with an in-memory API fake; the engine those tests imitate is itself covered against real SQLite.

## Notes on the original intake scenarios

- "Unsaved edits recovered safely" — the MVP saves on explicit actions only; there is no draft/autosave state to recover. Recorded as a deliberate MVP boundary, not a pass.
- "No silent overwrites from optional AI features" — no AI features exist in the MVP; nothing writes without an explicit user action. Import is the one destructive operation: it replaces the whole project, is labeled as such in the UI, and validates fully before touching existing data.
