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

## State update (2026-11-04 night, later still): same signature defect class fixed in pid_alive + clipboard

The future pass noted above has now happened. The whole Windows
ctypes surface of the agent was audited for the undeclared-
signature class (a pointer-sized handle or size value crossing a
ctypes call without declared `argtypes`/`restype`):

**Fixed — `pid_alive` (jobs/process liveness, core path):**
`OpenProcess` had no declared `restype` (HANDLE truncated to the
default `c_int`) and `GetExitCodeProcess` / `CloseHandle` had no
`argtypes`, so the handle was passed on through the 32-bit Windows
C long conversion — the identical latent failure to the screenshot
one: intermittent `OverflowError: int too long to convert`
whenever the OS handed out a handle above INT_MAX.
`_declare_process_signatures()` now declares all three
(`OpenProcess`, `GetExitCodeProcess`, `CloseHandle`; handle slots
`c_void_p`) and runs at the top of `pid_alive`'s Windows branch.

**Fixed — clipboard path (`clipboard_get` / `clipboard_set`):**
the handle-returning calls already declared `c_void_p` restypes,
but nothing declared `argtypes`, so the HGLOBAL was passed on to
`GlobalLock` / `GlobalUnlock` / `GlobalFree` /
`SetClipboardData` through the same 32-bit conversion, and
`GlobalAlloc`'s size parameter is `SIZE_T` (pointer-sized), not
the assumed 32-bit long. `_declare_clipboard_signatures()` now
declares the full table (OpenClipboard, CloseClipboard,
EmptyClipboard, GetClipboardData, SetClipboardData, GlobalAlloc,
GlobalLock, GlobalUnlock, GlobalFree), replacing the ad-hoc
per-function restype lines.

**Inspected, not in the class, no change:** the capture path
(fully declared by the screenshot fix); `SendInput` (arguments
are small ints plus a ctypes INPUT array passed by reference;
return is a UINT count); `GetSystemMetrics` (int in, int out);
`GetCursorPos` (takes a `byref` POINT, returns BOOL).
`agent/supervisor.py` and `agent/bridge_update.py` use no ctypes
at all — so the self-update / rollback path contains no instance
of this defect class.

**Regression coverage** (`tests/test_v1_platform.py`, 14 → 16):
`ProcessSignatureTests.test_process_signatures_declared` and
`ClipboardSignatureTests.test_clipboard_signatures_declared` pin
the two new declared tables with stand-in function objects, in
the same style as `CaptureSignatureTests`. Both were confirmed
to fail (errors=2) against the pre-fix agent code and pass with
the fix.

**Verification state:** full suite on Muse's Linux VM: before
59 tests OK (1 skip), after **61 tests, OK (1 skip)** — the skip
remains the Windows-only real-capture test. That is a VM result
only. **Live Windows verification of these two paths is PENDING**
and rides on the parent session's staging re-run on the PC (the
jobs-liveness and clipboard endpoints exercised against the
staging instance), alongside the still-pending `format=png`
re-verification.

### State update — 2026-11-04 night, final: PC staging verification COMPLETE

The parent session (the one holding the live bridge token) ran the
staging procedure from this handoff against tip `232b6d3`: the v1
agent was deployed to `D:\bridge-work\bridge-v1-stage`, port 8766,
with its own staging config and token. Verified live on Windows
(AthenZ971): `/v1/status` reports version 1.0.0 with the full
capability list; job submit → poll → done with correct output, and
job cancel → killed; `file/put` plus the server-side SHA-256
endpoint agree with the local hash; a chunked upload (200,000 B in
64 KiB chunks) completed with a matching final hash; the audit
tail shows `job_finish` events carrying output hashes; UIA
`windows` enumeration returned real window data; clipboard GET
returned 200 on the newly declared signature path; BMP capture
returned a real 1536x864 frame; and, after the two signature
fixes, `format=png` returned 200 with a valid PNG — the frame
shows the staging agent's own console banner ("muse-pc-bridge
1.0.0 listening"). Capture-resolution note: 1536x864 is the
DPI-scaled logical desktop size (the host display is 3840x2160 at
250% scaling); the agent is not DPI-aware yet.

The staging agent was then stopped (port 8766 closed) and the
transfer artifacts removed; the live v0.1 agent was never touched
and reported healthy afterwards. Still NOT verified anywhere: the
suite under Windows Python, the supervised service form, and
self-update apply on the PC — those ride on the owner's cutover
checklist (see the overnight report in `docs/V1_PLAN.md` terms:
staging first, then the manual first cutover, UAC step owner-only).

### State update — 2026-11-05 morning: first Windows Python suite run found 2 defects; both fixed on this branch

The cutover attempt ran the suite under Windows Python on the PC
(Windows 11, Python 3.14.2, checkout pulled to tip `bc48202`; the
running live agent is still v0.1, loaded in memory — it was not
stopped). Result: **61 tests, FAILED (failures=1, errors=1,
skipped=4)** in 37.7s. The 4 skips are the expected
platform-conditional ones (`test_{screenshot,input,clipboard,uia}_501_off_windows`
in `tests/test_v1_platform.py`); the Windows-only real-capture
test ran and passed. Everything else passed, including jobs,
files, the self-update rollback cycle, and hardening. The
cutover paused at this gate — the suite must be green on Windows
before the live agent is stopped. Two defects:

**Defect 1 — product bug: pipe-pump output starvation**
(FAIL `test_v1_jobs.JobsTestCase.test_session_roundtrip`).
`Session._pump_pipe` did `self.proc.stdout.read(65536)`;
`Job._pump` used the same `stream.read(65536)` pattern.
`BufferedReader.read(n)` blocks until *n* bytes arrive or EOF.
A job's exit eventually EOFs, but an interactive session's shell
never does — its output (a few hundred bytes) starved
indefinitely. Confirmed live over the API against a staging
agent on Windows: both powershell and cmd sessions returned
empty output forever. POSIX never saw it because sessions there
use the PTY path (`os.read` returns what is available). **Fix:**
both pumps now read through a shared `_read_available()` helper
in `agent/bridge_agent.py` that uses `read1()` — a single raw
read returning whatever is available — so partial output lands
in the buffer promptly. The PTY pump is unchanged. Jobs gain
the same fix: early output is now visible via the API while a
job is still running, as the v1 incremental-output design
intends.

**Defect 2 — test harness only** (ERROR `tearDownClass
(JobsTestCase)`): `PermissionError: [WinError 32]` deleting
`state/processes/<id>.err.log` during temp-dir cleanup — a
detached process the tests spawned still held its log files
open, and Windows refuses to delete open files (POSIX allows
it, so the VM never saw it). **Fix (tests only, no agent change
— holding log handles for live tracked processes is by
design):** `tearDownClass` now kills any spawned detached
processes through the API and waits until none report alive
before cleanup, and the cleanup itself retries briefly on
`PermissionError`.

**Regression coverage** (`tests/test_v1_jobs.py`, 12 → 14):
`PipePumpRegressionTests.test_session_pipe_output_streams_while_shell_alive`
forces the pipe path (IS_WINDOWS patched, echo child as the
shell) and asserts output reaches the buffer while the child is
still alive — **confirmed to fail against the pre-fix agent**
(fix stashed: buffer empty, the Windows symptom) and to pass
with the fix. `JobsTestCase.test_job_output_visible_while_job_still_running`
asserts a job's first line is visible via the API while its
state is still `running`.

**Verification state:** full suite on Muse's Linux VM after
the fix: **63 tests, OK (1 skip)** — the skip remains the
Windows-only real-capture test. That is a VM result only.
**Windows re-verification is PENDING**: the parent session will
re-pull the PC checkout and re-run the suite under Windows
Python before the cutover resumes. The Windows suite is NOT
claimed green. Also still unverified: the supervised service
form and self-update apply on the PC.

### State update — 2026-11-05 morning, final: CUTOVER COMPLETE, v1.0.0 LIVE

The owner approved the staging-assisted cutover (staging instance
babysits while the live agent is swapped) and was present for it.

- **Windows suite GREEN**: after the pump/teardown fixes
  (`14970e4`), the PC checkout was re-pulled and the full suite
  run under Windows Python: **63 tests, OK (skipped=4)** — the
  four skips are the off-Windows 501 assertions, skipped by
  construction on Windows. One flake is on record: the jobs
  `tearDownClass` error (WinError 32 on a detached-process log)
  appeared in two full-suite runs and in neither the isolated
  module run nor the green full run — a Windows handle-release
  race in test cleanup, not product behavior; the teardown retry
  window was widened (40 × 0.5 s) in the same commit as this note.
- **One more defect found by the cutover itself**:
  `scripts/bridge-service.ps1` install failed on its first-ever
  Windows run — the local `$action` variable collided with the
  `$Action` parameter (PowerShell names are case-insensitive) and
  tripped the parameter's ValidateSet. Fixed at `d0f787b`
  (renamed to `$taskAction`); install then succeeded.
- **Cutover sequence as executed**: staging agent (8766)
  verified up → v0.1 agent (pid 36060) and its launcher console
  stopped through staging → service install (registered the
  per-user logon task "Muse PC Bridge (supervised)"; **no UAC
  prompt was required**) → `-Action start` → supervisor running,
  agent pid 40472, port 8765 listening.
- **Live verification against the production install** (owner's
  real token, port 8765): `/v1/status` reports **1.0.0** with 18
  capabilities; a job ran to done; an interactive **PowerShell
  session round-tripped** (`echo` marker returned — the pump fix
  proven end-to-end); a native **PNG screenshot** returned a
  valid 1536x864 frame. The staging agent was then stopped (8766
  closed) and the live agent re-confirmed healthy.
- The `v1.0.0` tag is applied at the tip containing this note.
- Still unverified (unchanged, honestly): self-update *apply*
  on the PC (nothing has been staged/applied through it yet) and
  the plan's elapsed-time criteria (reboot survival, a week
  unattended) — those are now running in production and will be
  proven by time, not by claim.

## 2026-11-05 afternoon — avatar-display supervisor form (owner's request)

The owner asked for the bridge's display to be Muse's avatar in a
floating window, animated by what the bridge is doing, instead of
the console window. Built as a third supervisor form beside the
console forms (nothing replaced):

- `agent/supervisor_gui.py` — the same `Supervisor` core hosted by
  a tkinter floating window (always-on-top, draggable, ✕ and
  right-click "Stop bridge"). Closing/stopping the window stops
  supervisor + agent: the kill-switch semantics are unchanged, and
  the window is the visible indicator (no hidden mode). Stdlib
  only (tkinter ships with Python). Launched console-free via
  `scripts/start-bridge-gui.cmd` (pyw/pythonw; supervisor prints
  go to `state/supervisor-gui.log`).
- `agent/display_state.py` — pure mapping from real signals
  (supervisor-status.json, agent /v1/status, update status) to
  idle / working / session / connecting / celebrate / alert.
  Nothing is faked: the avatar reflects bridge activity only.
- The window also publishes its current state to
  `state/display-state.json` on every change — a read-only local
  hook other apps on the PC (e.g. the owner's desktop pet) can
  observe. No token material, no new network surface, no new
  inputs to the bridge.
- Assets: `agent/assets/avatar/*.gif`, one loop per state,
  rendered from the avatar's own state-variant videos. They MUST
  stay full-frame GIFs (see below).

**Verification (owner's PC, temporary instance, port 8768,
production untouched throughout — uptime continuous):** the full
live state sequence was observed via display-state.json and
PrintWindow captures — idle → working (job running) → session
(session open) → connecting (sampled in an agent-kill restart
gap) → idle; supervisor restarts work under the GUI form; the
kill switch (WM_CLOSE) stopped everything and, after the fix
below, `supervisor-status.json` ends at "stopped". Temp instance
and all staged files were removed afterward. VM suite: 80 tests
OK (1 skip), including 17 new display tests.

**Defects the PC run found (all fixed, regression-noted):**
1. Window placed off-screen: geometry was computed before the
   first animation frame set the window's real size. The window
   now stays withdrawn until the first frame is applied, then
   places itself bottom-right.
2. Tk does not composite GIF difference frames: ffmpeg's default
   GIF output rendered as a speckled ghost after frame 0. Assets
   regenerated with `-gifflags -offsetting-transdiff` (full
   frames), 192-color palette, bayer dithering. Do not
   re-encode them with default GIF settings.
3. Synchronous GIF loading froze the window before it could
   appear (Tk re-scans the file per -index frame). Loading is now
   lazy and chunked; playback cycles frames as they arrive.
4. A window-close stop left `supervisor-status.json` stale at
   "running" (the process exited before the supervisor thread's
   final write). `main()` now joins the supervisor thread briefly
   at shutdown so the file records "stopped".

**Observation:** the agent's full-screen screenshot does not show
the avatar window (the capturing agent process is DPI-virtualized;
the GUI is per-monitor DPI-aware). The window's rendering was
proven by Win32 rect + `PrintWindow` + state files instead. A
human at the PC sees the window normally.

**Production switch (2026-11-05 evening, owner's go):** the
console production was stopped and its logon task disabled (kept,
disabled, as the rollback path). One hard lesson: the stop was
issued through a throwaway monitor instance on port 8768, and
`bridge-service.ps1 -Action stop` kills bridge python processes
broadly — it took the monitor down with production, leaving no
remote channel until the owner started the GUI form by hand at
the PC. Never run a service stop through a sibling instance
without reading its process-matching scope first. The owner then
launched `start-bridge-gui.cmd` himself; a new logon task
**"Muse PC Bridge (avatar)"** (enabled, Ready) now autostarts
the GUI form, and the avatar window + live `display-state.json`
were verified on production after the switch. The celebrate/alert
states remain unit-tested only (never driven live).

## 2026-11-05 evening — transparent avatar (owner's request)

The owner asked for the floating window's background to be
transparent. Two halves:

- **Assets regenerated with the backdrop keyed out.** The source
  videos sit the character on a near-white backdrop. Keying =
  pixels similar to the backdrop AND connected to the frame
  border (flood/labelling), plus 1 px of foreground erosion to
  strip the bright fringe — connectedness is what protects the
  pale skin and the black dress (neither touches the border as a
  similar-coloured region). Full frames, 320×320, 10 fps, one
  shared 255-colour palette per GIF + palette index 255 as the
  transparent colour; per-frame transparency runs 42–66%. The
  full-frame rule from the 2026-11-05 defect list still applies.
- **Window colour-key:** `supervisor_gui.py` sets Tk's
  `-transparentcolor` to a magenta key (`KEY = "#ff00ff"`, absent
  from the art) on the root and every label, so on Windows only
  the character and the status line are visible and clicks pass
  through the transparent parts. If the attribute is unsupported,
  the window falls back to the original dark box. The alert flash
  no longer repaints the whole window background (that would
  defeat the keying) — it flashes the status strip only; the
  alert GIF's red border is unchanged.

VM suite: **81 tests OK (1 skip)** — the new test is byte-level
(every GIF must declare a transparent colour in a Graphic Control
Extension). **PC verification (same evening):** production
checkout pulled; the GUI form was restarted via its own kill
switch (a detached restarter posted WM_CLOSE, waited for the
port to close, then started the "Muse PC Bridge (avatar)" task —
no sibling-instance stop this time). A screen grab of the new
window's region shows the working animation composited straight
over the desktop wallpaper/taskbar: no backdrop box, no key
colour, status line and ✕ floating over the desktop. The
owner's desktop pet, running at the same time, kept polling the
state file throughout.

## 2026-11-08 — Codex PR #27 findings fixed (branch `codex-fixes/pc-bridge`)

Codex reviewed the merged v1 PR (#27) and left four findings; the
owner directed fixing all of them. Each was verified against the
code first (all four real), reproduced by a regression test that
failed pre-fix, then fixed minimally:

1. **P1 — update staging path traversal** (`agent/bridge_update.py`):
   `stage_update()` joined the caller-supplied `version` onto the
   staging root and `rmtree()`d the result before any bundle
   verification; an absolute or `..` version deleted an arbitrary
   directory. Fix: `_validate_version()` requires a single safe
   path component, plus a resolved-containment check, before
   anything is removed.
2. **P2 — client job polling skipped output**
   (`client/bridge_client.py`): `job_wait()` advanced its offsets
   to the stream totals (`stdout_bytes`), but one response carries
   at most 256 KiB — a 600,000-byte job returned only 262,144
   bytes. Fix: request an explicit slice size, advance offsets
   only past bytes actually returned, and drain a finished job
   before returning.
3. **P1 — file/tree followed symlinks out of the root**
   (`agent/bridge_agent.py`): the recursion applied no containment
   check to descendants. Fix: each child is resolved and checked
   against the file root; escapes are skipped (never listed or
   followed), inside-root links still work — per AGENTS.md §10.
4. **P1 — supervisor stop bypassed the audited shutdown**
   (`agent/supervisor.py`, `agent/bridge_agent.py`): a normal stop
   terminated the agent, so the audit log kept `server_start`
   with no `server_stop`. Fix: the agent routes SIGTERM (POSIX)
   and SIGBREAK (Windows) through the same shutdown path as
   Ctrl+C, so `main()`'s finally writes `server_stop`; the
   supervisor sends CTRL_BREAK_EVENT on Windows (child now spawns
   in its own process group) and keeps forced termination as the
   fallback after the grace timeout.

**Verified (Muse's Linux VM, 2026-11-08):** full suite
**88 tests, OK (1 skip)** — the skip is the pre-existing
Windows-only real-capture test. The POSIX graceful-stop path is
proven end-to-end with the real agent (direct SIGTERM and via
`Supervisor._stop_child()`).

**NOT verified:** the Windows CTRL_BREAK_EVENT graceful stop
(needs the owner's PC), and no deployment was made — the
production bridge on the PC still runs the pre-fix v1.0.0 build.
Deploying this branch is a separate owner-directed step.

## 2026-11-08 — v1.1 features built (branch `muse-pc-bridge/v1-1-features`), VM-verified, NOT deployed

The owner directed the bridge v1.1 wish list ("Build them in
then", 2026-11-08) and barred PC testing that day — so this was
built entirely on the VM: **no PC contact, no deployment, no task
installed**. Agent version is now `1.1.0`.

**What was built** (one commit per feature on top of main
`822083c`, which already carried the PR #46 fixes):

1. **UAC consent detection + signal** (`bd22931`). A `UacMonitor`
   in the agent polls `consent.exe` presence via a Toolhelp32
   snapshot (ctypes signatures declared per the house discipline).
   Surfaces: `/v1/status` gains `uac_prompt: {active, since}`;
   audit events `uac_prompt_shown` / `uac_prompt_cleared`
   (presence/duration only — never credential content); the
   display mapping sends an active prompt to the avatar's alert
   art with the distinct label "Approval needed at PC". Poll
   interval is config `uac_poll_interval_s` (default 2.0). The
   probe is a no-op (False) off Windows and on any probe failure.
2. **Boot-surviving core** (`e32561a`). `supervisor.py --headless`
   is the core form (pythonw, prints to
   `state/supervisor-core.log`), started at boot by the new
   "Muse PC Bridge (core)" SYSTEM task (`scripts/bridge-core.ps1`
   + `start-bridge-core.cmd`) — bridge up before/without logon.
   The supervisor (all forms) now publishes `display-state.json`
   itself; the avatar window no longer writes it. The GUI probes
   first and **attaches display-only** when a core answers (with a
   short retry only while a core reports a transient state — the
   logon/boot race); its menu then reads "Close avatar (bridge
   keeps running)". A non-bridge answer on the port refuses
   startup. No core → the historical own-supervisor form.
   Rollback = uninstall the boot task, return to a logon form;
   config/token/state/audit are shared and untouched.
3. **Wake-on-LAN** (`3b22829`). `POST /v1/wol {mac, broadcast?,
   port?}` sends the 102-byte magic packet from the PC (token +
   audit, `wol` capability), client `wol()` + CLI. Standalone
   `scripts/wol-send.py` covers waking the bridge PC itself, with
   the honest prerequisite in its docstring: some other always-on
   LAN device must send the packet — a sleeping PC runs no agent.
4. **Detached GUI launch** (`262c73e`). `POST /v1/processes` with
   `{"gui": true, "executable", "args"}` spawns the executable
   directly — the tracked pid is the app, not a shell wrapper that
   exits on handoff (the Milky Way Godot defect). Windows spawn
   also requests breakaway-from-job, retrying without it when
   refused. Records persist/report `"gui"`. Client `process_spawn`
   gains `gui/executable/args`; CLI gains `spawn-gui`.

**Verified (Muse's Linux VM, 2026-11-08):** baseline before the
work **88 tests, OK (skipped=1)**; after, **full suite 132 tests,
OK (skipped=3)**. The two new skips are the WoL live-delivery
tests: this VM's sandbox refuses ALL outbound UDP (EPERM on a
plain loopback send, verified separately), so they skip with the
reason stated and run where UDP is permitted; the WoL route is
otherwise proven end-to-end with the sender stubbed and the
packet bytes proven exactly.

**NOT verified — PC-verification pending** (activation/checklist
in `docs/INSTALL_WINDOWS.md`, list in `docs/TEST_PLAN.md`): the
consent.exe probe against a real UAC prompt; a real GUI app
spawned via gui mode; a magic packet waking a real machine (both
directions); the boot task firing as SYSTEM, the agent answering
before logon, and the avatar attaching on the real desktop.
Deploying 1.1.0 and activating the boot core are separate
owner-approved steps — do not treat this branch landing as either.

---

**Script encoding fix (2026-11-08, later):** the owner's first
interactive run of `bridge-core.ps1 -Action install` failed to
parse on the PC -- Windows PowerShell 5.1 reads BOM-less `.ps1`
files as ANSI, and the UTF-8 em dashes in the scripts decoded to
bytes including a stray `"`, cascading into "Missing closing
'}'" parse errors. All 8 shipped `.ps1`/`.cmd` files carried em
dashes (21 total); all replaced with `--`, files now byte-pure
ASCII. `tests/test_script_encoding.py` guards this (fails on the
pre-fix files, passes now). Suite: **149 tests, OK (skipped=3)**
on the VM. **Owner-PC proof (same day, via the live bridge,
parse-only, non-elevated):** the PC checkout pulled the fix
(`c7b93bd` -> `c6c816c`, fast-forward) and Windows PowerShell's
own parser (`Parser::ParseFile`) reported **0 parse errors** for
each of `bridge-core.ps1`, `bridge-service.ps1`,
`install-autostart.ps1`, and `agent/helpers/uia.ps1`; a byte scan
on the PC confirmed **0 non-ASCII bytes** in all 8 shipped
scripts (`.ps1` + `.cmd`). Production was not restarted. The
install itself remains the owner's interactive run.

---

**Codex PR #47 re-review fixes + owner-PC suite (2026-11-08,
later still):** the owner ran the install interactively — the
"Muse PC Bridge (core)" boot task is now REGISTERED on the PC
(State=Ready, confirmed from the owner's elevated shell; the
agent's UAC monitor caught the consent prompt live, audit pair
`uac_prompt_shown`/`uac_prompt_cleared` present). Codex's
re-review of the broker fix round left two findings; both were
verified real and fixed. (P1, commit `7664444`) The agent and
the session helper append to ONE audit log through separate
`BridgeCore` instances whose threading locks cannot coordinate
rotation, so both could rotate from the same stale size and
discard retained entries: `audit()` now wraps rotate+append in
a per-path shared threading lock plus an OS file lock on a
sidecar (`audit.jsonl.lock`), degrading to the previous unlocked
behaviour with a warning if the lock cannot be taken (never a
crash, never a dropped entry; no content or policy change).
(P2, same commit) Brokered GUI spawns lived only in the helper's
registry while `GET /v1/processes` and the `/v1/status` counts
read only the local one; both now merge the helper's records
(tagged `via: session-helper`), degrading to local-only when no
helper answers. Regression tests were demonstrated failing
pre-fix (the audit race lost primed entries 6/6 on the VM in its
first form; the brokered spawn was absent from the main listing).
**VM suite: 153 tests, OK (skipped=3).** Owner-PC verification
ran as bridge jobs (production 1.1.0, avatar form, stayed up;
checkout pulled by fast-forward each time): at `7664444` and
again at `73f53ab` the PC suite ran 153 with ONE failure — the
new audit race test losing a retained archive. That failure was
traced to the TEST's byte accounting, not the lock: Windows text
mode writes CRLF, so a line occupies `len+2` bytes on disk while
the core accounts `len(line)+1`, and the test's arithmetic cap
made the second append rotate legitimately on Windows. (The
`73f53ab` commit message's attribution of the first failure to
msvcrt same-process lock semantics is NOT established — the
accounting bug fully explains both runs; `f4d0306` corrects the
record. The shared lock from `73f53ab` stays as hardening.) At
`f4d0306` — cap derived from measured on-disk sizes, interleave
forced structurally (pre-fix agent on the VM now fails 3/3 with
exactly the predicted loss) — the **owner-PC suite is fully
green: 153 tests, OK (skipped=8), Python 3.14.2**. What remains
unproven is unchanged in kind: the file-lock layer under the
real two-process split (the suites co-host the cores in one
process) and the boot-topology switch itself. The switch is
staged, not performed: the core task is installed and Ready;
production still runs the avatar form, executing the code loaded
at its last start (the `c7b93bd` deployment); the checkout has
since been pulled to `f4d0306`, which takes effect only when the
agent restarts — at the switch.
The choreographed switch (owner clicks the avatar's close =
audited stop; owner runs `bridge-core.ps1 -Action start` in the
elevated shell; verify the core on 8765; start the avatar task
to attach + register the helper; verify display-state freshness
and brokered desktop routes) is a separate owner-accompanied
step — see `docs/TEST_PLAN.md` for the verification split.

---

**Codex PR #47 second re-review fixes (2026-11-08, evening):**
Codex's review of the re-review fix round left two more
findings; both verified real against `dfc6227` and fixed, with
regression tests written first and demonstrated failing pre-fix.
(P2, commit `206e2f7`) `_status_obj()` merged helper-owned
processes through the listing's 5 s fetch synchronously, so a
helper that stays registered and heartbeating but stops
answering HTTP stalled `/v1/status` for 5 s — past the avatar
readers' 1.5 s and the supervisor health check's 3 s, whose
failure after an update triggers rollback of a healthy update.
The regression stub (accepts connections, never answers,
heartbeat keeps the registration fresh) measured status at
**5.01 s pre-fix**. The status path now uses its own bounded
merge (`_helper_processes_for_status`): a fresh-enough
last-known merge (2 s) is served with no network call, a failed
fetch backs off 1 s rather than stalling every poll, and a cold
fetch is bounded at 0.75 s; the plain listing keeps its 5 s
budget and refreshes the cache, and the merge when the helper
answers is unchanged. (P2, commit `6fbdd3d`) Opening the avatar
launcher twice started two session helpers whose heartbeats
overwrote the one `session-helper.json` while their process
registries diverged, so brokered processes 404'd or vanished
depending on whose heartbeat landed last. `SessionHelper.start()`
now claims an OS exclusive lock on
`state/session-helper-owner.lock` BEFORE loading anything, held
until `stop()` and released by process death (no stale-lock
janitor); a second start raises `HelperOwnershipError`. The GUI
attach path (`supervisor_gui.start_attach_helper`) applies the
agent's own liveness test first: a live registration is reused
and no second helper starts; a stale one never blocks. **VM
suite: 160 tests, OK (skipped=3). Owner-PC suite (checkout
fast-forwarded to `6fbdd3d` as a bridge job; production NOT
restarted — uptime continuous through pull and run; Windows,
Python 3.14.2): 160 tests, OK (skipped=8).** The switch
choreography above remains valid unchanged against the new
code: no step's mechanics changed — the status checks the
verification leans on are now deadline-safe even with a hung
helper, and at the attach step the stopped avatar's helper has
released its ownership with the window (so the re-opened avatar
starts a fresh helper), while a somehow-still-live helper would
now be reused instead of fought over. The checkout is staged at
`6fbdd3d` for the re-issued switch; production still executes
its previously loaded code until then.
