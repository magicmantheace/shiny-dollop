//! Milky Way Colonization Simulator — deterministic headless sim core.
//!
//! Slice S1: one civilization, survey → claim → colonize, ship/fuel
//! mechanics, monthly economy settlement, canonical save/load. The
//! Godot frontend does not call this crate yet (that is S2); the CLI
//! demo and the test suite are the S1 drivers.

pub mod catalog;
pub mod policy;
pub mod profile;
pub mod rng;
pub mod save;
pub mod state;

pub use catalog::{Galaxy, StaticPlanet, StaticStar};
pub use policy::ScriptedPolicy;
pub use profile::{PlanetProfile, PlanetSource, SystemProfile};
pub use rng::SeededRng;
pub use state::{
    Campaign, Civilization, Colony, ConstructionProject, EventKind, GameEvent, Purpose, Ship,
    ShipDesign, ShipKind, ShipState, SimError, SimResult, Specialization, SurveyState, SystemState,
    DAYS_PER_MONTH, DAYS_PER_YEAR, PLAYER_CIV,
};
