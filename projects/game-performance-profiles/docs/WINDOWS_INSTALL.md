# Windows install & run — Game Performance Profiles

How to build and run this app on Windows 11, and what still needs real hardware to verify. Written 2026-10-23; the Linux build/smoke below it ran on the build VM, **not** on Windows.

## Prerequisites (Windows 11)

- Node.js 20+ (https://nodejs.org) — check with `node --version`
- Git for Windows
- Administrator rights (power-plan switches and some priority changes require elevation)
- No paid services, no network calls at runtime — the app is fully offline

## Build

```powershell
cd projects\game-performance-profiles\app
npm install
npm run build        # main process (dist\main) + renderer (dist\renderer)
```

Expected: `dist\main\main.js` and `dist\renderer\index.html` exist, no errors.

## Run (development)

```powershell
npm run smoke          # launches Electron against the built output
# or, for renderer-only iteration:
npm run dev            # Vite dev server on http://localhost:5174
npm run test:ui        # 87 hermetic renderer tests (mocked window.gpp)
```

`npm test` runs Worker A's backend suite (69 tests, mock OS layer).

## What needs real hardware (not yet verified)

The app has **never executed against real Windows APIs**. Everything below is
implemented-against-documented-APIs plus a mock; the first Windows run must
confirm each line, in this order:

1. **Capability probing** — the backend probes game-mode, power-plan, process-priority and fullscreen-optimizations support at startup. On the Windows box, check the Profiles view shows "supported" badges (not "unknown").
2. **Game Mode toggle** — writes the game-mode registry DWORD. Preview should show the real current value in the "from" column (on Linux/mock it is synthetic).
3. **Power plan switch** — `powercfg /getactivescheme` → `/setactive <GUID>`. Needs admin. Confirm the previous plan is recorded in the journal so rollback restores it.
4. **Process priority** — needs a real running game process; confirm the denylist refuses protected processes (System, Registry, smss.exe, csrss.exe, …) and that realtime can never be selected.
5. **Fullscreen optimizations** — per-exe registry value under `GameConfigStore\Children`; confirm the exe path validation accepts the real path.
6. **Snapshots** — CPU % / memory MB come from the real OS on Windows; confirm the numbers look sane and the "approximate — point-in-time estimate, not a benchmark" note is present.
7. **Rollback / restore-all after a real activation** — the money test: activate a profile, confirm the journal's before/after values match reality, roll back, confirm the OS is back where it started.

## Safety notes for the Windows run

- Start with the seeded **"Balanced Gaming"** profile (game-mode on) — the lowest-risk change.
- Power-plan changes need an elevated terminal/session; without admin the backend must report the capability as unsupported (verify the UI blocks activation with the reason).
- Nothing in the app overclocks, patches drivers, stops security services, or touches anti-cheat — and the UI offers no such controls.
- Keep a `powercfg /list` printout before the first activation so you can manually restore the original plan if anything goes sideways.

## Troubleshooting

- **Blank window / "window.gpp is not available"** — the renderer was opened outside Electron (e.g. plain `vite dev` without the shell) or the preload failed. Run through `npm run smoke` / the packaged main entry.
- **`npm run build` fails on `build:main`** — Worker A's esbuild step; check `scripts/build-main.mjs` output, not the renderer.
- **Tests fail on `exactOptionalPropertyTypes`** — renderer strictness lives in `tsconfig.renderer.json`; the backend's stricter `tsconfig.json` intentionally excludes `src/` and `tests-ui/`.
