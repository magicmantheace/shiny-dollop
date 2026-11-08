# Product specification — Offline Personal Finance Simulator

**Intake status:** Approved project concept; implementation not started.
**Priority:** 5/17
**Audience/target platform:** Private finance / Windows desktop

## Problem and outcome

Model income, expenses, debts, mortgage renewals, and savings scenarios offline using transparent calculations.

## MVP user workflow and acceptance contract

Enter synthetic debts, income and payments; compare avalanche versus snowball and display monthly balances and interest totals.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Recurring and irregular income calendars** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Debt balances, APR, minimums and payoff ordering** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Scenario comparison and budget constraints** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Mortgage renewal and amortization cases** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Emergency-fund and savings goals** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Cash-flow and payoff charts** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Exportable scenario reports and backups** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Offline desktop UI + SQLite; deterministic financial calculation module with explicit currency and compounding assumptions.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Standalone; no live provider APIs needed.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

No bank-account access by default; use synthetic fixtures only; calculations are scenarios, not financial advice.

- Prefer offline operation and no paid API dependency.
- Optimize for a Windows 11 desktop (i5-10400F, RTX 3060 12 GB, 32 GB RAM), where relevant.
- Avoid destructive defaults, unapproved network calls, or hidden data collection.
- Make errors actionable; provide accessible keyboard navigation and recovery paths.
- Use original/licensed assets and scrub private example data.

## Completion criteria

1. Runnable build and reproducible install or launch instructions.
2. End-to-end MVP workflow exercised with recorded evidence.
3. Focused automated tests and relevant platform manual tests executed.
4. Clear distinction between implemented, verified, planned and blocked features.
5. Scoped pull request left unmerged for review.

## Appendix A — As-built notes (MVP, 2026-10-23, Worker B UI + docs)

### Engine rules (as implemented by Worker A in `app/engine/simulator.ts`; read, not written, by Worker B)

- Money is integer cents everywhere; interest per month = `floor(balanceCents * aprPercent / 1200 + 0.5)` (round-half-up, monthly rate = APR/12).
- Each simulated month, in order: (a) interest accrues on every open debt; (b) minimums are paid in input order, capped at the amount owed; (c) the extra pool (`extraPaymentCents` + minimums freed by debts paid off in *earlier* months) targets one debt at a time per the strategy.
- Avalanche target: highest APR, ties broken by smallest balance. Snowball target: smallest balance, ties broken by highest APR.
- `MonthlyPoint.totalPaidCents` is the amount paid **that month** (not cumulative); the renderer accumulates it for the schedule table. `monthsToPayoff` is `null` (and `neverPaysOff` true) when any debt is still open after `MAX_MONTHS = 1200` (100 years); `neverPaysOffDebts` lists debt **names**.
- Validation limits (engine): debt name 1–100 chars; balance integer cents ≥ 0; APR 0–100; minimum ≥ 0.

### UI validation limits (renderer, `app/renderer/src/lib/validation.ts`)

- Debt form: name required; balance and minimum parsed from dollars to integer cents (rejects malformed input); APR numeric, 0–100 inclusive.
- Income form: name required; amount parsed to cents; frequency must be one of monthly / biweekly / weekly / once.
- Extra-payment input: blank means zero; otherwise must parse as dollars.
- Monthly income conversion: monthly ×1, biweekly ×26/12, weekly ×52/12 (rounded to cents), one-time excluded with a visible note.

### Contract notes (preload deviations vs. the original task brief)

The UI codes against `app/electron/preload.ts` / `app/shared/api-types.ts` as read, not the brief. Deviations: `debts.remove`/`income.remove` (not `delete`); `simulate.run(extraPaymentCents: number)` takes a positional number; `monthsToPayoff: number | null`; per-debt fields are `debtId`, `payoffMonth: number | null`, `interestPaidCents`; monthly points carry no per-month interest; `neverPaysOffDebts` are names. Report CSV layout is per-debt per-month in cents: `strategy,debt,month,balance_cents,interest_cents,payment_cents` (authoritative in `app/electron/report.ts`).

### Deferred items — explicit backlog (not in MVP)

- **Mortgage-renewal cases** — renewal events, amortization schedules, rate-change modeling. Not started.
- **Emergency-fund and savings goals** — goal tracking, target dates. Not started.
- **Irregular-income calendar** — one-time income is recorded but excluded from monthly totals; no calendar view or irregular-cadence planning. Not started.
- Recurring-expense modeling, scenario baselines/snapshots, import/export of app data (backup/restore). Not started.

### Guardrails observed

- Synthetic data only in tests and docs; no network calls in the renderer; disclaimer "Scenarios only — not financial advice." rendered permanently in the app header and footer.
