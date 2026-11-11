//! S5 acceptance: the Fungal Reaches gate set — spores sicken the
//! unmasked, masks protect, the oil flows home and lights tier-2
//! lanterns, and a herbalist speeds recovery. Plus the band
//! recombination table that makes depth endless.

use underreach_sim::scenario::{build_scenario_s5, light_the_deep};
use underreach_sim::sim::{hazards_at, LedgerKind, Sim};
use underreach_sim::world::Pos;

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

#[test]
fn unmasked_miner_gets_the_spore_cough_and_brings_oil_home() {
    let mut sim = build_scenario_s5();
    light_the_deep(&mut sim);
    for _ in 0..5000 {
        sim.tick();
    }
    assert!(
        count(&sim, LedgerKind::DelverSick) >= 1,
        "someone working the fungal face unmasked should fall sick"
    );
    assert!(
        sim.stores.fungal_oil >= 1,
        "fungal oil should reach the stores, oil={}",
        sim.stores.fungal_oil
    );
}

#[test]
fn a_mask_protects_its_wearer() {
    let mut sim = build_scenario_s5();
    // The scenario starts with 4 goods: exactly two masks.
    assert!(sim.craft_mask());
    assert!(sim.craft_mask());
    assert_eq!(sim.stores.masks, 2);
    light_the_deep(&mut sim);
    for _ in 0..4000 {
        sim.tick();
    }
    let bram = sim.delvers.iter().find(|d| d.name == "Bram").unwrap();
    assert!(bram.masked, "Bram should have equipped a mask at camp");
    assert!(
        !sim.ledger
            .iter()
            .any(|e| e.kind == LedgerKind::DelverSick && e.detail.contains("Bram")),
        "the masked miner should never get the spore-cough"
    );
    assert!(sim.stores.fungal_oil >= 1, "the oil still flows");
}

#[test]
fn tier2_lanterns_need_oil() {
    let mut sim = build_scenario_s5();
    let before = sim.lanterns.len();
    // No oil: refused, nothing placed, nothing charged.
    assert!(!sim.place_lantern(Pos::new(7, 14, 4), 2, 500.0));
    assert_eq!(sim.lanterns.len(), before);
    // One charge of oil: placed, oil spent.
    sim.stores.fungal_oil = 1;
    assert!(sim.place_lantern(Pos::new(7, 14, 4), 2, 500.0));
    assert_eq!(sim.stores.fungal_oil, 0);
    assert_eq!(sim.lanterns.len(), before + 1);
    // And the next one is refused again.
    assert!(!sim.place_lantern(Pos::new(5, 14, 4), 2, 500.0));
}

#[test]
fn a_herbalist_speeds_recovery() {
    // Recovery speed is the claim: from spore 90 to well (<30).
    // With Wren tending, care + clean air clear ~1.0/tick; without
    // a herbalist, clean air alone manages 0.15/tick (~400 ticks).
    // (The endpoint can't be "spore at tick N": a recovered miner
    // walks straight back into the band and re-exposes — which is
    // what masks are for.)
    let mut sim = build_scenario_s5();
    light_the_deep(&mut sim);
    sim.delvers.iter_mut().find(|d| d.name == "Bram").unwrap().spore = 90.0;
    let mut recovered_at = None;
    for t in 0..150 {
        sim.tick();
        if sim.delvers.iter().find(|d| d.name == "Bram").unwrap().spore < 30.0 {
            recovered_at = Some(t);
            break;
        }
    }
    assert!(
        recovered_at.is_some(),
        "with Wren tending him, Bram should be well within 150 ticks"
    );

    // Control: same colony, Wren reassigned to farming — no care.
    let mut sim = build_scenario_s5();
    light_the_deep(&mut sim);
    let wren_id = sim.delvers.iter().find(|d| d.name == "Wren").unwrap().id;
    sim.set_job(wren_id, underreach_sim::sim::Job::Farmer);
    sim.delvers.iter_mut().find(|d| d.name == "Bram").unwrap().spore = 90.0;
    for _ in 0..150 {
        sim.tick();
    }
    let bram = sim.delvers.iter().find(|d| d.name == "Bram").unwrap();
    assert!(
        bram.spore >= 60.0,
        "without a herbalist, Bram should still be sick at 150 ticks, spore={:.0}",
        bram.spore
    );
}

#[test]
fn hazards_recombine_with_depth() {
    let clean = hazards_at(3);
    assert!(!clean.spores && !clean.flooded && !clean.hot);
    let fungal = hazards_at(12);
    assert!(fungal.spores && !fungal.flooded && !fungal.hot);
    let spore_flood = hazards_at(20);
    assert!(spore_flood.spores && spore_flood.flooded && !spore_flood.hot);
    let spore_heat = hazards_at(28);
    assert!(spore_heat.spores && !spore_heat.flooded && spore_heat.hot);
    let flood_heat = hazards_at(36);
    assert!(!flood_heat.spores && flood_heat.flooded && flood_heat.hot);
    // And it keeps cycling, endlessly.
    assert_eq!(hazards_at(44), fungal);
}

#[test]
fn s5_stays_deterministic() {
    let mut a = build_scenario_s5();
    light_the_deep(&mut a);
    let mut b = build_scenario_s5();
    light_the_deep(&mut b);
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
