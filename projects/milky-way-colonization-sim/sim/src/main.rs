//! `sim-cli` — the headless campaign demo (S1; S3 added `--ai`).
//!
//! Usage:
//!   sim-cli [--data PATH] [--seed N] [--years N] [--ai N]
//!
//! Starts a campaign at Sol, drives the player with the
//! deterministic scripted policy, and prints one summary line per
//! game year. With `--ai N`, the campaign is set up with N AI
//! civilizations (design §6) that expand under the same rules; the
//! yearly line gains galaxy-wide totals.

use mwcs_sim::policy::ScriptedPolicy;
use mwcs_sim::{Campaign, Galaxy, GameSetup, DAYS_PER_YEAR};

struct Args {
    data: String,
    seed: u64,
    years: u64,
    ai: Option<usize>,
}

fn parse_args() -> Result<Args, String> {
    let argv: Vec<String> = std::env::args().collect();
    let mut args = Args {
        data: "../data/stars.bin".into(),
        seed: 42,
        years: 25,
        ai: None,
    };
    let mut i = 1;
    while i < argv.len() {
        match argv[i].as_str() {
            "--data" => {
                i += 1;
                args.data = argv.get(i).ok_or("--data needs a value")?.clone();
            }
            "--seed" => {
                i += 1;
                args.seed = argv
                    .get(i)
                    .ok_or("--seed needs a value")?
                    .parse()
                    .map_err(|_| "--seed needs an unsigned integer".to_string())?;
            }
            "--years" => {
                i += 1;
                args.years = argv
                    .get(i)
                    .ok_or("--years needs a value")?
                    .parse()
                    .map_err(|_| "--years needs an unsigned integer".to_string())?;
            }
            "--ai" => {
                i += 1;
                args.ai = Some(
                    argv.get(i)
                        .ok_or("--ai needs a value")?
                        .parse()
                        .map_err(|_| "--ai needs an unsigned integer".to_string())?,
                );
            }
            other => return Err(format!("unknown argument: {other}")),
        }
        i += 1;
    }
    Ok(args)
}

fn main() {
    let args = match parse_args() {
        Ok(args) => args,
        Err(e) => {
            eprintln!("sim-cli: {e}");
            std::process::exit(2);
        }
    };
    let galaxy = match Galaxy::load_table_file(&args.data) {
        Ok(galaxy) => galaxy,
        Err(e) => {
            eprintln!("sim-cli: failed to load star table {}: {e}", args.data);
            std::process::exit(1);
        }
    };
    let (mut campaign, ai_report) = match args.ai {
        None => match Campaign::new_default(&galaxy, args.seed) {
            Ok(campaign) => (campaign, None),
            Err(e) => {
                eprintln!("sim-cli: failed to start campaign: {e}");
                std::process::exit(1);
            }
        },
        Some(ai_count) => {
            let setup = GameSetup {
                ai_count,
                ..GameSetup::default()
            };
            match Campaign::new_game(&galaxy, args.seed, &setup) {
                Ok((campaign, report)) => (campaign, Some(report)),
                Err(e) => {
                    eprintln!("sim-cli: failed to start campaign: {e}");
                    std::process::exit(1);
                }
            }
        }
    };
    let mut policy = ScriptedPolicy;

    println!(
        "campaign_start seed={} stars={} home={} ",
        args.seed,
        galaxy.len(),
        campaign.home_system()
    );
    if let Some(report) = &ai_report {
        for ai in &report.ai {
            println!(
                "ai_civ id={} name={:?} archetype={:?} home={} homeworld_adjusted={}",
                ai.civ_id, ai.name, ai.archetype, ai.home_system, ai.homeworld_adjusted
            );
        }
    }
    for year in 1..=args.years {
        for _ in 0..DAYS_PER_YEAR {
            policy.step(&mut campaign, &galaxy);
            campaign.advance(&galaxy, 1);
        }
        if ai_report.is_some() {
            println!(
                "year={} day={} surveyed={} colonized={} population_millions={:.2} fuel_stock={:.2} credits={:.2} ships={} galaxy_surveyed={} galaxy_colonized={} galaxy_claimed={} contacts={} disputes={}",
                year,
                campaign.day(),
                campaign.surveyed_count(),
                campaign.colonized_count(),
                campaign.total_population_millions(),
                campaign.total_fuel_stock(),
                campaign.credits(),
                campaign.ships().len(),
                campaign.total_surveyed_count(),
                campaign.total_colonized_count(),
                campaign.total_claimed_count(),
                campaign.contacts().len(),
                campaign.disputes().len()
            );
        } else {
            println!(
                "year={} day={} surveyed={} colonized={} population_millions={:.2} fuel_stock={:.2} credits={:.2} ships={}",
                year,
                campaign.day(),
                campaign.surveyed_count(),
                campaign.colonized_count(),
                campaign.total_population_millions(),
                campaign.total_fuel_stock(),
                campaign.credits(),
                campaign.ships().len()
            );
        }
    }
    println!("final_state_hash={}", campaign.state_hash());
}
