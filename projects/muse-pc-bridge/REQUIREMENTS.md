# Requirements — muse-pc-bridge

## Runtime

- **Python >= 3.11** (agent and client). No third-party packages —
  Python standard library only. There is intentionally no
  `requirements.txt` with dependencies; nothing to `pip install`.
- **Target platform (agent):** Windows 11 on the owner's PC.
- **Development support:** the agent and client also run on POSIX
  (Linux/macOS) so the test suite and protocol work can be developed
  and verified off-Windows. POSIX runs use `/bin/sh` as the `posix`
  shell. Windows-only behavior (PowerShell/cmd shells, Tailscale
  binding on the owner's PC) is **not** proven by POSIX runs — see
  `docs/TEST_PLAN.md`.
- **Client platform:** anywhere Python >= 3.11 runs (Muse's VM is
  Linux).

## Network

- **Tailscale** installed and signed in on the owner's PC (agent side)
  and on Muse's VM (client side). The agent binds to the PC's
  Tailscale `100.x` address only; no inbound access from the LAN or
  the public internet is required or wanted.
- One TCP port on the tailnet interface (default `8765`,
  configurable).

## Owner-side prerequisites for install

- Python 3.11+ on the PC with `python` on PATH.
- Tailscale running on the PC; the PC's Tailscale IPv4 address
  (`tailscale ip -4`).
- A few MB of disk for the agent, its file root, and the audit log.
