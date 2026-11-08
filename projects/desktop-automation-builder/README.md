# Desktop Automation Builder

**Status:** MVP FUNCTIONAL / REVIEW READY (2026-10-23) — see `docs/IMPLEMENTATION_STATUS.md` for evidence.

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

## Run / install (developer)

```bash
cd app
npm ci
npm run build      # renderer bundle + main/preload compile to dist/
npx electron .     # launches the app (or: npm run smoke for the headless self-check)
```

Tests: `npm test` · Typecheck: `npm run typecheck` · Lint: `npm run lint`.

Windows installer packaging (NSIS) is **not yet produced** — no Wine on the build VM; the packaged main is verified via the smoke self-check. See `docs/IMPLEMENTATION_STATUS.md` for the implemented/unverified split.

## What the MVP does

Step-list flow editor (file copy, move-to-trash, folder create, run-approved-script from an explicit allowlist, log message) → sandboxed executor (all paths confined to the workflow's sandbox root; escapes rejected) → dry-run preview → explicit approval checkpoint → durable per-step run logs in SQLite → cancel + retry-from-failed-step. Workflows are versioned (every edit archives a snapshot) and export/import as versioned JSON (`formatVersion 1.0.0`). Files are never deleted outright — moves land in the sandbox's `.dab-trash/` folder.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
