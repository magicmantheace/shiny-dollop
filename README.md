# Meta Muse — Multi-Project Development Workspace

This repository is a permanent, **multi-project** workspace. Its root is an index and global instructions, not one shared application. Read [AGENTS.md](AGENTS.md) before changing anything.

## Existing projects — preserve their own development tracks

| Project | Directory | Status |
| --- | --- | --- |
| Universal PC Game Launcher | [`projects/universal-game-launcher/`](projects/universal-game-launcher/README.md) | Existing development; unmerged review branch/PR — do not overwrite |
| GitHub Development Command Center | [`projects/github-development-command-center/`](projects/github-development-command-center/README.md) | PARKED — do not implement without new authorization |

## New Muse application queue — specifications only

**Status of every entry below:** PLANNED. The folders contain product definitions and Muse handoffs, **not built or tested applications**.

| Priority | Application | Directory | Status |
| --- | --- | --- | --- |
| 1 | Universal Game Save Manager | [`projects/game-save-manager/`](projects/game-save-manager/README.md) | Planned |
| 2 | Concrete Operations Manager | [`projects/concrete-operations-manager/`](projects/concrete-operations-manager/README.md) | Planned |
| 3 | Volumetric Concrete Mix Calculator | [`projects/volumetric-concrete-calculator/`](projects/volumetric-concrete-calculator/README.md) | Planned |
| 4 | PC Storage and Duplicate Finder | [`projects/storage-analyzer/`](projects/storage-analyzer/README.md) | Planned |
| 5 | Offline Personal Finance Simulator | [`projects/finance-simulator/`](projects/finance-simulator/README.md) | Planned |
| 6 | Household Inventory and Warranty Tracker | [`projects/household-inventory/`](projects/household-inventory/README.md) | Planned |
| 7 | Game Library Metadata Enricher | [`projects/game-metadata-manager/`](projects/game-metadata-manager/README.md) | Planned |
| 8 | Windows Game Performance Profiles | [`projects/game-performance-profiles/`](projects/game-performance-profiles/README.md) | Planned |
| 9 | Digital Product Template Factory | [`projects/digital-template-factory/`](projects/digital-template-factory/README.md) | Planned |
| 10 | Small Business Website Generator | [`projects/business-website-generator/`](projects/business-website-generator/README.md) | Planned |
| 11 | Personal Knowledge Vault | [`projects/personal-knowledge-vault/`](projects/personal-knowledge-vault/README.md) | Planned |
| 12 | Desktop Automation Builder | [`projects/desktop-automation-builder/`](projects/desktop-automation-builder/README.md) | MVP functional / review ready |
| 13 | Local AI Command Center | [`projects/local-ai-command-center/`](projects/local-ai-command-center/README.md) | Planned |
| 14 | Novel and Worldbuilding Manager | [`projects/worldbuilding-manager/`](projects/worldbuilding-manager/README.md) | Planned |
| 15 | Procedural Dungeon Designer | [`projects/procedural-dungeon-designer/`](projects/procedural-dungeon-designer/README.md) | Planned |
| 16 | AI Dungeon Master | [`projects/ai-dungeon-master/`](projects/ai-dungeon-master/README.md) | Planned |
| 17 | Crawl Live Spectator Desktop | [`projects/crawl-spectator-desktop/`](projects/crawl-spectator-desktop/README.md) | Planned |

**Start implementation with:** [Universal Game Save Manager](projects/game-save-manager/docs/MUSE_HANDOFF.md). Begin its real MVP first; do not simultaneously scaffold or claim completion for all projects.

## Repository rules

1. Keep one application per `projects/<slug>/`; each owns its manifests, code, docs, tests and generated-file paths.
2. Before coding, declare the active project directory and follow root + project-specific `AGENTS.md`.
3. Never edit another existing project to implement an optional integration; use versioned interchange formats until a separate change is authorized.
4. Work on scoped feature branches, open reviewable PRs, and do not auto-merge or force-push.
5. Do not commit secrets, customer records, personal financial data, save files, local databases, cached models or generated releases.
6. Document verified behavior honestly: planned != implemented != tested.
7. Preserve the parked GitHub Development Command Center.
