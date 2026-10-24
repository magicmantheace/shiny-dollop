# Test plan — Local AI Command Center

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Mock model and real local endpoint adapter checks
- Unavailable model and timeout behavior
- User rejection cannot apply a patch
- Workspace path containment and permissions
- Resource limit and task cancellation

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Configure an installed local model endpoint, submit a text task, review output/logs, and cancel the task; provide useful offline setup mode.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

## Verification record — 2026-10-23 (MVP, branch `local-ai-command-center/mvp`)

**Environment:** Linux VM, Node 24, Electron 45 under Xvfb for smoke. Fixtures/synthetic data only. Windows 11 behavior is **implemented but not verified on target OS**.

**Commands run (from `projects/local-ai-command-center/app/`), all after a clean `npm install`:**

| Command | Result |
|---|---|
| `npm test` | **38/38 tests pass** (9 files: 27 backend + 11 renderer) |
| `npm run typecheck` | Clean |
| `npm run lint` | Clean (after removing one unused import in `electron/main/ipc.ts`) |
| `npm run build` | Green (Vite renderer bundle + `tsc` main/preload) |
| `npm run smoke` | **SMOKE PASS** — packaged main printed `SMOKE_OK` under Xvfb |

**Scenario coverage (automated):**

- Mock-adapter task success path incl. propose-fence echo → proposal created with diff
- Unavailable endpoint (`http://127.0.0.1:1`): health returns `ok:false`; task fails with `ENDPOINT_UNREACHABLE`
- Timeout: signal-ignoring hanging adapter + small `timeoutMs` → task fails `ENDPOINT_TIMEOUT`
- Cancellation: running `[mock:hang]` task → `cancelled`, audit contains `task.cancelled`; queued-task cancel also covered
- Workspace containment: `../evil`, nested `a/../../evil`, absolute paths → `PATH_OUTSIDE_WORKSPACE`; escaping propose path → no proposal, task completes, audited
- Patch rejection cannot apply: reject → file absent; approve → exact content written; re-deciding → `PROPOSAL_NOT_PENDING`
- Malformed/oversized input: empty prompt → `TASK_INVALID`; prompt > 32,000 chars → `INPUT_TOO_LARGE`; non-loopback config URL → `CONFIG_INVALID`
- Persistence across restart: config, completed task + output, and audit entries survive DB close/reopen
- Audit append-only: raw SQL `UPDATE`/`DELETE` on the audit table throw (trigger-enforced)
- Resources: fake OS layer maps fields; GPU reported `unavailable` with reason; zero load average → `null`
- Renderer: config/health-offline banner, submit, cancel, approve, reject, audit rendering — 11 hermetic tests with a fake `window.lacc`

**End-to-end acceptance (smoke mode, real packaged main):** save mock config → health OK → submit task → completes with output/logs → submit hanging task → cancel → `cancelled` → propose task → reject → file does **not** exist → propose task → approve → file content on disk matches exactly → `SMOKE_OK`.
