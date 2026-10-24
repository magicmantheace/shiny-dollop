# Muse implementation handoff — Volumetric Concrete Mix Calculator

**Priority:** 3/17. **Project:** `projects/volumetric-concrete-calculator/`.
**Status:** Project documentation is created; application code has not yet been implemented.

## Assignment

Calculate calibrated volumetric-truck material needs, stock use, and estimated production yield without claiming unverified strength results.

### Start here

1. Read repository-root `AGENTS.md` and this project's `AGENTS.md`.
2. Inspect the latest `main` and all relevant unmerged branches/PRs. Do not overwrite someone else's work.
3. Begin a dedicated `volumetric-concrete-calculator/mvp` branch once this intake has been merged (or base appropriately without rewriting history).
4. Choose the simplest maintainable stack compatible with: Offline calculation engine with typed units and a simple desktop UI; portable JSON/CSV calibration exchange.
5. Implement the **actual** MVP: Enter a calibrated mix and desired cubic metres and obtain reproducible cement, sand, stone, water and estimated remaining-stock quantities.
6. Write automated tests for its success path and critical failure modes. Execute `docs/TEST_PLAN.md` where the environment permits.
7. Commit scope-limited production code, validate the build, and open an unmerged PR documenting evidence and limitations.
8. Update `docs/IMPLEMENTATION_STATUS.md`; do not claim unverified capabilities work.

### Expansion backlog

- Versioned mix/calibration profiles
- Cement, sand, stone, water, and admixture quantities
- Adjustable target volume and waste allowance
- Onboard inventory and silo balance estimate
- Payload and capacity warning inputs
- Measured-versus-theoretical yield comparison
- Unit-aware CSV and JSON exports

### Project-specific guardrails

Do not assert structural concrete strength, code compliance, legal truck payload, or tested mix adequacy from estimates. Mark assumptions and measurement sources.

**Integrations:** Export format usable by Concrete Operations Manager; applications must compile and run independently.

Do not access or modify the other project directories, the original Crawl repository, real personal data, connected accounts, or production systems to test this app. Use fixtures or explicitly approved narrow interfaces.

### Stop/continue logic

Finish a small, functional vertical slice rather than scaffolding all 17 projects. If blocked by platform or a genuinely missing dependency, record the blocker, preserve reviewable work, and then proceed to another independent approved task.
