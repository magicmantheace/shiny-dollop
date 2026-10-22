# Meta Muse — Multi-Project Development Workspace

This repository is a long-term workspace for **multiple separate Muse-built applications**. The repository root is an index and global rules, **not** a single application.

## Projects

| Project | Directory | Status |
| --- | --- | --- |
| **Universal PC Game Launcher** | [`projects/universal-game-launcher/`](projects/universal-game-launcher/README.md) | **ACTIVE — build this next** |
| GitHub Development Command Center | [`projects/github-development-command-center/`](projects/github-development-command-center/README.md) | **PARKED / BACK BURNER — do not implement now** |

**Muse: start here:** [Game Launcher task handoff](projects/universal-game-launcher/docs/MUSE_HANDOFF.md). Do **not** continue the GitHub Development Command Center until the owner explicitly reactivates it.

## Workspace structure

```text
shiny-dollop/
  README.md                    # workspace index
  AGENTS.md                    # global coding-agent instructions
  projects/
    universal-game-launcher/  # ACTIVE; owns all launcher code, tests and docs
    github-development-command-center/  # PARKED; preserved specifications
    <future-project>/         # each future project is independent
```

## Permanent rules

1. **One application per `projects/<slug>/` folder** — no code, dependency manifests, lockfiles or installers at repository root.
2. Read [root AGENTS.md](AGENTS.md), then the active project's own `AGENTS.md` and `docs/MUSE_HANDOFF.md`.
3. Do not modify another project while working on the active one.
4. Prefer project-scoped branches/PRs and narrow commits. No history rewrites or unapproved automatic merges.
5. Never commit secrets, personal information, local databases, caches, downloads or binary releases.
6. For a new application, add a new isolated project folder, its own docs and tests, and a row in this index.
7. Keep status truthful: written specifications are not a completed implementation.

**Current assignment: BUILD THE UNIVERSAL PC GAME LAUNCHER.** Make a genuinely usable Windows application, not a static mockup. Read its detailed requirements and verify your changes.
