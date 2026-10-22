# Execution roadmap for Muse

Status at handoff: **documentation prepared; application not yet implemented**. All unchecked items genuinely pending until tested.

**Instruction:** do not spend multiple sessions merely reorganizing plans. Implement working vertical slices with tests. Keep unrelated projects untouched. Prefer a feature demonstrable on a normal Windows PC over a large untested architecture.

## M0 — project scaffold and local app [DONE 2026-10-22, verified on Linux]
- [x] Inspect workspace and read instructions/specs.
- [x] Scaffold Electron/React/TypeScript in this project's `app/` folder only; pin supported tool versions and lockfile.
- [x] Start a real native desktop window and show Library, Favorites, Recent, Settings navigation with real empty states.
- [x] Add strict main/preload/renderer privilege boundary and validated IPC.
- [x] Implement project-local build, tests, lint and typecheck scripts.
- [x] Confirm `npm ci` + development start + production compile where supported.
**Completion gate:** runnable desktop app, not browser-only prototype. **Met:** `npm run smoke` opens a real Electron window under xvfb; `npm run dev` verified (tsc watch + Vite + Electron).

## M1 — genuinely useful manual launcher [DONE 2026-10-22, verified on Linux; Windows .exe path implemented but unverified]
- [x] File picker to add an installed local Windows executable. (Picker implemented; on Windows filters to `.exe`. Exercised on Linux where the filter allows any file — documented in app README.)
- [x] Title editing and duplicate detection. (Card artwork/cover is M5; cards are text-only, no fake covers.)
- [x] SQLite persisted game list + migrations; library cards and details page.
- [x] Launch the user-selected executable safely, with path checking and actionable errors.
- [x] Favorites, remove-from-library (non-destructive), search and sorting.
- [x] A reliable tracked process session for manually launched programs, stop/end detection where possible.
- [x] Save/reload data after closing and reopening app; unit/integration/Electron smoke tests.
**Completion gate:** add a real local game, launch it, see actual session, favorite it, restart and see all changes persisted. **Met on Linux** with a real spawned process: 2010 ms observed session on natural exit, favorite + totals + session all survived DB reopen. Windows `.exe` launch and installer are implemented per spec but unverified (need Windows).

## M2 — Steam integration [DONE on Linux 2026-10-22; Windows client verification pending]
- [x] Steam presence discovery and local multi-library file parsing.
- [x] Parse VDF libraryfolders and ACF manifests with fixture tests and malformed-input resilience.
- [x] Import installed AppIDs/titles, preserve user edits after re-scan.
- [x] Launch via validated Steam native URI with accurate launch-request state.
- [x] Missing Steam / invalid AppID / removed install handling, source filter and status UI.
**Completion gate:** on Windows with Steam-installed games, rescan finds real games and a chosen game opens through Steam; test negative and offline cases. — **Partially met:** all parsing/scan/sync/launch-handoff logic verified on Linux against fixture Steam trees (124/124 tests pass, incl. malformed manifests, hostile paths, cancellation, idempotent re-scans). Still unverified: real Steam client discovery on Windows, real `steam://` handoff opening the client, multi-drive libraries on a real PC.

## M3 — Epic integration [NOT STARTED]
- [ ] Implement local Epic manifests scanner with fixtures and path validation.
- [ ] Import known installed titles without needing an API credential.
- [ ] Verify direct-launch route on real client or implement honest Open Epic Launcher fallback.
- [ ] Expose capability/reason on game cards. Preserve user customizations on re-scan.
**Completion gate:** real available Epic installations appear accurately; supported actions work and unsupported actions never pretend to succeed.

## M4 — Battle.net integration [NOT STARTED]
- [ ] Investigate verifiable, nonsecret local detection mechanisms and supported games.
- [ ] Implement best-effort adapter and fixture tests, or a clearly documented manual registration fallback where unsupported.
- [ ] Verify direct launch only when genuine supported mechanism exists; otherwise Open Battle.net client.
- [ ] Show limitations and permission/missing-client cases.
**Completion gate:** Battle.net-associated detected entries work as far as reliably possible, and the UI never fabricates universal support.

## M5 — production quality, artwork and sessions [NOT STARTED]
- [ ] User-selected cover art; local icon extraction or safe placeholders.
- [ ] Recently Played, favorite/game filters, sort, appearance modes, keyboard focus/accessibility.
- [ ] Reliable manual process duration; source-specific honest playtime coverage; privacy tracking toggle and clear history.
- [ ] Partial scan failures, rescans/deduplication, selected-folder scans, missing paths, cancellation.
- [ ] Offline restart and cache, interruption/session recovery, progress indicators.
- [ ] Performance baseline with 500+ library entries.
**Completion gate:** robust, polished launcher with no fabricated session durations.

## M6 — Windows package, tests, sign-off [NOT STARTED]
- [ ] Windows x64 installer build command, installable artifact (not committed), installation README.
- [ ] Verify first launch, scan, launch, persistence, missing clients, uninstall on Windows 11, where environment permits.
- [ ] Validate bundled app still loads assets, DB and sandboxed main process after packaging.
- [ ] Run project tests, typecheck, lint, build, end-to-end smoke and security checks. Record commands/outcomes.
- [ ] Update README, handoff and release notes with actual shipped features and known limitations.
- [ ] Do not release or auto-publish without owner approval.
**Completion gate:** `TEST_PLAN.md` MVP tests passed with evidence, or any Windows-specific unverified tests called out precisely.

## Useful stretch items — DO NOT block MVP

- [ ] Import/export local catalog metadata
- [ ] Per-game local launch presets
- [ ] Gamepad-friendly couch UI
- [ ] Cover-art service with attribution and opt-in networking
- [ ] Optional library deduplication/grouping across stores
- [ ] Additional stores: GOG, EA app, Ubisoft Connect, itch.io
- [ ] Linux/Steam Deck support (separate project phase)
- [ ] Advanced session correlation for vendor-launched games only with verified methods
- [ ] Advanced hardware/performance overlays — not part of MVP

## Iteration discipline

1. Check git status and preserve work already present.
2. Pick the smallest unchecked, user-visible functionality.
3. Implement code and test it in the actual app, not mockup screenshots.
4. Run available lint/types/tests/build; paste actual command results in progress notes.
5. Update checkboxes only after validation (mark **implemented but unverified** if testing unavailable).
6. Commit project-scoped changes and provide next concrete task.
7. Ask owner only for a real blocker: Windows machine/test access, vendor installation/test library, release authorization or a decision not covered by the brief.

## Progress log

2026-10-22: Documentation and instructions created, no app implementation, no runtime tests.
2026-10-22: M0+M1 implemented and verified on Linux (branch `universal-game-launcher/m0-m1-foundation`, local commits only, not pushed).
  Toolchain: electron 45.0.0, react 19.3.1, vite 8.3.5, typescript 5.9.3, zod 4.6.7, vitest 5.0.5, electron-builder 26.15.3 (config only).
  SQLite via node:sqlite (built into Node 24/Electron 45) — chosen over better-sqlite3 after a spike showed it works identically in vitest and Electron with zero native builds; documented in app/README.md.
  Evidence: `npm ci` ok; `npm run typecheck` clean (3 projects); `npm run lint` clean; `npm test` 56/56 pass (unit: args/validation/migrations/sessions/IPC schemas; integration: library CRUD + launch lifecycle with stubbed spawn; AT-07 headless security); `npm run build` ok; `npm run smoke` PASS (real window under xvfb); `npm run dev` verified (tsc watch + Vite :5173 + Electron under xvfb).
  M1 e2e (real process, /tmp script): add -> launch -> 2010 ms observed session on exit -> favorite -> DB reopen: game, favorite, totalPlayMs, lastPlayedAt, session all persisted.
  Windows-only (implemented, unverified): real .exe launch, .exe picker filter branch, electron-builder installer, packaged-app startup.
2026-10-22: M2 Steam integration implemented and verified on Linux (branch `universal-game-launcher/m2-steam`, local commits only, not pushed).
  New: `electron/main/sources/steam/` (vdf.ts pure parser, os.ts injectable OS layer, adapter.ts probe/scan/validateLaunch, sync.ts idempotent merge); DB migration v2 (install_dir, launch_uri, launch_capability, launch_reason + unique index on source/external_id); steam:// URI handoff in launcher with 'unavailable' tracking sessions (no invented playtime); IPC sources.scan/sources.status/sources.cancelScan; UI source filter + Steam scan controls in Settings + capability-aware Play buttons.
  Evidence: `npm run typecheck` clean; `npm run lint` 0 errors (1 pre-existing warning); `npm test` 124/124 pass (new: 22 VDF, 30 adapter, 6 sync, 10 IPC integration); `npm run build` ok.
  Windows-only (implemented, unverified): real Steam client discovery, real steam:// handoff opening the client, multi-drive libraries on a real PC.
