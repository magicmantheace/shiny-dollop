//! Procedural floor generation (S6) — the owner's 2026-11-12
//! design: every floor is generated from its band **theme** and a
//! **unified world seed**, as a pure function of
//! `(world_seed, floor_index)`. See `docs/FLOOR_GENERATION.md` for
//! the full design record.
//!
//! The rules this module lives by:
//! - Generation uses its own RNG seeded from a hash-mix of the
//!   world seed and the floor index. It never touches the sim's
//!   runtime RNG state, and it never reads how many floors were
//!   generated before — floor N is the same generated standalone
//!   or after floors 1..N−1.
//! - A generated floor is mostly **solid rock**. Generation decides
//!   what is embedded in it (ore veins, hazard pockets, dressing)
//!   and what is already open (the entry camp, natural cavities,
//!   and the pre-connected passage network the owner asked for).
//!   The colony is still carved out of it by delving — the carve
//!   model is untouched.
//! - Passages start dark like everything else. They are ordinary
//!   carved cells: the player (who carries light) can walk them,
//!   delvers can only use them once they are lanterned, per the
//!   lit-nav-graph rule. No sim rule treats them specially.

use std::collections::{BTreeSet, HashMap, HashSet, VecDeque};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::sim::{CritterKind, Face, Hazards, Rng, YieldKind};
use crate::world::{Cell, Pos, World};

// ---------------------------------------------------------------------------
// Floor geometry (Floor 1 keeps the proven S1–S3 play space)
// ---------------------------------------------------------------------------

pub const FLOOR_W: usize = 24;
pub const FLOOR_H: usize = 12;
pub const FLOOR_D: usize = 8;

/// The entry cell: the camp stockpile, where the colony starts and
/// where network distances are measured from. Matches the position
/// the hand-built scenarios use.
pub const ENTRY: Pos = Pos { x: 3, y: 3, z: 4 };
/// Centre of the entry camp chamber (the camp lantern's cell).
pub const CAMP_CENTRE: Pos = Pos { x: 4, y: 3, z: 4 };
/// Where surface arrivals appear.
pub const GATE: Pos = Pos { x: 6, y: 3, z: 4 };
/// Depth of the camp chamber.
pub const CAMP_Y: i32 = 3;
/// Deepest depth generation places features at. Depths 10–11 are
/// the solid under-crust between floors (and stay above nothing —
/// the Fungal line in `hazards_at` starts at 10, so the Shallows'
/// playable rock ends at 9).
pub const GEN_MAX_Y: i32 = 9;

// ---------------------------------------------------------------------------
// Seed derivation
// ---------------------------------------------------------------------------

/// Derive one floor's seed from the colony's world seed. A
/// splitmix64-style hash mix — deliberately *not* sequential RNG
/// draws, so generating floor 5 never depends on floors 2–4.
pub fn floor_seed(world_seed: u64, floor_index: u32) -> u64 {
    let mut z = world_seed ^ (floor_index as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

fn gen_rng(seed: u64) -> Rng {
    // xorshift sticks at zero; the sim guards its own seed the
    // same way.
    Rng {
        state: if seed == 0 {
            0x9E37_79B9_7F4A_7C15
        } else {
            seed
        },
    }
}

// ---------------------------------------------------------------------------
// Bands and themes
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Band {
    Shallows,
    FungalReaches,
    DrownedGalleries,
    CrystalDark,
    MagmaRoots,
}

/// Which depth band a floor belongs to. Floors are 1-based; below
/// the Magma Roots the bands **recombine** (owner decision 9): the
/// cycle repeats, which is what makes depth endless without a
/// longer linear list.
pub fn band_for_floor(floor_index: u32) -> Band {
    match floor_index {
        0 | 1 => Band::Shallows,
        2 => Band::FungalReaches,
        3 => Band::DrownedGalleries,
        4 => Band::CrystalDark,
        5 => Band::MagmaRoots,
        n => [Band::FungalReaches, Band::DrownedGalleries, Band::CrystalDark, Band::MagmaRoots]
            [((n - 6) % 4) as usize],
    }
}

/// A generated hazard pocket's kind (mirrors the `Cell` the pocket
/// is embedded as).
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug, Serialize, Deserialize)]
pub enum HazardKind {
    LooseRock,
    BadAir,
}

/// Theme dressing: what a band's open spaces are decorated with.
/// Every kind renders as a placeholder marker in the frontend
/// today; `docs/FLOOR_GENERATION.md` maps each kind to the queued
/// Game Asset Builder asset that will replace it.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug, Serialize, Deserialize)]
pub enum DressingKind {
    Stalactite,
    Stalagmite,
    Rubble,
    Boulder,
    DescentStairs,
    SporePod,
    GiantMushroom,
    Pump,
    AirBell,
    CrystalFormation,
    LensPost,
    BasaltColumn,
    HeatPipe,
}

/// The data-driven per-band theme table. The generator is driven
/// entirely by these numbers; only the Shallows row is balanced
/// and verified — the other bands are explicit stubs (`built:
/// false`) with placeholder numbers, so later floors plug into
/// the same generator when their slices are built.
#[derive(Clone)]
pub struct Theme {
    pub band: Band,
    /// True only for Floor 1 (the Shallows): designed,
    /// scenario'd, and verified. Stub themes generate worlds
    /// through the same code path but carry no balance claims.
    pub built: bool,
    /// The band's hazard flags (same data type as S5's
    /// `hazards_at`, recorded per floor rather than per depth).
    pub hazards: Hazards,
    /// Depths of Earth (soil) at the top of the floor slab.
    pub cap_depth: i32,
    /// Rock cells veins are made of, primary first.
    pub resource_cells: &'static [Cell],
    /// Extra fungal-node clusters embedded in the rock (the
    /// Fungal Reaches' second resource).
    pub fungal_node_clusters: usize,
    /// Natural cavities connected into the passage network.
    pub connected_cavities: usize,
    /// Natural cavities left in the rock, reachable only by
    /// carving.
    pub off_network_cavities: usize,
    pub cavity_w: (i32, i32),
    pub cavity_d: (i32, i32),
    /// Monster dens: how many sit on the passage network (a
    /// minimum the generator guarantees) and off it (a minority).
    pub dens_on_network: usize,
    pub dens_off_network: usize,
    /// No on-network den sits closer than this to the entry, in
    /// passage steps (owner amendment, 2026-11-12).
    pub den_min_network_distance: u32,
    /// The descent cavern sits at least this far from the entry
    /// in passage steps — deep into the floor, past danger, but
    /// always reachable by exploration (owner decision,
    /// 2026-11-12: finding the way down is never a strip-mining
    /// search).
    pub descent_min_network_distance: u32,
    /// Ore veins embedded per floor (faces + pockets together).
    pub veins: usize,
    pub vein_cells: (usize, usize),
    /// The richest pocket, deliberately off-network.
    pub rich_vein_cells: usize,
    /// How many veins at most become workable faces (their stand
    /// cell is carved network/cavity space). The rest stay
    /// embedded pockets.
    pub face_veins_max: usize,
    pub loose_count: usize,
    pub loose_size: (usize, usize),
    pub bad_air_count: usize,
    pub bad_air_size: (usize, usize),
    /// Dead-end spurs off the passage network.
    pub spurs: usize,
    pub spur_len: (i32, i32),
    /// Extra node-to-node links beyond the chain — the network
    /// always contains a loop.
    pub loop_edges: usize,
    /// Percent chance a routed segment is widened to 2 cells.
    pub widen_pct: u64,
    pub dressing_kinds: &'static [DressingKind],
    /// Den critters and the band's spawn table, primary first.
    pub critter_kinds: &'static [CritterKind],
}

fn base_theme(band: Band) -> Theme {
    Theme {
        band,
        built: false,
        hazards: Hazards::default(),
        cap_depth: 2,
        resource_cells: &[Cell::Ore],
        fungal_node_clusters: 0,
        connected_cavities: 5,
        off_network_cavities: 2,
        cavity_w: (2, 3),
        cavity_d: (2, 3),
        dens_on_network: 2,
        dens_off_network: 1,
        den_min_network_distance: 10,
        descent_min_network_distance: 24,
        veins: 6,
        vein_cells: (2, 3),
        rich_vein_cells: 4,
        face_veins_max: 3,
        loose_count: 5,
        loose_size: (1, 3),
        bad_air_count: 4,
        bad_air_size: (1, 2),
        spurs: 3,
        spur_len: (3, 6),
        loop_edges: 1,
        widen_pct: 33,
        dressing_kinds: &[DressingKind::Stalactite, DressingKind::Stalagmite, DressingKind::Rubble],
        critter_kinds: &[CritterKind::GloamRat],
    }
}

/// The theme for a band. Floor 1's row is the designed one; the
/// rest are stubs marked NOT BUILT (see `built`).
pub fn theme_for_band(band: Band) -> Theme {
    let mut t = base_theme(band);
    match band {
        Band::Shallows => {
            t.built = true;
            t.dressing_kinds = &[
                DressingKind::Stalactite,
                DressingKind::Stalagmite,
                DressingKind::Rubble,
                DressingKind::Boulder,
            ];
            t.critter_kinds = &[CritterKind::GloamRat];
        }
        Band::FungalReaches => {
            t.hazards = Hazards { spores: true, flooded: false, hot: false };
            t.resource_cells = &[Cell::Ore, Cell::FungalNode];
            t.fungal_node_clusters = 4;
            t.loose_count = 3;
            t.bad_air_count = 3;
            t.dressing_kinds = &[
                DressingKind::GiantMushroom,
                DressingKind::SporePod,
                DressingKind::Stalactite,
                DressingKind::Rubble,
            ];
            t.critter_kinds = &[CritterKind::GloamRat, CritterKind::DeepLurker];
        }
        Band::DrownedGalleries => {
            t.hazards = Hazards { spores: false, flooded: true, hot: false };
            t.loose_count = 4;
            t.bad_air_count = 5;
            t.veins = 5;
            t.dressing_kinds = &[
                DressingKind::Pump,
                DressingKind::AirBell,
                DressingKind::Rubble,
                DressingKind::Stalagmite,
            ];
            t.critter_kinds = &[CritterKind::DeepLurker];
        }
        Band::CrystalDark => {
            t.loose_count = 6; // brittle floors
            t.bad_air_count = 2;
            t.dressing_kinds = &[
                DressingKind::CrystalFormation,
                DressingKind::LensPost,
                DressingKind::Rubble,
            ];
            t.critter_kinds = &[CritterKind::DeepLurker];
        }
        Band::MagmaRoots => {
            t.hazards = Hazards { spores: false, flooded: false, hot: true };
            t.loose_count = 6;
            t.bad_air_count = 4;
            t.dressing_kinds = &[
                DressingKind::BasaltColumn,
                DressingKind::HeatPipe,
                DressingKind::Rubble,
            ];
            t.critter_kinds = &[CritterKind::DeepLurker];
        }
    }
    t
}

pub fn theme_for_floor(floor_index: u32) -> Theme {
    theme_for_band(band_for_floor(floor_index))
}

// ---------------------------------------------------------------------------
// Layout — everything generation decided, in canonical order
// ---------------------------------------------------------------------------

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Cavity {
    pub centre: Pos,
    /// All carved cells of the cavity, sorted.
    pub cells: Vec<Pos>,
    /// Part of the passage network (vs sealed in the rock).
    pub connected: bool,
    /// A monster den: a lair cavity with a resident critter.
    pub den: bool,
    pub critter: Option<CritterKind>,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Vein {
    /// The resource cells, sorted.
    pub cells: Vec<Pos>,
    /// True when the vein is registered as a workable face
    /// (its stand cell is carved space). False = an embedded
    /// pocket, visible in the layout but not yet a face.
    pub is_face: bool,
    /// Units in the face record (faces only).
    pub ore_units: u32,
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct HazardPocket {
    pub pos: Pos,
    pub kind: HazardKind,
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct DressingAnchor {
    pub pos: Pos,
    pub kind: DressingKind,
}

/// The generator's full record for one floor. Everything is in
/// canonical (sorted) order so equal floors compare equal.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct FloorLayout {
    pub floor_index: u32,
    pub band: Band,
    pub entry: Pos,
    /// The stairs down: a cell inside the descent cavern.
    pub descent: Pos,
    /// The descent cavern's carved cells, sorted.
    pub descent_cavern: Vec<Pos>,
    /// Passage steps from the entry to the descent, measured on
    /// the generated grid.
    pub descent_network_distance: u32,
    pub cavities: Vec<Cavity>,
    /// Passage-network node centres in chain order (entry camp
    /// first, descent cavern last).
    pub nodes: Vec<Pos>,
    /// Node-graph links (chain + loop edges) over `nodes`.
    pub links: Vec<(usize, usize)>,
    /// Cells carved as passages (not camp/cavity/descent
    /// interiors), sorted.
    pub network_cells: Vec<Pos>,
    pub veins: Vec<Vein>,
    pub hazards: Vec<HazardPocket>,
    pub dressing: Vec<DressingAnchor>,
    /// Workable faces registered from veins, sorted by rock
    /// position (the order `Sim` keeps).
    pub faces: Vec<Face>,
    /// Which sampling attempt produced this layout (see
    /// `generate_floor`): 0 = the first layout the seed drew.
    pub generation_attempts: u32,
}

/// The small part of the layout the sim carries in its save, so
/// the frontend can render the floor's features after a load.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct FloorInfo {
    pub index: u32,
    pub descent: Pos,
    /// Den centres (on- and off-network), sorted.
    pub dens: Vec<Pos>,
    pub dressing: Vec<DressingAnchor>,
    pub hazards: Vec<HazardPocket>,
}

pub struct Floor {
    pub world: World,
    pub layout: FloorLayout,
}

impl Floor {
    pub fn info(&self) -> FloorInfo {
        FloorInfo {
            index: self.layout.floor_index,
            descent: self.layout.descent,
            dens: self
                .layout
                .cavities
                .iter()
                .filter(|c| c.den)
                .map(|c| c.centre)
                .collect(),
            dressing: self.layout.dressing.clone(),
            hazards: self.layout.hazards.clone(),
        }
    }
}

// ---------------------------------------------------------------------------
// Carved-space routing helpers (light-agnostic: generation and
// scenario scripts route through open space; the *sim's* pathing
// rules are unchanged and still demand light)
// ---------------------------------------------------------------------------

/// BFS distances over carved cells from `from`; −1 = unreachable.
pub fn carved_distances(world: &World, from: Pos) -> Vec<i32> {
    let mut dist = vec![-1; world.volume()];
    let Some(start) = world.idx(from) else {
        return dist;
    };
    if world.get(from) != Some(Cell::Carved) {
        return dist;
    }
    let mut queue: VecDeque<Pos> = VecDeque::new();
    dist[start] = 0;
    queue.push_back(from);
    while let Some(cur) = queue.pop_front() {
        let d = dist[world.idx(cur).unwrap()];
        for n in cur.neighbors6() {
            if world.get(n) != Some(Cell::Carved) {
                continue;
            }
            let ni = world.idx(n).unwrap();
            if dist[ni] < 0 {
                dist[ni] = d + 1;
                queue.push_back(n);
            }
        }
    }
    dist
}

/// A path through carved cells, excluding `from`, including `to`
/// (the same convention as the sim's `find_path`).
pub fn carved_path(world: &World, from: Pos, to: Pos) -> Option<Vec<Pos>> {
    if from == to {
        return Some(Vec::new());
    }
    if world.get(to) != Some(Cell::Carved) {
        return None;
    }
    let mut prev: HashMap<Pos, Pos> = HashMap::new();
    let mut seen: HashSet<Pos> = HashSet::new();
    let mut queue: VecDeque<Pos> = VecDeque::new();
    seen.insert(from);
    queue.push_back(from);
    while let Some(cur) = queue.pop_front() {
        for n in cur.neighbors6() {
            if seen.contains(&n) || world.get(n) != Some(Cell::Carved) {
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

/// A stable signature of a world grid (dims + every cell), for
/// tests and diagnostics.
pub fn world_hash(world: &World) -> String {
    let mut h = Sha256::new();
    h.update(world.sx.to_le_bytes());
    h.update(world.sy.to_le_bytes());
    h.update(world.sz.to_le_bytes());
    for y in 0..world.sy as i32 {
        for z in 0..world.sz as i32 {
            for x in 0..world.sx as i32 {
                let c = world.get(Pos::new(x, y, z)).unwrap_or(Cell::Stone);
                h.update([match c {
                    Cell::Earth => 1u8,
                    Cell::Stone => 2,
                    Cell::Ore => 3,
                    Cell::FungalNode => 4,
                    Cell::Loose => 5,
                    Cell::BadAir => 6,
                    Cell::Carved => 7,
                }]);
            }
        }
    }
    format!("{:x}", h.finalize())
}

// ---------------------------------------------------------------------------
// Generation internals
// ---------------------------------------------------------------------------

fn chebyshev(a: Pos, b: Pos) -> i32 {
    (a.x - b.x).abs().max((a.y - b.y).abs()).max((a.z - b.z).abs())
}

fn manhattan(a: Pos, b: Pos) -> i32 {
    (a.x - b.x).abs() + (a.y - b.y).abs() + (a.z - b.z).abs()
}

/// Add cells (and their Chebyshev-1 halo) to the reserved set, so
/// later features keep at least one cell of rock between rooms.
fn reserve(reserved: &mut HashSet<Pos>, cells: &[Pos]) {
    for &c in cells {
        for dy in -1..=1 {
            for dx in -1..=1 {
                for dz in -1..=1 {
                    reserved.insert(Pos::new(c.x + dx, c.y + dy, c.z + dz));
                }
            }
        }
    }
}

struct PlacedRoom {
    centre: Pos,
    cells: Vec<Pos>,
}

/// The plan-view (x, z) cells of `cells` plus their Chebyshev-1
/// halo in plan. Passage shafts run in the plan column of a
/// room's centre, so rooms that must never be breached are kept
/// at plan distance ≥ 2 — a 3D spacing rule alone lets a shaft
/// pass one cell *beside* a sealed room on the same depth.
fn plan_halo(cells: &[Pos]) -> HashSet<(i32, i32)> {
    let mut out = HashSet::new();
    for c in cells {
        for dx in -1..=1 {
            for dz in -1..=1 {
                out.insert((c.x + dx, c.z + dz));
            }
        }
    }
    out
}

/// Place one rectangular cavity (single-height, like every carved
/// space in the sim) inside the given sampling ranges, clear of
/// everything already reserved — in 3D (`reserved`) and in plan
/// view (`plan_blocked`).
#[allow(clippy::too_many_arguments)]
fn place_room(
    world: &mut World,
    rng: &mut Rng,
    reserved: &HashSet<Pos>,
    plan_blocked: &HashSet<(i32, i32)>,
    xr: (i32, i32),
    yr: (i32, i32),
    zr: (i32, i32),
    w_range: (i32, i32),
    d_range: (i32, i32),
    attempts: usize,
) -> Option<PlacedRoom> {
    for _ in 0..attempts {
        let w = w_range.0 + rng.below((w_range.1 - w_range.0 + 1) as u64) as i32;
        let d = d_range.0 + rng.below((d_range.1 - d_range.0 + 1) as u64) as i32;
        let x0 = xr.0 + rng.below((xr.1 - xr.0 + 1) as u64) as i32;
        let y = yr.0 + rng.below((yr.1 - yr.0 + 1) as u64) as i32;
        let z0 = zr.0 + rng.below((zr.1 - zr.0 + 1) as u64) as i32;
        if x0 + w - 1 > FLOOR_W as i32 - 2 || z0 + d - 1 > FLOOR_D as i32 - 2 {
            continue;
        }
        let mut cells = Vec::new();
        let mut ok = true;
        for x in x0..x0 + w {
            for z in z0..z0 + d {
                let p = Pos::new(x, y, z);
                if reserved.contains(&p)
                    || plan_blocked.contains(&(x, z))
                    || world.get(p) != Some(Cell::Stone)
                {
                    ok = false;
                    break;
                }
                cells.push(p);
            }
            if !ok {
                break;
            }
        }
        if !ok {
            continue;
        }
        for &p in &cells {
            world.carve(p);
        }
        cells.sort();
        return Some(PlacedRoom {
            centre: Pos::new(x0 + w / 2, y, z0 + d / 2),
            cells,
        });
    }
    None
}

/// Carve `p` as a passage cell (recording it unless it belongs to
/// a feature room).
fn carve_passage(
    world: &mut World,
    network: &mut BTreeSet<Pos>,
    features: &HashSet<Pos>,
    p: Pos,
) {
    if world.get(p).is_some_and(|c| c.is_solid()) {
        world.carve(p);
    }
    if world.get(p) == Some(Cell::Carved) && !features.contains(&p) {
        network.insert(p);
    }
}

/// Route one passage segment from `from` to `to`: a horizontal
/// run at `from`'s depth (BFS over the plan view, detouring
/// around `avoid` cells at that depth), then a vertical shaft
/// at the target's column. The shaft column is safe by the
/// room-spacing rule (target rooms sit at least 2 cells in plan
/// from any avoided room). A share of segments are widened to
/// 2 cells on their horizontal runs.
#[allow(clippy::too_many_arguments)]
fn route_segment(
    world: &mut World,
    rng: &mut Rng,
    network: &mut BTreeSet<Pos>,
    features: &HashSet<Pos>,
    avoid: &HashSet<Pos>,
    from: Pos,
    to: Pos,
    widen_pct: u64,
) {
    // Horizontal plan: BFS from (from.x, from.z) to (to.x, to.z).
    let blocked = |x: i32, z: i32| -> bool {
        x < 1 || x > FLOOR_W as i32 - 2 || z < 1 || z > FLOOR_D as i32 - 2
            || avoid.contains(&Pos::new(x, from.y, z))
    };
    let mut plan: Vec<(i32, i32)> = Vec::new();
    if (from.x, from.z) != (to.x, to.z) {
        let mut prev: HashMap<(i32, i32), (i32, i32)> = HashMap::new();
        let mut seen: HashSet<(i32, i32)> = HashSet::new();
        let mut queue: VecDeque<(i32, i32)> = VecDeque::new();
        seen.insert((from.x, from.z));
        queue.push_back((from.x, from.z));
        let mut found = false;
        while let Some(cur) = queue.pop_front() {
            if cur == (to.x, to.z) {
                found = true;
                break;
            }
            for (dx, dz) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let n = (cur.0 + dx, cur.1 + dz);
                if seen.contains(&n) || blocked(n.0, n.1) {
                    continue;
                }
                seen.insert(n);
                prev.insert(n, cur);
                queue.push_back(n);
            }
        }
        if found {
            let mut cur = (to.x, to.z);
            plan.push(cur);
            while cur != (from.x, from.z) {
                cur = prev[&cur];
                plan.push(cur);
            }
            plan.reverse();
        } else {
            // Should not happen (the plan view is mostly open
            // rock); fall back to a straight axis run so the
            // segment still connects.
            let mut cur = (from.x, from.z);
            plan.push(cur);
            while cur.0 != to.x {
                cur.0 += (to.x - cur.0).signum();
                plan.push(cur);
            }
            while cur.1 != to.z {
                cur.1 += (to.z - cur.1).signum();
                plan.push(cur);
            }
        }
    }
    let widen = rng.below(100) < widen_pct;
    let mut prev_step: Option<(i32, i32)> = None;
    for &(x, z) in &plan {
        let p = Pos::new(x, from.y, z);
        carve_passage(world, network, features, p);
        if widen {
            if let Some((px, _pz)) = prev_step {
                // Widen perpendicular to the direction of travel.
                let cand = if px != x {
                    Pos::new(x, from.y, z + 1)
                } else {
                    Pos::new(x + 1, from.y, z)
                };
                if cand.x <= FLOOR_W as i32 - 2
                    && cand.z <= FLOOR_D as i32 - 2
                    && !avoid.contains(&cand)
                    && !features.contains(&cand)
                {
                    carve_passage(world, network, features, cand);
                }
            }
        }
        prev_step = Some((x, z));
    }
    // The shaft at the target's column.
    let mut y = from.y;
    while y != to.y {
        y += (to.y - y).signum();
        carve_passage(world, network, features, Pos::new(to.x, y, to.z));
    }
}

/// A dead-end spur off the network: a short blind passage that
/// stops before breaching anything sealed.
fn carve_spur(
    world: &mut World,
    rng: &mut Rng,
    network: &mut BTreeSet<Pos>,
    features: &HashSet<Pos>,
    avoid: &HashSet<Pos>,
    starts: &[Pos],
    len_range: (i32, i32),
) {
    if starts.is_empty() {
        return;
    }
    let start = starts[rng.below(starts.len() as u64) as usize];
    let (dx, dz) = [(1, 0), (-1, 0), (0, 1), (0, -1)][rng.below(4) as usize];
    let len = len_range.0 + rng.below((len_range.1 - len_range.0 + 1) as u64) as i32;
    let mut cur = start;
    for _ in 0..len {
        let next = Pos::new(cur.x + dx, cur.y, cur.z + dz);
        if next.x < 1 || next.x > FLOOR_W as i32 - 2 || next.z < 1 || next.z > FLOOR_D as i32 - 2 {
            break;
        }
        if world.get(next) == Some(Cell::Carved) || avoid.contains(&next) || features.contains(&next)
        {
            break;
        }
        carve_passage(world, network, features, next);
        cur = next;
    }
}

/// A rock cell a vein may grow into: still plain stone, and not
/// touching any previously placed vein (veins stay distinct).
fn vein_ok<'a>(all: &'a HashSet<Pos>) -> impl Fn(&World, Pos) -> bool + 'a {
    move |w: &World, p: Pos| {
        w.get(p) == Some(Cell::Stone) && !p.neighbors6().iter().any(|n| all.contains(n))
    }
}

/// Grow a cluster of `kind` cells from `start`, through cells
/// `can_take` accepts. Used for veins, fungal clusters, and
/// hazard pockets — all embedded in solid rock.
fn grow_cluster(
    world: &mut World,
    rng: &mut Rng,
    start: Pos,
    kind: Cell,
    target: usize,
    can_take: &dyn Fn(&World, Pos) -> bool,
) -> Vec<Pos> {
    if !can_take(world, start) {
        return Vec::new();
    }
    world.set(start, kind);
    let mut cells = vec![start];
    let mut tries = 0;
    while cells.len() < target && tries < 60 {
        tries += 1;
        let base = cells[rng.below(cells.len() as u64) as usize];
        let n = base.neighbors6()[rng.below(6) as usize];
        if n.x < 1 || n.x > FLOOR_W as i32 - 2 || n.z < 1 || n.z > FLOOR_D as i32 - 2 {
            continue;
        }
        if cells.contains(&n) || !can_take(world, n) {
            continue;
        }
        world.set(n, kind);
        cells.push(n);
    }
    cells.sort();
    cells
}

// ---------------------------------------------------------------------------
// The generator
// ---------------------------------------------------------------------------

/// Generate one floor. Pure: the same `(world_seed, floor_index)`
/// always yields the same floor, however often and in whatever
/// order floors are generated.
///
/// The floor's guarantees (the descent's minimum network
/// distance, the on-network den minimums, sealed cavities stay
/// sealed, connected cavities stay reachable) are enforced by
/// **deterministic sampling**: layouts are drawn from a stream
/// derived from the floor seed until one meets every guarantee
/// — up to 16 attempts, keeping the best (longest descent trek
/// among the hard-invariant-satisfying attempts) if none
/// qualifies. The attempt stream is derived from the same floor
/// seed, so the chosen layout is still a pure function of
/// `(world_seed, floor_index)`.
pub fn generate_floor(world_seed: u64, floor_index: u32) -> Floor {
    let theme = theme_for_floor(floor_index);
    let mut master = gen_rng(floor_seed(world_seed, floor_index));
    let mut best: Option<Floor> = None;
    let mut best_key = (false, 0u32);
    for attempt in 0..16 {
        let attempt_seed = master.next_u64();
        let floor = generate_once(attempt_seed, floor_index, attempt);
        if floor_meets_guarantees(&floor, &theme) {
            return floor;
        }
        let key = (
            floor_hard_invariants_hold(&floor),
            floor.layout.descent_network_distance,
        );
        if best.is_none() || key > best_key {
            best_key = key;
            best = Some(floor);
        }
    }
    best.expect("at least one attempt is generated")
}

/// The guarantees a sampled layout must meet to be accepted on
/// the spot (see `generate_floor`).
fn floor_meets_guarantees(floor: &Floor, theme: &Theme) -> bool {
    if floor.layout.descent_network_distance < theme.descent_min_network_distance {
        return false;
    }
    if !floor_hard_invariants_hold(floor) {
        return false;
    }
    let dist = carved_distances(&floor.world, ENTRY);
    let dens_on = floor
        .layout
        .cavities
        .iter()
        .filter(|c| c.den && c.connected)
        .filter(|c| {
            floor
                .world
                .idx(c.centre)
                .map(|i| dist[i])
                .is_some_and(|d| d >= theme.den_min_network_distance as i32)
        })
        .count();
    dens_on >= theme.dens_on_network
}

/// The invariants that must hold for *every* generated floor,
/// accepted attempt or fallback: the network reaches what it
/// claims to connect, and sealed cavities stay sealed.
fn floor_hard_invariants_hold(floor: &Floor) -> bool {
    let dist = carved_distances(&floor.world, ENTRY);
    let reached = |p: Pos| floor.world.idx(p).map(|i| dist[i]).is_some_and(|d| d >= 0);
    if !reached(floor.layout.descent) {
        return false;
    }
    floor.layout.cavities.iter().all(|c| {
        if c.connected {
            reached(c.centre)
        } else {
            !reached(c.centre)
        }
    })
}

fn generate_once(seed: u64, floor_index: u32, attempt: u32) -> Floor {
    let theme = theme_for_floor(floor_index);
    let mut rng = gen_rng(seed);
    let mut world = World::new(FLOOR_W, FLOOR_H, FLOOR_D, Cell::Stone);
    for x in 0..FLOOR_W as i32 {
        for z in 0..FLOOR_D as i32 {
            for y in 0..theme.cap_depth {
                world.set(Pos::new(x, y, z), Cell::Earth);
            }
        }
    }

    let mut reserved: HashSet<Pos> = HashSet::new();
    let mut features: HashSet<Pos> = HashSet::new();

    // -- The entry camp: the existing starting room, unchanged. --
    let mut camp_cells = Vec::new();
    for x in 2..=6 {
        for z in 3..=5 {
            let p = Pos::new(x, CAMP_Y, z);
            world.carve(p);
            camp_cells.push(p);
        }
    }
    reserve(&mut reserved, &camp_cells);
    features.extend(camp_cells.iter().copied());

    // -- The descent cavern: far east, deep, on the network. --
    let descent = Pos::new(
        17 + rng.below(4) as i32,
        7 + rng.below(3) as i32,
        2 + rng.below(4) as i32,
    );
    let mut descent_cavern = Vec::new();
    for x in descent.x - 1..=descent.x + 1 {
        for z in descent.z - 1..=descent.z + 1 {
            let p = Pos::new(x, descent.y, z);
            world.carve(p);
            descent_cavern.push(p);
        }
    }
    descent_cavern.sort();
    reserve(&mut reserved, &descent_cavern);
    features.extend(descent_cavern.iter().copied());
    // No cavity may share the descent cavern's plan column
    // (see `plan_halo`): the final approach must be the only
    // way in, discovered by following the passages.
    let plan_descent = plan_halo(&descent_cavern);

    // -- Natural cavities: a connected set placed west→east in
    // zones (so the network's trek lengthens naturally), plus a
    // sealed minority left in the rock. --
    let whole = ((2, 20), (4, GEN_MAX_Y), (1, 5));
    let zones: [((i32, i32), (i32, i32), (i32, i32)); 5] = [
        ((2, 7), (4, 6), (1, 5)),   // A — near the camp
        ((8, 13), (4, 8), (1, 5)),  // B — mid floor
        ((8, 13), (4, 8), (1, 5)),  // B
        ((14, 20), (5, 9), (1, 5)), // C — far
        ((14, 20), (5, 9), (1, 5)), // C
    ];
    let mut cavities: Vec<Cavity> = Vec::new();
    for i in 0..theme.connected_cavities {
        let (xr, yr, zr) = zones[i.min(zones.len() - 1)];
        let placed = place_room(
            &mut world, &mut rng, &reserved, &plan_descent, xr, yr, zr,
            theme.cavity_w, theme.cavity_d, 300,
        )
        .or_else(|| {
            place_room(
                &mut world, &mut rng, &reserved, &plan_descent, whole.0, whole.1, whole.2,
                theme.cavity_w, theme.cavity_d, 300,
            )
        });
        if let Some(room) = placed {
            reserve(&mut reserved, &room.cells);
            features.extend(room.cells.iter().copied());
            cavities.push(Cavity {
                centre: room.centre,
                cells: room.cells,
                connected: true,
                den: false,
                critter: None,
            });
        }
    }
    // The detour cavity: far west and deep. The chain visits it
    // last before the descent, so the final approach crosses
    // the whole floor — the descent's network distance is long
    // by construction, not by luck.
    let mut detour_centre: Option<Pos> = None;
    if let Some(room) = place_room(
        &mut world, &mut rng, &reserved, &plan_descent, (2, 5), (7, 9), (1, 5),
        theme.cavity_w, theme.cavity_d, 600,
    ) {
        reserve(&mut reserved, &room.cells);
        features.extend(room.cells.iter().copied());
        detour_centre = Some(room.centre);
        cavities.push(Cavity {
            centre: room.centre,
            cells: room.cells,
            connected: true,
            den: false,
            critter: None,
        });
    }
    // Sealed cavities additionally respect plan separation from
    // the camp, the descent, and every connected room — that is
    // what "sealed" means against shafts and runs alike.
    let mut plan_off = plan_descent.clone();
    plan_off.extend(plan_halo(&camp_cells));
    for c in &cavities {
        plan_off.extend(plan_halo(&c.cells));
    }
    let mut off_network: Vec<Cavity> = Vec::new();
    for _ in 0..theme.off_network_cavities {
        if let Some(room) = place_room(
            &mut world, &mut rng, &reserved, &plan_off, whole.0, whole.1, whole.2,
            theme.cavity_w, theme.cavity_d, 300,
        ) {
            reserve(&mut reserved, &room.cells);
            features.extend(room.cells.iter().copied());
            off_network.push(Cavity {
                centre: room.centre,
                cells: room.cells,
                connected: false,
                den: false,
                critter: None,
            });
        }
    }

    // -- The passage network: chain the nodes (camp → cavities
    // → detour → descent cavern), add a loop link, then
    // dead-end spurs. --
    // Chain order: among the last two pre-detour cavities, visit
    // the one *farther* from the descent first — the trek
    // swings wide before doubling back west to the detour.
    let mut chain: Vec<Pos> = cavities
        .iter()
        .map(|c| c.centre)
        .filter(|c| Some(*c) != detour_centre)
        .collect();
    if chain.len() >= 2 {
        let n = chain.len();
        if manhattan(chain[n - 2], descent) < manhattan(chain[n - 1], descent) {
            chain.swap(n - 2, n - 1);
        }
    }
    let mut nodes: Vec<Pos> = vec![CAMP_CENTRE];
    nodes.extend(chain);
    if let Some(d) = detour_centre {
        nodes.push(d);
    }
    nodes.push(descent);

    // Cells no passage may breach: the sealed cavities and (for
    // every segment except the final approach) the descent
    // cavern — each with its halo.
    let mut off_limits: HashSet<Pos> = HashSet::new();
    for c in &off_network {
        reserve(&mut off_limits, &c.cells);
    }
    let off_limits_no_descent = off_limits.clone();
    reserve(&mut off_limits, &descent_cavern);

    let mut network: BTreeSet<Pos> = BTreeSet::new();
    let mut links: Vec<(usize, usize)> = Vec::new();
    for i in 0..nodes.len() - 1 {
        let avoid = if i + 1 == nodes.len() - 1 {
            &off_limits_no_descent
        } else {
            &off_limits
        };
        route_segment(
            &mut world, &mut rng, &mut network, &features, avoid,
            nodes[i], nodes[i + 1], theme.widen_pct,
        );
        links.push((i, i + 1));
    }
    for _ in 0..theme.loop_edges {
        if nodes.len() >= 4 {
            let i = rng.below((nodes.len() - 3) as u64) as usize;
            route_segment(
                &mut world, &mut rng, &mut network, &features, &off_limits,
                nodes[i], nodes[i + 2], theme.widen_pct,
            );
            links.push((i, i + 2));
        }
    }
    let mut spur_starts: Vec<Pos> = network.iter().copied().collect();
    spur_starts.extend(cavities.iter().map(|c| c.centre));
    for _ in 0..theme.spurs {
        carve_spur(
            &mut world, &mut rng, &mut network, &features, &off_limits,
            &spur_starts, theme.spur_len,
        );
    }

    // -- Measure the network honestly, on the generated grid. --
    let dist = carved_distances(&world, ENTRY);
    let descent_network_distance = world
        .idx(descent)
        .map(|i| dist[i])
        .filter(|&d| d >= 0)
        .unwrap_or(0) as u32;

    // -- Dens: the farthest qualifying connected cavities (the
    // owner's on-network teeth), plus a sealed minority. --
    let mut den_candidates: Vec<(i32, Pos)> = cavities
        .iter()
        .map(|c| {
            (
                world.idx(c.centre).map(|i| dist[i]).unwrap_or(-1),
                c.centre,
            )
        })
        .filter(|(d, _)| *d >= theme.den_min_network_distance as i32)
        .collect();
    den_candidates.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    let den_centres: Vec<Pos> = den_candidates
        .iter()
        .take(theme.dens_on_network)
        .map(|(_, c)| *c)
        .collect();
    for c in cavities.iter_mut() {
        if den_centres.contains(&c.centre) {
            c.den = true;
            c.critter = Some(theme.critter_kinds[0]);
        }
    }
    if theme.dens_off_network > 0 {
        if let Some(c) = off_network.first_mut() {
            c.den = true;
            c.critter = Some(theme.critter_kinds[0]);
        }
    }
    cavities.extend(off_network);
    cavities.sort_by_key(|c| c.centre);

    // -- Veins: a starter face near the network's first stretch,
    // deeper faces beyond it, and pockets (the richest included)
    // sealed in the rock. --
    let primary = theme.resource_cells[0];
    let yield_of = |cell: Cell| match cell {
        Cell::FungalNode => YieldKind::FungalOil,
        _ => YieldKind::Ore,
    };
    let mut vein_cells_all: HashSet<Pos> = HashSet::new();
    let mut veins: Vec<Vein> = Vec::new();
    let mut faces: Vec<Face> = Vec::new();
    // Stone cells with a carved neighbour whose network distance
    // falls in [lo, hi] — face candidates.
    let face_candidates = |world: &World, dist: &[i32], lo: i32, hi: i32| -> Vec<(Pos, Pos)> {
        let mut out = Vec::new();
        for y in 4..=GEN_MAX_Y {
            for x in 1..FLOOR_W as i32 - 1 {
                for z in 1..FLOOR_D as i32 - 1 {
                    let p = Pos::new(x, y, z);
                    if world.get(p) != Some(Cell::Stone) {
                        continue;
                    }
                    let mut best: Option<(i32, Pos)> = None;
                    for n in p.neighbors6() {
                        if world.get(n) == Some(Cell::Carved) {
                            let d = world.idx(n).map(|i| dist[i]).unwrap_or(-1);
                            if d >= lo && d <= hi && best.map_or(true, |(bd, _)| d < bd) {
                                best = Some((d, n));
                            }
                        }
                    }
                    if let Some((_, stand)) = best {
                        out.push((p, stand));
                    }
                }
            }
        }
        out
    };
    let try_face = |world: &mut World,
                        rng: &mut Rng,
                        vein_cells_all: &mut HashSet<Pos>,
                        veins: &mut Vec<Vein>,
                        faces: &mut Vec<Face>,
                        lo: i32,
                        hi: i32|
     -> bool {
        let candidates = face_candidates(world, &dist, lo, hi);
        if candidates.is_empty() {
            return false;
        }
        for _ in 0..24 {
            let (rock, stand) = candidates[rng.below(candidates.len() as u64) as usize];
            let target = theme.vein_cells.0
                + rng.below((theme.vein_cells.1 - theme.vein_cells.0 + 1) as u64) as usize;
            let cells = grow_cluster(world, rng, rock, primary, target, &vein_ok(vein_cells_all));
            if cells.len() < 2 {
                // Roll the failed vein back to plain rock so the
                // layout accounts for every resource cell placed.
                for p in &cells {
                    world.set(*p, Cell::Stone);
                }
                continue;
            }
            vein_cells_all.extend(cells.iter().copied());
            let ore_units = 6 * cells.len() as u32;
            faces.push(Face {
                rock,
                stand,
                ore: ore_units,
                cache: 0,
                yield_kind: yield_of(primary),
            });
            veins.push(Vein { cells, is_face: true, ore_units });
            return true;
        }
        false
    };
    // The starter face: near enough to matter, far enough that
    // the camp lantern alone doesn't reach it (the S1 refusal
    // beat belongs to generated floors too).
    try_face(&mut world, &mut rng, &mut vein_cells_all, &mut veins, &mut faces, 8, 14);
    for _ in 1..theme.face_veins_max {
        try_face(&mut world, &mut rng, &mut vein_cells_all, &mut veins, &mut faces, 12, 80);
    }
    // Pockets: the richest first, in deep rock with no carved
    // neighbour; the rest anywhere in the rock.
    let try_pocket = |world: &mut World,
                          rng: &mut Rng,
                          vein_cells_all: &mut HashSet<Pos>,
                          veins: &mut Vec<Vein>,
                          target: usize,
                          deep_only: bool|
     -> bool {
        let mut candidates = Vec::new();
        for y in 4..=GEN_MAX_Y {
            for x in 1..FLOOR_W as i32 - 1 {
                for z in 1..FLOOR_D as i32 - 1 {
                    let p = Pos::new(x, y, z);
                    if world.get(p) != Some(Cell::Stone) {
                        continue;
                    }
                    if deep_only && (p.x < 14 || p.y < 6) {
                        continue;
                    }
                    if p.neighbors6().iter().any(|n| world.get(*n) == Some(Cell::Carved)) {
                        continue;
                    }
                    candidates.push(p);
                }
            }
        }
        if candidates.is_empty() {
            return false;
        }
        for _ in 0..24 {
            let start = candidates[rng.below(candidates.len() as u64) as usize];
            let cells = grow_cluster(world, rng, start, primary, target, &vein_ok(vein_cells_all));
            if cells.len() < 2 {
                for p in &cells {
                    world.set(*p, Cell::Stone);
                }
                continue;
            }
            vein_cells_all.extend(cells.iter().copied());
            veins.push(Vein { cells, is_face: false, ore_units: 0 });
            return true;
        }
        false
    };
    try_pocket(
        &mut world, &mut rng, &mut vein_cells_all, &mut veins,
        theme.rich_vein_cells, true,
    );
    while veins.len() < theme.veins {
        let target = theme.vein_cells.0
            + rng.below((theme.vein_cells.1 - theme.vein_cells.0 + 1) as u64) as usize;
        if !try_pocket(&mut world, &mut rng, &mut vein_cells_all, &mut veins, target, false) {
            break;
        }
    }
    veins.sort_by_key(|v| v.cells.first().copied().unwrap_or(ENTRY));
    faces.sort_by_key(|f| f.rock);

    // -- Fungal node clusters (stub bands' second resource). --
    if theme.fungal_node_clusters > 0 {
        let mut placed_clusters = 0;
        let mut guard = 0;
        while placed_clusters < theme.fungal_node_clusters && guard < 200 {
            guard += 1;
            // Sorted before sampling: a HashSet's iteration
            // order is not stable between calls, and generation
            // must be a pure function of the seed.
            let mut near: Vec<Pos> = features
                .iter()
                .copied()
                .filter(|f| (4..=GEN_MAX_Y).contains(&f.y))
                .collect();
            near.sort();
            if near.is_empty() {
                break;
            }
            let anchor = near[rng.below(near.len() as u64) as usize];
            let start = Pos::new(
                (anchor.x + rng.below(7) as i32 - 3).clamp(1, FLOOR_W as i32 - 2),
                anchor.y,
                (anchor.z + rng.below(5) as i32 - 2).clamp(1, FLOOR_D as i32 - 2),
            );
            let cells = grow_cluster(&mut world, &mut rng, start, Cell::FungalNode, 2, &|w: &World, p: Pos| {
                w.get(p) == Some(Cell::Stone)
            });
            if !cells.is_empty() {
                placed_clusters += 1;
            }
        }
    }

    // -- Hazard pockets: loose rock anywhere in the walls, bad
    // air pooled deep. Embedded kinds the sim does not yet
    // simulate (see world::Cell docs). --
    let mut hazards: Vec<HazardPocket> = Vec::new();
    let place_hazards = |world: &mut World,
                             rng: &mut Rng,
                             hazards: &mut Vec<HazardPocket>,
                             count: usize,
                             size: (usize, usize),
                             kind: Cell,
                             hk: HazardKind,
                             deep: bool,
                             min_y: i32| {
        for _ in 0..count {
            let mut candidates = Vec::new();
            for y in 3..=GEN_MAX_Y {
                for x in 1..FLOOR_W as i32 - 1 {
                    for z in 1..FLOOR_D as i32 - 1 {
                        let p = Pos::new(x, y, z);
                        if world.get(p) != Some(Cell::Stone) {
                            continue;
                        }
                        if deep && p.y < 6 {
                            continue;
                        }
                        if manhattan(p, ENTRY) < 6 || chebyshev(p, descent) < 2 {
                            continue;
                        }
                        candidates.push(p);
                    }
                }
            }
            if candidates.is_empty() {
                break;
            }
            let start = candidates[rng.below(candidates.len() as u64) as usize];
            let target = size.0 + rng.below((size.1 - size.0 + 1) as u64) as usize;
            // The depth rule binds the whole pocket, not just
            // its seed cell: growth may not climb above `min_y`
            // (bad air pools deep — it never leaks upward).
            let cells = grow_cluster(world, rng, start, kind, target, &|w: &World, p: Pos| {
                p.y >= min_y && w.get(p) == Some(Cell::Stone)
            });
            for p in cells {
                hazards.push(HazardPocket { pos: p, kind: hk });
            }
        }
    };
    place_hazards(
        &mut world, &mut rng, &mut hazards,
        theme.loose_count, theme.loose_size, Cell::Loose, HazardKind::LooseRock, false, 0,
    );
    place_hazards(
        &mut world, &mut rng, &mut hazards,
        theme.bad_air_count, theme.bad_air_size, Cell::BadAir, HazardKind::BadAir, true, 6,
    );
    hazards.sort_by_key(|h| h.pos);

    // -- Dressing anchors: a few per cavity, and the stairs
    // themselves in the descent cavern. --
    let mut dressing: Vec<DressingAnchor> = Vec::new();
    let dress_room = |rng: &mut Rng, dressing: &mut Vec<DressingAnchor>, cells: &[Pos]| {
        if cells.is_empty() || theme.dressing_kinds.is_empty() {
            return;
        }
        let n = (1 + rng.below(3) as usize).min(cells.len());
        let mut pool: Vec<Pos> = cells.to_vec();
        for _ in 0..n {
            let idx = rng.below(pool.len() as u64) as usize;
            let pos = pool.remove(idx);
            let kind = theme.dressing_kinds[rng.below(theme.dressing_kinds.len() as u64) as usize];
            dressing.push(DressingAnchor { pos, kind });
        }
    };
    for c in &cavities {
        dress_room(&mut rng, &mut dressing, &c.cells);
    }
    dressing.push(DressingAnchor {
        pos: descent,
        kind: DressingKind::DescentStairs,
    });
    dress_room(&mut rng, &mut dressing, &descent_cavern);
    dressing.sort_by_key(|a| (a.pos, a.kind));

    let layout = FloorLayout {
        floor_index,
        band: theme.band,
        entry: ENTRY,
        descent,
        descent_cavern,
        descent_network_distance,
        cavities,
        nodes,
        links,
        network_cells: network.into_iter().collect(),
        veins,
        hazards,
        dressing,
        faces,
        generation_attempts: attempt,
    };
    Floor { world, layout }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seed_mix_varies_with_seed_and_floor() {
        assert_ne!(floor_seed(1, 1), floor_seed(2, 1));
        assert_ne!(floor_seed(1, 1), floor_seed(1, 2));
        assert_eq!(floor_seed(7, 3), floor_seed(7, 3));
    }

    #[test]
    fn bands_cycle_below_the_magma_roots() {
        assert_eq!(band_for_floor(1), Band::Shallows);
        assert_eq!(band_for_floor(2), Band::FungalReaches);
        assert_eq!(band_for_floor(5), Band::MagmaRoots);
        assert_eq!(band_for_floor(6), Band::FungalReaches);
        assert_eq!(band_for_floor(9), Band::MagmaRoots);
        assert!(theme_for_floor(1).built);
        assert!(!theme_for_floor(2).built);
    }
}
