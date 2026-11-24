//! S7 acceptance: the Shallows' own gate set — cave-ins at a
//! loose face and bad air beside sealed pockets, answered by
//! timber supports and vents. Proven piece by piece, the way
//! S5 proved the Fungal gate set: the hazards bite unprotected,
//! each answer stops exactly its own hazard, a buried delver is
//! dug out on the rescue clock, and the slice stays
//! deterministic.

use underreach_sim::scenario::{build_scenario_s7, light_the_way};
use underreach_sim::sim::{LedgerKind, Sim};
use underreach_sim::world::{Cell, Pos};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

/// Run the colony, with the player clearing each fall as it
/// happens (re-carving the face's stand) — an attentive player
/// who has set no timber and rigged no vent.
fn run_with_clearing(sim: &mut Sim, ticks: u32) {
    let stand = sim.faces[0].stand;
    for _ in 0..ticks {
        sim.tick();
        if sim.world.get(stand) == Some(Cell::Stone) {
            sim.carve(stand);
        }
    }
}

#[test]
fn the_unprotected_face_bites_both_ways() {
    let mut sim = build_scenario_s7();
    light_the_way(&mut sim);
    run_with_clearing(&mut sim, 6000);
    assert!(
        count(&sim, LedgerKind::CaveIn) >= 1,
        "mining a loose face unprotected should bring rock down"
    );
    assert!(
        count(&sim, LedgerKind::DelverGasping) >= 1,
        "working a gassy face unventilated should gasp someone"
    );
    assert_eq!(
        count(&sim, LedgerKind::DelverLost),
        0,
        "the colony weathers it: falls are cleared, the downed are rescued"
    );
    assert!(
        sim.stores.goods > 4,
        "production still flowed, goods={}",
        sim.stores.goods
    );
}

#[test]
fn timber_support_stops_cave_ins() {
    let mut sim = build_scenario_s7();
    let stand = sim.faces[0].stand;
    assert!(sim.place_support(stand));
    light_the_way(&mut sim);
    run_with_clearing(&mut sim, 6000);
    assert_eq!(
        count(&sim, LedgerKind::CaveIn),
        0,
        "a supported face never caves in"
    );
    assert_eq!(
        sim.world.get(stand),
        Some(Cell::Carved),
        "the stand was never buried"
    );
    assert!(
        sim.stores.goods > 2,
        "the face produced under its timber, goods={}",
        sim.stores.goods
    );
}

#[test]
fn a_vent_keeps_the_air_clean() {
    let mut sim = build_scenario_s7();
    let stand = sim.faces[0].stand;
    assert!(sim.place_vent(stand));
    light_the_way(&mut sim);
    run_with_clearing(&mut sim, 6000);
    assert_eq!(
        count(&sim, LedgerKind::DelverGasping),
        0,
        "nobody gasps within the vent's reach"
    );
    assert!(
        sim.delvers.iter().all(|d| d.air == 0.0),
        "no delver carries any bad-air load at all"
    );
    assert!(
        count(&sim, LedgerKind::CaveIn) >= 1,
        "the vent answers air, not rock: the unsupported face still falls"
    );
}

#[test]
fn supports_and_vents_cost_goods_and_need_open_cells() {
    let mut sim = build_scenario_s7();
    let camp = Pos::new(3, 3, 4); // carved, the stockpile cell
    let rock = Pos::new(0, 5, 0); // solid stone
    // Solid rock refuses both.
    assert!(!sim.place_support(rock));
    assert!(!sim.place_vent(rock));
    assert_eq!(sim.stores.goods, 4);
    // The scenario's 4 goods buy one of each, at 1 apiece.
    assert!(sim.place_support(camp));
    assert_eq!(sim.stores.goods, 3);
    // No stacking a second kit on the same cell.
    assert!(!sim.place_support(camp));
    assert!(sim.place_vent(camp));
    assert_eq!(sim.stores.goods, 2);
    assert!(!sim.place_vent(camp));
    // Broke colonies place nothing.
    sim.stores.goods = 0;
    let other = Pos::new(4, 3, 4);
    assert!(!sim.place_support(other));
    assert!(!sim.place_vent(other));
    assert_eq!(sim.supports.len(), 1);
    assert_eq!(sim.vents.len(), 1);
}

#[test]
fn a_cave_in_buries_the_miner_and_the_colony_digs_him_out() {
    let mut sim = build_scenario_s7();
    let stand = sim.faces[0].stand;
    // Answer the air, skip the timber: isolate the rock.
    assert!(sim.place_vent(stand));
    light_the_way(&mut sim);
    // A hurt miner: the fall's 55 damage will put him down.
    sim.delvers
        .iter_mut()
        .find(|d| d.name == "Bram")
        .unwrap()
        .hp = 50.0;
    let mut caved = false;
    for _ in 0..6000 {
        sim.tick();
        if count(&sim, LedgerKind::CaveIn) >= 1 {
            caved = true;
            break;
        }
    }
    assert!(caved, "the loose face should fall within 6000 ticks");
    assert_eq!(
        sim.world.get(stand),
        Some(Cell::Stone),
        "the stand is buried under the fall"
    );
    assert!(
        count(&sim, LedgerKind::DelverDowned) >= 1,
        "the fall downed the miner — the rescue clock is running"
    );
    // The colony digs him out: a rescuer paths to the rubble's
    // edge and carries him home well inside the 900-tick clock.
    for _ in 0..3000 {
        sim.tick();
    }
    assert!(
        count(&sim, LedgerKind::DelverRescued) >= 1,
        "a buried delver is rescued, not lost"
    );
    assert_eq!(count(&sim, LedgerKind::DelverLost), 0);
    assert!(
        sim.delvers.iter().any(|d| d.name == "Bram"),
        "Bram is home again"
    );
}

#[test]
fn s7_stays_deterministic() {
    let mut a = build_scenario_s7();
    let mut b = build_scenario_s7();
    for sim in [&mut a, &mut b] {
        let stand = sim.faces[0].stand;
        assert!(sim.place_support(stand));
        assert!(sim.place_vent(stand));
        light_the_way(sim);
    }
    for _ in 0..1200 {
        a.tick();
        b.tick();
    }
    assert_eq!(a.state_hash(), b.state_hash());
    let saved = a.save_json();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), a.state_hash());
    for _ in 0..300 {
        a.tick();
        loaded.tick();
    }
    assert_eq!(a.state_hash(), loaded.state_hash());
}
