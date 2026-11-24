//! S14 acceptance: fungal-oil face registration — the S9/S10
//! finding's second half, closed. On generated floors the
//! generator used to register faces from the theme's primary
//! resource cell (ore) only, so the Fungal Reaches' fungal
//! nodes sat in the rock as embedded pockets and fungal oil
//! never flowed there: the band's whole economy (tier-2+
//! lanterns burn oil) was dead on the very floors it belongs
//! to. S14 registers a face for every fungal-node cluster
//! that touches carved, reachable space — the same rule a
//! vein follows — with the cluster's cells as its yield at
//! the generator's per-cell rate. Registration draws no RNG
//! and moves no rock: the generated world is byte-identical
//! to the pre-S14 world; only the layout's face list grows.
//!
//! The colony proof below is the full gate-set run a player
//! would make: found on generated floor 2, light the routes
//! to the faces in order, craft spore masks from the first
//! goods (the deep ore face stands in spore air), work
//! through the ore faces to the fungal face, haul oil home,
//! and burn a charge of it in a tier-2 lantern.

use underreach_sim::gen::{carved_distances, generate_floor, theme_for_floor, ENTRY};
use underreach_sim::scenario::{build_scenario_gen_floor, light_route_to_face, GEN_WORLD_SEED};
use underreach_sim::sim::{LedgerKind, Sim, YieldKind, LANTERN_OIL_COST};
use underreach_sim::world::{Cell, Pos};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

fn oil_hauls(sim: &Sim) -> usize {
    sim.ledger
        .iter()
        .filter(|e| e.kind == LedgerKind::HaulDelivered && e.detail.contains("fungal oil"))
        .count()
}

#[test]
fn fungal_faces_register_where_clusters_touch_carved_space() {
    let mut seeds: Vec<u64> = (1..=16).collect();
    seeds.push(GEN_WORLD_SEED);
    for seed in seeds {
        // Floor 2 and floor 6 are both the Fungal band (the
        // band cycle below the Magma Roots).
        for floor_index in [2u32, 6] {
            let floor = generate_floor(seed, floor_index);
            let theme = theme_for_floor(floor_index);
            let dist = carved_distances(&floor.world, ENTRY);
            let fungal: Vec<_> = floor
                .layout
                .faces
                .iter()
                .filter(|f| f.yield_kind == YieldKind::FungalOil)
                .collect();
            assert!(
                !fungal.is_empty(),
                "seed {seed} floor {floor_index}: at least one fungal face registers"
            );
            assert!(
                fungal.len() <= theme.fungal_node_clusters,
                "seed {seed} floor {floor_index}: at most one face per cluster"
            );
            let ore_faces = floor.layout.faces.len() - fungal.len();
            assert!(
                ore_faces <= theme.face_veins_max,
                "seed {seed} floor {floor_index}: the ore face cap still binds"
            );
            for f in &fungal {
                assert_eq!(
                    floor.world.get(f.rock),
                    Some(Cell::FungalNode),
                    "seed {seed} floor {floor_index}: the face's rock is a fungal node cell"
                );
                assert_eq!(
                    floor.world.get(f.stand),
                    Some(Cell::Carved),
                    "seed {seed} floor {floor_index}: the stand is carved space"
                );
                let d = floor.world.idx(f.stand).map(|i| dist[i]).unwrap_or(-1);
                assert!(
                    d >= 0,
                    "seed {seed} floor {floor_index}: the stand is reachable over carved space"
                );
                assert_eq!(
                    f.ore % 6,
                    0,
                    "seed {seed} floor {floor_index}: the yield is the per-cell rate times the cluster"
                );
                assert!(f.ore >= 6, "seed {seed} floor {floor_index}: a cluster holds yield");
            }
        }
    }
}

#[test]
fn no_fungal_faces_on_the_other_bands() {
    for floor_index in [1u32, 3, 4, 5] {
        let floor = generate_floor(GEN_WORLD_SEED, floor_index);
        assert!(
            floor.layout.faces.iter().all(|f| f.yield_kind == YieldKind::Ore),
            "floor {floor_index}: faces yield ore only"
        );
    }
}

#[test]
fn demo_floor_2_fungal_face_is_the_registered_cluster() {
    let floor = generate_floor(GEN_WORLD_SEED, 2);
    let fungal: Vec<_> = floor
        .layout
        .faces
        .iter()
        .filter(|f| f.yield_kind == YieldKind::FungalOil)
        .collect();
    assert_eq!(fungal.len(), 1, "exactly one cluster touches carved space");
    assert_eq!(fungal[0].rock, Pos::new(15, 4, 1));
    assert_eq!(fungal[0].stand, Pos::new(15, 4, 2));
    assert_eq!(fungal[0].ore, 12, "two cluster cells at the per-cell rate of 6");
    // Third in the colony's working order, behind the two ore
    // faces — the order the colony proof below works through.
    assert_eq!(floor.layout.faces[2].yield_kind, YieldKind::FungalOil);
}

#[test]
fn fungal_oil_flows_and_burns_on_generated_floor_2() {
    // The gate is real at founding: a tier-2 lantern refuses
    // while the oil store is empty.
    let mut gated = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    let fungal_face = gated
        .faces
        .iter()
        .find(|f| f.yield_kind == YieldKind::FungalOil)
        .cloned()
        .expect("the demo floor registers a fungal face");
    assert!(
        !gated.place_lantern(fungal_face.stand, 2, 500.0),
        "a tier-2 lantern refuses with no oil in stores"
    );
    assert_eq!(gated.stores.fungal_oil, 0);

    // Found the colony and light the routes to the faces in
    // working order, up to and including the fungal face.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    for f in sim.faces.clone() {
        light_route_to_face(&mut sim, &f);
        if f.yield_kind == YieldKind::FungalOil {
            break;
        }
    }

    // Phase 1: the first ore face funds the gate set. Craft
    // two spore masks (miner + hauler both travel to the deep
    // ore face) as soon as the goods allow.
    let mut ticks = 0u32;
    while sim.stores.masks < 2 && ticks < 20_000 {
        for _ in 0..100 {
            sim.tick();
        }
        ticks += 100;
        while sim.stores.masks < 2 && sim.craft_mask() {}
    }
    assert_eq!(sim.stores.masks + sim.delvers.iter().filter(|d| d.masked).count() as u32, 2,
        "two masks crafted from the first goods (some may already be worn)");

    // Phase 2: work through the remaining ore face to the
    // fungal face. The run stops the tick oil first lands.
    while sim.stores.fungal_oil == 0 && ticks < 40_000 {
        for _ in 0..100 {
            sim.tick();
        }
        ticks += 100;
    }
    assert!(
        sim.stores.fungal_oil > 0,
        "fungal oil reached the stores after {ticks} ticks"
    );
    assert!(oil_hauls(&sim) >= 1, "an oil haul was delivered and ledgered");
    assert!(sim.stores.goods > 0, "the ore economy ran alongside: goods in stores");
    assert_eq!(count(&sim, LedgerKind::DelverLost), 0, "nobody is lost");
    assert!(
        sim.delvers.iter().filter(|d| d.masked).count() >= 1,
        "the mask was equipped for the deep work"
    );
    let ticks_to_oil = ticks;

    // The state — a partially worked fungal face included —
    // saves and loads to the identical hash, and a twin
    // continuation stays identical.
    let saved = sim.save_json();
    let hash = sim.state_hash();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), hash, "load reproduces the hash mid-flow");
    for _ in 0..300 {
        sim.tick();
        loaded.tick();
    }
    assert_eq!(sim.state_hash(), loaded.state_hash(), "twin continuation identical");

    // Phase 3: burn the oil. A tier-2 lantern at the fungal
    // face draws exactly one charge from the stores.
    let before = sim.stores.fungal_oil;
    assert!(before >= LANTERN_OIL_COST, "oil remains for the lantern");
    assert!(
        sim.place_lantern(fungal_face.stand, 2, 500.0),
        "the tier-2 lantern places once oil flows"
    );
    assert_eq!(
        sim.stores.fungal_oil,
        before - LANTERN_OIL_COST,
        "exactly one oil charge was drawn"
    );
    assert!(
        sim.lanterns.iter().any(|l| l.pos == fungal_face.stand && l.tier == 2),
        "a tier-2 lantern stands at the fungal face"
    );
    println!("S14 proof: oil first landed at tick {ticks_to_oil}");
}
