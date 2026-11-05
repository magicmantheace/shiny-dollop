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
4. **v1 plan recorded** in `docs/V1_PLAN.md` (2026-11-04, owner's
   direction): async jobs, native screenshot + host input, service
   form + self-update, chunked files with server-side hashes, a real
   client library. It supersedes this earlier v0.2 sketch; an approval
   mode is an explicit non-goal in the plan (owner's full-access
   decision stands).

## State update (2026-11-04, later the same day)

- Installed on the owner's PC at `D:\shiny-dollop\projects\muse-pc-bridge`
  via the delegated install handoff; that install reported the suite
  passing 10/10 under Windows Python.
- Tailnet link verified firsthand by Muse from the VM: an
  unauthenticated request returns 401; authenticated status, exec,
  and a file put/list/get round trip (SHA-256 verified) all passed.
- The bridge then carried a full day of production work on the PC
  (packaged-app validation, Gradle and Godot runs, a QEMU guest
  update cycle). The friction observed that day is the evidence base
  for `docs/V1_PLAN.md`. Connection details (IP, token) stay
  out-of-band per the hard rules — never in this repo.

## State update (2026-11-04 night): v1 built, VM-verified, NOT yet staged on the PC

**Version:** agent `1.0.0`. Built overnight per `docs/V1_PLAN.md` in
five slice commits on `muse-pc-bridge/foundation` (draft PR #27):
S1 `1347b9a` (jobs/processes/sessions core), S2 `488bc29` (eyes/
hands), S3 `db4947c` (supervisor + self-update), S4 `b91d0b6`
(files/client), S5 `6440762` (hardening tests), plus this docs pass.
Every push verified via ls-remote. The live PC agent is untouched
and still runs v0.1.0.

### What v1 adds (all in the S1–S5 commits above)

- **Jobs:** `POST /v1/exec` submits a job (202 + job id); polling
  with byte offsets; cancel; `wait_s` keeps the v0 inline shape.
  Client disconnects can no longer lose work. Detached processes
  with log files + a persisted registry. Interactive sessions (PTY
  on POSIX, pipes on Windows — stdlib has no ConPTY).
- **Eyes/hands (Windows):** screenshot captured in-agent via ctypes
  GDI + a pure-Python PNG encoder (no script-based capture pattern
  anywhere — see DESIGN.md); SendInput host input; clipboard;
  UI Automation through the bundled fixed `agent/helpers/uia.ps1`.
  Off Windows these return 501 and list in `platform_limited`.
- **Lifecycle:** `agent/supervisor.py` (visible console, crash
  restart with backoff, supervisor-status.json) and self-update:
  the agent stages bundles (`agent/bridge_update.py`, SHA-256 +
  manifest verified, zip-slip guarded); the supervisor applies at a
  restart boundary with backup, health-checks, and **rolls back
  automatically** on failure. `scripts/bridge-service.ps1` manages
  a per-user logon task for the supervised form — owner-run only;
  **nothing was installed on the PC during this build**.
- **Files/client:** chunked resumable uploads (persisted under
  `state/`), ranged downloads, server-side SHA-256, tree/mkdir/
  move/delete, configurable multi-root file config. The client is
  now a real library (`BridgeClient`) with the v0 CLI preserved.
- **§5 audit changes (owner approved the plan as a whole; listed
  here distinctly for review):** (1) size-based audit rotation
  (`audit_max_bytes` 10 MiB, `audit_keep` 5; 0 disables); (2) new
  `job_finish` audit events carrying job_id, exit code, byte totals,
  and stdout/stderr SHA-256s; (3) job-related request entries may
  carry `job_id` / `output_sha256` fields; (4) new
  `GET /v1/audit/tail` endpoint; (5) auth-failure rate limiting —
  blocked attempts still audited as `auth_failed` with
  `"rate_limited": true`, correct-token requests from a blocked IP
  still succeed. No entries were dropped, reordered, or redacted;
  every `/v1/*` request is still audited.

### Verified (Muse's Linux VM, 2026-11-04 night)

- `python3 -m unittest discover -s tests` → **57 tests, OK
  (1 skip: the Windows-only real-capture test)** — 10 v0 + 47 v1
  across jobs/platform/lifecycle/files/hardening suites.
- Client CLI smoke against a local v1 agent: status, exec, put,
  get, jobs, hash, audit-tail, update-status all exit 0, hashes
  verified.

### NOT verified — PC staging still pending, and why

The overnight build session could reach the live bridge through
the tunnel (an unauthenticated request returned 401 as expected)
but the live token was **not present in the build session's
environment**, so no authenticated staging run happened. Nothing
was deployed to the PC; the live checkout, its config, and the
running v0.1 agent were not touched. Staging procedure, ready to
run from a session that has the token:

1. Copy the v1 `agent/` + `client/` files through the live bridge
   into `D:\bridge-work\bridge-v1-stage\` (never the live checkout).
2. In the staging dir on the PC, create a staging config (host =
   the PC's tailnet IP, **port 8766**, its own staging token kept
   only in the staging dir, file root + state + audit under the
   staging dir) and start the v1 agent detached.
3. Through the tunnel against 8766: status/capabilities; job
   submit/poll/cancel + submit-now-fetch-later; detached process
   spawn/kill; **real screenshot** (verify PNG magic + dimensions
   + SHA-256); hash endpoint; chunked round-trip of a multi-MB
   file via the new client library with SHA-256 verification;
   input limited to cursor query/zero-distance move; UIA window
   enumeration (+ a Notepad tree read, then close Notepad);
   clipboard set-then-restore.
4. Kill the staging agent, confirm 8766 is closed and 8765 still
   healthy, leave the staging files in place, record results here.

Also still unverified anywhere: the v1 suite under Windows Python,
the supervisor/service scripts on Windows, a staged self-update
apply cycle on the PC, and the plan's elapsed-time exit criteria
(reboot survival, a week unattended).

### Cutover (owner, when ready — see INSTALL_WINDOWS.md upgrade path)

The first cutover cannot use v1 self-update (v0.1 has no staging
endpoint): stop the v0 console, update the checkout, run the suite
on Windows, restart — via `scripts\start-bridge.cmd` (same as v0)
or the new supervised form. Installing the supervised logon task
(`scripts\bridge-service.ps1 -Action install`) may prompt for UAC —
that step is the owner's to run. A `v1.0.0` tag is prepared but NOT
applied; the owner applies it after cutover:

```
git tag -a v1.0.0 -m "muse-pc-bridge v1.0.0" <v1-tip-commit>
git push origin v1.0.0
```

## State update (2026-11-04 night, later): screenshot PNG defect — found by PC staging, fixed, VM-verified

The first PC staging run of v1 (second instance on port 8766) found
a defect the VM suite could not: `GET /v1/screenshot?format=png`
returned HTTP 500 with `{"error": "internal error: argument 1:
OverflowError: int too long to convert"}`, while `format=bmp` on the
same staging agent returned 200 with a real 1536x864 capture and a
correct SHA-256.

**Root cause** (`agent/bridge_agent.py`: `capture_screen`, plus
`_monitor_rects`): the ctypes GDI capture declared
`restype = ctypes.c_void_p` for the handle-returning calls — so
handles came back as full pointer-sized Python ints — but never
declared `argtypes` for any user32/gdi32 function. With undeclared
signatures, ctypes passes Python ints through the platform C long
conversion, which is 32-bit on Windows; any HDC/HBITMAP handle
value above INT_MAX then raises exactly the observed error at
argument 1 (a handle in every capture-path call). Both formats
share `capture_screen`, so the PNG/BMP difference in staging was
which requests happened to draw a high handle value, not the
encoders: the pure-Python `encode_png`/`bgra_to_rgba` path was
verified innocent by round-tripping 1536x864 and 3840x2160
synthetic frames on the VM (structure + per-chunk CRC +
pixel-exact decode), and the pre-existing encoder tests only ever
used tiny images.

**Fix:** `_declare_capture_signatures()` in `bridge_agent.py`
declares argtypes + restype for all ten user32/gdi32 functions the
capture path calls (every handle slot `c_void_p`) and runs at the
top of `capture_screen`; `_monitor_rects` likewise declares
`EnumDisplayMonitors`, and its callback's LPARAM parameter is now
`c_void_p` (was `c_double`). No other behavior change.

**Regression coverage** (`tests/test_v1_platform.py`, 12 → 14):
`test_png_roundtrip_real_capture_size` runs the full
BGRA→RGBA→PNG path at 1536x864 and decodes it end to end;
`test_capture_signatures_declared` pins the declared signature
table using stand-in function objects (the capture itself remains
Windows-only). The signature test was confirmed to error against
the pre-fix agent code.

**Verification state:** full suite on Muse's Linux VM after the
fix: **59 tests, OK (1 skip)** — the skip remains the Windows-only
real-capture test. That is a VM result only. **Live Windows
re-verification of `format=png` is PENDING** the staging session's
re-run on the PC; BMP was verified live on Windows by that session
(200, 1536x864, SHA-256 correct). Noted for a future pass, not
touched by this fix: the same undeclared-signature pattern exists
in the jobs process-exit helper (`OpenProcess` /
`GetExitCodeProcess` near the top of `bridge_agent.py`).
