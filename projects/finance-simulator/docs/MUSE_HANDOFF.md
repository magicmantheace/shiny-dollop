# Muse implementation handoff — Offline Personal Finance Simulator

**Priority:** 5/17. **Project:** `projects/finance-simulator/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Model income, expenses, debts, mortgage renewals, and savings scenarios offline using transparent calculations.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `finance-simulator/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Offline desktop UI + SQLite; deterministic financial calculation module with explicit currency and compounding assumptions.
5. Implement the **actual** MVP: Enter synthetic debts, income and payments; compare avalanche versus snowball and display monthly balances and interest totals.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Recurring and irregular income calendars
- Debt balances, APR, minimums and payoff ordering
- Scenario comparison and budget constraints
- Mortgage renewal and amortization cases
- Emergency-fund and savings goals
- Cash-flow and payoff charts
- Exportable scenario reports and backups

### Project-specific guardrails

No bank-account access by default; use synthetic fixtures only; calculations are scenarios, not financial advice.

**Integrations:** Standalone; no live provider APIs needed.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
