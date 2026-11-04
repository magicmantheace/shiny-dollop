# PC Storage and Duplicate Finder — project agent instructions

**ACTIVE PROJECT FOLDER WHEN ASSIGNED:** `projects/storage-analyzer/`

Root `AGENTS.md` overrides these instructions on conflict.

1. Work only inside `projects/storage-analyzer/` for application code, manifests, scripts, tests, build artifacts, and project documentation. Other projects are off limits, even if an optional integration is mentioned.
2. Use a dedicated branch named `storage-analyzer/<milestone>`; never force-push or merge without owner approval.
3. Before writing code, read `docs/PRODUCT_SPEC.md`, `docs/TEST_PLAN.md`, and `docs/IMPLEMENTATION_STATUS.md`.
4. Build working executable functionality with realistic error handling, not mockup-only views. Keep deterministic logic and data handling separately testable.
5. Initial MVP is read-only. Never follow reparse points into loops; no system-directory modifications; clearly label stale results.
6. Use synthetic or fixture data in tests. Never commit actual saved games, personal data, invoices, receipts, credentials, model files, runtime databases, or generated products.
7. Validate paths, untrusted inputs, and permissions. Make destructive or external actions opt-in; provide rollback when practical.
8. Record commands actually run, observed results and unresolved platform limitations; do not claim Windows/AI/provider tests passed without executing them.
9. Only update this project's status to MVP/verified after a genuine runnable demonstration. Maintain `docs/IMPLEMENTATION_STATUS.md` after substantive work.
10. Leave project-specific code on a reviewable, unmerged PR. Do not modify shared root workflows or utilities without separate permission.

## Implementation notes (Worker B — renderer + docs, 2026-10-23)

- Renderer lives in `app/src/` (React 19 + TypeScript). Backend (`app/electron/`),
  shared contract (`app/shared/`) and configs are Worker A's; both workers landed on
  the shared `storage-analyzer/mvp` branch. The two halves were developed in parallel
  against the handoff's IPC contract and reconciled before verification.
- `src/types.ts` re-exports the canonical `app/shared/types.ts` and
  `app/shared/api-types.ts` — the renderer declares no IPC types of its own. If the
  contract changes, only `app/shared/` changes.
- `window.storageAnalyzer` is the only bridge the renderer touches (see
  `src/api.ts` for envelope unwrapping and friendly error mapping). No raw
  `ipcRenderer` access from React code.
- `src/format.ts` holds the pure presentation helpers (`formatBytes`,
  `isProtectedPath`, `duplicateSavingsBytes`, `parseExclusions`) with direct unit
  tests; views stay thin.
- The start-scan `warning` (`'protected-path'`) returned by the backend is surfaced
  as a banner in the scan view, alongside the renderer's own client-side
  protected-path heuristic on the start view.
- UI tests live in `src/__tests__/` (picked up by the `ui` vitest project) and mock
  `window.storageAnalyzer` via `mockStorageAnalyzer.ts`. jest-dom matchers need the
  `/vitest` entry point (`import '@testing-library/jest-dom/vitest'`) for
  TypeScript to see them — the bare package entry only augments jest types.
- Backend (Worker A) verification was NOT green at handoff: 1 failing backend test
  (case-insensitive exclusion matching), 1 main-process typecheck error
  (`electron/main/db/scans.ts` TS2352), 2 eslint unused-variable errors. Renderer
  verification is fully green; see README "Verification" and
  `docs/TEST_PLAN.md` appendix.
