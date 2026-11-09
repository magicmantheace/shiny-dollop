//! A deterministic scripted policy used by the CLI demo and tests.
//!
//! This is not the AI of design §6 (that is S3). It is the S1 harness
//! driver: a fixed set of legible rules that expand one civilization
//! from its homeworld under the same APIs a frontend or AI will use.
//!
//! S3 note: the policy drives the **player's** civilization only.
//! Since S3 the world contains other civilizations' ships and
//! colonies; the policy skips them (the core would refuse the
//! commands anyway, but scanning the galaxy on behalf of a foreign
//! surveyor was wasted work, and foreign hulls must not count
//! toward the player's own fleet needs).

use crate::catalog::Galaxy;
use crate::state::{
    Campaign, Purpose, ShipKind, ShipState, Specialization, StarId, PLAYER_CIV,
};

#[derive(Debug, Default, Clone, Copy)]
pub struct ScriptedPolicy;

impl ScriptedPolicy {
    /// Make at most one round of decisions for the current day.
    /// Calling this once per simulated day gives the demo/tests their
    /// fixed decision cadence.
    pub fn step(&mut self, sim: &mut Campaign, galaxy: &Galaxy) {
        self.assign_specializations(sim);
        self.drive_ships(sim, galaxy);
        self.build_missing_ships(sim);
    }

    fn assign_specializations(&mut self, sim: &mut Campaign) {
        let systems: Vec<StarId> = sim.systems().keys().copied().collect();
        for system in systems {
            let Some(state) = sim.system(system) else {
                continue;
            };
            if state.claimed_by != Some(PLAYER_CIV) {
                continue;
            }
            let Some(colony) = state.colony.as_ref() else {
                continue;
            };
            if colony.development < 3 || colony.specialization.is_some() {
                continue;
            }
            let Some(profile) = state.profile.as_ref() else {
                continue;
            };
            let specialization = if profile.fuel_trait >= 1.30 {
                Specialization::Refinery
            } else if profile.habitability_percent >= 70.0 {
                Specialization::Agricultural
            } else {
                Specialization::Industrial
            };
            let _ = sim.assign_specialization(system, specialization);
        }
    }

    fn drive_ships(&mut self, sim: &mut Campaign, galaxy: &Galaxy) {
        let ship_ids: Vec<u32> = sim.ships().keys().copied().collect();
        for ship_id in ship_ids {
            let Some(ship) = sim.ship(ship_id) else {
                continue;
            };
            if ship.owner != PLAYER_CIV {
                continue;
            }
            let design = sim.design(ship.design_idx).cloned();
            let Some(design) = design else { continue };
            match ship.state.clone() {
                ShipState::StrandedAtSystem { .. } => {
                    let _ = sim.refuel_ship(ship_id);
                }
                ShipState::AtSystem { system } => {
                    // Top up whenever a colony here can supply fuel.
                    if sim.system(system).and_then(|s| s.colony.as_ref()).is_some()
                        && ship.fuel < design.tank_capacity * 0.98
                    {
                        let _ = sim.refuel_ship(ship_id);
                        // Refuelling is this ship's action for the step;
                        // it may still depart on a later day.
                        continue;
                    }
                    match design.kind {
                        ShipKind::Surveyor => self.drive_surveyor(sim, galaxy, ship_id, system),
                        ShipKind::Colony => self.drive_colony_ship(sim, galaxy, ship_id, system),
                    }
                }
                _ => {}
            }
        }
    }

    fn drive_surveyor(
        &mut self,
        sim: &mut Campaign,
        galaxy: &Galaxy,
        ship_id: u32,
        system: StarId,
    ) {
        let state = sim.system(system);
        // Per-civilization knowledge since S3: another civilization's
        // survey of this system is invisible to the player, so the
        // question is whether *the player* has surveyed it.
        if !sim.surveyed_by(PLAYER_CIV, system) {
            let _ = sim.begin_survey(galaxy, ship_id);
            return;
        }
        if state.and_then(|s| s.claimed_by).is_none() {
            if sim.credits() >= 100.0 {
                let _ = sim.claim_system(system);
            }
            return;
        }
        if let Some(target) = nearest_unknown_within_range(sim, galaxy, system, ship_id) {
            // Prudence rule: only hop when the tanks also hold the
            // return leg from the target to the nearest colony.
            // Without it a surveyor chains single legs until it is
            // marooned at a claim with too little fuel to move at
            // all — the S1 demo found exactly that failure at
            // Teegarden's Star with 0.04 fuel aboard.
            let ship = sim.ship(ship_id);
            let design = ship.and_then(|s| sim.design(s.design_idx));
            if let (Some(ship), Some(design)) = (ship, design) {
                let distance = galaxy.distance_ly(system, target).unwrap_or(0.0);
                let needed = distance * design.fuel_per_ly;
                let return_ly = nearest_colony_distance(sim, galaxy, target).unwrap_or(distance);
                let reserve = return_ly * design.fuel_per_ly;
                if ship.fuel + 1e-9 >= needed + reserve {
                    let _ = sim.dispatch_ship(galaxy, ship_id, target, Purpose::Survey);
                    return;
                }
            }
            // Not prudent to hop: fall through and head back to a
            // colony to refuel instead of retrying forever.
        }
        // No (prudent) frontier hop from here: fall back to a colony
        // reachable on the fuel actually aboard.
        if sim.system(system).and_then(|s| s.colony.as_ref()).is_none() {
            if let Some(base) = nearest_colony_within_fuel(sim, galaxy, system, ship_id) {
                let _ = sim.dispatch_ship(galaxy, ship_id, base, Purpose::Relocate);
            }
        }
    }

    fn drive_colony_ship(
        &mut self,
        sim: &mut Campaign,
        galaxy: &Galaxy,
        ship_id: u32,
        system: StarId,
    ) {
        if let Some(target) = nearest_colonizable_within_range(sim, galaxy, system, ship_id) {
            let _ = sim.dispatch_ship(galaxy, ship_id, target, Purpose::Colonize);
            return;
        }
        if sim.system(system).and_then(|s| s.colony.as_ref()).is_none() {
            if let Some(base) = nearest_colony_within_range(sim, galaxy, system, ship_id) {
                let _ = sim.dispatch_ship(galaxy, ship_id, base, Purpose::Relocate);
            }
        }
    }

    fn build_missing_ships(&mut self, sim: &mut Campaign) {
        for wanted in [ShipKind::Surveyor, ShipKind::Colony] {
            if self.kind_available_or_queued(sim, wanted) {
                continue;
            }
            let design_idx = sim
                .designs()
                .iter()
                .position(|d| d.kind == wanted)
                .map(|i| i as u32);
            let Some(design_idx) = design_idx else {
                continue;
            };
            let design = sim.design(design_idx).unwrap().clone();
            // Keep a treasury reserve: frontier colonies run at a
            // deficit for years, so the policy only builds when the
            // civilization can afford the hull and the subsidy.
            let reserve = match wanted {
                ShipKind::Colony => 4_000.0,
                ShipKind::Surveyor => 500.0,
            };
            if sim.credits() + 1e-9 < design.credits_cost() + reserve {
                continue;
            }
            // Build where the alloys are: richest colony first, then
            // lowest star id for a stable tie-break. Only the
            // player's own colonies can build for the player.
            let mut colonies: Vec<(StarId, f64)> = sim
                .systems()
                .iter()
                .filter(|(_, state)| state.claimed_by == Some(PLAYER_CIV))
                .filter_map(|(id, state)| state.colony.as_ref().map(|c| (*id, c.alloys_stock)))
                .collect();
            colonies.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
            for (system, alloys) in colonies {
                if alloys + 1e-9 >= design.alloys_cost() {
                    let _ = sim.build_ship(system, design_idx);
                    break;
                }
            }
        }
    }

    fn kind_available_or_queued(&self, sim: &Campaign, wanted: ShipKind) -> bool {
        let in_fleet = sim.ships().values().any(|ship| {
            ship.owner == PLAYER_CIV
                && sim
                    .design(ship.design_idx)
                    .map(|d| d.kind == wanted)
                    .unwrap_or(false)
        });
        if in_fleet {
            return true;
        }
        sim.systems().values().any(|state| {
            state.claimed_by == Some(PLAYER_CIV)
                && state
                .colony
                .as_ref()
                .map(|colony| {
                    colony.construction_queue.iter().any(|project| {
                        sim.design(project.design_idx)
                            .map(|d| d.kind == wanted)
                            .unwrap_or(false)
                    })
                })
                .unwrap_or(false)
        })
    }
}

fn ship_range(sim: &Campaign, ship_id: u32) -> Option<f64> {
    let ship = sim.ship(ship_id)?;
    sim.design(ship.design_idx).map(|d| d.range_ly())
}

fn nearest_unknown_within_range(
    sim: &Campaign,
    galaxy: &Galaxy,
    from: StarId,
    ship_id: u32,
) -> Option<StarId> {
    let range = ship_range(sim, ship_id)?;
    let origin = galaxy.star(from)?;
    let mut best: Option<(f64, StarId)> = None;
    for star in galaxy.stars() {
        if star.id == from {
            continue;
        }
        if sim.surveyed_by(PLAYER_CIV, star.id) {
            continue;
        }
        let distance = crate::catalog::distance_between(origin.pos_ly, star.pos_ly);
        if distance <= range + 1e-9 {
            let candidate = (distance, star.id);
            if best.map(|b| candidate < b).unwrap_or(true) {
                best = Some(candidate);
            }
        }
    }
    best.map(|(_, id)| id)
}

fn nearest_colonizable_within_range(
    sim: &Campaign,
    galaxy: &Galaxy,
    from: StarId,
    ship_id: u32,
) -> Option<StarId> {
    let range = ship_range(sim, ship_id)?;
    let mut best: Option<(f64, StarId)> = None;
    for (id, state) in sim.systems() {
        if !state.surveyed_by.contains(&PLAYER_CIV)
            || state.claimed_by != Some(PLAYER_CIV)
            || state.colony.is_some()
        {
            continue;
        }
        let habitability = state
            .profile
            .as_ref()
            .map(|p| p.habitability_percent)
            .unwrap_or(0.0);
        if habitability < 40.0 {
            continue;
        }
        let Some(distance) = galaxy.distance_ly(from, *id) else {
            continue;
        };
        if distance <= range + 1e-9 {
            let candidate = (distance, *id);
            if best.map(|b| candidate < b).unwrap_or(true) {
                best = Some(candidate);
            }
        }
    }
    best.map(|(_, id)| id)
}

fn nearest_colony_within_range(
    sim: &Campaign,
    galaxy: &Galaxy,
    from: StarId,
    ship_id: u32,
) -> Option<StarId> {
    let range = ship_range(sim, ship_id)?;
    let mut best: Option<(f64, StarId)> = None;
    for (id, state) in sim.systems() {
        if *id == from || state.colony.is_none() || state.claimed_by != Some(PLAYER_CIV) {
            continue;
        }
        let Some(distance) = galaxy.distance_ly(from, *id) else {
            continue;
        };
        if distance <= range + 1e-9 {
            let candidate = (distance, *id);
            if best.map(|b| candidate < b).unwrap_or(true) {
                best = Some(candidate);
            }
        }
    }
    best.map(|(_, id)| id)
}

/// Distance from `from` to the nearest of the player's colonies
/// (0 if `from` is itself one).
fn nearest_colony_distance(sim: &Campaign, galaxy: &Galaxy, from: StarId) -> Option<f64> {
    let mut best: Option<f64> = None;
    for (id, state) in sim.systems() {
        if state.colony.is_none() || state.claimed_by != Some(PLAYER_CIV) {
            continue;
        }
        let Some(distance) = galaxy.distance_ly(from, *id) else {
            continue;
        };
        if best.map(|b| distance < b).unwrap_or(true) {
            best = Some(distance);
        }
    }
    best
}

/// Nearest colony the ship can actually reach on its current fuel
/// (stricter than design range: the tanks, not the brochure).
fn nearest_colony_within_fuel(
    sim: &Campaign,
    galaxy: &Galaxy,
    from: StarId,
    ship_id: u32,
) -> Option<StarId> {
    let ship = sim.ship(ship_id)?;
    let design = sim.design(ship.design_idx)?;
    let mut best: Option<(f64, StarId)> = None;
    for (id, state) in sim.systems() {
        if *id == from || state.colony.is_none() {
            continue;
        }
        let Some(distance) = galaxy.distance_ly(from, *id) else {
            continue;
        };
        if distance * design.fuel_per_ly <= ship.fuel + 1e-9 && distance <= design.range_ly() + 1e-9
        {
            let candidate = (distance, *id);
            if best.map(|b| candidate < b).unwrap_or(true) {
                best = Some(candidate);
            }
        }
    }
    best.map(|(_, id)| id)
}
