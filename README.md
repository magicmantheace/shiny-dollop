# Meta Muse — Multi-Project Development Workspace

This repository is a permanent, **multi-project** workspace. Its root is an index and global instructions, not one shared application. Read [AGENTS.md](AGENTS.md) before changing anything.

## Existing projects — preserve their own development tracks

| Project | Directory | Status |
| --- | --- | --- |
| Universal PC Game Launcher | [`projects/universal-game-launcher/`](projects/universal-game-launcher/README.md) | Existing development; unmerged review branch/PR — do not overwrite |
| **Synveil — bootable desktop and safe installation** | [`projects/synveil/`](projects/synveil/README.md) | **CRITICAL — Muse current assignment; native desktop / A/B installation** |
| GitHub Development Command Center | [`projects/github-development-command-center/`](projects/github-development-command-center/README.md) | PARKED — do not implement without new authorization |
| Developmental-AI | [`projects/developmental-ai/`](projects/developmental-ai/README.md) | Imported 2026-10-27 from the standalone `magicmantheace/Developmental-AI` repo; **canonical building home per owner decision 2026-10-27** — development continues here (working line: `developmental-ai/standalone-policy-review`); the standalone repo is the pre-move archive |
| AthenZ | [`projects/athenz/`](projects/athenz/README.md) | Imported copy of the standalone AthenZ repo (main `ff3b407`); unmerged review PR — do not overwrite |
| Milky Way Colonization Simulator | [`projects/milky-way-colonization-sim/`](projects/milky-way-colonization-sim/README.md) | S0 data pipeline + viewer built on its foundation branch; unmerged, awaiting owner review — do not overwrite |
| Drabbit Pet | [`projects/drabbit-pet/`](projects/drabbit-pet/README.md) | In development — P0/P1 (design + pet-brain core) built on a review branch; desktop/Android slices planned |
| Muse PC Bridge | [`projects/muse-pc-bridge/`](projects/muse-pc-bridge/README.md) | v0 foundation on an unmerged branch; VM-tested only — not yet installed on the owner's PC |
| Game Asset Builder | [`projects/game-asset-builder/`](projects/game-asset-builder/README.md) | Fully local, no-API game asset pipeline (owner-commissioned 2026-11-06); scaffold + model bake-off on its own branch/PR — do not overwrite |

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
| 13 | Local AI Command Center | [`projects/local-ai-command-center/`](projects/local-ai-command-center/README.md) | MVP functional / review ready |
| 14 | Novel and Worldbuilding Manager | [`projects/worldbuilding-manager/`](projects/worldbuilding-manager/README.md) | MVP functional / review ready |
| 15 | Procedural Dungeon Designer | [`projects/procedural-dungeon-designer/`](projects/procedural-dungeon-designer/README.md) | MVP functional / review ready |
| 16 | AI Dungeon Master | [`projects/ai-dungeon-master/`](projects/ai-dungeon-master/README.md) | MVP functional / review ready |
| 17 | Crawl Live Spectator Desktop | [`projects/crawl-spectator-desktop/`](projects/crawl-spectator-desktop/README.md) | MVP functional / review ready |

**Current Muse assignment:** [Synveil first-boot handoff](projects/synveil/docs/MUSE_HANDOFF.md). Prioritize a real Synveil desktop, secure persistence, external-media installation, and A/B updates. The 17-app queue remains approved, but Synveil has the immediate development priority; preserve its existing branches and PRs.

## Independent project: AI Animation Studio

| Project | Directory | Status |
| --- | --- | --- |
| Stylized 3D AI Animation Studio | [`projects/ai-animation-studio/`](projects/ai-animation-studio/README.md) | Foundation scaffold and documentation, not production-ready; separate development track |

## Repository rules

1. Keep one application per `projects/<slug>/`; each owns its manifests, code, docs, tests and generated-file paths.
2. Before coding, declare the active project directory and follow root + project-specific `AGENTS.md`.
3. Never edit another existing project to implement an optional integration; use versioned interchange formats until a separate change is authorized.
4. Work on scoped feature branches, open reviewable PRs, and do not auto-merge or force-push.
5. Do not commit secrets, customer records, personal financial data, save files, local databases, cached models or generated releases.
6. Document verified behavior honestly: planned != implemented != tested.
7. Preserve the parked GitHub Development Command Center.
