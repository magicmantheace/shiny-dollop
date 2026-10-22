# GitHub Development Command Center

**Working name:** GitHub Development Command Center (GDCC)  
**Repository:** `magicmantheace/shiny-dollop`  
**Project root:** `projects/github-development-command-center/`  
**Status:** Requirements defined; application not yet implemented.  
**Initial target:** Windows 11 desktop app, local-first, single-user, GitHub.com.

## Product purpose

Build a genuinely usable desktop application that gathers **repository activity, branches, commits, pull requests, issues and CI/check status** into one fast, understandable control center. Let the owner select and monitor multiple GitHub repositories without altering them. Real data, local persistence and an installable release are essential.

This is **a standalone product inside a multi-project workspace** — not a module of any other software in this repository.

## Specification and build instructions

Read in this order:

1. [Repository-wide agent rules](../../AGENTS.md)
2. [Project agent rules](AGENTS.md)
3. [Muse start instructions](docs/MUSE_HANDOFF.md)
4. [Product requirements](docs/PRODUCT_SPEC.md)
5. [Architecture and security](docs/ARCHITECTURE.md)
6. [Delivery milestones](docs/IMPLEMENTATION_PLAN.md)
7. [Test and acceptance plan](docs/TEST_PLAN.md)

## Intended application layout

```text
projects/github-development-command-center/
  README.md
  AGENTS.md
  docs/
    MUSE_HANDOFF.md
    PRODUCT_SPEC.md
    ARCHITECTURE.md
    IMPLEMENTATION_PLAN.md
    TEST_PLAN.md
  app/               # Muse creates application source and its own package/build configs here
  scripts/           # optional project-local helper scripts
```

If an implementation-specific tool works better when the application package is directly at this project root, Muse may do so **within this project folder**, keeping all build metadata scoped here. Do not move it to the repository root.

## Initial workflows

1. Start the installed application and connect to GitHub with a user-provided, read-only credential.
2. Select several repositories from accessible GitHub repositories.
3. See a summary of recent activity, active/open PRs, issues, default branches and workflow/check state.
4. Inspect a repository, open items in a browser, filter and refresh, without modifying any GitHub data.
5. Quit and reopen the app: selected repos, preferences and nonsecret cached data remain.
6. Disconnect/revoke locally stored credentials and use the app's safe offline mode.

## Current truth

**No code or tests have been delivered yet.** The present commit supplies a complete implementation brief for Muse. Implementation status must be updated with evidence as work proceeds.
