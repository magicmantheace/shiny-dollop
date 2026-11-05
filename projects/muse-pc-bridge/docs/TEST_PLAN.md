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
| `tests/test_v1_jobs.py` (12) | job submit returns immediately with a job id; result/output/exit code; incremental byte-offset reads (head + tail reconstruct the whole, no repeats); cancel → killed; timeout → failed + timed_out + null exit code; job list; unknown job → 404; **job_finish audited with a 64-char stdout SHA-256**; detached process spawn/list/kill with log tails; PTY session echo round-trip; missing session → 400 |
| `tests/test_v1_platform.py` (14) | PNG encoder structure (IHDR, filter-0 scanlines round-trip), BMP structure, BGRA→RGBA conversion; PNG round-trip at real capture size (1536x864, per-chunk CRC + pixel-exact decode) and the declared ctypes capture-signature table pinned with stand-in functions (regressions for the staging-found screenshot HTTP 500); capabilities vs platform_limited in /v1/status; screenshot/input/clipboard/UIA → 501 off Windows; bad format → 400; empty input actions → 400; real-capture test is Windows-only (skipped on the VM) |
| `tests/test_v1_lifecycle.py` (8) | update stage/apply/rollback file cycle; wrong SHA-256, version mismatch, and zip-slip bundles rejected; apply without pending → error; supervisor restarts a twice-crashing agent and reports it; a staged **unhealthy update is rolled back automatically** (file bytes restored); a healthy update stays applied |
| `tests/test_v1_files.py` (9) | hash endpoint + ranged get; chunked upload round-trip through the client library; **resume after partial upload** (2 chunks sent, client resumes by id); hash mismatch at completion rejected with no file placed; wrong chunk size rejected; upload discard; tree/mkdir/move/delete incl. root protection; a second named root (and unknown root → 400); path escapes still confined; client `exec_run` |
| `tests/test_v1_hardening.py` (6) | audit rotation bounds the log and honors `audit_keep`; audit tail returns well-formed recent entries from the current file and clamps n; the rate-limit flow end-to-end (401 → 429 + `retry_after_s`, real token unaffected, blocked attempts still audited with `rate_limited: true`); update staging API (empty → staged; running agent untouched) |

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
