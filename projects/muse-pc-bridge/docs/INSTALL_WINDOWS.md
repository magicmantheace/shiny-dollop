# Install on the owner's Windows PC

Exact, ordered steps. Everything runs from the project folder
(`projects\muse-pc-bridge\`) once it's on the PC. Nothing here needs
administrator rights.

## 0. Prerequisites

1. **Python 3.11+** installed, with `python` on PATH. Verify in
   PowerShell:
   ```powershell
   python --version
   ```
2. **Tailscale** installed, running, and signed in on this PC.
   Get the PC's Tailscale IPv4 address:
   ```powershell
   tailscale ip -4
   ```
   It looks like `100.x.y.z`. Write it down — step 3 needs it, and
   Muse needs it later.

## 1. Get the project onto the PC

Clone the repo (or copy the `projects\muse-pc-bridge` folder from an
existing checkout) and check out the bridge branch:

```powershell
git clone https://github.com/magicmantheace/shiny-dollop.git
cd shiny-dollop
git checkout muse-pc-bridge/foundation
cd projects\muse-pc-bridge
```

## 2. Run the test suite (Windows-side verification)

```powershell
python -m unittest discover -s tests -v
```

Expect: **all tests pass**. (On Windows the suite drives the `cmd`
shell paths.) If anything fails, stop and show Muse the output
before continuing.

## 3. Generate the config and token

```powershell
cd agent
python bridge_agent.py --init
```

This writes `agent\config.json` and prints the token **once**.
Copy the token somewhere safe for step 6 — it is the key to full
shell access on this PC. `config.json` is git-ignored; never commit
it, never paste the token into a repo file or an issue.

## 4. Point the agent at the Tailscale address

Open `agent\config.json` in a text editor and change only:

```json
"host": "100.x.y.z"
```

— using the address from step 0. Leave `port` at `8765` unless it's
taken. Do **not** set `host` to `0.0.0.0`: that would listen on the
LAN too, and the agent prints a loud warning if you do.

> Firewall note: because the agent binds **only** to the Tailscale
> `100.x` address, only tailnet devices can reach it. If Windows
> Firewall prompts about Python the first time the agent starts,
> you can safely **deny** public/private network access — the
> Tailscale interface is all it needs. If the client check in step 5
> fails, allow Python on the Tailscale adapter only.

## 5. Start the agent and verify it from the PC itself

Double-click `scripts\start-bridge.cmd` (or run it from PowerShell).
A console window opens and stays open — **that window is the running
indicator; closing it is the kill switch.**

In a second PowerShell window, verify locally first (this checks the
agent without involving the tailnet):

```powershell
cd <repo>\projects\muse-pc-bridge\client
$env:MUSE_PC_BRIDGE_URL = "http://100.x.y.z:8765"
$env:MUSE_PC_BRIDGE_TOKEN = "<the token from step 3>"
python bridge_client.py status
python bridge_client.py exec hostname
```

Expect `status` to report this PC's hostname and `exec` to print it
again. Then check the audit log recorded both:

```powershell
Get-Content ..\agent\logs\audit.jsonl -Tail 5
```

## 6. Hand over to Claude

Send Muse, **out-of-band** (not in git, not in a repo file):

- the PC's Tailscale IP (`100.x.y.z`),
- the port (8765 unless changed),
- the token from step 3.

Muse stores the token in its client environment only and runs a
`status` check over the tailnet. After that, the bridge is live.

## Day-to-day

- **Start:** run `scripts\start-bridge.cmd`; leave the console open.
- **Stop (kill switch):** close the console window, or focus it and
  press Ctrl+C. Access ends immediately.
- **Optional autostart:** `scripts\install-autostart.ps1` registers a
  logon task that opens the same visible console at logon. Optional
  in v0; the manual start above is the default.
- **Review what Muse did:** read `agent\logs\audit.jsonl` — every
  request, command, and file transfer, in order.
- **Rotate the token:** stop the agent, delete `agent\config.json`,
  redo steps 3–6.

## Upgrading to v1 (from the live v0.1 install)

v1 is backward-compatible with the v0 config: every new setting is
optional (see `config.example.json` for the full shape). The first
cutover is manual — v0.1 has no self-update endpoint to stage it
with. Steps, in order:

1. **Stop the v0 agent** — close its console window (the kill
   switch). Access is down during the upgrade; that's expected.
2. **Update the checkout** to the v1 tip of
   `muse-pc-bridge/foundation`:
   ```powershell
   cd D:\shiny-dollop
   git pull
   cd projects\muse-pc-bridge
   ```
   Your `agent\config.json`, `agent\logs\`, and
   `agent\bridge-files\` are git-ignored and stay untouched.
3. **Run the suite on Windows:**
   ```powershell
   python -m unittest discover -s tests -v
   ```
   Expect all tests to pass except one Windows-only skip pattern in
   reverse: on Windows the real-screenshot test runs and the
   POSIX-only 501 tests skip. If anything fails, stop and show
   Muse the output — do not cut over on a red suite.
4. **(Optional) name extra file roots** in `agent\config.json` —
   e.g. add `"file_roots": [{"name": "default", "path":
   "./bridge-files"}, {"name": "work", "path": "D:\\bridge-work"}]`.
   Skip this to keep exactly the v0 behavior.
5. **Restart, one of two ways:**
   - Same as v0: `scripts\start-bridge.cmd` (single agent console).
   - Supervised (v1 service form): `scripts\start-bridge-service.cmd`
     — a supervisor console that restarts the agent if it crashes
     and applies staged self-updates with automatic rollback.
     Closing the supervisor console stops everything (kill switch
     preserved).
6. **Verify:** from the PC, `client\bridge_client.py status` should
   report `"version": "1.0.0"` with a capabilities list; then Muse
   verifies from the VM over the tailnet as before.
7. **(Optional) autostart the supervised form:**
   ```powershell
   scripts\bridge-service.ps1 -Action install
   ```
   This registers a per-user logon Scheduled Task. **It may prompt
   for UAC — run it yourself, interactively.** `-Action status`,
   `-Action start`, `-Action stop`, and `-Action uninstall` manage
   it afterwards.

After cutover, later updates can ride the v1 self-update: Muse
stages a signed-by-hash bundle via `POST /v1/update/stage`, and the
supervisor applies it at the next restart with a health check and
automatic rollback. (Self-update only exists in the supervised
form.)

## v1.1 boot topology (core at boot, avatar at logon) — OPTIONAL, owner-activated

**Status: built and VM-verified 2026-11-08; NOT activated.**
Activation is a separate, owner-approved step — nothing in the
v1.1 branch installs a task or changes the running bridge by
itself. The production bridge keeps running in the avatar form
until you do this.

### What starts when

| When | What | Task | Runs as |
| --- | --- | --- | --- |
| Machine boot | **Core**: `supervisor.py --headless` (pythonw) → agent | `Muse PC Bridge (core)` (new) | SYSTEM |
| User logon | **Avatar**: `supervisor_gui.py`, attaches display-only to the core | `Muse PC Bridge (avatar)` (existing) | the user |
| User logon | **Session helper**: hosted by the avatar process; serves the desktop routes on loopback for the core to broker to | (inside the avatar process) | the user |
| — (rollback) | Console supervisor form | `Muse PC Bridge (supervised)` (existing, currently disabled) | the user |

The core does no GUI work. `display-state.json` is published by
the supervisor core in every form, so it stays fresh before logon
and with no window open. The avatar attaching does not own the
agent: closing it leaves the bridge running (its menu reads
"Close avatar (bridge keeps running)"). If the avatar starts and
no core answers, it falls back to running its own supervisor,
exactly as before v1.1.

**Desktop routes in this topology** (screenshot, input, UIA,
clipboard, GUI launch): the core runs in session 0, whose desktop
is not yours, so it never serves these itself. While the avatar
is running, its session helper serves them in your session and
the core brokers requests to it transparently (same port, same
token; both sides audit). Before logon — or after you close the
avatar — no helper is registered and those routes answer an
honest 501 saying so; everything else (exec, files, jobs, WoL,
UAC status) works from the core at any time. Set
`"session_broker": false` in `config.json` to disable brokering.

Stopping is audited: `bridge-core.ps1 -Action stop` (and
`bridge-service.ps1 -Action stop`) first ask the supervisor for a
graceful shutdown via a stop-request file, so the audit log gains
its `server_stop` entry; a direct process kill is only the
fallback if the supervisor does not answer within 20 s.

### Activation (owner, interactive, in order)

1. Pull the v1.1 branch on the PC checkout and run the suite:
   `python -m unittest discover -s tests -v` — expect OK under
   Windows Python (skips for POSIX-only tests are expected, the
   reverse of the VM).
2. Deploy agent 1.1.0 to production the usual way (staged
   self-update or a manual swap during a stopped window) and
   confirm `client\bridge_client.py status` reports
   `"version": "1.1.0"` and a `uac_prompt` field.
3. Stop the bridge (avatar kill switch) so no supervisor owns the
   agent port.
4. From an **elevated** PowerShell in `scripts\`:
   `.\bridge-core.ps1 -Action install` — expect a UAC prompt
   (creating a SYSTEM task needs it); the script also warns if
   the old `(supervised)` logon task is still enabled — leave it
   disabled; it is the rollback path, not a second owner.
5. `.\bridge-core.ps1 -Action start`, wait ~10 s, then
   `.\bridge-core.ps1 -Action status` — the supervisor status
   file should show `running`; from the VM, Muse's `status`
   check should answer **without anyone logged on** after a
   reboot (that is the point of the exercise — verify it with an
   actual reboot when convenient).
6. Log on: the avatar task starts the GUI, which should attach —
   its state follows the already-running agent, and closing it
   (to test) leaves `status` answering from the VM.

### Rollback

`.\bridge-core.ps1 -Action stop`, then
`.\bridge-core.ps1 -Action uninstall`, then start the avatar form
(or re-enable the `(supervised)` console task via
`bridge-service.ps1`). Config, token, state dir, and audit log
are shared by all forms and are not touched by any of this.

### v1.1 feature checks on the PC (the VM could not prove these)

1. **UAC signal**: with the bridge running, trigger an elevation
   prompt (e.g. run `bridge-core.ps1 -Action status` from a
   non-elevated shell via "Run as administrator" on something
   harmless, or install anything). While the prompt is up:
   `client\bridge_client.py status` shows
   `"uac_prompt": {"active": true, ...}`, the avatar reads
   "Approval needed at PC", and `logs\audit.jsonl` gains a
   `uac_prompt_shown` line. Dismiss the prompt: status flips back
   and the audit log gains `uac_prompt_cleared` with the seconds
   it waited.
2. **GUI launch**: `client\bridge_client.py spawn-gui <path to
   Godot exe>` (or any GUI app) — the window opens on the PC,
   `processes` shows it alive with `gui: true` and the app's own
   pid, and `processes <id> kill` closes it. This replaces the old
   exec + Start-Process workaround.
5. **Session broker (boot topology only)**: with the core running
   and nobody logged on, `status` answers but a screenshot request
   returns 501 (no helper yet). Log on (the avatar starts and
   registers its helper): the same screenshot now succeeds and
   shows the real desktop, `status` reports
   `"session_helper": {"registered": true, ...}`, and the audit
   log shows the request twice — the core's entry marked
   `via: session-broker` and the helper's `via: session-helper`.
   A GUI spawn through the core likewise opens its window on the
   real desktop.
3. **Wake-on-LAN, from the PC**: note another LAN machine's MAC
   (`ipconfig /all` on it), power it down with WoL enabled in its
   BIOS, then `client\bridge_client.py wol <MAC> --broadcast
   <subnet broadcast, e.g. 192.168.1.255>` — it should wake.
4. **Wake-on-LAN, to the PC**: from any other awake device on the
   LAN, run `python scripts\wol-send.py <the PC NIC's MAC>
   --broadcast <subnet broadcast>` while the PC is asleep — the
   PC should wake. (The bridge cannot do this direction itself; a
   sleeping PC runs no agent. One-time prerequisites on the PC:
   WoL enabled in BIOS/UEFI, the wired NIC allowed to wake the
   machine in Device Manager, wired Ethernet connected.)
