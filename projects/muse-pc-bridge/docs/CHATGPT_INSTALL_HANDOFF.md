# Handoff: install the Muse PC Bridge on Adam's PC (for ChatGPT)

You are installing a small program on Adam's Windows PC. Another AI
(Muse, called Nyx) will use it later to run commands and transfer
files on this PC over Tailscale. Your job is everything **except** the
final setup — Adam does the last steps himself. Read the whole
document before starting.

## The one hard rule

**Stop before step 5.** Step 5 generates the access token. That token
is shown exactly once, and Adam must be the person who runs it and
holds it. Do not run `--init`, do not open or create `config.json`,
and never type, paste, or store a token anywhere. If you run `--init`
by accident: stop immediately, tell Adam, delete
`agent\config.json`, and let Adam redo step 5 himself so the token he
holds is the live one.

## Where it installs

Everything goes on the **D: drive**:

- Repo checkout: `D:\shiny-dollop`
- The bridge itself: `D:\shiny-dollop\projects\muse-pc-bridge`

## Step 0 — Prerequisites (report, don't fix silently)

In PowerShell, check and record the results:

```powershell
python --version
git --version
tailscale ip -4
```

- Python must be **3.11 or newer** (the bridge is standard-library
  only; there is nothing to pip-install).
- Git is needed for step 1. If Git is missing, use the zip fallback
  in step 1 instead.
- Tailscale must be installed, running, and signed in. `tailscale ip
  -4` prints this PC's tailnet address (`100.x.y.z`). **Write it down
  and include it in your report** — Adam needs it in step 6. If
  Tailscale is not signed in, stop and tell Adam; signing in is his
  account action, not yours.

## Step 1 — Get the code onto D:

If `D:\shiny-dollop` already exists and is a git checkout of
`magicmantheace/shiny-dollop`, use it (run `git fetch` inside it).
Otherwise clone:

```powershell
cd D:\
git clone https://github.com/magicmantheace/shiny-dollop.git
cd D:\shiny-dollop
git checkout muse-pc-bridge/foundation
cd D:\shiny-dollop\projects\muse-pc-bridge
```

Fallback (no Git): download
`https://github.com/magicmantheace/shiny-dollop/archive/refs/heads/muse-pc-bridge/foundation.zip`
and extract it so the project lands at
`D:\shiny-dollop\projects\muse-pc-bridge` (rename the extracted
`shiny-dollop-muse-pc-bridge-foundation` folder to `shiny-dollop`).
Note in your report if you used the fallback.

Verify the layout exists before continuing:

```powershell
Test-Path D:\shiny-dollop\projects\muse-pc-bridge\agent\bridge_agent.py
```

Expected: `True`.

## Step 2 — Run the test suite on Windows

```powershell
cd D:\shiny-dollop\projects\muse-pc-bridge
python -m unittest discover -s tests -v
```

Expected: **10 tests, all passing** (the suite boots the real server
on loopback and drives the Windows `cmd` shell paths). If anything
fails: **stop**. Include the full failing output in your report and
do not continue to step 3. These tests have only ever run on a Linux
VM before; a Windows failure is exactly what this step exists to
catch, and Nyx needs the output.

## Step 3 — Confirm the launch script is present

```powershell
Test-Path D:\shiny-dollop\projects\muse-pc-bridge\scripts\start-bridge.cmd
```

Expected: `True`. Do **not** run it — the agent is not configured
yet, and starting it is Adam's step.

## Step 4 — Report and stop

Leave a PowerShell window open at
`D:\shiny-dollop\projects\muse-pc-bridge` for Adam, and report to
him:

- Python version, Git version (or "zip fallback used")
- Test suite result (exact pass count, or the failure output)
- This PC's Tailscale IPv4 (`100.x.y.z`) from step 0
- Confirmation that the install is at
  `D:\shiny-dollop\projects\muse-pc-bridge`
- One sentence: "Ready for your final setup — the bridge is
  installed and tested but has no token and is not running."

**Do not** do any of these — they are Adam's final setup, not yours:

- `python bridge_agent.py --init` (token generation)
- Editing `config.json`
- Starting the bridge
- Installing the optional autostart task
  (`scripts\install-autostart.ps1`) — Adam decides on that later
- Approving any Tailscale device — Adam approves Nyx's VM (device
  name `muse`) himself, with Nyx, in their own chat

---

## For Adam — your final setup (about 5 minutes, after ChatGPT reports)

Full detail: `docs\INSTALL_WINDOWS.md` steps 3–6. The short version:

```powershell
cd D:\shiny-dollop\projects\muse-pc-bridge\agent
python bridge_agent.py --init
```

1. The token prints **once** — copy it somewhere safe.
2. Open `agent\config.json`, set `"host"` to the PC's Tailscale IP
   from ChatGPT's report. Leave the port at `8765`. Never use
   `0.0.0.0`.
3. Start it: double-click `scripts\start-bridge.cmd` back in the
   project folder. The console window that stays open **is** the
   bridge running; closing it is the kill switch. If Windows
   Firewall asks about Python, you can deny public/private access —
   the Tailscale interface is all it needs.
4. Send Nyx, in your chat with Nyx (never in git): the Tailscale IP,
   port 8765, and the token. Nyx will also give you a Tailscale link
   to approve this VM joining your tailnet as the device `muse` —
   that approval is yours to click, and you can remove the device
   from your Tailscale admin console at any time.
5. Nyx runs a `status` check over the tailnet. When it answers with
   this PC's hostname, the bridge is live. Everything Nyx does
   through it is written to `agent\logs\audit.jsonl` on this PC.
