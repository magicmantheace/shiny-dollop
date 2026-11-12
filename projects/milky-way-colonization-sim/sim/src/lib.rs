//! Milky Way Colonization Simulator — deterministic headless sim core.
//!
//! Slice S1: one civilization, survey → claim → colonize, ship/fuel
//! mechanics, monthly economy settlement, canonical save/load.
//! Slice S2 wired the core to the Godot frontend through the bridge
//! crate. Slice S3 adds AI civilizations (placement, personalities,
//! per-civilization fog of war, contact and claim disputes) running
//! the same rules through the same command surface.

pub mod ai;
pub mod catalog;
pub mod diplomacy;
pub mod policy;
pub mod profile;
pub mod race;
pub mod rng;
pub mod save;
pub mod state;

pub use catalog::{Galaxy, StaticPlanet, StaticStar};
pub use diplomacy::{DealEvaluation, OpinionBreakdown, Relation};
pub use policy::ScriptedPolicy;
pub use profile::{PlanetProfile, PlanetSource, SystemProfile};
pub use race::{Archetype, HomeworldRules, Personality, ARCHETYPES, DEFAULT_AI_COUNT, MAX_AI_COUNT};
pub use rng::SeededRng;
pub use state::{
    AiCivSetup, Campaign, Civilization, Colony, ConstructionProject, DealOutcome, Dispute, Embargo,
    EventKind, GameEvent, GameSetup, PeaceTerms, Proposal, ProposalKind, Purpose, SetupReport, Ship,
    ShipDesign, ShipKind, ShipState, SimError, SimResult, Specialization, SurveyState, SystemState,
    TradeRoute, Treaty, TreatyBreach, TreatyKind, CLAIM_COST_CREDITS, DAYS_PER_MONTH,
    DAYS_PER_YEAR, PLAYER_CIV, PROPOSAL_COOLDOWN_DAYS, PROPOSAL_TTL_DAYS,
    RESEARCH_PACT_BONUS_FRACTION, TRADE_INCOME_RATE, TRADE_LEG_LY, TRANSLATION_DAYS,
};
