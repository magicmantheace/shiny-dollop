# Implementation status — Procedural Dungeon Designer

- **Overall status:** MVP FUNCTIONAL / REVIEW READY (implemented and verified on Linux; Windows 11 behavior implemented but not verified on target OS)
- **Priority:** 15/17
- **Branch:** `procedural-dungeon-designer/mvp`
- **Build validated:** Yes — `npm run build` (renderer + main) green on Linux
- **Automated tests executed:** Yes — 44/44 passing (38 backend + 6 renderer)
- **End-to-end MVP verified:** Yes — packaged-main smoke (`--pdd-smoke`, under xvfb) runs the full acceptance sequence and prints `SMOKE_OK`; see `docs/TEST_PLAN.md`
- **Owner review:** Pending (PR intentionally left unmerged)

## What is implemented

Desktop app (Electron 45 + React 19 + TypeScript strict + Vite, `node:sqlite`,
zod-validated IPC) under `app/`. Fully offline; no network calls anywhere.

- **Deterministic generator library** (`app/shared/generator.ts`): all
  randomness flows from one mulberry32 PRNG stream seeded by an FNV-1a hash
  of the seed + params. No `Math.random()`, no `Date` in generation paths.
  Same seed + params produce a byte-identical map and export, across runs
  and process restarts (proven by tests and the smoke run).
- **Connectivity by construction + proof**: room centers are joined by a
  minimum spanning tree of carved L-corridors plus extra loop corridors;
  `app/shared/validate.ts` independently proves reachability with BFS from
  the entrance and names any unreachable rooms.
- **Two original themes** (`app/shared/themes.ts`): Sunken Crypt and Ember
  Deep. Each changes room naming, encounter/trap/hazard/treasure tables
  (original names + budget costs), and the map palette.
- **Encounter/hazard budgets**: every placement has a cost from its theme
  table. Budget limit rule: `30 + 20 x difficulty + 2 x requested rooms`.
  Generation never exceeds the budget. **Edit rule (documented): edits are
  BLOCKED** — adding a placement that would exceed the budget fails with
  `BUDGET_EXCEEDED` and leaves the map unchanged. Costs/names always come
  from the theme table; unknown keys fail with `PLACEMENT_UNKNOWN`.
- **Map view + editor**: SVG grid rendering (walls/rooms/corridors from the
  theme palette, entrance tinted, selected room outlined), click-to-inspect
  rooms, placement add/remove/move on saved dungeons, budget meter, live
  connectivity readout, print view (on-screen toggle + `@media print`
  black-on-white rules).
- **Persistence**: saved dungeons (seed + params + the full map including
  user edits) in SQLite via `node:sqlite`; reopening restores exactly.
- **Export/import**: versioned JSON envelope
  `{ format: "procedural-dungeon-designer/map", formatVersion: "1.0.0", name, map }`
  serialized with a stable key-sorting stringify — byte-identical for the
  same map + name. This envelope is the manifest other tools (e.g. AI
  Dungeon Master) can consume. Markdown export renders an ASCII map plus a
  per-room placement listing. Import rejects non-JSON / wrong format
  (`IMPORT_INVALID`), unknown major versions
  (`IMPORT_VERSION_UNSUPPORTED`), oversized input (`INPUT_TOO_LARGE`),
  and disconnected maps (`IMPORT_INVALID`); `budgetUsed` is always
  recomputed from placements, never trusted from the file.
- **Preload hygiene**: the sandboxed preload is self-contained at runtime —
  literal channel strings and a type-only shared import; a regression test
  (`tests/backend/preload-hygiene.test.ts`) guards this.

## Implemented but not verified on target OS

- Windows 11 click-through of the packaged app, real printing, and NSIS
  packaging. No Wine is available in the build environment; no code signing.

## Not in MVP (planned)

- Endpoint-style integrations (AI Dungeon Master consuming the manifest is
  a consumer-side step; the export contract is ready and documented above).
- Room-shape editing, corridor editing, doors/locks, multi-level dungeons,
  theme authoring UI.

## Verification summary

See `docs/TEST_PLAN.md` for the full record: 56/56 tests, typecheck, lint,
build, and packaged-main smoke all green (Linux, Node 24).

Codex-review fix cycle (2026-10-24): save/import now reject placements
whose costs (or kind/key) do not match the theme tables, so zeroed costs
cannot defeat the budget; the connectivity BFS no longer seeds a walled
or out-of-bounds entrance center; and the print-view toggle moved to the
header (outside every hidden panel) as a visible Exit print view control,
so an unsaved map can no longer be trapped in print view.

Codex-review fix cycle 2 (2026-10-24): IPC failures now travel as a
structured { ok, value | error } envelope returned from the handlers and
unwrapped in the preload, so named errors (e.g. BUDGET_EXCEEDED) survive
the Electron bridge instead of being reduced to their message; and the
per-room placement cap (50, shared constant with roomSchema) is enforced
by add/move placement edits (PLACEMENT_LIMIT_EXCEEDED), so an edit can
no longer persist a map that validation, saving and import would reject.
