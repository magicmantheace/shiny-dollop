//! The deterministic, headless simulation state and rules.
//!
//! One tick is one game day. Economy and population are settled every
//! 30 ticks. The core is a pure step function: it does not read a wall
//! clock and it does not call platform randomness. All random-looking
//! values are derived from the campaign seed.
//!
//! S1 built this for one civilization. S3 generalizes the same rules
//! to many: every command is parameterized by the acting
//! civilization, ships and colonies carry their owner, survey
//! knowledge is per-civilization (the fog of war is state, not a
//! view trick), and AI civilizations re-plan inside the monthly
//! settlement step — so advancing a save by N days produces the same
//! galaxy whether the days were played live or applied as offline
//! catch-up. The S1 public API remains as player-civilization
//! wrappers over the generalized commands.
//!
//! S4 adds the diplomacy depth of design §6.3/§4.3 on top of S3's
//! contact and dispute records: treaties (trade, gate access,
//! non-aggression, alliance, research), embargoes, peace settlements
//! with system cessions, inter-civilization trade routes with a
//! credit ledger, and a per-civilization research stockpile that
//! research pacts feed. Deal evaluation lives in `diplomacy.rs` and
//! is a pure function of state, so every acceptance or refusal comes
//! with stated, inspectable reasons (§6.2).

use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

use crate::catalog::Galaxy;
use crate::profile::{profile_for_star, survey_duration_days, SystemProfile};
use crate::race::{generate_ai_civs, AiCivSpec, HomeworldRules, Personality};
use crate::rng::SeededRng;

pub const DAYS_PER_MONTH: u64 = 30;
pub const DAYS_PER_YEAR: u64 = 365;
pub const PLAYER_CIV: u32 = 0;
pub const CLAIM_COST_CREDITS: f64 = 25.0;

/// S4 (§6.3): after first contact, full diplomacy waits out a
/// translation delay — a few months of research-flavoured waiting,
/// at first contact only.
pub const TRANSLATION_DAYS: u64 = 90;
/// S4 (§4.3): one leg of an inter-civilization trade route may span
/// at most this many light-years. Tankers are implied, not
/// micro-managed (§4.3), so the leg is a route-layer constant —
/// twice the colony ship's design range, the longest hull leg in
/// the game. Gate hops would ignore it, but gate construction is
/// S5, so no S4 route uses one.
pub const TRADE_LEG_LY: f64 = 150.0;
/// S4 (§4.3): monthly income per side of a trade route is
/// throughput × distance factor × this rate. A balance placeholder
/// in the same sense as §10's other numbers.
pub const TRADE_INCOME_RATE: f64 = 0.25;
/// S4: a research pact pays each partner this fraction of the
/// *other* partner's monthly research output as bonus points.
pub const RESEARCH_PACT_BONUS_FRACTION: f64 = 0.30;
/// S4: an unanswered proposal to the player lapses after this many
/// days; the proposer then waits out a cooldown before offering
/// the same instrument again.
pub const PROPOSAL_TTL_DAYS: u64 = 180;
pub const PROPOSAL_COOLDOWN_DAYS: u64 = 365;
/// S4: how many endpoint pairs `suggest_trade_route` path-checks,
/// best first, before giving up. A perf bound on a heuristic (see
/// the method's docs); explicit-endpoint commands are unaffected.
pub const SUGGEST_PATH_CHECK_CAP: usize = 24;

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
    ShipNotOwned(ShipId),
    NotYourColony(StarId),
    NoForeignClaim(StarId),
    DisputeAlreadyOpen(StarId),
    UnknownCivilization(u32),
    NoContact(u32),
    DiplomacyNotReady {
        ready_day: u64,
    },
    TreatyAlreadyActive,
    TreatyNotActive,
    EmbargoAlreadyDeclared,
    NoEmbargoInForce,
    ContestBarredByTreaty,
    TradeAgreementRequired,
    NoTradePath,
    TradeRouteAlreadyExists,
    UnknownTradeRoute(u32),
    NotRouteParty(u32),
    UnknownProposal(u32),
    NotProposalRecipient(u32),
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
            Self::ShipNotOwned(id) => {
                write!(f, "ship {id} is not owned by the acting civilization")
            }
            Self::NotYourColony(id) => {
                write!(f, "system {id}'s colony belongs to another civilization")
            }
            Self::NoForeignClaim(id) => {
                write!(f, "system {id} is not claimed by another civilization")
            }
            Self::DisputeAlreadyOpen(id) => {
                write!(f, "a dispute over system {id} is already open for this civilization")
            }
            Self::UnknownCivilization(id) => write!(f, "unknown civilization {id}"),
            Self::NoContact(id) => {
                write!(f, "no contact with civilization {id} — survey a system they hold first")
            }
            Self::DiplomacyNotReady { ready_day } => write!(
                f,
                "translation is still in progress — full diplomacy opens on day {ready_day}"
            ),
            Self::TreatyAlreadyActive => {
                write!(f, "a treaty of this kind is already active between these civilizations")
            }
            Self::TreatyNotActive => {
                write!(f, "no treaty of this kind is active between these civilizations")
            }
            Self::EmbargoAlreadyDeclared => {
                write!(f, "an embargo is already in force in that direction")
            }
            Self::NoEmbargoInForce => write!(f, "no embargo is in force in that direction"),
            Self::ContestBarredByTreaty => write!(
                f,
                "a non-aggression pact or alliance bars contesting this civilization's claims"
            ),
            Self::TradeAgreementRequired => {
                write!(f, "a trade agreement must be active before a route can open")
            }
            Self::NoTradePath => write!(
                f,
                "no route path: the two colony networks have no chain of legs within tanker range"
            ),
            Self::TradeRouteAlreadyExists => {
                write!(f, "a trade route already links these two systems")
            }
            Self::UnknownTradeRoute(id) => write!(f, "unknown trade route {id}"),
            Self::NotRouteParty(id) => {
                write!(f, "civilization {id} is not a party to this trade route")
            }
            Self::UnknownProposal(id) => write!(f, "unknown proposal {id}"),
            Self::NotProposalRecipient(id) => {
                write!(f, "proposal {id} is not addressed to this civilization")
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
    /// The civilization that owns this hull (S3). Every order checks
    /// the acting civilization against this field.
    pub owner: u32,
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
    /// Surveyed by at least one civilization (the revealed truth;
    /// `profile` below is a pure function of seed + star, so storing
    /// it once is safe). Who knows it lives in `surveyed_by`.
    pub survey: SurveyState,
    /// Civilizations that have completed a survey of this system
    /// (S3). This set is the fog of war: commands, AI planning, and
    /// player-facing views all gate on it.
    pub surveyed_by: BTreeSet<u32>,
    pub profile: Option<SystemProfile>,
    pub claimed_by: Option<u32>,
    pub colony: Option<Colony>,
}

impl Default for SystemState {
    fn default() -> Self {
        Self {
            survey: SurveyState::Unknown,
            surveyed_by: BTreeSet::new(),
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
    /// S3: two civilizations met (design §6.3). `civ` is the
    /// discoverer, `other_civ` the civilization discovered.
    FirstContact,
    /// S3: `civ` lodged a competing claim against `other_civ`'s
    /// claim on `system` (design §6.3's disputes).
    ClaimContested,
    /// S4: a treaty was signed between `civ` (the proposer) and
    /// `other_civ`. The instrument itself lives in the treaty
    /// record; the event marks the day.
    TreatySigned,
    /// S4: `civ` broke a treaty with `other_civ`. The breach is
    /// remembered (opinion, §6.2) — breaking is an act with a
    /// reputation.
    TreatyBroken,
    /// S4: `civ` declared an embargo on `other_civ`.
    EmbargoDeclared,
    /// S4: `civ` lifted its embargo on `other_civ`.
    EmbargoLifted,
    /// S4: a trade route opened between `civ` and `other_civ`
    /// (`system` is `civ`'s endpoint).
    TradeRouteEstablished,
    /// S4: a trade route between `civ` and `other_civ` closed —
    /// severed by a party, or its agreement, path, or an endpoint
    /// ceased to hold (`system` is `civ`'s endpoint).
    TradeRouteSevered,
    /// S4: `civ` and `other_civ` settled their disputes in a peace
    /// settlement (terms may include system cessions and credits).
    PeaceSettled,
    /// S4: `civ` sent `other_civ` a proposal that awaits an answer
    /// (only ever addressed to the player; AI-to-AI deals resolve
    /// on the spot).
    TreatyProposed,
    /// S4: `other_civ` refused a deal `civ` proposed. The stated
    /// reasons ride in the command result, not the event.
    DealRefused,
}

#[derive(Debug, Clone, PartialEq)]
pub struct GameEvent {
    pub day: u64,
    pub kind: EventKind,
    pub system: Option<StarId>,
    pub ship: Option<ShipId>,
    /// S3: the civilization this event is about (the actor or
    /// owner). The catch-up review uses it to surface AI
    /// developments during the player's absence.
    pub civ: Option<u32>,
    /// S3: the second civilization for relational events
    /// (FirstContact, ClaimContested).
    pub other_civ: Option<u32>,
}

/// An open claim dispute (design §6.3): `challenger` contests
/// `holder`'s claim on `system`. Disputes are records with opinion
/// effects; settling them is diplomacy (S4).
#[derive(Debug, Clone, PartialEq)]
pub struct Dispute {
    pub system: StarId,
    pub holder: u32,
    pub challenger: u32,
    pub opened_day: u64,
}

/// The negotiable treaty instruments of design §6.3's diplomacy
/// set, S4 subset. (Declare war / sue for peace as war acts are S5;
/// peace *settlements* of disputes are `PeaceTerms` below. Tribute
/// and demands are credits terms inside a peace settlement.)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum TreatyKind {
    /// Opens inter-civilization trade routes (§4.3).
    TradeAgreement,
    /// Port access: each party's ships may refuel at the other's
    /// colonies. §5.3's gate-access treaty, in the only form S4 can
    /// honour — gate *structures* are S5, and this same treaty is
    /// what will govern their transit then.
    GateAccess,
    /// Neither party may contest the other's claims.
    NonAggressionPact,
    /// Non-aggression, port access, and integrated markets (trade
    /// routes between allies carry a throughput bonus). The
    /// defensive-war meaning arrives with war itself in S5.
    Alliance,
    /// A small mutual research bonus while both honour it (§6.3):
    /// each partner gains a fraction of the other's monthly
    /// research output as bonus research points.
    ResearchPact,
}

impl TreatyKind {
    /// Stable serialization / map-key code (save format v3).
    pub fn code(self) -> u8 {
        match self {
            Self::TradeAgreement => 0,
            Self::GateAccess => 1,
            Self::NonAggressionPact => 2,
            Self::Alliance => 3,
            Self::ResearchPact => 4,
        }
    }

    pub fn from_code(code: u8) -> Option<Self> {
        match code {
            0 => Some(Self::TradeAgreement),
            1 => Some(Self::GateAccess),
            2 => Some(Self::NonAggressionPact),
            3 => Some(Self::Alliance),
            4 => Some(Self::ResearchPact),
            _ => None,
        }
    }

    /// Short player-facing name.
    pub fn label(self) -> &'static str {
        match self {
            Self::TradeAgreement => "trade agreement",
            Self::GateAccess => "gate-access treaty",
            Self::NonAggressionPact => "non-aggression pact",
            Self::Alliance => "alliance",
            Self::ResearchPact => "research pact",
        }
    }

    pub const ALL: [TreatyKind; 5] = [
        TreatyKind::TradeAgreement,
        TreatyKind::GateAccess,
        TreatyKind::NonAggressionPact,
        TreatyKind::Alliance,
        TreatyKind::ResearchPact,
    ];
}

/// An active treaty between two civilizations. Treaties are
/// indefinite: they hold until a party breaks one (a breach, with
/// opinion consequences) or a peace settlement supersedes them.
#[derive(Debug, Clone, PartialEq)]
pub struct Treaty {
    pub kind: TreatyKind,
    /// The two parties, sorted `(lo, hi)`.
    pub parties: (u32, u32),
    pub signed_day: u64,
}

/// A unilateral embargo (design §6.3's "trade war without
/// shooting"): `declarer` has closed trade with `target`. While any
/// embargo stands between a pair, in either direction, no trade
/// route runs and no new deal is evaluated — and declaring one
/// terminates the pair's trade agreement on the spot.
#[derive(Debug, Clone, PartialEq)]
pub struct Embargo {
    pub declarer: u32,
    pub target: u32,
    pub since_day: u64,
}

/// An established inter-civilization trade route (§4.3): a named
/// system of each party, the colony-to-colony path the goods
/// actually travel (each leg within tanker range), and the credit
/// ledger — cumulative income earned by each side, which the
/// monthly settlement extends by exactly throughput × distance
/// factor × rate.
#[derive(Debug, Clone, PartialEq)]
pub struct TradeRoute {
    pub id: u32,
    /// Sorted `(lo, hi)`; `system_a` belongs to `civ_a`,
    /// `system_b` to `civ_b`.
    pub civ_a: u32,
    pub civ_b: u32,
    pub system_a: StarId,
    pub system_b: StarId,
    /// Colony systems from `system_a` to `system_b`, inclusive —
    /// the line drawn on the map.
    pub path: Vec<StarId>,
    pub path_ly: f64,
    pub established_day: u64,
    /// The ledger: cumulative credits this route has paid each
    /// side, and the most recent month's payment.
    pub earned_a: f64,
    pub earned_b: f64,
    pub last_income_a: f64,
    pub last_income_b: f64,
    pub months_active: u32,
}

/// The remembered fact that `breaker` broke a treaty of `kind`
/// with `other` (design §6.2's "broken treaties" opinion
/// component). Breaches never expire within a campaign: a record
/// of faithlessness is exactly the kind of thing diplomacy runs on.
#[derive(Debug, Clone, PartialEq)]
pub struct TreatyBreach {
    pub breaker: u32,
    pub other: u32,
    pub kind: TreatyKind,
    pub day: u64,
}

/// The terms of a peace settlement (design §6.3's claim
/// recognition / sue-for-peace, dispute scope): cessions are
/// systems whose *claim* transfers — a colonized system changes
/// owner with its colony, annexation being a treaty act (§6.4).
/// Acceptance closes every open dispute between the pair and
/// lifts any embargo between them.
#[derive(Debug, Clone, PartialEq)]
pub struct PeaceTerms {
    /// Systems the *other* party cedes to the proposer.
    pub cede_to_proposer: Vec<StarId>,
    /// Systems the proposer cedes to the other party.
    pub cede_to_other: Vec<StarId>,
    /// Credits the proposer pays the other party; negative means
    /// the other party pays the proposer.
    pub credits_from_proposer: f64,
}

impl PeaceTerms {
    pub fn recognition_only() -> Self {
        Self {
            cede_to_proposer: Vec::new(),
            cede_to_other: Vec::new(),
            credits_from_proposer: 0.0,
        }
    }

    pub fn is_empty(&self) -> bool {
        self.cede_to_proposer.is_empty()
            && self.cede_to_other.is_empty()
            && self.credits_from_proposer == 0.0
    }
}

/// What a proposal asks for: a treaty, or a peace settlement on
/// stated terms.
#[derive(Debug, Clone, PartialEq)]
pub enum ProposalKind {
    Treaty(TreatyKind),
    Peace(PeaceTerms),
}

impl ProposalKind {
    /// Map key component for proposal cooldowns: treaty kinds use
    /// their own code; peace uses a reserved code.
    pub fn cooldown_code(&self) -> u8 {
        match self {
            Self::Treaty(kind) => kind.code(),
            Self::Peace(_) => 15,
        }
    }
}

/// A deal offered by one civilization to another that awaits an
/// answer. Only proposals addressed to the *player* are ever
/// stored: AI-to-AI offers are evaluated and resolved on the spot,
/// because an AI's answer is a pure function of state. The stated
/// reasons the proposer gave are stored verbatim — the player
/// reads the same numbers the proposer computed.
#[derive(Debug, Clone, PartialEq)]
pub struct Proposal {
    pub id: u32,
    pub from: u32,
    pub to: u32,
    pub kind: ProposalKind,
    pub proposed_day: u64,
    pub reasons: Vec<String>,
}

/// The result of proposing a deal.
#[derive(Debug, Clone, PartialEq)]
pub enum DealOutcome {
    /// The deal was accepted and is in force from today.
    Signed,
    /// The other civilization refused; `reasons` are its stated,
    /// itemized grounds (the §6.2 legibility rule applied to the
    /// answer itself).
    Refused { reasons: Vec<String> },
    /// The offer awaits the player's answer in their proposal
    /// inbox.
    Pending { proposal_id: u32 },
    /// The player declined an offer made to them.
    Declined,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Civilization {
    pub id: u32,
    pub name: String,
    pub credits: f64,
    pub home_system: StarId,
    /// S3: the archetype name for AI civilizations ("Merchant
    /// League", …); `None` for the player.
    pub archetype: Option<String>,
    /// S3: the personality vector for AI civilizations (design
    /// §6.2); `None` for the player.
    pub personality: Option<Personality>,
    /// S4: accumulated research points. Research-specialized
    /// colonies produce points monthly; a research pact adds a
    /// bonus drawn from the partner's output. Points have no
    /// spending sink until the technology tree lands (§8 is a
    /// sketch); the stockpile is the pact's honest ledger.
    pub research_points: f64,
}

impl Civilization {
    pub fn is_ai(&self) -> bool {
        self.id != PLAYER_CIV
    }
}

/// Setup for a full game (S3): the player plus AI civilizations.
#[derive(Debug, Clone)]
pub struct GameSetup {
    /// AI civilizations to place (design §11.3: 12 by default; the
    /// 4–40 setup slider counts all civilizations, so at most 39).
    pub ai_count: usize,
    pub player_name: String,
    pub home_rules: HomeworldRules,
}

impl Default for GameSetup {
    fn default() -> Self {
        Self {
            ai_count: crate::race::DEFAULT_AI_COUNT,
            player_name: "Player Civilization".into(),
            home_rules: HomeworldRules::default(),
        }
    }
}

/// One AI civilization as placed by game setup.
#[derive(Debug, Clone, PartialEq)]
pub struct AiCivSetup {
    pub civ_id: u32,
    pub name: String,
    pub archetype: String,
    pub home_system: StarId,
    /// Design §6.1's homeworld guarantee, flagged openly: true when
    /// the star's natural profile was below the homeworld bar and
    /// setup granted the standard profile anyway.
    pub homeworld_adjusted: bool,
}

/// What game setup did, for the setup screen and the records.
#[derive(Debug, Clone, PartialEq)]
pub struct SetupReport {
    pub player_home: StarId,
    pub spacing_used_ly: f64,
    pub ai: Vec<AiCivSetup>,
}

#[derive(Debug, Clone)]
pub struct Campaign {
    pub(crate) galaxy_fingerprint: String,
    pub(crate) star_count: usize,
    pub(crate) seed: u64,
    pub(crate) day: u64,
    pub(crate) rng: SeededRng,
    /// All civilizations, indexed by id; `civs[PLAYER_CIV]` is the
    /// player. S1 campaigns hold exactly one entry.
    pub(crate) civs: Vec<Civilization>,
    pub(crate) designs: Vec<ShipDesign>,
    pub(crate) systems: BTreeMap<StarId, SystemState>,
    pub(crate) ships: BTreeMap<ShipId, Ship>,
    pub(crate) events: Vec<GameEvent>,
    /// S3: first-contact days, keyed by the sorted civilization
    /// pair `(lo, hi)`.
    pub(crate) contacts: BTreeMap<(u32, u32), u64>,
    /// S3: open claim disputes, in the order they opened.
    pub(crate) disputes: Vec<Dispute>,
    /// S4: active treaties, in signing order.
    pub(crate) treaties: Vec<Treaty>,
    /// S4: embargoes in force, in declaration order.
    pub(crate) embargoes: Vec<Embargo>,
    /// S4: established trade routes, in opening order.
    pub(crate) trade_routes: Vec<TradeRoute>,
    /// S4: remembered treaty breaches, in the order they happened.
    pub(crate) breaches: Vec<TreatyBreach>,
    /// S4: proposals awaiting the player's answer.
    pub(crate) proposals: Vec<Proposal>,
    /// S4: per-(pair, instrument) day before which a proposer will
    /// not re-offer an instrument the player refused or let lapse,
    /// keyed `(lo, hi, cooldown_code)`.
    pub(crate) proposal_cooldowns: BTreeMap<(u32, u32, u8), u64>,
    pub(crate) next_ship_id: ShipId,
    pub(crate) next_project_id: u32,
    pub(crate) next_route_id: u32,
    pub(crate) next_proposal_id: u32,
    /// S4: all-time trade income paid out across every route that
    /// ever ran (both sides). Route ledgers are per-route records
    /// that close when a route does; this counter is the campaign
    /// total the long-run reports quote.
    pub(crate) total_trade_income: f64,
    /// Derived cache (never serialized, rebuilt lazily after load):
    /// stars within `NEIGHBOR_CACHE_RANGE_LY` of a key star, sorted
    /// by `(distance, id)`. It exists so monthly AI planning over a
    /// 113k-star catalog does not rescan the galaxy per ship; its
    /// contents cannot change any decision, only how fast it is
    /// reached.
    pub(crate) neighbor_cache: BTreeMap<StarId, Vec<(f64, StarId)>>,
}

/// The neighbor cache's fixed radius: just beyond the longest
/// design range in the game (75 ly colony/survey designs).
pub(crate) const NEIGHBOR_CACHE_RANGE_LY: f64 = 80.0;

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
        let mut campaign = Self::shell(galaxy, seed);
        campaign.add_civilization(
            Civilization {
                id: PLAYER_CIV,
                name: civ_name.into(),
                credits: 15_000.0,
                home_system,
                archetype: None,
                personality: None,
                research_points: 0.0,
            },
            SystemProfile::homeworld(),
        );
        Ok(campaign)
    }

    /// Start a full S3 game: the player at Sol (ruling §11.7) plus
    /// `setup.ai_count` AI civilizations placed by the §6.1 fairness
    /// algorithm, each starting under exactly the player's rules —
    /// same credits, same homeworld colony, same two ships.
    pub fn new_game(
        galaxy: &Galaxy,
        seed: u64,
        setup: &GameSetup,
    ) -> SimResult<(Self, SetupReport)> {
        if setup.ai_count > crate::race::MAX_AI_COUNT {
            return Err(SimError::InvalidHomeworld);
        }
        let player_home = galaxy
            .find_by_name("Sol")
            .map(|s| s.id)
            .or_else(|| galaxy.star(0).map(|s| s.id))
            .ok_or(SimError::InvalidHomeworld)?;
        let (specs, spacing_used): (Vec<AiCivSpec>, f64) = if setup.ai_count == 0 {
            (Vec::new(), setup.home_rules.min_spacing_ly)
        } else {
            generate_ai_civs(galaxy, seed, player_home, setup.ai_count, &setup.home_rules)
        };
        if specs.len() < setup.ai_count {
            // The galaxy cannot seat that many civilizations under
            // the fairness rules — refuse rather than silently
            // start a smaller game than was asked for.
            return Err(SimError::InvalidHomeworld);
        }
        let mut campaign = Self::shell(galaxy, seed);
        campaign.add_civilization(
            Civilization {
                id: PLAYER_CIV,
                name: setup.player_name.clone(),
                credits: 15_000.0,
                home_system: player_home,
                archetype: None,
                personality: None,
                research_points: 0.0,
            },
            SystemProfile::homeworld(),
        );
        let mut report_ai = Vec::with_capacity(specs.len());
        for (i, spec) in specs.iter().enumerate() {
            let civ_id = (i + 1) as u32;
            let star_name = galaxy
                .star(spec.home_system)
                .map(|s| s.name.clone())
                .unwrap_or_default();
            campaign.add_civilization(
                Civilization {
                    id: civ_id,
                    name: spec.name.clone(),
                    credits: 15_000.0,
                    home_system: spec.home_system,
                    archetype: Some(spec.archetype.to_string()),
                    personality: Some(spec.personality),
                    research_points: 0.0,
                },
                SystemProfile::homeworld_named(format!("{star_name} Prime")),
            );
            report_ai.push(AiCivSetup {
                civ_id,
                name: spec.name.clone(),
                archetype: spec.archetype.to_string(),
                home_system: spec.home_system,
                homeworld_adjusted: spec.homeworld_adjusted,
            });
        }
        Ok((
            campaign,
            SetupReport {
                player_home,
                spacing_used_ly: spacing_used,
                ai: report_ai,
            },
        ))
    }

    /// An empty campaign shell: the two fixed S1 ship designs
    /// (custom designs are a later slice, per the S2 scope notes),
    /// no civilizations yet.
    fn shell(galaxy: &Galaxy, seed: u64) -> Self {
        Self {
            galaxy_fingerprint: galaxy.fingerprint().to_string(),
            star_count: galaxy.len(),
            seed,
            day: 0,
            rng: SeededRng::new(seed),
            civs: Vec::new(),
            designs: vec![
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
            ],
            systems: BTreeMap::new(),
            ships: BTreeMap::new(),
            events: Vec::new(),
            contacts: BTreeMap::new(),
            disputes: Vec::new(),
            treaties: Vec::new(),
            embargoes: Vec::new(),
            trade_routes: Vec::new(),
            breaches: Vec::new(),
            proposals: Vec::new(),
            proposal_cooldowns: BTreeMap::new(),
            next_ship_id: 1,
            next_project_id: 1,
            next_route_id: 1,
            next_proposal_id: 1,
            total_trade_income: 0.0,
            neighbor_cache: BTreeMap::new(),
        }
    }

    /// Seat a civilization on its homeworld: the standard starting
    /// colony (identical numbers for every civilization — §6.1's
    /// "same rules"), a surveyor and a colony ship in orbit, and
    /// the campaign-started event.
    fn add_civilization(&mut self, civ: Civilization, home_profile: SystemProfile) {
        let civ_id = civ.id;
        let home_system = civ.home_system;
        debug_assert_eq!(self.civs.len() as u32, civ_id);
        self.civs.push(civ);
        let home_state = SystemState {
            survey: SurveyState::Surveyed,
            surveyed_by: BTreeSet::from([civ_id]),
            profile: Some(home_profile),
            claimed_by: Some(civ_id),
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
        self.systems.insert(home_system, home_state);
        self.spawn_ship(civ_id, 0, home_system);
        self.spawn_ship(civ_id, 1, home_system);
        self.push_event(
            EventKind::CampaignStarted,
            Some(home_system),
            None,
            Some(civ_id),
            None,
        );
    }

    pub fn seed(&self) -> u64 {
        self.seed
    }

    pub fn day(&self) -> u64 {
        self.day
    }

    /// The player's credits (S1 accessor; see `credits_for`).
    pub fn credits(&self) -> f64 {
        self.credits_for(PLAYER_CIV)
    }

    pub fn credits_for(&self, civ_id: u32) -> f64 {
        self.civ(civ_id).map(|c| c.credits).unwrap_or(0.0)
    }

    /// The player's home system (S1 accessor; see `civ`).
    pub fn home_system(&self) -> StarId {
        self.civs[PLAYER_CIV as usize].home_system
    }

    pub fn civ(&self, id: u32) -> Option<&Civilization> {
        self.civs.get(id as usize)
    }

    pub fn civs(&self) -> &[Civilization] {
        &self.civs
    }

    /// Has `civ_id` completed a survey of `system`? This is that
    /// civilization's fog-of-war knowledge, nothing more global.
    pub fn surveyed_by(&self, civ_id: u32, system: StarId) -> bool {
        self.systems
            .get(&system)
            .map(|s| s.surveyed_by.contains(&civ_id))
            .unwrap_or(false)
    }

    /// The system's profile as known by `civ_id`: present only when
    /// that civilization has surveyed the system.
    pub fn known_profile(&self, civ_id: u32, system: StarId) -> Option<&SystemProfile> {
        if !self.surveyed_by(civ_id, system) {
            return None;
        }
        self.systems.get(&system).and_then(|s| s.profile.as_ref())
    }

    /// Systems where `civ_id` holds a colony, ascending by star id.
    pub fn colonies_of(&self, civ_id: u32) -> Vec<StarId> {
        self.systems
            .iter()
            .filter(|(_, s)| s.claimed_by == Some(civ_id) && s.colony.is_some())
            .map(|(id, _)| *id)
            .collect()
    }

    /// Ships owned by `civ_id`, ascending by ship id.
    pub fn ships_of(&self, civ_id: u32) -> Vec<ShipId> {
        self.ships
            .values()
            .filter(|s| s.owner == civ_id)
            .map(|s| s.id)
            .collect()
    }

    /// Systems this civilization has surveyed, ascending by id.
    pub fn surveyed_systems_of(&self, civ_id: u32) -> Vec<StarId> {
        self.systems
            .iter()
            .filter(|(_, s)| s.surveyed_by.contains(&civ_id))
            .map(|(id, _)| *id)
            .collect()
    }

    pub fn disputes(&self) -> &[Dispute] {
        &self.disputes
    }

    pub fn contacts(&self) -> &BTreeMap<(u32, u32), u64> {
        &self.contacts
    }

    // ------------------------------------------------------- S4 access

    pub fn treaties(&self) -> &[Treaty] {
        &self.treaties
    }

    pub fn embargoes(&self) -> &[Embargo] {
        &self.embargoes
    }

    pub fn trade_routes(&self) -> &[TradeRoute] {
        &self.trade_routes
    }

    pub fn breaches(&self) -> &[TreatyBreach] {
        &self.breaches
    }

    pub fn proposals(&self) -> &[Proposal] {
        &self.proposals
    }

    pub fn research_points_for(&self, civ_id: u32) -> f64 {
        self.civ(civ_id).map(|c| c.research_points).unwrap_or(0.0)
    }

    pub fn total_trade_income(&self) -> f64 {
        self.total_trade_income
    }

    /// The canonical sorted key for a civilization pair.
    pub(crate) fn pair_key(a: u32, b: u32) -> (u32, u32) {
        if a < b {
            (a, b)
        } else {
            (b, a)
        }
    }

    /// The treaty of `kind` active between the pair, if any.
    pub fn treaty_between(&self, a: u32, b: u32, kind: TreatyKind) -> Option<&Treaty> {
        let key = Self::pair_key(a, b);
        self.treaties
            .iter()
            .find(|t| t.parties == key && t.kind == kind)
    }

    pub fn treaty_active(&self, a: u32, b: u32, kind: TreatyKind) -> bool {
        self.treaty_between(a, b, kind).is_some()
    }

    /// All active treaties between the pair, in signing order.
    pub fn treaties_between(&self, a: u32, b: u32) -> Vec<&Treaty> {
        let key = Self::pair_key(a, b);
        self.treaties
            .iter()
            .filter(|t| t.parties == key)
            .collect()
    }

    /// The embargo `declarer` holds on `target`, if any.
    pub fn embargo_of(&self, declarer: u32, target: u32) -> Option<&Embargo> {
        self.embargoes
            .iter()
            .find(|e| e.declarer == declarer && e.target == target)
    }

    /// True when an embargo stands between the pair in either
    /// direction — trade is closed both ways while one stands.
    pub fn embargo_between(&self, a: u32, b: u32) -> bool {
        self.embargo_of(a, b).is_some() || self.embargo_of(b, a).is_some()
    }

    /// Routes running between the pair (either orientation).
    pub fn routes_between(&self, a: u32, b: u32) -> Vec<&TradeRoute> {
        let key = Self::pair_key(a, b);
        self.trade_routes
            .iter()
            .filter(|r| (r.civ_a, r.civ_b) == key)
            .collect()
    }

    pub fn trade_route(&self, route_id: u32) -> Option<&TradeRoute> {
        self.trade_routes.iter().find(|r| r.id == route_id)
    }

    /// Cumulative trade income `civ_id` has earned across its
    /// currently open routes (a severed route's ledger closes with
    /// it; the campaign-wide all-time total is
    /// `total_trade_income`).
    pub fn trade_income_of(&self, civ_id: u32) -> f64 {
        self.trade_routes
            .iter()
            .map(|r| {
                if r.civ_a == civ_id {
                    r.earned_a
                } else if r.civ_b == civ_id {
                    r.earned_b
                } else {
                    0.0
                }
            })
            .sum()
    }

    /// The day full diplomacy (§6.3's translation delay) opens
    /// between the pair: `None` before first contact.
    pub fn diplomacy_ready_day(&self, a: u32, b: u32) -> Option<u64> {
        self.contacted_day(a, b)
            .map(|day| day + TRANSLATION_DAYS)
    }

    /// True when the pair has met and the translation delay has run.
    pub fn diplomacy_open(&self, a: u32, b: u32) -> bool {
        self.diplomacy_ready_day(a, b)
            .map(|ready| self.day >= ready)
            .unwrap_or(false)
    }

    /// May `civ_id`'s ships refuel at `owner`'s colonies? Their own
    /// always; a treaty partner's under a gate-access treaty or an
    /// alliance (§5.3's treaty-gated access, port form).
    pub fn port_access(&self, civ_id: u32, owner: u32) -> bool {
        civ_id == owner
            || self.treaty_active(civ_id, owner, TreatyKind::GateAccess)
            || self.treaty_active(civ_id, owner, TreatyKind::Alliance)
    }

    /// This month's research output for a civilization if it were
    /// settled now: the sum over its Research-specialized colonies.
    /// Settlement accrues exactly this (times each colony's energy
    /// efficiency, which the stored colony already carries from the
    /// last settlement), and deal evaluation quotes it.
    pub fn research_output_for(&self, civ_id: u32) -> f64 {
        self.colonies_of(civ_id)
            .into_iter()
            .filter_map(|id| self.systems.get(&id).and_then(|s| s.colony.as_ref()))
            .filter(|c| c.specialization == Some(Specialization::Research))
            .map(|c| {
                (c.development as f64 * 1.5 + c.population_millions * 0.004)
                    * c.energy_efficiency
            })
            .sum()
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

    /// Systems the **player** has surveyed (S1 accessor semantics,
    /// per-civilization since S3; see `surveyed_count_for`).
    pub fn surveyed_count(&self) -> usize {
        self.surveyed_count_for(PLAYER_CIV)
    }

    pub fn surveyed_count_for(&self, civ_id: u32) -> usize {
        self.systems
            .values()
            .filter(|s| s.surveyed_by.contains(&civ_id))
            .count()
    }

    /// Colonies held by the **player** (see `colonized_count_for`
    /// and `total_colonized_count`).
    pub fn colonized_count(&self) -> usize {
        self.colonized_count_for(PLAYER_CIV)
    }

    pub fn colonized_count_for(&self, civ_id: u32) -> usize {
        self.colonies_of(civ_id).len()
    }

    /// Colonies held by all civilizations together — the §6.5
    /// hegemony denominator.
    /// Systems surveyed by at least one civilization.
    pub fn total_surveyed_count(&self) -> usize {
        self.systems
            .values()
            .filter(|s| !s.surveyed_by.is_empty())
            .count()
    }

    pub fn total_colonized_count(&self) -> usize {
        self.systems.values().filter(|s| s.colony.is_some()).count()
    }

    pub fn total_claimed_count(&self) -> usize {
        self.systems
            .values()
            .filter(|s| s.claimed_by.is_some())
            .count()
    }

    /// The **player's** total population (see `population_for`).
    pub fn total_population_millions(&self) -> f64 {
        self.population_for(PLAYER_CIV)
    }

    pub fn population_for(&self, civ_id: u32) -> f64 {
        self.colonies_of(civ_id)
            .into_iter()
            .filter_map(|id| self.systems.get(&id).and_then(|s| s.colony.as_ref()))
            .map(|c| c.population_millions)
            .sum()
    }

    /// The **player's** total fuel stock (see `fuel_stock_for`).
    pub fn total_fuel_stock(&self) -> f64 {
        self.fuel_stock_for(PLAYER_CIV)
    }

    pub fn fuel_stock_for(&self, civ_id: u32) -> f64 {
        self.colonies_of(civ_id)
            .into_iter()
            .filter_map(|id| self.systems.get(&id).and_then(|s| s.colony.as_ref()))
            .map(|c| c.fuel_stock)
            .sum()
    }

    /// Stars within `max_ly` of `from`, nearest first, ties broken
    /// by star id. Backed by the derived neighbor cache; the result
    /// is a pure function of the catalog.
    pub fn neighbors_within(
        &mut self,
        galaxy: &Galaxy,
        from: StarId,
        max_ly: f64,
    ) -> Vec<(f64, StarId)> {
        if galaxy.star(from).is_none() {
            return Vec::new();
        }
        if !self.neighbor_cache.contains_key(&from) {
            let origin = galaxy.star(from).expect("checked above").pos_ly;
            let near: Vec<(f64, StarId)> = galaxy
                .stars_within(origin, NEIGHBOR_CACHE_RANGE_LY)
                .into_iter()
                .filter(|(_, id)| *id != from)
                .collect();
            self.neighbor_cache.insert(from, near);
        }
        self.neighbor_cache
            .get(&from)
            .map(|entries| {
                entries
                    .iter()
                    .copied()
                    .filter(|(d, _)| *d <= max_ly + 1e-9)
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Record first contact between two civilizations (§6.3):
    /// idempotent, and the second and later meetings change nothing.
    pub(crate) fn note_contact(&mut self, a: u32, b: u32, system: Option<StarId>) {
        if a == b {
            return;
        }
        let key = if a < b { (a, b) } else { (b, a) };
        if self.contacts.contains_key(&key) {
            return;
        }
        self.contacts.insert(key, self.day);
        self.push_event(EventKind::FirstContact, system, None, Some(a), Some(b));
    }

    fn system_mut_or_default(&mut self, id: StarId) -> &mut SystemState {
        self.systems.entry(id).or_default()
    }

    fn push_event(
        &mut self,
        kind: EventKind,
        system: Option<StarId>,
        ship: Option<ShipId>,
        civ: Option<u32>,
        other_civ: Option<u32>,
    ) {
        let day = self.day;
        self.events.push(GameEvent {
            day,
            kind,
            system,
            ship,
            civ,
            other_civ,
        });
    }

    fn spawn_ship(&mut self, owner: u32, design_idx: u32, system: StarId) -> ShipId {
        let id = self.next_ship_id;
        self.next_ship_id += 1;
        let fuel = self.designs[design_idx as usize].tank_capacity;
        self.ships.insert(
            id,
            Ship {
                id,
                owner,
                design_idx,
                fuel,
                state: ShipState::AtSystem { system },
            },
        );
        id
    }

    /// Begin surveying the system a surveyor is already sitting in.
    /// (Player-civilization wrapper over `begin_survey_for`.)
    pub fn begin_survey(&mut self, galaxy: &Galaxy, ship_id: ShipId) -> SimResult<()> {
        self.begin_survey_for(PLAYER_CIV, galaxy, ship_id)
    }

    /// `begin_survey` for an acting civilization: the ship must be
    /// theirs, and "already surveyed" means surveyed *by them* —
    /// another civilization's survey is invisible to them (§6.1).
    pub fn begin_survey_for(
        &mut self,
        civ_id: u32,
        galaxy: &Galaxy,
        ship_id: ShipId,
    ) -> SimResult<()> {
        let ship = self
            .ships
            .get(&ship_id)
            .ok_or(SimError::UnknownShip(ship_id))?;
        if ship.owner != civ_id {
            return Err(SimError::ShipNotOwned(ship_id));
        }
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
        if self.surveyed_by(civ_id, system) {
            return Err(SimError::SystemAlreadySurveyed(system));
        }
        let days = survey_duration_days(self.seed, star);
        let ship = self.ships.get_mut(&ship_id).unwrap();
        ship.state = ShipState::Surveying {
            system,
            days_remaining: days,
        };
        self.push_event(
            EventKind::SurveyStarted,
            Some(system),
            Some(ship_id),
            Some(civ_id),
            None,
        );
        Ok(())
    }

    /// Dispatch a ship to another system. Normal orders are refused
    /// when the destination is beyond the design's range or beyond
    /// the fuel actually on board. (Player wrapper over
    /// `dispatch_ship_for`.)
    pub fn dispatch_ship(
        &mut self,
        galaxy: &Galaxy,
        ship_id: ShipId,
        destination: StarId,
        purpose: Purpose,
    ) -> SimResult<()> {
        self.dispatch_inner(PLAYER_CIV, galaxy, ship_id, destination, purpose, false)
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
        self.dispatch_inner(PLAYER_CIV, galaxy, ship_id, destination, purpose, true)
    }

    /// `dispatch_ship` for an acting civilization: the ship must be
    /// theirs, and purpose preconditions (surveyed, claimed) are
    /// judged against *their* knowledge and claims.
    pub fn dispatch_ship_for(
        &mut self,
        civ_id: u32,
        galaxy: &Galaxy,
        ship_id: ShipId,
        destination: StarId,
        purpose: Purpose,
    ) -> SimResult<()> {
        self.dispatch_inner(civ_id, galaxy, ship_id, destination, purpose, false)
    }

    fn dispatch_inner(
        &mut self,
        civ_id: u32,
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
            if ship.owner != civ_id {
                return Err(SimError::ShipNotOwned(ship_id));
            }
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
                Purpose::Survey => self.begin_survey_for(civ_id, galaxy, ship_id),
                Purpose::Colonize => self.found_colony_with_ship_for(civ_id, ship_id).map(|_| ()),
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
                if self.surveyed_by(civ_id, destination) {
                    return Err(SimError::SystemAlreadySurveyed(destination));
                }
            }
            Purpose::Colonize => self.require_colonizable_for(civ_id, destination)?,
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
        self.push_event(
            EventKind::ShipDispatched,
            Some(destination),
            Some(ship_id),
            Some(civ_id),
            None,
        );
        Ok(())
    }

    /// May `civ_id` found a colony at `system` right now? Judged
    /// against that civilization's own survey knowledge and claim
    /// (design §3's pipeline, per civilization since S3).
    fn require_colonizable_for(&self, civ_id: u32, system: StarId) -> SimResult<()> {
        if !self.surveyed_by(civ_id, system) {
            return Err(SimError::SystemNotSurveyed(system));
        }
        let state = self.systems.get(&system);
        if state.and_then(|s| s.claimed_by) != Some(civ_id) {
            return Err(SimError::SystemNotClaimed(system));
        }
        if state.map(|s| s.colony.is_some()).unwrap_or(false) {
            return Err(SimError::SystemAlreadyColonized(system));
        }
        Ok(())
    }

    /// Claim a surveyed system. Claims precede founding (design §3).
    /// (Player wrapper over `claim_system_for`.)
    pub fn claim_system(&mut self, system: StarId) -> SimResult<()> {
        self.claim_system_for(PLAYER_CIV, system)
    }

    /// `claim_system` for an acting civilization: the system must be
    /// surveyed *by them* and unclaimed. A system claimed by another
    /// civilization cannot be taken by claiming — contesting it is
    /// the diplomatic act (`contest_claim_for`), and taking it is
    /// war (S5).
    pub fn claim_system_for(&mut self, civ_id: u32, system: StarId) -> SimResult<()> {
        if !self.surveyed_by(civ_id, system) {
            return Err(SimError::SystemNotSurveyed(system));
        }
        let state = self
            .systems
            .get(&system)
            .ok_or(SimError::SystemNotSurveyed(system))?;
        if state.claimed_by.is_some() {
            return Err(SimError::SystemAlreadyClaimed(system));
        }
        let credits = self.credits_for(civ_id);
        if credits + 1e-9 < CLAIM_COST_CREDITS {
            return Err(SimError::InsufficientCredits {
                needed: CLAIM_COST_CREDITS,
                available: credits,
            });
        }
        if let Some(civ) = self.civs.get_mut(civ_id as usize) {
            civ.credits -= CLAIM_COST_CREDITS;
        }
        self.system_mut_or_default(system).claimed_by = Some(civ_id);
        self.push_event(
            EventKind::SystemClaimed,
            Some(system),
            None,
            Some(civ_id),
            None,
        );
        Ok(())
    }

    /// Contest another civilization's claim (player wrapper over
    /// `contest_claim_for`).
    pub fn contest_claim(&mut self, system: StarId) -> SimResult<()> {
        self.contest_claim_for(PLAYER_CIV, system)
    }

    /// Lodge a competing claim against the civilization holding
    /// `system` (design §6.3): the system must be surveyed by the
    /// acting civilization and claimed by a different one. Opens a
    /// dispute — a record with opinion effects — and establishes
    /// contact if the two have somehow not met.
    pub fn contest_claim_for(&mut self, civ_id: u32, system: StarId) -> SimResult<()> {
        if !self.surveyed_by(civ_id, system) {
            return Err(SimError::SystemNotSurveyed(system));
        }
        let holder = self
            .systems
            .get(&system)
            .and_then(|s| s.claimed_by)
            .filter(|&h| h != civ_id)
            .ok_or(SimError::NoForeignClaim(system))?;
        // S4: a non-aggression pact or an alliance is a promise not
        // to do exactly this. The promise binds even when the claim
        // is coveted — that is what makes it a promise.
        if self.treaty_active(civ_id, holder, TreatyKind::NonAggressionPact)
            || self.treaty_active(civ_id, holder, TreatyKind::Alliance)
        {
            return Err(SimError::ContestBarredByTreaty);
        }
        if self
            .disputes
            .iter()
            .any(|d| d.system == system && d.challenger == civ_id)
        {
            return Err(SimError::DisputeAlreadyOpen(system));
        }
        self.disputes.push(Dispute {
            system,
            holder,
            challenger: civ_id,
            opened_day: self.day,
        });
        self.note_contact(civ_id, holder, Some(system));
        self.push_event(
            EventKind::ClaimContested,
            Some(system),
            None,
            Some(civ_id),
            Some(holder),
        );
        Ok(())
    }

    /// Found a colony using a colony ship that is already in the
    /// target system. The ship is consumed (design §3).
    /// (Player wrapper over `found_colony_with_ship_for`.)
    pub fn found_colony_with_ship(&mut self, ship_id: ShipId) -> SimResult<StarId> {
        self.found_colony_with_ship_for(PLAYER_CIV, ship_id)
    }

    /// `found_colony_with_ship` for the ship's owning civilization.
    pub fn found_colony_with_ship_for(
        &mut self,
        civ_id: u32,
        ship_id: ShipId,
    ) -> SimResult<StarId> {
        let ship = self
            .ships
            .get(&ship_id)
            .ok_or(SimError::UnknownShip(ship_id))?;
        if ship.owner != civ_id {
            return Err(SimError::ShipNotOwned(ship_id));
        }
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
        self.require_colonizable_for(civ_id, system)?;
        let remaining_fuel = ship.fuel;
        self.found_colony(civ_id, system, remaining_fuel);
        self.ships.remove(&ship_id);
        self.push_event(
            EventKind::ColonyFounded,
            Some(system),
            Some(ship_id),
            Some(civ_id),
            None,
        );
        Ok(system)
    }

    fn found_colony(&mut self, civ_id: u32, system: StarId, remaining_ship_fuel: f64) {
        let day = self.day;
        let state = self.system_mut_or_default(system);
        state.claimed_by = Some(civ_id);
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
    /// (Player wrapper over `build_ship_for`.)
    pub fn build_ship(&mut self, system: StarId, design_idx: u32) -> SimResult<u32> {
        self.build_ship_for(PLAYER_CIV, system, design_idx)
    }

    /// `build_ship` for an acting civilization: the colony must be
    /// theirs — its alloys are spent and the acting civilization's
    /// treasury pays.
    pub fn build_ship_for(
        &mut self,
        civ_id: u32,
        system: StarId,
        design_idx: u32,
    ) -> SimResult<u32> {
        let design = self
            .design(design_idx)
            .ok_or(SimError::UnknownDesign(design_idx))?
            .clone();
        let credits_cost = design.credits_cost();
        let alloys_cost = design.alloys_cost();
        let owner = self
            .systems
            .get(&system)
            .and_then(|s| s.claimed_by);
        match self.systems.get(&system).and_then(|s| s.colony.as_ref()) {
            None => return Err(SimError::NoColony(system)),
            Some(_) if owner != Some(civ_id) => {
                return Err(SimError::NotYourColony(system));
            }
            Some(_) => {}
        }
        let credits = self.credits_for(civ_id);
        if credits + 1e-9 < credits_cost {
            return Err(SimError::InsufficientCredits {
                needed: credits_cost,
                available: credits,
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
        if let Some(civ) = self.civs.get_mut(civ_id as usize) {
            civ.credits -= credits_cost;
        }
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
    /// (Player wrapper over `refuel_ship_for`.)
    pub fn refuel_ship(&mut self, ship_id: ShipId) -> SimResult<f64> {
        self.refuel_ship_for(PLAYER_CIV, ship_id)
    }

    /// `refuel_ship` for the ship's owning civilization: fuel comes
    /// from a colony of *their own* — or, since S4, from a treaty
    /// partner's colony under a gate-access treaty or an alliance
    /// (`port_access`): drawing on another civilization's stocks is
    /// treaty business, and the treaty is the permission.
    pub fn refuel_ship_for(&mut self, civ_id: u32, ship_id: ShipId) -> SimResult<f64> {
        let (system, design_idx, current_fuel, pending) = {
            let ship = self
                .ships
                .get(&ship_id)
                .ok_or(SimError::UnknownShip(ship_id))?;
            if ship.owner != civ_id {
                return Err(SimError::ShipNotOwned(ship_id));
            }
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
        let colony_owner = self.systems.get(&system).and_then(|s| s.claimed_by);
        if colony_owner != Some(civ_id)
            && self
                .systems
                .get(&system)
                .map(|s| s.colony.is_some())
                .unwrap_or(false)
        {
            match colony_owner {
                Some(owner) if self.port_access(civ_id, owner) => {}
                _ => return Err(SimError::NotYourColony(system)),
            }
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
        self.push_event(
            EventKind::ShipRefuelled,
            Some(system),
            Some(ship_id),
            Some(civ_id),
            None,
        );

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
                    self.found_colony_with_ship_for(civ_id, ship_id)?;
                }
                Purpose::Relocate => {}
            }
        }
        Ok(amount)
    }

    /// (Player wrapper over `assign_specialization_for`.)
    pub fn assign_specialization(
        &mut self,
        system: StarId,
        specialization: Specialization,
    ) -> SimResult<()> {
        self.assign_specialization_for(PLAYER_CIV, system, specialization)
    }

    pub fn assign_specialization_for(
        &mut self,
        civ_id: u32,
        system: StarId,
        specialization: Specialization,
    ) -> SimResult<()> {
        match self.systems.get(&system) {
            None => return Err(SimError::NoColony(system)),
            Some(state) => {
                if state.colony.is_none() {
                    return Err(SimError::NoColony(system));
                }
                if state.claimed_by != Some(civ_id) {
                    return Err(SimError::NotYourColony(system));
                }
            }
        }
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
        self.push_event(
            EventKind::SpecializationSet,
            Some(system),
            None,
            Some(civ_id),
            None,
        );
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
            let research_outputs = self.monthly_settlement();
            // S4: trade routes pay out, research pacts pay their
            // bonus, stale routes close, and unanswered proposals
            // lapse — all on the same settlement boundary, so
            // catch-up equivalence (§11.1) covers diplomacy too.
            self.monthly_diplomacy_settlement(galaxy, &research_outputs);
            // AI civilizations re-plan on the settlement boundary
            // (design §2: AI civs re-plan; §6.5), *after* the same
            // settlement the player experiences, so monthly chunking
            // is identical to daily stepping for every actor.
            let ai_civs: Vec<u32> = self
                .civs
                .iter()
                .filter(|c| c.is_ai())
                .map(|c| c.id)
                .collect();
            for civ_id in ai_civs {
                crate::ai::plan_month(self, galaxy, civ_id);
            }
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
            let (system, owner) = match self.ships.get(&ship_id) {
                Some(s) => (s.state.current_system(), Some(s.owner)),
                None => (None, None),
            };
            self.push_event(
                EventKind::ShipStranded,
                system,
                Some(ship_id),
                owner,
                None,
            );
        }
        for (ship_id, system, purpose) in arrivals {
            // Arriving where another civilization holds a claim is
            // first contact (design §6.1) — for both sides at once.
            if let Some(owner) = self.ships.get(&ship_id).map(|s| s.owner) {
                if let Some(present) = self
                    .systems
                    .get(&system)
                    .and_then(|s| s.claimed_by)
                {
                    if present != owner {
                        self.note_contact(owner, present, Some(system));
                    }
                }
            }
            let arrival_owner = self.ships.get(&ship_id).map(|s| s.owner);
            self.push_event(
                EventKind::ShipArrived,
                Some(system),
                Some(ship_id),
                arrival_owner,
                None,
            );
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
                        if let Some(owner) = self.ships.get(&ship_id).map(|s| s.owner) {
                            let _ = self.begin_survey_for(owner, galaxy, ship_id);
                        }
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
                        if let Some(owner) = self.ships.get(&ship_id).map(|s| s.owner) {
                            let _ = self.found_colony_with_ship_for(owner, ship_id);
                        }
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
            let owner = self.ships.get(&ship_id).map(|s| s.owner);
            if let Some(star) = galaxy.star(system) {
                let profile = profile_for_star(self.seed, star);
                let state = self.system_mut_or_default(system);
                state.survey = SurveyState::Surveyed;
                state.profile = Some(profile);
                if let Some(owner) = owner {
                    state.surveyed_by.insert(owner);
                }
            }
            if let Some(ship) = self.ships.get_mut(&ship_id) {
                ship.state = ShipState::AtSystem { system };
            }
            // Surveying a system another civilization holds is first
            // contact (design §6.1) — the surveyor learns someone is
            // here, and the holder learns of the surveyor.
            if let Some(owner) = owner {
                if let Some(holder) = self
                    .systems
                    .get(&system)
                    .and_then(|s| s.claimed_by)
                {
                    if holder != owner {
                        self.note_contact(owner, holder, Some(system));
                    }
                }
            }
            self.push_event(
                EventKind::SurveyCompleted,
                Some(system),
                Some(ship_id),
                owner,
                None,
            );
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
            let owner = self
                .systems
                .get(&system)
                .and_then(|s| s.claimed_by)
                .unwrap_or(PLAYER_CIV);
            let ship_id = self.spawn_ship(owner, design_idx, system);
            self.push_event(
                EventKind::ShipBuilt,
                Some(system),
                Some(ship_id),
                Some(owner),
                None,
            );
        }
    }

    /// Settle one month of colony economy. Returns each
    /// civilization's research output for the month (S4) so the
    /// diplomacy settlement can pay research-pact bonuses from the
    /// same numbers that were just accrued.
    fn monthly_settlement(&mut self) -> BTreeMap<u32, f64> {
        let system_ids: Vec<StarId> = self.systems.keys().copied().collect();
        let mut abandoned: Vec<(StarId, u32)> = Vec::new();
        // Each colony's income lands in its *owner's* treasury
        // (design §6.5: same economy rules for every civilization).
        let mut credits_delta: BTreeMap<u32, f64> = BTreeMap::new();
        let mut research_delta: BTreeMap<u32, f64> = BTreeMap::new();

        for system in system_ids {
            let Some(state) = self.systems.get_mut(&system) else {
                continue;
            };
            let owner = state.claimed_by.unwrap_or(PLAYER_CIV);
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
            *credits_delta.entry(owner).or_insert(0.0) += income - upkeep;

            // Research (S4): Research-specialized colonies produce
            // research points. The formula is the one
            // `research_output_for` quotes between settlements.
            if spec == Some(Specialization::Research) {
                *research_delta.entry(owner).or_insert(0.0) +=
                    (dev * 1.5 + colony.population_millions * 0.004) * efficiency;
            }

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
                abandoned.push((system, owner));
            }
        }

        for (owner, delta) in credits_delta {
            if let Some(civ) = self.civs.get_mut(owner as usize) {
                civ.credits += delta;
            }
        }
        for (owner, delta) in &research_delta {
            if let Some(civ) = self.civs.get_mut(*owner as usize) {
                civ.research_points += delta;
            }
        }
        for (system, owner) in abandoned {
            if let Some(state) = self.systems.get_mut(&system) {
                state.colony = None;
            }
            self.push_event(
                EventKind::ColonyAbandoned,
                Some(system),
                None,
                Some(owner),
                None,
            );
        }
        research_delta
    }

    // ------------------------------------------------------------ S4
    // Trade & diplomacy depth (design §4.3, §6.3). Every command is
    // parameterized by the acting civilization, exactly like the
    // S3 command surface; the player wrappers sit next to the S1
    // ones above in spirit and are spelled out where the bridge
    // needs them.

    fn require_civ(&self, civ_id: u32) -> SimResult<()> {
        if self.civ(civ_id).is_none() {
            return Err(SimError::UnknownCivilization(civ_id));
        }
        Ok(())
    }

    /// The shared gate for every negotiated instrument: both
    /// civilizations exist, they are distinct, they have met, and
    /// the §6.3 translation delay has run.
    fn require_diplomacy(&self, a: u32, b: u32) -> SimResult<()> {
        self.require_civ(a)?;
        self.require_civ(b)?;
        if a == b {
            return Err(SimError::UnknownCivilization(a));
        }
        if !self.has_contact(a, b) {
            return Err(SimError::NoContact(b));
        }
        if let Some(ready_day) = self.diplomacy_ready_day(a, b) {
            if self.day < ready_day {
                return Err(SimError::DiplomacyNotReady { ready_day });
            }
        }
        Ok(())
    }

    /// Record a signed treaty and its event. Callers have already
    /// validated and (for AI counterparties) evaluated.
    fn sign_treaty(&mut self, proposer: u32, other: u32, kind: TreatyKind) {
        let parties = Self::pair_key(proposer, other);
        self.treaties.push(Treaty {
            kind,
            parties,
            signed_day: self.day,
        });
        self.push_event(
            EventKind::TreatySigned,
            None,
            None,
            Some(proposer),
            Some(other),
        );
    }

    /// Close every trade route between the pair (the agreement
    /// that sustained them is gone). Each closure is an event.
    fn sever_routes_between(&mut self, a: u32, b: u32) {
        let key = Self::pair_key(a, b);
        let doomed: Vec<u32> = self
            .trade_routes
            .iter()
            .filter(|r| (r.civ_a, r.civ_b) == key)
            .map(|r| r.id)
            .collect();
        for route_id in doomed {
            self.close_route(route_id);
        }
    }

    /// Remove a route from the state, recording its closure.
    fn close_route(&mut self, route_id: u32) {
        if let Some(pos) = self.trade_routes.iter().position(|r| r.id == route_id) {
            let route = self.trade_routes.remove(pos);
            self.push_event(
                EventKind::TradeRouteSevered,
                Some(route.system_a),
                None,
                Some(route.civ_a),
                Some(route.civ_b),
            );
        }
    }

    /// Propose a treaty to another civilization (player wrapper
    /// over `propose_treaty_for`).
    pub fn propose_treaty(
        &mut self,
        galaxy: &Galaxy,
        other: u32,
        kind: TreatyKind,
    ) -> SimResult<DealOutcome> {
        self.propose_treaty_for(PLAYER_CIV, galaxy, other, kind)
    }

    /// Propose a treaty (design §6.3). When the counterparty is an
    /// AI civilization it answers on the spot, from the stated-
    /// reasons evaluation in `diplomacy.rs`. When the counterparty
    /// is the player (only the AI planner proposes this way), the
    /// offer lands in the player's proposal inbox with the
    /// proposer's stated reasons attached.
    pub fn propose_treaty_for(
        &mut self,
        proposer: u32,
        galaxy: &Galaxy,
        other: u32,
        kind: TreatyKind,
    ) -> SimResult<DealOutcome> {
        self.require_diplomacy(proposer, other)?;
        if self.treaty_active(proposer, other, kind) {
            return Err(SimError::TreatyAlreadyActive);
        }
        if other == PLAYER_CIV {
            // The proposer's own stated reasons for wanting this.
            let evaluation = self.evaluate_treaty(galaxy, proposer, other, kind);
            return self.file_proposal(
                proposer,
                ProposalKind::Treaty(kind),
                evaluation.reasons,
            );
        }
        let evaluation = self.evaluate_treaty(galaxy, other, proposer, kind);
        if evaluation.accept {
            self.sign_treaty(proposer, other, kind);
            Ok(DealOutcome::Signed)
        } else {
            self.push_event(
                EventKind::DealRefused,
                None,
                None,
                Some(proposer),
                Some(other),
            );
            Ok(DealOutcome::Refused {
                reasons: evaluation.reasons,
            })
        }
    }

    /// Propose a peace settlement on stated terms (player wrapper
    /// over `propose_peace_for`).
    pub fn propose_peace(
        &mut self,
        galaxy: &Galaxy,
        other: u32,
        terms: PeaceTerms,
    ) -> SimResult<DealOutcome> {
        self.propose_peace_for(PLAYER_CIV, galaxy, other, terms)
    }

    /// Propose a peace settlement (design §6.3): acceptance closes
    /// every open dispute between the pair, transfers the ceded
    /// claims, moves the credits, and lifts any embargo between
    /// them. AI counterparties evaluate the terms with stated
    /// reasons; offers to the player go to the inbox.
    pub fn propose_peace_for(
        &mut self,
        proposer: u32,
        galaxy: &Galaxy,
        other: u32,
        terms: PeaceTerms,
    ) -> SimResult<DealOutcome> {
        self.require_diplomacy(proposer, other)?;
        self.validate_peace_terms(proposer, other, &terms)?;
        if other == PLAYER_CIV {
            let evaluation = self.evaluate_peace(galaxy, proposer, other, &terms);
            return self.file_proposal(proposer, ProposalKind::Peace(terms), evaluation.reasons);
        }
        let evaluation = self.evaluate_peace(galaxy, other, proposer, &terms);
        if evaluation.accept {
            self.apply_peace(proposer, other, &terms);
            Ok(DealOutcome::Signed)
        } else {
            self.push_event(
                EventKind::DealRefused,
                None,
                None,
                Some(proposer),
                Some(other),
            );
            Ok(DealOutcome::Refused {
                reasons: evaluation.reasons,
            })
        }
    }

    /// Terms must be *executable*: ceded systems are actually
    /// claimed by the ceding party, and whoever pays can pay.
    fn validate_peace_terms(
        &self,
        proposer: u32,
        other: u32,
        terms: &PeaceTerms,
    ) -> SimResult<()> {
        for &system in &terms.cede_to_proposer {
            if self.systems.get(&system).and_then(|s| s.claimed_by) != Some(other) {
                return Err(SimError::SystemNotClaimed(system));
            }
        }
        for &system in &terms.cede_to_other {
            if self.systems.get(&system).and_then(|s| s.claimed_by) != Some(proposer) {
                return Err(SimError::SystemNotClaimed(system));
            }
        }
        let (payer, amount) = if terms.credits_from_proposer >= 0.0 {
            (proposer, terms.credits_from_proposer)
        } else {
            (other, -terms.credits_from_proposer)
        };
        let available = self.credits_for(payer);
        if amount > 0.0 && available + 1e-9 < amount {
            return Err(SimError::InsufficientCredits {
                needed: amount,
                available,
            });
        }
        Ok(())
    }

    /// Execute an accepted settlement.
    fn apply_peace(&mut self, proposer: u32, other: u32, terms: &PeaceTerms) {
        let transfers: Vec<(StarId, u32)> = terms
            .cede_to_proposer
            .iter()
            .map(|&s| (s, proposer))
            .chain(terms.cede_to_other.iter().map(|&s| (s, other)))
            .collect();
        for (system, new_owner) in transfers {
            if let Some(state) = self.systems.get_mut(&system) {
                state.claimed_by = Some(new_owner);
                // Receiving a system in a treaty tells you where it
                // is and what it holds — the treaty itself is the
                // information transfer.
                state.surveyed_by.insert(new_owner);
            }
            // A dispute over a ceded system is settled by the
            // cession itself, whichever direction it pointed.
            self.disputes.retain(|d| d.system != system);
        }
        if terms.credits_from_proposer != 0.0 {
            let amount = terms.credits_from_proposer;
            if let Some(civ) = self.civs.get_mut(proposer as usize) {
                civ.credits -= amount;
            }
            if let Some(civ) = self.civs.get_mut(other as usize) {
                civ.credits += amount;
            }
        }
        // Every remaining dispute between the pair is settled by
        // the recognition itself, and a settlement lifts embargoes:
        // trade war ends when peace is signed.
        self.disputes
            .retain(|d| !((d.holder == proposer && d.challenger == other)
                || (d.holder == other && d.challenger == proposer)));
        self.embargoes
            .retain(|e| !((e.declarer == proposer && e.target == other)
                || (e.declarer == other && e.target == proposer)));
        self.push_event(
            EventKind::PeaceSettled,
            None,
            None,
            Some(proposer),
            Some(other),
        );
    }

    /// Store an offer to the player, honouring the refusal/lapse
    /// cooldown and the one-pending-offer-per-instrument rule.
    fn file_proposal(
        &mut self,
        proposer: u32,
        kind: ProposalKind,
        reasons: Vec<String>,
    ) -> SimResult<DealOutcome> {
        let key = Self::pair_key(proposer, PLAYER_CIV);
        if self
            .proposals
            .iter()
            .any(|p| p.from == proposer && p.to == PLAYER_CIV && p.kind == kind)
        {
            return Ok(DealOutcome::Refused {
                reasons: vec![
                    "an identical offer is already awaiting the player's answer".to_string(),
                ],
            });
        }
        let cooldown_key = (key.0, key.1, kind.cooldown_code());
        if let Some(&ready_day) = self.proposal_cooldowns.get(&cooldown_key) {
            if self.day < ready_day {
                return Ok(DealOutcome::Refused {
                    reasons: vec![format!(
                        "too soon after a refused or lapsed offer — {} will not re-offer this before day {}",
                        self.civ(proposer).map(|c| c.name.clone()).unwrap_or_default(),
                        ready_day
                    )],
                });
            }
        }
        let id = self.next_proposal_id;
        self.next_proposal_id += 1;
        self.proposals.push(Proposal {
            id,
            from: proposer,
            to: PLAYER_CIV,
            kind,
            proposed_day: self.day,
            reasons,
        });
        self.push_event(
            EventKind::TreatyProposed,
            None,
            None,
            Some(proposer),
            Some(PLAYER_CIV),
        );
        Ok(DealOutcome::Pending { proposal_id: id })
    }

    /// Answer a proposal addressed to `civ_id` (the player, in
    /// practice). Acceptance re-validates the deal against today's
    /// state — the galaxy may have moved since the offer was made —
    /// and refusal starts the proposer's cooldown.
    pub fn respond_to_proposal(
        &mut self,
        galaxy: &Galaxy,
        civ_id: u32,
        proposal_id: u32,
        accept: bool,
    ) -> SimResult<DealOutcome> {
        let proposal = self
            .proposals
            .iter()
            .find(|p| p.id == proposal_id)
            .cloned()
            .ok_or(SimError::UnknownProposal(proposal_id))?;
        if proposal.to != civ_id {
            return Err(SimError::NotProposalRecipient(proposal_id));
        }
        if !accept {
            self.proposals.retain(|p| p.id != proposal_id);
            let key = Self::pair_key(proposal.from, civ_id);
            self.proposal_cooldowns.insert(
                (key.0, key.1, proposal.kind.cooldown_code()),
                self.day + PROPOSAL_COOLDOWN_DAYS,
            );
            return Ok(DealOutcome::Declined);
        }
        match &proposal.kind {
            ProposalKind::Treaty(kind) => {
                let kind = *kind;
                self.require_diplomacy(proposal.from, civ_id)?;
                if self.treaty_active(proposal.from, civ_id, kind) {
                    return Err(SimError::TreatyAlreadyActive);
                }
                self.proposals.retain(|p| p.id != proposal_id);
                self.sign_treaty(proposal.from, civ_id, kind);
                let _ = galaxy;
                Ok(DealOutcome::Signed)
            }
            ProposalKind::Peace(terms) => {
                let terms = terms.clone();
                self.require_diplomacy(proposal.from, civ_id)?;
                self.validate_peace_terms(proposal.from, civ_id, &terms)?;
                self.proposals.retain(|p| p.id != proposal_id);
                self.apply_peace(proposal.from, civ_id, &terms);
                Ok(DealOutcome::Signed)
            }
        }
    }

    /// Break an active treaty (player wrapper over
    /// `break_treaty_for`).
    pub fn break_treaty(&mut self, other: u32, kind: TreatyKind) -> SimResult<()> {
        self.break_treaty_for(PLAYER_CIV, other, kind)
    }

    /// Break a treaty: the instrument ends today, its trade routes
    /// close with it, and the breach is remembered against the
    /// breaker (§6.2). There is no quiet way to break a promise.
    pub fn break_treaty_for(
        &mut self,
        actor: u32,
        other: u32,
        kind: TreatyKind,
    ) -> SimResult<()> {
        self.require_civ(actor)?;
        self.require_civ(other)?;
        let key = Self::pair_key(actor, other);
        let Some(pos) = self
            .treaties
            .iter()
            .position(|t| t.parties == key && t.kind == kind)
        else {
            return Err(SimError::TreatyNotActive);
        };
        self.treaties.remove(pos);
        self.breaches.push(TreatyBreach {
            breaker: actor,
            other,
            kind,
            day: self.day,
        });
        if kind == TreatyKind::TradeAgreement {
            self.sever_routes_between(actor, other);
        }
        self.push_event(
            EventKind::TreatyBroken,
            None,
            None,
            Some(actor),
            Some(other),
        );
        Ok(())
    }

    /// Declare an embargo (player wrapper over
    /// `declare_embargo_for`).
    pub fn declare_embargo(&mut self, target: u32) -> SimResult<()> {
        self.declare_embargo_for(PLAYER_CIV, target)
    }

    /// Declare an embargo: trade with the target closes today.
    /// Declaring one against a trade partner terminates the trade
    /// agreement on the spot — and terminating an agreement by
    /// embargo is a breach, recorded like any other.
    pub fn declare_embargo_for(&mut self, declarer: u32, target: u32) -> SimResult<()> {
        self.require_civ(declarer)?;
        self.require_civ(target)?;
        if declarer == target {
            return Err(SimError::UnknownCivilization(target));
        }
        if !self.has_contact(declarer, target) {
            return Err(SimError::NoContact(target));
        }
        if self.embargo_of(declarer, target).is_some() {
            return Err(SimError::EmbargoAlreadyDeclared);
        }
        if self.treaty_active(declarer, target, TreatyKind::TradeAgreement) {
            let key = Self::pair_key(declarer, target);
            self.treaties
                .retain(|t| !(t.parties == key && t.kind == TreatyKind::TradeAgreement));
            self.breaches.push(TreatyBreach {
                breaker: declarer,
                other: target,
                kind: TreatyKind::TradeAgreement,
                day: self.day,
            });
            self.sever_routes_between(declarer, target);
            self.push_event(
                EventKind::TreatyBroken,
                None,
                None,
                Some(declarer),
                Some(target),
            );
        }
        self.embargoes.push(Embargo {
            declarer,
            target,
            since_day: self.day,
        });
        self.push_event(
            EventKind::EmbargoDeclared,
            None,
            None,
            Some(declarer),
            Some(target),
        );
        Ok(())
    }

    /// Lift an embargo (player wrapper over `lift_embargo_for`).
    pub fn lift_embargo(&mut self, target: u32) -> SimResult<()> {
        self.lift_embargo_for(PLAYER_CIV, target)
    }

    pub fn lift_embargo_for(&mut self, declarer: u32, target: u32) -> SimResult<()> {
        self.require_civ(declarer)?;
        self.require_civ(target)?;
        let Some(pos) = self
            .embargoes
            .iter()
            .position(|e| e.declarer == declarer && e.target == target)
        else {
            return Err(SimError::NoEmbargoInForce);
        };
        self.embargoes.remove(pos);
        self.push_event(
            EventKind::EmbargoLifted,
            None,
            None,
            Some(declarer),
            Some(target),
        );
        Ok(())
    }

    /// The colony-to-colony path a trade route would travel
    /// between two endpoint colonies: a chain over *both* parties'
    /// colonies (the agreement makes their networks one graph for
    /// this purpose), each leg within tanker range (`TRADE_LEG_LY`),
    /// fewest legs first, nearest first on ties. Returns the path
    /// and its total length. This is §4.3's route solver in its S4
    /// form: the nodes are colonies, the legs are free flight, and
    /// gate hops join it when gates exist (S5).
    pub fn trade_path(
        &self,
        galaxy: &Galaxy,
        a: u32,
        b: u32,
        from: StarId,
        to: StarId,
    ) -> Option<(Vec<StarId>, f64)> {
        if from == to {
            return None;
        }
        let mut nodes: Vec<StarId> = self.colonies_of(a);
        for system in self.colonies_of(b) {
            if !nodes.contains(&system) {
                nodes.push(system);
            }
        }
        if !nodes.contains(&from) || !nodes.contains(&to) {
            return None;
        }
        // Adjacency, computed once: for each node the neighbours
        // within tanker range, in `nodes` order — the exact edge
        // set and relaxation order the naive scan would use, so
        // the chosen path is unchanged. (The naive form re-scanned
        // every pair at every settle step; with ~100 colonies a
        // side that made route searches minutes-slow on the real
        // table — found by the S4 long run stalling at first
        // contact.)
        let mut adjacency: BTreeMap<StarId, Vec<(StarId, f64)>> = BTreeMap::new();
        for &node in &nodes {
            let mut edges = Vec::new();
            for &next in &nodes {
                if next == node {
                    continue;
                }
                if let Some(leg) = galaxy.distance_ly(node, next) {
                    if leg <= TRADE_LEG_LY + 1e-9 {
                        edges.push((next, leg));
                    }
                }
            }
            adjacency.insert(node, edges);
        }
        // Dijkstra over the colony graph. Colony counts are small;
        // the (distance, system) ordering keeps the chosen path a
        // pure function of the state.
        let mut dist: BTreeMap<StarId, f64> = BTreeMap::new();
        let mut prev: BTreeMap<StarId, StarId> = BTreeMap::new();
        let mut settled: BTreeSet<StarId> = BTreeSet::new();
        dist.insert(from, 0.0);
        loop {
            let mut best: Option<(f64, StarId)> = None;
            for &node in &nodes {
                if settled.contains(&node) {
                    continue;
                }
                if let Some(&d) = dist.get(&node) {
                    if best.map(|(bd, bid)| d < bd || (d == bd && node < bid)).unwrap_or(true) {
                        best = Some((d, node));
                    }
                }
            }
            let Some((cost, node)) = best else {
                break;
            };
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
            settled.insert(node);
            for &(next, leg) in &adjacency[&node] {
                if settled.contains(&next) {
                    continue;
                }
                let next_cost = cost + leg;
                if next_cost < *dist.get(&next).unwrap_or(&f64::INFINITY) {
                    dist.insert(next, next_cost);
                    prev.insert(next, node);
                }
            }
        }
        None
    }

    /// The throughput a route between two endpoint colonies would
    /// carry today (§4.3): a function of both endpoints'
    /// development and population, with the alliance integration
    /// bonus when the pair are allies. Zero when either endpoint
    /// is not currently a colony of the right owner.
    pub fn route_throughput(&self, a: u32, b: u32, system_a: StarId, system_b: StarId) -> f64 {
        let endpoint = |owner: u32, system: StarId| -> Option<(f64, f64)> {
            let state = self.systems.get(&system)?;
            if state.claimed_by != Some(owner) {
                return None;
            }
            let colony = state.colony.as_ref()?;
            Some((colony.development as f64, colony.population_millions))
        };
        let Some((dev_a, pop_a)) = endpoint(a, system_a) else {
            return 0.0;
        };
        let Some((dev_b, pop_b)) = endpoint(b, system_b) else {
            return 0.0;
        };
        let base = 4.0 * (dev_a + dev_b) + 0.02 * (pop_a + pop_b);
        if self.treaty_active(a, b, TreatyKind::Alliance) {
            base * 1.25
        } else {
            base
        }
    }

    /// A live route's current throughput, from its endpoints.
    pub fn live_route_throughput(&self, route: &TradeRoute) -> f64 {
        self.route_throughput(route.civ_a, route.civ_b, route.system_a, route.system_b)
    }

    /// A route's distance factor (§4.3: income is proportional to
    /// throughput × distance factor — goods that travel farther
    /// are worth more at the far end).
    pub fn route_distance_factor(route: &TradeRoute) -> f64 {
        1.0 + route.path_ly / 1000.0
    }

    /// The monthly income one side of a live route earns at its
    /// current throughput: the exact figure the settlement pays
    /// and the ledger records. Both sides earn the same (§4.3:
    /// "both sides earn credits monthly").
    pub fn route_monthly_income(&self, route: &TradeRoute) -> f64 {
        self.live_route_throughput(route) * Self::route_distance_factor(route) * TRADE_INCOME_RATE
    }

    /// The best route a pair could open today: the endpoint pair
    /// with the highest throughput among pairs a path exists for,
    /// ties broken by endpoint ids. `None` when no pair connects.
    /// Used by the AI planner and by the bridge's "open the best
    /// route" command alike — one rule for everyone.
    ///
    /// Candidates are weighed in the preference order above and
    /// path-checked in that order, so the winner is the same pair
    /// an exhaustive search would pick whenever the best pair
    /// connects. Path checks stop after
    /// [`SUGGEST_PATH_CHECK_CAP`] candidates: a suggestion is a
    /// heuristic, and the exhaustive form (a Dijkstra per colony
    /// pair, monthly, per contacted pair) stalled the S4 long run
    /// at first contact. Explicit-endpoint route commands still
    /// path-check exactly.
    pub fn suggest_trade_route(
        &self,
        galaxy: &Galaxy,
        a: u32,
        b: u32,
    ) -> Option<(StarId, StarId, Vec<StarId>, f64)> {
        let mut candidates: Vec<(f64, StarId, StarId)> = Vec::new();
        for system_a in self.colonies_of(a) {
            for system_b in self.colonies_of(b) {
                let throughput = self.route_throughput(a, b, system_a, system_b);
                if throughput > 0.0 {
                    candidates.push((throughput, system_a, system_b));
                }
            }
        }
        candidates.sort_by(|x, y| {
            y.0.partial_cmp(&x.0)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then((x.1, x.2).cmp(&(y.1, y.2)))
        });
        for (_, system_a, system_b) in candidates.into_iter().take(SUGGEST_PATH_CHECK_CAP) {
            if let Some((path, path_ly)) = self.trade_path(galaxy, a, b, system_a, system_b) {
                return Some((system_a, system_b, path, path_ly));
            }
        }
        None
    }

    /// Open a trade route between two endpoint colonies (player
    /// wrapper over `establish_trade_route_for`; endpoints are the
    /// player's system first).
    pub fn establish_trade_route(
        &mut self,
        galaxy: &Galaxy,
        other: u32,
        my_system: StarId,
        their_system: StarId,
    ) -> SimResult<u32> {
        self.establish_trade_route_for(PLAYER_CIV, galaxy, other, my_system, their_system)
    }

    /// Open a trade route (design §4.3). Requires an active trade
    /// agreement, no embargo, both endpoints held as colonies by
    /// the right parties, and a colony-network path within tanker
    /// range. Returns the new route's id.
    pub fn establish_trade_route_for(
        &mut self,
        civ_id: u32,
        galaxy: &Galaxy,
        other: u32,
        system_a: StarId,
        system_b: StarId,
    ) -> SimResult<u32> {
        self.require_diplomacy(civ_id, other)?;
        if !self.treaty_active(civ_id, other, TreatyKind::TradeAgreement) {
            return Err(SimError::TradeAgreementRequired);
        }
        if self.embargo_between(civ_id, other) {
            return Err(SimError::TradeAgreementRequired);
        }
        for (owner, system) in [(civ_id, system_a), (other, system_b)] {
            match self.systems.get(&system) {
                Some(state) if state.colony.is_some() && state.claimed_by == Some(owner) => {}
                Some(state) if state.colony.is_some() => {
                    return Err(SimError::NotYourColony(system));
                }
                _ => return Err(SimError::NoColony(system)),
            }
        }
        if self.trade_routes.iter().any(|r| {
            (r.civ_a == civ_id && r.system_a == system_a && r.system_b == system_b)
                || (r.civ_a == other && r.system_a == system_b && r.system_b == system_a)
        }) {
            return Err(SimError::TradeRouteAlreadyExists);
        }
        let Some((path, path_ly)) = self.trade_path(galaxy, civ_id, other, system_a, system_b)
        else {
            return Err(SimError::NoTradePath);
        };
        let (civ_a, civ_b, sys_a, sys_b) = if civ_id < other {
            (civ_id, other, system_a, system_b)
        } else {
            (other, civ_id, system_b, system_a)
        };
        let (path, path_ly) = if civ_id < other {
            (path, path_ly)
        } else {
            let mut reversed = path;
            reversed.reverse();
            (reversed, path_ly)
        };
        let id = self.next_route_id;
        self.next_route_id += 1;
        self.trade_routes.push(TradeRoute {
            id,
            civ_a,
            civ_b,
            system_a: sys_a,
            system_b: sys_b,
            path,
            path_ly,
            established_day: self.day,
            earned_a: 0.0,
            earned_b: 0.0,
            last_income_a: 0.0,
            last_income_b: 0.0,
            months_active: 0,
        });
        self.push_event(
            EventKind::TradeRouteEstablished,
            Some(sys_a),
            None,
            Some(civ_a),
            Some(civ_b),
        );
        Ok(id)
    }

    /// Sever one of your own trade routes (player wrapper over
    /// `sever_trade_route_for`). Closing a route is a commercial
    /// act, not a breach — the treaty that enables routes is the
    /// promise; a route is just business.
    pub fn sever_trade_route(&mut self, route_id: u32) -> SimResult<()> {
        self.sever_trade_route_for(PLAYER_CIV, route_id)
    }

    pub fn sever_trade_route_for(&mut self, civ_id: u32, route_id: u32) -> SimResult<()> {
        let route = self
            .trade_routes
            .iter()
            .find(|r| r.id == route_id)
            .ok_or(SimError::UnknownTradeRoute(route_id))?;
        if route.civ_a != civ_id && route.civ_b != civ_id {
            return Err(SimError::NotRouteParty(civ_id));
        }
        self.close_route(route_id);
        Ok(())
    }

    /// The monthly diplomacy settlement: research-pact bonuses,
    /// trade-route income against the route ledgers, route
    /// validity, and proposal expiry. Runs inside the daily step
    /// on settlement days, after the colony settlement, so a save
    /// advanced by catch-up settles identically (§11.1).
    fn monthly_diplomacy_settlement(
        &mut self,
        galaxy: &Galaxy,
        research_outputs: &BTreeMap<u32, f64>,
    ) {
        // Research pacts: each partner gains a bonus drawn from
        // the other's actual output this month.
        let pacts: Vec<(u32, u32)> = self
            .treaties
            .iter()
            .filter(|t| t.kind == TreatyKind::ResearchPact)
            .map(|t| t.parties)
            .collect();
        for (a, b) in pacts {
            let bonus_a = research_outputs.get(&b).copied().unwrap_or(0.0)
                * RESEARCH_PACT_BONUS_FRACTION;
            let bonus_b = research_outputs.get(&a).copied().unwrap_or(0.0)
                * RESEARCH_PACT_BONUS_FRACTION;
            if let Some(civ) = self.civs.get_mut(a as usize) {
                civ.research_points += bonus_a;
            }
            if let Some(civ) = self.civs.get_mut(b as usize) {
                civ.research_points += bonus_b;
            }
        }

        // Trade routes: a route pays only while its agreement
        // holds, no embargo stands, both endpoints are still the
        // parties' colonies, and every system on its path still
        // holds a colony of one of the two parties. Otherwise it
        // closes, on the record.
        let route_ids: Vec<u32> = self.trade_routes.iter().map(|r| r.id).collect();
        for route_id in route_ids {
            let Some(route) = self.trade_routes.iter().find(|r| r.id == route_id).cloned() else {
                continue;
            };
            let valid = self.treaty_active(route.civ_a, route.civ_b, TreatyKind::TradeAgreement)
                && !self.embargo_between(route.civ_a, route.civ_b)
                && self.live_route_throughput(&route) > 0.0
                && route.path.iter().all(|&system| {
                    self.systems.get(&system).map(|s| {
                        s.colony.is_some()
                            && (s.claimed_by == Some(route.civ_a)
                                || s.claimed_by == Some(route.civ_b))
                    }) == Some(true)
                });
            if !valid {
                self.close_route(route_id);
                continue;
            }
            let income = self.route_monthly_income(&route);
            if let Some(live) = self.trade_routes.iter_mut().find(|r| r.id == route_id) {
                live.earned_a += income;
                live.earned_b += income;
                live.last_income_a = income;
                live.last_income_b = income;
                live.months_active += 1;
            }
            self.total_trade_income += income * 2.0;
            if let Some(civ) = self.civs.get_mut(route.civ_a as usize) {
                civ.credits += income;
            }
            if let Some(civ) = self.civs.get_mut(route.civ_b as usize) {
                civ.credits += income;
            }
        }

        // Unanswered proposals lapse, and the proposer waits out a
        // shorter cooldown before offering that instrument again.
        let today = self.day;
        let lapsed: Vec<Proposal> = self
            .proposals
            .iter()
            .filter(|p| today > p.proposed_day + PROPOSAL_TTL_DAYS)
            .cloned()
            .collect();
        if !lapsed.is_empty() {
            self.proposals
                .retain(|p| today <= p.proposed_day + PROPOSAL_TTL_DAYS);
            for proposal in lapsed {
                let key = Self::pair_key(proposal.from, proposal.to);
                self.proposal_cooldowns.insert(
                    (key.0, key.1, proposal.kind.cooldown_code()),
                    today + PROPOSAL_TTL_DAYS,
                );
            }
        }
        let _ = galaxy;
    }
}
