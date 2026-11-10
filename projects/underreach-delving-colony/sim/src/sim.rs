//! Simulation core: lanterns and light, pathing through the lit
//! network, one delver running delve → haul → convert, the Deep
//! Ledger, and canonical save/load with a state hash.
//!
//! The design rules encoded here (owner decisions, see
//! docs/MUSE_HANDOFF.md):
//! - Delvers path **only** through lit, carved cells. The lantern
//!   network is the navigation graph.
//! - Placing light records **first light** per depth in the Ledger.
//! - Lantern fuel burns; a dead lantern's light goes with it (the seed
//!   of the rescue clock).

use std::collections::{BTreeSet, HashMap, HashSet, VecDeque};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

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
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct LedgerEntry {
    pub tick: u64,
    pub kind: LedgerKind,
    pub detail: String,
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
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Delver {
    pub name: String,
    pub pos: Pos,
    /// 0..100 — spent by work, restored by rest.
    pub energy: f32,
    /// 0..100 — 100 is fully fed; restored by eating from stores.
    pub hunger: f32,
    pub mining_xp: u32,
    pub hauling_xp: u32,
    pub carrying: u32,
    pub state: DelverState,
    pub path: Vec<Pos>,
    pub mine_progress: f32,
    pub blocked_logged: bool,
}

impl Delver {
    pub fn mining_level(&self) -> u32 {
        self.mining_xp / 10
    }
    pub fn capacity(&self) -> u32 {
        4
    }
}

#[derive(Clone, Copy, Default, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct Stores {
    pub ore: u32,
    pub goods: u32,
    pub food: u32,
}

// ---------------------------------------------------------------------------
// Sim
// ---------------------------------------------------------------------------

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Sim {
    pub world: World,
    /// Kept sorted by position so serialization is canonical.
    pub lanterns: Vec<LanternEntry>,
    pub delver: Delver,
    pub stockpile: Pos,
    pub bed: Pos,
    /// The ore cell being worked, and the carved cell the delver
    /// stands on to work it.
    pub face: Pos,
    pub face_stand: Pos,
    pub face_ore: u32,
    pub stores: Stores,
    pub ledger: Vec<LedgerEntry>,
    pub lit_depths: BTreeSet<i32>,
    pub tick_count: u64,
    #[serde(skip)]
    pub lit: Vec<bool>,
}

impl Sim {
    pub fn new(
        world: World,
        delver: Delver,
        stockpile: Pos,
        bed: Pos,
        face: Pos,
        face_stand: Pos,
        face_ore: u32,
        stores: Stores,
    ) -> Self {
        let mut sim = Self {
            world,
            lanterns: Vec::new(),
            delver,
            stockpile,
            bed,
            face,
            face_stand,
            face_ore,
            stores,
            ledger: Vec::new(),
            lit_depths: BTreeSet::new(),
            tick_count: 0,
            lit: Vec::new(),
        };
        sim.refresh_light();
        sim.log(
            LedgerKind::ColonyFounded,
            format!("{} takes the lantern down", sim.delver.name),
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
    pub fn place_lantern(&mut self, pos: Pos, tier: u8, fuel: f32) {
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
        self.tick_delver();
        self.tick_count += 1;
    }

    fn start_path(&mut self, to: Pos) -> bool {
        match find_path(&self.world, &self.lit, self.delver.pos, to) {
            Some(path) => {
                self.delver.path = path;
                true
            }
            None => false,
        }
    }

    /// One movement step along the current path. Returns true on arrival.
    fn follow_path(&mut self) -> bool {
        if let Some(next) = self.delver.path.first().copied() {
            self.delver.pos = next;
            self.delver.path.remove(0);
        }
        self.delver.path.is_empty()
    }

    /// The camp decision, made whenever the delver is at camp with no
    /// active job: eat if hungry, rest if spent, otherwise go to work —
    /// or discover the dark says no.
    fn decide_from_camp(&mut self) {
        if self.delver.hunger < 40.0 && self.stores.food > 0 {
            self.delver.state = DelverState::Eating;
            return;
        }
        if self.delver.energy < 30.0 {
            if self.start_path(self.bed) {
                self.delver.state = DelverState::ToBed;
            } else {
                self.delver.state = DelverState::Resting;
            }
            return;
        }
        if self.face_ore == 0 {
            self.delver.state = DelverState::Idle;
            return;
        }
        if self.start_path(self.face_stand) {
            self.delver.state = DelverState::ToFace;
            self.delver.blocked_logged = false;
        } else {
            self.delver.state = DelverState::Blocked;
            if !self.delver.blocked_logged {
                self.delver.blocked_logged = true;
                self.log(
                    LedgerKind::RouteBlocked,
                    format!(
                        "{} cannot reach the face — the way is dark",
                        self.delver.name
                    ),
                );
            }
        }
    }

    fn tick_delver(&mut self) {
        // Needs decay by exertion.
        let exertion = match self.delver.state {
            DelverState::ToFace
            | DelverState::Mining
            | DelverState::ToCamp
            | DelverState::ToBed => 0.08,
            DelverState::Resting => 0.0,
            _ => 0.02,
        };
        if self.delver.state != DelverState::Resting {
            self.delver.energy = (self.delver.energy - exertion).clamp(0.0, 100.0);
        }
        if self.delver.state != DelverState::Eating {
            self.delver.hunger = (self.delver.hunger - 0.02).clamp(0.0, 100.0);
        }

        match self.delver.state {
            DelverState::Idle => self.decide_from_camp(),
            DelverState::Blocked => {
                // Retry: home if carrying, the face otherwise.
                let (target, next) = if self.delver.carrying > 0 {
                    (self.stockpile, DelverState::ToCamp)
                } else {
                    (self.face_stand, DelverState::ToFace)
                };
                if self.start_path(target) {
                    self.delver.state = next;
                    self.delver.blocked_logged = false;
                }
            }
            DelverState::ToFace => {
                if self.follow_path() {
                    self.delver.state = DelverState::Mining;
                }
            }
            DelverState::Mining => {
                let rate = 0.2 + 0.04 * self.delver.mining_level() as f32;
                self.delver.mine_progress += rate;
                while self.delver.mine_progress >= 1.0
                    && self.face_ore > 0
                    && self.delver.carrying < self.delver.capacity()
                {
                    self.delver.mine_progress -= 1.0;
                    self.face_ore -= 1;
                    self.delver.carrying += 1;
                    self.delver.mining_xp += 1;
                }
                if self.delver.carrying >= self.delver.capacity() || self.face_ore == 0 {
                    if self.start_path(self.stockpile) {
                        self.delver.state = DelverState::ToCamp;
                    } else {
                        self.delver.state = DelverState::Blocked;
                    }
                }
            }
            DelverState::ToCamp => {
                if self.follow_path() {
                    self.delver.state = DelverState::Converting;
                }
            }
            DelverState::Converting => {
                let amount = self.delver.carrying;
                if amount > 0 {
                    self.delver.carrying = 0;
                    self.delver.hauling_xp += amount;
                    self.stores.ore += amount;
                    self.log(
                        LedgerKind::HaulDelivered,
                        format!("{} hauled {amount} ore to the stockpile", self.delver.name),
                    );
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
                self.decide_from_camp();
            }
            DelverState::ToBed => {
                if self.follow_path() {
                    self.delver.state = DelverState::Resting;
                }
            }
            DelverState::Resting => {
                self.delver.energy = (self.delver.energy + 2.5).clamp(0.0, 100.0);
                if self.delver.energy >= 100.0 {
                    self.decide_from_camp();
                }
            }
            DelverState::Eating => {
                if self.stores.food > 0 {
                    self.stores.food -= 1;
                    self.delver.hunger = 100.0;
                }
                self.decide_from_camp();
            }
        }
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
