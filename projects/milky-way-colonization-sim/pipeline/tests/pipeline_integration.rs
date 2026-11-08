//! End-to-end pipeline behaviour on committed fixtures: parse → filter
//! → merge (name match, coordinate match, host insertion, skip) →
//! binary write → read-back identical. No network.

use mwcs_pipeline::exo::parse_archive;
use mwcs_pipeline::hyg::parse_hyg;
use mwcs_pipeline::merge::merge;
use mwcs_pipeline::table::{read_table, write_table, FLAG_HAS_PLANETS, FLAG_SOURCE_EXOPLANET_ARCHIVE};

const HYG_FIXTURE: &str = include_str!("fixtures/hyg_fixture.csv");
const EXO_FIXTURE: &str = include_str!("fixtures/exo_fixture.csv");

#[test]
fn full_pipeline_on_fixtures() {
    let hyg = parse_hyg(HYG_FIXTURE);
    assert_eq!(hyg.len(), 5, "fixture HYG rows");
    let archive = parse_archive(EXO_FIXTURE);
    assert_eq!(archive.len(), 7, "fixture archive planet rows");

    let (stars, stats) = merge(&hyg, &archive);
    // 5 HYG rows − 1 placeholder = 4 usable; + 1 inserted host = 5 stars.
    assert_eq!(stats.hyg_rows_total, 5);
    assert_eq!(stats.hyg_rows_usable, 4);
    assert_eq!(stats.archive_systems, 4);
    assert_eq!(stats.hosts_matched_by_name, 1, "Proxima Centauri by name");
    assert_eq!(stats.hosts_matched_by_coords, 1, "SURVEY-9 by position");
    assert_eq!(stats.hosts_inserted, 1, "FARSTAR-7 inserted");
    assert_eq!(stats.hosts_skipped_no_position, 1, "NOPOS-1 skipped");
    assert_eq!(stats.planets_attached, 6);
    assert_eq!(stars.len(), 5);

    let sol = stars.iter().find(|s| s.name == "Sol").unwrap();
    assert_eq!(sol.pos_ly, [0.0, 0.0, 0.0]);

    let proxima = stars.iter().find(|s| s.name == "Proxima Centauri").unwrap();
    assert_eq!(proxima.planets.len(), 2);
    assert!(proxima.flags & FLAG_HAS_PLANETS != 0);
    let d = (proxima.pos_ly[0].powi(2) + proxima.pos_ly[1].powi(2) + proxima.pos_ly[2].powi(2))
        .sqrt();
    assert!((d - 4.2264).abs() < 0.01, "Proxima distance {d} ly");

    let hip_star = stars.iter().find(|s| s.name == "HIP 4242").unwrap();
    assert_eq!(hip_star.planets.len(), 1, "SURVEY-9's planet landed here");
    assert_eq!(hip_star.planets[0].name, "SURVEY-9 b");

    let inserted = stars.iter().find(|s| s.name == "FARSTAR-7").unwrap();
    assert_eq!(inserted.planets.len(), 3);
    assert!(inserted.flags & FLAG_SOURCE_EXOPLANET_ARCHIVE != 0);
    assert_eq!(inserted.teff, 5000.0, "archive-measured teff, not derived");
    assert_eq!(inserted.mass, 0.8, "archive-measured mass");

    // Binary round-trip must be lossless.
    let bytes = write_table(&stars);
    let back = read_table(&bytes).unwrap();
    assert_eq!(stars, back);
}

#[test]
fn placeholder_row_never_reaches_table() {
    let hyg = parse_hyg(HYG_FIXTURE);
    let (stars, _) = merge(&hyg, &[]);
    assert_eq!(stars.len(), 4);
    assert!(stars.iter().all(|s| {
        let d = (s.pos_ly[0].powi(2) + s.pos_ly[1].powi(2) + s.pos_ly[2].powi(2)).sqrt();
        d < 1000.0
    }));
}
