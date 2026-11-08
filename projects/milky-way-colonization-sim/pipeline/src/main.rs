//! milky-way-colonization-sim data pipeline CLI (design §1.6).
//!
//! Usage:
//!   pipeline build [--out DIR] [--cache DIR] [--offline]
//!                  [--hyg-csv PATH] [--exo-csv PATH] [--skip-exo]
//!
//! `build` ingests HYG v4.4 + the NASA Exoplanet Archive pscomppars
//! table, merges them into the game star table, and writes:
//!   <out>/stars.bin       the binary game table (see table.rs)
//!   <out>/manifest.json   counts, source versions, input/output hashes
//!   <out>/SOURCES.md      human-readable provenance + license record
//!
//! Downloads are cached under <cache>/ (default: ./cache beside the
//! working directory). --offline never touches the network and fails
//! if a needed input is not already cached.

use std::path::{Path, PathBuf};
use std::process::Command;

use mwcs_pipeline::exo::parse_archive;
use mwcs_pipeline::hyg::parse_hyg;
use mwcs_pipeline::merge::{merge, MergeStats};
use mwcs_pipeline::sha256::sha256_hex;
use mwcs_pipeline::table::{read_table, write_table, StarRecord};

const HYG_GZ_URL: &str =
    "https://codeberg.org/astronexus/hyg/media/branch/main/data/hyg/CURRENT/hyg_v44.csv.gz";
const HYG_VERSION: &str = "v4.4";
const TAP_URL: &str = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync";
const TAP_QUERY: &str = "SELECT hostname, sy_snum, sy_pnum, sy_dist, ra, dec, \
    st_spectype, st_teff, st_mass, pl_name, pl_letter, pl_orbper, pl_orbsmax, \
    pl_rade, pl_bmasse, pl_eqt, disc_year, discoverymethod FROM pscomppars";

struct Args {
    out: PathBuf,
    cache: PathBuf,
    offline: bool,
    hyg_csv: Option<PathBuf>,
    exo_csv: Option<PathBuf>,
    skip_exo: bool,
}

fn parse_args() -> Result<Args, String> {
    let argv: Vec<String> = std::env::args().collect();
    if argv.len() < 2 || argv[1] != "build" {
        return Err("usage: pipeline build [--out DIR] [--cache DIR] [--offline] \
                    [--hyg-csv PATH] [--exo-csv PATH] [--skip-exo]"
            .into());
    }
    let mut args = Args {
        out: PathBuf::from("../data"),
        cache: PathBuf::from("cache"),
        offline: false,
        hyg_csv: None,
        exo_csv: None,
        skip_exo: false,
    };
    let mut i = 2;
    while i < argv.len() {
        match argv[i].as_str() {
            "--out" => {
                i += 1;
                args.out = PathBuf::from(argv.get(i).ok_or("--out needs a value")?);
            }
            "--cache" => {
                i += 1;
                args.cache = PathBuf::from(argv.get(i).ok_or("--cache needs a value")?);
            }
            "--offline" => args.offline = true,
            "--hyg-csv" => {
                i += 1;
                args.hyg_csv = Some(PathBuf::from(argv.get(i).ok_or("--hyg-csv needs a value")?));
            }
            "--exo-csv" => {
                i += 1;
                args.exo_csv = Some(PathBuf::from(argv.get(i).ok_or("--exo-csv needs a value")?));
            }
            "--skip-exo" => args.skip_exo = true,
            other => return Err(format!("unknown argument: {other}")),
        }
        i += 1;
    }
    Ok(args)
}

fn run(cmd: &mut Command, what: &str) -> Result<(), String> {
    let status = cmd
        .status()
        .map_err(|e| format!("failed to launch {what}: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("{what} exited with {status}"))
    }
}

fn utc_now() -> String {
    Command::new("date")
        .args(["-u", "+%Y-%m-%dT%H:%M:%SZ"])
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_else(|_| "unknown".into())
}

fn ensure_hyg(cache: &Path, offline: bool) -> Result<PathBuf, String> {
    let csv = cache.join("hyg_v44.csv");
    if csv.exists() {
        return Ok(csv);
    }
    let gz = cache.join("hyg_v44.csv.gz");
    if !gz.exists() {
        if offline {
            return Err(format!(
                "HYG not cached at {} and --offline forbids downloading",
                gz.display()
            ));
        }
        std::fs::create_dir_all(cache).map_err(|e| e.to_string())?;
        eprintln!("downloading HYG {HYG_VERSION} …");
        run(
            Command::new("curl").args(["-sSL", "-o"]).arg(&gz).arg(HYG_GZ_URL),
            "curl (HYG download)",
        )?;
    }
    eprintln!("decompressing HYG …");
    let mut cmd = Command::new("gzip");
    cmd.args(["-dc"]).arg(&gz);
    let out = cmd.output().map_err(|e| format!("gzip launch: {e}"))?;
    if !out.status.success() {
        return Err("gzip decompression of HYG failed".into());
    }
    std::fs::write(&csv, &out.stdout).map_err(|e| e.to_string())?;
    Ok(csv)
}

fn ensure_exo(cache: &Path, offline: bool) -> Result<PathBuf, String> {
    let csv = cache.join("pscomppars.csv");
    if csv.exists() {
        return Ok(csv);
    }
    if offline {
        return Err(format!(
            "Exoplanet Archive table not cached at {} and --offline forbids downloading",
            csv.display()
        ));
    }
    std::fs::create_dir_all(cache).map_err(|e| e.to_string())?;
    eprintln!("downloading Exoplanet Archive pscomppars via TAP …");
    run(
        Command::new("curl")
            .args(["-sSL", "-G", TAP_URL])
            .arg("--data-urlencode")
            .arg(format!("query={TAP_QUERY}"))
            .arg("--data-urlencode")
            .arg("format=csv")
            .arg("-o")
            .arg(&csv),
        "curl (TAP download)",
    )?;
    Ok(csv)
}

fn json_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn distance_stats(stars: &[StarRecord]) -> (f64, f64) {
    let mut dists: Vec<f64> = stars
        .iter()
        .map(|s| {
            (s.pos_ly[0] as f64).powi(2)
                + (s.pos_ly[1] as f64).powi(2)
                + (s.pos_ly[2] as f64).powi(2)
        })
        .map(|v| v.sqrt())
        .collect();
    dists.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median = if dists.is_empty() {
        0.0
    } else {
        dists[dists.len() / 2]
    };
    let max = dists.last().copied().unwrap_or(0.0);
    (median, max)
}

fn find_star<'a>(stars: &'a [StarRecord], name: &str) -> Option<&'a StarRecord> {
    stars.iter().find(|s| s.name == name)
}

fn main() {
    let args = match parse_args() {
        Ok(a) => a,
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(2);
        }
    };
    if let Err(e) = real_main(&args) {
        eprintln!("pipeline failed: {e}");
        std::process::exit(1);
    }
}

fn real_main(args: &Args) -> Result<(), String> {
    let hyg_path = match &args.hyg_csv {
        Some(p) => p.clone(),
        None => ensure_hyg(&args.cache, args.offline)?,
    };
    let hyg_bytes = std::fs::read(&hyg_path).map_err(|e| format!("read HYG: {e}"))?;
    let hyg_sha = sha256_hex(&hyg_bytes);
    let hyg_text = String::from_utf8_lossy(&hyg_bytes).into_owned();
    eprintln!("parsing HYG ({:.1} MB) …", hyg_bytes.len() as f64 / 1e6);
    let hyg_rows = parse_hyg(&hyg_text);

    if args.skip_exo {
        let (stars, stats) = merge(&hyg_rows, &[]);
        return finish(args, stars, stats, &hyg_sha, "", "skipped (--skip-exo)");
    }
    let exo_path = match &args.exo_csv {
        Some(p) => p.clone(),
        None => ensure_exo(&args.cache, args.offline)?,
    };
    let exo_bytes = std::fs::read(&exo_path).map_err(|e| format!("read archive: {e}"))?;
    let exo_sha = sha256_hex(&exo_bytes);
    let exo_text = String::from_utf8_lossy(&exo_bytes).into_owned();
    eprintln!("parsing Exoplanet Archive …");
    let archive = parse_archive(&exo_text);
    let (stars, stats) = merge(&hyg_rows, &archive);
    finish(args, stars, stats, &hyg_sha, &exo_sha, "live TAP pull (cached)")
}

fn finish(
    args: &Args,
    stars: Vec<StarRecord>,
    stats: MergeStats,
    hyg_sha: &str,
    exo_sha: &str,
    exo_note: &str,
) -> Result<(), String> {
    let bin = write_table(&stars);
    let bin_sha = sha256_hex(&bin);
    std::fs::create_dir_all(&args.out).map_err(|e| e.to_string())?;
    let bin_path = args.out.join("stars.bin");
    std::fs::write(&bin_path, &bin).map_err(|e| format!("write stars.bin: {e}"))?;

    // Verification pass: read the artifact back and check the anchors
    // the design calls out (§10 S0 spot-checks).
    let back = read_table(&bin).map_err(|e| format!("read-back failed: {e}"))?;
    if back.len() != stars.len() {
        return Err("read-back star count mismatch".into());
    }
    let sol = find_star(&back, "Sol").ok_or("Sol not found in table")?;
    let sol_d = (sol.pos_ly[0].powi(2) + sol.pos_ly[1].powi(2) + sol.pos_ly[2].powi(2)).sqrt();
    if sol_d > 0.01 {
        return Err(format!("Sol is not at the origin (dist {sol_d} ly)"));
    }
    let proxima = find_star(&back, "Proxima Centauri");
    let trappist = back
        .iter()
        .find(|s| s.name.eq_ignore_ascii_case("TRAPPIST-1"));
    let (median_ly, max_ly) = distance_stats(&back);
    let built = utc_now();

    let manifest = format!(
        "{{\n  \"format\": \"mwcs-stars\",\n  \"format_version\": 1,\n  \"built_utc\": \"{built}\",\n  \"pipeline\": \"mwcs-pipeline 0.1.0\",\n  \"sources\": {{\n    \"hyg\": {{\"version\": \"{HYG_VERSION}\", \"url\": \"{}\", \"rows\": {}, \"csv_sha256\": \"{}\"}},\n    \"exoplanet_archive\": {{\"table\": \"pscomppars\", \"note\": \"{}\", \"planet_rows\": {}, \"systems\": {}, \"csv_sha256\": \"{}\"}}\n  }},\n  \"filter\": \"HYG rows with 0 <= dist < 100000 pc (placeholder distances dropped)\",\n  \"frame\": \"heliocentric, galactic axes, light-years\",\n  \"table\": {{\"file\": \"stars.bin\", \"bytes\": {}, \"stars\": {}, \"planets\": {}, \"sha256\": \"{}\"}},\n  \"merge\": {{\"matched_by_name\": {}, \"matched_by_coords\": {}, \"hosts_inserted\": {}, \"hosts_skipped_no_position\": {}}},\n  \"stats\": {{\"hyg_named_proper_usable\": {}, \"stars_with_planets\": {}, \"median_distance_ly\": {:.1}, \"max_distance_ly\": {:.1}}}\n}}\n",
        json_escape(HYG_GZ_URL),
        stats.hyg_rows_total,
        hyg_sha,
        exo_note,
        stats.archive_planet_rows,
        stats.archive_systems,
        exo_sha,
        bin.len(),
        back.len(),
        back.iter().map(|s| s.planets.len()).sum::<usize>(),
        bin_sha,
        stats.hosts_matched_by_name,
        stats.hosts_matched_by_coords,
        stats.hosts_inserted,
        stats.hosts_skipped_no_position,
        stats.hyg_named_proper,
        back.iter().filter(|s| !s.planets.is_empty()).count(),
        median_ly,
        max_ly,
    );
    std::fs::write(args.out.join("manifest.json"), &manifest)
        .map_err(|e| format!("write manifest: {e}"))?;

    let sources_md = format!(
        "# Sources — game star table\n\nBuilt {built} by mwcs-pipeline 0.1.0 (design §1.6 pipeline).\n\n## HYG Database {HYG_VERSION}\n\n- Source: https://codeberg.org/astronexus/hyg (`hyg_v44.csv.gz`)\n- License: **CC BY-SA 4.0** — this derived star table is shared under\n  the same license. Credit: HYG Database (astronexus), merging\n  Hipparcos, Yale Bright Star, and Gliese-Jahreiss catalogs.\n- Input rows: {}; usable after the placeholder-distance filter: {}.\n- Decompressed CSV SHA-256: `{hyg_sha}`\n\n## NASA Exoplanet Archive — pscomppars\n\n- Source: TAP sync service, https://exoplanetarchive.ipac.caltech.edu/TAP\n  ({exo_note}). Planet rows: {}; planetary systems: {}.\n- CSV SHA-256: `{exo_sha}`\n- Acknowledgement: This research has made use of the NASA Exoplanet\n  Archive, which is operated by the California Institute of Technology,\n  under contract with NASA under the Exoplanet Exploration Program.\n\n## Output\n\n- `stars.bin`: {} stars, {} planets attached, {} bytes, SHA-256\n  `{bin_sha}`. Format: see `pipeline/src/table.rs`.\n- Temperature and mass values derived by the pipeline (spectral\n  lookup / mass–luminosity relation) are flagged `derived` per record.\n  Host stars inserted from the Exoplanet Archive are flagged\n  `source: exoplanet-archive`.\n",
        stats.hyg_rows_total,
        stats.hyg_rows_usable,
        stats.archive_planet_rows,
        stats.archive_systems,
        back.len(),
        back.iter().map(|s| s.planets.len()).sum::<usize>(),
        bin.len(),
    );
    std::fs::write(args.out.join("SOURCES.md"), &sources_md)
        .map_err(|e| format!("write SOURCES.md: {e}"))?;

    // ---- Stats report -------------------------------------------------
    println!("== milky-way-colonization-sim pipeline — build report ==");
    println!("HYG {HYG_VERSION} input rows:            {}", stats.hyg_rows_total);
    println!("  dropped (placeholder distance):  {}", stats.hyg_rows_total - stats.hyg_rows_usable);
    println!("  usable stars:                    {}", stats.hyg_rows_usable);
    println!("  with proper names:               {}", stats.hyg_named_proper);
    println!("Exoplanet Archive planet rows:     {}", stats.archive_planet_rows);
    println!("  planetary systems:               {}", stats.archive_systems);
    println!("  hosts matched by designation:    {}", stats.hosts_matched_by_name);
    println!("  hosts matched by coordinates:    {}", stats.hosts_matched_by_coords);
    println!("  hosts inserted (not in HYG):     {}", stats.hosts_inserted);
    println!("  hosts skipped (no position):     {}", stats.hosts_skipped_no_position);
    println!("  planets attached:                {}", stats.planets_attached);
    println!("Final table: {} stars, {} bytes (stars.bin)", back.len(), bin.len());
    println!("Distance from Sol: median {median_ly:.1} ly, max {max_ly:.1} ly");
    if let Some(p) = proxima {
        let d = (p.pos_ly[0].powi(2) + p.pos_ly[1].powi(2) + p.pos_ly[2].powi(2)).sqrt();
        println!("Spot-check: Proxima Centauri at {d:.3} ly (HYG v4.4 distance; modern value 4.246 ly)");
    }
    match trappist {
        Some(t) => println!(
            "Spot-check: TRAPPIST-1 present with {} planets (expected 7)",
            t.planets.len()
        ),
        None => println!("Spot-check: TRAPPIST-1 NOT FOUND — investigate"),
    }
    println!("Read-back verification: OK ({} records round-tripped)", back.len());
    Ok(())
}
