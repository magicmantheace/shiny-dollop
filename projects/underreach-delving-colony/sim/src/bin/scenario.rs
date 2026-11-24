//! Slice demonstrations: S1 (the dark refuses, then first light
//! opens production), S2 (a working colony of three, plus a
//! recruit, dividing the labour), S3/S5, and S6 — the same
//! colony loop founded on a procedurally generated Floor 1.

use underreach_sim::gen::generate_floor;
use underreach_sim::scenario::{
    build_scenario, build_scenario_gen, build_scenario_gen_floor, build_scenario_s2,
    build_scenario_s3, build_scenario_s5, build_scenario_s7, light_the_deep, light_the_way,
    open_current_floor, open_floor1, GEN_WORLD_SEED,
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

    // ---- S7: the Shallows bite back -------------------------------------
    // The same colony, but the face is ringed with loose rock and
    // bad air pools beside the stand. Run one works it bare; the
    // player clears each fall as it happens (re-carving the
    // stand), but sets no timber and rigs no vent.
    let mut sim = build_scenario_s7();
    light_the_way(&mut sim);
    let s7_stand = sim.faces[0].stand;
    for _ in 0..6000 {
        sim.tick();
        if sim.world.get(s7_stand) == Some(underreach_sim::world::Cell::Stone) {
            sim.carve(s7_stand);
        }
    }
    println!(
        "S7 unprotected face ({} ticks): delvers alive={}, goods={}, cave-ins={}, gasping={}, downed={}, lost={}",
        sim.tick_count,
        sim.delvers.len(),
        sim.stores.goods,
        count(&sim, LedgerKind::CaveIn),
        count(&sim, LedgerKind::DelverGasping),
        count(&sim, LedgerKind::DelverDowned),
        count(&sim, LedgerKind::DelverLost),
    );
    for d in &sim.delvers {
        println!(
            "  {} ({:?}): hp={:.0} air={:.0} morale={:.0} mining_xp={}",
            d.name, d.job, d.hp, d.air, d.morale, d.mining_xp,
        );
    }
    println!("S7 unprotected state hash: {}", sim.state_hash());

    // Run two spends 2 of its 4 goods on the gate set — a timber
    // support and a vent on the face's stand — before lighting up.
    let mut sim = build_scenario_s7();
    let stand = sim.faces[0].stand;
    let supported = sim.place_support(stand);
    let vented = sim.place_vent(stand);
    light_the_way(&mut sim);
    for _ in 0..6000 {
        sim.tick();
    }
    println!(
        "S7 protected face ({} ticks): support placed={}, vent placed={}, delvers alive={}, goods={}, cave-ins={}, gasping={}, downed={}, lost={}",
        sim.tick_count,
        supported,
        vented,
        sim.delvers.len(),
        sim.stores.goods,
        count(&sim, LedgerKind::CaveIn),
        count(&sim, LedgerKind::DelverGasping),
        count(&sim, LedgerKind::DelverDowned),
        count(&sim, LedgerKind::DelverLost),
    );
    println!("S7 protected state hash: {}", sim.state_hash());

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

    // ---- S8: floor-to-floor traversal ------------------------------------
    // A fresh generated colony: open floor 1 and produce, descend
    // to floor 2 and produce there, then climb back and find
    // floor 1 exactly as it was left (its lanterns froze while
    // the colony was away).
    let mut s8 = build_scenario_gen(GEN_WORLD_SEED);
    open_floor1(&mut s8);
    for _ in 0..6000 {
        s8.tick();
    }
    println!(
        "S8 floor 1 ({} ticks): goods={}, deliveries={}, delvers alive={}, lost={}",
        s8.tick_count,
        s8.stores.goods,
        count(&s8, LedgerKind::HaulDelivered),
        s8.delvers.len(),
        count(&s8, LedgerKind::DelverLost),
    );
    let floor1_world = s8.world.clone();
    let floor1_lanterns = s8.lanterns.clone();
    let descended = s8.descend();
    println!(
        "S8 descend: ok={}, now on floor={}",
        descended,
        s8.floor.as_ref().map(|f| f.index).unwrap_or(0),
    );
    open_current_floor(&mut s8);
    let goods_at_arrival = s8.stores.goods;
    let deliveries_at_arrival = count(&s8, LedgerKind::HaulDelivered);
    for _ in 0..6000 {
        s8.tick();
    }
    println!(
        "S8 floor 2 ({} ticks): goods={} (was {} on arrival), deliveries on this floor={}, delvers alive={}, lost={}, first-light entries={}",
        s8.tick_count,
        s8.stores.goods,
        goods_at_arrival,
        count(&s8, LedgerKind::HaulDelivered) - deliveries_at_arrival,
        s8.delvers.len(),
        count(&s8, LedgerKind::DelverLost),
        count(&s8, LedgerKind::FirstLight),
    );
    let ascended = s8.ascend();
    println!(
        "S8 ascend: ok={}, back on floor={}, floor 1 world intact={}, floor 1 lanterns intact (frozen while away)={}",
        ascended,
        s8.floor.as_ref().map(|f| f.index).unwrap_or(0),
        s8.world == floor1_world,
        s8.lanterns == floor1_lanterns,
    );
    println!("S8 state hash: {}", s8.state_hash());

    // ---- S9: a colony founded on each band floor -------------------------
    // One run per band (floors 2–5): founded directly on the
    // generated floor, opened, and run for the standard budget.
    // The band events are printed per floor — sick for the
    // Fungal Reaches (the S9 finding: it stays 0, because spore
    // exposure is keyed to depth y ≥ 10 and generated floors
    // hold their carved space at y ≤ 9), gasping / cave-ins /
    // downed for the generic S7 hazards every floor carries.
    for (label, floor) in [
        ("F2 fungal reaches", 2),
        ("F3 drowned galleries", 3),
        ("F4 crystal dark", 4),
        ("F5 magma roots", 5),
    ] {
        let mut s9 = build_scenario_gen_floor(GEN_WORLD_SEED, floor);
        open_current_floor(&mut s9);
        for _ in 0..6000 {
            s9.tick();
        }
        println!(
            "S9 {label} ({} ticks): goods={}, deliveries={}, delvers alive={}, lost={}, sick={}, gasping={}, cave-ins={}, downed={}, fungal oil={}",
            s9.tick_count,
            s9.stores.goods,
            count(&s9, LedgerKind::HaulDelivered),
            s9.delvers.len(),
            count(&s9, LedgerKind::DelverLost),
            count(&s9, LedgerKind::DelverSick),
            count(&s9, LedgerKind::DelverGasping),
            count(&s9, LedgerKind::CaveIn),
            count(&s9, LedgerKind::DelverDowned),
            s9.stores.fungal_oil,
        );
        println!("S9 {label} state hash: {}", s9.state_hash());
    }

    println!("deep ledger (S2):");
    for e in &sim.ledger {
        println!("  [{:>5}] {:?} — {}", e.tick, e.kind, e.detail);
    }
}
