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
