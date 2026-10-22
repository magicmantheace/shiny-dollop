# Universal Game Launcher — app

Real Electron + React + TypeScript desktop app. All source, tests, configs and the
lockfile live in this directory; nothing is installed at the workspace root.

**Status (2026-10-22):** M0 + M1 implemented and verified on Linux. Windows-only
behaviors (real `.exe` launch, installer) are implemented per spec and marked
unverified below.

## Toolchain (pinned)

| Tool | Version | Notes |
|---|---|---|
| Electron | 45.0.0 | main process Node 24 |
| React / React-DOM | 19.3.1 | renderer UI |
| Vite | 8.3.5 | renderer dev + build |
| TypeScript | 5.9.3 | strict, three project configs |
| zod | 4.6.7 | IPC payload validation |
| Vitest | 5.0.5 | unit + integration + security tests |
| electron-builder | 26.15.3 | Windows x64 config only (M6) |
| SQLite | node:sqlite (Node 24 built-in) | see decision below |

### SQLite decision (evidence, not preference)

The recommended baseline was better-sqlite3. I spiked both in this environment:

- `node:sqlite` works identically in system Node (vitest) **and** inside Electron 45
  (verified: in-memory round-trip in the real Electron runtime under xvfb).
- better-sqlite3 would need `electron-rebuild` for the Electron ABI, which then
  breaks the system-Node prebuilt that vitest uses — one `node_modules` cannot
  serve both runtimes without fragile ordering.

Using `node:sqlite` removes the entire native-module class of problems (install,
test, package) with a synchronous API sufficient for a local library database.
No native dependencies are installed at all.

## Scripts

| Command | What it does |
|---|---|
| `npm ci` | clean install from the lockfile |
| `npm run dev` | tsc watch (main/preload) + Vite + Electron against the dev server |
| `npm run build` | typecheck + production compile (renderer, main, preload) |
| `npm run lint` | eslint |
| `npm run typecheck` | tsc --noEmit on all three projects |
| `npm test` | vitest run (56 tests) |
| `npm run smoke` | production build + real Electron window under xvfb, expects SMOKE_OK |
| `npm run package:win` | electron-builder Windows x64 installer (configured, not yet run) |

## Architecture

- **Main (trusted):** `electron/main/` — window lifecycle, SQLite (`data/`), IPC
  handlers (`ipc/`, every payload validated with zod, errors sanitized), process
  launching (`launch/`, `shell:false`, structured argv, game looked up by UUID —
  the renderer never supplies a raw path), OS file picker (`files/`).
- **Preload (narrow):** `electron/preload/` — exposes only the typed
  `window.gameLauncher` API via `contextBridge`. No raw `ipcRenderer`, no Node.
- **Renderer (untrusted):** `src/` — Library, Favorites, Recently Played,
  Settings views; add/edit/remove game dialogs; search + sort. No `nodeIntegration`,
  `contextIsolation` on, strict CSP.
- **Shared:** `shared/` — types, IPC channel constants, zod schemas, and the
  pure launch-argument parser used by both main and renderer.

Window security: `contextIsolation: true`, `nodeIntegration: false`,
`sandbox: true`; navigation and `window.open` locked to app content; permission
requests denied by default; single-instance lock.

## Data

SQLite lives in the OS per-user app-data dir (`app.getPath('userData')/data/library.db`),
never in the repo. Migrations are versioned and idempotent (`schema_version` table).
Tables: `games`, `sessions`, `settings`, `scan_log`.

## Verified vs unverified (2026-10-22, Linux)

**Verified here:**
- `npm ci`, `npm run dev` wiring, `npm run build` (production compile), `npm run lint`,
  `npm run typecheck`, `npm test` (56/56), `npm run smoke` (real window under xvfb).
- M1 vertical slice end-to-end with a real spawned process: add executable →
  launch → observed 2010 ms session on natural exit → favorite → close/reopen →
  everything persisted (game, favorite, total playtime, last played, session).
- Crash recovery: interrupted sessions finalize at the last checkpoint (no invented time).
- AT-07 headless security checks: strict IPC schemas reject smuggled paths, spawn
  always `shell:false` with structured argv, hostile titles/args stay inert, IPC
  errors carry no stack traces.

**Implemented but unverified (needs Windows):**
- Launching a real Windows `.exe` (implemented per spec; exercised here only with
  Linux executables).
- OS file-picker `.exe` filter path (Windows-only branch).
- `electron-builder` Windows x64 installer build, install/uninstall flow.
- Packaged-app startup (asar, sandbox, CSP in packaged mode).

## Not yet built

M2 Steam, M3 Epic, M4 Battle.net integrations; cover art; export/import;
Windows installer (M6).
