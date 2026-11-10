//! Two-phase S1 demonstration: the dark refuses, then first light
//! opens the way and the delve → haul → convert loop starts producing.

use underreach_sim::scenario::{build_scenario, light_the_way};
use underreach_sim::sim::LedgerKind;

fn count(sim: &underreach_sim::sim::Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

fn main() {
    let mut sim = build_scenario();

    for _ in 0..200 {
        sim.tick();
    }
    println!(
        "phase 1 — carved but unlit ({} ticks): goods={}, deliveries={}, route-blocked entries={}",
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
        "phase 2 — lantern network extended ({} ticks): goods={}, ore left in stores={}, deliveries={}, conversions={}, first-light entries={}, delver mining xp={}",
        sim.tick_count,
        sim.stores.goods,
        sim.stores.ore,
        count(&sim, LedgerKind::HaulDelivered),
        count(&sim, LedgerKind::Converted),
        count(&sim, LedgerKind::FirstLight),
        sim.delver.mining_xp,
    );
    println!("state hash: {}", sim.state_hash());
    println!("deep ledger:");
    for e in &sim.ledger {
        println!("  [{:>5}] {:?} — {}", e.tick, e.kind, e.detail);
    }
}
