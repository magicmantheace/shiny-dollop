# Novel and Worldbuilding Manager

**Status:** MVP functional / review ready — implemented and verified on Linux (see `docs/IMPLEMENTATION_STATUS.md`); Windows 11 behavior is implemented but not verified on the target OS.

**Priority:** 14 of 17 in the approved intake queue.
**Category:** Creative writing desktop
**Repository workspace:** `projects/worldbuilding-manager/`

## Purpose

Organize stories, characters, lore, timelines, locations and relationship continuity — fully offline. The author retains control and copyright; there is no external sync and no network access.

## MVP (implemented)

- **Entities** — characters (role, birth/death timeline order), locations, factions, timeline events (story date + numeric order key) and notes/chapters/outlines (markdown-friendly body, tags), all with persisted, validated CRUD.
- **Links & relationships** — any entity can link to any other with a label (ally, rival, family, located-in, …); links are bidirectional in views, listed on each character sheet, and are cleaned up when an entity is deleted (no dangling references).
- **Timeline view** — events ordered by their order key (keyless events last), then story date.
- **Search** — SQLite FTS5 full-text search across names, descriptions and bodies, with an optional type filter.
- **Continuity warnings** — one deterministic rule set: an event linked to a character fires `EVENT_AFTER_DEATH` when its order key is after the character's recorded death order, and `EVENT_BEFORE_BIRTH` when before their birth order. No vague or AI-generated warnings.
- **Revision history** — every create/update appends an immutable revision snapshot, viewable per entity.
- **Backup & export** — a complete project backup as a versioned JSON bundle (`worldbuilding-manager.project`, `formatVersion 1.0.0`, byte-deterministic) plus a human-readable single-document Markdown export. Import restores a backup into a fresh database byte-identically; corrupt, malformed-dangling or unknown-major-version bundles are rejected with named errors (`IMPORT_INVALID`, `IMPORT_TOO_LARGE`, `IMPORT_VERSION_UNSUPPORTED`).

## Running it

```bash
cd projects/worldbuilding-manager/app
npm install
npm run build      # typecheck + main + preload + renderer
npm test           # 27 tests (backend engine + renderer UI)
npm run smoke      # end-to-end MVP acceptance workflow against the compiled build
```

The packaged app stores its database as `worldbuilding.sqlite` in the OS user-data folder. Windows packaging (`npm run package:win`, electron-builder) is configured but has not been verified on Windows hardware.

## Layout

- `app/db/world.ts` — the SQLite engine (entities, links, revisions, FTS5 search, timeline, continuity, backup/Markdown export). Pure Node, no Electron imports.
- `app/shared/` — domain types, named error codes, zod IPC schemas.
- `app/electron/` — main process, zod-validated IPC handlers, and a self-contained sandboxed preload exposing only `window.wbm`.
- `app/src/` — React renderer (create/edit, links, timeline, warnings, search, backup).

See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), [status](docs/IMPLEMENTATION_STATUS.md), and the [development handoff](docs/MUSE_HANDOFF.md).
