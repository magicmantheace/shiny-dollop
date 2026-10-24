# Test plan — AI Dungeon Master

**Current test status:** RUN — 40/40 passing on 2026-10-23 (Linux VM, Node 24). See the verification record below.

## Required automated and integration scenarios

- Dice distribution bounds and seed replay — `tests/backend/dice.test.ts`: notation parsing/validation (bad notation → `DICE_NOTATION_INVALID`), deterministic sequences from a seed, every roll replaying exactly from its recorded stream state, bounds over hundreds of draws.
- Combat state transactions — `tests/backend/encounters.test.ts`: logged initiative ordering, turn/round advance, damage/heal HP math with clamping and before/after log entries, second-active-encounter refusal, ended-encounter guards.
- Campaign save/resume integrity — `tests/backend/campaigns.test.ts` + smoke: persistence across DB close/reopen, dice stream continuing seamlessly, active encounter resuming exactly mid-fight.
- Optional AI cannot silently change canonical dice/results — `tests/backend/narration.test.ts`: after narration, the entry's text/detail/seq, the campaign dice state, the log length, and all character HP are byte-identical; narration only fills the entry's narration fields.
- Missing model graceful fallback — same file: unreachable loopback endpoint → `mock-fallback` narration; a live loopback test server → `local` narration; cloud endpoints rejected in settings.

## Cross-cutting tests

- Malformed/oversized inputs — IPC zod boundary tests (`tests/backend/ipc.test.ts`), stat/HP validation, 2,000,001-char import → `INPUT_TOO_LARGE`.
- Export/import consistency — `tests/backend/imports.test.ts`: byte-identical export, fresh-DB round-trip byte-identical, id-collision remap, corrupt/unknown-major rejection; worldbuilding and dungeon contract fixtures (real v1 shapes) plus cross-format and unknown-major rejection for both.
- Memory search — substring/tag search incl. case-insensitivity.
- Preload hygiene — `tests/backend/preload-hygiene.test.ts`: type-only shared imports, literal channel strings, no `require(`, and the built preload has no runtime require of project modules.
- Renderer — `tests/renderer/App.test.tsx`: full UI workflow against an in-memory API backed by the real shared dice engine (create campaign → characters → roll → log → encounter → damage → end; narrate; memory add/search; error banner on bad notation).

## End-to-end MVP verification

Create a campaign and characters, roll dice, run initiative/combat with logged state, save, and resume — executed by `npm run smoke`, which runs the packaged Electron main under xvfb and performs exactly this workflow against a real SQLite file, including closing and reopening the database mid-encounter and an export/import pass. Result: `SMOKE_OK`.

## Mandatory verification record

Run: 2026-10-23 · environment: Linux VM, Node 24, Electron 45 under xvfb · branch `ai-dungeon-master/mvp`.

| Command | Result |
| --- | --- |
| `npm test` | **40 passed / 40** (8 files: dice 6, campaigns 7, encounters 5, narration 4, imports 7, ipc 3, preload-hygiene 4, renderer 4) |
| `npm run typecheck` | clean |
| `npm run lint` | clean |
| `npm run build` | green |
| `npm run smoke` | SMOKE PASS (`SMOKE_OK` printed by the packaged main) |

Platform gaps: Windows 11 execution and a real Ollama endpoint on the owner's hardware were not run here and are labeled "implemented but not verified on target OS" in `docs/IMPLEMENTATION_STATUS.md`. No release or owner-acceptance claim is made.
