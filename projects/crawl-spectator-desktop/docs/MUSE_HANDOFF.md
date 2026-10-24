# Muse implementation handoff — Crawl Live Spectator Desktop

**Priority:** 17/17. **Project:** `projects/crawl-spectator-desktop/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Read-only desktop viewer for real Descender state, live events, relationships, stories and replays.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `crawl-spectator-desktop/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Desktop client with typed, versioned read-only API adapter and reconnect handling; use existing Underreach Feed contracts.
5. Implement the **actual** MVP: Connect to a running local Underreach Feed API, display real Descenders, select one and inspect authentic state/history plus live updates.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Connection setup and runtime status
- Descender search and profiles
- Current stratum/sector and status
- Relationships, parties and history
- Live Ledger event feed
- Follow/favorites local preferences
- Replay browser and highlights
- Archived Descent navigation

### Project-specific guardrails

Strictly read-only: never alter canonical Crawl/Underreach data. Do not change `projects/crawl/` during this project.

**Integrations:** Consumes `projects/crawl/` APIs only, without cross-project source coupling.

Do not access or modify the other project directories, the original Crawl repository, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
