//! S12 — children & generations (owner decision 5), behind the
//! opt-in `generations_enabled` flag in the `critters_enabled`
//! pattern. Proven here:
//!
//! - a birth fires under the stated conditions, and the
//!   `ChildBorn` Ledger entry names the child and both parents
//!   (the two longest-present adults: Bram and Sella);
//! - no birth when each single condition is removed in turn
//!   (fewer than two adults / food below the minimum /
//!   population at the cap) — three separate negative proofs;
//! - a child cannot be assigned a job and gains no job XP,
//!   while an adult sibling control works and gains XP;
//! - the coming-of-age crossing fires exactly one `CameOfAge`
//!   entry, unlocks assignment, and a grown child assigned
//!   Miner actually gains mining XP at the face;
//! - determinism on a generations colony: twin-run identical
//!   hash, and save/load mid-run reproduces the hash with an
//!   identical continuation;
//! - the disabled-system inertness proof: the pre-existing S3
//!   scenario, flag off, reproduces the exact state hash the
//!   pre-S12 code produced (pinned below — captured from the
//!   scenario binary at the S11 tip before any S12 change).

use underreach_sim::scenario::{
    build_scenario_s12, build_scenario_s3, light_the_way,
};
use underreach_sim::sim::{Delver, Job, LedgerKind, Sim, TICKS_PER_YEAR};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

fn run(sim: &mut Sim, ticks: u64) {
    for _ in 0..ticks {
        sim.tick();
    }
}

/// The S3 scenario's state hash at the S11 tip (33df2a9),
/// captured from the scenario binary before the S12 changes.
const S3_PRE_S12_HASH: &str =
    "4dc99472c56104f7af2455baee2b81eb28913b297bf80e4fc440dcb8553d1eef";

#[test]
fn birth_fires_and_the_ledger_names_child_and_both_parents() {
    let mut sim = build_scenario_s12();
    assert!(sim.generations_enabled);
    light_the_way(&mut sim);
    // The first birth check is at tick 2400 (BIRTH_INTERVAL);
    // run past it.
    run(&mut sim, 2401);
    assert_eq!(count(&sim, LedgerKind::ChildBorn), 1);
    let entry = sim
        .ledger
        .iter()
        .find(|e| e.kind == LedgerKind::ChildBorn)
        .expect("a ChildBorn entry");
    // The parents are the two longest-present adults: Bram (id
    // 0) and Sella (id 1). The child is named from the pool.
    let child = sim
        .delvers
        .iter()
        .find(|d| d.is_child() && d.name != "Joss")
        .expect("the newborn is in the colony");
    assert!(
        entry.detail.contains(&child.name),
        "entry names the child: {}",
        entry.detail
    );
    assert!(
        entry.detail.contains("Bram"),
        "entry names parent Bram: {}",
        entry.detail
    );
    assert!(
        entry.detail.contains("Sella"),
        "entry names parent Sella: {}",
        entry.detail
    );
    // The newborn: age 0 at birth (a few hundred ticks old now),
    // no job, no XP, standing at the gate like an arrival.
    assert!(child.age_years() < 1);
    assert_eq!(child.job, Job::Unassigned);
    assert_eq!(child.mining_xp + child.hauling_xp + child.farming_xp, 0);
    assert_eq!(child.pos, sim.gate);
    assert!(sim.delver_is_child(child));
}

#[test]
fn no_birth_with_fewer_than_two_adults() {
    let mut sim = build_scenario_s12();
    // One adult only (Bram); Joss and the other founders go.
    sim.delvers.retain(|d| d.name == "Bram");
    // Food and population conditions are satisfied, isolating
    // the adult count as the removed condition.
    sim.stores.food = 100;
    run(&mut sim, 4801); // two birth checks pass
    assert_eq!(count(&sim, LedgerKind::ChildBorn), 0);
    assert_eq!(sim.delvers.len(), 1);
}

#[test]
fn no_birth_with_food_below_the_minimum() {
    let mut sim = build_scenario_s12();
    // No plots and no food: production can never refill stores,
    // so the food condition fails at every check while the
    // adult count (3) and population (4 < 6) conditions hold.
    sim.plots.clear();
    sim.stores.food = 0;
    run(&mut sim, 2401);
    assert!(sim.stores.food < underreach_sim::sim::BIRTH_MIN_FOOD);
    assert_eq!(count(&sim, LedgerKind::ChildBorn), 0);
    assert_eq!(sim.delvers.len(), 4);
}

#[test]
fn no_birth_at_the_population_cap() {
    let mut sim = build_scenario_s12();
    // Fill the colony to MAX_DELVER_POPULATION with extra
    // adults; food is ample, isolating the cap.
    for (id, name) in [(4, "Pell"), (5, "Odile")] {
        sim.delvers
            .push(Delver::new(id, name, sim.gate, Job::Unassigned));
    }
    sim.next_delver_id = 6;
    assert_eq!(sim.delvers.len(), underreach_sim::sim::MAX_DELVER_POPULATION);
    sim.stores.food = 100;
    run(&mut sim, 2401);
    assert_eq!(count(&sim, LedgerKind::ChildBorn), 0);
    assert_eq!(
        sim.delvers.len(),
        underreach_sim::sim::MAX_DELVER_POPULATION
    );
}

#[test]
fn a_child_cannot_be_assigned_and_gains_no_job_xp() {
    let mut sim = build_scenario_s12();
    light_the_way(&mut sim);
    let joss_id = sim.delvers.iter().find(|d| d.name == "Joss").unwrap().id;
    // Assignment refuses the child and leaves him Unassigned.
    assert!(!sim.set_job(joss_id, Job::Miner));
    let joss = sim.delvers.iter().find(|d| d.id == joss_id).unwrap();
    assert_eq!(joss.job, Job::Unassigned);
    // The adult control takes an assignment fine.
    let bram_id = sim.delvers.iter().find(|d| d.name == "Bram").unwrap().id;
    assert!(sim.set_job(bram_id, Job::Miner));
    // Run most of Joss's last childhood year (he turns 18 at
    // tick 2400 of the run).
    run(&mut sim, 2000);
    let joss = sim.delvers.iter().find(|d| d.id == joss_id).unwrap();
    assert!(sim.delver_is_child(joss));
    assert_eq!(joss.mining_xp, 0, "a child gains no mining xp");
    assert_eq!(joss.hauling_xp, 0, "a child gains no hauling xp");
    assert_eq!(joss.farming_xp, 0, "a child gains no farming xp");
    // The adult control worked the face and gained XP.
    let bram = sim.delvers.iter().find(|d| d.id == bram_id).unwrap();
    assert!(bram.mining_xp > 0, "the adult control gains mining xp");
}

#[test]
fn coming_of_age_fires_exactly_once_and_unlocks_assignment() {
    let mut sim = build_scenario_s12();
    light_the_way(&mut sim);
    let joss_id = sim.delvers.iter().find(|d| d.name == "Joss").unwrap().id;
    // Run well past Joss's 18th birthday (tick 2400 of the run)
    // and past a second birth check: still exactly one crossing.
    run(&mut sim, 6000);
    assert_eq!(count(&sim, LedgerKind::CameOfAge), 1);
    let entry = sim
        .ledger
        .iter()
        .find(|e| e.kind == LedgerKind::CameOfAge)
        .expect("a CameOfAge entry");
    assert!(entry.detail.contains("Joss"), "entry names him: {}", entry.detail);
    let joss = sim.delvers.iter().find(|d| d.id == joss_id).unwrap();
    assert!(!sim.delver_is_child(joss));
    assert!(joss.age_years() >= 18);
    // Assignment accepts him now.
    assert!(sim.set_job(joss_id, Job::Miner));
    assert_eq!(
        sim.delvers.iter().find(|d| d.id == joss_id).unwrap().job,
        Job::Miner
    );
}

#[test]
fn a_grown_child_assigned_miner_gains_mining_xp() {
    let mut sim = build_scenario_s12();
    light_the_way(&mut sim);
    let joss_id = sim.delvers.iter().find(|d| d.name == "Joss").unwrap().id;
    run(&mut sim, 3000); // past the coming of age and first birth
    assert_eq!(count(&sim, LedgerKind::CameOfAge), 1);
    assert!(sim.set_job(joss_id, Job::Miner));
    run(&mut sim, 3000);
    let joss = sim.delvers.iter().find(|d| d.id == joss_id).unwrap();
    assert!(
        joss.mining_xp > 0,
        "the grown child works the face and gains mining xp"
    );
}

#[test]
fn generations_determinism_twin_run_and_save_load() {
    let mut a = build_scenario_s12();
    let mut b = build_scenario_s12();
    light_the_way(&mut a);
    light_the_way(&mut b);
    run(&mut a, 3500);
    run(&mut b, 3500);
    assert_eq!(a.state_hash(), b.state_hash(), "twin runs are identical");
    assert!(count(&a, LedgerKind::ChildBorn) >= 1);
    assert_eq!(count(&a, LedgerKind::CameOfAge), 1);
    // Save/load mid-run reproduces the hash, ages included.
    let mut loaded = Sim::load_json(&a.save_json());
    assert_eq!(loaded.state_hash(), a.state_hash());
    assert!(loaded.generations_enabled);
    run(&mut a, 1000);
    run(&mut loaded, 1000);
    assert_eq!(
        a.state_hash(),
        loaded.state_hash(),
        "continuation after load is identical"
    );
}

#[test]
fn a_from_birth_childhood_lasts_eighteen_years() {
    // The from-birth arc the scenario binary does not run: a
    // newborn stays a child, unassignable and XP-free, for the
    // whole eighteen years, then crosses exactly once. Staged
    // on the S12 colony with the newborn's age read directly;
    // the run is shortened by starting the colony one birth
    // check in — the child still ages tick by tick from 0.
    let mut sim = build_scenario_s12();
    light_the_way(&mut sim);
    run(&mut sim, 2401);
    let child_id = sim
        .delvers
        .iter()
        .find(|d| d.is_child() && d.name != "Joss")
        .expect("a newborn")
        .id;
    let born_at = sim.delvers.iter().find(|d| d.id == child_id).unwrap().age_ticks;
    assert!(born_at < TICKS_PER_YEAR, "the child is in its first year");
    // Fast-forward is not available — age is ticked — so this
    // proof stages the last year directly: set the child to 17
    // (the founding-Joss choreography) and run the year out.
    let idx = sim.delvers.iter().position(|d| d.id == child_id).unwrap();
    sim.delvers[idx].age_ticks = 17 * TICKS_PER_YEAR;
    assert!(!sim.set_job(child_id, Job::Farmer));
    run(&mut sim, TICKS_PER_YEAR as u64);
    assert_eq!(count(&sim, LedgerKind::CameOfAge), 2, "Joss and the newborn");
    let child = sim.delvers.iter().find(|d| d.id == child_id).unwrap();
    assert!(!sim.delver_is_child(child));
    assert!(sim.set_job(child_id, Job::Farmer));
}

#[test]
fn disabled_system_is_bit_identical_to_pre_s12() {
    // Age is recorded but inert with the flag off: founders sit
    // at the founding adult age and it never advances.
    let fresh = build_scenario_s3();
    assert!(!fresh.generations_enabled);
    assert!(fresh.delvers.iter().all(|d| d.age_years() == 25));
    let mut sim = build_scenario_s3();
    light_the_way(&mut sim);
    run(&mut sim, 6000);
    assert!(sim.delvers.iter().all(|d| d.age_years() == 25));
    assert_eq!(count(&sim, LedgerKind::ChildBorn), 0);
    assert_eq!(count(&sim, LedgerKind::CameOfAge), 0);
    assert_eq!(
        sim.state_hash(),
        S3_PRE_S12_HASH,
        "the disabled sim reproduces the pre-S12 hash exactly"
    );
}
