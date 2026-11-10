//! S1 acceptance: the scripted Shallows scenario.

use underreach_sim::scenario::{build_scenario, light_the_way};
use underreach_sim::sim::{DelverState, LedgerKind, Sim};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

#[test]
fn phase1_the_dark_refuses() {
    let mut sim = build_scenario();
    for _ in 0..200 {
        sim.tick();
    }
    // Nothing can be produced: the face is beyond the light.
    assert_eq!(sim.stores.goods, 0);
    assert_eq!(count(&sim, LedgerKind::HaulDelivered), 0);
    // And the refusal is on the record.
    assert!(count(&sim, LedgerKind::RouteBlocked) >= 1);
}

#[test]
fn phase2_first_light_and_production() {
    let mut sim = build_scenario();
    for _ in 0..200 {
        sim.tick();
    }
    light_the_way(&mut sim);
    // First light reaches the tunnel depths.
    assert!(sim
        .ledger
        .iter()
        .any(|e| e.kind == LedgerKind::FirstLight && e.detail.contains("depth 8")));
    for _ in 0..4000 {
        sim.tick();
    }
    assert!(
        count(&sim, LedgerKind::HaulDelivered) >= 3,
        "expected at least 3 haul deliveries, ledger: {:?}",
        sim.ledger
    );
    assert!(sim.stores.goods >= 2, "goods={}", sim.stores.goods);
    assert!(sim.delver.mining_xp > 0);
}

#[test]
fn save_load_roundtrip_and_deterministic_continuation() {
    let mut sim = build_scenario();
    for _ in 0..200 {
        sim.tick();
    }
    light_the_way(&mut sim);
    // Run to a quiescent moment: delver at camp, deciding, path empty.
    let mut guard = 0;
    loop {
        sim.tick();
        guard += 1;
        if sim.delver.state == DelverState::Idle && sim.delver.path.is_empty() {
            break;
        }
        assert!(guard < 4000, "never reached a quiescent state");
    }
    let saved = sim.save_json();
    let hash_at_save = sim.state_hash();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), hash_at_save);
    // Continuation from the load must match the uninterrupted run.
    for _ in 0..300 {
        sim.tick();
        loaded.tick();
    }
    assert_eq!(sim.state_hash(), loaded.state_hash());
}
