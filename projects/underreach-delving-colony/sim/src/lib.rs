//! Underreach: Delving Colony — deterministic simulation core (S1).
//!
//! Engine-agnostic: the core owns world, light, delvers, and the Deep
//! Ledger. A frontend (Godot, later slice) reads state and issues the
//! player actions (`carve`, `place_lantern`); it holds no sim rules.

pub mod gen;
pub mod scenario;
pub mod sim;
pub mod world;
