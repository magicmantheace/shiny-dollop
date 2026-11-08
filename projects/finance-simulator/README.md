# Offline Personal Finance Simulator

**Status:** MVP — Worker B (React UI, UI tests, docs) slice committed on `finance-simulator/mvp`; backend by Worker A. **Not end-to-end verified.** Honest state:

- ✅ React UI builds (`npm run build:renderer`) and typechecks clean; 48/48 UI tests pass.
- ✅ UI codes against the actual preload contract (several deviations from the brief were found and handled — see `docs/IMPLEMENTATION_STATUS.md`).
- ❌ `npm run smoke` fails in Worker A's backend (`installSecurityGuards` calls `session.defaultSession` before app ready) — no window boot verified.
- ❌ 2 failing tests in Worker A's `tests/engine/simulator.test.ts` (engine semantics, his domain).
- ❌ No Windows run / portable zip produced yet.

See [implementation status](docs/IMPLEMENTATION_STATUS.md), [test plan](docs/TEST_PLAN.md),
[specification](docs/PRODUCT_SPEC.md) (incl. as-built appendix), and
[Windows install notes](docs/WINDOWS_INSTALL.md).

**Priority:** 5 of 17 in the approved intake queue.
**Category:** Private finance / Windows desktop
**Repository workspace:** `projects/finance-simulator/`

## Purpose

Model income, expenses, debts, mortgage renewals, and savings scenarios offline using transparent calculations.

## First usable release (MVP)

Enter synthetic debts, income and payments; compare avalanche versus snowball and display monthly balances and interest totals.

## Full intended capabilities

- Recurring and irregular income calendars
- Debt balances, APR, minimums and payoff ordering
- Scenario comparison and budget constraints
- Mortgage renewal and amortization cases
- Emergency-fund and savings goals
- Cash-flow and payoff charts
- Exportable scenario reports and backups

## Proposed implementation direction

Offline desktop UI + SQLite; deterministic financial calculation module with explicit currency and compounding assumptions. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Standalone; no live provider APIs needed.

No bank-account access by default; use synthetic fixtures only; calculations are scenarios, not financial advice.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
