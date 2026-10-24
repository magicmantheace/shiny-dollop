# Test plan — Offline Personal Finance Simulator

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Debt amortization and interest arithmetic against worked examples
- Zero-rate, overpayment, skipped-month and irregular-income cases
- Calendar monthly versus biweekly payment handling
- Scenario edits cannot alter saved baselines
- No personal data transmitted over network

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Enter synthetic debts, income and payments; compare avalanche versus snowball and display monthly balances and interest totals.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

## Recorded results — Worker B (UI + docs), 2026-10-23

Environment: Linux VM (this build host), branch `finance-simulator/mvp`. UI-only checks below; engine/electron results belong to Worker A.

| # | Command | Env | Result |
|---|---|---|---|
| B-1 | vitest 3.2.7 (scratch install) `--dir app/tests/ui` | Linux VM, Node (npx) | **5 files, 48/48 tests pass** |
| B-2 | `tsc --noEmit --strict --jsx react-jsx` over `app/renderer/**` (TS 5, React 19 types, scratch) | Linux VM | **clean, 0 errors** |
| B-3 | `npm run build:renderer` (vite, Worker A's `vite.config.ts`) | Linux VM, `app/` node_modules | **builds OK** → `dist/renderer/index.html` + `assets/index-*.js` |
| B-4 | `npm test` in `app/` (Worker A's vitest config; picks up `app/tests/ui/**`) | Linux VM | 9 files, 98/100 pass — all 48 UI tests pass; 2 failures are in Worker A's `tests/engine/simulator.test.ts` |
| B-5 | `npm run smoke` (Worker A's `scripts/smoke.mjs`, xvfb) | Linux VM | **FAIL — backend bug, not UI**: `installSecurityGuards` in `dist/electron/main.js` calls `session.defaultSession` before app ready (`TypeError: Session can only be received when app is ready`). Window never boots. Referred to Worker A. |

### UI test coverage (48 tests, `app/tests/ui/`)

- `money.test.ts` (14): dollars↔cents parsing incl. `$`/commas, invalid input rejection, USD formatting, horizon formatting.
- `validation.test.ts` (14): debt form (name required, balance/malformed, APR 0–100 boundaries, minimum), income form (name, amount, frequency), extra-payment input (blank=zero, invalid rejected).
- `frequency.test.ts` (6): biweekly/weekly annualization factors, one-time exclusion, monthly total sum, empty list.
- `chart.test.ts` (7): polyline point count, max→top/zero→bottom mapping, empty series, downsample keeps first/last, shared y-axis ceiling.
- `report.test.ts` (7): CSV header pinned to main-process contract, cell escaping (commas/quotes), per-debt row rendering, header-only empty case.

All tests use synthetic fixtures only; no network, no Electron, no personal data.

### Not run (platform gaps, marked implemented-but-unverified)

- Electron window boot with the real preload bridge (blocked on B-5 backend bug).
- Windows portable zip build / install / SmartScreen behavior (needs Windows hardware; see `docs/WINDOWS_INSTALL.md`).
