# Muse Project Workspace

This repository is a long-term, multi-project development workspace for Meta Muse. **It is not one application.** Each independent project lives entirely under `projects/<project-slug>/`.

## Project index

| Folder | Product | Status |
| --- | --- | --- |
| [`projects/github-development-command-center/`](projects/github-development-command-center/README.md) | GitHub Development Command Center — a usable Windows desktop application for monitoring and managing GitHub development work | Specification / ready for implementation |

## Rules for Muse and other coding agents

Read [AGENTS.md](AGENTS.md) before changing anything. Then read the selected project's own `AGENTS.md`, `README.md`, and `docs/MUSE_HANDOFF.md`.

- **One independent project per folder:** `projects/<project-slug>/`. Never build unrelated projects at the repository root.
- All code, assets, tests, build configuration, local documentation, lockfiles, output paths and per-project scripts stay inside that project's folder.
- Never edit, refactor, format, delete, or import another project's files as a side effect of current work.
- Prefer narrow commits and pull requests; identify which project they change.
- Make each project independently installable/buildable/testable. Do not assume a shared runtime or a single root package.
- Do not include API credentials, access tokens, personal data, local databases or generated binaries in Git.
- If work truly requires a repository-root change (such as a GitHub Actions workflow), explain the reason and obtain owner approval first.
- When adding a project, create its own `README.md`, `AGENTS.md`, `docs/MUSE_HANDOFF.md`, and a row in this index.

## Getting started with the first project

Open [the project handoff](projects/github-development-command-center/docs/MUSE_HANDOFF.md), follow its reading order, then **implement and test real working code**. Documentation alone is not completion.

Project specifications are intended to be revised as engineering discoveries are made, but do not silently reduce user-facing requirements. When a requested capability is blocked, document the blocker and implement the next independently useful slice.
