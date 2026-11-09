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
