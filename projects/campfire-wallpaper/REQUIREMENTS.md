# Requirements — Campfire Companions v1

Commissioned by the owner 2026-11-08 (Lively + three.js route chosen
over a Godot-native build).

## Functional

1. A live desktop wallpaper for Lively Wallpaper (web type,
   `LivelyInfo.json` at the project root, entry `index.html`); the
   same page must also run as a browser preview over HTTP.
2. Scene: a grass field at dusk/night, a campfire at centre built
   from primitives (stone ring, logs) with particle flames, rising
   embers, a flickering warm light and ground glow; scattered
   primitive rocks, pines and bushes; a starry dusk sky and fog.
3. Creatures: the Game Asset Builder's ember-dragon, snow-goblin and
   triceratops GLBs, plus the treasure-chest as set dressing, copied
   into the project (self-contained).
4. Creature director: per-instance state machine — spawn at a random
   field edge, travel to a random free spot near the fire, dwell on
   the idle clip (occasionally playing the creature's signature
   clip), then leave by an edge and despawn. Random creature choice
   and timing; at most 3 concurrent creatures; a fire spot is never
   double-booked.
5. Travel uses a `walk` clip by name when a creature's GLB provides
   one; until then, per-creature gait from existing clips (dragon
   hops, triceratops bounces, goblin glides).

## Non-functional

6. Wallpaper manners: fixed camera with only a slight drift, pixel
   ratio capped at 2, modest particle counts, no shadow maps
   (blob shadows), render loop paused while the page is hidden.
7. Robust: a missing/failed GLB degrades to fewer creatures, never
   a blank page; no WebGL shows a readable fallback message.
8. No build step, no runtime network access, no dependencies beyond
   vendored three.js r180.

## Out of scope for v1

- Installing/deploying to the owner's PC (a later step, done with
  the owner).
- New GAB animations beyond the P4 set (walk/run/idle/signature)
  without a director review.
- Lively user properties (creature toggles, fire size sliders).
- Sound.
