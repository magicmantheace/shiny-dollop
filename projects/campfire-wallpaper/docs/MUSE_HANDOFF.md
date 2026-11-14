# Handoff — Campfire Companions

**State (2026-11-09): initial build + scene enrichment +
real-clock celestial cycle + south-facing rotation and density
pass, all on branch `campfire-wallpaper/initial-build`, draft
PR #49 open, NOT merged.** Deployed live on the owner's PC
2026-11-08 (Lively Wallpaper 2.2.1.0, "Campfire Companions"
active on the primary display); the enrichment + celestial
build was redeployed over both PC copies the same night, and
the south-facing + density build again on 2026-11-09 ~00:00
(see Deployment).

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

- Max 3 concurrent creatures; 5 fire spots at r 2.75 on the +z
  side of the fire, never double-booked. (World positions never
  moved; since the 2026-11-09 rotation the camera sits at −z,
  so the spots are across the fire from the viewer and dwelling
  creatures face the camera.)
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
- Wallpaper manners: pixel ratio ≤ 2, ~136 fire particles, blob
  shadows (no shadow maps), render loop fully stopped while the
  page is hidden.

## Scene dressing (2026-11-08 enrichment, 2026-11-09 density pass)

Dressing only — the director, GLBs, and fire-spot semantics are
untouched, and the fire clearing stays readable. Everything is
primitives/instancing; per-frame updates run through a
`dressingUpdaters` hook list called from the main tick.

- **Forest edge:** one foliage geometry + one trunk geometry
  as two InstancedMeshes sharing matrices — 245 pines after
  the density pass (160 at r 54–81, scale 0.95–2.1; 30 in a
  r 44–58 blending band; 55 taller back-ring pines at
  r 66–84, scale 1.5–2.7), per-instance colour tint. The
  foliage is `makePineFoliageGeo()` (tree-fix pass,
  2026-11-09): five flat stepped tiers with per-tier rotation
  and a baked vertex-colour shade gradient, flat-shaded — the
  same geometry serves the 15 scattered ring pines and the
  feature pine. Feature trees: broad oak at (−10.5, −5.5),
  tall pine at (11, −7.5), dead snag at (−16, 8).
- **Ground life:** 1,250 instanced grass tufts (r 3–52, sparse
  inside r 7, none within 0.8 of the path); 115 instanced
  ferns (biased to the clearing edge); 10 extra bushes, 7
  carrying 63 instanced berries; 46 moss discs and 30 extra
  rocks (some moss-tinted) outside the keep-clear guide; 2
  fallen logs.
- **Whimsy:** 9 glowing-mushroom clusters (~40 instanced stems +
  emissive caps, one additive glow sprite per cluster, pulsing);
  64 fireflies (one Points system, sine wander + twinkle).
- **Fire furniture:** 2 log benches (angles ±1.75, r 3.5), 3
  stump seats (r 3.2), a 6-log woodpile at (4.7, 2.1), chopping
  block + split log at (3.9, 3.3); the fire pit itself is
  ringed by a 16-stone InstancedMesh (r 0.92–1.06, per-stone
  scale/tilt/shade).
- **Foreground framing:** the density pass's 4 large pines at
  the frame edges were **removed 2026-11-09 at the owner's
  request** — the view across the clearing is open; the
  forest edge and ridges carry the frame.
- **Dirt path:** terrain-following ribbon along a quadratic
  Bézier from (17, 36) to (2.3, 4.6); its 61 samples double as
  the keep-clear guide (`distToPath`) for grass/fern scatter.
- **Horizon:** 6 hill domes (MeshBasicMaterial, unfogged) whose
  colour follows the sky palette via `skyFollowers` (below);
  one shooting-star sprite on a ~9–25 s cycle.
- **Mountain vista (density pass):** three layered low-poly
  ridge ribbons (`buildRidge`, full ring so no azimuth reads
  empty; the composition reads to the south) at R 118 (peaks
  ~24, dark green), R 142 (peaks ~34, blue) and R 168 (peaks
  ~45, snow above a jagged 0.78 snowline, snow vertex colour
  0xeef2fa). Vertex-colour gradients tint from the same sky
  palette via `skyFollowers` (fog:false, so they read as
  distance, not fog) — alpenglow at sunset, blue at noon,
  near-black silhouettes at night. Aligned notches at
  |θ| = 65° keep the rise/set arcs unobstructed.

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
  **Moon gate (2026-11-09):** disc opacity/visibility also scale
  with `clamp((6 − sunEl)/10) × clamp(frac × 2.5)` — without it,
  the near-new moon drew as a solid black disc in the day sky
  (a latent bug the south rotation exposed). Deliberate v1
  trade-off: no pale daytime moon.
- **Directional light** (`skyLight`): contribution-weighted blend
  of sun and moon — warm low sun (twilight-aware ramp so dawn/dusk
  aren't black), white midday, cool dim moonlight, 0.12 floor.
  Hemisphere + fire balance via `nightFactor`/`fireScale`: the
  fire burns around the clock but its light/flame presence scales
  to ~0.35 in full day; fireflies and mushroom glow are
  night-gated by `nightFactor`; stars fade in as the sun drops.
- **Framing (2026-11-09, supersedes the old north-facing
  caveat):** the camera sits at (0, 3.1, −10.8) looking south
  (`CAM_LOOK` (0, 3.0, 0); frame ≈ az 137–223°, el −28°…+27°),
  so the discs cross the frame: sun disc captured in frame at
  the 2026-11-08 noon culmination (el 23.7°, az 179.9°), moon
  disc captured in frame on the summer-transit geometry
  (2026-07-24 22:40, el 12.6°, az 187.8°). Winter full moons
  and dates like 2026-11-20 (transit el 49.2°) pass above the
  frame — moonlight only, by geometry. Azimuth was already
  honoured in world space (`azElToVec`: N = −z, S = +z), so
  the rotation needed no sky-math change and the event-time
  accuracy table in `docs/TEST_PLAN.md` stands.
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
clock (night state at redeploy time). The south-facing +
density redeploy (2026-11-09 ~00:00) repeated the route for
`js/wallpaper.js` (sha256 `dc180cb5ba044eacf1081cf481d6bf46da8635493085c75c11ba31a35f86bc0a`) and `preview.jpg` (sha256 `107aa39e8d82fb6a592f9524ab150d364d7e1cb228fff8d0b453cb8af06f43ab`): staged through the bridge file API, copied by a staged
`.cmd` (inline quoted paths get mangled by the bridge's cmd
wrapping — scripts on disk are the reliable route; destination
hashes for the spaced Library paths were verified by copying
the files back into the sandbox and hashing there), Lively
killed and relaunched, tile re-invoked via UIA, UI process
closed afterwards leaving core + watchdog + player. Final
live screenshot (00:05, moonless night) shows the south-facing
framing with ridge silhouettes on the real 3840×2160 desktop.
The tree-fix redeploy (2026-11-09 ~05:58) repeated the route
for `js/wallpaper.js` (sha256 `e1a18b87b985acabafbada93dbc97cd1bd8ebd28b8498d3919f9a8d74aba227b`) and `preview.jpg` (sha256 `46a646d0d07c9b14a51a18e63e5dfccfa90b447087cb944ede653d4901ad6584`):
staged through the bridge file API, copied by a staged
`.cmd` to both copies, destination hashes verified from
certutil output read back over the bridge, Lively killed
and relaunched, the Campfire Companions tile re-invoked via
UIA, and the UI process (Lively.UI.WinUI.exe) closed
afterwards leaving core + watchdog + player. The final live
screenshot (06:00, moonless night) shows the open frame and
the tiered treeline on the real desktop — see
docs/TEST_PLAN.md, "tree fix pass".
The definition pass (2026-11-09, owner-directed: "increase
the definition of everything") raised fidelity across the
board — ground mesh at 170×170 segments, higher segment
counts on every primitive family, rocks and bushes one
subdivision richer, ridge steps 88 → 160, moon texture
512², pixel-ratio cap raised to 2, and anisotropic
filtering (≤ 8) applied to the GLB textures at load.
Measured on frozen-noon probe copies: 217,024 → 311,626
triangles at an unchanged 119 draw calls, SwiftShader fps
22 → 22. Its redeploy (2026-11-09 ~11:51) repeated the
route for `js/wallpaper.js` (sha256
`54ae175c934cd67a7c8fc4ac326cb7c6ea362972d0b16431af6e29bef66b06b1`)
and `preview.jpg` (sha256
`3367c20a890a3b6b32c0f9d4ddf3704d530c38535cc3c9449c057057381de865`):
destination hashes verified at all four files, Lively
relaunched, tile re-invoked, UI closed after. The final
live screenshot (10:59 PC clock, morning sun) shows a
triceratops and the ember dragon at the fire — see
docs/TEST_PLAN.md, "definition pass".

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
- South-facing rotation + density pass (2026-11-09, same
  harness): seven frozen captures, all zero console errors —
  **sun disc in frame** at the Nov 8 noon culmination and
  **moon disc in frame** on the 2026-07-24 summer transit;
  sunset capture echoes the density reference (fire foreground,
  forest frame, alpenglow on the snow range); the Nov 20 case
  probed as moonlight-only by transit geometry (el 49.2°,
  above the frame). The pass also caught and fixed a latent
  bug: the near-new moon rendering as a black disc in the day
  sky (now gated). Standard 420-step verify at the live clock
  re-run: **PASS** (walk-in on `"walk"`, dwell observed,
  `loadErrors: []`). Full record in TEST_PLAN.

Screenshots live outside the repo in the build worktree:
`~/workspace/_build-wallpaper-verification/` — `shot-a.png` /
`shot-b.png` (initial proof-of-life pair), `sky-noon.png`,
`sky-sunrise.png`, `sky-sunset.png`, `sky-night.png`,
`sky-moonlit.png`, `moon-phase-grid.png` (enrichment/celestial
pass), and `final2-noon.png`, `final2-sunrise.png`,
`final2-sunset.png`, `final2-descent.png`, `final2-night.png`,
`final2-moondisc.png`, `final-moonlit.png` (south-facing +
density pass). `preview.jpg` in the project is the south-facing
sunset capture, used as the Lively thumbnail.

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

## Builder environment pack (2026-11-10)

The foreground/mid-field dressing is now the Game Asset Builder's
environment pack (pine-tree, boulder, bush, fern, mushroom-cluster,
fallen-log, stump — catalogued GLBs, byte-for-byte copies in
`assets/`). Mechanism: the procedural dressing blocks register their
placements in `BUILDER_SWAPS` (record-only — the seeded layout RNG
stream is untouched); `placeBuilderPack()` loads each GLB once and
swaps clones in at the recorded spots, matching each procedural
object's world height (length for the logs). Ferns swap every 4th
instanced spot (~29 larger clones; the instanced mesh is emptied);
mushroom clusters keep their glow sprites and gain a low teal
emissive so the builder caps still read at night; rocks beyond
30 units stay procedural (the round boulder reads as a dark ball
against the fog wall at range — noon capture, 2026-11-10). The
harness status now reports `builderDone`, and the sky-capture
driver waits for it, which also fixes the static-load race that
used to cost the treasure chest its screenshot. Verified: gated
captures at noon, golden hour, and night with zero console errors,
plus a scene-graph audit of all 107 pack placements. Cost: ~99
extra draw calls and ~455k static vertices; the SwiftShader
harness fps was unchanged (22), but real-GPU frame cost remains
unmeasured, as before.

## Next steps (not done here)

1. Possible v2: Lively properties (creature toggles, fire size).
   The commissioned weird roster joined the scene 2026-11-10 (see
   the pack section above): all six P5 creatures are in `CREATURES`
   with catalog-byte-identical GLBs in `assets/`. Any future
   creature is the same drop-in: new GLB + one config row; re-sync
   BOTH PC copies and re-apply in Lively afterwards.
2. PR #49 stays draft until the owner says merge.


## Ember Owl-Cat joins the roster (2026-11-10)

The last commissioned creature is in. The builder fixed its
Hunyuan paint stall (a CUDA caching-allocator pathology, cured by
`expandable_segments` — builder `docs/PAINT_STALL.md`), and the
Ember Owl-Cat finished segment → rig → animate → catalog
(catalog-verify MATCH). Roster row: height 1.0, speed 0.9,
`bounce` travel, signature `headturn`, bobAmp 0.06. GLB in
`assets/` is the byte-for-byte catalog copy, sha256
`f5a642353fa8cc892ed4a1f95c2b44805ed922ae0e496f31be738d831eea5500`
(20,053,292 bytes — the largest template; on-stage count is still
capped by MAX_ACTIVE = 3). Gated golden-hour harness capture:
all eleven templates loaded with zero errors, Owl-Cat entering
on `walk`. **The roster is complete: 11 creatures** (the original
three + all eight P5 smashups). Deployed live the same day —
both PC copies re-synced and hash-verified, Lively re-applied.


## Owl-Cat headturn rework synced (2026-11-10)

The builder reworked the Owl-Cat's signature at the owner's
direction (the original read as a tilt): `headturn` is now a
±1.05 rad turn with holds. The catalog GLB changed (animation
data only — same mesh, texture, rig, byte size); current
`assets/ember-owl-cat.glb` sha256 is
`2bd78ce04579dbc605c7bcaf198ffa57c399165cec166ba6702f22c9e5844b3a`,
superseding `f5a642353fa8…` recorded above. Re-deployed live the
same day (both PC copies hash-verified, Lively re-applied).


## Owl-Cat headturn correction synced (2026-11-10)

The owner rejected the plateau version as still a tilt, and
measurement proved him right (bone-local yaw dipped the beak
~0.25–0.30). The builder now drives the turn about the world
vertical (builder HANDOFF has the details); the catalog GLB
changed again — current `assets/ember-owl-cat.glb` sha256 is
`98bc4f3f5c25f9ecb941a0d63ab387e14139fa808f2d16f4fcf779d2dad7102f`,
superseding `2bd78ce04579…`. Measured on the baked clip: yaw
−55°/+57.7° at the holds, beak height level (±0.005).
Re-deployed live the same day (both PC copies hash-verified,
Lively re-applied).


## Arm-separation rebuilds deployed — crow, toasty, axolotl (2026-11-12)

The owner's arm-separation hard requirement (arms/limbs must not be
fused to the body along their length) failed 6 of the 11 roster
creatures in the 2026-11-10 audit. Three rebuilds have now passed
both builder gates (concept preflight + posed-render) and are
catalogued on builder branch `game-asset-builder/arm-separation-fixes`;
their GLBs were copied byte-for-byte into `assets/`, superseding the
audited originals:

| File | Bytes | sha256 | Change vs old |
| --- | --- | --- | --- |
| crow-postman.glb | 19,319,632 | `c2e23612d2b2507c0a6458c6558e7f30145369129562c4c1133772b23a69f68a` | was 21,106,560 bytes; 299,290 → 269,509 verts; clips bow/idle/run/walk unchanged |
| toasty.glb | 22,066,560 | `3818679c9ffcaee8c6298247b3e423fb5e10722c79f9033b60343c812a486d48` | was 21,960,832 bytes; 298,831 → 297,350 verts; clips bounce/idle/run/walk unchanged |
| axolotl-capybara.glb | 19,814,040 | `a925ab9292794da7dc4b22d1a369581a3373c975dbec0bf631ef6b831ef3d214` | was 19,525,868 bytes; 256,278 → 267,894 verts; clips idle/run/walk/wiggle unchanged |

Disclosed gate weaknesses carried with the rebuilds (builder record):
the crow's coat side panel sails at a 2.2 rad stress raise (onset
~1.7 rad; no shipped crow clip exceeds ~0.6 rad arm raise) and
Toasty peels a body-surface flap at the same out-of-range stress;
the axolotl gate was clean. Snow-goblin, mandrake-toddler and
ember-owl-cat remain the ORIGINAL builds in `assets/` — no gated
replacement exists for them yet (the goblin rebuild's good textured
mesh is held at the posed gate by its wave-clip fur blade; see the
builder HANDOFF). Deployed live 2026-11-12: both PC copies
re-synced and hash-verified, Lively re-applied.


## Arm-separation rebuild deployed — snow-goblin (2026-11-12)

The goblin's wave-clip fur blade is fixed — not by a re-bake but by
a new rig policy in the builder (the cross-zone bone ban,
`--zone-ban trunk:arm.L/trunk:arm.R`; see the builder HANDOFF).
The rebuild's existing textured mesh was re-rigged with arm bones
banned from owning torso-labelled flesh: bone heat accepted with
torso arm share 0.0385 (gate 0.25; the deployed original's rebuild
attempts sat at 0.32–0.54), and the posed gate passed — at the
wave apex the raised arm no longer drags a continuous sheet from
armpit to hip. The gated GLB was copied byte-for-byte into
`assets/`, superseding the audited original:

| File | Bytes | sha256 | Change vs old |
| --- | --- | --- | --- |
| snow-goblin.glb | 21,058,412 | `6cfaaa6e706c764d1beeea67c226fa1c5eb06711a1f91c606d234a1a844af301` | was 22,227,900 bytes (`c4ba135b…`); 50,883 → 45,825 verts; clips idle/run/walk/wave unchanged |

Disclosed gate weakness carried with the rebuild (builder record):
the arm's own underside fur fringe — flat fur-card geometry in the
mesh — hangs as a soft flap under the raised arm during the wave
(it moves with the arm; the torso contributes nothing) and spikes
into thin slivers only at a beyond-spec 2.2 rad stress raise no
shipped clip approaches (wave apex ≈0.95 rad). Mandrake-toddler
and ember-owl-cat remain the ORIGINAL builds — the last two
arm-gate violators; both need redesign work, owner's call.
Deployed live 2026-11-12: both PC copies re-synced and
hash-verified, Lively re-applied.

## Obstacle-aware creature routing (2026-11-13)

Creatures now route around the campfire and every solid prop
instead of walking straight lines through them. Placement sites
register obstacle circles — capsules for benches and fallen
logs — into `OBSTACLES` (129 entries) using only values already
computed there, so the seeded layout is byte-identical;
`Creature.setTarget()` plans a per-trip route with `planRoute()`
(start step-out + grid A* + `segBlocker()`-validated
string-pulling; margin 0.30 + height × 0.15), and `update()`
consumes the waypoints. Arrival/dwell/heading/bob behaviour and
the `walk`-clip preference are unchanged; failed GLB loads still
degrade to fewer creatures. Geometry battery: 540/540 trips
clear at the test margin (full record in docs/TEST_PLAN.md).
Headless fps unchanged (22 → 22 at both noon and sunset;
indicative only, real-GPU still unmeasured). **Not deployed:**
built and verified VM-only; the PC copies still run the previous
build until the owner says to sync them.
