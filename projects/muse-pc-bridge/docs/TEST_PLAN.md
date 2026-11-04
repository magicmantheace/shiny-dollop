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

### Verified so far

- 2026-11-04, Muse's Linux VM (Python 3.12.3): **10 tests, all
  passing** (run output recorded in `docs/MUSE_HANDOFF.md`).
- Manual smoke on the same VM: `--init` generated a config + token;
  the client CLI completed status / put / list / get / exec against a
  locally running agent; the resulting audit log contained the
  requests and no token.

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
