# START HERE — META MUSE DEVELOPMENT HANDOFF

**Date:** 2026-10-22  
**Repository:** `magicmantheace/shiny-dollop`  
**Active project:** `projects/universal-game-launcher/`  
**Priority:** HIGH — real, usable Windows desktop app  
**Previous concept:** GitHub Development Command Center is **PARKED**, not to be worked on.

## Owner's instruction

**Create a universal PC game launcher.** It should organize installed games from Steam, Epic Games, Battle.net and user-selected executables in a single polished library, launch them safely, save favorites/preferences and track play sessions. This is a practical evaluation of whether Muse can produce a useful, installable, maintainable application, not a toy exercise.

The entire app and its configuration MUST remain under `projects/universal-game-launcher/` because `shiny-dollop` is a permanent multi-project repo. Do not modify the repo root beyond permissioned index changes. Do not modify the parked project.

## Execution order (do the work, do not merely propose it)

1. Read `../../AGENTS.md`, `AGENTS.md`, this handoff and all project docs.
2. Inspect files, git status, available build tools, and existing dependencies. Preserve any work already in progress.
3. Choose an exact supported Electron + React + TypeScript toolchain or document a technically justified alternative.
4. Implement the first runnable vertical slice: window + library, **manual Add Game**, durable local database and **successful launch of user-selected executable** with confirmation/safety gates.
5. Add Steam discovery via supported local artifacts, then Epic, then Battle.net where possible, keeping each adapter isolated.
6. Add real store-native launch flows where validated, library artwork/metadata, game session/playtime tracking, sorting/filtering/favorites.
7. Package a Windows x64 installer, test install/start/launch/restart/uninstall in Windows when available, and document unavoidable platform limitations.
8. Run available lint, typecheck, unit, integration, smoke and security tests. Fix observed errors rather than merely writing tests.
9. Update implementation checklist, test evidence and README; commit the working work in small reviewable steps and report real progress and blockers.

**Keep implementing until a usable milestone is reached.** If a vendor client cannot be directly launched with a reliably validated URI, implement a fallback that opens that client's library or clearly instructs the user to launch there. Do not forge unsupported vendor protocol commands or present the client opening as a guaranteed game launch.

## Real product bar

- A responsive desktop UI with accessible navigation and actual buttons.
- Locally discovered games, not an example catalog.
- No online account required by **our** app.
- Safe, explicit launch flows for manual executable and verified client launch schemes.
- Persist library items, scanned source ids, favorite status, custom covers and play sessions after restart.
- Idempotent re-scans that avoid duplicates and preserve manual edits.
- Honest offline, missing-client, permission-denied and launch-error states.
- Do not bypass platform restrictions, run as admin, alter game installations or scan user directories indiscriminately.
- Low overhead while games are active; no tracking when disabled.

## Definition of "done" for the first useful demo

The user can run a development build, use a file picker to add a local executable, see the correct title, launch it, stop it, see a session entry, favorite it and restart without losing it. This is the minimum meaningful vertical slice; it is **not** the complete multi-store MVP. Then finish the rest of MVP defined in `TEST_PLAN.md`.

## What you must report after each session

- Files changed and commits/branch.
- Which app workflows now actually work.
- Exact commands executed and results.
- Verified Windows behavior vs untested Windows-only behavior.
- Known unresolved store integration limitations.
- Next concrete implementation step.

Do not request the owner to manually paste code that you can write into this project.
