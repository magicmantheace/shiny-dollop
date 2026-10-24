# Muse implementation handoff — Procedural Dungeon Designer

**Priority:** 15/17. **Project:** `projects/procedural-dungeon-designer/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Generate original seeded, navigable dungeon maps with encounter and hazard budgets.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `procedural-dungeon-designer/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Deterministic generator library + map editor/preview; versioned JSON map export.
5. Implement the **actual** MVP: Generate a seeded connected dungeon, inspect rooms, edit encounter placements, and export the same map deterministically.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Seeds and reproducible layouts
- Connected rooms and corridors
- Theme/biome rules
- Traps, hazards and encounters
- Difficulty/loot budget controls
- Connectivity validator
- Map export and print view

### Project-specific guardrails

Use original assets and rules; do not depend on proprietary RPG content.

**Integrations:** Exports dungeon manifests for AI Dungeon Master.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
