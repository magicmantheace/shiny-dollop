# AI Dungeon Master

**Status:** MVP FUNCTIONAL — implemented and verified on Linux; Windows 11 behavior is implemented but not verified on target OS (see `docs/IMPLEMENTATION_STATUS.md`).

**Priority:** 16 of 17 in the approved intake queue.
**Category:** Tabletop RPG desktop
**Repository workspace:** `projects/ai-dungeon-master/`

## Purpose

Support offline-capable tabletop campaigns with auditable rules, dice, memory, NPCs and optional local AI narration.

**Foundational rule:** the deterministic house-rules engine is authoritative. Narration is optional flavor attached to log entries and can never decide or change a rules outcome. The ruleset is original (four attributes, 2d6 checks, HP) — no published rulebook content is used.

## MVP (implemented)

Create a campaign and characters, roll dice, run initiative/combat with logged state, save, and resume — plus sessions and notes, NPC/location memory with search, campaign export/import, worldbuilding-backup and dungeon-manifest imports, and mock/local narration.

## Install and launch

Prerequisites: Node.js 22+ and npm.

```bash
cd projects/ai-dungeon-master/app
npm install
npm run build
npx electron .          # launch the app
```

Development: `npm run dev` (Vite renderer) with `npm run build:main` and `npx electron .` for the shell.

Verification:

```bash
npm test                # 40 tests (backend + renderer)
npm run typecheck
npm run lint
npm run smoke           # full acceptance workflow in the packaged main (needs xvfb on Linux)
```

## Data and formats

- Local SQLite database (`aidm.sqlite` in the OS user-data folder). No account, no cloud, no network calls except an optionally configured **loopback-only** narration endpoint.
- Campaign backup: `{ "format": "ai-dungeon-master/campaign", "formatVersion": "1.0.0", ... }` — byte-deterministic JSON; import reproduces the campaign.
- Imports accepted: `worldbuilding-manager.project` v1 backups (→ memory entries) and `procedural-dungeon-designer/map` v1 manifests (→ location memory entry). Unknown major versions are rejected with named errors.

## Dice auditability

Each campaign has a dice seed; the PRNG stream state is stored on the campaign and recorded with every roll (dice, modifier, total, state before/after). Any roll in the session log can be replayed exactly from its recorded state — see `app/shared/dice.ts`.

## Project docs

[Project instructions](AGENTS.md) · [development handoff](docs/MUSE_HANDOFF.md) · [specification](docs/PRODUCT_SPEC.md) · [test plan](docs/TEST_PLAN.md) · [implementation status](docs/IMPLEMENTATION_STATUS.md)
