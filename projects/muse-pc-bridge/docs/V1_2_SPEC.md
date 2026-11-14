# Muse PC Bridge — v1.2 spec

**Status:** BUILT on branch `muse-pc-bridge/v1-2` (2026-11-13) —
all three items implemented in the §5 build order with their §4
tests; full suite green on Muse's Linux VM (see
`docs/MUSE_HANDOFF.md` and `docs/TEST_PLAN.md` for the run
record). **NOT deployed: production still runs v1.1.** The Windows
smoke on the owner's PC (non-elevated) and the production switch
remain owner-gated, per §4.

**Scope:** three owner-requested improvements on top of v1.1 (PR #47,
merged 2026-11-12):

1. **UAC pre-flight surfacing** — flag a job as likely to raise a UAC
   prompt *before* it starts, instead of discovering the stall mid-run.
2. **Audit log read access** — let the client read the JSONL audit log
   through the bridge, so completed work can be confirmed without extra
   permission steps on the PC.
3. **Resident queue runner** — a small on-PC runner that drains a queue
   of pre-approved jobs while Muse is not actively connected, so work
   keeps moving between sessions.

## 0. Invariants carried over (do not weaken)

- Stdlib-only Python, agent and client both.
- Bearer-token auth on every `/v1/*` route; the token is **never**
  written to the audit log, job files, or any output.
- The JSONL audit log is non-negotiable: every action the bridge takes
  is recorded, including everything the queue runner does.
- The agent binds only to the PC's Tailscale address.
- Full shell access is the owner's standing decision (2026-11-04); this
  spec adds no allowlist and removes none.
- **UAC remains the owner's click.** Nothing in v1.2 clicks, bypasses,
  or suppresses a consent prompt. The bridge detects and reports; the
  owner decides.
- The runner inherits the v1.1 boot topology (SYSTEM core +
  supervisor); no new service, scheduled task, or autostart entry.

## 1. UAC pre-flight surfacing

### Behaviour

- `POST /v1/exec` and `POST /v1/queue` responses gain a `uac` object:
  `{ "likely": bool, "reasons": [str], "consent_pending": bool }`.
- Assessment is computed **before** execution:
  - *Static heuristics* over the command/script text: installer
    invocations (`msiexec`, `setup*.exe`, `*.msi`), `Start-Process
    -Verb RunAs`, writes under `HKLM:`, `Program Files`, or
    `%SystemRoot%`, `net start|stop`, `sc config|create`, machine-scope
    `Set-ExecutionPolicy`, `dism`, `sfc`, `bcdedit`, `schtasks /create`
    with `/RU SYSTEM`, driver installs (`pnputil /add-driver`).
  - *Live state*: `consent_pending` reuses the v1.1 UAC consent
    detection — is a consent prompt already on screen?
- A request may set `"require_no_uac": true`. If the assessment says
  `likely`, the bridge **does not execute** and returns
  `409 { "error": "uac_likely", "uac": {...} }`. Default (flag absent)
  is unchanged v1.1 behaviour: execute and report the assessment.

### Honest limit

Heuristics cannot prove a negative. `likely: false` is advisory — a
command can still elevate indirectly. The client treats pre-flight as a
warning aid, not a guarantee, and the standing rule (warn the owner and
wait before UAC-likely commands) is unchanged.

## 2. Audit log read access

### Endpoint

`GET /v1/audit?since=<unix-ts>&limit=<n>` — token-authed like every
route.

- Returns the audit entries at/after `since`, oldest first, as a JSON
  array. `limit` defaults to 200, hard cap 1000; the response carries
  `next_since` for paging.
- The path read is the agent's **own configured audit file only** —
  never a request-supplied path. No arbitrary-file surface is added;
  for anything else the existing `/v1/file/*` sandbox rules apply.
- Read-only: no endpoint may truncate, rotate, or rewrite the log.

### Safety

- The token is never written to the log (invariant, §0), so returning
  stored lines adds no credential surface. A regression test seeds the
  token string into a command and asserts it appears in **neither** the
  audit file **nor** the endpoint output.
- Audit entries for audit reads themselves are written (the log records
  that it was read, by job/request id — not the token).

### Client

`bridge_client.py audit [--since TS] [--limit N]` printing one JSON
object per line.

## 3. Resident queue runner

### Shape

`agent/queue_runner.py`, stdlib-only, running as a thread inside the
existing core process. No new service or task; it inherits boot
survival and supervisor restart from v1.1.

Store, under the agent directory:

```
state/queue/
  pending/    one JSON file per queued job
  running/    the job currently executing (at most one)
  done/       completed jobs, with result summary
  failed/     failed / skipped / cancelled jobs, with reason
  PAUSED      presence of this file pauses the runner
```

### Job file

```json
{
  "id": "uuid",
  "submitted_at": 1794600000,
  "kind": "exec | script",
  "command": "…",                  // kind=exec
  "script": "bridge-files/x.ps1",  // kind=script, sandbox-relative
  "script_sha256": "…",            // required for kind=script
  "shell": "cmd",
  "timeout_s": 900,
  "uac_policy": "skip-if-likely",  // or "run-anyway"
  "on_failure": "stop",            // or "continue"
  "note": "free text, for the audit trail"
}
```

Scripts are **hash-pinned at submission**: the runner recomputes the
sha256 immediately before executing and refuses on mismatch
(`failed/`, reason `script_hash_mismatch`). What was approved is what
runs — a script edited between submit and run does not silently
execute.

### API

- `POST /v1/queue` — submit a job (token auth). Runs the §1 pre-flight
  assessment and stores it in the job's record.
- `GET /v1/queue` — counts + per-state job summaries.
- `DELETE /v1/queue/<id>` — cancel a **pending** job (a running job is
  cancelled through the existing job-cancel path).
- `POST /v1/queue/pause` / `POST /v1/queue/resume` — toggle the PAUSED
  file via the API. The owner can also create/delete `state/queue/
  PAUSED` directly on the PC: a local kill switch that needs no
  network and no token.

### Execution semantics

- **Strictly sequential** — one job at a time (matches the PC norm of
  one heavy stage at a time on the GPU).
- Execution reuses the same job executor as `/v1/exec`, so output
  capture, timeouts (with process-tree kill), and audit format are
  identical whether Muse is connected or not.
- The runner checks `PAUSED` before every job. Owner pause orders
  (including an in-chat "pause") are effected by setting PAUSED; the
  runner takes no new work until resumed. A job already running is not
  killed by pausing — killing is the existing explicit cancel path.
- `uac_policy: "skip-if-likely"` (the default): if pre-flight says
  likely, the job goes straight to `failed/` with reason `uac_likely`
  and an audit entry — it never stalls the queue waiting for a click
  nobody is there to make. If a consent prompt appears mid-run, v1.1
  detection marks the job `waiting_uac`; after a bounded grace
  (config `queue_uac_grace_s`, default 120 s) the job is failed with
  reason `uac_timeout` and the runner moves on. The runner **never**
  clicks consent.
- **Restart recovery:** on core start, a job found in `running/` is
  moved to `failed/` with reason `core_restarted`. Jobs are **not**
  silently re-run after a crash — re-queueing is a deliberate act.
- Every transition (submitted, started, finished + exit code, failed +
  reason, paused, resumed, cancelled) is an audit entry carrying the
  job id.

### Explicit non-goals

- No autonomous decision-making. The runner executes only queued,
  hash-pinned steps. Judgment stays with Muse and the owner.
- No scheduling on the PC. When something runs remains the client's
  (Muse's) side of the fence; the queue is a buffer, not a calendar.
- No elevation. The runner works in the core's existing context; UAC
  stays the owner's click (§0).

## 4. Tests (all must pass before the version bumps)

- Pre-flight classifier: positive/negative cases per heuristic family;
  `require_no_uac` returns 409 and executes nothing.
- Audit endpoint: auth required; `since`/`limit` paging; token-absence
  regression (§2); read attempts cannot escape the configured file.
- Queue lifecycle: submit → run → done; `on_failure` stop vs continue;
  hash-mismatch refusal; PAUSED blocks new starts and resumes cleanly;
  restart recovery moves `running/` → `failed/core_restarted`;
  `skip-if-likely` never executes; `waiting_uac` grace expiry.
- Full existing suite stays green; agent reports `1.2.0` only when all
  three items pass; Windows smoke on the PC (non-elevated) before the
  production switch — which, as with v1.1, is the owner pressing go.

## 5. Build order

1. **Audit read (§2)** — first: it makes verifying the other two
   remotely much easier.
2. **UAC pre-flight (§1)** — the queue's skip policy depends on it.
3. **Queue runner (§3)**.

One branch, `muse-pc-bridge/v1-2`; each item lands with its tests
before the next starts. No production change until the whole version
passes and the owner says go.
