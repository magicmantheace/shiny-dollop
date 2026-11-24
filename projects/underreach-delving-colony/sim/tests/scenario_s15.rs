//! S15 — co-op rules: the owner's five rulings of 2026-11-24
//! (docs/COOP_ASSESSMENT.md (c)), proven headless on the S13
//! session layer. Players are session-layer actors issuing typed
//! commands; the sim itself is untouched by this slice.
//!
//! (a) full frontier rights for every player, colony-shared credit
//! (b) any-player lantern-clock rescue, light-planting clock
//!     extension, line-bell heard by everyone
//! (c) downed players: setup/pop-up rescue option, non-hardcore
//!     solo fallback to the closest colony with gear lost,
//!     last-player-down clock-out (non-hardcore) vs run over
//!     (hardcore)
//! (d) contested same-tick actions: host priority, then join
//!     order, loser quietly recorded `applied: false`
//! (e) drop-in/drop-out; host leave pauses everyone, host return
//!     resumes

use underreach_sim::scenario::{build_scenario, SHAFT_LANTERN, TUNNEL_LANTERN_A};
use underreach_sim::session::{
    replay, AttributedCommand, Command, CoopConfig, CoopError, CoopEvent, CoopSession,
    IncidentMode, PlayerCommand, PlayerStatus, SharedCredit,
};
use underreach_sim::sim::Job;
use underreach_sim::world::Pos;

const STOCKPILE: Pos = Pos { x: 3, y: 3, z: 4 };
const FACE_STAND: Pos = Pos { x: 14, y: 8, z: 4 };
const SUPPORT_A: Pos = Pos { x: 2, y: 3, z: 3 };
const SUPPORT_B: Pos = Pos { x: 2, y: 3, z: 5 };

fn entry(player: u8, seq: u32, tick: u64, command: Command) -> AttributedCommand {
    AttributedCommand { tick, player, seq, command }
}

fn coop(config: CoopConfig) -> CoopSession {
    CoopSession::new(build_scenario(), config).expect("host is a valid player")
}

fn coop_with_goods(goods: u32) -> CoopSession {
    let mut sim = build_scenario();
    sim.stores.goods = goods;
    CoopSession::new(sim, CoopConfig::default()).expect("host is a valid player")
}

// -- (a) Frontier rights + shared credit ------------------------------------

#[test]
fn non_host_plants_first_light_and_credit_is_shared() {
    let mut s = coop(CoopConfig::default());
    // The founding camp lantern already wrote its own first-light
    // entries before the session began; shared credit covers the
    // first light planted *through the session*.
    let founding_first_light = s
        .sim()
        .ledger
        .iter()
        .filter(|e| e.kind == underreach_sim::sim::LedgerKind::FirstLight)
        .count();
    s.join(2).expect("P2 joins");
    // P2 — not the host — extends the network down the shaft.
    let applied = s
        .apply_entry(&entry(2, 0, 0, Command::Lantern { pos: SHAFT_LANTERN, tier: 1, fuel: 5_000.0 }))
        .expect("a non-host may plant first light");
    assert!(applied);
    let applied = s
        .apply_entry(&entry(2, 1, 0, Command::Lantern { pos: TUNNEL_LANTERN_A, tier: 1, fuel: 5_000.0 }))
        .expect("a non-host may plant first light");
    assert!(applied);

    // First light happened, in the sim's own Deep Ledger…
    let first_light: Vec<_> = s
        .sim()
        .ledger
        .iter()
        .filter(|e| e.kind == underreach_sim::sim::LedgerKind::FirstLight)
        .collect();
    assert!(first_light.len() > 1, "the shaft and tunnel were first lit");
    // …with no player named anywhere in the credit text…
    assert!(
        first_light.iter().all(|e| !e.detail.contains("player")),
        "ledger credit names no player: {:?}",
        first_light.iter().map(|e| &e.detail).collect::<Vec<_>>()
    );
    // …and the session's shared credit records it colony-level:
    // every credit is a FirstLight with no planter attached (the
    // type has no such field), even though the log's mechanical
    // attribution knows P2 issued the commands.
    let credits = s.shared_credits();
    assert!(!credits.is_empty(), "shared first-light credit was recorded");
    assert!(
        credits.iter().all(|c| matches!(c, SharedCredit::FirstLight { .. })),
        "all credit so far is colony-shared first light"
    );
    assert_eq!(
        credits.len(),
        first_light.len() - founding_first_light,
        "one shared credit per first light planted through the session"
    );
    assert!(s.log().entries.iter().all(|e| e.player == 2), "P2 issued every command");
}

#[test]
fn every_player_can_carve_assign_and_spend() {
    let mut s = coop_with_goods(2);
    s.join(2).expect("P2 joins");
    s.join(3).expect("P3 joins");
    // P3 carves new tunnel east of camp.
    assert!(s
        .apply_entry(&entry(3, 0, 0, Command::Carve { pos: Pos::new(7, 3, 4) }))
        .expect("a non-host may carve"));
    // P2 spends colony goods on a timber support.
    assert!(s
        .apply_entry(&entry(2, 0, 0, Command::Support { pos: SUPPORT_A }))
        .expect("a non-host may spend colony goods"));
    assert_eq!(s.sim().stores.goods, 1, "the support cost 1 good");
    // P3 assigns a delver's job.
    assert!(s
        .apply_entry(&entry(3, 1, 0, Command::Job { id: 0, job: Job::Hauler }))
        .expect("a non-host may assign jobs"));
    assert_eq!(s.sim().delvers[0].job, Job::Hauler);
}

// -- (b) Lantern-clock rescue ------------------------------------------------

#[test]
fn non_host_rescue_light_extension_and_line_bell_for_all() {
    let mut s = coop(CoopConfig { rescue_at_setup: true, ..Default::default() });
    s.join(2).expect("P2 joins");
    s.join(3).expect("P3 joins");
    let incident = s.player_goes_down(3, FACE_STAND).expect("P3 goes down");

    // The line-bell is heard by EVERY joined player…
    for p in [1, 2, 3] {
        assert!(
            s.events_visible_to(p)
                .iter()
                .any(|e| *e == CoopEvent::LineBell { downed_player: 3, pos: FACE_STAND }),
            "player {p} hears the line-bell"
        );
    }
    // …and by nobody who never joined.
    assert!(s.events_visible_to(4).is_empty(), "player 4 never joined");

    // The downed player cannot act.
    let err = s.apply_entry(&entry(3, 0, 0, Command::CraftMask));
    assert_eq!(err, Err(CoopError::PlayerDowned(3)));

    // P2 (non-host) plants light to stretch the clock: 900 → 1200.
    assert_eq!(s.incidents()[0].clock, 900);
    let planted = s
        .rescue_plant_light(2, incident, SHAFT_LANTERN, 1, 5_000.0)
        .expect("any player may plant light for a rescue");
    assert!(planted);
    assert_eq!(s.incidents()[0].clock, 1_200, "the planting stretched the clock");

    // P2 runs the rescue. P3 wakes standing at the closest camp,
    // gear kept, and the credit is the colony's.
    s.run_rescue(2, incident).expect("any player may run the rescue");
    let p3 = s.player(3).expect("P3 is on the roster");
    assert_eq!(p3.status, PlayerStatus::Standing);
    assert!(p3.has_gear, "a rescued player keeps their gear");
    assert_eq!(p3.pos, STOCKPILE, "the rescued player wakes at camp");
    assert!(
        s.shared_credits().contains(&SharedCredit::Rescue { downed_player: 3 }),
        "the rescue is credited to the colony, not to P2"
    );
}

// -- (c) Downed players --------------------------------------------------------

#[test]
fn rescue_via_popup() {
    // Rescue NOT pre-enabled at setup: the pop-up decides.
    let mut s = coop(CoopConfig::default());
    s.join(2).expect("P2 joins");
    let incident = s.player_goes_down(2, FACE_STAND).expect("P2 goes down");
    assert_eq!(s.incidents()[0].mode, IncidentMode::AwaitingPopup);
    // No rescue is in play until the pop-up allows it.
    assert_eq!(
        s.run_rescue(1, incident),
        Err(CoopError::IncidentNotRescuable(incident))
    );
    s.resolve_popup(incident, true).expect("the pop-up allows a rescue");
    assert_eq!(s.incidents()[0].mode, IncidentMode::Rescue);
    s.run_rescue(1, incident).expect("the host runs the rescue");
    let p2 = s.player(2).expect("P2 is on the roster");
    assert_eq!(p2.status, PlayerStatus::Standing);
    assert!(p2.has_gear, "a rescued player keeps their gear");
}

#[test]
fn popup_declined_returns_to_closest_colony_gear_lost() {
    let mut s = coop(CoopConfig::default());
    s.join(2).expect("P2 joins");
    // A forward camp much nearer the face than the home stockpile.
    s.register_camp(Pos::new(10, 8, 4));
    let incident = s.player_goes_down(2, Pos::new(13, 8, 4)).expect("P2 goes down");
    s.resolve_popup(incident, false).expect("the pop-up declines a rescue");
    let p2 = s.player(2).expect("P2 is on the roster");
    assert_eq!(p2.status, PlayerStatus::Standing, "solo rules: the player wakes");
    assert_eq!(p2.pos, Pos::new(10, 8, 4), "at the CLOSEST colony, not the home camp");
    assert!(!p2.has_gear, "solo rules: gear is lost");
    assert!(
        s.events()
            .contains(&CoopEvent::PlayerReturned { player: 2, camp: Pos::new(10, 8, 4) })
    );
}

#[test]
fn last_player_down_nonhardcore_clock_runs_out_into_solo_fallback() {
    let mut s = coop(CoopConfig::default());
    // A one-player session: the host is the last standing player.
    let incident = s.player_goes_down(1, FACE_STAND).expect("the host goes down");
    assert!(!s.run_over(), "non-hardcore: the run is not over");
    assert_eq!(s.incidents()[0].mode, IncidentMode::SoloAfterClock);
    // Nobody can rescue; the clock runs out…
    s.run_to(900).expect("time runs while the host is present");
    // …and the same solo fallback applies.
    let p1 = s.player(1).expect("the host is on the roster");
    assert_eq!(p1.status, PlayerStatus::Standing);
    assert_eq!(p1.pos, STOCKPILE);
    assert!(!p1.has_gear, "gear is lost");
    let _ = incident;
}

#[test]
fn hardcore_last_player_down_ends_the_run() {
    let mut s = coop(CoopConfig { hardcore: true, ..Default::default() });
    s.player_goes_down(1, FACE_STAND).expect("the host goes down");
    assert!(s.run_over(), "hardcore: last standing player down = run over");
    assert!(s.events().contains(&CoopEvent::RunOver));
    assert_eq!(
        s.apply_entry(&entry(1, 0, 0, Command::CraftMask)),
        Err(CoopError::RunOver),
        "no commands are processed after the run ends"
    );
    assert_eq!(s.run_to(10), Err(CoopError::RunOver));
}

#[test]
fn hardcore_rescue_clock_expiry_loses_the_player() {
    // Assumption (rulings silent, recorded in TEST_PLAN S15): a
    // rescue clock that runs out is a failed rescue, and decision
    // 1's permadeath-on-failed-rescue makes that a loss in a
    // hardcore colony — short of the last player, so play goes on.
    let mut s = coop(CoopConfig { hardcore: true, rescue_at_setup: true, ..Default::default() });
    s.join(2).expect("P2 joins");
    s.player_goes_down(2, FACE_STAND).expect("P2 goes down");
    s.run_to(900).expect("the clock runs out unrescued");
    assert_eq!(s.player(2).expect("roster").status, PlayerStatus::Lost);
    assert!(!s.run_over(), "the host still stands: the run continues");
    assert!(s.events().contains(&CoopEvent::PlayerLost { player: 2 }));
}

// -- (d) Contested actions -----------------------------------------------------

#[test]
fn contested_spend_host_wins_loser_fails_quietly() {
    let mut s = coop_with_goods(1);
    s.join(2).expect("P2 joins");
    // Both players spend the colony's single good in the same
    // tick; the streams arrive with P2's first. Host priority
    // reorders them.
    let streams = vec![
        (2, vec![PlayerCommand { tick: 0, seq: 0, command: Command::Support { pos: SUPPORT_B } }]),
        (1, vec![PlayerCommand { tick: 0, seq: 0, command: Command::Support { pos: SUPPORT_A } }]),
    ];
    let merged = s.apply_streams(&streams).expect("a contested tick is not an error");
    assert_eq!(merged[0].player, 1, "the host's command is ordered first");
    let log = s.log();
    assert_eq!(log.entries.len(), 2);
    assert!(log.entries[0].applied && log.entries[0].player == 1, "the host's spend applies");
    assert!(
        !log.entries[1].applied && log.entries[1].player == 2,
        "the loser is simply recorded applied=false — no claim, no queue"
    );
    assert_eq!(s.sim().stores.goods, 0, "the good was spent exactly once");
    assert_eq!(s.sim().supports, vec![SUPPORT_A], "only the host's support stands");
    // State stays consistent: the canonical log replays to it.
    let replayed = replay(&log).expect("the contested log replays");
    assert_eq!(replayed.state_hash(), s.sim().state_hash());
}

#[test]
fn contested_spend_join_order_after_host() {
    let mut s = coop_with_goods(1);
    s.join(2).expect("P2 joins first");
    s.join(3).expect("P3 joins second");
    // The host sits this tick out; P2 vs P3 over the same good,
    // streams arriving P3-first. Join order decides: P2 wins.
    let streams = vec![
        (3, vec![PlayerCommand { tick: 0, seq: 0, command: Command::Support { pos: SUPPORT_B } }]),
        (2, vec![PlayerCommand { tick: 0, seq: 0, command: Command::Support { pos: SUPPORT_A } }]),
    ];
    let merged = s.apply_streams(&streams).expect("a contested tick is not an error");
    assert_eq!(merged[0].player, 2, "the earlier joiner is ordered first");
    let log = s.log();
    assert!(log.entries[0].applied && log.entries[0].player == 2);
    assert!(!log.entries[1].applied && log.entries[1].player == 3);
    assert_eq!(s.sim().supports, vec![SUPPORT_A]);
}

// -- (e) Drop-in / drop-out and host authority ---------------------------------

#[test]
fn join_leave_mid_session_and_host_pause() {
    let mut s = coop(CoopConfig::default());
    s.join(2).expect("P2 joins");
    s.leave(2).expect("P2 leaves");
    // A non-host leaving never ends the colony: the host plays on.
    assert!(!s.run_over() && !s.is_paused());
    assert_eq!(
        s.apply_entry(&entry(2, 0, 0, Command::CraftMask)),
        Err(CoopError::NotPresent(2)),
        "an absent player issues no commands"
    );
    assert!(s
        .apply_entry(&entry(1, 0, 0, Command::Carve { pos: Pos::new(7, 3, 4) }))
        .expect("the host plays on without P2"));
    // Drop-in mid-session: P3 joins a running colony and acts.
    s.join(3).expect("P3 drops in");
    assert!(s
        .apply_entry(&entry(3, 0, 0, Command::Plant { pos: Pos::new(5, 3, 3) }))
        .expect("a drop-in player may act at once"));
    s.run_to(10).expect("the colony runs");
    assert_eq!(s.sim().tick_count, 10);

    // The HOST leaves: the colony pauses for everyone.
    s.leave(1).expect("the host leaves");
    assert!(s.is_paused());
    let paused_hash = s.sim().state_hash();
    assert_eq!(
        s.apply_entry(&entry(3, 1, 10, Command::CraftMask)),
        Err(CoopError::HostAbsent),
        "no command is processed while the host is away"
    );
    assert_eq!(s.run_to(20), Err(CoopError::HostAbsent), "time itself pauses");
    assert_eq!(s.sim().tick_count, 10);
    assert_eq!(s.sim().state_hash(), paused_hash, "paused state does not move");

    // The host returns: play resumes on the host's authoritative
    // copy — the same log, the same hash, commands flowing again.
    s.host_return().expect("the host returns");
    assert!(!s.is_paused());
    assert!(s
        .apply_entry(&entry(3, 1, 10, Command::Carve { pos: Pos::new(8, 3, 4) }))
        .expect("commands flow again after the host returns"));
    s.run_to(20).expect("time runs again");
    assert_eq!(s.sim().tick_count, 20);
    let replayed = replay(&s.log()).expect("the session log still replays");
    assert_eq!(replayed.state_hash(), s.sim().state_hash());
}
