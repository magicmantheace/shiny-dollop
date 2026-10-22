# Architecture and engineering constraints

## Baseline technology

**Recommended:** Electron + React + TypeScript + Vite with strict TypeScript, Node LTS, maintained dependencies, pinned lockfile. The Electron main process handles native OS actions, scanners, persistence and process observation; the renderer is UI only. Use a Windows x64 installer builder such as electron-builder. If changing stack, record evidence and preserve every product requirement.

**Build scope:** All package manifests, lockfiles, application source, test source, config and packaging scripts live in `projects/universal-game-launcher/app/` (or project directory if tooling requires; never workspace root).

## Process boundary

### Electron main (trusted)
- Securely resolve vendor install locations, Windows registry reads (read-only where appropriate) and local manifests; no uncontrolled walking of entire drives.
- Game catalog persistence (SQLite, with migrations) and bounded cover cache.
- OS file picker and validated manual target/working-directory validation.
- Launch manual game through a direct OS spawn/process API using structured `argv` and `shell: false`; vendor launch through verified URI and/or official executable with tightly restricted URI scheme; do not pass arbitrary external URLs.
- Session watcher at modest interval or process exit handles; minimize background work.
- IPC request schema validation (zod/equivalent); errors sanitized.

### Preload (narrow API)
Expose explicit typed operations:
`library.list`, `library.addManual`, `library.update`, `library.remove`, `library.setFavorite`, `library.setHidden`, `sources.scan`, `sources.status`, `games.launch`, `sessions.list`, `sessions.clear`, `settings.get/update`, `files.chooseExecutable`, `files.chooseArtwork`.

Do not expose Node, arbitrary file read/write, raw `ipcRenderer`, unrestricted URLs, shell commands or arbitrary process spawning.

### Renderer (untrusted)
- Screens and accessible components, search/filter/sort, caching and list virtualization when needed.
- Use only typed preload APIs.
- No `nodeIntegration`, no remote content inside privileged window and no credential handling.

## Data model suggestion

`games`: internal UUID, source (`manual|steam|epic|battlenet`), external source ID, display title, install path/URI metadata (validated at use), source-specific launch capability, library state (visible/hidden/missing), discovered timestamps, cover override, favorite, tag metadata, added origin.

`installations`: source-specific install identity, canonical path, last verified timestamp, discovery method, present/missing.

`sessions`: UUID, game UUID, start/end UTC timestamps, measured duration ms when supported, state (`running|completed|interrupted|manual`), tracking method/confidence, optional notes, last update checkpoint.

`settings`: source enable flags, authorized scan locations, appearance, minimize preference, tracking toggle, source settings.

`scan_log`: source, time, result status, counts, sanitized error summary.

Use stable uniqueness per `(source,external_id,installation_identity)` when possible. Store mutable user edits separately from scanner-derived source metadata so re-scan never erases favorites/custom titles.

## Scanner adapter contract

Each scanner must implement equivalent of:
- `probe(): SourceAvailability` (installed/unavailable/limited + why)
- `scan(config): DiscoveredGame[]` (side-effect-free local reads; cancellable; bounded)
- `validateLaunch(game): LaunchCapability` (`direct|native-uri|open-client|unavailable`, with reason)
- `launch(game): LaunchAttempt` (only after explicit user click, capability validation)
- diagnostic parse/test fixtures and schema version.

**Steam:** detect installation location via known Windows locations and read-only registry keys if needed; parse VDF `libraryfolders.vdf`, `appmanifest_*.acf`, handle nested VDF, escaped strings, multiple drives, malformed and missing files; native URI `steam://rungameid/<decimal-appid>` only after validating decimal ID. Avoid public Web APIs requiring keys.

**Epic:** inspect locally installed manifest metadata from candidate known Windows locations (implementation must verify their use); use JSON/whitelisted keys, reject path traversal and invalid fields; only use native game deep links after experimentally/officially validated format, otherwise `open-client` fallback. Offline import must not require Epic login via our app.

**Battle.net:** rely on local nonsecret metadata if present and known installed locations with user-approved specific folders; verify any nonpublic manifest parsing and direct launch approach, record confidence. For ambiguous installations, don't invent games or silently scan drives. When direct game launch is unsupported, open installed Battle.net app and tell user to select the title.

**Manual:** OS file picker for `.exe` or Windows shortcut resolution if implemented safely. Validate absolute canonical file target and working directory. Allow custom args as an array or escaped parse with tests. Avoid shell metacharacter surprises. Warn clearly that manual executables should only be added when trusted by owner.

## Launch lifecycle

1. User presses Play or Open Launcher.
2. Main looks up the **stored game by UUID**, never accepts an arbitrary executable command from renderer.
3. Revalidate path/source ID/protocol and classify capability.
4. Execute via secure native API.
5. Report `requested`, `process started` (if known) or error. Never return `running` based solely on a URI handoff.
6. Track session **only** when process identity is actually observed/validated. Store interruption markers and end reason.
7. A crash recovery must conservatively finalize interrupted sessions without inventing time between last checkpoint and restart.

Avoid starting duplicate sessions for repeated rapid Play clicks. Never terminate unrelated processes automatically.

## Security

- Electron `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true` where compatible; strict CSP and navigation/window-open restrictions.
- `shell.openExternal` only for hardcoded/validated scheme + host combinations or whitelisted vendor protocols with strictly validated identifiers.
- No unchecked use of `cmd.exe`, PowerShell, `eval`, string-built command lines, remote HTML, or `exec(...shell...)`.
- Reject untrusted shortcut targets/arguments/paths where unsafe; local manifest contents are data, not trusted commands.
- Scanners may read installed-program metadata only; never write vendor manifests, user game data, installation folders or system registry.
- Store game library locally under per-user OS app data, not in source repository. No accounts, web backend, ads or telemetry. Ask before external artwork fetches.
- Mark custom cover URLs/files as user-owned inputs; never execute downloaded assets.
- Non-admin normal operation; don't interfere with vendor anti-cheat and DRM.

## Performance and reliability

- Startup must not block on scanning; show saved library then asynchronously scan when requested/configured.
- Allow cancellation, bounded filesystem I/O and errors per source; fail isolated scanner rather than whole app.
- Prevent CPU-heavy file hashing at startup; fingerprint manifests cheaply.
- Track vendor missing/uninstalled separately from user-removed entries; source errors must not erase existing library.
- Database transactions and migrations; test Windows path normalization and long/unicode paths.
- Avoid per-second polling when not needed. Suspend/watchers off when tracking disabled.

## Suggested project tree

```text
projects/universal-game-launcher/
  app/
    package.json
    <lockfile>
    electron/
      main/
        index.ts
        ipc/
        data/
        sources/{manual,steam,epic,battlenet}/
        launch/
        sessions/
      preload/
    src/
      pages/
      components/
      features/
      state/
      styles/
    tests/{unit,integration,e2e}/
    assets/
    README.md
  docs/
  AGENTS.md
  README.md
```

## Packaging

Project-local commands with exact documentation, for example `npm ci`, `npm run dev`, `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`, `npm run package:win`. Windows x64 installer output must be ignored by git. Run genuine Windows installer validation if environment is Windows; otherwise clearly report which parts are unverified. Do not publish/sign binaries without owner approval or access to an approved signing workflow.
