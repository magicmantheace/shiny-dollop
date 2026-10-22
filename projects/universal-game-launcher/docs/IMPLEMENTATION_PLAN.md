# Execution roadmap for Muse

Status at handoff: **documentation prepared; application not yet implemented**. All unchecked items genuinely pending until tested.

**Instruction:** do not spend multiple sessions merely reorganizing plans. Implement working vertical slices with tests. Keep unrelated projects untouched. Prefer a feature demonstrable on a normal Windows PC over a large untested architecture.

## M0 — project scaffold and local app [NOT STARTED]
- [ ] Inspect workspace and read instructions/specs.
- [ ] Scaffold Electron/React/TypeScript in this project's `app/` folder only; pin supported tool versions and lockfile.
- [ ] Start a real native desktop window and show Library, Favorites, Recent, Settings navigation with real empty states.
- [ ] Add strict main/preload/renderer privilege boundary and validated IPC.
- [ ] Implement project-local build, tests, lint and typecheck scripts.
- [ ] Confirm `npm ci` + development start + production compile where supported.
**Completion gate:** runnable desktop app, not browser-only prototype.

## M1 — genuinely useful manual launcher [NOT STARTED]
- [ ] File picker to add an installed local Windows executable.
- [ ] Title editing and cover/icon fallback; duplicate detection.
- [ ] SQLite persisted game list + migrations; library cards and details page.
- [ ] Launch the user-selected executable safely, with path checking and actionable errors.
- [ ] Favorites, remove-from-library (non-destructive), search and sorting.
- [ ] A reliable tracked process session for manually launched programs, stop/end detection where possible.
- [ ] Save/reload data after closing and reopening app; unit/integration/Electron smoke tests.
**Completion gate:** add a real local game, launch it, see actual session, favorite it, restart and see all changes persisted. This is the FIRST functional demo.

## M2 — Steam integration [NOT STARTED]
- [ ] Steam presence discovery and local multi-library file parsing.
- [ ] Parse VDF libraryfolders and ACF manifests with fixture tests and malformed-input resilience.
- [ ] Import installed AppIDs/titles, preserve user edits after re-scan.
- [ ] Launch via validated Steam native URI with accurate launch-request state.
- [ ] Missing Steam / invalid AppID / removed install handling, source filter and status UI.
**Completion gate:** on Windows with Steam-installed games, rescan finds real games and a chosen game opens through Steam; test negative and offline cases.

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
