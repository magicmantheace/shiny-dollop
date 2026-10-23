# Offline Personal Finance Simulator

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

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
