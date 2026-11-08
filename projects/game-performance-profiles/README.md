# Windows Game Performance Profiles

**Status:** MVP — renderer UI complete and tested; backend (Worker A) in progress on the same branch. End-to-end run on real Windows 11 hardware is still pending, so treat this as **implemented but not yet verified on the target OS**.

**Priority:** 8 of 17 in the approved intake queue.
**Category:** Windows gaming utility
**Repository workspace:** `projects/game-performance-profiles/`

## Purpose

Apply reversible, consented per-game performance settings and show before/after resource observations.

## First usable release (MVP)

Define one low-risk profile, preview proposed changes, activate with approval, and fully restore prior settings.

## Full intended capabilities

- Per-game named profiles
- Process and resource telemetry
- Safe power-plan presets where supported
- Window/process identification
- Opt-in changes and automatic rollback
- Before/after resource comparison
- Restore-all and failure diagnostics

## Proposed implementation direction

Windows desktop UI with narrow OS APIs; capability probing and change journal for rollback. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Standalone; optional data import from game metadata manager.

Read-only recommendations by default. No overclocking, driver patching, security-service shutdown, or anti-cheat interference.

## What the MVP actually does

React 19 + TypeScript (strict) renderer inside the Electron shell (`app/`), talking to the main process only through the `window.gpp` preload bridge — twelve fixed channels plus an activation-progress event, typed in `app/shared/gpp-types.ts`.

- **Profiles tab** — profile cards with name, change count, per-change capability badges (supported / unsupported / unknown), and an applied/not-applied badge derived from the change journal. Create, edit, delete (with a confirm step that warns deletion does not undo OS changes).
- **Profile editor** — name plus a change builder with one form per change kind: Game Mode on/off; power-plan GUID (validated 8-4-4-4-12 format, with a "you must pick your own plan — run `powercfg /list`" warning); process priority (process `.exe` name + above-normal/high only — realtime is never offered); fullscreen optimizations (absolute `.exe` path + on/off). All validated client-side before any IPC call.
- **Preview → approval (the safety centerpiece)** — "Preview & activate" shows every planned change with kind, target, from → to, reversible badge, and unsupported warnings with reasons. The Activate button stays disabled until the user ticks an explicit "I understand these changes and approve" checkbox **and** every planned change is supported — any unsupported change blocks activation with an explanation. Activation streams progress events, then reports the result: applied entries, skipped changes, and any automatic rollback.
- **Rollback + Restore all** — per-profile rollback (confirm dialog) and a prominent "Restore all changes" button (confirm dialog) that rolls back every live journal entry across all profiles. Both report exactly what was restored.
- **Journal tab** — every applied change with before → after, applied-at and rolled-back-at timestamps; live entries are badged.
- **Snapshots tab** — take a labeled point-in-time resource snapshot (CPU %, memory MB), list them, and compare any two. Every snapshot carries the note "approximate — point-in-time estimate, not a benchmark".
- Empty states everywhere, actionable error messages (including a clear message when the preload bridge is missing), and keyboard-accessible dialogs (Escape closes, focus outlines).

UI tests: `app/tests-ui/` — 87 hermetic tests (vitest + jsdom) against a mocked `window.gpp`; no test touches real IPC.

## Deferred (not in the MVP)

Per the intake spec's "subsequent milestones" and owner triage, these are **deferred, not planned for this milestone**:

- **Per-game auto-detection** — profiles are defined manually; nothing scans for installed games or running processes.
- **Telemetry charts** — snapshots are point-in-time numbers with before/after comparison only; no graphs, no history views.
- **Scheduled profiles** — no time-based or event-based auto-activation.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
