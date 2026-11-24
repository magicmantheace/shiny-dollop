//! Slice demonstrations: S1 (the dark refuses, then first light
//! opens production), S2 (a working colony of three, plus a
//! recruit, dividing the labour), S3/S5, and S6 — the same
//! colony loop founded on a procedurally generated Floor 1.

use underreach_sim::gen::{carved_path, generate_floor};
use underreach_sim::scenario::{
    build_scenario, build_scenario_gen, build_scenario_gen_floor, build_scenario_s2,
    build_scenario_s3, build_scenario_s5, build_scenario_s7, build_scenario_s12, light_the_deep,
    light_the_way, open_current_floor, open_current_floor_as, open_floor1, GEN_WORLD_SEED,
};
use underreach_sim::session::{merge_streams, replay, Command, PlayerCommand, Session};
use underreach_sim::sim::{Job, LedgerKind};
use underreach_sim::world::{Cell, Pos};

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
    // The band events are printed per floor. (S10 note: exposure
    // is band-keyed now, so the Drowned run shows drowning and
    // doused lanterns and the Magma run shows overheating. The
    // Fungal run's sick count stays 0 on the demo seed — not
    // because spores cannot engage, but because the colony
    // spends the whole budget on the first face, whose stand
    // at y = 5 sits above the floor's deep zone; the deeper
    // faces are proven in the S10 tests.)
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
            "S9 {label} ({} ticks): goods={}, deliveries={}, delvers alive={}, lost={}, sick={}, gasping={}, cave-ins={}, downed={}, fungal oil={}, drowning={}, doused={}, overheating={}",
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
            count(&s9, LedgerKind::DelverDrowning),
            count(&s9, LedgerKind::LanternDoused),
            count(&s9, LedgerKind::DelverOverheating),
        );
        println!("S9 {label} state hash: {}", s9.state_hash());
    }

    // ---- S10: the deeper bands bite --------------------------------------
    // Drowned, unprotected: founded on floor 3, opened with
    // ordinary tier-1 lanterns, no pumps. The flood works the
    // colony over — drowning loads at the deep faces and the
    // route lanterns standing in the water are doused.
    let mut s10 = build_scenario_gen_floor(GEN_WORLD_SEED, 3);
    open_current_floor(&mut s10);
    for _ in 0..6000 {
        s10.tick();
    }
    println!(
        "S10 drowned unprotected ({} ticks): goods={}, deliveries={}, delvers alive={}, lost={}, drowning={}, doused={}, downed={}",
        s10.tick_count,
        s10.stores.goods,
        count(&s10, LedgerKind::HaulDelivered),
        s10.delvers.len(),
        count(&s10, LedgerKind::DelverLost),
        count(&s10, LedgerKind::DelverDrowning),
        count(&s10, LedgerKind::LanternDoused),
        count(&s10, LedgerKind::DelverDowned),
    );
    println!("S10 drowned unprotected state hash: {}", s10.state_hash());

    // Drowned, protected: the colony comes down prepared — a
    // pump on every face stand (3 goods) and sealed pressure
    // lanterns (tier 3, one oil charge apiece) along the route.
    // The supplies are granted by the script, as a colony that
    // had delved the Fungal Reaches first would carry them.
    let mut s10 = build_scenario_gen_floor(GEN_WORLD_SEED, 3);
    s10.stores.goods += 3;
    s10.stores.fungal_oil += 8;
    let mut pumps = 0;
    for f in s10.faces.clone() {
        if s10.place_pump(f.stand) {
            pumps += 1;
        }
    }
    open_current_floor_as(&mut s10, 3);
    for _ in 0..6000 {
        s10.tick();
    }
    println!(
        "S10 drowned protected ({} ticks): pumps placed={}, goods={}, deliveries={}, delvers alive={}, lost={}, drowning={}, doused={}, downed={}",
        s10.tick_count,
        pumps,
        s10.stores.goods,
        count(&s10, LedgerKind::HaulDelivered),
        s10.delvers.len(),
        count(&s10, LedgerKind::DelverLost),
        count(&s10, LedgerKind::DelverDrowning),
        count(&s10, LedgerKind::LanternDoused),
        count(&s10, LedgerKind::DelverDowned),
    );
    println!("S10 drowned protected state hash: {}", s10.state_hash());

    // Magma, unprotected: founded on floor 5 and opened bare.
    let mut s10 = build_scenario_gen_floor(GEN_WORLD_SEED, 5);
    open_current_floor(&mut s10);
    for _ in 0..6000 {
        s10.tick();
    }
    println!(
        "S10 magma unprotected ({} ticks): goods={}, deliveries={}, delvers alive={}, lost={}, overheating={}, downed={}",
        s10.tick_count,
        s10.stores.goods,
        count(&s10, LedgerKind::HaulDelivered),
        s10.delvers.len(),
        count(&s10, LedgerKind::DelverLost),
        count(&s10, LedgerKind::DelverOverheating),
        count(&s10, LedgerKind::DelverDowned),
    );
    println!("S10 magma unprotected state hash: {}", s10.state_hash());

    // Magma, protected: cooling gear for the whole colony
    // (6 sets at 2 goods, granted by the script as carried-in
    // supplies), crafted before the floor is opened; delvers
    // equip it at camp automatically.
    let mut s10 = build_scenario_gen_floor(GEN_WORLD_SEED, 5);
    s10.stores.goods += 12;
    let mut gear = 0;
    for _ in 0..6 {
        if s10.craft_cooling_gear() {
            gear += 1;
        }
    }
    open_current_floor(&mut s10);
    for _ in 0..6000 {
        s10.tick();
    }
    println!(
        "S10 magma protected ({} ticks): gear crafted={}, goods={}, deliveries={}, delvers alive={}, lost={}, overheating={}, downed={}, cooled delvers={}",
        s10.tick_count,
        gear,
        s10.stores.goods,
        count(&s10, LedgerKind::HaulDelivered),
        s10.delvers.len(),
        count(&s10, LedgerKind::DelverLost),
        count(&s10, LedgerKind::DelverOverheating),
        count(&s10, LedgerKind::DelverDowned),
        s10.delvers.iter().filter(|d| d.cooled).count(),
    );
    println!("S10 magma protected state hash: {}", s10.state_hash());

    // ---- S12: children & generations --------------------------------------
    // A generations colony: three working founders plus Joss, a
    // founding child of 17 (the choreography is recorded in
    // docs/TEST_PLAN.md — a from-birth childhood is eighteen
    // years of ticks; the from-birth proof lives in the tests).
    // Phase 1 runs one year and change: Joss comes of age and a
    // first child is born. Phase 2 puts the grown Joss to work
    // as a second miner and runs on.
    let mut s12 = build_scenario_s12();
    light_the_way(&mut s12);
    for _ in 0..3000 {
        s12.tick();
    }
    let joss_id = s12
        .delvers
        .iter()
        .find(|d| d.name == "Joss")
        .map(|d| d.id)
        .unwrap_or(u32::MAX);
    let joss_assigned = s12.set_job(joss_id, Job::Miner);
    for _ in 0..4000 {
        s12.tick();
    }
    let joss = s12.delvers.iter().find(|d| d.name == "Joss");
    println!(
        "S12 generations colony ({} ticks): delvers alive={}, goods={}, births={}, comings-of-age={}, grown child assigned miner={}, grown child mining xp={}, children at camp={}, lost={}",
        s12.tick_count,
        s12.delvers.len(),
        s12.stores.goods,
        count(&s12, LedgerKind::ChildBorn),
        count(&s12, LedgerKind::CameOfAge),
        joss_assigned,
        joss.map(|d| d.mining_xp).unwrap_or(0),
        s12.delvers.iter().filter(|d| s12.delver_is_child(d)).count(),
        count(&s12, LedgerKind::DelverLost),
    );
    for d in &s12.delvers {
        println!(
            "  {} ({:?}): age={} child={} mining_xp={} hauling_xp={} farming_xp={}",
            d.name,
            d.job,
            d.age_years(),
            s12.delver_is_child(d),
            d.mining_xp,
            d.hauling_xp,
            d.farming_xp,
        );
    }
    println!("S12 state hash: {}", s12.state_hash());

    // ---- S13: co-op foundations -------------------------------------------
    // A two-player lockstep session on the generated Floor 1,
    // driven entirely through the typed command layer (no
    // scenario scripts touch the sim after founding). P1 lights
    // the way — the opening lantern route `open_floor1` would
    // place, issued as P1's own commands. P2 plants a camp plot,
    // then sets a timber support and rigs a vent on the first
    // face's stand once production has put goods in stores. The
    // streams are merged into the canonical order, applied, run
    // to production — and the whole session is replayed from its
    // log inside this section to prove the hashes match.
    let founding = build_scenario_gen(GEN_WORLD_SEED);
    let face = founding.faces.first().expect("gen founding has faces");
    let route = carved_path(&founding.world, founding.stockpile, face.stand)
        .expect("route is carved");
    let p1: Vec<PlayerCommand> = route
        .iter()
        .enumerate()
        .filter(|(i, _)| i % 4 == 3 || *i == route.len() - 1)
        .map(|(_, p)| *p)
        .collect::<Vec<Pos>>()
        .into_iter()
        .enumerate()
        .map(|(i, pos)| PlayerCommand {
            tick: 0,
            seq: i as u32,
            command: Command::Lantern { pos, tier: 1, fuel: 5_000.0 },
        })
        .collect();
    let plant_pos = (0..founding.world.sy as i32)
        .flat_map(|y| {
            (0..founding.world.sx as i32)
                .flat_map(move |x| (0..founding.world.sz as i32).map(move |z| Pos::new(x, y, z)))
        })
        .find(|p| {
            founding.world.get(*p) == Some(Cell::Carved)
                && *p != founding.stockpile
                && *p != founding.gate
                && !founding.beds.contains(p)
                && !founding.plots.iter().any(|pl| pl.pos == *p)
                && !founding.lanterns.iter().any(|l| l.pos == *p)
        })
        .expect("gen founding has a plantable camp cell");
    let stand = face.stand;
    let p2 = vec![
        PlayerCommand { tick: 0, seq: 0, command: Command::Plant { pos: plant_pos } },
        PlayerCommand { tick: 1_000, seq: 1, command: Command::Support { pos: stand } },
        PlayerCommand { tick: 1_000, seq: 2, command: Command::Vent { pos: stand } },
    ];
    let merged = merge_streams(&[(1, p1), (2, p2)]).expect("streams are well-formed");
    let mut s13 = Session::new(founding);
    s13.apply_merged(&merged).expect("merged entries apply");
    s13.run_to(6_200);
    let s13_log = s13.log();
    let applied_of = |player: u8| {
        s13_log.entries.iter().filter(|e| e.player == player && e.applied).count()
    };
    let replayed = replay(&s13_log).expect("the session log replays");
    let replay_matches = replayed.state_hash() == s13.sim().state_hash();
    println!(
        "S13 two-player session ({} ticks): P1 applied commands={}, P2 applied commands={}, goods={}, delvers alive={}, lost={}, replay_matches={}",
        s13.sim().tick_count,
        applied_of(1),
        applied_of(2),
        s13.sim().stores.goods,
        s13.sim().delvers.len(),
        count(s13.sim(), LedgerKind::DelverLost),
        replay_matches,
    );
    println!("S13 state hash: {}", s13.sim().state_hash());

    // ---- S16: the Crystal Dark's gate -------------------------------------
    // A colony founded on floor 4 comes prepared the way a
    // colony that delved there would: raw crystal in the stores
    // (mined at the band's crystal face — proven live in the
    // S16 tests), a cutter and a grinder assigned, and goods
    // for rope. Phase 1 runs the production jobs: lenses and a
    // set of quiet gear come out of the crystal. Phase 2 fits a
    // crystal-heart lantern at the deep crystal face — where a
    // plain lantern's light falls short (also proven in the
    // tests) — and ropes the descent cavern's brittle floor.
    let mut s16 = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    open_current_floor(&mut s16);
    s16.stores.crystal = 4;
    s16.stores.goods += 6;
    s16.set_job(0, Job::CrystalCutter);
    s16.set_job(1, Job::LensGrinder);
    for _ in 0..1500 {
        s16.tick();
    }
    // The pipeline ground every cut crystal into lenses; one
    // more cut crystal (staged, as a fifth hauled crystal's
    // cutting would leave) goes to quiet gear instead.
    s16.stores.cut_crystals += 1;
    let quiet_crafted = s16.craft_quiet_gear();
    println!(
        "S16 crystal dark production ({} ticks): raw crystal left={}, cut crystals={}, lenses={}, quiet gear crafted={}, quiet delvers={}, goods={}, lost={}",
        s16.tick_count,
        s16.stores.crystal,
        s16.stores.cut_crystals,
        s16.stores.lenses,
        quiet_crafted,
        s16.delvers.iter().filter(|d| d.quiet).count(),
        s16.stores.goods,
        count(&s16, LedgerKind::DelverLost),
    );
    let deep_stand = s16.faces[2].stand;
    s16.stores.fungal_oil += 1;
    let crystal_lantern = s16.place_lantern(deep_stand, 4, 5_000.0);
    let descent = s16.floor.as_ref().map(|f| f.descent).unwrap_or(s16.stockpile);
    let roped = s16.place_rope(descent);
    for _ in 0..1500 {
        s16.tick();
    }
    println!(
        "S16 crystal dark gate ({} ticks): crystal lantern fitted={}, descent roped={}, ropes laid={}, brittle collapses={}, goods={}, delvers alive={}, lost={}",
        s16.tick_count,
        crystal_lantern,
        roped,
        s16.ropes.len(),
        count(&s16, LedgerKind::BrittleCollapse),
        s16.stores.goods,
        s16.delvers.len(),
        count(&s16, LedgerKind::DelverLost),
    );
    println!("S16 state hash: {}", s16.state_hash());

    println!("deep ledger (S2):");
    for e in &sim.ledger {
        println!("  [{:>5}] {:?} — {}", e.tick, e.kind, e.detail);
    }
}
