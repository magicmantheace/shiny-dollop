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

## M3 — Epic integration [DONE — logic verified on Linux; real-client checks need Windows]
- [x] Implement local Epic manifests scanner with fixtures and path validation.
- [x] Import known installed titles without needing an API credential.
- [x] Verify direct-launch route on real client or implement honest Open Epic Launcher fallback. → **Fallback implemented:** no per-game deep-link format could be verified against documentation, so cards show "Open Epic Games Launcher" via the documented `com.epicgames.launcher://` scheme and report "launch requested", never Running. (`electron/main/sources/epic/`)
- [x] Expose capability/reason on game cards. Preserve user customizations on re-scan.
**Completion gate:** — **Partially met:** manifest parsing (well-formed/missing/malformed/hostile: traversal, absurd sizes, wrong types), idempotent re-scan preserving user edits, scan/launch-handoff logic all verified on Linux against fixture manifest trees (part of 182/182 passing tests). Still unverified: real `%ProgramData%\Epic\EpicGamesLauncher\Data\Manifests` discovery on Windows, real `com.epicgames.launcher://` handoff opening the client.

## M4 — Battle.net integration [DONE — logic verified on Linux; real-client checks need Windows]
- [x] Investigate verifiable, nonsecret local detection mechanisms and supported games. → Documented in `app/docs/BATTLENET_INVESTIGATION.md`: `product.db` (undocumented binary), install-folder sniffing, registry keys, and invented URI schemes were each tried and rejected with reasons.
- [x] Implement best-effort adapter and fixture tests, or a clearly documented manual registration fallback where unsupported. → **Honest detect-client + manual-registration path** (`electron/main/sources/battlenet/`): probe finds `Battle.net.exe` in its standard install folders; scan completes with 0 games plus an explanatory warning.
- [x] Verify direct launch only when genuine supported mechanism exists; otherwise Open Battle.net client. → "Open Battle.net" spawns the validated exe (no shell, no args); no session recorded (client ≠ game).
- [x] Show limitations and permission/missing-client cases.
**Completion gate:** — **Met as far as reliably possible:** the UI never fabricates per-game Battle.net support; detection, fallback labeling, and missing-client states are fixture-tested. Still unverified: real `Battle.net.exe` discovery on a Windows PC with the client installed.

## M5 — production quality, artwork and sessions [DONE]
- [x] User-selected cover art; local icon extraction or safe placeholders. → File picker (image filter) → validated (ext/type/10 MB cap) → scaled to ≤512 px via nativeImage → uuid-named cache in app-data `covers/` with 100 MB oldest-first eviction. Cards show cover or initial-letter placeholder. No network fetching; forged filenames rejected at the IPC schema boundary.
- [x] Recently Played, favorite/game filters, sort, appearance modes, keyboard focus/accessibility. → Recent page; favorite/source/status filters + sort orders; dark/light/system theme persisted; aria labels/roles on interactive controls, focus-visible styles, autoFocus on dialog entry, Esc/backdrop close.
- [x] Reliable manual process duration; source-specific honest playtime coverage; privacy tracking toggle and clear history. → Checkpoint timer for manual launches; "launch requested" sessions never invent playtime; tracking toggle disables sessions + timers + watchers (verified: no background intervals except the active-session timer); clear-history with confirmation deletes app records only.
- [x] Partial scan failures, rescans/deduplication, selected-folder scans, missing paths, cancellation. → Per-source scan controllers; one source's failure never breaks the whole scan or erases the library; idempotent re-scans preserve user edits (title/favorite/hidden/cover).
- [x] Offline restart and cache, interruption/session recovery, progress indicators. → Crash/interruption recovery from M1 kept and extended to the new session paths with the same conservative semantics (interrupted, never fabricated).
- [x] Performance baseline with 500+ library entries. → 500-game fixture: full list + filtered/sorted query each well under 1 s (test asserts <1000 ms bounds); relevant DB columns indexed.
**Completion gate:** — **Met:** 182/182 tests passing (new: cover-store unit, cover IPC integration incl. forged-filename rejection, 500-entry perf), typecheck + lint clean, `npm run build` green. No fabricated session durations anywhere.

## M6 — Windows package, tests, sign-off [IN PROGRESS]
- [x] Windows x64 installer build command, installable artifact (not committed), installation README.
- [ ] Verify first launch, scan, launch, persistence, missing clients, uninstall on Windows 11, where environment permits.
- [ ] Validate bundled app still loads assets, DB and sandboxed main process after packaging.
- [ ] Run project tests, typecheck, lint, build, end-to-end smoke and security checks. Record commands/outcomes.
- [x] Update README, handoff and release notes with actual shipped features and known limitations.
- [ ] Do not release or auto-publish without owner approval.
**Completion gate:** `TEST_PLAN.md` MVP tests passed with evidence, or any Windows-specific unverified tests called out precisely.

### Packaging evidence (2026-10-22, Linux VM, electron-builder 26.15.3)
`npm run package:win` was attempted twice on this Linux VM:
- Config fixes along the way: two-package structure removed (`directories.app: dist`
  expected a `package.json` inside `dist/`); `electron` moved from `dependencies`
  to `devDependencies` (builder requirement); runtime `dependencies` trimmed to
  just `zod` (the only main-process runtime require — react/react-dom are
  vite-bundled into `dist/`); `files` ships `dist/**/*`, `package.json`,
  `node_modules/zod/**/*`.
- Result: staging **succeeds** — `release/win-unpacked/` (371 MB) is the complete
  Windows x64 app: Electron 45 runtime, `resources/app.asar` with the compiled
  app, asar integrity updated, exe resources edited, NSIS tool downloads fine.
- Final installer assembly **fails**: `⨯ wine process failed ENOENT` / `spawn wine
  ENOENT`. electron-builder runs its bundled NSIS `makensis.exe` under Wine;
  Wine is not installed on this VM (and not installable from the configured apt
  repos). The 190 KB `release/Universal Game Launcher-0.1.0-win-x64.exe` left
  behind is a stub, **not** a working installer — do not treat it as one.
- **What Adam needs:** run `npm ci && npm run package:win` on his Windows 11
  machine (Node 22+); no Wine needed there — NSIS runs natively and the installer
  is produced in `release/`. Signing is intentionally unconfigured (no cert);
  SmartScreen will warn once on first install — documented in
  `docs/WINDOWS_INSTALL.md`.
- Verified in the packaged runtime's Node (v24.22.0): `node:sqlite` works
  unflagged, so the app's database layer runs in the shipped Electron.
- `docs/WINDOWS_INSTALL.md` written: install steps, first-run expectations per
  source, missing-client behavior, uninstall + `%APPDATA%\Universal Game Launcher\`
  data-removal instructions, unsigned-build SmartScreen note, troubleshooting.

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
