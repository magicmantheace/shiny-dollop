# Handoff — Campfire Companions

**State (2026-11-08): initial build + scene enrichment + real-clock
celestial cycle, all on branch `campfire-wallpaper/initial-build`,
draft PR #49 open, NOT merged.** Deployed live on the owner's PC
2026-11-08 (Lively Wallpaper 2.2.1.0, "Campfire Companions" active
on the primary display); the enrichment + celestial build was
redeployed over both PC copies the same night (see Deployment).

## What it is

A Lively Wallpaper (web type) live desktop background: a dressed
field where Game Asset Builder creatures wander in, gather around
a campfire, and wander off, under a sky that follows the real
sun/moon cycle for Lethbridge, Alberta. Entry point `index.html`;
scene and creature director in `js/wallpaper.js`; no build step,
no runtime network access, three.js r180 vendored in
`vendor/three/` (`three.module.js` + `three.core.js` — r180
splits its build — plus the `GLTFLoader`, `BufferGeometryUtils`
and `SkeletonUtils` addons).

## Assets (copied verbatim from the Game Asset Builder catalog)

| File | Bytes | sha256 | Clips |
| --- | --- | --- | --- |
| ember-dragon.glb | 20,671,744 | `2837c6b2969f0bf628314b19c8230c92fb3bc8480b045f8462bd1f1540ef6bb2` | hop, idle, run, walk |
| snow-goblin.glb | 22,227,900 | `c4ba135bcb26a85dde5012b367dd7c5417c99ba8a3ee60dbc1fe51a985721670` | idle, run, walk, wave |
| triceratops.glb | 20,330,868 | `39b5f934eb2e1943a11208c43141fcb99ab49606812d1003bfba4d9b8eb3acc6` | bounce, idle, run, walk |
| treasure-chest.glb | 11,249,652 | `2b6e51cc0d8273e318e6e2dad64d8b03cc0c3da029fe132463055f1b060125b1` | — (static) |

Assets total 74,480,164 bytes; whole project ≈ 76.7 MB.

**History worth knowing:** the build started with the pre-P4 GLBs
(idle + signature only). Mid-build, the Game Asset Builder's P4
animation slice landed (branch `game-asset-builder/p4-game-animations`,
tip `57fab45`) and regenerated the catalog with walk + run clips;
the three creature GLBs were re-copied from the regenerated outputs
and the hashes above are the post-P4 ones. The chest is unchanged.

## Director behaviour (as built)

- Max 3 concurrent creatures; 5 fire spots on the camera side of
  the fire, never double-booked.
- Travel clip: `walk` when the GLB provides one (all three do);
  fallback per-creature gait from the signature clip (dragon hop /
  trike bounce surge-and-lift synced to the clip cycle; goblin
  glides on idle).
- Dwell 16–42 s on idle; signature clip (hop/wave/bounce) plays
  once every 7–16 s; then the creature walks to a random edge and
  despawns. Respawn cadence 6–14 s (2.5 s if the field is empty).
- The scene opens mid-moment: one creature already dwelling, one
  walking in from mid-field.
- Models are auto-normalized at load (bounding-box height →
  per-creature target height, feet at y=0), so future GAB exports
  at other scales drop in safely.
- Wallpaper manners: pixel ratio ≤ 1.5, ~136 fire particles, blob
  shadows (no shadow maps), render loop fully stopped while the
  page is hidden.

## Scene dressing (2026-11-08 enrichment)

Dressing only — the director, GLBs, and fire-spot semantics are
untouched, and the fire clearing stays readable. Everything is
primitives/instancing; per-frame updates run through a
`dressingUpdaters` hook list called from the main tick.

- **Forest edge:** one merged-cone foliage geometry + one trunk
  geometry as two InstancedMeshes sharing matrices — 190 pines
  (160 at r 54–81, scale 0.95–2.1; 30 in a r 44–58 blending band),
  per-instance colour tint. Feature trees: broad oak at
  (−10.5, −5.5), tall 4-cone pine at (11, −7.5), dead snag at
  (−16, 8).
- **Ground life:** 950 instanced grass tufts (r 3–52, sparse
  inside r 7, none within 0.8 of the path); 70 instanced ferns;
  10 extra bushes, 7 carrying 63 instanced berries.
- **Whimsy:** 9 glowing-mushroom clusters (~40 instanced stems +
  emissive caps, one additive glow sprite per cluster, pulsing);
  64 fireflies (one Points system, sine wander + twinkle).
- **Fire furniture:** 2 log benches (angles ±1.75, r 3.5), 3
  stump seats (r 3.2), a 6-log woodpile at (4.7, 2.1), chopping
  block + split log at (3.9, 3.3).
- **Dirt path:** terrain-following ribbon along a quadratic
  Bézier from (17, 36) to (2.3, 4.6); its 61 samples double as
  the keep-clear guide (`distToPath`) for grass/fern scatter.
- **Horizon:** 6 hill domes (MeshBasicMaterial, unfogged) whose
  colour follows the sky palette via `skyFollowers` (below);
  one shooting-star sprite on a ~9–25 s cycle.

## Celestial cycle (2026-11-08)

Real sun/moon for **Lethbridge: `HOME = { lat: 49.6942,
lon: -112.8456 }`** (hardcoded constant in `js/wallpaper.js`),
time from the system `Date` (WebView2 supplies the real clock +
America/Edmonton; Alberta Time is UTC−6 year-round). No network.

- **Math:** SunCalc-style `sunCoords`/`moonCoords`/`bodyPosition`
  (sidereal time, hour angle; compass azimuth = atan2 + π) and
  `moonIllumination` (fraction, phase 0=new/0.5=full, bright-limb
  angle). Events are never special-cased — everything is driven
  by elevation/azimuth each frame in `updateSky(nowMs)`.
- **Palette:** `SKY_STOPS` keyed by sun elevation (−18/−8/0/6/18/
  40°), smoothstep-lerped (sky gradient, fog colour+density,
  hemisphere colours+intensity). **The 0° stop is the original
  shipped dusk palette** (incl. its original hemisphere colours)
  — it is now the sunrise/sunset state.
- **Bodies:** sun disc + halo at r 192, disc colour warming at
  low elevation; moon disc with a canvas-generated phase texture
  (`drawMoonPhase`, redrawn at most hourly) rotated so the bright
  limb faces the sun (bright-limb angle − parallactic angle),
  brightness scaled by elevation × (0.3 + 0.7·illumination).
- **Directional light** (`skyLight`): contribution-weighted blend
  of sun and moon — warm low sun (twilight-aware ramp so dawn/dusk
  aren't black), white midday, cool dim moonlight, 0.12 floor.
  Hemisphere + fire balance via `nightFactor`/`fireScale`: the
  fire burns around the clock but its light/flame presence scales
  to ~0.35 in full day; fireflies and mushroom glow are
  night-gated by `nightFactor`; stars fade in as the sun drops.
- **Framing caveat:** the camera faces north (−z); at 49.7° N the
  bodies transit the *southern* sky, so in-frame disc appearances
  are limited to rise/set seasons — the visible product is the
  light and colour cycle. Verified states + accuracy table
  (sun events ≤ ~1.5 min vs timeanddate.com; moon events ≤
  ~10 min) are in `docs/TEST_PLAN.md`.
- **Harness seam:** `?harness=1&time=<epoch ms | ISO>` freezes
  the celestial computation; `#status`/`window.__campfireStatus`
  now include a `sky` object (sun/moon el+az, moon fraction).

## Deployment

Lively Wallpaper 2.2.1.0 (per-user install) on the owner's PC;
the wallpaper lives in **two** copies that must stay in sync:
`D:\wallpapers\campfire-wallpaper` and the Lively Library copy
at `C:\Users\adamw\AppData\Local\Lively Wallpaper\Library\
wallpapers\campfire-wallpaper`. Lively 2.2.1.0's CLI is broken
(livelycu crashes, `setwp` silently ignored) — apply by dropping
the folder into the Library, restarting Lively, and invoking the
library tile (UIA). The enrichment + celestial redeploy synced
the changed files to both copies (hash-verified) and restarted
Lively; the live desktop was screenshot-verified on the real
clock (night state at redeploy time).

## Verification (see docs/TEST_PLAN.md for the full record)

Headless Chromium (Chrome-for-Testing headless shell 157,
SwiftShader) on the build VM, CDP-driven, serving the shipped
folder over HTTP:

- All templates load, no console errors, scene renders with fire,
  glow, chest, and creatures at their spots.
- The entering creature's status reports clip `"walk"` — the P4
  walk preference engages with the shipped GLBs.
- Proof of life via the page's `?harness=1` step seam
  (`window.__campfireStep(steps, dt)` — deterministic fixed-step
  simulation, harness-only; Lively never passes the flag): a goblin
  photographed at the field's edge is photographed at its fire
  spot 420 steps (14 scene-seconds) later, beside the dwelling
  triceratops.
- Not directly observed in the VM runs: leave/despawn and a
  signature clip firing (observation windows were short; recorded
  honestly in TEST_PLAN). Real-GPU frame rate is unverified —
  SwiftShader numbers on the shared VM are a floor distorted by
  the dt cap, not a measurement of the owner's RTX 3060.
- Enrichment + celestial pass (2026-11-08, same harness plus the
  frozen-time seam): five state captures (noon / sunrise /
  sunset / moonless night / moonlit night) all with zero console
  errors; the page's reported sun/moon values matched a
  standalone copy of the math exactly; event-time accuracy vs
  timeanddate.com and the moon-phase texture grid are recorded
  in TEST_PLAN. The standard 420-step verify was re-run after
  the changes as a regression check.

Screenshots live outside the repo in the build worktree:
`~/workspace/_build-wallpaper-verification/` — `shot-a.png` /
`shot-b.png` (initial proof-of-life pair), `sky-noon.png`,
`sky-sunrise.png`, `sky-sunset.png`, `sky-night.png`,
`sky-moonlit.png`, `moon-phase-grid.png` (enrichment/celestial
pass). `preview.jpg` in the project is the sunset capture,
used as the Lively thumbnail.

## Harness notes for the next verifier

- This VM's bundled Chromium (`/opt/meta-chromium/chrome`) is the
  Muse browser and refuses scripted launch ("Hatch WebGL domain
  policy is required") — use a Chrome-for-Testing headless shell.
- Node on this VM honours the egress proxy env
  (`NODE_USE_ENV_PROXY=1`); the CDP driver must clear proxy vars
  or loopback DevTools calls vanish into the proxy.
- Headless Chromium composites frames only on demand; expect
  ~0.5–3 s per software frame of this scene on a busy VM. Use the
  `?harness=1` step seam for behaviour checks and treat fps
  readings as artifacts.
- The reference drivers used for this build are in
  `~/workspace/_build-wallpaper-verification/` (`run_verify.mjs`,
  `run_sky.mjs`). Both now use a **fresh `--user-data-dir` per
  run**: a killed run leaves its Chrome profile locked, and a
  later Chrome exits instantly on the stale singleton lock while
  the driver polls a dead socket until its deadline. Wrap runs
  in a `timeout` watchdog for the same reason.
- Capture instants for Lethbridge must use the **UTC−6** offset
  (Alberta Time is permanent UTC−6). An earlier capture round
  used −07:00 and silently photographed instants one hour later
  than labelled; the page math itself was never wrong (its
  reported values matched the standalone math at both offsets).

## Next steps (not done here)

1. Possible v2: Lively properties (creature toggles, fire size),
   the commissioned weird-roster creatures as the GAB makes them
   (drop-in: new GLB + one config row in `CREATURES`; re-sync
   BOTH PC copies and re-apply in Lively afterwards).
2. PR #49 stays draft until the owner says merge.
