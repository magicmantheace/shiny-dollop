//! Static galaxy data used by the sim core.
//!
//! This is an in-memory view of the S0 star table. Gameplay state is
//! deliberately not stored here: stars remain inert catalog data until
//! the simulation creates sparse per-system state for them.

use std::collections::BTreeMap;
use std::path::Path;

use mwcs_pipeline::sha256::sha256_hex;
use mwcs_pipeline::table::{read_table, StarRecord};

#[derive(Debug, Clone, PartialEq)]
pub struct StaticPlanet {
    pub name: String,
    pub period_days: f32,
    pub semimajor_au: f32,
    pub radius_earth: f32,
    pub mass_earth: f32,
    pub eq_temp_k: f32,
    pub flags: u8,
}

#[derive(Debug, Clone, PartialEq)]
pub struct StaticStar {
    pub id: u32,
    pub name: String,
    pub pos_ly: [f32; 3],
    pub absmag: f32,
    pub bv: f32,
    pub teff_k: f32,
    pub mass_solar: f32,
    pub spectral: u8,
    pub flags: u8,
    pub planets: Vec<StaticPlanet>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Galaxy {
    stars: Vec<StaticStar>,
    by_id: BTreeMap<u32, usize>,
    fingerprint: String,
}

impl Galaxy {
    pub fn from_star_records(records: Vec<StarRecord>) -> Self {
        let stars: Vec<StaticStar> = records
            .into_iter()
            .map(|r| StaticStar {
                id: r.id,
                name: r.name,
                pos_ly: r.pos_ly,
                absmag: r.absmag,
                bv: r.bv,
                teff_k: r.teff,
                mass_solar: r.mass,
                spectral: r.spectral,
                flags: r.flags,
                planets: r
                    .planets
                    .into_iter()
                    .map(|p| StaticPlanet {
                        name: p.name,
                        period_days: p.period_days,
                        semimajor_au: p.semimajor_au,
                        radius_earth: p.radius_earth,
                        mass_earth: p.mass_earth,
                        eq_temp_k: p.eq_temp,
                        flags: p.flags,
                    })
                    .collect(),
            })
            .collect();
        Self::from_static_stars(stars)
    }

    pub fn from_static_stars(mut stars: Vec<StaticStar>) -> Self {
        stars.sort_by_key(|s| s.id);
        let by_id = stars
            .iter()
            .enumerate()
            .map(|(idx, star)| (star.id, idx))
            .collect();
        let fingerprint = fingerprint_stars(&stars);
        Self {
            stars,
            by_id,
            fingerprint,
        }
    }

    pub fn from_table_bytes(bytes: &[u8]) -> Result<Self, String> {
        Ok(Self::from_star_records(read_table(bytes)?))
    }

    pub fn load_table_file(path: impl AsRef<Path>) -> Result<Self, String> {
        let bytes = std::fs::read(path.as_ref())
            .map_err(|e| format!("failed to read {}: {e}", path.as_ref().display()))?;
        Self::from_table_bytes(&bytes)
    }

    pub fn len(&self) -> usize {
        self.stars.len()
    }

    pub fn is_empty(&self) -> bool {
        self.stars.is_empty()
    }

    pub fn stars(&self) -> &[StaticStar] {
        &self.stars
    }

    pub fn star(&self, id: u32) -> Option<&StaticStar> {
        self.by_id.get(&id).map(|idx| &self.stars[*idx])
    }

    pub fn find_by_name(&self, name: &str) -> Option<&StaticStar> {
        self.stars.iter().find(|s| s.name == name)
    }

    pub fn fingerprint(&self) -> &str {
        &self.fingerprint
    }

    pub fn distance_ly(&self, a: u32, b: u32) -> Option<f64> {
        let a = self.star(a)?;
        let b = self.star(b)?;
        Some(distance_between(a.pos_ly, b.pos_ly))
    }
}

pub fn distance_between(a: [f32; 3], b: [f32; 3]) -> f64 {
    let dx = a[0] as f64 - b[0] as f64;
    let dy = a[1] as f64 - b[1] as f64;
    let dz = a[2] as f64 - b[2] as f64;
    (dx * dx + dy * dy + dz * dz).sqrt()
}

fn fingerprint_stars(stars: &[StaticStar]) -> String {
    // Canonical fingerprint of the catalog contents (not of a file's
    // incidental encoding). Save/load uses it to reject a save paired
    // with a different galaxy table.
    let mut bytes = Vec::new();
    for star in stars {
        bytes.extend_from_slice(&star.id.to_le_bytes());
        for v in star.pos_ly {
            bytes.extend_from_slice(&v.to_bits().to_le_bytes());
        }
        bytes.extend_from_slice(&star.absmag.to_bits().to_le_bytes());
        bytes.extend_from_slice(&star.teff_k.to_bits().to_le_bytes());
        bytes.extend_from_slice(&star.mass_solar.to_bits().to_le_bytes());
        bytes.push(star.spectral);
        bytes.push(star.flags);
        bytes.extend_from_slice(&(star.name.len() as u32).to_le_bytes());
        bytes.extend_from_slice(star.name.as_bytes());
        bytes.extend_from_slice(&(star.planets.len() as u32).to_le_bytes());
        for planet in &star.planets {
            bytes.extend_from_slice(&(planet.name.len() as u32).to_le_bytes());
            bytes.extend_from_slice(planet.name.as_bytes());
            bytes.extend_from_slice(&planet.eq_temp_k.to_bits().to_le_bytes());
            bytes.extend_from_slice(&planet.radius_earth.to_bits().to_le_bytes());
        }
    }
    sha256_hex(&bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    use mwcs_pipeline::table::PlanetRecord;

    fn record(id: u32, name: &str, pos: [f32; 3]) -> StarRecord {
        StarRecord {
            id,
            pos_ly: pos,
            absmag: 4.8,
            bv: 0.65,
            teff: 5500.0,
            mass: 1.0,
            spectral: 4,
            flags: 0,
            planets: vec![PlanetRecord {
                name: format!("{name} b"),
                period_days: 365.0,
                semimajor_au: 1.0,
                radius_earth: 1.0,
                mass_earth: 1.0,
                eq_temp: 288.0,
                disc_year: 2020,
                method: 1,
                flags: 0b1111,
            }],
            name: name.into(),
        }
    }

    #[test]
    fn distance_and_lookup() {
        let galaxy = Galaxy::from_star_records(vec![
            record(0, "Sol", [0.0, 0.0, 0.0]),
            record(1, "Near", [3.0, 4.0, 0.0]),
        ]);
        assert_eq!(galaxy.len(), 2);
        assert_eq!(galaxy.find_by_name("Near").unwrap().id, 1);
        assert_eq!(galaxy.distance_ly(0, 1), Some(5.0));
    }
}
