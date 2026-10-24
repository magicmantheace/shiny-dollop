# Muse implementation handoff — Game Library Metadata Enricher

**Priority:** 7/17. **Project:** `projects/game-metadata-manager/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Organize game artwork, descriptions, collections, tags, and missing-install metadata without altering games.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `game-metadata-manager/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Standalone Electron or equivalent Windows app with versioned import/export; keep existing game launcher untouched.
5. Implement the **actual** MVP: Import a fixture library, edit artwork/title/tags, detect a missing path, and export a reversible metadata bundle.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Game library importer and schema versioning
- Editable descriptions and original titles
- Artwork picker and cache provenance
- Custom tags, groups and filters
- Missing executable/install detection
- Conflict-safe metadata merges
- JSON/CSV export and undoable edits

### Project-specific guardrails

No modification of the existing Universal Game Launcher as part of this project; do not scrape copyrighted art without appropriate rights.

**Integrations:** Optional future reviewed interoperability with `projects/universal-game-launcher/`.

Do not access or modify the other project directories, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
