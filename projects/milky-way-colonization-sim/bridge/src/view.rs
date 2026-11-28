//! Serialization of Campaign + Galaxy into VIEW / EVENT / SNAPSHOT /
//! INSPECT JSON, exactly per the S2 bridge spec.
//!
//! S3: the view is the **player's perspective**. Other
//! civilizations exist in the campaign, but the frontend only ever
//! sees what the player could know: the player's own ships, systems
//! the player has surveyed (plus the player's own claims), events
//! that involve the player or happen in player-surveyed space, and
//! — for civilizations the player has met — the diplomacy picture
//! of design §6.3. Aggregate galaxy totals (colonized/claimed by
//! anyone) are public-scale facts and live in the `galaxy` block;
//! they power the "While you were away" summary (§11.1).

use mwcs_pipeline::table::{FLAG_MASS_DERIVED, FLAG_SOURCE_EXOPLANET_ARCHIVE, FLAG_TEMP_DERIVED};
use mwcs_sim::{
    Campaign, Colony, EventKind, Galaxy, GameEvent, Gate, PeaceTerms, PlanetSource, ProposalKind,
    Purpose, ShipKind, ShipState, Specialization, SurveyState, TreatyKind, VictoryRule, PLAYER_CIV,
};

use crate::json::Value;

fn num(n: f64) -> Value {
    Value::Number(n)
}

fn claimed_count(campaign: &Campaign) -> usize {
    campaign
        .systems()
        .values()
        .filter(|s| s.claimed_by == Some(PLAYER_CIV))
        .count()
}

pub fn star_index(galaxy: &Galaxy, id: u32) -> Option<usize> {
    galaxy.stars().iter().position(|s| s.id == id)
}

pub fn star_name(galaxy: &Galaxy, id: u32) -> Option<String> {
    galaxy.star(id).map(|s| s.name.clone())
}

pub fn kind_str(kind: ShipKind) -> &'static str {
    match kind {
        ShipKind::Surveyor => "surveyor",
        ShipKind::Colony => "colony",
        ShipKind::Frigate => "frigate",
        ShipKind::Cruiser => "cruiser",
        ShipKind::GateBuilder => "gate_builder",
    }
}

pub fn purpose_str(purpose: Purpose) -> &'static str {
    match purpose {
        Purpose::Survey => "survey",
        Purpose::Colonize => "colonize",
        Purpose::Relocate => "relocate",
    }
}

pub fn spec_str(spec: Specialization) -> &'static str {
    match spec {
        Specialization::Industrial => "industrial",
        Specialization::Agricultural => "agricultural",
        Specialization::Refinery => "refinery",
        Specialization::Research => "research",
        Specialization::Fortress => "fortress",
        Specialization::TradeHub => "trade_hub",
        Specialization::Shipyard => "shipyard",
    }
}

pub fn event_kind_str(kind: EventKind) -> &'static str {
    match kind {
        EventKind::CampaignStarted => "campaign_started",
        EventKind::SurveyStarted => "survey_started",
        EventKind::SurveyCompleted => "survey_completed",
        EventKind::SystemClaimed => "system_claimed",
        EventKind::ShipDispatched => "ship_dispatched",
        EventKind::ShipArrived => "ship_arrived",
        EventKind::ShipStranded => "ship_stranded",
        EventKind::ShipRefuelled => "ship_refuelled",
        EventKind::ShipBuilt => "ship_built",
        EventKind::ColonyFounded => "colony_founded",
        EventKind::ColonyAbandoned => "colony_abandoned",
        EventKind::SpecializationSet => "specialization_set",
        EventKind::FirstContact => "first_contact",
        EventKind::ClaimContested => "claim_contested",
        EventKind::TreatySigned => "treaty_signed",
        EventKind::TreatyBroken => "treaty_broken",
        EventKind::EmbargoDeclared => "embargo_declared",
        EventKind::EmbargoLifted => "embargo_lifted",
        EventKind::TradeRouteEstablished => "trade_route_established",
        EventKind::TradeRouteSevered => "trade_route_severed",
        EventKind::PeaceSettled => "peace_settled",
        EventKind::TreatyProposed => "treaty_proposed",
        EventKind::DealRefused => "deal_refused",
        EventKind::WarDeclared => "war_declared",
        EventKind::ShipDestroyed => "ship_destroyed",
        EventKind::OccupationStarted => "occupation_started",
        EventKind::OccupationEnded => "occupation_ended",
        EventKind::GateConstructionStarted => "gate_construction_started",
        EventKind::GateCompleted => "gate_completed",
        EventKind::GatePaired => "gate_paired",
        EventKind::GateDestroyed => "gate_destroyed",
        EventKind::TerraformStarted => "terraform_started",
        EventKind::TerraformCompleted => "terraform_completed",
        EventKind::VictoryAchieved => "victory_achieved",
        EventKind::ColonyBlockaded => "colony_blockaded",
        EventKind::WarEnded => "war_ended",
        EventKind::ColonyResisted => "colony_resisted",
    }
}

pub fn colony_json(colony: &Colony) -> Value {
    let queue: Vec<Value> = colony
        .construction_queue
        .iter()
        .map(|p| {
            Value::obj(vec![
                ("design_idx", Value::from(p.design_idx)),
                ("days_remaining", Value::from(p.days_remaining)),
                ("total_days", Value::from(p.total_days)),
            ])
        })
        .collect();
    Value::obj(vec![
        ("founded_day", Value::from(colony.founded_day)),
        ("population_millions", num(colony.population_millions)),
        ("development", num(colony.development as f64)),
        (
            "specialization",
            match colony.specialization {
                Some(spec) => Value::from(spec_str(spec)),
                None => Value::Null,
            },
        ),
        ("fuel_stock", num(colony.fuel_stock)),
        ("supplies_stock", num(colony.supplies_stock)),
        ("alloys_stock", num(colony.alloys_stock)),
        ("electronics_stock", num(colony.electronics_stock)),
        ("exotics_stock", num(colony.exotics_stock)),
        ("energy_generation", num(colony.energy_generation)),
        ("energy_consumption", num(colony.energy_consumption)),
        ("supplied", Value::Bool(colony.supplied)),
        ("unsupplied_months", Value::from(colony.unsupplied_months)),
        ("construction_queue", Value::Array(queue)),
        // S5: occupation (§6.4) — who holds the colony, since
        // when, and how long the resistance has been building.
        (
            "occupied_by",
            match colony.occupied_by {
                Some(c) => Value::from(c),
                None => Value::Null,
            },
        ),
        (
            "occupied_since_day",
            match colony.occupied_by {
                Some(_) => Value::from(colony.occupied_since_day),
                None => Value::Null,
            },
        ),
        (
            "occupation_resistance_months",
            Value::from(colony.occupation_resistance_months),
        ),
        // S5: the terraforming project (§5.4), when one runs.
        (
            "terraform",
            match colony.terraform_planet {
                Some(planet) => Value::obj(vec![
                    ("planet", Value::from(planet)),
                    ("days_remaining", Value::from(colony.terraform_days_remaining)),
                ]),
                None => Value::Null,
            },
        ),
    ])
}

fn ship_state_json(state: &ShipState) -> Value {
    match state {
        ShipState::AtSystem { system } => Value::obj(vec![
            ("type", Value::from("at_system")),
            ("system", Value::from(*system)),
        ]),
        ShipState::Surveying {
            system,
            days_remaining,
        } => Value::obj(vec![
            ("type", Value::from("surveying")),
            ("system", Value::from(*system)),
            ("days_remaining", Value::from(*days_remaining)),
        ]),
        ShipState::EnRoute {
            from,
            to,
            distance_ly,
            progress_ly,
            purpose,
            unchecked,
        } => Value::obj(vec![
            ("type", Value::from("en_route")),
            ("from", Value::from(*from)),
            ("to", Value::from(*to)),
            ("distance_ly", num(*distance_ly)),
            ("progress_ly", num(*progress_ly)),
            ("purpose", Value::from(purpose_str(*purpose))),
            ("unchecked", Value::Bool(*unchecked)),
        ]),
        ShipState::StrandedEnRoute {
            from,
            to,
            distance_ly,
            progress_ly,
            purpose,
        } => Value::obj(vec![
            ("type", Value::from("stranded_en_route")),
            ("from", Value::from(*from)),
            ("to", Value::from(*to)),
            ("distance_ly", num(*distance_ly)),
            ("progress_ly", num(*progress_ly)),
            ("purpose", Value::from(purpose_str(*purpose))),
        ]),
        ShipState::StrandedAtSystem {
            system,
            pending_purpose,
        } => Value::obj(vec![
            ("type", Value::from("stranded_at_system")),
            ("system", Value::from(*system)),
            (
                "pending_purpose",
                match pending_purpose {
                    Some(p) => Value::from(purpose_str(*p)),
                    None => Value::Null,
                },
            ),
        ]),
        ShipState::GateTransit {
            from_system,
            to_system,
            days_remaining,
        } => Value::obj(vec![
            ("type", Value::from("gate_transit")),
            ("from_system", Value::from(*from_system)),
            ("to_system", Value::from(*to_system)),
            ("days_remaining", Value::from(*days_remaining)),
        ]),
    }
}

pub fn view_json(campaign: &Campaign, galaxy: &Galaxy) -> Value {
    let day = campaign.day();
    let designs: Vec<Value> = campaign
        .designs()
        .iter()
        .enumerate()
        .map(|(idx, d)| {
            Value::obj(vec![
                ("idx", Value::from(idx)),
                ("name", Value::from(d.name.clone())),
                ("kind", Value::from(kind_str(d.kind))),
                ("tank_capacity", num(d.tank_capacity)),
                ("fuel_per_ly", num(d.fuel_per_ly)),
                ("speed_ly_per_day", num(d.speed_ly_per_day)),
                ("range_ly", num(d.range_ly())),
                ("credits_cost", num(d.credits_cost())),
                ("alloys_cost", num(d.alloys_cost())),
                ("build_days", Value::from(d.build_days())),
                // S5: the fixed combat fit (§5.2/§6).
                ("attack", num(d.attack)),
                ("defence", num(d.defence)),
                ("troop_capacity", num(d.troop_capacity)),
                ("hull_strength", num(d.hull_strength())),
            ])
        })
        .collect();

    // Player's ships only: foreign fleets are not the player's to
    // see (their arrivals in player space surface as events).
    let ships: Vec<Value> = campaign
        .ships()
        .values()
        .filter(|ship| ship.owner == PLAYER_CIV)
        .map(|ship| {
            let design = campaign.design(ship.design_idx);
            let (design_name, kind, tank_capacity, range_ly, hull_strength) = match design {
                Some(d) => (
                    d.name.clone(),
                    kind_str(d.kind),
                    d.tank_capacity,
                    d.range_ly(),
                    d.hull_strength(),
                ),
                None => (String::new(), "surveyor", 0.0, 0.0, 0.0),
            };
            Value::obj(vec![
                ("id", Value::from(ship.id)),
                ("owner", Value::from(ship.owner)),
                ("design_idx", Value::from(ship.design_idx)),
                ("design_name", Value::from(design_name)),
                ("kind", Value::from(kind)),
                ("fuel", num(ship.fuel)),
                ("tank_capacity", num(tank_capacity)),
                ("range_ly", num(range_ly)),
                // S5: battle damage is persistent (§6.1) — the
                // viewer shows hull integrity per ship.
                ("hull_damage", num(ship.hull_damage)),
                ("hull_strength", num(hull_strength)),
                ("state", ship_state_json(&ship.state)),
            ])
        })
        .collect();

    // Systems the player knows: surveyed by the player, or held by
    // the player. A system another civilization surveyed stays off
    // the player's map until the player surveys it (§6.1).
    let systems: Vec<Value> = campaign
        .systems()
        .iter()
        .filter(|(_, state)| {
            state.surveyed_by.contains(&PLAYER_CIV) || state.claimed_by == Some(PLAYER_CIV)
        })
        .map(|(id, state)| {
            Value::obj(vec![
                ("id", Value::from(*id)),
                (
                    "index",
                    match star_index(galaxy, *id) {
                        Some(i) => Value::from(i),
                        None => Value::Null,
                    },
                ),
                (
                    "name",
                    match star_name(galaxy, *id) {
                        Some(n) => Value::from(n),
                        None => Value::Null,
                    },
                ),
                (
                    "survey",
                    Value::from(
                        if state.surveyed_by.contains(&PLAYER_CIV) {
                            "surveyed"
                        } else {
                            "unknown"
                        },
                    ),
                ),
                (
                    "claimed_by",
                    match state.claimed_by {
                        Some(c) => Value::from(c),
                        None => Value::Null,
                    },
                ),
                (
                    "colony",
                    match &state.colony {
                        Some(c) => colony_json(c),
                        None => Value::Null,
                    },
                ),
            ])
        })
        .collect();

    Value::obj(vec![
        ("day", Value::from(day)),
        ("year", Value::from(day / 365 + 1)),
        ("day_of_year", Value::from(day % 365 + 1)),
        ("seed", Value::from(campaign.seed())),
        ("credits", num(campaign.credits())),
        ("home_system", Value::from(campaign.home_system())),
        ("state_hash", Value::from(campaign.state_hash())),
        (
            "counts",
            Value::obj(vec![
                ("surveyed", Value::from(campaign.surveyed_count())),
                ("claimed", Value::from(claimed_count(campaign))),
                ("colonized", Value::from(campaign.colonized_count())),
            ]),
        ),
        (
            "total_population_millions",
            num(campaign.total_population_millions()),
        ),
        ("total_fuel_stock", num(campaign.total_fuel_stock())),
        ("designs", Value::Array(designs)),
        ("ships", Value::Array(ships)),
        ("systems", Value::Array(systems)),
        ("events_total", Value::from(campaign.events().len())),
        ("galaxy", galaxy_json(campaign)),
        ("civilizations", civilizations_json(campaign, galaxy)),
        ("trade_routes", trade_routes_json(campaign, galaxy)),
        ("proposals", proposals_json(campaign, galaxy)),
        ("gates", gates_json(campaign, galaxy)),
        ("victory", victory_json(campaign, galaxy)),
    ])
}

/// Galaxy-wide aggregate counts (all civilizations). These are the
/// numbers the §11.1 "While you were away" review watches: the
/// galaxy visibly moves while the player is gone.
pub fn galaxy_json(campaign: &Campaign) -> Value {
    Value::obj(vec![
        ("surveyed", Value::from(campaign.total_surveyed_count())),
        ("claimed", Value::from(campaign.total_claimed_count())),
        ("colonized", Value::from(campaign.total_colonized_count())),
        ("civilizations", Value::from(campaign.civs().len())),
        ("contacts", Value::from(campaign.contacts().len())),
        ("disputes", Value::from(campaign.disputes().len())),
        ("treaties", Value::from(campaign.treaties().len())),
        ("trade_routes", Value::from(campaign.trade_routes().len())),
        ("trade_income_total", num(campaign.total_trade_income())),
    ])
}

fn civ_name(campaign: &Campaign, civ_id: u32) -> Value {
    match campaign.civ(civ_id) {
        Some(civ) => Value::from(civ.name.clone()),
        None => Value::Null,
    }
}

/// The diplomacy roster (§6.3): the player, plus every civilization
/// the player has made contact with, with the legible opinion
/// breakdown in both directions and the open disputes between the
/// pair. Uncontacted civilizations do not appear — the player does
/// not know they exist.
pub fn civilizations_json(campaign: &Campaign, galaxy: &Galaxy) -> Value {
    let mut out: Vec<Value> = Vec::new();
    if let Some(player) = campaign.civ(PLAYER_CIV) {
        out.push(Value::obj(vec![
            ("id", Value::from(PLAYER_CIV)),
            ("name", Value::from(player.name.clone())),
            ("archetype", Value::Null),
            ("is_player", Value::Bool(true)),
            ("home_system", Value::from(player.home_system)),
            (
                "home_name",
                match star_name(galaxy, player.home_system) {
                    Some(n) => Value::from(n),
                    None => Value::Null,
                },
            ),
            ("colonies", Value::from(campaign.colonies_of(PLAYER_CIV).len())),
            ("surveyed", Value::from(campaign.surveyed_count())),
            (
                "research_points",
                num(campaign.research_points_for(PLAYER_CIV)),
            ),
            ("contacted_day", Value::Null),
            ("opinion_of_player", Value::Null),
            ("player_opinion", Value::Null),
            ("disputes", Value::Array(vec![])),
            ("treaties", Value::Array(vec![])),
            ("embargo_by_me", Value::Bool(false)),
            ("embargo_by_them", Value::Bool(false)),
            ("diplomacy_ready", Value::Bool(false)),
            ("translation_ready_day", Value::Null),
            (
                "at_war",
                Value::Bool(!campaign.wars().is_empty()),
            ),
            ("war", Value::Null),
            ("my_war_exhaustion", num(campaign.war_exhaustion(PLAYER_CIV))),
            ("their_war_exhaustion", Value::Null),
        ]));
    }
    for civ in campaign.civs() {
        if civ.id == PLAYER_CIV {
            continue;
        }
        let Some(contacted_day) = campaign.contacted_day(PLAYER_CIV, civ.id) else {
            continue;
        };
        let theirs = campaign.relation(galaxy, civ.id, PLAYER_CIV);
        let ours = campaign.relation(galaxy, PLAYER_CIV, civ.id);
        let disputes: Vec<Value> = campaign
            .disputes_between(PLAYER_CIV, civ.id)
            .iter()
            .map(|d| {
                Value::obj(vec![
                    ("system", Value::from(d.system)),
                    (
                        "system_name",
                        match star_name(galaxy, d.system) {
                            Some(n) => Value::from(n),
                            None => Value::Null,
                        },
                    ),
                    ("holder", Value::from(d.holder)),
                    ("challenger", Value::from(d.challenger)),
                    ("opened_day", Value::from(d.opened_day)),
                    ("tension", num(campaign.dispute_tension(d))),
                ])
            })
            .collect();
        let treaties: Vec<Value> = campaign
            .treaties_between(PLAYER_CIV, civ.id)
            .iter()
            .map(|t| {
                Value::obj(vec![
                    ("kind", Value::from(treaty_kind_str(t.kind))),
                    ("signed_day", Value::from(t.signed_day)),
                ])
            })
            .collect();
        out.push(Value::obj(vec![
            ("id", Value::from(civ.id)),
            ("name", Value::from(civ.name.clone())),
            (
                "archetype",
                match &civ.archetype {
                    Some(a) => Value::from(a.clone()),
                    None => Value::Null,
                },
            ),
            ("is_player", Value::Bool(false)),
            ("home_system", Value::from(civ.home_system)),
            (
                "home_name",
                match star_name(galaxy, civ.home_system) {
                    Some(n) => Value::from(n),
                    None => Value::Null,
                },
            ),
            (
                "known_colonies",
                Value::from(campaign.known_colonies_of(PLAYER_CIV, civ.id)),
            ),
            ("contacted_day", Value::from(contacted_day)),
            (
                "opinion_of_player",
                opinion_json(theirs.opinion),
            ),
            ("player_opinion", opinion_json(ours.opinion)),
            ("disputes", Value::Array(disputes)),
            ("treaties", Value::Array(treaties)),
            (
                "embargo_by_me",
                Value::Bool(campaign.embargo_of(PLAYER_CIV, civ.id).is_some()),
            ),
            (
                "embargo_by_them",
                Value::Bool(campaign.embargo_of(civ.id, PLAYER_CIV).is_some()),
            ),
            (
                "diplomacy_ready",
                Value::Bool(campaign.diplomacy_open(PLAYER_CIV, civ.id)),
            ),
            (
                "translation_ready_day",
                match campaign.diplomacy_ready_day(PLAYER_CIV, civ.id) {
                    Some(day) => Value::from(day),
                    None => Value::Null,
                },
            ),
            // S5 (§6): the war record between the pair, when one
            // is being fought — who declared, when, the losses on
            // each side, and both sides' exhaustion.
            (
                "at_war",
                Value::Bool(campaign.at_war(PLAYER_CIV, civ.id)),
            ),
            (
                "war",
                match campaign.war_between(PLAYER_CIV, civ.id) {
                    Some(war) => {
                        let (my_lost, their_lost) = if war.parties.0 == PLAYER_CIV {
                            (war.ships_lost.0, war.ships_lost.1)
                        } else {
                            (war.ships_lost.1, war.ships_lost.0)
                        };
                        Value::obj(vec![
                            ("aggressor", Value::from(war.aggressor)),
                            ("declared_day", Value::from(war.declared_day)),
                            ("my_ships_lost", Value::from(my_lost)),
                            ("their_ships_lost", Value::from(their_lost)),
                        ])
                    }
                    None => Value::Null,
                },
            ),
            ("my_war_exhaustion", num(campaign.war_exhaustion(PLAYER_CIV))),
            ("their_war_exhaustion", num(campaign.war_exhaustion(civ.id))),
        ]));
    }
    Value::Array(out)
}

fn opinion_json(opinion: mwcs_sim::OpinionBreakdown) -> Value {
    Value::obj(vec![
        ("total", num(opinion.total)),
        ("disposition", num(opinion.disposition)),
        ("disputes", num(opinion.disputes)),
        ("border_friction", num(opinion.border_friction)),
        ("trade_volume", num(opinion.trade_volume)),
        ("broken_treaties", num(opinion.broken_treaties)),
        ("shared_enemies", num(opinion.shared_enemies)),
    ])
}

pub fn victory_rule_str(rule: VictoryRule) -> &'static str {
    match rule {
        VictoryRule::Hegemony => "hegemony",
        VictoryRule::GateWeb => "gate_web",
        VictoryRule::FirstAmongEquals => "first_among_equals",
        VictoryRule::Sandbox => "sandbox",
    }
}

/// One gate (§5.3) as the player may know it. Callers apply the
/// visibility rule; this renders the full record.
pub fn gate_json(campaign: &Campaign, galaxy: &Galaxy, gate: &Gate) -> Value {
    let controller = campaign.gate_controller(gate);
    let state = if gate.build_days_remaining > 0 {
        "building"
    } else if gate.relink_days_remaining > 0 {
        "relinking"
    } else if gate.partner.is_some() {
        "operational"
    } else {
        "unpaired"
    };
    let partner_system = gate.partner.and_then(|pid| {
        campaign
            .gates()
            .iter()
            .find(|g| g.id == pid)
            .map(|g| g.system)
    });
    Value::obj(vec![
        ("id", Value::from(gate.id)),
        ("system", Value::from(gate.system)),
        (
            "system_name",
            match star_name(galaxy, gate.system) {
                Some(n) => Value::from(n),
                None => Value::Null,
            },
        ),
        (
            "controller",
            match controller {
                Some(c) => Value::from(c),
                None => Value::Null,
            },
        ),
        ("mine", Value::Bool(controller == Some(PLAYER_CIV))),
        ("state", Value::from(state)),
        (
            "partner",
            match gate.partner {
                Some(p) => Value::from(p),
                None => Value::Null,
            },
        ),
        (
            "partner_system",
            match partner_system {
                Some(s) => Value::from(s),
                None => Value::Null,
            },
        ),
        ("build_days_remaining", Value::from(gate.build_days_remaining)),
        ("relink_days_remaining", Value::from(gate.relink_days_remaining)),
        ("integrity", num(gate.integrity)),
        ("transits_today", Value::from(gate.transits_today)),
    ])
}

/// The gates the player can see (§5.3 under §6.1 fog): their own,
/// and any gate at a system the player has surveyed — a gate is a
/// large orbital structure; charts that know the system know the
/// gate is there.
pub fn gates_json(campaign: &Campaign, galaxy: &Galaxy) -> Value {
    let gates: Vec<Value> = campaign
        .gates()
        .iter()
        .filter(|g| {
            campaign.gate_controller(g) == Some(PLAYER_CIV)
                || campaign.surveyed_by(PLAYER_CIV, g.system)
        })
        .map(|g| gate_json(campaign, galaxy, g))
        .collect();
    Value::Array(gates)
}

/// The §6.5 victory picture, from the player's seat: the rule in
/// force, the end year for First Among Equals, the recorded
/// winner once one exists (public knowledge — a victory is
/// galaxy news), and the player's own standing on all three
/// measures, tracked whatever rule is in force (§11.4).
pub fn victory_json(campaign: &Campaign, galaxy: &Galaxy) -> Value {
    Value::obj(vec![
        ("rule", Value::from(victory_rule_str(campaign.victory_rule()))),
        ("end_year", Value::from(campaign.victory_end_year())),
        (
            "winner",
            match campaign.victory_winner() {
                Some((civ, day)) => Value::obj(vec![
                    ("civ", Value::from(civ)),
                    (
                        "civ_name",
                        match campaign.civ(civ) {
                            Some(c) => Value::from(c.name.clone()),
                            None => Value::Null,
                        },
                    ),
                    ("day", Value::from(day)),
                ]),
                None => Value::Null,
            },
        ),
        (
            "player",
            Value::obj(vec![
                ("score", num(campaign.victory_score(PLAYER_CIV))),
                ("hegemony_share", num(campaign.hegemony_share(PLAYER_CIV))),
                ("gate_web_share", num(campaign.gate_web_share(galaxy, PLAYER_CIV))),
            ]),
        ),
    ])
}

pub fn treaty_kind_str(kind: TreatyKind) -> &'static str {
    match kind {
        TreatyKind::TradeAgreement => "trade_agreement",
        TreatyKind::GateAccess => "gate_access",
        TreatyKind::NonAggressionPact => "non_aggression_pact",
        TreatyKind::Alliance => "alliance",
        TreatyKind::ResearchPact => "research_pact",
    }
}

/// The player's trade routes (§4.3): endpoints with names, the
/// path the goods travel (star ids — the viewer draws the line
/// along its own table), live throughput, and the ledger. Routes
/// between other civilizations are their business, not the
/// player's map data.
pub fn trade_routes_json(campaign: &Campaign, galaxy: &Galaxy) -> Value {
    let routes: Vec<Value> = campaign
        .trade_routes()
        .iter()
        .filter(|r| r.civ_a == PLAYER_CIV || r.civ_b == PLAYER_CIV)
        .map(|r| {
            let (my_system, their_system, other, earned_by_me) = if r.civ_a == PLAYER_CIV {
                (r.system_a, r.system_b, r.civ_b, r.earned_a)
            } else {
                (r.system_b, r.system_a, r.civ_a, r.earned_b)
            };
            Value::obj(vec![
                ("id", Value::from(r.id)),
                ("other_civ", Value::from(other)),
                (
                    "other_name",
                    match campaign.civ(other) {
                        Some(c) => Value::from(c.name.clone()),
                        None => Value::Null,
                    },
                ),
                ("my_system", Value::from(my_system)),
                (
                    "my_system_name",
                    match star_name(galaxy, my_system) {
                        Some(n) => Value::from(n),
                        None => Value::Null,
                    },
                ),
                ("their_system", Value::from(their_system)),
                (
                    "their_system_name",
                    match star_name(galaxy, their_system) {
                        Some(n) => Value::from(n),
                        None => Value::Null,
                    },
                ),
                (
                    "path",
                    Value::Array(r.path.iter().map(|&s| Value::from(s)).collect()),
                ),
                ("path_ly", num(r.path_ly)),
                ("established_day", Value::from(r.established_day)),
                (
                    "throughput",
                    num(campaign.live_route_throughput(r)),
                ),
                (
                    "distance_factor",
                    num(Campaign::route_distance_factor(r)),
                ),
                (
                    "monthly_income",
                    num(campaign.route_monthly_income(r)),
                ),
                ("earned_by_me", num(earned_by_me)),
                ("earned_total", num(r.earned_a + r.earned_b)),
                ("months_active", Value::from(r.months_active)),
            ])
        })
        .collect();
    Value::Array(routes)
}

fn peace_terms_json(campaign: &Campaign, galaxy: &Galaxy, terms: &PeaceTerms) -> Value {
    let systems = |ids: &[u32]| -> Value {
        Value::Array(
            ids.iter()
                .map(|&id| {
                    Value::obj(vec![
                        ("system", Value::from(id)),
                        (
                            "system_name",
                            match star_name(galaxy, id) {
                                Some(n) => Value::from(n),
                                None => Value::Null,
                            },
                        ),
                        (
                            "has_colony",
                            Value::Bool(
                                campaign
                                    .system(id)
                                    .map(|s| s.colony.is_some())
                                    .unwrap_or(false),
                            ),
                        ),
                    ])
                })
                .collect(),
        )
    };
    Value::obj(vec![
        ("cede_to_proposer", systems(&terms.cede_to_proposer)),
        ("cede_to_other", systems(&terms.cede_to_other)),
        ("credits_from_proposer", num(terms.credits_from_proposer)),
    ])
}

/// Proposals awaiting the player's answer (§6.3): who offers,
/// what instrument or what settlement terms, the day, and the
/// proposer's stated reasons, verbatim.
pub fn proposals_json(campaign: &Campaign, galaxy: &Galaxy) -> Value {
    let proposals: Vec<Value> = campaign
        .proposals()
        .iter()
        .filter(|p| p.to == PLAYER_CIV)
        .map(|p| {
            let (kind_str, treaty_kind, terms) = match &p.kind {
                ProposalKind::Treaty(kind) => (
                    Value::from("treaty"),
                    Value::from(treaty_kind_str(*kind)),
                    Value::Null,
                ),
                ProposalKind::Peace(terms) => (
                    Value::from("peace"),
                    Value::Null,
                    peace_terms_json(campaign, galaxy, terms),
                ),
            };
            Value::obj(vec![
                ("id", Value::from(p.id)),
                ("from", Value::from(p.from)),
                (
                    "from_name",
                    match campaign.civ(p.from) {
                        Some(c) => Value::from(c.name.clone()),
                        None => Value::Null,
                    },
                ),
                ("kind", kind_str),
                ("treaty_kind", treaty_kind),
                ("terms", terms),
                ("proposed_day", Value::from(p.proposed_day)),
                (
                    "reasons",
                    Value::Array(
                        p.reasons
                            .iter()
                            .map(|r| Value::from(r.clone()))
                            .collect(),
                    ),
                ),
            ])
        })
        .collect();
    Value::Array(proposals)
}

pub fn event_json(galaxy: &Galaxy, event: &GameEvent) -> Value {
    event_json_for(galaxy, event, None)
}

/// `event_json` with civilization names resolved against the
/// campaign (the plain form leaves the name fields null).
pub fn event_json_with_names(galaxy: &Galaxy, event: &GameEvent, campaign: &Campaign) -> Value {
    event_json_for(galaxy, event, Some(campaign))
}

fn event_json_for(galaxy: &Galaxy, event: &GameEvent, campaign: Option<&Campaign>) -> Value {
    let civ_field = |civ: Option<u32>| match (civ, campaign) {
        (Some(id), Some(c)) => match c.civ(id) {
            Some(found) => Value::from(found.name.clone()),
            None => Value::Null,
        },
        _ => Value::Null,
    };
    Value::obj(vec![
        ("day", Value::from(event.day)),
        ("kind", Value::from(event_kind_str(event.kind))),
        (
            "system",
            match event.system {
                Some(id) => Value::from(id),
                None => Value::Null,
            },
        ),
        (
            "system_name",
            match event.system.and_then(|id| star_name(galaxy, id)) {
                Some(n) => Value::from(n),
                None => Value::Null,
            },
        ),
        (
            "ship",
            match event.ship {
                Some(id) => Value::from(id),
                None => Value::Null,
            },
        ),
        (
            "civ",
            match event.civ {
                Some(id) => Value::from(id),
                None => Value::Null,
            },
        ),
        ("civ_name", civ_field(event.civ)),
        (
            "other_civ",
            match event.other_civ {
                Some(id) => Value::from(id),
                None => Value::Null,
            },
        ),
        ("other_civ_name", civ_field(event.other_civ)),
    ])
}

/// May the player see this event? (§6.1 fog of war, applied to the
/// event stream.)
///
/// * The player's own events: always.
/// * First contact and claim contests the player is a party to:
///   always (they are the diplomacy record).
/// * Another civilization's *presence* events — founding or losing
///   a colony, claiming a system, completing a survey, arriving or
///   stranding — at a system the player has surveyed: the player's
///   charts can see something happened there.
/// * Everything else (foreign builds, refuels, specializations,
///   movements in uncharted space, diplomacy between strangers):
///   hidden.
pub fn event_visible_to_player(campaign: &Campaign, event: &GameEvent) -> bool {
    match event.kind {
        EventKind::CampaignStarted => event.civ == Some(PLAYER_CIV),
        // Relational events — contact, contests, and the whole S4
        // diplomacy record — are visible when the player is a
        // party to them. Diplomacy between strangers stays hidden,
        // like everything else foreign.
        EventKind::FirstContact
        | EventKind::ClaimContested
        | EventKind::TreatySigned
        | EventKind::TreatyBroken
        | EventKind::EmbargoDeclared
        | EventKind::EmbargoLifted
        | EventKind::TradeRouteEstablished
        | EventKind::TradeRouteSevered
        | EventKind::PeaceSettled
        | EventKind::TreatyProposed
        | EventKind::DealRefused
        // S5: declarations and settlements of war are diplomacy
        // record too — visible to their parties.
        | EventKind::WarDeclared
        | EventKind::WarEnded => {
            event.civ == Some(PLAYER_CIV) || event.other_civ == Some(PLAYER_CIV)
        }
        // S5: a victory is galaxy news, whoever won it.
        EventKind::VictoryAchieved => true,
        _ => {
            if event.civ == Some(PLAYER_CIV) || event.civ.is_none() {
                return true;
            }
            match event.kind {
                EventKind::ColonyFounded
                | EventKind::ColonyAbandoned
                | EventKind::SystemClaimed
                | EventKind::SurveyCompleted
                | EventKind::ShipArrived
                | EventKind::ShipStranded
                // S5 presence events: a battle, an occupation, a
                // blockade, a gate rising or dying, a world being
                // remade — visible in space the player has charted.
                | EventKind::ShipDestroyed
                | EventKind::OccupationStarted
                | EventKind::OccupationEnded
                | EventKind::ColonyResisted
                | EventKind::ColonyBlockaded
                | EventKind::GateConstructionStarted
                | EventKind::GateCompleted
                | EventKind::GatePaired
                | EventKind::GateDestroyed
                | EventKind::TerraformStarted
                | EventKind::TerraformCompleted => {
                    // Charted space — or the player was the other
                    // party (their fleet did the shooting, in
                    // space they may not have surveyed).
                    event
                        .system
                        .map(|s| campaign.surveyed_by(PLAYER_CIV, s))
                        .unwrap_or(false)
                        || event.other_civ == Some(PLAYER_CIV)
                }
                _ => false,
            }
        }
    }
}

pub fn events_since(campaign: &Campaign, galaxy: &Galaxy, cursor: u64) -> Vec<Value> {
    let start = cursor as usize;
    if start >= campaign.events().len() {
        return Vec::new();
    }
    campaign.events()[start..]
        .iter()
        .filter(|e| event_visible_to_player(campaign, e))
        .map(|e| event_json_for(galaxy, e, Some(campaign)))
        .collect()
}

pub fn snapshot_json(campaign: &Campaign) -> Value {
    Value::obj(vec![
        ("day", Value::from(campaign.day())),
        ("credits", num(campaign.credits())),
        (
            "total_population_millions",
            num(campaign.total_population_millions()),
        ),
        ("surveyed", Value::from(campaign.surveyed_count())),
        ("claimed", Value::from(claimed_count(campaign))),
        ("colonized", Value::from(campaign.colonized_count())),
        ("total_fuel_stock", num(campaign.total_fuel_stock())),
        // §11.1: the "While you were away" review surfaces major AI
        // developments — galaxy totals moving, first contacts made,
        // disputes opened — alongside the player's own numbers.
        ("galaxy_surveyed", Value::from(campaign.total_surveyed_count())),
        ("galaxy_claimed", Value::from(campaign.total_claimed_count())),
        (
            "galaxy_colonized",
            Value::from(campaign.total_colonized_count()),
        ),
        ("contacts", Value::from(campaign.contacts().len())),
        ("disputes", Value::from(campaign.disputes().len())),
        // S4: the same review shows diplomacy that moved — treaties
        // in force galaxy-wide, routes open, and the player's own
        // research stockpile growing.
        ("treaties", Value::from(campaign.treaties().len())),
        ("trade_routes", Value::from(campaign.trade_routes().len())),
        (
            "research_points",
            num(campaign.research_points_for(PLAYER_CIV)),
        ),
    ])
}

pub fn inspect_json(campaign: &Campaign, galaxy: &Galaxy, system_id: u32) -> Result<Value, String> {
    let star = galaxy
        .star(system_id)
        .ok_or_else(|| format!("unknown star {system_id}"))?;
    let index = star_index(galaxy, system_id)
        .ok_or_else(|| format!("unknown star {system_id}"))?;
    let dist_sol = ((star.pos_ly[0] as f64).powi(2)
        + (star.pos_ly[1] as f64).powi(2)
        + (star.pos_ly[2] as f64).powi(2))
    .sqrt();
    let home = campaign.home_system();
    let dist_home = galaxy.distance_ly(home, system_id).unwrap_or(dist_sol);

    let catalog_planets: Vec<Value> = star
        .planets
        .iter()
        .map(|p| {
            Value::obj(vec![
                ("name", Value::from(p.name.clone())),
                ("period_days", num(p.period_days as f64)),
                ("semimajor_au", num(p.semimajor_au as f64)),
                ("radius_earth", num(p.radius_earth as f64)),
                ("mass_earth", num(p.mass_earth as f64)),
                ("eq_temp_k", num(p.eq_temp_k as f64)),
            ])
        })
        .collect();

    let state = campaign.system(system_id);
    // Player's knowledge of this system (§6.1): an unsurveyed system
    // shows its catalog data only — no profile, no claim, no colony,
    // however much another civilization knows about it.
    let player_surveyed = campaign.surveyed_by(PLAYER_CIV, system_id);
    let (survey_str, claimed_by, profile_json, colony) = match state {
        None => ("no_state", Value::Null, Value::Null, Value::Null),
        Some(s) if !player_surveyed && s.claimed_by != Some(PLAYER_CIV) => {
            ("unknown", Value::Null, Value::Null, Value::Null)
        }
        Some(s) => {
            let profile = match &s.profile {
                None => Value::Null,
                Some(profile) => {
                    let planets: Vec<Value> = profile
                        .planets
                        .iter()
                        .map(|p| {
                            Value::obj(vec![
                                ("name", Value::from(p.name.clone())),
                                (
                                    "source",
                                    Value::from(match p.source {
                                        PlanetSource::RealCatalog => "real_catalog",
                                        PlanetSource::Generated => "generated",
                                        PlanetSource::HomeworldSetup => "homeworld_setup",
                                    }),
                                ),
                                ("habitability_percent", num(p.habitability_percent)),
                                (
                                    "natural_habitability_percent",
                                    num(p.natural_habitability_percent),
                                ),
                                ("eq_temp_k", num(p.eq_temp_k as f64)),
                                ("radius_earth", num(p.radius_earth as f64)),
                            ])
                        })
                        .collect();
                    Value::obj(vec![
                        ("habitability_percent", num(profile.habitability_percent)),
                        ("fuel_trait", num(profile.fuel_trait)),
                        ("industry_trait", num(profile.industry_trait)),
                        ("exotics_trait", num(profile.exotics_trait)),
                        ("planets", Value::Array(planets)),
                    ])
                }
            };
            (
                if player_surveyed {
                    "surveyed"
                } else {
                    "unknown"
                },
                match s.claimed_by {
                    Some(c) => Value::from(c),
                    None => Value::Null,
                },
                profile,
                match &s.colony {
                    Some(c) => colony_json(c),
                    None => Value::Null,
                },
            )
        }
    };

    // S5: the gate at this system, under the same knowledge rule
    // as the colony — the player knows of a gate where they have
    // charted the system or hold it.
    let player_knows = player_surveyed
        || state.map(|s| s.claimed_by == Some(PLAYER_CIV)).unwrap_or(false);
    let gate = match (player_knows, campaign.gate_at(system_id)) {
        (true, Some(g)) => gate_json(campaign, galaxy, g),
        _ => Value::Null,
    };

    let ships_present: Vec<Value> = campaign
        .ships()
        .values()
        .filter(|ship| ship.owner == PLAYER_CIV && ship.state.current_system() == Some(system_id))
        .map(|ship| Value::from(ship.id))
        .collect();

    Ok(Value::obj(vec![
        ("id", Value::from(star.id)),
        ("index", Value::from(index)),
        ("name", Value::from(star.name.clone())),
        ("spectral", Value::from(star.spectral as u32)),
        (
            "pos_ly",
            Value::Array(vec![
                num(star.pos_ly[0] as f64),
                num(star.pos_ly[1] as f64),
                num(star.pos_ly[2] as f64),
            ]),
        ),
        ("absmag", num(star.absmag as f64)),
        ("teff_k", num(star.teff_k as f64)),
        ("mass_solar", num(star.mass_solar as f64)),
        ("flags", Value::from(star.flags as u32)),
        (
            "temp_derived",
            Value::Bool(star.flags & FLAG_TEMP_DERIVED != 0),
        ),
        (
            "mass_derived",
            Value::Bool(star.flags & FLAG_MASS_DERIVED != 0),
        ),
        (
            "source_exoplanet_archive",
            Value::Bool(star.flags & FLAG_SOURCE_EXOPLANET_ARCHIVE != 0),
        ),
        ("distance_from_sol_ly", num(dist_sol)),
        ("distance_from_home_ly", num(dist_home)),
        ("catalog_planets", Value::Array(catalog_planets)),
        ("survey", Value::from(survey_str)),
        ("claimed_by", claimed_by),
        ("profile", profile_json),
        ("colony", colony),
        ("gate", gate),
        ("ships_present", Value::Array(ships_present)),
    ]))
}
