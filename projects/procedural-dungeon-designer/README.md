# Procedural Dungeon Designer

**Status:** MVP FUNCTIONAL / REVIEW READY — deterministic seeded dungeon generator with budgets, editor, persistence and versioned export, implemented and verified on Linux (see `docs/IMPLEMENTATION_STATUS.md`). Windows 11 behavior is implemented but not verified on target OS.

**Priority:** 15 of 17 in the approved intake queue.
**Category:** Game design / tabletop
**Repository workspace:** `projects/procedural-dungeon-designer/`

## Purpose

Generate original seeded, navigable dungeon maps with encounter and hazard budgets.

## First usable release (MVP)

Generate a seeded connected dungeon, inspect rooms, edit encounter placements, and export the same map deterministically.

## Full intended capabilities

- Seeds and reproducible layouts
- Connected rooms and corridors
- Theme/biome rules
- Traps, hazards and encounters
- Difficulty/loot budget controls
- Connectivity validator
- Map export and print view

## Proposed implementation direction

Deterministic generator library + map editor/preview; versioned JSON map export. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Exports dungeon manifests for AI Dungeon Master.

Use original assets and rules; do not depend on proprietary RPG content.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
