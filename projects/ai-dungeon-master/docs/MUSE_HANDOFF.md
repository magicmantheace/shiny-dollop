# Muse implementation handoff — AI Dungeon Master

**Priority:** 16/17. **Project:** `projects/ai-dungeon-master/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Support offline-capable tabletop campaigns with auditable rules, dice, memory, NPCs and optional local AI narration.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `ai-dungeon-master/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Deterministic campaign-state engine + local UI; optional local-model narration adapter.
5. Implement the **actual** MVP: Create a campaign and characters, roll dice, run initiative/combat with logged state, save, and resume.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Campaign and session records
- Character sheets and stats
- Transparent dice engine
- Initiative and encounter state
- NPC/location memory
- Inventory and session notes
- Optional local AI speech/narration
- Versioned ruleset packs and import

### Project-specific guardrails

No unlicensed proprietary rulebooks; AI flavor is never the authoritative rules engine.

**Integrations:** Can import approved character/world exports from Worldbuilding Manager and dungeon manifests from Procedural Dungeon Designer.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
