//! Merge the Exoplanet Archive into the HYG star table (design §1.5):
//! hosts are matched to HYG stars by designation first, then by 3D
//! position; unmatched hosts are **inserted** as real rows positioned
//! from the archive's own coordinates (flagged with their source) —
//! no real planetary system is dropped.

use std::collections::HashMap;

use crate::astro;
use crate::derive;
use crate::exo::ArchivePlanet;
use crate::hyg::{to_star_record, HygRow};
use crate::table::{
    StarRecord, FLAG_HAS_PLANETS, FLAG_MASS_DERIVED, FLAG_SOURCE_EXOPLANET_ARCHIVE,
    FLAG_TEMP_DERIVED,
};

/// Coordinate-match tolerance (pc). Archive and HYG distances for the
/// same star routinely differ by ~0.01–0.1 pc; 1 pc is "small" against
/// catalog scales while staying well below typical inter-star spacing
/// outside dense clusters.
pub const COORD_TOLERANCE_PC: f64 = 1.0;
const GRID_CELL_PC: f64 = 2.0;

#[derive(Debug, Default, Clone)]
pub struct MergeStats {
    pub hyg_rows_total: usize,
    pub hyg_rows_usable: usize,
    pub hyg_named_proper: usize,
    pub archive_planet_rows: usize,
    pub archive_systems: usize,
    pub hosts_matched_by_name: usize,
    pub hosts_matched_by_coords: usize,
    pub hosts_inserted: usize,
    pub hosts_skipped_no_position: usize,
    pub planets_attached: usize,
}

/// Normalize a designation for matching: uppercase alphanumerics only.
pub fn normalize_name(s: &str) -> String {
    s.chars()
        .filter(|c| c.is_ascii_alphanumeric())
        .flat_map(|c| c.to_uppercase())
        .collect()
}

fn name_index(rows: &[HygRow], usable: &[usize]) -> HashMap<String, usize> {
    let mut map: HashMap<String, usize> = HashMap::new();
    for (new_idx, &src) in usable.iter().enumerate() {
        let row = &rows[src];
        let mut keys: Vec<String> = Vec::new();
        if !row.proper.is_empty() {
            keys.push(normalize_name(&row.proper));
        }
        if !row.bf.is_empty() {
            keys.push(normalize_name(&row.bf));
        }
        if !row.gl.is_empty() {
            let g = normalize_name(&row.gl);
            keys.push(g.clone());
            // Gliese numbers appear as both "Gl" and "GJ" in the archive.
            if let Some(rest) = g.strip_prefix("GL") {
                keys.push(format!("GJ{rest}"));
            }
        }
        if let Some(hip) = row.hip {
            keys.push(format!("HIP{hip}"));
        }
        if let Some(hd) = row.hd {
            keys.push(format!("HD{hd}"));
        }
        if let Some(hr) = row.hr {
            keys.push(format!("HR{hr}"));
        }
        for k in keys {
            map.entry(k).or_insert(new_idx);
        }
    }
    map
}

struct Grid {
    cells: HashMap<(i32, i32, i32), Vec<usize>>,
}

impl Grid {
    fn build(positions: &[[f64; 3]]) -> Grid {
        let mut cells: HashMap<(i32, i32, i32), Vec<usize>> = HashMap::new();
        for (i, p) in positions.iter().enumerate() {
            cells.entry(cell_of(*p)).or_default().push(i);
        }
        Grid { cells }
    }
    fn nearest_within(&self, positions: &[[f64; 3]], target: [f64; 3], tol: f64) -> Option<usize> {
        let c = cell_of(target);
        let mut best: Option<(usize, f64)> = None;
        for dx in -1..=1 {
            for dy in -1..=1 {
                for dz in -1..=1 {
                    if let Some(list) = self.cells.get(&(c.0 + dx, c.1 + dy, c.2 + dz)) {
                        for &i in list {
                            let d = astro::dist(positions[i], target);
                            if d <= tol && best.map(|(_, bd)| d < bd).unwrap_or(true) {
                                best = Some((i, d));
                            }
                        }
                    }
                }
            }
        }
        best.map(|(i, _)| i)
    }
}

fn cell_of(p: [f64; 3]) -> (i32, i32, i32) {
    (
        (p[0] / GRID_CELL_PC).floor() as i32,
        (p[1] / GRID_CELL_PC).floor() as i32,
        (p[2] / GRID_CELL_PC).floor() as i32,
    )
}

/// Group archive rows by host, preserving first-seen host order;
/// planets within a host sorted by name for determinism.
fn group_hosts(archive: &[ArchivePlanet]) -> Vec<(String, Vec<ArchivePlanet>)> {
    let mut order: Vec<String> = Vec::new();
    let mut by_host: HashMap<String, Vec<ArchivePlanet>> = HashMap::new();
    for row in archive {
        if !by_host.contains_key(&row.hostname) {
            order.push(row.hostname.clone());
        }
        by_host
            .entry(row.hostname.clone())
            .or_default()
            .push(row.clone());
    }
    let mut groups: Vec<(String, Vec<ArchivePlanet>)> = order
        .into_iter()
        .map(|h| {
            let mut planets = by_host.remove(&h).unwrap();
            planets.sort_by(|a, b| a.planet.name.cmp(&b.planet.name));
            (h, planets)
        })
        .collect();
    // Deterministic processing order for insertion: by hostname.
    groups.sort_by(|a, b| a.0.cmp(&b.0));
    groups
}

pub fn merge(hyg_rows: &[HygRow], archive: &[ArchivePlanet]) -> (Vec<StarRecord>, MergeStats) {
    let mut stats = MergeStats {
        hyg_rows_total: hyg_rows.len(),
        archive_planet_rows: archive.len(),
        ..Default::default()
    };
    let usable: Vec<usize> = (0..hyg_rows.len())
        .filter(|&i| crate::hyg::is_usable(&hyg_rows[i]))
        .collect();
    stats.hyg_rows_usable = usable.len();
    stats.hyg_named_proper = usable
        .iter()
        .filter(|&&i| !hyg_rows[i].proper.is_empty())
        .count();

    let mut stars: Vec<StarRecord> = usable
        .iter()
        .enumerate()
        .map(|(new_idx, &src)| to_star_record(&hyg_rows[src], new_idx as u32))
        .collect();
    let eq_positions: Vec<[f64; 3]> = usable.iter().map(|&i| hyg_rows[i].xyz_pc).collect();
    let names = name_index(hyg_rows, &usable);
    let grid = Grid::build(&eq_positions);

    let groups = group_hosts(archive);
    stats.archive_systems = groups.len();

    for (hostname, planets) in &groups {
        let first = &planets[0];
        let planet_records: Vec<_> = planets.iter().map(|p| p.planet.clone()).collect();

        // 1) designation match
        let by_name = names.get(&normalize_name(hostname)).copied();
        if let Some(idx) = by_name {
            attach(&mut stars[idx], planet_records, &mut stats);
            stats.hosts_matched_by_name += 1;
            continue;
        }
        // 2) coordinate match, or 3) insert
        let host_eq = match (first.ra_deg, first.dec_deg, first.sy_dist_pc) {
            (Some(ra), Some(dec), Some(d)) if d > 0.0 => {
                Some(astro::radec_dist_to_eq_pc(ra, dec, d))
            }
            _ => None,
        };
        match host_eq {
            Some(eq) => {
                if let Some(idx) = grid.nearest_within(&eq_positions, eq, COORD_TOLERANCE_PC) {
                    attach(&mut stars[idx], planet_records, &mut stats);
                    stats.hosts_matched_by_coords += 1;
                } else {
                    let rec = inserted_host_record(
                        stars.len() as u32,
                        hostname,
                        first,
                        eq,
                        planet_records,
                        &mut stats,
                    );
                    stars.push(rec);
                    stats.hosts_inserted += 1;
                }
            }
            None => {
                stats.hosts_skipped_no_position += 1;
            }
        }
    }
    (stars, stats)
}

fn attach(star: &mut StarRecord, planets: Vec<crate::table::PlanetRecord>, stats: &mut MergeStats) {
    stats.planets_attached += planets.len();
    star.planets.extend(planets);
    if !star.planets.is_empty() {
        star.flags |= FLAG_HAS_PLANETS;
    }
}

fn inserted_host_record(
    new_id: u32,
    hostname: &str,
    first: &ArchivePlanet,
    eq_pc: [f64; 3],
    planets: Vec<crate::table::PlanetRecord>,
    stats: &mut MergeStats,
) -> StarRecord {
    let gal_ly = astro::eq_pc_to_gal_ly(eq_pc);
    let (class, subclass) = derive::parse_spectral(&first.st_spectype);
    let mut flags = FLAG_SOURCE_EXOPLANET_ARCHIVE | FLAG_HAS_PLANETS;
    // The archive measures teff/mass for many hosts — those are real
    // values, not derivations. Fall back to the spectral derivation for
    // temperature only, and flag it when we do.
    let teff = match first.st_teff {
        Some(t) if t > 0.0 => t,
        _ => match derive::derive_temp(class, subclass) {
            Some(t) => {
                flags |= FLAG_TEMP_DERIVED;
                t
            }
            None => 0.0,
        },
    };
    let mass = first.st_mass.filter(|m| *m > 0.0).unwrap_or(0.0);
    if mass > 0.0 {
        // measured — no flag
    } else {
        let _ = FLAG_MASS_DERIVED; // mass stays 0 = unknown; nothing to flag
    }
    stats.planets_attached += planets.len();
    StarRecord {
        id: new_id,
        pos_ly: [gal_ly[0] as f32, gal_ly[1] as f32, gal_ly[2] as f32],
        absmag: 0.0, // not published in our archive pull — unknown
        bv: 0.0,
        teff,
        mass,
        spectral: derive::spectral_code(class),
        flags,
        planets,
        name: hostname.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::table::PlanetRecord;

    fn hyg_row(id: i64, proper: &str, xyz: [f64; 3], dist: f64) -> HygRow {
        HygRow {
            id,
            hip: None,
            hd: None,
            hr: None,
            gl: String::new(),
            bf: String::new(),
            proper: proper.into(),
            dist_pc: dist,
            absmag: Some(5.0),
            spect: "G2V".into(),
            ci: Some(0.65),
            xyz_pc: xyz,
            comp_primary: String::new(),
            comp: String::new(),
            lum: Some(1.0),
        }
    }

    fn archive_planet(host: &str, ra: f64, dec: f64, dist: f64, planet: &str) -> ArchivePlanet {
        ArchivePlanet {
            hostname: host.into(),
            sy_dist_pc: Some(dist),
            ra_deg: Some(ra),
            dec_deg: Some(dec),
            st_spectype: "M5 V".into(),
            st_teff: Some(2900.0),
            st_mass: Some(0.15),
            planet: PlanetRecord {
                name: planet.into(),
                period_days: 10.0,
                semimajor_au: 0.05,
                radius_earth: 1.0,
                mass_earth: 1.0,
                eq_temp: 250.0,
                disc_year: 2020,
                method: 2,
                flags: 0b1111,
            },
        }
    }

    #[test]
    fn match_by_name_coords_and_insert() {
        // Star A at eq (10,0,0) pc with a proper name; star B anonymous.
        let rows = vec![
            hyg_row(0, "Alpha Testis", [10.0, 0.0, 0.0], 10.0),
            hyg_row(1, "", [50.0, 0.0, 0.0], 50.0),
        ];
        // Host 1 matches by name (coords deliberately absent-ish/far).
        let mut h1 = archive_planet("Alpha Testis", 0.0, 0.0, 999.0, "Alpha Testis b");
        h1.sy_dist_pc = Some(999.0);
        // Host 2: unknown designation, coords land on star B.
        // ra/dec for eq (50,0,0): ra=0, dec=0, dist=50.
        let h2 = archive_planet("SURVEY-42", 0.0, 0.0, 50.0, "SURVEY-42 b");
        // Host 3: nowhere near anything → inserted. ra=90, dec=0, dist=500 → eq (0,500,0).
        let h3 = archive_planet("FARAWAY-1", 90.0, 0.0, 500.0, "FARAWAY-1 b");
        let (stars, stats) = merge(&rows, &[h1, h2, h3]);
        assert_eq!(stats.hosts_matched_by_name, 1);
        assert_eq!(stats.hosts_matched_by_coords, 1);
        assert_eq!(stats.hosts_inserted, 1);
        assert_eq!(stats.planets_attached, 3);
        assert_eq!(stars.len(), 3);
        assert_eq!(stars[0].planets.len(), 1);
        assert_eq!(stars[1].planets.len(), 1);
        let inserted = &stars[2];
        assert_eq!(inserted.name, "FARAWAY-1");
        assert!(inserted.flags & FLAG_SOURCE_EXOPLANET_ARCHIVE != 0);
        assert!(inserted.flags & FLAG_HAS_PLANETS != 0);
        // Inserted position: eq (0,500,0) pc rotated — norm must stay 500 pc in ly.
        let n = (inserted.pos_ly[0].powi(2) + inserted.pos_ly[1].powi(2) + inserted.pos_ly[2].powi(2))
            .sqrt();
        assert!((n - 500.0 * astro::PC_TO_LY as f32).abs() < 1.0, "norm {n}");
    }

    #[test]
    fn host_without_position_is_skipped_not_dropped_silently() {
        let rows = vec![hyg_row(0, "Solo", [1.0, 0.0, 0.0], 1.0)];
        let mut h = archive_planet("NOPOS", 0.0, 0.0, 0.0, "NOPOS b");
        h.sy_dist_pc = None;
        let (stars, stats) = merge(&rows, &[h]);
        assert_eq!(stats.hosts_skipped_no_position, 1);
        assert_eq!(stars.len(), 1);
        assert_eq!(stats.planets_attached, 0);
    }
}
