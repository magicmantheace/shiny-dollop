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

## AT-04 Battle.net scan and launch / fallback

1. On a computer with Battle.net, discover verifiably installed games using validated metadata or user-provided install paths.
2. Don't invent unsupported product IDs or tokens.
3. If verified per-game launching is available, test it. Otherwise Open Battle.net client with correctly labeled action and verify it opens.
4. Absent, moved or unknown installation results in truthful unavailable/manual-add option; other sources still work.

## AT-05 Library usability

- [ ] Filter by favorite/source/installed status; sort by name/last played/tracked duration.
- [ ] Search case-insensitively; keyboard navigable controls, focus indicators, screen-reader labels.
- [ ] Theme persistence, missing artwork graceful fallback, custom cover survives re-scan.
- [ ] 500 items renders and filters without frozen UI or unreasonable idle resource use.
- [ ] Manual exclusions are preserved; false uninstall detection does not erase history.
- [ ] No mandatory network or account of the app; installed titles remain visible when disconnected.

## AT-06 Playtime accuracy and crash behavior

- [ ] Actual manual launched process exits normally: observed end and duration plausible.
- [ ] Manual process exits unexpectedly: recovery marks interrupted and uses last known observation conservatively.
- [ ] App crashes while manual game running: no multi-day phantom session when app reopened.
- [ ] Vendor URI handoff with no correlated process does **not** accumulate invented playtime.
- [ ] Tracking disabled: no sessions collected until enabled.
- [ ] Clear history affects only app records, not installed games.
- [ ] Clock/timezone changes don't yield negative/absurd durations.

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

- [ ] Missing vendor client and malformed manifest errors are source-local.
- [ ] Scan can be cancelled and re-run without duplicates.
- [ ] Selected scan folders obey user intent; no default full-disk recursion.
- [ ] Errors are actionable; no fabricated green success.
- [ ] Library persists across restarts, migrations are idempotent, and corrupted DB has recoverable error path.

## Evidence Muse must produce

For each milestone: date, OS/tool versions, commit ref, command executed, pass/fail summary, one or more **real** workflow observations (e.g. a game spawned and exited), known gaps and next step. Automated unit/integration tests use fixture manifests and stubbed process-launch operations (do NOT start arbitrary real executables inside CI). Store-client runtime tests require a Windows environment with the respective clients and games installed and must remain clearly labeled pending until performed.

## Release gate

MVP accepted only when **real manual launch, Steam integration, best-effort Epic and Battle.net support with truthful fallbacks, favorites/search/persistence, honest sessions, Windows install path and critical security tests** all meet these criteria. An app window with demo game cards is not an MVP.
