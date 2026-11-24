# Floor generation — procedural floors from a unified world seed (S6)

Design record for slice S6, built 2026-11-12 on branch
`underreach-delving-colony/floor-generation`. The generator lives
in `sim/src/gen.rs`; the demo colony founded on a generated
Floor 1 is `build_scenario_gen` in `sim/src/scenario.rs`.

## Owner decisions behind this slice (2026-11-12)

1. **Themed, seeded floors.** "While each floor will have a theme
   can we get each floor to be randomly generated based on the
   theme and a unified world seed? Starting by designing floor 1
   even if it has placeholder assets for now?"
2. **Pre-connected passages (amendment, same day).** "I think
   there should also be some pre connected passages through each
   floor to start."
3. **Dens and stairs on the network (amendment #2, same day).**
   The passage network must also connect to some monster dens,
   and the stairs down live in a natural cavern **on** the
   network, far from the entry in network distance — finding the
   way down must be exploration, never a strip-mining search.

## The seed scheme

- One **world seed** per colony/save (`Sim.world_seed`, persisted
  in the save; for hand-built scenarios it equals the RNG seed
  they were founded with).
- Each floor's layout is a **pure function** of
  `(world_seed, floor_index)`:
  `floor_seed = splitmix64_mix(world_seed ^ floor_index · φ)`,
  and generation runs on its own xorshift64* stream derived from
  that — **hash-mixed, never sequential draws** from a shared
  stream. Generating floor 5 without visiting floors 2–4 yields
  the identical floor 5; generation order is irrelevant
  (test-verified for floors 1–4, standalone vs sequential vs
  interleaved).
- **Generation never touches the sim's runtime RNG.** The
  scenario founded on a generated floor starts with
  `rng_state == world_seed`, and the player's opening script
  draws nothing either (test-verified).
- The sim carries a small `FloorInfo` record (floor index,
  descent cell, den centres, dressing anchors, hazard pockets)
  in its save, so the frontend renders the floor's features
  after a load. Save/load reproduces the state hash exactly,
  floor record included (test-verified).
- Purity rule learned the hard way during this slice: any set
  sampled during generation must be **sorted first** — a
  `HashSet`'s iteration order is not stable between calls, and
  one unsorted sample made floor 2 differ between generation
  orders. The independence test caught it; the rule is now part
  of the generator's contract.

## Guarantees, enforced by deterministic sampling

Some floor properties are promises, not hopes: the descent's
minimum network distance, the on-network den minimums, sealed
cavities staying sealed, connected cavities staying reachable.
Wandering passages in a small grid self-shortcut (segments pass
adjacent and merge), so construction alone cannot promise them.
The generator therefore **samples**: layouts are drawn from a
stream derived from the floor seed until one meets every
guarantee — up to 16 attempts, keeping the best (longest descent
trek among attempts satisfying the hard invariants) if none
qualifies. The attempt stream derives from the same floor seed,
so the chosen layout is still a pure function of
`(world_seed, floor_index)`; the winning attempt number is
recorded in the layout (`generation_attempts`).

## The theme table

One row per band (`Theme` in `sim/src/gen.rs`); floors 1–5 map
to the five bands, floors ≥ 6 cycle the four non-Shallows bands,
mirroring the S5 `hazards_at` recombination. Shared base values
unless a row overrides: footprint 24×12×8; 5 connected cavities
+ up to 2 sealed; cavity size 2–3 × 2–3 cells; dens 2 on-network
+ 1 off, den minimum network distance 10; descent minimum
network distance 24; 6 veins of 2–3 cells (richest pocket 4);
at most 3 registered faces; loose rock 5 pockets of 1–3 cells;
bad air 4 pockets of 1–2 cells (all at y ≥ 6); 3 dead-end spurs
of 3–6 cells; 1 loop edge; ~33 % of passage segments widened to
2 cells.

| Band (floors) | Built | Hazards | Resources | Loose / bad-air pockets | Dressing kinds | Den critters |
|---|---|---|---|---|---|---|
| Shallows (1) | **yes** | none | ore | 5 / 4 (base) | stalactite, stalagmite, rubble, boulder | gloam rat |
| Fungal Reaches (2) | stub | spores | ore + fungal nodes (4 clusters) | 3 / 3 | giant mushroom, spore pod, stalactite, rubble | gloam rat, deep lurker |
| Drowned Galleries (3) | stub | flooded (flag only) | ore | 4 / 5, veins 5 | pump, air bell, rubble, stalagmite | deep lurker |
| Crystal Dark (4) | stub | none flagged | ore | 6 / 2 | crystal formation, lens post, rubble | deep lurker |
| Magma Roots (5) | stub | hot (flag only) | ore | 6 / 4 | basalt column, heat pipe, rubble | deep lurker |

The stub rows are **explicitly NOT BUILT**: they generate
through the same code so the shape is testable, but no scenario,
balance, or band mechanics exist for them yet.

## The generator, step by step

1. **Base fill.** Stone everywhere; Earth cap at y 0–1 (the S1
   convention). Content lives at y 3–9, inside a 1-cell rock
   skin.
2. **The entry camp** — the same room every scenario has used
   (x 2–6, z 3–5 at y 3). Every floor's entry is this room; the
   colony is founded there.
3. **The descent cavern** — 3×1×3, deep east (centre x 17–20,
   y 7–9, z 2–5). It holds the `DescentStairs` anchor; its centre
   is the floor's descent point.
4. **Cavities.** Five connected cavities placed in depth zones
   (west-shallow → mid → east-deep), two sealed cavities, and
   one **detour cavity** far west and deep. Every room keeps at
   least one rock cell from every other (**plan separation**:
   sealed rooms and the descent cavern also keep their (x, z)
   column plus halo clear of other rooms and of passage columns,
   so a shaft can never clip a sealed room open).
5. **The passage network.** Nodes: camp → connected cavities
   (the last pair visited far-from-descent first) → detour →
   descent. Segments route in plan view at the start node's
   depth, then shaft down/up at the target's column; segments
   never breach sealed rooms, and only the final approach may
   enter the descent cavern. One extra link (node *i* → *i+2*)
   makes exactly one loop; three spurs end blind. Network cells
   are plain carved cells — **no sim rule treats them
   specially**; they start dark like everything else and become
   colony-usable only when lanterned, exactly per the
   lit-nav-graph rule.
6. **Measurement.** BFS distances from the entry over the final
   carved grid — the numbers the guarantees are checked
   against, recorded in the layout.
7. **Dens.** The two farthest connected cavities at network
   distance ≥ 10 become dens of the theme's first critter kind;
   one sealed cavity may also be a den (the minority). On
   Floor 1 that is gloam rats, well past the camp's first
   stretch — early exploration down the passages meets teeth,
   not empty cave.
8. **Veins and faces.** Six veins: the richest pocket (4 cells)
   is embedded off-network in deep rock; the rest grow where
   their stand cell is already carved space. A vein whose stand
   is carved registers as a workable face (ore = 6 × its cells);
   at most 3 faces, and the **starter face's stand sits 8–14
   network steps from the entry** — deliberately beyond the
   camp lantern's light, so the S1 beat survives on generated
   floors: the colony refuses the dark until the player carries
   light down the passages. Veins that fail to grow are rolled
   back to stone; the layout accounts for every resource cell.
9. **Hazard pockets.** Loose rock and bad air are new cell
   kinds (`Cell::Loose`, `Cell::BadAir`) — generation and
   rendering only in this slice, the same modelling stance S5
   took for flooded/hot. Bad air is seeded **and grown** only at
   y ≥ 6: it pools deep and never leaks upward. Pockets keep
   clear of the entry (Manhattan ≥ 6) and of the descent.
10. **Dressing.** 1–3 anchors per cavity from the theme's
    dressing kinds, plus the stairs anchor in the descent
    cavern. Anchors are data; the frontend draws placeholder
    markers (below).

## Floor 1 — the Shallows, in numbers

- **Footprint 24 × 12 × 8** — the exact dimensions of the proven
  S1–S5 scenario worlds, so every existing loop (pathing,
  lantern radius 3, rescue clock) behaves identically.
- **Network:** 8 nodes, 8 links (one loop), 52–97 passage cells
  across the verified seed spread; 5 connected cavities + the
  detour, 0–2 sealed cavities.
- **Descent:** network distance **25–45** across the spread
  (guarantee ≥ 24). Demo seed `0x5EED0007`: stairs at (20, 9, 3),
  distance 28, 52 network cells.
- **Dens:** exactly 2 on-network (distances 18–36 across the
  spread, guarantee ≥ 10), 0–1 sealed. The scenario spawns one
  resident gloam rat per den at founding.
- **Economy:** 3 faces, 6 veins; face ore = 6 × vein cells. The
  demo colony produced 24 goods in 6 000 ticks after opening —
  comfortably above the hand-built S3 colony's 20.
- **Hazards:** loose rock 7–12 cells, bad air 5–8 cells across
  the spread (pocket counts/sizes per the theme table).
- **Dressing:** 15–23 anchors per floor.

## Placeholders and their queued replacements

Adam approved placeholders for this slice ("even if it has
placeholder assets for now"). Dressing renders as small coloured
boxes in the frontend, grouped by band family; hazard rock gets
rim colours (loose rock amber-brown, bad air green); the descent
is an emissive violet block; dens are dark red-brown blocks.
**Passages need no placeholder at all** — they are carved rock
cells and render as ordinary floor.

| Placeholder | Queued asset (docs/ASSET_LIST.md) |
|---|---|
| Boulder dressing | ✅ already in the Game Asset Builder catalog (env pack) — swap-in is frontend work, not queued |
| Stalactite / Stalagmite / Rubble | §6 Shallows dressing set — ⬜ not built |
| DescentStairs anchor / descent marker | Surface gate / descents — ⬜ not built |
| SporePod / GiantMushroom | §6 Fungal dressing set — ⬜ |
| Pump / AirBell | §6 Drowned dressing set — ⬜ |
| CrystalFormation / LensPost | §6 Crystal dressing set — ⬜ |
| BasaltColumn / HeatPipe | §6 Magma dressing set — ⬜ |

## Explicitly NOT built in this slice

- **Cave-in and bad-air mechanics** — and with them the gameplay
  answers (timber supports, ventilation). The cells exist so
  floors can be designed around them; walking past one does
  nothing yet.
- **Face registration for embedded pockets.** An off-network
  vein is layout data; if a player carves into one today, no
  face appears. Registering faces on exposure is a later slice.
- **Floor-to-floor traversal.** The descent is a placed,
  rendered, guaranteed-reachable point — not yet a transition.
  Multi-floor saves arrive with it.
- **Den wiring for the runtime auto-spawner.** Dens seed their
  residents at founding in the gen scenario; the 700-tick
  auto-spawner still uses its S3 rule (carved, unlit, near
  light).
- **Floors 2–5 scenarios and balance** — stub themes only.
- **Per-band footprints** — every floor currently generates in
  the Floor 1 footprint.
