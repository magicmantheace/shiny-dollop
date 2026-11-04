# Drabbit Pet — Muse Handoff

## What this project is

A Tamagotchi-style virtual pet: the renfaire drabbit (furry winged
dragon-rabbit, Imaginarium Galleries shoulder-puppet style). One pet,
two apps — an Electron desktop pet that owns the pet and its save, and
a Kotlin Android companion that connects to it. Both are driven by one
framework-free TypeScript pet brain in `core/`. Full design:
[PET_DESIGN.md](PET_DESIGN.md) (simulation spec) and
[DESIGN.md](DESIGN.md) (architecture + companion protocol draft).

## Current state (2026-11-04)

**P0 — foundation + design: DONE on this branch.**
README, AGENTS.md, PET_DESIGN, DESIGN, TEST_PLAN, this handoff,
monorepo layout (`core/`, `desktop/`, `android/`, `assets/` with
placeholder READMEs for unbuilt slices), root README registration.

**P1 — pet brain (`core/`): DONE on this branch.**
TypeScript, strict, zero runtime dependencies (devDeps: typescript,
vitest, tsx, @types/node). Deterministic 1-minute-step simulation:
needs/health/care-score model, egg→adult lifecycle, care-shaped adult
forms (radiant/content/scruffy), messes, sickness, death + lineage,
canonical JSON persistence with schema versioning and a migration
stub, append-only capped event log, headless demo.

**P2–P4: NOT STARTED.** Desktop shell, companion server, and Android
app are placeholders plus the protocol draft in DESIGN.md.

## Verified (this Linux VM, Node v24.22.1, 2026-11-04)

- `npm --prefix core test` → **46 tests, 46 passed** (vitest 3.2.7):
  decay math per stage, asleep modifiers, egg rules, stage thresholds,
  offline catch-up == live ticking **byte-identical** across 1-jump /
  hourly / minute chunking over 24 h, every action's effects and error
  paths, sickness onset/cure, messes, neglect death (~14.8 h, cause
  sickness — probed and pinned as a regression test), adult forms in
  all three care bands, save round-trip byte-identical, bad-save
  rejection.
- `npm --prefix core run typecheck` and `npm run build` → clean under
  `tsc` strict.
- `npm --prefix core run demo` → exit 0; a scripted caretaker raises
  "Pip" from egg to a **radiant** adult over ~19 simulated hours,
  printing a diary of hatches, stage changes, messes, sleeps, and
  status lines (35 events, 3,253-byte save).

## NOT verified (no evidence exists yet)

- Anything Windows: the Electron shell doesn't exist yet (P2).
- Anything Android: no app, no SDK check, no device run (P4).
- The companion protocol is a **draft on paper only** — no server has
  run (P3).
- Sprite/art assets: none exist; `assets/` is a placeholder (P2).

## Working rules for the next agent

- Repo root `AGENTS.md` + project `AGENTS.md` bind; the core's
  determinism invariant (no clocks, no hidden tick counters, hashed
  rolls) is a hard rule, not a style preference.
- PET_DESIGN.md and `core/src/constants.ts` must change together.
- Slices land in queue order (P2 desktop → P3 server → P4 Android),
  each verified before the next; keep this file's verified/unverified
  split honest after every slice.

## Next step

P2 — the Electron desktop pet (see the build queue). Owner-side
checkpoint after P2: first visual check of the pet on the owner's
Windows PC.
