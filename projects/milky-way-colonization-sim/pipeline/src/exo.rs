//! NASA Exoplanet Archive `pscomppars` ingest (one row per planet,
//! composite/best parameters). Pulled via the TAP sync service.

use crate::csv::{col, get, parse_csv, parse_f32, parse_f64, parse_i64};
use crate::table::{method_code, PlanetRecord};

#[derive(Debug, Clone)]
pub struct ArchivePlanet {
    pub hostname: String,
    pub sy_dist_pc: Option<f64>,
    pub ra_deg: Option<f64>,
    pub dec_deg: Option<f64>,
    pub st_spectype: String,
    pub st_teff: Option<f32>,
    pub st_mass: Option<f32>,
    pub planet: PlanetRecord,
}

pub fn parse_archive(text: &str) -> Vec<ArchivePlanet> {
    let rows = parse_csv(text);
    assert!(!rows.is_empty(), "archive CSV is empty");
    let header = &rows[0];
    let c_host = col(header, "hostname");
    let c_dist = col(header, "sy_dist");
    let c_ra = col(header, "ra");
    let c_dec = col(header, "dec");
    let c_spect = col(header, "st_spectype");
    let c_teff = col(header, "st_teff");
    let c_mass = col(header, "st_mass");
    let c_plname = col(header, "pl_name");
    let c_period = col(header, "pl_orbper");
    let c_sma = col(header, "pl_orbsmax");
    let c_rade = col(header, "pl_rade");
    let c_bmasse = col(header, "pl_bmasse");
    let c_eqt = col(header, "pl_eqt");
    let c_year = col(header, "disc_year");
    let c_method = col(header, "discoverymethod");

    let mut out = Vec::with_capacity(rows.len());
    for row in &rows[1..] {
        if row.len() < header.len() {
            continue;
        }
        let hostname = get(row, c_host).trim().to_string();
        let pl_name = get(row, c_plname).trim().to_string();
        if hostname.is_empty() || pl_name.is_empty() {
            continue;
        }
        let period = parse_f32(get(row, c_period));
        let sma = parse_f32(get(row, c_sma));
        let rade = parse_f32(get(row, c_rade));
        let bmasse = parse_f32(get(row, c_bmasse));
        let mut pflags = 0u8;
        if rade.is_some() {
            pflags |= 1 << 0;
        }
        if bmasse.is_some() {
            pflags |= 1 << 1;
        }
        if period.is_some() {
            pflags |= 1 << 2;
        }
        if sma.is_some() {
            pflags |= 1 << 3;
        }
        out.push(ArchivePlanet {
            hostname,
            sy_dist_pc: parse_f64(get(row, c_dist)),
            ra_deg: parse_f64(get(row, c_ra)),
            dec_deg: parse_f64(get(row, c_dec)),
            st_spectype: get(row, c_spect).trim().to_string(),
            st_teff: parse_f32(get(row, c_teff)),
            st_mass: parse_f32(get(row, c_mass)),
            planet: PlanetRecord {
                name: pl_name,
                period_days: period.unwrap_or(0.0),
                semimajor_au: sma.unwrap_or(0.0),
                radius_earth: rade.unwrap_or(0.0),
                mass_earth: bmasse.unwrap_or(0.0),
                eq_temp: parse_f32(get(row, c_eqt)).unwrap_or(0.0),
                disc_year: parse_i64(get(row, c_year))
                    .and_then(|y| u16::try_from(y).ok())
                    .unwrap_or(0),
                method: method_code(get(row, c_method)),
                flags: pflags,
            },
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_one_row() {
        let text = "hostname,sy_snum,sy_pnum,sy_dist,ra,dec,st_spectype,st_teff,st_mass,pl_name,pl_letter,pl_orbper,pl_orbsmax,pl_rade,pl_bmasse,pl_eqt,disc_year,discoverymethod\n\
                    \"55 Cnc\",2,7,12.5855,133.1468373,28.3298154,\"G8 V\",5198.00,1.015,\"55 Cnc b\",\"b\",14.651552,0.118,13.9,263.9785,700,1996,\"Radial Velocity\"\n";
        let rows = parse_archive(text);
        assert_eq!(rows.len(), 1);
        let r = &rows[0];
        assert_eq!(r.hostname, "55 Cnc");
        assert_eq!(r.planet.name, "55 Cnc b");
        assert_eq!(r.planet.method, 1);
        assert_eq!(r.planet.disc_year, 1996);
        assert_eq!(r.planet.flags, 0b1111);
        assert!((r.sy_dist_pc.unwrap() - 12.5855).abs() < 1e-9);
    }
}
