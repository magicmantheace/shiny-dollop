# PROJECT_QUEUE.md — application build queue

> **Note:** this queue lives here (at
> `projects/game-save-manager/docs/PROJECT_QUEUE.md`) until the owner
> approves a shared repo-level tracker. A candidate repo-level location is
> `projects/MUSE_PROJECT_QUEUE.md` — do NOT create it without the owner's
> explicit approval.

17-application queue from the owner's handoff, in the owner's order.
Statuses: **MVP functional / review ready**, **Not started**.

| # | Project | Status | Branch / evidence |
|---|---|---|---|
| 1 | **Game Save Manager** (Windows desktop app: discover, back up, version, restore PC game saves; Electron + React + TS) | **MVP functional / review ready** | Branch `game-save-manager/initial-development`. Backend 42/42 tests, React UI 24/24 tests — **66/66 green** (2026-10-23, Linux VM), plus typecheck, lint, build, and a production window smoke test, all green. Portable Windows zip built on Linux (see `docs/WINDOWS_INSTALL.md`). No push, no PR — held for the owner's review. |
| 2 | Concrete Operations Manager | Not started | — |
| 3 | Volumetric Concrete Mix Calculator | Not started | — |
| 4 | PC Storage and Duplicate Finder | Not started | — |
| 5 | Offline Personal Finance Simulator | Not started | — |
| 6 | Household Inventory and Warranty Tracker | Not started | — |
| 7 | Game Library Metadata Enricher | Not started | — |
| 8 | Windows Game Performance Profiles | Not started | — |
| 9 | Digital Product Template Factory | Not started | — |
| 10 | Small Business Website Generator | Not started | — |
| 11 | Personal Knowledge Vault | Not started | — |
| 12 | Desktop Automation Builder | Not started | — |
| 13 | Local AI Command Center | Not started | — |
| 14 | Novel and Worldbuilding Manager | Not started | — |
| 15 | Procedural Dungeon Designer | Not started | — |
| 16 | AI Dungeon Master | Not started | — |
| 17 | Crawl Live Spectator Desktop | Not started | — |

Project 1's full evidence ledger lives in
`docs/IMPLEMENTATION_TRACKER.md` (Verified vs Pending).
Windows-only behaviors remain pending until validated on the owner's
Windows machine; they are never claimed as verified here.
