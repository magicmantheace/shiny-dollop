# Muse implementation handoff — Concrete Operations Manager

**Priority:** 2/17. **Project:** `projects/concrete-operations-manager/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Track concrete delivery customers, jobs, pours, pricing, inventory, quoting, and invoicing in one auditable system.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `concrete-operations-manager/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Local-first desktop app with SQLite and PDF/CSV exports; choose a scoped Windows-friendly UI stack.
5. Implement the **actual** MVP: Create a customer and job, record one pour, calculate an itemized quote with tax, finalize delivered volume, and export an invoice.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Customer records and purchase orders
- Job scheduling, dates and delivery locations
- Mix/strength and ordered versus delivered volume
- Customer pricing, small-load and flat or mileage delivery fees
- Canadian tax configuration and separate charge lines
- Quote, invoice and payment states
- Cement/aggregate deliveries and stock movements
- Calibration-linked yield and reconciliation reports

### Project-specific guardrails

Never commit genuine customer data. Show each invoice charge separately; preserve issued document history; allow overrides with audit trails.

**Integrations:** Can import/export versioned calibration data from the independent Volumetric Concrete Mix Calculator.

Do not access or modify the other project directories, the original Crawl repository, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
