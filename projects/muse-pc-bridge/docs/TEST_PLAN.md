# Test plan — muse-pc-bridge

## Automated suite

Run from the project directory:

```
python -m unittest discover -s tests -v
```

(`tests/test_bridge.py`; on the Linux dev VM use `python3`.)

The suite boots the **real** agent on an ephemeral loopback port
(127.0.0.1, port 0) with a temp config, temp file root, and temp
audit log, and drives it over real HTTP with `urllib`. It is hermetic:
no real config, repo files, or external network are touched.

### What it proves

| Area | Tests |
| --- | --- |
| Auth | `/v1/status` without a token → 401; with a wrong token → 401 |
| Status | 200 with token; response carries agent name, version, hostname, platform, python, uptime, default shell, file root |
| Exec | echo command exits 0 with the expected stdout; a command exiting 3 reports `exit_code: 3`; a long command with `timeout_s: 0.3` reports `timed_out: true` and `exit_code: null`; a missing `command` field → 400 |
| Files | put → get round-trip is byte-identical with matching sha256; list shows the stored file |
| Path safety | put to `../evil.txt` is rejected and creates **no** file outside the root; get of `../..` and of an absolute path are rejected |
| Audit | log file exists; every line parses as JSON; it contains `server_start`, at least one `auth_failed`, and at least one `/v1/exec` request entry; the token string appears **nowhere** in the log |

Shell commands in the suite are chosen per platform (`cmd` on
Windows, `posix` elsewhere) so the same suite can run on the owner's
PC during install verification.

### v1 suites (added 2026-11-04)

| File | Covers |
| --- | --- |
| `tests/test_v1_jobs.py` (14) | job submit returns immediately with a job id; result/output/exit code; incremental byte-offset reads (head + tail reconstruct the whole, no repeats); **first line visible via the API while the job is still running** (regression for the pipe-pump starvation below); cancel → killed; timeout → failed + timed_out + null exit code; job list; unknown job → 404; **job_finish audited with a 64-char stdout SHA-256**; detached process spawn/list/kill with log tails; PTY session echo round-trip; **pipe-pump regression: session output reaches the buffer while the shell is still alive** (pipe path forced, echo child — fails against the pre-fix pump); missing session → 400 |
| `tests/test_v1_platform.py` (16) | PNG encoder structure (IHDR, filter-0 scanlines round-trip), BMP structure, BGRA→RGBA conversion; PNG round-trip at real capture size (1536x864, per-chunk CRC + pixel-exact decode) and the declared ctypes capture-signature table pinned with stand-in functions (regressions for the staging-found screenshot HTTP 500); the same signature pinning for the kernel32 process calls in `pid_alive` (OpenProcess/GetExitCodeProcess/CloseHandle) and for the clipboard path's user32/kernel32 calls (HGLOBAL round-trip, incl. GlobalAlloc's SIZE_T parameter); capabilities vs platform_limited in /v1/status; screenshot/input/clipboard/UIA → 501 off Windows; bad format → 400; empty input actions → 400; real-capture test is Windows-only (skipped on the VM) |
| `tests/test_v1_lifecycle.py` (8) | update stage/apply/rollback file cycle; wrong SHA-256, version mismatch, and zip-slip bundles rejected; apply without pending → error; supervisor restarts a twice-crashing agent and reports it; a staged **unhealthy update is rolled back automatically** (file bytes restored); a healthy update stays applied |
| `tests/test_v1_files.py` (9) | hash endpoint + ranged get; chunked upload round-trip through the client library; **resume after partial upload** (2 chunks sent, client resumes by id); hash mismatch at completion rejected with no file placed; wrong chunk size rejected; upload discard; tree/mkdir/move/delete incl. root protection; a second named root (and unknown root → 400); path escapes still confined; client `exec_run` |
| `tests/test_v1_hardening.py` (6) | audit rotation bounds the log and honors `audit_keep`; audit tail returns well-formed recent entries from the current file and clamps n; the rate-limit flow end-to-end (401 → 429 + `retry_after_s`, real token unaffected, blocked attempts still audited with `rate_limited: true`); update staging API (empty → staged; running agent untouched) |

### Avatar-display suites (added 2026-11-05)

| File | Covers |
| --- | --- |
| `tests/test_display_state.py` (14) | the pure signal→display mapping: idle / working (job or tracked process) / session outranks working / staged update → connecting / fresh `applied_ok` → celebrate, stale → falls through / apply + rollback failures and a fresh rollback → alert / supervisor failure states → alert / agent unreachable: briefly → connecting, during restart states → connecting, too long → alert / alert outranks activity |
| `tests/test_supervisor_gui.py` (4) | import-level smoke only (module imports with no window created); every art key the mapping can emit has a committed animation asset; the mapping only ever emits known art keys; every asset declares a transparent colour (byte-level Graphic Control Extension check — the floating window is colour-key transparent). A real Tk window needs a display and is verified on the owner's PC, never claimed from a headless run |

### Verified so far

- 2026-11-04, Muse's Linux VM (Python 3.12.3): **10 tests, all
  passing** (run output recorded in `docs/MUSE_HANDOFF.md`).
- Manual smoke on the same VM: `--init` generated a config + token;
  the client CLI completed status / put / list / get / exec against a
  locally running agent; the resulting audit log contained the
  requests and no token.
- 2026-11-04 night, same VM: **full suite 57 tests, OK (1 skip)** —
  the skip is the Windows-only real-screenshot test. Plus a client
  CLI smoke run (status / exec / put / get / jobs / hash /
  audit-tail / update-status) against a locally running v1 agent,
  all exit 0 with verified hashes.
- **PC staging verification of v1 (port 8766 beside the live v0.1)**
  has since run — see the next bullet for its screenshot findings.
  Apart from that BMP result, nothing in the v1 column above is a
  Windows result.
- 2026-11-04 night, later (defect fix): the first PC staging run
  reported `GET /v1/screenshot?format=png` → HTTP 500
  (`argument 1: OverflowError: int too long to convert`) while
  `format=bmp` returned 200 with a real 1536x864 capture and a
  correct SHA-256 — a live Windows result for the BMP path. Root
  cause: undeclared ctypes `argtypes` in the GDI capture (see
  `docs/MUSE_HANDOFF.md`). Fixed on this branch; **full suite on
  the VM: 59 tests, OK (1 skip)**, including the new real-size PNG
  round-trip and capture-signature regression tests. Live Windows
  re-verification of `format=png` is still pending (the staging
  session re-runs it on the PC).
- 2026-11-04 night, later still (same-class follow-up): the
  undeclared-signature pattern the screenshot fix noted in the jobs
  process-exit helper was fixed, and an audit of the remaining
  Windows ctypes surface found the same class in the clipboard
  path (HGLOBAL handle arguments and GlobalAlloc's SIZE_T
  parameter had no declared `argtypes`). Signatures are now
  declared for the `pid_alive` kernel32 calls and the full
  clipboard table; the rest of the surface was inspected and is
  not in the class (SendInput and GetSystemMetrics pass only
  small ints / ctypes arrays; GetCursorPos takes a byref;
  `supervisor.py` and `bridge_update.py` use no ctypes). **Full
  suite on the VM: 61 tests, OK (1 skip)**, including the two new
  signature-pinning tests — both confirmed to fail (errors)
  against the pre-fix agent code. VM result only: live Windows
  verification of the process/clipboard paths rides on the
  staging session's re-run on the PC.
- 2026-11-04 night, staging re-run (parent session): tip
  `232b6d3` deployed as a staging instance on the PC (port 8766).
  Live Windows results: `format=png` now 200 (valid PNG,
  1536x864, real desktop frame); a job ran to done after the
  process-signature fix; clipboard GET 200; jobs, cancel,
  file hash, chunked upload, audit tail (`job_finish` with
  output hashes), and UIA window enumeration all verified
  working. Staging agent stopped afterwards; live v0.1 agent
  untouched and healthy. See `docs/MUSE_HANDOFF.md`.
- 2026-11-05 morning (cutover): the full suite ran under Windows
  Python on the PC. First run (at `bc48202`): 61 tests,
  failures=1/errors=1/skipped=4 — session output starvation
  (product bug, pump read) + a jobs tearDownClass WinError 32
  (test cleanup race). After the fixes, re-run at `14970e4`:
  **63 tests, OK (skipped=4)**; the teardown error is flaky
  (absent in an isolated module run and in the green full run,
  present in two earlier full runs) and its retry window was
  widened. The supervised service form was then installed and
  started on the PC, and the live v1.0.0 agent verified end to
  end (status, job, session round-trip, PNG screenshot). See
  `docs/MUSE_HANDOFF.md`.
- 2026-11-05 morning (owner PC): **the full suite ran under
  Windows Python for the first time** (Windows 11, Python 3.14.2,
  checkout at tip `bc48202`): **61 tests, FAILED (failures=1,
  errors=1, skipped=4)** in 37.7s. The 4 skips are the expected
  platform-conditional ones (`test_{screenshot,input,clipboard,uia}_501_off_windows`
  in `test_v1_platform.py`); the Windows-only real-capture test
  ran and passed. Everything else passed, including jobs, files,
  self-update rollback, and hardening. Two findings:
  (1) **FAIL `test_session_roundtrip`** — a real product bug:
  `Session._pump_pipe` (and `Job._pump`, same pattern) used
  `BufferedReader.read(65536)`, which blocks until the buffer
  fills or EOF; an interactive shell never EOFs, so session
  output starved indefinitely (also live-reproduced over the API
  against a staging agent: powershell and cmd sessions returned
  empty output forever). On POSIX the session test uses the PTY
  path, which is why the VM never saw it. Fixed: both pumps now
  read via a shared `_read_available()` helper (`read1()`), so
  partial output lands promptly; jobs gain the same incremental
  visibility while running.
  (2) **ERROR `tearDownClass (JobsTestCase)`** — test harness
  only: `WinError 32` deleting a detached process's log file
  during temp-dir cleanup, because the process still held it
  open (Windows refuses to delete open files; POSIX allows it).
  Fixed in the tests: teardown now kills any spawned detached
  processes via the API, waits until none report alive, then
  cleans up with a short retry. No agent behavior changed.
- 2026-11-05 morning (fix verification, Muse's Linux VM):
  new regression tests in `tests/test_v1_jobs.py` —
  `PipePumpRegressionTests.test_session_pipe_output_streams_while_shell_alive`
  (confirmed to FAIL against the pre-fix agent with the fix
  stashed: buffer empty, same symptom as Windows) and
  `JobsTestCase.test_job_output_visible_while_job_still_running`.
  **Full suite on the VM after the fix: 63 tests, OK (1 skip)** —
  the skip remains the Windows-only real-capture test.
  **Windows re-verification is PENDING** the parent session's
  re-run on the PC; the Windows suite is not claimed green.
- 2026-11-05 afternoon (avatar-display form, owner's PC, TEMPORARY
  instance on port 8768 beside the untouched production bridge —
  the same isolation pattern as the self-update test): full suite
  on the VM **80 tests, OK (1 skip)** including the 17 new display
  tests. On the PC the GUI supervisor was verified live: window
  rendered fully on-screen (Win32 rect + PrintWindow capture) with
  the idle animation; display state followed real signals —
  **working** during a running job, **session** while a session
  was open (outranking the job), **connecting** sampled during an
  agent-kill restart gap, back to **idle** after; the supervisor
  restarted the killed agent under the GUI form (restarts counted,
  new pid); the **kill switch** (WM_CLOSE to the window) stopped
  supervisor + agent, the port closed, and after a shutdown fix
  `supervisor-status.json` records the final **stopped** state.
  Three defects were found by this PC run and fixed (window placed
  off-screen when sized before its first frame; Tk not compositing
  GIF difference frames — assets regenerated full-frame; slow
  synchronous GIF loading freezing the window — now lazy/chunked).
  One observation, not a defect of the window: the agent's own
  full-screen capture does not show the DPI-aware avatar window
  (the capturing process is DPI-virtualized); the window itself
  was proven by window rect + PrintWindow + state files.
  **Production form, updated 2026-11-05 evening:** the owner
  approved the switch; the console production was stopped and its
  logon task disabled (kept as the rollback path), the owner
  started the GUI form directly, and a new enabled logon task
  "Muse PC Bridge (avatar)" now autostarts the GUI form. The
  avatar window and live `display-state.json` were verified on
  the production instance after the switch.
- 2026-11-05 evening (transparent avatar, owner's request): the
  six state GIFs were regenerated with the videos' near-white
  backdrop keyed out (border-connected flood keying + 1 px
  foreground erosion; full frames, shared 255-colour palette,
  index 255 transparent — frame transparency 42–66%). The GUI
  window now colour-keys that transparency on Windows
  (`-transparentcolor`): only the character and the status line
  show; the alert flash moved to the status strip so it no longer
  paints the window background. A new byte-level test proves
  every asset declares a transparent colour. **Full suite on the
  VM: 81 tests, OK (1 skip). Owner-PC verification (same
  evening):** the production checkout was pulled to the change
  and the GUI form restarted through its own kill switch
  (WM_CLOSE) + the avatar logon task; a screen grab of the
  window's region shows the working avatar composited directly
  over the desktop wallpaper and taskbar — no backdrop box, no
  key colour visible — with the status line and ✕ rendered over
  the desktop. The pet (running concurrently) was unaffected.

## What the tests cannot prove

These require the owner's PC and are **not** claimed by any VM test:

- **Windows execution**: PowerShell and cmd shells actually spawning
  under Windows, path/drive-letter handling on a real NTFS volume,
  console behavior of `scripts/start-bridge.cmd`.
- **Tailscale link**: binding to the PC's real `100.x` address,
  reachability from Muse's VM over the tailnet, firewall behavior.
- **Autostart task**: `scripts/install-autostart.ps1` registering and
  firing on the owner's machine.
- **Long-session behavior**: hours-long uptime, log growth, Windows
  sleep/wake effects on the listener.
- **v1 Windows-only services**: the ctypes GDI screenshot, SendInput
  injection, clipboard, and the `uia.ps1` helper (the VM proves the
  encoders, the protocol, and the 501 behavior only); Windows
  sessions are pipe-based by design.
- **v1 service form on Windows**: the supervisor's crash-restart and
  update rollback are proven with fake agents on the VM; the logon
  task from `scripts/bridge-service.ps1` has never been installed.
- **v1 exit criteria from the plan**: surviving a reboot and a week
  of unattended running, and the four 2026-11-04 workflows running
  with zero workarounds — these are owner-PC, elapsed-time checks.

## Owner-PC verification checklist (part of install)

From `docs/INSTALL_WINDOWS.md`:

1. `python -m unittest discover -s tests -v` in the project folder on
   the PC — expect all tests to pass under Windows (cmd shell paths).
2. Agent running via `scripts\start-bridge.cmd`; from the PC itself:
   client `status` returns the PC's hostname; client `exec` of a
   harmless command (e.g. `hostname`) returns its output.
3. `logs/audit.jsonl` on the PC shows those requests.
4. Only then: Muse runs the same `status` check from the VM over the
   tailnet.
