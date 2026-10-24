# Muse implementation handoff — Personal Knowledge Vault

**Priority:** 11/17. **Project:** `projects/personal-knowledge-vault/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Store searchable source-linked personal knowledge with review, provenance, and corrections.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `personal-knowledge-vault/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Offline desktop app with SQLite and local full-text index; optional later embedding adapter.
5. Implement the **actual** MVP: Create unverified notes with sources, approve individual records, search them, correct history, and export a safe backup.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Notes and source citations
- Candidate/verified/rejected review statuses
- Revision and correction history
- Search, tagging and linked records
- Source-document pointers and access labels
- JSON export/import with provenance
- Local backups and optional encryption

### Project-specific guardrails

No ingestion of owner's private data without authorization; no automatic AthenZ sync or edits to AthenZ.

**Integrations:** Future opt-in, versioned export interface for AthenZ and Local AI Command Center.

Do not access or modify the other project directories, the original Crawl repository, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
