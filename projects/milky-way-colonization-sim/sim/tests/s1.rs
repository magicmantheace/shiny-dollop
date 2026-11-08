//! S1 integration tests: determinism, fuel, colonization rules,
//! save/load continuity, construction, and the scripted campaign.

use mwcs_pipeline::table::{PlanetRecord, StarRecord};
use mwcs_sim::{Campaign, Galaxy, Purpose, ScriptedPolicy, ShipKind, ShipState, SimError};

fn star(
    id: u32,
    name: &str,
    pos: [f32; 3],
    teff: f32,
    spectral: u8,
    planets: Vec<PlanetRecord>,
) -> StarRecord {
    StarRecord {
        id,
        pos_ly: pos,
        absmag: 4.8,
        bv: 0.65,
        teff,
        mass: 1.0,
        spectral,
        flags: 0,
        planets,
        name: name.into(),
    }
}

fn earthlike_planet(host: &str) -> PlanetRecord {
    PlanetRecord {
        name: format!("{host} b"),
        period_days: 365.0,
        semimajor_au: 1.0,
        radius_earth: 1.0,
        mass_earth: 1.0,
        eq_temp: 273.0,
        disc_year: 2024,
        method: 2,
        flags: 0b1111,
    }
}

/// Sol + one habitable neighbour 10 ly away.
fn two_star_galaxy() -> Galaxy {
    Galaxy::from_star_records(vec![
        star(0, "Sol", [0.0, 0.0, 0.0], 5778.0, 4, vec![]),
        star(
            1,
            "Haven",
            [10.0, 0.0, 0.0],
            5200.0,
            5,
            vec![earthlike_planet("Haven")],
        ),
    ])
}

/// Sol + two stars in a 60 ly chain (for range/fuel-edge tests).
fn chain_galaxy() -> Galaxy {
    Galaxy::from_star_records(vec![
        star(0, "Sol", [0.0, 0.0, 0.0], 5778.0, 4, vec![]),
        star(1, "Midway", [60.0, 0.0, 0.0], 5200.0, 5, vec![]),
        star(2, "Farpoint", [120.0, 0.0, 0.0], 5200.0, 5, vec![]),
    ])
}

fn ship_by_kind(sim: &Campaign, kind: ShipKind) -> u32 {
    sim.ships()
        .values()
        .find(|ship| sim.design(ship.design_idx).map(|d| d.kind) == Some(kind))
        .map(|ship| ship.id)
        .expect("ship of kind exists")
}

fn run_policy_days(sim: &mut Campaign, galaxy: &Galaxy, days: u64) {
    let mut policy = ScriptedPolicy;
    for _ in 0..days {
        policy.step(sim, galaxy);
        sim.advance(galaxy, 1);
    }
}

fn survey_haven(sim: &mut Campaign, galaxy: &Galaxy) {
    let surveyor = ship_by_kind(sim, ShipKind::Surveyor);
    sim.dispatch_ship(galaxy, surveyor, 1, Purpose::Survey)
        .unwrap();
    // 34 travel days + at most ~40 survey days.
    sim.advance(galaxy, 90);
    assert!(matches!(
        sim.ship(surveyor).unwrap().state,
        ShipState::AtSystem { system: 1 }
    ));
    assert_eq!(
        sim.system(1).map(|s| s.survey),
        Some(mwcs_sim::SurveyState::Surveyed)
    );
}

#[test]
fn chunked_vs_single_advance_identical_hash() {
    let galaxy = two_star_galaxy();
    let mut a = Campaign::new_default(&galaxy, 7).unwrap();
    let mut b = Campaign::new_default(&galaxy, 7).unwrap();
    let mut c = Campaign::new_default(&galaxy, 7).unwrap();
    for sim in [&mut a, &mut b, &mut c] {
        let surveyor = ship_by_kind(sim, ShipKind::Surveyor);
        sim.dispatch_ship(&galaxy, surveyor, 1, Purpose::Survey)
            .unwrap();
    }
    a.advance(&galaxy, 3_650);
    for _ in 0..365 {
        b.advance(&galaxy, 10);
    }
    for _ in 0..3_650 {
        c.advance(&galaxy, 1);
    }
    assert_eq!(a.state_hash(), b.state_hash());
    assert_eq!(a.state_hash(), c.state_hash());
    assert_eq!(a.canonical_bytes(), c.canonical_bytes());
}

#[test]
fn save_load_at_year_5_matches_uninterrupted_campaign() {
    let galaxy = two_star_galaxy();
    let mut uninterrupted = Campaign::new_default(&galaxy, 11).unwrap();
    run_policy_days(&mut uninterrupted, &galaxy, 3_650);

    let mut interrupted = Campaign::new_default(&galaxy, 11).unwrap();
    run_policy_days(&mut interrupted, &galaxy, 1_825);
    let saved = interrupted.save_bytes();
    let mut restored = Campaign::load_bytes(&galaxy, &saved).unwrap();
    assert_eq!(interrupted.state_hash(), restored.state_hash());
    run_policy_days(&mut restored, &galaxy, 1_825);

    assert_eq!(uninterrupted.state_hash(), restored.state_hash());
    assert!(uninterrupted.colonized_count() >= 2);
}

#[test]
fn dispatch_beyond_design_range_is_refused() {
    let galaxy = chain_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 3).unwrap();
    let surveyor = ship_by_kind(&sim, ShipKind::Surveyor);
    // Sol -> Farpoint is 120 ly; the surveyor's range is 75 ly.
    let err = sim
        .dispatch_ship(&galaxy, surveyor, 2, Purpose::Survey)
        .unwrap_err();
    assert!(matches!(err, SimError::BeyondRange { .. }));
}

#[test]
fn fuel_consumption_matches_distance_and_refuel_restores_range() {
    let galaxy = two_star_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 5).unwrap();
    let surveyor = ship_by_kind(&sim, ShipKind::Surveyor);
    sim.dispatch_ship(&galaxy, surveyor, 1, Purpose::Survey)
        .unwrap();
    sim.advance(&galaxy, 34); // 10 ly at 0.30 ly/day, arrival on day 34
    let fuel_after = sim.ship(surveyor).unwrap().fuel;
    // Burn is exactly distance * fuel_per_ly = 10 * 2.0 = 20.
    assert!((fuel_after - 130.0).abs() < 1e-6, "fuel was {fuel_after}");

    // Finish the survey, claim, and send the colony ship.
    sim.advance(&galaxy, 60);
    sim.claim_system(1).unwrap();
    let colony_ship = ship_by_kind(&sim, ShipKind::Colony);
    sim.dispatch_ship(&galaxy, colony_ship, 1, Purpose::Colonize)
        .unwrap();
    sim.advance(&galaxy, 60); // colony founded on arrival
    assert_eq!(sim.colonized_count(), 2);

    // The surveyor refuels to a full tank from the new colony.
    let transferred = sim.refuel_ship(surveyor).unwrap();
    assert!((transferred - 20.0).abs() < 1e-6);
    let ship = sim.ship(surveyor).unwrap();
    let design = sim.design(ship.design_idx).unwrap();
    assert!((ship.fuel - design.tank_capacity).abs() < 1e-6);
    // Full tank = full design range again, and the 10 ly trip home is
    // comfortably affordable.
    assert!(ship.fuel >= 10.0 * design.fuel_per_ly);
}

#[test]
fn insufficient_fuel_refused_and_unchecked_order_strands_en_route() {
    let galaxy = chain_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 9).unwrap();
    let surveyor = ship_by_kind(&sim, ShipKind::Surveyor);
    // Sol -> Midway: 60 ly, burns 120 of 150 fuel, 200 travel days.
    sim.dispatch_ship(&galaxy, surveyor, 1, Purpose::Survey)
        .unwrap();
    sim.advance(&galaxy, 260); // travel + survey of Midway
    let ship = sim.ship(surveyor).unwrap();
    assert!(matches!(ship.state, ShipState::AtSystem { system: 1 }));
    assert!((ship.fuel - 30.0).abs() < 1e-6);

    // Midway -> Farpoint needs 120 fuel; only 30 are aboard.
    let err = sim
        .dispatch_ship(&galaxy, surveyor, 2, Purpose::Survey)
        .unwrap_err();
    assert!(matches!(err, SimError::InsufficientFuel { .. }));

    // The deliberate one-way order departs anyway and stops dry:
    // 30 fuel / 2 per ly = 15 ly of progress.
    sim.dispatch_ship_unchecked(&galaxy, surveyor, 2, Purpose::Survey)
        .unwrap();
    sim.advance(&galaxy, 60);
    let ship = sim.ship(surveyor).unwrap();
    match ship.state {
        ShipState::StrandedEnRoute {
            from,
            to,
            progress_ly,
            ..
        } => {
            assert_eq!((from, to), (1, 2));
            assert!((progress_ly - 15.0).abs() < 1e-6, "progress {progress_ly}");
        }
        ref other => panic!("expected stranded en route, got {other:?}"),
    }
    assert!(ship.fuel.abs() < 1e-9);
}

#[test]
fn arrival_on_empty_tanks_still_surveys() {
    // A target exactly at the edge of the design range: 75 ly burns
    // the surveyor's whole 150-unit tank. The ship is stranded for
    // movement on arrival, but surveying is local sensor work and
    // must proceed (otherwise the ship deadlocks: it cannot refuel
    // without a colony, and no colony can follow to an unsurveyed
    // system).
    let galaxy = Galaxy::from_star_records(vec![
        star(0, "Sol", [0.0, 0.0, 0.0], 5778.0, 4, vec![]),
        star(1, "Edge", [75.0, 0.0, 0.0], 5200.0, 5, vec![]),
    ]);
    let mut sim = Campaign::new_default(&galaxy, 41).unwrap();
    let surveyor = ship_by_kind(&sim, ShipKind::Surveyor);
    sim.dispatch_ship(&galaxy, surveyor, 1, Purpose::Survey)
        .unwrap();
    sim.advance(&galaxy, 250); // 75 ly at 0.30 ly/day
    let ship = sim.ship(surveyor).unwrap();
    assert!(ship.fuel.abs() < 1e-9);
    assert!(
        matches!(ship.state, ShipState::Surveying { system: 1, .. }),
        "state was {:?}",
        ship.state
    );
    sim.advance(&galaxy, 60);
    assert_eq!(
        sim.system(1).map(|s| s.survey),
        Some(mwcs_sim::SurveyState::Surveyed)
    );
}

#[test]
fn cannot_colonize_unsurveyed_system() {
    let galaxy = two_star_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 13).unwrap();
    let colony_ship = ship_by_kind(&sim, ShipKind::Colony);
    let err = sim
        .dispatch_ship(&galaxy, colony_ship, 1, Purpose::Colonize)
        .unwrap_err();
    assert!(matches!(err, SimError::SystemNotSurveyed(1)));
}

#[test]
fn claim_must_precede_founding() {
    let galaxy = two_star_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 17).unwrap();
    survey_haven(&mut sim, &galaxy);
    let colony_ship = ship_by_kind(&sim, ShipKind::Colony);
    let err = sim
        .dispatch_ship(&galaxy, colony_ship, 1, Purpose::Colonize)
        .unwrap_err();
    assert!(matches!(err, SimError::SystemNotClaimed(1)));
    sim.claim_system(1).unwrap();
    sim.dispatch_ship(&galaxy, colony_ship, 1, Purpose::Colonize)
        .unwrap();
}

#[test]
fn colony_growth_is_positive_and_bounded() {
    let galaxy = two_star_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 19).unwrap();
    survey_haven(&mut sim, &galaxy);
    sim.claim_system(1).unwrap();
    let colony_ship = ship_by_kind(&sim, ShipKind::Colony);
    sim.dispatch_ship(&galaxy, colony_ship, 1, Purpose::Colonize)
        .unwrap();
    sim.advance(&galaxy, 60);
    let colony = sim.system(1).and_then(|s| s.colony.as_ref()).unwrap();
    let initial_pop = colony.population_millions;
    // Founded at 0.25M; a monthly settlement may already have applied
    // a first growth step by the time the travel window ends.
    assert!(
        (0.25..0.26).contains(&initial_pop),
        "initial pop {initial_pop}"
    );

    sim.advance(&galaxy, 365);
    let colony = sim.system(1).and_then(|s| s.colony.as_ref()).unwrap();
    assert!(colony.population_millions > initial_pop);
    // Logistic bound: nowhere near the ~3,675M carrying capacity of a
    // 98%-habitable, development-1 system after a single year.
    assert!(colony.population_millions < 10.0);
    assert!(colony.supplied);
}

#[test]
fn ship_construction_queue_produces_a_ship() {
    let galaxy = two_star_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 23).unwrap();
    let home = sim.home_system();
    let before = sim.ships().len();
    sim.build_ship(home, 0).unwrap(); // a surveyor, 90 build days
    sim.advance(&galaxy, 90);
    assert_eq!(sim.ships().len(), before + 1);
}

#[test]
fn scripted_campaign_expands_from_sol() {
    let galaxy = two_star_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 29).unwrap();
    run_policy_days(&mut sim, &galaxy, 3 * 365);
    assert!(sim.surveyed_count() >= 2);
    assert!(sim.colonized_count() >= 2);
    assert!(sim.total_population_millions() > 1_200.0);
}

#[test]
fn save_rejects_a_different_galaxy() {
    let galaxy = two_star_galaxy();
    let other = chain_galaxy();
    let sim = Campaign::new_default(&galaxy, 31).unwrap();
    let err = Campaign::load_bytes(&other, &sim.save_bytes()).unwrap_err();
    assert!(matches!(err, SimError::GalaxyMismatch));
}

#[test]
fn advance_100_years_completes() {
    let galaxy = two_star_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 37).unwrap();
    let surveyor = ship_by_kind(&sim, ShipKind::Surveyor);
    sim.dispatch_ship(&galaxy, surveyor, 1, Purpose::Survey)
        .unwrap();
    sim.advance(&galaxy, 36_500);
    assert_eq!(sim.day(), 36_500);
    assert_eq!(sim.state_hash().len(), 64);
}
