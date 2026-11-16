# Underreach Wallpaper — test plan & verification record

## Standing rules this plan enforces

- **Roster rule (owner, 2026-11-16):** every gate-passed Game
  Asset Builder asset appears in the scene at least once. The
  page checks this itself: `#status.rosterMissing` must be `[]`.
  If the full roster ever breaks the perf budget, the finding is
  reported here with numbers — assets are never silently dropped.
- **Perf discipline (from the campfire project):** any change
  raising steady-state GPU/CPU cost needs a measured before/after
  recorded here. Real-light budget: **5** (1 hemisphere + 4 point
  lights). No shadow maps, no postprocessing chain. Everything
  else that glows is emissive + sprite + pool decal.
- **Town layout rule (owner, 2026-11-16):** the founding
  settlement is the core; named expansion zones (workshop-row,
  residential-edge, south-meadow, deep-ward) are defined in
  `js/layout.js` with surveyed, unbuilt plots. The town state is
  data (`TOWN_STATE`), shaped for a future living-world feed —
  phase 2 is discussed, not commissioned; nothing is built for
  it beyond this shape.

## Method (all on the build VM; the owner's PC is never touched)

Headless Chromium (SwiftShader) drives the page over localhost
with `?harness=1`, exactly as the campfire project's harness
does. Drivers live outside the shipped project in the build
workspace (`_build-wallpaper-verification/ur_verify.mjs`,
`ur_route_check.mjs`):

1. **Load + roster verification** (`ur_verify.mjs`): poll the
   `#status` JSON until the town is built and a creature is
   alive; assert `loadErrors` empty and `rosterMissing` empty;
   two screenshots 30 s of stepped scene-time apart prove life
   (creatures move/dwell, clips advance).
2. **Routing battery** (`ur_route_check.mjs`): via
   `window.__underreachRoute` — graph connectivity (BFS from the
   gate node reaches every node), plus a clearance battery over
   every graph-edge leg (both directions) and every spawn/exit
   mouth × every node, at margin 0.45: every planned segment
   must clear every obstacle by ≥ r + margin − 0.02, route
   length ≤ 2.2× straight-line, ≤ 16 points.
3. **Perf**: the page's live `fps` under SwiftShader (a known
   software-render artifact — the campfire project reads ~22 the
   same way; it is NOT a GPU figure) **and**
   `window.__underreachBench(40)`: 40 back-to-back renders of
   the full scene timed directly — the honest per-frame render
   cost on this host. The real-GPU figure is only measurable at
   deploy time on the owner's PC and is recorded as unmeasured
   until then.

## Results — v1, 2026-11-16

All runs below are clean single-session runs (one headless
Chromium at a time — see the process note at the end).

- **Loads / roster: PASS.** All 39 catalogue GLBs loaded;
  `loadErrors: []`; the page's own roster check reports
  `rosterMissing: []` — every roster slug is placed at least
  once (roster rule satisfied for the full v1 set). 44 of 53
  defined plots are built; the other 9 are surveyed expansion
  plots, unbuilt by design. Obstacle registry reconciles
  exactly with the layout data: 36 = 44 occupied plots − 8
  no-obstacle dressing props (verified by dumping the page's
  registry and diffing it against `js/layout.js`: 0 extra,
  0 missing).
- **Life: PASS.** Two screenshots 30 s of stepped scene-time
  apart show creatures repositioned along the network; the
  director held 4 active creatures (cap) with walk clips while
  travelling and idle/signature clips while dwelling; spawns
  enter via the gate, the south street, and the rim mouths.
- **Routing: PASS.** Full-registry battery (36 obstacles):
  112 cases (every graph-edge leg both directions + every
  spawn/exit mouth × every node), **0 failures**; graph fully
  connected (`disconnected: []`); worst segment clearance 0
  beyond the required margin (i.e. the tightest leg sits
  exactly at the design margin, never inside it); max route
  length 1.258× straight-line; max 5 points per route.
- **Perf: bounded by design; absolute GPU figure UNMEASURED.**
  SwiftShader numbers on this shared 1.5-CPU build VM proved
  contention-dominated and are recorded for honesty, not as a
  verdict: live fps 5–17 across sessions (the campfire project
  reads ~22 in the same harness), raw render bench 2.2
  ms/frame in the least-contended clean run vs 47–313
  ms/frame under dual-Chromium contention. These cannot bound
  real-GPU cost. The scene's steady-state cost is instead
  bounded by construction: 5 real lights total, no shadow
  maps, no postprocessing, ≤4 active skinned creatures,
  statics cloned from one load per slug (shared
  geometry/materials), pixel-ratio capped at 2, ~200 dust/spore
  particles. **The RTX 3060 figure must be measured at deploy
  time** (first step after the owner's go): if the full roster
  misses 60 fps there, report back with numbers before any
  roster change — per the roster rule.
- **Composition (headless screenshots):** the founding core
  reads clearly — warm town light centre-frame, fungal green
  west, crystal violet east, thermal orange south-east,
  creatures silhouetted in the pools; expansion ground lies
  dark around the core as intended. The Surface Gate at ~80
  units in fog reads as a dim presence rather than a landmark
  in the software render; acceptable for v1's mood, first
  thing to re-check on the real GPU.
- **Process note:** early verification attempts ran two
  headless Chromiums concurrently on this VM and produced
  contaminated readings (inflated counters, wild bench
  spread). All figures above are from sequential clean runs;
  the harness drivers now wait for the complete obstacle
  registry before measuring.

## Known limitations of this verification

- SwiftShader FPS understates real GPU performance by a large,
  unknown factor; treat `msPerFrame` from the bench as a
  relative cost gauge (e.g. for before/after comparisons), not
  an absolute prediction.
- Headless screenshots verify composition and placement sanity
  (no floating/sunken props at readable scale), not texture
  fidelity — the catalogue GLBs are the game's own verified
  outputs, copied byte-for-byte.
