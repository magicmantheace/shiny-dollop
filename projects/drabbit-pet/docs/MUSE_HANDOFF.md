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

**P2 — desktop pet (`desktop/`): DONE on this branch** (pending Nyx
verification, then the owner's first visual check on Windows).
Electron 45 + React 19 + TS strict + Vite, consuming `drabbit-core`
via a `file:` dependency — **the core is unchanged**; no core edits
were needed. Main process owns the one pet state: save in Electron
`userData` (`drabbit-save.json`, atomic temp+rename writes; a corrupt
save is renamed aside, never destroyed, and a fresh egg starts), a
5 s tick service that advances with `Date.now()` (the shell is the
only place clocks live) and persists only on change, plus a final
advance+persist on quit. Frameless transparent always-on-top pet
window (220×220, bottom-right start) roaming the work-area bottom via
a pure, tested planner — long sits, short hops, paused while the pet
sleeps / the care panel is open / tray pause is on. Care-panel
window (single instance, hide-on-close), tray icon (Show pet / Care
panel / Pause roaming / Quit), single-instance lock. Typed IPC
(`pet:getSummary` / `pet:action` / `pet:events` / `pet:openPanel` +
`pet:changed` / `pet:roamState` pushes), contextIsolation on,
nodeIntegration off, sandboxed preload, hand-rolled payload
validation; core `PetError`s return as IPC error results. The pet is
rendered as a hand-drawn inline SVG (all six fur variants, adult-form
flavour, idle/hop/sleep/eat/play/sick/egg/ghost animation states) —
**v1 placeholder art**, structured for later sprite replacement.
Packaging (electron-builder) is future work, out of P2 scope.

**P3–P4: NOT STARTED.** Companion server and Android app are
placeholders plus the protocol draft in DESIGN.md.

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
- `npm --prefix desktop run typecheck` → clean (main, preload,
  renderer, tests — all `tsc` strict).
- `npm --prefix desktop test` → **29 tests, 29 passed** (vitest
  3.2.7): save-store round-trip / missing / corrupt-recovery (bytes
  preserved aside), tick persistence (writes only on change, never
  for a dead pet, scheduler wiring), roaming planner (bounds under
  adversarial randomness, blocked contexts never move, hop→arrive→
  sit), IPC action mapping (every UI kind → the right core action;
  wrong-stage actions raise the core's typed errors) + payload
  validation, and visual-state derivation.
- `npm --prefix desktop run build` → clean: core `tsc`, desktop
  `tsc` (main + preload), Vite production build of both windows.
- `npm --prefix desktop run smoke` → **SMOKE_OK**: the real Electron
  45 binary launched headlessly under Xvfb against a throwaway
  userData, created and persisted a fresh save (canonical JSON with
  the egg's `created` event), and loaded both production windows.

## NOT verified (no evidence exists yet)

- The desktop pet **on Windows**: transparency, always-on-top over
  real windows, tray behaviour, roaming feel, multi-monitor,
  high-DPI. The Xvfb smoke proves launch + window load + save
  creation on Linux — not the Windows desktop experience. That is
  the owner's first-visual-check checkpoint.
- Anything Android: no app, no SDK check, no device run (P4).
- The companion protocol is a **draft on paper only** — no server has
  run (P3).
- Sprite assets: the pet is inline SVG (v1 placeholder art);
  `assets/` holds only the generated app/tray icon.

## Working rules for the next agent

- Repo root `AGENTS.md` + project `AGENTS.md` bind; the core's
  determinism invariant (no clocks, no hidden tick counters, hashed
  rolls) is a hard rule, not a style preference.
- PET_DESIGN.md and `core/src/constants.ts` must change together.
- Slices land in queue order (P2 desktop → P3 server → P4 Android),
  each verified before the next; keep this file's verified/unverified
  split honest after every slice.

## Next step

P3 — the companion server inside the desktop app (protocol drafted
in DESIGN.md). Owner-side checkpoint, still open: first visual check
of the P2 pet on the owner's Windows PC (look, roaming feel,
transparency) — do it whenever convenient; it doesn't block P3's
headless work.
