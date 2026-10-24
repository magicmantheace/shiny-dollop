# Test plan — Small Business Website Generator

**Current test status:** RUN 2026-10-23 (Linux VM, Node 24) — **132/132 pass** across 15 files:
`tests/backend/*` (99: themes determinism + injection-inertness, all five validator codes, export pipeline happy-path/blocking/dest-guards, db CRUD + reopen, IPC contract shape, preload method list),
`tests/renderer/*` (32: editor validation blocking bad email/URL/phone, dynamic list add/remove, restaurant-vs-trades menu sections, theme switch → setTheme + preview re-render, preview iframe srcDoc/tab/viewport, export blocked-while-issues/clean-export/picker-cancel, dashboard wizard/delete/Escape),
`tests/backend/acceptance.test.ts` (MVP walkthrough: restaurant site → fill profile → validate clean → export 6 files → internal links resolve → no third-party assets → byte-identical second export → missing name blocks export, nothing written).
`npm run typecheck` clean (main + renderer), `npm run lint` clean, `npm run build` green, `npm run smoke` PASS (real window under xvfb, export ok).
Windows click-through not executed here — marked pending, not passing.

## Required automated and integration scenarios

- Preview/export match
- Links and relative asset paths work offline
- Responsive keyboard/navigation checks
- Injection-safe user content
- No third-party hosted assets required

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Choose a business type, fill contact/services, preview a responsive website, and export a deployable static folder.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.
