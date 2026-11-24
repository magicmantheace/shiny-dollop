//! S9 acceptance: floors 2–5 scenarios and balance — a colony
//! founded directly on each generated band floor runs the
//! delve → haul → convert loop there, deterministically, and
//! nobody is lost. The Fungal finding these tests also encode
//! (recorded in `docs/TEST_PLAN.md`): the S5 spore mechanics do
//! NOT engage on generated floor 2, because exposure is keyed
//! to depth via `hazards_at(y)` — spores start at y ≥ 10
//! (`FUNGAL_FROM`) while generated floors hold all their carved
//! space at y ≤ 9 (`GEN_MAX_Y`). No band's `built` flag flips
//! in this slice; see the per-band reasoning in TEST_PLAN.

use underreach_sim::gen::{generate_floor, theme_for_floor, DressingKind, GEN_MAX_Y};
use underreach_sim::scenario::{
    build_scenario_gen, build_scenario_gen_floor, open_current_floor, GEN_WORLD_SEED,
};
use underreach_sim::sim::{hazards_at, CritterKind, LedgerKind, Sim, YieldKind, FUNGAL_FROM};
use underreach_sim::world::Cell;

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

/// Found a colony on `floor`, open it, run the fixed budget.
fn run_band(floor: u32, ticks: u32) -> Sim {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, floor);
    assert_eq!(
        sim.floor.as_ref().map(|f| f.index),
        Some(floor),
        "the colony stands on floor {floor}"
    );
    assert_eq!(
        sim.world,
        generate_floor(GEN_WORLD_SEED, floor).world,
        "the founded world is the generated floor {floor}"
    );
    assert_eq!(sim.rng_state, GEN_WORLD_SEED, "founding drew no runtime RNG");
    let goods_before = sim.stores.goods;
    open_current_floor(&mut sim);
    for _ in 0..ticks {
        sim.tick();
    }
    assert!(
        sim.stores.goods > goods_before,
        "floor {floor}: goods strictly increase ({} -> {})",
        goods_before,
        sim.stores.goods
    );
    assert!(
        count(&sim, LedgerKind::HaulDelivered) >= 1,
        "floor {floor}: deliveries happened"
    );
    assert_eq!(
        count(&sim, LedgerKind::DelverLost),
        0,
        "floor {floor}: nobody is lost"
    );
    sim
}

#[test]
fn founding_on_floor_1_is_the_gen_scenario() {
    // The generalization must not move Floor 1: founding via
    // the new entry point is byte-identical to the S6 founding.
    let a = build_scenario_gen(GEN_WORLD_SEED);
    let b = build_scenario_gen_floor(GEN_WORLD_SEED, 1);
    assert_eq!(a.state_hash(), b.state_hash());
}

#[test]
fn floor2_fungal_reaches_runs_the_colony_loop() {
    let sim = run_band(2, 6000);
    assert!(sim.delvers.len() >= 3, "the colony stands");
}

#[test]
fn floor3_drowned_galleries_runs_the_colony_loop() {
    let sim = run_band(3, 6000);
    assert!(sim.delvers.len() >= 3, "the colony stands");
}

#[test]
fn floor4_crystal_dark_runs_the_colony_loop() {
    let sim = run_band(4, 6000);
    assert!(sim.delvers.len() >= 3, "the colony stands");
}

#[test]
fn floor5_magma_roots_runs_the_colony_loop() {
    let sim = run_band(5, 6000);
    assert!(sim.delvers.len() >= 3, "the colony stands");
}

#[test]
fn determinism_on_floor_2() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    open_current_floor(&mut sim);
    for _ in 0..1000 {
        sim.tick();
    }
    let saved = sim.save_json();
    let hash = sim.state_hash();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), hash, "load reproduces the hash on floor 2");
    for _ in 0..300 {
        sim.tick();
        loaded.tick();
    }
    assert_eq!(sim.state_hash(), loaded.state_hash(), "twin continuation identical");
}

#[test]
fn determinism_on_floor_5() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 5);
    open_current_floor(&mut sim);
    for _ in 0..1000 {
        sim.tick();
    }
    let saved = sim.save_json();
    let hash = sim.state_hash();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), hash, "load reproduces the hash on floor 5");
    for _ in 0..300 {
        sim.tick();
        loaded.tick();
    }
    assert_eq!(sim.state_hash(), loaded.state_hash(), "twin continuation identical");
}

/// The Fungal proof (S9 item 3): on generated floor 2 the S5
/// spore mechanics do **not** engage. Exposure is keyed to
/// depth — `hazards_at(y).spores` is true only at y ≥ 10 —
/// and a generated floor's carved space tops out at y = 9, so
/// no delver on the floor can ever stand in spore-bearing air.
/// Fungal oil does not flow either: the generator registers
/// faces from the theme's primary resource cell (ore) only,
/// and the fungal-node clusters are embedded pockets, not
/// faces. Mask protection itself remains proven by the S5
/// tests on the hand-built deep floor (chamber at y = 14).
#[test]
fn fungal_spores_do_not_engage_on_generated_floor_2() {
    let floor = generate_floor(GEN_WORLD_SEED, 2);
    // Every carved cell of the generated floor is above the
    // Fungal line, and every face stand is in clean air.
    assert!(GEN_MAX_Y < FUNGAL_FROM, "generated content sits above the Fungal line");
    for stand in floor.layout.faces.iter().map(|f| f.stand) {
        assert!(
            !hazards_at(stand.y).spores,
            "face stand {stand:?} is in spore-bearing air"
        );
    }
    // The faces yield ore, not fungal oil.
    assert!(
        floor.layout.faces.iter().all(|f| f.yield_kind == YieldKind::Ore),
        "generated floor 2 faces yield ore only"
    );

    // An unmasked delver staged at the first face's stand for
    // 2,000 ticks gains exactly no spore load and never sickens.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    open_current_floor(&mut sim);
    let stand = sim.faces[0].stand;
    assert!(!sim.delvers[0].masked, "the probe delver is unmasked");
    sim.delvers[0].pos = stand;
    for _ in 0..2000 {
        sim.tick();
        sim.delvers[0].pos = stand;
        assert_eq!(sim.delvers[0].spore, 0.0, "no spore load accrues at the face");
    }
    assert_eq!(count(&sim, LedgerKind::DelverSick), 0);

    // And across a full colony run, no delver's load ever moves
    // and no oil reaches the stores.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    open_current_floor(&mut sim);
    for _ in 0..6000 {
        sim.tick();
        for d in &sim.delvers {
            assert_eq!(d.spore, 0.0, "spore load moved on generated floor 2");
        }
    }
    assert_eq!(count(&sim, LedgerKind::DelverSick), 0);
    assert_eq!(sim.stores.fungal_oil, 0, "no fungal oil flows from ore faces");
}

/// Guard: Floor 1's theme row is untouchable in this slice —
/// pin every value the Shallows row carried before S9.
#[test]
fn floor1_theme_row_is_pinned() {
    let t = theme_for_floor(1);
    assert!(t.built);
    assert_eq!(
        t.hazards,
        underreach_sim::sim::Hazards { spores: false, flooded: false, hot: false }
    );
    assert_eq!(t.cap_depth, 2);
    assert_eq!(t.resource_cells, &[Cell::Ore]);
    assert_eq!(t.fungal_node_clusters, 0);
    assert_eq!(t.connected_cavities, 5);
    assert_eq!(t.off_network_cavities, 2);
    assert_eq!(t.cavity_w, (2, 3));
    assert_eq!(t.cavity_d, (2, 3));
    assert_eq!(t.dens_on_network, 2);
    assert_eq!(t.dens_off_network, 1);
    assert_eq!(t.den_min_network_distance, 10);
    assert_eq!(t.descent_min_network_distance, 24);
    assert_eq!(t.veins, 6);
    assert_eq!(t.vein_cells, (2, 3));
    assert_eq!(t.rich_vein_cells, 4);
    assert_eq!(t.face_veins_max, 3);
    assert_eq!(t.loose_count, 5);
    assert_eq!(t.loose_size, (1, 3));
    assert_eq!(t.bad_air_count, 4);
    assert_eq!(t.bad_air_size, (1, 2));
    assert_eq!(t.spurs, 3);
    assert_eq!(t.spur_len, (3, 6));
    assert_eq!(t.loop_edges, 1);
    assert_eq!(t.widen_pct, 33);
    assert_eq!(
        t.dressing_kinds,
        &[
            DressingKind::Stalactite,
            DressingKind::Stalagmite,
            DressingKind::Rubble,
            DressingKind::Boulder,
        ]
    );
    assert_eq!(t.critter_kinds, &[CritterKind::GloamRat]);
}
