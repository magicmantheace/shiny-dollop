# Muse implementation handoff — Digital Product Template Factory

**Priority:** 9/17. **Project:** `projects/digital-template-factory/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Generate editable, quality-checked downloadable templates from original reusable designs.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `digital-template-factory/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Local application with deterministic template manifests, validators, preview and exporters.
5. Implement the **actual** MVP: Select an original template, edit its data/theme, preview it, and export a functional HTML or printable package with checks.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Template catalog and metadata
- Editable design tokens and content fields
- Batch generation
- Preview and output validation
- Accessible HTML export
- Document/spreadsheet/planner package types in later milestones
- Versioned templates and license records

### Project-specific guardrails

Use original assets, legal licenses, and one-time purchase compatible outputs; avoid paid-service requirements.

**Integrations:** Provide documented export manifest for Business Website Generator.

Do not access or modify the other project directories, the original Crawl repository, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
