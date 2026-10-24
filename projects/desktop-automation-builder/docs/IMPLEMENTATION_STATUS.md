# Implementation status — Desktop Automation Builder

- **Overall status:** MVP FUNCTIONAL / REVIEW READY (2026-10-23)
- **Priority:** 12/17
- **Source/code implemented:** Yes — `app/` (Electron 45 + React 19 + TS strict + Vite, `node:sqlite`, zod-validated IPC)
- **Build validated:** Yes — `npm run build` green, `npm run smoke` prints SMOKE_OK (packaged main under Xvfb, Linux VM)
- **Automated tests executed:** Yes — **44/44 pass** (29 backend + 15 renderer), verified independently by the coordinator on the final pushed tree
- **End-to-end MVP verified:** Yes, at the engine/IPC level with real filesystem fixtures: build file-copy workflow → dry-run preview (zero writes) → approval gate (`awaiting-approval`, no side effects) → run → per-step durable log → mid-run failure persists partial log → retry resumes from the failed step only. Renderer flow covered by 15 hermetic tests including approval-gate ordering (preview before start, `runsStart(id, true)` only after the checkbox).
- **Owner review:** Pending (PR not yet created — parent creates it; left unmerged)

## MVP walkthrough evidence (2026-10-23, Linux VM, Node 24)

- `tests/backend/runs.test.ts`: dry-run performs ZERO filesystem writes and returns plain-language descriptions; `runsStart(approved=false)` creates an `awaiting-approval` run with no side effects; mid-run failure persists a partial log and retry resumes from the failed step only; cancel mid-run → `cancelled` plus a persisted partial log.
- `tests/backend/sandbox.test.ts`: `../evil` and absolute-outside paths rejected with `PATH_OUTSIDE_SANDBOX`.
- `tests/backend/scripts.test.ts`: unapproved scriptId blocked; move-to-trash lands in `.dab-trash/<ts>-<uuid>-<name>` and is fully recoverable — files are never deleted outright.
- `tests/backend/workflows.test.ts` + `ipc.test.ts`: version bumps archive snapshots; export envelope `formatVersion: '1.0.0'`; import rejects major ≠ 1 (`IMPORT_VERSION_UNSUPPORTED`) and bad shapes (`IMPORT_INVALID`); imported workflows never auto-run; channel map asserted 1:1 with `DAB_IPC_CHANNELS`.

## Unfinished / not in MVP (never claimed)

- No triggers/conditions (scheduled or event-based runs), no network steps, no node-graph editor (step-list only), no auto-restart of interrupted runs.
- Windows 11 click-through, real script spawning on Windows (kill uses direct child kill there instead of POSIX process groups), and NSIS packaging are **unverified** — no Wine on this VM. No code signing.
- `APPROVAL_REQUIRED` exists as an executor guard code; per the contract, `runsStart(id, false)` returns an `awaiting-approval` run instead of throwing, so no public path throws it in this MVP.

## History

- **Overall status (intake):** PLANNED (documentation setup only)
- **Priority:** 12/17
- **Source/code implemented:** None as part of project intake
- **Build validated:** No
- **Automated tests executed:** No
- **End-to-end MVP verified:** No
- **Owner review:** Pending

## First milestone

Build a simple non-destructive file-copy workflow, preview its actions, approve, run, inspect log, and retry safely.

## Next action

Have Muse read `AGENTS.md`, `docs/PRODUCT_SPEC.md` and `docs/MUSE_HANDOFF.md`, implement and validate the first vertical slice on a project-scoped branch.

## Acceptance notes

Record actual commits, tests, blockers and PR links here when implementation begins. Do not infer success from the existence of this planning document.

## 2026-10-23 — Backend MVP (Worker A)

- **Backend implemented and verified on Linux (Node 24, Electron 45):** SQLite store (`node:sqlite`, explicit transactions) with workflows / workflow_versions / approved_scripts / runs / run_steps; sandboxed executor (path-escape rejection, dry-run preview with zero writes, approval gate, per-step durable logs, cancel with process-group kill, retry-from-failed-step); export/import with format-version checks; all 17 IPC channels zod-validated in main; preload exposes flat `window.dab` 1:1 with `DAB_IPC_CHANNELS`.
- **Verification:** `npm test` — 44/44 green (29 backend + 15 renderer); `npm run typecheck`, `npm run lint`, `npm run build` clean; `npm run smoke` prints SMOKE_OK (packaged main under Xvfb).
- **Unverified:** real Windows execution (script spawning uses POSIX process groups; Windows uses direct child kill), NSIS packaging.

## 2026-10-24 — Codex review fixes (PR #16, head 265ab56)

Five P1 findings from the Codex review, each verified against the code before fixing:

- **Renderer path:** main loaded `dist/electron/renderer/index.html`; Vite writes `dist/renderer`. New `electron/main/paths.ts` helpers (`rendererIndexPath` = two levels up, `preloadScriptPath`) used by `main.ts`, unit-tested.
- **Sandboxed preload:** preload imported `./channels.js`, which a sandboxed preload cannot `require`. The channel map is now inlined in `preload.ts` (pinned to `DAB_IPC_CHANNELS` by test); the compiled `dist/electron/preload/preload.js` requires only `electron`. `channels.ts` remains for main-process registration.
- **Sandbox link traversal:** `resolveInSandbox` was lexical only. New `resolveInSandboxReal` realpath-validates the target / nearest existing ancestor before (and after creating) mutations in file-copy, move-to-trash, and folder-create; symlink escapes fail with `PATH_OUTSIDE_SANDBOX` and write nothing outside.
- **Retry version:** retry loaded the workflow's current definition but recorded the failed run's version. It now executes the archived snapshot of the failed run's version (`workflowForVersion`); if no snapshot survives it refuses with `RUN_NOT_RETRYABLE` rather than running an unapproved edit.
- **Blocking start:** `runsStart`/`runsRetry` resolved only after execution finished, so the running record and cancel were unreachable mid-run. `startRun`/`retryRun` now return the `running` record immediately and execute in the background (polling/cancel track it); `startRunAndWait`/`retryRunAndWait` preserve the blocking form for smoke/tests.

- **Verification:** `npm test` — **57/57 pass** (44 before; +13 regression tests); `npm run typecheck`, `npm run lint`, `npm run build` clean; `npm run smoke` SMOKE_OK.
- **Not acted on:** the unrelated `projects/game-save-manager/docs/MUSE_HANDOFF.md` line in this PR's diff came from the shared ancestry-cleanup commit `f5aa771`, not from this project's commits — left for the owner to handle separately rather than adding a cross-project edit here.

## 2026-10-24 — Codex review fixes, cycle 3 (PR #16, head 56d86f6)

Both findings from the cycle-2 re-review verified against the code before fixing:

- **Stop active scripts before closing the application (P1, `main.ts`):** the `before-quit` handler only closed SQLite, while approved scripts run in a detached POSIX process group that would survive the app. The executor now exports `hasActiveRuns` / `activeRunIds` / `shutdownActiveRuns` — the latter cancels every active run (killing its process group) and awaits termination AND finalized (cancelled) log persistence. `main.ts` now intercepts `before-quit` when runs are active (`preventDefault`), awaits `shutdownActiveRuns`, and only then closes the DB and quits; with no active runs it closes the DB and quits as before.
- **Reject duplicate step IDs before persisting (P2, `executor.ts` retry / `schemas.ts`):** `stepsSchema` validated steps independently, so duplicate IDs persisted and made `retryRun`'s resume-by-ID ambiguous. The shared `stepsSchema` now `superRefine`-rejects duplicate IDs (naming the ID and both indexes), covering both persistence paths that use it — workflow update (IPC handler now also parses the whole list through `stepsSchema` instead of per-step only) and import (`IMPORT_INVALID`, nothing persisted).

- **Verification:** `npm test` — **70/70 pass** (65 before; +5 regression tests: shutdown cancels an active script run + kills its descendant + finalized log persisted before return, shutdown no-op with no active runs, schema rejects duplicates, import with duplicates rejected and persists nothing, IPC update with duplicates rejected and persists nothing); `npm run typecheck`, `npm run lint`, `npm run build` clean; `npm run smoke` SMOKE_OK.
