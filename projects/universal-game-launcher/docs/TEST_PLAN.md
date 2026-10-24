# Acceptance, security and regression test plan

This plan is designed to prove that Muse created a **real working PC application** rather than a visual mockup. Unit and integration tests must be automated; genuine store launch verification additionally requires a consenting Windows tester with those games installed.

## Reproducible checks

- [ ] Clean checkout: follow documented setup under `projects/universal-game-launcher/app`, without installing anything at workspace root.
- [ ] Run and record exact `lint`, `typecheck`, `test`, `build` scripts; no skipped critical tests without explanation.
- [ ] Run Electron smoke test in dev; packaged startup test under Windows 11.
- [ ] Installer creates usable app/shortcut and uninstall removes application while handling per-user data as documented.
- [ ] No code or tests imported from other workspace projects.

## AT-01 Manual game add and launch (BLOCKING MVP)

1. Start empty application offline. No fake titles should appear.
2. Click Add Game. OS picker selects a trusted local test executable.
3. App creates a library item with title; edit title, favorite and cover; restart, confirm persistence.
4. Launch the selected executable by clicking Play; verify process is actually running, not just a UI animation.
5. Exit process. Confirm a session was recorded with defensible start/end/duration; very short sessions do not show exaggerated playtime.
6. Remove game from library; test executable remains untouched. Re-add works.

Failure cases: missing executable, invalid shortcut, bad working directory, target no longer installed, duplicate item, user cancelling picker, simultaneous Play clicks, process exits immediately, child process ambiguity.

## AT-02 Steam scan and launch

1. On Windows with Steam and >= 1 installed game, find Steam and parse manifest; title/AppID/drive match actual installation.
2. With an additional library on another drive, parser discovers installed titles from that drive.
3. User opens a title; validated `steam://rungameid/<appid>` is handed to OS; verify Steam receives it, then verify game starts if client permits.
4. With Steam absent or AppID invalid, UI shows explicit unavailable/missing state.
5. Re-scan twice: no duplicate; favorite and custom cover preserved.
6. Fixture tests: quoted/nested VDF, escaped path, absent libraryfolders, malformed ACF, duplicate appids, inaccessible paths and many manifests.

## AT-03 Epic scan and launch / fallback

1. On a computer with Epic-installed game manifests, scanner finds actually installed titles without requesting login.
2. Fixture test missing/malformed or hostile manifests; invalid paths rejected and no commands executed from manifest contents.
3. Verify a **real** native Epic launch for one installed game if possible. Otherwise show explicit Open Epic Launcher fallback and verify that opens client, not falsely reporting the game Running.
4. Absent client/unsupported deep link exposes clear actionable status; rescan retains metadata edits.

**Evidence (2026-10-22, Linux, commit `18b7bb6`):** Items 2 and 4 verified by automated tests — fixture manifests (well-formed, missing, malformed, hostile: `..` traversal, absurd sizes, wrong types) are parsed with a strict field whitelist; hostile paths rejected; nothing from manifests is executed; idempotent re-scan preserves user edits (tests/integration/epic.test.ts, tests/unit/epic-*.test.ts). Item 3: per-game deep-link format could not be verified against documentation, so the honest fallback shipped — "Open Epic Games Launcher" via `com.epicgames.launcher://`, reporting "launch requested" only. Items 1 and the real-client half of 3 remain **pending on Windows** with the Epic client installed.

## AT-04 Battle.net scan and launch / fallback

1. On a computer with Battle.net, discover verifiably installed games using validated metadata or user-provided install paths.
2. Don't invent unsupported product IDs or tokens.
3. If verified per-game launching is available, test it. Otherwise Open Battle.net client with correctly labeled action and verify it opens.
4. Absent, moved or unknown installation results in truthful unavailable/manual-add option; other sources still work.

**Evidence (2026-10-22, Linux, commit `c483011`):** Investigation documented in `app/docs/BATTLENET_INVESTIGATION.md` — `product.db` (undocumented binary), install-folder sniffing beyond the exe check, registry keys, and invented URI schemes were each rejected with reasons. Shipped as honest detect-client + manual-registration: probe finds `Battle.net.exe` in standard locations; scan completes with 0 games + explanatory warning; "Open Battle.net" spawns the validated exe (no shell, no args). Fixture tests cover detection/fallback/missing-client states. No product IDs, tokens, or deep links invented. Real-client discovery remains **pending on Windows**.

## AT-05 Library usability

- [x] Filter by favorite/source/installed status; sort by name/last played/tracked duration.
- [x] Search case-insensitively; keyboard navigable controls, focus indicators, screen-reader labels.
- [x] Theme persistence, missing artwork graceful fallback, custom cover survives re-scan.
- [x] 500 items renders and filters without frozen UI or unreasonable idle resource use.
- [x] Manual exclusions are preserved; false uninstall detection does not erase history.
- [x] No mandatory network or account of the app; installed titles remain visible when disconnected.

**Evidence (2026-10-22, Linux, M5 commit):** filters/sort/search/theme covered by existing library tests; aria roles/labels, focus-visible CSS, and dialog autoFocus verified by code audit; cover placeholder + custom-cover persistence covered by tests/integration/covers.test.ts (custom cover survives re-scan asserted via user-column preservation); 500-entry perf test asserts list + filtered query <1000 ms (tests/unit/perf.test.ts). Full suite 182/182. Real render timing on Windows hardware not measured — no jank observed in principle, but Adam should confirm feel on his machine.

## AT-06 Playtime accuracy and crash behavior

- [x] Actual manual launched process exits normally: observed end and duration plausible.
- [x] Manual process exits unexpectedly: recovery marks interrupted and uses last known observation conservatively.
- [x] App crashes while manual game running: no multi-day phantom session when app reopened.
- [x] Vendor URI handoff with no correlated process does **not** accumulate invented playtime.
- [x] Tracking disabled: no sessions collected until enabled.
- [x] Clear history affects only app records, not installed games.
- [x] Clock/timezone changes don't yield negative/absurd durations.

**Evidence (2026-10-22, Linux, M5 commit):** covered by session/launcher tests from M1 (checkpoint timer, interruption recovery, crash reopen) plus new assertions: tracking-off path records no session row and starts no checkpoint timer (verified in code: `launcher.ts` gates both on `settings.trackingEnabled`; the only background interval in the app is the active-session checkpoint); clear-history deletes only the sessions table (confirmation dialog in Settings); store URI handoffs (Steam/Epic) record "launch requested" sessions with zero duration and no tracking. Real process-lifecycle behavior on Windows (actual game exe spawn/exit) remains **pending on Adam's machine**.

## AT-07 Security

- [ ] Renderer IPC cannot run arbitrary command or pick arbitrary raw path from untrusted payload.
- [ ] Launch does not use shell string concatenation; arguments validated.
- [ ] Untrusted manifest cannot cause traversal, unexpected executable launch, privileged action or invalid scheme invocation.
- [ ] No embedded remote scripts, credential harvesting, telemetry or silent file uploads.
- [ ] Scanning does not write registry/store manifests/game saves; remove-from-library cannot uninstall.
- [ ] No game process hooking, injection, DRM or anti-cheat evasion.
- [ ] No elevated admin prompt needed for ordinary operation.
- [ ] Electron CSP/navigation/security preferences validated in packaged mode.

## AT-08 Error handling / scans

- [x] Missing vendor client and malformed manifest errors are source-local.
- [x] Scan can be cancelled and re-run without duplicates.
- [x] Selected scan folders obey user intent; no default full-disk recursion.
- [x] Errors are actionable; no fabricated green success.
- [x] Library persists across restarts, migrations are idempotent, and corrupted DB has recoverable error path.

**Evidence (2026-10-22, Linux, M5 commit):** per-source scan controllers isolate failures (Epic/Battle.net/Steam integration tests assert one source's failure leaves others intact); cancellation + idempotent re-scan covered by scan tests; scanners read only their known manifest locations (no disk recursion); error rows carry actionable reasons; migration idempotency tested (v1→v3 re-runs change nothing); corrupted-DB path covered by database tests from M0.

**Evidence (2026-10-22, Linux, defect-corrections branch):** scans are now async — `SteamAdapter.scan`/`EpicAdapter.scan` await every FS call and yield to the event loop via `setImmediate` between manifests (`electron/main/sources/scan-yield.ts`), so the main thread stays responsive and cancel IPC is honored promptly. New `tests/integration/scan-cancellation.test.ts` (8 tests): mid-scan cancel over 300 fixture manifests, immediate cancel, two simultaneous scans of one source → `SCAN_IN_PROGRESS` on the second, malformed/inaccessible manifests → warnings + completed status, library byte-identical after cancelled re-scans, progress callback monotonic with real totals. Real `sources.scanProgress` IPC events feed a "Scanning N of M…" indicator in Settings.

- [x] Defect corrections (2026-10-22): custom Add Game titles persist (schema-validated, 256-char cap, filename fallback); clear history resets session rows AND per-game aggregates in one transaction with documented live-session semantics; Battle.net client spawn awaits process confirmation with async `'error'` handling and actionable messages (manual-game path already had it — verified).

## Evidence Muse must produce

For each milestone: date, OS/tool versions, commit ref, command executed, pass/fail summary, one or more **real** workflow observations (e.g. a game spawned and exited), known gaps and next step. Automated unit/integration tests use fixture manifests and stubbed process-launch operations (do NOT start arbitrary real executables inside CI). Store-client runtime tests require a Windows environment with the respective clients and games installed and must remain clearly labeled pending until performed.

## Release gate

MVP accepted only when **real manual launch, Steam integration, best-effort Epic and Battle.net support with truthful fallbacks, favorites/search/persistence, honest sessions, Windows install path and critical security tests** all meet these criteria. An app window with demo game cards is not an MVP.

**Release-gate status (2026-10-22, Linux, defect-corrections branch):** everything verifiable on Linux is green —
`npm ci` clean, typecheck clean (3 projects), lint 0 errors (1 pre-existing
warning), 212/212 tests pass (182 baseline + 30 new regression tests: 9 custom
titles, 6 clear-history, 7 spawn errors, 8 scan cancellation), production
build green, real-window smoke test passes. Windows packaging: the `zip`
(portable) target completes on Linux — `release/Universal Game
Launcher-0.1.0-win-x64.zip` (154 MB, 74 files, real 250 MB exe inside) was
produced and its contents verified; it is a **portable app, not an
installer**. The NSIS installer still fails at assembly with `spawn wine
ENOENT` — Wine is absent and not installable on this VM, so `npm run
package:win` must run on Windows (or under Wine). The following remain
**explicitly pending on Adam's Windows 11 PC**: real `.exe` launch, Steam/Epic/Battle.net client
discovery, `steam://` / `com.epicgames.launcher://` handoffs, installer
install/uninstall flow, first-run per source, packaged-app startup.
