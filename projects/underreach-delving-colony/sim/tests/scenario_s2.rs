//! S2 acceptance: colony breadth — jobs divide the labour, the
//! farmer feeds the colony, a recruit arrives, morale moves.

use underreach_sim::scenario::{build_scenario_s2, light_the_way};
use underreach_sim::sim::{Job, LedgerKind, Sim};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

fn lit_s2(ticks: u64) -> Sim {
    let mut sim = build_scenario_s2();
    light_the_way(&mut sim);
    for _ in 0..ticks {
        sim.tick();
    }
    sim
}

#[test]
fn colony_divides_the_labour_and_produces() {
    let sim = lit_s2(6000);
    assert!(
        sim.stores.goods >= 2,
        "colony should convert ore to goods, goods={}",
        sim.stores.goods
    );
    // The miner mined and the hauler ran the cache home.
    let bram = &sim.delvers[0];
    assert!(bram.mining_xp > 0, "miner should have mining xp");
    let hale = sim
        .delvers
        .iter()
        .find(|d| d.job == Job::Hauler)
        .expect("a hauler exists");
    assert!(
        count(&sim, LedgerKind::HaulDelivered) >= 1,
        "deliveries should be on the ledger"
    );
    let _ = hale;
}

#[test]
fn farmer_feeds_the_colony() {
    let sim = lit_s2(6000);
    assert!(
        count(&sim, LedgerKind::Harvested) >= 2,
        "expected at least 2 harvests, ledger kinds: {:?}",
        sim.ledger.iter().map(|e| e.kind).collect::<Vec<_>>()
    );
    let sella = sim
        .delvers
        .iter()
        .find(|d| d.name == "Sella")
        .expect("Sella exists");
    assert!(sella.farming_xp > 0, "farmer should have farming xp");
}

#[test]
fn a_recruit_arrives_while_the_colony_is_fed() {
    // First arrival is due at tick 1500; the next is not until 3900.
    let sim = lit_s2(3000);
    assert_eq!(
        sim.delvers.len(),
        4,
        "one recruit should have arrived by tick 3000"
    );
    assert_eq!(count(&sim, LedgerKind::RecruitArrived), 1);
    let recruit = &sim.delvers[3];
    assert!(recruit.id == 3 && !recruit.name.is_empty());
}

#[test]
fn morale_falls_when_the_colony_starves() {
    let mut sim = build_scenario_s2();
    light_the_way(&mut sim);
    sim.stores.food = 0;
    // No food and no harvests yet reaching stores fast enough is not
    // guaranteed — force the issue: strip the plots too.
    sim.plots.clear();
    let start: f32 = sim.delvers.iter().map(|d| d.morale).sum::<f32>() / 3.0;
    for _ in 0..4000 {
        sim.tick();
    }
    let end: f32 =
        sim.delvers.iter().map(|d| d.morale).sum::<f32>() / sim.delvers.len() as f32;
    assert!(
        end < start - 10.0,
        "morale should fall in a starving colony: start={start:.1} end={end:.1}"
    );
    assert!(count(&sim, LedgerKind::SpiritsFallen) >= 1);
}

#[test]
fn s2_save_load_is_deterministic() {
    let mut sim = lit_s2(800);
    let saved = sim.save_json();
    let hash_at_save = sim.state_hash();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), hash_at_save);
    for _ in 0..500 {
        sim.tick();
        loaded.tick();
    }
    assert_eq!(sim.state_hash(), loaded.state_hash());
}
