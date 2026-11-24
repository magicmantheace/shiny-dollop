//! Simulation core: lanterns and light, pathing through the lit
//! network, the Deep Ledger, and canonical save/load with a state
//! hash. S2 grows the S1 single-delver loop into a colony: multiple
//! delvers with jobs (miner / hauler / farmer), morale, camp food
//! production, and surface recruitment. S7 adds the Shallows'
//! hazards: cave-ins at loose faces and bad air beside sealed
//! pockets, answered by timber supports and vents. S10 keys
//! hazard exposure to the active floor's band on generated
//! floors (`hazards_here`) and makes the Drowned flooding and
//! Magma heat hazards live, answered by pumps, sealed pressure
//! lanterns (tier 3), and crafted cooling gear. S12 adds children
//! and generations (owner decision 5) behind the opt-in
//! `generations_enabled` flag, in the `critters_enabled` pattern:
//! with the flag off, age is inert recorded data, no birth or
//! coming-of-age ever fires, and the sim is bit-identical to the
//! pre-S12 sim (the new save fields omit themselves at their
//! inert defaults — see the S12 section below).
//!
//! The design rules encoded here (owner decisions, see
//! docs/MUSE_HANDOFF.md):
//! - Delvers path **only** through lit, carved cells. The lantern
//!   network is the navigation graph.
//! - Placing light records **first light** per depth in the Ledger.
//! - Lantern fuel burns; a dead lantern's light goes with it (the seed
//!   of the rescue clock).
//! - Food is produced at camp by farmers tending mushroom plots;
//!   miners fill a cache at the face, haulers run it home.
//! - Recruitment arrives from the surface on a schedule while the
//!   colony looks viable (food in stores), named by the seeded RNG.

use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet, VecDeque};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::gen::{band_for_floor, generate_floor, theme_for_floor, FloorInfo, CAMP_CENTRE, ENTRY, GATE};
use crate::world::{Cell, Pos, World};

// ---------------------------------------------------------------------------
// Lanterns & light
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Debug, Serialize, Deserialize)]
pub struct LanternEntry {
    pub pos: Pos,
    pub tier: u8,
    pub fuel: f32,
}

/// Light radius by lantern tier (torches → oil → fungal → pressure →
/// crystal → thermal, per the adopted lantern progression).
pub fn tier_radius(tier: u8) -> i32 {
    match tier {
        0 => 2,
        1 => 3,
        2 => 4,
        _ => 5,
    }
}

/// Fuel burned per tick by tier.
pub fn tier_burn(tier: u8) -> f32 {
    match tier {
        0 => 0.05,
        1 => 0.02,
        2 => 0.015,
        _ => 0.01,
    }
}

/// Compute the lit set: carved cells within radius of a fueled lantern.
/// Light does not exist inside solid rock.
pub fn compute_lit(world: &World, lanterns: &[LanternEntry]) -> Vec<bool> {
    let mut lit = vec![false; world.volume()];
    for e in lanterns {
        if e.fuel <= 0.0 {
            continue;
        }
        let r = tier_radius(e.tier);
        for dy in -r..=r {
            for dx in -r..=r {
                for dz in -r..=r {
                    let p = Pos::new(e.pos.x + dx, e.pos.y + dy, e.pos.z + dz);
                    if let Some(i) = world.idx(p) {
                        if world.get(p) == Some(Cell::Carved) {
                            lit[i] = true;
                        }
                    }
                }
            }
        }
    }
    lit
}

// ---------------------------------------------------------------------------
// Pathing — BFS over lit, carved cells only
// ---------------------------------------------------------------------------

pub fn find_path(world: &World, lit: &[bool], from: Pos, to: Pos) -> Option<Vec<Pos>> {
    if from == to {
        return Some(Vec::new());
    }
    let traversable = |p: Pos| -> bool {
        match world.idx(p) {
            Some(i) => world.get(p) == Some(Cell::Carved) && lit[i],
            None => false,
        }
    };
    if !traversable(to) {
        return None;
    }
    let mut prev: HashMap<Pos, Pos> = HashMap::new();
    let mut seen: HashSet<Pos> = HashSet::new();
    let mut queue: VecDeque<Pos> = VecDeque::new();
    seen.insert(from);
    queue.push_back(from);
    while let Some(cur) = queue.pop_front() {
        for n in cur.neighbors6() {
            if seen.contains(&n) || !traversable(n) {
                continue;
            }
            seen.insert(n);
            prev.insert(n, cur);
            if n == to {
                let mut path = vec![n];
                let mut c = n;
                while c != from {
                    c = prev[&c];
                    if c != from {
                        path.push(c);
                    }
                }
                path.reverse();
                return Some(path);
            }
            queue.push_back(n);
        }
    }
    None
}

// ---------------------------------------------------------------------------
// The Deep Ledger
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum LedgerKind {
    ColonyFounded,
    LanternPlaced,
    FirstLight,
    RouteBlocked,
    HaulDelivered,
    Converted,
    LanternOut,
    Harvested,
    RecruitArrived,
    SpiritsFallen,
    CreatureSpotted,
    CreatureSlain,
    DelverDowned,
    DelverRescued,
    DelverLost,
    DelverSick,
    Crafted,
    CaveIn,
    DelverGasping,
    Descended,
    Ascended,
    /// A delver's water load crossed the drowning threshold (S10).
    DelverDrowning,
    /// A delver's heat load crossed the overheating threshold (S10).
    DelverOverheating,
    /// An unsealed lantern was doused by flood water (S10).
    LanternDoused,
    /// A child was born in the colony (S12, generations only).
    ChildBorn,
    /// A child reached adulthood (S12, generations only).
    CameOfAge,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct LedgerEntry {
    pub tick: u64,
    pub kind: LedgerKind,
    pub detail: String,
}

// ---------------------------------------------------------------------------
// Jobs, faces, plots
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Job {
    Unassigned,
    Miner,
    Hauler,
    Farmer,
    /// Tends the sick (spore care in S5); farms when nobody is ill.
    Herbalist,
}

/// What a face yields when mined.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum YieldKind {
    Ore,
    FungalOil,
}

/// A work face: the rock cell being worked, the carved cell the
/// delver stands on, the units still in the rock, and the mined
/// cache waiting at the face for a hauler.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Face {
    pub rock: Pos,
    pub stand: Pos,
    pub ore: u32,
    pub cache: u32,
    pub yield_kind: YieldKind,
}

/// A camp mushroom plot. Growth runs 0..10; at 10 it is ready to
/// harvest. Plots grow slowly untended and fast under a farmer.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Plot {
    pub pos: Pos,
    pub growth: f32,
}

pub const PLOT_READY: f32 = 10.0;
pub const PLOT_PASSIVE_GROWTH: f32 = 0.002;
pub const PLOT_YIELD: u32 = 2;

// ---------------------------------------------------------------------------
// Depth bands & hazards (S5)
// ---------------------------------------------------------------------------

/// The hazard flags a depth can carry. S5 wires `spores` to real
/// mechanics; `flooded` and `hot` are the Drowned / Magma hazards,
/// present in the data model now so deeper bands compose from the
/// same table instead of new code.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default, Serialize, Deserialize)]
pub struct Hazards {
    pub spores: bool,
    pub flooded: bool,
    pub hot: bool,
}

/// The Fungal Reaches begin at this depth.
pub const FUNGAL_FROM: i32 = 10;
/// Thickness of one recombined band below the Fungal Reaches.
pub const DEEP_BAND_SPAN: i32 = 8;

/// Hazards by depth. The Shallows are clean; the Fungal Reaches are
/// spore-bearing; deeper still, the bands **recombine** — the hazard
/// sets cycle through unions of the parent bands' flags, which is
/// what makes depth endless without new mechanics per band.
pub fn hazards_at(y: i32) -> Hazards {
    if y < FUNGAL_FROM {
        return Hazards::default();
    }
    let idx = (y - FUNGAL_FROM) / DEEP_BAND_SPAN;
    match idx % 4 {
        0 => Hazards {
            spores: true,
            flooded: false,
            hot: false,
        },
        1 => Hazards {
            spores: true,
            flooded: true,
            hot: false,
        },
        2 => Hazards {
            spores: true,
            flooded: false,
            hot: true,
        },
        _ => Hazards {
            spores: false,
            flooded: true,
            hot: true,
        },
    }
}

/// Spore exposure per tick in a spore band, unmasked vs masked.
/// A mask protects its wearer entirely (the S5 record's words):
/// the masked rate is zero — S10 corrects the 0.05 leak S5
/// shipped, which no S5 assertion ever depended on (its mask
/// test asserts no sickness, which holds either way).
pub const SPORE_RATE_UNMASKED: f32 = 0.6;
pub const SPORE_RATE_MASKED: f32 = 0.0;
/// Spore load at which a delver is sick (the spore-cough).
pub const SICK_AT: f32 = 60.0;
/// Spore load clears this fast in clean air, plus herbalist care.
pub const SPORE_CLEAR_RATE: f32 = 0.15;
pub const HERBALIST_CARE_RATE: f32 = 0.85;
/// Goods cost of one crafted spore mask.
pub const MASK_GOODS_COST: u32 = 2;
/// Fungal oil a tier-2+ lantern placement (or refuel) draws: one
/// charge of oil per lantern, flat — oil is the fuel, the lantern
/// is the lantern, however long the scenario says it burns.
pub const LANTERN_OIL_COST: u32 = 1;

// ---------------------------------------------------------------------------
// Shallows hazards — cave-ins & bad air (S7)
// ---------------------------------------------------------------------------
//
// The Shallows' own gate set (owner decision 9): cave-ins and bad
// air, answered by timber supports and ventilation. S6's floor
// generator already embeds the pockets — `Cell::Loose` rock in
// the walls, `Cell::BadAir` pooled deep — as data; this slice
// gives them mechanics, the way S5 gave spores mechanics over
// its `hazards_at` table.

/// Bad-air load gained per tick spent breathing a gassy cell
/// (a carved cell touching a `Cell::BadAir` pocket, unvented).
/// Worse per tick than ambient spores — a pocket's seep is
/// concentrated — but it only bites where the pocket touches
/// open space, so passing through costs little and lingering
/// at a gassy face is what gasps a delver.
pub const AIR_RATE: f32 = 1.0;
/// Air load at which a delver is gasping: work halved and morale
/// hit, like the spore-cough.
pub const GASPING_AT: f32 = 60.0;
/// Air load clears this fast in clean air.
pub const AIR_CLEAR_RATE: f32 = 0.25;
/// Air load clear rate within a vent's reach — moving air is the
/// cure, as a herbalist's care is for spores.
pub const VENT_CLEAR_RATE: f32 = 1.25;
/// A vent keeps carved cells within this Chebyshev radius
/// ventilated: no bad air gathers there.
pub const VENT_RADIUS: i32 = 2;
/// Goods cost of one placed vent (a crafted kit piece).
pub const VENT_GOODS_COST: u32 = 1;
/// Goods cost of one placed timber support (a crafted kit piece).
pub const SUPPORT_GOODS_COST: u32 = 1;
/// Cave-in chance per mined unit, per mille, for each loose cell
/// neighbouring the face (rock or stand) — 2% apiece. A supported
/// face never rolls.
pub const CAVE_IN_PER_MILLE_PER_LOOSE: u64 = 20;
/// Damage a cave-in deals to the delver working the face. Enough
/// to down a hurt delver (and start the rescue clock), not to
/// kill a healthy one outright.
pub const CAVE_IN_DAMAGE: f32 = 55.0;

// ---------------------------------------------------------------------------
// Band-keyed exposure & the deeper bands (S10)
// ---------------------------------------------------------------------------
//
// The S9 finding: on generated floors, depth-keyed exposure
// never engages — a generated floor holds all its carved space
// at y ≤ 9 (GEN_MAX_Y), above the Fungal line at y = 10. S10
// keys exposure to the floor instead, designed once for all
// bands (the `hazards_here` query on `Sim`):
//
// - On a generated floor (`Sim.floor` is Some), the active
//   floor's band flags — `theme_for_floor(index).hazards` —
//   decide WHICH hazards a cell can carry. Depth-keyed
//   `hazards_at` is not consulted there, so nothing
//   double-applies.
// - The band's hazards fill the floor's **deep zone**: carved
//   cells at y ≥ `BAND_ZONE_FROM_Y`. That is the same depth
//   line the generator already uses (bad air pools only at
//   y ≥ 6; the entry camp sits at y = 3), and it mirrors the
//   hand-built world, where the camp is clean air above the
//   Fungal line and the hazard lives in the deep workings.
//   The camp stays a refuge on every band floor; the faces,
//   which generation places deep, are where the band bites.
// - Hand-built worlds (`floor` is None) keep the depth-keyed
//   `hazards_at(y)` behaviour exactly, at every depth.
//
// Flooding (the Drowned Galleries' hazard, owner decision 9:
// flooding, drowning, lantern failure) is a delver **water
// load** in the spore/air pattern, plus lantern failure: an
// unsealed lantern standing in flood water is doused. The
// answers are decision 9's gate items in the established kit
// patterns: a **pump** (placed kit, the vent's mirror — carved
// cells within its reach are dry) and the **sealed pressure
// lantern** (lantern tier 3, the progression's waterproof
// tier from decision 8; placement follows the existing tier
// rules, so it draws the tier-2+ oil charge). Air bells and
// drains were not modelled: the pump's dry reach already
// gives delvers refuge cells and a workable face, so a second
// water answer would duplicate it, not complete it.
//
// Heat (the Magma Roots' hazard) is a delver **heat load** in
// the same pattern. The answer is **cooling gear**: worn
// crafted kit, the mask's mirror (goods cost, permanent once
// equipped, auto-equipped at camp). A placed heat answer was
// not modelled: decision 9's list leads with cooling gear,
// and worn kit travels with the delver through the whole hot
// zone, where a placed piece would strand the same transit
// problem the pump solves for water only at fixed points.

/// On a generated floor, the band's hazards fill carved cells
/// at this depth and below — the floor's deep zone (the same
/// line generation uses for bad-air pooling).
pub const BAND_ZONE_FROM_Y: i32 = 6;
/// Water load gained per tick standing in flood water
/// (a flooded-band deep-zone cell no pump keeps dry).
pub const WATER_RATE: f32 = 1.0;
/// Water load at which a delver is drowning: work halved and
/// morale hit, like the spore-cough and gasping.
pub const DROWNING_AT: f32 = 60.0;
/// Water load clears this fast in dry air.
pub const WATER_CLEAR_RATE: f32 = 0.25;
/// Water load clear rate within a pump's reach — a pumped
/// cell is bailed dry, as a vented cell is aired.
pub const PUMP_CLEAR_RATE: f32 = 1.25;
/// A pump keeps carved cells within this Chebyshev radius dry.
pub const PUMP_RADIUS: i32 = 2;
/// Goods cost of one placed pump (a crafted kit piece).
pub const PUMP_GOODS_COST: u32 = 1;
/// The sealed pressure lantern tier (decision 8): the only
/// tier that keeps burning in flood water. Lower tiers are
/// unsealed and are doused there.
pub const PRESSURE_TIER: u8 = 3;
/// Extra fuel per tick an unsealed lantern loses to flood
/// water it stands in — on top of its tier burn. A 5,000-fuel
/// route lantern is doused in ~2,475 ticks.
pub const DOUSE_RATE: f32 = 2.0;
/// Heat load gained per tick standing in a hot band's deep
/// zone, without cooling gear. Cooling gear prevents the
/// gain entirely (a sealed suit, like a mask for spores).
pub const HEAT_RATE: f32 = 1.0;
/// Heat load at which a delver is overheating: work halved
/// and morale hit, like the other threshold loads.
pub const OVERHEATING_AT: f32 = 60.0;
/// Heat load clears this fast in cool areas.
pub const HEAT_CLEAR_RATE: f32 = 0.25;
/// Goods cost of one crafted set of cooling gear.
pub const COOLING_GOODS_COST: u32 = 2;

// ---------------------------------------------------------------------------
// Children & generations (S12)
// ---------------------------------------------------------------------------
//
// Owner decision 5: delvers are full-ASKA people, and colony
// growth comes from surface recruitment **and children growing
// up**. The system is opt-in per scenario, in the
// `critters_enabled` precedent (S3): `Sim::generations_enabled`
// defaults to false, every pre-existing scenario leaves it off,
// and with it off the sim is **bit-identical** to the pre-S12
// sim — no RNG draws, no Ledger entries, no behaviour change,
// and no state-hash movement. That inertness is engineered, not
// hoped for:
//
// - `generations_enabled` omits itself from the canonical save
//   while false (`skip_serializing_if`), and `Delver::age_ticks`
//   omits itself while it holds the founding adult age. A field
//   omitted at its serde default loads back as exactly that
//   default, so the omission is roundtrip-safe at any value.
// - Age advances only while the system is enabled, so a disabled
//   sim's ages never leave the omitted default. (Modelling
//   decision where the record was silent: with the system off,
//   age is inert recorded data — the founding age — exactly as
//   the slice spec's inertness clause requires.)
//
// Modelling decisions where the record was silent (all flagged
// in docs/TEST_PLAN.md and docs/MUSE_HANDOFF.md):
//
// - `TICKS_PER_YEAR` = 2400: one year is one surface-recruitment
//   cycle (`RECRUIT_INTERVAL`), the colony's existing calendar
//   beat. Founders and recruits are founded at 25 years
//   (`FOUNDER_AGE_YEARS`, the serde default above); adulthood is
//   18 (`ADULT_AGE_YEARS`).
// - Births are checked on the recruitment family's cadence
//   (`BIRTH_INTERVAL` = `RECRUIT_INTERVAL`, on tick multiples)
//   and are **deterministic, with no probability roll**: a birth
//   fires at a check when at least two adults live, food in
//   stores is at or above `BIRTH_MIN_FOOD` (which reuses
//   `RECRUIT_MIN_FOOD` — a colony that looks viable to a recruit
//   can feed a child), and total population is below
//   `MAX_DELVER_POPULATION`. The only RNG draw is the child's
//   name, drawn exactly as recruitment draws one, and only when
//   a birth actually fires in an enabled sim.
// - Parents are the two longest-present adults — the two lowest
//   delver ids among the living adults (ids are issued in
//   arrival order and never reused). The Ledger names the child
//   and both parents (decision 2's spirit: the record is by
//   name).
// - The child's name comes from the recruitment name pool
//   (`RECRUIT_NAMES`) not currently in use. Fallback if the pool
//   is exhausted: no birth at that check (the recruitment
//   pattern) — unreachable in practice while the population cap
//   (6) sits below the pool size (12), but stated so the rule is
//   total.
// - Childhood scoping: a child lives the camp life of an
//   Unassigned delver — eats, rests, morale — but the job
//   decision never dispatches them to work, job assignment
//   refuses them, and they are never picked as a rescuer. No
//   school, childcare, or carrying system is modelled; children
//   at camp are in the lit safe zone by construction.

/// Ticks in one year of a delver's life (S12): one surface
/// recruitment cycle, the colony's existing calendar beat.
pub const TICKS_PER_YEAR: u64 = 2400;
/// A delver is an adult at this many years (S12).
pub const ADULT_AGE_YEARS: u64 = 18;
/// The age founders and surface recruits are founded at (S12).
pub const FOUNDER_AGE_YEARS: u64 = 25;
/// Births are checked on this cadence (S12) — the recruitment
/// interval, the periodic-check idiom of the growth family.
pub const BIRTH_INTERVAL: u64 = RECRUIT_INTERVAL;
/// Food in stores a birth requires (S12): the recruitment
/// minimum, reused — a colony viable to a recruit can feed a
/// child.
pub const BIRTH_MIN_FOOD: u32 = RECRUIT_MIN_FOOD;

/// The founding adult age in ticks — the serde default for
/// `Delver::age_ticks`, so pre-S12 saves load as adults.
fn default_age_ticks() -> u64 {
    FOUNDER_AGE_YEARS * TICKS_PER_YEAR
}

/// A field holding the founding age omits itself from the
/// canonical save (see the S12 note above): pre-S12 state
/// hashes are bit-identical, and the omission roundtrips
/// because the default *is* the omitted value.
fn age_is_default(age: &u64) -> bool {
    *age == default_age_ticks()
}

/// A false flag omits itself from the canonical save, the
/// `generations_enabled` mirror of `age_is_default`.
fn flag_is_false(flag: &bool) -> bool {
    !*flag
}

// ---------------------------------------------------------------------------
// Delver
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum DelverState {
    Idle,
    ToFace,
    Mining,
    ToCamp,
    Converting,
    ToBed,
    Resting,
    Eating,
    Blocked,
    ToPlot,
    Tending,
    /// Incapacitated (hp spent). The rescue clock is running.
    Downed,
    /// Heading to a downed delver to carry them home.
    ToRescue,
    /// Carrying a downed delver back to camp (half speed).
    Rescuing,
    /// Herbalist heading to a sick delver.
    ToPatient,
    /// Herbalist tending a patient within reach.
    Care,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Delver {
    pub id: u32,
    pub name: String,
    pub pos: Pos,
    /// Age in ticks (S12). Founders and recruits are founded at
    /// the adult default; children are born at 0. Advances only
    /// while the colony's generations system is enabled, and
    /// omits itself from the save at the founding default (see
    /// the S12 section note) so disabled sims hash identically
    /// to pre-S12 sims. Pre-S12 saves load at the default.
    #[serde(default = "default_age_ticks", skip_serializing_if = "age_is_default")]
    pub age_ticks: u64,
    /// 0..100 — spent by work, restored by rest.
    pub energy: f32,
    /// 0..100 — 100 is fully fed; restored by eating from stores.
    pub hunger: f32,
    /// 0..100 — drifts toward a target set by how fed and rested the
    /// delver is (plus a small colony-prosperity term); scales work.
    pub morale: f32,
    pub mining_xp: u32,
    pub hauling_xp: u32,
    pub farming_xp: u32,
    pub carrying: u32,
    /// What the carried units are (a load is homogeneous).
    pub carrying_kind: YieldKind,
    pub carrying_food: u32,
    /// Spore load 0..100 (S5). Sick at `SICK_AT`; at 100 it eats hp.
    pub spore: f32,
    /// Wearing a crafted spore mask (permanent kit once equipped).
    pub masked: bool,
    pub sick_logged: bool,
    /// Bad-air load 0..100 (S7). Gasping at `GASPING_AT`; at 100
    /// it eats hp, like a full spore load.
    pub air: f32,
    pub gasping_logged: bool,
    /// Water load 0..100 (S10). Drowning at `DROWNING_AT`; at
    /// 100 it eats hp, like a full spore or air load.
    pub water: f32,
    pub drowning_logged: bool,
    /// Heat load 0..100 (S10). Overheating at `OVERHEATING_AT`;
    /// at 100 it eats hp, like the other loads.
    pub heat: f32,
    pub overheating_logged: bool,
    /// Wearing crafted cooling gear (permanent kit once
    /// equipped, the mask's mirror for heat).
    pub cooled: bool,
    /// 0..100 — spent in combat and accidents; a delver at 0 is
    /// Downed, not dead: the rescue clock decides which.
    pub hp: f32,
    pub combat_xp: u32,
    pub fight_cd: u32,
    /// Ticks of survival left while downed or cut off in the dark.
    /// `None` while safe.
    pub dark_clock: Option<u32>,
    /// The delver id this delver is rescuing, if any.
    pub rescue_target: Option<u32>,
    pub job: Job,
    pub state: DelverState,
    pub path: Vec<Pos>,
    pub mine_progress: f32,
    pub convert_progress: f32,
    pub target_face: Option<usize>,
    pub target_plot: Option<usize>,
    pub blocked_logged: bool,
    pub low_morale_logged: bool,
}

impl Delver {
    pub fn new(id: u32, name: &str, pos: Pos, job: Job) -> Self {
        Self {
            id,
            name: name.to_string(),
            pos,
            age_ticks: default_age_ticks(),
            energy: 100.0,
            hunger: 100.0,
            morale: 60.0,
            mining_xp: 0,
            hauling_xp: 0,
            farming_xp: 0,
            carrying: 0,
            carrying_kind: YieldKind::Ore,
            carrying_food: 0,
            spore: 0.0,
            masked: false,
            sick_logged: false,
            air: 0.0,
            gasping_logged: false,
            water: 0.0,
            drowning_logged: false,
            heat: 0.0,
            overheating_logged: false,
            cooled: false,
            hp: 100.0,
            combat_xp: 0,
            fight_cd: 0,
            dark_clock: None,
            rescue_target: None,
            job,
            state: DelverState::Idle,
            path: Vec::new(),
            mine_progress: 0.0,
            convert_progress: 0.0,
            target_face: None,
            target_plot: None,
            blocked_logged: false,
            low_morale_logged: false,
        }
    }

    /// Whole years of age (S12): `age_ticks` by integer
    /// division, so a delver is 17 until the tick their age
    /// crosses the 18-year line.
    pub fn age_years(&self) -> u64 {
        self.age_ticks / TICKS_PER_YEAR
    }
    /// Under the adult line by age alone (S12). Whether a young
    /// delver is a *child* in play also needs the colony's
    /// generations flag — see `Sim::delver_is_child`.
    pub fn is_child(&self) -> bool {
        self.age_years() < ADULT_AGE_YEARS
    }
    pub fn mining_level(&self) -> u32 {
        self.mining_xp / 10
    }
    pub fn farming_level(&self) -> u32 {
        self.farming_xp / 10
    }
    pub fn capacity(&self) -> u32 {
        4
    }
    pub fn sick(&self) -> bool {
        self.spore >= SICK_AT
    }
    pub fn gasping(&self) -> bool {
        self.air >= GASPING_AT
    }
    pub fn drowning(&self) -> bool {
        self.water >= DROWNING_AT
    }
    pub fn overheating(&self) -> bool {
        self.heat >= OVERHEATING_AT
    }
    /// Any threshold load is biting: the delver works halved
    /// and seeks a bed until it clears.
    pub fn suffering(&self) -> bool {
        self.sick() || self.gasping() || self.drowning() || self.overheating()
    }
    /// Morale scales all work rates: a miserable delver works at
    /// 0.6x, a thriving one at 1.2x. Sickness halves it again —
    /// and so does gasping for air, drowning, or overheating.
    pub fn work_mult(&self) -> f32 {
        let base = 0.6 + 0.6 * (self.morale / 100.0);
        if self.suffering() {
            base * 0.5
        } else {
            base
        }
    }
}

#[derive(Clone, Copy, Default, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct Stores {
    pub ore: u32,
    pub goods: u32,
    pub food: u32,
    /// Rendered from fungal nodes; fuels tier-2+ lanterns (S5).
    pub fungal_oil: u32,
    /// Crafted spore masks waiting to be equipped (S5).
    pub masks: u32,
    /// Crafted cooling gear waiting to be equipped (S10).
    #[serde(default)]
    pub cooling_gear: u32,
}

// ---------------------------------------------------------------------------
// Seeded RNG (xorshift64*) — the only randomness in the sim, and its
// state lives in the save, per the determinism rule.
// ---------------------------------------------------------------------------

pub struct Rng {
    pub state: u64,
}

impl Rng {
    pub fn next_u64(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.state = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }
    pub fn below(&mut self, n: u64) -> u64 {
        self.next_u64() % n
    }
}

// ---------------------------------------------------------------------------
// Critters — what lives in the dark (S3)
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum CritterKind {
    GloamRat,
    DeepLurker,
}

impl CritterKind {
    pub fn max_hp(&self) -> f32 {
        match self {
            CritterKind::GloamRat => 20.0,
            CritterKind::DeepLurker => 45.0,
        }
    }
    pub fn damage(&self) -> f32 {
        match self {
            CritterKind::GloamRat => 4.0,
            CritterKind::DeepLurker => 8.0,
        }
    }
    /// Food the colony renders from the carcass.
    pub fn food_value(&self) -> u32 {
        match self {
            CritterKind::GloamRat => 1,
            CritterKind::DeepLurker => 2,
        }
    }
    pub fn label(&self) -> &'static str {
        match self {
            CritterKind::GloamRat => "gloam rat",
            CritterKind::DeepLurker => "deep lurker",
        }
    }
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Critter {
    pub id: u32,
    pub kind: CritterKind,
    pub pos: Pos,
    pub hp: f32,
    pub move_cd: u32,
    pub attack_cd: u32,
    pub spotted: bool,
}

pub const CRITTER_SPAWN_INTERVAL: u64 = 700;
pub const CRITTER_CAP: usize = 4;
pub const CRITTER_MIN_DEPTH: i32 = 5;
pub const ATTACK_PERIOD: u32 = 6;
pub const LIGHT_DAMAGE: f32 = 1.5;
/// Ticks a downed delver's emergency light lasts — the rescue clock.
pub const DOWNED_CLOCK: u32 = 900;
/// Ticks a delver cut off in total darkness can last.
pub const DARK_CLOCK: u32 = 600;

pub const RECRUIT_NAMES: &[&str] = &[
    "Wren", "Tomas", "Ines", "Pell", "Odile", "Sanna", "Yuri", "Bea", "Alba", "Fenn", "Maren",
    "Silas",
];
pub const MAX_DELVER_POPULATION: usize = 6;
pub const RECRUIT_INTERVAL: u64 = 2400;
pub const RECRUIT_MIN_FOOD: u32 = 4;

// ---------------------------------------------------------------------------
// Sim
// ---------------------------------------------------------------------------

/// Per-floor stored state (S8): everything floor-local, packed
/// away when the colony travels to another floor and unpacked
/// exactly on return. A floor left behind is frozen — its
/// lanterns do not burn while the colony is away. Global state
/// (delvers, stores, ledger, tick, RNG, world seed, arrival
/// schedule, the active floor's `FloorInfo`) never packs; it
/// lives on `Sim` itself.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct FloorState {
    pub world: World,
    pub lanterns: Vec<LanternEntry>,
    pub faces: Vec<Face>,
    pub supports: Vec<Pos>,
    pub vents: Vec<Pos>,
    #[serde(default)]
    pub pumps: Vec<Pos>,
    pub plots: Vec<Plot>,
    pub beds: Vec<Pos>,
    pub stockpile: Pos,
    pub gate: Pos,
    pub critters: Vec<Critter>,
    pub lit_depths: BTreeSet<i32>,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Sim {
    pub world: World,
    /// Kept sorted by position so serialization is canonical.
    pub lanterns: Vec<LanternEntry>,
    /// Kept in id order (arrivals append).
    pub delvers: Vec<Delver>,
    pub stockpile: Pos,
    pub beds: Vec<Pos>,
    /// Kept sorted by rock position.
    pub faces: Vec<Face>,
    /// Placed timber supports (S7): a face whose stand cell is a
    /// support's cell or touches one cannot cave in. Sorted.
    pub supports: Vec<Pos>,
    /// Placed vents (S7): carved cells within `VENT_RADIUS` are
    /// ventilated — bad air neither gathers nor lingers there.
    /// Sorted.
    pub vents: Vec<Pos>,
    /// Placed pumps (S10): carved cells within `PUMP_RADIUS`
    /// are kept dry in a flooded band. Sorted.
    #[serde(default)]
    pub pumps: Vec<Pos>,
    /// Kept sorted by position.
    pub plots: Vec<Plot>,
    /// Where surface arrivals appear.
    pub gate: Pos,
    pub stores: Stores,
    pub ledger: Vec<LedgerEntry>,
    pub lit_depths: BTreeSet<i32>,
    pub tick_count: u64,
    /// The colony's unified world seed (S6): every floor's
    /// layout is a pure function of this seed and the floor
    /// index (see `crate::gen`). Recorded at founding from the
    /// construction seed; generation never draws on the runtime
    /// RNG below. Saves from before S6 load with 0 (unset).
    #[serde(default)]
    pub world_seed: u64,
    /// The generated floor this colony is playing on, if it was
    /// founded on one (S6). Hand-built scenarios leave it `None`.
    #[serde(default)]
    pub floor: Option<FloorInfo>,
    /// Stored state of visited floors the colony is not
    /// currently on (S8), keyed by floor index in canonical
    /// (BTree) order. The active floor's state stays in the
    /// fields above and swaps in/out of this map on travel.
    #[serde(default)]
    pub floors: BTreeMap<u32, FloorState>,
    pub rng_state: u64,
    pub next_arrival: u64,
    pub next_delver_id: u32,
    /// Kept in id order (spawns append).
    pub critters: Vec<Critter>,
    pub next_critter_id: u32,
    /// Scenarios from before the dark bit (S1/S2) keep critters off;
    /// S3 turns them on.
    pub critters_enabled: bool,
    /// Children & generations (S12), opt-in in the
    /// `critters_enabled` pattern: scenarios before S12 leave it
    /// off, and off is bit-identical to the pre-S12 sim — the
    /// flag omits itself from the save while false, age never
    /// advances, and no birth or coming-of-age ever fires.
    #[serde(default, skip_serializing_if = "flag_is_false")]
    pub generations_enabled: bool,
    #[serde(skip)]
    pub lit: Vec<bool>,
}

impl Sim {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        world: World,
        delvers: Vec<Delver>,
        stockpile: Pos,
        beds: Vec<Pos>,
        faces: Vec<Face>,
        gate: Pos,
        stores: Stores,
        rng_seed: u64,
        next_arrival: u64,
        critters_enabled: bool,
    ) -> Self {
        let mut faces = faces;
        faces.sort_by_key(|f| f.rock);
        let next_delver_id = delvers.iter().map(|d| d.id).max().map_or(0, |m| m + 1);
        let founder = delvers
            .first()
            .map(|d| d.name.clone())
            .unwrap_or_else(|| "No one".to_string());
        let mut sim = Self {
            world,
            lanterns: Vec::new(),
            delvers,
            stockpile,
            beds,
            faces,
            supports: Vec::new(),
            vents: Vec::new(),
            pumps: Vec::new(),
            plots: Vec::new(),
            gate,
            stores,
            ledger: Vec::new(),
            lit_depths: BTreeSet::new(),
            tick_count: 0,
            world_seed: rng_seed,
            floor: None,
            floors: BTreeMap::new(),
            rng_state: if rng_seed == 0 { 0x9E37_79B9_7F4A_7C15 } else { rng_seed },
            next_arrival,
            next_delver_id,
            critters: Vec::new(),
            next_critter_id: 0,
            critters_enabled,
            generations_enabled: false,
            lit: Vec::new(),
        };
        sim.refresh_light();
        sim.log(
            LedgerKind::ColonyFounded,
            format!("{founder} takes the lantern down"),
        );
        sim
    }

    fn log(&mut self, kind: LedgerKind, detail: String) {
        self.ledger.push(LedgerEntry {
            tick: self.tick_count,
            kind,
            detail,
        });
    }

    pub fn refresh_light(&mut self) {
        self.lit = compute_lit(&self.world, &self.lanterns);
    }

    fn depth_is_lit(&self, y: i32) -> bool {
        for x in 0..self.world.sx as i32 {
            for z in 0..self.world.sz as i32 {
                if let Some(i) = self.world.idx(Pos::new(x, y, z)) {
                    if self.lit[i] {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// After a change that can extend light, record first light for
    /// any depth that has never been lit before.
    fn note_new_lit_depths(&mut self) {
        let mut fresh: Vec<i32> = Vec::new();
        for y in 0..self.world.sy as i32 {
            if !self.lit_depths.contains(&y) && self.depth_is_lit(y) {
                fresh.push(y);
            }
        }
        for d in fresh {
            self.lit_depths.insert(d);
            self.log(LedgerKind::FirstLight, format!("first light at depth {d}"));
        }
    }

    // -- Player (frontier) actions -------------------------------------------

    /// Carve a cell (the player carries their own light; carving is
    /// not restricted by the network).
    pub fn carve(&mut self, p: Pos) -> Option<Cell> {
        let prev = self.world.carve(p)?;
        self.refresh_light();
        self.note_new_lit_depths();
        Some(prev)
    }

    /// Place (or refuel/replace) a lantern and extend the network.
    /// Tier-2+ lanterns burn fungal oil: placement draws
    /// `LANTERN_OIL_COST` oil from the stores and fails (returns
    /// false, nothing placed) when the colony has none — the Fungal
    /// Reaches' own product is what lights them.
    pub fn place_lantern(&mut self, pos: Pos, tier: u8, fuel: f32) -> bool {
        if tier >= 2 {
            if self.stores.fungal_oil < LANTERN_OIL_COST {
                return false;
            }
            self.stores.fungal_oil -= LANTERN_OIL_COST;
        }
        if let Some(e) = self.lanterns.iter_mut().find(|e| e.pos == pos) {
            e.tier = tier;
            e.fuel = fuel;
        } else {
            self.lanterns.push(LanternEntry { pos, tier, fuel });
            self.lanterns.sort_by_key(|e| e.pos);
        }
        self.log(
            LedgerKind::LanternPlaced,
            format!("tier {tier} lantern at ({}, {}, {})", pos.x, pos.y, pos.z),
        );
        self.refresh_light();
        self.note_new_lit_depths();
        true
    }

    /// Set a timber support on a carved cell (the Shallows gate
    /// set's cave-in answer, S7). A face whose stand cell is the
    /// support's cell or touches it cannot cave in. Costs
    /// `SUPPORT_GOODS_COST` goods — a crafted kit piece, like a
    /// mask — and fails (returns false, nothing placed, nothing
    /// charged) without the goods, on solid rock, or where a
    /// support already stands.
    pub fn place_support(&mut self, pos: Pos) -> bool {
        if self.world.get(pos) != Some(Cell::Carved)
            || self.supports.contains(&pos)
            || self.stores.goods < SUPPORT_GOODS_COST
        {
            return false;
        }
        self.stores.goods -= SUPPORT_GOODS_COST;
        self.supports.push(pos);
        self.supports.sort();
        self.log(
            LedgerKind::Crafted,
            format!(
                "a timber support was set at ({}, {}, {})",
                pos.x, pos.y, pos.z
            ),
        );
        true
    }

    /// Rig a vent on a carved cell (the Shallows gate set's
    /// bad-air answer, S7). Carved cells within `VENT_RADIUS`
    /// are ventilated. Costs `VENT_GOODS_COST` goods and fails
    /// like `place_support` does.
    pub fn place_vent(&mut self, pos: Pos) -> bool {
        if self.world.get(pos) != Some(Cell::Carved)
            || self.vents.contains(&pos)
            || self.stores.goods < VENT_GOODS_COST
        {
            return false;
        }
        self.stores.goods -= VENT_GOODS_COST;
        self.vents.push(pos);
        self.vents.sort();
        self.log(
            LedgerKind::Crafted,
            format!("a vent was rigged at ({}, {}, {})", pos.x, pos.y, pos.z),
        );
        true
    }

    /// Is this cell within a vent's reach?
    fn ventilated(&self, p: Pos) -> bool {
        self.vents.iter().any(|v| {
            (v.x - p.x)
                .abs()
                .max((v.y - p.y).abs())
                .max((v.z - p.z).abs())
                <= VENT_RADIUS
        })
    }

    /// Set a pump on a carved cell (the Drowned gate set's
    /// first answer, S10). Carved cells within `PUMP_RADIUS`
    /// are kept dry. Costs `PUMP_GOODS_COST` goods and fails
    /// like `place_support` does.
    pub fn place_pump(&mut self, pos: Pos) -> bool {
        if self.world.get(pos) != Some(Cell::Carved)
            || self.pumps.contains(&pos)
            || self.stores.goods < PUMP_GOODS_COST
        {
            return false;
        }
        self.stores.goods -= PUMP_GOODS_COST;
        self.pumps.push(pos);
        self.pumps.sort();
        self.log(
            LedgerKind::Crafted,
            format!("a pump was set at ({}, {}, {})", pos.x, pos.y, pos.z),
        );
        true
    }

    /// Is this cell within a pump's reach (kept dry)?
    fn pumped(&self, p: Pos) -> bool {
        self.pumps.iter().any(|v| {
            (v.x - p.x)
                .abs()
                .max((v.y - p.y).abs())
                .max((v.z - p.z).abs())
                <= PUMP_RADIUS
        })
    }

    /// The hazards a cell exposes a delver to (S10) — the one
    /// query all exposure code consults. On a generated floor
    /// the active floor's band flags rule, applied in the
    /// floor's deep zone (y ≥ `BAND_ZONE_FROM_Y`); the camp
    /// shallows of the floor are clean. On a hand-built world
    /// the depth-keyed `hazards_at` table rules, exactly as
    /// before S10. The two never combine: no double-apply.
    pub fn hazards_here(&self, pos: Pos) -> Hazards {
        match &self.floor {
            Some(f) => {
                if pos.y >= BAND_ZONE_FROM_Y {
                    theme_for_floor(f.index).hazards
                } else {
                    Hazards::default()
                }
            }
            None => hazards_at(pos.y),
        }
    }

    /// Flood water stands in this cell: the band is flooded,
    /// the cell is in the flooded zone, and no pump keeps it
    /// dry. (On a hand-built world the depth table's flooded
    /// flag rules and pumps still bail their reach.)
    pub fn flooded_at(&self, p: Pos) -> bool {
        self.world.get(p) == Some(Cell::Carved)
            && self.hazards_here(p).flooded
            && !self.pumped(p)
    }

    /// Bad air gathers in a carved cell that touches a bad-air
    /// pocket — unless a vent reaches it. (A pocket carved open
    /// is spent: its gas is gone with the rock. Pockets the
    /// colony leaves sealed keep seeping into the adjoining
    /// open space until they are carved out or vented around.)
    fn bad_air_at(&self, p: Pos) -> bool {
        if self.world.get(p) != Some(Cell::Carved) || self.ventilated(p) {
            return false;
        }
        p.neighbors6()
            .iter()
            .any(|n| self.world.get(*n) == Some(Cell::BadAir))
    }

    /// The loose cells neighbouring a face — around its rock and
    /// around the delver's stand — in a fixed scan order, so a
    /// collapse is deterministic.
    fn loose_neighbours(&self, face: &Face) -> Vec<Pos> {
        let mut out: Vec<Pos> = Vec::new();
        for c in face
            .rock
            .neighbors6()
            .iter()
            .chain(face.stand.neighbors6().iter())
        {
            if self.world.get(*c) == Some(Cell::Loose) && !out.contains(c) {
                out.push(*c);
            }
        }
        out
    }

    /// A supported face never caves in: the support stands on the
    /// face's stand cell or touches it.
    fn face_supported(&self, face: &Face) -> bool {
        self.supports
            .iter()
            .any(|s| *s == face.stand || face.stand.neighbors6().contains(s))
    }

    /// Roll for a cave-in at the face delver `idx` is mining —
    /// called per unit mined. Draws on the sim RNG only when
    /// loose rock actually neighbours the face and no support
    /// holds it, so colonies working sound rock never draw.
    /// On a collapse the loose cell is spent (ordinary stone
    /// behind it), the stand cell fills with fallen rock, and
    /// the delver working there takes `CAVE_IN_DAMAGE` — which
    /// can down them and start the rescue clock. Returns true
    /// when a cave-in fired.
    fn maybe_cave_in(&mut self, idx: usize, fi: usize) -> bool {
        let face = self.faces[fi].clone();
        if self.face_supported(&face) {
            return false;
        }
        let loose = self.loose_neighbours(&face);
        if loose.is_empty() {
            return false;
        }
        let mut rng = Rng {
            state: self.rng_state,
        };
        let roll = rng.below(1000);
        self.rng_state = rng.state;
        if roll >= loose.len() as u64 * CAVE_IN_PER_MILLE_PER_LOOSE {
            return false;
        }
        self.world.set(loose[0], Cell::Stone);
        self.world.set(face.stand, Cell::Stone);
        self.refresh_light();
        let name = self.delvers[idx].name.clone();
        self.log(
            LedgerKind::CaveIn,
            format!("a cave-in at the face — {name} was caught in the fall"),
        );
        self.delvers[idx].hp -= CAVE_IN_DAMAGE;
        if self.delvers[idx].hp <= 0.0 {
            self.down_delver(idx);
        }
        true
    }

    /// Craft a spore mask from colony goods (the Fungal gate set's
    /// first item). Delvers equip masks automatically at camp.
    pub fn craft_mask(&mut self) -> bool {
        if self.stores.goods < MASK_GOODS_COST {
            return false;
        }
        self.stores.goods -= MASK_GOODS_COST;
        self.stores.masks += 1;
        self.log(
            LedgerKind::Crafted,
            format!("a spore mask was crafted from {MASK_GOODS_COST} goods"),
        );
        true
    }

    /// Craft cooling gear from colony goods (the Magma gate
    /// set's first item, S10 — the mask's mirror). Delvers
    /// equip it automatically at camp.
    pub fn craft_cooling_gear(&mut self) -> bool {
        if self.stores.goods < COOLING_GOODS_COST {
            return false;
        }
        self.stores.goods -= COOLING_GOODS_COST;
        self.stores.cooling_gear += 1;
        self.log(
            LedgerKind::Crafted,
            format!("cooling gear was crafted from {COOLING_GOODS_COST} goods"),
        );
        true
    }

    /// Is this delver a child in play (S12)? A child is a young
    /// delver in a colony whose generations system is enabled;
    /// with the system off, age gates nothing.
    pub fn delver_is_child(&self, d: &Delver) -> bool {
        self.generations_enabled && d.is_child()
    }

    /// Assign a delver's job. Takes effect at their next decision.
    /// Returns false — leaving the delver's job untouched — when
    /// no such delver exists, or when the delver is a child in a
    /// generations colony and the job is real work (S12:
    /// children cannot be assigned; assigning `Unassigned` is
    /// always allowed). The refusal's visible signal in the
    /// bridge view is that the delver simply stays `Unassigned`.
    pub fn set_job(&mut self, delver_id: u32, job: Job) -> bool {
        if job != Job::Unassigned {
            match self.delvers.iter().find(|d| d.id == delver_id) {
                Some(d) if self.delver_is_child(d) => return false,
                Some(_) => {}
                None => return false,
            }
        }
        if let Some(d) = self.delvers.iter_mut().find(|d| d.id == delver_id) {
            d.job = job;
            d.state = DelverState::Idle;
            d.path.clear();
            d.target_face = None;
            d.target_plot = None;
            true
        } else {
            false
        }
    }

    /// Designate a carved camp cell as a mushroom plot.
    pub fn plant_plot(&mut self, pos: Pos) {
        if self.world.get(pos) != Some(Cell::Carved) {
            return;
        }
        if self.plots.iter().any(|p| p.pos == pos) {
            return;
        }
        self.plots.push(Plot { pos, growth: 0.0 });
        self.plots.sort_by_key(|p| p.pos);
    }

    // -- Floor-to-floor traversal (S8) ---------------------------------------
    //
    // Modelling decisions where the design record was silent
    // (recorded in docs/TEST_PLAN.md and docs/MUSE_HANDOFF.md):
    // - Whole-colony immediate transition: every delver travels
    //   together; there is no per-delver cross-floor pathing.
    // - A floor left behind is frozen: its lanterns do not burn
    //   fuel while the colony is away (its state is packed, not
    //   ticked).
    // - On first arrival a forward camp is founded at the new
    //   floor's entry camp, mirroring `build_scenario_gen`'s
    //   founding (delvers at the entry camp, beds + stockpile
    //   there, the generated floor's registered faces, gate at
    //   the entry camp, a camp lantern, one resident critter
    //   per den) — except that farming plots do not carry down:
    //   a fresh floor starts with no plots.

    /// Snapshot the active floor's floor-local state.
    fn pack_floor(&self) -> FloorState {
        FloorState {
            world: self.world.clone(),
            lanterns: self.lanterns.clone(),
            faces: self.faces.clone(),
            supports: self.supports.clone(),
            vents: self.vents.clone(),
            pumps: self.pumps.clone(),
            plots: self.plots.clone(),
            beds: self.beds.clone(),
            stockpile: self.stockpile,
            gate: self.gate,
            critters: self.critters.clone(),
            lit_depths: self.lit_depths.clone(),
        }
    }

    /// Make a stored floor state the active floor.
    fn unpack_floor(&mut self, state: FloorState) {
        self.world = state.world;
        self.lanterns = state.lanterns;
        self.faces = state.faces;
        self.supports = state.supports;
        self.vents = state.vents;
        self.pumps = state.pumps;
        self.plots = state.plots;
        self.beds = state.beds;
        self.stockpile = state.stockpile;
        self.gate = state.gate;
        self.critters = state.critters;
        self.lit_depths = state.lit_depths;
        self.refresh_light();
    }

    /// Reset every delver to a fresh decision at `positions`
    /// (cycled through when there are more delvers than spots):
    /// travel interrupts whatever step they were on, and face /
    /// plot indices from another floor mean nothing here.
    fn gather_delvers(&mut self, positions: &[Pos]) {
        if positions.is_empty() {
            return;
        }
        for (i, d) in self.delvers.iter_mut().enumerate() {
            d.pos = positions[i % positions.len()];
            if d.state != DelverState::Downed {
                d.state = DelverState::Idle;
            }
            d.path.clear();
            d.target_face = None;
            d.target_plot = None;
            d.mine_progress = 0.0;
            d.convert_progress = 0.0;
            d.rescue_target = None;
            d.blocked_logged = false;
        }
    }

    /// Camp cells delvers gather at on arrival on a floor, in
    /// founding order (the generated entry camp chamber).
    fn entry_camp_positions() -> Vec<Pos> {
        vec![
            ENTRY,
            Pos::new(4, 3, 5),
            Pos::new(4, 3, 3),
            Pos::new(5, 3, 4),
            GATE,
            Pos::new(2, 3, 4),
        ]
    }

    /// Found a forward camp on a freshly generated floor: the
    /// `build_scenario_gen` founding, minus the plots.
    fn found_forward_camp(&mut self, floor: crate::gen::Floor) {
        let info = floor.info();
        let dens: Vec<(Pos, CritterKind)> = floor
            .layout
            .cavities
            .iter()
            .filter(|c| c.den)
            .map(|c| (c.centre, c.critter.unwrap_or(CritterKind::GloamRat)))
            .collect();
        self.world = floor.world;
        self.lanterns = Vec::new();
        self.faces = floor.layout.faces.clone();
        self.supports = Vec::new();
        self.vents = Vec::new();
        self.pumps = Vec::new();
        self.plots = Vec::new();
        self.beds = vec![Pos::new(2, 3, 3), Pos::new(2, 3, 5), Pos::new(6, 3, 5)];
        self.stockpile = ENTRY;
        self.gate = GATE;
        self.critters = Vec::new();
        self.lit_depths = BTreeSet::new();
        self.floor = Some(info);
        self.refresh_light();
        // The camp lantern is pipe-fed for scenario purposes,
        // exactly as at the founding on floor 1.
        self.place_lantern(CAMP_CENTRE, 1, 1_000_000.0);
        for (pos, kind) in dens {
            self.spawn_critter(kind, pos);
        }
    }

    /// Take the stairs down to the next floor. Refuses (false,
    /// no state change) when the colony is not on a generated
    /// floor. Generation of a never-visited floor is a pure
    /// function of `(world_seed, floor_index)` and never draws
    /// on the runtime RNG.
    pub fn descend(&mut self) -> bool {
        let Some(cur) = self.floor.clone() else {
            return false;
        };
        let target = cur.index + 1;
        let packed = self.pack_floor();
        self.floors.insert(cur.index, packed);
        if let Some(state) = self.floors.remove(&target) {
            self.unpack_floor(state);
            self.floor = Some(generate_floor(self.world_seed, target).info());
        } else {
            let floor = generate_floor(self.world_seed, target);
            self.found_forward_camp(floor);
        }
        self.gather_delvers(&Self::entry_camp_positions());
        self.log(
            LedgerKind::Descended,
            format!(
                "the colony descended to floor {} ({:?})",
                target,
                band_for_floor(target)
            ),
        );
        true
    }

    /// Climb back to the floor above. Refuses (false, no state
    /// change) on floor 1, off a generated floor, or when the
    /// floor above was never visited (no stored state). The
    /// colony arrives at the floor above's descent cell — they
    /// climb back up the stairs they came down.
    pub fn ascend(&mut self) -> bool {
        let Some(cur) = self.floor.clone() else {
            return false;
        };
        if cur.index <= 1 {
            return false;
        }
        let target = cur.index - 1;
        if !self.floors.contains_key(&target) {
            return false;
        }
        let packed = self.pack_floor();
        self.floors.insert(cur.index, packed);
        let state = self.floors.remove(&target).expect("checked above");
        self.unpack_floor(state);
        let info = generate_floor(self.world_seed, target).info();
        let descent = info.descent;
        self.floor = Some(info);
        self.gather_delvers(&[descent]);
        self.log(
            LedgerKind::Ascended,
            format!(
                "the colony ascended to floor {} ({:?})",
                target,
                band_for_floor(target)
            ),
        );
        true
    }

    // -- Save / load ------------------------------------------------------------

    pub fn save_json(&self) -> String {
        serde_json::to_string(self).expect("sim serialization is infallible")
    }

    pub fn load_json(s: &str) -> Self {
        let mut sim: Sim = serde_json::from_str(s).expect("save JSON parses");
        sim.refresh_light();
        sim
    }

    pub fn state_hash(&self) -> String {
        let mut h = Sha256::new();
        h.update(self.save_json().as_bytes());
        format!("{:x}", h.finalize())
    }

    // -- Recruitment --------------------------------------------------------------

    fn maybe_recruit(&mut self) {
        if self.tick_count < self.next_arrival {
            return;
        }
        self.next_arrival += RECRUIT_INTERVAL;
        if self.delvers.len() >= MAX_DELVER_POPULATION {
            return;
        }
        if self.stores.food < RECRUIT_MIN_FOOD {
            return;
        }
        let mut rng = Rng {
            state: self.rng_state,
        };
        let taken: Vec<&str> = self.delvers.iter().map(|d| d.name.as_str()).collect();
        let free: Vec<&&str> = RECRUIT_NAMES.iter().filter(|n| !taken.contains(n)).collect();
        if free.is_empty() {
            self.rng_state = rng.state;
            return;
        }
        let name = free[rng.below(free.len() as u64) as usize].to_string();
        self.rng_state = rng.state;
        // Fill the colony's gaps first: miner, then farmer, then hauler.
        let has = |j: Job| self.delvers.iter().any(|d| d.job == j);
        let job = if !has(Job::Miner) {
            Job::Miner
        } else if !has(Job::Farmer) {
            Job::Farmer
        } else if !has(Job::Hauler) {
            Job::Hauler
        } else {
            Job::Miner
        };
        let id = self.next_delver_id;
        self.next_delver_id += 1;
        let mut d = Delver::new(id, &name, self.gate, job);
        d.energy = 90.0;
        d.hunger = 80.0;
        self.delvers.push(d);
        self.log(
            LedgerKind::RecruitArrived,
            format!("{name} arrived from the surface and takes up work as a {:?}", job),
        );
    }

    // -- Generations (S12) ----------------------------------------------------

    /// Advance every living delver's age by one tick and ledger
    /// any coming of age — the tick a delver's age crosses the
    /// 18-year line, exactly once (age is monotonic, so the
    /// crossing can fire only once). Called only in generations
    /// colonies; with the system off age never advances and no
    /// entry is ever written.
    fn age_delvers(&mut self) {
        let mut came_of_age: Vec<String> = Vec::new();
        for d in self.delvers.iter_mut() {
            let was = d.age_years();
            d.age_ticks += 1;
            if was < ADULT_AGE_YEARS && d.age_years() >= ADULT_AGE_YEARS {
                came_of_age.push(d.name.clone());
            }
        }
        for name in came_of_age {
            self.log(
                LedgerKind::CameOfAge,
                format!("{name} has come of age and takes up work as an adult"),
            );
        }
    }

    /// The birth check (S12): on the recruitment cadence, a child
    /// is born when the colony can support one — at least two
    /// adults alive, food at or above `BIRTH_MIN_FOOD`, and total
    /// population below `MAX_DELVER_POPULATION`. Deterministic:
    /// no probability roll; the parents are the two
    /// longest-present adults (lowest ids); the only RNG draw is
    /// the child's name from the pool not currently in use,
    /// exactly as recruitment draws one, and only when a birth
    /// fires. If the name pool is exhausted there is no birth at
    /// this check. Never runs in a disabled sim.
    fn maybe_birth(&mut self) {
        if !self.generations_enabled
            || self.tick_count == 0
            || !self.tick_count.is_multiple_of(BIRTH_INTERVAL)
        {
            return;
        }
        if self.delvers.len() >= MAX_DELVER_POPULATION {
            return;
        }
        if self.stores.food < BIRTH_MIN_FOOD {
            return;
        }
        let mut adults: Vec<&Delver> =
            self.delvers.iter().filter(|d| !d.is_child()).collect();
        if adults.len() < 2 {
            return;
        }
        adults.sort_by_key(|d| d.id);
        let parent_a = adults[0].name.clone();
        let parent_b = adults[1].name.clone();
        let mut rng = Rng {
            state: self.rng_state,
        };
        let taken: Vec<&str> = self.delvers.iter().map(|d| d.name.as_str()).collect();
        let free: Vec<&&str> = RECRUIT_NAMES.iter().filter(|n| !taken.contains(n)).collect();
        if free.is_empty() {
            return;
        }
        let name = free[rng.below(free.len() as u64) as usize].to_string();
        self.rng_state = rng.state;
        let id = self.next_delver_id;
        self.next_delver_id += 1;
        let mut child = Delver::new(id, &name, self.gate, Job::Unassigned);
        child.age_ticks = 0;
        self.delvers.push(child);
        self.log(
            LedgerKind::ChildBorn,
            format!("{name} was born to {parent_a} and {parent_b}"),
        );
    }

    // -- Tick -------------------------------------------------------------------

    pub fn tick(&mut self) {
        // Ages advance (and comings of age are ledgered) only in
        // generations colonies (S12); disabled sims never call it.
        if self.generations_enabled {
            self.age_delvers();
        }
        // Lanterns burn. A lantern that dies takes its light with it.
        // An unsealed lantern standing in flood water is doused
        // (S10): it loses fuel to the water on top of its burn,
        // and its death is ledgered as a dousing, not a burnout.
        // Sealed pressure lanterns (tier `PRESSURE_TIER`) and
        // lanterns a pump keeps dry burn normally.
        let mut burned_out: Vec<(Pos, bool)> = Vec::new();
        let dousing: Vec<bool> = self
            .lanterns
            .iter()
            .map(|e| e.tier < PRESSURE_TIER && self.flooded_at(e.pos))
            .collect();
        for (e, doused) in self.lanterns.iter_mut().zip(dousing) {
            if e.fuel > 0.0 {
                let doused = doused;
                e.fuel -= tier_burn(e.tier);
                if doused {
                    e.fuel -= DOUSE_RATE;
                }
                if e.fuel <= 0.0 {
                    e.fuel = 0.0;
                    burned_out.push((e.pos, doused));
                }
            }
        }
        if !burned_out.is_empty() {
            for (p, doused) in &burned_out {
                if *doused {
                    self.log(
                        LedgerKind::LanternDoused,
                        format!(
                            "an unsealed lantern at ({}, {}, {}) was doused by the flood water",
                            p.x, p.y, p.z
                        ),
                    );
                } else {
                    self.log(
                        LedgerKind::LanternOut,
                        format!("lantern at ({}, {}, {}) burned out", p.x, p.y, p.z),
                    );
                }
            }
            self.refresh_light();
        }
        // Mushroom plots grow a little on their own.
        for p in self.plots.iter_mut() {
            p.growth = (p.growth + PLOT_PASSIVE_GROWTH).min(PLOT_READY);
        }
        self.maybe_recruit();
        self.maybe_birth();
        self.maybe_spawn_critter();
        self.assign_rescues();
        self.tick_critters();
        for idx in 0..self.delvers.len() {
            self.tick_delver(idx);
        }
        self.sweep_danger();
        self.tick_count += 1;
    }

    fn lit_at(&self, p: Pos) -> bool {
        match self.world.idx(p) {
            Some(i) => self.lit.get(i).copied().unwrap_or(false),
            None => false,
        }
    }

    // -- Critters ---------------------------------------------------------------

    /// Spawn a critter at a carved cell (world events and scenario
    /// scripting both use this; auto-spawn picks the cell itself).
    pub fn spawn_critter(&mut self, kind: CritterKind, pos: Pos) -> u32 {
        let id = self.next_critter_id;
        self.next_critter_id += 1;
        self.critters.push(Critter {
            id,
            kind,
            pos,
            hp: kind.max_hp(),
            move_cd: 0,
            attack_cd: 0,
            spotted: false,
        });
        id
    }

    fn maybe_spawn_critter(&mut self) {
        if !self.critters_enabled
            || self.tick_count == 0
            || !self.tick_count.is_multiple_of(CRITTER_SPAWN_INTERVAL)
            || self.critters.len() >= CRITTER_CAP
        {
            return;
        }
        // Candidate cells: carved, unlit, deep enough, touching light.
        let mut cells: Vec<Pos> = Vec::new();
        for y in CRITTER_MIN_DEPTH..self.world.sy as i32 {
            for x in 0..self.world.sx as i32 {
                for z in 0..self.world.sz as i32 {
                    let p = Pos::new(x, y, z);
                    if self.world.get(p) != Some(Cell::Carved) || self.lit_at(p) {
                        continue;
                    }
                    if p.neighbors6().iter().any(|n| self.lit_at(*n)) {
                        cells.push(p);
                    }
                }
            }
        }
        if cells.is_empty() {
            return;
        }
        let mut rng = Rng {
            state: self.rng_state,
        };
        if rng.below(100) >= 65 {
            self.rng_state = rng.state;
            return;
        }
        let pos = cells[rng.below(cells.len() as u64) as usize];
        let kind = if pos.y >= 7 && rng.below(2) == 0 {
            CritterKind::DeepLurker
        } else {
            CritterKind::GloamRat
        };
        self.rng_state = rng.state;
        self.spawn_critter(kind, pos);
    }

    fn kill_critter(&mut self, cid: u32, credit: Option<&str>) {
        let Some(ci) = self.critters.iter().position(|c| c.id == cid) else {
            return;
        };
        let critter = self.critters.remove(ci);
        self.stores.food += critter.kind.food_value();
        let detail = match credit {
            Some(name) => format!(
                "{} slew a {}",
                name,
                critter.kind.label()
            ),
            None => format!("a {} burned away in the light", critter.kind.label()),
        };
        self.log(LedgerKind::CreatureSlain, detail);
    }

    /// BFS over carved cells regardless of light — how critters move.
    fn critter_path(&self, from: Pos, to: Pos) -> Option<Vec<Pos>> {
        if from == to {
            return Some(Vec::new());
        }
        let traversable = |p: Pos| self.world.get(p) == Some(Cell::Carved);
        if !traversable(to) {
            return None;
        }
        let mut prev: HashMap<Pos, Pos> = HashMap::new();
        let mut seen: HashSet<Pos> = HashSet::new();
        let mut queue: VecDeque<Pos> = VecDeque::new();
        seen.insert(from);
        queue.push_back(from);
        while let Some(cur) = queue.pop_front() {
            for n in cur.neighbors6() {
                if seen.contains(&n) || !traversable(n) {
                    continue;
                }
                seen.insert(n);
                prev.insert(n, cur);
                if n == to {
                    let mut path = vec![n];
                    let mut c = n;
                    while c != from {
                        c = prev[&c];
                        if c != from {
                            path.push(c);
                        }
                    }
                    path.reverse();
                    return Some(path);
                }
                queue.push_back(n);
            }
        }
        None
    }

    fn down_delver(&mut self, idx: usize) {
        if self.delvers[idx].state == DelverState::Downed {
            return;
        }
        self.delvers[idx].hp = 0.0;
        self.delvers[idx].state = DelverState::Downed;
        self.delvers[idx].path.clear();
        self.delvers[idx].carrying = 0;
        self.delvers[idx].rescue_target = None;
        self.delvers[idx].dark_clock = Some(DOWNED_CLOCK);
        let name = self.delvers[idx].name.clone();
        let pos = self.delvers[idx].pos;
        self.log(
            LedgerKind::DelverDowned,
            format!(
                "{} is down at ({}, {}, {}) — the rescue clock is running",
                name, pos.x, pos.y, pos.z
            ),
        );
    }

    fn tick_critters(&mut self) {
        let ids: Vec<u32> = self.critters.iter().map(|c| c.id).collect();
        for cid in ids {
            let Some(ci) = self.critters.iter().position(|c| c.id == cid) else {
                continue;
            };
            // Light burns.
            if self.lit_at(self.critters[ci].pos) {
                if !self.critters[ci].spotted {
                    self.critters[ci].spotted = true;
                    let label = self.critters[ci].kind.label();
                    self.log(
                        LedgerKind::CreatureSpotted,
                        format!("a {label} — in the light!"),
                    );
                }
                self.critters[ci].hp -= LIGHT_DAMAGE;
                if self.critters[ci].hp <= 0.0 {
                    self.kill_critter(cid, None);
                    continue;
                }
            }
            if self.critters[ci].attack_cd > 0 {
                self.critters[ci].attack_cd -= 1;
            }
            // Nearest living, non-downed delver.
            let cpos = self.critters[ci].pos;
            let target = self
                .delvers
                .iter()
                .filter(|d| d.state != DelverState::Downed)
                .min_by_key(|d| {
                    (d.pos.x - cpos.x).abs() + (d.pos.y - cpos.y).abs() + (d.pos.z - cpos.z).abs()
                })
                .map(|d| (d.id, d.pos));
            let Some((tid, tpos)) = target else {
                continue;
            };
            let dist = (tpos.x - cpos.x).abs() + (tpos.y - cpos.y).abs() + (tpos.z - cpos.z).abs();
            if dist <= 1 {
                if self.critters[ci].attack_cd == 0 {
                    self.critters[ci].attack_cd = ATTACK_PERIOD;
                    let dmg = self.critters[ci].kind.damage();
                    if let Some(di) = self.delvers.iter().position(|d| d.id == tid) {
                        self.delvers[di].hp -= dmg;
                        if self.delvers[di].hp <= 0.0 {
                            self.down_delver(di);
                        }
                    }
                }
                continue;
            }
            if self.critters[ci].move_cd > 0 {
                self.critters[ci].move_cd -= 1;
                continue;
            }
            self.critters[ci].move_cd = 1; // critters move every other tick
            if let Some(path) = self.critter_path(cpos, tpos) {
                if let Some(next) = path.first().copied() {
                    // Never step onto the delver's own cell.
                    if next != tpos {
                        self.critters[ci].pos = next;
                    }
                }
            }
        }
    }

    // -- Rescue -------------------------------------------------------------------

    /// Path where every intermediate cell must be lit and carved, but
    /// the final cell may be dark — a rescuer's dash to a delver who
    /// is down just past the light's edge.
    fn find_path_dash(&self, from: Pos, to: Pos) -> Option<Vec<Pos>> {
        if self.world.get(to) != Some(Cell::Carved) {
            return None;
        }
        if from == to {
            return Some(Vec::new());
        }
        let intermediate_ok = |p: Pos| -> bool {
            match self.world.idx(p) {
                Some(i) => self.world.get(p) == Some(Cell::Carved) && self.lit[i],
                None => false,
            }
        };
        let mut prev: HashMap<Pos, Pos> = HashMap::new();
        let mut seen: HashSet<Pos> = HashSet::new();
        let mut queue: VecDeque<Pos> = VecDeque::new();
        seen.insert(from);
        queue.push_back(from);
        while let Some(cur) = queue.pop_front() {
            for n in cur.neighbors6() {
                if seen.contains(&n) {
                    continue;
                }
                if n != to && !intermediate_ok(n) {
                    continue;
                }
                seen.insert(n);
                prev.insert(n, cur);
                if n == to {
                    let mut path = vec![n];
                    let mut c = n;
                    while c != from {
                        c = prev[&c];
                        if c != from {
                            path.push(c);
                        }
                    }
                    path.reverse();
                    return Some(path);
                }
                queue.push_back(n);
            }
        }
        None
    }

    fn assign_rescues(&mut self) {
        let downed: Vec<u32> = self
            .delvers
            .iter()
            .filter(|d| d.state == DelverState::Downed)
            .map(|d| d.id)
            .collect();
        for did in downed {
            if self.delvers.iter().any(|d| d.rescue_target == Some(did)) {
                continue;
            }
            let dpos = match self.delvers.iter().find(|d| d.id == did) {
                Some(d) => d.pos,
                None => continue,
            };
            // Nearest able delver: upright, healthy enough, not
            // already on a rescue.
            let candidate = self
                .delvers
                .iter()
                .filter(|d| {
                    d.state != DelverState::Downed
                        && d.hp >= 30.0
                        && d.rescue_target.is_none()
                        // Children (S12) are never sent on rescues.
                        && !self.delver_is_child(d)
                })
                .min_by_key(|d| {
                    (d.pos.x - dpos.x).abs() + (d.pos.y - dpos.y).abs() + (d.pos.z - dpos.z).abs()
                })
                .map(|d| d.id);
            let Some(rid) = candidate else {
                continue;
            };
            let ridx = self.delvers.iter().position(|d| d.id == rid).unwrap();
            let from = self.delvers[ridx].pos;
            // A delver buried by a cave-in (S7) lies in a
            // rubble-filled cell: aim the rescue at the nearest
            // carved neighbour instead — the carry triggers
            // within reach of the downed delver, as it does for
            // a dash into the dark.
            let aim = if self.world.get(dpos) == Some(Cell::Carved) {
                Some(dpos)
            } else {
                dpos.neighbors6()
                    .into_iter()
                    .filter(|n| self.world.get(*n) == Some(Cell::Carved))
                    .min_by_key(|n| {
                        (n.x - from.x).abs() + (n.y - from.y).abs() + (n.z - from.z).abs()
                    })
            };
            let Some(aim) = aim else {
                continue;
            };
            let path = if self.lit_at(aim) {
                find_path(&self.world, &self.lit, from, aim)
            } else {
                self.find_path_dash(from, aim)
            };
            if let Some(path) = path {
                self.delvers[ridx].state = DelverState::ToRescue;
                self.delvers[ridx].rescue_target = Some(did);
                self.delvers[ridx].path = path;
                self.delvers[ridx].target_face = None;
                self.delvers[ridx].target_plot = None;
            }
        }
    }

    /// The danger sweep: clocks run for the downed and for anyone cut
    /// off in total darkness. A clock that reaches zero is a loss,
    /// and the Ledger keeps the name.
    fn sweep_danger(&mut self) {
        let mut lost: Vec<u32> = Vec::new();
        for idx in 0..self.delvers.len() {
            let (id, pos, state, prev_clock) = {
                let d = &self.delvers[idx];
                (d.id, d.pos, d.state, d.dark_clock)
            };
            let in_dark = !self.lit_at(pos);
            let cut_off = in_dark
                && pos != self.stockpile
                && find_path(&self.world, &self.lit, pos, self.stockpile).is_none();
            let downed = state == DelverState::Downed;
            if downed || cut_off {
                let clock = match prev_clock {
                    Some(c) => c.saturating_sub(1),
                    None => {
                        if downed {
                            DOWNED_CLOCK
                        } else {
                            DARK_CLOCK
                        }
                    }
                };
                self.delvers[idx].dark_clock = Some(clock);
                if clock == 0 {
                    lost.push(id);
                }
            } else if !downed {
                self.delvers[idx].dark_clock = None;
            }
        }
        for id in lost {
            if let Some(pos) = self.delvers.iter().position(|d| d.id == id) {
                let name = self.delvers[pos].name.clone();
                self.delvers.remove(pos);
                self.log(
                    LedgerKind::DelverLost,
                    format!("{name} was lost to the dark"),
                );
            }
            for d in self.delvers.iter_mut() {
                if d.rescue_target == Some(id) {
                    d.rescue_target = None;
                    if d.state == DelverState::ToRescue || d.state == DelverState::Rescuing {
                        d.state = DelverState::Idle;
                        d.path.clear();
                    }
                }
            }
        }
    }

    fn start_path(&mut self, idx: usize, to: Pos) -> bool {
        let from = self.delvers[idx].pos;
        match find_path(&self.world, &self.lit, from, to) {
            Some(path) => {
                self.delvers[idx].path = path;
                true
            }
            None => false,
        }
    }

    /// One movement step along the current path. Returns true on arrival.
    fn follow_path(&mut self, idx: usize) -> bool {
        if let Some(next) = self.delvers[idx].path.first().copied() {
            self.delvers[idx].pos = next;
            self.delvers[idx].path.remove(0);
        }
        self.delvers[idx].path.is_empty()
    }

    fn delver_bed(&self, idx: usize) -> Pos {
        if self.beds.is_empty() {
            return self.stockpile;
        }
        self.beds[(self.delvers[idx].id as usize) % self.beds.len()]
    }

    fn has_hauler(&self) -> bool {
        self.delvers.iter().any(|d| d.job == Job::Hauler)
    }

    /// Deposit whatever the delver is carrying into the stores. Ore
    /// converts to goods in pairs (the S1 rule); fungal oil goes to
    /// the oil store as-is.
    fn deposit(&mut self, idx: usize) {
        let amount = self.delvers[idx].carrying;
        if amount > 0 {
            self.delvers[idx].carrying = 0;
            self.delvers[idx].hauling_xp += amount;
            let name = self.delvers[idx].name.clone();
            match self.delvers[idx].carrying_kind {
                YieldKind::Ore => {
                    self.stores.ore += amount;
                    self.log(
                        LedgerKind::HaulDelivered,
                        format!("{name} hauled {amount} ore to the stockpile"),
                    );
                    self.convert_stores();
                }
                YieldKind::FungalOil => {
                    self.stores.fungal_oil += amount;
                    self.log(
                        LedgerKind::HaulDelivered,
                        format!("{name} hauled {amount} fungal oil to the stockpile"),
                    );
                }
            }
        }
        let food = self.delvers[idx].carrying_food;
        if food > 0 {
            self.delvers[idx].carrying_food = 0;
            self.stores.food += food;
        }
    }

    fn convert_stores(&mut self) {
        let pairs = self.stores.ore / 2;
        if pairs > 0 {
            self.stores.ore -= pairs * 2;
            self.stores.goods += pairs;
            self.log(
                LedgerKind::Converted,
                format!("converted {} ore into {pairs} goods", pairs * 2),
            );
        }
    }

    fn go_blocked(&mut self, idx: usize, what: &str) {
        self.delvers[idx].state = DelverState::Blocked;
        if !self.delvers[idx].blocked_logged {
            self.delvers[idx].blocked_logged = true;
            let name = self.delvers[idx].name.clone();
            self.log(
                LedgerKind::RouteBlocked,
                format!("{name} cannot reach {what} — the way is dark"),
            );
        }
    }

    /// The camp decision, made whenever a delver stands at camp with
    /// empty hands and no active job step: eat, rest, or work by job.
    fn decide(&mut self, idx: usize) {
        // Nobody works in the dark. A delver caught out by a light
        // failure cowers and waits for rescue or a relight; the
        // danger sweep runs their clock meanwhile.
        if !self.lit_at(self.delvers[idx].pos) && self.delvers[idx].pos != self.stockpile {
            self.delvers[idx].state = DelverState::Idle;
            return;
        }
        // Pick up a mask if the colony has one spare.
        if !self.delvers[idx].masked && self.stores.masks > 0 {
            self.stores.masks -= 1;
            self.delvers[idx].masked = true;
        }
        // Pick up cooling gear if the colony has a set spare.
        if !self.delvers[idx].cooled && self.stores.cooling_gear > 0 {
            self.stores.cooling_gear -= 1;
            self.delvers[idx].cooled = true;
        }
        if self.delvers[idx].hunger < 40.0 && self.stores.food > 0 {
            self.delvers[idx].state = DelverState::Eating;
            return;
        }
        // The spore-sick, the gasping, the drowning, and the
        // overheated go to bed and stay there until it clears.
        if self.delvers[idx].suffering() {
            let bed = self.delver_bed(idx);
            if self.delvers[idx].pos == bed || self.start_path(idx, bed) {
                self.delvers[idx].state = DelverState::ToBed;
            } else {
                self.delvers[idx].state = DelverState::Resting;
            }
            return;
        }
        if self.delvers[idx].energy < 30.0 {
            let bed = self.delver_bed(idx);
            if self.delvers[idx].pos == bed || self.start_path(idx, bed) {
                self.delvers[idx].state = DelverState::ToBed;
            } else {
                self.delvers[idx].state = DelverState::Resting;
            }
            return;
        }
        // Children (S12) live the camp life above — eat, rest,
        // morale — but are never dispatched to work: no job step,
        // no job XP. They idle at camp, in the lit safe zone.
        if self.delver_is_child(&self.delvers[idx]) {
            self.delvers[idx].state = DelverState::Idle;
            return;
        }
        match self.delvers[idx].job {
            Job::Miner => self.decide_miner(idx),
            Job::Farmer => self.decide_farmer(idx),
            Job::Herbalist => self.decide_herbalist(idx),
            // Haulers and the unassigned run the camp↔face route and
            // work the camp converter in between.
            Job::Hauler | Job::Unassigned => self.decide_hauler(idx),
        }
    }

    fn decide_miner(&mut self, idx: usize) {
        // Nearest workable face (deterministic: faces are sorted).
        let face_idx = self
            .faces
            .iter()
            .position(|f| f.ore > 0 || f.cache > 0);
        let Some(fi) = face_idx else {
            self.delvers[idx].state = DelverState::Idle;
            return;
        };
        let stand = self.faces[fi].stand;
        self.delvers[idx].target_face = Some(fi);
        if self.delvers[idx].pos == stand || self.start_path(idx, stand) {
            self.delvers[idx].state = DelverState::ToFace;
            self.delvers[idx].blocked_logged = false;
        } else {
            self.go_blocked(idx, "the face");
        }
    }

    fn decide_hauler(&mut self, idx: usize) {
        let face_idx = self.faces.iter().position(|f| f.cache > 0);
        if let Some(fi) = face_idx {
            let stand = self.faces[fi].stand;
            self.delvers[idx].target_face = Some(fi);
            if self.delvers[idx].pos == stand || self.start_path(idx, stand) {
                self.delvers[idx].state = DelverState::ToFace;
                self.delvers[idx].blocked_logged = false;
            } else {
                self.go_blocked(idx, "the face");
            }
            return;
        }
        if self.stores.ore >= 2 {
            self.delvers[idx].state = DelverState::Converting;
            return;
        }
        self.delvers[idx].state = DelverState::Idle;
    }

    fn decide_farmer(&mut self, idx: usize) {
        if self.plots.is_empty() {
            self.delvers[idx].state = DelverState::Idle;
            return;
        }
        // Prefer a ready plot, else the most-grown one.
        let pos = self.delvers[idx].pos;
        let mut best: Option<usize> = None;
        let mut best_key: (bool, i32) = (false, i32::MAX);
        for (pi, p) in self.plots.iter().enumerate() {
            let dist = (p.pos.x - pos.x).abs() + (p.pos.y - pos.y).abs() + (p.pos.z - pos.z).abs();
            let key = (p.growth >= PLOT_READY, dist);
            if best.is_none() || (key.0 && !best_key.0) || (key.0 == best_key.0 && key.1 < best_key.1)
            {
                best = Some(pi);
                best_key = key;
            }
        }
        let pi = best.unwrap();
        let target = self.plots[pi].pos;
        self.delvers[idx].target_plot = Some(pi);
        if pos == target || self.start_path(idx, target) {
            self.delvers[idx].state = DelverState::ToPlot;
            self.delvers[idx].blocked_logged = false;
        } else {
            self.go_blocked(idx, "the plots");
        }
    }

    fn tick_delver(&mut self, idx: usize) {
        // Needs decay by exertion; morale drifts toward how well the
        // delver's needs are met.
        let state = self.delvers[idx].state;
        let exertion = match state {
            DelverState::ToFace
            | DelverState::Mining
            | DelverState::ToCamp
            | DelverState::ToBed
            | DelverState::ToPlot
            | DelverState::Tending => 0.08,
            DelverState::Resting => 0.0,
            _ => 0.02,
        };
        if state != DelverState::Resting {
            self.delvers[idx].energy = (self.delvers[idx].energy - exertion).clamp(0.0, 100.0);
        }
        if state != DelverState::Eating {
            self.delvers[idx].hunger = (self.delvers[idx].hunger - 0.045).clamp(0.0, 100.0);
        }
        // A starving delver tires at everything.
        if self.delvers[idx].hunger <= 0.0 && state != DelverState::Resting {
            self.delvers[idx].energy = (self.delvers[idx].energy - 0.04).clamp(0.0, 100.0);
        }
        // Spores (S5): exposure in a spore band, clearing in clean
        // air — faster with a herbalist close by. Exposure goes
        // through `hazards_here` (S10): band-keyed on generated
        // floors, depth-keyed on hand-built worlds.
        {
            let pos = self.delvers[idx].pos;
            if self.hazards_here(pos).spores {
                let rate = if self.delvers[idx].masked {
                    SPORE_RATE_MASKED
                } else {
                    SPORE_RATE_UNMASKED
                };
                self.delvers[idx].spore = (self.delvers[idx].spore + rate).min(100.0);
                if self.delvers[idx].spore >= 100.0 {
                    self.delvers[idx].hp -= 0.2;
                    if self.delvers[idx].hp <= 0.0 {
                        self.down_delver(idx);
                        return;
                    }
                }
            } else if self.delvers[idx].spore > 0.0 {
                let near_herbalist = self.delvers.iter().any(|d| {
                    d.job == Job::Herbalist
                        && d.id != self.delvers[idx].id
                        && (d.pos.x - pos.x).abs() + (d.pos.y - pos.y).abs() + (d.pos.z - pos.z).abs()
                            <= 2
                });
                let clear = SPORE_CLEAR_RATE
                    + if near_herbalist {
                        HERBALIST_CARE_RATE
                    } else {
                        0.0
                    };
                self.delvers[idx].spore = (self.delvers[idx].spore - clear).max(0.0);
            }
            if self.delvers[idx].sick() && !self.delvers[idx].sick_logged {
                self.delvers[idx].sick_logged = true;
                let name = self.delvers[idx].name.clone();
                self.log(
                    LedgerKind::DelverSick,
                    format!("{name} has the spore-cough"),
                );
            }
            if self.delvers[idx].spore < 30.0 {
                self.delvers[idx].sick_logged = false;
            }
        }
        // Bad air (S7): exposure in a gassy cell, clearing in
        // clean air — fastest within a vent's reach.
        {
            let pos = self.delvers[idx].pos;
            if self.bad_air_at(pos) {
                self.delvers[idx].air = (self.delvers[idx].air + AIR_RATE).min(100.0);
                if self.delvers[idx].air >= 100.0 {
                    self.delvers[idx].hp -= 0.2;
                    if self.delvers[idx].hp <= 0.0 {
                        self.down_delver(idx);
                        return;
                    }
                }
            } else if self.delvers[idx].air > 0.0 {
                let rate = if self.ventilated(pos) {
                    VENT_CLEAR_RATE
                } else {
                    AIR_CLEAR_RATE
                };
                self.delvers[idx].air = (self.delvers[idx].air - rate).max(0.0);
            }
            if self.delvers[idx].gasping() && !self.delvers[idx].gasping_logged {
                self.delvers[idx].gasping_logged = true;
                let name = self.delvers[idx].name.clone();
                self.log(
                    LedgerKind::DelverGasping,
                    format!("{name} is gasping in bad air"),
                );
            }
            if self.delvers[idx].air < 30.0 {
                self.delvers[idx].gasping_logged = false;
            }
        }
        // Flooding (S10): exposure standing in flood water,
        // clearing in dry cells — fastest within a pump's reach.
        {
            let pos = self.delvers[idx].pos;
            if self.flooded_at(pos) {
                self.delvers[idx].water = (self.delvers[idx].water + WATER_RATE).min(100.0);
                if self.delvers[idx].water >= 100.0 {
                    self.delvers[idx].hp -= 0.2;
                    if self.delvers[idx].hp <= 0.0 {
                        self.down_delver(idx);
                        return;
                    }
                }
            } else if self.delvers[idx].water > 0.0 {
                let rate = if self.pumped(pos) {
                    PUMP_CLEAR_RATE
                } else {
                    WATER_CLEAR_RATE
                };
                self.delvers[idx].water = (self.delvers[idx].water - rate).max(0.0);
            }
            if self.delvers[idx].drowning() && !self.delvers[idx].drowning_logged {
                self.delvers[idx].drowning_logged = true;
                let name = self.delvers[idx].name.clone();
                self.log(
                    LedgerKind::DelverDrowning,
                    format!("{name} is drowning in the flooded workings"),
                );
            }
            if self.delvers[idx].water < 30.0 {
                self.delvers[idx].drowning_logged = false;
            }
        }
        // Heat (S10): exposure in a hot band's deep zone,
        // clearing in cool areas. Cooling gear prevents the
        // gain entirely.
        {
            let pos = self.delvers[idx].pos;
            if self.hazards_here(pos).hot && !self.delvers[idx].cooled {
                self.delvers[idx].heat = (self.delvers[idx].heat + HEAT_RATE).min(100.0);
                if self.delvers[idx].heat >= 100.0 {
                    self.delvers[idx].hp -= 0.2;
                    if self.delvers[idx].hp <= 0.0 {
                        self.down_delver(idx);
                        return;
                    }
                }
            } else if self.delvers[idx].heat > 0.0 {
                self.delvers[idx].heat =
                    (self.delvers[idx].heat - HEAT_CLEAR_RATE).max(0.0);
            }
            if self.delvers[idx].overheating() && !self.delvers[idx].overheating_logged {
                self.delvers[idx].overheating_logged = true;
                let name = self.delvers[idx].name.clone();
                self.log(
                    LedgerKind::DelverOverheating,
                    format!("{name} is overcome by the heat"),
                );
            }
            if self.delvers[idx].heat < 30.0 {
                self.delvers[idx].overheating_logged = false;
            }
        }
        {
            let d = &mut self.delvers[idx];
            // Colony prosperity lifts spirits only for the fed —
            // goods in the store mean little on an empty stomach.
            let goods_term = (self.stores.goods.min(10)) as f32 * (d.hunger / 100.0);
            let sick_term = if d.suffering() { -20.0 } else { 0.0 };
            let target =
                (10.0 + d.hunger * 0.5 + d.energy * 0.3 + goods_term + sick_term).clamp(0.0, 100.0);
            d.morale += (target - d.morale) * 0.02;
            d.morale = d.morale.clamp(0.0, 100.0);
        }
        if self.delvers[idx].morale < 25.0 && !self.delvers[idx].low_morale_logged {
            self.delvers[idx].low_morale_logged = true;
            let name = self.delvers[idx].name.clone();
            self.log(
                LedgerKind::SpiritsFallen,
                format!("{name}'s spirits have fallen"),
            );
        }
        if self.delvers[idx].morale > 40.0 {
            self.delvers[idx].low_morale_logged = false;
        }

        // The downed cannot act; their clock runs in the sweep.
        if self.delvers[idx].state == DelverState::Downed {
            return;
        }
        if self.delvers[idx].fight_cd > 0 {
            self.delvers[idx].fight_cd -= 1;
        }

        let on_rescue = matches!(
            self.delvers[idx].state,
            DelverState::ToRescue | DelverState::Rescuing
        );

        // In the dark with a way home: take it. (No way home is the
        // sweep's problem — the clock is running.)
        if !on_rescue
            && !self.lit_at(self.delvers[idx].pos)
            && self.delvers[idx].state != DelverState::ToCamp
        {
            if self.start_path(idx, self.stockpile) {
                self.delvers[idx].state = DelverState::ToCamp;
            }
        }

        // Combat: something is at claw's reach. The healthy stand
        // and fight; the hurt run for camp.
        if !on_rescue {
            let pos = self.delvers[idx].pos;
            let adjacent = self
                .critters
                .iter()
                .filter(|c| {
                    (c.pos.x - pos.x).abs() + (c.pos.y - pos.y).abs() + (c.pos.z - pos.z).abs()
                        <= 1
                })
                .map(|c| c.id)
                .next();
            if let Some(cid) = adjacent {
                if self.delvers[idx].hp < 35.0 {
                    if self.delvers[idx].state != DelverState::ToCamp
                        && self.start_path(idx, self.stockpile)
                    {
                        self.delvers[idx].state = DelverState::ToCamp;
                    }
                } else {
                    if self.delvers[idx].fight_cd == 0 {
                        self.delvers[idx].fight_cd = ATTACK_PERIOD;
                        let dmg = 3.0 + (self.delvers[idx].combat_xp / 8) as f32;
                        let name = self.delvers[idx].name.clone();
                        let mut slain = false;
                        if let Some(c) = self.critters.iter_mut().find(|c| c.id == cid) {
                            c.hp -= dmg;
                            slain = c.hp <= 0.0;
                        }
                        if slain {
                            self.delvers[idx].combat_xp += 2;
                            self.kill_critter(cid, Some(&name));
                        }
                    }
                    return; // busy fighting this tick
                }
            }
        }

        match self.delvers[idx].state {
            DelverState::Idle => self.decide(idx),
            DelverState::Blocked => {
                // Retry the job decision; light may have arrived.
                self.delvers[idx].state = DelverState::Idle;
                self.decide(idx);
            }
            DelverState::ToFace => {
                if self.follow_path(idx) {
                    match self.delvers[idx].job {
                        Job::Miner => {
                            self.delvers[idx].state = DelverState::Mining;
                        }
                        _ => {
                            // Hauler arrival: load from the face cache.
                            let fi = self.delvers[idx].target_face.unwrap_or(0);
                            let space = self.delvers[idx].capacity()
                                - self.delvers[idx].carrying;
                            let take = self
                                .faces
                                .get(fi)
                                .map_or(0, |f| f.cache.min(space));
                            if take > 0 {
                                if let Some(f) = self.faces.get_mut(fi) {
                                    f.cache -= take;
                                    self.delvers[idx].carrying_kind = f.yield_kind;
                                }
                                self.delvers[idx].carrying += take;
                            }
                            if self.delvers[idx].carrying > 0 {
                                if self.start_path(idx, self.stockpile) {
                                    self.delvers[idx].state = DelverState::ToCamp;
                                } else {
                                    self.go_blocked(idx, "the stockpile");
                                }
                            } else {
                                self.delvers[idx].state = DelverState::Idle;
                            }
                        }
                    }
                }
            }
            DelverState::Mining => {
                let fi = match self.delvers[idx].target_face {
                    Some(fi) if fi < self.faces.len() => fi,
                    _ => {
                        self.delvers[idx].state = DelverState::Idle;
                        return;
                    }
                };
                let mult = self.delvers[idx].work_mult();
                let rate = (0.2 + 0.04 * self.delvers[idx].mining_level() as f32) * mult;
                self.delvers[idx].mine_progress += rate;
                while self.delvers[idx].mine_progress >= 1.0 && self.faces[fi].ore > 0 {
                    self.delvers[idx].mine_progress -= 1.0;
                    self.faces[fi].ore -= 1;
                    self.faces[fi].cache += 1;
                    self.delvers[idx].mining_xp += 1;
                    // Working loose rock can bring it down (S7).
                    if self.maybe_cave_in(idx, fi) {
                        break;
                    }
                }
                if self.delvers[idx].state == DelverState::Downed {
                    return;
                }
                let face_done = self.faces[fi].ore == 0;
                let cache_full = self.faces[fi].cache >= 8;
                let self_haul = self.faces[fi].cache >= self.delvers[idx].capacity()
                    && !self.has_hauler();
                if face_done || cache_full || self_haul {
                    // Load up and run it home personally.
                    let space =
                        self.delvers[idx].capacity() - self.delvers[idx].carrying;
                    let take = self.faces[fi].cache.min(space);
                    self.faces[fi].cache -= take;
                    self.delvers[idx].carrying_kind = self.faces[fi].yield_kind;
                    self.delvers[idx].carrying += take;
                    if self.delvers[idx].carrying > 0 {
                        if self.start_path(idx, self.stockpile) {
                            self.delvers[idx].state = DelverState::ToCamp;
                        } else {
                            self.go_blocked(idx, "the stockpile");
                        }
                    } else if face_done {
                        // Nothing left and nothing to carry: head home.
                        if self.start_path(idx, self.stockpile) {
                            self.delvers[idx].state = DelverState::ToCamp;
                        } else {
                            self.delvers[idx].state = DelverState::Idle;
                        }
                    } else {
                        self.delvers[idx].state = DelverState::Idle;
                    }
                }
            }
            DelverState::ToCamp => {
                if self.follow_path(idx) {
                    self.deposit(idx);
                    // Wounds close slowly at camp.
                    if self.delvers[idx].hp < 100.0 {
                        self.delvers[idx].state = DelverState::Resting;
                    } else {
                        self.decide(idx);
                    }
                }
            }
            DelverState::Downed => unreachable!("downed delvers return early"),
            DelverState::ToRescue => {
                let Some(tid) = self.delvers[idx].rescue_target else {
                    self.delvers[idx].state = DelverState::Idle;
                    return;
                };
                let tpos = self
                    .delvers
                    .iter()
                    .find(|d| d.id == tid && d.state == DelverState::Downed)
                    .map(|d| d.pos);
                let Some(tpos) = tpos else {
                    self.delvers[idx].rescue_target = None;
                    self.delvers[idx].state = DelverState::Idle;
                    return;
                };
                let arrived = self.follow_path(idx);
                let pos = self.delvers[idx].pos;
                let near = (pos.x - tpos.x).abs()
                    + (pos.y - tpos.y).abs()
                    + (pos.z - tpos.z).abs()
                    <= 1;
                if arrived || (self.delvers[idx].path.is_empty() && near) {
                    if self.start_path(idx, self.stockpile) {
                        self.delvers[idx].state = DelverState::Rescuing;
                    }
                    // No lit way home yet: wait with them; the sweep
                    // keeps their clock running, not the rescuer's.
                }
            }
            DelverState::Rescuing => {
                let Some(tid) = self.delvers[idx].rescue_target else {
                    self.delvers[idx].state = DelverState::Idle;
                    return;
                };
                let ti = self
                    .delvers
                    .iter()
                    .position(|d| d.id == tid && d.state == DelverState::Downed);
                let Some(ti) = ti else {
                    self.delvers[idx].rescue_target = None;
                    self.delvers[idx].state = DelverState::Idle;
                    return;
                };
                // Carrying is slow work: move every other tick, and
                // the carried delver moves with the carrier.
                if self.tick_count % 2 == 0 {
                    let arrived = self.follow_path(idx);
                    let my_pos = self.delvers[idx].pos;
                    self.delvers[ti].pos = my_pos;
                    if arrived || my_pos == self.stockpile {
                        let rname = self.delvers[idx].name.clone();
                        let dname = self.delvers[ti].name.clone();
                        self.delvers[ti].hp = 30.0;
                        self.delvers[ti].state = DelverState::Resting;
                        self.delvers[ti].dark_clock = None;
                        self.delvers[idx].rescue_target = None;
                        self.delvers[idx].state = DelverState::Idle;
                        self.log(
                            LedgerKind::DelverRescued,
                            format!("{rname} carried {dname} home"),
                        );
                    }
                }
            }
            DelverState::Converting => {
                // Camp conversion work (haulers): pairs of ore become
                // goods at a working pace rather than instantly.
                let mult = self.delvers[idx].work_mult();
                self.delvers[idx].convert_progress += 0.1 * mult;
                if self.delvers[idx].convert_progress >= 1.0 {
                    self.delvers[idx].convert_progress = 0.0;
                    if self.stores.ore >= 2 {
                        self.stores.ore -= 2;
                        self.stores.goods += 1;
                        self.delvers[idx].hauling_xp += 1;
                        self.log(
                            LedgerKind::Converted,
                            format!(
                                "{} converted 2 ore into 1 goods",
                                self.delvers[idx].name
                            ),
                        );
                    }
                }
                if self.stores.ore < 2 {
                    self.delvers[idx].state = DelverState::Idle;
                }
                // New cache at a face outranks converting.
                if self.faces.iter().any(|f| f.cache > 0)
                    && matches!(self.delvers[idx].job, Job::Hauler | Job::Unassigned)
                {
                    self.decide(idx);
                }
            }
            DelverState::ToBed => {
                if self.follow_path(idx) {
                    self.delvers[idx].state = DelverState::Resting;
                }
            }
            DelverState::Resting => {
                // A starving delver cannot rest properly.
                let cap = if self.delvers[idx].hunger <= 1.0 {
                    50.0
                } else {
                    100.0
                };
                self.delvers[idx].energy = (self.delvers[idx].energy + 2.5).min(cap);
                // Wounds close at camp, slower than energy returns.
                if self.delvers[idx].hp < 100.0 {
                    self.delvers[idx].hp = (self.delvers[idx].hp + 0.8).min(100.0);
                }
                if self.delvers[idx].energy >= cap
                    && self.delvers[idx].hp >= 60.0
                    && self.delvers[idx].spore < 30.0
                    && self.delvers[idx].air < 30.0
                    && self.delvers[idx].water < 30.0
                    && self.delvers[idx].heat < 30.0
                {
                    self.decide(idx);
                }
            }
            DelverState::Eating => {
                if self.stores.food > 0 {
                    self.stores.food -= 1;
                    self.delvers[idx].hunger = 100.0;
                }
                self.decide(idx);
            }
            DelverState::ToPatient => {
                if self.follow_path(idx) {
                    self.delvers[idx].state = DelverState::Care;
                }
            }
            DelverState::Care => {
                // Stand with the patient; the care itself lands in
                // the patient's own spore clearing. When nobody near
                // is sick any more, re-decide.
                let pos = self.delvers[idx].pos;
                let any_sick_near = self.delvers.iter().any(|d| {
                    d.id != self.delvers[idx].id
                        && d.spore >= 30.0
                        && (d.pos.x - pos.x).abs() + (d.pos.y - pos.y).abs() + (d.pos.z - pos.z).abs()
                            <= 2
                });
                if !any_sick_near {
                    self.decide(idx);
                }
            }
            DelverState::ToPlot => {
                if self.follow_path(idx) {
                    self.delvers[idx].state = DelverState::Tending;
                }
            }
            DelverState::Tending => {
                let pi = match self.delvers[idx].target_plot {
                    Some(pi) if pi < self.plots.len() => pi,
                    _ => {
                        self.delvers[idx].state = DelverState::Idle;
                        return;
                    }
                };
                if self.plots[pi].growth >= PLOT_READY {
                    self.plots[pi].growth = 0.0;
                    self.delvers[idx].carrying_food += PLOT_YIELD;
                    self.delvers[idx].farming_xp += PLOT_YIELD;
                    let name = self.delvers[idx].name.clone();
                    self.log(
                        LedgerKind::Harvested,
                        format!("{name} harvested {PLOT_YIELD} food from the plots"),
                    );
                    if self.delvers[idx].carrying_food >= PLOT_YIELD * 2 {
                        if self.start_path(idx, self.stockpile) {
                            self.delvers[idx].state = DelverState::ToCamp;
                        } else {
                            self.decide(idx);
                        }
                    } else {
                        self.decide_farmer_next(idx);
                    }
                } else {
                    let mult = self.delvers[idx].work_mult();
                    let rate = (0.055 + 0.005 * self.delvers[idx].farming_level() as f32) * mult;
                    self.plots[pi].growth = (self.plots[pi].growth + rate).min(PLOT_READY);
                }
            }
        }
    }

    fn decide_herbalist(&mut self, idx: usize) {
        // The sickest delver is the patient; go to them, or farm.
        // A patient stays a patient until they are well (spore under
        // 30), not merely until they stop being critical.
        let my_pos = self.delvers[idx].pos;
        let patient = self
            .delvers
            .iter()
            .filter(|d| d.id != self.delvers[idx].id && d.spore >= 30.0)
            .max_by(|a, b| a.spore.partial_cmp(&b.spore).unwrap());
        let Some(patient) = patient.map(|d| (d.id, d.pos)) else {
            self.decide_farmer(idx);
            return;
        };
        let (_, ppos) = patient;
        let dist = (ppos.x - my_pos.x).abs() + (ppos.y - my_pos.y).abs() + (ppos.z - my_pos.z).abs();
        if dist <= 2 {
            self.delvers[idx].state = DelverState::Care;
        } else if self.start_path(idx, ppos) {
            self.delvers[idx].state = DelverState::ToPatient;
            self.delvers[idx].blocked_logged = false;
        } else {
            // Patient is somewhere light doesn't reach; farm instead.
            self.decide_farmer(idx);
        }
    }

    /// After a harvest with room to carry more, move to the next plot
    /// worth tending instead of walking home.
    fn decide_farmer_next(&mut self, idx: usize) {
        self.delvers[idx].state = DelverState::Idle;
        self.decide_farmer(idx);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::world::World;

    fn tiny_world() -> World {
        // 7x3x3, all stone; carve a corridor along x at y=1, z=1.
        let mut w = World::new(7, 3, 3, Cell::Stone);
        for x in 0..7 {
            w.carve(Pos::new(x, 1, 1));
        }
        w
    }

    #[test]
    fn lantern_lights_carved_cells_only() {
        let w = tiny_world();
        let lanterns = vec![LanternEntry {
            pos: Pos::new(1, 1, 1),
            tier: 1,
            fuel: 100.0,
        }];
        let lit = compute_lit(&w, &lanterns);
        // Corridor cell within radius is lit.
        assert!(lit[w.idx(Pos::new(4, 1, 1)).unwrap()]);
        // Beyond radius: dark.
        assert!(!lit[w.idx(Pos::new(6, 1, 1)).unwrap()]);
        // Solid rock is never lit.
        assert!(!lit[w.idx(Pos::new(1, 1, 0)).unwrap()]);
    }

    #[test]
    fn dead_lantern_lights_nothing() {
        let w = tiny_world();
        let lanterns = vec![LanternEntry {
            pos: Pos::new(1, 1, 1),
            tier: 1,
            fuel: 0.0,
        }];
        let lit = compute_lit(&w, &lanterns);
        assert!(lit.iter().all(|&l| !l));
    }

    #[test]
    fn path_requires_light() {
        let w = tiny_world();
        let lanterns = vec![LanternEntry {
            pos: Pos::new(3, 1, 1),
            tier: 1,
            fuel: 100.0,
        }];
        let lit = compute_lit(&w, &lanterns);
        let path = find_path(&w, &lit, Pos::new(0, 1, 1), Pos::new(6, 1, 1));
        assert!(path.is_some());
        // Same corridor, no lantern: no path through the dark.
        let dark = compute_lit(&w, &[]);
        assert!(find_path(&w, &dark, Pos::new(0, 1, 1), Pos::new(6, 1, 1)).is_none());
    }
}
