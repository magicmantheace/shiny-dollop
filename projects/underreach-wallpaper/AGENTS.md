# Underreach Wallpaper — project instructions

Self-contained Lively Wallpaper (web type) project: an Underreach
delving-colony town in a cavern. Everything the wallpaper needs
lives in this folder: no build step, no package installs, no
network calls at runtime, no shared code with other projects.

Rules for work in this folder:

- Keep it dependency-free beyond the vendored three.js in
  `vendor/three/`. Do not add npm, a bundler, or a framework.
- `assets/*.glb` are byte-for-byte copies of Game Asset Builder
  catalog outputs. Never edit them here; regenerate or re-copy
  from the Game Asset Builder and record the new sha256 in
  `docs/MUSE_HANDOFF.md`.
- **Roster rule (owner, 2026-11-16):** every gate-passed Game
  Asset Builder asset appears in the scene at least once. Adding
  an asset = a row in `js/roster.js` + a plot row in
  `js/layout.js` + the GLB in `assets/`. Parked/untextured
  assets (queue #29, #31) stay out until they complete and pass
  their gates. Never silently drop an asset for performance —
  report with measured numbers instead (see `docs/TEST_PLAN.md`).
- **Layout rule:** placements live in `js/layout.js` as named
  plots in named zones (the town state). Do not scatter
  hard-coded coordinates through scene code. The town-state
  shape is the contract a future living-world feed (phase 2,
  not commissioned) would drive — keep it stable.
- Preserve the wallpaper manners: pixel-ratio cap, hidden-page
  pause, modest particle counts, **no shadow maps, no post
  chain, real-light budget of 5** (1 hemisphere + 4 points;
  everything else is emissive + glow sprite + light-pool decal).
  Any change that raises the steady-state GPU/CPU cost needs a
  measured before/after (see `docs/TEST_PLAN.md`).
- Creatures travel the lantern network graph (`NETWORK` in
  `js/layout.js`) node to node, each leg obstacle-routed by the
  grid A* + string-pull planner in `js/wallpaper.js`. Keep the
  planner's clearance semantics intact; the routing battery in
  `docs/TEST_PLAN.md` is the regression check.
- Scene logic must never assume a specific GLB exists: a failed
  model load degrades to an empty plot / fewer creatures, never
  a black screen. The `#status` JSON + `?harness=1` seams are
  the verification contract — keep them working.
