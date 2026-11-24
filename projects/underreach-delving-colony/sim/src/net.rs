//! S17 — loopback transport: the first real multiplayer piece.
//!
//! Two processes — one host, one or more clients — exchanging the
//! S13/S15 session artefacts over a TCP socket bound to
//! **127.0.0.1 only**. Nothing here can reach a LAN or the
//! internet: the host binary binds the loopback interface, and
//! the client binary is only ever pointed at it.
//!
//! ## Authority model (ruling 5, as implemented)
//!
//! The HOST process is the sole authority. It owns the one live
//! [`CoopSession`]; clients own nothing but a *reconstruction*.
//! A client sends its typed commands (the S13 vocabulary,
//! attributed to its player) to the host; the host merges each
//! delivery window under ruling 4's priority (host first, then
//! join order — the exact ordering [`merge_coop_streams`]
//! implements), applies the merged window to its `CoopSession`,
//! and broadcasts the resulting canonical [`SessionLog`] plus
//! the sim's SHA-256 state hash and a snapshot of the co-op
//! rules state. A client converges by *replaying the host's
//! log* through the S13 [`replay`] machinery and checking its
//! replayed hash against the host's hash — a client's local
//! state is canonical only insofar as it is that replay. Any
//! commands a client applies locally on its own (a divergent
//! stream) are simply overwritten by the next host sync.
//!
//! ## Protocol
//!
//! Newline-delimited JSON (one message per line, UTF-8) over
//! TCP — the simplest framing the std library supports, chosen
//! over UDP because the canonical log must arrive complete and
//! in order, and TCP gives both for free. Messages are
//! [`ClientMsg`] (client → host) and [`HostMsg`] (host →
//! client), serde-tagged by `type`.
//!
//! ## Join sync (ruling 5, drop-in)
//!
//! On `Join` the host immediately sends the joining client a
//! full `Sync` — the complete canonical log so far, not a
//! snapshot save. The joiner replays it and lands on the host's
//! exact hash; the same `Sync` is broadcast to everyone after
//! every change, so join sync and steady-state sync are one
//! mechanism.
//!
//! ## Incremental delivery vs `merge_coop_streams`
//!
//! `merge_coop_streams` validates *complete* streams (each
//! player's `seq` from 0, no gaps). A live transport delivers
//! commands in windows, so the host validates each window as a
//! *continuation*: a batch's first `seq` must be exactly the
//! count of that player's commands the host has already
//! accepted (applied + queued), incrementing by 1 — the same
//! no-duplicate, no-gap rule, applied incrementally. A batch
//! that fails validation is refused with a `HostMsg::Error` to
//! the sender only; it never enters the canonical log.
//! [`merge_window`] then orders one window's attributed
//! commands with the identical priority rule
//! `merge_coop_streams` uses (stable sort by
//! `(tick, priority, seq)`).

use std::io::{BufRead, BufReader, Write};

use serde::{Deserialize, Serialize};

use crate::session::{
    replay, AttributedCommand, CoopConfig, CoopEvent, CoopSession, DownedIncident,
    PlayerCommand, PlayerState, SessionLog, SharedCredit,
};
use crate::sim::Sim;
use crate::world::Pos;

/// The only interface the transport binds or dials.
pub const LOOPBACK: &str = "127.0.0.1";

/// Client → host messages.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ClientMsg {
    /// Claim a player slot (1..=4). The host answers with a
    /// full `Sync` (the join sync) or an `Error`.
    Join { player: u8 },
    /// One delivery window of this player's typed commands.
    /// `seq` values must continue the player's accepted stream.
    Commands { commands: Vec<PlayerCommand> },
    /// Plant light to stretch a downed player's clock
    /// (ruling 2), as the S15 `CoopSession::rescue_plant_light`.
    RescuePlant { incident: u32, pos: Pos, tier: u8, fuel: f32 },
    /// Run a lantern-clock rescue (ruling 2), as the S15
    /// `CoopSession::run_rescue`.
    Rescue { incident: u32 },
}

/// A serializable snapshot of the co-op rules layer's state —
/// everything about a `CoopSession` that is *not* in the sim
/// log (roster, incidents, events, shared credit). Built from
/// the session's public getters; the client holds it as
/// received truth from the host, while its *sim* state is
/// always its own replay of the log.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct CoopSnapshot {
    pub config: CoopConfig,
    pub join_order: Vec<u8>,
    pub players: Vec<PlayerState>,
    pub incidents: Vec<DownedIncident>,
    pub events: Vec<CoopEvent>,
    pub credits: Vec<SharedCredit>,
    pub run_over: bool,
    pub paused: bool,
}

impl CoopSnapshot {
    pub fn of(session: &CoopSession) -> Self {
        let players = (1..=crate::session::MAX_PLAYERS)
            .filter_map(|p| session.player(p).cloned())
            .collect();
        CoopSnapshot {
            config: session.config(),
            join_order: session.join_order().to_vec(),
            players,
            incidents: session.incidents().to_vec(),
            events: session.events().to_vec(),
            credits: session.shared_credits().to_vec(),
            run_over: session.run_over(),
            paused: session.is_paused(),
        }
    }
}

/// Host → client messages.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum HostMsg {
    /// The canonical state of the session: the full session
    /// log, the host's state hash for it, and the co-op rules
    /// snapshot. Sent to a joiner on `Join` and broadcast to
    /// every client after every accepted change.
    Sync { log: SessionLog, hash: String, snapshot: CoopSnapshot },
    /// A refusal addressed to one client (bad player id, a
    /// `seq` gap in a command batch, a refused rescue action).
    /// The canonical log is unchanged by anything that earns
    /// an `Error`.
    Error { message: String },
}

/// Write one NDJSON message (a single JSON line) and flush.
pub fn send_msg<T: Serialize>(w: &mut impl Write, msg: &T) -> std::io::Result<()> {
    let mut line = serde_json::to_string(msg).expect("protocol serialization is infallible");
    line.push('\n');
    w.write_all(line.as_bytes())?;
    w.flush()
}

/// Read one NDJSON message from a buffered reader. `Ok(None)`
/// is a clean end of stream (the peer closed the connection).
pub fn recv_msg<T: for<'de> Deserialize<'de>>(
    r: &mut BufReader<impl std::io::Read>,
) -> std::io::Result<Option<T>> {
    loop {
        let mut line = String::new();
        if r.read_line(&mut line)? == 0 {
            return Ok(None);
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        return serde_json::from_str(trimmed).map(Some).map_err(std::io::Error::other);
    }
}

/// Ruling 4's priority for one player: the host first (0), then
/// join order, then anyone not in the order by id — copied from
/// `merge_coop_streams`, whose stable re-prioritisation this
/// mirrors for a single delivery window.
fn priority_of(player: u8, host: u8, join_order: &[u8]) -> (usize, u8) {
    if player == host {
        (0, 0)
    } else if let Some(i) = join_order.iter().position(|j| *j == player) {
        (1 + i, 0)
    } else {
        (usize::MAX, player)
    }
}

/// Order one delivery window's per-player batches into the
/// canonical sequence for that window: a stable sort by
/// `(tick, host/join-order priority, seq)` — ruling 4, exactly
/// as `merge_coop_streams` orders a whole session's streams.
/// Batches must already have passed
/// [`validate_continuation`]; the caller applies the result
/// through `CoopSession::apply_entry` in order, so a contested
/// loser's command is applied after the winner's spend and is
/// recorded `applied: false` by the session itself — the quiet
/// failure, identically on every peer that replays the log.
pub fn merge_window(
    batches: &[(u8, Vec<PlayerCommand>)],
    host: u8,
    join_order: &[u8],
) -> Vec<AttributedCommand> {
    let mut merged: Vec<AttributedCommand> = Vec::new();
    for (player, cmds) in batches {
        merged.extend(cmds.iter().map(|c| AttributedCommand {
            tick: c.tick,
            player: *player,
            seq: c.seq,
            command: c.command.clone(),
        }));
    }
    merged.sort_by_key(|e| (e.tick, priority_of(e.player, host, join_order), e.seq));
    merged
}

/// The incremental form of `merge_streams`' seq validation: a
/// batch from `player` must continue exactly where the host's
/// accepted stream for that player left off (`already` =
/// applied + queued commands), incrementing by 1 per command.
/// Duplicates and gaps are refused, never repaired.
pub fn validate_continuation(
    player: u8,
    commands: &[PlayerCommand],
    already: u32,
) -> Result<(), String> {
    for (i, c) in commands.iter().enumerate() {
        let expected = already + i as u32;
        if c.seq != expected {
            return Err(format!(
                "player {player}'s batch jumps: expected seq {expected}, found seq {}",
                c.seq
            ));
        }
    }
    Ok(())
}

/// The client's side of the bargain: everything a client holds
/// that it is entitled to believe. The sim is *only* ever the
/// replay of the last host log received; `hash` is the host's
/// hash that replay reproduced.
pub struct ClientState {
    pub player: u8,
    pub log: Option<SessionLog>,
    pub sim: Option<Sim>,
    pub hash: Option<String>,
    pub snapshot: Option<CoopSnapshot>,
}

impl ClientState {
    pub fn new(player: u8) -> Self {
        ClientState { player, log: None, sim: None, hash: None, snapshot: None }
    }

    /// Converge on a host `Sync`: replay its log through the
    /// S13 machinery and require the replayed hash to equal
    /// the host's stated hash. On success the client's
    /// canonical state *is* this replay — whatever it held
    /// before (including any locally applied divergent
    /// commands) is discarded. On mismatch nothing is stored:
    /// a desync is named, never papered over.
    pub fn apply_sync(
        &mut self,
        log: SessionLog,
        hash: String,
        snapshot: CoopSnapshot,
    ) -> Result<String, String> {
        let sim = replay(&log).map_err(|e| format!("host log does not replay: {e}"))?;
        let replayed = sim.state_hash();
        if replayed != hash {
            return Err(format!(
                "desync: replayed hash {replayed} != host hash {hash}"
            ));
        }
        self.log = Some(log);
        self.sim = Some(sim);
        self.hash = Some(hash.clone());
        self.snapshot = Some(snapshot);
        Ok(hash)
    }

    /// Apply commands to a *local, non-canonical* copy of the
    /// current state (what a client-side prediction or a
    /// divergent stream would do) and return the resulting
    /// hash. The stored canonical state is untouched — this
    /// exists so tests can prove a divergent local stream does
    /// not move the converged result: the next `apply_sync`
    /// replaces it wholesale.
    pub fn local_diverge(&mut self, commands: &[PlayerCommand]) -> Result<String, String> {
        let log = self.log.clone().ok_or("no canonical log yet")?;
        let sim = replay(&log).map_err(|e| format!("canonical log does not replay: {e}"))?;
        let mut session = crate::session::Session::new(sim);
        for c in commands {
            session
                .apply_entry(&AttributedCommand {
                    tick: c.tick,
                    player: self.player,
                    seq: c.seq,
                    command: c.command.clone(),
                })
                .map_err(|e| format!("local command refused: {e}"))?;
        }
        Ok(session.sim().state_hash())
    }
}
