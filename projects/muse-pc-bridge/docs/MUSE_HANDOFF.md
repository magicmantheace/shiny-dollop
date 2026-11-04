# Muse handoff — muse-pc-bridge

## What this is

A small Python (stdlib-only) agent the owner runs on his Windows PC so
Muse can do full-shell work on the PC over Tailscale, plus a thin
CLI client Muse uses from the VM. Full shell access with a mandatory
audit log is the owner's explicit decision (2026-11-04) — see
`docs/DESIGN.md` for the threat model.

## State (2026-11-04): v0 foundation built, VM-verified, NOT yet installed

**Version:** agent `0.1.0`. Branch: `muse-pc-bridge/foundation`.

### Implemented

- `agent/bridge_agent.py` — ThreadingHTTPServer agent:
  - `--init` writes `config.json` with a `secrets.token_urlsafe(32)`
    token, printed once; refuses to overwrite an existing config.
  - Bearer-token auth on every `/v1/*` route, compared with
    `hmac.compare_digest`; 401 JSON on failure. Token never logged.
  - Endpoints: `GET /v1/status`, `POST /v1/exec` (powershell via
    pwsh-or-powershell / cmd / posix; timeout with process kill;
    per-stream truncation at `max_output_bytes`), `GET /v1/file/list`,
    `GET /v1/file/get` (16 MiB cap → 413), `POST /v1/file/put`.
  - File paths confined to `allowed_file_root`: absolute paths,
    Windows drive-letter paths, and `..` escapes rejected with 400.
  - Audit: JSONL, one entry per request including `auth_failed`,
    plus `server_start`/`server_stop`; lock-guarded; a failed audit
    write warns on stderr instead of crashing the server.
  - Loud stderr warning if `host` is `0.0.0.0`/`::`.
  - Ctrl+C shuts down cleanly with a `server_stop` audit line.
- `client/bridge_client.py` — `status`, `exec`, `list`, `get`, `put`
  subcommands; base URL/token from flags or `MUSE_PC_BRIDGE_URL` /
  `MUSE_PC_BRIDGE_TOKEN`; verifies sha256 on get/put; non-zero exit
  on HTTP errors with the error body printed.
- `scripts/start-bridge.cmd` — visible console = running indicator +
  kill switch. `scripts/install-autostart.ps1` — OPTIONAL logon task
  that opens the same visible console.
- `config.example.json`, `.gitignore` (config.json, logs/,
  bridge-files/ are never committed).

### Verified (Muse's Linux VM, Python 3.12.3, 2026-11-04)

- `python3 -m unittest discover -s tests -v` → **10 tests, OK**
  (auth 401s, status fields, exec echo/exit-code/timeout, put→get
  round-trip with sha256, list, path-escape rejection with no file
  created outside the root, audit contents + token-absence).
- Manual smoke: `--init` generated config + 43-char token; a live
  agent on 127.0.0.1:8765 served the client CLI for status, put,
  list, get, and exec; the audit log recorded the requests and did
  not contain the token.

### NOT verified (owner-PC only — do not claim otherwise)

- Windows execution: PowerShell/cmd shells, `start-bridge.cmd`
  console behavior, NTFS path handling.
- Binding to a real Tailscale `100.x` address and reachability from
  the VM over the tailnet; Windows Firewall behavior.
- The autostart task on the owner's machine.
- The test suite passing under Windows Python (it is written to, via
  per-platform shell selection, but has not run there yet).

## Decisions on record

- **Full shell, no allowlist** — owner, 2026-11-04. Do not quietly
  reintroduce restrictions; changes to this posture need the owner.
- **Audit log is non-negotiable** — every request, including auth
  failures and lifecycle events.
- **Tailnet-only binding** by configuration; wildcard bind warns.
- **Visible console run model** in v0 — no Windows service — so the
  running state and kill switch are obvious.
- Stdlib only; no third-party dependencies anywhere in the project.

## Next steps

1. Owner installs on the PC per `docs/INSTALL_WINDOWS.md` (includes
   running the suite on Windows and a local client check), then hands
   Muse the tailnet IP + port + token out-of-band.
2. Muse verifies `status` from the VM over the tailnet and records
   the result here.
3. First real task through the bridge; review the PC-side audit log
   with the owner afterward.
4. Possible v0.2 (see DESIGN future work): approval mode, Tailscale
   identity checks, chunked transfers.
