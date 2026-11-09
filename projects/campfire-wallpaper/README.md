# Campfire Companions — live desktop wallpaper

A field at dusk, rendered live in your desktop background. Creatures
built by the [Game Asset Builder](../game-asset-builder/) wander in
from the dark, gather around a campfire to warm themselves, and wander
off again — an ember dragon that hops, a snow goblin that waves, a
triceratops that bounces — while the fire crackles with drifting
embers under a starry sky.

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
  P4 animation slice, all three catalog creatures do (they also carry
  an unused-for-now `run` clip). The fallback, for any future GLB
  without a walk clip, is each creature's natural gait: the dragon
  hops, the triceratops bounces, the goblin glides. Adding a creature
  later needs no director change — drop the GLB in `assets/`, add a
  config row, reload.
- **Wallpaper manners:** pixel ratio capped at 1.5, ~136 fire
  particles, no shadow maps, and the render loop stops entirely when
  the page is hidden. It sips, it doesn't drink.

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
