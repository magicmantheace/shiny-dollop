//! Slice demonstrations: S1 (the dark refuses, then first light
//! opens production) and S2 (a working colony of three, plus a
//! recruit, dividing the labour).

use underreach_sim::scenario::{build_scenario, build_scenario_s2, build_scenario_s3, light_the_way};
use underreach_sim::sim::LedgerKind;

fn count(sim: &underreach_sim::sim::Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

fn main() {
    // ---- S1 ------------------------------------------------------------
    let mut sim = build_scenario();
    for _ in 0..200 {
        sim.tick();
    }
    println!(
        "S1 phase 1 — carved but unlit ({} ticks): goods={}, deliveries={}, route-blocked entries={}",
        sim.tick_count,
        sim.stores.goods,
        count(&sim, LedgerKind::HaulDelivered),
        count(&sim, LedgerKind::RouteBlocked),
    );
    light_the_way(&mut sim);
    for _ in 0..4000 {
        sim.tick();
    }
    println!(
        "S1 phase 2 — lantern network extended ({} ticks): goods={}, ore left in stores={}, deliveries={}, conversions={}, first-light entries={}, delver mining xp={}",
        sim.tick_count,
        sim.stores.goods,
        sim.stores.ore,
        count(&sim, LedgerKind::HaulDelivered),
        count(&sim, LedgerKind::Converted),
        count(&sim, LedgerKind::FirstLight),
        sim.delvers[0].mining_xp,
    );
    println!("S1 state hash: {}", sim.state_hash());

    // ---- S2 ------------------------------------------------------------
    let mut sim = build_scenario_s2();
    light_the_way(&mut sim);
    for _ in 0..6000 {
        sim.tick();
    }
    println!(
        "S2 colony ({} ticks): delvers={}, goods={}, food in stores={}, harvests={}, deliveries={}, recruits={}, spirits-fallen={}",
        sim.tick_count,
        sim.delvers.len(),
        sim.stores.goods,
        sim.stores.food,
        count(&sim, LedgerKind::Harvested),
        count(&sim, LedgerKind::HaulDelivered),
        count(&sim, LedgerKind::RecruitArrived),
        count(&sim, LedgerKind::SpiritsFallen),
    );
    for d in &sim.delvers {
        println!(
            "  {} ({:?}): energy={:.0} hunger={:.0} morale={:.0} mining_xp={} hauling_xp={} farming_xp={}",
            d.name, d.job, d.energy, d.hunger, d.morale, d.mining_xp, d.hauling_xp, d.farming_xp,
        );
    }
    println!("S2 state hash: {}", sim.state_hash());

    // ---- S3 ------------------------------------------------------------
    let mut sim = build_scenario_s3();
    light_the_way(&mut sim);
    for _ in 0..6000 {
        sim.tick();
    }
    println!(
        "S3 colony under threat ({} ticks): delvers alive={}, goods={}, food={}, spotted={}, slain={}, downed={}, rescued={}, lost={}",
        sim.tick_count,
        sim.delvers.len(),
        sim.stores.goods,
        sim.stores.food,
        count(&sim, LedgerKind::CreatureSpotted),
        count(&sim, LedgerKind::CreatureSlain),
        count(&sim, LedgerKind::DelverDowned),
        count(&sim, LedgerKind::DelverRescued),
        count(&sim, LedgerKind::DelverLost),
    );
    for d in &sim.delvers {
        println!(
            "  {} ({:?}): hp={:.0} energy={:.0} morale={:.0} combat_xp={}",
            d.name, d.job, d.hp, d.energy, d.morale, d.combat_xp,
        );
    }
    println!("S3 state hash: {}", sim.state_hash());

    println!("deep ledger (S2):");
    for e in &sim.ledger {
        println!("  [{:>5}] {:?} — {}", e.tick, e.kind, e.detail);
    }
}
