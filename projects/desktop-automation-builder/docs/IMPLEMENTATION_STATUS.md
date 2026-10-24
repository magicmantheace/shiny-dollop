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
