//! `sim-cli` — the S1 headless campaign demo.
//!
//! Usage:
//!   sim-cli [--data PATH] [--seed N] [--years N]
//!
//! Starts a campaign at Sol, drives it with the deterministic
//! scripted policy, and prints one summary line per game year.

use mwcs_sim::policy::ScriptedPolicy;
use mwcs_sim::{Campaign, Galaxy, DAYS_PER_YEAR};

struct Args {
    data: String,
    seed: u64,
    years: u64,
}

fn parse_args() -> Result<Args, String> {
    let argv: Vec<String> = std::env::args().collect();
    let mut args = Args {
        data: "../data/stars.bin".into(),
        seed: 42,
        years: 25,
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
    let mut campaign = match Campaign::new_default(&galaxy, args.seed) {
        Ok(campaign) => campaign,
        Err(e) => {
            eprintln!("sim-cli: failed to start campaign: {e}");
            std::process::exit(1);
        }
    };
    let mut policy = ScriptedPolicy;

    println!(
        "campaign_start seed={} stars={} home={} ",
        args.seed,
        galaxy.len(),
        campaign.home_system()
    );
    for year in 1..=args.years {
        for _ in 0..DAYS_PER_YEAR {
            policy.step(&mut campaign, &galaxy);
            campaign.advance(&galaxy, 1);
        }
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
    println!("final_state_hash={}", campaign.state_hash());
}
