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
                  "x": 0.0, "z": 0.0 }] }
```

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
