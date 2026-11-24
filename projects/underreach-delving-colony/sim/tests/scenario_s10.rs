//! S10 acceptance: deeper band hazards — band-keyed exposure
//! on generated floors, Drowned flooding (water load, lantern
//! dousing) answered by pumps and sealed pressure lanterns,
//! and Magma heat (heat load) answered by cooling gear. Proven
//! in the S7 pattern: the hazards bite unprotected, each
//! answer stops exactly its own hazard, placement/cost rules
//! hold, and the slice stays deterministic.
//!
//! Choreography note: several proofs stage a delver at a
//! face stand and pin them there across ticks (the S9 staging
//! pattern), because a free-running colony works the first
//! face first — on the demo seed that face's stand can sit
//! above the deep zone. The colony-run engagement of flooding
//! and heat is proven by the scenario binary's S10 sections
//! (docs/TEST_PLAN.md); the staged proofs here pin the
//! mechanics themselves.

use underreach_sim::scenario::{
    build_scenario_gen_floor, open_current_floor, GEN_WORLD_SEED,
};
use underreach_sim::sim::{LedgerKind, Sim};
use underreach_sim::world::Pos;

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

fn count_for(sim: &Sim, kind: LedgerKind, name: &str) -> usize {
    sim.ledger
        .iter()
        .filter(|e| e.kind == kind && e.detail.contains(name))
        .count()
}

/// Pin delver 0 at `stand` for `ticks`, tracking their peak
/// loads. Returns (peak spore, peak water, peak heat).
fn pin_at_stand(sim: &mut Sim, stand: Pos, ticks: u32) -> (f32, f32, f32) {
    sim.delvers[0].pos = stand;
    let mut peaks = (0.0f32, 0.0f32, 0.0f32);
    for _ in 0..ticks {
        sim.tick();
        sim.delvers[0].pos = stand;
        let d = &sim.delvers[0];
        peaks.0 = peaks.0.max(d.spore);
        peaks.1 = peaks.1.max(d.water);
        peaks.2 = peaks.2.max(d.heat);
    }
    peaks
}

// ---------------------------------------------------------------------------
// Band-keyed exposure
// ---------------------------------------------------------------------------

#[test]
fn spores_engage_on_generated_floor_2_and_a_mask_protects() {
    // The deep faces of floor 2 stand in the band's spore zone:
    // an unmasked delver working there loads up and sickens.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    open_current_floor(&mut sim);
    let stand = sim.faces[1].stand; // (6, 7, 2) — deep zone
    assert!(sim.hazards_here(stand).spores, "the band keys the exposure");
    sim.place_lantern(stand, 1, 100_000.0); // the player carries light to the staging
    assert!(
        !sim.hazards_here(sim.stockpile).spores,
        "the camp shallows stay clean air"
    );
    let (spore, _, _) = pin_at_stand(&mut sim, stand, 2000);
    assert!(spore >= 100.0, "spore load maxes at the deep face, got {spore}");
    assert!(
        count_for(&sim, LedgerKind::DelverSick, "Bram") >= 1,
        "the spore-cough fires on generated floor 2"
    );

    // The same stand, masked: the load never moves at all —
    // a mask protects its wearer entirely.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 2);
    open_current_floor(&mut sim);
    sim.delvers[0].masked = true;
    let stand = sim.faces[1].stand;
    sim.place_lantern(stand, 1, 100_000.0);
    let (spore, _, _) = pin_at_stand(&mut sim, stand, 2000);
    assert_eq!(spore, 0.0, "a masked delver gains no spore load");
    assert_eq!(sim.delvers[0].spore, 0.0);
    assert_eq!(count_for(&sim, LedgerKind::DelverSick, "Bram"), 0);
}

#[test]
fn nothing_engages_on_generated_floor_1() {
    // Floor 1's band is clean: no flag is set, so no load of
    // any kind accrues even at the deepest face stand.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 1);
    open_current_floor(&mut sim);
    let stand = sim.faces[0].stand;
    let h = sim.hazards_here(stand);
    assert!(!h.spores && !h.flooded && !h.hot);
    let peaks = pin_at_stand(&mut sim, stand, 500);
    assert_eq!(peaks, (0.0, 0.0, 0.0), "no load engages on floor 1");
}

// ---------------------------------------------------------------------------
// Drowned flooding
// ---------------------------------------------------------------------------

#[test]
fn flooding_loads_and_downs_the_unprotected() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 3);
    open_current_floor(&mut sim);
    let stand = sim.faces[2].stand; // (19, 8, 4) — flooded deep zone
    assert!(sim.flooded_at(stand), "the deep face stands in flood water");
    sim.place_lantern(stand, 1, 100_000.0); // lit staging: the flood, not the dark, is the threat
    let (_, water, _) = pin_at_stand(&mut sim, stand, 2000);
    assert!(water >= 100.0, "water load maxes in the flood, got {water}");
    assert!(
        count_for(&sim, LedgerKind::DelverDrowning, "Bram") >= 1,
        "the drowning threshold fires"
    );

    // And the load can down: a hurt delver kept working the
    // flooded face (staged Mining, the S7 hurt-miner pattern —
    // a delver who rests between trips heals faster than the
    // drain, which is the flood's honest pace) is worn down
    // by the hp drain at a full load and goes onto the clock.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 3);
    open_current_floor(&mut sim);
    let stand = sim.faces[2].stand;
    sim.place_lantern(stand, 1, 100_000.0);
    sim.delvers[0].hp = 30.0;
    sim.delvers[0].pos = stand;
    sim.delvers[0].target_face = Some(2);
    for _ in 0..2000 {
        if sim.delvers[0].state != underreach_sim::sim::DelverState::Downed {
            sim.delvers[0].state = underreach_sim::sim::DelverState::Mining;
        }
        sim.tick();
        if sim.delvers[0].state != underreach_sim::sim::DelverState::Downed {
            sim.delvers[0].pos = stand;
        }
        if count(&sim, LedgerKind::DelverDowned) >= 1 {
            break;
        }
    }
    assert!(
        count(&sim, LedgerKind::DelverDowned) >= 1,
        "a delver kept in the flood is downed onto the rescue clock"
    );
}

#[test]
fn a_pump_keeps_its_reach_dry() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 3);
    open_current_floor(&mut sim);
    let stand = sim.faces[2].stand;
    sim.stores.goods += 1; // the colony brought a pump down
    assert!(sim.place_pump(stand));
    assert!(!sim.flooded_at(stand), "the pumped stand is dry");
    // A tier-1 lantern on the pumped stand: lit staging for the
    // pin, and proof the pump answers the dousing for its reach.
    assert!(sim.place_lantern(stand, 1, 5_000.0));
    let (_, water, _) = pin_at_stand(&mut sim, stand, 2000);
    assert_eq!(water, 0.0, "no water load accrues within the pump's reach");
    assert_eq!(sim.delvers[0].water, 0.0);
    assert_eq!(count_for(&sim, LedgerKind::DelverDrowning, "Bram"), 0);
    // The lantern on the pumped stand burned at its plain tier
    // rate for the whole pin (2,000 ticks × 0.02) — never doused.
    let lantern = sim.lanterns.iter().find(|l| l.pos == stand).unwrap();
    assert!(
        lantern.fuel > 4_900.0,
        "a pumped lantern is not doused, fuel={}",
        lantern.fuel
    );
}

#[test]
fn a_pressure_lantern_burns_where_a_tier1_is_doused() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 3);
    let wet = sim.faces[0].stand; // (3, 9, 2) — flooded deep zone
    let wet2 = sim.faces[1].stand; // (8, 8, 4) — flooded deep zone
    assert!(sim.flooded_at(wet) && sim.flooded_at(wet2));
    // Tier 3 is a tier-2+ placement: it draws the oil charge.
    assert!(!sim.place_lantern(wet2, 3, 100.0), "no oil, no pressure lantern");
    sim.stores.fungal_oil = 1;
    assert!(sim.place_lantern(wet, 1, 100.0), "tier-1 places freely");
    assert!(sim.place_lantern(wet2, 3, 100.0), "one oil charge places the pressure lantern");
    assert_eq!(sim.stores.fungal_oil, 0);
    for _ in 0..200 {
        sim.tick();
    }
    let t1 = sim.lanterns.iter().find(|l| l.pos == wet).unwrap();
    assert_eq!(t1.fuel, 0.0, "the unsealed lantern was doused by the flood water");
    assert!(count(&sim, LedgerKind::LanternDoused) >= 1, "the dousing is ledgered");
    let t3 = sim.lanterns.iter().find(|l| l.pos == wet2).unwrap();
    assert!(t3.fuel > 90.0, "the sealed pressure lantern keeps burning, fuel={}", t3.fuel);
    let wet2_idx = sim.world.idx(wet2).unwrap();
    assert!(
        sim.lit[wet2_idx],
        "the pressure lantern's cell is lit in the flood"
    );
}

// ---------------------------------------------------------------------------
// Magma heat
// ---------------------------------------------------------------------------

#[test]
fn heat_loads_the_unprotected() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 5);
    open_current_floor(&mut sim);
    let stand = sim.faces[0].stand; // (8, 6, 2) — hot deep zone
    assert!(sim.hazards_here(stand).hot, "the band keys the heat");
    sim.place_lantern(stand, 1, 100_000.0); // lit staging
    let (_, _, heat) = pin_at_stand(&mut sim, stand, 2000);
    assert!(heat >= 100.0, "heat load maxes in the hot zone, got {heat}");
    assert!(
        count_for(&sim, LedgerKind::DelverOverheating, "Bram") >= 1,
        "the overheating threshold fires"
    );
}

#[test]
fn cooling_gear_prevents_heat_entirely() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 5);
    // Crafted at camp and equipped there, as a player's would
    // be — Bram is still at camp at founding, so his first
    // camp decision equips the gear before he heads out.
    sim.stores.goods += 2;
    assert!(sim.craft_cooling_gear());
    for _ in 0..50 {
        sim.tick();
    }
    open_current_floor(&mut sim);
    assert!(sim.delvers[0].cooled, "Bram equipped the cooling gear at camp");
    let stand = sim.faces[0].stand;
    let (_, _, heat) = pin_at_stand(&mut sim, stand, 2000);
    assert_eq!(heat, 0.0, "cooling gear prevents any heat gain");
    assert_eq!(sim.delvers[0].heat, 0.0);
    assert_eq!(count_for(&sim, LedgerKind::DelverOverheating, "Bram"), 0);
}

// ---------------------------------------------------------------------------
// Placement & cost rules
// ---------------------------------------------------------------------------

#[test]
fn pumps_and_cooling_gear_follow_the_kit_rules() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 3);
    let camp = sim.stockpile; // carved
    let rock = Pos::new(0, 5, 0); // solid stone
    // A broke colony places and crafts nothing.
    assert_eq!(sim.stores.goods, 0);
    assert!(!sim.place_pump(camp));
    assert!(!sim.craft_cooling_gear());
    // Solid rock refuses a pump even with goods in hand.
    sim.stores.goods = 3;
    assert!(!sim.place_pump(rock));
    assert_eq!(sim.stores.goods, 3);
    // A pump costs 1 goods; no stacking a second on its cell.
    assert!(sim.place_pump(camp));
    assert_eq!(sim.stores.goods, 2);
    assert!(!sim.place_pump(camp));
    // Cooling gear costs 2 goods, the mask's price.
    assert!(sim.craft_cooling_gear());
    assert_eq!(sim.stores.goods, 0);
    assert_eq!(sim.stores.cooling_gear, 1);
    assert!(!sim.craft_cooling_gear(), "broke again: refused");
    assert_eq!(sim.pumps.len(), 1);
}

// ---------------------------------------------------------------------------
// Determinism on the new bands
// ---------------------------------------------------------------------------

fn determinism_on(floor: u32) {
    let mut a = build_scenario_gen_floor(GEN_WORLD_SEED, floor);
    let mut b = build_scenario_gen_floor(GEN_WORLD_SEED, floor);
    for sim in [&mut a, &mut b] {
        open_current_floor(sim);
    }
    for _ in 0..1500 {
        a.tick();
        b.tick();
    }
    assert_eq!(a.state_hash(), b.state_hash(), "floor {floor}: twin-run identical");
    let saved = a.save_json();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), a.state_hash(), "floor {floor}: load reproduces the hash");
    for _ in 0..300 {
        a.tick();
        loaded.tick();
    }
    assert_eq!(a.state_hash(), loaded.state_hash(), "floor {floor}: continuation identical");
}

#[test]
fn s10_stays_deterministic_on_a_flooded_floor() {
    determinism_on(3);
}

#[test]
fn s10_stays_deterministic_on_a_hot_floor() {
    determinism_on(5);
}
