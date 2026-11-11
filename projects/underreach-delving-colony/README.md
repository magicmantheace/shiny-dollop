# Underreach — Delving Colony

A survival/colony game set in the Underreach: ASKA's self-sustaining NPC
village fused with RuneScape: Dragonwilds' skills spine, built around one
idea — **the player is the frontier**. Delvers only work inside the lantern
network; only the player carries light into the dark. The loop is
delve → haul → convert, down through gated depth bands, forever: there is
no bottom and no ending, only the colony's **Deep Ledger**.

- 1–4 co-op (Dragonwilds-sized), not an MMO.
- Hybrid voxel-carve building: voxel terrain for digging and carving,
  crafted kit pieces for everything a colonist uses.
- Delvers lost in the dark are rescuable on a real-time lantern clock;
  permadeath only when a rescue fails. Colonies can fall — and a
  successor colony inherits the Ledger and digs down into the ruins.

The full design record (every owner decision) is in
[`docs/MUSE_HANDOFF.md`](docs/MUSE_HANDOFF.md). The design is the spec:
if implementation reality fights it, the conflict is recorded there, not
silently redesigned around.

## Status

**S1 — sim core: built and verified on the VM (headless).** A
deterministic Rust simulation core (`sim/`), engine-agnostic, following
the Milky Way pattern: verified core first, frontend later.

S1 proves the spine of the game in simulation:

- A voxel grid world (the Shallows) with carving.
- The lantern network: placed lanterns light carved cells; **the lit
  network is the navigation graph** — a delver paths only through light.
- One named delver with needs and skills running the full
  delve → haul → convert loop, resting and eating at camp.
- Frontier extension: an unlit ore face is unreachable (the delver
  refuses the dark and the blockage is ledgered); placing lanterns
  extends the network, records **first light** at the new depth in the
  Deep Ledger, and the loop starts producing.
- Lantern fuel burns down; a lantern that dies takes its light with it.
- Canonical save/load with a SHA-256 state hash; a loaded game continues
  deterministically identically to an uninterrupted one.

Verified: `cargo test` in `sim/` (unit + scenario tests), and the
`scenario` binary's two-phase run (blocked in the dark → lit → producing).

**Not yet built:** rendering/frontend (Godot 4, a later slice), combat,
the deeper bands' mechanics (Drowned flooding, Magma heat — their
hazard flags are modelled in S5's recombination table but not yet
simulated), co-op, and children/generations. S2 added the colony
(multiple delvers, jobs, morale, camp farming, recruitment); S3
added creatures, combat, lantern-clock strandings, rescue runs, and
permadeath; S5 added the Fungal Reaches: spore sickness, crafted
masks, a herbalist, fungal oil, and oil-burning tier-2 lanterns. No
frame or performance claims exist — nothing has run on owner
hardware.

## Layout

- `sim/` — the Rust simulation core and its tests.
- `docs/MUSE_HANDOFF.md` — design record, slice plan, status.
- `docs/TEST_PLAN.md` — verification plan and results.
- `REQUIREMENTS.md` — project requirements.
- `AGENTS.md` — project rules.
