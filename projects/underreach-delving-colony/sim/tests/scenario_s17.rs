//! S17 — loopback transport: two PROCESSES, one host and one
//! or more clients, over a real TCP socket on 127.0.0.1.
//!
//! The tests spawn the crate's `net_host` / `net_client`
//! binaries (ephemeral loopback ports, stdin/stdout JSON
//! directive channels), drive the scripted session the task
//! fixes — ordinary commands from both players, a contested
//! same-tick spend resolved by host priority, a lantern-clock
//! rescue — and assert the heart of the slice: **host and
//! client state hashes are EQUAL**, because the client's state
//! is the replay of the host's canonical log (S13 machinery),
//! never its own stream. Also covered: drop-in join mid-session
//! converging from the join sync alone, client-originated
//! rescue actions, a divergent client-local stream changing
//! nothing, and a seq-gapped batch refused without touching
//! the canonical log.
//!
//! Every wait is deadline-bound and every child is reaped
//! (Drop kills), so a wedged transport fails a test instead of
//! hanging the suite.

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command as ProcCommand, Stdio};
use std::sync::mpsc::{channel, Receiver};
use std::time::{Duration, Instant};

use serde_json::{json, Value};

use underreach_sim::scenario::{SHAFT_LANTERN, TUNNEL_LANTERN_A, TUNNEL_LANTERN_B};
use underreach_sim::session::{replay, Command, SessionLog};
use underreach_sim::world::{Cell, Pos};

const TIMEOUT: Duration = Duration::from_secs(60);
const STOCKPILE: Pos = Pos { x: 3, y: 3, z: 4 };
const FACE_STAND: Pos = Pos { x: 14, y: 8, z: 4 };
const SUPPORT_A: Pos = Pos { x: 2, y: 3, z: 3 };
const SUPPORT_B: Pos = Pos { x: 2, y: 3, z: 5 };

// ---------------------------------------------------------------------------
// Process harness
// ---------------------------------------------------------------------------

struct Proc {
    child: Child,
    stdin: ChildStdin,
    lines: Receiver<String>,
}

impl Proc {
    fn spawn(program: &str, args: &[&str]) -> Proc {
        let mut child = ProcCommand::new(program)
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .expect("spawn transport binary");
        let stdin = child.stdin.take().expect("child stdin");
        let stdout = child.stdout.take().expect("child stdout");
        let (tx, rx) = channel();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines() {
                match line {
                    Ok(l) => {
                        if tx.send(l).is_err() {
                            return;
                        }
                    }
                    Err(_) => return,
                }
            }
        });
        Proc { child, stdin, lines: rx }
    }

    fn send(&mut self, v: &Value) {
        writeln!(self.stdin, "{v}").expect("write directive");
        self.stdin.flush().expect("flush directive");
    }

    /// Read stdout lines until one parses as JSON and matches
    /// `pred`; skip the rest (both binaries narrate as they go).
    fn wait_for(&mut self, what: &str, pred: impl Fn(&Value) -> bool) -> Value {
        let deadline = Instant::now() + TIMEOUT;
        let mut skipped: Vec<String> = Vec::new();
        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            assert!(
                !remaining.is_zero(),
                "timeout waiting for {what}; lines seen: {skipped:?}"
            );
            match self.lines.recv_timeout(remaining) {
                Ok(line) => {
                    let v: Value = serde_json::from_str(&line).unwrap_or(Value::Null);
                    if v != Value::Null && pred(&v) {
                        return v;
                    }
                    skipped.push(line);
                }
                Err(e) => panic!("channel closed waiting for {what} ({e}); lines seen: {skipped:?}"),
            }
        }
    }

    fn wait_ok(&mut self, op: &str) -> Value {
        self.wait_for(&format!("ok {op}"), |v| v["type"] == "ok" && v["op"] == op)
    }

    /// Send `quit`, collect the final line, and require a clean
    /// exit — a transport process that cannot shut down on
    /// request fails here, not by hanging.
    fn quit(mut self) -> Value {
        self.send(&json!({"op": "quit"}));
        let f = self.wait_for("final line", |v| v["type"] == "final");
        let deadline = Instant::now() + TIMEOUT;
        loop {
            match self.child.try_wait() {
                Ok(Some(status)) => {
                    assert!(status.success(), "transport process exited with {status}");
                    break;
                }
                Ok(None) => {
                    assert!(Instant::now() < deadline, "transport process did not exit");
                    std::thread::sleep(Duration::from_millis(20));
                }
                Err(e) => panic!("waiting on transport process: {e}"),
            }
        }
        f
    }
}

impl Drop for Proc {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

// ---------------------------------------------------------------------------
// Spawning + JSON command helpers
// ---------------------------------------------------------------------------

fn spawn_host(args: &[&str]) -> (Proc, u16) {
    let mut full: Vec<&str> = vec!["--timeout-ms", "30000"];
    full.extend(args);
    let mut host = Proc::spawn(env!("CARGO_BIN_EXE_net_host"), &full);
    let ready = host.wait_for("host ready", |v| v["type"] == "ready");
    let port = ready["port"].as_u64().expect("host prints its port") as u16;
    (host, port)
}

fn spawn_client(port: u16, player: u8) -> (Proc, Value) {
    let addr = format!("127.0.0.1:{port}");
    let p = player.to_string();
    let mut client = Proc::spawn(
        env!("CARGO_BIN_EXE_net_client"),
        &["--addr", &addr, "--player", &p, "--timeout-ms", "30000"],
    );
    let joined = client.wait_for("client joined", |v| v["type"] == "joined");
    (client, joined)
}

fn pj(p: Pos) -> Value {
    json!({"x": p.x, "y": p.y, "z": p.z})
}

fn pcmd(tick: u64, seq: u32, command: Value) -> Value {
    json!({"tick": tick, "seq": seq, "command": command})
}

fn lantern(pos: Pos) -> Value {
    json!({"Lantern": {"pos": pj(pos), "tier": 1, "fuel": 5000.0}})
}

/// Drive one client to the host hash `hash` and assert the
/// client's own ok line names it.
fn expect_client_at(client: &mut Proc, hash: &str) {
    client.send(&json!({"op": "expect_sync", "hash": hash}));
    let ok = client.wait_ok("expect_sync");
    assert_eq!(ok["hash"], hash, "client converged on the host's hash");
}

fn parse_log(final_line: &Value) -> SessionLog {
    serde_json::from_value(final_line["log"].clone()).expect("final line carries the session log")
}

// ---------------------------------------------------------------------------
// The scripted session: ordinary commands, contested spend, rescue
// ---------------------------------------------------------------------------

#[test]
fn loopback_session_hashes_agree() {
    // One good in stores: the contested spend below is decided
    // by there being exactly one good to spend.
    let (mut host, port) = spawn_host(&["--goods", "1", "--rescue-at-setup"]);
    host.send(&json!({"op": "sync"}));
    let h0 = host.wait_ok("sync")["hash"].clone();
    let (mut client, joined) = spawn_client(port, 2);
    assert_eq!(joined["hash"], h0, "the join sync lands the client on the founding hash");

    // -- Ordinary commands from BOTH players (tick 0 window) --
    client.send(&json!({"op": "submit", "commands": [
        pcmd(0, 0, lantern(TUNNEL_LANTERN_A)),
        pcmd(0, 1, json!({"Plant": {"pos": pj(Pos::new(5, 3, 3))}})),
        pcmd(0, 2, json!({"Job": {"id": 0, "job": "Hauler"}})),
    ]}));
    client.wait_ok("submit");
    host.send(&json!({"op": "submit", "commands": [
        pcmd(0, 0, json!({"Carve": {"pos": pj(Pos::new(7, 3, 4))}})),
        pcmd(0, 1, lantern(SHAFT_LANTERN)),
    ]}));
    host.wait_ok("submit");
    host.send(&json!({"op": "flush", "from": [2]}));
    let flush = host.wait_ok("flush");
    assert_eq!(
        flush["applied"],
        json!([true, true, true, true, true]),
        "every ordinary command from both players applies"
    );
    let h1 = flush["hash"].as_str().unwrap().to_string();
    assert_ne!(h1, h0.as_str().unwrap(), "the colony moved");
    expect_client_at(&mut client, &h1);

    // -- Contested spend: both players, same tick, one good ---
    client.send(&json!({"op": "submit", "commands": [
        pcmd(0, 3, json!({"Support": {"pos": pj(SUPPORT_B)}})),
    ]}));
    client.wait_ok("submit");
    host.send(&json!({"op": "submit", "commands": [
        pcmd(0, 2, json!({"Support": {"pos": pj(SUPPORT_A)}})),
    ]}));
    host.wait_ok("submit");
    host.send(&json!({"op": "flush", "from": [2]}));
    let flush = host.wait_ok("flush");
    assert_eq!(
        flush["applied"],
        json!([true, false]),
        "host priority: the host's spend lands, the client's quietly fails"
    );
    let h2 = flush["hash"].as_str().unwrap().to_string();
    expect_client_at(&mut client, &h2);

    // -- Time passes ------------------------------------------
    host.send(&json!({"op": "run_to", "tick": 50}));
    let run = host.wait_ok("run_to");
    expect_client_at(&mut client, run["hash"].as_str().unwrap());

    // -- Lantern-clock rescue over the wire --------------------
    host.send(&json!({"op": "down", "player": 2, "pos": pj(FACE_STAND)}));
    let down = host.wait_ok("down");
    assert_eq!(down["incident"], 1);
    expect_client_at(&mut client, down["hash"].as_str().unwrap());

    // The host plants light to stretch P2's clock: 900 → 1200.
    host.send(&json!({"op": "rescue_plant", "incident": 1, "pos": pj(TUNNEL_LANTERN_B), "tier": 1, "fuel": 5000.0}));
    let plant = host.wait_ok("rescue_plant");
    assert_eq!(plant["applied"], true, "the rescue light was planted");
    assert_eq!(plant["clock"], 1200, "the planting stretched the downed player's clock");
    expect_client_at(&mut client, plant["hash"].as_str().unwrap());

    host.send(&json!({"op": "rescue", "incident": 1}));
    let rescue = host.wait_ok("rescue");
    expect_client_at(&mut client, rescue["hash"].as_str().unwrap());

    host.send(&json!({"op": "run_to", "tick": 120}));
    let run = host.wait_ok("run_to");
    let h_final = run["hash"].as_str().unwrap().to_string();
    expect_client_at(&mut client, &h_final);

    // -- The consistency check ---------------------------------
    let host_final = host.quit();
    let client_final = client.quit();
    assert_eq!(host_final["hash"], h_final);
    assert_eq!(
        client_final["hash"], host_final["hash"],
        "CONSISTENCY: host and client state hashes are EQUAL"
    );
    assert_eq!(
        client_final["log"], host_final["log"],
        "the client's canonical log is the host's log, byte for byte"
    );
    assert_eq!(
        client_final["snapshot"], host_final["snapshot"],
        "both sides hold the same co-op rules state"
    );

    // The contested loser is recorded identically on both
    // sides (the log equality above) — name it in the replay:
    let log = parse_log(&host_final);
    let supports: Vec<_> = log
        .entries
        .iter()
        .filter(|e| matches!(e.command, Command::Support { .. }))
        .map(|e| (e.player, e.applied))
        .collect();
    assert_eq!(supports, vec![(1, true), (2, false)], "host won, client lost, in the log");
    let replayed = replay(&log).expect("the transported log replays");
    assert_eq!(replayed.state_hash(), h_final, "replay reproduces the agreed hash");
    assert_eq!(replayed.stores.goods, 0, "the single good was spent exactly once");
    assert_eq!(replayed.supports, vec![SUPPORT_A], "only the host's support stands");

    // The rescue landed in the shared record both sides hold:
    let snap = &host_final["snapshot"];
    assert!(
        snap["credits"].as_array().unwrap().contains(&json!({"Rescue": {"downed_player": 2}})),
        "the rescue is credited to the colony: {}",
        snap["credits"]
    );
    assert!(
        snap["events"]
            .as_array()
            .unwrap()
            .iter()
            .any(|e| e["LineBell"]["downed_player"] == 2),
        "the line-bell event crossed the wire"
    );
    let p2 = snap["players"]
        .as_array()
        .unwrap()
        .iter()
        .find(|p| p["player"] == 2)
        .expect("P2 is on the roster");
    assert_eq!(p2["status"], "Standing", "the rescued player stands");
    assert_eq!(p2["has_gear"], true, "a rescued player keeps their gear");
    assert_eq!(p2["pos"], pj(STOCKPILE), "the rescued player woke at camp");
}

// ---------------------------------------------------------------------------
// Drop-in join mid-session + client-originated rescue
// ---------------------------------------------------------------------------

#[test]
fn drop_in_join_converges_and_client_rescue_crosses_the_wire() {
    let (mut host, port) = spawn_host(&["--goods", "4", "--rescue-at-setup"]);
    let (mut client2, _joined) = spawn_client(port, 2);

    // A first window with just the host and P2.
    client2.send(&json!({"op": "submit", "commands": [
        pcmd(0, 0, json!({"Plant": {"pos": pj(Pos::new(5, 3, 3))}})),
    ]}));
    client2.wait_ok("submit");
    host.send(&json!({"op": "submit", "commands": [
        pcmd(0, 0, json!({"Carve": {"pos": pj(Pos::new(7, 3, 4))}})),
    ]}));
    host.wait_ok("submit");
    host.send(&json!({"op": "flush", "from": [2]}));
    let flush = host.wait_ok("flush");
    let h1 = flush["hash"].as_str().unwrap().to_string();
    expect_client_at(&mut client2, &h1);

    // P3 drops in MID-SESSION. The join sync alone — the full
    // canonical log — must land them on the host's exact hash.
    let (mut client3, joined3) = spawn_client(port, 3);
    assert_eq!(
        joined3["hash"], h1,
        "drop-in convergence: the joiner replays the log to the live hash"
    );
    host.send(&json!({"op": "expect_join", "player": 3}));
    host.wait_ok("expect_join");

    // The drop-in player acts in the very next window.
    client3.send(&json!({"op": "submit", "commands": [
        pcmd(0, 0, json!({"Carve": {"pos": pj(Pos::new(8, 3, 4))}})),
    ]}));
    client3.wait_ok("submit");
    host.send(&json!({"op": "flush", "from": [3]}));
    let flush = host.wait_ok("flush");
    let h2 = flush["hash"].as_str().unwrap().to_string();
    expect_client_at(&mut client3, &h2);
    expect_client_at(&mut client2, &h2);

    // P2 goes down; the rescue is run BY THE DROP-IN CLIENT,
    // its actions crossing the wire as transport messages.
    host.send(&json!({"op": "down", "player": 2, "pos": pj(FACE_STAND)}));
    let down = host.wait_ok("down");
    assert_eq!(down["incident"], 1);
    expect_client_at(&mut client3, down["hash"].as_str().unwrap());

    client3.send(&json!({"op": "rescue_plant", "incident": 1, "pos": pj(SHAFT_LANTERN), "tier": 1, "fuel": 5000.0}));
    client3.wait_ok("rescue_plant");
    client3.send(&json!({"op": "rescue", "incident": 1}));
    client3.wait_ok("rescue");
    host.send(&json!({"op": "pump", "expect": 2}));
    let pump = host.wait_ok("pump");
    let results = pump["results"].as_array().expect("pump reports per-action results");
    assert_eq!(results.len(), 2, "both queued rescue actions were applied");
    assert_eq!(results[0]["applied"], true, "the client's light-planting applied");
    assert_eq!(results[1]["applied"], true, "the client's rescue applied");
    assert!(
        results.iter().all(|r| r["player"] == 3),
        "the rescuer of record in the transport is the drop-in client"
    );
    let h3 = pump["hash"].as_str().unwrap().to_string();
    expect_client_at(&mut client3, &h3);
    expect_client_at(&mut client2, &h3);

    let host_final = host.quit();
    let final2 = client2.quit();
    let final3 = client3.quit();
    assert_eq!(final2["hash"], host_final["hash"], "P2 agrees with the host");
    assert_eq!(final3["hash"], host_final["hash"], "the drop-in client agrees with the host");
    assert_eq!(final3["log"], host_final["log"], "the drop-in client's log is canonical");
    let snap = &host_final["snapshot"];
    assert!(
        snap["credits"].as_array().unwrap().contains(&json!({"Rescue": {"downed_player": 2}})),
        "the client-run rescue is credited to the colony"
    );
    let p2 = snap["players"]
        .as_array()
        .unwrap()
        .iter()
        .find(|p| p["player"] == 2)
        .expect("P2 is on the roster");
    assert_eq!(p2["status"], "Standing");
    assert_eq!(p2["has_gear"], true);
}

// ---------------------------------------------------------------------------
// Host authority: a divergent client stream changes nothing
// ---------------------------------------------------------------------------

#[test]
fn client_divergence_does_not_change_the_converged_result() {
    let (mut host, port) = spawn_host(&["--goods", "4"]);
    let (mut client, _joined) = spawn_client(port, 2);

    client.send(&json!({"op": "submit", "commands": [
        pcmd(0, 0, json!({"Plant": {"pos": pj(Pos::new(5, 3, 3))}})),
    ]}));
    client.wait_ok("submit");
    host.send(&json!({"op": "submit", "commands": [
        pcmd(0, 0, json!({"Carve": {"pos": pj(Pos::new(7, 3, 4))}})),
    ]}));
    host.wait_ok("submit");
    host.send(&json!({"op": "flush", "from": [2]}));
    let flush = host.wait_ok("flush");
    let h1 = flush["hash"].as_str().unwrap().to_string();
    expect_client_at(&mut client, &h1);

    // The client goes rogue LOCALLY: it carves a cell the host
    // never heard of, on its own copy. Its local hash moves…
    client.send(&json!({"op": "local_diverge", "commands": [
        pcmd(0, 0, json!({"Carve": {"pos": pj(Pos::new(9, 3, 4))}})),
    ]}));
    let local = client.wait_for("local hash", |v| v["type"] == "local_hash");
    assert_ne!(
        local["hash"], h1,
        "the divergent local stream really does diverge locally"
    );
    assert_eq!(
        local["canonical_hash"], h1,
        "…but the client's canonical state is still the host's"
    );

    // The next host sync overwrites the divergence wholesale.
    host.send(&json!({"op": "run_to", "tick": 30}));
    let run = host.wait_ok("run_to");
    let h2 = run["hash"].as_str().unwrap().to_string();
    expect_client_at(&mut client, &h2);

    let host_final = host.quit();
    let client_final = client.quit();
    assert_eq!(client_final["hash"], host_final["hash"]);
    assert_eq!(client_final["log"], host_final["log"]);
    // The divergent carve is nowhere in the canonical world.
    let log = parse_log(&host_final);
    let replayed = replay(&log).expect("the canonical log replays");
    assert_eq!(
        replayed.world.get(Pos::new(9, 3, 4)),
        Some(Cell::Stone),
        "the client's private carve never happened, canonically"
    );
    assert_eq!(
        replayed.world.get(Pos::new(7, 3, 4)),
        Some(Cell::Carved),
        "the host's carve did"
    );
}

// ---------------------------------------------------------------------------
// A malformed batch is refused; the canonical log is untouched
// ---------------------------------------------------------------------------

#[test]
fn seq_gap_batch_is_refused_and_the_log_is_untouched() {
    let (mut host, port) = spawn_host(&["--goods", "4"]);
    let (mut client, _joined) = spawn_client(port, 2);

    // seq starts at 5: a gap. The host refuses the batch to the
    // sender only; nothing enters the canonical log.
    client.send(&json!({"op": "submit", "commands": [
        pcmd(0, 5, json!({"Carve": {"pos": pj(Pos::new(7, 3, 4))}})),
    ]}));
    client.wait_ok("submit");
    client.send(&json!({"op": "expect_error"}));
    let err = client.wait_ok("expect_error");
    assert!(
        err["message"].as_str().unwrap().contains("expected seq 0"),
        "the refusal names the gap: {}",
        err["message"]
    );

    // A well-formed batch from the same client still works —
    // the refusal poisoned nothing.
    client.send(&json!({"op": "submit", "commands": [
        pcmd(0, 0, json!({"Plant": {"pos": pj(Pos::new(5, 3, 3))}})),
    ]}));
    client.wait_ok("submit");
    host.send(&json!({"op": "flush", "from": [2]}));
    let flush = host.wait_ok("flush");
    assert_eq!(flush["applied"], json!([true]));
    expect_client_at(&mut client, flush["hash"].as_str().unwrap());

    let host_final = host.quit();
    let client_final = client.quit();
    assert_eq!(client_final["hash"], host_final["hash"]);
    let log = parse_log(&host_final);
    assert_eq!(log.entries.len(), 1, "only the valid command ever entered the log");
    assert_eq!(log.entries[0].player, 2);
}
