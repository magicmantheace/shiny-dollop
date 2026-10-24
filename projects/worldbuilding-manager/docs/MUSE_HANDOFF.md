# Muse implementation handoff — Novel and Worldbuilding Manager

**Priority:** 14/17. **Project:** `projects/worldbuilding-manager/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Organize stories, characters, lore, timelines, locations and relationship continuity offline.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `worldbuilding-manager/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Local desktop editor, SQLite, markdown-friendly notes, entity links and export bundles.
5. Implement the **actual** MVP: Create characters, locations and a timeline event, link them, search notes, and export a complete project backup.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Character and location sheets
- Factions and relationship map
- Timeline events and dates
- Notes, chapters, outlines and tags
- Cross-references and continuity warnings
- Snapshots and version history
- Markdown/JSON exports

### Project-specific guardrails

Author retains control and copyright; no external sync by default.

**Integrations:** Optional export of settings and characters to AI Dungeon Master.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
