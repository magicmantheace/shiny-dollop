# AI Dungeon Master

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 16 of 17 in the approved intake queue.
**Category:** Tabletop RPG desktop
**Repository workspace:** `projects/ai-dungeon-master/`

## Purpose

Support offline-capable tabletop campaigns with auditable rules, dice, memory, NPCs and optional local AI narration.

## First usable release (MVP)

Create a campaign and characters, roll dice, run initiative/combat with logged state, save, and resume.

## Full intended capabilities

- Campaign and session records
- Character sheets and stats
- Transparent dice engine
- Initiative and encounter state
- NPC/location memory
- Inventory and session notes
- Optional local AI speech/narration
- Versioned ruleset packs and import

## Proposed implementation direction

Deterministic campaign-state engine + local UI; optional local-model narration adapter. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Can import approved character/world exports from Worldbuilding Manager and dungeon manifests from Procedural Dungeon Designer.

No unlicensed proprietary rulebooks; AI flavor is never the authoritative rules engine.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
