# Underreach frontend (S4 prototype)

A Godot 4 presentation layer over the Rust sim core. It holds **no
sim rules**: it renders the view JSON produced by the bridge
(`../sim/src/bin/bridge.rs`) and sends player commands back through
it (carve, place lantern, assign job, plant a plot, craft a mask,
plus the scenario network scripts).

## Run

1. Build the bridge: `cargo build --release --bin bridge` in `../sim`.
2. Open this folder in Godot 4.7+ and run, or:
   `godot --path .` (the frontend finds the bridge at
   `../sim/target/release/bridge`; override with the
   `UNDERREACH_BRIDGE` environment variable, and pick a scenario
   with `UNDERREACH_SCENARIO=s1|s2|s3|s5`, default `s3`).

## Play

- The view is a **depth slice**: one sim depth (layer) at a time.
  `Layer − / +` moves through the dig; the camera targets that
  depth. Right/middle-drag orbits, wheel zooms, Q/E/W/S pan.
- Tools (left panel): **Inspect**, **Carve** (click a cell — the
  player-frontier digs), **Lantern** (place a tier-1 lantern),
  **Plant** (designate a mushroom plot).
- Colony buttons: **Light the way** / **Light the deep** run the
  scenario's lantern scripts; **Craft mask** spends 2 goods.
- The right panel lists every delver with live needs and a job
  dropdown (Miner / Hauler / Farmer / Herbalist / Unassigned). A
  downed delver's name turns red and a `CLOCK` count appears — that's
  the rescue clock, live.
- Bottom: the Deep Ledger feed, newest last.

## Verify (headless)

```
godot --headless --path . -- --underreach-verify
```

Initialises the S3 colony through the bridge, lights the way, drives
4,000 ticks from inside Godot, and asserts the colony produced goods
and the rendered entity/floor state matches the sim view. Prints
`UNDERREACH_VERIFY_PASS ...` on success.

Since S6 the verify runs a **second pass**: it initialises the `gen`
scenario (the same colony founded on a procedurally generated
Floor 1), jumps the view layer to the descent's depth, queues the
`open_floor1` command (lanterns down the passages to the first
face), drives another 4,000 ticks, and prints a second line —
`UNDERREACH_VERIFY_PASS scenario=gen goods=24 delvers=5
floor_instances=61 tick=4000` (floor_instances = carved cells on
the descent layer, a generated number).

The `gen` scenario also appears in the Scenario button row, with
an **Open Floor 1 (gen)** colony button. Generated-floor features
render as placeholder markers: the descent is an emissive violet
block, dens are dark red-brown blocks, dressing anchors are small
coloured boxes by kind, and loose-rock / bad-air rock rims are
tinted (amber-brown / green). Placeholder → asset mapping:
`../docs/FLOOR_GENERATION.md`.

## Assets

All models are byte-for-byte **Game Asset Builder** catalog files —
the pipeline is the art source, per the owner's direction:

| File | Role here | Catalog sha256 |
|---|---|---|
| `assets/delver.glb` | the delvers (dedicated asset) | `7ab7262b7eeb5716c23bd0494f133a7674a0f858cd4a839bd80c8ca7e8b7edc4` |
| `assets/lantern.glb` | lantern prop (Tier 1) | `5dffb6360730c30d9a0a3c928afd89f5f9148c4a1ecf732b8ffbc71f426cf900` |
| `assets/cot.glb` | delver beds | `67e070f2012f416f96b202fe0cb419255b5f57a72b83053f916ba22ca1659ef7` |
| `assets/gloam-lurker.glb` | critters (dedicated asset) | `f0c881cb9bd39e0b2223f3d20be45fd46e18fd220de64ae4ed7d9ce05d8ff4c3` |
| `assets/ember-dragon.glb` | former critter stand-in (unused) | `2837c6b2969f0bf6…` |
| `assets/treasure-chest.glb` | the stockpile | `2b6e51cc0d8273e3…` |
| `assets/mushroom-cluster.glb` | farm plots | `6e607ffdaeed58c7…` |
| `assets/snow-goblin.glb` | former delver stand-in (unused) | `c4ba135bcb26a85d…` |

Source for the three 2026-11-11 additions: Game Asset Builder
catalog on branch `game-asset-builder/underreach-assets` @
`5642dce` (`outputs/<slug>/<slug>.glb` in that worktree), copied
byte-for-byte — the frontend copies hash to the catalog values
above. The gloam-lurker followed on 2026-11-12 from the same
branch @ `328bca3`, copied the same way.

The dedicated **delver** replaced the snow-goblin stand-in on
2026-11-11 (`DELVER_SCENE` in `main.gd`). It is the
arm-separation-gated rebuild: a new A-pose concept passed the
builder's preflight (arm daylight 0.5955), and the finished rigged
biped carries idle / walk / run / bounce clips. The **gloam-lurker**
critter asset landed on 2026-11-12 (`CRITTER_SCENE` now points at
it; the ember-dragon stand-in is retired, file kept unused). It
passed the builder's quadruped leg-separation gates — concept
preflight and posed renders of every shipped clip (idle / walk /
run / shiver) — before cataloguing.
Lanterns now render the builder's Tier-1 lantern prop; the actual
light still comes from an `OmniLight3D` per lantern, with a small
emissive marker at the flame point (the prop is untextured
vertex-colour geometry). Beds render the builder cot prop, scaled
by height target so its footprint matches the plain box it
replaced.

## Honest limits

- Nothing here has run on owner hardware; no frame-rate claims.
  The catalog GLBs are unoptimized source meshes (the delver alone
  is ~20 MB) — fine for a prototype, not for shipping.
- The 2026-11-11 asset swap is verified for loading and logic
  only (headless verify below); how the delver, lantern, and cot
  actually look in the scene is **unverified** until the on-PC
  visual pass.
- The depth-slice view is a prototype answer to presenting a 3D
  voxel dig, not the final camera design.
