//! S17 — the loopback CLIENT process.
//!
//! Connects to a `net_host` on 127.0.0.1, claims its player
//! slot, and thereafter holds exactly one thing: the replay of
//! the host's canonical log (see `net::ClientState`). It sends
//! typed commands and rescue actions to the host; it never
//! advances a sim of its own except as a replay, and its hash
//! is canonical only because that replay reproduced the host's
//! hash. Driven by JSON directives on stdin:
//!
//! ```text
//! {"op":"submit","commands":[PlayerCommand…]}  send a command window to the host
//! {"op":"rescue_plant","incident":I,"pos":Pos,"tier":1,"fuel":5000.0}
//! {"op":"rescue","incident":I}                 ask the host to run a rescue as us
//! {"op":"expect_sync","hash":"…"}              block until a Sync with this hash lands
//! {"op":"expect_error"}                        block until the host refuses something
//! {"op":"local_diverge","commands":[PlayerCommand…]}
//!                                               apply commands to a LOCAL copy only and
//!                                               report the (non-canonical) local hash
//! {"op":"quit"}                                print the final state line, exit 0
//! ```
//!
//! Startup prints `{"type":"joined","hash":…}` once the join
//! sync has been replayed and verified. A sync whose replay
//! does not reproduce the host's hash is a desync: the process
//! prints `{"type":"desync",…}` and exits 4. All waits are
//! deadline-bound (`--timeout-ms`, default 30,000); on expiry
//! the process prints a `fatal` line and exits 2.
//!
//! Usage: net_client --addr 127.0.0.1:PORT --player N
//!                   [--timeout-ms N]

use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;
use std::sync::mpsc::{channel, Receiver, RecvTimeoutError};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::Deserialize;

use underreach_sim::net::{send_msg, ClientMsg, ClientState, HostMsg};
use underreach_sim::session::PlayerCommand;
use underreach_sim::world::Pos;

#[derive(Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
enum Directive {
    Submit { commands: Vec<PlayerCommand> },
    RescuePlant { incident: u32, pos: Pos, tier: u8, fuel: f32 },
    Rescue { incident: u32 },
    ExpectSync { hash: String },
    ExpectError,
    LocalDiverge { commands: Vec<PlayerCommand> },
    Quit,
}

struct Client {
    state: ClientState,
    rx: Receiver<HostMsg>,
    writer: Arc<Mutex<TcpStream>>,
    timeout: Duration,
}

impl Client {
    fn out(&self, v: serde_json::Value) {
        println!("{v}");
        let _ = std::io::stdout().flush();
    }

    fn fatal(&self, message: &str) -> ! {
        self.out(serde_json::json!({"type": "fatal", "message": message}));
        std::process::exit(2);
    }

    fn send(&mut self, msg: &ClientMsg) {
        let mut w = self.writer.lock().unwrap();
        if send_msg(&mut *w, msg).is_err() {
            self.fatal("socket write to host failed");
        }
    }

    /// Process one host message. A `Sync` is converged on
    /// (replay + hash check); an `Error` is reported.
    fn handle(&mut self, msg: HostMsg) {
        match msg {
            HostMsg::Sync { log, hash, snapshot } => {
                match self.state.apply_sync(log, hash, snapshot) {
                    Ok(h) => self.out(serde_json::json!({
                        "type": "synced",
                        "hash": h,
                        "tick": self.state.sim.as_ref().map(|s| s.tick_count),
                    })),
                    Err(m) => {
                        self.out(serde_json::json!({"type": "desync", "message": m}));
                        std::process::exit(4);
                    }
                }
            }
            HostMsg::Error { message } => {
                self.out(serde_json::json!({"type": "host_error", "message": message}));
            }
        }
    }

    /// Wait until `cond` holds over the stream of host
    /// messages, handling every message that arrives meanwhile.
    /// Deadline-bound.
    fn wait_until(&mut self, what: &str, cond: &dyn Fn(&Client) -> bool) {
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
                Ok(msg) => self.handle(msg),
                Err(RecvTimeoutError::Timeout) => {
                    self.fatal(&format!("timeout waiting for {what}"))
                }
                Err(RecvTimeoutError::Disconnected) => {
                    self.fatal("host closed the connection while waiting")
                }
            }
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut addr: Option<String> = None;
    let mut player: Option<u8> = None;
    let mut timeout_ms: u64 = 30_000;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--addr" => {
                i += 1;
                addr = args.get(i).cloned();
            }
            "--player" => {
                i += 1;
                player = args.get(i).and_then(|v| v.parse().ok());
            }
            "--timeout-ms" => {
                i += 1;
                timeout_ms = args.get(i).and_then(|v| v.parse().ok()).unwrap_or(30_000);
            }
            other => {
                eprintln!("net_client: unknown argument {other}");
                std::process::exit(64);
            }
        }
        i += 1;
    }
    let addr = addr.unwrap_or_else(|| {
        eprintln!("net_client: --addr is required");
        std::process::exit(64);
    });
    let player = player.unwrap_or_else(|| {
        eprintln!("net_client: --player is required");
        std::process::exit(64);
    });

    let stream = TcpStream::connect(&addr).unwrap_or_else(|e| {
        eprintln!("net_client: cannot connect to {addr}: {e}");
        std::process::exit(2);
    });
    let writer = Arc::new(Mutex::new(stream.try_clone().expect("clone stream")));
    let (tx, rx) = channel::<HostMsg>();
    {
        let mut reader = BufReader::new(stream);
        std::thread::spawn(move || loop {
            match underreach_sim::net::recv_msg::<HostMsg>(&mut reader) {
                Ok(Some(msg)) => {
                    if tx.send(msg).is_err() {
                        return;
                    }
                }
                _ => return,
            }
        });
    }

    let mut client = Client {
        state: ClientState::new(player),
        rx,
        writer,
        timeout: Duration::from_millis(timeout_ms),
    };
    client.send(&ClientMsg::Join { player });
    // The join sync: replay the host's log-so-far and verify.
    client.wait_until("join sync", &|c: &Client| c.state.hash.is_some());
    client.out(serde_json::json!({
        "type": "joined",
        "player": player,
        "hash": client.state.hash,
        "tick": client.state.sim.as_ref().map(|s| s.tick_count),
    }));

    let stdin = std::io::stdin();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            continue;
        }
        let d: Directive = match serde_json::from_str(&line) {
            Ok(d) => d,
            Err(e) => {
                client.out(serde_json::json!({"type": "error", "message": format!("bad directive: {e}")}));
                continue;
            }
        };
        match d {
            Directive::Submit { commands } => {
                client.send(&ClientMsg::Commands { commands });
                client.out(serde_json::json!({"type": "ok", "op": "submit"}));
            }
            Directive::RescuePlant { incident, pos, tier, fuel } => {
                client.send(&ClientMsg::RescuePlant { incident, pos, tier, fuel });
                client.out(serde_json::json!({"type": "ok", "op": "rescue_plant"}));
            }
            Directive::Rescue { incident } => {
                client.send(&ClientMsg::Rescue { incident });
                client.out(serde_json::json!({"type": "ok", "op": "rescue"}));
            }
            Directive::ExpectSync { hash } => {
                let target = hash.clone();
                client.wait_until("expected sync", &move |c: &Client| {
                    c.state.hash.as_deref() == Some(target.as_str())
                });
                client.out(serde_json::json!({"type": "ok", "op": "expect_sync", "hash": hash}));
            }
            Directive::ExpectError => {
                // Errors are printed by `handle` as they arrive;
                // here we only need to drain until one has been
                // seen. Track via a marker: wait for any message
                // by consuming until the channel yields an Error
                // — handled inline because `handle` returns ().
                let deadline = Instant::now() + client.timeout;
                loop {
                    let remaining = deadline.saturating_duration_since(Instant::now());
                    if remaining.is_zero() {
                        client.fatal("timeout waiting for host error");
                    }
                    match client.rx.recv_timeout(remaining) {
                        Ok(HostMsg::Error { message }) => {
                            client.out(serde_json::json!({
                                "type": "ok", "op": "expect_error", "message": message,
                            }));
                            break;
                        }
                        Ok(other) => client.handle(other),
                        Err(RecvTimeoutError::Timeout) => {
                            client.fatal("timeout waiting for host error")
                        }
                        Err(RecvTimeoutError::Disconnected) => {
                            client.fatal("host closed the connection while waiting")
                        }
                    }
                }
            }
            Directive::LocalDiverge { commands } => {
                match client.state.local_diverge(&commands) {
                    Ok(h) => client.out(serde_json::json!({
                        "type": "local_hash",
                        "hash": h,
                        "canonical_hash": client.state.hash,
                    })),
                    Err(m) => {
                        client.out(serde_json::json!({"type": "error", "op": "local_diverge", "message": m}))
                    }
                }
            }
            Directive::Quit => {
                client.out(serde_json::json!({
                    "type": "final",
                    "player": player,
                    "hash": client.state.hash,
                    "tick": client.state.sim.as_ref().map(|s| s.tick_count),
                    "log": client.state.log,
                    "snapshot": client.state.snapshot,
                }));
                std::process::exit(0);
            }
        }
    }
}
