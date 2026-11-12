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

**Not yet built:** the deeper bands' mechanics (Drowned flooding,
Magma heat — their hazard flags are modelled in S5's recombination
table but not yet simulated), co-op, and children/generations. S2
added the colony (multiple delvers, jobs, morale, camp farming,
recruitment); S3 added creatures, combat, lantern-clock strandings,
rescue runs, and permadeath; S5 added the Fungal Reaches: spore
sickness, crafted masks, a herbalist, fungal oil, and oil-burning
tier-2 lanterns; S4 added the Godot 4 frontend over the sim core.
On 2026-11-11 the frontend's delver visual became the builder's
dedicated delver asset (arm-separation-gated build), with the
builder's lantern and cot props swapped in as well — verified
headless for load and logic; the rendered appearance is still
unverified, pending an on-PC visual pass. No frame or performance
claims exist — nothing has run on owner hardware.

**S6 — procedural floor generation (2026-11-12, branch
`underreach-delving-colony/floor-generation`):** each floor is
generated as a pure function of the colony's unified world seed
and the floor index, driven by a per-band theme table — a natural
passage network with monster dens and the stairs down on it,
embedded ore veins, hazard pockets, and dressing anchors. Floor 1
(the Shallows) is designed and verified end-to-end (the colony
loop runs on it through the bridge's `gen` scenario); the other
four bands are explicit NOT-BUILT stubs that generate through the
same code. Design record: `docs/FLOOR_GENERATION.md`.

## Layout

- `sim/` — the Rust simulation core, its tests, the `scenario`
  demo binary, and the `bridge` binary the frontend speaks to.
- `frontend/` — the Godot 4 frontend (S4): a depth-slice view over
  the core, driven entirely through the bridge. See
  `frontend/README.md` for controls, verification, and asset
  provenance.
- `docs/MUSE_HANDOFF.md` — design record, slice plan, status.
- `docs/TEST_PLAN.md` — verification plan and results.
- `docs/FLOOR_GENERATION.md` — the S6 floor-generation design
  record (seed scheme, theme table, Floor 1 numbers, placeholder
  mapping).
- `REQUIREMENTS.md` — project requirements.
- `AGENTS.md` — project rules.
