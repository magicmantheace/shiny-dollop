//! S5 integration tests: drive the real `sim-bridge` binary with
//! war & victory — the war commands and their outcome details
//! (§6), the gate commands and the gate view/inspect surface
//! (§5.3), the victory block and the `new` op's victory options
//! (§6.5), and the S5 event-visibility rules (§6.1). Campaign
//! states are crafted in-process with the sim core and written
//! as envelopes, the same way the binary itself saves (the
//! S3/S4 pattern).

use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus};

use mwcs_bridge::envelope::write_envelope;
use mwcs_bridge::json::{parse, Value};
use mwcs_pipeline::table::{write_table, PlanetRecord, StarRecord};
use mwcs_sim::race::HomeworldRules;
use mwcs_sim::{
    Campaign, Galaxy, GameSetup, Purpose, ShipKind, VictoryRule, PLAYER_CIV, TRANSLATION_DAYS,
};

const NOW: u64 = 1_700_000_000;

fn test_dir(test_name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "mwcs-bridge-test-s5-{}-{}",
        std::process::id(),
        test_name
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("create test dir");
    dir
}

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

fn write_stars(dir: &Path) -> PathBuf {
    let mut records = vec![record(0, "Sol", [0.0, 0.0, 0.0], 4)];
    let mut id = 1u32;
    for &x in &[-55.0f32, -28.0, 0.0, 28.0, 55.0] {
        for &y in &[-36.0f32, 0.0, 36.0] {
            for &z in &[-22.0f32, 22.0] {
                if x == 0.0 && y == 0.0 {
                    continue;
                }
                let spectral = [4u8, 5, 6][(id % 3) as usize];
                records.push(record(id, &format!("Star{id}"), [x, y, z], spectral));
                id += 1;
            }
        }
    }
    let path = dir.join("stars.bin");
    std::fs::write(&path, write_table(&records)).expect("write stars.bin");
    path
}

fn galaxy(dir: &Path) -> Galaxy {
    Galaxy::load_table_file(dir.join("stars.bin")).expect("load galaxy")
}

fn run_bridge(dir: &Path, data: &Path, request_text: &str, tag: &str) -> (Value, ExitStatus) {
    let req_path = dir.join(format!("req-{tag}.json"));
    let res_path = dir.join(format!("res-{tag}.json"));
    std::fs::write(&req_path, request_text).expect("write request");
    let status = Command::new(env!("CARGO_BIN_EXE_sim-bridge"))
        .arg("--data")
        .arg(data)
        .arg("--request")
        .arg(&req_path)
        .arg("--response")
        .arg(&res_path)
        .status()
        .expect("run sim-bridge");
    let text = std::fs::read_to_string(&res_path)
        .unwrap_or_else(|e| panic!("response file for {tag} unreadable ({e}); status={status}"));
    let value =
        parse(&text).unwrap_or_else(|e| panic!("response for {tag} not JSON ({e}): {text}"));
    (value, status)
}

fn run_req(dir: &Path, data: &Path, req: Value, tag: &str) -> Value {
    let (value, status) = run_bridge(dir, data, &req.to_json_string(), tag);
    assert!(status.success(), "bridge exited with {status} for tag {tag}");
    value
}

fn req_obj(pairs: Vec<(&str, Value)>) -> Value {
    Value::obj(pairs)
}

fn view_of(response: &Value) -> &Value {
    response.get("view").expect("response has a view")
}

fn arr<'a>(value: &'a Value, key: &str) -> &'a [Value] {
    value
        .get(key)
        .and_then(|v| v.as_array().ok())
        .unwrap_or_else(|| panic!("field {key} is not an array in {value:?}"))
}

fn exec_req(save: &Path, commands: Vec<Value>, tag: &str, dir: &Path, data: &Path) -> Value {
    run_req(
        dir,
        data,
        req_obj(vec![
            ("op", Value::from("exec")),
            ("save", Value::from(save.to_string_lossy().to_string())),
            ("commands", Value::Array(commands)),
            ("now_unix", Value::from(NOW)),
        ]),
        tag,
    )
}

fn view_req(save: &Path, tag: &str, dir: &Path, data: &Path) -> Value {
    run_req(
        dir,
        data,
        req_obj(vec![
            ("op", Value::from("view")),
            ("save", Value::from(save.to_string_lossy().to_string())),
            ("now_unix", Value::from(NOW)),
        ]),
        tag,
    )
}

fn cmd(pairs: Vec<(&str, Value)>) -> Value {
    Value::obj(pairs)
}

fn result0(response: &Value) -> &Value {
    &arr(response, "results")[0]
}

fn detail_of(response: &Value) -> String {
    result0(response)
        .get("detail")
        .and_then(|v| v.as_str().ok())
        .unwrap_or_default()
        .to_string()
}

fn error_of(response: &Value) -> String {
    result0(response)
        .get("error")
        .and_then(|v| v.as_str().ok())
        .unwrap_or_default()
        .to_string()
}

fn civ_entry<'a>(view: &'a Value, civ_id: u64) -> &'a Value {
    arr(view, "civilizations")
        .iter()
        .find(|c| c.get("id").and_then(|v| v.as_u64().ok()) == Some(civ_id))
        .unwrap_or_else(|| panic!("civ {civ_id} not in the roster: {view:?}"))
}

fn is_null(value: &Value) -> bool {
    matches!(value, Value::Null)
}

fn event_kinds(response: &Value) -> Vec<String> {
    arr(response, "events")
        .iter()
        .map(|e| {
            e.get("kind")
                .and_then(|v| v.as_str().ok())
                .unwrap_or_default()
                .to_string()
        })
        .collect()
}

/// A campaign where the player has met the first AI civilization
/// (always a Merchant League by archetype rotation) and the
/// translation delay has run. Returns the campaign, the merchant,
/// and its home. (The S4 helper, unchanged.)
fn contacted_campaign(galaxy: &Galaxy, ai_count: usize) -> (Campaign, u32, u32) {
    let setup = GameSetup {
        ai_count,
        home_rules: HomeworldRules {
            region_radius_ly: 500.0,
            min_spacing_ly: 20.0,
            ..HomeworldRules::default()
        },
        ..GameSetup::default()
    };
    let (mut campaign, report) = Campaign::new_game(galaxy, 0, &setup).expect("new game");
    let merchant = report.ai[0].civ_id;
    let home = report.ai[0].home_system;
    let surveyor = campaign
        .ships_of(PLAYER_CIV)
        .into_iter()
        .find(|id| {
            campaign
                .design(campaign.ship(*id).unwrap().design_idx)
                .map(|d| d.kind)
                == Some(ShipKind::Surveyor)
        })
        .expect("player surveyor");
    campaign
        .dispatch_ship(galaxy, surveyor, home, Purpose::Survey)
        .expect("dispatch to the merchant home");
    for _ in 0..60 {
        campaign.advance(galaxy, 30);
        if campaign.has_contact(PLAYER_CIV, merchant) {
            break;
        }
    }
    assert!(campaign.has_contact(PLAYER_CIV, merchant));
    campaign.advance(galaxy, TRANSLATION_DAYS + 120);
    assert!(campaign.diplomacy_open(PLAYER_CIV, merchant));
    (campaign, merchant, home)
}

#[test]
fn war_commands_view_and_events() {
    let dir = test_dir("war-commands");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    let (campaign, merchant, _home) = contacted_campaign(&galaxy, 1);
    let save = dir.join("campaign.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    // The design table carries the S5 combat fit, and ship
    // records carry hull state.
    let resp = view_req(&save, "initial-view", &dir, &data);
    let view = view_of(&resp);
    let cruiser = arr(view, "designs")
        .iter()
        .find(|d| d.get("kind").and_then(|v| v.as_str().ok()) == Some("cruiser"))
        .expect("cruiser design in the table");
    assert_eq!(cruiser.get("attack").unwrap().as_f64().unwrap(), 24.0);
    assert_eq!(cruiser.get("defence").unwrap().as_f64().unwrap(), 20.0);
    assert_eq!(cruiser.get("troop_capacity").unwrap().as_f64().unwrap(), 50.0);
    assert_eq!(cruiser.get("hull_strength").unwrap().as_f64().unwrap(), 150.0);
    let ship = &arr(view, "ships")[0];
    assert_eq!(ship.get("hull_damage").unwrap().as_f64().unwrap(), 0.0);
    assert!(ship.get("hull_strength").unwrap().as_f64().unwrap() > 0.0);
    // Not at war yet.
    let entry = civ_entry(view, merchant as u64);
    assert_eq!(entry.get("at_war").unwrap().as_bool().unwrap(), false);
    assert!(is_null(entry.get("war").unwrap()));
    // The opinion block carries the S5 component.
    let opinion = entry.get("opinion_of_player").unwrap();
    assert!(opinion.get("shared_enemies").is_some());

    // Declare war through the binary: the outcome detail, the
    // roster's war block, and the event stream all move.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("declare_war")),
            ("civ", Value::from(merchant)),
        ])],
        "declare-war",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), true);
    assert_eq!(detail_of(&resp), "war declared");
    let view = view_of(&resp);
    let entry = civ_entry(view, merchant as u64);
    assert_eq!(entry.get("at_war").unwrap().as_bool().unwrap(), true);
    let war = entry.get("war").unwrap();
    assert_eq!(war.get("aggressor").unwrap().as_u64().unwrap(), 0);
    assert_eq!(war.get("my_ships_lost").unwrap().as_u64().unwrap(), 0);
    assert_eq!(war.get("their_ships_lost").unwrap().as_u64().unwrap(), 0);
    assert!(entry.get("my_war_exhaustion").unwrap().as_f64().unwrap() >= 0.0);
    assert!(entry.get("their_war_exhaustion").unwrap().as_f64().unwrap() >= 0.0);
    assert!(
        event_kinds(&resp).iter().any(|k| k == "war_declared"),
        "the declaration is in the player's event stream"
    );

    // A second declaration is refused with the stated reason.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("declare_war")),
            ("civ", Value::from(merchant)),
        ])],
        "declare-war-again",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), false);
    assert!(
        error_of(&resp).contains("already at war"),
        "stated reason: {}",
        error_of(&resp)
    );
}

#[test]
fn gate_commands_view_and_inspect() {
    let dir = test_dir("gate-commands");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    // Grow the homeworld in-process until it can pay the gate
    // bill and field a Gate Builder (Industrial specialization
    // from development 3 for the alloys/electronics rates).
    let (mut campaign, _report) = Campaign::new_game(
        &galaxy,
        0,
        &GameSetup {
            ai_count: 0,
            ..GameSetup::default()
        },
    )
    .expect("solo game");
    let home = campaign.home_system();
    let mut builder = None;
    for _ in 0..80 {
        campaign.advance(&galaxy, 90);
        let colony = campaign
            .system(home)
            .and_then(|s| s.colony.as_ref())
            .expect("home colony");
        if colony.development >= 3 && colony.specialization.is_none() {
            let _ = campaign.assign_specialization(home, mwcs_sim::Specialization::Industrial);
        }
        let colony = campaign
            .system(home)
            .and_then(|s| s.colony.as_ref())
            .unwrap();
        if colony.development >= 6
            && colony.alloys_stock >= 420.0
            && colony.electronics_stock >= 40.0
            && campaign.credits() >= 16_000.0
        {
            let design_idx = campaign
                .designs()
                .iter()
                .position(|d| d.kind == ShipKind::GateBuilder)
                .expect("gate builder design");
            campaign
                .build_ship(home, design_idx as u32)
                .expect("queue the builder");
            campaign.advance(&galaxy, 400);
            builder = campaign
                .ships_of(PLAYER_CIV)
                .into_iter()
                .find(|id| {
                    campaign
                        .design(campaign.ship(*id).unwrap().design_idx)
                        .map(|d| d.kind)
                        == Some(ShipKind::GateBuilder)
                });
            break;
        }
    }
    assert!(builder.is_some(), "gate builder built and waiting");
    let save = dir.join("campaign.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    // Build the gate through the binary.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("build_gate")),
            ("system", Value::from(home)),
        ])],
        "build-gate",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), true);
    let detail = detail_of(&resp);
    assert!(detail.starts_with("gate #"), "detail: {detail}");
    let gate_id: u64 = detail
        .trim_start_matches("gate #")
        .split(' ')
        .next()
        .and_then(|n| n.parse().ok())
        .expect("gate id in the detail");
    // The view's gate array shows it, building, ours, unpaired.
    let view = view_of(&resp);
    let gates = arr(view, "gates");
    assert_eq!(gates.len(), 1);
    let gate = &gates[0];
    assert_eq!(gate.get("id").unwrap().as_u64().unwrap(), gate_id);
    assert_eq!(gate.get("system").unwrap().as_u64().unwrap(), home as u64);
    assert_eq!(gate.get("state").unwrap().as_str().unwrap(), "building");
    assert_eq!(gate.get("mine").unwrap().as_bool().unwrap(), true);
    assert!(is_null(gate.get("partner").unwrap()));
    assert_eq!(
        gate.get("build_days_remaining").unwrap().as_u64().unwrap(),
        1460
    );
    // Inspect shows the same gate at the system.
    let resp = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("inspect")),
            ("save", Value::from(save.to_string_lossy().to_string())),
            ("system", Value::from(home)),
            ("now_unix", Value::from(NOW)),
        ]),
        "inspect-home",
    );
    let system = resp.get("system").expect("inspect payload");
    let gate = system.get("gate").unwrap();
    assert!(!is_null(gate), "gate block present in inspect");
    assert_eq!(gate.get("state").unwrap().as_str().unwrap(), "building");
    // The colony record carries the S5 fields (idle here).
    let colony = system.get("colony").unwrap();
    assert!(is_null(colony.get("occupied_by").unwrap()));
    assert!(is_null(colony.get("terraform").unwrap()));

    // Pairing against a gate that does not exist is refused, and
    // transit through a gate still building is refused — both
    // with stated reasons.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("pair_gates")),
            ("gate_a", Value::from(gate_id)),
            ("gate_b", Value::from(999u64)),
        ])],
        "pair-missing",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), false);
    assert!(!error_of(&resp).is_empty());
    let surveyor = campaign
        .ships_of(PLAYER_CIV)
        .into_iter()
        .find(|id| {
            campaign
                .design(campaign.ship(*id).unwrap().design_idx)
                .map(|d| d.kind)
                == Some(ShipKind::Surveyor)
        })
        .expect("player surveyor");
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("gate_transit")),
            ("ship", Value::from(surveyor)),
            ("gate", Value::from(gate_id)),
        ])],
        "transit-building",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), false);
    assert!(
        error_of(&resp).contains("not operational"),
        "stated reason: {}",
        error_of(&resp)
    );
    // Terraforming a development-6 home is refused too (needs 7).
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("start_terraform")),
            ("system", Value::from(home)),
        ])],
        "terraform-early",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), false);
    assert!(!error_of(&resp).is_empty());
}

#[test]
fn victory_options_in_new() {
    let dir = test_dir("victory-new");
    let data = write_stars(&dir);
    let save = dir.join("fae.mwsb");
    let resp = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("new")),
            ("save", Value::from(save.to_string_lossy().to_string())),
            ("seed", Value::from(7u64)),
            ("ai_races", Value::from(2u64)),
            ("ai_min_spacing_ly", Value::Number(25.0)),
            ("ai_region_radius_ly", Value::Number(60.0)),
            ("victory", Value::from("first_among_equals")),
            ("victory_end_year", Value::from(2u64)),
            ("now_unix", Value::from(NOW)),
        ]),
        "new-fae",
    );
    let victory = view_of(&resp).get("victory").unwrap();
    assert_eq!(
        victory.get("rule").unwrap().as_str().unwrap(),
        "first_among_equals"
    );
    assert_eq!(victory.get("end_year").unwrap().as_u64().unwrap(), 2);
    assert!(is_null(victory.get("winner").unwrap()));
    let player = victory.get("player").unwrap();
    assert!(player.get("score").unwrap().as_f64().unwrap() > 0.0);
    assert!(player.get("hegemony_share").is_some());
    assert!(player.get("gate_web_share").is_some());

    // Defaults hold when the fields are absent: a §6 game is
    // Hegemony; a solo game is Sandbox.
    let save2 = dir.join("hegemony.mwsb");
    let resp = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("new")),
            ("save", Value::from(save2.to_string_lossy().to_string())),
            ("seed", Value::from(7u64)),
            ("ai_races", Value::from(1u64)),
            ("ai_min_spacing_ly", Value::Number(25.0)),
            ("ai_region_radius_ly", Value::Number(60.0)),
            ("now_unix", Value::from(NOW)),
        ]),
        "new-default",
    );
    assert_eq!(
        view_of(&resp)
            .get("victory")
            .unwrap()
            .get("rule")
            .unwrap()
            .as_str()
            .unwrap(),
        "hegemony"
    );
    let save3 = dir.join("solo.mwsb");
    let resp = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("new")),
            ("save", Value::from(save3.to_string_lossy().to_string())),
            ("seed", Value::from(7u64)),
            ("now_unix", Value::from(NOW)),
        ]),
        "new-solo",
    );
    assert_eq!(
        view_of(&resp)
            .get("victory")
            .unwrap()
            .get("rule")
            .unwrap()
            .as_str()
            .unwrap(),
        "sandbox"
    );
}

#[test]
fn victory_achieved_is_galaxy_news() {
    let dir = test_dir("victory-news");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    let setup = GameSetup {
        ai_count: 2,
        home_rules: HomeworldRules {
            region_radius_ly: 500.0,
            min_spacing_ly: 20.0,
            ..HomeworldRules::default()
        },
        victory: VictoryRule::FirstAmongEquals,
        victory_end_year: 2,
        ..GameSetup::default()
    };
    let (mut campaign, _report) = Campaign::new_game(&galaxy, 0, &setup).expect("FAE game");
    campaign.advance(&galaxy, 2 * 365 + 40);
    let (winner, _day) = campaign.victory_winner().expect("a winner at the end year");
    let save = dir.join("campaign.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    let resp = view_req(&save, "view-winner", &dir, &data);
    let victory = view_of(&resp).get("victory").unwrap();
    let winner_json = victory.get("winner").unwrap();
    assert_eq!(
        winner_json.get("civ").unwrap().as_u64().unwrap(),
        winner as u64
    );
    assert!(
        event_kinds(&resp).iter().any(|k| k == "victory_achieved"),
        "the victory reaches the player's event stream whoever won it"
    );
}

#[test]
fn strangers_war_stays_out_of_the_players_stream() {
    let dir = test_dir("strangers-war");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    let setup = GameSetup {
        ai_count: 5,
        home_rules: HomeworldRules {
            region_radius_ly: 500.0,
            min_spacing_ly: 20.0,
            ..HomeworldRules::default()
        },
        ..GameSetup::default()
    };
    let (mut campaign, _report) = Campaign::new_game(&galaxy, 0, &setup).expect("game");
    // Wait for two AI civilizations to meet and open diplomacy
    // with each other (dense grid: contacts form within years),
    // then set them at war in-process. The player is party to
    // neither the contact nor the war.
    let mut declared = false;
    for _ in 0..(365 * 25) {
        campaign.advance(&galaxy, 30);
        let civs: Vec<u32> = campaign.civs().iter().map(|c| c.id).collect();
        for &a in &civs {
            if a == PLAYER_CIV {
                continue;
            }
            for &b in &civs {
                if b <= a {
                    continue;
                }
                if campaign.diplomacy_open(a, b) {
                    campaign.declare_war_for(a, b).expect("strangers declare war");
                    declared = true;
                    break;
                }
            }
            if declared {
                break;
            }
        }
        if declared {
            break;
        }
    }
    assert!(declared, "two AI civilizations met and went to war");
    let save = dir.join("campaign.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    let resp = view_req(&save, "view-strangers", &dir, &data);
    assert!(
        !event_kinds(&resp).iter().any(|k| k == "war_declared"),
        "a war between strangers is not the player's news"
    );
}
