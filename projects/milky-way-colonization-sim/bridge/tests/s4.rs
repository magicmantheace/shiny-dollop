//! S4 integration tests: drive the real `sim-bridge` binary with
//! diplomacy — treaty commands and their outcome details (§6.3),
//! the trade-route view and ledger (§4.3), embargoes, peace terms
//! with cessions, and the proposal inbox. Campaign states are
//! crafted in-process with the sim core and written as envelopes,
//! the same way the binary itself saves (the S3 pattern).

use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus};

use mwcs_bridge::envelope::write_envelope;
use mwcs_bridge::json::{parse, Value};
use mwcs_pipeline::table::{write_table, PlanetRecord, StarRecord};
use mwcs_sim::race::HomeworldRules;
use mwcs_sim::{
    Campaign, DealOutcome, Galaxy, GameSetup, PeaceTerms, Purpose, ShipKind, TreatyKind,
    PLAYER_CIV, TRANSLATION_DAYS,
};

const NOW: u64 = 1_700_000_000;

fn test_dir(test_name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "mwcs-bridge-test-s4-{}-{}",
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

fn civ_entry<'a>(view: &'a Value, civ_id: u64) -> &'a Value {
    arr(view, "civilizations")
        .iter()
        .find(|c| c.get("id").and_then(|v| v.as_u64().ok()) == Some(civ_id))
        .unwrap_or_else(|| panic!("civ {civ_id} not in the roster: {view:?}"))
}

/// A campaign where the player has met the first AI civilization
/// (always a Merchant League by archetype rotation) and the
/// translation delay has run. Returns the campaign, the merchant,
/// and its home.
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
fn treaty_commands_route_view_and_embargo_round_trip() {
    let dir = test_dir("treaty-commands");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    let (campaign, merchant, _home) = contacted_campaign(&galaxy, 1);
    let save = dir.join("campaign.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    // Propose trade: signed on the spot, with the outcome detail.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("propose_treaty")),
            ("civ", Value::from(merchant)),
            ("kind", Value::from("trade_agreement")),
        ])],
        "propose-trade",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), true);
    assert_eq!(detail_of(&resp), "signed");
    let view = view_of(&resp);
    let entry = civ_entry(view, merchant as u64);
    let treaties = arr(entry, "treaties");
    assert_eq!(treaties.len(), 1);
    assert_eq!(
        treaties[0].get("kind").unwrap().as_str().unwrap(),
        "trade_agreement"
    );
    // The opinion block carries the S4 components.
    let opinion = entry.get("opinion_of_player").unwrap();
    assert!(opinion.get("trade_volume").is_some());
    assert!(opinion.get("broken_treaties").is_some());
    assert_eq!(entry.get("diplomacy_ready").unwrap().as_bool().unwrap(), true);
    // Empty S4 collections are present, not absent.
    assert_eq!(arr(view, "trade_routes").len(), 0);
    assert!(view.get("proposals").is_some());

    // Open the suggested route; two months later the view's ledger
    // shows real earnings.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("establish_route")),
            ("civ", Value::from(merchant)),
        ])],
        "open-route",
        &dir,
        &data,
    );
    assert!(detail_of(&resp).contains("trade route"), "{}", detail_of(&resp));
    let view = view_of(&resp);
    let routes = arr(view, "trade_routes");
    assert_eq!(routes.len(), 1);
    assert!(arr(&routes[0], "path").len() >= 2, "route carries its path");
    assert!(routes[0].get("throughput").unwrap().as_f64().unwrap() > 0.0);

    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("advance")),
            ("days", Value::from(60u64)),
        ])],
        "advance-60",
        &dir,
        &data,
    );
    let view = view_of(&resp);
    let routes = arr(view, "trade_routes");
    assert_eq!(routes.len(), 1);
    assert!(
        routes[0].get("earned_by_me").unwrap().as_f64().unwrap() > 0.0,
        "the ledger accrues through the binary too"
    );
    assert_eq!(routes[0].get("months_active").unwrap().as_u64().unwrap(), 2);

    // Embargo: the view loses the treaty and the route at once.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("declare_embargo")),
            ("civ", Value::from(merchant)),
        ])],
        "embargo",
        &dir,
        &data,
    );
    assert_eq!(detail_of(&resp), "embargo declared");
    let view = view_of(&resp);
    let entry = civ_entry(view, merchant as u64);
    assert_eq!(arr(entry, "treaties").len(), 0);
    assert_eq!(entry.get("embargo_by_me").unwrap().as_bool().unwrap(), true);
    assert_eq!(arr(view, "trade_routes").len(), 0);

    // Lift it again.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("lift_embargo")),
            ("civ", Value::from(merchant)),
        ])],
        "lift-embargo",
        &dir,
        &data,
    );
    assert_eq!(detail_of(&resp), "embargo lifted");
    let entry = civ_entry(view_of(&resp), merchant as u64);
    assert_eq!(entry.get("embargo_by_me").unwrap().as_bool().unwrap(), false);
}

#[test]
fn proposal_inbox_over_the_bridge() {
    let dir = test_dir("proposal-inbox");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    let (mut campaign, merchant, _home) = contacted_campaign(&galaxy, 1);
    // Two offers from the merchant, filed in-process with the
    // core's exact planner calls: a research pact and a peace
    // recognition.
    let treaty_outcome = campaign
        .propose_treaty_for(merchant, &galaxy, PLAYER_CIV, TreatyKind::ResearchPact)
        .expect("file treaty offer");
    assert!(matches!(treaty_outcome, DealOutcome::Pending { .. }));
    let peace_outcome = campaign
        .propose_peace_for(
            merchant,
            &galaxy,
            PLAYER_CIV,
            PeaceTerms::recognition_only(),
        )
        .expect("file peace offer");
    assert!(matches!(peace_outcome, DealOutcome::Pending { .. }));
    let save = dir.join("campaign.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    let resp = run_req(
        &dir,
        &data,
        req_obj(vec![
            ("op", Value::from("view")),
            ("save", Value::from(save.to_string_lossy().to_string())),
        ]),
        "view-inbox",
    );
    let proposals = arr(view_of(&resp), "proposals");
    // The merchant's planner may have filed an offer of its own
    // during the staging advances — the inbox is a live place.
    // What matters: both of the offers filed above are in it.
    let baseline = proposals.len() - 2;
    let treaty_proposal = proposals
        .iter()
        .find(|p| {
            p.get("kind").unwrap().as_str().unwrap() == "treaty"
                && p.get("treaty_kind").unwrap().as_str().unwrap() == "research_pact"
        })
        .expect("the research-pact offer");
    assert!(!arr(treaty_proposal, "reasons").is_empty());
    assert!(treaty_proposal.get("from_name").unwrap().as_str().is_ok());
    let treaty_id = treaty_proposal.get("id").unwrap().as_u64().unwrap();
    let peace_proposal = proposals
        .iter()
        .find(|p| p.get("kind").unwrap().as_str().unwrap() == "peace")
        .expect("the peace offer");
    let peace_id = peace_proposal.get("id").unwrap().as_u64().unwrap();

    // Refuse the pact; accept the peace.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("refuse_proposal")),
            ("proposal", Value::from(treaty_id)),
        ])],
        "refuse-pact",
        &dir,
        &data,
    );
    assert_eq!(detail_of(&resp), "declined");
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("accept_proposal")),
            ("proposal", Value::from(peace_id)),
        ])],
        "accept-peace",
        &dir,
        &data,
    );
    assert_eq!(detail_of(&resp), "signed");
    let remaining = arr(view_of(&resp), "proposals");
    assert_eq!(remaining.len(), baseline, "both filed offers resolved");
    assert!(remaining
        .iter()
        .all(|p| p.get("id").unwrap().as_u64().unwrap() != treaty_id
            && p.get("id").unwrap().as_u64().unwrap() != peace_id));
}

#[test]
fn refusals_and_errors_carry_their_reasons() {
    let dir = test_dir("refusals");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    // Four AI civs: civ 4 is the Isolationist Gardeners.
    let setup = GameSetup {
        ai_count: 4,
        home_rules: HomeworldRules {
            region_radius_ly: 500.0,
            min_spacing_ly: 20.0,
            ..HomeworldRules::default()
        },
        ..GameSetup::default()
    };
    let (mut campaign, report) = Campaign::new_game(&galaxy, 0, &setup).expect("new game");
    let isolationist = report.ai[3].civ_id;
    let iso_home = report.ai[3].home_system;
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
        .dispatch_ship(&galaxy, surveyor, iso_home, Purpose::Survey)
        .expect("dispatch to the isolationist home");
    for _ in 0..60 {
        campaign.advance(&galaxy, 30);
        if campaign.has_contact(PLAYER_CIV, isolationist) {
            break;
        }
    }
    campaign.advance(&galaxy, TRANSLATION_DAYS + 120);
    let save = dir.join("campaign.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    // The isolationist refuses trade — the command succeeds, and
    // the refusal's stated reasons ride in the detail.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("propose_treaty")),
            ("civ", Value::from(isolationist)),
            ("kind", Value::from("trade_agreement")),
        ])],
        "propose-iso",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), true);
    let detail = detail_of(&resp);
    assert!(detail.starts_with("refused:"), "{detail}");
    assert!(detail.contains("xenophobia"), "{detail}");

    // A civilization never met refuses at the command level.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("propose_treaty")),
            ("civ", Value::from(report.ai[1].civ_id)),
            ("kind", Value::from("trade_agreement")),
        ])],
        "propose-unmet",
        &dir,
        &data,
    );
    assert_eq!(result0(&resp).get("ok").unwrap().as_bool().unwrap(), false);
    let error = result0(&resp).get("error").unwrap().as_str().unwrap();
    assert!(error.contains("no contact"), "{error}");
}

#[test]
fn peace_command_with_cession_moves_the_claim() {
    let dir = test_dir("peace-cession");
    let data = write_stars(&dir);
    let galaxy = galaxy(&dir);
    let (mut campaign, merchant, home) = contacted_campaign(&galaxy, 1);
    // Stage the dispute in-process (the sim suite covers the same
    // staging at core level): port access for fuel, survey a
    // merchant claim, contest it.
    let outcome = campaign
        .propose_treaty(&galaxy, merchant, TreatyKind::GateAccess)
        .expect("propose gate access");
    assert!(matches!(outcome, DealOutcome::Signed), "{outcome:?}");
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
    campaign.refuel_ship(surveyor).expect("refuel");
    let target = campaign
        .systems()
        .iter()
        .filter(|(_, s)| s.claimed_by == Some(merchant) && s.colony.is_none())
        .map(|(id, _)| *id)
        .filter(|id| {
            galaxy
                .distance_ly(home, *id)
                .map(|d| d <= 70.0)
                .unwrap_or(false)
        })
        .min()
        .expect("a merchant claim in reach");
    campaign
        .dispatch_ship(&galaxy, surveyor, target, Purpose::Survey)
        .expect("survey the claim");
    for _ in 0..40 {
        campaign.advance(&galaxy, 30);
        if campaign.surveyed_by(PLAYER_CIV, target) {
            break;
        }
    }
    campaign.contest_claim(target).expect("contest the claim");
    let save = dir.join("campaign.mwsb");
    write_envelope(&save, NOW, &campaign).expect("write envelope");

    // The peace command, from the player's chair: the claim to me,
    // 300 credits to them.
    let resp = exec_req(
        &save,
        vec![cmd(vec![
            ("cmd", Value::from("propose_peace")),
            ("civ", Value::from(merchant)),
            (
                "cede_to_me",
                Value::Array(vec![Value::from(target)]),
            ),
            ("credits", Value::Number(300.0)),
        ])],
        "propose-peace",
        &dir,
        &data,
    );
    assert_eq!(detail_of(&resp), "signed");
    let view = view_of(&resp);
    // The dispute is closed in the diplomacy view...
    let entry = civ_entry(view, merchant as u64);
    assert_eq!(arr(entry, "disputes").len(), 0);
    // ...and the system itself now shows as the player's claim.
    let system = arr(view, "systems")
        .iter()
        .find(|s| s.get("id").unwrap().as_u64().unwrap() == target as u64)
        .expect("the ceded system is in the player's view");
    assert_eq!(
        system.get("claimed_by").unwrap().as_u64().unwrap(),
        PLAYER_CIV as u64
    );
}
