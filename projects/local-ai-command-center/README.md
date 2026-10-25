# Local AI Command Center

**Status:** MVP FUNCTIONAL / REVIEW READY — working application in `app/` on branch `local-ai-command-center/mvp` (unmerged). 38/38 automated tests pass; end-to-end workflow verified via the packaged main's smoke mode on Linux. Windows 11 behavior is implemented but not verified on target OS. See [implementation status](docs/IMPLEMENTATION_STATUS.md).

**Priority:** 13 of 17 in the approved intake queue.
**Category:** AI operations desktop
**Repository workspace:** `projects/local-ai-command-center/`

## Purpose

Supervise local LLM runtimes and constrained coding agents with queues, reviews and resource policies.

## First usable release (MVP)

Configure an installed local model endpoint, submit a text task, review output/logs, and cancel the task; provide useful offline setup mode.

## Full intended capabilities

- Local endpoint discovery and health checks
- Model selection and comparison
- Task queue and cancellation
- CPU/RAM/GPU resource monitoring
- Scoped agent workspaces
- Diff/patch proposal review
- Approval and audit log
- No-cloud default and bounded optional integrations

## Proposed implementation direction

Windows desktop UI, local runtime adapters, subprocess metrics and constrained task/workspace API. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Later optional import from Personal Knowledge Vault and approval-mediated actions from Desktop Automation Builder.

No autonomous unrestricted write access, credentials, shell or network privileges; no paid inference by default.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
