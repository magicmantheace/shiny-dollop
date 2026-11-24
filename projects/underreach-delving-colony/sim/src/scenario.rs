//! Scripted scenarios.
//!
//! S1: a small Shallows colony — camp chamber, shaft, tunnel, ore
//! face. The tunnel starts carved but **unlit**: the face is
//! unreachable until the player extends the lantern network.
//!
//! S2: the same colony grown up — three delvers with jobs (miner,
//! farmer, hauler), mushroom plots at camp, and a recruitment
//! arrival scheduled while the colony looks viable.

use crate::gen::{carved_path, generate_floor, ENTRY, GATE};
use crate::sim::{CritterKind, Delver, Face, Job, Sim, Stores};
use crate::world::{Cell, Pos, World};

pub const CAMP_LANTERN: Pos = Pos { x: 4, y: 3, z: 4 };
pub const SHAFT_LANTERN: Pos = Pos { x: 4, y: 7, z: 4 };
pub const TUNNEL_LANTERN_A: Pos = Pos { x: 10, y: 8, z: 4 };
pub const TUNNEL_LANTERN_B: Pos = Pos { x: 13, y: 8, z: 4 };

fn shallows_world() -> World {
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
    world
}

fn the_face() -> Face {
    Face {
        rock: Pos::new(15, 8, 4),
        stand: Pos::new(14, 8, 4),
        ore: 12,
        cache: 0,
        yield_kind: crate::sim::YieldKind::Ore,
    }
}

pub fn build_scenario() -> Sim {
    let bram = Delver::new(0, "Bram", Pos::new(3, 3, 4), Job::Miner);
    let mut sim = Sim::new(
        shallows_world(),
        vec![bram],
        Pos::new(3, 3, 4), // stockpile
        vec![Pos::new(2, 3, 3)],
        vec![the_face()],
        Pos::new(6, 3, 4), // gate
        Stores {
            ore: 0,
            goods: 0,
            food: 10,
            fungal_oil: 0,
            masks: 0,
        },
        0x5EED_0001,
        u64::MAX, // the S1 scenario takes no recruits
        false,    // and the dark does not bite yet
    );
    // The camp lantern is pipe-fed for scenario purposes.
    sim.place_lantern(CAMP_LANTERN, 1, 1_000_000.0);
    sim
}

pub fn build_scenario_s2() -> Sim {
    let delvers = vec![
        Delver::new(0, "Bram", Pos::new(3, 3, 4), Job::Miner),
        Delver::new(1, "Sella", Pos::new(4, 3, 5), Job::Farmer),
        Delver::new(2, "Hale", Pos::new(4, 3, 3), Job::Hauler),
    ];
    let mut sim = Sim::new(
        shallows_world(),
        delvers,
        Pos::new(3, 3, 4), // stockpile
        vec![Pos::new(2, 3, 3), Pos::new(2, 3, 5), Pos::new(6, 3, 5)],
        vec![the_face()],
        Pos::new(6, 3, 4), // gate
        Stores {
            ore: 0,
            goods: 0,
            food: 12,
            fungal_oil: 0,
            masks: 0,
        },
        0x5EED_0002,
        1500, // first recruit is due at tick 1500 if the colony is fed
        false,
    );
    sim.place_lantern(CAMP_LANTERN, 1, 1_000_000.0);
    // Mushroom plots in the camp chamber.
    sim.plant_plot(Pos::new(5, 3, 3));
    sim.plant_plot(Pos::new(6, 3, 3));
    sim
}

/// S3: the S2 colony, a richer face, and a dark gallery running
/// parallel to the tunnel — carved, unlit, and connected. Things
/// come out of it.
pub fn build_scenario_s3() -> Sim {
    let mut world = shallows_world();
    // The parallel gallery at depth 8, z=6, with three connectors.
    for x in 8..=18 {
        world.carve(Pos::new(x, 8, 6));
    }
    for x in [8, 14, 18] {
        world.carve(Pos::new(x, 8, 5));
    }
    let delvers = vec![
        Delver::new(0, "Bram", Pos::new(3, 3, 4), Job::Miner),
        Delver::new(1, "Sella", Pos::new(4, 3, 5), Job::Farmer),
        Delver::new(2, "Hale", Pos::new(4, 3, 3), Job::Hauler),
    ];
    let mut face = the_face();
    face.ore = 40;
    let mut sim = Sim::new(
        world,
        delvers,
        Pos::new(3, 3, 4),
        vec![Pos::new(2, 3, 3), Pos::new(2, 3, 5), Pos::new(6, 3, 5)],
        vec![face],
        Pos::new(6, 3, 4),
        Stores {
            ore: 0,
            goods: 0,
            food: 12,
            fungal_oil: 0,
            masks: 0,
        },
        0x5EED_0003,
        1500,
        true, // the dark bites
    );
    sim.place_lantern(CAMP_LANTERN, 1, 1_000_000.0);
    sim.plant_plot(Pos::new(5, 3, 3));
    sim.plant_plot(Pos::new(6, 3, 3));
    sim
}

/// Extend the network down the shaft and along the tunnel — the
/// player's frontier work in phase 2.
pub fn light_the_way(sim: &mut Sim) {
    sim.place_lantern(SHAFT_LANTERN, 1, 5_000.0);
    sim.place_lantern(TUNNEL_LANTERN_A, 1, 5_000.0);
    sim.place_lantern(TUNNEL_LANTERN_B, 1, 5_000.0);
}

pub const DEEP_SHAFT_LANTERN: Pos = Pos { x: 4, y: 11, z: 4 };
pub const FUNGAL_LANTERN: Pos = Pos { x: 6, y: 14, z: 4 };

/// S5: the colony digs past the Shallows. A deep shaft drops from
/// the tunnel level to a fungal chamber at depth 14 — spore-bearing
/// air, fungal nodes to mine for oil, and the full gate set to test:
/// masks, a herbalist, and tier-2 lanterns that burn the oil.
pub fn build_scenario_s5() -> Sim {
    let mut world = World::new(24, 20, 8, Cell::Stone);
    for x in 0..24 {
        for z in 0..8 {
            world.set(Pos::new(x, 0, z), Cell::Earth);
            world.set(Pos::new(x, 1, z), Cell::Earth);
        }
    }
    for x in 2..=6 {
        for z in 3..=5 {
            world.carve(Pos::new(x, 3, z));
        }
    }
    for y in 4..=8 {
        world.carve(Pos::new(4, y, 4));
    }
    for x in 4..=14 {
        world.carve(Pos::new(x, 8, 4));
    }
    world.set(Pos::new(15, 8, 4), Cell::Ore);
    world.set(Pos::new(16, 8, 4), Cell::Ore);
    // The deep shaft: from the tunnel down to the fungal chamber.
    for y in 9..=14 {
        world.carve(Pos::new(4, y, 4));
    }
    // Fungal chamber at depth 14.
    for x in 2..=8 {
        for z in 3..=5 {
            world.carve(Pos::new(x, 14, z));
        }
    }
    world.set(Pos::new(8, 14, 4), Cell::FungalNode);
    world.set(Pos::new(8, 14, 3), Cell::FungalNode);

    let delvers = vec![
        Delver::new(0, "Bram", Pos::new(3, 3, 4), Job::Miner),
        Delver::new(1, "Sella", Pos::new(4, 3, 5), Job::Farmer),
        Delver::new(2, "Hale", Pos::new(4, 3, 3), Job::Hauler),
        Delver::new(3, "Wren", Pos::new(5, 3, 5), Job::Herbalist),
    ];
    let fungal_face = Face {
        rock: Pos::new(8, 14, 4),
        stand: Pos::new(7, 14, 4),
        ore: 20,
        cache: 0,
        yield_kind: crate::sim::YieldKind::FungalOil,
    };
    let mut sim = Sim::new(
        world,
        delvers,
        Pos::new(3, 3, 4),
        vec![
            Pos::new(2, 3, 3),
            Pos::new(2, 3, 5),
            Pos::new(6, 3, 5),
            Pos::new(6, 3, 3),
        ],
        vec![the_face(), fungal_face],
        Pos::new(6, 3, 4),
        Stores {
            ore: 0,
            goods: 4,
            food: 12,
            fungal_oil: 0,
            masks: 0,
        },
        0x5EED_0005,
        1500,
        true,
    );
    sim.place_lantern(CAMP_LANTERN, 1, 1_000_000.0);
    sim.plant_plot(Pos::new(5, 3, 3));
    sim.plant_plot(Pos::new(6, 3, 3));
    sim
}

/// Light the deep shaft and the fungal chamber (tier-1 lanterns;
/// tier-2 comes once the oil flows).
pub fn light_the_deep(sim: &mut Sim) {
    light_the_way(sim);
    sim.place_lantern(DEEP_SHAFT_LANTERN, 1, 5_000.0);
    sim.place_lantern(FUNGAL_LANTERN, 1, 5_000.0);
}

// ---------------------------------------------------------------------------
// S6 — the generated Floor 1
// ---------------------------------------------------------------------------

/// The demo world seed for the generated-floor scenario (the
/// bridge's `gen`, the scenario binary's GEN section, the
/// frontend verify).
pub const GEN_WORLD_SEED: u64 = 0x5EED_0007;

/// S6: the S3 colony founded on a **generated** Floor 1 — the
/// Shallows produced by `crate::gen` from the colony's world
/// seed instead of by hand. The camp chamber is the generator's
/// entry room (same shape as the hand-built scenarios); the
/// passages, cavities, dens, veins, and descent are the seed's.
/// The dens' residents are home: one critter per den, placed by
/// the scenario script, as choreographed tests place theirs.
pub fn build_scenario_gen(world_seed: u64) -> Sim {
    let floor = generate_floor(world_seed, 1);
    let info = floor.info();
    let faces = floor.layout.faces.clone();
    let dens: Vec<(Pos, CritterKind)> = floor
        .layout
        .cavities
        .iter()
        .filter(|c| c.den)
        .map(|c| (c.centre, c.critter.unwrap_or(CritterKind::GloamRat)))
        .collect();
    let delvers = vec![
        Delver::new(0, "Bram", Pos::new(3, 3, 4), Job::Miner),
        Delver::new(1, "Sella", Pos::new(4, 3, 5), Job::Farmer),
        Delver::new(2, "Hale", Pos::new(4, 3, 3), Job::Hauler),
    ];
    let mut sim = Sim::new(
        floor.world,
        delvers,
        ENTRY,
        vec![Pos::new(2, 3, 3), Pos::new(2, 3, 5), Pos::new(6, 3, 5)],
        faces,
        GATE,
        Stores {
            ore: 0,
            goods: 0,
            food: 12,
            fungal_oil: 0,
            masks: 0,
        },
        world_seed,
        1500,
        true, // the dark bites — and this floor's dens are occupied
    );
    sim.floor = Some(info);
    sim.place_lantern(CAMP_LANTERN, 1, 1_000_000.0);
    sim.plant_plot(Pos::new(5, 3, 3));
    sim.plant_plot(Pos::new(6, 3, 3));
    for (pos, kind) in dens {
        sim.spawn_critter(kind, pos);
    }
    sim
}

/// The player's frontier work on a generated floor — the
/// analogue of `light_the_way`: carry light from the camp along
/// the natural passages to the first workable face (the faces
/// are sorted, so it is the same one the miner will pick),
/// lanterns spaced inside each other's radius.
pub fn open_floor1(sim: &mut Sim) {
    let Some(face) = sim.faces.first().cloned() else {
        return;
    };
    let Some(path) = carved_path(&sim.world, sim.stockpile, face.stand) else {
        return;
    };
    for (i, p) in path.iter().enumerate() {
        if i % 4 == 3 || i == path.len() - 1 {
            sim.place_lantern(*p, 1, 5_000.0);
        }
    }
}
