# Requirements — Underreach: Delving Colony

## Product requirements (owner-decided; see docs/MUSE_HANDOFF.md)

1. A survival/colony game in the Underreach fusing ASKA's self-sustaining
   NPC village with RuneScape: Dragonwilds' skills/XP spine.
2. Scope: 1–4 co-op. Not an MMO.
3. The player is the frontier: NPC delvers work only inside the lantern
   network; only the player extends the light into the dark.
4. Core loop: delve → haul → convert, through gated depth-band economies
   (Shallows → Fungal Reaches → Drowned Galleries → Crystal Dark →
   Magma Roots, then recombined mutations — depth is endless).
5. Building: hybrid voxel-carve. Voxel terrain (smaller, bevelled/
   smoothed presentation) for digging, walls, floors, stairs, plugs,
   dams, rescue shafts; crafted kit pieces snapped to the grid for
   colonist-facing objects (beds, forges, lanterns, pumps, rails,
   workshops).
6. The lantern network doubles as the NPC navigation graph: delvers
   path along lit routes.
7. Delvers are full-ASKA people: names, needs, moods, skill growth.
   Colony growth: surface recruitment and children growing up.
8. Threats: a mix, leaning combat-led.
9. Rescue: delvers lost in the dark are rescuable on a real-time lantern
   clock; permadeath only when a rescue fails. Player death (default):
   wake rescued at the last camp with no gear; hardcore mode optional.
10. No ending: the record is the colony's Deep Ledger (depths first lit,
    rescues, losses by name). Abandoned forward camps persist as ruins.
    A colony can fall; a successor colony inherits the Ledger and can
    dig down into its predecessor's ruins.

## Technical requirements

11. Core/frontend split: deterministic Rust sim core, headless-testable;
    Godot 4 frontend later, replaceable, holding no sim rules.
12. Determinism: identical initial state + commands → identical state
    hash. Randomness only via a seeded RNG recorded in the save.
13. Saves: canonical JSON + SHA-256 state hash; load reproduces hash;
    the Deep Ledger is append-only.
14. Lantern model (adopted 2026-11-10): each depth band produces the
    fuel/housing that makes the next band survivable; lantern tiers
    carry radius, burn time, steadiness, and tags; steadiness affects
    delver morale/accidents; the rescue clock is the trapped delver's
    lantern tier + fuel remaining.
15. Depth gates (adopted 2026-11-10): soft gates with hard physical
    edges (no air solution → no flooded sections; no heat protection →
    no Magma Roots).

## S1 acceptance (this slice)

- Voxel world with carving; lantern lighting over carved cells; BFS
  pathing restricted to lit carved cells.
- One delver running delve → haul → convert with needs (energy, hunger)
  and skills (mining, hauling XP), resting/eating at camp.
- Unlit work face is unreachable and the blockage is ledgered; placing
  lanterns records first light per depth and unblocks production.
- Lantern fuel burn-down can extinguish a lantern and shrink the network.
- Save/load roundtrip preserves the state hash; post-load continuation
  is deterministic.
- `cargo test` green; `scenario` binary demonstrates both phases.
