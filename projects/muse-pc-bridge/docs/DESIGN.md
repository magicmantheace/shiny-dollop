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
413 too large, 500 internal).

### GET /v1/status
Response:
```json
{
  "agent": "muse-pc-bridge", "version": "0.1.0",
  "hostname": "<pc name>", "platform": "Windows-11-...",
  "python": "3.12.x", "uptime_s": 123.4,
  "shell_default": "powershell",
  "file_root": "C:\\...\\agent\\bridge-files"
}
```

### POST /v1/exec
Request:
```json
{
  "command": "Get-ChildItem C:\\",
  "shell": "powershell",          // "powershell" | "cmd" | "posix";
                                  // default: powershell on Windows,
                                  // posix elsewhere
  "cwd": "C:\\work",              // optional; must exist
  "timeout_s": 120,               // optional; clamped to max_timeout_s
  "env": {"EXTRA": "1"}           // optional extra environment vars
}
```
`powershell` runs via `pwsh` when present, else `powershell`, always
with `-NoProfile -NonInteractive -Command`. `cmd` runs
`cmd /d /s /c`. `posix` runs `/bin/sh -c`.

Response:
```json
{
  "exit_code": 0,                 // null when timed_out
  "stdout": "...", "stderr": "...",
  "duration_ms": 812,
  "timed_out": false,
  "truncated": false              // true if a stream hit
                                  // max_output_bytes and was cut
}
```
On timeout the process (on POSIX, its process group) is killed and
whatever output was captured is returned with `timed_out: true`.
Commands run with the agent's full user privileges — that is the
point of the design, and the reason for the threat model below.

### GET /v1/file/list?path=<rel>
Lists one directory inside the file root. Response:
`{"path": "sub", "entries": [{"name": "a.txt", "type": "file", "size": 12}, ...]}`
sorted by name; `size` is null for directories.

### GET /v1/file/get?path=<rel>
Response: `{"path", "size", "sha256", "content_b64"}`. Files over
16 MiB are refused with 413 (use exec + the owner's own tooling for
bigger transfers, or a future chunked endpoint).

### POST /v1/file/put
Request: `{"path": "<rel>", "content_b64": "..."}`. Parent directories
are created. Response: `{"path", "size", "sha256"}`.

**Path safety:** all file paths are relative to `allowed_file_root`.
Absolute paths, drive-letter paths (Windows), and anything that
resolves outside the root (`..`) are rejected with 400. Note the file
endpoints are a convenience and an audit-friendly transfer channel —
they are **not** a security boundary against the exec endpoint, which
is full-shell by design.

## Audit log

Append-only JSONL at `logs/audit.jsonl` (configurable). One object per
line:

```json
{"ts": "2026-11-04T17:07:20.513Z", "event": "request",
 "ip": "100.64.0.9", "method": "POST", "path": "/v1/exec",
 "summary": "exec[powershell]: Get-ChildItem C:\\",
 "status": 200, "exit_code": 0, "duration_ms": 812}
```

- `event` is `request`, `auth_failed`, `server_start`, or
  `server_stop`.
- Exec summaries carry the shell and the command (truncated to 500
  chars); file summaries carry path, size, and sha256.
- The token and the `Authorization` header are **never** written.
- Writes are lock-guarded (threaded server) and failure-tolerant: a
  failed audit write prints a warning to the agent console instead of
  crashing the server.

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
4. **The kill switch is stopping the agent.** The v0 run model is a
   visible console window: window open = agent running. Close it (or
   Ctrl+C, or kill the process) and access ends immediately. There is
   no background service in v0 precisely so "is it running?" is
   always answerable at a glance.

Explicitly accepted risks (owner's decision): no per-command
approval, no command allowlist, no sandboxing of executed commands,
plain HTTP inside the tunnel (relying on WireGuard), and exec is not
confined to the file root (only the file endpoints are).

## Future work (not in v0)

- **Approval mode:** optional per-command owner confirmation in the
  console before exec runs.
- **Tailscale identity checks:** verify the caller's Tailscale node
  identity (via the local Tailscale API / `tailscale whois`) in
  addition to the token.
- **Chunked/streamed transfers** for files over 16 MiB, and streamed
  exec output for long-running commands.
- **File watching** on the file root to push change notifications.
- **Token scoping** (e.g. a read-only token for status/list/get).
- Windows service packaging — only if the owner ever prefers it over
  the visible-console model.
