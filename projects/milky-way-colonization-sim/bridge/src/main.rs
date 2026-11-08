//! sim-bridge — CLI wall-clock boundary for the S2 bridge.
//!
//! Usage: sim-bridge --data <stars.bin> --request <req.json> --response <res.json>
//! Always writes a response file (on any handled error:
//! {"ok":false,"error":"<message>"}). Exit code 0 whenever a
//! response was written, 2 only for usage errors (missing args /
//! unreadable request file).

use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::time::{SystemTime, UNIX_EPOCH};

use mwcs_bridge::envelope::{read_envelope, read_envelope_header, write_envelope};
use mwcs_bridge::json::{parse, Value};
use mwcs_bridge::view::{
    event_json_with_names, event_visible_to_player, events_since, inspect_json, snapshot_json,
    view_json,
};
use mwcs_sim::race::HomeworldRules;
use mwcs_sim::{Campaign, Galaxy, GameSetup, Purpose, Specialization};

fn error_value(message: &str) -> Value {
    Value::obj(vec![
        ("ok", Value::Bool(false)),
        ("error", Value::from(message.to_string())),
    ])
}

fn write_response(path: &Path, value: &Value) -> Result<(), String> {
    std::fs::write(path, value.to_json_string())
        .map_err(|e| format!("failed to write response {}: {e}", path.display()))
}

fn req_str(req: &Value, key: &str) -> Result<String, String> {
    match req.get(key) {
        Some(v) => v.as_str().map(|s| s.to_string()),
        None => Err(format!("missing required field \"{key}\"")),
    }
}

fn req_u64(req: &Value, key: &str) -> Result<u64, String> {
    match req.get(key) {
        Some(v) => v
            .as_u64()
            .map_err(|e| format!("field \"{key}\": {e}")),
        None => Err(format!("missing required field \"{key}\"")),
    }
}

fn opt_u64(req: &Value, key: &str) -> Result<Option<u64>, String> {
    match req.get(key) {
        Some(v) => v
            .as_u64()
            .map(Some)
            .map_err(|e| format!("field \"{key}\": {e}")),
        None => Ok(None),
    }
}

fn opt_f64(req: &Value, key: &str) -> Result<Option<f64>, String> {
    match req.get(key) {
        Some(v) => v
            .as_f64()
            .map(Some)
            .map_err(|e| format!("field \"{key}\": {e}")),
        None => Ok(None),
    }
}

fn now_unix(req: &Value) -> u64 {
    if let Ok(Some(now)) = opt_u64(req, "now_unix") {
        return now;
    }
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn load_campaign(galaxy: &Galaxy, save: &str) -> Result<Campaign, String> {
    let (_, _, payload) = read_envelope(Path::new(save))?;
    Campaign::load_bytes(galaxy, &payload).map_err(|e| format!("{e}"))
}

fn parse_purpose(s: &str) -> Result<Purpose, String> {
    match s {
        "survey" => Ok(Purpose::Survey),
        "colonize" => Ok(Purpose::Colonize),
        "relocate" => Ok(Purpose::Relocate),
        other => Err(format!("unknown purpose \"{other}\"")),
    }
}

fn parse_specialization(s: &str) -> Result<Specialization, String> {
    match s {
        "industrial" => Ok(Specialization::Industrial),
        "agricultural" => Ok(Specialization::Agricultural),
        "refinery" => Ok(Specialization::Refinery),
        "research" => Ok(Specialization::Research),
        "fortress" => Ok(Specialization::Fortress),
        "trade_hub" => Ok(Specialization::TradeHub),
        "shipyard" => Ok(Specialization::Shipyard),
        other => Err(format!("unknown specialization \"{other}\"")),
    }
}

fn cmd_u64(cmd: &Value, key: &str) -> Result<u64, String> {
    match cmd.get(key) {
        Some(v) => v
            .as_u64()
            .map_err(|e| format!("command field \"{key}\": {e}")),
        None => Err(format!("command missing required field \"{key}\"")),
    }
}

fn exec_command(campaign: &mut Campaign, galaxy: &Galaxy, cmd: &Value) -> Result<(), String> {
    let name = match cmd.get("cmd") {
        Some(v) => v
            .as_str()
            .map_err(|e| format!("command field \"cmd\": {e}"))?
            .to_string(),
        None => return Err("command missing required field \"cmd\"".to_string()),
    };
    match name.as_str() {
        "advance" => {
            let days = cmd_u64(cmd, "days")?;
            campaign.advance(galaxy, days);
            Ok(())
        }
        "survey" => {
            let ship = cmd_u64(cmd, "ship")? as u32;
            campaign
                .begin_survey(galaxy, ship)
                .map_err(|e| format!("{e}"))
        }
        "dispatch" => {
            let ship = cmd_u64(cmd, "ship")? as u32;
            let to = cmd_u64(cmd, "to")? as u32;
            let purpose_s = match cmd.get("purpose") {
                Some(v) => v.as_str().map_err(|e| format!("command field \"purpose\": {e}"))?,
                None => return Err("command missing required field \"purpose\"".to_string()),
            };
            let purpose = parse_purpose(purpose_s)?;
            let unchecked = match cmd.get("unchecked") {
                Some(v) => v
                    .as_bool()
                    .map_err(|e| format!("command field \"unchecked\": {e}"))?,
                None => false,
            };
            if unchecked {
                campaign
                    .dispatch_ship_unchecked(galaxy, ship, to, purpose)
                    .map_err(|e| format!("{e}"))
            } else {
                campaign
                    .dispatch_ship(galaxy, ship, to, purpose)
                    .map_err(|e| format!("{e}"))
            }
        }
        "claim" => {
            let system = cmd_u64(cmd, "system")? as u32;
            campaign.claim_system(system).map_err(|e| format!("{e}"))
        }
        "contest" => {
            let system = cmd_u64(cmd, "system")? as u32;
            campaign
                .contest_claim(system)
                .map_err(|e| format!("{e}"))
        }
        "found" => {
            let ship = cmd_u64(cmd, "ship")? as u32;
            campaign
                .found_colony_with_ship(ship)
                .map(|_| ())
                .map_err(|e| format!("{e}"))
        }
        "build" => {
            let system = cmd_u64(cmd, "system")? as u32;
            let design = cmd_u64(cmd, "design")? as u32;
            campaign
                .build_ship(system, design)
                .map(|_| ())
                .map_err(|e| format!("{e}"))
        }
        "refuel" => {
            let ship = cmd_u64(cmd, "ship")? as u32;
            campaign.refuel_ship(ship).map(|_| ()).map_err(|e| format!("{e}"))
        }
        "specialize" => {
            let system = cmd_u64(cmd, "system")? as u32;
            let spec_s = match cmd.get("spec") {
                Some(v) => v.as_str().map_err(|e| format!("command field \"spec\": {e}"))?,
                None => return Err("command missing required field \"spec\"".to_string()),
            };
            let spec = parse_specialization(spec_s)?;
            campaign
                .assign_specialization(system, spec)
                .map_err(|e| format!("{e}"))
        }
        other => Err(format!("unknown command \"{other}\"")),
    }
}

fn dispatch(galaxy: &Galaxy, req: &Value) -> Value {
    let op = match req.get("op") {
        Some(v) => match v.as_str() {
            Ok(s) => s.to_string(),
            Err(e) => return error_value(&format!("field \"op\": {e}")),
        },
        None => return error_value("missing required field \"op\""),
    };
    match op.as_str() {
        "new" => op_new(galaxy, req),
        "load" => op_load(galaxy, req),
        "exec" => op_exec(galaxy, req),
        "view" => op_view(galaxy, req),
        "inspect" => op_inspect(galaxy, req),
        "list_saves" => op_list_saves(req),
        other => error_value(&format!("unknown op \"{other}\"")),
    }
}

fn op_new(galaxy: &Galaxy, req: &Value) -> Value {
    let save = match req_str(req, "save") {
        Ok(s) => s,
        Err(e) => return error_value(&e),
    };
    let seed = match opt_u64(req, "seed") {
        Ok(Some(s)) => s,
        Ok(None) => 42,
        Err(e) => return error_value(&e),
    };
    let ai_races = match opt_u64(req, "ai_races") {
        Ok(v) => v,
        Err(e) => return error_value(&e),
    };
    let ai_min_spacing = match opt_f64(req, "ai_min_spacing_ly") {
        Ok(v) => v,
        Err(e) => return error_value(&e),
    };
    let now = now_unix(req);
    // S3: `ai_races` absent = the S1/S2 solo campaign, byte-for-byte
    // the old behaviour. Present (including 0) = a §6 setup: the
    // player at Sol plus that many AI civilizations. The frontend's
    // setup screen owns the design's default of 12 (§11.3); the
    // bridge defaults to solo so existing callers never change
    // meaning under their feet. `ai_min_spacing_ly` overrides the
    // §6.1 fairness spacing (small test galaxies need it; real games
    // should leave it alone).
    let (campaign, setup_json) = match ai_races {
        None => match Campaign::new_default(galaxy, seed) {
            Ok(c) => (c, Value::Null),
            Err(e) => return error_value(&format!("{e}")),
        },
        Some(ai_count) => {
            let mut rules = HomeworldRules::default();
            if let Some(spacing) = ai_min_spacing {
                rules.min_spacing_ly = spacing;
            }
            let setup = GameSetup {
                ai_count: ai_count as usize,
                home_rules: rules,
                ..GameSetup::default()
            };
            match Campaign::new_game(galaxy, seed, &setup) {
                Ok((c, report)) => {
                    // Identities only — never home systems. Where a
                    // rival lives is §6.1 fog-of-war knowledge, won
                    // by contact, not read off the setup screen.
                    let ai: Vec<Value> = report
                        .ai
                        .iter()
                        .map(|ai| {
                            Value::obj(vec![
                                ("id", Value::from(ai.civ_id)),
                                ("name", Value::from(ai.name.clone())),
                                ("archetype", Value::from(ai.archetype.clone())),
                            ])
                        })
                        .collect();
                    let setup_json = Value::obj(vec![
                        ("player_home", Value::from(report.player_home)),
                        ("spacing_used_ly", Value::Number(report.spacing_used_ly)),
                        ("ai", Value::Array(ai)),
                    ]);
                    (c, setup_json)
                }
                Err(e) => return error_value(&format!("{e}")),
            }
        }
    };
    if let Err(e) = write_envelope(Path::new(&save), now, &campaign) {
        return error_value(&e);
    }
    Value::obj(vec![
        ("ok", Value::Bool(true)),
        ("view", view_json(&campaign, galaxy)),
        ("setup", setup_json),
        ("catchup", Value::Null),
    ])
}

fn op_load(galaxy: &Galaxy, req: &Value) -> Value {
    let save = match req_str(req, "save") {
        Ok(s) => s,
        Err(e) => return error_value(&e),
    };
    let now = now_unix(req);
    let override_days = match opt_u64(req, "elapsed_override_days") {
        Ok(v) => v,
        Err(e) => return error_value(&e),
    };
    let (saved_at, _, _) = match read_envelope(Path::new(&save)) {
        Ok(t) => t,
        Err(e) => return error_value(&e),
    };
    let mut campaign = match load_campaign(galaxy, &save) {
        Ok(c) => c,
        Err(e) => return error_value(&e),
    };
    let day_before = campaign.day();
    let before = snapshot_json(&campaign);
    let elapsed = match override_days {
        Some(d) => d,
        None => now.saturating_sub(saved_at) / 86_400,
    };
    if elapsed > 0 {
        campaign.advance(galaxy, elapsed);
        // The catch-up review shows what the player could know:
        // their own events, diplomacy they are party to, and
        // foreign presence in player-surveyed space (§6.1/§11.1).
        let events: Vec<Value> = campaign
            .events()
            .iter()
            .filter(|e| e.day > day_before && e.day <= campaign.day())
            .filter(|e| event_visible_to_player(&campaign, e))
            .map(|e| event_json_with_names(galaxy, e, &campaign))
            .collect();
        if let Err(e) = write_envelope(Path::new(&save), now, &campaign) {
            return error_value(&e);
        }
        let day_after = campaign.day();
        return Value::obj(vec![
            ("ok", Value::Bool(true)),
            ("view", view_json(&campaign, galaxy)),
            (
                "catchup",
                Value::obj(vec![
                    ("days", Value::from(elapsed)),
                    (
                        "months_settled",
                        Value::from(day_after / 30 - day_before / 30),
                    ),
                    ("before", before),
                    ("after", snapshot_json(&campaign)),
                    ("events", Value::Array(events)),
                ]),
            ),
        ]);
    }
    Value::obj(vec![
        ("ok", Value::Bool(true)),
        ("view", view_json(&campaign, galaxy)),
        (
            "catchup",
            Value::obj(vec![
                ("days", Value::from(0u64)),
                ("months_settled", Value::from(0u64)),
                ("before", before.clone()),
                ("after", snapshot_json(&campaign)),
                ("events", Value::Array(vec![])),
            ]),
        ),
    ])
}

fn op_exec(galaxy: &Galaxy, req: &Value) -> Value {
    let save = match req_str(req, "save") {
        Ok(s) => s,
        Err(e) => return error_value(&e),
    };
    let commands = match req.get("commands") {
        Some(v) => match v.as_array() {
            Ok(a) => a.to_vec(),
            Err(e) => return error_value(&format!("field \"commands\": {e}")),
        },
        None => return error_value("missing required field \"commands\""),
    };
    let event_cursor = match opt_u64(req, "event_cursor") {
        Ok(Some(c)) => c,
        Ok(None) => 0,
        Err(e) => return error_value(&e),
    };
    let now = now_unix(req);
    let mut campaign = match load_campaign(galaxy, &save) {
        Ok(c) => c,
        Err(e) => return error_value(&e),
    };
    let mut results: Vec<Value> = Vec::new();
    let mut all_ok = true;
    for cmd in &commands {
        match exec_command(&mut campaign, galaxy, cmd) {
            Ok(()) => results.push(Value::obj(vec![
                ("ok", Value::Bool(true)),
                ("error", Value::Null),
            ])),
            Err(e) => {
                results.push(Value::obj(vec![
                    ("ok", Value::Bool(false)),
                    ("error", Value::from(e)),
                ]));
                all_ok = false;
                break;
            }
        }
    }
    if let Err(e) = write_envelope(Path::new(&save), now, &campaign) {
        return error_value(&e);
    }
    Value::obj(vec![
        ("ok", Value::Bool(all_ok)),
        ("results", Value::Array(results)),
        ("view", view_json(&campaign, galaxy)),
        (
            "events",
            Value::Array(events_since(&campaign, galaxy, event_cursor)),
        ),
        (
            "event_cursor",
            Value::from(campaign.events().len()),
        ),
    ])
}

fn op_view(galaxy: &Galaxy, req: &Value) -> Value {
    let save = match req_str(req, "save") {
        Ok(s) => s,
        Err(e) => return error_value(&e),
    };
    let event_cursor = match opt_u64(req, "event_cursor") {
        Ok(Some(c)) => c,
        Ok(None) => 0,
        Err(e) => return error_value(&e),
    };
    let campaign = match load_campaign(galaxy, &save) {
        Ok(c) => c,
        Err(e) => return error_value(&e),
    };
    Value::obj(vec![
        ("ok", Value::Bool(true)),
        ("view", view_json(&campaign, galaxy)),
        (
            "events",
            Value::Array(events_since(&campaign, galaxy, event_cursor)),
        ),
        (
            "event_cursor",
            Value::from(campaign.events().len()),
        ),
    ])
}

fn op_inspect(galaxy: &Galaxy, req: &Value) -> Value {
    let save = match req_str(req, "save") {
        Ok(s) => s,
        Err(e) => return error_value(&e),
    };
    let system = match req_u64(req, "system") {
        Ok(s) => s as u32,
        Err(e) => return error_value(&e),
    };
    let campaign = match load_campaign(galaxy, &save) {
        Ok(c) => c,
        Err(e) => return error_value(&e),
    };
    match inspect_json(&campaign, galaxy, system) {
        Ok(system_json) => Value::obj(vec![
            ("ok", Value::Bool(true)),
            ("system", system_json),
        ]),
        Err(e) => error_value(&e),
    }
}

fn op_list_saves(req: &Value) -> Value {
    let dir = match req_str(req, "dir") {
        Ok(s) => s,
        Err(e) => return error_value(&e),
    };
    let dir_path = Path::new(&dir);
    let entries = match std::fs::read_dir(dir_path) {
        Ok(e) => e,
        Err(e) => return error_value(&format!("failed to read directory {dir}: {e}")),
    };
    let mut saves: Vec<(String, PathBuf, u64, u64)> = Vec::new();
    let mut skipped = 0usize;
    for entry in entries {
        let entry = match entry {
            Ok(e) => e,
            Err(_) => continue,
        };
        let name = entry.file_name().to_string_lossy().to_string();
        if !name.ends_with(".mwsb") {
            continue;
        }
        let path = entry.path();
        match read_envelope_header(&path) {
            Ok((saved_at, day)) => saves.push((name, path, saved_at, day)),
            Err(_) => skipped += 1,
        }
    }
    saves.sort_by(|a, b| a.0.cmp(&b.0));
    let saves_json: Vec<Value> = saves
        .into_iter()
        .map(|(name, path, saved_at, day)| {
            Value::obj(vec![
                ("name", Value::from(name)),
                (
                    "path",
                    Value::from(path.to_string_lossy().to_string()),
                ),
                ("saved_at_unix", Value::from(saved_at)),
                ("day", Value::from(day)),
            ])
        })
        .collect();
    Value::obj(vec![
        ("ok", Value::Bool(true)),
        ("saves", Value::Array(saves_json)),
        ("skipped", Value::from(skipped)),
    ])
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let mut data: Option<String> = None;
    let mut request: Option<String> = None;
    let mut response: Option<String> = None;
    let mut i = 1;
    while i < args.len() {
        let key = args[i].as_str();
        let take = |i: &mut usize| -> Option<String> {
            *i += 1;
            args.get(*i).cloned()
        };
        match key {
            "--data" => data = take(&mut i),
            "--request" => request = take(&mut i),
            "--response" => response = take(&mut i),
            _ => {
                eprintln!(
                    "usage: sim-bridge --data <stars.bin> --request <req.json> --response <res.json>"
                );
                return ExitCode::from(2);
            }
        }
        i += 1;
    }
    let (data, request, response) = match (data, request, response) {
        (Some(d), Some(r), Some(res)) => (d, r, res),
        _ => {
            eprintln!(
                "usage: sim-bridge --data <stars.bin> --request <req.json> --response <res.json>"
            );
            return ExitCode::from(2);
        }
    };
    let response_path = Path::new(&response);

    let request_text = match std::fs::read_to_string(&request) {
        Ok(t) => t,
        Err(e) => {
            eprintln!("cannot read request file {request}: {e}");
            return ExitCode::from(2);
        }
    };

    let parsed = match parse(&request_text) {
        Ok(v) => v,
        Err(e) => {
            let value = error_value(&format!("malformed request JSON: {e}"));
            return match write_response(response_path, &value) {
                Ok(()) => ExitCode::SUCCESS,
                Err(e) => {
                    eprintln!("{e}");
                    ExitCode::from(2)
                }
            };
        }
    };

    let galaxy = match Galaxy::load_table_file(&data) {
        Ok(g) => g,
        Err(e) => {
            let value = error_value(&format!("failed to load galaxy table: {e}"));
            return match write_response(response_path, &value) {
                Ok(()) => ExitCode::SUCCESS,
                Err(e) => {
                    eprintln!("{e}");
                    ExitCode::from(2)
                }
            };
        }
    };

    let response_value = dispatch(&galaxy, &parsed);
    match write_response(response_path, &response_value) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::from(2)
        }
    }
}
