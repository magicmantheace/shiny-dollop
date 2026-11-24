# The Crystal Dark — band mechanics (S16)

Design and implementation record for slice S16, built
2026-11-24 on branch
`underreach-delving-colony/crystal-dark-gates`. The Crystal
Dark was the last unbuilt band: S9 gave it a scenario and a
balance pass, S10 built band-keyed exposure for the other
bands, and the owner's 2026-11-24 ruling ("Crystal Dark gate
mechanics: DECIDED as a future slice — approved in
principle") named this work. S16 implements it. The full
design record is owner decision 9 in
`docs/MUSE_HANDOFF.md`; the test record is the S16 section
of `docs/TEST_PLAN.md`.

## Band position

The Crystal Dark is the **fourth band**: floors map 1
Shallows, 2 Fungal Reaches, 3 Drowned Galleries, **4 Crystal
Dark**, 5 Magma Roots, and below the Magma Roots the bands
recombine in cycle (floors 8, 12, … are Crystal Dark again —
`band_for_floor` in `sim/src/gen.rs`). Its theme row now has
`built: true`, like every other band's.

Everything in this slice is **band-scoped**, in the S10
pattern: a mechanic engages only on a generated floor whose
band is the Crystal Dark, and only in the floor's **deep
zone** — carved cells at y ≥ `BAND_ZONE_FROM_Y` (6), the same
line S10 uses for band exposure and generation uses for
bad-air pooling. The camp at y = 3 stays refuge. Hand-built
worlds (no generated floor) and the other four bands are
untouched; the non-leak tests in `scenario_s16.rs` pin that
for darkness, detection, and brittleness alike. The one band
query is `Sim::crystal_dark_here` / `Sim::thick_dark_at`,
alongside `hazards_here`.

## The darkness model

The band had no distinct darkness model before this slice —
light was the global lantern system (radius by tier, carved
cells only). S16 adds the minimal band model on top of it,
in `Sim::refresh_light`:

- In the deep zone of a Crystal Dark floor, a lantern below
  the crystal tier sheds light at `tier_radius −
  DARK_RADIUS_PENALTY` (penalty 2): a tier-1 oil lantern's
  radius 3 becomes 1 there, a tier-3 pressure lantern's 5
  becomes 3. The dark drinks the outer ring of a plain flame.
  Shallows cells of the same floor are lit at full radius.
- The answer is owner decision 8's **crystal-heart lantern**
  — lantern **tier 4** (`CRYSTAL_TIER`), which already had
  radius 5 and the slowest burn in the tier table. A tier-4
  lantern is **fitted with a ground crystal lens** at
  placement: `place_lantern` consumes 1 lens from the stores
  (plus the existing tier-2+ oil charge) and fails whole —
  nothing placed, no oil drawn — when the colony has no
  lens. Fitted, its focused light keeps the full radius in
  the thick dark, so first light can be planted in the deep
  zone where a plain lantern falls short (the scenario
  contrast is test-proven at Chebyshev distance 2 from a
  deep face stand).

## Gate kit

| Item | Kind | Cost | Answers |
|---|---|---|---|
| Crystal lens | lantern fitting, consumed at tier-4 placement | 1 lens + 1 oil charge (the tier-2+ rule) | thicker darkness |
| Quiet gear | worn kit (the mask pattern: permanent, auto-equipped at camp) | 1 cut crystal + 1 goods, via `craft_quiet_gear` | sound hunters |
| Rope (per cell) | placed kit (the support pattern), via `place_rope` | 1 goods | brittle floors |

**Quiet gear and sound hunters.** On a Crystal Dark floor,
critters hunt by sound: in `tick_critters`, a critter engages
its nearest delver only if it can *hear* them — Manhattan
distance ≤ `SOUND_HUNTER_RANGE` (16), where a delver wearing
quiet gear counts `QUIET_NOISE` (4) steps farther away. Past
earshot the hunter idles in the dark. Off the band, critters
hunt exactly as before (nearest delver, any distance), quiet
gear or not. The test contrast stages a lone deep lurker 13–16
steps from a delver: unquiet, it closes; quiet, it never
moves; the same quiet staging on floor 5 still gets hunted.

**Marked routes over brittle floors.** A carved deep-zone
cell on a Crystal Dark floor is brittle (`Sim::brittle_at`):
a delver whose path step lands on it unroped brings it down
— the cell fills with fallen crystal rubble (ordinary
`Cell::Stone`), the path is interrupted, the fall is
ledgered (`LedgerKind::BrittleCollapse`), and the delver
takes `BRITTLE_DAMAGE` (35). Rope laid on the cell first
(`place_rope`, 1 goods, carved cells only, no stacking)
makes that cell permanently safe to cross: a marked route
is a chain of roped cells across the brittle floor.

## Production jobs

Raw crystal is the band's own resource, and it is minable —
the fungal nodes' known gap (embedded pockets, no faces) is
deliberately not repeated:

- **Generation**: the Crystal Dark theme gains crystal as
  its second resource. The generator converts the **deepest
  registered face** of a Crystal Dark floor into a crystal
  face (its vein's cells become `Cell::Crystal`, its yield
  `YieldKind::Crystal`) and embeds 4 crystal clusters in the
  rock, placed last so no other layout element moves. Mining
  and hauling work exactly as for ore; a crystal load
  deposits into `Stores.crystal`.
- **Crystal cutting** — colony job `Job::CrystalCutter`. At
  camp the cutter works in the converter's pattern
  (`DelverState::Cutting`, the same 0.1-progress pace): 1 raw
  crystal → 1 cut crystal (`Stores.cut_crystals`), ledgered
  as `Crafted`.
- **Lens grinding** — colony job `Job::LensGrinder`, same
  pattern (`DelverState::Grinding`): 1 cut crystal → 1 lens
  (`Stores.lenses`).
- **Outputs feed the gate kit**: lenses fit crystal-heart
  lanterns; cut crystals also feed the quiet-gear recipe
  (1 cut crystal + 1 goods). The band's product answers both
  its darkness and its hunters.

All S16 store fields (`crystal`, `cut_crystals`, `lenses`,
`quiet_gear`), the delver's `quiet` flag, and the floor's
`ropes` omit themselves from the canonical save at their
inert defaults, so a colony that never touches the Crystal
Dark hashes bit-identically to the pre-S16 sim.

## Assumptions made (the record was silent)

1. **Darkness as radius loss.** Decision 9 says only
   "thicker darkness" and decision 8 gives the crystal-heart
   lantern "focused light for the Crystal Dark". S16 reads
   those together as: plain light loses radius in the band's
   deep zone, focused (lens-fitted) light does not. The
   penalty (2) and the deep-zone footprint (S10's y ≥ 6 line)
   are this slice's numbers.
2. **A brittle fall never downs by itself.** Damage floors
   the delver's hp at 1 — they scramble clear, wounded, and
   lose their route. The rescue clock stays the province of
   cave-ins, combat, loads, and the dark, as in every earlier
   slice; a brittle-specific downing rule would need an owner
   decision.
3. **Sound hunting is whole-floor, not deep-zone-only.**
   Darkness and brittleness are deep-zone (they are properties
   of place); hearing is a property of the hunter, and the
   band's hunters lair in its dens across the floor. The
   range (16) is set so every den-to-colony distance on the
   demo floor stays inside it — free-running colony behaviour
   on floor 4 is unchanged (verified by the scenario diff).
4. **Harnesses and cartography are not modelled.**
   Decision 9's gate list also names harnesses and its job
   list cartography. Harnesses answer falls, and this sim has
   no fall/cliff traversal to answer; cartography has no
   map/reveal system to feed. Both are recorded as open, not
   silently dropped.

## Not built in this slice

- Frontend/bridge surfacing for ropes, quiet gear, crystal
  stores, and the new jobs (the S7/S10 pattern: sim first,
  surfacing follows as its own slice).
- Harnesses and cartography (above).
- Face registration for embedded pockets generally — the
  crystal clusters are embedded data like the fungal nodes;
  only the converted crystal *face* is minable.
