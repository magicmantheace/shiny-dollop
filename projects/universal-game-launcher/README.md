# Universal PC Game Launcher

**Project status:** ACTIVE — M0 (scaffold), M1 (manual launcher), M2 (Steam), M3 (Epic), M4 (Battle.net) and M5 (polish: cover art, filters/a11y, tracking toggle, clear history, perf gate) implemented and verified on Linux 2026-10-22 (182/182 tests). M6 (Windows packaging) in progress — installer build attempted, install guide written. Windows-only behaviors (real `.exe` launch, client discovery, URI handoffs, installer run) implemented per spec, unverified pending Windows.
**Project home:** `projects/universal-game-launcher/` in `magicmantheace/shiny-dollop`.
**Mission:** Deliver a genuine Windows 11 desktop application that finds installed PC games, combines them into one useful library, launches them safely, and preserves local preferences and play history.

The launcher must work **without a web account, subscription, hosted backend, telemetry or permission to alter other projects**. It is not intended to replace Steam/Epic/Battle.net DRM, entitlements, updates, or anti-cheat.

## Start here (Muse)

1. [Global agent rules](../../AGENTS.md)
2. [Local agent rules](AGENTS.md)
3. [Direct build assignment](docs/MUSE_HANDOFF.md)
4. [Product requirements](docs/PRODUCT_SPEC.md)
5. [Architecture and security](docs/ARCHITECTURE.md)
6. [Milestones](docs/IMPLEMENTATION_PLAN.md)
7. [Testing and acceptance](docs/TEST_PLAN.md)

**Do not work on the parked GitHub Development Command Center.**

## Goals

- Find Steam, Epic Games and Battle.net-installed titles where reliable local information exists.
- Add arbitrary installed Windows games or apps manually.
- Present a clean searchable, filterable library with cover art when legitimately available.
- Launch games through the **appropriate official launcher** or an explicitly user-approved executable.
- Track game sessions and approximate playtime honestly; manage favorites and per-game metadata.
- Re-scan without losing manual edits, selections, or history.
- Run offline for library browsing and local game launch (vendor entitlement checks may still require vendor clients/network).
- Package as a Windows x64 installer after functional validation.

## Project-only layout

```text
projects/universal-game-launcher/
  README.md
  AGENTS.md
  .gitignore
  docs/
    MUSE_HANDOFF.md
    PRODUCT_SPEC.md
    ARCHITECTURE.md
    IMPLEMENTATION_PLAN.md
    TEST_PLAN.md
  app/              # Muse creates a self-contained desktop application here
  scripts/          # optional local project utilities
```

No root-level package manager configs. Keep application code, tests, assets, scripts and build outputs **inside this directory**.

## Truthful progress

M0 and M1 are implemented in `app/` (branch `universal-game-launcher/m0-m1-foundation`) and verified on Linux 2026-10-22: 56/56 tests pass, production build + real-window smoke test pass, and the M1 vertical slice (add executable → launch → observed session → favorite → restart persistence) was proven end-to-end with a real spawned process. M2 (Steam), M3 (Epic), M4 (Battle.net) and M5 (polish) followed on branch `universal-game-launcher/m3-m6-complete`: 182/182 tests pass, typecheck + lint clean, production build green. Windows `.exe` launching, real client discovery, URI handoffs and the installer run are implemented per spec but unverified — see `app/README.md` for the full verified-vs-unverified ledger and `docs/IMPLEMENTATION_PLAN.md` for the milestone checklist with evidence.
