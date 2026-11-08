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
