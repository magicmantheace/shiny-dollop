//! Slice demonstrations: S1 (the dark refuses, then first light
//! opens production), S2 (a working colony of three, plus a
//! recruit, dividing the labour), S3/S5, and S6 — the same
//! colony loop founded on a procedurally generated Floor 1.

use underreach_sim::gen::generate_floor;
use underreach_sim::scenario::{
    build_scenario, build_scenario_gen, build_scenario_s2, build_scenario_s3, build_scenario_s5,
    light_the_deep, light_the_way, open_floor1, GEN_WORLD_SEED,
};
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

    // ---- S5 ------------------------------------------------------------
    let mut sim = build_scenario_s5();
    // The player crafts two masks from the colony's goods, then
    // lights the deep. Bram and Sella win the masks (camp order);
    // whoever else works the fungal face goes unprotected.
    sim.craft_mask();
    sim.craft_mask();
    light_the_deep(&mut sim);
    for _ in 0..6000 {
        sim.tick();
    }
    let tier2_placed = sim.place_lantern(underreach_sim::world::Pos::new(5, 14, 4), 2, 500.0);
    println!(
        "S5 fungal reaches ({} ticks): delvers alive={}, goods={}, fungal oil={}, masks in stores={}, sick events={}, tier-2 lantern placed={}",
        sim.tick_count,
        sim.delvers.len(),
        sim.stores.goods,
        sim.stores.fungal_oil,
        sim.stores.masks,
        count(&sim, LedgerKind::DelverSick),
        tier2_placed,
    );
    for d in &sim.delvers {
        println!(
            "  {} ({:?}): hp={:.0} spore={:.0} masked={} morale={:.0}",
            d.name, d.job, d.hp, d.spore, d.masked, d.morale,
        );
    }
    println!("S5 state hash: {}", sim.state_hash());

    // ---- GEN (S6): the colony loop on a generated Floor 1 ---------------
    let mut gen = build_scenario_gen(GEN_WORLD_SEED);
    for _ in 0..200 {
        gen.tick();
    }
    println!(
        "GEN phase 1 — passages dark ({} ticks): goods={}, deliveries={}, route-blocked entries={}",
        gen.tick_count,
        gen.stores.goods,
        count(&gen, LedgerKind::HaulDelivered),
        count(&gen, LedgerKind::RouteBlocked),
    );
    open_floor1(&mut gen);
    for _ in 0..6000 {
        gen.tick();
    }
    // Regenerating the floor here is free and proves the point:
    // the layout the sim stands on is a pure function of the seed.
    let layout = generate_floor(GEN_WORLD_SEED, 1).layout;
    println!(
        "GEN colony on generated floor 1 ({} ticks): goods={}, deliveries={}, conversions={}, delvers alive={}, lost={}, descent at ({},{},{}) network distance={}, network cells={}, dens={}, faces={}",
        gen.tick_count,
        gen.stores.goods,
        count(&gen, LedgerKind::HaulDelivered),
        count(&gen, LedgerKind::Converted),
        gen.delvers.len(),
        count(&gen, LedgerKind::DelverLost),
        layout.descent.x,
        layout.descent.y,
        layout.descent.z,
        layout.descent_network_distance,
        layout.network_cells.len(),
        layout.cavities.iter().filter(|c| c.den).count(),
        layout.faces.len(),
    );
    println!("GEN state hash: {}", gen.state_hash());

    println!("deep ledger (S2):");
    for e in &sim.ledger {
        println!("  [{:>5}] {:?} — {}", e.tick, e.kind, e.detail);
    }
}
