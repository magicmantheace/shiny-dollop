# Muse implementation handoff — Local AI Command Center

**Priority:** 13/17. **Project:** `projects/local-ai-command-center/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Supervise local LLM runtimes and constrained coding agents with queues, reviews and resource policies.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `local-ai-command-center/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Windows desktop UI, local runtime adapters, subprocess metrics and constrained task/workspace API.
5. Implement the **actual** MVP: Configure an installed local model endpoint, submit a text task, review output/logs, and cancel the task; provide useful offline setup mode.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Local endpoint discovery and health checks
- Model selection and comparison
- Task queue and cancellation
- CPU/RAM/GPU resource monitoring
- Scoped agent workspaces
- Diff/patch proposal review
- Approval and audit log
- No-cloud default and bounded optional integrations

### Project-specific guardrails

No autonomous unrestricted write access, credentials, shell or network privileges; no paid inference by default.

**Integrations:** Later optional import from Personal Knowledge Vault and approval-mediated actions from Desktop Automation Builder.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
