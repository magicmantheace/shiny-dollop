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
| `client/bridge_client.py` | Muse-side CLI (status / exec / list / get / put) |
| `scripts/start-bridge.cmd` | start the agent in a visible console |
| `scripts/install-autostart.ps1` | OPTIONAL logon autostart (same visible console) |
| `config.example.json` | config shape (real `config.json` is git-ignored) |
| `tests/test_bridge.py` | end-to-end suite: boots the real server on loopback |
| `docs/DESIGN.md` | architecture, wire protocol, threat model |
| `docs/INSTALL_WINDOWS.md` | exact Windows install + verification steps |
| `docs/CHATGPT_INSTALL_HANDOFF.md` | delegated install (D: drive) that stops before the owner's token/final-setup steps |
| `docs/TEST_PLAN.md` | what the tests prove — and what they cannot |
| `docs/MUSE_HANDOFF.md` | current state, decisions, next steps |
| `REQUIREMENTS.md` | Python >= 3.11, stdlib only, Tailscale |

## Status — honest version

**v0 foundation (agent 0.1.0), verified on Muse's Linux VM only:**
the suite (10 tests) passes and a client↔agent smoke test succeeded
there. **Not yet verified:** anything on Windows (PowerShell/cmd,
the .cmd launcher), the real Tailscale link, and the autostart task.
Those are owner-PC checks built into the install doc; until they are
done, this project is *implemented and VM-tested*, not *installed*.
See `docs/MUSE_HANDOFF.md`.
