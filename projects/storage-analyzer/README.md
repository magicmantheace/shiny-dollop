# PC Storage and Duplicate Finder

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 4 of 17 in the approved intake queue.
**Category:** Windows utility
**Repository workspace:** `projects/storage-analyzer/`

## Purpose

Understand drive usage and duplicate files with non-destructive analysis and transparent evidence.

## First usable release (MVP)

Choose a directory, view ranked file/folder sizes and verified duplicate groups, cancel scans, and export a report; no deletion.

## Full intended capabilities

- Folder and drive-space treemap/list
- Large-file filtering
- Size-first and hash-confirmed duplicate groups
- Search and file-type summaries
- Exclusion rules and protected-path warnings
- Cancellable scans with progress
- CSV/JSON results and rescan comparison

## Proposed implementation direction

Windows desktop UI plus cancellable background filesystem indexer and SHA-256 duplicate verification. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Standalone.

Initial MVP is read-only. Never follow reparse points into loops; no system-directory modifications; clearly label stale results.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
