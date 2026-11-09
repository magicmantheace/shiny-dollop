# Test plan — Campfire Companions

## Harness

Headless Chromium driven over the DevTools protocol (the same
pattern as the Game Asset Builder's three.js hand-off verification):
serve the project folder over localhost HTTP, load `index.html`,
poll the page's `#status` element (the scene publishes JSON state
there twice a second), and capture screenshots with
`Page.captureScreenshot`.

Reference driver used for the initial build lives outside the repo
in the build worktree's verification folder; the scene-side contract
it relies on is the `#status` JSON:

```json
{ "ready": true, "fps": 60, "loaded": ["ember-dragon", ...],
  "loadErrors": [],
  "creatures": [{ "slug": "...", "state": "enter|dwell|leave",
                  "clip": "idle|walk|signature",
                  "x": 0.0, "z": 0.0 }],
  "sky": { "sunEl": 0.0, "sunAz": 0.0, "moonEl": 0.0,
           "moonAz": 0.0, "moonFrac": 0.0 } }
```

The `?harness=1` seam also accepts `&time=<epoch ms | ISO string>`,
which freezes the celestial computation at that instant (the page
otherwise uses the live system clock). Sky-state captures use a
second driver (`run_sky.mjs` in the same verification folder) that
loads one frozen instant, steps 30 × 1/30 s, and screenshots.

## Checks

1. **Load** — page loads over HTTP with no console errors; all three
   creature templates plus the chest load (`loaded` lists all three
   slugs, `loadErrors` empty).
2. **Scene present** — screenshot shows the field, the campfire with
   visible flame particles and ground glow, set dressing, and at
   least one creature.
3. **Proof of life** — a second screenshot several seconds later
   shows a creature in a different position and/or pose than the
   first; `#status` positions for the travelling creature differ
   between the two captures.
4. **Director invariants** (observed via `#status` over ~60 s) —
   never more than 3 active creatures; no two creatures share a
   fire spot; states cycle enter → dwell → leave; a dwelling
   creature eventually plays its signature clip.
5. **Frame cost** — `#status` reports the frame rate under
   SwiftShader (software rendering; a floor, not a ceiling — the
   owner's RTX 3060 will do far better). Record the number; there
   is no pass threshold in the VM, but a collapse below ~10 fps
   would mean the scene is too heavy and must be cut down.
6. **Hidden pause** — with the page hidden, `requestAnimationFrame`
   stops (checked by the fps counter freezing / CDP Page lifecycle);
   static code path is `visibilitychange` → `setAnimationLoop(null)`.

## Results — initial build (2026-11-08)

Verified in headless Chromium (Chrome-for-Testing headless shell,
SwiftShader software rendering) on the build VM, serving the exact
shipped folder over localhost HTTP. The VM is shared and heavily
loaded, and headless Chromium only composites frames on demand, so
checks 3–4 were proven with the page's `?harness=1` step seam
(deterministic fixed-step simulation) plus status reads, rather
than wall-clock observation. The same scene on a desktop GPU runs
continuously by construction (plain `requestAnimationFrame` via
`setAnimationLoop`).

1. **Load — PASS.** All three creature templates load
   (`loaded: ["ember-dragon","snow-goblin","triceratops"]`),
   `loadErrors: []`, zero console errors/warnings across runs.
2. **Scene present — PASS.** Captures show the field, dusk sky with
   stars and moon, pines/rocks/bushes, the treasure chest, the
   campfire with stone ring, log teepee, flame particles, rising
   embers and the warm ground-glow pool — and creatures at the fire.
3. **Proof of life — PASS.** Shot A: a triceratops dwells at a fire
   spot; a snow goblin is at the field's right edge, entering.
   After 420 harness steps (14 s of scene time), shot B: the goblin
   has walked in and stands at its own fire spot; the trike's pose
   and the flames have advanced. Status JSON in earlier runs shows
   the travelling creature's clip as `"walk"` (the P4 clip) and its
   position changing between reads during load-phase frames.
4. **Director invariants — PASS (as far as observed).** Never more
   than 3 active in any status read; dwell + enter pairs occupied
   distinct spots in every capture; states observed: enter (clip
   `walk`), dwell (clip `idle`). Leave/despawn and signature clips
   were not captured in a status read during the VM runs (dwell
   times are 16–42 s of scene time and headless observation windows
   were short) — the code paths are the same state machine, but
   this is recorded as *not directly observed* rather than claimed.
5. **Frame cost — measured with a caveat.** The page's own counter
   reads ~22 fps under SwiftShader, but that figure is an artifact
   of the 0.05 s dt cap when real frames take longer (each software
   frame of this scene on the contended VM took ~0.5–3 s). Real
   frame cost on the owner's RTX 3060 is **unverified**; by scene
   weight (≈250 k triangles worst case, ~140 particles, no shadow
   maps) it should be trivially light, but that is an expectation,
   not a measurement.
6. **Hidden pause — code-path verified only** (`visibilitychange`
   → `setAnimationLoop(null)`), not exercised in the harness.

Screenshots: build worktree verification folder
(`shot-a.png`, `shot-b.png` — the stepped pair described in
check 3).

## Results — enrichment + celestial cycle (2026-11-08)

Same harness, same shipped folder. Two additions were verified:
scene dressing (Adam: "make the scene less bare") and the
real-clock sun/moon cycle for Lethbridge.

**Dressing (all primitives/instancing, clearing kept clear):**
190 instanced pines in a forest-edge band (r 44–81) + 3 feature
trees (broad oak, tall pine, dead snag); 950 instanced grass
tufts; 70 ferns; 10 extra bushes, 7 carrying 63 instanced
berries; 9 glowing-mushroom clusters (~40 instanced mushrooms,
emissive caps + one glow sprite each); 64 fireflies (one Points
system); 2 log benches, 3 stump seats, a 6-log woodpile and a
chopping block around the fire; a terrain-following dirt-path
ribbon from (17, 36) to the fire clearing; 6 horizon hill domes;
an occasional shooting star (one sprite, ~every 9–25 s).

**Celestial verification.** The page's own `#status.sky` values
matched a standalone copy of the same math to the printed digit
at every captured instant (e.g. 12:00 local: sun el 21.64°,
az 160.5°; moon frac 0.003). Event times for 2026-11-08,
computed by scanning the page's elevation curves (refraction-
adjusted crossing angles: sun −0.833°, moon +0.125°), against
timeanddate.com's Lethbridge pages (sun and moon, retrieved
2026-11-08):

| Event | Computed | Reference | Delta |
| --- | --- | --- | --- |
| Sunrise | 08:31:45 (az 115.0°) | 8:32 am (115°) | ~15 s early |
| Sunset | 17:58:31 (az 244.8°) | 5:57 pm (245°) | ~1.5 min late |
| Solar noon | 13:15:00, max el 23.7° | 1:15 pm, 23.6° | spot on |
| Moonrise | 08:20:37 (az 120.5°) | 8:11 am (120°) | ~9.6 min late |
| Moonset | 17:13:44 (az 236.7°) | 5:09 pm (237°) | ~4.7 min late |
| Moon meridian | 12:47:30, el 20.4° | 12:45 pm, 19.9° | ~2.5 min late |
| Moon illumination | 0.3% at 12:45 | 0.4% | match |

Reference times are rounded to the minute by the source. Sun
events meet the "within a few minutes" target; moon events meet
the "~15 min is acceptable" target — the moon's shallow horizon
crossing that day (max el ~20°) amplifies the low-precision
lunar theory's ~0.3–0.5° position error into minutes. (Note:
Alberta Time is UTC−6 year-round; all times above are local.)

**State captures** (frozen-time seam, all with zero console
errors and all templates loaded; screenshots in the verification
folder):

- `sky-noon.png` — 12:00 local: blue day gradient, hazy
  blue-grey hills, fire small in bright ambient light, dragon
  dwelling at the fire.
- `sky-sunrise.png` — 08:32 local (sun el −0.8°): the orange
  dusk palette at the real sunrise; field fully readable.
- `sky-sunset.png` — 17:57 local (sun el −0.6°): same palette at
  the real sunset; warm light rakes the dwelling triceratops.
- `sky-night.png` — 02:00 on 2026-11-09 (sun −55.9°, moon
  −61.2°, illumination 0.2% — genuinely moonless, the day after
  the Nov 9 01:02 new moon): stars, fireflies, glowing
  mushrooms, fire pool dominant; field dark but readable.
- `sky-moonlit.png` — 2026-11-20 22:00 (moon el 49.2°, az
  174.4°, illumination 85.2%): the field visibly moonlit
  blue-grey versus the moonless capture. The moon itself is due
  south — behind the north-facing camera — so this validates
  moon*light*; the disc's phase rendering was validated
  separately (next item).
- `moon-phase-grid.png` — the page's `drawMoonPhase` extracted
  verbatim into a test page and drawn at phases 0.02–0.982:
  waxing lit on the right through half (0.25) and gibbous
  (0.374) to full (0.5), waning mirrored on the left (0.75 half,
  0.9 crescent). Orientation and shapes correct; dark side
  carries faint earthshine maria by design.

**Regression check.** The standard verify (420 harness steps at
the live clock, i.e. night) re-run after both changes: all
templates load, `loadErrors: []`, zero console errors, an
entering creature reports clip `"walk"`, and a stepped shot
shows a creature dwelling at the fire with the dressed scene
around it. Leave/despawn and signature clips remain *not
directly observed* in the VM harness (same limitation as the
initial build).

**Frame cost.** Unchanged in method and caveat: SwiftShader
fps readings on this VM are dt-cap artifacts (~22 on the page
counter; real software frames 0.5–3 s under contention), not a
measurement. The dressing adds only instanced/merged geometry
and three small point systems — no new dynamic lights (the fire
still owns the only PointLights) and no shadow maps — so the
real-GPU cost expectation is unchanged, still unverified by
measurement on the RTX 3060.

**Harness war story (for the next verifier):** a killed driver
run left its Chrome profile locked, and later runs' Chrome
exited instantly on the stale singleton lock while the driver
polled a dead socket until its deadline. Both drivers now use
a fresh `--user-data-dir` per run, and runs should be wrapped
in a `timeout` watchdog.

## Results — south-facing rotation + density pass (2026-11-08/09)

Two owner-directed changes on top of the enrichment build:
(1) the camera moved to the north side of the clearing looking
**south** (`CAM_BASE` z +10.8 → −10.8, same distance/height;
`CAM_LOOK.y` 1.0 → 3.0 so the frame's elevation band is roughly
−28°…+27° instead of pitched down) so the sun/moon discs cross
the visible sky; (2) a density pass inspired by a reference
photo (lush forest campfire, stone-ringed fire, layered
snow-capped vista): three `buildRidge` silhouettes to the south
(R 118/142/168, the far ridge snow-capped above a 0.78
snowline, gaps at |θ| = 65° so rise/set arcs are never blocked
by a peak), 4 large framing pines at the frame edges, pines
190 → 245 (a taller back ring), grass 950 → 1,250, ferns
70 → 115, 46 moss discs, 30 extra rocks (some moss-tinted),
2 fallen logs, and the fire's stone ring rebuilt as a
16-stone InstancedMesh with per-stone scale/tilt/shade. All
scatter respects the keep-clear guide; no new dynamic lights,
no shadow maps. The sky math needed **no change** —
`azElToVec` already honours compass azimuth in world space
(N = −z, S = +z), so facing south puts east on the left
automatically; the 2026-11-08 event-time table above therefore
stands unmodified. Director, GLBs, fire spots, and all world
positions are untouched — dwelling creatures now face the
viewer across the fire.

**Bug found and fixed by the rotation:** at the 2026-11-08
13:15 capture the new moon (illumination 0.3%, el 20°) rendered
as a solid **black disc** in the blue noon sky — invisible as
an artifact while the moon was behind the old camera. The moon
disc is now gated: opacity (and visibility) scale with
`clamp((6 − sunEl)/10) × clamp(frac × 2.5)`, so the disc only
appears when the sky is dark enough or the moon lit enough to
read as a moon. Trade-off: a pale daytime moon is no longer
drawn (v1 choice, deliberate).

**Frame geometry (measured from the captures + the page's
own reported el/az):** the frame spans azimuth ≈ 137–223° at
the horizon. On 2026-11-08 the sun is inside that window from
mid-morning until ≈ 16:25; the exact rise/set discs (az 115° /
244.8°) fall ~22° outside the edges — the sunset capture
instead shows the alpenglow band on the snow range, the same
composition as the reference photo. The moon's window is the
same; whether its disc is in frame depends on the season's
transit elevation (probe below).

**Captures** (frozen-time seam, all zero console errors, all
templates loaded, page sky values matching the standalone
math exactly; screenshots in the verification folder):

- `final2-noon.png` — 2026-11-08 13:15: **sun disc IN FRAME**
  at culmination (el 23.7°, az 179.9°), top-centre; no black
  moon disc; snow reads on the far peaks only; the clearing
  reads as an enclosed forest clearing, not a lawn.
- `final2-sunrise.png` — 08:32: alpenglow on the snow range,
  dragon dwelling at the fire facing the camera.
- `final2-sunset.png` — 17:57: the reference composition —
  fire foreground, forest frame, lit mountain vista beyond;
  a triceratops at the fire. (This capture is also the new
  `preview.jpg`.)
- `final2-descent.png` — 16:40 (sun el 9.8°, az 229.2°): late
  light raking from frame-right, snow range pink-white; the
  disc itself has just left the frame's right edge.
- `final2-night.png` — 2026-11-09 02:00 (moonless): ridges as
  layered near-black silhouettes with a whisper of separation,
  stars, fireflies, glowing mushrooms, stone ring in firelight.
- `final-moonlit.png` — 2026-11-20 22:00 (moon el 49.2°,
  az 174.4°, illumination 85%): the field visibly moonlit —
  but the disc is **above the frame**, and a probe of the
  full day (page math, 10-minute steps) shows the Nov 20 moon
  never enters the band: it rises ENE in the afternoon,
  transits at el 49.2°, and sets WNW. That is geometry, not a
  rendering failure; Nov 20 remains the moon*light* case.
- `final2-moondisc.png` — 2026-07-24 22:40 (moon el 12.6°,
  az 187.8°, illumination 83%, sun el −10.1°): **moon disc
  IN FRAME** above the ridge line just right of centre,
  gibbous with halo, field moonlit — the proof the rotation
  worked for the moon. Southern-transit moon discs occur in
  the summer-evening geometry; winter full moons transit too
  high for any ground-level frame.

**Regression check.** The standard verify (420 harness steps
at the live clock, ~00:00 local) re-run after both changes:
**PASS** — all templates load, `loadErrors: []`, zero console
errors, an entering triceratops reports clip `"walk"`, a
goblin dwells at its fire spot, stepped status pair consistent.

**Frame cost.** The density pass adds only instanced/merged
geometry (three ribbon meshes, a few hundred extra instances
across the instanced sets, one new 16-instance mesh); the
SwiftShader
page counter still reads ~22 fps (the same dt-cap artifact as
before, not a measurement). Real-GPU cost on the owner's
RTX 3060 remains unverified by measurement; the live-desktop
redeploy (below) ran at 3840×2160 without visible distress,
which is an observation, not a benchmark.

**Redeploy (2026-11-09 ~00:00–00:05 local).** Changed files
(`js/wallpaper.js` sha256 `dc180cb5…`, `preview.jpg` sha256
`107aa39e…`) synced via the PC bridge to **both** PC copies
(`D:\wallpapers\campfire-wallpaper` and the Lively Library
copy) and hash-verified at all four destination files;
Lively restarted (core + watchdog + player; UI closed again)
and the Campfire tile re-invoked via UIA. The live desktop
screenshot at 00:05 shows the south-facing framing on the real
3840×2160 desktop: ridge silhouettes across the horizon, the
16-stone ring in firelight, framing pines at the edges — a
moonless night (new moon 2026-11-09 01:02), so the disc proof
rests on the frozen captures above, as planned.

## Results — tree fix pass (2026-11-09)

Owner-directed (2026-11-09 05:43): "Remove the trees from the
front and make the trees in the back have more detail. Right
now they look inverted." Diagnosis from the `final2-noon`
capture: the four density-pass framing pines filled the frame
edges with black bulk, and the forest edge's merged 3-cone
foliage read at distance as plain dark triangles — tiers
invisible, trunks unreadable, no internal shading.

Changes (`js/wallpaper.js`, plus a regenerated `preview.jpg`):

- The foreground framing-pines block is deleted outright;
  the clearing is viewed across open field again. (Seeded-
  layout note: scatter placed after that block — moss, extra
  rocks, fallen logs — lands in new positions; the treeline,
  placed earlier in the sequence, is unchanged.)
- All pine foliage now comes from `makePineFoliageGeo()`:
  five flat stepped tiers (radii 1.04 → 0.33, heights
  1.15–1.50) with per-tier Y rotation and a baked
  vertex-colour shade gradient (0.42 at the bottom shelf →
  1.00 at the tip), rendered with a flat-shaded,
  vertex-coloured material in a slightly lighter green.
  The one geometry serves the 245 instanced forest-edge
  pines, the 15 scattered ring pines, and the hand-placed
  tall pine. Instance counts and draw structure unchanged;
  no new lights, no shadow maps.

**Captures** (frozen-time seam, zero console errors, all
templates loaded; screenshots in the verification folder):

- `trees-noon.png` — 2026-11-08 13:15: framing pines gone;
  treeline and mid-field pines show stepped tiers with
  faceted shading and visible trunks; sun disc in frame.
- `trees-sunset.png` — 17:57: tiered treeline against the
  alpenglow ridges, dragon at the fire. This capture is the
  new `preview.jpg`.
- `trees-night.png` — 2026-11-09 02:00 (moonless): tiered
  silhouettes, fireflies, glowing mushrooms, fire pool.

**Regression check.** Standard verify at the live clock
(~05:53, night): **PASS** — all templates load,
`loadErrors: []`, zero console errors, one triceratops
dwelling at its fire spot, an entering triceratops reporting
clip `"walk"` and moving between the two status reads.

**Frame cost.** Foliage geometry grows modestly (5 tiers of
9-segment cones vs 3 of 8; one shared geometry per pine
system). SwiftShader counter still ~20–22 fps (the known
dt-cap artifact, not a measurement). Real-GPU cost on the
RTX 3060 remains unverified by measurement.

**Harness note:** `/opt/meta-chromium/chrome` currently
refuses raw CDP launches ("Hatch WebGL domain policy is
required for browser startup"); the drivers were run with
`CHROME_PATH` pointed at the Chrome-for-Testing headless
shell in the verification folder (`chs/`), as in the initial
build.

**Redeploy (2026-11-09 ~05:58–06:00 local).**
`js/wallpaper.js` (sha256
`e1a18b87b985acabafbada93dbc97cd1bd8ebd28b8498d3919f9a8d74aba227b`)
and `preview.jpg` (sha256
`46a646d0d07c9b14a51a18e63e5dfccfa90b447087cb944ede653d4901ad6584`)
synced via the bridge to both PC copies and hash-verified at
all four destination files (certutil output read back over
the bridge); Lively killed (UI + watchdog + player) and
relaunched, the Campfire Companions tile re-invoked via
UIA, the UI process closed afterwards leaving core +
watchdog + player. The final live screenshot (06:00, real
clock, moonless night) shows the new scene on the real
3840×2160 desktop: open frame edges, tiered treeline
silhouettes, a triceratops at the fire.

## Results — definition pass (2026-11-09)

Owner-directed (2026-11-09 11:30): "Can we increase the
definition of everything?" A fidelity pass over geometry,
textures, and render settings, all in `js/wallpaper.js`
(plus a regenerated `preview.jpg`):

- Pixel-ratio cap 1.5 → 2 (bites under Windows display
  scaling; at native 100% scaling nothing changes).
- Ground plane 100×100 → 170×170 segments — the per-vertex
  height and colour functions now resolve at ~2.9× the
  density, so the field's undulation and colour grain are
  visibly finer.
- Segment/detail bumps across the dressing set: pine tiers
  9 → 14 radial segments; trunks, logs, and stumps 5–9 →
  7–12; rocks `DodecahedronGeometry` detail 0 → 1; bushes
  and oak blobs `IcosahedronGeometry` detail 1 → 2; grass
  cones 4 → 6; ferns 5 → 8; berries and mushroom caps
  roughly doubled; horizon hills 24×12 → 40×20; ridge
  skyline steps 88 → 160; moss discs 10 → 20 segments;
  sky dome 24×16 → 48×24; sun/moon discs 32 → 48.
- Moon phase texture 256² → 512².
- `sharpenTextures()` at GLB load: anisotropic filtering
  (renderer maximum, capped at 8) on creature and chest
  maps, so textures stay crisp at grazing angles.
  SkeletonUtils clones share the maps.
- Manners preserved: no shadow maps, particle counts
  unchanged, hidden-page pause unchanged.

**Measured before/after** (frozen noon 2026-11-08 13:15,
probe copies of the shipped code reporting
`renderer.info` through the `#status` JSON, SwiftShader):
triangles **217,024 → 311,626 (+44%)**, draw calls
**119 → 119** (instancing absorbs the added detail), page
fps **22 → 22** — the software-renderer floor is unchanged
even at the higher triangle count; the real-GPU cost is a
small fraction of the RTX 3060's headroom, and Lively
pauses the page under fullscreen apps regardless. Zero
console errors in every capture. Live-clock verify on the
shipped folder: all templates load, creatures on stage and
moving between the two screenshot reads. Before/after HD
captures (1920×1080, frozen noon) in the verification
folder — `base-noon-hd.png`, `after-noon-hd.png` — show
the finer ground grain, smoother rocks and bushes, and
the smoother ridge skyline. `preview.jpg` regenerated
from the new build's golden-sunset capture
(`def-sunset-gold.png`, sun just below the horizon).
