# Muse implementation handoff — Desktop Automation Builder

**Priority:** 12/17. **Project:** `projects/desktop-automation-builder/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Create supervised repeatable automation flows for files, scripts and applications.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `desktop-automation-builder/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Desktop flow editor and sandboxed/permissioned workflow executor with durable logs.
5. Implement the **actual** MVP: Build a simple non-destructive file-copy workflow, preview its actions, approve, run, inspect log, and retry safely.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Node-based or step-list workflow authoring
- Triggers and conditions
- File and folder actions
- Approved process/script steps
- Dry-run and explicit approval checkpoints
- Retry policy and cancellation
- Workflow versioning and exports

### Project-specific guardrails

No unrestricted shell execution or invisible background persistence; no privileged/destructive actions without separate explicit approval.

**Integrations:** Optional future permission-mediated action interface for Local AI Command Center.

Do not access or modify the other project directories, the original Crawl repository, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
