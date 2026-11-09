//! Deterministic per-system profiles revealed by surveys.
//!
//! Real exoplanets in the S0 table stay real. Systems without catalog
//! planets receive a generated profile from the host star's catalog
//! properties and the campaign seed (design founding decision 4).
//! Generated planets are explicitly marked as generated; they are not
//! catalog data.

use crate::catalog::StaticStar;
use crate::rng::SeededRng;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PlanetSource {
    RealCatalog,
    Generated,
    HomeworldSetup,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PlanetProfile {
    pub name: String,
    pub source: PlanetSource,
    pub habitability_percent: f64,
    pub eq_temp_k: f32,
    pub radius_earth: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SystemProfile {
    pub habitability_percent: f64,
    pub fuel_trait: f64,
    pub industry_trait: f64,
    pub exotics_trait: f64,
    pub planets: Vec<PlanetProfile>,
}

impl SystemProfile {
    pub fn homeworld() -> Self {
        Self::homeworld_named("Earth".into())
    }

    /// The §6.1/§11.7 homeworld guarantee for a named world: an AI
    /// civilization's home planet carries its own name ("<star>
    /// Prime"), with the same guaranteed habitability and traits as
    /// the player's Earth.
    pub fn homeworld_named(planet_name: String) -> Self {
        Self {
            habitability_percent: 95.0,
            fuel_trait: 1.0,
            industry_trait: 1.0,
            exotics_trait: 0.0,
            planets: vec![PlanetProfile {
                name: planet_name,
                source: PlanetSource::HomeworldSetup,
                habitability_percent: 95.0,
                eq_temp_k: 288.0,
                radius_earth: 1.0,
            }],
        }
    }
}

/// Generate (or derive from real catalog planets) the fixed profile
/// for `star`. This is a pure function of the campaign seed and star.
pub fn profile_for_star(seed: u64, star: &StaticStar) -> SystemProfile {
    let mut rng = SeededRng::child_for_star(seed, star.id);
    if !star.planets.is_empty() {
        profile_from_real_planets(star, &mut rng)
    } else {
        profile_generated(star, &mut rng)
    }
}

fn profile_from_real_planets(star: &StaticStar, rng: &mut SeededRng) -> SystemProfile {
    let mut planets = Vec::with_capacity(star.planets.len());
    let mut best: f64 = 0.0;
    let mut has_gas_giant = false;

    for planet in &star.planets {
        if planet.radius_earth > 6.0 || planet.mass_earth > 50.0 {
            has_gas_giant = true;
        }
        let eq_temp = if planet.eq_temp_k > 0.0 {
            planet.eq_temp_k
        } else if planet.semimajor_au > 0.0 {
            estimated_eq_temp_k(star, planet.semimajor_au)
        } else {
            0.0
        };
        let habitability = real_planet_habitability(eq_temp, planet.radius_earth);
        best = best.max(habitability);
        planets.push(PlanetProfile {
            name: planet.name.clone(),
            source: PlanetSource::RealCatalog,
            habitability_percent: habitability,
            eq_temp_k: eq_temp,
            radius_earth: planet.radius_earth,
        });
    }

    SystemProfile {
        habitability_percent: best.clamp(0.0, 98.0),
        fuel_trait: if has_gas_giant {
            1.65
        } else {
            0.75 + planets.len() as f64 * 0.05
        },
        industry_trait: 0.6 + rng.next_f64() * 0.7,
        exotics_trait: if rng.next_below(17) == 0 { 0.25 } else { 0.0 },
        planets,
    }
}

fn profile_generated(star: &StaticStar, rng: &mut SeededRng) -> SystemProfile {
    let count = match rng.next_below(100) {
        0..=7 => 0,
        8..=24 => 1,
        25..=49 => 2,
        50..=69 => 3,
        70..=84 => 4,
        85..=93 => 5,
        94..=97 => 6,
        _ => 7,
    };
    let stellar_base = if star.teff_k > 0.0 {
        (100.0 - ((star.teff_k as f64 - 5_200.0).abs() / 55.0)).clamp(4.0, 90.0)
    } else {
        match star.spectral {
            4 => 78.0, // G
            5 => 72.0, // K
            3 => 58.0, // F
            6 => 42.0, // M: many worlds, harsher stellar environment
            2 => 35.0, // A
            _ => 18.0,
        }
    };

    let mut planets = Vec::with_capacity(count);
    let mut best: f64 = 0.0;
    let mut has_gas_giant = false;
    for i in 0..count {
        let gas_giant = rng.next_below(100) < 18;
        if gas_giant {
            has_gas_giant = true;
        }
        let habitability = if gas_giant {
            (stellar_base * 0.15 + rng.next_f64() * 8.0).clamp(0.0, 25.0)
        } else {
            (stellar_base + (rng.next_f64() * 36.0 - 18.0)).clamp(0.0, 96.0)
        };
        best = best.max(habitability);
        let radius = if gas_giant {
            6.0 + rng.next_f64() * 8.0
        } else {
            0.4 + rng.next_f64() * 2.2
        };
        planets.push(PlanetProfile {
            name: format!("{} generated {}", star.name, i + 1),
            source: PlanetSource::Generated,
            habitability_percent: habitability,
            eq_temp_k: (180.0 + rng.next_f64() * 260.0) as f32,
            radius_earth: radius as f32,
        });
    }

    SystemProfile {
        habitability_percent: best,
        fuel_trait: if has_gas_giant {
            1.55
        } else {
            0.4 + rng.next_f64() * 0.8
        },
        industry_trait: 0.5 + rng.next_f64() * 1.0,
        exotics_trait: if rng.next_below(20) == 0 { 0.3 } else { 0.0 },
        planets,
    }
}

fn estimated_eq_temp_k(star: &StaticStar, semimajor_au: f32) -> f32 {
    if star.absmag <= 0.0 || semimajor_au <= 0.0 {
        return 0.0;
    }
    // Solar absolute magnitude 4.83; equilibrium temperature scales as
    // 278 K * L^(1/4) / sqrt(distance in AU).
    let luminosity = 10f64.powf((4.83 - star.absmag as f64) / 2.5);
    (278.0 * luminosity.powf(0.25) / (semimajor_au as f64).sqrt()) as f32
}

fn real_planet_habitability(eq_temp_k: f32, radius_earth: f32) -> f64 {
    if eq_temp_k <= 0.0 {
        return 30.0;
    }
    let temp_score = (100.0 - ((eq_temp_k as f64 - 273.0).abs() / 1.35)).clamp(0.0, 100.0);
    let radius_score = if radius_earth > 0.0 {
        (100.0 - ((radius_earth as f64 - 1.0).abs() * 55.0)).clamp(0.0, 100.0)
    } else {
        55.0
    };
    temp_score * 0.75 + radius_score * 0.25
}

/// Deterministic survey duration. It is known when a survey starts,
/// while the profile itself is revealed only on completion.
pub fn survey_duration_days(seed: u64, star: &StaticStar) -> u32 {
    let mut rng = SeededRng::child_for_star(seed ^ 0x5355_5256_4559_4c4c, star.id);
    24 + rng.next_below(14) as u32 + (star.planets.len().min(8) as u32) * 2
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::catalog::{Galaxy, StaticPlanet};
    use mwcs_pipeline::table::{PlanetRecord, StarRecord};

    fn star(id: u32, with_planet: bool) -> StaticStar {
        let planets = if with_planet {
            vec![PlanetRecord {
                name: "Kepler test b".into(),
                period_days: 300.0,
                semimajor_au: 1.0,
                radius_earth: 1.0,
                mass_earth: 1.0,
                eq_temp: 273.0,
                disc_year: 2020,
                method: 2,
                flags: 0b1111,
            }]
        } else {
            vec![]
        };
        let galaxy = Galaxy::from_star_records(vec![StarRecord {
            id,
            pos_ly: [id as f32, 0.0, 0.0],
            absmag: 4.8,
            bv: 0.65,
            teff: 5500.0,
            mass: 1.0,
            spectral: 4,
            flags: 0,
            planets,
            name: format!("Star {id}"),
        }]);
        galaxy.star(id).unwrap().clone()
    }

    #[test]
    fn real_planets_stay_real_and_score_habitable() {
        let profile = profile_for_star(99, &star(1, true));
        assert_eq!(profile.planets[0].source, PlanetSource::RealCatalog);
        assert!(profile.habitability_percent > 90.0);
        let _ = StaticPlanet {
            name: "unused".into(),
            period_days: 0.0,
            semimajor_au: 0.0,
            radius_earth: 0.0,
            mass_earth: 0.0,
            eq_temp_k: 0.0,
            flags: 0,
        };
    }

    #[test]
    fn generated_profiles_are_repeatable_and_labelled() {
        let a = profile_for_star(5, &star(9, false));
        let b = profile_for_star(5, &star(9, false));
        assert_eq!(a, b);
        assert!(a
            .planets
            .iter()
            .all(|p| p.source == PlanetSource::Generated));
    }
}
