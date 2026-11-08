//! S3 integration tests: AI civilization placement (§6.1/§6.2),
//! per-civilization fog of war (§6.1), AI expansion under the same
//! rules (§6.5), first contact (§6.1), claim disputes (§6.3), and
//! catch-up equivalence with AI races active (§11.1).

use mwcs_pipeline::table::{PlanetRecord, StarRecord};
use mwcs_sim::race::HomeworldRules;
use mwcs_sim::{
    Campaign, Galaxy, GameSetup, Purpose, ScriptedPolicy, ShipKind, SimError, PLAYER_CIV,
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

/// Sol plus a grid of G/K/M stars, every grid point within ~70 ly
/// of Sol (inside one surveyor hop), spaced ~25+ ly apart so the
/// placement ladder seats several civilizations at 20 ly spacing.
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

#[test]
fn placement_is_deterministic_spaced_and_equally_provisioned() {
    let galaxy = cluster_galaxy();
    let (a, report_a) = Campaign::new_game(&galaxy, 42, &setup(4)).expect("game A");
    let (b, report_b) = Campaign::new_game(&galaxy, 42, &setup(4)).expect("game B");
    assert_eq!(a.state_hash(), b.state_hash(), "same seed, same setup");
    let homes_a: Vec<u32> = report_a.ai.iter().map(|ai| ai.home_system).collect();
    let homes_b: Vec<u32> = report_b.ai.iter().map(|ai| ai.home_system).collect();
    assert_eq!(homes_a, homes_b);
    assert_eq!(homes_a.len(), 4, "all four AI civs seated");
    assert!(report_a.spacing_used_ly > 0.0);
    for (i, &h1) in homes_a.iter().enumerate() {
        for &h2 in &homes_a[i + 1..] {
            assert_ne!(h1, h2, "homeworlds are distinct");
            let d = galaxy.distance_ly(h1, h2).unwrap();
            assert!(
                d + 1e-9 >= report_a.spacing_used_ly,
                "homes {h1} and {h2} are {d} ly apart, below spacing {}",
                report_a.spacing_used_ly
            );
        }
        let d_sol = galaxy.distance_ly(0, h1).unwrap();
        assert!(d_sol + 1e-9 >= report_a.spacing_used_ly);
    }
    // §6.1's equal start: same credits, same two ships, one colony.
    for civ in 0..=4u32 {
        assert_eq!(a.colonies_of(civ).len(), 1, "civ {civ} home colony");
        assert_eq!(a.ships_of(civ).len(), 2, "civ {civ} starting ships");
        assert_eq!(a.credits_for(civ), 15_000.0, "civ {civ} treasury");
    }
    for ai in &report_a.ai {
        let civ = a.civ(ai.civ_id).expect("civ exists");
        assert!(civ.is_ai());
        assert!(civ.personality.is_some());
        assert_eq!(civ.archetype.as_deref(), Some(ai.archetype.as_str()));
    }
}

#[test]
fn zero_ai_game_matches_the_solo_campaign() {
    let galaxy = cluster_galaxy();
    let (mut with_setup, _) = Campaign::new_game(&galaxy, 7, &setup(0)).expect("setup game");
    let mut solo = Campaign::new_default(&galaxy, 7).expect("solo game");
    assert_eq!(with_setup.state_hash(), solo.state_hash());
    let mut policy = ScriptedPolicy;
    for _ in 0..365 {
        policy.step(&mut with_setup, &galaxy);
        with_setup.advance(&galaxy, 1);
        policy.step(&mut solo, &galaxy);
        solo.advance(&galaxy, 1);
    }
    assert_eq!(with_setup.state_hash(), solo.state_hash());
}

#[test]
fn fog_of_war_is_per_civilization() {
    let galaxy = cluster_galaxy();
    let (campaign, report) = Campaign::new_game(&galaxy, 42, &setup(2)).expect("game");
    let ai_home = report.ai[0].home_system;
    // The AI homeworld *has* been surveyed (by the AI) — globally
    // true — but the player has not surveyed it and cannot see its
    // profile.
    assert!(campaign.system(ai_home).is_some());
    assert!(!campaign.surveyed_by(PLAYER_CIV, ai_home));
    assert!(campaign.known_profile(PLAYER_CIV, ai_home).is_none());
    assert!(campaign.surveyed_by(1, ai_home));
    assert!(campaign.known_profile(1, ai_home).is_some());
    // And symmetrically: the AI does not know Sol.
    assert!(!campaign.surveyed_by(1, 0));
    assert!(campaign.known_profile(1, 0).is_none());
    assert_eq!(campaign.surveyed_count(), 1);
    assert_eq!(campaign.surveyed_count_for(1), 1);
    assert_eq!(campaign.total_surveyed_count(), 3);
    assert!(!campaign.has_contact(0, 1));
}

#[test]
fn ai_expands_and_catch_up_equivalence_holds() {
    let galaxy = cluster_galaxy();
    let (mut a, _) = Campaign::new_game(&galaxy, 42, &setup(3)).expect("game A");
    let (mut c, _) = Campaign::new_game(&galaxy, 42, &setup(3)).expect("game C");
    assert_eq!(a.total_colonized_count(), 4, "four homeworlds");

    a.advance(&galaxy, 1825);
    c.advance(&galaxy, 1825);
    // Save / load mid-run: the loaded campaign must continue to the
    // identical state (catch-up equivalence, §11.1, with AI active).
    let bytes = c.save_bytes();
    let mut c = Campaign::load_bytes(&galaxy, &bytes).expect("load mid-run save");
    assert_eq!(a.state_hash(), c.state_hash(), "round trip at day 1825");

    a.advance(&galaxy, 1825);
    c.advance(&galaxy, 1825);
    assert_eq!(
        a.state_hash(),
        c.state_hash(),
        "save/load at day 1825 then continuing matches the uninterrupted run at day 3650"
    );

    // The AI civilizations expanded under the same rules: more
    // colonies than the four homeworlds, at least one AI civ beyond
    // its homeworld, and every AI colony sits in a system that civ
    // itself surveyed and claimed (no back door).
    assert!(
        a.total_colonized_count() > 4,
        "galaxy colonized {} systems, expected expansion beyond homeworlds",
        a.total_colonized_count()
    );
    let ai_expanded = (1..=3u32).any(|civ| a.colonies_of(civ).len() > 1);
    assert!(ai_expanded, "at least one AI civ founded a second colony");
    for civ in 1..=3u32 {
        for system in a.colonies_of(civ) {
            assert!(a.surveyed_by(civ, system), "civ {civ} surveyed {system}");
            assert_eq!(
                a.system(system).and_then(|s| s.claimed_by),
                Some(civ),
                "civ {civ} holds its colony at {system}"
            );
        }
        assert_ne!(
            a.credits_for(civ),
            15_000.0,
            "civ {civ} economy settled over ten years"
        );
    }
}

#[test]
fn first_contact_when_the_player_surveys_a_foreign_home() {
    let galaxy = cluster_galaxy();
    let (mut campaign, report) = Campaign::new_game(&galaxy, 42, &setup(1)).expect("game");
    let ai_home = report.ai[0].home_system;
    assert!(galaxy.distance_ly(0, ai_home).unwrap() <= 75.0);
    let surveyor = ship_of(&campaign, PLAYER_CIV, ShipKind::Surveyor);
    campaign
        .dispatch_ship(&galaxy, surveyor, ai_home, Purpose::Survey)
        .expect("dispatch surveyor to the AI home");
    campaign.advance(&galaxy, 400);
    assert!(
        campaign.surveyed_by(PLAYER_CIV, ai_home),
        "player survey completed"
    );
    assert!(campaign.has_contact(0, 1), "contact established");
    let contact_day = campaign.contacted_day(0, 1).expect("contact day");
    assert!(contact_day <= 400);
    let contact_events: Vec<_> = campaign
        .events()
        .iter()
        .filter(|e| e.kind == mwcs_sim::EventKind::FirstContact)
        .collect();
    assert_eq!(contact_events.len(), 1, "exactly one first contact");
    assert_eq!(contact_events[0].day, contact_day);
    assert!(campaign.known_profile(PLAYER_CIV, ai_home).is_some());
}

#[test]
fn claim_disputes_open_tension_and_opinion() {
    let galaxy = cluster_galaxy();
    let (mut campaign, report) = Campaign::new_game(&galaxy, 42, &setup(1)).expect("game");
    let ai_home = report.ai[0].home_system;

    // Pick the star that is jointly closest to Sol and the AI home
    // so both civilizations' surveyors can reach it.
    let target = galaxy
        .stars()
        .iter()
        .filter(|s| s.id != 0 && s.id != ai_home)
        .min_by(|a, b| {
            let da = galaxy.distance_ly(0, a.id).unwrap() + galaxy.distance_ly(ai_home, a.id).unwrap();
            let db = galaxy.distance_ly(0, b.id).unwrap() + galaxy.distance_ly(ai_home, b.id).unwrap();
            da.total_cmp(&db)
        })
        .map(|s| s.id)
        .expect("a target star");
    assert!(galaxy.distance_ly(0, target).unwrap() <= 75.0);
    assert!(galaxy.distance_ly(ai_home, target).unwrap() <= 75.0);

    // The player surveys and claims first. (Sequencing matters:
    // left to itself the AI planner claims surveyed systems at
    // month-end — the expansion test relies on exactly that.)
    let player_surveyor = ship_of(&campaign, PLAYER_CIV, ShipKind::Surveyor);
    campaign
        .dispatch_ship(&galaxy, player_surveyor, target, Purpose::Survey)
        .expect("player surveys the target");
    for _ in 0..400 {
        if campaign.surveyed_by(PLAYER_CIV, target) {
            break;
        }
        campaign.advance(&galaxy, 1);
    }
    assert!(campaign.surveyed_by(PLAYER_CIV, target));
    campaign.claim_system(target).expect("player claims");
    // The AI cannot claim what it has not surveyed…
    assert!(matches!(
        campaign.claim_system_for(1, target),
        Err(SimError::SystemNotSurveyed(_))
    ));
    // …and the holder has no foreign claim to contest.
    assert!(matches!(
        campaign.contest_claim_for(PLAYER_CIV, target),
        Err(SimError::NoForeignClaim(_))
    ));

    // Now the AI surveys the claimed system: that is first contact,
    // and the AI gains the knowledge a contest requires. The AI's
    // own planner keeps its surveyors busy, so wait for one to be
    // idle at one of its colonies, top it up, and send it.
    let mut dispatched = false;
    for _ in 0..1500 {
        if campaign.surveyed_by(1, target) {
            dispatched = true;
            break;
        }
        if !dispatched {
            let idle_surveyor = campaign.ships_of(1).into_iter().find(|id| {
                let ship = campaign.ship(*id).unwrap();
                campaign.design(ship.design_idx).map(|d| d.kind) == Some(ShipKind::Surveyor)
                    && matches!(ship.state, mwcs_sim::ShipState::AtSystem { .. })
            });
            if let Some(id) = idle_surveyor {
                let _ = campaign.refuel_ship_for(1, id);
                if campaign
                    .dispatch_ship_for(1, &galaxy, id, target, Purpose::Survey)
                    .is_ok()
                {
                    dispatched = true;
                }
            }
        }
        campaign.advance(&galaxy, 1);
    }
    assert!(campaign.surveyed_by(1, target));
    assert!(
        campaign.has_contact(0, 1),
        "surveying a system the player holds made contact"
    );
    // …and now that it *has* surveyed the system, claiming is
    // refused because the player already holds it.
    assert!(matches!(
        campaign.claim_system_for(1, target),
        Err(SimError::SystemAlreadyClaimed(_))
    ));

    // The AI contests: a dispute opens, with opinion effects. An
    // aggressive AI planner may already have opened it on its own —
    // either path leaves exactly one open dispute.
    if campaign.disputes_between(0, 1).is_empty() {
        campaign
            .contest_claim_for(1, target)
            .expect("AI contests the claim");
    }
    let disputes = campaign.disputes_between(0, 1);
    assert_eq!(disputes.len(), 1);
    assert_eq!(disputes[0].holder, PLAYER_CIV);
    assert_eq!(disputes[0].challenger, 1);
    assert!(matches!(
        campaign.contest_claim_for(1, target),
        Err(SimError::DisputeAlreadyOpen(_))
    ));
    let relation = campaign.relation(&galaxy, 1, PLAYER_CIV);
    assert!(relation.opinion.disputes < 0.0, "dispute hurts opinion");
    assert_eq!(relation.contacted_day, campaign.contacted_day(0, 1));

    let tension_now = campaign.dispute_tension(&disputes[0]);
    campaign.advance(&galaxy, 365);
    let disputes = campaign.disputes_between(0, 1);
    let tension_later = campaign.dispute_tension(&disputes[0]);
    assert!(
        tension_later > tension_now,
        "tension grows while a dispute stays open ({tension_now} -> {tension_later})"
    );
}

#[test]
fn v1_saves_are_rejected_with_a_version_error() {
    let galaxy = cluster_galaxy();
    let (campaign, _) = Campaign::new_game(&galaxy, 42, &setup(1)).expect("game");
    let mut bytes = campaign.save_bytes();
    bytes[4..8].copy_from_slice(&1u32.to_le_bytes());
    match Campaign::load_bytes(&galaxy, &bytes) {
        Err(SimError::InvalidSave(message)) => {
            assert!(message.contains("version 1"), "message was: {message}");
        }
        other => panic!("expected a version error, got {other:?}"),
    }
}
