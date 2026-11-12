# Campfire Wallpaper — project instructions

Self-contained Lively Wallpaper (web type) project. Everything the
wallpaper needs lives in this folder: no build step, no package
installs, no network calls at runtime, no shared code with other
projects.

Rules for work in this folder:

- Keep it dependency-free beyond the vendored three.js in
  `vendor/three/`. Do not add npm, a bundler, or a framework.
- `assets/*.glb` are byte-for-byte copies of Game Asset Builder
  catalog outputs. Never edit them here; regenerate or re-copy from
  the Game Asset Builder and record the new sha256 in
  `docs/MUSE_HANDOFF.md`.
- Preserve the wallpaper manners: pixel-ratio cap, hidden-page pause,
  modest particle counts, no shadow maps. Any change that raises the
  steady-state GPU/CPU cost needs a measured before/after (see
  `docs/TEST_PLAN.md`).
- The creature director must keep preferring a `walk` clip by name
  for travel, with the per-creature style fallback — future GAB
  animation work depends on that seam.
- Creature/director logic must never assume a specific GLB exists:
  a failed model load degrades to fewer creatures, never a black
  screen.
