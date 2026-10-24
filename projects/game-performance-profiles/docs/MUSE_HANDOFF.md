# Muse implementation handoff — Windows Game Performance Profiles

**Priority:** 8/17. **Project:** `projects/game-performance-profiles/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Apply reversible, consented per-game performance settings and show before/after resource observations.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `game-performance-profiles/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Windows desktop UI with narrow OS APIs; capability probing and change journal for rollback.
5. Implement the **actual** MVP: Define one low-risk profile, preview proposed changes, activate with approval, and fully restore prior settings.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Per-game named profiles
- Process and resource telemetry
- Safe power-plan presets where supported
- Window/process identification
- Opt-in changes and automatic rollback
- Before/after resource comparison
- Restore-all and failure diagnostics

### Project-specific guardrails

Read-only recommendations by default. No overclocking, driver patching, security-service shutdown, or anti-cheat interference.

**Integrations:** Standalone; optional data import from game metadata manager.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
