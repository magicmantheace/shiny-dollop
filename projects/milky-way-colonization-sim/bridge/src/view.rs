//! Serialization of Campaign + Galaxy into VIEW / EVENT / SNAPSHOT /
//! INSPECT JSON, exactly per the S2 bridge spec.

use mwcs_pipeline::table::{FLAG_MASS_DERIVED, FLAG_SOURCE_EXOPLANET_ARCHIVE, FLAG_TEMP_DERIVED};
use mwcs_sim::{
    Campaign, Colony, EventKind, Galaxy, GameEvent, PlanetSource, Purpose, ShipKind, ShipState,
    Specialization, SurveyState,
};

use crate::json::Value;

fn num(n: f64) -> Value {
    Value::Number(n)
}

fn claimed_count(campaign: &Campaign) -> usize {
    campaign
        .systems()
        .values()
        .filter(|s| s.claimed_by.is_some())
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
            ])
        })
        .collect();

    let ships: Vec<Value> = campaign
        .ships()
        .values()
        .map(|ship| {
            let design = campaign.design(ship.design_idx);
            let (design_name, kind, tank_capacity, range_ly) = match design {
                Some(d) => (
                    d.name.clone(),
                    kind_str(d.kind),
                    d.tank_capacity,
                    d.range_ly(),
                ),
                None => (String::new(), "surveyor", 0.0, 0.0),
            };
            Value::obj(vec![
                ("id", Value::from(ship.id)),
                ("design_idx", Value::from(ship.design_idx)),
                ("design_name", Value::from(design_name)),
                ("kind", Value::from(kind)),
                ("fuel", num(ship.fuel)),
                ("tank_capacity", num(tank_capacity)),
                ("range_ly", num(range_ly)),
                ("state", ship_state_json(&ship.state)),
            ])
        })
        .collect();

    let systems: Vec<Value> = campaign
        .systems()
        .iter()
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
                    Value::from(match state.survey {
                        SurveyState::Unknown => "unknown",
                        SurveyState::Surveyed => "surveyed",
                    }),
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
    ])
}

pub fn event_json(galaxy: &Galaxy, event: &GameEvent) -> Value {
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
    ])
}

pub fn events_since(campaign: &Campaign, galaxy: &Galaxy, cursor: u64) -> Vec<Value> {
    let start = cursor as usize;
    if start >= campaign.events().len() {
        return Vec::new();
    }
    campaign.events()[start..]
        .iter()
        .map(|e| event_json(galaxy, e))
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
    let (survey_str, claimed_by, profile_json, colony) = match state {
        None => ("no_state", Value::Null, Value::Null, Value::Null),
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
                match s.survey {
                    SurveyState::Unknown => "unknown",
                    SurveyState::Surveyed => "surveyed",
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

    let ships_present: Vec<Value> = campaign
        .ships()
        .values()
        .filter(|ship| ship.state.current_system() == Some(system_id))
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
        ("ships_present", Value::Array(ships_present)),
    ]))
}
