//! S5 integration tests: war & victory (design §5.3, §6.4, §6.5,
//! §3). War declaration and its treaty consequences, deterministic
//! fleet combat with counted losses, retreat, invasion and
//! occupation with its resistance schedule, blockade starvation,
//! peace cessions, the gate lifecycle (build, pair, transit,
//! throughput, treaty access, destruction), gate-fed trade,
//! terraforming against the natural baseline, the victory rules,
//! AI wars that conclude in peace, and catch-up/save equivalence
//! with S5 mechanics active (§11.1).
//!
//! Counterparties follow the S4 convention: archetypes are
//! assigned by civ index (civ 1 is always a Merchant League).
//! Timelines the tests rely on were measured, not assumed: a
//! homeworld reaches development 6 in ~4 years and 7 in ~5; a
//! frontier colony founded on a high-habitability exotics system
//! reaches development 7 with a full exotics stock in ~510 years
//! (the long-game test pays that advance once and exercises gates,
//! trade, terraforming, and gate destruction inside it).

use mwcs_pipeline::table::{PlanetRecord, StarRecord};
use mwcs_sim::race::HomeworldRules;
use mwcs_sim::{
    Campaign, DealOutcome, EventKind, Galaxy, GameSetup, PeaceTerms, Purpose, ShipKind, SimError,
    Specialization, TreatyKind, VictoryRule, PLAYER_CIV, TRANSLATION_DAYS,
};

fn star(id: u32, name: &str, pos: [f32; 3], spectral: u8) -> StarRecord {
    StarRecord {
        id,
        pos_ly: pos,
        absmag: 4.8,
        bv: 0.65,
        teff: 5200.0,
        mass: 1.0,
        spectral,
        flags: 0,
        planets: vec![PlanetRecord {
            name: format!("{name} b"),
            period_days: 365.0,
            semimajor_au: 1.0,
            radius_earth: 1.0,
            mass_earth: 1.0,
            eq_temp: 273.0,
            disc_year: 2024,
            method: 2,
            flags: 0b1111,
        }],
        name: name.into(),
    }
}

/// The S3/S4 cluster: Sol plus a G/K/M grid, every point within
/// ~70 ly of Sol.
fn cluster_galaxy() -> Galaxy {
    let mut records = vec![star(0, "Sol", [0.0, 0.0, 0.0], 4)];
    let mut id = 1u32;
    for &x in &[-55.0f32, -28.0, 0.0, 28.0, 55.0] {
        for &y in &[-36.0f32, 0.0, 36.0] {
            for &z in &[-22.0f32, 22.0] {
                if x == 0.0 && y == 0.0 {
                    continue;
                }
                let spectral = [4u8, 5, 6][(id % 3) as usize];
                records.push(star(id, &format!("Star{id}"), [x, y, z], spectral));
                id += 1;
            }
        }
    }
    Galaxy::from_star_records(records)
}

fn setup(ai_count: usize) -> GameSetup {
    GameSetup {
        ai_count,
        home_rules: HomeworldRules {
            region_radius_ly: 500.0,
            min_spacing_ly: 20.0,
            ..HomeworldRules::default()
        },
        ..GameSetup::default()
    }
}

fn ship_of(sim: &Campaign, civ: u32, kind: ShipKind) -> u32 {
    sim.ships_of(civ)
        .into_iter()
        .find(|id| sim.design(sim.ship(*id).unwrap().design_idx).map(|d| d.kind) == Some(kind))
        .expect("ship of kind exists")
}

fn design_idx_of(sim: &Campaign, kind: ShipKind) -> u32 {
    (0..sim.designs().len() as u32)
        .find(|&i| sim.design(i).map(|d| d.kind) == Some(kind))
        .expect("design exists")
}

/// A fresh game (on the cluster) containing an AI civilization
/// with the named archetype (the S4 helper, verbatim convention).
fn game_with_archetype(archetype: &str, ai_count: usize) -> (Campaign, Galaxy, u32, u32) {
    let galaxy = cluster_galaxy();
    let (campaign, report) = Campaign::new_game(&galaxy, 0, &setup(ai_count)).expect("game setup");
    for ai in &report.ai {
        if ai.archetype == archetype {
            return (campaign, galaxy, ai.civ_id, ai.home_system);
        }
    }
    panic!("ai_count {ai_count} seats no {archetype}");
}

fn make_contact(sim: &mut Campaign, galaxy: &Galaxy, civ: u32, home: u32) {
    let surveyor = ship_of(sim, PLAYER_CIV, ShipKind::Surveyor);
    sim.dispatch_ship(galaxy, surveyor, home, Purpose::Survey)
        .expect("dispatch surveyor to the foreign home");
    for _ in 0..60 {
        sim.advance(galaxy, 30);
        if sim.has_contact(PLAYER_CIV, civ) {
            return;
        }
    }
    panic!("contact with civ {civ} never happened");
}

fn open_diplomacy(sim: &mut Campaign, galaxy: &Galaxy, civ: u32) {
    sim.advance(galaxy, TRANSLATION_DAYS + 120);
    assert!(
        sim.diplomacy_open(PLAYER_CIV, civ),
        "diplomacy should be open with civ {civ} on day {}",
        sim.day()
    );
}

fn contact_and_open(sim: &mut Campaign, galaxy: &Galaxy, civ: u32, home: u32) {
    make_contact(sim, galaxy, civ, home);
    open_diplomacy(sim, galaxy, civ);
}

/// Build a fresh ship of `kind` for `civ` at `system`, waiting
/// out the build (and, if the treasury is short, the settlements
/// that refill it). Returns the new ship's id.
fn build_ship_for_civ(
    sim: &mut Campaign,
    galaxy: &Galaxy,
    civ: u32,
    system: u32,
    kind: ShipKind,
) -> u32 {
    let design_idx = design_idx_of(sim, kind);
    let build_days = sim.design(design_idx).unwrap().build_days();
    let ships_before: Vec<u32> = sim.ships_of(civ);
    for _ in 0..24 {
        if sim.build_ship_for(civ, system, design_idx).is_ok() {
            break;
        }
        sim.advance(galaxy, 180);
    }
    sim.advance(galaxy, build_days as u64 + 10);
    // Filter by kind: an AI civilization's own planner builds
    // ships during the wait, and the first new hull is not
    // necessarily ours.
    sim.ships_of(civ)
        .into_iter()
        .filter(|id| !ships_before.contains(id))
        .find(|id| {
            sim.design(sim.ship(*id).unwrap().design_idx).map(|d| d.kind) == Some(kind)
        })
        .expect("ship was built")
}

fn count_events(sim: &Campaign, kind: EventKind) -> usize {
    sim.events().iter().filter(|e| e.kind == kind).count()
}

// ------------------------------------------------------------ war

#[test]
fn war_declaration_ends_treaties_severs_trade_and_records_breaches() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    // War needs contact first: an unmet civilization is refused.
    let err = sim.declare_war(merchant).unwrap_err();
    assert!(matches!(err, SimError::NoContact(c) if c == merchant), "{err}");

    contact_and_open(&mut sim, &galaxy, merchant, home);
    let trade = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::TradeAgreement)
        .expect("propose trade");
    assert!(matches!(trade, DealOutcome::Signed), "{trade:?}");
    let nap = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::NonAggressionPact)
        .expect("propose pact");
    assert!(matches!(nap, DealOutcome::Signed), "{nap:?}");
    let route_id = sim
        .establish_trade_route(&galaxy, merchant, sim.home_system(), home)
        .expect("establish route");
    assert!(sim.trade_route(route_id).is_some());

    sim.declare_war(merchant).expect("declare war");
    assert!(sim.at_war(PLAYER_CIV, merchant));
    let war = sim.war_between(PLAYER_CIV, merchant).expect("war record");
    assert_eq!(war.aggressor, PLAYER_CIV);
    // Every instrument between the pair ends today...
    assert!(!sim.treaty_active(PLAYER_CIV, merchant, TreatyKind::TradeAgreement));
    assert!(!sim.treaty_active(PLAYER_CIV, merchant, TreatyKind::NonAggressionPact));
    // ...trade routes sever with the war (§4.3)...
    assert!(sim.trade_route(route_id).is_none(), "route severed by war");
    // ...and only the promises war *breaks* (the pact, not the
    // trade agreement's ordinary termination) stain the declarer.
    assert_eq!(sim.breaches().len(), 1);
    assert_eq!(sim.breaches()[0].breaker, PLAYER_CIV);
    assert_eq!(sim.breaches()[0].kind, TreatyKind::NonAggressionPact);
    assert_eq!(count_events(&sim, EventKind::WarDeclared), 1);
    // A second declaration is refused, and no treaty is weighed
    // while fleets fight.
    let err = sim.declare_war(merchant).unwrap_err();
    assert!(matches!(err, SimError::AlreadyAtWar(c) if c == merchant), "{err}");
    let evaluation = sim.evaluate_treaty(&galaxy, merchant, PLAYER_CIV, TreatyKind::TradeAgreement);
    assert!(!evaluation.accept);
    assert!(
        evaluation.reasons[0].contains("at war"),
        "stated reason: {:?}",
        evaluation.reasons
    );
    // Exhaustion is 0 on day one of a bloodless war, and the
    // at-war pair's opinion carries the −25 war fold.
    assert_eq!(sim.war_exhaustion(PLAYER_CIV), 0.0);
    let relation = sim.relation(&galaxy, merchant, PLAYER_CIV);
    assert!(relation.opinion.disputes <= -25.0, "{:?}", relation.opinion);
}

#[test]
fn shared_enemies_warm_a_relation() {
    // Player at war with two civilizations: from either one's
    // chair, the other is a fellow enemy of their enemy. The two
    // nearest AI homes are the counterparties (archetype is
    // irrelevant to the component), each contacted by its own
    // surveyor — a surveyor that flies 69 ly out cannot refuel
    // at a foreign port without a treaty, so one ship cannot
    // make both trips.
    let galaxy = cluster_galaxy();
    let (mut sim, report) = Campaign::new_game(&galaxy, 0, &setup(7)).expect("game");
    let mut homes: Vec<(u32, u32)> = report
        .ai
        .iter()
        .map(|ai| (ai.civ_id, ai.home_system))
        .collect();
    homes.sort_by_key(|&(_, home)| galaxy.distance_ly(0, home).map(|d| d as i64));
    let (a, a_home) = homes[0];
    let (b, b_home) = homes[1];
    contact_and_open(&mut sim, &galaxy, a, a_home);
    // A fresh surveyor makes the second contact from Sol.
    let sol = sim.home_system();
    let second = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, sol, ShipKind::Surveyor);
    sim.dispatch_ship(&galaxy, second, b_home, Purpose::Survey)
        .expect("dispatch second surveyor");
    for _ in 0..60 {
        sim.advance(&galaxy, 30);
        if sim.has_contact(PLAYER_CIV, b) {
            break;
        }
    }
    assert!(sim.has_contact(PLAYER_CIV, b), "contact with civ {b}");
    open_diplomacy(&mut sim, &galaxy, b);
    sim.declare_war(a).expect("war on A");
    sim.declare_war(b).expect("war on B");
    let relation = sim.relation(&galaxy, a, b);
    assert_eq!(relation.opinion.shared_enemies, 8.0, "{:?}", relation.opinion);
    let total_without = relation.opinion.total - relation.opinion.shared_enemies;
    assert!(relation.opinion.total > total_without);
}

/// Stage a duel at the merchant's home: two fresh player
/// cruisers parked there in peacetime (a frigate's 66.7 ly legs
/// cannot reach the 69 ly home; a cruiser's 74.3 can). The
/// target is a surveyor caught in port: the merchant's own
/// surveyor whenever it idles at home, or — the deterministic
/// route — a fresh surveyor built at the home shipyard and
/// caught on its spawn day, before the monthly planner can
/// re-task it (a daily poll checks after every day's step).
/// War is NOT yet declared — the caller declares it.
fn staged_duel() -> (Campaign, Galaxy, u32, u32, u32) {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    let sol = sim.home_system();
    let cruiser_a = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, sol, ShipKind::Cruiser);
    let cruiser_b = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, sol, ShipKind::Cruiser);
    for cruiser in [cruiser_a, cruiser_b] {
        sim.dispatch_ship(&galaxy, cruiser, home, Purpose::Relocate)
            .expect("dispatch cruiser to the merchant home");
    }
    for _ in 0..(365 * 2) {
        sim.advance(&galaxy, 1);
        if [cruiser_a, cruiser_b].iter().all(|id| {
            sim.ship(*id).and_then(|s| s.state.current_system()) == Some(home)
        }) {
            break;
        }
    }
    assert!(
        [cruiser_a, cruiser_b]
            .iter()
            .all(|id| sim.ship(*id).and_then(|s| s.state.current_system()) == Some(home)),
        "cruisers on station at the merchant home"
    );
    // Any merchant surveyor in port at home is a target; if none
    // is, build one there and catch it on its spawn day. Up to
    // six builds — a spawn day that coincides with the monthly
    // planner can re-task one attempt, rarely two.
    let surveyor_idx = design_idx_of(&sim, ShipKind::Surveyor);
    for _attempt in 0..6 {
        let before: Vec<u32> = sim.ships_of(merchant);
        // Their own surveyor may already be in port.
        if let Some(target) = before.iter().copied().find(|id| {
            sim.design(sim.ship(*id).unwrap().design_idx).map(|d| d.kind)
                == Some(ShipKind::Surveyor)
                && sim.ship(*id).and_then(|s| s.state.current_system()) == Some(home)
        }) {
            return (sim, galaxy, merchant, target, home);
        }
        if sim.build_ship_for(merchant, home, surveyor_idx).is_err() {
            sim.advance(&galaxy, 90);
            continue;
        }
        for _ in 0..200 {
            sim.advance(&galaxy, 1);
            let fresh = sim
                .ships_of(merchant)
                .into_iter()
                .filter(|id| !before.contains(id))
                .find(|id| {
                    sim.design(sim.ship(*id).unwrap().design_idx).map(|d| d.kind)
                        == Some(ShipKind::Surveyor)
                });
            match fresh {
                Some(id)
                    if sim.ship(id).and_then(|s| s.state.current_system()) == Some(home) =>
                {
                    return (sim, galaxy, merchant, id, home);
                }
                Some(_) => break, // spawned and already re-tasked
                None => continue,
            }
        }
    }
    panic!("duel never staged");
}

#[test]
fn combat_destroys_ships_and_counts_losses() {
    let (mut sim, galaxy, merchant, their_surveyor, home) = staged_duel();
    sim.declare_war(merchant).expect("declare war");
    // Two cruisers (attack 24 each) against a lone surveyor
    // (hull 36): a round or two ends it, before the cripple
    // threshold can save it.
    let mut destroyed_day = None;
    for _ in 0..20 {
        sim.advance(&galaxy, 1);
        if sim.ship(their_surveyor).is_none() {
            destroyed_day = Some(sim.day());
            break;
        }
    }
    assert!(destroyed_day.is_some(), "surveyor should be destroyed");
    // Damage is allocated in ship-id order, so another merchant
    // hull in port may have died first — the assertions key on
    // this ship's own destruction record.
    let event = sim
        .events()
        .iter()
        .find(|e| e.kind == EventKind::ShipDestroyed && e.ship == Some(their_surveyor))
        .expect("destruction event for the target");
    assert_eq!(event.civ, Some(merchant));
    assert_eq!(event.other_civ, Some(PLAYER_CIV));
    assert_eq!(event.system, Some(home));
    let war = sim.war_between(PLAYER_CIV, merchant).expect("war record");
    assert_eq!(war.ships_lost.0, 0, "the player lost nothing");
    assert!(war.ships_lost.1 >= 1, "the loss lands on the owner's side");
    // The cruisers survive: surveyors' attack 1 barely scratches,
    // and the colony's defensive fire is light.
    let cruisers_alive = sim
        .ships_of(PLAYER_CIV)
        .iter()
        .filter(|id| {
            sim.design(sim.ship(**id).unwrap().design_idx).map(|d| d.kind)
                == Some(ShipKind::Cruiser)
        })
        .count();
    assert_eq!(cruisers_alive, 2);
    // Exhaustion now counts the loss.
    assert!(sim.war_exhaustion(merchant) >= 8.0);
}

#[test]
fn crippled_ship_retreats_toward_its_own_colony() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    // The duel ground: unclaimed, unsurveyed by the player, and
    // within one leg of BOTH homes (cruiser legs from the
    // merchant home, surveyor legs from Sol).
    let neutral = (1..galaxy.len() as u32)
        .filter(|&s| {
            sim.system(s).and_then(|st| st.claimed_by).is_none()
                && !sim.surveyed_by(PLAYER_CIV, s)
                && galaxy.distance_ly(home, s).map(|d| d <= 70.0).unwrap_or(false)
                && galaxy.distance_ly(0, s).map(|d| d <= 60.0).unwrap_or(false)
        })
        .min_by_key(|&s| galaxy.distance_ly(0, s).map(|d| d as i64))
        .expect("a duel ground within reach of both homes");
    // The merchant's fresh cruiser parks at the neutral system
    // first: a warship is never re-tasked in peacetime, so it
    // holds station indefinitely. The player's surveyor then
    // flies out and surveys the same system.
    let cruiser = build_ship_for_civ(&mut sim, &galaxy, merchant, home, ShipKind::Cruiser);
    sim.dispatch_ship_for(merchant, &galaxy, cruiser, neutral, Purpose::Relocate)
        .expect("dispatch cruiser");
    for _ in 0..(365 * 2) {
        sim.advance(&galaxy, 1);
        if sim.ship(cruiser).and_then(|s| s.state.current_system()) == Some(neutral) {
            break;
        }
    }
    assert_eq!(
        sim.ship(cruiser).and_then(|s| s.state.current_system()),
        Some(neutral),
        "cruiser on station"
    );
    // A fresh surveyor flies from Sol: the contact trip left the
    // original surveyor at the merchant's home with nearly dry
    // tanks and no port access to refuel with — it stays there,
    // a spectator.
    let sol = sim.home_system();
    let surveyor = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, sol, ShipKind::Surveyor);
    sim.dispatch_ship(&galaxy, surveyor, neutral, Purpose::Survey)
        .expect("dispatch surveyor");
    for _ in 0..(365 * 2) {
        sim.advance(&galaxy, 1);
        let surveying = matches!(
            sim.ship(surveyor).map(|s| &s.state),
            Some(mwcs_sim::ShipState::Surveying { system, .. }) if *system == neutral
        );
        if surveying {
            break;
        }
    }
    sim.declare_war(merchant).expect("declare war");
    // A cruiser's 24 attack cripples the surveyor (hull 36) in a
    // round or two; the retreat rule fires before destruction.
    let mut fled = false;
    for _ in 0..10 {
        sim.advance(&galaxy, 1);
        let ship = sim.ship(surveyor).expect("surveyor survives by fleeing");
        if ship.state.current_system() != Some(neutral) || !matches!(ship.state, mwcs_sim::ShipState::Surveying { .. }) {
            fled = true;
            break;
        }
    }
    assert!(fled, "crippled surveyor should retreat");
    assert!(sim.ship(surveyor).is_some());
}

#[test]
fn war_state_survives_save_reload_and_chunked_advance() {
    let (mut sim, galaxy, merchant, _surveyor, _neutral) = staged_duel();
    sim.declare_war(merchant).expect("declare war");
    sim.advance(&galaxy, 2);
    let bytes = sim.save_bytes();
    let mut reloaded = Campaign::load_bytes(&galaxy, &bytes).expect("reload mid-war");
    // One run advances in a single call, the other day by day:
    // catch-up equivalence (§11.1) with combat active.
    sim.advance(&galaxy, 6);
    for _ in 0..6 {
        reloaded.advance(&galaxy, 1);
    }
    assert_eq!(sim.state_hash(), reloaded.state_hash());
}

// ------------------------------------------------------- occupation

/// Stage an invasion of the merchant's home: three player
/// cruisers (troop capacity 150 against a homeworld garrison of
/// ~100) parked there in peacetime, war declared. Returns with
/// the fleet on station and the war live, defenders not yet
/// cleared.
fn staged_invasion() -> (Campaign, Galaxy, u32, u32, Vec<u32>) {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    let sol = sim.home_system();
    let mut fleet = Vec::new();
    for _ in 0..3 {
        let cruiser =
            build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, sol, ShipKind::Cruiser);
        sim.dispatch_ship(&galaxy, cruiser, home, Purpose::Relocate)
            .expect("dispatch cruiser");
        fleet.push(cruiser);
    }
    for _ in 0..(365 * 3) {
        sim.advance(&galaxy, 1);
        if fleet.iter().all(|id| {
            sim.ship(*id).and_then(|s| s.state.current_system()) == Some(home)
        }) {
            break;
        }
    }
    assert!(
        fleet.iter().all(|id| sim.ship(*id).and_then(|s| s.state.current_system()) == Some(home)),
        "invasion fleet on station"
    );
    sim.declare_war(merchant).expect("declare war");
    (sim, galaxy, merchant, home, fleet)
}

/// Clear the defenders over `home` by letting daily combat run,
/// then invade. Asserts the occupation lands.
fn clear_and_invade(sim: &mut Campaign, galaxy: &Galaxy, merchant: u32, home: u32) {
    // While a defending ship is present, invasion is refused.
    if !sim.ships_present_at(merchant, home).is_empty() {
        let err = sim.invade_system(home).unwrap_err();
        assert!(
            matches!(err, SimError::DefendingFleetPresent(s) if s == home),
            "{err}"
        );
    }
    for _ in 0..180 {
        if sim.ships_present_at(merchant, home).is_empty() {
            break;
        }
        sim.advance(galaxy, 1);
    }
    assert!(
        sim.ships_present_at(merchant, home).is_empty(),
        "defenders cleared by combat"
    );
    sim.invade_system(home).expect("invade the homeworld");
    let colony = sim.system(home).and_then(|s| s.colony.as_ref()).unwrap();
    assert_eq!(colony.occupied_by, Some(PLAYER_CIV));
    // The claim does NOT move: occupation is leverage, not
    // annexation (§6.4).
    assert_eq!(sim.system(home).and_then(|s| s.claimed_by), Some(merchant));
    assert_eq!(count_events(sim, EventKind::OccupationStarted), 1);
}

#[test]
fn invasion_occupies_and_ungarrisoned_occupation_collapses() {
    // The resistance schedule is exercised on a frontier colony,
    // not the homeworld: a frontier colony sits at development
    // 1 for centuries (its population gate is that slow), so a
    // single cruiser's 50 troops beat its garrison of ~36 — and
    // a colony within ~45 ly of Sol leaves the cruiser enough
    // fuel, between its tanks and the occupied port's stock, to
    // withdraw afterwards. The homeworld variant (three
    // cruisers, no withdrawal) is the peace-cession test below.
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    // Wait for the merchant to found a colony close to Sol.
    let mut target = None;
    for _ in 0..(365 * 6) {
        sim.advance(&galaxy, 1);
        target = sim
            .colonies_of(merchant)
            .into_iter()
            .filter(|&c| c != home)
            .find(|&c| galaxy.distance_ly(0, c).map(|d| d <= 48.0).unwrap_or(false));
        if target.is_some() {
            break;
        }
    }
    let target = target.expect("merchant founds a colony near Sol within six years");
    let sol = sim.home_system();
    let cruiser = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, sol, ShipKind::Cruiser);
    sim.dispatch_ship(&galaxy, cruiser, target, Purpose::Relocate)
        .expect("dispatch cruiser to the frontier colony");
    for _ in 0..(365 * 2) {
        sim.advance(&galaxy, 1);
        if sim.ship(cruiser).and_then(|s| s.state.current_system()) == Some(target) {
            break;
        }
    }
    assert_eq!(
        sim.ship(cruiser).and_then(|s| s.state.current_system()),
        Some(target),
        "cruiser on station"
    );
    sim.declare_war(merchant).expect("declare war");
    clear_and_invade(&mut sim, &galaxy, merchant, target);
    // Withdraw the garrison: refuel at the occupied port, then
    // fly home. Resistance now runs on schedule — a
    // ColonyResisted event at three months, collapse at six.
    sim.refuel_ship(cruiser).expect("refuel at the occupied port");
    sim.dispatch_ship(&galaxy, cruiser, sol, Purpose::Relocate)
        .expect("garrison withdraws");
    let home = target;
    let mut resisted = false;
    for _ in 0..7 {
        sim.advance(&galaxy, 30);
        if count_events(&sim, EventKind::ColonyResisted) >= 1 {
            resisted = true;
        }
    }
    assert!(resisted, "resistance should surface at three months");
    let colony = sim.system(home).and_then(|s| s.colony.as_ref()).unwrap();
    assert_eq!(colony.occupied_by, None, "occupation collapsed at six months");
    assert_eq!(count_events(&sim, EventKind::OccupationEnded), 1);
}

#[test]
fn peace_cession_transfers_claim_clears_occupation_and_ends_war() {
    let (mut sim, galaxy, merchant, home, _fleet) = staged_invasion();
    clear_and_invade(&mut sim, &galaxy, merchant, home);
    // Offer the merchant its home back as a cession to us, with
    // 4,000 credits of compensation: the exhaustion of a lost
    // fleet and an occupied home plus the credits outweigh the
    // homeworld's settlement value in its own evaluation.
    let terms = PeaceTerms {
        cede_to_proposer: vec![home],
        cede_to_other: vec![],
        credits_from_proposer: 4000.0,
    };
    let evaluation = sim.evaluate_peace(&galaxy, merchant, PLAYER_CIV, &terms);
    assert!(evaluation.accept, "cession should price out: {:?}", evaluation.reasons);
    let outcome = sim.propose_peace(&galaxy, merchant, terms).expect("propose peace");
    assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");
    assert!(!sim.at_war(PLAYER_CIV, merchant), "the war is over");
    assert_eq!(sim.system(home).and_then(|s| s.claimed_by), Some(PLAYER_CIV));
    let colony = sim.system(home).and_then(|s| s.colony.as_ref()).unwrap();
    assert_eq!(colony.occupied_by, None, "cession clears the occupation");
    assert_eq!(count_events(&sim, EventKind::PeaceSettled), 1);
}

#[test]
fn blockade_starves_a_colony_on_the_supply_schedule() {
    let (mut sim, galaxy, merchant, home, _fleet) = staged_invasion();
    // The cruisers simply hold station: an enemy fleet over a
    // colony blockades it (§6.4). The first monthly settlement
    // with the fleet present must show the colony unsupplied,
    // its unsupplied clock started, and the event recorded.
    let mut blockaded = false;
    for _ in 0..60 {
        sim.advance(&galaxy, 1);
        let colony = sim.system(home).and_then(|s| s.colony.as_ref()).unwrap();
        if !colony.supplied && colony.unsupplied_months >= 1 {
            blockaded = true;
            break;
        }
    }
    assert!(blockaded, "blockade should bite at the first settlement");
    assert_eq!(count_events(&sim, EventKind::ColonyBlockaded), 1);
    // And the defenders are gone — the fleet saw to that — so
    // nothing relieves the blockade from inside.
    assert!(sim.ships_present_at(merchant, home).is_empty());
}

// ------------------------------------------------------------ gates

#[test]
fn gate_build_refusals_and_home_lifecycle() {
    let galaxy = cluster_galaxy();
    let mut sim = Campaign::new_default(&galaxy, 0).expect("solo game");
    let home = sim.home_system();
    // Development 3 < 6: refused with the stated gate.
    let err = sim.build_gate(home).unwrap_err();
    assert!(
        matches!(err, SimError::DevelopmentTooLow { needed: 6, actual: 3 }),
        "{err}"
    );
    // Grow the homeworld: Industrial specialization feeds the
    // alloy/electronics stocks the gate bill draws on. Poll until
    // the colony can actually pay (dev 6, 300 alloys, 40
    // electronics), at most a decade.
    let mut ready = false;
    for _ in 0..40 {
        sim.advance(&galaxy, 90);
        let colony = sim.system(home).and_then(|s| s.colony.as_ref()).unwrap();
        if colony.development >= 3 && colony.specialization.is_none() {
            let _ = sim.assign_specialization(home, Specialization::Industrial);
        }
        let colony = sim.system(home).and_then(|s| s.colony.as_ref()).unwrap();
        if colony.development >= 6
            && colony.alloys_stock >= 300.0
            && colony.electronics_stock >= 40.0
        {
            ready = true;
            break;
        }
    }
    assert!(ready, "homeworld should reach gate readiness within a decade");
    // No Gate Builder present yet: refused, naming the requirement.
    let err = sim.build_gate(home).unwrap_err();
    assert!(matches!(err, SimError::GateBuilderRequired(s) if s == home), "{err}");
    // Build the builder, then the gate: 1,460 days later it
    // stands complete and unpaired, and transit refuses.
    let _builder = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, home, ShipKind::GateBuilder);
    let gate_id = sim.build_gate(home).expect("build gate");
    assert_eq!(count_events(&sim, EventKind::GateConstructionStarted), 1);
    let err = sim.build_gate(home).unwrap_err();
    assert!(matches!(err, SimError::GateAlreadyExists(s) if s == home), "{err}");
    // The builder was consumed by the project.
    assert!(sim
        .ships_of(PLAYER_CIV)
        .iter()
        .all(|id| sim.design(sim.ship(*id).unwrap().design_idx).map(|d| d.kind)
            != Some(ShipKind::GateBuilder)));
    sim.advance(&galaxy, 1460 + 5);
    let gate = sim.gate(gate_id).expect("gate exists");
    assert_eq!(gate.build_days_remaining, 0);
    assert_eq!(gate.partner, None);
    assert_eq!(count_events(&sim, EventKind::GateCompleted), 1);
    let surveyor = ship_of(&sim, PLAYER_CIV, ShipKind::Surveyor);
    let err = sim.gate_transit(surveyor, gate_id).unwrap_err();
    assert!(matches!(err, SimError::GateUnpaired(g) if g == gate_id), "{err}");
}

// ---------------------------------------------------------- victory

#[test]
fn victory_first_among_equals_at_the_end_year_and_sandbox_never() {
    let galaxy = cluster_galaxy();
    let mut fae_setup = setup(2);
    fae_setup.victory = VictoryRule::FirstAmongEquals;
    fae_setup.victory_end_year = 2;
    let (mut sim, _) = Campaign::new_game(&galaxy, 0, &fae_setup).expect("FAE game");
    sim.advance(&galaxy, 2 * 365 + 40);
    // A winner is recorded at the end year, and it is the
    // civilization holding the highest §6.5 score — computed
    // independently here from the public score function.
    let (winner, _day) = sim.victory_winner().expect("a winner at the end year");
    let best = sim
        .civs()
        .iter()
        .map(|c| c.id)
        .max_by(|&x, &y| {
            sim.victory_score(x)
                .total_cmp(&sim.victory_score(y))
                .then(y.cmp(&x))
        })
        .unwrap();
    assert_eq!(winner, best, "the highest score wins");
    assert_eq!(count_events(&sim, EventKind::VictoryAchieved), 1);

    // The same horizon under Sandbox records nothing, ever.
    let mut sandbox_setup = setup(2);
    sandbox_setup.victory = VictoryRule::Sandbox;
    sandbox_setup.victory_end_year = 2;
    let (mut sim2, _) = Campaign::new_game(&galaxy, 0, &sandbox_setup).expect("sandbox game");
    sim2.advance(&galaxy, 3 * 365);
    assert_eq!(sim2.victory_winner(), None);
}

/// A closed galaxy: Sol plus nine stars on a 45 ly ring. Every
/// star seats a homeworld and there is nowhere to expand to, so
/// the colonized total is fixed at ten forever — hegemony's
/// denominator cannot run away from the test.
fn ring_galaxy() -> Galaxy {
    let mut records = vec![star(0, "Sol", [0.0, 0.0, 0.0], 4)];
    for i in 1..=9u32 {
        let angle = (i as f32) * std::f32::consts::TAU / 9.0;
        records.push(star(
            i,
            &format!("Ring{i}"),
            [45.0 * angle.cos(), 45.0 * angle.sin(), 0.0],
            [4u8, 5, 6][(i % 3) as usize],
        ));
    }
    Galaxy::from_star_records(records)
}

#[test]
fn victory_hegemony_by_peace_cession() {
    // Ten civilizations, one colony each, no frontier: the
    // player needs four of the ten colonized systems for the
    // 40% share. Three homeworlds change hands by compensated
    // cession; the victory lands at the next monthly evaluation.
    let galaxy = ring_galaxy();
    let (mut sim, report) = Campaign::new_game(&galaxy, 0, &setup(9)).expect("game");
    assert_eq!(sim.total_colonized_count(), 10);
    let mut targets: Vec<(u32, u32)> = report
        .ai
        .iter()
        .map(|ai| (ai.civ_id, ai.home_system))
        .collect();
    targets.sort_by_key(|&(_, home)| galaxy.distance_ly(0, home).map(|d| d as i64));
    let mut surveyor = ship_of(&sim, PLAYER_CIV, ShipKind::Surveyor);
    for (i, (civ, home)) in targets.iter().take(3).enumerate() {
        // Each contact uses a fresh surveyor from Sol: the
        // previous one is stranded abroad on dry tanks.
        if i > 0 {
            let sol = sim.home_system();
            surveyor = build_ship_for_civ(
                &mut sim,
                &galaxy,
                PLAYER_CIV,
                sol,
                ShipKind::Surveyor,
            );
        }
        sim.dispatch_ship(&galaxy, surveyor, *home, Purpose::Survey)
            .expect("dispatch contact surveyor");
        for _ in 0..60 {
            sim.advance(&galaxy, 30);
            if sim.has_contact(PLAYER_CIV, *civ) {
                break;
            }
        }
        assert!(sim.has_contact(PLAYER_CIV, *civ), "contact with civ {civ}");
        open_diplomacy(&mut sim, &galaxy, *civ);
        let terms = PeaceTerms {
            cede_to_proposer: vec![*home],
            cede_to_other: vec![],
            credits_from_proposer: 5000.0,
        };
        let evaluation = sim.evaluate_peace(&galaxy, *civ, PLAYER_CIV, &terms);
        assert!(
            evaluation.accept,
            "civ {civ} should sell its homeworld for 5,000: {:?}",
            evaluation.reasons
        );
        // Three cessions at 5,000 against a 15,000 treasury: the
        // last one may have to wait a few months for income.
        let mut signed = false;
        for _ in 0..10 {
            match sim.propose_peace(&galaxy, *civ, terms.clone()) {
                Ok(DealOutcome::Signed) => {
                    signed = true;
                    break;
                }
                Ok(other) => panic!("cession refused: {other:?}"),
                Err(_) => sim.advance(&galaxy, 90),
            }
        }
        assert!(signed, "cession to civ {civ} eventually signed");
        assert_eq!(sim.system(*home).and_then(|s| s.claimed_by), Some(PLAYER_CIV));
    }
    assert_eq!(sim.colonies_of(PLAYER_CIV).len(), 4);
    // The next settlement's victory evaluation records it.
    sim.advance(&galaxy, 31);
    let (winner, _) = sim.victory_winner().expect("hegemony achieved");
    assert_eq!(winner, PLAYER_CIV);
    assert_eq!(count_events(&sim, EventKind::VictoryAchieved), 1);
}

// ------------------------------------------------------------ AI war

#[test]
fn ai_war_declares_and_concludes_in_peace() {
    // The measured seed-42 cluster dynamic: a Warriors–Raiders
    // war opens in the first years and, once exhaustion's
    // duration term bites (~12 years), ends at the peace table.
    let galaxy = cluster_galaxy();
    let (mut sim, _) = Campaign::new_game(&galaxy, 42, &setup(12)).expect("game");
    let mut declared = 0;
    let mut settled = 0;
    for _ in 0..60 {
        sim.advance(&galaxy, 365);
        declared = count_events(&sim, EventKind::WarDeclared);
        settled = count_events(&sim, EventKind::PeaceSettled);
        if declared >= 1 && settled >= 1 {
            break;
        }
    }
    assert!(declared >= 1, "an AI war should be declared");
    assert!(settled >= 1, "an AI war should conclude in peace");
    // And the peace is real: at least one formerly-warring pair
    // is no longer at war (the wars list holds only live wars).
    assert!(
        sim.wars().len() < declared,
        "some declared wars have ended: {} active of {} declared",
        sim.wars().len(),
        declared
    );
}

// ------------------------------------------------------- long game

/// The full S5 arc in one campaign, because the frontier
/// colony's ~510-year climb to development 7 should be paid
/// once: home gate, frontier gate, pairing, transit and its
/// throughput cap, foreign transit refused then admitted by
/// treaty, gate-fed trade doubling, terraforming against the
/// natural baseline, and the frontier gate's destruction under
/// bombardment unpairing its partner.
#[test]
fn gate_network_trade_terraform_and_destruction_long_game() {
    let (mut sim, galaxy, merchant, m_home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, m_home);
    let home = sim.home_system();

    // Trade first: an agreement and a running route give the
    // relation its trade-volume warmth (and the treasury its
    // income) for the centuries ahead.
    let trade = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::TradeAgreement)
        .expect("propose trade");
    assert!(matches!(trade, DealOutcome::Signed), "{trade:?}");

    // Find the frontier: a fresh surveyor surveys outward from
    // Sol hunting the best exotics system (the measured target
    // on this galaxy/seed is ~51 ly out, habitability 98,
    // exotics trait 0.25).
    let scout = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, home, ShipKind::Surveyor);
    let mut candidates: Vec<u32> = (1..galaxy.len() as u32).collect();
    candidates.sort_by_key(|&s| galaxy.distance_ly(0, s).map(|d| d as i64));
    let mut frontier: Option<u32> = None;
    let mut best_hab = 0.0;
    for target in candidates {
        if sim.dispatch_ship(&galaxy, scout, target, Purpose::Survey).is_err() {
            continue;
        }
        for _ in 0..40 {
            sim.advance(&galaxy, 10);
            if sim.surveyed_by(PLAYER_CIV, target) {
                break;
            }
        }
        if let Some(profile) = sim.known_profile(PLAYER_CIV, target) {
            if profile.exotics_trait > 0.0 && profile.habitability_percent > best_hab {
                best_hab = profile.habitability_percent;
                frontier = Some(target);
            }
        }
        if frontier.is_some() && sim.day() > 365 * 3 {
            break;
        }
    }
    let frontier = frontier.expect("an exotics system within survey reach");

    // Claim and colonize it.
    if sim.system(frontier).and_then(|s| s.claimed_by).is_none() {
        sim.claim_system(frontier).expect("claim the frontier");
    }
    let colony_ship = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, home, ShipKind::Colony);
    sim.dispatch_ship(&galaxy, colony_ship, frontier, Purpose::Colonize)
        .expect("dispatch colony ship");
    for _ in 0..200 {
        sim.advance(&galaxy, 10);
        if sim.system(frontier).and_then(|s| s.colony.as_ref()).is_some() {
            break;
        }
    }
    assert!(
        sim.system(frontier).and_then(|s| s.colony.as_ref()).is_some(),
        "frontier colony founded"
    );
    // A route between the frontier and the merchant home starts
    // earning (its path is gate-free for centuries yet).
    let _route = sim
        .establish_trade_route(&galaxy, merchant, frontier, m_home)
        .expect("establish frontier route");

    // The home gate: poll to readiness, build, wait out the
    // 1,460 days. The specialization is Agricultural, not
    // Industrial: over five centuries an unspecialized home
    // outgrows its food supply and starves (the AI's heuristic
    // picks Agricultural for the same reason), while the gate
    // bill still accumulates — electronics just take ~6 years
    // instead of ~2.5.
    let _ = sim.assign_specialization(home, Specialization::Agricultural);
    let mut home_gate = None;
    for _ in 0..60 {
        sim.advance(&galaxy, 90);
        let colony = sim.system(home).and_then(|s| s.colony.as_ref()).unwrap();
        if colony.development >= 6
            && colony.alloys_stock >= 420.0
            && colony.electronics_stock >= 40.0
            && sim.credits() >= 16_000.0
        {
            // 420 alloys, not 300: the Gate Builder's own hull
            // costs 120 of them before the gate bill comes due.
            let _builder =
                build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, home, ShipKind::GateBuilder);
            home_gate = Some(sim.build_gate(home).expect("build home gate"));
            break;
        }
    }
    let home_gate = home_gate.expect("home gate construction started");
    sim.advance(&galaxy, 1460 + 5);
    assert_eq!(sim.gate(home_gate).unwrap().build_days_remaining, 0);

    // The long climb: Agricultural at development 3 for the
    // supplies margin, then centuries of growth to development
    // 7 with a full exotics stock (measured: ~year 510).
    let mut spec_set = false;
    let mut mature = false;
    for _ in 0..560 {
        sim.advance(&galaxy, 365);
        let (dev, exo) = {
            let colony = sim
                .system(frontier)
                .and_then(|s| s.colony.as_ref())
                .expect("frontier colony persists");
            (colony.development, colony.exotics_stock)
        };
        if !spec_set && dev >= 3 {
            let _ = sim.assign_specialization(frontier, Specialization::Agricultural);
            spec_set = true;
        }
        if dev >= 7 && exo >= 15.0 {
            mature = true;
            break;
        }
    }
    assert!(mature, "frontier colony should mature to dev 7 with exotics");

    // The frontier gate, built on the spot.
    let _builder2 =
        build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, frontier, ShipKind::GateBuilder);
    let frontier_gate = sim.build_gate(frontier).expect("build frontier gate");
    sim.advance(&galaxy, 1460 + 5);
    assert_eq!(sim.gate(frontier_gate).unwrap().build_days_remaining, 0);

    // Throughput accounting BEFORE pairing: for every merchant
    // colony, the endpoint throughput the route formula gives.
    let merchant_colonies = sim.colonies_of(merchant);
    let base_throughput: Vec<(u32, f64)> = merchant_colonies
        .iter()
        .map(|&x| (x, sim.route_throughput(PLAYER_CIV, merchant, frontier, x)))
        .collect();

    // Pair the gates.
    sim.pair_gates(home_gate, frontier_gate).expect("pair gates");
    assert_eq!(sim.gate(home_gate).unwrap().partner, Some(frontier_gate));
    assert_eq!(sim.gate(frontier_gate).unwrap().partner, Some(home_gate));
    assert_eq!(count_events(&sim, EventKind::GatePaired), 1);

    // Trade through the web: at least one merchant colony's
    // route must now hop the gate (the frontier–Sol hop costs
    // 1 ly by gate against ~51 by ship), and a live route over
    // that path carries double throughput (§4.3).
    let mut doubled = false;
    for (x, base) in &base_throughput {
        let Some((path, _)) = sim.trade_path(&galaxy, PLAYER_CIV, merchant, frontier, *x)
        else {
            continue;
        };
        let hops_gate = path
            .windows(2)
            .any(|w| (w[0] == frontier && w[1] == home) || (w[0] == home && w[1] == frontier));
        if hops_gate {
            // The frontier–home route from the early game may
            // already cover these endpoints; reuse it if so.
            let live = match sim.establish_trade_route(&galaxy, merchant, frontier, *x) {
                Ok(route_id) => {
                    sim.live_route_throughput(sim.trade_route(route_id).unwrap())
                }
                Err(_) => {
                    let route = sim
                        .routes_between(PLAYER_CIV, merchant)
                        .into_iter()
                        .find(|r| {
                            (r.system_a == frontier && r.system_b == *x)
                                || (r.system_a == *x && r.system_b == frontier)
                        })
                        .expect("an existing route covers these endpoints");
                    sim.live_route_throughput(route)
                }
            };
            assert!(
                (live - 2.0 * base).abs() < 1e-6,
                "gate-fed throughput {live} should double the base {base}"
            );
            doubled = true;
            break;
        }
    }
    assert!(doubled, "some merchant colony's route should hop the gate");

    // Transit: five fresh surveyors at Sol. The first crosses —
    // the departing colony pays 25 fuel — and arrives at the
    // frontier a day later, whatever the 51 ly.
    let mut ships = Vec::new();
    for _ in 0..5 {
        ships.push(build_ship_for_civ(
            &mut sim,
            &galaxy,
            PLAYER_CIV,
            home,
            ShipKind::Surveyor,
        ));
    }
    let fuel_before = sim
        .system(home)
        .and_then(|s| s.colony.as_ref())
        .map(|c| c.fuel_stock)
        .unwrap();
    sim.gate_transit(ships[0], home_gate).expect("first transit");
    let fuel_after = sim
        .system(home)
        .and_then(|s| s.colony.as_ref())
        .map(|c| c.fuel_stock)
        .unwrap();
    assert!((fuel_before - fuel_after - 25.0).abs() < 1e-9, "transit fuel burn");
    sim.advance(&galaxy, 1);
    assert_eq!(
        sim.ship(ships[0]).and_then(|s| s.state.current_system()),
        Some(frontier),
        "arrived through the gate in one day"
    );
    // A fresh day: three more cross, the fifth is refused — the
    // pair's daily throughput is three (§5.3).
    for ship in &ships[1..4] {
        sim.gate_transit(*ship, home_gate).expect("transit within throughput");
    }
    let err = sim.gate_transit(ships[4], home_gate).unwrap_err();
    assert!(matches!(err, SimError::GateThroughputFull(g) if g == home_gate), "{err}");

    // Foreign transit: bring a merchant surveyor to Sol (via its
    // home if it is out roaming). Without a gate-access treaty
    // the pair refuses it; with one, it crosses.
    let their_surveyor = ship_of(&sim, merchant, ShipKind::Surveyor);
    hop_to_system(&mut sim, &galaxy, merchant, their_surveyor, home);
    assert_eq!(
        sim.ship(their_surveyor).and_then(|s| s.state.current_system()),
        Some(home),
        "merchant surveyor at Sol"
    );
    let err = sim.gate_transit_for(merchant, their_surveyor, home_gate).unwrap_err();
    assert!(
        matches!(err, SimError::GateNotOperational(_)),
        "foreign transit refused without treaty: {err}"
    );
    let access = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::GateAccess)
        .expect("propose gate access");
    assert!(matches!(access, DealOutcome::Signed), "{access:?}");
    sim.gate_transit_for(merchant, their_surveyor, home_gate)
        .expect("foreign transit under treaty");
    sim.advance(&galaxy, 1);
    assert_eq!(
        sim.ship(their_surveyor).and_then(|s| s.state.current_system()),
        Some(frontier),
        "merchant surveyor crossed under treaty"
    );

    // Terraforming: the best planet rises 25 points above where
    // it stood; its natural baseline never moves (§3).
    let profile = sim
        .system(frontier)
        .and_then(|s| s.profile.as_ref())
        .unwrap()
        .clone();
    let (best_idx, before, natural) = profile
        .planets
        .iter()
        .enumerate()
        .max_by(|x, y| x.1.habitability_percent.total_cmp(&y.1.habitability_percent))
        .map(|(i, p)| (i, p.habitability_percent, p.natural_habitability_percent))
        .unwrap();
    sim.start_terraform(frontier).expect("start terraforming");
    assert_eq!(count_events(&sim, EventKind::TerraformStarted), 1);
    sim.advance(&galaxy, 10_950 + 40);
    let profile = sim
        .system(frontier)
        .and_then(|s| s.profile.as_ref())
        .unwrap()
        .clone();
    let planet = &profile.planets[best_idx];
    assert!(
        (planet.habitability_percent - (before + 25.0).min(100.0)).abs() < 1e-9,
        "terraformed habitability {} vs expected {}",
        planet.habitability_percent,
        (before + 25.0).min(100.0)
    );
    assert_eq!(planet.natural_habitability_percent, natural, "baseline unmoved");
    assert_eq!(count_events(&sim, EventKind::TerraformCompleted), 1);

    // Destruction: three merchant cruisers hop colony-to-colony
    // to the frontier (refuelling at their own ports), war is
    // declared, and their bombardment wrecks the gate — leaving
    // the home gate unpaired. A player surveyor built at the
    // frontier stands guard so the cruisers cannot simply
    // invade instead (invasion needs an undefended system).
    let _guard = build_ship_for_civ(&mut sim, &galaxy, PLAYER_CIV, frontier, ShipKind::Surveyor);
    let mut cruisers = Vec::new();
    for _ in 0..3 {
        cruisers.push(build_ship_for_civ(
            &mut sim,
            &galaxy,
            merchant,
            m_home,
            ShipKind::Cruiser,
        ));
    }
    for cruiser in &cruisers {
        hop_to_system(&mut sim, &galaxy, merchant, *cruiser, frontier);
    }
    assert!(cruisers.iter().all(|id| {
        sim.ship(*id).and_then(|s| s.state.current_system()) == Some(frontier)
    }));
    // Declare just after a settlement boundary: the merchant's
    // monthly planning (its only chance to convert the cruisers'
    // presence into an invasion) is then a full month away, and
    // the bombardment needs only days.
    while sim.day() % 30 != 1 {
        sim.advance(&galaxy, 1);
    }
    sim.declare_war(merchant).expect("declare war for the bombardment");
    let mut destroyed = false;
    for _ in 0..40 {
        sim.advance(&galaxy, 1);
        if sim.gate(frontier_gate).is_none() {
            destroyed = true;
            break;
        }
    }
    assert!(destroyed, "bombardment should wreck the frontier gate");
    assert_eq!(count_events(&sim, EventKind::GateDestroyed), 1);
    assert_eq!(
        sim.gate(home_gate).unwrap().partner,
        None,
        "the surviving partner is left unpaired"
    );
}

/// Move one of `civ`'s ships to `target`, hopping between the
/// civilization's own colonies (refuelling at each) when the
/// direct leg exceeds the ship's range. Used to walk merchant
/// cruisers across the cluster to the frontier.
fn hop_to_system(sim: &mut Campaign, galaxy: &Galaxy, civ: u32, ship_id: u32, target: u32) {
    for _ in 0..12 {
        let at = sim
            .ship(ship_id)
            .and_then(|s| s.state.current_system())
            .expect("ship somewhere");
        if at == target {
            return;
        }
        // Top up at the current port when it is one of the
        // owner's own: an in-range leg still fails on a
        // part-empty tank.
        if sim.colonies_of(civ).contains(&at) {
            let _ = sim.refuel_ship_for(civ, ship_id);
        }
        if sim
            .dispatch_ship_for(civ, galaxy, ship_id, target, Purpose::Relocate)
            .is_ok()
        {
            wait_at_system(sim, galaxy, ship_id, target);
            return;
        }
        // Pick the own colony in range that gets closest to the
        // target, refuel there, and go again.
        let range = sim
            .design(sim.ship(ship_id).unwrap().design_idx)
            .unwrap()
            .range_ly();
        let mut best: Option<(f64, u32)> = None;
        for colony in sim.colonies_of(civ) {
            if colony == at {
                continue;
            }
            let (Some(d1), Some(d2)) = (
                galaxy.distance_ly(at, colony),
                galaxy.distance_ly(colony, target),
            ) else {
                continue;
            };
            if d1 <= range && best.map(|(bd, _)| d2 < bd).unwrap_or(true) {
                best = Some((d2, colony));
            }
        }
        let (_, hop) = best.expect("a colony hop toward the target exists");
        sim.dispatch_ship_for(civ, galaxy, ship_id, hop, Purpose::Relocate)
            .expect("dispatch hop");
        wait_at_system(sim, galaxy, ship_id, hop);
        let _ = sim.refuel_ship_for(civ, ship_id);
    }
    panic!("ship {ship_id} never reached system {target}");
}

fn wait_at_system(sim: &mut Campaign, galaxy: &Galaxy, ship_id: u32, system: u32) {
    for _ in 0..(365 * 3) {
        sim.advance(galaxy, 1);
        if sim.ship(ship_id).and_then(|s| s.state.current_system()) == Some(system) {
            return;
        }
    }
    panic!("ship {ship_id} never arrived at system {system}");
}
