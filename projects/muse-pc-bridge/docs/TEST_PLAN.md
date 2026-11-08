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
| `tests/test_v1_lifecycle.py` (13) | update stage/apply/rollback file cycle; wrong SHA-256, version mismatch, and zip-slip bundles rejected; apply without pending → error; **unsafe update versions rejected before any delete** (absolute path, `..` traversal, non-component — Codex PR #27 regressions, victim dirs verified intact); supervisor restarts a twice-crashing agent and reports it; a staged **unhealthy update is rolled back automatically** (file bytes restored); a healthy update stays applied; **graceful-stop audit regressions** (POSIX): the real agent writes `server_stop` to the audit log on SIGTERM, both directly and via `Supervisor._stop_child()` (Codex PR #27) |
| `tests/test_v1_files.py` (12) | hash endpoint + ranged get; chunked upload round-trip through the client library; **resume after partial upload** (2 chunks sent, client resumes by id); hash mismatch at completion rejected with no file placed; wrong chunk size rejected; upload discard; tree/mkdir/move/delete incl. root protection; **tree never follows a symlink out of the root** (escapes skipped, inside-root links still followed — Codex PR #27 regression); a second named root (and unknown root → 400); path escapes still confined; client `exec_run`; **client `job_wait` drains output past one 256 KiB response slice** (600,000-byte job returns every byte, untruncated — Codex PR #27 regression) |
| `tests/test_v1_hardening.py` (6) | audit rotation bounds the log and honors `audit_keep`; audit tail returns well-formed recent entries from the current file and clamps n; the rate-limit flow end-to-end (401 → 429 + `retry_after_s`, real token unaffected, blocked attempts still audited with `rate_limited: true`); update staging API (empty → staged; running agent untouched) |

### Avatar-display suites (added 2026-11-05)

| File | Covers |
| --- | --- |
| `tests/test_display_state.py` (18) | the pure signal→display mapping: idle / working (job or tracked process) / session outranks working / staged update → connecting / fresh `applied_ok` → celebrate, stale → falls through / apply + rollback failures and a fresh rollback → alert / supervisor failure states → alert / agent unreachable: briefly → connecting, during restart states → connecting, too long → alert / alert outranks activity / **v1.1: an active UAC prompt → alert art with label "Approval needed at PC", outranking working/session but not update failures; inactive or absent `uac_prompt` falls through** |
| `tests/test_supervisor_gui.py` (4) | import-level smoke only (module imports with no window created); every art key the mapping can emit has a committed animation asset; the mapping only ever emits known art keys; every asset declares a transparent colour (byte-level Graphic Control Extension check — the floating window is colour-key transparent). A real Tk window needs a display and is verified on the owner's PC, never claimed from a headless run |

### v1.1 suites (added 2026-11-08)

| File | Covers |
| --- | --- |
| `tests/test_v1_gui_spawn.py` (9) | detached GUI launch: `{"gui": true, "executable", "args"}` spawns the executable directly and the registry tracks its real, live pid (the pid's own cmdline is the spawned program, not a wrapper); client-library round trip; missing/nonexistent `executable` → 400; bad `args` (string, non-string list, object) → 400; bad `cwd` → 400; the `gui` flag persists in `state/processes.json` and survives a record restore; a restored record (no Popen handle) reports liveness by OS pid; shell spawn still works and reports `gui: false` |
| `tests/test_v1_wol.py` (12, 2 environment-skipped) | magic-packet layout (102 bytes: 6×0xFF + MAC×16); MAC normalization (colon/dash/bare/lowercase) and rejection of garbage; payload validation incl. defaults (255.255.255.255:9) and bad port/broadcast rejection; the route with the sender stubbed (validation → sender called with canonical values → result returned → audit line written with the MAC, status 200); auth required (401 both ways); `wol` in status capabilities; the standalone `scripts/wol-send.py` produces byte-identical packets. **Live delivery tests** (agent → UDP listener on loopback receives the exact packet; client-library live send) run only where the environment permits outbound UDP — the build VM's sandbox refuses ALL UDP sends (EPERM, verified for plain loopback with no broadcast flag), so they skip there with the reason stated |
| `tests/test_v1_uac.py` (7) | monitor transitions with a stubbed probe: appear (snapshot `active` + ISO `since`), steady state (no duplicate transition, stable `since`), clear; exactly one `uac_prompt_shown` and one `uac_prompt_cleared` audit event, the cleared event carrying the waited seconds, and no credential strings anywhere in the events; a raising probe reads as no prompt; poll-interval config hardening (junk → 2.0 default, floor 0.5 s); the real probe returns False off Windows; `/v1/status` carries `uac_prompt: {active: false, since: null}` by default and flips when the core monitor transitions |
| `tests/test_v1_boot_core.py` (18) | the supervisor core publishes `display-state.json` itself: working / idle / agent-down-too-long → alert states resolved from stubbed signals; write-on-change only (identical bytes incl. `since` on a repeat publish); **a label-only change (alert reason: agent down → UAC waiting) republishes with the original `since`**; the real run loop with a fake agent publishes and settles to idle; `choose_gui_mode` — attach when our agent answers, foreign when another agent answers, own immediately when nothing answers and no live core is evidenced (no status file / "stopped" / stale timestamp with a dead pid), **wait while a core may be alive (fresh status — including steady "running", which the supervisor writes before the agent binds — or a live agent_pid), then attach when the agent starts answering**, own after the bounded wait when it never answers; **stop-request file: a running supervisor consumes it and stops gracefully (status "stopped", no restart, file consumed), and a stale file is cleared at startup**; `--headless` stdio guard redirects pythonw-style None streams to `supervisor-core.log`; a real `supervisor.py --headless` subprocess starts its fake agent and reports `running` |
| `tests/test_v1_session_broker.py` (11) | the session broker: desktop-route whitelist matrix (exec/status/files/sessions/WoL/update all excluded); the helper server 404s non-desktop routes, 501s desktop routes honestly off Windows, still enforces auth; registration lifecycle (fresh registry with port/pid/session, removed on stop); **a real main server proxies a GUI spawn → inspect → kill to a real helper, the record living with the helper, and both sides audit with `via` markers (`session-broker` / `session-helper`)**; a stale registration or `session_broker: false` means local service; **a session-0 agent (session probe patched to 0) refuses desktop routes 501 without a helper and proxies them with one**; the helper starts no second UAC watch (watch starts counted via the entry point; the monitor loop itself is a no-op off Windows); **the listing merge (Codex PR #47 re-review): a brokered spawn appears in the main agent's `GET /v1/processes` (tagged `via: session-helper`) and in `/v1/status` process counts, kill through the main agent is reflected in both, and the listing/counts degrade to local-only when the helper stops** |
| `tests/test_v1_audit_coordination.py` (2) | audit coordination across two cores sharing ONE log (Codex PR #47 re-review): two `BridgeCore` instances append in strict alternation with entries in order; **the rotation race — the log + archives are primed with sentinel entries, the cap is derived from measured on-disk sizes so exactly one of two concurrent appends may rotate, and the first writer is parked between its rotation size check and the renames until the second writer has fully rotated and appended; every entry a serialized run retains (all but the oldest archive) must survive**. The cap deliberately comes from measured sizes: a line occupies one more byte on disk on Windows than POSIX (text-mode CRLF) while the core accounts `len(line)+1`, and an arithmetic cap made the second append rotate legitimately on Windows |
| `tests/test_script_encoding.py` (2) | every shipped `.ps1`/`.cmd` file is **pure ASCII bytes** -- Windows PowerShell 5.1 reads a BOM-less `.ps1` as ANSI, so a UTF-8 em dash decodes to bytes including a stray `"` and the whole file fails to parse (the `bridge-core.ps1` install failure on the owner's PC, 2026-11-08). The scan must find the scripts (incl. `bridge-core.ps1`) and every byte must be < 128 |
| `tests/test_v1_status_helper_timeout.py` (2) | **status-probe deadlines vs a hung helper (Codex PR #47 re-review)**: a raw TCP listener accepts connections and never answers while a heartbeat thread keeps its registration fresh (the real failure shape — heartbeat and request handling are separate threads); `/v1/status` must answer **well inside the supervisor health check's 3 s** (asserted < 2 s), twice in a row, with local process counts intact; `GET /v1/processes` still returns the local listing. Pre-fix, status took **5.01 s** (the listing's fetch budget, synchronous in `_status_obj`) |
| `tests/test_v1_helper_ownership.py` (5) | **single-helper ownership of the state dir (Codex PR #47 re-review)**: a second `SessionHelper` against the same state dir is refused (`HelperOwnershipError`) and the first helper's registration is untouched; `supervisor_gui.start_attach_helper` reuses a live registration (returns None, registration unchanged) and a process spawned through the surviving helper stays visible via the main agent by id and in the listing; a stale registration does not block attach; a stopped owner frees the state dir for the next helper |

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
- 2026-11-08 (Codex PR #27 fixes, Muse's Linux VM, Python 3.12):
  the four Codex findings on the merged v1 PR were each reproduced
  by a new regression test that failed against the pre-fix code
  (staging `rmtree` deleted the victim dir; tree leaked an
  outside symlink's contents; `job_wait` returned 262,144 of
  600,000 bytes; SIGTERM left only `server_start` in the audit
  log), then fixed: version validation in `stage_update`, per-entry
  containment in `/v1/file/tree`, offset accounting in the client's
  `job_wait`, and a graceful SIGTERM/SIGBREAK shutdown path in the
  agent + supervisor. **Full suite on the VM: 88 tests, OK
  (1 skip)** — the skip is still the Windows-only real-capture
  test. **Not verified:** the Windows graceful-stop path
  (CTRL_BREAK_EVENT) and everything else Windows-side; nothing was
  deployed to the owner's PC — the production bridge is untouched.
- 2026-11-08 (v1.1 features, Muse's Linux VM, Python 3.12):
  baseline re-run before the work: **88 tests, OK (1 skip)**.
  After: **full suite 132 tests, OK (3 skips)** — the pre-existing
  Windows-only real-capture skip plus the two WoL live-delivery
  tests, which skip in this sandbox because it refuses all outbound
  UDP (EPERM on a plain loopback send, no broadcast involved);
  the WoL route is still proven end-to-end there with the sender
  stubbed, and the packet bytes are proven exactly. The 44 new
  tests cover GUI-mode detached spawn, Wake-on-LAN, the UAC
  monitor + status field + display mapping, and the boot-core
  topology (display publishing, GUI mode choice, headless entry).
  **Not verified (owner-PC only, activation not performed):** the
  Toolhelp32 consent.exe probe against a real UAC prompt; a real
  GUI application launched via gui mode (window appears, pid
  tracked, breakaway flags); a magic packet actually waking a
  sleeping machine; the SYSTEM boot task starting the core before
  logon and the avatar attaching on the real desktop. Nothing was
  deployed to the owner's PC.
- 2026-11-08 (Codex PR #47 fixes, Muse's Linux VM, Python 3.12):
  Codex reviewed `12efcdb` and left four findings (3 P1, 1 P2); all
  four were verified real against the code and fixed. (1) The
  SYSTEM boot core lives in session 0, so desktop routes served
  locally would act on the wrong desktop — the agent now brokers
  them to an interactive **session helper** hosted by the avatar
  (new `agent/session_helper.py`, desktop-routes-only, loopback,
  same token, shared audit log) and answers an honest 501 for them
  from session 0 when no helper is registered. (2) `choose_gui_mode`
  treated a fresh "running" supervisor status as "core gone" and
  could race a second supervisor onto the port — it now waits while
  a core may be alive (fresh status or live agent_pid) and answers
  "own" immediately only for stopped/stale/absent evidence. (3) The
  management scripts' stop killed processes outright, bypassing the
  audited agent shutdown — they now drop a **stop-request file**
  the supervisor consumes for a graceful stop, with the process
  sweep kept only as a 20 s fallback. (4) Display-state publishing
  compared only the state, leaving a stale label when the alert
  reason changed — it now compares state+art+label and republishes,
  preserving `since`. **Full suite on the VM: 147 tests, OK
  (3 skips)** — the same three skips as the 132 run.
- 2026-11-08 (script encoding fix, Muse's Linux VM, Python 3.12):
  the owner's first run of `scripts/bridge-core.ps1 -Action install`
  on the PC failed to parse under Windows PowerShell 5.1 with
  cascading errors (the error text itself showed mojibake): every
  shipped `.ps1`/`.cmd` file contained UTF-8 em dashes saved
  without a BOM, and 5.1 reads BOM-less files as ANSI, so the em
  dash decoded to bytes including a stray `"` that broke string
  quoting. All 21 em dashes across 8 files replaced with `--`;
  files are byte-pure ASCII. New regression suite
  `tests/test_script_encoding.py` (2 tests) asserts ASCII-only
  bytes for every shipped script -- verified to FAIL against the
  pre-fix `bridge-core.ps1` and pass after. **Full suite on the
  VM: 149 tests, OK (3 skips).** Owner-PC proof the same day:
  PowerShell's own parser (`Parser::ParseFile`) run over the
  pulled scripts on the PC reported 0 errors for each -- see the
  run note in `docs/MUSE_HANDOFF.md`.
- 2026-11-08 (Codex PR #47 re-review fixes, VM + owner's PC):
  Codex's re-review of the broker fix round left two findings;
  both verified real and fixed. (P1) The agent and the session
  helper append to ONE audit log through separate `BridgeCore`
  instances whose per-instance threading locks cannot coordinate
  rotation: both could rotate from the same stale size and shift
  the archives twice, discarding retained entries. `audit()` now
  wraps rotate+append in two layers — a threading lock shared per
  resolved log path within the process, and an OS file lock on a
  sidecar (`audit.jsonl.lock`) across processes; acquisition
  failure degrades to the previous unlocked behaviour with a
  stderr warning (never a crash, never a dropped entry; no entry
  content or rotation policy change). (P2) Brokered GUI spawns
  lived only in the helper's registry while `GET /v1/processes`
  and the `/v1/status` counts read only the local one; both now
  merge the helper's records (tagged `via: session-helper`), and
  a missing/unanswering helper degrades the merge to local-only.
  **Full suite on the VM: 153 tests, OK (3 skips).** Owner-PC
  runs (checkout pulled through the production bridge as jobs;
  production 1.1.0 in the avatar form stayed up throughout;
  Windows, Python 3.14.2): at `7664444` (the two fixes) the suite
  ran 153 with **one failure** — the new audit race test lost a
  retained archive (R2); at `73f53ab` (shared per-path lock added)
  the same single failure recurred. Root cause then traced to the
  TEST, not the lock: Windows text mode writes CRLF, so a line
  occupies `len+2` bytes on disk while the core accounts an
  incoming line as `len(line)+1`; the test's arithmetic cap sat
  low enough on Windows that the second append rotated
  legitimately and discarded R2 by the book. (The `73f53ab`
  commit message attributed the first PC failure to msvcrt
  same-process lock semantics; that claim is not established —
  the accounting bug fully explains both PC runs — and commit
  `f4d0306` corrects the record in the code/test comments. The
  shared lock stays as deliberate hardening.) The test now
  derives its cap from measured on-disk sizes and forces the
  interleave structurally (first writer parked between its size
  check and the renames until the second writer has fully
  rotated and appended): against the pre-fix agent on the VM it
  fails 3/3 with exactly the predicted R2 loss, and at
  `f4d0306` the **owner-PC suite is fully green: 153 tests, OK
  (8 skips)** — the 8 skips are the platform-mirror tests. Still
  unproven: the file-lock layer under the real two-PROCESS split
  (both suites run the two cores in one process, exercising the
  in-process layer; the cross-process layer is exercised by the
  activation verification below, not by the suite), and the boot
  topology activation itself — see "What the tests cannot prove".

- 2026-11-08 (Codex PR #47 second re-review fixes, VM + owner's
  PC): Codex's review of the re-review fix round left two more
  findings; both verified real against the code and fixed, each
  with regression tests written first and demonstrated failing on
  the pre-fix code. (P2) `/v1/status` merged helper processes
  through the listing's 5 s fetch synchronously, so a helper that
  stays registered and heartbeating but stops answering HTTP
  stalled status for 5 s — past the avatar readers' 1.5 s and the
  supervisor health check's 3 s, whose failure after an update
  triggers rollback of a healthy update. The status path now has
  its own bounded merge: a fresh-enough last-known merge (2 s) is
  served without touching the network, a failed fetch backs off
  for 1 s instead of stalling every poll, and a cold fetch is
  bounded at 0.75 s; the plain listing keeps its 5 s budget and
  refreshes the cache, and the merge behaviour when the helper
  answers is unchanged. The new deadline test measured status at
  **5.01 s pre-fix** against a hung-helper stub (accepts, never
  answers, heartbeat keeps the registration fresh) and inside
  2 s post-fix. (P2) Opening the avatar launcher twice started
  two session helpers whose heartbeats overwrote the one
  registration while their process registries diverged, so
  brokered processes 404'd or vanished; `SessionHelper.start()`
  now claims an OS exclusive lock on
  `state/session-helper-owner.lock` before loading anything,
  held until `stop()` and released by process death (no
  stale-lock janitor), and a second start is refused with
  `HelperOwnershipError`. The GUI attach path applies the agent's
  own liveness test first — a live registration is reused, a
  stale one never blocks. **Full suite on the VM: 160 tests, OK
  (3 skips). Owner-PC run (checkout fast-forwarded to `6fbdd3d`
  through the production bridge as a job; production 1.1.0 in
  the avatar form was NOT restarted — its uptime ran
  continuously through the pull and the run; Windows,
  Python 3.14.2): 160 tests, OK (8 skips)** — the 8 skips are
  the platform-mirror tests. Still unproven: the ownership lock
  under the real two-PROCESS split on Windows (both suites
  exercise it between two helpers in one process; the
  cross-process case is the owner opening the launcher twice,
  which the staged core-switch verification covers), and the
  boot topology activation itself.

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
- **v1.1 UAC probe on real Windows**: that consent.exe presence
  tracks a real elevation prompt's lifetime, that the agent (in
  whichever session the core runs) can enumerate it, and that the
  avatar flips to "Approval needed at PC" while a prompt is up and
  back when it clears. The VM proves the monitor logic and every
  surface with the probe stubbed — never the probe itself.
- **v1.1 GUI launch on real Windows**: spawning an actual GUI
  executable (e.g. Godot) with `gui: true` — window opens, the
  tracked pid is the app, the app survives the request and agent
  restarts of the supervisor, and the breakaway-from-job flags
  behave. The VM proves the direct-spawn mechanics with a console
  child only.
- **v1.1 Wake-on-LAN end-to-end**: a packet from the agent (or from
  `scripts/wol-send.py` on another LAN device) actually waking a
  configured, sleeping machine — a property of that machine's
  BIOS/NIC/OS settings. The VM build sandbox cannot even send UDP,
  so live delivery is unproven there by environment, not by code.
- **v1.1 boot topology activation**: the "Muse PC Bridge (core)"
  task firing at boot as SYSTEM, the agent answering before logon,
  the avatar attaching at logon (and its close leaving the core
  running), and rollback to the logon form. Script/code + VM tests
  only; activation is a separate owner-approved step.
- **v1.1 session broker on real Windows**: the SYSTEM core
  brokering desktop routes to the avatar's session helper —
  screenshot/content, input, clipboard and GUI launch acting on the
  owner's real desktop through the core's port — plus the honest
  501 for desktop routes before logon (no helper yet). The VM
  proves the proxy, whitelist, registry and audit mechanics with
  both servers on loopback; it cannot prove session behaviour.

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
