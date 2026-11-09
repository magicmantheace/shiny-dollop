//! S3 integration tests: drive the real `sim-bridge` binary with
//! AI races — setup (§6.1/§11.3), the player-perspective view and
//! event filter (§6.1), AI expansion + catch-up equivalence with
//! AI active (§11.1), and the diplomacy view (§6.3). Rich campaign
//! states are crafted in-process with the sim core and written as
//! envelopes, the same way the binary itself saves.

use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus};

use mwcs_bridge::envelope::write_envelope;
use mwcs_bridge::json::{parse, Value};
use mwcs_pipeline::table::{write_table, PlanetRecord, StarRecord};
use mwcs_sim::race::HomeworldRules;
use mwcs_sim::{Campaign, Galaxy, GameSetup, Purpose, ShipKind, PLAYER_CIV};

const NOW: u64 = 1_700_000_000;

fn test_dir(test_name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "mwcs-bridge-test-s3-{}-{}",
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

/// The sim suite's cluster: Sol plus a G/K/M grid, every point
/// within ~70 ly of Sol, so placement seats several civilizations
/// at 15 ly spacing and expansion makes contact quickly.
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

fn save_str(path: &Path) -> Value {
    Value::from(path.to_string_lossy().to_string())
}

fn new_game_req(save: &Path, ai_races: u64) -> Value {
    req_obj(vec![
        ("op", Value::from("new")),
        ("save", save_str(save)),
        ("seed", Value::from(42u64)),
        ("now_unix", Value::from(NOW)),
        ("ai_races", Value::from(ai_races)),
        ("ai_min_spacing_ly", Value::Number(15.0)),
    ])
}

fn view_of(response: &Value) -> &Value {
    response.get("view").expect("response has view")
}

fn arr<'a>(value: &'a Value, key: &str) -> &'a [Value] {
    value
        .get(key)
        .and_then(|v| v.as_array().ok())
        .unwrap_or_else(|| panic!("{key} is an array"))
}

#[test]
fn new_with_ai_races_sets_up_the_game_without_leaking_it() {
    let dir = test_dir("setup");
    let data = write_stars(&dir);
    let save = dir.join("game.mwsb");
    let response = run_req(&dir, &data, new_game_req(&save, 3), "new");
    assert_eq!(response.get("ok").and_then(|v| v.as_bool().ok()), Some(true));

    // Setup block: identities and the spacing actually used — and
    // no home systems (§6.1 fog starts at setup).
    let setup = response.get("setup").expect("setup block present");
    assert_eq!(arr(setup, "ai").len(), 3);
    for ai in arr(setup, "ai") {
        assert!(ai.get("home_system").is_none(), "setup must not leak homes");
        assert!(ai.get("name").is_some());
        assert!(ai.get("archetype").is_some());
    }

    let view = view_of(&response);
    // The roster shows only the player until contact is made.
    let civs = arr(view, "civilizations");
    assert_eq!(civs.len(), 1);
    assert_eq!(
        civs[0].get("is_player").and_then(|v| v.as_bool().ok()),
        Some(true)
    );
    // Galaxy block knows the true scale of the game.
    let galaxy_block = view.get("galaxy").expect("galaxy block");
    assert_eq!(
        galaxy_block
            .get("civilizations")
            .and_then(|v| v.as_u64().ok()),
        Some(4)
    );
    assert_eq!(
        galaxy_block.get("colonized").and_then(|v| v.as_u64().ok()),
        Some(4),
        "four homeworlds"
    );
    // Player perspective: only the player's two ships and one
    // known system (Sol), not the whole roster's.
    assert_eq!(arr(view, "ships").len(), 2);
    assert_eq!(arr(view, "systems").len(), 1);
    assert_eq!(
        view.get("counts")
            .and_then(|c| c.get("surveyed"))
            .and_then(|v| v.as_u64().ok()),
        Some(1)
    );
}

#[test]
fn new_without_ai_races_is_the_solo_game() {
    let dir = test_dir("solo");
    let data = write_stars(&dir);
    let save = dir.join("game.mwsb");
    let response = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("new")),
            ("save", save_str(&save)),
            ("seed", Value::from(42u64)),
            ("now_unix", Value::from(NOW)),
        ]),
        "new-solo",
    );
    assert_eq!(response.get("ok").and_then(|v| v.as_bool().ok()), Some(true));
    assert!(matches!(response.get("setup"), Some(Value::Null)));
    let view = view_of(&response);
    assert_eq!(arr(view, "civilizations").len(), 1);
    assert_eq!(
        view.get("galaxy")
            .and_then(|g| g.get("civilizations"))
            .and_then(|v| v.as_u64().ok()),
        Some(1)
    );
}

#[test]
fn ai_expansion_and_bridge_catch_up_equivalence() {
    let dir = test_dir("catchup");
    let data = write_stars(&dir);

    // Path A: advance inside exec.
    let save_a = dir.join("a.mwsb");
    run_req(&dir, &data, new_game_req(&save_a, 2), "new-a");
    let exec_a = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("exec")),
            ("save", save_str(&save_a)),
            (
                "commands",
                Value::Array(vec![req_obj(vec![
                    ("cmd", Value::from("advance")),
                    ("days", Value::from(730u64)),
                ])]),
            ),
            ("now_unix", Value::from(NOW)),
        ]),
        "exec-a",
    );
    let hash_a = view_of(&exec_a)
        .get("state_hash")
        .and_then(|v| v.as_str().ok())
        .expect("hash A")
        .to_string();

    // Path B: the same elapsed time arriving as a catch-up load.
    let save_b = dir.join("b.mwsb");
    run_req(&dir, &data, new_game_req(&save_b, 2), "new-b");
    let load_b = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("load")),
            ("save", save_str(&save_b)),
            ("now_unix", Value::from(NOW)),
            ("elapsed_override_days", Value::from(730u64)),
        ]),
        "load-b",
    );
    let hash_b = view_of(&load_b)
        .get("state_hash")
        .and_then(|v| v.as_str().ok())
        .expect("hash B")
        .to_string();
    assert_eq!(hash_a, hash_b, "catch-up load ≡ uninterrupted advance");

    // The catch-up report carries the galaxy's movement (§11.1).
    let catchup = load_b.get("catchup").expect("catchup block");
    assert_eq!(catchup.get("days").and_then(|v| v.as_u64().ok()), Some(730));
    let after = catchup.get("after").expect("after snapshot");
    assert!(after.get("galaxy_colonized").is_some());
    assert!(after.get("galaxy_claimed").is_some());
    assert!(after.get("contacts").is_some());

    // And the AI really played: keep advancing both saves to year
    // 10 in exec; colonies galaxy-wide must exceed the 3 homes, and
    // the two paths must still agree state-for-state.
    let mut hashes = Vec::new();
    for (save, tag) in [(&save_a, "exec-a2"), (&save_b, "exec-b2")] {
        let response = run_req(
            &dir,
            &data,
            req_obj(vec![
                ("op", Value::from("exec")),
                ("save", save_str(save)),
                (
                    "commands",
                    Value::Array(vec![req_obj(vec![
                        ("cmd", Value::from("advance")),
                        ("days", Value::from(2920u64)),
                    ])]),
                ),
                ("now_unix", Value::from(NOW)),
            ]),
            tag,
        );
        let view = view_of(&response);
        let colonized = view
            .get("galaxy")
            .and_then(|g| g.get("colonized"))
            .and_then(|v| v.as_u64().ok())
            .expect("galaxy colonized");
        assert!(
            colonized > 3,
            "AI expanded beyond homeworlds (galaxy colonized = {colonized})"
        );
        hashes.push(
            view.get("state_hash")
                .and_then(|v| v.as_str().ok())
                .expect("state hash")
                .to_string(),
        );
    }
    assert_eq!(hashes[0], hashes[1], "paths A and B still identical at year 10");
}

/// Craft a campaign in-process (contact made, a dispute open),
/// save it as an envelope, and read it back through the binary:
/// the diplomacy view and the event filter must both hold.
#[test]
fn diplomacy_view_and_event_filter() {
    let dir = test_dir("diplomacy");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    let setup = GameSetup {
        ai_count: 1,
        home_rules: HomeworldRules {
            region_radius_ly: 500.0,
            min_spacing_ly: 15.0,
            ..HomeworldRules::default()
        },
        ..GameSetup::default()
    };
    let (mut campaign, report) = Campaign::new_game(&galaxy, 42, &setup).expect("game");
    let ai_home = report.ai[0].home_system;

    // Choreography (as in the sim suite): the player surveys and
    // claims a system both sides can reach; the AI then surveys it
    // — first contact — and contests the claim.
    let target = galaxy
        .stars()
        .iter()
        .filter(|s| s.id != 0 && s.id != ai_home)
        .min_by(|a, b| {
            let da = galaxy.distance_ly(0, a.id).unwrap()
                + galaxy.distance_ly(ai_home, a.id).unwrap();
            let db = galaxy.distance_ly(0, b.id).unwrap()
                + galaxy.distance_ly(ai_home, b.id).unwrap();
            da.total_cmp(&db)
        })
        .map(|s| s.id)
        .expect("target");
    let surveyor = campaign
        .ships_of(PLAYER_CIV)
        .into_iter()
        .find(|id| {
            campaign.design(campaign.ship(*id).unwrap().design_idx).map(|d| d.kind)
                == Some(ShipKind::Surveyor)
        })
        .expect("player surveyor");
    campaign
        .dispatch_ship(&galaxy, surveyor, target, Purpose::Survey)
        .expect("player surveys target");
    for _ in 0..500 {
        if campaign.surveyed_by(PLAYER_CIV, target) {
            break;
        }
        campaign.advance(&galaxy, 1);
    }
    assert!(campaign.surveyed_by(PLAYER_CIV, target));
    campaign.claim_system(target).expect("player claims target");

    // The AI's planner keeps its surveyors busy; wait for an idle
    // one, top it up at its colony, and send it to the target.
    let mut dispatched = false;
    for _ in 0..1500 {
        if campaign.surveyed_by(1, target) {
            break;
        }
        if !dispatched {
            let idle = campaign.ships_of(1).into_iter().find(|id| {
                let ship = campaign.ship(*id).unwrap();
                campaign.design(ship.design_idx).map(|d| d.kind) == Some(ShipKind::Surveyor)
                    && matches!(ship.state, mwcs_sim::ShipState::AtSystem { .. })
            });
            if let Some(id) = idle {
                let _ = campaign.refuel_ship_for(1, id);
                if campaign
                    .dispatch_ship_for(1, &galaxy, id, target, Purpose::Survey)
                    .is_ok()
                {
                    dispatched = true;
                }
            }
        }
        campaign.advance(&galaxy, 1);
    }
    assert!(campaign.surveyed_by(1, target));
    assert!(campaign.has_contact(0, 1), "the AI's survey made contact");
    if campaign.disputes_between(0, 1).is_empty() {
        campaign
            .contest_claim_for(1, target)
            .expect("AI contests the claim");
    }
    assert_eq!(campaign.disputes_between(0, 1).len(), 1);

    let save = dir.join("crafted.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    let response = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("view")),
            ("save", save_str(&save)),
            ("event_cursor", Value::from(0u64)),
        ]),
        "view-crafted",
    );
    let view = view_of(&response);

    // Diplomacy roster: the contacted AI appears with both opinion
    // directions and the open dispute, tension included.
    let civs = arr(view, "civilizations");
    assert_eq!(civs.len(), 2, "player + contacted AI");
    let ai = &civs[1];
    assert_eq!(ai.get("id").and_then(|v| v.as_u64().ok()), Some(1));
    assert!(ai.get("contacted_day").is_some());
    let opinion = ai.get("opinion_of_player").expect("opinion block");
    assert!(
        opinion
            .get("disputes")
            .and_then(|v| v.as_f64().ok())
            .expect("dispute component")
            < 0.0,
        "the dispute drags the AI's opinion of the player below zero"
    );
    let disputes = arr(ai, "disputes");
    assert_eq!(disputes.len(), 1);
    assert_eq!(
        disputes[0].get("system").and_then(|v| v.as_u64().ok()),
        Some(target as u64)
    );
    assert!(
        disputes[0]
            .get("tension")
            .and_then(|v| v.as_f64().ok())
            .expect("tension")
            > 0.0
    );

    // Event stream: first contact is visible with names resolved,
    // and no foreign internal event (their ship builds) leaks.
    let events = arr(&response, "events");
    let kinds: Vec<&str> = events
        .iter()
        .filter_map(|e| e.get("kind").and_then(|k| k.as_str().ok()))
        .collect();
    assert!(kinds.contains(&"first_contact"), "kinds: {kinds:?}");
    assert!(kinds.contains(&"claim_contested"), "kinds: {kinds:?}");
    for event in events {
        let civ = event.get("civ").and_then(|v| v.as_u64().ok());
        let kind = event.get("kind").and_then(|k| k.as_str().ok()).unwrap_or("");
        if civ == Some(1) {
            assert!(
                !matches!(kind, "ship_built" | "ship_refuelled" | "specialization_set"),
                "foreign internal event leaked: {kind}"
            );
        }
    }
    let contact_event = events
        .iter()
        .find(|e| e.get("kind").and_then(|k| k.as_str().ok()) == Some("first_contact"))
        .expect("contact event");
    assert!(contact_event.get("civ_name").and_then(|v| v.as_str().ok()).is_some());
    assert!(
        contact_event
            .get("other_civ_name")
            .and_then(|v| v.as_str().ok())
            .is_some()
    );
}

#[test]
fn new_with_ai_races_respects_the_overwrite_guard() {
    // The PR #45 overwrite guard composes with S3 setup: it sits in
    // op_new ahead of campaign creation, so it protects multi-civ
    // campaigns exactly like solo ones (regression pin for the
    // PR #43 / PR #45 reconciliation).
    let dir = test_dir("overwrite_guard");
    let data = write_stars(&dir);
    let save = dir.join("game.mwsb");
    let response = run_req(&dir, &data, new_game_req(&save, 3), "new-first");
    assert_eq!(response.get("ok").and_then(|v| v.as_bool().ok()), Some(true));

    // Same save path, no overwrite flag: refused, campaign intact.
    let refused = run_req(&dir, &data, new_game_req(&save, 3), "new-refused");
    assert_eq!(
        refused.get("ok").and_then(|v| v.as_bool().ok()),
        Some(false),
        "second new without overwrite must be refused: {refused}"
    );
    let err = refused
        .get("error")
        .and_then(|v| v.as_str().ok())
        .unwrap_or("");
    assert!(err.contains("already exists"), "error names the cause: {err}");
    let intact = run_req(
        &dir,
        &data,
        req_obj(vec![("op", Value::from("view")), ("save", save_str(&save))]),
        "view-intact",
    );
    assert_eq!(
        view_of(&intact)
            .get("galaxy")
            .and_then(|g| g.get("civilizations"))
            .and_then(|v| v.as_u64().ok()),
        Some(4),
        "refused overwrite leaves the 4-civ campaign intact"
    );

    // Explicit overwrite: a fresh multi-civ game replaces it.
    let pairs = vec![
        ("op", Value::from("new")),
        ("save", save_str(&save)),
        ("seed", Value::from(42u64)),
        ("now_unix", Value::from(NOW)),
        ("ai_races", Value::from(2u64)),
        ("ai_min_spacing_ly", Value::Number(15.0)),
        ("overwrite", Value::Bool(true)),
    ];
    let replaced = run_req(&dir, &data, req_obj(pairs), "new-overwrite");
    assert_eq!(
        replaced.get("ok").and_then(|v| v.as_bool().ok()),
        Some(true),
        "explicit overwrite succeeds: {replaced}"
    );
    assert_eq!(
        arr(replaced.get("setup").expect("setup block present"), "ai").len(),
        2,
        "the replacement is the new 2-AI game, not the old 3-AI one"
    );
}
