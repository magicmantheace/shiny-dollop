//! The deterministic, headless simulation state and rules (S1).
//!
//! One tick is one game day. Economy and population are settled every
//! 30 ticks. The core is a pure step function: it does not read a wall
//! clock and it does not call platform randomness. All random-looking
//! values are derived from the campaign seed.

use std::collections::BTreeMap;
use std::fmt;

use crate::catalog::Galaxy;
use crate::profile::{profile_for_star, survey_duration_days, SystemProfile};
use crate::rng::SeededRng;

pub const DAYS_PER_MONTH: u64 = 30;
pub const DAYS_PER_YEAR: u64 = 365;
pub const PLAYER_CIV: u32 = 0;
pub const CLAIM_COST_CREDITS: f64 = 25.0;

pub type StarId = u32;
pub type ShipId = u32;

#[derive(Debug, Clone, PartialEq)]
pub enum SimError {
    UnknownStar(StarId),
    UnknownShip(ShipId),
    UnknownDesign(u32),
    InvalidHomeworld,
    SystemNotSurveyed(StarId),
    SystemAlreadySurveyed(StarId),
    SystemNotClaimed(StarId),
    SystemAlreadyClaimed(StarId),
    SystemAlreadyColonized(StarId),
    ShipBusy(ShipId),
    ShipNotAtSystem(ShipId),
    ShipWrongKind(ShipId),
    BeyondRange {
        distance_ly: f64,
        range_ly: f64,
    },
    InsufficientFuel {
        needed: f64,
        available: f64,
    },
    InsufficientCredits {
        needed: f64,
        available: f64,
    },
    InsufficientStock {
        resource: &'static str,
        needed: f64,
        available: f64,
    },
    NoColony(StarId),
    ColonyRequired(StarId),
    DevelopmentTooLow {
        needed: u8,
        actual: u8,
    },
    SpecializationAlreadySet(StarId),
    InvalidSave(String),
    GalaxyMismatch,
}

impl fmt::Display for SimError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnknownStar(id) => write!(f, "unknown star {id}"),
            Self::UnknownShip(id) => write!(f, "unknown ship {id}"),
            Self::UnknownDesign(id) => write!(f, "unknown ship design {id}"),
            Self::InvalidHomeworld => write!(f, "galaxy has no usable homeworld"),
            Self::SystemNotSurveyed(id) => write!(f, "system {id} has not been surveyed"),
            Self::SystemAlreadySurveyed(id) => write!(f, "system {id} is already surveyed"),
            Self::SystemNotClaimed(id) => {
                write!(f, "system {id} is not claimed by the civilization")
            }
            Self::SystemAlreadyClaimed(id) => write!(f, "system {id} is already claimed"),
            Self::SystemAlreadyColonized(id) => write!(f, "system {id} is already colonized"),
            Self::ShipBusy(id) => write!(f, "ship {id} is not idle at a system"),
            Self::ShipNotAtSystem(id) => write!(f, "ship {id} is not at a system"),
            Self::ShipWrongKind(id) => {
                write!(f, "ship {id} has the wrong hull kind for that order")
            }
            Self::BeyondRange {
                distance_ly,
                range_ly,
            } => write!(
                f,
                "destination is {distance_ly:.2} ly away, beyond the design range {range_ly:.2} ly"
            ),
            Self::InsufficientFuel { needed, available } => {
                write!(f, "ship needs {needed:.2} fuel but carries {available:.2}")
            }
            Self::InsufficientCredits { needed, available } => write!(
                f,
                "order needs {needed:.2} credits but {available:.2} are available"
            ),
            Self::InsufficientStock {
                resource,
                needed,
                available,
            } => write!(
                f,
                "order needs {needed:.2} {resource} but only {available:.2} are stocked"
            ),
            Self::NoColony(id) => write!(f, "system {id} has no colony"),
            Self::ColonyRequired(id) => write!(f, "system {id} must be colonized first"),
            Self::DevelopmentTooLow { needed, actual } => write!(
                f,
                "development {actual} is below the required level {needed}"
            ),
            Self::SpecializationAlreadySet(id) => {
                write!(f, "system {id} already has a specialization")
            }
            Self::InvalidSave(msg) => write!(f, "invalid save: {msg}"),
            Self::GalaxyMismatch => write!(f, "save does not belong to this galaxy table"),
        }
    }
}

impl std::error::Error for SimError {}

pub type SimResult<T> = Result<T, SimError>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SurveyState {
    Unknown,
    Surveyed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Specialization {
    Industrial,
    Agricultural,
    Refinery,
    Research,
    Fortress,
    TradeHub,
    Shipyard,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ShipKind {
    Surveyor,
    Colony,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ShipDesign {
    pub name: String,
    pub kind: ShipKind,
    pub tank_capacity: f64,
    pub fuel_per_ly: f64,
    pub speed_ly_per_day: f64,
    pub payload_capacity: f64,
}

impl ShipDesign {
    pub fn range_ly(&self) -> f64 {
        if self.fuel_per_ly <= 0.0 {
            0.0
        } else {
            self.tank_capacity / self.fuel_per_ly
        }
    }

    pub fn credits_cost(&self) -> f64 {
        match self.kind {
            ShipKind::Surveyor => 400.0,
            ShipKind::Colony => 1_500.0,
        }
    }

    pub fn alloys_cost(&self) -> f64 {
        match self.kind {
            ShipKind::Surveyor => 12.0,
            ShipKind::Colony => 45.0,
        }
    }

    pub fn build_days(&self) -> u32 {
        match self.kind {
            ShipKind::Surveyor => 90,
            ShipKind::Colony => 240,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Purpose {
    Survey,
    Colonize,
    Relocate,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ShipState {
    AtSystem {
        system: StarId,
    },
    Surveying {
        system: StarId,
        days_remaining: u32,
    },
    EnRoute {
        from: StarId,
        to: StarId,
        distance_ly: f64,
        progress_ly: f64,
        purpose: Purpose,
        unchecked: bool,
    },
    StrandedEnRoute {
        from: StarId,
        to: StarId,
        distance_ly: f64,
        progress_ly: f64,
        purpose: Purpose,
    },
    StrandedAtSystem {
        system: StarId,
        pending_purpose: Option<Purpose>,
    },
}

impl ShipState {
    pub fn current_system(&self) -> Option<StarId> {
        match self {
            Self::AtSystem { system }
            | Self::Surveying { system, .. }
            | Self::StrandedAtSystem { system, .. } => Some(*system),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Ship {
    pub id: ShipId,
    pub design_idx: u32,
    pub fuel: f64,
    pub state: ShipState,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ConstructionProject {
    pub id: u32,
    pub design_idx: u32,
    pub days_remaining: u32,
    pub total_days: u32,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Colony {
    pub founded_day: u64,
    /// Population in millions (the design's per-system unit).
    pub population_millions: f64,
    pub development: u8,
    pub specialization: Option<Specialization>,
    pub fuel_stock: f64,
    pub supplies_stock: f64,
    pub alloys_stock: f64,
    pub electronics_stock: f64,
    pub exotics_stock: f64,
    /// Last monthly energy flow values. Energy is local flow, not a
    /// stockpile (design §4.1).
    pub energy_generation: f64,
    pub energy_consumption: f64,
    pub energy_efficiency: f64,
    /// Defence is a placeholder strength in S1; combat is S5.
    pub defence_strength: f64,
    pub supplied: bool,
    pub unsupplied_months: u32,
    pub development_progress_days: u32,
    pub construction_queue: Vec<ConstructionProject>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SystemState {
    pub survey: SurveyState,
    pub profile: Option<SystemProfile>,
    pub claimed_by: Option<u32>,
    pub colony: Option<Colony>,
}

impl Default for SystemState {
    fn default() -> Self {
        Self {
            survey: SurveyState::Unknown,
            profile: None,
            claimed_by: None,
            colony: None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EventKind {
    CampaignStarted,
    SurveyStarted,
    SurveyCompleted,
    SystemClaimed,
    ShipDispatched,
    ShipArrived,
    ShipStranded,
    ShipRefuelled,
    ShipBuilt,
    ColonyFounded,
    ColonyAbandoned,
    SpecializationSet,
}

#[derive(Debug, Clone, PartialEq)]
pub struct GameEvent {
    pub day: u64,
    pub kind: EventKind,
    pub system: Option<StarId>,
    pub ship: Option<ShipId>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Civilization {
    pub id: u32,
    pub name: String,
    pub credits: f64,
    pub home_system: StarId,
}

#[derive(Debug, Clone)]
pub struct Campaign {
    pub(crate) galaxy_fingerprint: String,
    pub(crate) star_count: usize,
    pub(crate) seed: u64,
    pub(crate) day: u64,
    pub(crate) rng: SeededRng,
    pub(crate) civ: Civilization,
    pub(crate) designs: Vec<ShipDesign>,
    pub(crate) systems: BTreeMap<StarId, SystemState>,
    pub(crate) ships: BTreeMap<ShipId, Ship>,
    pub(crate) events: Vec<GameEvent>,
    pub(crate) next_ship_id: ShipId,
    pub(crate) next_project_id: u32,
}

impl Campaign {
    /// Start at Sol (Adam's §11.7 ruling). If a test/custom galaxy has
    /// no star literally named Sol, star id 0 is used as its homeworld.
    pub fn new_default(galaxy: &Galaxy, seed: u64) -> SimResult<Self> {
        let home = galaxy
            .find_by_name("Sol")
            .map(|s| s.id)
            .or_else(|| galaxy.star(0).map(|s| s.id))
            .ok_or(SimError::InvalidHomeworld)?;
        Self::new_at(galaxy, seed, home, "Player Civilization")
    }

    pub fn new_at(
        galaxy: &Galaxy,
        seed: u64,
        home_system: StarId,
        civ_name: impl Into<String>,
    ) -> SimResult<Self> {
        if galaxy.star(home_system).is_none() {
            return Err(SimError::UnknownStar(home_system));
        }
        let designs = vec![
            ShipDesign {
                name: "Pathfinder Surveyor".into(),
                kind: ShipKind::Surveyor,
                tank_capacity: 150.0,
                fuel_per_ly: 2.0,
                speed_ly_per_day: 0.30,
                payload_capacity: 8.0,
            },
            ShipDesign {
                name: "Mayflower Colony Ship".into(),
                kind: ShipKind::Colony,
                tank_capacity: 300.0,
                fuel_per_ly: 4.0,
                speed_ly_per_day: 0.18,
                payload_capacity: 120.0,
            },
        ];

        let mut campaign = Self {
            galaxy_fingerprint: galaxy.fingerprint().to_string(),
            star_count: galaxy.len(),
            seed,
            day: 0,
            rng: SeededRng::new(seed),
            civ: Civilization {
                id: PLAYER_CIV,
                name: civ_name.into(),
                credits: 15_000.0,
                home_system,
            },
            designs,
            systems: BTreeMap::new(),
            ships: BTreeMap::new(),
            events: Vec::new(),
            next_ship_id: 1,
            next_project_id: 1,
        };

        let home_state = SystemState {
            survey: SurveyState::Surveyed,
            profile: Some(SystemProfile::homeworld()),
            claimed_by: Some(PLAYER_CIV),
            colony: Some(Colony {
                founded_day: 0,
                population_millions: 1_200.0,
                development: 3,
                specialization: None,
                fuel_stock: 800.0,
                supplies_stock: 120.0,
                alloys_stock: 200.0,
                electronics_stock: 10.0,
                exotics_stock: 0.0,
                energy_generation: 0.0,
                energy_consumption: 0.0,
                energy_efficiency: 1.0,
                defence_strength: 10.0,
                supplied: true,
                unsupplied_months: 0,
                development_progress_days: 0,
                construction_queue: Vec::new(),
            }),
        };
        campaign.systems.insert(home_system, home_state);
        campaign.spawn_ship(0, home_system);
        campaign.spawn_ship(1, home_system);
        campaign.push_event(EventKind::CampaignStarted, Some(home_system), None);
        Ok(campaign)
    }

    pub fn seed(&self) -> u64 {
        self.seed
    }

    pub fn day(&self) -> u64 {
        self.day
    }

    pub fn credits(&self) -> f64 {
        self.civ.credits
    }

    pub fn home_system(&self) -> StarId {
        self.civ.home_system
    }

    pub fn designs(&self) -> &[ShipDesign] {
        &self.designs
    }

    pub fn design(&self, idx: u32) -> Option<&ShipDesign> {
        self.designs.get(idx as usize)
    }

    pub fn system(&self, id: StarId) -> Option<&SystemState> {
        self.systems.get(&id)
    }

    pub fn systems(&self) -> &BTreeMap<StarId, SystemState> {
        &self.systems
    }

    pub fn ship(&self, id: ShipId) -> Option<&Ship> {
        self.ships.get(&id)
    }

    pub fn ships(&self) -> &BTreeMap<ShipId, Ship> {
        &self.ships
    }

    pub fn events(&self) -> &[GameEvent] {
        &self.events
    }

    pub fn surveyed_count(&self) -> usize {
        self.systems
            .values()
            .filter(|s| s.survey == SurveyState::Surveyed)
            .count()
    }

    pub fn colonized_count(&self) -> usize {
        self.systems.values().filter(|s| s.colony.is_some()).count()
    }

    pub fn total_population_millions(&self) -> f64 {
        self.systems
            .values()
            .filter_map(|s| s.colony.as_ref())
            .map(|c| c.population_millions)
            .sum()
    }

    pub fn total_fuel_stock(&self) -> f64 {
        self.systems
            .values()
            .filter_map(|s| s.colony.as_ref())
            .map(|c| c.fuel_stock)
            .sum()
    }

    fn system_mut_or_default(&mut self, id: StarId) -> &mut SystemState {
        self.systems.entry(id).or_default()
    }

    fn push_event(&mut self, kind: EventKind, system: Option<StarId>, ship: Option<ShipId>) {
        let day = self.day;
        self.events.push(GameEvent {
            day,
            kind,
            system,
            ship,
        });
    }

    fn spawn_ship(&mut self, design_idx: u32, system: StarId) -> ShipId {
        let id = self.next_ship_id;
        self.next_ship_id += 1;
        let fuel = self.designs[design_idx as usize].tank_capacity;
        self.ships.insert(
            id,
            Ship {
                id,
                design_idx,
                fuel,
                state: ShipState::AtSystem { system },
            },
        );
        id
    }

    /// Begin surveying the system a surveyor is already sitting in.
    pub fn begin_survey(&mut self, galaxy: &Galaxy, ship_id: ShipId) -> SimResult<()> {
        let ship = self
            .ships
            .get(&ship_id)
            .ok_or(SimError::UnknownShip(ship_id))?;
        let design = self
            .design(ship.design_idx)
            .ok_or(SimError::UnknownDesign(ship.design_idx))?;
        if design.kind != ShipKind::Surveyor {
            return Err(SimError::ShipWrongKind(ship_id));
        }
        let system = match ship.state {
            ShipState::AtSystem { system } => system,
            _ => return Err(SimError::ShipBusy(ship_id)),
        };
        let star = galaxy.star(system).ok_or(SimError::UnknownStar(system))?;
        if self
            .systems
            .get(&system)
            .map(|s| s.survey)
            .unwrap_or(SurveyState::Unknown)
            == SurveyState::Surveyed
        {
            return Err(SimError::SystemAlreadySurveyed(system));
        }
        let days = survey_duration_days(self.seed, star);
        let ship = self.ships.get_mut(&ship_id).unwrap();
        ship.state = ShipState::Surveying {
            system,
            days_remaining: days,
        };
        self.push_event(EventKind::SurveyStarted, Some(system), Some(ship_id));
        Ok(())
    }

    /// Dispatch a ship to another system. Normal orders are refused
    /// when the destination is beyond the design's range or beyond
    /// the fuel actually on board.
    pub fn dispatch_ship(
        &mut self,
        galaxy: &Galaxy,
        ship_id: ShipId,
        destination: StarId,
        purpose: Purpose,
    ) -> SimResult<()> {
        self.dispatch_inner(galaxy, ship_id, destination, purpose, false)
    }

    /// A deliberate one-way order (design §5.2). This is the only S1
    /// path that can strand a ship: it departs with the fuel on board
    /// even when that fuel cannot complete the leg, then stops when
    /// the tanks are empty. It is never used by the scripted policy.
    pub fn dispatch_ship_unchecked(
        &mut self,
        galaxy: &Galaxy,
        ship_id: ShipId,
        destination: StarId,
        purpose: Purpose,
    ) -> SimResult<()> {
        self.dispatch_inner(galaxy, ship_id, destination, purpose, true)
    }

    fn dispatch_inner(
        &mut self,
        galaxy: &Galaxy,
        ship_id: ShipId,
        destination: StarId,
        purpose: Purpose,
        unchecked: bool,
    ) -> SimResult<()> {
        if galaxy.star(destination).is_none() {
            return Err(SimError::UnknownStar(destination));
        }
        let (from, design_idx, fuel) = {
            let ship = self
                .ships
                .get(&ship_id)
                .ok_or(SimError::UnknownShip(ship_id))?;
            let from = match ship.state {
                ShipState::AtSystem { system } => system,
                _ => return Err(SimError::ShipBusy(ship_id)),
            };
            (from, ship.design_idx, ship.fuel)
        };
        let design = self
            .design(design_idx)
            .ok_or(SimError::UnknownDesign(design_idx))?
            .clone();
        match purpose {
            Purpose::Survey if design.kind != ShipKind::Surveyor => {
                return Err(SimError::ShipWrongKind(ship_id));
            }
            Purpose::Colonize if design.kind != ShipKind::Colony => {
                return Err(SimError::ShipWrongKind(ship_id));
            }
            _ => {}
        }
        if from == destination {
            return match purpose {
                Purpose::Survey => self.begin_survey(galaxy, ship_id),
                Purpose::Colonize => self.found_colony_with_ship(ship_id).map(|_| ()),
                Purpose::Relocate => Ok(()),
            };
        }
        let distance = galaxy
            .distance_ly(from, destination)
            .ok_or(SimError::UnknownStar(destination))?;
        if distance > design.range_ly() + 1e-9 {
            return Err(SimError::BeyondRange {
                distance_ly: distance,
                range_ly: design.range_ly(),
            });
        }
        match purpose {
            Purpose::Survey => {
                if self
                    .systems
                    .get(&destination)
                    .map(|s| s.survey)
                    .unwrap_or(SurveyState::Unknown)
                    == SurveyState::Surveyed
                {
                    return Err(SimError::SystemAlreadySurveyed(destination));
                }
            }
            Purpose::Colonize => self.require_colonizable(destination)?,
            Purpose::Relocate => {}
        }
        let needed = distance * design.fuel_per_ly;
        if !unchecked && fuel + 1e-9 < needed {
            return Err(SimError::InsufficientFuel {
                needed,
                available: fuel,
            });
        }
        let ship = self.ships.get_mut(&ship_id).unwrap();
        ship.state = ShipState::EnRoute {
            from,
            to: destination,
            distance_ly: distance,
            progress_ly: 0.0,
            purpose,
            unchecked,
        };
        self.push_event(EventKind::ShipDispatched, Some(destination), Some(ship_id));
        Ok(())
    }

    fn require_colonizable(&self, system: StarId) -> SimResult<()> {
        let state = self.systems.get(&system);
        if state.map(|s| s.survey).unwrap_or(SurveyState::Unknown) != SurveyState::Surveyed {
            return Err(SimError::SystemNotSurveyed(system));
        }
        if state.and_then(|s| s.claimed_by) != Some(PLAYER_CIV) {
            return Err(SimError::SystemNotClaimed(system));
        }
        if state.map(|s| s.colony.is_some()).unwrap_or(false) {
            return Err(SimError::SystemAlreadyColonized(system));
        }
        Ok(())
    }

    /// Claim a surveyed system. Claims precede founding (design §3).
    pub fn claim_system(&mut self, system: StarId) -> SimResult<()> {
        let state = self
            .systems
            .get(&system)
            .ok_or(SimError::SystemNotSurveyed(system))?;
        if state.survey != SurveyState::Surveyed {
            return Err(SimError::SystemNotSurveyed(system));
        }
        if state.claimed_by.is_some() {
            return Err(SimError::SystemAlreadyClaimed(system));
        }
        if self.civ.credits + 1e-9 < CLAIM_COST_CREDITS {
            return Err(SimError::InsufficientCredits {
                needed: CLAIM_COST_CREDITS,
                available: self.civ.credits,
            });
        }
        self.civ.credits -= CLAIM_COST_CREDITS;
        self.system_mut_or_default(system).claimed_by = Some(PLAYER_CIV);
        self.push_event(EventKind::SystemClaimed, Some(system), None);
        Ok(())
    }

    /// Found a colony using a colony ship that is already in the
    /// target system. The ship is consumed (design §3).
    pub fn found_colony_with_ship(&mut self, ship_id: ShipId) -> SimResult<StarId> {
        let ship = self
            .ships
            .get(&ship_id)
            .ok_or(SimError::UnknownShip(ship_id))?;
        let design = self
            .design(ship.design_idx)
            .ok_or(SimError::UnknownDesign(ship.design_idx))?;
        if design.kind != ShipKind::Colony {
            return Err(SimError::ShipWrongKind(ship_id));
        }
        let system = match ship.state {
            ShipState::AtSystem { system } => system,
            _ => return Err(SimError::ShipBusy(ship_id)),
        };
        self.require_colonizable(system)?;
        let remaining_fuel = ship.fuel;
        self.found_colony(system, remaining_fuel);
        self.ships.remove(&ship_id);
        self.push_event(EventKind::ColonyFounded, Some(system), Some(ship_id));
        Ok(system)
    }

    fn found_colony(&mut self, system: StarId, remaining_ship_fuel: f64) {
        let day = self.day;
        let state = self.system_mut_or_default(system);
        state.claimed_by = Some(PLAYER_CIV);
        state.colony = Some(Colony {
            founded_day: day,
            population_millions: 0.25,
            development: 1,
            specialization: None,
            fuel_stock: 30.0 + remaining_ship_fuel * 0.25,
            supplies_stock: 18.0,
            alloys_stock: 30.0,
            electronics_stock: 2.0,
            exotics_stock: 0.0,
            energy_generation: 0.0,
            energy_consumption: 0.0,
            energy_efficiency: 1.0,
            defence_strength: 1.0,
            supplied: true,
            unsupplied_months: 0,
            development_progress_days: 0,
            construction_queue: Vec::new(),
        });
    }

    /// Queue a ship at a colonized system. Costs are paid at enqueue;
    /// the hull appears when its deterministic build time elapses.
    pub fn build_ship(&mut self, system: StarId, design_idx: u32) -> SimResult<u32> {
        let design = self
            .design(design_idx)
            .ok_or(SimError::UnknownDesign(design_idx))?
            .clone();
        let credits_cost = design.credits_cost();
        let alloys_cost = design.alloys_cost();
        if self.civ.credits + 1e-9 < credits_cost {
            return Err(SimError::InsufficientCredits {
                needed: credits_cost,
                available: self.civ.credits,
            });
        }
        let state = self
            .systems
            .get_mut(&system)
            .ok_or(SimError::NoColony(system))?;
        let colony = state.colony.as_mut().ok_or(SimError::NoColony(system))?;
        if colony.alloys_stock + 1e-9 < alloys_cost {
            return Err(SimError::InsufficientStock {
                resource: "alloys",
                needed: alloys_cost,
                available: colony.alloys_stock,
            });
        }
        self.civ.credits -= credits_cost;
        colony.alloys_stock -= alloys_cost;
        let project_id = self.next_project_id;
        self.next_project_id += 1;
        colony.construction_queue.push(ConstructionProject {
            id: project_id,
            design_idx,
            days_remaining: design.build_days(),
            total_days: design.build_days(),
        });
        Ok(project_id)
    }

    /// Refuel a ship from the colony it is sitting in. Returns the
    /// amount transferred. A ship stranded at a system becomes usable
    /// again; a ship stranded en route cannot be reached in S1 (it
    /// awaits the tanker mechanics of a later slice).
    pub fn refuel_ship(&mut self, ship_id: ShipId) -> SimResult<f64> {
        let (system, design_idx, current_fuel, pending) = {
            let ship = self
                .ships
                .get(&ship_id)
                .ok_or(SimError::UnknownShip(ship_id))?;
            let pending = match ship.state {
                ShipState::AtSystem { system } => (system, None),
                ShipState::StrandedAtSystem {
                    system,
                    pending_purpose,
                } => (system, pending_purpose),
                _ => return Err(SimError::ShipNotAtSystem(ship_id)),
            };
            (pending.0, ship.design_idx, ship.fuel, pending.1)
        };
        let design = self
            .design(design_idx)
            .ok_or(SimError::UnknownDesign(design_idx))?
            .clone();
        let wanted = (design.tank_capacity - current_fuel).max(0.0);
        if wanted <= 1e-9 {
            return Ok(0.0);
        }
        let state = self
            .systems
            .get_mut(&system)
            .ok_or(SimError::NoColony(system))?;
        let colony = state.colony.as_mut().ok_or(SimError::NoColony(system))?;
        let amount = wanted.min(colony.fuel_stock);
        if amount <= 1e-9 {
            return Err(SimError::InsufficientStock {
                resource: "fuel",
                needed: wanted,
                available: colony.fuel_stock,
            });
        }
        colony.fuel_stock -= amount;
        let ship = self.ships.get_mut(&ship_id).unwrap();
        ship.fuel += amount;
        ship.state = ShipState::AtSystem { system };
        self.push_event(EventKind::ShipRefuelled, Some(system), Some(ship_id));

        // A ship that arrived empty with an order still outstanding
        // now carries that order out.
        if let Some(purpose) = pending {
            match purpose {
                Purpose::Survey => {
                    // Survey duration depends on the star; handled by
                    // begin_survey through a temporary galaxy-free
                    // duration fallback is not possible, so the ship
                    // becomes idle and the policy/frontend re-issues
                    // the survey order. This keeps one code path.
                    let _ = purpose;
                }
                Purpose::Colonize => {
                    self.found_colony_with_ship(ship_id)?;
                }
                Purpose::Relocate => {}
            }
        }
        Ok(amount)
    }

    pub fn assign_specialization(
        &mut self,
        system: StarId,
        specialization: Specialization,
    ) -> SimResult<()> {
        let state = self
            .systems
            .get_mut(&system)
            .ok_or(SimError::NoColony(system))?;
        let colony = state.colony.as_mut().ok_or(SimError::NoColony(system))?;
        if colony.development < 3 {
            return Err(SimError::DevelopmentTooLow {
                needed: 3,
                actual: colony.development,
            });
        }
        if colony.specialization.is_some() {
            return Err(SimError::SpecializationAlreadySet(system));
        }
        colony.specialization = Some(specialization);
        self.push_event(EventKind::SpecializationSet, Some(system), None);
        Ok(())
    }

    /// Advance the simulation by whole days. Chunking is irrelevant:
    /// this is exactly a loop over the same daily step.
    pub fn advance(&mut self, galaxy: &Galaxy, days: u64) {
        for _ in 0..days {
            self.advance_one_day(galaxy);
        }
    }

    fn advance_one_day(&mut self, galaxy: &Galaxy) {
        self.day += 1;
        self.process_ship_movement(galaxy);
        self.process_surveys(galaxy);
        self.process_construction();
        if self.day % DAYS_PER_MONTH == 0 {
            self.monthly_settlement();
        }
    }

    fn process_ship_movement(&mut self, galaxy: &Galaxy) {
        let ship_ids: Vec<ShipId> = self.ships.keys().copied().collect();
        let mut arrivals: Vec<(ShipId, StarId, Purpose)> = Vec::new();
        let mut stranded: Vec<ShipId> = Vec::new();

        for ship_id in ship_ids {
            let Some(ship) = self.ships.get_mut(&ship_id) else {
                continue;
            };
            let ShipState::EnRoute {
                from: _,
                to,
                distance_ly,
                progress_ly,
                purpose,
                unchecked,
            } = ship.state.clone()
            else {
                continue;
            };
            let design = self.designs[ship.design_idx as usize].clone();
            let remaining = distance_ly - progress_ly;
            let mut step = design.speed_ly_per_day.min(remaining);
            if unchecked {
                let affordable = ship.fuel / design.fuel_per_ly;
                step = step.min(affordable);
            }
            let burn = step * design.fuel_per_ly;
            ship.fuel = (ship.fuel - burn).max(0.0);
            let new_progress = progress_ly + step;
            if new_progress + 1e-9 >= distance_ly {
                if ship.fuel <= 1e-9 {
                    ship.state = ShipState::StrandedAtSystem {
                        system: to,
                        pending_purpose: Some(purpose),
                    };
                    stranded.push(ship_id);
                } else {
                    ship.state = ShipState::AtSystem { system: to };
                }
                arrivals.push((ship_id, to, purpose));
            } else if ship.fuel <= 1e-9 {
                ship.state = ShipState::StrandedEnRoute {
                    from: match ship.state {
                        ShipState::EnRoute { from, .. } => from,
                        _ => unreachable!(),
                    },
                    to,
                    distance_ly,
                    progress_ly: new_progress,
                    purpose,
                };
                stranded.push(ship_id);
            } else if let ShipState::EnRoute { progress_ly, .. } = &mut ship.state {
                *progress_ly = new_progress;
            }
        }

        for ship_id in stranded {
            let system = self
                .ships
                .get(&ship_id)
                .and_then(|s| s.state.current_system());
            self.push_event(EventKind::ShipStranded, system, Some(ship_id));
        }
        for (ship_id, system, purpose) in arrivals {
            self.push_event(EventKind::ShipArrived, Some(system), Some(ship_id));
            // A ship that arrives with dry tanks is stranded for
            // *movement*, but its arrival order itself does not need
            // fuel: surveying is local sensor work, and founding a
            // colony is what the colony ship is for. Both proceed;
            // only the next departure waits for a refuel.
            match purpose {
                Purpose::Survey => {
                    let stranded_here = matches!(
                        self.ships.get(&ship_id).map(|s| &s.state),
                        Some(ShipState::StrandedAtSystem {
                            pending_purpose: Some(Purpose::Survey),
                            ..
                        })
                    );
                    if stranded_here {
                        if let Some(ship) = self.ships.get_mut(&ship_id) {
                            ship.state = ShipState::AtSystem { system };
                        }
                    }
                    let is_idle = matches!(
                        self.ships.get(&ship_id).map(|s| &s.state),
                        Some(ShipState::AtSystem { .. })
                    );
                    if is_idle {
                        let _ = self.begin_survey(galaxy, ship_id);
                    }
                }
                Purpose::Colonize => {
                    let stranded_here = matches!(
                        self.ships.get(&ship_id).map(|s| &s.state),
                        Some(ShipState::StrandedAtSystem {
                            pending_purpose: Some(Purpose::Colonize),
                            ..
                        })
                    );
                    if stranded_here {
                        if let Some(ship) = self.ships.get_mut(&ship_id) {
                            ship.state = ShipState::AtSystem { system };
                        }
                    }
                    let is_idle = matches!(
                        self.ships.get(&ship_id).map(|s| &s.state),
                        Some(ShipState::AtSystem { .. })
                    );
                    if is_idle {
                        let _ = self.found_colony_with_ship(ship_id);
                    }
                }
                Purpose::Relocate => {}
            }
        }
    }

    fn process_surveys(&mut self, galaxy: &Galaxy) {
        let ship_ids: Vec<ShipId> = self.ships.keys().copied().collect();
        let mut completed: Vec<(ShipId, StarId)> = Vec::new();
        for ship_id in ship_ids {
            let Some(ship) = self.ships.get_mut(&ship_id) else {
                continue;
            };
            if let ShipState::Surveying {
                system,
                days_remaining,
            } = &mut ship.state
            {
                *days_remaining = days_remaining.saturating_sub(1);
                if *days_remaining == 0 {
                    completed.push((ship_id, *system));
                }
            }
        }
        for (ship_id, system) in completed {
            if let Some(star) = galaxy.star(system) {
                let profile = profile_for_star(self.seed, star);
                let state = self.system_mut_or_default(system);
                state.survey = SurveyState::Surveyed;
                state.profile = Some(profile);
            }
            if let Some(ship) = self.ships.get_mut(&ship_id) {
                ship.state = ShipState::AtSystem { system };
            }
            self.push_event(EventKind::SurveyCompleted, Some(system), Some(ship_id));
        }
    }

    fn process_construction(&mut self) {
        let system_ids: Vec<StarId> = self.systems.keys().copied().collect();
        let mut completed: Vec<(StarId, u32)> = Vec::new();
        for system in system_ids {
            let Some(state) = self.systems.get_mut(&system) else {
                continue;
            };
            let Some(colony) = state.colony.as_mut() else {
                continue;
            };
            let mut finished = Vec::new();
            for project in &mut colony.construction_queue {
                project.days_remaining = project.days_remaining.saturating_sub(1);
                if project.days_remaining == 0 {
                    finished.push(project.design_idx);
                }
            }
            colony.construction_queue.retain(|p| p.days_remaining > 0);
            for design_idx in finished {
                completed.push((system, design_idx));
            }
        }
        for (system, design_idx) in completed {
            let ship_id = self.spawn_ship(design_idx, system);
            self.push_event(EventKind::ShipBuilt, Some(system), Some(ship_id));
        }
    }

    fn monthly_settlement(&mut self) {
        let system_ids: Vec<StarId> = self.systems.keys().copied().collect();
        let mut abandoned: Vec<StarId> = Vec::new();
        let mut credits_delta = 0.0;

        for system in system_ids {
            let Some(state) = self.systems.get_mut(&system) else {
                continue;
            };
            let profile = state.profile.clone();
            let Some(colony) = state.colony.as_mut() else {
                continue;
            };
            let habitability = profile
                .as_ref()
                .map(|p| p.habitability_percent)
                .unwrap_or(50.0);
            let fuel_trait = profile.as_ref().map(|p| p.fuel_trait).unwrap_or(0.8);
            let industry_trait = profile.as_ref().map(|p| p.industry_trait).unwrap_or(1.0);
            let exotics_trait = profile.as_ref().map(|p| p.exotics_trait).unwrap_or(0.0);
            let dev = colony.development as f64;

            // Energy: local flow (design §4.1). Deficit reduces the
            // efficiency of everything else this month.
            colony.energy_generation = 120.0 + dev * 30.0 + colony.population_millions.sqrt() * 2.0;
            colony.energy_consumption = 25.0 + dev * 12.0 + colony.population_millions * 0.025;
            colony.energy_efficiency = if colony.energy_consumption <= 0.0 {
                1.0
            } else {
                (colony.energy_generation / colony.energy_consumption).clamp(0.5, 1.0)
            };
            let efficiency = colony.energy_efficiency;

            let spec = colony.specialization;
            let fuel_mult = if spec == Some(Specialization::Refinery) {
                3.0
            } else {
                1.0
            };
            let alloys_mult = if spec == Some(Specialization::Industrial) {
                2.5
            } else {
                1.0
            };
            let supplies_mult = if spec == Some(Specialization::Agricultural) {
                2.2
            } else {
                1.0
            };
            let trade_mult = if spec == Some(Specialization::TradeHub) {
                1.4
            } else {
                1.0
            };

            colony.fuel_stock += (0.8 + dev * 0.45) * fuel_trait * fuel_mult * efficiency;
            colony.alloys_stock += (0.6 + dev * 0.3) * industry_trait * alloys_mult * efficiency;
            colony.supplies_stock +=
                (2.2 + dev * 0.5) * (0.45 + habitability / 100.0) * supplies_mult * efficiency;
            if colony.development >= 5 {
                colony.electronics_stock +=
                    (colony.development as f64 - 4.0) * 0.2 * alloys_mult * efficiency;
            }
            if colony.development >= 4 {
                colony.exotics_stock += exotics_trait * efficiency;
            }
            colony.defence_strength = 1.0
                + dev * 2.0
                + if spec == Some(Specialization::Fortress) {
                    10.0
                } else {
                    0.0
                };

            // Supplies are the binding upkeep in S1 (routes/trade are
            // later slices; each colony draws on its own production
            // and stored buffer, per design §3's buffer rule).
            let supplies_need = colony.population_millions * 0.003 + 0.2;
            if colony.supplies_stock + 1e-9 >= supplies_need {
                colony.supplies_stock -= supplies_need;
                colony.supplied = true;
                colony.unsupplied_months = 0;
            } else {
                colony.supplies_stock = 0.0;
                colony.supplied = false;
                colony.unsupplied_months += 1;
            }

            // Credits: population-driven income minus upkeep.
            let income =
                colony.population_millions * 0.045 * (0.7 + dev * 0.08) * efficiency * trade_mult;
            let upkeep = 2.0 + dev * 1.0 + colony.population_millions * 0.004;
            credits_delta += income - upkeep;

            // Population: logistic growth toward a habitability and
            // development carrying capacity when supplied; decline
            // only after a three-month unsupplied buffer period, and
            // abandonment after twelve (design §3: slow, telegraphed).
            let capacity = 100.0 + habitability * 25.0 + dev * 400.0;
            if colony.supplied {
                let rate = 0.0018 * (habitability / 100.0) * (0.7 + dev * 0.05) * efficiency;
                let headroom = (1.0 - colony.population_millions / capacity).max(0.0);
                colony.population_millions += colony.population_millions * rate * headroom;
                colony.development_progress_days += DAYS_PER_MONTH as u32;
                if colony.development < 5
                    && colony.development_progress_days >= DAYS_PER_YEAR as u32
                    && colony.population_millions > colony.development as f64 * 150.0
                {
                    colony.development += 1;
                    colony.development_progress_days = 0;
                }
            } else if colony.unsupplied_months >= 3 {
                colony.population_millions *= 0.995;
            }
            if colony.unsupplied_months >= 12 {
                abandoned.push(system);
            }
        }

        self.civ.credits += credits_delta;
        for system in abandoned {
            if let Some(state) = self.systems.get_mut(&system) {
                state.colony = None;
            }
            self.push_event(EventKind::ColonyAbandoned, Some(system), None);
        }
    }
}
