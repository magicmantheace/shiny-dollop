# Implementation status — Windows Game Performance Profiles

- **Overall status:** IN PROGRESS — backend + OS layer + engine implemented and verified on Linux (Worker A); renderer MVP complete with 87/87 UI tests green (Worker B). Full-stack smoke passed on Linux; real Windows execution NOT verified (needs Adam's Windows box)
- **Priority:** 8/17
- **Branch:** `game-performance-profiles/mvp` (base: origin/main @ d4441fd)
- **Source/code implemented:** `projects/game-performance-profiles/app/` — Electron 45 + TypeScript strict + Vite, `node:sqlite`, zod IPC, typed preload, React 19 renderer
- **Build validated:** Yes (Linux) — `npm run build` produces dist/main + dist/renderer
- **Automated tests executed:** Yes — 100/100 backend vitest tests pass (MockOsLayer, synthetic fixtures) + 87/87 renderer UI tests pass (`app/tests-ui/`, mocked `window.gpp`, jsdom)

## Codex fix cycle 1 — 2026-10-24

- Wildcard process names rejected in shared backend validation (`processImageNameProblem`): `Get-Process -Name` expands `*`/`?`/`[...]`/backtick patterns, so `explor*` could have matched protected `explorer.exe` past the exact-match denylist. Enforced in preview/activation validation, MockOsLayer, and WindowsOsLayer (read/apply/restore); the denylist is also re-checked against every resolved process before any mutation.
- Windows process priority is now single-instance by identity: resolution returns id|name|priority per instance, the first instance is the one read and later set/restored by process id — other instances' original priorities are never touched.
- Out-of-order rollback over a shared setting rebases instead of clobbering: retiring an older journal entry while a newer entry for the same setting is live splices it out of the chain (successor inherits its `before`, OS untouched), so restore-all still recovers the original state.
- Reverted the unrelated `projects/game-save-manager/docs/MUSE_HANDOFF.md` edit that had landed on this branch (file now matches main exactly).
- Regression tests added for all of the above (each verified failing pre-fix); backend 69 → 100 tests, typecheck + lint + build:main clean. Windows-only execution still NOT verified (needs Adam's Windows box).
- **End-to-end MVP verified:** Partially — backend workflow (seed → preview → approve → apply → rollback → restore-all) verified against the mock on Linux; full stack (main → preload → React UI → IPC) smoke-tested in a real window under xvfb; real Windows execution NOT verified (needs Adam's Windows box)
- **Owner review:** Pending (coordinator reconciles and pushes; nothing pushed)

## Codex fix cycle 2 — 2026-10-24

- Activation, rollback and restore-all are now serialized through one shared mutation lock in the IPC handlers (`createHandlers`): the three operations queue in invocation order, so OS mutations and journal inserts can no longer interleave (e.g. a second activation started after closing the activation dialog mid-run) and journal order always matches OS mutation order. The queue never wedges on a failed operation, and activation re-reads its profile inside the lock.
- Restore failures now preserve dependent rollback history: in `restoreAll` and `rollbackProfile`, once restoring a newer entry for a setting fails, older entries for the same setting are skipped and left un-rolled-back for a later retry instead of being restored/retired out from under the failed entry's baseline — so a second restore-all still recovers the original state (Game Mode scenario). Entries for independent settings still restore in the same run, and each skip is reported in `errors`.
- Regression tests added for both (each verified failing pre-fix): backend 100 → 103 tests (UI suite unchanged at 87/87), typecheck (backend + renderer) + lint + build clean. Windows-only execution still NOT verified (needs Adam's Windows box).

## First milestone

Define one low-risk profile, preview proposed changes, activate with approval, and fully restore prior settings.

**Status:** Backend slice complete. The built-in "Balanced Gaming" profile (game-mode on + power-plan placeholder) is seeded on first run; preview/approve/apply/rollback/restore-all/snapshots all work end-to-end against the mock OS layer. Renderer slice complete (Worker B): full React UI against the live `window.gpp` contract, 87/87 UI tests green, strict typecheck clean, and the full stack smoke-tested in a real window under xvfb.

## Worker B (renderer) deliverables — 2026-10-23

- `app/src/gpp.ts` — typed bridge wrapper; missing bridge → one actionable error; `{ error }` responses → thrown Errors.
- `app/src/validation.ts` — pure client-side validation (profile names, GUID shape, exe names/paths, priority allow-list; realtime never offered).
- `app/src/components/` — `ProfilesList`, `ProfileEditor` (per-kind forms), `PreviewModal` (preview table, approval-checkbox gate, unsupported-block, progress events, result reporting), `JournalView`, `SnapshotsView` (labeled snapshots, two-snapshot delta compare, "approximate — point-in-time estimate, not a benchmark" on every snapshot), `CapabilityBadge`.
- `app/src/App.tsx` — tab shell, "Restore all changes" with confirm, per-profile rollback confirm, result notices naming what was restored.
- `app/src/main.tsx` + `app/index.html` — replaced Worker A's `src/main.ts` renderer stub with the real UI (per the stub's own "Worker B replaces this" note).
- `app/tests-ui/` — 87 hermetic tests (vitest + jsdom, mocked `window.gpp`); `app/vitest.ui.config.ts` (`globals: true` so RTL cleanup runs); `app/tsconfig.renderer.json` (strict, clean).
- Shared `app/package.json`: added react/react-dom, testing deps, and the `test:ui` script — Worker A's scripts untouched.

## Worker A (backend) deliverables — 2026-10-23

- `app/shared/gpp-types.ts` — stable IPC contract (Worker B builds against this)
- `app/electron/main/os-layer/` — `OsLayer` interface, `MockOsLayer` (failure injection), `WindowsOsLayer` (documented APIs only; compiles everywhere, executes on win32 only)
- `app/electron/main/engine/` — preview, activate (auto-rollback on failure), rollback, restoreAll, snapshots
- `app/electron/main/store/database.ts` — `node:sqlite`, explicit BEGIN/COMMIT/ROLLBACK
- `app/electron/main/ipc/` — zod schemas + exactly the 12 `gpp:*` channels; `approved === true` gate on activate
- `app/electron/preload.ts` — typed `window.gpp`; `app/src/gpp-api.d.ts` re-exports types for Worker B
- `app/tests/` — 69 tests, all passing

## Cross-worker notes (shared worktree, 2026-10-23 ~20:47 UTC, updated ~21:10 UTC)

- Renderer build finished by Worker B: `app/src/` (React + `main.tsx`, components, `tests-ui/`) is complete — 87/87 UI tests green, strict typecheck (`tsconfig.renderer.json`) clean, `vite build` succeeds. Worker A's stub `src/main.ts` was removed and `index.html` now loads `/src/main.tsx`, per the stub's own replacement note.
- Worker B's `src/gpp.ts` imports the contract directly from `../shared/gpp-types` — the Worker A contract held with no changes needed. The preload method names match the wrapper 1:1 (verified by reading `electron/preload.ts`).
- Shared configs adjusted cooperatively, no cross-ownership edits:
  - `vite.config.ts`: `@vitejs/plugin-react` restored + dep installed.
  - `tsconfig.json`: scoped to Worker A files (`electron`, `shared`, `tests`, `scripts`, `src/gpp-api.d.ts`, configs). Worker B's strictness is enforced separately via `tsconfig.renderer.json` (clean).
  - `app/package.json`: Worker B added react/react-dom, testing deps, and the `test:ui` script; Worker A's scripts untouched.
  - `app/index.html`: owned by Worker B; now loads the real React entry.
- `npm run build` + `npm run smoke` verified against Worker B's real React renderer: full stack (main → preload → React UI → IPC) loads in a real window under xvfb.

## Verification record (all on Linux, this VM)

| Gate | Command | Result |
|---|---|---|
| typecheck | `npm run typecheck` | clean |
| lint | `npm run lint` | clean (scoped to Worker A files; Worker B scaffold excluded, untouched) |
| tests | `npx vitest run` | 69/69 pass |
| tests (renderer) | `npx vitest run --config vitest.ui.config.ts` | 87/87 pass (jsdom, mocked `window.gpp`) |
| typecheck (renderer) | `npx tsc --noEmit -p tsconfig.renderer.json` | clean (strict) |
| build | `npm run build` | dist/main + dist/renderer produced |
| smoke | `npm run smoke` (xvfb, --no-sandbox as root) | real window opened, renderer loaded, seed ran, exit 0 |

## Implemented but UNVERIFIED (needs Windows)

- `WindowsOsLayer` real paths: `reg.exe` game-mode DWORD, `powercfg` get/setactivescheme, `tasklist` + PowerShell `PriorityClass` for process priority, per-game `GameConfigStore\Children` values. Code compiles; capability probing reports unsupported off-Windows and the layer refuses to execute there. **Never claimed working — needs Adam's Windows box.**
- NSIS/installer packaging: not attempted (out of Worker A scope).

## Next action

Both slices are built on this branch. Coordinator reconciles, runs both suites once more, and arranges the Windows 11 end-to-end run (see `docs/WINDOWS_INSTALL.md`) before any MVP claim; PR left unmerged for review per project rules.

## Deferred (not in this milestone)

Per-game auto-detection, telemetry charts, scheduled profiles.

## Acceptance notes

- Commits: `game-performance-profiles: backend ...` (Worker A) and `game-performance-profiles: renderer/docs ...` (Worker B) on `game-performance-profiles/mvp`, NOT pushed.
- No real OS settings were changed at any point: every test and the smoke run used MockOsLayer / synthetic state.
- Denylist enforced in both layers: System, Registry, smss.exe, csrss.exe, wininit.exe, services.exe, lsass.exe, svchost.exe, explorer.exe, dwm.exe, etc. Realtime priority can never be set (not representable in the allowed type).
