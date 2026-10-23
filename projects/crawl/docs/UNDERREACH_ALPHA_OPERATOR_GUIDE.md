# Underreach Alpha 0.1 Operator Guide

The Alpha runtime is a local-only spectator build. One authoritative process
advances a deterministic Descent and durable Ledger. The Feed API, viewer, live
bridge, automatic camera, and Unreal consumer are supervised projections; none
can change canonical simulation state.

## Start

From `D:\CrawlTesting`:

```powershell
.\scripts\start-underreach-alpha.ps1
```

The default `alpha` profile starts the whole stack, serves the viewer at
`http://127.0.0.1:8011`, checkpoints once per minute, rotates controlled logs,
and runs until Ctrl+C or a clean stop request.

Profiles:

- `-Profile qa`: accelerated, dense local validation with Unreal and viewer.
- `-Profile alpha`: unattended real-time Alpha runtime with Unreal and viewer.
- `-Profile headless`: simulation, Ledger, bridge planning, and checkpoints; no HTTP or Unreal.

Use a different `-StateDirectory` when intentionally running an isolated QA
session. A state directory has a single authoritative owner.

## Health

The compact viewer header reports overall runtime state, uptime, presentation
lag, Unreal connection, and checkpoint age. The full read-only payload is:

```text
GET http://127.0.0.1:8011/api/feed/runtime/health
```

States are `starting`, `healthy`, `degraded`, `recovering`, `failed`,
`stopping`, and `stopped`. Non-authoritative components are restarted and
reconnected. A canonical recovery proceeds only from a digest-valid checkpoint
whose exact Ledger prefix exists in SQLite.

## Checkpoints and resume

Default state layout:

```text
unreal/CrawlPresentation/Generated/runtime/
  runtime.lock
  state/runtime.json
  state/underreach.sqlite3
  checkpoints/latest.json
  checkpoints/checkpoint-<tick>-<digest>.json
  logs/
```

Checkpoints are written to a temporary file, flushed, validated, atomically
renamed, and only then promoted by `latest.json`. The newest 12 are retained.
The SQLite Ledger remains complete canonical truth; the checkpoint stores the
complete Descent state and verifies its exact event prefix with ID and content
digests.

Resume after a clean stop or recoverable crash:

```powershell
.\scripts\start-underreach-alpha.ps1 -Resume
```

Never delete SQLite while keeping checkpoints. Resume intentionally fails when
the durable canonical Ledger prefix cannot be proven.

## Clean stop

Ctrl+C performs the protected shutdown sequence. From another terminal, use:

```powershell
.\scripts\stop-underreach-alpha.ps1
```

The stop helper validates that the lock PID belongs to the Underreach runtime
and writes a scoped stop request. It does not kill a process. Shutdown stops new
controls, writes a final checkpoint, flushes persistence, closes presentation
components, and writes the final report.

## Validation and soak

Short fault/recovery/resume validation:

```powershell
.\scripts\run-underreach-alpha-validation.ps1
```

Minimum acceptance soak:

```powershell
.\scripts\run-underreach-alpha-soak.ps1 -Hours 2 -FaultInjection
```

The soak runner rejects durations below two hours. Alpha diagnostics are lean:
it does not continuously render video. Metrics are appended to
`unreal/CrawlPresentation/Generated/runtime_soak_metrics.jsonl`; the final report
is `unreal/CrawlPresentation/Generated/underreach_alpha_runtime_report.json`.

## Recovery policy

- Viewer outage: the page returns a temporary recovery response; simulation continues.
- Feed/API outage: HTTP is restarted against durable state; viewer polling reconnects.
- Unreal outage: the consumer restarts from a current bootstrap/reconnect cursor; obsolete presentation-only backlog is skipped.
- Simulation exception: dependent presentation degrades while the last valid canonical checkpoint and exact Ledger prefix are validated and restored.
- Unprovable canonical restore: runtime fails clearly. It never invents or skips Ledger truth.

UE 5.8 can return a non-zero shutdown code after producing valid artifacts.
Operational health therefore uses fresh heartbeat/result files and their
validated content, not the editor exit code alone.
