//! S8 acceptance: floor-to-floor traversal — per-floor stored
//! state, `descend` / `ascend`, generation purity across
//! travel, first light per floor, and the colony loop running
//! on floor 2. The modelling decisions these tests encode
//! (whole-colony immediate transition, a floor left behind is
//! frozen, forward camp on first arrival with no plots) are
//! recorded in `docs/TEST_PLAN.md`.

use underreach_sim::gen::generate_floor;
use underreach_sim::scenario::{
    build_scenario, build_scenario_gen, open_current_floor, open_floor1, GEN_WORLD_SEED,
};
use underreach_sim::sim::{LedgerKind, Sim};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

#[test]
fn descend_lands_on_floor_2() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    assert_eq!(sim.floor.as_ref().map(|f| f.index), Some(1));
    assert!(sim.descend());
    assert_eq!(sim.floor.as_ref().map(|f| f.index), Some(2));
    let expected = generate_floor(GEN_WORLD_SEED, 2);
    assert_eq!(sim.world, expected.world, "the active world is floor 2 as generated");
    assert_eq!(sim.floor, Some(expected.info()), "FloorInfo is floor 2's");
    assert_eq!(count(&sim, LedgerKind::Descended), 1);
    assert!(
        sim.ledger
            .iter()
            .any(|e| e.kind == LedgerKind::Descended && e.detail.contains("floor 2")),
        "the descent is ledgered, naming the floor"
    );
    // A forward camp at the entry camp: stockpile and beds
    // there, the generated floor's faces, no plots carried down.
    assert_eq!(sim.stockpile, underreach_sim::gen::ENTRY);
    assert!(!sim.beds.is_empty());
    assert_eq!(sim.faces, expected.layout.faces);
    assert!(sim.plots.is_empty(), "farming plots do not carry down");
    assert!(
        sim.delvers.iter().all(|d| d.pos.y == 3),
        "the whole colony gathered at the entry camp"
    );
    assert!(sim.floors.contains_key(&1), "floor 1 is stored behind");
}

#[test]
fn generation_purity_across_travel() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    let rng_before = sim.rng_state;
    assert!(sim.descend(), "1 -> 2 generates floor 2");
    assert_eq!(sim.rng_state, rng_before, "generation drew no runtime RNG");
    assert_eq!(sim.world, generate_floor(GEN_WORLD_SEED, 2).world);
    assert!(sim.descend(), "2 -> 3 generates floor 3");
    assert_eq!(sim.rng_state, rng_before, "generation drew no runtime RNG");
    assert_eq!(sim.world, generate_floor(GEN_WORLD_SEED, 3).world);
    assert_eq!(sim.floor.as_ref().map(|f| f.index), Some(3));
}

#[test]
fn round_trip_restores_floor_1_exactly() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    open_floor1(&mut sim);
    for _ in 0..6000 {
        sim.tick();
    }
    // Leave a mark of the player on floor 1: the gate set on
    // the first face's stand.
    let stand = sim.faces[0].stand;
    assert!(sim.place_support(stand));
    assert!(sim.place_vent(stand));
    let world = sim.world.clone();
    let lanterns = sim.lanterns.clone();
    let faces = sim.faces.clone();
    let supports = sim.supports.clone();
    let vents = sim.vents.clone();
    let lit_depths = sim.lit_depths.clone();

    assert!(sim.descend());
    open_current_floor(&mut sim);
    for _ in 0..1000 {
        sim.tick();
    }
    assert!(sim.ascend());
    assert_eq!(sim.floor.as_ref().map(|f| f.index), Some(1));
    assert_eq!(sim.world, world, "floor 1's world is as it was left");
    assert_eq!(sim.lanterns, lanterns, "floor 1's lanterns did not burn while away");
    assert_eq!(sim.faces, faces);
    assert_eq!(sim.supports, supports);
    assert_eq!(sim.vents, vents);
    assert_eq!(sim.lit_depths, lit_depths);
    // The colony climbed back up the stairs it came down.
    let descent = sim.floor.as_ref().unwrap().descent;
    assert!(
        sim.delvers.iter().all(|d| d.pos == descent),
        "delvers arrive at floor 1's descent cell"
    );
    assert_eq!(count(&sim, LedgerKind::Ascended), 1);
}

#[test]
fn save_load_across_floors() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    open_floor1(&mut sim);
    for _ in 0..1000 {
        sim.tick();
    }
    assert!(sim.descend());
    open_current_floor(&mut sim);
    for _ in 0..500 {
        sim.tick();
    }
    let saved = sim.save_json();
    let hash = sim.state_hash();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), hash, "load reproduces the hash on floor 2");
    assert_eq!(loaded.floor, sim.floor);
    assert!(loaded.floors.contains_key(&1), "the stored floor survives the save");
    for _ in 0..300 {
        sim.tick();
        loaded.tick();
    }
    assert_eq!(sim.state_hash(), loaded.state_hash(), "twin continuation stays identical");
    // And the loaded copy can still climb home.
    assert!(loaded.ascend());
    assert_eq!(loaded.floor.as_ref().map(|f| f.index), Some(1));
}

#[test]
fn first_light_is_per_floor() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    open_floor1(&mut sim);
    let on_floor_1 = count(&sim, LedgerKind::FirstLight);
    assert!(on_floor_1 > 0);
    assert!(sim.descend());
    open_current_floor(&mut sim);
    let after = count(&sim, LedgerKind::FirstLight);
    assert!(
        after > on_floor_1,
        "lighting floor 2 records fresh first light ({after} vs {on_floor_1} on floor 1)"
    );
}

#[test]
fn the_loop_continues_on_floor_2() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    open_floor1(&mut sim);
    for _ in 0..3000 {
        sim.tick();
    }
    assert!(sim.descend());
    open_current_floor(&mut sim);
    let goods_at_arrival = sim.stores.goods;
    let deliveries_at_arrival = count(&sim, LedgerKind::HaulDelivered);
    for _ in 0..6000 {
        sim.tick();
    }
    assert!(
        count(&sim, LedgerKind::HaulDelivered) > deliveries_at_arrival,
        "deliveries happened on floor 2"
    );
    assert!(
        sim.stores.goods > goods_at_arrival,
        "goods strictly increased on floor 2 ({} -> {})",
        goods_at_arrival,
        sim.stores.goods
    );
    assert_eq!(count(&sim, LedgerKind::DelverLost), 0, "nobody lost on floor 2");
}

#[test]
fn refusals_change_nothing() {
    // The hand-built S1 colony stands on no generated floor.
    let mut sim = build_scenario();
    let hash = sim.state_hash();
    assert!(!sim.descend(), "descend refuses with no floor record");
    assert_eq!(sim.state_hash(), hash, "a refused descend changes nothing");
    assert!(!sim.ascend());
    assert_eq!(sim.state_hash(), hash);

    // Floor 1 has no floor above.
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    let hash = sim.state_hash();
    assert!(!sim.ascend(), "ascend refuses on floor 1");
    assert_eq!(sim.state_hash(), hash, "a refused ascend changes nothing");
}

#[test]
fn the_ledger_is_append_only_across_a_descent() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    open_floor1(&mut sim);
    for _ in 0..500 {
        sim.tick();
    }
    let before = sim.ledger.clone();
    assert!(sim.descend());
    assert!(sim.ledger.len() > before.len(), "the descent appended entries");
    assert_eq!(
        sim.ledger[..before.len()],
        before[..],
        "entries before the descent are a strict prefix of the ledger after it"
    );
}
