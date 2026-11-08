# Design — muse-pc-bridge

## Purpose

Let Muse (Nyx, running on a separate Linux VM) do real work on the
owner's Windows PC — run commands, move files, check results — without
a human relaying every step. The owner considered restricted/allowlist
designs and explicitly chose **full shell access with a mandatory
audit log** (2026-11-04). This document describes how that choice is
implemented and what protects it.

## Architecture

```
Owner's Windows PC                          Muse's Linux VM
┌──────────────────────────────┐            ┌─────────────────────────┐
│ bridge_agent.py              │  Tailscale │ bridge_client.py        │
│  ThreadingHTTPServer         │◄══════════►│  urllib, token from env │
│  binds to PC's 100.x IP:8765 │  (WireGuard│                         │
│                              │   tunnel)  │                         │
│  ├─ exec: powershell/cmd     │            └─────────────────────────┘
│  ├─ files: bridge-files/     │
│  └─ audit: logs/audit.jsonl  │
└──────────────────────────────┘
```

- **Agent** (`agent/bridge_agent.py`): one Python file, stdlib only.
  Long-running HTTP server. Started manually via
  `scripts/start-bridge.cmd` (visible console) or, optionally, by a
  logon task.
- **Supervisor forms (v1.1 topology)**: one `Supervisor` core
  (`agent/supervisor.py`) — crash restart, staged-update apply with
  health check and rollback, `supervisor-status.json`, and (since
  v1.1) publishing of `display-state.json` — runs in three forms:
  a visible **console** (the original kill-switch form), a
  **headless core** (`--headless`, pythonw, started at machine boot
  by the "Muse PC Bridge (core)" Scheduled Task as SYSTEM, before
  any logon), and embedded in the **avatar GUI**
  (`agent/supervisor_gui.py`). When a core already answers, the GUI
  **attaches display-only** instead of starting a second supervisor:
  closing the avatar then leaves the bridge running, and the window
  says so. The headless core never does GUI work; display-state
  publishing is the supervisor's, so the file local apps read stays
  fresh with no window open.
- **Client** (`client/bridge_client.py`): thin CLI used by Muse.
  Reads `MUSE_PC_BRIDGE_URL` / `MUSE_PC_BRIDGE_TOKEN` from the
  environment.
- **Transport**: plain HTTP *inside* the Tailscale tunnel. Tailscale
  provides encryption and peer authentication at the network layer;
  the bearer token authenticates at the application layer. No TLS
  termination is configured on the agent itself, deliberately — the
  agent must never be exposed outside the tailnet, where plain HTTP
  would be unacceptable.

## Wire protocol (v1)

All requests to `/v1/*` require header `Authorization: Bearer <token>`.
All bodies are JSON. Errors are `{"error": "<message>"}` with a
matching HTTP status (400 bad request, 401 unauthorized, 404 missing,
413 too large, 429 rate-limited, 500 internal, 501 platform-limited).

### GET /v1/status
Response (agent `1.0.0`; v0 fields retained):
```json
{
  "agent": "muse-pc-bridge", "version": "1.0.0",
  "hostname": "<pc name>", "platform": "Windows-11-...",
  "python": "3.12.x", "uptime_s": 123.4,
  "shell_default": "powershell",
  "file_root": "C:\\...\\agent\\bridge-files",
  "file_roots": {"default": "C:\\...\\agent\\bridge-files"},
  "capabilities": ["jobs", "processes", "sessions", "screenshot",
                   "input", "clipboard", "uia", "files.chunked",
                   "files.hash", "audit.tail", "update.stage"],
  "platform_limited": [],
  "jobs": {"running": 0, "total": 3},
  "processes": {"alive": 0, "tracked": 0},
  "sessions_open": 0,
  "disk": {"total_bytes": 0, "free_bytes": 0},
  "audit": {"path": "...", "bytes": 12345}
}
```
`capabilities` lists what this agent on this platform can do;
Windows-only services appear in `platform_limited` (and return 501)
on other platforms.

Since v1.1 the status body also carries **`uac_prompt`**:
`{"active": bool, "since": <ISO timestamp or null>}` — whether a
UAC elevation/consent prompt is currently awaiting the owner on
the PC (detected by the presence of `consent.exe`, polled every
`uac_poll_interval_s`, default 2 s; always inactive off Windows).
Presence only: the agent never reads the prompt's contents.
Transitions are audited as `uac_prompt_shown` /
`uac_prompt_cleared` events, and the avatar maps an active prompt
to its alert art with the label "Approval needed at PC".

### POST /v1/exec — jobs (v1)
Exec is a **job**. Submitting returns `202` with a `job_id`
immediately; the command runs to completion on the agent even if
the client disconnects. Request:
```json
{
  "command": "Get-ChildItem C:\\",
  "shell": "powershell",          // "powershell" | "cmd" | "posix";
                                  // default: powershell on Windows,
                                  // posix elsewhere
  "cwd": "C:\\work",              // optional; must exist
  "timeout_s": 120,               // optional job timeout (a job
                                  // property); 0 = no deadline,
                                  // otherwise clamped to max_timeout_s
  "env": {"EXTRA": "1"},          // optional extra environment vars
  "wait_s": 10                    // optional: block up to N seconds
                                  // and return the job inline (the
                                  // v0 one-call shape, plus job_id);
                                  // "wait": true waits for completion
}
```
`powershell` runs via `pwsh` when present, else `powershell`, always
with `-NoProfile -NonInteractive -Command`. `cmd` runs
`cmd /d /s /c`. `posix` runs `/bin/sh -c`.

Job object (from submit, `GET /v1/jobs/{id}`, or `GET /v1/jobs`):
```json
{
  "job_id": "…", "state": "done",   // queued|running|done|failed|killed
  "exit_code": 0,                   // null when timed_out (v0 contract)
  "stdout": "...", "stderr": "...",
  "stdout_bytes": 812, "stderr_bytes": 0,   // logical totals
  "timed_out": false, "truncated": false,
  "duration_ms": 812
}
```
`GET /v1/jobs/{id}?stdout_offset=N&stderr_offset=M&max_bytes=K`
returns output incrementally by byte offset — the poll contract the
client library uses. `POST /v1/jobs/{id}/cancel` kills the job's
process tree. On timeout the process tree is killed and the job ends
`failed` with `timed_out: true`. Output is captured per stream up to
`job_output_cap_bytes` (default 8 MiB), offset-stable. Commands run
with the agent's full user privileges — that is the point of the
design, and the reason for the threat model below.

### Detached processes (v1)
`POST /v1/processes` spawns a long-lived process detached from any
request; its stdout/stderr go to per-process log files under the
state dir. `GET /v1/processes`, `GET /v1/processes/{id}?tail_bytes=N`,
`POST /v1/processes/{id}/kill`. The registry persists to
`state/processes.json`; after an agent restart, tracked processes
are reported by OS pid liveness.

**GUI mode (v1.1):** with `"gui": true`, the request names an
`executable` (plus optional `args` list) instead of a shell
`command`, and the agent spawns the executable **directly**. A
shell-wrapped spawn cannot track a GUI application — the wrapper
exits as soon as it hands off to the GUI exe, so the app reported
dead instantly (hit with the Godot launches, 2026-11-06). In GUI
mode the tracked pid IS the application; on Windows the spawn also
requests breakaway from any job object that dies with the agent,
retrying without that flag when the job refuses. Records and
responses carry `"gui": true/false`. A command string is not
accepted in GUI mode — it cannot be split into argv safely.

### Session broker (v1.1, Codex-fix)
Desktop routes — `GET /v1/screenshot`, `POST /v1/input`,
`POST /v1/uia`, `GET|POST /v1/clipboard`, GUI-mode process spawns
and the process records they own — act on the **interactive**
desktop. An agent in Windows session 0 (the SYSTEM boot core) must
not serve them locally: it would capture and inject into the
services desktop. Instead it **brokers** them to the session
helper (`agent/session_helper.py`), a loopback-only HTTP server
hosted by the avatar process in the owner's logon session:

- the helper serves ONLY the desktop routes (everything else
  404s), with the same token, and registers itself in
  `state/session-helper.json` (port, pid, session id, 5 s
  heartbeat); the agent trusts only a fresh registration with a
  live pid outside session 0;
- the agent forwards the request verbatim and returns the
  helper's response; **both sides audit** — the agent's entry is
  marked `"via": "session-broker"`, the helper's (same audit log)
  `"via": "session-helper"`;
- GUI process records live with the helper (its own registry under
  `state/session-helper/`); inspect/kill for an id the agent does
  not own are brokered too;
- `GET /v1/processes` and the `/v1/status` process counts merge
  the helper's records (tagged `via: session-helper`), so a
  brokered process stays discoverable after its spawn response is
  gone; a registered helper that does not answer degrades the
  merge to local-only rather than failing the request. The two
  merges are budgeted differently: the listing fetches generously
  (5 s), while `/v1/status` — whose readers time out at 1.5 s
  (avatar) and 3 s (the supervisor's update health check, whose
  failure can roll back a healthy update) — serves a fresh-enough
  last-known merge (2 s), backs off briefly after a failed fetch,
  and otherwise makes one sub-second (0.75 s) fetch attempt, so a
  live-but-hung helper can never make a healthy agent look dead;
- exactly one helper owns a state directory: `SessionHelper`
  holds an OS exclusive lock on `state/session-helper-owner.lock`
  for its lifetime (released on stop or process death), a second
  start against the same directory is refused, and an attaching
  avatar window reuses a live registration instead of starting a
  rival helper — two helpers would overwrite the one registration
  while their process registries diverged, losing brokered
  processes;
- with no helper registered, a session-0 agent answers these
  routes **501** with the reason, rather than touching the wrong
  desktop; an agent already in the interactive session (console /
  avatar own-form) serves them directly, as before. Config
  `"session_broker": false` disables brokering. `/v1/status`
  reports `session_helper: {registered, session_id}`.

### Wake-on-LAN (v1.1)
`POST /v1/wol` with `{"mac": "AA:BB:CC:DD:EE:FF", "broadcast":
"192.168.1.255", "port": 9}` (broadcast/port optional; defaults
255.255.255.255 and 9) sends the 102-byte magic packet by UDP
broadcast **from the agent machine**, for waking *other* machines
on its LAN. Token-authed and audited like every route; advertised
as the `wol` capability. The honest limit: a sleeping PC runs no
agent, so **the bridge cannot wake its own host** — waking the
bridge PC itself requires a sender on some other always-on LAN
device (or an awake Tailscale peer on that LAN); `scripts/wol-send.py`
is that sender, and its docstring lists the target-side
prerequisites (BIOS WoL, NIC wake permission, wired Ethernet).

### Interactive sessions (v1)
`POST /v1/sessions` opens a shell session; `GET /v1/sessions/{id}`
reads merged output by offset; `POST /v1/sessions/{id}/input`
writes stdin (`data` or `data_b64`, optional `close_stdin`);
`POST /v1/sessions/{id}/close` ends it. POSIX uses a real PTY from
the stdlib; **Windows uses pipes** (the stdlib has no ConPTY), so
Windows sessions are line-oriented — an honest limitation. Idle
sessions are reaped after `session_idle_timeout_s` (default 1800).

### Eyes and hands (v1, Windows agent)
- `GET /v1/screenshot?format=png|bmp&monitor=N&region=x,y,w,h` —
  captured **inside the agent process** via ctypes GDI
  (BitBlt/GetDIBits) with a pure-Python PNG encoder. No script-based
  screen capture exists anywhere in this design (the owner's
  antivirus blocked that pattern and he chose otherwise — do not
  reintroduce it).
- `POST /v1/input` — a list of actions (mouse move/down/up/click/
  drag, named keys, key combos, Unicode text, sleep, cursor query)
  injected via ctypes `SendInput`.
- `GET`/`POST /v1/clipboard` — clipboard text via ctypes
  (`CF_UNICODETEXT`).
- `POST /v1/uia` — UI Automation via the agent's bundled, fixed
  helper (`agent/helpers/uia.ps1`): actions `windows`, `tree`,
  `find`, `invoke`, `get_value`, `set_value`. Clients supply JSON
  parameters only, never script text.

### GET /v1/file/list?path=<rel>
Lists one directory inside the file root. Response:
`{"path": "sub", "entries": [{"name": "a.txt", "type": "file", "size": 12}, ...]}`
sorted by name; `size` is null for directories.

### GET /v1/file/get?path=<rel>
Response: `{"path", "size", "sha256", "content_b64"}`. Whole-file
requests over 16 MiB are refused with 413 pointing at ranged reads:
`?offset=N&length=K` returns a slice (`length` capped at 64 MiB per
call) for resumable downloads of any size.

### POST /v1/file/put
Request: `{"path": "<rel>", "content_b64": "..."}`. Parent directories
are created. Response: `{"path", "size", "sha256"}`.

### Chunked uploads (v1)
`POST /v1/file/upload/start` `{"path", "size", "sha256"?,
"chunk_bytes"?}` → `201` with an `upload_id` (the destination is
validated up front; the chunk size is clamped to 64 KiB–16 MiB).
`PUT /v1/file/upload/{id}/{index}` uploads one raw chunk (exact
length enforced). `GET /v1/file/upload/{id}` reports received
chunks — uploads are persisted under `state/uploads/` and survive
an agent restart, so transfers resume. `POST
/v1/file/upload/{id}/complete` assembles the file, verifies size
and SHA-256, and places it atomically; `DELETE
/v1/file/upload/{id}` discards it.

### Hashes and recursive ops (v1)
- `GET /v1/file/hash?path=<rel>` — streamed server-side SHA-256:
  `{"path", "size", "sha256"}`.
- `GET /v1/file/tree?path=<rel>&max_depth=&max_entries=` — recursive
  listing with truncation flags.
- `POST /v1/file/mkdir` `{"path"}`; `POST /v1/file/move`
  `{"from", "to", "from_root"?, "to_root"?}`; `POST /v1/file/delete`
  `{"path", "recursive"?}` (directories require `"recursive": true`).

**Multiple roots (v1):** config `file_roots` is a list of
`{"name", "path"}`; the legacy `allowed_file_root` becomes the root
named `default`. Every file endpoint accepts an optional root name
(query `root=` or JSON `"root"`). Confinement is enforced **per
root**.

**Path safety:** all file paths are relative to their root.
Absolute paths, drive-letter paths (Windows), and anything that
resolves outside the root (`..`) are rejected with 400. Roots
themselves cannot be moved or deleted. Note the file endpoints are
a convenience and an audit-friendly transfer channel — they are
**not** a security boundary against the exec endpoint, which is
full-shell by design.

### Self-update (v1)
`GET /v1/update/status` reports staged/applied update state.
`POST /v1/update/stage` `{"source", "sha256", "version"}` downloads
or copies a release bundle (a `.zip` with a `bridge-release.json`
manifest), verifies its SHA-256, and extracts it zip-slip-guarded
under `state/staging/<version>/`. **The agent only stages.** The
supervisor applies a staged update at a restart boundary — backing
up the replaced files first — then health-checks the new agent and
**rolls back automatically** if the health check fails.

## Audit log

Append-only JSONL at `logs/audit.jsonl` (configurable). One object per
line:

```json
{"ts": "2026-11-04T17:07:20.513Z", "event": "request",
 "ip": "100.64.0.9", "method": "POST", "path": "/v1/exec",
 "summary": "exec[powershell]: Get-ChildItem C:\\",
 "status": 200, "exit_code": 0, "duration_ms": 812}
```

- `event` is `request`, `auth_failed`, `job_finish`, `server_start`,
  or `server_stop`.
- Exec summaries carry the shell and the command (truncated to 500
  chars); file summaries carry path, size, and sha256.
- The token and the `Authorization` header are **never** written.
- Writes are lock-guarded (threaded server) and failure-tolerant: a
  failed audit write prints a warning to the agent console instead of
  crashing the server.

**v1 hardening (§5 of the v1 plan, owner-approved):**

- **Rotation:** when the current file would exceed
  `audit_max_bytes` (default 10 MiB), it is rotated to
  `audit.jsonl.1`, older files shift up, and at most `audit_keep`
  (default 5) rotated files are kept. Set either to 0 to disable.
- **Two writers, one log (v1.1):** the session helper appends to
  the same log through its own core. Rotation + append are
  serialized across both writers by a threading lock shared per
  log path within a process, plus an OS file lock on a sidecar
  (`audit.jsonl.lock`) across processes — so the size check and
  the archive renames cannot interleave into a double rotation
  that discards retained entries. If the file lock cannot be
  taken, the append proceeds unlocked with a console warning
  rather than dropping the entry.
- **Job completion entries:** every job completion writes a
  `job_finish` entry with the `job_id`, exit code, timed-out flag,
  per-stream byte totals, and the **SHA-256 of the captured stdout
  and stderr** — output can be verified against the log without
  storing the output itself. Request entries for job-related calls
  also carry `job_id` (and `output_sha256` where a single result is
  returned inline).
- **Audit tail:** `GET /v1/audit/tail?n=` (n clamped to 1–1000)
  returns the most recent entries of the current audit file.
- **Auth-failure rate limiting:** failures are counted per source
  IP in a sliding window (`auth_fail_limit` 5 per
  `auth_fail_window_s` 60 s). Past the limit, failures get `429`
  with `retry_after_s` and the block lasts `auth_block_s` (30 s,
  extended by repeat failures). Blocked attempts are **still
  audited** as `auth_failed` with `"rate_limited": true`. A
  successful auth clears the IP's failure history, and a blocked IP
  presenting the correct token still succeeds — the limiter targets
  guessing, not the owner.

## Threat model

The design has exactly four protections; everything else is the
owner's informed choice.

1. **The token is the key.** Anyone holding the bearer token has full
   shell access as the owner's user. It is generated with
   `secrets.token_urlsafe(32)` (256 bits), shown once at `--init`,
   stored only in `config.json` on the PC and in Muse's client
   environment. It is never committed to git, never written to the
   audit log, and handed over out-of-band. Rotation = delete
   `config.json`, re-run `--init`, hand over the new token.
2. **The tailnet is the perimeter.** The agent binds to the PC's
   Tailscale `100.x` address only — not the LAN, not the public
   internet. Only devices signed into the owner's tailnet can even
   reach the port. Binding to `0.0.0.0`/`::` is possible but prints a
   loud startup warning. Keep Tailscale ACLs tight; a compromised
   tailnet device plus a leaked token is game over.
3. **The audit log is the record.** Every request — including failed
   auth — is written before/with the response, with the command text.
   Reviewing `logs/audit.jsonl` shows everything Muse (or anyone
   with the token) did. The log lives on the PC, under the owner's
   control.
4. **The kill switch is stopping the agent.** The run model is a
   visible console window: window open = agent running. Close it (or
   Ctrl+C, or kill the process) and access ends immediately. The v1
   **supervised form** keeps exactly this property: the supervisor
   runs in its own visible console, restarts the agent on crash, and
   closing the supervisor console stops both. There is deliberately
   no hidden background mode, so "is it running?" is always
   answerable at a glance.

Explicitly accepted risks (owner's decision): no per-command
approval, no command allowlist, no sandboxing of executed commands,
plain HTTP inside the tunnel (relying on WireGuard), and exec is not
confined to the file root (only the file endpoints are).

## Future work (not in v1)

- **Tailscale identity checks:** verify the caller's Tailscale node
  identity (via the local Tailscale API / `tailscale whois`) in
  addition to the token.
- **File watching** on the file roots to push change notifications.
- **Token scoping** (e.g. a read-only token for status/list/get).

Explicit non-goals (owner's standing decisions): an approval mode
or command allowlist (full shell stands), and any script-based
screen-capture pattern (see the screenshot note above). Streamed
exec output and chunked transfers — v0 future work — shipped in v1
as offset-based job polling and chunked uploads; the supervised
service form shipped as `agent/supervisor.py` with the visible
console preserved.
