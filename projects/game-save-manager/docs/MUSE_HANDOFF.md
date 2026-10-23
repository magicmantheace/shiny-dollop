# Muse implementation handoff — Universal Game Save Manager

**Priority:** 1/17. **Project:** `projects/game-save-manager/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Safely discover, back up, version, verify, and restore PC game saves across manual locations and common storefront layouts.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `game-save-manager/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Electron + React + TypeScript + SQLite; filesystem operations through a validated main-process API.
5. Implement the **actual** MVP: Register a manual save folder, produce a dated, checksum-verified snapshot, list backups, and restore one with a safety copy and explicit confirmation.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Manual game/save-folder registration
- Steam, Epic, and Battle.net location discovery where reliable
- Versioned timestamped backups and per-file checksums
- Safe restoration with pre-restore backup
- Change detection and backup retention settings
- Scheduled backups while running
- History, searchable game list, and exportable manifest

### Project-specific guardrails

Do not assume storefront installation paths equal game save locations. Do not delete game data, bypass cloud sync, or silently overwrite saves.

**Integrations:** Standalone; optional future interoperability with the existing Universal PC Game Launcher only by separate approval.

Do not access or modify the other project directories, the original Crawl repository, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
