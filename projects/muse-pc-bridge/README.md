# muse-pc-bridge

A small agent the owner runs on his Windows PC so Muse (Nyx) can do
real work on that PC — run shell commands and transfer files — over
**Tailscale**, with **every request written to an audit log** on the
PC. Python standard library only; no third-party dependencies.

## Why

Work on the owner's PC kept needing a human relay (owner or another
assistant) for every command. This bridge removes the relay: Muse
connects from its VM to the agent on the PC through the owner's
tailnet and works directly, while the owner keeps visibility (audit
log) and control (kill switch).

## Safety model

Full shell access is the owner's explicit choice (2026-11-04). Four
things protect it — read `docs/DESIGN.md` before changing any of them:

1. **Token auth** — a 256-bit bearer token, generated on the PC,
   shown once, never committed to git, never written to the audit
   log. Whoever holds it has full shell as the owner; treat it like
   a password.
2. **Tailnet-only** — the agent binds to the PC's Tailscale `100.x`
   address only. It is not reachable from the LAN or the internet.
3. **Audit log** — append-only JSONL on the PC records every
   request (including failed auth), every command, and every file
   transfer. Non-negotiable.
4. **Kill switch** — v0 runs in a visible console window. Window
   open = running. Close it and access ends immediately. No
   background service.

## Quick start (owner's PC, summary)

Full ordered steps: **`docs/INSTALL_WINDOWS.md`**.

```powershell
cd projects\muse-pc-bridge
python -m unittest discover -s tests -v      # verify on Windows
cd agent
python bridge_agent.py --init                # writes config.json, prints token ONCE
# edit config.json: set "host" to this PC's Tailscale 100.x IP
cd ..
scripts\start-bridge.cmd                     # leave the console open
```

Then, from a second window, set `MUSE_PC_BRIDGE_URL` /
`MUSE_PC_BRIDGE_TOKEN` and verify with
`client\bridge_client.py status`. Finally hand the tailnet IP, port,
and token to Muse **out-of-band** — never via git.

## Layout

| Path | What |
| --- | --- |
| `agent/bridge_agent.py` | the server (runs on the PC) |
| `agent/supervisor.py` | v1 service form: visible-console supervisor (auto-restart, staged-update apply + health check + auto-rollback) |
| `agent/bridge_update.py` | self-update mechanics (bundle verify, staged apply, rollback) |
| `agent/helpers/uia.ps1` | fixed UI Automation helper driven by the agent (JSON parameters only) |
| `client/bridge_client.py` | Muse-side library + CLI (jobs, processes, sessions, chunked files, screenshot/input/clipboard/uia) |
| `scripts/start-bridge.cmd` | start the agent in a visible console |
| `scripts/start-bridge-service.cmd` | start the supervised agent (v1 service form) |
| `scripts/bridge-service.ps1` | manage the supervised form as a logon task (install/start/stop/status/uninstall) |
| `scripts/install-autostart.ps1` | OPTIONAL logon autostart (same visible console) |
| `config.example.json` | config shape (real `config.json` is git-ignored) |
| `tests/` | end-to-end suites: boot the real server on loopback (`test_bridge.py` + `test_v1_*.py`) |
| `docs/DESIGN.md` | architecture, wire protocol, threat model |
| `docs/INSTALL_WINDOWS.md` | exact Windows install + verification steps, plus the v1 upgrade path |
| `docs/CHATGPT_INSTALL_HANDOFF.md` | delegated install (D: drive) that stops before the owner's token/final-setup steps |
| `docs/TEST_PLAN.md` | what the tests prove — and what they cannot |
| `docs/MUSE_HANDOFF.md` | current state, decisions, next steps |
| `docs/V1_PLAN.md` | the v1 feature plan (recorded 2026-11-04) |
| `REQUIREMENTS.md` | Python >= 3.11, stdlib only, Tailscale |

## Status — honest version

**v0 foundation (agent 0.1.0), verified on Muse's Linux VM only:**
the suite (10 tests) passes and a client↔agent smoke test succeeded
there. **Not yet verified:** anything on Windows (PowerShell/cmd,
the .cmd launcher), the real Tailscale link, and the autostart task.
Those are owner-PC checks built into the install doc; until they are
done, this project is *implemented and VM-tested*, not *installed*.
See `docs/MUSE_HANDOFF.md`.

**Update (2026-11-04):** installed and live on the owner's PC — see
the state update in `docs/MUSE_HANDOFF.md`. The v1 feature plan is
recorded in `docs/V1_PLAN.md`.

**Update (2026-11-04 night): v1 built (agent `1.0.0`).** Async jobs,
detached processes, interactive sessions, in-agent screenshot /
host input / clipboard / UI Automation, chunked resumable transfers
with server-side SHA-256, multi-root files, a supervised service
form with self-update + automatic rollback, audit hardening (§5),
and a real client library — per `docs/V1_PLAN.md`, in five slice
commits on this branch. **Verified on Muse's Linux VM: 63 tests
pass** (1 Windows-only skip) plus a client-CLI smoke run. The first
PC staging run found a screenshot defect (`format=png` → HTTP 500,
undeclared ctypes signatures in the GDI capture); it is fixed on
this branch and VM-verified, and the same signature defect class
has since been fixed in the `pid_alive` process helper and the
clipboard path, with live Windows staging
verification completed the same night (see
`docs/MUSE_HANDOFF.md`). The first suite run under Windows
Python (2026-11-05, during the cutover attempt) found one more
defect — interactive-session output starving behind a 64 KiB
buffered pipe read, plus a Windows-only test-teardown error —
both fixed on this branch and VM-verified; Windows
re-verification is pending (see `docs/MUSE_HANDOFF.md`). The live
agent on the PC is still v0.1 — v1 is *implemented,
VM-verified, and staging-verified on the PC*, not yet
*cut over*.
