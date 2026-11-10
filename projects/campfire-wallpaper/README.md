# Campfire Companions — live desktop wallpaper

A living field, rendered live in your desktop background. Creatures
built by the [Game Asset Builder](../game-asset-builder/) wander in
from the treeline, gather around a campfire to warm themselves, and
wander off again — an ember dragon that hops, a snow goblin that
waves, a triceratops that bounces. The field is dressed with a pine
forest edge, grass, ferns, glowing mushrooms, fireflies, log benches
and a worn dirt path — and the sky follows the **real clock**: a
true sun and moon cycle for Lethbridge, Alberta, computed locally
in the page, so the scene is bright at noon, burns orange at the
real sunset, and sits under real moonlight (or a real moonless
night) after dark.

Built with three.js (vendored, no build step, no network calls) and
packaged for [Lively Wallpaper](https://www.rocksdanister.com/wallpaper/)
on Windows. The same page also runs as a plain browser preview.

## Install in Lively (Windows)

1. **Get the project folder.** Clone this repo and use the
   `projects/campfire-wallpaper/` folder as-is — it is self-contained
   (three.js and all creature models are inside it, ~77 MB total).
2. **Install Lively Wallpaper** (free) if you haven't:
   - Microsoft Store: search **Lively Wallpaper** (by rocksdanister), or
   - GitHub: `lively-community/lively` releases — download and run the
     installer. (Installing software may raise a Windows UAC prompt;
     that's Lively's installer, expected.)
3. **Add the wallpaper:**
   - Open Lively, click **Add Wallpaper** (the `+` button).
   - Either drag the `campfire-wallpaper` folder onto the Lively
     window, or click **Browse** and select the folder that contains
     `LivelyInfo.json` (the folder itself, not a file inside it).
   - "Campfire Companions" appears in your library with a preview.
4. **Set it:** click the wallpaper in the library. It applies as your
   desktop background immediately. Lively automatically pauses it
   while a fullscreen game or app is in front — it costs nothing while
   you play.
5. **Remove it:** in Lively, right-click the wallpaper → Delete; or
   just pick a different background.

## Preview without Lively

ES modules don't load from `file://`, so serve the folder over HTTP:

```text
cd projects/campfire-wallpaper
python -m http.server 8000
```

Then open <http://localhost:8000> in Chrome or Edge. You should see
the field, the fire, and the first creature already by the fire within
a few seconds.

## How it behaves

- Up to **3 creatures** at a time. Each spawns at the field's edge,
  travels to a free spot around the fire, idles there for a while
  (occasionally doing its signature move — the goblin waves at you),
  then wanders off and despawns. Spots are never double-booked.
- The director **prefers a `walk` clip** for travel whenever a
  creature's model provides one — and since the Game Asset Builder's
  P4 animation slice, all nine catalog creatures do (they also carry
  an unused-for-now `run` clip). The roster is the original three
  (Ember Dragon, Snow Goblin, Triceratops) plus the six P5 weird
  smashups: Moth-Hart, Toasty, Lantern Snail (no walk clip — it
  travels on its idle, glide-style, and retracts as its signature),
  Axolotl-Capybara, Geode Tortoise, and Crow Postman — plus the
  Mandrake Toddler, whose builder run was finished on 2026-11-10
  after its paint was recovered (signature: `scream`). Only the
  Ember Owl-Cat of the commissioned eight is still missing; its
  paint failure is genuine and awaits the paint fix. The fallback, for any future GLB
  without a walk clip, is each creature's natural gait: the dragon
  hops, the triceratops bounces, the goblin glides. Adding a creature
  later needs no director change — drop the GLB in `assets/`, add a
  config row, reload.
- **The clearing's models are Game Asset Builder work.** The pines,
  boulders, bushes, ferns, mushroom clusters, fallen logs, and stump
  seats are the builder's catalogued environment pack (byte-for-byte
  GLB copies in `assets/`), swapped in at the same spots the
  procedural dressing used. The sky, ridges, ground, and fire stay
  code. Rocks past 30 units stay procedural — the builder boulder
  reads as a dark ball against the fog wall at range.
- **The sky runs on the real clock.** Sun and moon positions are
  computed in the page (standard SunCalc/NOAA-style solar math and
  the standard lunar approximation) for **Lethbridge, Alberta —
  49.6942° N, 112.8456° W**, a hardcoded constant; the time comes
  from the system clock, and nothing is fetched from the network.
  Sky colours, fog, the sun/moon discs, star opacity, and the
  directional light all follow the sun's elevation:
  - **Day:** blue gradient, bright ambient light; the fire stays
    lit but burns smaller and matters less.
  - **Sunrise/sunset:** the warm orange dusk this wallpaper
    originally shipped with — now the real golden-hour states.
  - **Night:** stars out, fireflies drift, the mushroom clusters
    glow, and the campfire is the dominant warm light. Moonlight
    is real too: the moon disc is drawn with its actual phase
    (canvas-generated texture, refreshed hourly), and on a
    moonless night the field is genuinely dark.
  - Precision: computed sunrise/sunset for 2026-11-08 land within
    ~1.5 minutes of timeanddate.com's Lethbridge values; moonrise/
    moonset within ~10 minutes (the low-precision lunar theory is
    the limit). Good enough for a wallpaper; details in
    `docs/TEST_PLAN.md`.
  - The camera faces **south**, so the discs cross the visible
    sky: the sun rises on the left of frame, culminates in frame
    at midday (23.7° at the November noon in Lethbridge), and
    descends toward the right; the moon crosses the same band
    whenever its transit is low enough (its high summer-evening
    transits pass overhead, out of frame — its light still
    arrives). One subtlety: near the new moon the disc is gated
    invisible rather than drawn as a black circle against the
    day sky.
- **The field is dressed, not bare.** A 245-pine instanced forest
  edge (plus three feature trees and four large framing pines at
  the frame edges), 1,250 grass tufts, ferns, berry bushes, moss
  patches, scattered rocks, two fallen logs, nine clusters of
  softly glowing mushrooms, 64 drifting fireflies, log benches
  and stump seats around a 16-stone fire ring, a woodpile and
  chopping block, a worn dirt path from the field's edge to the
  fire — and, opening to the south beyond the trees, a layered
  mountain vista: three low-poly ridge silhouettes, the farthest
  snow-capped, tinting with the sky (alpenglow at sunset, blue
  distance at noon, near-black at night). All
  primitives/instancing — no external assets — and the fire
  clearing stays readable.
- **Wallpaper manners:** pixel ratio capped at 2, ~136 fire
  particles (plus the small firefly/star point systems), no shadow
  maps, and the render loop stops entirely when the page is
  hidden. It sips, it doesn't drink.

## Layout

| Path | What |
| --- | --- |
| `index.html` | Entry point (what Lively loads) |
| `LivelyInfo.json` | Lively package metadata (type: web) |
| `js/wallpaper.js` | The whole scene + creature director |
| `assets/*.glb` | Creature models, copied verbatim from the Game Asset Builder catalog (checksums in `docs/MUSE_HANDOFF.md`) |
| `vendor/three/` | three.js r180 (module + core + GLTFLoader/SkeletonUtils addons), MIT-licensed |
| `preview.jpg` | Library thumbnail, a real capture of the scene |

Creature models are owner-generated (Hunyuan3D pipeline) and are
copied here byte-for-byte so the wallpaper has no dependency on the
Game Asset Builder's local output folders.
