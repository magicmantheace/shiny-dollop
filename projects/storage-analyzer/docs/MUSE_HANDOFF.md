# Muse implementation handoff — PC Storage and Duplicate Finder

**Priority:** 4/17. **Project:** `projects/storage-analyzer/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Understand drive usage and duplicate files with non-destructive analysis and transparent evidence.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `storage-analyzer/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Windows desktop UI plus cancellable background filesystem indexer and SHA-256 duplicate verification.
5. Implement the **actual** MVP: Choose a directory, view ranked file/folder sizes and verified duplicate groups, cancel scans, and export a report; no deletion.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Folder and drive-space treemap/list
- Large-file filtering
- Size-first and hash-confirmed duplicate groups
- Search and file-type summaries
- Exclusion rules and protected-path warnings
- Cancellable scans with progress
- CSV/JSON results and rescan comparison

### Project-specific guardrails

Initial MVP is read-only. Never follow reparse points into loops; no system-directory modifications; clearly label stale results.

**Integrations:** Standalone.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
