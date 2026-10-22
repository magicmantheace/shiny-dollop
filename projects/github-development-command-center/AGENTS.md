# Project-local instructions for Muse

**Current project:** `projects/github-development-command-center/`. Scope your edits to this folder. Also obey [the repository root AGENTS.md](../../AGENTS.md).

## Mission

Deliver a complete, installable, useful **Windows-first GitHub Development Command Center**, not merely a concept, component gallery, command-line script or documentation set. Read `docs/MUSE_HANDOFF.md` first.

## Development behavior

- Start by examining the repository and specs. Do not ask broad questions already answered in the documents.
- Choose a stable, supportable TypeScript desktop stack consistent with `docs/ARCHITECTURE.md`; document exact versions as pinned in lockfile. Prioritize a working application over unnecessary abstractions.
- Work in small integrated slices; each milestone should be runnable and testable. Prefer finishing a small real workflow before building a sprawling skeleton.
- Keep repository structure strict; all app files remain under this project folder.
- Use GitHub REST APIs with safe pagination, abortability, cached responses and clear permission/rate-limit errors. Show **real** GitHub data in authenticated mode; use explicit mock/fixture data only in tests or a clearly labeled demo mode.
- Initial release is **read-only for GitHub**. UI can open GitHub web pages but cannot push, merge, comment, close issues, dispatch workflows, change settings or write to GitHub.
- Credentials must remain in an OS-backed credential store, never source, local plain JSON, SQLite, renderer localStorage, analytics or logs.
- Never silently expand token scopes or perform automatic write actions.
- Use conventional accessible controls; support keyboard focus and empty/loading/error states.
- Do not assert tests passed unless executed. If platform limitations prevent running a Windows installer test, record what was/was not validated.
- Update README, handoff and implementation checklist with every meaningful delivery.
- No production API credential is supplied by the repo; use test fixtures and mocks for automated tests.

## Definition of done

All MVP acceptance criteria in `docs/TEST_PLAN.md` are satisfied with verifiable evidence; the Windows installer/startup path works; the app displays live account-owned GitHub information when configured; and a user can install, authenticate, select repos, inspect details, and reopen the app with preferences intact.

If a feature is not done, report it as incomplete — never fill the gap with a fake button or hard-coded "green" status.

## Boundaries

Only read other GitHub repositories if the owner explicitly authorizes access through their own credential. Do not touch the owner's unrelated repositories, branches or CI configuration. No AthenZ, Synveil or Developmental AI integration is part of this project; they are simply possible tracked repositories at the owner's discretion.
