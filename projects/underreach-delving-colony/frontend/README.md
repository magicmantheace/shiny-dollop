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

## Assets

All models are byte-for-byte **Game Asset Builder** catalog files —
the pipeline is the art source, per the owner's direction:

| File | Role here | Catalog sha256 |
|---|---|---|
| `assets/snow-goblin.glb` | delver stand-in | `c4ba135bcb26a85d…` |
| `assets/ember-dragon.glb` | critter stand-in | `2837c6b2969f0bf6…` |
| `assets/treasure-chest.glb` | the stockpile | `2b6e51cc0d8273e3…` |
| `assets/mushroom-cluster.glb` | farm plots | `6e607ffdaeed58c7…` |

The dedicated **delver** and **gloam-lurker** assets were in the
pipeline (delver through prep) when the owner ordered all PC GPU
work stopped on 2026-11-10. Until that lane reopens, the two
catalogued creatures above stand in; swapping them in later is a
two-line change (`DELVER_SCENE` / `CRITTER_SCENE` in `main.gd`).
Lanterns are emissive spheres on posts (a builder lantern prop is
in the same stopped queue).

## Honest limits

- Nothing here has run on owner hardware; no frame-rate claims.
  The catalog GLBs are unoptimized source meshes (the snow-goblin
  alone is ~22 MB) — fine for a prototype, not for shipping.
- The depth-slice view is a prototype answer to presenting a 3D
  voxel dig, not the final camera design.
