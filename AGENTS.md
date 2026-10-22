# Repository instructions for Meta Muse and coding agents

**Repository role:** multi-project coding workspace. These instructions apply to every project and take precedence over project-specific instructions where they conflict.

## Scope / isolation — mandatory

1. The root is a **project registry**, not a Node/Python/Rust application.
2. Put each new product in `projects/<descriptive-kebab-case-slug>/`; keep its source, tests, configuration, lockfiles, documentation, scripts, and generated-file paths scoped to that directory.
3. Before implementing, declare your active project folder. Do not modify any other project, even to "clean up" code or dependencies.
4. Never create a shared root package manifest, shared dependency install, shared compiler configuration, or common utilities package without explicit owner approval.
5. Repository-root changes are limited to maintaining the root project index and global instructions. Root GitHub workflow/configuration changes require prior owner approval. A nested `.github/workflows` in a project folder does **not** activate GitHub Actions.
6. Use project-prefixed branches, commits and PR titles: e.g. `github-command-center/feature-name`.
7. Preserve existing unrelated work; never force-push, rewrite history or auto-merge without an explicit request.
8. Never commit secrets, tokens, private customer data, local state/SQLite files, crash dumps or generated release artifacts. Ensure per-project `.gitignore` rules are comprehensive.
9. Do not access or modify connected external repositories as part of testing. Test against mocks/fixtures, or request explicit consent and exact repository/operation for live write tests.
10. Maintain the project's README, tests, implementation status and handoff after substantive changes.

## Minimum standards

- Deliver functional code, not mockup-only interfaces, placeholder APIs or unchecked claims of success.
- Prefer incremental, independently demonstrable vertical slices.
- Verify build, types, tests, lints, and installer/package flow where supported by the environment.
- Clearly separate **implemented and verified**, **implemented but unverified**, **planned**, and **blocked** work.
- Favor safe defaults, least-privilege authentication, accessible UI and actionable error messages.
- Do not claim a test ran or a feature works without actual evidence.
- Read the applicable project instructions first; if they conflict with this document, obey this root document and report the conflict.

## When starting a new project

Create `projects/<slug>/README.md`, `projects/<slug>/AGENTS.md`, `projects/<slug>/docs/MUSE_HANDOFF.md`, project requirements, a test plan, and an initial independently runnable application as soon as practical. Register it in the root README. Do not reuse another project's build setup implicitly.
