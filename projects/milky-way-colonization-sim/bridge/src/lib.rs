//! Milky Way Colonization Simulator — bridge library (S2).
//!
//! The `sim-bridge` binary is the designated wall-clock boundary:
//! the sim core stays clock-free, and all `now` handling lives in
//! the binary. This library holds the JSON implementation, the save
//! envelope, and the view/event/snapshot/inspect serialization.

pub mod envelope;
pub mod json;
pub mod view;
