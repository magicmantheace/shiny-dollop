# Implementation status — Offline Personal Finance Simulator

- **Overall status:** MVP (Worker B slice: React UI, UI tests, docs) — committed, not PR'd
- **Priority:** 5/17
- **Branch:** `finance-simulator/mvp`
- **Coordination:** Worker A (backend: engine, db, electron, preload) and Worker B (UI + docs) built in the same worktree/branch. A's backend files exist in the worktree but were **uncommitted** at the time of the Worker B commit (see below); B's commit contains only B-owned paths.

## Worker B deliverables (this commit)

**Renderer** (`app/renderer/`, React 19 + TypeScript, inline styles, no CSS framework):
- `src/App.tsx` — tab navigation (Debts / Income / Simulator); permanent header + footer disclaimer: "Scenarios only — not financial advice."
- `src/components/DebtsView.tsx` — debt table (name, balance, APR, minimum) + add/edit/delete with inline field validation (name required; balance ≥ 0; APR 0–100; minimum ≥ 0). Delete is confirm-gated.
- `src/components/IncomeView.tsx` — income table (name, amount, frequency) + add/edit/delete; computed **monthly income total** (monthly ×1, biweekly ×26/12, weekly ×52/12, one-time excluded with a note).
- `src/components/SimulatorView.tsx` — extra-monthly-payment input; "Run comparison" → side-by-side avalanche vs snowball cards (months to payoff or "Never — minimums don't cover interest", total paid, total interest); SVG line chart of total balance per month (both strategies, shared y-axis); monthly aggregate schedule table (first 24 months + final, scrollable); per-debt payoff breakdown table (payoff month, total paid, interest paid); budget-check banner (total minimums vs monthly income → "unaffordable" warning); CSV/JSON export buttons via `sim.report.save`.
- `src/lib/` — pure, tested helpers: `money.ts` (dollars↔cents, USD formatting), `validation.ts` (form validators), `frequency.ts` (monthly math), `chart.ts` (SVG transforms), `report.ts` (CSV layout contract mirror).
- `src/types.ts` — renderer-side copy of the preload contract, aligned to `app/shared/api-types.ts` / `app/engine/simulator.ts` / `app/shared/types.ts` after reading Worker A's implementation.

**UI tests** (`app/tests/ui/`, vitest): 48 tests, all passing — money (14), validation (14), frequency (6), chart (7), report (7).

**Docs:** `docs/IMPLEMENTATION_STATUS.md` (this file, rewritten), `docs/TEST_PLAN.md` (results table appended), `docs/PRODUCT_SPEC.md` (as-built appendix), `docs/WINDOWS_INSTALL.md` (new), `README.md` (PLANNED → MVP), `AGENTS.md` (10 owner rules kept verbatim; implementation notes appended).

## Verification evidence (Worker B)

| Check | Command / env | Result |
|---|---|---|
| UI tests (standalone) | vitest 3.2.7 in scratch dir, `--dir app/tests/ui` | **48/48 pass** (5 files) |
| UI tests (project suite) | `npm test` in `app/` (A's vitest config) | my 5 files pass; 98/100 total pass — 2 failures are in A's `tests/engine/simulator.test.ts` (see open issues) |
| Renderer typecheck | `tsc --noEmit --strict --jsx react-jsx` on `app/renderer/**` (scratch TS 5 + React 19 types) | **clean, 0 errors** |
| Renderer build | `npm run build:renderer` (vite, Worker A's config) | **succeeds** → `dist/renderer/` |
| Smoke | `npm run smoke` (A's script, xvfb) | **FAILS — in A's backend code**, not the UI (see open issues) |

## Contract deviations found in Worker A's preload (UI aligned to actual, not brief)

1. `sim.debts.delete(id)` → actual is **`sim.debts.remove(id)`**.
2. `sim.income.delete(id)` → actual is **`sim.income.remove(id)`**.
3. `sim.simulate.run({ extraPaymentCents })` → actual is **`run(extraPaymentCents: number)`** (positional).
4. `SimulationResult.monthsToPayoff` is `number | null` (not `number`); UI treats `null` as never-pays-off.
5. Per-debt result fields are `debtId`, `payoffMonth: number | null`, `interestPaidCents` (not `id`/`totalInterestCents`).
6. Monthly series points are `{ month, totalBalanceCents, totalPaidCents }` — **no per-month interest field**; schedule table shows balance + cumulative paid only.
7. `neverPaysOffDebts` contains debt **names**, not ids (per `engine/simulator.ts`); UI displays them as names.
8. Report CSV layout is per-debt per-month in cents: `strategy,debt,month,balance_cents,interest_cents,payment_cents` (authoritative in `app/electron/report.ts`); renderer `lib/report.ts` mirrors this contract for tests/docs.
9. Entry wiring: A's `app/index.html` loads `/renderer/main.tsx`; UI provides that as a thin shim re-exporting `./src/main`.

## Open issues (Worker A domain — not touched)

1. **`npm run smoke` fails:** `dist/electron/main.js` → `installSecurityGuards` calls `session.defaultSession` before app is ready → `TypeError: Session can only be received when app is ready`. Backend bug; window never boots here.
2. **2 engine test failures:** `tests/engine/simulator.test.ts` — "snowballing freed minimums / rolls paid-off minimums into the extra pool" (expected 3, got 5) and "target ordering / snowball breaks balance ties by highest APR" (expected 9 < 4). Engine semantics vs test expectations; needs A's call.
3. **`npm run typecheck` does not cover the renderer** (only `tsconfig.main.json` + `tsconfig.preload.json`). Recommend adding a renderer tsconfig to the typecheck chain.
4. **A's backend commit:** at Worker B commit time, `app/electron/**`, `app/engine/**`, `app/db/**`, `app/shared/**`, `app/tests/engine/**`, configs, and scripts existed in the worktree **uncommitted**. UI was verified against those files as read.

## Not verified (honest gaps)

- No end-to-end run of the packaged app on Windows (or anywhere) — smoke is blocked on issue #1 above.
- Renderer components were typechecked and built, but not exercised against the live preload bridge (needs the Electron shell).
- Portable Windows zip not produced (blocked on smoke + Windows hardware).

## Next actions

1. Worker A: fix `installSecurityGuards` ordering; resolve the 2 engine test failures; commit backend.
2. Worker A: add renderer typecheck to `npm run typecheck`.
3. Re-run `npm run smoke` after (1); then `npm run package:win` on Windows hardware and follow `docs/WINDOWS_INSTALL.md`.
4. Owner review via PR (do not merge without approval).
