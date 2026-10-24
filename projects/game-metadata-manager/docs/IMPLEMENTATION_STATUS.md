# Implementation status — Game Library Metadata Enricher

- **Overall status:** MVP functional — review ready (2026-10-23)
- **Priority:** 7/17
- **Source/code implemented:** Full stack — backend (`app/engine/`, `app/db/`, `app/main/`, `app/preload/`), renderer (`app/renderer/`), shared IPC contract
- **Build validated:** Yes — `npm run build` compiles renderer JSX + main + preload; `npm run smoke` PASS (real window under xvfb, renderer bundle loaded)
- **Automated tests executed:** Yes — **82/82 green** (32 backend + 50 renderer), 2026-10-23
- **End-to-end MVP verified:** Yes — recorded acceptance walkthrough (`app/tests/acceptance.test.ts`) on the real engine: import 3-game fixture → edit title/description/tags/artwork → delete one exe → rescan flags it missing (nothing deleted) → export bundle v1.0.0 → wipe → re-import restores everything identically
- **Owner review:** Pending

## First milestone

Import a fixture library, edit artwork/title/tags, detect a missing path, and export a reversible metadata bundle.

## Worker A — backend (2026-10-23, branch `game-metadata-manager/mvp`)

**Implemented & verified:**
- `app/shared/ipc-contract.ts` — shared `window.gmm` channel contract (17 channels; committed first so the renderer builds against it)
- `app/engine/scanner.ts` — `*.exe` scan, depth ≤ 4, skips `node_modules`/`.git`/`Windows`, title from filename, symlink-loop guard, id = sha256(normalized installPath)
- `app/engine/library.ts` — CRUD, dedupe-by-id import, `rescan()` marks missing via `fs.existsSync` and **never deletes**, per-field `ChangeEntry` on update, tag/collection add/remove (removal detaches, never deletes games)
- `app/engine/artwork.ts` — magic-byte validation (PNG/JPEG/WEBP only), ≤ 10 MB, symlinks resolved explicitly, app-owned cache dir, `file://` URLs
- `app/engine/bundle.ts` — export JSON (`formatVersion: "1.0.0"`, games + base64 artwork + tags/collections), 50 MB guard, semver version gate rejecting unknown majors, per-field newest-`updatedAt` merge with `ConflictInfo` records, `ChangeEntry` records for bundle-sourced changes, export→wipe→import reversibility
- `app/engine/changes.ts` — append-only changelog, `undo` restores the most recent field (undo of a bundle-added game removes the game)
- `app/db/schema.ts` — `node:sqlite` with `schema_version` migration v1, explicit BEGIN/COMMIT/ROLLBACK, DB at userData (gitignored)
- `app/main/main.ts` + `app/preload/preload.ts` — Electron 45 main, BrowserWindow, zod-validated IPC handlers for all 17 channels, typed `window.gmm`

**Evidence (2026-10-23, Linux VM, Node v24):**
- `npm run typecheck` (tsc strict + noUncheckedIndexedAccess): clean
- `npm run lint` (eslint, `--max-warnings=0`): clean
- `npx vitest run`: **31/31 green** — scanner (depth limit, skips, symlink loop, title derivation), artwork (valid PNG/JPEG/WEBP, corrupt, oversize, missing, dangling symlink, GIF rejection), library (dedupe, change entries, no-op update, missing detection without deletion, tag detach), undo (revert, empty log), bundle (round-trip identical incl. artwork/tags/collections, newer-bundle-wins / older-local-wins conflicts listed, change entries for bundle changes, version rejection: unknown major / bad semver / missing formatVersion / non-JSON / >50 MB, minor/patch acceptance)
- `npm run build` (vite): clean — `dist/` contains renderer, `main.js`, `preload.mjs`
- Window smoke (`xvfb-run electron --no-sandbox dist/main.js`, 25 s): window created, handlers registered, no JS errors
- Bundle round-trip acceptance: export → wipe → import restores title/description/artworkId/tagIds/collectionIds, artwork files, tags and collections identically

**Platform gaps (not verified here, need Windows):** real `.exe` discovery on a Windows drive, `file://` artwork display in the renderer, portable zip install/uninstall on Win11.

## Worker B — renderer

Renderer files are being built by Worker B against the shared contract above (untracked in this branch at the time of the backend commit; Worker B commits them separately).

## Reconciliation pass (2026-10-23, coordinator)

Worker A (backend) and Worker B (renderer) built against the shared contract
but diverged in three integration points; all reconciled and verified:

1. **Build wiring** — `app/vite.config.ts` had no `@vitejs/plugin-react`, so
   `npm run build` could not compile the renderer JSX. Added the React plugin;
   `dist/` now contains `index.html` + renderer assets + `main.js` +
   `preload.mjs`. (`app/index.html`, `app/tsconfig.renderer.json` also committed.)
2. **Test wiring** — root `vitest.config.ts` only ran backend tests. `npm test`
   now runs both suites: backend (node) + renderer (jsdom).
3. **`window.gmm` API shape** — the original spec sketched nested namespaces
   (`gmm.lib.list()`); the preload implements a flat typed API (`gmm.list()`,
   `gmm.updateGame()`, …). Resolution: the flat API is canonical (implemented,
   typed, tested, smoke-verified); the contract header documents the method→
   channel mapping; the renderer keeps a tested nested facade over it.
4. **Real bug found and fixed — missing-install badges never lit up:**
   `lib:rescan` returns `missingIds` but `lib:list` always reports
   `missing: false` (flags are computed on demand, never persisted), so the
   library view's MISSING badges and missing-only filter stayed empty after a
   rescan. Fixed in `app/renderer/src/hooks.ts`: `useLibraryData` now merges
   the rescan result into the loaded games on every refresh — badges and the
   filter work on load and after each rescan. Regression tests:
   `renderer/tests/hooks.test.tsx` (2).
5. **Smoke script** — added `npm run smoke` (`GMM_SMOKE=1` hook in
   `app/main/main.ts` prints SMOKE_OK once the real renderer bundle loads,
   then quits) and wired the renderer into `npm run typecheck`.

## Next action

Open the PR (left unmerged for owner review); continue with Project 8.

## Acceptance notes

Record actual commits, tests, blockers and PR links here when implementation begins. Do not infer success from the existence of this planning document.
