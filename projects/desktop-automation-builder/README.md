# Desktop Automation Builder

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 12 of 17 in the approved intake queue.
**Category:** Windows automation
**Repository workspace:** `projects/desktop-automation-builder/`

## Purpose

Create supervised repeatable automation flows for files, scripts and applications.

## First usable release (MVP)

Build a simple non-destructive file-copy workflow, preview its actions, approve, run, inspect log, and retry safely.

## Full intended capabilities

- Node-based or step-list workflow authoring
- Triggers and conditions
- File and folder actions
- Approved process/script steps
- Dry-run and explicit approval checkpoints
- Retry policy and cancellation
- Workflow versioning and exports

## Proposed implementation direction

Desktop flow editor and sandboxed/permissioned workflow executor with durable logs. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Optional future permission-mediated action interface for Local AI Command Center.

No unrestricted shell execution or invisible background persistence; no privileged/destructive actions without separate explicit approval.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
