//! Canonical serialization, state hashing, and save/load.
//!
//! The canonical form is a purpose-built binary encoding: maps are
//! stored in `BTreeMap` key order, sequences in their stored order,
//! strings as length-prefixed UTF-8, and floats as their raw bits.
//! The same logical state therefore serializes to the same bytes, and
//! the SHA-256 of those bytes is the state hash used by the
//! determinism tests.
//!
//! The save format is the canonical payload behind a small header
//! (`MWSS`, version, payload length). Loading a save requires the
//! same galaxy table (checked by catalog fingerprint + star count);
//! the static catalog itself is not duplicated into the save.
//!
//! Format history: v1 was the S1/S2 single-civilization format. v2
//! (S3) stores the civilization list with AI personalities, ship
//! owners, per-civilization survey knowledge, contacts, and
//! disputes. v1 saves are rejected with an explicit version error —
//! S3 changed what a campaign *is*, and silently upgrading would
//! invent AI state the old save never had.

use std::collections::{BTreeMap, BTreeSet};

use mwcs_pipeline::sha256::sha256_hex;

use crate::catalog::Galaxy;
use crate::profile::{PlanetProfile, PlanetSource, SystemProfile};
use crate::race::Personality;
use crate::rng::SeededRng;
use crate::state::{
    Campaign, Civilization, Colony, ConstructionProject, Dispute, EventKind, GameEvent, Purpose,
    Ship, ShipDesign, ShipKind, ShipState, SimError, SimResult, Specialization, SurveyState,
    SystemState,
};

const SAVE_MAGIC: &[u8; 4] = b"MWSS";
const SAVE_VERSION: u32 = 2;

impl Campaign {
    pub fn canonical_bytes(&self) -> Vec<u8> {
        let mut w = Writer::default();
        w.string(&self.galaxy_fingerprint);
        w.u64(self.star_count as u64);
        w.u64(self.seed);
        w.u64(self.day);
        w.u64(self.rng.state());
        w.u32(self.civs.len() as u32);
        for civ in &self.civs {
            write_civ(&mut w, civ);
        }

        w.u32(self.designs.len() as u32);
        for design in &self.designs {
            w.string(&design.name);
            w.u8(ship_kind_code(design.kind));
            w.f64(design.tank_capacity);
            w.f64(design.fuel_per_ly);
            w.f64(design.speed_ly_per_day);
            w.f64(design.payload_capacity);
        }

        w.u32(self.systems.len() as u32);
        for (id, state) in &self.systems {
            w.u32(*id);
            write_system(&mut w, state);
        }

        w.u32(self.ships.len() as u32);
        for (id, ship) in &self.ships {
            w.u32(*id);
            w.u32(ship.owner);
            w.u32(ship.design_idx);
            w.f64(ship.fuel);
            write_ship_state(&mut w, &ship.state);
        }

        w.u32(self.events.len() as u32);
        for event in &self.events {
            w.u64(event.day);
            w.u8(event_kind_code(event.kind));
            w.option_u32(event.system);
            w.option_u32(event.ship);
            w.option_u32(event.civ);
            w.option_u32(event.other_civ);
        }

        w.u32(self.contacts.len() as u32);
        for ((lo, hi), day) in &self.contacts {
            w.u32(*lo);
            w.u32(*hi);
            w.u64(*day);
        }

        w.u32(self.disputes.len() as u32);
        for dispute in &self.disputes {
            w.u32(dispute.system);
            w.u32(dispute.holder);
            w.u32(dispute.challenger);
            w.u64(dispute.opened_day);
        }

        w.u32(self.next_ship_id);
        w.u32(self.next_project_id);
        w.bytes
    }

    pub fn state_hash(&self) -> String {
        sha256_hex(&self.canonical_bytes())
    }

    pub fn save_bytes(&self) -> Vec<u8> {
        let payload = self.canonical_bytes();
        let mut out = Vec::with_capacity(16 + payload.len());
        out.extend_from_slice(SAVE_MAGIC);
        out.extend_from_slice(&SAVE_VERSION.to_le_bytes());
        out.extend_from_slice(&(payload.len() as u64).to_le_bytes());
        out.extend_from_slice(&payload);
        out
    }

    pub fn load_bytes(galaxy: &Galaxy, bytes: &[u8]) -> SimResult<Self> {
        if bytes.len() < 16 || &bytes[0..4] != SAVE_MAGIC {
            return Err(SimError::InvalidSave("bad magic".into()));
        }
        let version = u32::from_le_bytes(bytes[4..8].try_into().unwrap());
        if version != SAVE_VERSION {
            return Err(SimError::InvalidSave(format!(
                "unsupported save version {version}"
            )));
        }
        let payload_len = u64::from_le_bytes(bytes[8..16].try_into().unwrap()) as usize;
        if bytes.len() != 16 + payload_len {
            return Err(SimError::InvalidSave("length mismatch".into()));
        }
        let mut r = Reader::new(&bytes[16..]);
        let campaign = read_campaign(&mut r)?;
        if r.remaining() != 0 {
            return Err(SimError::InvalidSave("trailing bytes".into()));
        }
        if campaign.galaxy_fingerprint != galaxy.fingerprint()
            || campaign.star_count != galaxy.len()
        {
            return Err(SimError::GalaxyMismatch);
        }
        Ok(campaign)
    }
}

#[derive(Default)]
struct Writer {
    bytes: Vec<u8>,
}

impl Writer {
    fn u8(&mut self, v: u8) {
        self.bytes.push(v);
    }
    fn bool(&mut self, v: bool) {
        self.u8(if v { 1 } else { 0 });
    }
    fn u32(&mut self, v: u32) {
        self.bytes.extend_from_slice(&v.to_le_bytes());
    }
    fn u64(&mut self, v: u64) {
        self.bytes.extend_from_slice(&v.to_le_bytes());
    }
    fn f32(&mut self, v: f32) {
        self.bytes.extend_from_slice(&v.to_bits().to_le_bytes());
    }
    fn f64(&mut self, v: f64) {
        self.bytes.extend_from_slice(&v.to_bits().to_le_bytes());
    }
    fn string(&mut self, v: &str) {
        self.u32(v.len() as u32);
        self.bytes.extend_from_slice(v.as_bytes());
    }
    fn option_u32(&mut self, v: Option<u32>) {
        match v {
            None => self.u8(0),
            Some(x) => {
                self.u8(1);
                self.u32(x);
            }
        }
    }
}

struct Reader<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, pos: 0 }
    }
    fn remaining(&self) -> usize {
        self.bytes.len().saturating_sub(self.pos)
    }
    fn take(&mut self, n: usize) -> SimResult<&'a [u8]> {
        if self.remaining() < n {
            return Err(SimError::InvalidSave("unexpected end of save".into()));
        }
        let out = &self.bytes[self.pos..self.pos + n];
        self.pos += n;
        Ok(out)
    }
    fn u8(&mut self) -> SimResult<u8> {
        Ok(self.take(1)?[0])
    }
    fn bool(&mut self) -> SimResult<bool> {
        match self.u8()? {
            0 => Ok(false),
            1 => Ok(true),
            other => Err(SimError::InvalidSave(format!("bad bool {other}"))),
        }
    }
    fn u32(&mut self) -> SimResult<u32> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    fn u64(&mut self) -> SimResult<u64> {
        Ok(u64::from_le_bytes(self.take(8)?.try_into().unwrap()))
    }
    fn f32(&mut self) -> SimResult<f32> {
        Ok(f32::from_bits(self.u32()?))
    }
    fn f64(&mut self) -> SimResult<f64> {
        Ok(f64::from_bits(self.u64()?))
    }
    fn string(&mut self) -> SimResult<String> {
        let len = self.u32()? as usize;
        let bytes = self.take(len)?;
        String::from_utf8(bytes.to_vec())
            .map_err(|e| SimError::InvalidSave(format!("bad utf-8: {e}")))
    }
    fn option_u32(&mut self) -> SimResult<Option<u32>> {
        match self.u8()? {
            0 => Ok(None),
            1 => Ok(Some(self.u32()?)),
            other => Err(SimError::InvalidSave(format!("bad option tag {other}"))),
        }
    }
}

fn ship_kind_code(kind: ShipKind) -> u8 {
    match kind {
        ShipKind::Surveyor => 0,
        ShipKind::Colony => 1,
    }
}

fn ship_kind_from(code: u8) -> SimResult<ShipKind> {
    match code {
        0 => Ok(ShipKind::Surveyor),
        1 => Ok(ShipKind::Colony),
        other => Err(SimError::InvalidSave(format!("bad ship kind {other}"))),
    }
}

fn specialization_code(spec: Specialization) -> u8 {
    match spec {
        Specialization::Industrial => 0,
        Specialization::Agricultural => 1,
        Specialization::Refinery => 2,
        Specialization::Research => 3,
        Specialization::Fortress => 4,
        Specialization::TradeHub => 5,
        Specialization::Shipyard => 6,
    }
}

fn specialization_from(code: u8) -> SimResult<Specialization> {
    match code {
        0 => Ok(Specialization::Industrial),
        1 => Ok(Specialization::Agricultural),
        2 => Ok(Specialization::Refinery),
        3 => Ok(Specialization::Research),
        4 => Ok(Specialization::Fortress),
        5 => Ok(Specialization::TradeHub),
        6 => Ok(Specialization::Shipyard),
        other => Err(SimError::InvalidSave(format!("bad specialization {other}"))),
    }
}

fn purpose_code(purpose: Purpose) -> u8 {
    match purpose {
        Purpose::Survey => 0,
        Purpose::Colonize => 1,
        Purpose::Relocate => 2,
    }
}

fn purpose_from(code: u8) -> SimResult<Purpose> {
    match code {
        0 => Ok(Purpose::Survey),
        1 => Ok(Purpose::Colonize),
        2 => Ok(Purpose::Relocate),
        other => Err(SimError::InvalidSave(format!("bad purpose {other}"))),
    }
}

fn event_kind_code(kind: EventKind) -> u8 {
    match kind {
        EventKind::CampaignStarted => 0,
        EventKind::SurveyStarted => 1,
        EventKind::SurveyCompleted => 2,
        EventKind::SystemClaimed => 3,
        EventKind::ShipDispatched => 4,
        EventKind::ShipArrived => 5,
        EventKind::ShipStranded => 6,
        EventKind::ShipRefuelled => 7,
        EventKind::ShipBuilt => 8,
        EventKind::ColonyFounded => 9,
        EventKind::ColonyAbandoned => 10,
        EventKind::SpecializationSet => 11,
        EventKind::FirstContact => 12,
        EventKind::ClaimContested => 13,
    }
}

fn event_kind_from(code: u8) -> SimResult<EventKind> {
    match code {
        0 => Ok(EventKind::CampaignStarted),
        1 => Ok(EventKind::SurveyStarted),
        2 => Ok(EventKind::SurveyCompleted),
        3 => Ok(EventKind::SystemClaimed),
        4 => Ok(EventKind::ShipDispatched),
        5 => Ok(EventKind::ShipArrived),
        6 => Ok(EventKind::ShipStranded),
        7 => Ok(EventKind::ShipRefuelled),
        8 => Ok(EventKind::ShipBuilt),
        9 => Ok(EventKind::ColonyFounded),
        10 => Ok(EventKind::ColonyAbandoned),
        11 => Ok(EventKind::SpecializationSet),
        12 => Ok(EventKind::FirstContact),
        13 => Ok(EventKind::ClaimContested),
        other => Err(SimError::InvalidSave(format!("bad event kind {other}"))),
    }
}

fn planet_source_code(source: PlanetSource) -> u8 {
    match source {
        PlanetSource::RealCatalog => 0,
        PlanetSource::Generated => 1,
        PlanetSource::HomeworldSetup => 2,
    }
}

fn planet_source_from(code: u8) -> SimResult<PlanetSource> {
    match code {
        0 => Ok(PlanetSource::RealCatalog),
        1 => Ok(PlanetSource::Generated),
        2 => Ok(PlanetSource::HomeworldSetup),
        other => Err(SimError::InvalidSave(format!("bad planet source {other}"))),
    }
}

fn write_civ(w: &mut Writer, civ: &Civilization) {
    w.u32(civ.id);
    w.string(&civ.name);
    w.f64(civ.credits);
    w.u32(civ.home_system);
    match &civ.archetype {
        None => w.u8(0),
        Some(archetype) => {
            w.u8(1);
            w.string(archetype);
        }
    }
    match &civ.personality {
        None => w.u8(0),
        Some(p) => {
            w.u8(1);
            w.f64(p.expansion);
            w.f64(p.aggression);
            w.f64(p.trade_affinity);
            w.f64(p.xenophobia);
            w.f64(p.honour);
        }
    }
}

fn read_civ(r: &mut Reader<'_>) -> SimResult<Civilization> {
    let id = r.u32()?;
    let name = r.string()?;
    let credits = r.f64()?;
    let home_system = r.u32()?;
    let archetype = match r.u8()? {
        0 => None,
        1 => Some(r.string()?),
        other => {
            return Err(SimError::InvalidSave(format!(
                "bad archetype tag {other}"
            )))
        }
    };
    let personality = match r.u8()? {
        0 => None,
        1 => Some(Personality {
            expansion: r.f64()?,
            aggression: r.f64()?,
            trade_affinity: r.f64()?,
            xenophobia: r.f64()?,
            honour: r.f64()?,
        }),
        other => {
            return Err(SimError::InvalidSave(format!(
                "bad personality tag {other}"
            )))
        }
    };
    Ok(Civilization {
        id,
        name,
        credits,
        home_system,
        archetype,
        personality,
    })
}

fn write_system(w: &mut Writer, state: &SystemState) {
    w.u8(match state.survey {
        SurveyState::Unknown => 0,
        SurveyState::Surveyed => 1,
    });
    w.u32(state.surveyed_by.len() as u32);
    for civ_id in &state.surveyed_by {
        w.u32(*civ_id);
    }
    match &state.profile {
        None => w.u8(0),
        Some(profile) => {
            w.u8(1);
            w.f64(profile.habitability_percent);
            w.f64(profile.fuel_trait);
            w.f64(profile.industry_trait);
            w.f64(profile.exotics_trait);
            w.u32(profile.planets.len() as u32);
            for planet in &profile.planets {
                w.string(&planet.name);
                w.u8(planet_source_code(planet.source));
                w.f64(planet.habitability_percent);
                w.f32(planet.eq_temp_k);
                w.f32(planet.radius_earth);
            }
        }
    }
    w.option_u32(state.claimed_by);
    match &state.colony {
        None => w.u8(0),
        Some(colony) => {
            w.u8(1);
            write_colony(w, colony);
        }
    }
}

fn write_colony(w: &mut Writer, colony: &Colony) {
    w.u64(colony.founded_day);
    w.f64(colony.population_millions);
    w.u8(colony.development);
    match colony.specialization {
        None => w.u8(0),
        Some(spec) => {
            w.u8(1);
            w.u8(specialization_code(spec));
        }
    }
    w.f64(colony.fuel_stock);
    w.f64(colony.supplies_stock);
    w.f64(colony.alloys_stock);
    w.f64(colony.electronics_stock);
    w.f64(colony.exotics_stock);
    w.f64(colony.energy_generation);
    w.f64(colony.energy_consumption);
    w.f64(colony.energy_efficiency);
    w.f64(colony.defence_strength);
    w.bool(colony.supplied);
    w.u32(colony.unsupplied_months);
    w.u32(colony.development_progress_days);
    w.u32(colony.construction_queue.len() as u32);
    for project in &colony.construction_queue {
        w.u32(project.id);
        w.u32(project.design_idx);
        w.u32(project.days_remaining);
        w.u32(project.total_days);
    }
}

fn write_ship_state(w: &mut Writer, state: &ShipState) {
    match state {
        ShipState::AtSystem { system } => {
            w.u8(0);
            w.u32(*system);
        }
        ShipState::Surveying {
            system,
            days_remaining,
        } => {
            w.u8(1);
            w.u32(*system);
            w.u32(*days_remaining);
        }
        ShipState::EnRoute {
            from,
            to,
            distance_ly,
            progress_ly,
            purpose,
            unchecked,
        } => {
            w.u8(2);
            w.u32(*from);
            w.u32(*to);
            w.f64(*distance_ly);
            w.f64(*progress_ly);
            w.u8(purpose_code(*purpose));
            w.bool(*unchecked);
        }
        ShipState::StrandedEnRoute {
            from,
            to,
            distance_ly,
            progress_ly,
            purpose,
        } => {
            w.u8(3);
            w.u32(*from);
            w.u32(*to);
            w.f64(*distance_ly);
            w.f64(*progress_ly);
            w.u8(purpose_code(*purpose));
        }
        ShipState::StrandedAtSystem {
            system,
            pending_purpose,
        } => {
            w.u8(4);
            w.u32(*system);
            match pending_purpose {
                None => w.u8(0),
                Some(purpose) => {
                    w.u8(1);
                    w.u8(purpose_code(*purpose));
                }
            }
        }
    }
}

fn read_campaign(r: &mut Reader<'_>) -> SimResult<Campaign> {
    let galaxy_fingerprint = r.string()?;
    let star_count = r.u64()? as usize;
    let seed = r.u64()?;
    let day = r.u64()?;
    let rng = SeededRng::from_state(r.u64()?);
    let civ_count = r.u32()?;
    let mut civs = Vec::with_capacity(civ_count as usize);
    for _ in 0..civ_count {
        civs.push(read_civ(r)?);
    }

    let design_count = r.u32()?;
    let mut designs = Vec::with_capacity(design_count as usize);
    for _ in 0..design_count {
        designs.push(ShipDesign {
            name: r.string()?,
            kind: ship_kind_from(r.u8()?)?,
            tank_capacity: r.f64()?,
            fuel_per_ly: r.f64()?,
            speed_ly_per_day: r.f64()?,
            payload_capacity: r.f64()?,
        });
    }

    let system_count = r.u32()?;
    let mut systems = BTreeMap::new();
    for _ in 0..system_count {
        let id = r.u32()?;
        systems.insert(id, read_system(r)?);
    }

    let ship_count = r.u32()?;
    let mut ships = BTreeMap::new();
    for _ in 0..ship_count {
        let id = r.u32()?;
        ships.insert(
            id,
            Ship {
                id,
                owner: r.u32()?,
                design_idx: r.u32()?,
                fuel: r.f64()?,
                state: read_ship_state(r)?,
            },
        );
    }

    let event_count = r.u32()?;
    let mut events = Vec::with_capacity(event_count as usize);
    for _ in 0..event_count {
        events.push(GameEvent {
            day: r.u64()?,
            kind: event_kind_from(r.u8()?)?,
            system: r.option_u32()?,
            ship: r.option_u32()?,
            civ: r.option_u32()?,
            other_civ: r.option_u32()?,
        });
    }

    let contact_count = r.u32()?;
    let mut contacts = BTreeMap::new();
    for _ in 0..contact_count {
        let lo = r.u32()?;
        let hi = r.u32()?;
        let day = r.u64()?;
        contacts.insert((lo, hi), day);
    }

    let dispute_count = r.u32()?;
    let mut disputes = Vec::with_capacity(dispute_count as usize);
    for _ in 0..dispute_count {
        disputes.push(Dispute {
            system: r.u32()?,
            holder: r.u32()?,
            challenger: r.u32()?,
            opened_day: r.u64()?,
        });
    }

    Ok(Campaign {
        galaxy_fingerprint,
        star_count,
        seed,
        day,
        rng,
        civs,
        designs,
        systems,
        ships,
        events,
        contacts,
        disputes,
        neighbor_cache: BTreeMap::new(),
        next_ship_id: r.u32()?,
        next_project_id: r.u32()?,
    })
}

fn read_system(r: &mut Reader<'_>) -> SimResult<SystemState> {
    let survey = match r.u8()? {
        0 => SurveyState::Unknown,
        1 => SurveyState::Surveyed,
        other => return Err(SimError::InvalidSave(format!("bad survey state {other}"))),
    };
    let surveyed_count = r.u32()?;
    let mut surveyed_by = BTreeSet::new();
    for _ in 0..surveyed_count {
        surveyed_by.insert(r.u32()?);
    }
    let profile = match r.u8()? {
        0 => None,
        1 => {
            let habitability_percent = r.f64()?;
            let fuel_trait = r.f64()?;
            let industry_trait = r.f64()?;
            let exotics_trait = r.f64()?;
            let planet_count = r.u32()?;
            let mut planets = Vec::with_capacity(planet_count as usize);
            for _ in 0..planet_count {
                planets.push(PlanetProfile {
                    name: r.string()?,
                    source: planet_source_from(r.u8()?)?,
                    habitability_percent: r.f64()?,
                    eq_temp_k: r.f32()?,
                    radius_earth: r.f32()?,
                });
            }
            Some(SystemProfile {
                habitability_percent,
                fuel_trait,
                industry_trait,
                exotics_trait,
                planets,
            })
        }
        other => return Err(SimError::InvalidSave(format!("bad profile tag {other}"))),
    };
    let claimed_by = r.option_u32()?;
    let colony = match r.u8()? {
        0 => None,
        1 => Some(read_colony(r)?),
        other => return Err(SimError::InvalidSave(format!("bad colony tag {other}"))),
    };
    Ok(SystemState {
        survey,
        surveyed_by,
        profile,
        claimed_by,
        colony,
    })
}

fn read_colony(r: &mut Reader<'_>) -> SimResult<Colony> {
    let founded_day = r.u64()?;
    let population_millions = r.f64()?;
    let development = r.u8()?;
    let specialization = match r.u8()? {
        0 => None,
        1 => Some(specialization_from(r.u8()?)?),
        other => {
            return Err(SimError::InvalidSave(format!(
                "bad specialization tag {other}"
            )))
        }
    };
    let fuel_stock = r.f64()?;
    let supplies_stock = r.f64()?;
    let alloys_stock = r.f64()?;
    let electronics_stock = r.f64()?;
    let exotics_stock = r.f64()?;
    let energy_generation = r.f64()?;
    let energy_consumption = r.f64()?;
    let energy_efficiency = r.f64()?;
    let defence_strength = r.f64()?;
    let supplied = r.bool()?;
    let unsupplied_months = r.u32()?;
    let development_progress_days = r.u32()?;
    let queue_count = r.u32()?;
    let mut construction_queue = Vec::with_capacity(queue_count as usize);
    for _ in 0..queue_count {
        construction_queue.push(ConstructionProject {
            id: r.u32()?,
            design_idx: r.u32()?,
            days_remaining: r.u32()?,
            total_days: r.u32()?,
        });
    }
    Ok(Colony {
        founded_day,
        population_millions,
        development,
        specialization,
        fuel_stock,
        supplies_stock,
        alloys_stock,
        electronics_stock,
        exotics_stock,
        energy_generation,
        energy_consumption,
        energy_efficiency,
        defence_strength,
        supplied,
        unsupplied_months,
        development_progress_days,
        construction_queue,
    })
}

fn read_ship_state(r: &mut Reader<'_>) -> SimResult<ShipState> {
    match r.u8()? {
        0 => Ok(ShipState::AtSystem { system: r.u32()? }),
        1 => Ok(ShipState::Surveying {
            system: r.u32()?,
            days_remaining: r.u32()?,
        }),
        2 => Ok(ShipState::EnRoute {
            from: r.u32()?,
            to: r.u32()?,
            distance_ly: r.f64()?,
            progress_ly: r.f64()?,
            purpose: purpose_from(r.u8()?)?,
            unchecked: r.bool()?,
        }),
        3 => Ok(ShipState::StrandedEnRoute {
            from: r.u32()?,
            to: r.u32()?,
            distance_ly: r.f64()?,
            progress_ly: r.f64()?,
            purpose: purpose_from(r.u8()?)?,
        }),
        4 => {
            let system = r.u32()?;
            let pending_purpose = match r.u8()? {
                0 => None,
                1 => Some(purpose_from(r.u8()?)?),
                other => {
                    return Err(SimError::InvalidSave(format!(
                        "bad pending-purpose tag {other}"
                    )))
                }
            };
            Ok(ShipState::StrandedAtSystem {
                system,
                pending_purpose,
            })
        }
        other => Err(SimError::InvalidSave(format!("bad ship state {other}"))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::catalog::Galaxy;
    use mwcs_pipeline::table::StarRecord;

    fn galaxy() -> Galaxy {
        Galaxy::from_star_records(vec![StarRecord {
            id: 0,
            pos_ly: [0.0, 0.0, 0.0],
            absmag: 4.8,
            bv: 0.65,
            teff: 5500.0,
            mass: 1.0,
            spectral: 4,
            flags: 0,
            planets: vec![],
            name: "Sol".into(),
        }])
    }

    #[test]
    fn save_round_trip_preserves_hash() {
        let galaxy = galaxy();
        let campaign = Campaign::new_default(&galaxy, 123).unwrap();
        let loaded = Campaign::load_bytes(&galaxy, &campaign.save_bytes()).unwrap();
        assert_eq!(campaign.canonical_bytes(), loaded.canonical_bytes());
        assert_eq!(campaign.state_hash(), loaded.state_hash());
    }
}
