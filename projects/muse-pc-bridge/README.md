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
4. **Kill switch** — the console and avatar forms run in a visible
   window: window open = running, close it and access ends
   immediately. The optional v1.1 **boot core** runs headless from
   machine boot (see below); its switches are the Scheduled Task
   controls and `scripts\bridge-core.ps1 -Action stop`, and the
   avatar at logon shows its state.

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
| `agent/supervisor.py` | supervisor core (auto-restart, staged-update apply + health check + auto-rollback, publishes `display-state.json`): visible-console form, or `--headless` boot-core form under pythonw |
| `agent/supervisor_gui.py` | avatar-display form: floating window — Muse's avatar animated by real bridge activity, colour-key transparent so only the character shows on the desktop; owns its supervisor (closing the window is the kill switch) or **attaches display-only** to a running core (closing it then leaves the bridge running, and the menu says so); in attach mode it also hosts the session helper |
| `agent/session_helper.py` | interactive session helper: loopback-only server (same token) serving ONLY the desktop routes from inside the owner's logon session, so a session-0 boot core can broker screenshot/input/UIA/clipboard/GUI-launch to the real desktop; registers in `state/session-helper.json` with a heartbeat |
| `agent/display_state.py` | pure signal→display-state mapping for the avatar (idle / working / session / connecting / celebrate / alert; an active UAC prompt maps to alert with label "Approval needed at PC") |
| `agent/assets/avatar/` | avatar animation loops, one full-frame transparent GIF per display state |
| `agent/bridge_update.py` | self-update mechanics (bundle verify, staged apply, rollback) |
| `agent/helpers/uia.ps1` | fixed UI Automation helper driven by the agent (JSON parameters only) |
| `client/bridge_client.py` | Muse-side library + CLI (jobs, processes incl. `spawn-gui`, sessions, chunked files, screenshot/input/clipboard/uia, `wol`) |
| `scripts/start-bridge.cmd` | start the agent in a visible console |
| `scripts/start-bridge-service.cmd` | start the supervised agent (v1 service form) |
| `scripts/start-bridge-gui.cmd` | start the avatar-display form (no console window) |
| `scripts/start-bridge-core.cmd` | start the headless core (v1.1 boot form, pythonw, no window) |
| `scripts/bridge-service.ps1` | manage the supervised form as a logon task (install/start/stop/status/uninstall) |
| `scripts/bridge-core.ps1` | manage the boot core task (install/start/stop/status/uninstall; SYSTEM, at startup) |
| `scripts/wol-send.py` | standalone Wake-on-LAN sender (for waking the bridge PC itself from another LAN device — the bridge cannot wake its own host) |
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
Python (2026-11-05, during the cutover) found one more
defect — interactive-session output starving behind a 64 KiB
buffered pipe read, plus a Windows-only test-teardown error —
both fixed on this branch, and the **full suite then passed
under Windows Python: 63 tests, OK (4 platform skips)**. The
cutover completed the same morning: the live agent on the PC
now runs **v1.0.0 in the supervised (service) form** — see
`docs/MUSE_HANDOFF.md` for the full record.

**Update (2026-11-08):** the four Codex review findings on the
v1 PR (update-staging path traversal, file/tree symlink escape,
client job-polling output loss, unaudited supervisor stop) are
fixed on branch `codex-fixes/pc-bridge`, each with a regression
test that failed pre-fix. **Verified on Muse's Linux VM:
88 tests, OK (1 skip).** The Windows graceful-stop path
(CTRL_BREAK_EVENT) is implemented but **not yet verified on the
PC**, and this branch is **not deployed** — the production
bridge still runs the pre-fix build. See the 2026-11-08 entry in
`docs/MUSE_HANDOFF.md`.

**Update (2026-11-08, v1.1 — agent `1.1.0`, branch
`muse-pc-bridge/v1-1-features`):** four features, all owner-requested.
(1) **UAC consent signal**: the agent polls for `consent.exe` and
reports `uac_prompt` on `/v1/status`, audits appear/clear, and the
avatar shows "Approval needed at PC". (2) **Boot-surviving core**:
a headless supervisor form started by a SYSTEM boot task
(`scripts\bridge-core.ps1`) brings the bridge up before logon; the
avatar attaches to it display-only. (3) **Wake-on-LAN**:
`POST /v1/wol` sends a magic packet from the PC to wake other LAN
machines, plus the standalone `scripts\wol-send.py` for the other
direction (the bridge cannot wake its own host — stated plainly in
both places). (4) **Detached GUI launch**: `process_spawn` gains a
`gui` mode that spawns the executable directly so the tracked pid
is the app itself. **Verified on Muse's Linux VM: 132 tests,
OK (3 skips)** — baseline was 88; the new skips are the two WoL
live-delivery tests, which need outbound UDP the VM sandbox
refuses. **Not verified on the PC** (no PC contact during this
work, at the owner's direction): the consent.exe probe against a
real prompt, a real GUI app spawn, an actual machine waking, and
the boot-task activation. **Not deployed** — production still runs
the pre-v1.1 build; deploying and activating the boot core are
separate owner-approved steps. See the 2026-11-08 v1.1 entry in
`docs/MUSE_HANDOFF.md` and the checklists in `docs/TEST_PLAN.md`.

**Codex-fix follow-up (2026-11-08, same branch):** Codex's review
of the v1.1 PR found four real defects, all fixed. The boot core
runs in session 0, so desktop routes are now **brokered to a
session helper** in the owner's logon session (and answer an
honest 501 before logon instead of touching the wrong desktop);
the avatar's attach decision no longer races a starting core;
the management scripts stop the bridge through an **audited
graceful stop-request** instead of killing processes; and
display-state publishing follows label changes, not just state
changes. **VM suite: 147 tests, OK (3 skips).**
