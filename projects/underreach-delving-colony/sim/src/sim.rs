//! Simulation core: lanterns and light, pathing through the lit
//! network, the Deep Ledger, and canonical save/load with a state
//! hash. S2 grows the S1 single-delver loop into a colony: multiple
//! delvers with jobs (miner / hauler / farmer), morale, camp food
//! production, and surface recruitment.
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

use std::collections::{BTreeSet, HashMap, HashSet, VecDeque};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::gen::FloorInfo;
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
pub const SPORE_RATE_UNMASKED: f32 = 0.6;
pub const SPORE_RATE_MASKED: f32 = 0.05;
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
    /// Morale scales all work rates: a miserable delver works at
    /// 0.6x, a thriving one at 1.2x. Sickness halves it again.
    pub fn work_mult(&self) -> f32 {
        let base = 0.6 + 0.6 * (self.morale / 100.0);
        if self.sick() {
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
    pub rng_state: u64,
    pub next_arrival: u64,
    pub next_delver_id: u32,
    /// Kept in id order (spawns append).
    pub critters: Vec<Critter>,
    pub next_critter_id: u32,
    /// Scenarios from before the dark bit (S1/S2) keep critters off;
    /// S3 turns them on.
    pub critters_enabled: bool,
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
            plots: Vec::new(),
            gate,
            stores,
            ledger: Vec::new(),
            lit_depths: BTreeSet::new(),
            tick_count: 0,
            world_seed: rng_seed,
            floor: None,
            rng_state: if rng_seed == 0 { 0x9E37_79B9_7F4A_7C15 } else { rng_seed },
            next_arrival,
            next_delver_id,
            critters: Vec::new(),
            next_critter_id: 0,
            critters_enabled,
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

    /// Assign a delver's job. Takes effect at their next decision.
    pub fn set_job(&mut self, delver_id: u32, job: Job) {
        if let Some(d) = self.delvers.iter_mut().find(|d| d.id == delver_id) {
            d.job = job;
            d.state = DelverState::Idle;
            d.path.clear();
            d.target_face = None;
            d.target_plot = None;
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

    // -- Tick -------------------------------------------------------------------

    pub fn tick(&mut self) {
        // Lanterns burn. A lantern that dies takes its light with it.
        let mut burned_out: Vec<Pos> = Vec::new();
        for e in self.lanterns.iter_mut() {
            if e.fuel > 0.0 {
                e.fuel -= tier_burn(e.tier);
                if e.fuel <= 0.0 {
                    e.fuel = 0.0;
                    burned_out.push(e.pos);
                }
            }
        }
        if !burned_out.is_empty() {
            for p in &burned_out {
                self.log(
                    LedgerKind::LanternOut,
                    format!("lantern at ({}, {}, {}) burned out", p.x, p.y, p.z),
                );
            }
            self.refresh_light();
        }
        // Mushroom plots grow a little on their own.
        for p in self.plots.iter_mut() {
            p.growth = (p.growth + PLOT_PASSIVE_GROWTH).min(PLOT_READY);
        }
        self.maybe_recruit();
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
            let path = if self.lit_at(dpos) {
                find_path(&self.world, &self.lit, from, dpos)
            } else {
                self.find_path_dash(from, dpos)
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
        if self.delvers[idx].hunger < 40.0 && self.stores.food > 0 {
            self.delvers[idx].state = DelverState::Eating;
            return;
        }
        // The spore-sick go to bed and stay there until it clears.
        if self.delvers[idx].sick() {
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
        // air — faster with a herbalist close by.
        {
            let pos = self.delvers[idx].pos;
            if hazards_at(pos.y).spores {
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
        {
            let d = &mut self.delvers[idx];
            // Colony prosperity lifts spirits only for the fed —
            // goods in the store mean little on an empty stomach.
            let goods_term = (self.stores.goods.min(10)) as f32 * (d.hunger / 100.0);
            let sick_term = if d.sick() { -20.0 } else { 0.0 };
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
