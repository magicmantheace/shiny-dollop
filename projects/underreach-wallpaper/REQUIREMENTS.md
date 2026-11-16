# Underreach Wallpaper — requirements

Commissioned by the owner (voice, 2026-11-16), with two
refinements the same day: the Surface Gate is mandatory, the
roster rule, and the town-scale starting layout.

## v1 (this build)

1. **A new, separate Lively Wallpaper project** at
   `projects/underreach-wallpaper/`, sibling to the campfire
   wallpaper (its architecture is the template; its files and
   assets are never touched).
2. **Scene:** a town-scale cavern — the founding Underreach
   settlement as its core (Surface Gate entrance, lantern-network
   streets, workshop stations, the Deep Ledger as civic heart),
   with named expansion zones of open ground around it
   (gate-ward, founding-core, fungal-terraces, crystal-reach,
   magma-verge, workshop-row, residential-edge, south-meadow,
   deep-ward).
3. **Surface Gate (#26) is IN** — mandatory, placed as the cave
   entrance in the north wall.
4. **Roster rule:** at least one copy of every gate-passed,
   catalogue-verified Game Asset Builder asset. v1 = queue
   #1–#28, #30, the Cart extra, and the 4 pre-queue Underreach
   catalogue assets (39 GLBs), copied byte-for-byte and
   hash-verified against the catalogue.
5. **Exclusions:** #29 ore face and #31 crystal cluster are
   PARKED/untextured — not used. They join when they complete
   and pass their gates, like all future assets (#32 onward).
6. **Wanderers** walk the lantern network (graph in
   `js/layout.js`) with the campfire build's obstacle-aware
   routing (grid A* + string-pulling); creatures use their
   catalogue animation clips (walk to travel, signature clips
   while dwelling).
7. **Mood/lighting:** near-dark ambient, warm lantern pools,
   fungal/crystal glow accents, light fog. Real-light budget:
   5 (hemisphere + 4 points); all other lanterns faked.
8. **Data-driven layout:** roster in `js/roster.js`, town state
   (zones/plots/network) in `js/layout.js`, in a shape a future
   living-world sim feed could drive. **No sim or feed is built
   in this phase.**
9. **Verification on the build VM only** (headless Chromium):
   per-asset load verification, roster completeness reported by
   the page itself, routing geometry battery, FPS + raw render
   bench. **No contact with the owner's PC; no deployment.**
   End state: "ready to deploy" with deploy steps documented.

## Explicitly out of scope for v1

- Deployment to Lively on the owner's PC (later step, owner's go).
- The living-world simulation / any external feed (phase 2,
  discussed, not commissioned).
- Any change to the campfire wallpaper, the Game Asset Builder,
  the asset queue, or the Underreach game project.
- Parked assets #29/#31 and unfinished queue assets #32+.
