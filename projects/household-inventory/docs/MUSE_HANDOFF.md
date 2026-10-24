# Muse implementation handoff — Household Inventory and Warranty Tracker

**Priority:** 6/17. **Project:** `projects/household-inventory/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Maintain a private catalogue of household assets, receipts, warranties, and maintenance history.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `household-inventory/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Local-first desktop application and SQLite plus app-owned attachment store.
5. Implement the **actual** MVP: Add an item and receipt, record purchase and warranty dates, find expiring warranties, and export a backup.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Product and location records
- Purchase price, date, serial number and notes
- Warranty dates and reminders
- Receipt/photo attachments
- Maintenance events
- Search, category filters and replacement estimates
- Portable encrypted-export option later

### Project-specific guardrails

Keep real receipts and serial numbers local; no mandatory online accounts.

**Integrations:** Standalone.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
