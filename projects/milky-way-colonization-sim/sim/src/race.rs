//! AI race generation for S3 (design §6): personalities drawn from
//! hand-written archetypes with seeded jitter, species names generated
//! from the campaign seed, and homeworld placement by the §6.1
//! fairness algorithm.
//!
//! Everything in this module is a pure function of the campaign seed
//! and the static catalog: the same seed and galaxy always produce
//! the same races on the same homeworlds, so a multi-civilization
//! campaign is exactly as deterministic as the S1 solo campaign.

use std::collections::HashMap;

use crate::catalog::Galaxy;
use crate::profile::profile_for_star;
use crate::rng::SeededRng;
use crate::state::StarId;

/// Design §11.3 ruling: 12 AI civilizations + the player by default.
pub const DEFAULT_AI_COUNT: usize = 12;
/// The design's setup slider is 4–40 civilizations in total
/// (§6.1/§11.3), so at most 39 of them are AI.
pub const MAX_AI_COUNT: usize = 39;

/// A civilization's drives (design §6.2), each in `[0, 1]`.
/// Personality drives what an AI claims, what it contests, and (from
/// S4) what it offers and whether its treaties hold.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Personality {
    pub expansion: f64,
    pub aggression: f64,
    pub trade_affinity: f64,
    pub xenophobia: f64,
    pub honour: f64,
}

impl Personality {
    pub(crate) fn clamped(self) -> Self {
        Self {
            expansion: self.expansion.clamp(0.0, 1.0),
            aggression: self.aggression.clamp(0.0, 1.0),
            trade_affinity: self.trade_affinity.clamp(0.0, 1.0),
            xenophobia: self.xenophobia.clamp(0.0, 1.0),
            honour: self.honour.clamp(0.0, 1.0),
        }
    }
}

/// One hand-written archetype (design §6.2): a named centre that
/// per-game personalities jitter around.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Archetype {
    pub name: &'static str,
    pub expansion: f64,
    pub aggression: f64,
    pub trade_affinity: f64,
    pub xenophobia: f64,
    pub honour: f64,
}

impl Archetype {
    fn centre(&self) -> Personality {
        Personality {
            expansion: self.expansion,
            aggression: self.aggression,
            trade_affinity: self.trade_affinity,
            xenophobia: self.xenophobia,
            honour: self.honour,
        }
    }
}

pub const ARCHETYPES: &[Archetype] = &[
    Archetype {
        name: "Merchant League",
        expansion: 0.55,
        aggression: 0.15,
        trade_affinity: 0.95,
        xenophobia: 0.15,
        honour: 0.80,
    },
    Archetype {
        name: "Hive Expansionist",
        expansion: 0.95,
        aggression: 0.55,
        trade_affinity: 0.20,
        xenophobia: 0.60,
        honour: 0.40,
    },
    Archetype {
        name: "Honourable Warriors",
        expansion: 0.50,
        aggression: 0.80,
        trade_affinity: 0.30,
        xenophobia: 0.35,
        honour: 0.95,
    },
    Archetype {
        name: "Isolationist Gardeners",
        expansion: 0.20,
        aggression: 0.10,
        trade_affinity: 0.35,
        xenophobia: 0.80,
        honour: 0.70,
    },
    Archetype {
        name: "Opportunist Raiders",
        expansion: 0.65,
        aggression: 0.70,
        trade_affinity: 0.45,
        xenophobia: 0.45,
        honour: 0.25,
    },
    Archetype {
        name: "Scholarly Federation",
        expansion: 0.60,
        aggression: 0.20,
        trade_affinity: 0.60,
        xenophobia: 0.25,
        honour: 0.75,
    },
];

const NAME_A: &[&str] = &[
    "Vel", "Kor", "Tha", "Mir", "Os", "Run", "Zel", "An", "Tor", "Ka", "Sel", "Ur", "Ith", "Vor",
    "Nyx", "Hal",
];
const NAME_B: &[&str] = &[
    "ari", "eth", "omi", "kar", "esh", "une", "ath", "ira", "on", "ek", "asi", "ur", "im", "ox",
    "el", "is",
];

/// The generated identity of one AI civilization, before it is
/// placed into a campaign.
#[derive(Debug, Clone, PartialEq)]
pub struct AiCivSpec {
    pub name: String,
    pub archetype: &'static str,
    pub personality: Personality,
    pub home_system: StarId,
    /// True when the star's natural (seeded) profile fell below the
    /// homeworld habitability bar and setup granted the standard
    /// homeworld profile anyway — design §6.1's "galaxy's first lie,
    /// told openly", recorded here instead of hidden.
    pub homeworld_adjusted: bool,
}

fn race_stream(seed: u64, civ_index: u32) -> SeededRng {
    SeededRng::child_for_star(seed ^ 0x5241_4345_5F47_454E, civ_index)
}

/// Draw the archetype + jittered personality + unique species name
/// for AI civilization `civ_index` (1-based civilization id). `taken`
/// holds species names already used by earlier civilizations.
fn generate_identity(seed: u64, civ_index: u32, taken: &[String]) -> (String, Archetype, Personality) {
    let mut rng = race_stream(seed, civ_index);
    // Archetypes cycle in a seeded order so a 12-civ game fields the
    // full spread of agendas instead of twelve draws of one kind.
    let archetype = ARCHETYPES[(civ_index as usize - 1) % ARCHETYPES.len()];
    let jitter = |rng: &mut SeededRng, centre: f64| centre + (rng.next_f64() * 0.24 - 0.12);
    let personality = Personality {
        expansion: jitter(&mut rng, archetype.expansion),
        aggression: jitter(&mut rng, archetype.aggression),
        trade_affinity: jitter(&mut rng, archetype.trade_affinity),
        xenophobia: jitter(&mut rng, archetype.xenophobia),
        honour: jitter(&mut rng, archetype.honour),
    }
    .clamped();
    let species = loop {
        let a = NAME_A[rng.next_below(NAME_A.len() as u64) as usize];
        let b = NAME_B[rng.next_below(NAME_B.len() as u64) as usize];
        let candidate = format!("{a}{b}");
        if !taken.iter().any(|t| t == &candidate) {
            break candidate;
        }
    };
    (species, archetype, personality)
}

/// Placement rules for AI homeworlds (design §6.1). The defaults are
/// the design's numbers; tests and small synthetic galaxies override
/// them.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct HomeworldRules {
    /// Homeworlds live inside the Mapped Region (§1.4): this radius
    /// around the player's home star.
    pub region_radius_ly: f64,
    /// Minimum pairwise homeworld distance (§6.1 asks for ≥ 250 ly;
    /// placement relaxes down a fixed ladder if the region cannot
    /// satisfy it, and reports the spacing actually used).
    pub min_spacing_ly: f64,
    /// A homeworld candidate's natural profile must reach this
    /// habitability (the setup guarantee then tops it up to the
    /// standard homeworld profile).
    pub min_habitability: f64,
    /// "Comparable local star density" (§6.1): candidates whose
    /// 100-ly neighbourhood count falls outside
    /// `[lo × median, hi × median]` are dropped before selection.
    pub density_band: (f64, f64),
}

impl Default for HomeworldRules {
    fn default() -> Self {
        Self {
            region_radius_ly: 1_000.0,
            min_spacing_ly: 250.0,
            min_habitability: 40.0,
            density_band: (0.4, 2.5),
        }
    }
}

/// The outcome of homeworld selection.
#[derive(Debug, Clone, PartialEq)]
pub struct HomeworldSelection {
    pub homes: Vec<StarId>,
    /// The spacing the ladder actually achieved (≤ the requested
    /// minimum when relaxation was needed).
    pub spacing_used_ly: f64,
}

/// Spectral codes for G, K, M (pipeline `derive.rs`): the §6.1
/// candidate classes.
fn is_candidate_class(spectral: u8) -> bool {
    matches!(spectral, 4 | 5 | 6)
}

/// Count stars within `radius` of each candidate, using a uniform
/// grid so a 113k-star catalog stays cheap. Counts are order-free,
/// so the grid's hash iteration order cannot leak into results.
fn neighbourhood_counts(
    galaxy: &Galaxy,
    candidates: &[StarId],
    radius: f64,
) -> Vec<usize> {
    let cell = radius.max(1.0);
    let key_of = |pos: [f32; 3]| -> (i32, i32, i32) {
        (
            (pos[0] as f64 / cell).floor() as i32,
            (pos[1] as f64 / cell).floor() as i32,
            (pos[2] as f64 / cell).floor() as i32,
        )
    };
    let mut grid: HashMap<(i32, i32, i32), Vec<usize>> = HashMap::new();
    for (idx, star) in galaxy.stars().iter().enumerate() {
        grid.entry(key_of(star.pos_ly)).or_default().push(idx);
    }
    let radius_sq = radius * radius;
    candidates
        .iter()
        .map(|&id| {
            let star = galaxy.star(id).expect("candidate exists");
            let (cx, cy, cz) = key_of(star.pos_ly);
            let mut count = 0usize;
            for dx in -1..=1 {
                for dy in -1..=1 {
                    for dz in -1..=1 {
                        if let Some(bucket) = grid.get(&(cx + dx, cy + dy, cz + dz)) {
                            for &idx in bucket {
                                let other = &galaxy.stars()[idx];
                                if other.id == id {
                                    continue;
                                }
                                let ddx = other.pos_ly[0] as f64 - star.pos_ly[0] as f64;
                                let ddy = other.pos_ly[1] as f64 - star.pos_ly[1] as f64;
                                let ddz = other.pos_ly[2] as f64 - star.pos_ly[2] as f64;
                                if ddx * ddx + ddy * ddy + ddz * ddz <= radius_sq {
                                    count += 1;
                                }
                            }
                        }
                    }
                }
            }
            count
        })
        .collect()
}

/// Select `count` AI homeworlds by the §6.1 fairness algorithm:
/// G/K/M stars with habitable natural profiles inside the mapped
/// region, comparable local density, spaced as far apart as the
/// region allows. Deterministic in `(galaxy, seed, excluded)`.
pub fn select_homeworlds(
    galaxy: &Galaxy,
    seed: u64,
    player_home: StarId,
    count: usize,
    rules: &HomeworldRules,
) -> HomeworldSelection {
    if count == 0 {
        return HomeworldSelection {
            homes: Vec::new(),
            spacing_used_ly: rules.min_spacing_ly,
        };
    }
    let origin = galaxy
        .star(player_home)
        .map(|s| s.pos_ly)
        .unwrap_or([0.0, 0.0, 0.0]);

    // Candidate pool: right spectral class, inside the region, not
    // the player's home, and naturally habitable enough to start on.
    let mut candidates: Vec<StarId> = Vec::new();
    for star in galaxy.stars() {
        if star.id == player_home || !is_candidate_class(star.spectral) {
            continue;
        }
        if crate::catalog::distance_between(origin, star.pos_ly) > rules.region_radius_ly {
            continue;
        }
        if profile_for_star(seed, star).habitability_percent < rules.min_habitability {
            continue;
        }
        candidates.push(star.id);
    }

    // Comparable-density filter (§6.1: nobody starts in a void or a
    // cluster core). Skipped when it would starve the pool.
    if candidates.len() > count {
        let counts = neighbourhood_counts(galaxy, &candidates, 100.0);
        let mut sorted = counts.clone();
        sorted.sort_unstable();
        let median = sorted[sorted.len() / 2] as f64;
        if median > 0.0 {
            let (lo, hi) = rules.density_band;
            let filtered: Vec<StarId> = candidates
                .iter()
                .zip(counts.iter())
                .filter(|(_, c)| {
                    let c = **c as f64;
                    c >= lo * median && c <= hi * median
                })
                .map(|(id, _)| *id)
                .collect();
            if filtered.len() >= count {
                candidates = filtered;
            }
        }
    }

    // Seeded shuffle, then greedy spacing down a relaxation ladder.
    let mut rng = SeededRng::new(seed ^ 0x484F_4D45_5F50_4943);
    for i in (1..candidates.len()).rev() {
        let j = rng.next_below((i + 1) as u64) as usize;
        candidates.swap(i, j);
    }
    let ladder = [
        rules.min_spacing_ly,
        rules.min_spacing_ly * 0.8,
        rules.min_spacing_ly * 0.6,
        rules.min_spacing_ly * 0.4,
        rules.min_spacing_ly * 0.24,
        rules.min_spacing_ly * 0.12,
        0.0,
    ];
    let mut picked: Vec<StarId> = Vec::new();
    let mut spacing_used = 0.0;
    for &spacing in &ladder {
        picked.clear();
        'next: for &id in &candidates {
            if picked.len() >= count {
                break;
            }
            let pos = galaxy.star(id).expect("candidate exists").pos_ly;
            if crate::catalog::distance_between(origin, pos) < spacing {
                continue;
            }
            for &other in &picked {
                let other_pos = galaxy.star(other).expect("picked exists").pos_ly;
                if crate::catalog::distance_between(pos, other_pos) < spacing {
                    continue 'next;
                }
            }
            picked.push(id);
        }
        spacing_used = spacing;
        if picked.len() >= count {
            break;
        }
    }
    HomeworldSelection {
        homes: picked,
        spacing_used_ly: spacing_used,
    }
}

/// Generate the full AI roster for a new game: identities plus
/// placed homeworlds. Returns fewer specs than requested when the
/// galaxy cannot place that many homeworlds; the caller decides
/// whether that is an error.
pub fn generate_ai_civs(
    galaxy: &Galaxy,
    seed: u64,
    player_home: StarId,
    count: usize,
    rules: &HomeworldRules,
) -> (Vec<AiCivSpec>, f64) {
    let selection = select_homeworlds(galaxy, seed, player_home, count, rules);
    let mut taken: Vec<String> = Vec::new();
    let mut specs = Vec::with_capacity(selection.homes.len());
    for (i, &home) in selection.homes.iter().enumerate() {
        let civ_index = (i + 1) as u32;
        let (species, archetype, personality) = generate_identity(seed, civ_index, &taken);
        taken.push(species.clone());
        let adjusted = profile_for_star(seed, galaxy.star(home).expect("home exists"))
            .habitability_percent
            < 60.0;
        specs.push(AiCivSpec {
            name: format!("{species} {}", archetype.name),
            archetype: archetype.name,
            personality,
            home_system: home,
            homeworld_adjusted: adjusted,
        });
    }
    (specs, selection.spacing_used_ly)
}

#[cfg(test)]
mod tests {
    use super::*;
    use mwcs_pipeline::table::{PlanetRecord, StarRecord};

    fn record(id: u32, name: &str, pos: [f32; 3], spectral: u8) -> StarRecord {
        StarRecord {
            id,
            pos_ly: pos,
            absmag: 4.8,
            bv: 0.65,
            teff: 5200.0,
            mass: 1.0,
            spectral,
            flags: 0,
            planets: vec![PlanetRecord {
                name: format!("{name} b"),
                period_days: 365.0,
                semimajor_au: 1.0,
                radius_earth: 1.0,
                mass_earth: 1.0,
                eq_temp: 273.0,
                disc_year: 2024,
                method: 2,
                flags: 0b1111,
            }],
            name: name.into(),
        }
    }

    fn galaxy() -> Galaxy {
        // Sol plus a loose ring of K stars 300 ly out.
        let mut records = vec![record(0, "Sol", [0.0, 0.0, 0.0], 4)];
        for i in 0..8u32 {
            let angle = (i as f64) * std::f64::consts::FRAC_PI_4;
            records.push(record(
                i + 1,
                &format!("Ring {i}"),
                [
                    (300.0 * angle.cos()) as f32,
                    (300.0 * angle.sin()) as f32,
                    0.0,
                ],
                5,
            ));
        }
        Galaxy::from_star_records(records)
    }

    #[test]
    fn placement_is_deterministic_and_spaced() {
        let galaxy = galaxy();
        let rules = HomeworldRules::default();
        let a = select_homeworlds(&galaxy, 42, 0, 4, &rules);
        let b = select_homeworlds(&galaxy, 42, 0, 4, &rules);
        assert_eq!(a, b);
        assert_eq!(a.homes.len(), 4);
        assert!(!a.homes.contains(&0));
        for (i, &h) in a.homes.iter().enumerate() {
            for &o in &a.homes[i + 1..] {
                assert!(galaxy.distance_ly(h, o).unwrap() >= a.spacing_used_ly - 1e-9);
            }
            assert!(galaxy.distance_ly(0, h).unwrap() >= a.spacing_used_ly - 1e-9);
        }
    }

    #[test]
    fn identities_are_unique_and_personalities_in_range() {
        let galaxy = galaxy();
        let (specs, _) = generate_ai_civs(&galaxy, 7, 0, 6, &HomeworldRules::default());
        assert_eq!(specs.len(), 6);
        let mut names: Vec<&str> = specs.iter().map(|s| s.name.as_str()).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), 6, "names must be unique: {names:?}");
        for spec in &specs {
            let p = spec.personality;
            for v in [p.expansion, p.aggression, p.trade_affinity, p.xenophobia, p.honour] {
                assert!((0.0..=1.0).contains(&v), "personality component {v}");
            }
        }
    }
}
