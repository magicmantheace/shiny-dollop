//! The scripted S1 scenario: a small Shallows colony — camp chamber,
//! shaft, tunnel, ore face. The tunnel starts carved but **unlit**:
//! the face is unreachable until the player extends the lantern
//! network. Used by the scenario binary and the acceptance tests.

use crate::sim::{Delver, DelverState, Sim, Stores};
use crate::world::{Cell, Pos, World};

pub const CAMP_LANTERN: Pos = Pos { x: 4, y: 3, z: 4 };
pub const SHAFT_LANTERN: Pos = Pos { x: 4, y: 7, z: 4 };
pub const TUNNEL_LANTERN_A: Pos = Pos { x: 10, y: 8, z: 4 };
pub const TUNNEL_LANTERN_B: Pos = Pos { x: 13, y: 8, z: 4 };

pub fn build_scenario() -> Sim {
    let mut world = World::new(24, 12, 8, Cell::Stone);
    for x in 0..24 {
        for z in 0..8 {
            world.set(Pos::new(x, 0, z), Cell::Earth);
            world.set(Pos::new(x, 1, z), Cell::Earth);
        }
    }
    // Camp chamber at depth 3.
    for x in 2..=6 {
        for z in 3..=5 {
            world.carve(Pos::new(x, 3, z));
        }
    }
    // Shaft down from camp to depth 8.
    for y in 4..=8 {
        world.carve(Pos::new(4, y, 4));
    }
    // Tunnel along depth 8 to the face.
    for x in 4..=14 {
        world.carve(Pos::new(x, 8, 4));
    }
    world.set(Pos::new(15, 8, 4), Cell::Ore);
    world.set(Pos::new(16, 8, 4), Cell::Ore);

    let delver = Delver {
        name: "Bram".to_string(),
        pos: Pos::new(3, 3, 4),
        energy: 100.0,
        hunger: 100.0,
        mining_xp: 0,
        hauling_xp: 0,
        carrying: 0,
        state: DelverState::Idle,
        path: Vec::new(),
        mine_progress: 0.0,
        blocked_logged: false,
    };

    let mut sim = Sim::new(
        world,
        delver,
        Pos::new(3, 3, 4),  // stockpile
        Pos::new(2, 3, 3),  // bed
        Pos::new(15, 8, 4), // ore face
        Pos::new(14, 8, 4), // stand cell in front of the face
        12,                 // ore in the face
        Stores {
            ore: 0,
            goods: 0,
            food: 10,
        },
    );
    // The camp lantern is pipe-fed for scenario purposes.
    sim.place_lantern(CAMP_LANTERN, 1, 1_000_000.0);
    sim
}

/// Extend the network down the shaft and along the tunnel — the
/// player's frontier work in phase 2.
pub fn light_the_way(sim: &mut Sim) {
    sim.place_lantern(SHAFT_LANTERN, 1, 5_000.0);
    sim.place_lantern(TUNNEL_LANTERN_A, 1, 5_000.0);
    sim.place_lantern(TUNNEL_LANTERN_B, 1, 5_000.0);
}
