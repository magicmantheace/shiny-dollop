//! S17 — the loopback HOST process.
//!
//! Owns the one authoritative `CoopSession` (ruling 5). Binds a
//! TCP listener on 127.0.0.1 with an ephemeral port, prints
//! `{"type":"ready","port":N}` to stdout, then is driven by
//! JSON directives on stdin (one per line) while client
//! connections arrive over the socket:
//!
//! ```text
//! {"op":"submit","commands":[PlayerCommand…]}   queue the host player's window batch
//! {"op":"flush","from":[2]}                     wait for those players' batches, merge the
//!                                               window (ruling 4), apply, broadcast Sync
//! {"op":"run_to","tick":N}                      advance the colony, broadcast Sync
//! {"op":"down","player":P,"pos":Pos}            a player goes down (line-bell), broadcast
//! {"op":"popup","incident":I,"allowed":bool}    resolve a downing pop-up, broadcast
//! {"op":"rescue_plant","incident":I,"pos":Pos,"tier":1,"fuel":5000.0}
//!                                               the HOST player plants rescue light
//! {"op":"rescue","incident":I}                  the HOST player runs the rescue
//! {"op":"pump","expect":N}                      wait until N client rescue actions are
//!                                               queued, apply them in arrival order, broadcast
//! {"op":"expect_join","player":P}               block until P has joined
//! {"op":"sync"}                                 broadcast the current Sync
//! {"op":"quit"}                                 print the final state line, exit 0
//! ```
//!
//! Every directive answers with one stdout JSON line
//! (`{"type":"ok","op":…,"hash":…}` or `{"type":"error",…}`).
//! All waits are deadline-bound (`--timeout-ms`, default
//! 30,000): on expiry the process prints a `fatal` line and
//! exits 2, so a wedged session can never hang a test suite.
//!
//! Usage: net_host [--goods N] [--hardcore] [--rescue-at-setup]
//!                 [--timeout-ms N]

use std::collections::{HashMap, VecDeque};
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::mpsc::{channel, Receiver, RecvTimeoutError};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::Deserialize;

use underreach_sim::net::{
    merge_window, send_msg, validate_continuation, ClientMsg, CoopSnapshot, HostMsg, LOOPBACK,
};
use underreach_sim::scenario::build_scenario;
use underreach_sim::session::{CoopConfig, CoopSession, PlayerCommand};
use underreach_sim::world::Pos;

#[derive(Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
enum Directive {
    Submit { commands: Vec<PlayerCommand> },
    Flush { from: Vec<u8> },
    RunTo { tick: u64 },
    Down { player: u8, pos: Pos },
    Popup { incident: u32, allowed: bool },
    RescuePlant { incident: u32, pos: Pos, tier: u8, fuel: f32 },
    Rescue { incident: u32 },
    Pump {
        /// How many queued client rescue actions to wait for
        /// before draining — a client's "sent" only means the
        /// bytes left its socket, so the drain must be gated on
        /// arrival, not on the sender's say-so.
        #[serde(default)]
        expect: usize,
    },
    ExpectJoin { player: u8 },
    Sync,
    Quit,
}

enum Ev {
    Line(String),
    Net(u64, ClientMsg),
    Gone(u64),
}

type Writers = Arc<Mutex<HashMap<u64, Arc<Mutex<TcpStream>>>>>;

struct Host {
    coop: CoopSession,
    host_player: u8,
    rx: Receiver<Ev>,
    queued_directives: VecDeque<Directive>,
    writers: Writers,
    conn_player: HashMap<u64, u8>,
    stash: HashMap<u8, Vec<PlayerCommand>>,
    rescue_queue: Vec<(u8, ClientMsg)>,
    timeout: Duration,
}

impl Host {
    fn out(&self, v: serde_json::Value) {
        println!("{v}");
        let _ = std::io::stdout().flush();
    }

    fn ok(&self, op: &str, extra: serde_json::Value) {
        let mut v = serde_json::json!({
            "type": "ok",
            "op": op,
            "hash": self.coop.sim().state_hash(),
            "tick": self.coop.sim().tick_count,
        });
        if let (Some(o), Some(e)) = (v.as_object_mut(), extra.as_object()) {
            for (k, val) in e {
                o.insert(k.clone(), val.clone());
            }
        }
        self.out(v);
    }

    fn error(&self, op: &str, message: String) {
        self.out(serde_json::json!({"type": "error", "op": op, "message": message}));
    }

    fn fatal(&self, message: &str) -> ! {
        self.out(serde_json::json!({"type": "fatal", "message": message}));
        std::process::exit(2);
    }

    fn sync_msg(&self) -> HostMsg {
        HostMsg::Sync {
            log: self.coop.log(),
            hash: self.coop.sim().state_hash(),
            snapshot: CoopSnapshot::of(&self.coop),
        }
    }

    fn send_to(&self, conn: u64, msg: &HostMsg) {
        let w = self.writers.lock().unwrap().get(&conn).cloned();
        if let Some(w) = w {
            let mut w = w.lock().unwrap();
            let _ = send_msg(&mut *w, msg);
        }
    }

    fn broadcast(&self) {
        let msg = self.sync_msg();
        let conns: Vec<u64> = self.writers.lock().unwrap().keys().copied().collect();
        for c in conns {
            self.send_to(c, &msg);
        }
    }

    fn accepted_count(&self, player: u8) -> u32 {
        let applied = self.coop.log().entries.iter().filter(|e| e.player == player).count();
        let queued = self.stash.get(&player).map(|v| v.len()).unwrap_or(0);
        (applied + queued) as u32
    }

    /// Handle one client message (also used for messages that
    /// arrive while a directive is waiting).
    fn handle_net(&mut self, conn: u64, msg: ClientMsg) {
        match msg {
            ClientMsg::Join { player } => {
                if let Some(&other) = self.conn_player.get(&conn) {
                    if other != player {
                        self.send_to(
                            conn,
                            &HostMsg::Error {
                                message: format!("connection already joined as player {other}"),
                            },
                        );
                        return;
                    }
                }
                match self.coop.join(player) {
                    Ok(()) => {
                        self.conn_player.insert(conn, player);
                        // The join sync: the full canonical log.
                        let sync = self.sync_msg();
                        self.send_to(conn, &sync);
                        // The roster changed: everyone else syncs too.
                        let conns: Vec<u64> =
                            self.writers.lock().unwrap().keys().copied().collect();
                        for c in conns {
                            if c != conn {
                                self.send_to(c, &sync);
                            }
                        }
                    }
                    Err(e) => {
                        // A re-join of an already-present player is
                        // answered with a fresh sync, not an error:
                        // the joiner may be reconnecting.
                        if self.coop.player(player).map(|p| p.present) == Some(true) {
                            self.conn_player.insert(conn, player);
                            let sync = self.sync_msg();
                            self.send_to(conn, &sync);
                        } else {
                            self.send_to(conn, &HostMsg::Error { message: e.to_string() });
                        }
                    }
                }
            }
            ClientMsg::Commands { commands } => {
                let Some(&player) = self.conn_player.get(&conn) else {
                    self.send_to(
                        conn,
                        &HostMsg::Error { message: "commands before join".into() },
                    );
                    return;
                };
                let already = self.accepted_count(player);
                match validate_continuation(player, &commands, already) {
                    Ok(()) => {
                        self.stash.entry(player).or_default().extend(commands);
                    }
                    Err(m) => {
                        self.send_to(conn, &HostMsg::Error { message: m });
                    }
                }
            }
            ClientMsg::RescuePlant { .. } | ClientMsg::Rescue { .. } => {
                match self.conn_player.get(&conn) {
                    Some(&player) => self.rescue_queue.push((player, msg)),
                    None => self.send_to(
                        conn,
                        &HostMsg::Error { message: "rescue action before join".into() },
                    ),
                }
            }
        }
    }

    /// Block until `cond` holds, processing network events (and
    /// queueing further directives) meanwhile. Deadline-bound.
    fn wait_until(&mut self, what: &str, cond: &dyn Fn(&Host) -> bool) {
        let deadline = Instant::now() + self.timeout;
        loop {
            if cond(self) {
                return;
            }
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                self.fatal(&format!("timeout waiting for {what}"));
            }
            match self.rx.recv_timeout(remaining) {
                Ok(Ev::Net(conn, msg)) => self.handle_net(conn, msg),
                Ok(Ev::Gone(conn)) => {
                    self.conn_player.remove(&conn);
                    self.writers.lock().unwrap().remove(&conn);
                }
                Ok(Ev::Line(line)) => match serde_json::from_str::<Directive>(&line) {
                    Ok(d) => self.queued_directives.push_back(d),
                    Err(e) => self.error("parse", format!("bad directive while waiting: {e}")),
                },
                Err(RecvTimeoutError::Timeout) => {
                    self.fatal(&format!("timeout waiting for {what}"))
                }
                Err(RecvTimeoutError::Disconnected) => {
                    self.fatal("all input channels closed while waiting")
                }
            }
        }
    }

    fn run(&mut self) {
        loop {
            let ev = match self.queued_directives.pop_front() {
                Some(d) => {
                    self.execute(d);
                    continue;
                }
                None => match self.rx.recv() {
                    Ok(ev) => ev,
                    Err(_) => return, // stdin and sockets all closed
                },
            };
            match ev {
                Ev::Line(line) => {
                    if line.trim().is_empty() {
                        continue;
                    }
                    match serde_json::from_str::<Directive>(&line) {
                        Ok(d) => self.execute(d),
                        Err(e) => self.error("parse", format!("bad directive: {e}")),
                    }
                }
                Ev::Net(conn, msg) => self.handle_net(conn, msg),
                Ev::Gone(conn) => {
                    self.conn_player.remove(&conn);
                    self.writers.lock().unwrap().remove(&conn);
                }
            }
        }
    }

    fn execute(&mut self, d: Directive) {
        match d {
            Directive::Submit { commands } => {
                let already = self.accepted_count(self.host_player);
                match validate_continuation(self.host_player, &commands, already) {
                    Ok(()) => {
                        self.stash.entry(self.host_player).or_default().extend(commands);
                        self.ok("submit", serde_json::json!({}));
                    }
                    Err(m) => self.error("submit", m),
                }
            }
            Directive::Flush { from } => {
                let need = from.clone();
                self.wait_until("client command batches", &move |h: &Host| {
                    need.iter().all(|p| h.stash.get(p).map(|v| !v.is_empty()) == Some(true))
                });
                let mut batches: Vec<(u8, Vec<PlayerCommand>)> = Vec::new();
                if let Some(cmds) = self.stash.remove(&self.host_player) {
                    if !cmds.is_empty() {
                        batches.push((self.host_player, cmds));
                    }
                }
                for p in &from {
                    if let Some(cmds) = self.stash.remove(p) {
                        if !cmds.is_empty() {
                            batches.push((*p, cmds));
                        }
                    }
                }
                let merged = merge_window(&batches, self.host_player, &self.coop.join_order().to_vec());
                let mut applied = Vec::new();
                for e in &merged {
                    match self.coop.apply_entry(e) {
                        Ok(a) => applied.push(a),
                        Err(err) => {
                            self.error("flush", format!("canonical apply refused: {err}"));
                            return;
                        }
                    }
                }
                self.broadcast();
                self.ok("flush", serde_json::json!({"applied": applied}));
            }
            Directive::RunTo { tick } => match self.coop.run_to(tick) {
                Ok(()) => {
                    self.broadcast();
                    self.ok("run_to", serde_json::json!({}));
                }
                Err(e) => self.error("run_to", e.to_string()),
            },
            Directive::Down { player, pos } => match self.coop.player_goes_down(player, pos) {
                Ok(incident) => {
                    self.broadcast();
                    self.ok("down", serde_json::json!({"incident": incident}));
                }
                Err(e) => self.error("down", e.to_string()),
            },
            Directive::Popup { incident, allowed } => {
                match self.coop.resolve_popup(incident, allowed) {
                    Ok(()) => {
                        self.broadcast();
                        self.ok("popup", serde_json::json!({}));
                    }
                    Err(e) => self.error("popup", e.to_string()),
                }
            }
            Directive::RescuePlant { incident, pos, tier, fuel } => {
                match self.coop.rescue_plant_light(self.host_player, incident, pos, tier, fuel) {
                    Ok(applied) => {
                        let clock = self
                            .coop
                            .incidents()
                            .iter()
                            .find(|i| i.id == incident)
                            .map(|i| i.clock);
                        self.broadcast();
                        self.ok(
                            "rescue_plant",
                            serde_json::json!({"applied": applied, "clock": clock}),
                        );
                    }
                    Err(e) => self.error("rescue_plant", e.to_string()),
                }
            }
            Directive::Rescue { incident } => {
                match self.coop.run_rescue(self.host_player, incident) {
                    Ok(()) => {
                        self.broadcast();
                        self.ok("rescue", serde_json::json!({}));
                    }
                    Err(e) => self.error("rescue", e.to_string()),
                }
            }
            Directive::Pump { expect } => {
                if expect > 0 {
                    self.wait_until("queued client rescue actions", &move |h: &Host| {
                        h.rescue_queue.len() >= expect
                    });
                }
                let queue = std::mem::take(&mut self.rescue_queue);
                let mut results = Vec::new();
                for (player, msg) in queue {
                    let r = match msg {
                        ClientMsg::RescuePlant { incident, pos, tier, fuel } => self
                            .coop
                            .rescue_plant_light(player, incident, pos, tier, fuel)
                            .map(|a| serde_json::json!({"player": player, "action": "rescue_plant", "applied": a}))
                            .map_err(|e| e.to_string()),
                        ClientMsg::Rescue { incident } => self
                            .coop
                            .run_rescue(player, incident)
                            .map(|()| serde_json::json!({"player": player, "action": "rescue", "applied": true}))
                            .map_err(|e| e.to_string()),
                        _ => unreachable!("only rescue actions are queued"),
                    };
                    match r {
                        Ok(v) => results.push(v),
                        Err(m) => {
                            results.push(serde_json::json!({"player": player, "error": m}))
                        }
                    }
                }
                self.broadcast();
                self.ok("pump", serde_json::json!({"results": results}));
            }
            Directive::ExpectJoin { player } => {
                self.wait_until("player join", &move |h: &Host| {
                    h.coop.player(player).map(|p| p.present) == Some(true)
                });
                self.ok("expect_join", serde_json::json!({}));
            }
            Directive::Sync => {
                self.broadcast();
                self.ok("sync", serde_json::json!({}));
            }
            Directive::Quit => {
                self.out(serde_json::json!({
                    "type": "final",
                    "hash": self.coop.sim().state_hash(),
                    "tick": self.coop.sim().tick_count,
                    "log": self.coop.log(),
                    "snapshot": CoopSnapshot::of(&self.coop),
                }));
                std::process::exit(0);
            }
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut goods: Option<u32> = None;
    let mut hardcore = false;
    let mut rescue_at_setup = false;
    let mut timeout_ms: u64 = 30_000;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--goods" => {
                i += 1;
                goods = args.get(i).and_then(|v| v.parse().ok());
            }
            "--hardcore" => hardcore = true,
            "--rescue-at-setup" => rescue_at_setup = true,
            "--timeout-ms" => {
                i += 1;
                timeout_ms = args.get(i).and_then(|v| v.parse().ok()).unwrap_or(30_000);
            }
            other => {
                eprintln!("net_host: unknown argument {other}");
                std::process::exit(64);
            }
        }
        i += 1;
    }

    let listener = TcpListener::bind((LOOPBACK, 0)).expect("bind loopback listener");
    let port = listener.local_addr().expect("local addr").port();

    let (tx, rx) = channel::<Ev>();
    // stdin → directives
    {
        let tx = tx.clone();
        std::thread::spawn(move || {
            let stdin = std::io::stdin();
            for line in stdin.lock().lines() {
                match line {
                    Ok(l) => {
                        if tx.send(Ev::Line(l)).is_err() {
                            return;
                        }
                    }
                    Err(_) => return,
                }
            }
        });
    }
    // accept loop → per-connection readers
    let writers: Writers = Arc::new(Mutex::new(HashMap::new()));
    {
        let tx = tx.clone();
        let writers = writers.clone();
        std::thread::spawn(move || {
            let mut next_conn: u64 = 1;
            for stream in listener.incoming() {
                let Ok(stream) = stream else { continue };
                let conn = next_conn;
                next_conn += 1;
                let Ok(clone) = stream.try_clone() else { continue };
                writers.lock().unwrap().insert(conn, Arc::new(Mutex::new(clone)));
                let tx = tx.clone();
                std::thread::spawn(move || {
                    let mut reader = BufReader::new(stream);
                    loop {
                        match underreach_sim::net::recv_msg::<ClientMsg>(&mut reader) {
                            Ok(Some(msg)) => {
                                if tx.send(Ev::Net(conn, msg)).is_err() {
                                    return;
                                }
                            }
                            _ => {
                                let _ = tx.send(Ev::Gone(conn));
                                return;
                            }
                        }
                    }
                });
            }
        });
    }

    let mut sim = build_scenario();
    if let Some(g) = goods {
        sim.stores.goods = g;
    }
    let config = CoopConfig { host: 1, hardcore, rescue_at_setup };
    let coop = CoopSession::new(sim, config).expect("host config is valid");

    let mut host = Host {
        coop,
        host_player: 1,
        rx,
        queued_directives: VecDeque::new(),
        writers,
        conn_player: HashMap::new(),
        stash: HashMap::new(),
        rescue_queue: Vec::new(),
        timeout: Duration::from_millis(timeout_ms),
    };
    host.out(serde_json::json!({"type": "ready", "port": port}));
    host.run();
}
