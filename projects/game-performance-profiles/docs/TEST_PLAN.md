# Test plan — Windows Game Performance Profiles

**Current test status:** renderer UI suite green (see run record below); backend + on-hardware scenarios still pending.

## Current test status — run record (renderer / Worker B, 2026-10-23)

**UI suite: 87/87 passing** — `cd app && npx vitest run --config vitest.ui.config.ts`
(8 files in `app/tests-ui/`, hermetic: mocked `window.gpp`, no real IPC).

- `validation.test.ts` (26) — profile-name rules, GUID format accept/reject, process-name and exe-path rules, priority allow-list (realtime rejected), per-kind error messages, change summaries.
- `gpp-api.test.ts` (9) — missing-bridge actionable error, channel argument pass-through, `activate` always sends `approved: true`, `{ error }` responses become thrown Errors.
- `ProfilesList.test.tsx` (12) — empty state, cards with change counts, capability badges (supported/unsupported), applied/not-applied from journal, rollback-button enablement, delete confirm flow.
- `ProfileEditor.test.tsx` (12) — per-kind forms, client-side validation blocks bad input (bad GUID rejected, non-absolute exe path rejected), create/update call the right channels.
- `PreviewModal.test.tsx` (11) — from → to table, reversible badges, unsupported rows with reasons, Activate disabled until approval checkbox ticked, unsupported blocks activation, `approved: true` sent, progress events render, failure shows automatic-rollback notice, skipped changes listed, Escape closes.
- `JournalView.test.tsx` (4) — empty state, before → after rows, live badge, rolled-back timestamps.
- `SnapshotsView.test.tsx` (7) — empty state, approximate-note on every snapshot, label required, take-snapshot flow, two-snapshot delta comparison, backend error display.
- `App.test.tsx` (6) — tabs render, missing-bridge error, journal tab, rollback and restore-all confirm flows with result reports, editor open/cancel.

Also green: `npx tsc --noEmit -p tsconfig.renderer.json` (strict) and `npx vite build` (renderer bundle to `dist/renderer`).
Environment: Linux VM, node v24.22.1, npm 10.9.4, run 2026-10-23 ~20:45 MDT.

**Not yet run:** the required scenarios below that need the Electron backend and real Windows 11 hardware (apply/restore idempotency, rollback after unexpected exit, missing privileges, protected-process refusal, no anti-cheat interference). Those belong to Worker A's backend pass plus a Windows-box run; nothing above claims they passed.

## Required automated and integration scenarios

- Apply/restore idempotency
- Rollback after unexpected exit
- Missing privileges and unsupported OS features
- No protected/system process termination
- No changes to anti-cheat or security settings

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Define one low-risk profile, preview proposed changes, activate with approval, and fully restore prior settings.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.
