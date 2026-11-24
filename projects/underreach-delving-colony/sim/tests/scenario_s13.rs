//! S13 — co-op foundations: the lockstep session layer, proven
//! headless. Two attributed players found one colony on the
//! generated Floor 1 through the typed command layer; the merged
//! log replays to the identical state hash; arrival order does not
//! matter; a mid-session save/load continues identically; refused
//! commands are recorded, not applied; malformed streams are
//! rejected by the merge. No networking exists in this slice —
//! see docs/COOP_ASSESSMENT.md.

use underreach_sim::gen::carved_path;
use underreach_sim::scenario::{build_scenario_gen, GEN_WORLD_SEED};
use underreach_sim::session::{
    merge_streams, replay, AttributedCommand, Command, MergeError, PlayerCommand, Session,
    SessionError,
};
use underreach_sim::sim::{LedgerKind, Sim};
use underreach_sim::world::{Cell, Pos};

/// The lantern positions `open_floor1` would place on this
/// founding (same path, same spacing) — as P1's typed commands,
/// so the session layer, not the scenario script, lights the way.
fn opening_lanterns(sim: &Sim) -> Vec<Pos> {
    let face = sim.faces.first().expect("gen founding has faces");
    let path = carved_path(&sim.world, sim.stockpile, face.stand).expect("route is carved");
    path.iter()
        .enumerate()
        .filter(|(i, _)| i % 4 == 3 || *i == path.len() - 1)
        .map(|(_, p)| *p)
        .collect()
}

/// A carved camp cell P2 can plant a plot on: not the stockpile,
/// gate, a bed, the camp lantern, or an existing plot.
fn plantable_cell(sim: &Sim) -> Pos {
    for y in 0..sim.world.sy as i32 {
        for x in 0..sim.world.sx as i32 {
            for z in 0..sim.world.sz as i32 {
                let p = Pos::new(x, y, z);
                if sim.world.get(p) == Some(Cell::Carved)
                    && p != sim.stockpile
                    && p != sim.gate
                    && !sim.beds.contains(&p)
                    && !sim.plots.iter().any(|pl| pl.pos == p)
                    && !sim.lanterns.iter().any(|l| l.pos == p)
                {
                    return p;
                }
            }
        }
    }
    panic!("gen founding has a plantable camp cell");
}

/// The two players' streams. P1 lights the way at tick 0 (the
/// opening lantern route). P2 plants a camp plot at tick 0, then
/// — once production has put goods in stores (the gen colony
/// holds 2+ goods well before tick 1,000) — sets a timber support
/// and rigs a vent on the first face's stand.
fn two_player_streams(sim: &Sim) -> Vec<(u8, Vec<PlayerCommand>)> {
    let p1: Vec<PlayerCommand> = opening_lanterns(sim)
        .into_iter()
        .enumerate()
        .map(|(i, pos)| PlayerCommand {
            tick: 0,
            seq: i as u32,
            command: Command::Lantern { pos, tier: 1, fuel: 5_000.0 },
        })
        .collect();
    let stand = sim.faces.first().expect("gen founding has faces").stand;
    let p2 = vec![
        PlayerCommand { tick: 0, seq: 0, command: Command::Plant { pos: plantable_cell(sim) } },
        PlayerCommand { tick: 1_000, seq: 1, command: Command::Support { pos: stand } },
        PlayerCommand { tick: 1_000, seq: 2, command: Command::Vent { pos: stand } },
    ];
    vec![(1, p1), (2, p2)]
}

const RUN_TO: u64 = 6_200;

/// Found the two-player session, merge, apply, and run to
/// production.
fn run_two_player_session() -> Session {
    let founding = build_scenario_gen(GEN_WORLD_SEED);
    let streams = two_player_streams(&founding);
    let merged = merge_streams(&streams).expect("streams are well-formed");
    let mut session = Session::new(founding);
    session.apply_merged(&merged).expect("merged entries apply");
    session.run_to(RUN_TO);
    session
}

#[test]
fn two_players_one_colony_produces() {
    let session = run_two_player_session();
    let sim = session.sim();
    assert!(sim.stores.goods > 0, "the colony produced (goods={})", sim.stores.goods);
    assert_eq!(
        sim.ledger.iter().filter(|e| e.kind == LedgerKind::DelverLost).count(),
        0,
        "nobody lost"
    );
    let log = session.log();
    let p1: Vec<_> = log.entries.iter().filter(|e| e.player == 1).collect();
    let p2: Vec<_> = log.entries.iter().filter(|e| e.player == 2).collect();
    assert!(!p1.is_empty(), "P1 has attributed entries");
    assert_eq!(p2.len(), 3, "P2 has his three attributed entries");
    assert!(
        p1.iter().all(|e| e.applied && matches!(e.command, Command::Lantern { .. })),
        "P1's lantern commands all applied"
    );
    assert!(p2.iter().all(|e| e.applied), "P2's plant/support/vent all applied");
    // Attribution is per-player sequential.
    for (i, e) in p1.iter().enumerate() {
        assert_eq!(e.seq, i as u32);
    }
    for (i, e) in p2.iter().enumerate() {
        assert_eq!(e.seq, i as u32);
    }
}

#[test]
fn replay_reproduces_the_live_hash() {
    let session = run_two_player_session();
    let replayed = replay(&session.log()).expect("the log replays");
    assert_eq!(replayed.state_hash(), session.sim().state_hash());
    assert_eq!(replayed.tick_count, RUN_TO);
}

#[test]
fn arrival_order_does_not_matter() {
    let founding = build_scenario_gen(GEN_WORLD_SEED);
    let streams = two_player_streams(&founding);
    let mut reversed = streams.clone();
    reversed.reverse();
    let merged_a = merge_streams(&streams).expect("well-formed");
    let merged_b = merge_streams(&reversed).expect("well-formed");
    assert_eq!(merged_a, merged_b, "canonical order is arrival-independent");

    let run = |streams: &[(u8, Vec<PlayerCommand>)]| {
        let founding = build_scenario_gen(GEN_WORLD_SEED);
        let merged = merge_streams(streams).expect("well-formed");
        let mut s = Session::new(founding);
        s.apply_merged(&merged).expect("applies");
        s.run_to(RUN_TO);
        s
    };
    let a = run(&streams);
    let b = run(&reversed);
    assert_eq!(a.log().to_json(), b.log().to_json(), "byte-identical canonical logs");
    assert_eq!(a.sim().state_hash(), b.sim().state_hash());
}

#[test]
fn mid_session_save_load_continues_identically() {
    let uninterrupted = run_two_player_session();

    let founding = build_scenario_gen(GEN_WORLD_SEED);
    let streams = two_player_streams(&founding);
    let merged = merge_streams(&streams).expect("well-formed");
    let mut session = Session::new(founding);
    session.apply_merged(&merged).expect("applies");
    session.run_to(3_000);
    // Snapshot mid-session: save the live sim, load it back, and
    // resume the session on the loaded copy.
    let saved = session.sim().save_json();
    let loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), session.sim().state_hash());
    let mut resumed = Session::resume(loaded, session.log()).expect("resume at the snapshot tick");
    resumed.run_to(RUN_TO);
    assert_eq!(resumed.sim().state_hash(), uninterrupted.sim().state_hash());
    assert_eq!(resumed.log().to_json(), uninterrupted.log().to_json());
}

#[test]
fn rejected_commands_change_no_state() {
    let founding = build_scenario_gen(GEN_WORLD_SEED);
    let before = founding.state_hash();
    let mut session = Session::new(founding);

    // A support on solid rock (the first face's rock cell): the
    // sim refuses, the entry is recorded applied=false, and the
    // state hash does not move.
    let rock = session.sim().faces.first().expect("faces").rock;
    let applied = session
        .apply_entry(&AttributedCommand {
            tick: 0,
            player: 2,
            seq: 0,
            command: Command::Support { pos: rock },
        })
        .expect("a refused command is recorded, not an error");
    assert!(!applied);
    assert_eq!(session.sim().state_hash(), before);
    let log = session.log();
    assert_eq!(log.entries.len(), 1);
    assert!(!log.entries[0].applied && log.entries[0].player == 2);

    // Player 5 does not exist in a 1–4 co-op: refused at the API,
    // nothing recorded.
    let err = session.apply_entry(&AttributedCommand {
        tick: 0,
        player: 5,
        seq: 0,
        command: Command::CraftMask,
    });
    assert_eq!(err, Err(SessionError::InvalidPlayer(5)));
    assert_eq!(session.log().entries.len(), 1);
    assert_eq!(session.sim().state_hash(), before);

    // An entry whose tick is in the past is refused too.
    session.run_to(10);
    let err = session.apply_entry(&AttributedCommand {
        tick: 5,
        player: 1,
        seq: 0,
        command: Command::CraftMask,
    });
    assert!(matches!(err, Err(SessionError::TickInPast { .. })));
}

#[test]
fn merge_rejects_duplicates_and_gaps() {
    let cmd = |seq: u32| PlayerCommand { tick: 0, seq, command: Command::CraftMask };
    let dup = merge_streams(&[(1, vec![cmd(0), cmd(0)])]);
    assert_eq!(dup, Err(MergeError::DuplicateSeq { player: 1, seq: 0 }));
    let gap = merge_streams(&[(1, vec![cmd(0), cmd(2)])]);
    assert_eq!(gap, Err(MergeError::SeqGap { player: 1, expected: 1, found: 2 }));
    let outsider = merge_streams(&[(5, vec![cmd(0)])]);
    assert_eq!(outsider, Err(MergeError::InvalidPlayer(5)));
}

#[test]
fn log_roundtrip_preserves_replay() {
    let session = run_two_player_session();
    let log = session.log();
    let json = log.to_json();
    let parsed = underreach_sim::session::SessionLog::from_json(&json).expect("log parses");
    assert_eq!(parsed, log);
    assert_eq!(parsed.to_json(), json, "roundtrip is byte-identical");
    let replayed = replay(&parsed).expect("parsed log replays");
    assert_eq!(replayed.state_hash(), session.sim().state_hash());
}
