//! S2 integration tests: drive the real `sim-bridge` binary.
//!
//! Each test builds a synthetic 4-star table with the pipeline writer:
//! Sol (id 0) at origin, Near (id 1) at 10 ly, Mid (id 2) at 30 ly,
//! Far (id 3) at 200 ly (beyond the 75 ly design range).

use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus};

use mwcs_bridge::json::{parse, Value};
use mwcs_pipeline::table::{write_table, StarRecord};
use mwcs_sim::{Campaign, Galaxy};

const NOW: u64 = 1_700_000_000;

fn test_dir(test_name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "mwcs-bridge-test-{}-{}",
        std::process::id(),
        test_name
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("create test dir");
    dir
}

fn record(id: u32, name: &str, pos: [f32; 3], sol: bool) -> StarRecord {
    if sol {
        StarRecord {
            id,
            pos_ly: pos,
            absmag: 4.85,
            bv: 0.65,
            teff: 5778.0,
            mass: 1.0,
            spectral: 4,
            flags: 0,
            planets: vec![],
            name: name.into(),
        }
    } else {
        StarRecord {
            id,
            pos_ly: pos,
            absmag: 12.0,
            bv: 1.4,
            teff: 3200.0,
            mass: 0.4,
            spectral: 6,
            flags: 0,
            planets: vec![],
            name: name.into(),
        }
    }
}

fn write_stars(dir: &Path) -> PathBuf {
    let records = vec![
        record(0, "Sol", [0.0, 0.0, 0.0], true),
        record(1, "Near", [10.0, 0.0, 0.0], false),
        record(2, "Mid", [30.0, 0.0, 0.0], false),
        record(3, "Far", [200.0, 0.0, 0.0], false),
    ];
    let path = dir.join("stars.bin");
    std::fs::write(&path, write_table(&records)).expect("write stars.bin");
    path
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
    let value = parse(&text).unwrap_or_else(|e| panic!("response for {tag} not JSON ({e}): {text}"));
    (value, status)
}

fn run_req(dir: &Path, data: &Path, req: Value, tag: &str) -> Value {
    let (value, status) = run_bridge(dir, data, &req.to_json_string(), tag);
    assert!(
        status.success(),
        "bridge exited with {status} for tag {tag}"
    );
    value
}

fn req_obj(pairs: Vec<(&str, Value)>) -> Value {
    Value::obj(pairs)
}

fn save_str(path: &Path) -> Value {
    Value::from(path.to_string_lossy().to_string())
}

fn new_save(dir: &Path, data: &Path, save: &Path, tag: &str) -> Value {
    run_req(
        dir,
        data,
        req_obj(vec![
            ("op", Value::from("new")),
            ("save", save_str(save)),
            ("seed", Value::from(42u64)),
            ("now_unix", Value::from(NOW)),
        ]),
        tag,
    )
}

fn exec_cmds(dir: &Path, data: &Path, save: &Path, commands: Value, tag: &str) -> Value {
    run_req(
        dir,
        data,
        req_obj(vec![
            ("op", Value::from("exec")),
            ("save", save_str(save)),
            ("commands", commands),
            ("now_unix", Value::from(NOW)),
        ]),
        tag,
    )
}

fn get<'a>(v: &'a Value, key: &str) -> &'a Value {
    v.get(key)
        .unwrap_or_else(|| panic!("missing key \"{key}\" in {v}"))
}

fn get_u64(v: &Value, key: &str) -> u64 {
    get(v, key)
        .as_u64()
        .unwrap_or_else(|e| panic!("key \"{key}\": {e} in {v}"))
}

fn get_f64(v: &Value, key: &str) -> f64 {
    get(v, key)
        .as_f64()
        .unwrap_or_else(|e| panic!("key \"{key}\": {e} in {v}"))
}

fn get_bool(v: &Value, key: &str) -> bool {
    get(v, key)
        .as_bool()
        .unwrap_or_else(|e| panic!("key \"{key}\": {e} in {v}"))
}

fn get_str<'a>(v: &'a Value, key: &str) -> &'a str {
    get(v, key)
        .as_str()
        .unwrap_or_else(|e| panic!("key \"{key}\": {e} in {v}"))
}

fn get_arr<'a>(v: &'a Value, key: &str) -> &'a [Value] {
    get(v, key)
        .as_array()
        .unwrap_or_else(|e| panic!("key \"{key}\": {e} in {v}"))
}

fn view(resp: &Value) -> &Value {
    get(resp, "view")
}

fn state_hash(resp: &Value) -> String {
    get_str(view(resp), "state_hash").to_string()
}

fn count(view: &Value, key: &str) -> u64 {
    get_u64(get(view, "counts"), key)
}

fn find_ship<'a>(view: &'a Value, id: u64) -> &'a Value {
    get_arr(view, "ships")
        .iter()
        .find(|s| get_u64(s, "id") == id)
        .unwrap_or_else(|| panic!("ship {id} not in view {view}"))
}

fn ship_id_by_kind(view: &Value, kind: &str) -> u64 {
    get_arr(view, "ships")
        .iter()
        .find(|s| get_str(s, "kind") == kind)
        .map(|s| get_u64(s, "id"))
        .unwrap_or_else(|| panic!("no {kind} ship in view {view}"))
}

fn cmd(pairs: Vec<(&str, Value)>) -> Value {
    Value::obj(pairs)
}

fn dispatch_cmd(ship: u64, to: u64, purpose: &str) -> Value {
    cmd(vec![
        ("cmd", Value::from("dispatch")),
        ("ship", Value::from(ship)),
        ("to", Value::from(to)),
        ("purpose", Value::from(purpose)),
    ])
}

#[test]
fn new_and_view() {
    let dir = test_dir("new_and_view");
    let data = write_stars(&dir);
    let save = dir.join("campaign.mwsb");
    let resp = new_save(&dir, &data, &save, "new");
    assert!(get_bool(&resp, "ok"), "resp: {resp}");
    let v = view(&resp);
    assert_eq!(get_u64(v, "day"), 0);
    assert_eq!(count(v, "colonized"), 1);
    assert_eq!(count(v, "surveyed"), 1);
    assert_eq!(get_arr(v, "ships").len(), 2);
    let home = get_u64(v, "home_system");
    let home_entry = get_arr(v, "systems")
        .iter()
        .find(|s| get_u64(s, "id") == home)
        .expect("home system entry");
    assert_eq!(get_str(home_entry, "name"), "Sol");
    let galaxy = Galaxy::load_table_file(&data).unwrap();
    let expected = Campaign::new_default(&galaxy, 42).unwrap();
    assert_eq!(state_hash(&resp), expected.state_hash());
}

#[test]
fn catchup_equivalence() {
    let dir = test_dir("catchup_equivalence");
    let data = write_stars(&dir);
    // Path A: exec advance 400.
    let save_a = dir.join("a.mwsb");
    new_save(&dir, &data, &save_a, "new-a");
    let resp_a = exec_cmds(
        &dir,
        &data,
        &save_a,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("advance")),
            ("days", Value::from(400u64)),
        ])]),
        "exec-a",
    );
    assert!(get_bool(&resp_a, "ok"), "resp: {resp_a}");
    let hash_a = state_hash(&resp_a);
    // Path B: load with elapsed_override_days 400.
    let save_b = dir.join("b.mwsb");
    new_save(&dir, &data, &save_b, "new-b");
    let resp_b = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("load")),
            ("save", save_str(&save_b)),
            ("now_unix", Value::from(NOW)),
            ("elapsed_override_days", Value::from(400u64)),
        ]),
        "load-b",
    );
    assert!(get_bool(&resp_b, "ok"), "resp: {resp_b}");
    let catchup = get(&resp_b, "catchup");
    assert_eq!(get_u64(catchup, "days"), 400);
    assert_eq!(state_hash(&resp_b), hash_a);
    let before = get(catchup, "before");
    let after = get(catchup, "after");
    assert_eq!(get_u64(before, "day"), 0);
    assert_eq!(get_u64(after, "day"), 400);
    assert_eq!(get_u64(catchup, "months_settled"), 13);
    assert!(
        get_f64(after, "total_population_millions")
            > get_f64(before, "total_population_millions"),
        "population should grow: before={before} after={after}"
    );
}

#[test]
fn catchup_events_cover_period() {
    let dir = test_dir("catchup_events");
    let data = write_stars(&dir);
    // Load path.
    let save_b = dir.join("b.mwsb");
    let resp_new = new_save(&dir, &data, &save_b, "new-b");
    let surveyor = ship_id_by_kind(view(&resp_new), "surveyor");
    let resp_dispatch = exec_cmds(
        &dir,
        &data,
        &save_b,
        Value::Array(vec![dispatch_cmd(surveyor, 1, "survey")]),
        "dispatch-b",
    );
    assert!(get_bool(&resp_dispatch, "ok"), "dispatch resp: {resp_dispatch}");
    assert!(get_bool(&get_arr(&resp_dispatch, "results")[0], "ok"));
    let resp_load = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("load")),
            ("save", save_str(&save_b)),
            ("now_unix", Value::from(NOW)),
            ("elapsed_override_days", Value::from(200u64)),
        ]),
        "load-b",
    );
    assert!(get_bool(&resp_load, "ok"), "resp: {resp_load}");
    let catchup = get(&resp_load, "catchup");
    assert_eq!(get_u64(catchup, "days"), 200);
    let events = get_arr(catchup, "events");
    assert!(
        events.iter().any(|e| get_str(e, "kind") == "survey_completed"
            && get(e, "system").as_u64().ok() == Some(1)),
        "expected survey_completed for Near in {events:?}"
    );
    assert!(
        events.iter().any(|e| get_str(e, "kind") == "ship_arrived"),
        "expected ship_arrived in {events:?}"
    );
    for e in events {
        let d = get_u64(e, "day");
        assert!(d > 0 && d <= 200, "event day {d} out of (0,200]: {e}");
    }
    assert_eq!(count(view(&resp_load), "surveyed"), 2);
    // Hash equivalence with exec advance path.
    let save_a = dir.join("a.mwsb");
    new_save(&dir, &data, &save_a, "new-a");
    let resp_dispatch_a = exec_cmds(
        &dir,
        &data,
        &save_a,
        Value::Array(vec![dispatch_cmd(surveyor, 1, "survey")]),
        "dispatch-a",
    );
    assert!(get_bool(&resp_dispatch_a, "ok"), "resp: {resp_dispatch_a}");
    let resp_adv = exec_cmds(
        &dir,
        &data,
        &save_a,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("advance")),
            ("days", Value::from(200u64)),
        ])]),
        "advance-a",
    );
    assert!(get_bool(&resp_adv, "ok"), "resp: {resp_adv}");
    assert_eq!(state_hash(&resp_load), state_hash(&resp_adv));
}

#[test]
fn whole_days_floor() {
    let dir = test_dir("whole_days_floor");
    let data = write_stars(&dir);
    let save = dir.join("campaign.mwsb");
    new_save(&dir, &data, &save, "new");
    let resp = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("load")),
            ("save", save_str(&save)),
            ("now_unix", Value::from(NOW + 2 * 86_400 + 80_000)),
        ]),
        "load",
    );
    assert!(get_bool(&resp, "ok"), "resp: {resp}");
    assert_eq!(get_u64(get(&resp, "catchup"), "days"), 2);
}

#[test]
fn refusal_surfaces_and_state_intact() {
    let dir = test_dir("refusal");
    let data = write_stars(&dir);
    let save = dir.join("campaign.mwsb");
    let resp_new = new_save(&dir, &data, &save, "new");
    let h = state_hash(&resp_new);
    let surveyor = ship_id_by_kind(view(&resp_new), "surveyor");
    // Dispatch to Far (200 ly > 75 range) must be refused.
    let resp = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![dispatch_cmd(surveyor, 3, "survey")]),
        "dispatch-far",
    );
    assert!(!get_bool(&resp, "ok"), "resp should fail: {resp}");
    let result0 = &get_arr(&resp, "results")[0];
    assert!(!get_bool(result0, "ok"));
    let err = get_str(result0, "error");
    assert!(!err.is_empty(), "error must be non-empty");
    assert!(
        err.contains("range") || err.contains("fuel") || err.contains("ly"),
        "error should explain refusal, got: {err}"
    );
    assert_eq!(state_hash(&resp), h);
    // Claim of an unsurveyed system must be refused, state intact.
    let resp2 = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("claim")),
            ("system", Value::from(1u64)),
        ])]),
        "claim-near",
    );
    assert!(!get_bool(&resp2, "ok"), "resp should fail: {resp2}");
    assert_eq!(state_hash(&resp2), h);
}

#[test]
fn full_loop() {
    let dir = test_dir("full_loop");
    let data = write_stars(&dir);
    let save = dir.join("campaign.mwsb");
    let resp_new = new_save(&dir, &data, &save, "new");
    let surveyor = ship_id_by_kind(view(&resp_new), "surveyor");
    let colony_ship = ship_id_by_kind(view(&resp_new), "colony");
    assert_eq!(surveyor, 1);
    assert_eq!(colony_ship, 2);

    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![dispatch_cmd(surveyor, 1, "survey")]),
        "dispatch-survey",
    );
    assert!(get_bool(&r, "ok"), "dispatch survey: {r}");

    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("advance")),
            ("days", Value::from(150u64)),
        ])]),
        "advance-150",
    );
    assert!(get_bool(&r, "ok"), "advance: {r}");
    assert_eq!(count(view(&r), "surveyed"), 2);

    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("claim")),
            ("system", Value::from(1u64)),
        ])]),
        "claim",
    );
    assert!(get_bool(&r, "ok"), "claim: {r}");

    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![dispatch_cmd(colony_ship, 1, "colonize")]),
        "dispatch-colonize",
    );
    assert!(get_bool(&r, "ok"), "dispatch colonize: {r}");

    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("advance")),
            ("days", Value::from(300u64)),
        ])]),
        "advance-300",
    );
    assert!(get_bool(&r, "ok"), "advance: {r}");
    assert_eq!(count(view(&r), "colonized"), 2);

    let r = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("view")),
            ("save", save_str(&save)),
            ("event_cursor", Value::from(0u64)),
        ]),
        "view-events",
    );
    assert!(get_bool(&r, "ok"), "view: {r}");
    assert!(
        get_arr(&r, "events").iter().any(|e| {
            get_str(e, "kind") == "colony_founded" && get(e, "system").as_u64().ok() == Some(1)
        }),
        "expected colony_founded for Near: {r}"
    );

    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("build")),
            ("system", Value::from(0u64)),
            ("design", Value::from(0u64)),
        ])]),
        "build",
    );
    assert!(get_bool(&r, "ok"), "build: {r}");

    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("advance")),
            ("days", Value::from(200u64)),
        ])]),
        "advance-200",
    );
    assert!(get_bool(&r, "ok"), "advance: {r}");
    // Colony ship was consumed; surveyor + newly built surveyor remain.
    assert_eq!(get_arr(view(&r), "ships").len(), 2, "view: {}", view(&r));

    // Send the original surveyor (now at Near) back to Sol.
    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![dispatch_cmd(surveyor, 0, "relocate")]),
        "dispatch-relocate",
    );
    assert!(get_bool(&r, "ok"), "dispatch relocate: {r}");
    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("advance")),
            ("days", Value::from(100u64)),
        ])]),
        "advance-100",
    );
    assert!(get_bool(&r, "ok"), "advance: {r}");
    let ship = find_ship(view(&r), surveyor);
    assert_eq!(get_str(get(ship, "state"), "type"), "at_system");
    assert_eq!(get_u64(get(ship, "state"), "system"), 0);

    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("refuel")),
            ("ship", Value::from(surveyor)),
        ])]),
        "refuel",
    );
    assert!(get_bool(&r, "ok"), "refuel: {r}");
    assert!(get_bool(&get_arr(&r, "results")[0], "ok"));
    let ship = find_ship(view(&r), surveyor);
    let fuel = get_f64(ship, "fuel");
    let tank = get_f64(ship, "tank_capacity");
    assert!((tank - 150.0).abs() < 1e-9, "tank should be 150, got {tank}");
    assert!((fuel - tank).abs() < 1e-6, "fuel {fuel} should equal tank {tank}");
}

#[test]
fn session_continuity() {
    let dir = test_dir("session_continuity");
    let data = write_stars(&dir);
    let save = dir.join("campaign.mwsb");
    new_save(&dir, &data, &save, "new");
    let r = exec_cmds(
        &dir,
        &data,
        &save,
        Value::Array(vec![cmd(vec![
            ("cmd", Value::from("advance")),
            ("days", Value::from(50u64)),
        ])]),
        "advance-50",
    );
    assert!(get_bool(&r, "ok"), "advance: {r}");
    let resp_view = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("view")),
            ("save", save_str(&save)),
        ]),
        "view",
    );
    assert!(get_bool(&resp_view, "ok"), "view: {resp_view}");
    let galaxy = Galaxy::load_table_file(&data).unwrap();
    let mut expected = Campaign::new_default(&galaxy, 42).unwrap();
    expected.advance(&galaxy, 50);
    assert_eq!(state_hash(&resp_view), expected.state_hash());
}

#[test]
fn list_saves() {
    let dir = test_dir("list_saves");
    let data = write_stars(&dir);
    let save = dir.join("campaign.mwsb");
    new_save(&dir, &data, &save, "new");
    let resp = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("list_saves")),
            ("dir", Value::from(dir.to_string_lossy().to_string())),
        ]),
        "list",
    );
    assert!(get_bool(&resp, "ok"), "resp: {resp}");
    let saves = get_arr(&resp, "saves");
    assert_eq!(saves.len(), 1, "resp: {resp}");
    assert_eq!(get_str(&saves[0], "name"), "campaign.mwsb");
    assert_eq!(get_u64(&saves[0], "day"), 0);
    assert_eq!(get_u64(&saves[0], "saved_at_unix"), NOW);
}

#[test]
fn bad_inputs() {
    let dir = test_dir("bad_inputs");
    let data = write_stars(&dir);
    // Unknown op.
    let (resp, status) = run_bridge(
        &dir,
        &data,
        &req_obj(vec![("op", Value::from("frobnicate"))]).to_json_string(),
        "unknown-op",
    );
    assert!(status.success(), "exit should be 0, got {status}");
    assert!(!get_bool(&resp, "ok"), "resp: {resp}");
    // Inspect a save path that does not exist.
    let missing = dir.join("nope.mwsb");
    let (resp, status) = run_bridge(
        &dir,
        &data,
        &req_obj(vec![
            ("op", Value::from("inspect")),
            ("save", save_str(&missing)),
            ("system", Value::from(0u64)),
        ])
        .to_json_string(),
        "inspect-missing",
    );
    assert!(status.success(), "exit should be 0, got {status}");
    assert!(!get_bool(&resp, "ok"), "resp: {resp}");
    // Malformed request JSON: response file must still contain ok:false.
    let (resp, status) = run_bridge(&dir, &data, "{not json", "malformed");
    assert!(status.success(), "exit should be 0, got {status}");
    assert!(!get_bool(&resp, "ok"), "resp: {resp}");
}
