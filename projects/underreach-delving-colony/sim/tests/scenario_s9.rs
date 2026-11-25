//! S9 acceptance: floors 2–5 scenarios and balance — a colony
//! founded directly on each generated band floor runs the
//! delve → haul → convert loop there, deterministically, and
//! nobody is lost. The Fungal finding these tests originally
//! encoded (S9, recorded in `docs/TEST_PLAN.md`): the S5 spore
//! mechanics did NOT engage on generated floor 2, because
//! exposure was keyed to depth via `hazards_at(y)`. **S10
//! superseded that finding**: exposure is now band-keyed
//! (`hazards_here`), and the Fungal test below pins the new
//! truth — spores engage in floor 2's deep zone, and the
//! shallow first face stays clean. The full S10 proofs live
//! in `scenario_s10.rs`.

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

/// The Fungal proof, updated for S10 (this test's S9 form
/// proved the opposite; see the file header). Exposure is now
/// band-keyed: on generated floor 2 the band's spores fill the
/// floor's deep zone (y ≥ `BAND_ZONE_FROM_Y`), while the first
/// face's stand — at y = 5, in the floor's shallows — stays in
/// clean air, exactly as the camp does. That half of the
/// S9 finding stood until S14: fungal-node clusters that
/// touch carved space now register as faces (S14), so oil
/// can flow on generated floor 2 — the flow proof is
/// `scenario_s14.rs`. This test's own colony run below
/// still shows no oil, for the narrower reason its ending
/// records: the standard opening never reaches the fungal
/// face within the budget. The depth table itself is
/// untouched: every face stand is still above the
/// hand-built Fungal line, which is precisely why the S9
/// depth-keyed proof came back negative.
#[test]
fn fungal_spores_engage_in_floor_2s_deep_zone() {
    let floor = generate_floor(GEN_WORLD_SEED, 2);
    assert!(GEN_MAX_Y < FUNGAL_FROM, "generated content sits above the Fungal line");
    for stand in floor.layout.faces.iter().map(|f| f.stand) {
        assert!(
            !hazards_at(stand.y).spores,
            "the depth table alone still keys no stand {stand:?} as spore-bearing"
        );
    }
    // S14: the demo floor's faces are three ore faces plus
    // one fungal face — the cluster at rock (15, 4, 1) touches
    // carved space and registers, third in sorted order. The
    // staged probes below keep using faces[0] (the shallow
    // ore starter) and faces[1] (the deep ore face), whose
    // stands S14 does not move.
    let fungal: Vec<_> = floor
        .layout
        .faces
        .iter()
        .filter(|f| f.yield_kind == YieldKind::FungalOil)
        .collect();
    assert_eq!(fungal.len(), 1, "one fungal face registers on the demo floor");
    assert_eq!(fungal[0].rock, underreach_sim::world::Pos::new(15, 4, 1));
    assert_eq!(
        floor.world.get(fungal[0].rock),
        Some(Cell::FungalNode),
        "the fungal face's rock is a fungal node cell"
    );

    // An unmasked delver staged at the first face's stand (the
    // floor's shallows) for 2,000 ticks gains exactly no spore
    // load and never sickens — the shallows are refuge.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    open_current_floor(&mut sim);
    let stand = sim.faces[0].stand;
    assert!(!sim.delvers[0].masked, "the probe delver is unmasked");
    sim.delvers[0].pos = stand;
    for _ in 0..2000 {
        sim.tick();
        sim.delvers[0].pos = stand;
        assert_eq!(sim.delvers[0].spore, 0.0, "no spore load accrues in the shallows");
    }
    assert_eq!(count(&sim, LedgerKind::DelverSick), 0);

    // Staged at a deep face's stand, the same delver loads up
    // and the spore-cough fires — the band engages (the full
    // proof, mask included, is S10's `scenario_s10.rs`).
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    open_current_floor(&mut sim);
    let stand = sim.faces[1].stand;
    assert!(sim.hazards_here(stand).spores, "the deep stand is band-keyed spore air");
    sim.place_lantern(stand, 1, 100_000.0); // lit staging, as in the S10 proofs
    sim.delvers[0].pos = stand;
    let mut peak = 0.0f32;
    for _ in 0..2000 {
        sim.tick();
        sim.delvers[0].pos = stand;
        peak = peak.max(sim.delvers[0].spore);
    }
    assert!(peak > 0.0, "spore load accrues at the deep face");
    assert!(
        count(&sim, LedgerKind::DelverSick) >= 1,
        "the spore-cough fires on generated floor 2"
    );

    // And across the standard opening's run, no oil reaches
    // the stores — not because oil cannot flow (S14 removed
    // that block) but because the colony works faces in
    // order and spends the whole 6,000-tick budget on the
    // first two ore faces; the fungal face, third in order,
    // is never reached, and its route is never lit. The run
    // that lights the fungal route and works the face is
    // S14's proof (`scenario_s14.rs`).
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    open_current_floor(&mut sim);
    for _ in 0..6000 {
        sim.tick();
    }
    assert_eq!(
        sim.stores.fungal_oil, 0,
        "the standard opening never reaches the fungal face in budget"
    );
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
