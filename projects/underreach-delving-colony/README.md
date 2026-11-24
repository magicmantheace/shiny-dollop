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

**Not yet built:** the Crystal Dark's gate items and co-op
itself (its lockstep foundation was built in S13, below).
(The Drowned flooding and Magma heat mechanics were built
in S10, below, and children/generations in S12.) S2
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

**S7 — the Shallows bite back (2026-11-23, branch
`underreach-delving-colony/hazard-mechanics`):** the hazard
pockets S6 generates are live. Mining a face ringed with loose
rock can cave it in — rubble buries the stand, the fall can
down the miner, and the colony digs them out on the rescue
clock; bad air seeps from sealed pockets into the open cells
beside them and gasps anyone working there. The Shallows' gate
set answers both: timber supports and vents, placed kit at a
goods apiece. Verified headless (`cargo test` 43/43, the
`scenario` binary's protected/unprotected contrast); the Godot
frontend did not render the new pieces yet — surfaced in S11,
below.

**S8 — floor-to-floor traversal (2026-11-24, branch
`underreach-delving-colony/traversal`):** the descent is a
transition now. The colony can `descend` / `ascend` between
generated floors: each visited floor's local state (world,
lanterns, faces, supports, vents, plots, beds, stockpile,
gate, critters, lit depths) is packed into the save and
restored exactly on return, while delvers, stores, and the
Deep Ledger travel with the colony. A first arrival founds a
forward camp at the new floor's entry camp; a floor left
behind is frozen, its lanterns unburned on return. First
light is per floor, so lighting floor 2's depths is ledgered
fresh. Verified headless (`cargo test` 51/51, the `scenario`
binary's S8 section runs the loop on floor 2 and finds floor
1 intact on return); floors 2–5 remain stub themes with no
band mechanics or balance yet.

**S9 — floors 2–5 scenarios and balance (2026-11-24, branch
`underreach-delving-colony/band-scenarios`):** a colony can now
be founded directly on any generated floor
(`build_scenario_gen_floor`), and each band floor — Fungal
Reaches, Drowned Galleries, Crystal Dark, Magma Roots — has a
scenario run on the demo seed: founded, opened, and run for
6,000 ticks, every band produced (goods 9 / 15 / 9 / 6), ended
fed, and lost nobody, so the balance pass tuned nothing — all
four bands are playable exactly as the S6 stub themes
generated them. One finding matters more than the numbers:
the Fungal Reaches' spore mechanics do **not** engage on the
generated floor, because spore exposure is keyed to depth
(y ≥ 10) while generated floors hold their carved space at
y ≤ 9 — and generated faces yield ore only, so fungal oil
never flows there either. Since a band's `built` flag demands
that its existing mechanics demonstrably engage on its
generated floor, **no band flips to built in this slice**: the
Fungal Reaches wait on band-keyed exposure, the Drowned
Galleries and Magma Roots on their S10 flooding/heat
mechanics, and the Crystal Dark on gate items that have never
been modelled. Verified headless (`cargo test` 60/60, every
S1–S8 scenario section unchanged in numbers and hash).

**S10 — deeper band hazards (2026-11-24, branch
`underreach-delving-colony/band-hazards`):** hazard exposure
is now keyed to the active floor's band on generated floors
(`hazards_here`: the band's flags rule in the floor's deep
zone, y ≥ 6, while the camp at y = 3 stays refuge; hand-built
worlds keep the depth table exactly), and the two flag-only
hazards are live mechanics. In the Drowned Galleries, flood
water loads a delver toward drowning and douses unsealed
lanterns; the answers are placed **pumps** (1 goods, a dry
reach around them) and **sealed pressure lanterns** (tier 3).
In the Magma Roots, heat loads a delver toward overheating;
the answer is crafted **cooling gear** (2 goods, worn like a
mask). The ordinary colony runs show it: unprotected floor 3
takes 3 drowning events and 3 doused lanterns, floor 5 takes
2 overheating events, and the protected runs — pumps +
pressure lanterns, cooling gear — produce exactly as much
with zero band events and nobody lost. With each band's
mechanics demonstrably engaging on its generated floor, the
Fungal Reaches, Drowned Galleries, and Magma Roots flip to
`built`; the Crystal Dark stays unbuilt, its gate items
still unmodelled. Verified headless (`cargo test` 70/70,
every S1–S9 scenario section unchanged in behaviour
numbers).

**S11 — Godot frontend surfacing (2026-11-24, branch
`underreach-delving-colony/frontend-surfacing`):** everything
S7/S8/S10 left sim-side only is now in the frontend, closing
those slices' frontend-not-rendered caveats. Placed supports,
vents, and pumps render as placeholder markers (distinct
colours per kind; no catalog GLBs exist for them), flooded
cells get a blue-tinted overlay in the depth-slice view, and
each delver's panel line and name label show their air /
water / heat loads verbatim with suffering flagged in text
(`[GASPING]`, `[DROWNING]`, `[OVERHEATING]`, `[SICK]`) plus
masked/cooled state. The HUD shows the current floor and its
band, with Descend/Ascend controls (buttons or PgDn/PgUp),
new Support/Vent/Pump placement tools, and a cooling-gear
crafting button — all sending the existing bridge commands;
no sim rules moved into the frontend (the bridge view gained
only two additive presentation fields, the band name and the
sim's own suffering booleans). The headless verify gains a
third PASS line proving the frontend's synced counts match
the bridge view exactly, the floor indicator follows a
descend, and a Drowned floor's flooded overlay matches the
view cell-for-cell on the checked layer. Verified headless
(`cargo test` 70/70 and every scenario number unchanged);
**the rendered appearance of all S11 surfacing is
unverified** — headless proves load and logic only, and a
visual pass awaits the owner's PC.

**S12 — children & generations (2026-11-24, branch
`underreach-delving-colony/generations`):** the colony's
second growth source from the design record — children
growing up — is live, behind an opt-in `generations_enabled`
flag in the same pattern as S3's critters opt-in. Delvers
now carry an age (a year is 2,400 ticks, one recruitment
cycle; founders and recruits arrive at 25, adults at 18).
In a generations colony, a child is born on the recruitment
cadence when two adults live, food meets the recruitment
minimum, and the colony is under its population cap — the
Deep Ledger records the birth by name, child and both
parents. Children live the camp life but cannot be assigned
work, gain no job XP, and are never sent on rescues; at 18
a `CameOfAge` entry marks them an ordinary delver who can
be assigned and earn XP like anyone else. With the flag off
— every pre-existing scenario — the sim is bit-identical to
before, state hash included, which a pinned test proves.
The scenario binary's new S12 section runs the full arc in
7,000 ticks: two births, one coming of age, the grown child
working as a miner (388 mining XP), 964 goods produced, and
nobody lost. Verified headless (`cargo test` 80/80, every
S1–S11 scenario section unchanged in numbers and hash);
the bridge view carries each delver's age and child state,
but the frontend does not render them yet.

**S13 — co-op foundations (2026-11-24, branch
`underreach-delving-colony/coop-foundations`):** the
lockstep foundation for the 1–4 co-op is built — and co-op
itself is not. The sim was already deterministic and
command-driven; S13 adds the missing pieces as a library
layer: a typed `Command` enum mirroring the bridge's
player-action vocabulary (applying through the same `Sim`
methods the bridge calls), an attributed session log (the
founding save plus `{tick, player, seq, command, applied}`
entries, players numbered 1–4), a canonical merge that
orders per-player streams by `(tick, player, seq)` —
independent of arrival order, with duplicate sequence
numbers and gaps surfaced as errors — and replay: any
session reconstructs from its log to the identical SHA-256
state hash, which is the desync check two future peers will
compare. The scenario binary's S13 section runs a two-player
session on generated Floor 1 (one player lights the way, the
other plants, supports, and vents), produces goods, loses
nobody, and replays to a matching hash. **Not built, because
none of it is headless-verifiable:** network transport and
host/join, session discovery, lockstep pacing under real
latency, Godot multiplayer, desync recovery over a live
connection, and play with real clients on real machines.
The full assessment, the open owner design questions
(frontier rights, multi-rescuer rescues, player downing),
and the recommended first real-machine step are in
[`docs/COOP_ASSESSMENT.md`](docs/COOP_ASSESSMENT.md).
Verified headless (`cargo test` 87/87, every S1–S12
scenario section unchanged in numbers and hash).

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
- `docs/COOP_ASSESSMENT.md` — the S13 co-op assessment (what
  the lockstep foundation proves, what co-op still needs, the
  open owner design questions, the first real-machine step).
- `REQUIREMENTS.md` — project requirements.
- `AGENTS.md` — project rules.
