//! S4 integration tests: trade & diplomacy depth (design §4.3,
//! §6.3). Treaty lifecycles (sign → honour → break →
//! consequences) for every instrument, trade income reconciling
//! against route throughput month by month, AI accept/refuse with
//! stated reasons, peace settlements with system cessions,
//! embargoes, the proposal inbox, and catch-up equivalence with
//! diplomacy active (§11.1).
//!
//! Counterparties are chosen by archetype: race.rs assigns
//! archetypes by civ index, so civ 1 is always a Merchant League
//! (trade affinity 0.95, xenophobia 0.15, honour 0.80 — accepts
//! honest deals) and civ 4 always Isolationist Gardeners
//! (xenophobia 0.80 — refuse them, for reasons the tests read).
//! Personalities jitter ±0.1 around those centres by seed.

use mwcs_pipeline::table::{PlanetRecord, StarRecord};
use mwcs_sim::race::HomeworldRules;
use mwcs_sim::{
    Campaign, DealOutcome, Galaxy, GameSetup, PeaceTerms, Purpose, ShipKind, SimError,
    Specialization, TreatyKind, PLAYER_CIV, TRADE_LEG_LY, TRANSLATION_DAYS,
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

/// The S3 cluster: Sol plus a G/K/M grid, every point within ~70 ly
/// of Sol — contact is one surveyor hop away.
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

/// A fresh game (on the cluster) containing an AI civilization
/// with the named archetype. Archetypes are assigned by civ index
/// (race.rs): civ 1 is always a Merchant League, civ 4 always
/// Isolationist Gardeners, and so on — so this is a lookup, not a
/// search. Personalities jitter ±0.1 around the archetype centre
/// by seed; seed 0's draw is the one the acceptance margins in
/// these tests were verified against (seed 42's merchant, for
/// instance, draws trade affinity 0.87 and expands slowly enough
/// that gate access legitimately refuses — the evaluation is
/// doing its job in both cases).
fn game_with_archetype(
    archetype: &str,
    ai_count: usize,
) -> (Campaign, Galaxy, u32, u32) {
    let galaxy = cluster_galaxy();
    let (campaign, report) =
        Campaign::new_game(&galaxy, 0, &setup(ai_count)).expect("game setup");
    for ai in &report.ai {
        if ai.archetype == archetype {
            return (campaign, galaxy, ai.civ_id, ai.home_system);
        }
    }
    panic!("ai_count {ai_count} seats no {archetype}");
}

/// Fly the player's surveyor to the civilization's home and wait
/// for the survey to complete: first contact.
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

/// Advance past the §6.3 translation delay.
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

fn sign_trade(sim: &mut Campaign, galaxy: &Galaxy, civ: u32) {
    let outcome = sim
        .propose_treaty(galaxy, civ, TreatyKind::TradeAgreement)
        .expect("propose trade");
    assert!(
        matches!(outcome, DealOutcome::Signed),
        "merchant should sign a trade agreement, got {outcome:?}"
    );
}

// ------------------------------------------------------------ tests

#[test]
fn translation_delay_gates_diplomacy() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    // Before contact, every negotiated instrument is refused at
    // the command level.
    let err = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::TradeAgreement)
        .unwrap_err();
    assert!(matches!(err, SimError::NoContact(c) if c == merchant), "{err}");
    // After contact, the translation delay still gates.
    make_contact(&mut sim, &galaxy, merchant, home);
    let contacted = sim.contacted_day(PLAYER_CIV, merchant).unwrap();
    let err = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::TradeAgreement)
        .unwrap_err();
    assert!(
        matches!(err, SimError::DiplomacyNotReady { ready_day } if ready_day == contacted + TRANSLATION_DAYS),
        "{err}"
    );
    open_diplomacy(&mut sim, &galaxy, merchant);
    sign_trade(&mut sim, &galaxy, merchant);
}

#[test]
fn trade_agreement_lifecycle_and_ledger_reconciliation() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    sign_trade(&mut sim, &galaxy, merchant);
    assert!(sim.treaty_active(PLAYER_CIV, merchant, TreatyKind::TradeAgreement));

    // Open the route home-to-home and reconcile the ledger against
    // live throughput every month for two years: the settlement
    // must pay exactly throughput × distance factor × rate, and
    // the route record must accumulate exactly those payments.
    let route_id = sim
        .establish_trade_route(&galaxy, merchant, sim.home_system(), home)
        .expect("establish route");
    let mut prev_earned = 0.0;
    for month in 1..=24 {
        sim.advance(&galaxy, 30);
        let route = sim
            .trade_route(route_id)
            .unwrap_or_else(|| panic!("route closed unexpectedly in month {month}"));
        let expected = sim.route_monthly_income(route);
        assert!(expected > 0.0, "route should pay in month {month}");
        assert!(
            (route.last_income_a - expected).abs() < 1e-9,
            "month {month}: ledger last income {} != throughput income {expected}",
            route.last_income_a
        );
        assert!(
            (route.earned_a - prev_earned - expected).abs() < 1e-6,
            "month {month}: ledger grew by {} but throughput says {expected}",
            route.earned_a - prev_earned
        );
        assert_eq!(route.earned_a, route.earned_b, "both sides earn alike");
        assert_eq!(route.months_active, month);
        prev_earned = route.earned_a;
    }
    // Trade volume is now an opinion component (§6.2).
    let relation = sim.relation(&galaxy, merchant, PLAYER_CIV);
    assert!(relation.opinion.trade_volume > 0.0);
    let galaxy_trade_total = sim.total_trade_income();
    assert!(galaxy_trade_total >= prev_earned * 2.0 - 1e-6);

    // Break: the route closes with the agreement, the breach is
    // remembered against the breaker, and the campaign's all-time
    // trade total survives the route's ledger.
    sim.break_treaty(merchant, TreatyKind::TradeAgreement)
        .expect("break trade agreement");
    assert!(!sim.treaty_active(PLAYER_CIV, merchant, TreatyKind::TradeAgreement));
    assert!(sim.trade_route(route_id).is_none(), "route closes with its agreement");
    assert_eq!(sim.breaches().len(), 1);
    assert_eq!(sim.breaches()[0].breaker, PLAYER_CIV);
    assert_eq!(sim.breaches()[0].kind, TreatyKind::TradeAgreement);
    let relation = sim.relation(&galaxy, merchant, PLAYER_CIV);
    assert_eq!(relation.opinion.broken_treaties, -14.0);
    assert_eq!(sim.total_trade_income(), galaxy_trade_total);
}

#[test]
fn isolationist_refuses_trade_with_stated_reasons() {
    // Civ 4 by archetype rotation — the game seats four AI civs.
    let (mut sim, galaxy, isolationist, home) =
        game_with_archetype("Isolationist Gardeners", 4);
    contact_and_open(&mut sim, &galaxy, isolationist, home);
    let evaluation = sim.evaluate_treaty(
        &galaxy,
        isolationist,
        PLAYER_CIV,
        TreatyKind::TradeAgreement,
    );
    assert!(!evaluation.accept, "isolationists should refuse: {evaluation:?}");
    let outcome = sim
        .propose_treaty(&galaxy, isolationist, TreatyKind::TradeAgreement)
        .expect("propose trade");
    let DealOutcome::Refused { reasons } = outcome else {
        panic!("expected a refusal, got {outcome:?}");
    };
    let joined = reasons.join("\n");
    assert!(joined.contains("xenophobia"), "reasons must name the cause:\n{joined}");
    assert!(joined.contains("refused"), "reasons must end in the verdict:\n{joined}");
    assert!(!sim.treaty_active(PLAYER_CIV, isolationist, TreatyKind::TradeAgreement));
}

#[test]
fn gate_access_lifecycle_port_refuelling() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    // The surveyor sits at the merchant home, tanks partly drained
    // by the trip out. Without a treaty, its colony is not ours to
    // draw on.
    let surveyor = ship_of(&sim, PLAYER_CIV, ShipKind::Surveyor);
    let fuel_before = sim.ship(surveyor).unwrap().fuel;
    assert!(fuel_before < 150.0);
    let err = sim.refuel_ship(surveyor).unwrap_err();
    assert!(matches!(err, SimError::NotYourColony(s) if s == home), "{err}");

    // Sign gate access: the port opens.
    let outcome = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::GateAccess)
        .expect("propose gate access");
    assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");
    assert!(sim.port_access(PLAYER_CIV, merchant));
    let stock_before = sim
        .system(home)
        .and_then(|s| s.colony.as_ref())
        .unwrap()
        .fuel_stock;
    let amount = sim.refuel_ship(surveyor).expect("refuel under gate access");
    assert!(amount > 0.0);
    assert!((sim.ship(surveyor).unwrap().fuel - 150.0).abs() < 1e-9);
    let stock_after = sim
        .system(home)
        .and_then(|s| s.colony.as_ref())
        .unwrap()
        .fuel_stock;
    assert!((stock_before - stock_after - amount).abs() < 1e-9);

    // Break it: the port closes again, and the breach is on record.
    sim.break_treaty(merchant, TreatyKind::GateAccess)
        .expect("break gate access");
    assert!(!sim.port_access(PLAYER_CIV, merchant));
    let colony_ship = ship_of(&sim, PLAYER_CIV, ShipKind::Colony);
    sim.dispatch_ship(&galaxy, colony_ship, home, Purpose::Relocate)
        .expect("send colony ship to the merchant home");
    sim.advance(&galaxy, 400);
    let err = sim.refuel_ship(colony_ship).unwrap_err();
    assert!(matches!(err, SimError::NotYourColony(s) if s == home), "{err}");
}

#[test]
fn non_aggression_pact_bars_contests_until_broken() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    let outcome = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::NonAggressionPact)
        .expect("propose NAP");
    assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");

    // The merchant home is surveyed and foreign-held — exactly
    // what a contest needs — but the pact bars it.
    let err = sim.contest_claim(home).unwrap_err();
    assert!(matches!(err, SimError::ContestBarredByTreaty), "{err}");
    assert!(sim.disputes_between(PLAYER_CIV, merchant).is_empty());

    // Break the pact and the same contest opens a dispute.
    sim.break_treaty(merchant, TreatyKind::NonAggressionPact)
        .expect("break NAP");
    sim.contest_claim(home).expect("contest after breaking the pact");
    let disputes = sim.disputes_between(PLAYER_CIV, merchant);
    assert_eq!(disputes.len(), 1);
    assert_eq!(disputes[0].holder, merchant);
    assert_eq!(disputes[0].challenger, PLAYER_CIV);
}

#[test]
fn research_pact_bonus_accrues_and_stops_when_broken() {
    // Two identical games; only one signs the pact. The player's
    // home is a Research colony from day 0, so the pact partner
    // (who has no Research colony of its own) must gain exactly
    // the bonus in the pact game and nothing in the control game.
    let build = || {
        let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
        let player_home = sim.home_system();
        sim.assign_specialization(player_home, Specialization::Research)
            .expect("specialize home as Research");
        contact_and_open(&mut sim, &galaxy, merchant, home);
        (sim, galaxy, merchant)
    };
    let (mut pact, galaxy_p, merchant_p) = build();
    let (mut control, galaxy_c, merchant_c) = build();
    assert_eq!(merchant_p, merchant_c, "same seed, same civ");

    let outcome = pact
        .propose_treaty(&galaxy_p, merchant_p, TreatyKind::ResearchPact)
        .expect("propose research pact");
    assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");

    pact.advance(&galaxy_p, 180);
    control.advance(&galaxy_c, 180);
    let pact_ai = pact.research_points_for(merchant_p);
    let control_ai = control.research_points_for(merchant_c);
    assert!(
        pact_ai > control_ai + 5.0,
        "pact partner should gain the bonus: pact {pact_ai} vs control {control_ai}"
    );
    // The player's own accrual is identical in both (the merchant
    // contributes no research output of its own).
    assert!(
        (pact.research_points_for(PLAYER_CIV) - control.research_points_for(PLAYER_CIV)).abs()
            < 1e-9
    );

    // Break the pact: the partner's research growth stops dead.
    pact.break_treaty(merchant_p, TreatyKind::ResearchPact)
        .expect("break research pact");
    let before = pact.research_points_for(merchant_p);
    pact.advance(&galaxy_p, 90);
    let after = pact.research_points_for(merchant_p);
    assert!(
        (after - before).abs() < 1e-9,
        "no research output of its own, no bonus after the break: {before} -> {after}"
    );
}

#[test]
fn peace_settlement_with_cession_lifecycle() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    // Port access first (the surveyor needs the merchant's fuel to
    // reach a frontier claim), then find a merchant claim to
    // contest: surveyed by us, claimed by them, no colony on it.
    let outcome = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::GateAccess)
        .expect("propose gate access");
    assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");
    let surveyor = ship_of(&sim, PLAYER_CIV, ShipKind::Surveyor);
    sim.refuel_ship(surveyor).expect("refuel at the merchant home");
    let target = sim
        .systems()
        .iter()
        .filter(|(_, s)| s.claimed_by == Some(merchant) && s.colony.is_none())
        .map(|(id, _)| *id)
        .filter(|id| {
            galaxy
                .distance_ly(home, *id)
                .map(|d| d <= 70.0)
                .unwrap_or(false)
        })
        .min()
        .expect("a merchant claim within surveyor reach of its home");
    sim.dispatch_ship(&galaxy, surveyor, target, Purpose::Survey)
        .expect("survey the contested claim");
    for _ in 0..40 {
        sim.advance(&galaxy, 30);
        if sim.surveyed_by(PLAYER_CIV, target) {
            break;
        }
    }
    assert!(sim.surveyed_by(PLAYER_CIV, target));
    sim.contest_claim(target).expect("contest the claim");
    assert_eq!(sim.disputes_between(PLAYER_CIV, merchant).len(), 1);

    // A demand for their homeworld is refused, with the cession
    // named in the reasons.
    let greedy = PeaceTerms {
        cede_to_proposer: vec![home],
        cede_to_other: vec![],
        credits_from_proposer: 0.0,
    };
    let outcome = sim
        .propose_peace(&galaxy, merchant, greedy)
        .expect("propose greedy peace");
    let DealOutcome::Refused { reasons } = outcome else {
        panic!("expected refusal, got {outcome:?}");
    };
    let home_name = galaxy.star(home).unwrap().name.clone();
    assert!(
        reasons.join("\n").contains(&home_name),
        "refusal must name the demanded system: {reasons:?}"
    );
    assert_eq!(sim.disputes_between(PLAYER_CIV, merchant).len(), 1);

    // A fair settlement — the disputed claim itself, plus 300
    // credits — is accepted: the claim transfers, the dispute
    // closes, and the credits move exactly.
    let merchant_credits_before = sim.credits_for(merchant);
    let player_credits_before = sim.credits();
    let fair = PeaceTerms {
        cede_to_proposer: vec![target],
        cede_to_other: vec![],
        credits_from_proposer: 300.0,
    };
    let outcome = sim
        .propose_peace(&galaxy, merchant, fair)
        .expect("propose fair peace");
    assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");
    assert_eq!(
        sim.system(target).and_then(|s| s.claimed_by),
        Some(PLAYER_CIV),
        "the ceded claim changed hands"
    );
    assert!(sim.disputes_between(PLAYER_CIV, merchant).is_empty());
    assert!((sim.credits_for(merchant) - merchant_credits_before - 300.0).abs() < 1e-9);
    assert!((sim.credits() - player_credits_before + 300.0).abs() < 1e-9);

    // The settlement holds: two months on, no dispute reopens.
    sim.advance(&galaxy, 60);
    assert!(sim.disputes_between(PLAYER_CIV, merchant).is_empty());
}

#[test]
fn embargo_closes_trade_and_blocks_deals_until_lifted() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    sign_trade(&mut sim, &galaxy, merchant);
    let route_id = sim
        .establish_trade_route(&galaxy, merchant, sim.home_system(), home)
        .expect("establish route");
    sim.advance(&galaxy, 60);
    assert!(sim.trade_route(route_id).unwrap().earned_a > 0.0);

    // Declaring an embargo terminates the agreement as a breach
    // and severs its routes on the spot.
    sim.declare_embargo(merchant).expect("declare embargo");
    assert!(sim.embargo_of(PLAYER_CIV, merchant).is_some());
    assert!(!sim.treaty_active(PLAYER_CIV, merchant, TreatyKind::TradeAgreement));
    assert!(sim.trade_route(route_id).is_none());
    assert!(
        sim.breaches()
            .iter()
            .any(|b| b.breaker == PLAYER_CIV && b.kind == TreatyKind::TradeAgreement)
    );
    // While it stands, no deal is even weighed.
    let outcome = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::TradeAgreement)
        .expect("propose under embargo");
    let DealOutcome::Refused { reasons } = outcome else {
        panic!("expected refusal under embargo, got {outcome:?}");
    };
    assert!(reasons.join(" ").contains("embargo"), "{reasons:?}");

    // Lift it, and trade can be re-signed.
    sim.lift_embargo(merchant).expect("lift embargo");
    assert!(!sim.embargo_between(PLAYER_CIV, merchant));
    sign_trade(&mut sim, &galaxy, merchant);
}

#[test]
fn alliance_needs_shared_rivals_and_binds_like_a_pact() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 3);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    sign_trade(&mut sim, &galaxy, merchant);
    let route_id = sim
        .establish_trade_route(&galaxy, merchant, sim.home_system(), home)
        .expect("establish route");
    // Two years of trade: the trade-volume component warms the
    // relation, but without a shared rival an alliance still
    // refuses.
    sim.advance(&galaxy, 730);
    let before = sim.evaluate_treaty(&galaxy, merchant, PLAYER_CIV, TreatyKind::Alliance);
    assert!(!before.accept, "alliance too easy without a rival: {before:?}");

    // Stage a shared rival: a third civilization whose claim both
    // we and the merchant have surveyed; both contest it.
    let rivals: Vec<u32> = sim
        .civs()
        .iter()
        .map(|c| c.id)
        .filter(|&id| id != PLAYER_CIV && id != merchant)
        .collect();
    let mut staged = false;
    for rival in rivals {
        let candidates: Vec<u32> = sim
            .systems()
            .iter()
            .filter(|(_, s)| s.claimed_by == Some(rival))
            .map(|(id, _)| *id)
            .filter(|id| sim.surveyed_by(merchant, *id) && !sim.surveyed_by(PLAYER_CIV, *id))
            .filter(|id| {
                galaxy
                    .distance_ly(home, *id)
                    .map(|d| d <= 70.0)
                    .unwrap_or(false)
            })
            .collect();
        for target in candidates {
            // The surveyor needs the merchant's fuel for the hop.
            if !sim.treaty_active(PLAYER_CIV, merchant, TreatyKind::GateAccess) {
                let outcome = sim
                    .propose_treaty(&galaxy, merchant, TreatyKind::GateAccess)
                    .expect("propose gate access");
                assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");
            }
            let surveyor = ship_of(&sim, PLAYER_CIV, ShipKind::Surveyor);
            let _ = sim.refuel_ship(surveyor);
            if sim
                .dispatch_ship(&galaxy, surveyor, target, Purpose::Survey)
                .is_err()
            {
                continue;
            }
            for _ in 0..40 {
                sim.advance(&galaxy, 30);
                if sim.surveyed_by(PLAYER_CIV, target) {
                    break;
                }
            }
            if !sim.surveyed_by(PLAYER_CIV, target) {
                continue;
            }
            if sim.contest_claim(target).is_err() {
                continue;
            }
            if sim.contest_claim_for(merchant, target).is_err() {
                continue;
            }
            staged = true;
            break;
        }
        if staged {
            break;
        }
    }
    assert!(staged, "no shared-rival dispute could be staged");

    // Now the alliance weighs differently — and signs.
    let route = sim.trade_route(route_id).expect("route still open");
    let throughput_before = sim.live_route_throughput(route);
    let outcome = sim
        .propose_treaty(&galaxy, merchant, TreatyKind::Alliance)
        .expect("propose alliance");
    assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");
    // Allied markets integrate: the same route carries 25% more.
    let route = sim.trade_route(route_id).expect("route still open");
    let throughput_after = sim.live_route_throughput(route);
    assert!(
        (throughput_after - throughput_before * 1.25).abs() < 1e-9,
        "alliance throughput bonus: {throughput_before} -> {throughput_after}"
    );
    // And an ally's claims are barred from contest, like a pact's.
    let err = sim.contest_claim(home).unwrap_err();
    assert!(matches!(err, SimError::ContestBarredByTreaty), "{err}");
}

#[test]
fn proposal_inbox_accept_refuse_and_cooldown() {
    let (mut sim, galaxy, merchant, _home) = game_with_archetype("Merchant League", 1);
    contact_and_open(&mut sim, &galaxy, merchant, _home);

    // The merchant's own planner may already have offered trade
    // during the months that just passed — that *is* the inbox
    // working. Use a pending trade offer if one is there; file
    // one (the planner's exact call) if not.
    let pending_trade = sim.proposals().iter().find_map(|p| {
        if p.from == merchant
            && matches!(p.kind, mwcs_sim::ProposalKind::Treaty(TreatyKind::TradeAgreement))
        {
            Some(p.id)
        } else {
            None
        }
    });
    let proposal_id = match pending_trade {
        Some(id) => id,
        None => {
            let outcome = sim
                .propose_treaty_for(merchant, &galaxy, PLAYER_CIV, TreatyKind::TradeAgreement)
                .expect("merchant proposes trade");
            let DealOutcome::Pending { proposal_id } = outcome else {
                panic!("expected a pending proposal, got {outcome:?}");
            };
            proposal_id
        }
    };
    let proposal = sim
        .proposals()
        .iter()
        .find(|p| p.id == proposal_id)
        .expect("proposal stored");
    assert!(!proposal.reasons.is_empty(), "offers carry stated reasons");
    // Refuse it: the inbox empties of it, and the merchant will
    // not re-offer the same instrument inside the cooldown.
    let outcome = sim
        .respond_to_proposal(&galaxy, PLAYER_CIV, proposal_id, false)
        .expect("refuse proposal");
    assert!(matches!(outcome, DealOutcome::Declined));
    assert!(sim.proposals().iter().all(|p| p.id != proposal_id));
    let outcome = sim
        .propose_treaty_for(merchant, &galaxy, PLAYER_CIV, TreatyKind::TradeAgreement)
        .expect("merchant re-proposes");
    assert!(
        matches!(outcome, DealOutcome::Refused { .. }),
        "cooldown should refuse the re-offer: {outcome:?}"
    );

    // A different instrument is unaffected by the trade cooldown:
    // gate access is offered and accepted, and the treaty is in
    // force.
    let pending_gate = sim.proposals().iter().find_map(|p| {
        if p.from == merchant
            && matches!(p.kind, mwcs_sim::ProposalKind::Treaty(TreatyKind::GateAccess))
        {
            Some(p.id)
        } else {
            None
        }
    });
    let proposal_id = match pending_gate {
        Some(id) => id,
        None => {
            let outcome = sim
                .propose_treaty_for(merchant, &galaxy, PLAYER_CIV, TreatyKind::GateAccess)
                .expect("merchant proposes gate access");
            let DealOutcome::Pending { proposal_id } = outcome else {
                panic!("expected a pending proposal, got {outcome:?}");
            };
            proposal_id
        }
    };
    let outcome = sim
        .respond_to_proposal(&galaxy, PLAYER_CIV, proposal_id, true)
        .expect("accept proposal");
    assert!(matches!(outcome, DealOutcome::Signed));
    assert!(sim.treaty_active(PLAYER_CIV, merchant, TreatyKind::GateAccess));
    assert!(sim.proposals().iter().all(|p| p.id != proposal_id));
}

#[test]
fn catch_up_equivalence_with_diplomacy_active() {
    let stage = |sim: &mut Campaign, galaxy: &Galaxy, merchant: u32, home: u32| {
        contact_and_open(sim, galaxy, merchant, home);
        sign_trade(sim, galaxy, merchant);
        sim.establish_trade_route(galaxy, merchant, sim.home_system(), home)
            .expect("establish route");
        let outcome = sim
            .propose_treaty(galaxy, merchant, TreatyKind::NonAggressionPact)
            .expect("propose NAP");
        assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");
    };
    let (mut a, galaxy_a, merchant_a, home_a) = game_with_archetype("Merchant League", 2);
    stage(&mut a, &galaxy_a, merchant_a, home_a);
    a.advance(&galaxy_a, 730);

    let (mut b, galaxy_b, merchant_b, home_b) = game_with_archetype("Merchant League", 2);
    stage(&mut b, &galaxy_b, merchant_b, home_b);
    b.advance(&galaxy_b, 365);
    let bytes = b.save_bytes();
    let mut b = Campaign::load_bytes(&galaxy_b, &bytes).expect("reload mid-run");
    b.advance(&galaxy_b, 365);

    assert_eq!(a.state_hash(), b.state_hash(), "catch-up must not drift");
    assert!(a.total_trade_income() > 0.0, "trade actually flowed");
}

#[test]
fn save_round_trip_preserves_the_whole_diplomacy_record() {
    let (mut sim, galaxy, merchant, home) = game_with_archetype("Merchant League", 2);
    contact_and_open(&mut sim, &galaxy, merchant, home);
    sign_trade(&mut sim, &galaxy, merchant);
    sim.establish_trade_route(&galaxy, merchant, sim.home_system(), home)
        .expect("establish route");
    sim.advance(&galaxy, 90);
    sim.break_treaty(merchant, TreatyKind::TradeAgreement)
        .expect("break trade (a breach on record)");
    sim.declare_embargo(merchant).expect("embargo on record");
    let outcome = sim
        .propose_treaty_for(merchant, &galaxy, PLAYER_CIV, TreatyKind::ResearchPact)
        .expect("a pending proposal on record");
    assert!(matches!(outcome, DealOutcome::Pending { .. }));

    let loaded = Campaign::load_bytes(&galaxy, &sim.save_bytes()).expect("reload");
    assert_eq!(sim.canonical_bytes(), loaded.canonical_bytes());
    assert_eq!(sim.state_hash(), loaded.state_hash());
    // The player's own breach (AI civilizations may have breaches
    // of their own on record — the record is campaign-wide).
    assert_eq!(
        loaded
            .breaches()
            .iter()
            .filter(|b| b.breaker == PLAYER_CIV)
            .count(),
        1
    );
    assert!(
        loaded
            .embargoes()
            .iter()
            .any(|e| e.declarer == PLAYER_CIV && e.target == merchant)
    );
    assert!(
        loaded
            .proposals()
            .iter()
            .any(|p| p.from == merchant && p.to == PLAYER_CIV)
    );
}

/// A line galaxy: stars every 70 ly out to 560 — inside ship
/// range hop by hop, but far beyond one trade leg end to end.
fn line_galaxy() -> Galaxy {
    let mut records = vec![star(0, "Sol", [0.0, 0.0, 0.0], 4)];
    for i in 1..=8u32 {
        records.push(star(
            i,
            &format!("Line{i}"),
            [70.0 * i as f32, 0.0, 0.0],
            [4u8, 5, 6][(i % 3) as usize],
        ));
    }
    Galaxy::from_star_records(records)
}

/// Test-side shortest path over the two civilizations' colonies
/// (legs ≤ TRADE_LEG_LY), computed independently of the core's
/// Dijkstra so the two implementations cross-check.
fn expected_path(
    sim: &Campaign,
    galaxy: &Galaxy,
    ai: u32,
    from: u32,
    to: u32,
) -> Option<(Vec<u32>, f64)> {
    use std::collections::BTreeMap;
    let mut nodes = sim.colonies_of(PLAYER_CIV);
    for s in sim.colonies_of(ai) {
        if !nodes.contains(&s) {
            nodes.push(s);
        }
    }
    let mut dist: BTreeMap<u32, f64> = BTreeMap::new();
    let mut prev: BTreeMap<u32, u32> = BTreeMap::new();
    let mut done: Vec<u32> = Vec::new();
    dist.insert(from, 0.0);
    loop {
        let mut best: Option<(f64, u32)> = None;
        for &n in &nodes {
            if done.contains(&n) {
                continue;
            }
            if let Some(&d) = dist.get(&n) {
                if best.map(|(bd, bid)| d < bd || (d == bd && n < bid)).unwrap_or(true) {
                    best = Some((d, n));
                }
            }
        }
        let (cost, node) = best?;
        if node == to {
            let mut path = vec![to];
            let mut cursor = to;
            while cursor != from {
                cursor = *prev.get(&cursor)?;
                path.push(cursor);
            }
            path.reverse();
            return Some((path, cost));
        }
        done.push(node);
        for &next in &nodes {
            if next == node || done.contains(&next) {
                continue;
            }
            let leg = galaxy.distance_ly(node, next)?;
            if leg > TRADE_LEG_LY + 1e-9 {
                continue;
            }
            if cost + leg < *dist.get(&next).unwrap_or(&f64::INFINITY) {
                dist.insert(next, cost + leg);
                prev.insert(next, node);
            }
        }
    }
}

/// Build a fresh ship of `kind` at `system` and return its id.
/// New ships spawn with full tanks — the line test hops 70 ly at
/// a time, which burns nearly a whole tank, and a young colony's
/// fuel production (~1–3/month) cannot refill that quickly; real
/// expansion uses short hops between dense stars instead. If the
/// treasury cannot cover the build yet, wait for settlements and
/// retry.
fn build_fresh_ship(sim: &mut Campaign, galaxy: &Galaxy, system: u32, kind: ShipKind) -> u32 {
    let design_idx = (0..sim.designs().len() as u32)
        .find(|&i| sim.design(i).map(|d| d.kind) == Some(kind))
        .expect("design exists");
    let build_days = sim.design(design_idx).unwrap().build_days();
    let ships_before: Vec<u32> = sim.ships_of(PLAYER_CIV);
    for _ in 0..24 {
        if sim.build_ship(system, design_idx).is_ok() {
            break;
        }
        sim.advance(galaxy, 180);
    }
    sim.advance(galaxy, build_days as u64 + 10);
    sim.ships_of(PLAYER_CIV)
        .into_iter()
        .find(|id| !ships_before.contains(id))
        .expect("the built ship")
}

/// Survey, claim and colonize one line star from the current
/// frontier: a freshly built surveyor hops first (full tank), a
/// freshly built colony ship follows, and the colony is founded
/// on its arrival.
fn colonize_line_star(sim: &mut Campaign, galaxy: &Galaxy, frontier: u32, target: u32) {
    let surveyor = build_fresh_ship(sim, galaxy, frontier, ShipKind::Surveyor);
    sim.dispatch_ship(galaxy, surveyor, target, Purpose::Survey)
        .expect("surveyor hop");
    for _ in 0..40 {
        sim.advance(galaxy, 30);
        if sim.surveyed_by(PLAYER_CIV, target) {
            break;
        }
    }
    assert!(sim.surveyed_by(PLAYER_CIV, target), "survey of {target}");
    sim.claim_system(target).expect("claim the surveyed star");

    let colony_ship = build_fresh_ship(sim, galaxy, frontier, ShipKind::Colony);
    sim.dispatch_ship(galaxy, colony_ship, target, Purpose::Colonize)
        .expect("colony ship hop");
    for _ in 0..40 {
        sim.advance(galaxy, 30);
        if sim.system(target).map(|s| s.colony.is_some()).unwrap_or(false) {
            break;
        }
    }
    assert!(
        sim.system(target).map(|s| s.colony.is_some()).unwrap_or(false),
        "colony founded at {target}"
    );
}

#[test]
fn trade_paths_chain_colony_legs_and_suggestions_follow() {
    // Regression coverage for the route search itself: paths are
    // chains of colony-to-colony legs within tanker range, never a
    // single long jump — and the best-route suggestion follows the
    // same connectivity. (The exhaustive first version of this
    // search also stalled the S4 long run at first contact; the
    // search is now ordered + capped, with identical winners.)
    let galaxy = line_galaxy();
    // Seat the AI at the far end of the line (id 8, x = 560) — the
    // region must reach it, so this test uses its own setup.
    let line_setup = GameSetup {
        ai_count: 1,
        home_rules: HomeworldRules {
            region_radius_ly: 700.0,
            min_spacing_ly: 20.0,
            ..HomeworldRules::default()
        },
        ..GameSetup::default()
    };
    let mut found = None;
    for seed in 0..200u64 {
        let (campaign, report) = Campaign::new_game(&galaxy, seed, &line_setup).expect("setup");
        if report.ai[0].home_system == 8 {
            found = Some((campaign, report.ai[0].civ_id));
            break;
        }
    }
    let (mut sim, ai) = found.expect("some seed seats the AI at the far end");
    let home = 8u32;

    // Only the two homes are colonies: 560 ly apart, no chain.
    assert!(sim.trade_path(&galaxy, PLAYER_CIV, ai, 0, home).is_none());
    assert!(sim.suggest_trade_route(&galaxy, PLAYER_CIV, ai).is_none());

    // Colonize star by star toward the AI. After every founding,
    // the core's answer must match the independent expectation —
    // including the AI's own colonies as potential chain links.
    let mut connected = false;
    for next in 1..8u32 {
        colonize_line_star(&mut sim, &galaxy, next - 1, next);
        let core = sim.trade_path(&galaxy, PLAYER_CIV, ai, 0, home);
        let expected = expected_path(&sim, &galaxy, ai, 0, home);
        assert_eq!(
            core.is_some(),
            expected.is_some(),
            "connectivity after colonizing Line{next}"
        );
        match (core, expected) {
            (Some((path, cost)), Some((_, expected_cost))) => {
                assert_eq!(path.first(), Some(&0));
                assert_eq!(path.last(), Some(&home));
                for leg in path.windows(2) {
                    let d = galaxy.distance_ly(leg[0], leg[1]).unwrap();
                    assert!(d <= TRADE_LEG_LY + 1e-9, "leg of {d} ly in {path:?}");
                }
                assert!(
                    (cost - expected_cost).abs() < 1e-6,
                    "core cost {cost} vs expected {expected_cost}"
                );
                connected = true;
                break;
            }
            _ => {
                assert!(
                    sim.suggest_trade_route(&galaxy, PLAYER_CIV, ai).is_none(),
                    "no suggestion without a path"
                );
            }
        }
    }
    assert!(connected, "the chain eventually connects");

    // The suggestion names the AI home as the far endpoint and a
    // player colony as the near one, over a legal path.
    let (mine, theirs, path, path_ly) =
        sim.suggest_trade_route(&galaxy, PLAYER_CIV, ai).expect("a suggestion");
    assert_eq!(theirs, home);
    assert!(sim.colonies_of(PLAYER_CIV).contains(&mine));
    assert_eq!(path.first(), Some(&mine));
    assert_eq!(path.last(), Some(&home));
    assert!(path_ly > 0.0);
    for leg in path.windows(2) {
        assert!(galaxy.distance_ly(leg[0], leg[1]).unwrap() <= TRADE_LEG_LY + 1e-9);
    }
}
